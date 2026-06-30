import { app } from "../../scripts/app.js";
import { YAML_MIN_HEIGHT, CHIP_THRESHOLD, DEFAULT_YAML } from "./constants.js";
import { injectStyles } from "./styles.js";
import { createYamlEditor } from "./yaml-editor.js";
import { fetchUIDefinition } from "./api.js";
import { getIncludeRawStrings, buildInputSockets } from "./node-utils.js";
import {
    getVarState, createGroupHeader, createVarRow,
    updateSelectOptions, updateCheckboxes,
} from "./controls.js";

// Per-node generation counter: each rebuildVarControls call increments it; stale fetches bail out.
const _rebuildGen = new WeakMap();

export function setupPowerPromptPanel(node) {
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
        if (node._ppRebuilding) return;
        origOnConnectionsChange?.call(this, type, slotIndex, connected, link, ioSlot);
        updateConnectionState();
        const currentVarNames = (node.inputs ?? []).filter(i => i.type === "*").map(i => i.name);
        buildInputSockets(node, currentVarNames);
        scheduleRebuild();
    };

    const origOnConfigure = node.onConfigure?.bind(node);
    node.onConfigure = function (data) {
        origOnConfigure?.(data);
        if (yamlCanvasWidget) jar.updateCode(yamlCanvasWidget.value ?? DEFAULT_YAML);
        updateConnectionState();
        const currentVarNames = (node.inputs ?? []).filter(i => i.type === "*").map(i => i.name);
        buildInputSockets(node, currentVarNames);
        // Do NOT call rebuildVarControls here. ComfyUI sets widget values before firing
        // onConfigure, so setValue() has already queued a rebuild with the saved vars.
        // Calling rebuildVarControls here with getVarState (which reads an empty DOM) would
        // fire a later generation with {} and overwrite the saved selections.
    };

    updateConnectionState();
    buildInputSockets(node, []);
    rebuildVarControls(varsSection, jar.toString(), {}, node);
}

async function rebuildVarControls(varsSection, yamlText, currentVars, node) {
    const gen = (_rebuildGen.get(node) ?? 0) + 1;
    _rebuildGen.set(node, gen);

    const def = await fetchUIDefinition(yamlText, getIncludeRawStrings(node));

    if (_rebuildGen.get(node) !== gen) return; // a newer call started while we were fetching

    const controls = (def?.error || !def)
        ? []
        : def.controls.filter(c => !c.hidden);

    if (!def || def.error) {
        console.warn("[PowerPrompt] ui_definition:", def?.error ?? "fetch failed");
    }

    // Sync input-variable sockets before touching the DOM
    const inputVarNames = controls.filter(c => c.widget === "input").map(c => c.name);
    buildInputSockets(node, inputVarNames);

    // Only renderable (non-socket) controls get DOM rows
    const renderableControls = controls.filter(c => c.widget !== "input");

    // Split into groups (insertion-ordered Map) and ungrouped; groups render first.
    const groupMap = new Map();
    const ungrouped = [];
    for (const ctrl of renderableControls) {
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
