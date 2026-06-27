import logging

import jinja2
import yaml
from jinja2 import BaseLoader, Environment

from .utils import _strip_prompt_comments

logger = logging.getLogger(__name__)

DEFAULT_PARTIAL_YAML = """\
variables:
  hair_color:
    type: select
    count: 1
    options:
      - black
      - blonde
      - silver

fragments:
  appearance: "{{ hair_color }} hair"
"""


class PowerPromptPartial:
    CATEGORY = "prompt"
    RETURN_TYPES = ("POWER_PROMPT_PARTIAL",)
    RETURN_NAMES = ("partial",)
    FUNCTION = "generate"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "yaml_input": ("STRING", {
                    "multiline": True,
                    "default": DEFAULT_PARTIAL_YAML,
                }),
            },
        }

    def generate(self, yaml_input):
        try:
            doc = yaml.safe_load(yaml_input)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid partial YAML: {e}")

        doc = doc or {}
        if not isinstance(doc, dict):
            raise ValueError("Partial YAML must be a mapping at the top level.")
        if "variables" in doc and not isinstance(doc["variables"], dict):
            raise ValueError("'variables' must be a mapping.")
        if "fragments" in doc and not isinstance(doc["fragments"], dict):
            raise ValueError("'fragments' must be a mapping.")

        fragments = doc.get("fragments", {})
        if fragments:
            frag_env = Environment(loader=BaseLoader())
            for frag_name, frag_raw in fragments.items():
                try:
                    frag_env.from_string(_strip_prompt_comments(str(frag_raw)))
                except jinja2.TemplateSyntaxError as e:
                    raise ValueError(
                        f"Fragment '{frag_name}' has invalid Jinja2 template: {e}"
                    ) from e

        return (yaml_input,)
