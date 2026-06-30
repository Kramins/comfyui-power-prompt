export const YAML_MIN_HEIGHT = 220;
export const CHIP_THRESHOLD = 20;
export const OPTION_DISPLAY_MAX = 48;

export const DEFAULT_YAML = `variables:
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
`;

export const RESERVED_INPUT_NAMES = new Set(["yaml_input", "var_state", "seed"]);

export const DEFAULT_PARTIAL_YAML = `variables:
  hair_color:
    type: select
    count: 1
    options:
      - black
      - blonde
      - silver

fragments:
  appearance: "{{ hair_color }} hair"
`;
