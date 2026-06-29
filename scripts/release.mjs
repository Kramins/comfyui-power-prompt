#!/usr/bin/env node
/**
 * Usage: node scripts/release.mjs <version>
 *   e.g. node scripts/release.mjs 1.2.0
 *
 * What it does:
 *   1. Validates the version is valid semver
 *   2. Updates pyproject.toml and package.json
 *   3. Commits both files
 *   4. Creates an annotated git tag vX.Y.Z
 *
 * It does NOT push — run `git push && git push --tags` when ready.
 */

import { readFileSync, writeFileSync } from "fs";
import { execSync } from "child_process";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");

// ── Args ──────────────────────────────────────────────────────────────────────

const version = process.argv[2];

if (!version) {
    console.error("Usage: node scripts/release.mjs <version>");
    process.exit(1);
}

if (!/^\d+\.\d+\.\d+$/.test(version)) {
    console.error(`Invalid version "${version}" — must be X.Y.Z (e.g. 1.2.0)`);
    process.exit(1);
}

// ── Read current versions ─────────────────────────────────────────────────────

const pyprojectPath = join(root, "pyproject.toml");
const packagePath = join(root, "package.json");

const pyprojectContent = readFileSync(pyprojectPath, "utf8");
const packageContent = readFileSync(packagePath, "utf8");

const currentPyproject = pyprojectContent.match(/^version = "(.+)"/m)?.[1] ?? "(unknown)";
const currentPackage = JSON.parse(packageContent).version ?? "(unknown)";

console.log(`\nCurrent versions:`);
console.log(`  pyproject.toml  ${currentPyproject}`);
console.log(`  package.json    ${currentPackage}`);
console.log(`\nBumping to: ${version}\n`);

// ── Update files ──────────────────────────────────────────────────────────────

const newPyproject = pyprojectContent.replace(
    /^version = ".+"/m,
    `version = "${version}"`
);
writeFileSync(pyprojectPath, newPyproject);
console.log(`✓  pyproject.toml updated`);

const pkg = JSON.parse(packageContent);
pkg.version = version;
writeFileSync(packagePath, JSON.stringify(pkg, null, 2) + "\n");
console.log(`✓  package.json updated`);

// ── Git commit + tag ──────────────────────────────────────────────────────────

const run = (cmd) => execSync(cmd, { cwd: root, stdio: "inherit" });

run(`git add pyproject.toml package.json`);
run(`git commit -m "chore: release v${version}"`);
run(`git tag -a "v${version}" -m "v${version}"`);

console.log(`\n✓  Committed and tagged v${version}`);
console.log(`\nTo publish, push the commit and tag:`);
console.log(`  git push && git push --tags\n`);
