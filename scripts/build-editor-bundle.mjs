import { build } from "esbuild";
import { fileURLToPath } from "url";
import { dirname, join } from "path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");

await build({
  entryPoints: [join(__dirname, "cm-entry.mjs")],
  bundle: true,
  format: "esm",
  minify: true,
  outfile: join(root, "web/js/vendor/codemirror-bundle.js"),
});

console.log("Built web/js/vendor/codemirror-bundle.js");
