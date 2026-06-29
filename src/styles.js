import { YAML_MIN_HEIGHT } from "./constants.js";

export function injectStyles() {
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
