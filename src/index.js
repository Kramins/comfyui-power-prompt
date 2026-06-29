import { app } from "../../scripts/app.js";
import { setupPowerPromptPanel } from "./power-prompt-panel.js";
import { setupPartialPanel } from "./partial-panel.js";
import { setupFilePartialPanel } from "./file-partial-panel.js";

app.registerExtension({
    name: "PowerPromptNode.DOMPanel",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "PowerPromptNode") return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            onNodeCreated?.apply(this, arguments);
            setupPowerPromptPanel(this);
        };
    },
});

app.registerExtension({
    name: "PowerPromptPartial.DOMPanel",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "PowerPromptPartial") return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            onNodeCreated?.apply(this, arguments);
            setupPartialPanel(this);
        };
    },
});

app.registerExtension({
    name: "PowerPromptFilePartial.DOMPanel",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "PowerPromptFilePartial") return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            onNodeCreated?.apply(this, arguments);
            setupFilePartialPanel(this);
        };
    },
});
