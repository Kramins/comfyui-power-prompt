// Import path is relative to the OUTPUT file (web/js/). See build-node-bundle.mjs.
import { app } from "../../scripts/app.js";
import { RESERVED_INPUT_NAMES } from "./constants.js";

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
            if (fileWidget?.value) parts.push(`includes:\n  - ${fileWidget.value}`);
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

/**
 * Rebuild all dynamic input sockets in the correct order:
 *   connected includes → input variable sockets → trailing empty include
 *
 * Saves and restores link connections so the user's wiring is preserved.
 * Uses node._ppRebuilding to prevent re-entrant calls triggered by
 * removeInput / app.graph.connect firing onConnectionsChange mid-rebuild.
 */
export function buildInputSockets(node, inputVarNames) {
    if (node._ppRebuilding) return;
    node._ppRebuilding = true;
    try {
        // Snapshot connections for every dynamic socket that has a link.
        const savedConnections = new Map(); // socket name → { originId, originSlot }
        for (const inp of (node.inputs ?? [])) {
            if (inp.link == null) continue;
            if (inp.type !== "*" && !inp.name.startsWith("include_")) continue;
            const link = app.graph.links[inp.link];
            if (link) savedConnections.set(inp.name, { originId: link.origin_id, originSlot: link.origin_slot });
        }

        // Preserve connected include names in their current order.
        const connectedIncludes = (node.inputs ?? [])
            .filter(i => i.name.startsWith("include_") && i.link != null)
            .map(i => i.name);

        // Filter desired input var names.
        const desiredVars = (inputVarNames ?? []).filter(
            n => !RESERVED_INPUT_NAMES.has(n) && !n.startsWith("include_")
        );

        // Remove all dynamic sockets (backwards so indices stay valid).
        const inputs = node.inputs ?? [];
        for (let i = inputs.length - 1; i >= 0; i--) {
            if (inputs[i].type === "*" || inputs[i].name.startsWith("include_")) {
                node.removeInput(i);
            }
        }

        // Re-add in order: connected includes → input vars → trailing empty include.
        for (const name of connectedIncludes) {
            node.addInput(name, "POWER_PROMPT_PARTIAL");
        }
        for (const name of desiredVars) {
            node.addInput(name, "*");
        }
        node.addInput(`include_${connectedIncludes.length + 1}`, "POWER_PROMPT_PARTIAL");

        // Restore connections.
        for (const inp of (node.inputs ?? [])) {
            const conn = savedConnections.get(inp.name);
            if (!conn) continue;
            const slot = (node.inputs ?? []).indexOf(inp);
            const originNode = app.graph.getNodeById(conn.originId);
            originNode?.connect(conn.originSlot, node, slot);
        }

        app.graph.setDirtyCanvas?.(true, true);
    } finally {
        node._ppRebuilding = false;
    }
}
