import { app } from "../../scripts/app.js";
import { parse as parseYAML } from "./vendor/yaml.js";
import {
    EditorView, keymap, lineNumbers, highlightActiveLine, drawSelection,
    defaultKeymap, history, historyKeymap, indentWithTab,
    foldGutter, foldKeymap, syntaxHighlighting, defaultHighlightStyle, bracketMatching,
    autocompletion, completionKeymap, closeBrackets,
    linter, lintGutter,
    yaml,
    oneDark,
} from "./vendor/codemirror-bundle.js";

const NODE_TYPE = "PowerPromptNode";
const YAML_MIN_HEIGHT = 220;
const CHIP_THRESHOLD = 20; // options > this → chip/searchable UI

const DEFAULT_YAML = `variables:
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

const DEFAULT_PARTIAL_YAML = `variables:
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

// ── Styles ────────────────────────────────────────────────────────────────────

function injectStyles() {
    if (document.getElementById("pp-styles")) return;
    const style = document.createElement("style");
    style.id = "pp-styles";
    style.textContent = `
        .pp-panel {
            box-sizing: border-box;
            width: 100%;
            height: 100%;
            display: flex;
            flex-direction: column;
        }
        .pp-yaml-section {
            flex: 1;
            min-height: 0;
            display: flex;
            flex-direction: column;
        }
        .pp-yaml-editor {
            flex: 1;
            min-height: ${YAML_MIN_HEIGHT}px;
            width: 100%;
            box-sizing: border-box;
            border: 1px solid #555;
            border-radius: 4px;
            overflow: hidden;
        }
        .pp-yaml-editor .cm-editor { height: 100%; }
        .pp-vars-section {
            flex-shrink: 0;
            display: grid;
            grid-template-columns: max-content 1fr;
            align-items: start;
            gap: 5px 8px;
            padding: 0 0 2px;
        }
        .pp-vars-header {
            display: flex;
            justify-content: flex-end;
            padding: 6px 0 2px;
            grid-column: 1 / -1;
        }
        .pp-reset-btn {
            background: none;
            border: 1px solid #555;
            border-radius: 3px;
            color: #777;
            cursor: pointer;
            font-size: 11px;
            padding: 2px 8px;
            line-height: 1.4;
        }
        .pp-reset-btn:hover {
            border-color: #999;
            color: #ccc;
        }
        .pp-group-header {
            grid-column: 1 / -1;
            font-size: 10px;
            font-weight: 600;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            border-top: 1px solid #3a3a3a;
            padding: 8px 0 2px;
            margin-top: 2px;
        }
        .pp-group-header:first-child {
            border-top: none;
            padding-top: 2px;
            margin-top: 0;
        }
        .pp-var-row {
            display: contents;
        }
        .pp-var-label {
            font-size: 12px;
            color: #ccc;
            padding-top: 4px;
            line-height: 1.3;
            white-space: nowrap;
        }
        .pp-count-hint {
            display: block;
            font-size: 10px;
            color: #777;
            font-style: italic;
        }
        /* ── Simple dropdown ── */
        .pp-var-row select {
            flex: 1;
            background: #2a2a3e;
            color: #e0e0e0;
            border: 1px solid #555;
            border-radius: 3px;
            padding: 2px 6px;
            font-size: 12px;
        }
        /* ── Text input ── */
        .pp-var-row input[type="text"]:not(.pp-chip-search):not(.pp-search-input) {
            flex: 1;
            background: #2a2a3e;
            color: #e0e0e0;
            border: 1px solid #555;
            border-radius: 3px;
            padding: 2px 6px;
            font-size: 12px;
        }
        /* ── Checkbox group ── */
        .pp-multiselect {
            display: flex;
            flex-wrap: wrap;
            gap: 4px;
            flex: 1;
        }
        .pp-multiselect label {
            display: flex;
            align-items: center;
            gap: 3px;
            font-size: 12px;
            color: #ccc;
            cursor: pointer;
            background: #2a2a3e;
            border: 1px solid #555;
            border-radius: 3px;
            padding: 2px 6px;
            user-select: none;
        }
        .pp-multiselect label:has(input:checked) {
            background: #3a5a8e;
            border-color: #6a9ade;
        }
        /* ── Chip multi-select ── */
        .pp-chip-select {
            flex: 1;
            position: relative;
        }
        .pp-chips-area {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 3px;
            min-height: 26px;
            padding: 3px 4px;
            background: #2a2a3e;
            border: 1px solid #555;
            border-radius: 3px;
            cursor: text;
        }
        .pp-chip {
            display: inline-flex;
            align-items: center;
            gap: 2px;
            background: #3a5a8e;
            border: 1px solid #6a9ade;
            border-radius: 3px;
            padding: 1px 4px 1px 6px;
            font-size: 11px;
            color: #e0e0e0;
            white-space: nowrap;
        }
        .pp-chip-remove {
            background: none;
            border: none;
            color: #aaa;
            cursor: pointer;
            font-size: 13px;
            line-height: 1;
            padding: 0 1px;
        }
        .pp-chip-remove:hover { color: #fff; }
        .pp-chip-search {
            flex: 1;
            min-width: 60px;
            background: transparent;
            border: none;
            color: #e0e0e0;
            font-size: 12px;
            outline: none;
            padding: 1px 2px;
        }
        .pp-random-badge {
            font-size: 11px;
            color: #777;
            font-style: italic;
            padding: 1px 2px;
        }
        /* ── Searchable single dropdown ── */
        .pp-search-select {
            flex: 1;
            position: relative;
        }
        .pp-search-input {
            width: 100%;
            box-sizing: border-box;
            background: #2a2a3e;
            color: #e0e0e0;
            border: 1px solid #555;
            border-radius: 3px;
            padding: 2px 6px;
            font-size: 12px;
        }
        /* ── Shared dropdown panel ── */
        .pp-dropdown {
            position: absolute;
            top: calc(100% + 2px);
            left: 0;
            width: 100%;
            z-index: 9999;
            background: #2a2a3e;
            border: 1px solid #666;
            border-radius: 3px;
            max-height: 160px;
            overflow-y: auto;
            box-shadow: 0 4px 12px rgba(0,0,0,0.6);
        }
        .pp-dropdown-item {
            padding: 4px 8px;
            font-size: 12px;
            color: #e0e0e0;
            cursor: pointer;
            user-select: none;
        }
        .pp-dropdown-item:hover,
        .pp-dropdown-item.pp-highlighted { background: #3a5a8e; }
        .pp-dropdown-item.pp-selected { color: #6a9ade; }
        .pp-hidden { display: none !important; }
    `;
    document.head.appendChild(style);
}

// ── CodeMirror helpers ────────────────────────────────────────────────────────

const SCHEMA_COMPLETIONS = [
    { label: "variables:", type: "keyword" },
    { label: "prompt:", type: "keyword" },
    { label: "fragments:", type: "keyword" },
    { label: "type: select", type: "keyword" },
    { label: "type: text", type: "keyword" },
    { label: "type: multiselect", type: "keyword" },
    { label: "count: 1", type: "value" },
    { label: "count: any", type: "value" },
    { label: "options:", type: "keyword" },
    { label: "value:", type: "keyword" },
    { label: "weight:", type: "keyword" },
    { label: "when:", type: "keyword" },
    { label: "unless:", type: "keyword" },
    { label: "tags:", type: "keyword" },
    { label: "hidden: true", type: "keyword" },
    { label: "label:", type: "keyword" },
    { label: "group:", type: "keyword" },
];

function schemaCompletionSource(context) {
    const word = context.matchBefore(/[\w:]+/);
    if (!word && !context.explicit) return null;
    return { from: word?.from ?? context.pos, options: SCHEMA_COMPLETIONS };
}

function makeYamlLintSource() {
    return linter(view => {
        try {
            parseYAML(view.state.doc.toString());
            return [];
        } catch (e) {
            const msg = String(e.message ?? e);
            // Aliases referencing anchors from connected partials can't resolve in isolation.
            // Suppress these — Python will report a real error if the alias is genuinely broken.
            if (/alias|anchor/i.test(msg)) return [];
            return [{ from: 0, to: view.state.doc.length, severity: "error", message: msg }];
        }
    });
}

function createYamlEditor(parent, initialYaml) {
    const editorDiv = document.createElement("div");
    editorDiv.className = "pp-yaml-editor";
    parent.appendChild(editorDiv);

    let _onUpdateCb = null;
    const view = new EditorView({
        doc: initialYaml,
        parent: editorDiv,
        extensions: [
            oneDark,
            lineNumbers(),
            foldGutter(),
            highlightActiveLine(),
            drawSelection(),
            bracketMatching(),
            closeBrackets(),
            history(),
            syntaxHighlighting(defaultHighlightStyle),
            yaml(),
            autocompletion({ override: [schemaCompletionSource] }),
            lintGutter(),
            makeYamlLintSource(),
            keymap.of([
                ...defaultKeymap,
                ...historyKeymap,
                ...foldKeymap,
                ...completionKeymap,
                indentWithTab,
            ]),
            EditorView.updateListener.of(update => {
                if (update.docChanged && _onUpdateCb) _onUpdateCb(update.state.doc.toString());
            }),
            EditorView.theme({
                "&": { height: "100%", minHeight: `${YAML_MIN_HEIGHT}px` },
                ".cm-scroller": { fontFamily: "monospace", fontSize: "12px", lineHeight: "1.5" },
            }),
        ],
    });

    // Notify CodeMirror when the host container is resized (e.g. node drag-resize).
    // Without this CM keeps its initial height even as the flex parent grows.
    new ResizeObserver(() => view.requestMeasure()).observe(editorDiv);

    return {
        toString: () => view.state.doc.toString(),
        updateCode: (text) => view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: text } }),
        onUpdate: (cb) => { _onUpdateCb = cb; },
    };
}

function getIncludeRawStrings(node) {
    const parts = [];
    const inputs = (node.inputs ?? [])
        .filter(i => i.name.startsWith("include_") && i.link != null)
        .sort((a, b) => a.name.localeCompare(b.name));
    for (const input of inputs) {
        const link = app.graph.links[input.link];
        if (!link) continue;
        const srcNode = app.graph.getNodeById(link.origin_id);
        if (!srcNode) continue;
        if (srcNode.mode === 4) continue; // bypassed — exclude from UI definition
        if (srcNode.type === "PowerPromptFilePartial") {
            const fileWidget = srcNode.widgets?.find(w => w.name === "partial_file");
            if (fileWidget?.value) parts.push(`imports:\n  - ${fileWidget.value}`);
        } else {
            const w = srcNode.widgets?.find(w => w.name === "yaml_input");
            if (w?.value) parts.push(w.value);
        }
    }
    return parts;
}

async function fetchUIDefinition(yamlText, includeStrings) {
    try {
        const res = await fetch("/power_prompt/ui_definition", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ yaml: yamlText, includes: includeStrings }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return await res.json();
    } catch (e) {
        console.warn("[PowerPrompt] ui_definition fetch failed:", e);
        return null;
    }
}

function _notifyConnectedMainNodes(partialNode) {
    const outputLinks = partialNode.outputs?.[0]?.links ?? [];
    for (const linkId of outputLinks) {
        const link = app.graph.links[linkId];
        if (!link) continue;
        const target = app.graph.getNodeById(link.target_id);
        target?.onConnectionsChange?.(1, link.target_slot, true, link, null);
    }
}

function ensureIncludeSlots(node) {
    const inputs = node.inputs ?? [];
    const includeIndices = [];
    for (let i = 0; i < inputs.length; i++) {
        if (inputs[i].name.startsWith("include_")) includeIndices.push(i);
    }
    // Remove trailing unconnected include slots beyond the first
    while (includeIndices.length > 1 && inputs[includeIndices.at(-1)].link == null) {
        node.removeInput(includeIndices.pop());
    }
    // Always have exactly one unconnected slot at the end
    const currentIncludes = (node.inputs ?? []).filter(i => i.name.startsWith("include_"));
    if (currentIncludes.length === 0 || currentIncludes.at(-1).link != null) {
        node.addInput(`include_${currentIncludes.length + 1}`, "POWER_PROMPT_PARTIAL");
    }
}

// ── Extension registration ────────────────────────────────────────────────────

app.registerExtension({
    name: "PowerPromptNode.DOMPanel",

    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== NODE_TYPE) return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            onNodeCreated?.apply(this, arguments);
            setupPowerPromptPanel(this);
        };
    },
});

// ── Node setup ────────────────────────────────────────────────────────────────

function setupPowerPromptPanel(node) {
    injectStyles();

    const yamlCanvasWidget = node.widgets?.find(w => w.name === "yaml_input");
    const varStateCanvasWidget = node.widgets?.find(w => w.name === "var_state");
    const initialYaml = yamlCanvasWidget?.value ?? DEFAULT_YAML;

    const panel = document.createElement("div");
    panel.className = "pp-panel";

    const yamlSection = document.createElement("div");
    yamlSection.className = "pp-yaml-section";

    const jar = createYamlEditor(yamlSection, initialYaml);

    const varsSection = document.createElement("div");
    varsSection.className = "pp-vars-section";

    const varsHeader = document.createElement("div");
    varsHeader.className = "pp-vars-header";
    varsHeader.style.display = "none";

    const refreshBtn = document.createElement("button");
    refreshBtn.type = "button";
    refreshBtn.className = "pp-reset-btn";
    refreshBtn.textContent = "Refresh";
    refreshBtn.addEventListener("click", () => {
        rebuildVarControls(varsSection, jar.toString(), getVarState(varsSection), node);
    });
    varsHeader.appendChild(refreshBtn);

    const resetBtn = document.createElement("button");
    resetBtn.type = "button";
    resetBtn.className = "pp-reset-btn";
    resetBtn.textContent = "Reset all";
    resetBtn.addEventListener("click", () => {
        rebuildVarControls(varsSection, jar.toString(), {}, node);
    });
    varsHeader.appendChild(resetBtn);

    new MutationObserver(() => {
        varsHeader.style.display = varsSection.children.length > 0 ? "" : "none";
    }).observe(varsSection, { childList: true });

    panel.appendChild(yamlSection);
    panel.appendChild(varsHeader);
    panel.appendChild(varsSection);

    panel.addEventListener("keydown", e => e.stopPropagation());
    panel.addEventListener("pointerdown", e => e.stopPropagation());

    // Yaml edit → push to canvas widget + debounced rebuild
    let debounceTimer = null;
    const scheduleRebuild = () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            rebuildVarControls(varsSection, jar.toString(), getVarState(varsSection), node);
        }, 300);
    };
    jar.onUpdate(code => {
        if (yamlCanvasWidget) yamlCanvasWidget.value = code;
        scheduleRebuild();
    });

    // Connection state
    const isYamlConnected = () =>
        (node.inputs?.find(i => i.name === "yaml_input")?.link ?? null) != null;

    const updateConnectionState = () => {
        const connected = isYamlConnected();
        yamlSection.style.display = connected ? "none" : "";
        const computed = node.computeSize?.();
        if (computed && node.size) {
            if (connected) {
                node.setSize([node.size[0], Math.max(computed[1], node.size[1] - YAML_MIN_HEIGHT)]);
            } else {
                node.setSize([
                    Math.max(node.size[0], computed[0]),
                    Math.max(node.size[1], computed[1]),
                ]);
            }
        }
        app.graph?.setDirtyCanvas?.(true, true);
    };

    // Hide canvas yaml widget — keep it for connections + serialisation
    if (yamlCanvasWidget) {
        yamlCanvasWidget.hidden = true;
        yamlCanvasWidget.computedHeight = 0;
        yamlCanvasWidget.draw = () => {};
    }

    // var_state DOM widget — owns the full panel
    node.addDOMWidget("var_state", "ppPanel", panel, {
        getValue() {
            return JSON.stringify(getVarState(varsSection));
        },
        setValue(jsonStr) {
            if (yamlCanvasWidget) jar.updateCode(yamlCanvasWidget.value ?? DEFAULT_YAML);
            let vars = {};
            try { vars = JSON.parse(jsonStr) ?? {}; } catch (_) {}
            rebuildVarControls(varsSection, jar.toString(), vars, node);
        },
        getMinHeight() {
            const connected = isYamlConnected();
            const yamlH = connected ? 0 : YAML_MIN_HEIGHT;
            const controlsH = varsSection.scrollHeight || 0;
            const headerH = varsHeader.style.display !== "none" ? (varsHeader.scrollHeight || 0) : 0;
            const gap = (!connected && controlsH > 0) ? 6 : 0;
            return yamlH + gap + headerH + controlsH;
        },
        hideOnZoom: false,
    });

    // Remove canvas var_state widget
    if (varStateCanvasWidget) {
        const idx = node.widgets.indexOf(varStateCanvasWidget);
        if (idx !== -1) node.widgets.splice(idx, 1);
    }

    // Order: [yaml_canvas (h=0), var_state DOM, seed]
    const domWidget = node.widgets.find(w => w.element === panel);
    if (domWidget) {
        node.widgets.splice(node.widgets.indexOf(domWidget), 1);
        const yamlIdx = yamlCanvasWidget ? node.widgets.indexOf(yamlCanvasWidget) : -1;
        node.widgets.splice(yamlIdx + 1, 0, domWidget);
    }

    const origOnConnectionsChange = node.onConnectionsChange?.bind(node);
    node.onConnectionsChange = function (type, slotIndex, connected, link, ioSlot) {
        origOnConnectionsChange?.call(this, type, slotIndex, connected, link, ioSlot);
        updateConnectionState();
        ensureIncludeSlots(node);
        scheduleRebuild();
    };

    const origOnConfigure = node.onConfigure?.bind(node);
    node.onConfigure = function (data) {
        origOnConfigure?.(data);
        if (yamlCanvasWidget) jar.updateCode(yamlCanvasWidget.value ?? DEFAULT_YAML);
        updateConnectionState();
        ensureIncludeSlots(node);
        rebuildVarControls(varsSection, jar.toString(), getVarState(varsSection), node);
    };

    updateConnectionState();
    ensureIncludeSlots(node);
    rebuildVarControls(varsSection, jar.toString(), {}, node);
}

// ── Var state reader ──────────────────────────────────────────────────────────

function getVarState(varsSection) {
    const vars = {};
    for (const row of varsSection.querySelectorAll(".pp-var-row")) {
        const name = row.dataset.varName;
        const widget = row.dataset.varWidget;
        const isAny = row.dataset.varIsAny === "true";

        if (widget === "dropdown") {
            const searchSel = row.querySelector(".pp-search-select");
            const sel = row.querySelector("select");
            let val = null;
            if (searchSel) {
                val = searchSel._ppGetValue?.() ?? null;
            } else if (sel) {
                val = sel.value !== "random" ? sel.value : null;
            }
            if (val) vars[name] = val;
        } else if (widget === "checkboxes") {
            const chipSel = row.querySelector(".pp-chip-select");
            const ms = row.querySelector(".pp-multiselect");
            let selected;
            if (chipSel) {
                selected = chipSel._ppGetSelected?.() ?? [];
            } else if (ms) {
                selected = Array.from(ms.querySelectorAll("input:checked")).map(i => i.value);
            } else {
                selected = [];
            }
            // is_any: always store (empty = user wants nothing); range: omit when empty → Python uses seed
            if (selected.length > 0 || isAny) vars[name] = selected;
        } else if (widget === "text") {
            const inp = row.querySelector("input[type=text]:not(.pp-chip-search):not(.pp-search-input)");
            if (inp) vars[name] = inp.value;
        }
    }
    return vars;
}

// ── Rebuild controls ─────────────────────────────────────────────────────────

function createGroupHeader(groupName) {
    const header = document.createElement("div");
    header.className = "pp-group-header";
    header.textContent = groupName;
    return header;
}

async function rebuildVarControls(varsSection, yamlText, currentVars, node) {
    const def = await fetchUIDefinition(yamlText, getIncludeRawStrings(node));

    const controls = (def?.error || !def)
        ? []
        : def.controls.filter(c => !c.hidden);

    if (!def || def.error) {
        console.warn("[PowerPrompt] ui_definition:", def?.error ?? "fetch failed");
    }

    // Split into groups (insertion-ordered Map) and ungrouped; groups render first.
    const groupMap = new Map();
    const ungrouped = [];
    for (const ctrl of controls) {
        if (ctrl.group) {
            if (!groupMap.has(ctrl.group)) groupMap.set(ctrl.group, []);
            groupMap.get(ctrl.group).push(ctrl);
        } else {
            ungrouped.push(ctrl);
        }
    }

    const ordered = [];
    for (const [groupName, vars] of groupMap) {
        ordered.push({ kind: "header", groupName });
        for (const ctrl of vars) ordered.push({ kind: "ctrl", ctrl });
    }
    for (const ctrl of ungrouped) ordered.push({ kind: "ctrl", ctrl });

    // Index existing rows for potential reuse (event listeners are preserved on DOM moves)
    const existingRows = {};
    for (const row of varsSection.querySelectorAll(".pp-var-row")) {
        existingRows[row.dataset.varName] = row;
    }

    const prevRowCount = varsSection.children.length;
    varsSection.innerHTML = "";

    for (const item of ordered) {
        if (item.kind === "header") {
            varsSection.appendChild(createGroupHeader(item.groupName));
            continue;
        }

        const { ctrl } = item;
        const isLarge = ctrl.options.length > CHIP_THRESHOLD;
        const existing = existingRows[ctrl.name];
        const existingIsLarge = existing
            ? (existing.querySelector(".pp-chip-select") != null
               || existing.querySelector(".pp-search-select") != null)
            : false;
        // In-place update: only for simple widgets with unchanged widget/is_any signature
        const canUpdate = existing
            && existing.dataset.varWidget === ctrl.widget
            && existing.dataset.varIsAny === String(ctrl.is_any)
            && !isLarge
            && !existingIsLarge;

        if (canUpdate) {
            if (ctrl.widget === "dropdown") {
                const sel = existing.querySelector("select");
                if (sel) updateSelectOptions(sel, ctrl.options, currentVars[ctrl.name]);
            } else if (ctrl.widget === "checkboxes") {
                const ms = existing.querySelector(".pp-multiselect");
                if (ms) updateCheckboxes(ms, ctrl.options, currentVars[ctrl.name]);
            } else if (ctrl.widget === "text") {
                const inp = existing.querySelector("input[type=text]");
                if (inp) inp.value = String(currentVars[ctrl.name] ?? "");
            }
            varsSection.appendChild(existing);
        } else {
            varsSection.appendChild(createVarRow(ctrl, isLarge, currentVars[ctrl.name]));
        }
    }

    const newRowCount = varsSection.children.length;
    if (newRowCount !== prevRowCount) {
        const computed = node.computeSize?.();
        if (computed && node.size) {
            if (computed[0] > node.size[0] || computed[1] > node.size[1]) {
                node.setSize([
                    Math.max(node.size[0], computed[0]),
                    Math.max(node.size[1], computed[1]),
                ]);
            }
        }
        app.graph?.setDirtyCanvas?.(true, true);
    }
}

const OPTION_DISPLAY_MAX = 48;
function truncateOption(str) {
    return str.length > OPTION_DISPLAY_MAX ? str.slice(0, OPTION_DISPLAY_MAX - 1) + "…" : str;
}

// ── Row factory ───────────────────────────────────────────────────────────────

function createVarRow(ctrl, isLarge, savedValue) {
    const row = document.createElement("div");
    row.className = "pp-var-row";
    row.dataset.varName = ctrl.name;
    row.dataset.varWidget = ctrl.widget;
    row.dataset.varIsAny = String(ctrl.is_any);

    const label = document.createElement("span");
    label.className = "pp-var-label";
    label.textContent = ctrl.label;
    if (ctrl.count_hint) {
        const hint = document.createElement("span");
        hint.className = "pp-count-hint";
        hint.textContent = `pick ${ctrl.count_hint}`;
        label.appendChild(hint);
    }
    row.appendChild(label);

    if (ctrl.widget === "dropdown") {
        row.appendChild(isLarge
            ? createSearchableDropdown(ctrl.options, savedValue)
            : createDropdown(ctrl.options, savedValue));
    } else if (ctrl.widget === "checkboxes") {
        const savedArr = Array.isArray(savedValue) ? savedValue : [];
        row.appendChild(isLarge
            ? createChipSelect(ctrl.options, savedArr, ctrl.is_any)
            : createCheckboxGroup(ctrl.options, savedArr));
    } else if (ctrl.widget === "text") {
        const inp = document.createElement("input");
        inp.type = "text";
        inp.value = String(savedValue ?? "");
        row.appendChild(inp);
    }

    return row;
}

// ── Simple dropdown (count=1, small list) ─────────────────────────────────────

function createDropdown(options, savedValue) {
    const sel = document.createElement("select");
    updateSelectOptions(sel, options, savedValue);
    return sel;
}

function updateSelectOptions(sel, options, savedValue) {
    sel.innerHTML = "";
    for (const opt of ["random", ...options]) {
        const o = document.createElement("option");
        o.value = opt;
        o.textContent = truncateOption(opt);
        o.title = opt;
        sel.appendChild(o);
    }
    sel.value = (savedValue && (savedValue === "random" || options.includes(savedValue))) ? savedValue : "random";
}

// ── Checkbox group (count>1 or any, small list) ───────────────────────────────

function createCheckboxGroup(options, savedArr) {
    const container = document.createElement("div");
    container.className = "pp-multiselect";
    updateCheckboxes(container, options, savedArr);
    return container;
}

function updateCheckboxes(container, options, savedValue) {
    const savedArr = Array.isArray(savedValue) ? savedValue : [];
    const savedSet = new Set(savedArr);
    container.innerHTML = "";
    for (const opt of options) {
        const lbl = document.createElement("label");
        const cb = document.createElement("input");
        cb.type = "checkbox";
        cb.value = opt;
        cb.checked = savedSet.has(opt);
        lbl.title = opt;
        lbl.appendChild(cb);
        lbl.appendChild(document.createTextNode(truncateOption(opt)));
        container.appendChild(lbl);
    }
}

// ── Searchable dropdown (count=1, large list) ─────────────────────────────────

function createSearchableDropdown(options, savedValue) {
    const wrapper = document.createElement("div");
    wrapper.className = "pp-search-select";

    const input = document.createElement("input");
    input.type = "text";
    input.className = "pp-search-input";
    input.placeholder = "random (seed)";
    input.autocomplete = "off";
    wrapper.appendChild(input);

    const dropdown = document.createElement("div");
    dropdown.className = "pp-dropdown pp-hidden";
    wrapper.appendChild(dropdown);

    let selected = (savedValue && savedValue !== "random") ? String(savedValue) : "";
    if (selected) input.value = selected;

    const showDropdown = (filter) => {
        dropdown.innerHTML = "";
        const fl = filter.toLowerCase();
        const filtered = options.filter(o => o.toLowerCase().includes(fl));
        if (!filtered.length) { dropdown.classList.add("pp-hidden"); return; }
        for (const opt of filtered) {
            const item = document.createElement("div");
            item.className = "pp-dropdown-item" + (opt === selected ? " pp-selected" : "");
            item.textContent = truncateOption(opt);
            item.title = opt;
            item.onmousedown = (e) => {
                e.preventDefault();
                selected = opt;
                input.value = opt;
                dropdown.classList.add("pp-hidden");
            };
            dropdown.appendChild(item);
        }
        dropdown.classList.remove("pp-hidden");
    };

    input.addEventListener("input", () => { selected = ""; showDropdown(input.value); });
    input.addEventListener("focus", () => showDropdown(input.value));
    input.addEventListener("blur", () => setTimeout(() => {
        dropdown.classList.add("pp-hidden");
        // Revert to last valid selection if text doesn't match
        if (input.value && !options.includes(input.value)) input.value = selected;
        if (!input.value) selected = "";
    }, 150));
    input.addEventListener("keydown", (e) => {
        if (e.key === "Escape") { input.value = ""; selected = ""; dropdown.classList.add("pp-hidden"); }
        else if (e.key === "Enter") { dropdown.querySelector(".pp-dropdown-item")?.dispatchEvent(new MouseEvent("mousedown")); }
    });

    wrapper._ppGetValue = () => selected || "random";
    return wrapper;
}

// ── Chip multi-select (count>1 or any, large list) ────────────────────────────

function createChipSelect(options, savedArr, isAny) {
    const container = document.createElement("div");
    container.className = "pp-chip-select";

    const chipsArea = document.createElement("div");
    chipsArea.className = "pp-chips-area";
    container.appendChild(chipsArea);

    const searchInput = document.createElement("input");
    searchInput.type = "text";
    searchInput.className = "pp-chip-search";
    searchInput.placeholder = "type to add...";
    chipsArea.appendChild(searchInput);

    const dropdown = document.createElement("div");
    dropdown.className = "pp-dropdown pp-hidden";
    container.appendChild(dropdown);

    const selected = new Set(savedArr);

    const renderChips = () => {
        for (const el of [...chipsArea.querySelectorAll(".pp-chip, .pp-random-badge")]) el.remove();

        if (selected.size === 0 && !isAny) {
            const badge = document.createElement("span");
            badge.className = "pp-random-badge";
            badge.textContent = "random (seed)";
            chipsArea.insertBefore(badge, searchInput);
        }

        for (const val of selected) {
            const chip = document.createElement("span");
            chip.className = "pp-chip";
            chip.appendChild(document.createTextNode(val));
            const rm = document.createElement("button");
            rm.type = "button";
            rm.className = "pp-chip-remove";
            rm.textContent = "×";
            rm.addEventListener("mousedown", (e) => {
                e.preventDefault();
                e.stopPropagation();
                selected.delete(val);
                renderChips();
                showDropdown(searchInput.value);
            });
            chip.appendChild(rm);
            chipsArea.insertBefore(chip, searchInput);
        }
    };

    const showDropdown = (filter) => {
        dropdown.innerHTML = "";
        const fl = filter.toLowerCase();
        const available = options.filter(o => !selected.has(o) && o.toLowerCase().includes(fl));
        if (!available.length) { dropdown.classList.add("pp-hidden"); return; }
        for (const opt of available) {
            const item = document.createElement("div");
            item.className = "pp-dropdown-item";
            item.textContent = truncateOption(opt);
            item.title = opt;
            item.addEventListener("mousedown", (e) => {
                e.preventDefault();
                selected.add(opt);
                searchInput.value = "";
                renderChips();
                showDropdown("");
                searchInput.focus();
            });
            dropdown.appendChild(item);
        }
        dropdown.classList.remove("pp-hidden");
    };

    searchInput.addEventListener("input", () => showDropdown(searchInput.value));
    searchInput.addEventListener("focus", () => showDropdown(searchInput.value));
    searchInput.addEventListener("blur", () => setTimeout(() => {
        dropdown.classList.add("pp-hidden");
        searchInput.value = "";
    }, 150));
    searchInput.addEventListener("keydown", (e) => {
        if (e.key === "Escape") { dropdown.classList.add("pp-hidden"); searchInput.value = ""; }
        else if (e.key === "Enter") { e.preventDefault(); dropdown.querySelector(".pp-dropdown-item")?.dispatchEvent(new MouseEvent("mousedown")); }
        else if (e.key === "Backspace" && !searchInput.value) {
            const last = [...selected].at(-1);
            if (last) { selected.delete(last); renderChips(); showDropdown(""); }
        }
    });

    // Click on chips area (not a chip/button) focuses the search
    chipsArea.addEventListener("click", (e) => {
        if (e.target === chipsArea || e.target.classList.contains("pp-random-badge")) {
            searchInput.focus();
        }
    });

    container._ppGetSelected = () => [...selected];
    renderChips();
    return container;
}

// ── Power Prompt Partial node ─────────────────────────────────────────────────

app.registerExtension({
    name: "PowerPromptPartial.DOMPanel",

    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== "PowerPromptPartial") return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            onNodeCreated?.apply(this, arguments);
            setupPartialPanel(this);
        };
    },
});

function setupPartialPanel(node) {
    injectStyles();

    const yamlCanvasWidget = node.widgets?.find(w => w.name === "yaml_input");
    const initialYaml = yamlCanvasWidget?.value ?? DEFAULT_PARTIAL_YAML;

    const panel = document.createElement("div");
    panel.className = "pp-panel";

    const yamlSection = document.createElement("div");
    yamlSection.className = "pp-yaml-section";
    panel.appendChild(yamlSection);

    const jar = createYamlEditor(yamlSection, initialYaml);

    panel.addEventListener("keydown", e => e.stopPropagation());
    panel.addEventListener("pointerdown", e => e.stopPropagation());

    if (yamlCanvasWidget) {
        yamlCanvasWidget.hidden = true;
        yamlCanvasWidget.computedHeight = 0;
        yamlCanvasWidget.draw = () => {};
    }

    let partialDebounce = null;
    jar.onUpdate(code => {
        if (yamlCanvasWidget) yamlCanvasWidget.value = code;
        clearTimeout(partialDebounce);
        partialDebounce = setTimeout(() => _notifyConnectedMainNodes(node), 300);
    });

    const isYamlConnected = () =>
        (node.inputs?.find(i => i.name === "yaml_input")?.link ?? null) != null;

    const updateConnectionState = () => {
        yamlSection.style.display = isYamlConnected() ? "none" : "";
        app.graph?.setDirtyCanvas?.(true, true);
    };

    node.addDOMWidget("_partial_panel", "ppPartialPanel", panel, {
        getValue() { return jar.toString(); },
        setValue(text) {
            jar.updateCode(text ?? initialYaml);
        },
        getMinHeight() { return isYamlConnected() ? 0 : YAML_MIN_HEIGHT; },
        hideOnZoom: false,
    });

    const origOnConnectionsChange = node.onConnectionsChange?.bind(node);
    node.onConnectionsChange = function (...args) {
        origOnConnectionsChange?.call(this, ...args);
        updateConnectionState();
    };

    const origOnConfigure = node.onConfigure?.bind(node);
    node.onConfigure = function (data) {
        origOnConfigure?.(data);
        if (yamlCanvasWidget) jar.updateCode(yamlCanvasWidget.value ?? initialYaml);
        updateConnectionState();
    };

    updateConnectionState();
}

// ── Power Prompt File Partial node ───────────────────────────────────────────

app.registerExtension({
    name: "PowerPromptFilePartial.DOMPanel",

    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== "PowerPromptFilePartial") return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            onNodeCreated?.apply(this, arguments);
            setupFilePartialPanel(this);
        };
    },
});

function setupFilePartialPanel(node) {
    injectStyles();

    // partial_file is a COMBO — ComfyUI renders the native dropdown for us.
    // getIncludeRawStrings reads partial_file.value directly and builds an
    // `imports:` stub, so no file content caching is needed here.
    const comboWidget = node.widgets?.find(w => w.name === "partial_file");

    // ── Status + reload DOM widget ────────────────────────────────────────────

    const panel = document.createElement("div");
    panel.style.cssText = "display:flex;align-items:center;gap:6px;padding:2px 0 4px;";

    const statusLine = document.createElement("div");
    statusLine.style.cssText = [
        "flex:1;font-size:11px;min-height:16px;",
        "white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:#888;",
    ].join("");

    const uploadBtn = document.createElement("button");
    uploadBtn.type = "button";
    uploadBtn.className = "pp-reset-btn";
    uploadBtn.textContent = "Upload";

    const fileInput = document.createElement("input");
    fileInput.type = "file";
    fileInput.accept = ".yaml,.yml";
    fileInput.style.display = "none";
    uploadBtn.addEventListener("click", () => fileInput.click());

    const reloadBtn = document.createElement("button");
    reloadBtn.type = "button";
    reloadBtn.className = "pp-reset-btn";
    reloadBtn.textContent = "Reload";

    panel.appendChild(statusLine);
    panel.appendChild(uploadBtn);
    panel.appendChild(fileInput);
    panel.appendChild(reloadBtn);
    panel.addEventListener("keydown", e => e.stopPropagation());
    panel.addEventListener("pointerdown", e => e.stopPropagation());

    const setStatus = (msg, isError = false) => {
        statusLine.textContent = msg;
        statusLine.style.color = isError ? "#e06c75" : "#888";
    };

    // ── File select logic ─────────────────────────────────────────────────────

    const selectFile = (filename) => {
        if (!filename || filename === "") { setStatus(""); return; }
        setStatus(filename);
        _notifyConnectedMainNodes(node);
    };

    // ── Upload logic ──────────────────────────────────────────────────────────

    fileInput.addEventListener("change", async () => {
        const file = fileInput.files?.[0];
        fileInput.value = "";           // reset so the same file can be re-uploaded
        if (!file) return;
        setStatus("Uploading…");
        try {
            const form = new FormData();
            form.append("file", file);
            const res = await fetch("/power_prompt/upload_partial", { method: "POST", body: form });
            const data = await res.json();
            if (data.error) { setStatus(`Upload failed: ${data.error}`, true); return; }
            // Add to the COMBO list if not already present and select it.
            // app.refreshComboInNodes() would also work but causes a full re-render;
            // directly appending keeps the UX snappy and avoids a round-trip.
            if (comboWidget) {
                const vals = comboWidget.options?.values;
                if (Array.isArray(vals) && !vals.includes(data.filename)) {
                    vals.push(data.filename);
                }
                comboWidget.value = data.filename;
            }
            selectFile(data.filename);
        } catch (e) {
            setStatus(`Upload failed: ${e.message}`, true);
        }
    });

    // Hook the native COMBO widget so a dropdown change triggers a notify.
    if (comboWidget) comboWidget.callback = (value) => selectFile(value);
    reloadBtn.addEventListener("click", () => selectFile(comboWidget?.value ?? ""));

    // ── DOM widget (status row only — combo rendered natively above it) ───────

    node.addDOMWidget("_file_partial_panel", "ppFilePanel", panel, {
        getValue() { return ""; },
        setValue() {},
        getMinHeight() { return 40; },
        hideOnZoom: false,
    });

    // ── Lifecycle hooks ───────────────────────────────────────────────────────

    const origOnConfigure = node.onConfigure?.bind(node);
    node.onConfigure = function (data) {
        origOnConfigure?.(data);
        if (comboWidget?.value) selectFile(comboWidget.value);
    };
}

