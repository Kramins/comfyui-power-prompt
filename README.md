# Power Prompt

> **Note:** The `main` branch tracks active development and may be ahead of the latest release. Features documented here might not be available in an older installed version — check the [releases](../../releases) page to see what's in the version you have.

> **A note from me:** I built this mostly for myself - I kept running into the same frustration with other prompt nodes: either too little control or too much friction to use comfortably. I wanted a clean UI that made it fun to experiment with options, and I may have gotten a little carried away. It's a hobby project, but I'm genuinely open to feature requests and bug reports.

A ComfyUI node for building rich, dynamic prompts from a simple YAML definition. Define named variables with weighted options, conditional filtering, and Jinja2 templating — then let the node assemble your prompt at generation time.

## Features

- **Variables** — define named `select` or `text` variables and reference them in a Jinja2 prompt template
- **Weighted options** — give options a `weight` to control how often they're randomly chosen
- **Count ranges** — pick exactly N, a random range (`1-3`), or any number (`any`) of options
- **`when` / `unless` expressions** — Jinja2 expressions that control which options are available; `when` includes an option when true, `unless` excludes it when true
- **Tags** — attach semantic labels to options; downstream `when`/`unless` expressions can check `style_tags`, `season_tags`, etc.
- **Multi-value options** — a single option entry can expand to multiple values sharing the same weight, tags, and `when`/`unless`
- **UI controls** — `label:` sets a custom display name, `group:` organises variables into named sections, `hidden:` hides a variable from the UI while still resolving it
- **Prompt fragments** — define a `fragments:` mapping of named Jinja2 sub-templates rendered after variables resolve; reference them as `{{ fragment.name }}` in any prompt
- **Partials** — wire one or more **Power Prompt Partial** nodes into include slots to share `variables:` and `fragments:` across compositions

## Installation

1. Clone or copy this folder into `ComfyUI/custom_nodes/comfyui-power-prompt`
2. Install Python dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Restart ComfyUI — the **Power Prompt** node appears under the `prompt` category

## Local Development

**Prerequisites:** Node.js 18+

```bash
npm install   # also installs the Husky pre-commit hook
```

There are two JavaScript bundles, both built with esbuild:

| Script | Input | Output | When to rebuild |
|---|---|---|---|
| `npm run build-editor` | `scripts/cm-entry.mjs` | `web/js/vendor/codemirror-bundle.js` | CodeMirror version bump or new editor extensions |
| `npm run build-node` | `src/index.js` | `web/js/power-prompt-node.js` | Any change under `src/` |
| `npm run build` | both | both | — |

The Husky pre-commit hook runs `build-node` and stages the output automatically, so you never need to remember to rebuild before committing frontend changes. Rebuild `build-editor` manually if you touch the CodeMirror setup, and commit the result alongside your other changes.

## YAML Reference

A Power Prompt YAML has three top-level keys:

```yaml
variables:   # required — named inputs resolved at generation time
  ...

fragments:   # optional — named sub-templates composed from resolved variables
  ...

prompt: |    # required — Jinja2 template rendered after all variables resolve
  ...
```

---

### Variables

Each entry under `variables:` becomes a UI control and a template variable.

#### Variable fields

| Field | Type | Default | Description |
|---|---|---|---|
| `type` | `select` \| `text` | — | **Required.** `select` picks from a list; `text` is a free-text input. Aliases: `choice` (= select, count 1), `multiselect` (= select, count any) |
| `count` | int \| range \| `any` | `1` | How many options to pick. `1` = single dropdown; `0-3` = random range; `any` = user checks all they want |
| `options` | list | — | Required for `select`. The pool of values to choose from |
| `label` | string | key name | Custom display name shown in the UI panel. Underscores in the key name are replaced with spaces when no label is set |
| `group` | string | — | Groups this variable under a named section header in the UI. All variables sharing the same string are rendered together, before ungrouped variables |
| `hidden` | bool | `false` | When `true`, the variable is not shown in the UI. It is still resolved randomly and available in the prompt and `when`/`unless` expressions |

#### `type: select`

Picks one or more values from the `options` list:

```yaml
variables:
  season:
    type: select
    count: 1          # exactly one — renders as a dropdown
    options:
      - spring
      - summer
      - autumn
      - winter

  accessories:
    type: select
    count: 0-2        # zero to two — renders as a chip group
    options:
      - scarf
      - sunglasses
      - umbrella

  style:
    type: multiselect # alias: count is implicitly "any" — user checks what they want
    options:
      - anime
      - watercolor
      - oil painting
```

#### `type: text`

A free-text input field. The value is whatever the user types:

```yaml
variables:
  notes:
    type: text
    label: "Extra notes"   # shown in the UI as "Extra notes" instead of "notes"
```

#### `label`, `group`, and `hidden`

```yaml
variables:
  internal_season:
    type: select
    hidden: true           # resolved randomly but not shown in the UI panel
    options: [spring, summer, autumn, winter]

  outfit:
    type: select
    label: "Outfit Style"  # displayed as "Outfit Style" instead of "outfit"
    group: "Character"     # appears under a "Character" section header in the UI
    options:
      - casual
      - formal
      - fantasy

  setting:
    type: select
    group: "Character"     # shares the "Character" group with outfit above
    options:
      - city street
      - forest path
      - rooftop
```

---

### Options

Each entry in an `options:` list is either a plain string (shorthand) or a mapping with any of the following fields:

| Field | Type | Default | Description |
|---|---|---|---|
| `value` | string \| list | — | The option text. A list expands to multiple independent entries sharing the same weight, `when`, and tags |
| `weight` | float | `1.0` | Relative selection probability. Higher = chosen more often |
| `when` | Jinja2 expression | (always included) | Option is added to the random pool only when this evaluates to `true` |
| `unless` | Jinja2 expression | (never excluded) | Option is removed from the random pool when this evaluates to `true` |
| `tags` | string \| list | `[]` | Semantic labels attached to this value, available as `{varname}_tags` in downstream `when`/`unless` expressions |

```yaml
options:
  - simple string option               # shorthand — weight 1, no conditions

  - value: weighted option
    weight: 3                          # 3× more likely than weight-1 options

  - value: conditional option
    when: "season == 'winter'"         # only available when season is winter

  - value: excluded option
    unless: "'rainy' in weather_tags"  # excluded when the weather has a rainy tag

  - value:                             # multi-value: share weight, when, tags
      - option variant a
      - option variant b
    weight: 2
    tags: [shared_tag]
```

---

### `when` and `unless` expressions

Expressions are evaluated using the **Jinja2 sandbox** — attribute access on unsafe objects is blocked. Variables resolved above the current one in the YAML are available by name.

```yaml
when: "season == 'winter'"
when: "'cold' in season_tags"
when: "'student' in character_tags and 'cold' not in season_tags"
when: "time_of_day in ('dusk', 'night')"
when: "len(accessories) > 0"

unless: "season == 'summer'"
unless: "'rainy' in weather_tags"
```

**Available names in expressions:**

| Name | Value |
|---|---|
| `<varname>` | Resolved string (single-pick) or list (multi-pick) |
| `<varname>_tags` | List of tags from the resolved value(s), deduplicated in encounter order |
| `tags` | Accumulated list of every tag emitted by all variables resolved so far, deduplicated in encounter order. Useful when you need to branch on any tag regardless of which variable produced it |

**Available functions:** `len`, `any`, `all`, `min`, `max`, `str`, `int`, `float`, `bool`, `abs`, `round`

**Jinja2 notes:**
- Use lists `[x, y]` instead of set literals `{x, y}` — sets are not supported
- Generator expressions (`any(x for x in y)`) are not supported — use `in` membership checks instead
- Both `when` and `unless` can appear on the same option — the option is included only if `when` is true **and** `unless` is false
- Variables must be declared **above** any variable whose `when`/`unless` references them
- `tags` and all `<varname>_tags` lists are also available in `fragments:` and the `prompt:` template after all variables resolve

---

### Prompt fragments

Define named Jinja2 sub-templates that compose from resolved variables. Reference them in the prompt (or in later fragments) as `{{ fragment.name }}`.

```yaml
fragments:
  location: "{{ city }} at {{ time_of_day }}"
  full_scene: "{{ fragment.location }}, {{ weather }}"   # earlier fragment available here

prompt: |
  {{ character }}, {{ fragment.full_scene }}, masterpiece
```

Fragments are rendered in declaration order after all variables resolve. Fragments from connected Partials are merged in — the main YAML wins on name collisions.

---

### Partials

Partials contribute `variables:` and `fragments:` into a main node — useful for reusable character, location, or style libraries. There are two ways to bring a partial into a composition:

**Wired partials** — connect **Power Prompt Partial** or **Power Prompt File Partial** nodes into a main node's `include_1`, `include_2`, … input slots in the ComfyUI graph.

**Inline includes** — declare file dependencies directly inside any YAML with a top-level `includes:` list. Files are resolved from the registered `power-prompt` partials folder (the same folder that **Power Prompt File Partial** uses).

```yaml
includes:
  - characters/alice.yaml
  - styles/anime.yaml

variables:
  subject:
    type: select
    options: [1girl, 1boy]

prompt: |
  {{ subject }}, {{ fragment.style_block }}
```

Any YAML — main prompt, wired partial, or included file — can declare `includes:`. Imports are resolved **transitively**: if an included file itself has an `includes:` list, those files are loaded too. The same file is never loaded more than once regardless of how many times it appears in the graph (cycles are safe).

#### Merge order and priority

All sources are merged in a fixed order before the prompt renders. The rightmost source wins on any name collision:

```
included files  →  wired partials (include_1 … include_N)  →  main YAML
```

| Source | Priority | Notes |
|---|---|---|
| Included files | Lowest | Declared via `includes:`; earlier entries in the list lose to later ones |
| Wired partials | Middle | `include_1` < `include_2` < … (higher number wins) |
| Main YAML | Highest | Always overrides everything |

This applies to both `variables:` and `fragments:`.

#### Variable resolution order and cross-partial `when`/`unless`

Variables are **resolved in the same order** as the merge order above — wired-partial variables are evaluated before imported variables. This matters for cross-partial `when`/`unless` expressions:

```yaml
# character.yaml (wired as include_1) — defines char_archetype with tags
variables:
  char_archetype:
    type: select
    options:
      - value: student
        tags: [student]

# action-pose.yaml (imported) — options filtered by char_archetype_tags
variables:
  action:
    type: select
    options:
      - value: studying, surrounded by books
        when: "'student' in char_archetype_tags"   # ← works because wired partials
      - value: gazing into the distance             #   resolve before includes
```

Because wired partials resolve first, their tags are already in `eval_context` when imported variables are processed. **If you need a variable defined in a wired partial to gate options in an included file, always supply that variable via a wired partial, not another import.**

The `prompt:` key is not meaningful in a partial and is ignored.

---

### Node outputs

| Socket | Content |
|---|---|
| `prompt` | Normalized — newlines collapsed, whitespace trimmed, commas cleaned |
| `raw_prompt` | Unprocessed rendered output from the Jinja2 template |

---

See `examples/` for worked examples and `docs/prompt-schema.yaml` for the full annotated field reference.

## Examples

See the [`examples/`](examples/) folder:

- [`basic.yaml`](examples/basic.yaml) — two variables, minimal prompt
- [`standard.yaml`](examples/standard.yaml) — weighted options, tags, `when`/`unless`, count ranges, text variable
- [`advanced.yaml`](examples/advanced.yaml) — full feature showcase including `fragments:`

## License

GPL-3.0-or-later — see [LICENSE](LICENSE)
# comfyui-power-prompt
