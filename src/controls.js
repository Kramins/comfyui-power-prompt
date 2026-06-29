import { CHIP_THRESHOLD, OPTION_DISPLAY_MAX } from "./constants.js";

// ── Var state reader ──────────────────────────────────────────────────────────

export function getVarState(varsSection) {
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

// ── Group header ──────────────────────────────────────────────────────────────

export function createGroupHeader(groupName) {
    const header = document.createElement("div");
    header.className = "pp-group-header";
    header.textContent = groupName;
    return header;
}

// ── Row factory ───────────────────────────────────────────────────────────────

export function createVarRow(ctrl, isLarge, savedValue) {
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

export function updateSelectOptions(sel, options, savedValue) {
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

export function updateCheckboxes(container, options, savedValue) {
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

function truncateOption(str) {
    return str.length > OPTION_DISPLAY_MAX ? str.slice(0, OPTION_DISPLAY_MAX - 1) + "…" : str;
}
