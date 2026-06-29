// Import paths are written relative to the OUTPUT file (web/js/), not this source file.
// The esbuild plugin in scripts/build-node-bundle.mjs intercepts these and marks them external.
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

import { YAML_MIN_HEIGHT } from "./constants.js";

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

export function createYamlEditor(parent, initialYaml) {
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
