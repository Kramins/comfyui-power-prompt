from .power_prompt import PowerPromptNode
from .power_prompt_partial import PowerPromptPartial

NODE_CLASS_MAPPINGS = {
    "PowerPromptNode": PowerPromptNode,
    "PowerPromptPartial": PowerPromptPartial,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "PowerPromptNode": "Power Prompt",
    "PowerPromptPartial": "Power Prompt Partial",
}
