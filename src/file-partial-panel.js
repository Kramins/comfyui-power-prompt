import { injectStyles } from "./styles.js";
import { notifyConnectedMainNodes } from "./node-utils.js";

export function setupFilePartialPanel(node) {
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
        notifyConnectedMainNodes(node);
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
