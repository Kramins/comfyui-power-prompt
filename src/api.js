export async function fetchUIDefinition(yamlText, includeStrings) {
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
