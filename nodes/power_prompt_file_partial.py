import logging
import pathlib

import jinja2
import yaml
from jinja2 import BaseLoader, Environment

from .utils import _strip_prompt_comments

logger = logging.getLogger(__name__)


class PowerPromptFilePartial:
    CATEGORY = "prompt"
    RETURN_TYPES = ("POWER_PROMPT_PARTIAL",)
    RETURN_NAMES = ("partial",)
    FUNCTION = "generate"

    @classmethod
    def INPUT_TYPES(cls):
        files = []
        try:
            import folder_paths
            files = folder_paths.get_filename_list("power_prompt_partials")
        except Exception:
            pass
        return {
            "required": {
                "partial_file": (files or [""],),
            },
            "optional": {
                # yaml_input is kept in sync by the frontend after each file load so that
                # getIncludeVariables / getIncludeRawYaml on the main node can read partial
                # variables for building UI controls. generate() always reads fresh from disk.
                "yaml_input": ("STRING", {"default": "", "multiline": True, "hidden": True}),
            },
        }

    def generate(self, partial_file, yaml_input=""):
        if not partial_file or not partial_file.strip():
            raise ValueError("Power Prompt File Partial: no file path provided.")
        p = pathlib.Path(partial_file)
        if p.is_absolute():
            # Absolute path — used by tests and any direct fallback
            path = p
        else:
            try:
                import folder_paths
                resolved = folder_paths.get_full_path("power_prompt_partials", partial_file)
            except Exception:
                resolved = None
            if not resolved:
                raise ValueError(
                    f"Power Prompt File Partial: '{partial_file}' not found in the "
                    "power-prompt partials folder."
                )
            path = pathlib.Path(resolved)

        try:
            content = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise ValueError(f"Power Prompt File Partial: file not found: {path}")
        except OSError as e:
            raise ValueError(f"Power Prompt File Partial: could not read file: {e}")

        try:
            doc = yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise ValueError(f"Power Prompt File Partial: invalid YAML in {path}: {e}")

        doc = doc or {}
        if not isinstance(doc, dict):
            raise ValueError(
                f"Power Prompt File Partial: {path} must be a YAML mapping at the top level."
            )
        if "variables" in doc and not isinstance(doc["variables"], dict):
            raise ValueError(f"Power Prompt File Partial: 'variables' in {path} must be a mapping.")
        if "fragments" in doc and not isinstance(doc["fragments"], dict):
            raise ValueError(f"Power Prompt File Partial: 'fragments' in {path} must be a mapping.")

        fragments = doc.get("fragments", {})
        if fragments:
            frag_env = Environment(loader=BaseLoader())
            for frag_name, frag_raw in fragments.items():
                try:
                    frag_env.from_string(_strip_prompt_comments(str(frag_raw)))
                except jinja2.TemplateSyntaxError as e:
                    raise ValueError(
                        f"Power Prompt File Partial: fragment '{frag_name}' in {path} "
                        f"has invalid Jinja2 template: {e}"
                    ) from e

        logger.debug("[PowerPromptFilePartial] loaded %s (%d bytes)", path, len(content))
        return (content,)
