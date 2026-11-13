#!/usr/bin/env node
"use strict";

const { check, fix } = require("../src/index");
const pkg = require("../package.json");

const HELP = `echeck v${pkg.version}

Check that secrets (.env files, keys, credentials) are protected by
.gitignore / .dockerignore / .npmignore, not tracked by git, and not
hard-coded in source code.

Usage:
  echeck [directory] [options]

Options:
  --fix         Add missing rules to .gitignore automatically
  --no-scan     Skip scanning source files for hard-coded secrets
  --scan-tests  Also scan the contents of test folders / test files
                (skipped by default)
  --json        Print the result as JSON (useful in CI)
  --strict      Treat warnings as failures too
  -v, --version Show the version
  -h, --help    Show this help

Silencing false positives:
  - Add an "echeck-ignore" comment on a line to skip just that line
  - Create a .echeckignore file in the project root (same syntax as
    .gitignore); listed paths are not checked at all

Exit codes: 0 = no problems, 1 = problems found, 2 = error`;

const useColor = process.stdout.isTTY && !process.env.NO_COLOR;
const paint = (code, s) => (useColor ? "\x1b[" + code + "m" + s + "\x1b[0m" : s);

function parseArgs(argv) {
  const opts = { dir: ".", fix: false, scan: true, scanTests: false, json: false, strict: false };
  for (const arg of argv) {
    if (arg === "--fix") opts.fix = true;
    else if (arg === "--no-scan") opts.scan = false;
    else if (arg === "--scan-tests") opts.scanTests = true;
    else if (arg === "--json") opts.json = true;
    else if (arg === "--strict") opts.strict = true;
    else if (arg === "-h" || arg === "--help") opts.help = true;
    else if (arg === "-v" || arg === "--version") opts.version = true;
    else if (arg.startsWith("-")) throw new Error("Unknown option: " + arg);
    else opts.dir = arg;
  }
  return opts;
}

function main() {
  let opts;
  try {
    opts = parseArgs(process.argv.slice(2));
  } catch (err) {
    console.error(err.message);
    console.error("Run with --help for usage");
    return 2;
  }

  if (opts.help) {
    console.log(HELP);
    return 0;
  }
  if (opts.version) {
    console.log(pkg.version);
    return 0;
  }

  let result;
  try {
    result = check(opts.dir, { scan: opts.scan, scanTests: opts.scanTests });
  } catch (err) {
    console.error("Check failed: " + err.message);
    return 2;
  }

  let added = [];
  if (opts.fix) {
    added = fix(opts.dir, result);
    if (added.length > 0) result = check(opts.dir, { scan: opts.scan, scanTests: opts.scanTests });
  }

  const errors = result.findings.filter((f) => f.severity === "error");
  const warnings = result.findings.filter((f) => f.severity === "warning");
  const failed = errors.length > 0 || (opts.strict && warnings.length > 0);

  if (opts.json) {
    console.log(JSON.stringify({ ...result, added, ok: !failed }, null, 2));
    return failed ? 1 : 0;
  }

  console.log("Scanning " + result.root);
  console.log(result.filesChecked + " files checked, " + result.sensitiveFiles.length + " sensitive file(s) found");
  if (result.skipped.tests > 0) {
    console.log("Skipped content scan of " + result.skipped.tests + " test file(s) (use --scan-tests to include them)");
  }
  if (result.skipped.echeckignore > 0) {
    console.log("Skipped " + result.skipped.echeckignore + " file(s) listed in .echeckignore");
  }
  console.log("");

  if (added.length > 0) {
    console.log(paint("32", "Added to .gitignore:") + " " + added.join("  ") + "\n");
  }

  for (const f of result.findings) {
    const tag = f.severity === "error" ? paint("31", "[error]") : paint("33", "[warn] ");
    const where = f.line ? f.file + ":" + f.line : f.file;
    console.log(tag + " " + where);
    console.log("       " + f.message);
  }

  if (result.findings.length === 0) {
    console.log(paint("32", "No problems found."));
  } else {
    console.log("\n" + errors.length + " error(s), " + warnings.length + " warning(s)");
    if (!opts.fix && result.findings.some((f) => f.code === "not-gitignored")) {
      console.log("Tip: run with --fix to add the missing rules to .gitignore");
    }
  }
  return failed ? 1 : 0;
}

process.exitCode = main();
