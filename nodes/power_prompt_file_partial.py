import logging

import jinja2
import yaml
from jinja2 import BaseLoader, Environment

from .utils import _load_partials_file, _strip_prompt_comments

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
        content = _load_partials_file(partial_file)

        try:
            doc = yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise ValueError(f"Power Prompt File Partial: invalid YAML in {partial_file}: {e}")

        doc = doc or {}
        if not isinstance(doc, dict):
            raise ValueError(
                f"Power Prompt File Partial: {partial_file} must be a YAML mapping at the top level."
            )
        if "variables" in doc and not isinstance(doc["variables"], dict):
            raise ValueError(f"Power Prompt File Partial: 'variables' in {partial_file} must be a mapping.")
        if "fragments" in doc and not isinstance(doc["fragments"], dict):
            raise ValueError(f"Power Prompt File Partial: 'fragments' in {partial_file} must be a mapping.")

        fragments = doc.get("fragments", {})
        if fragments:
            frag_env = Environment(loader=BaseLoader())
            for frag_name, frag_raw in fragments.items():
                try:
                    frag_env.from_string(_strip_prompt_comments(str(frag_raw)))
                except jinja2.TemplateSyntaxError as e:
                    raise ValueError(
                        f"Power Prompt File Partial: fragment '{frag_name}' in {partial_file} "
                        f"has invalid Jinja2 template: {e}"
                    ) from e

        logger.debug("[PowerPromptFilePartial] loaded %s (%d bytes)", partial_file, len(content))
        return (content,)
