import { app } from "../../scripts/app.js";
import { YAML_MIN_HEIGHT, DEFAULT_PARTIAL_YAML } from "./constants.js";
import { injectStyles } from "./styles.js";
import { createYamlEditor } from "./yaml-editor.js";
import { notifyConnectedMainNodes } from "./node-utils.js";

export function setupPartialPanel(node) {
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
        partialDebounce = setTimeout(() => notifyConnectedMainNodes(node), 300);
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
