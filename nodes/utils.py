import hashlib
import logging
import random
import re

import jinja2
import yaml
from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment, SecurityError as JinjaSecurityError

logger = logging.getLogger(__name__)

# Sandbox for evaluating when/unless expressions. SandboxedEnvironment blocks
# unsafe attribute access (e.g. ().__class__.__bases__) at the Jinja2 layer.
# StrictUndefined raises immediately when a variable is referenced but not in context.
_when_sandbox = SandboxedEnvironment(undefined=StrictUndefined)
_when_sandbox.globals.update({
    "len": len,
    "any": any,
    "all": all,
    "min": min,
    "max": max,
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "abs": abs,
    "round": round,
})


def _parse_count(count_raw, option_count: int) -> tuple[int, int]:
    if count_raw is None or str(count_raw).lower() == "any":
        return 0, option_count
    s = str(count_raw)
    if "-" in s:
        lo_s, hi_s = s.split("-", 1)
        lo = int(lo_s.strip()) if lo_s.strip() else 0
        hi = int(hi_s.strip()) if hi_s.strip() else option_count
        return lo, min(hi, option_count)
    try:
        n = int(count_raw)
        return n, n
    except (ValueError, TypeError):
        return 0, option_count


def _weighted_sample(options: list, weights: list, k: int, rng: random.Random) -> list:
    """Sample k items without replacement using weights."""
    opts, wts = list(options), list(weights)
    result = []
    for _ in range(min(k, len(opts))):
        total = sum(wts)
        r = rng.random() * total
        cumulative = 0.0
        for i, w in enumerate(wts):
            cumulative += w
            if r <= cumulative:
                result.append(opts.pop(i))
                wts.pop(i)
                break
    return result


def _var_rng(seed: int, var_name: str) -> random.Random:
    """Return a deterministic RNG for a given seed+variable combination.

    Uses SHA-256 instead of Python's hash() so results are consistent across
    processes regardless of PYTHONHASHSEED.
    """
    digest = hashlib.sha256(f"{seed}:{var_name}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "little"))


def _merge_include_variables(includes: list) -> dict:
    """Parse and merge variables from partial YAML strings. Later entries override earlier ones."""
    merged = {}
    for inc in includes:
        if not inc or not str(inc).strip():
            continue
        try:
            doc = yaml.safe_load(inc)
            if isinstance(doc, dict):
                vars_ = doc.get("variables", {})
                if isinstance(vars_, dict):
                    merged.update(vars_)
        except yaml.YAMLError:
            pass
    return merged


def _merge_include_fragments(includes: list) -> dict:
    """Parse and merge fragments from partial YAML strings. Later entries override earlier ones."""
    merged = {}
    for inc in includes:
        if not inc or not str(inc).strip():
            continue
        try:
            doc = yaml.safe_load(inc)
            if isinstance(doc, dict):
                frags = doc.get("fragments", {})
                if isinstance(frags, dict):
                    merged.update(frags)
        except yaml.YAMLError:
            pass
    return merged


def _merge_tags(values: list, tags_by_value: dict) -> list:
    """Return the ordered union of tags for a list of resolved values."""
    seen, result = set(), []
    for v in values:
        for t in tags_by_value.get(v, []):
            if t not in seen:
                seen.add(t)
                result.append(t)
    return result


def _evaluate_when(expr, context: dict, field: str = "when") -> bool:
    """Evaluate a when/unless expression against a resolved context.

    Returns True for empty/None expressions. Raises ValueError on syntax or
    runtime errors so callers can surface a meaningful message to the user.
    """
    if not expr or not str(expr).strip():
        return True
    try:
        compiled = _when_sandbox.compile_expression(str(expr), undefined_to_none=False)
        result = bool(compiled(**context))
        logger.debug("  %s(%r) → %s", field, expr, result)
        return result
    except JinjaSecurityError as e:
        raise ValueError(f"Security violation in {field} expression: {e}") from e
    except jinja2.TemplateSyntaxError as e:
        raise ValueError(f"Invalid {field} expression syntax: {e}") from e
    except jinja2.UndefinedError as e:
        raise ValueError(str(e)) from e
    except Exception as e:
        raise ValueError(str(e)) from e


def _strip_prompt_comments(text: str) -> str:
    """Strip full-line # comments from the prompt template before Jinja2 rendering."""
    return '\n'.join(line for line in text.split('\n') if not line.lstrip().startswith('#'))


def _normalize_prompt(text: str) -> str:
    text = re.sub(r'[\r\n]+', ' ', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\s*,\s*', ',', text)
    text = re.sub(r',+', ',', text)
    text = re.sub(r',', ', ', text)
    return text.strip().strip(',').strip()
