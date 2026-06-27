from .power_prompt import PowerPromptNode
from .power_prompt_partial import PowerPromptPartial
from .power_prompt_file_partial import PowerPromptFilePartial

NODE_CLASS_MAPPINGS = {
    "PowerPromptNode": PowerPromptNode,
    "PowerPromptPartial": PowerPromptPartial,
    "PowerPromptFilePartial": PowerPromptFilePartial,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "PowerPromptNode": "Power Prompt",
    "PowerPromptPartial": "Power Prompt Partial",
    "PowerPromptFilePartial": "Power Prompt File Partial",
}
