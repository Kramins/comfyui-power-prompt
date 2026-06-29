/**
 * Bundle src/index.js → web/js/power-prompt-node.js
 *
 * External paths are written relative to the OUTPUT file (web/js/power-prompt-node.js):
 *   ../../scripts/app.js          → ComfyUI app singleton
 *   ./vendor/yaml.js              → js-yaml UMD shim
 *   ./vendor/codemirror-bundle.js → pre-built CodeMirror bundle
 *
 * The esbuild plugin below intercepts these imports and marks them external
 * so that the output contains verbatim `import ... from "<path>"` statements.
 */

import { build } from "esbuild";
import { fileURLToPath } from "url";
import { dirname, join } from "path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");

// Patterns that should be left as external imports in the output.
const EXTERNAL_PATTERNS = [
    /^\.\.\/\.\.\/scripts\/app\.js$/,
    /^\.\/vendor\//,
];

const comfyExternalPlugin = {
    name: "comfyui-externals",
    setup(build) {
        build.onResolve({ filter: /.*/ }, args => {
            for (const pattern of EXTERNAL_PATTERNS) {
                if (pattern.test(args.path)) {
                    return { path: args.path, external: true };
                }
            }
        });
    },
};

await build({
    entryPoints: [join(root, "src/index.js")],
    bundle: true,
    format: "esm",
    // Do NOT minify — keeps the output readable and diffable while still
    // being a single file. Enable minify only when releasing.
    // minify: true,
    outfile: join(root, "web/js/power-prompt-node.js"),
    plugins: [comfyExternalPlugin],
});

console.log("✓  web/js/power-prompt-node.js written");
