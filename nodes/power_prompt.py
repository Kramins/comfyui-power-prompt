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
        var_state_dict = self._parse_var_state(var_state)
        doc, variables, prompt_template, includes = self._load_and_parse_yaml(yaml_input, kwargs)
        context = self._resolve_all_variables(variables, var_state_dict, seed)
        return self._render_fragments_and_prompt(doc, includes, context, prompt_template)

    # ------------------------------------------------------------------
    # Pipeline stages
    # ------------------------------------------------------------------

    def _parse_var_state(self, var_state: str) -> dict:
        """Decode the JSON var_state string into a dict; returns {} on missing or malformed input."""
        try:
            return json.loads(var_state) if var_state else {}
        except json.JSONDecodeError:
            return {}

    def _load_and_parse_yaml(
        self, yaml_input: str, kwargs: dict
    ) -> tuple[dict, dict, str, list[str]]:
        """Collect include files, combine them with the main YAML, parse the document,
        and return (doc, variables, prompt_template, includes)."""
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

        return doc, variables, prompt_template, includes

    @staticmethod
    def _parse_select_options(
        var_name: str, options_raw: list
    ) -> tuple[list[tuple[str, float, str, str]], dict[str, list]]:
        """Parse raw option entries into (value, weight, when, unless) tuples and a tags lookup."""
        all_opts: list[tuple[str, float, str, str]] = []
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
        return all_opts, tags_by_value

    def _resolve_all_variables(
        self, variables: dict, var_state_dict: dict, seed: int
    ) -> dict:
        """Resolve every variable definition into concrete values and return the Jinja2 context.

        Iterates variables in declaration order. Each resolved value is immediately available
        to when/unless conditions on subsequent variables. Tags accumulate the same way via a
        live list aliased into eval_context["tags"]."""
        # Two parallel contexts: `context` is what Jinja2 templates see (always strings);
        # `eval_context` is what when/unless expressions see (lists for multi-pick variables).
        context: dict = {}
        eval_context: dict = {}

        # Tags accumulate as variables are resolved so later when/unless conditions can
        # filter on tags chosen by earlier variables. The live list alias means any append
        # to _accumulated_tags is immediately visible through eval_context["tags"].
        _global_tags_seen: set[str] = set()
        _accumulated_tags: list[str] = []
        if "tags" not in variables:
            eval_context["tags"] = _accumulated_tags  # live reference, not a copy

        for var_name, var_def in variables.items():
            if not isinstance(var_def, dict):
                raise ValueError(f"Variable '{var_name}' definition must be a mapping.")
            var_type = var_def.get("type")

            if var_type in ("select", "choice", "multiselect"):
                options_raw = var_def.get("options", [])
                if not options_raw:
                    raise ValueError(f"Variable '{var_name}' has no options.")

                # Step 1 — parse raw option entries into typed tuples.
                all_opts, tags_by_value = self._parse_select_options(var_name, options_raw)

                # Step 2 — determine how many values to pick.
                # "choice" and "multiselect" are legacy aliases for count=1 and count=any.
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

                # Step 3 — filter options by when/unless against variables resolved so far.
                # User-provided values skip this; filtering only applies to random selection.
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

                # Step 4 — pick value(s) and write into both contexts.
                # Single pick: use user value if provided, otherwise sample with seeded RNG.
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

                # "any" pick: all selections come from the user; no random sampling.
                elif is_any:
                    selected = [str(v) for v in (user_value if isinstance(user_value, list) else [])]
                    context[var_name] = ", ".join(selected)
                    eval_context[var_name] = selected
                    eval_context[f"{var_name}_tags"] = _merge_tags(selected, tags_by_value)
                    for _t in eval_context[f"{var_name}_tags"]:
                        if _t not in _global_tags_seen:
                            _global_tags_seen.add(_t)
                            _accumulated_tags.append(_t)

                # Range pick: use user list if provided, otherwise sample k within [min, max].
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

            # Text variables carry a free-form string typed by the user; no sampling.
            elif var_type == "text":
                val = str(var_state_dict.get(var_name, ""))
                context[var_name] = val
                eval_context[var_name] = val

            else:
                raise ValueError(f"Unknown variable type '{var_type}' for '{var_name}'.")

        # Copy per-variable tag lists into the template context so fragments and the
        # prompt can reference e.g. {{ subject_tags }}. Also snapshot the global tags list.
        for k, v in eval_context.items():
            if k.endswith("_tags"):
                context[k] = v
        if "tags" not in variables:
            context["tags"] = list(_accumulated_tags)

        return context

    def _render_fragments_and_prompt(
        self, doc: dict, includes: list[str], context: dict, prompt_template: str
    ) -> tuple[str, str]:
        """Render fragments incrementally (each can reference earlier ones), then render the
        final prompt template. Returns (normalized_prompt, raw_prompt)."""
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
