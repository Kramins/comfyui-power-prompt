from __future__ import annotations

from typing import Literal, Optional

import yaml
from pydantic import BaseModel

from .utils import _collect_imports, _merge_include_variables


class ControlDefinition(BaseModel):
    name: str
    label: str
    group: Optional[str] = None
    hidden: bool = False
    widget: Literal["dropdown", "checkboxes", "text"]
    options: list[str] = []
    is_any: bool = False
    count_hint: Optional[str] = None


class UIDefinitionRequest(BaseModel):
    yaml: str
    includes: list[str] = []


class UIDefinitionResponse(BaseModel):
    controls: list[ControlDefinition]
    error: Optional[str] = None


def _derive_label(name: str, var_def: dict) -> str:
    label = var_def.get("label")
    if label:
        return str(label)
    return name.replace("_", " ")


def _extract_option_values(options_raw: list) -> list[str]:
    result = []
    for opt in options_raw:
        if isinstance(opt, dict):
            raw = opt.get("value", "")
            values = raw if isinstance(raw, list) else [raw]
            for v in values:
                if v is not None and str(v).strip():
                    result.append(str(v))
        elif opt is not None and str(opt).strip():
            result.append(str(opt))
    return result


def _is_any_for(var_def: dict) -> bool:
    var_type = var_def.get("type")
    if var_type == "multiselect":
        return True
    if var_type in ("text", "choice"):
        return False
    count_raw = var_def.get("count", 1)
    return count_raw is None or str(count_raw).lower() == "any"


def _count_hint_for(var_def: dict, widget: str, is_any: bool) -> Optional[str]:
    if widget != "checkboxes" or is_any:
        return None
    count_raw = var_def.get("count", 1)
    if count_raw is None:
        return None
    s = str(count_raw)
    return None if s.lower() == "any" else s


def _widget_for(var_def: dict) -> Literal["dropdown", "checkboxes", "text"]:
    var_type = var_def.get("type")
    if var_type == "text":
        return "text"
    if var_type == "multiselect":
        return "checkboxes"
    if var_type == "choice":
        return "dropdown"
    # select
    count_raw = var_def.get("count", 1)
    if count_raw is None or str(count_raw).lower() == "any":
        return "checkboxes"
    s = str(count_raw)
    if "-" in s:
        return "checkboxes"
    try:
        n = int(count_raw)
        return "dropdown" if n == 1 else "checkboxes"
    except (ValueError, TypeError):
        return "checkboxes"


def build_ui_definition(yaml_input: str, includes: list[str]) -> UIDefinitionResponse:
    """Parse a Power Prompt YAML and return a UI control definition for the frontend.

    Resolves imports transitively, merges all variable sources in priority order
    (imports < wired includes < main YAML), and returns an ordered list of controls.
    Does not evaluate when/unless — all options are returned unfiltered.
    """
    try:
        wired_includes = [inc for inc in includes if inc and inc.strip()]
        import_includes = _collect_imports(yaml_input, wired_includes)

        _wired_vars = _merge_include_variables(wired_includes)
        _import_vars = _merge_include_variables(import_includes)
        merged: dict = dict(_wired_vars)
        for k, v in _import_vars.items():
            if k not in merged:
                merged[k] = v

        try:
            doc = yaml.safe_load(yaml_input) or {}
        except yaml.YAMLError as e:
            return UIDefinitionResponse(controls=[], error=f"Invalid YAML: {e}")

        if not isinstance(doc, dict):
            return UIDefinitionResponse(controls=[], error="YAML must be a mapping at the top level.")

        merged.update(doc.get("variables", {}) or {})

        controls: list[ControlDefinition] = []
        for var_name, var_def in merged.items():
            if not isinstance(var_def, dict):
                continue
            var_type = var_def.get("type")
            if var_type not in ("select", "choice", "multiselect", "text"):
                continue

            options: list[str] = []
            if var_type in ("select", "choice", "multiselect"):
                options = _extract_option_values(var_def.get("options") or [])

            widget = _widget_for(var_def)
            is_any = _is_any_for(var_def)
            controls.append(ControlDefinition(
                name=var_name,
                label=_derive_label(var_name, var_def),
                group=var_def.get("group") or None,
                hidden=bool(var_def.get("hidden", False)),
                widget=widget,
                options=options,
                is_any=is_any,
                count_hint=_count_hint_for(var_def, widget, is_any),
            ))

        return UIDefinitionResponse(controls=controls)

    except ValueError as e:
        return UIDefinitionResponse(controls=[], error=str(e))
    except Exception as e:
        return UIDefinitionResponse(controls=[], error=f"Unexpected error: {e}")
