// Import path is relative to the OUTPUT file (web/js/). See build-node-bundle.mjs.
import { app } from "../../scripts/app.js";

export function getIncludeRawStrings(node) {
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

export function notifyConnectedMainNodes(partialNode) {
    const outputLinks = partialNode.outputs?.[0]?.links ?? [];
    for (const linkId of outputLinks) {
        const link = app.graph.links[linkId];
        if (!link) continue;
        const target = app.graph.getNodeById(link.target_id);
        target?.onConnectionsChange?.(1, link.target_slot, true, link, null);
    }
}

export function ensureIncludeSlots(node) {
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
