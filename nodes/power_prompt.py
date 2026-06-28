import json
import logging

import jinja2
import yaml
from jinja2 import BaseLoader, Environment, StrictUndefined

from .utils import (
    _evaluate_when,
    _merge_include_fragments,
    _merge_include_variables,
    _merge_tags,
    _normalize_prompt,
    _parse_count,
    _strip_prompt_comments,
    _var_rng,
    _weighted_sample,
)

logger = logging.getLogger(__name__)

DEFAULT_YAML = """\
variables:
  subject:
    type: select
    count: 1
    options:
      - 1girl
      - 1boy

  art_style:
    type: select
    count: 1
    options:
      - anime
      - oil painting
      - watercolor sketch

  mood:
    type: text

prompt: |
  {{ subject }}, {{ art_style }},
  {% if mood %}{{ mood }},{% endif %}
  masterpiece, best quality
"""


class PowerPromptNode:
    CATEGORY = "prompt"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("prompt", "raw_prompt")
    FUNCTION = "generate"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "yaml_input": ("STRING", {
                    "multiline": True,
                    "default": DEFAULT_YAML,
                }),
                "var_state": ("STRING", {
                    "default": "{}",
                }),
                "seed": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 0xFFFFFFFFFFFFFFFF,
                }),
            },
        }

    def generate(self, yaml_input, var_state, seed, **kwargs):
        try:
            var_state_dict = json.loads(var_state) if var_state else {}
        except json.JSONDecodeError:
            var_state_dict = {}

        includes = [v for k, v in sorted(kwargs.items()) if k.startswith("include_") and v]
        base_variables = _merge_include_variables(includes)

        # Prepend partial texts so YAML anchors defined in partials are visible when the
        # main YAML is parsed. Duplicate top-level keys (e.g. `variables:`) resolve to the
        # last occurrence, so doc.get("variables") still returns the main document's block.
        prefix = "\n".join(inc for inc in includes if inc and inc.strip())
        combined_input = (prefix + "\n" + yaml_input) if prefix else yaml_input
        try:
            doc = yaml.safe_load(combined_input)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML: {e}")

        if not isinstance(doc, dict):
            raise ValueError("YAML must be a mapping at the top level.")
        base_variables.update(doc.get("variables", {}))
        variables = base_variables
        prompt_template = doc.get("prompt", "")

        if not isinstance(variables, dict):
            raise ValueError("'variables' must be a mapping.")
        if not prompt_template:
            raise ValueError("'prompt' key is missing or empty.")

        context = {}      # Jinja2 template context — always strings
        eval_context = {} # when expression context — strings for single-pick, lists for multi-pick

        _global_tags_seen: set[str] = set()
        _accumulated_tags: list[str] = []
        if "tags" not in variables:
            # Live reference — appends to _accumulated_tags are visible in when/unless expressions.
            eval_context["tags"] = _accumulated_tags

        for var_name, var_def in variables.items():
            if not isinstance(var_def, dict):
                raise ValueError(f"Variable '{var_name}' definition must be a mapping.")
            var_type = var_def.get("type")

            if var_type in ("select", "choice", "multiselect"):
                options_raw = var_def.get("options", [])
                if not options_raw:
                    raise ValueError(f"Variable '{var_name}' has no options.")

                # Parse options — extract value, weight, when, and tags.
                # value and tags each accept a scalar or a list.
                all_opts = []
                tags_by_value: dict[str, list] = {}
                for opt in options_raw:
                    if isinstance(opt, dict):
                        raw_value = opt.get("value", "")
                        try:
                            weight = float(opt.get("weight", 1.0))
                        except (ValueError, TypeError):
                            raise ValueError(
                                f"Weight for an option in variable '{var_name}' must be a "
                                f"number, got {opt.get('weight')!r}"
                            )
                        when = str(opt.get("when") or "")
                        unless = str(opt.get("unless") or "")
                        raw_tags = opt.get("tags", [])
                        tags = ([str(t) for t in raw_tags] if isinstance(raw_tags, list)
                                else ([str(raw_tags)] if raw_tags else []))
                        values = raw_value if isinstance(raw_value, list) else [raw_value]
                        for v in values:
                            if v is None:
                                continue
                            v_str = str(v)
                            all_opts.append((v_str, weight, when, unless))
                            tags_by_value[v_str] = tags
                    else:
                        v_str = str(opt)
                        all_opts.append((v_str, 1.0, "", ""))
                        tags_by_value[v_str] = []

                # Normalise legacy types
                if var_type == "choice":
                    count_raw = 1
                elif var_type == "multiselect":
                    count_raw = "any"
                else:
                    count_raw = var_def.get("count", 1)

                is_any = count_raw is None or str(count_raw).lower() == "any"
                count_min, count_max = _parse_count(count_raw, len(all_opts))
                is_single = count_min == 1 and count_max == 1

                user_value = var_state_dict.get(var_name)

                # Filter options by when/unless conditions against already-resolved eval_context.
                # User-selected values bypass this — filtering is for random resolution only.
                logger.debug("[PowerPrompt] resolving '%s' | context: %s", var_name,
                             {k: v for k, v in eval_context.items()})
                filtered = []
                for opt_name, opt_weight, when_expr, unless_expr in all_opts:
                    try:
                        include = _evaluate_when(when_expr, eval_context)
                        if include and unless_expr:
                            include = not _evaluate_when(unless_expr, eval_context, field="unless")
                        if include:
                            filtered.append((opt_name, opt_weight))
                    except ValueError as e:
                        raise ValueError(
                            f"Invalid 'when'/'unless' expression for option '{opt_name}' "
                            f"in variable '{var_name}': {e}"
                        ) from e
                if not filtered:
                    logger.debug(
                        "[PowerPrompt] variable '%s': all options excluded by when/unless "
                        "— variable will be empty", var_name
                    )
                    context[var_name] = ""
                    eval_context[var_name] = "" if is_single else []
                    eval_context[f"{var_name}_tags"] = []
                    continue

                f_options = [f[0] for f in filtered]
                f_weights = [f[1] for f in filtered]

                if is_single:
                    if user_value and user_value != "random":
                        val = str(user_value)
                    else:
                        rng = _var_rng(seed, var_name)
                        val = _weighted_sample(f_options, f_weights, 1, rng)[0]
                    context[var_name] = val
                    eval_context[var_name] = val
                    eval_context[f"{var_name}_tags"] = tags_by_value.get(val, [])
                    for _t in eval_context[f"{var_name}_tags"]:
                        if _t not in _global_tags_seen:
                            _global_tags_seen.add(_t)
                            _accumulated_tags.append(_t)

                elif is_any:
                    selected = [str(v) for v in (user_value if isinstance(user_value, list) else [])]
                    context[var_name] = ", ".join(selected)
                    eval_context[var_name] = selected
                    eval_context[f"{var_name}_tags"] = _merge_tags(selected, tags_by_value)
                    for _t in eval_context[f"{var_name}_tags"]:
                        if _t not in _global_tags_seen:
                            _global_tags_seen.add(_t)
                            _accumulated_tags.append(_t)

                else:
                    if isinstance(user_value, list) and len(user_value) > 0:
                        picked = [str(v) for v in user_value]
                    else:
                        rng = _var_rng(seed, var_name)
                        k = rng.randint(count_min, count_max) if count_min != count_max else count_min
                        picked = _weighted_sample(f_options, f_weights, k, rng)
                    context[var_name] = ", ".join(picked)
                    eval_context[var_name] = picked
                    eval_context[f"{var_name}_tags"] = _merge_tags(picked, tags_by_value)
                    for _t in eval_context[f"{var_name}_tags"]:
                        if _t not in _global_tags_seen:
                            _global_tags_seen.add(_t)
                            _accumulated_tags.append(_t)

            elif var_type == "text":
                val = str(var_state_dict.get(var_name, ""))
                context[var_name] = val
                eval_context[var_name] = val

            else:
                raise ValueError(f"Unknown variable type '{var_type}' for '{var_name}'.")

        # Expose _tags lists to Jinja2 templates (fragments and prompt).
        # eval_context holds tags for when/unless filtering; context is the
        # template render context — without this, _tags are unreachable in fragments.
        for k, v in eval_context.items():
            if k.endswith("_tags"):
                context[k] = v
        if "tags" not in variables:
            context["tags"] = list(_accumulated_tags)

        # Collect fragments from includes, then let the main doc override.
        all_fragments = _merge_include_fragments(includes)
        main_fragments = doc.get("fragments", {})
        if isinstance(main_fragments, dict):
            all_fragments.update(main_fragments)

        # Render fragments in merge order so each fragment can reference earlier ones
        # via {{ fragment.name }}. The growing dict is passed into each render call.
        rendered_fragments: dict[str, str] = {}
        if all_fragments:
            frag_env = Environment(loader=BaseLoader(), undefined=StrictUndefined)
            for frag_name, frag_raw in all_fragments.items():
                frag_tmpl = _strip_prompt_comments(str(frag_raw))
                render_ctx = {**context, "fragment": rendered_fragments}
                try:
                    rendered_fragments[str(frag_name)] = (
                        frag_env.from_string(frag_tmpl).render(**render_ctx).strip()
                    )
                    logger.debug(
                        "[PowerPrompt] rendered fragment '%s': %r",
                        frag_name, rendered_fragments[str(frag_name)],
                    )
                except jinja2.UndefinedError as e:
                    raise ValueError(
                        f"Fragment '{frag_name}' references undefined variable: {e}"
                    ) from e
                except jinja2.TemplateSyntaxError as e:
                    raise ValueError(
                        f"Fragment '{frag_name}' has invalid Jinja2 template: {e}"
                    ) from e
        context["fragment"] = rendered_fragments

        prompt_template = _strip_prompt_comments(prompt_template)
        env = Environment(loader=BaseLoader(), undefined=StrictUndefined)

        try:
            template = env.from_string(prompt_template)
            rendered = template.render(**context)
        except jinja2.TemplateSyntaxError as e:
            raise ValueError(f"Invalid Jinja template: {e}")
        except jinja2.UndefinedError as e:
            raise ValueError(f"Template references undefined variable: {e}")

        prompt = rendered.strip()
        return (_normalize_prompt(prompt), prompt)
