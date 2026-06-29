#!/usr/bin/env node
/**
 * Usage: node scripts/check-version.mjs <tag>
 *   e.g. node scripts/check-version.mjs v1.2.0
 *
 * Verifies that the tag version matches the version declared in both
 * pyproject.toml and package.json. Exits non-zero on any mismatch.
 */

import { readFileSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");

const tag = process.argv[2];

if (!tag) {
    console.error("Usage: node scripts/check-version.mjs <tag>");
    process.exit(1);
}

const tagVersion = tag.replace(/^v/, "");

const pyproject = readFileSync(join(root, "pyproject.toml"), "utf8");
const pyprojectVersion = pyproject.match(/^version = "(.+)"/m)?.[1];

const pkg = JSON.parse(readFileSync(join(root, "package.json"), "utf8"));
const packageVersion = pkg.version;

console.log(`Tag:          ${tagVersion}`);
console.log(`pyproject:    ${pyprojectVersion}`);
console.log(`package.json: ${packageVersion}`);

const mismatches = [];
if (tagVersion !== pyprojectVersion) mismatches.push(`pyproject.toml has "${pyprojectVersion}"`);
if (tagVersion !== packageVersion)   mismatches.push(`package.json has "${packageVersion}"`);

if (mismatches.length) {
    console.error(`\nVersion mismatch for tag "${tag}":`);
    for (const m of mismatches) console.error(`  • ${m}`);
    console.error(`\nRun: npm run release -- ${tagVersion}`);
    process.exit(1);
}

console.log(`\n✓ All versions match ${tagVersion}`);
