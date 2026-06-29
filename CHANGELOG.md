# Changelog

## [0.1.2] — 2026-06-29

### Added
- **Inline `includes:`** — any YAML (main prompt, wired partial, or included file) can declare a top-level `includes:` list of file paths to load before itself. Includes are resolved transitively and deduplicated, so the same file is never loaded more than once even if it appears multiple times in the graph. Merge priority: included files → wired partials → main YAML.
- **Global `tags` variable** — a synthetic `tags` name is now available in `when`/`unless` expressions and in `fragments:`/`prompt:`. It accumulates every tag emitted by all variables resolved so far, in encounter order, deduplicated. Useful for branching on a tag without knowing which variable produced it (e.g. `'cold' in tags`).
- **Power Prompt File Partial node** — a new `PowerPromptFilePartial` node loads a partial from a `.yaml`/`.yml` file registered in ComfyUI's `power-prompt` partials folder. Files can be uploaded directly from the node's UI panel.
- Pre-commit hook (Husky) that automatically rebuilds the frontend bundle before each commit, so the built output is always in sync with source changes.

### Fixed
- Reset button in the UI panel now works correctly.

---

## [0.1.1] — 2026-06-27

### Added
- Example workflow (`examples/Power Prompt - Example.json`) demonstrating wired partials and a file partial together in a full ComfyUI pipeline.
- ComfyUI registry publish action — CI publishes automatically on any `v*` tag push.

### Fixed
- YAML editor no longer clips or misresizes on narrow node canvases.
- Tags defined on options were missing from the `fragments:` template context; they are now correctly available after all variables resolve.

---

## [0.1.0] — 2026-06-25

### Added
- Initial release with the **Power Prompt** and **Power Prompt Partial** nodes.
- `select` and `text` variable types, with `label:`, `group:`, `hidden:`, and `count:` fields.
- Weighted random option selection (`weight:`), conditional filtering (`when:`/`unless:` via Jinja2 sandbox), and tag propagation (`tags:`, `<varname>_tags`).
- Count ranges: `1`, `N`, `M-N`, `any`; multi-value option shorthand (list under `value:`).
- `fragments:` for named Jinja2 sub-templates composed from resolved variables, referenceable as `{{ fragment.name }}`.
- Wired partial composition via `include_1` … `include_4` input slots on the main node.
- `prompt` (normalised — whitespace trimmed, commas cleaned) and `raw_prompt` outputs.
