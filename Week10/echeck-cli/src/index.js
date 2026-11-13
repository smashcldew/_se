"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { execFileSync } = require("node:child_process");
const { IgnoreMatcher } = require("./matcher");
const { SENSITIVE_FILES, RECOMMENDED_IGNORE, SECRET_PATTERNS, SKIP_DIRS } = require("./patterns");

const MAX_SCAN_BYTES = 1024 * 1024;
const BINARY_EXT = /\.(png|jpe?g|gif|webp|ico|pdf|zip|gz|tgz|7z|rar|woff2?|ttf|eot|mp3|mp4|mov|exe|dll|so|dylib|class|jar|lock)$/i;

function readIfExists(file) {
  try {
    return fs.readFileSync(file, "utf8");
  } catch {
    return null;
  }
}

function toPosix(p) {
  return p.split(path.sep).join("/");
}

// Recursively list all files (skips .git, node_modules, etc.)
function walk(root, dir = root, out = []) {
  let entries;
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return out;
  }
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (!SKIP_DIRS.has(entry.name)) walk(root, full, out);
    } else if (entry.isFile()) {
      out.push(toPosix(path.relative(root, full)));
    }
  }
  return out;
}

// Test folders / test files often contain fake credentials, so content scanning skips them by default
const TEST_DIRS = new Set(["test", "tests", "__tests__", "spec", "specs", "fixtures", "__fixtures__", "mocks", "__mocks__"]);

function isTestFile(relPath) {
  const parts = relPath.split("/");
  const base = parts[parts.length - 1];
  if (parts.slice(0, -1).some((seg) => TEST_DIRS.has(seg.toLowerCase()))) return true;
  return /\.(test|spec)\.[a-z0-9]+$/i.test(base) || /^test_.*\.py$/i.test(base) || /_test\.(py|go)$/i.test(base);
}

function sensitiveKind(relPath) {
  const base = relPath.split("/").pop();
  const hit = SENSITIVE_FILES.find((rule) => rule.test(base));
  return hit ? hit.name : null;
}

// Files tracked by git; returns null if this is not a git repo or git is not installed
function gitTrackedFiles(root) {
  try {
    const out = execFileSync("git", ["ls-files", "-z"], {
      cwd: root,
      stdio: ["ignore", "pipe", "ignore"],
      maxBuffer: 64 * 1024 * 1024,
    });
    return new Set(out.toString("utf8").split("\0").filter(Boolean));
  } catch {
    return null;
  }
}

function loadMatcher(root, names) {
  const text = names.map((n) => readIfExists(path.join(root, n))).filter((t) => t !== null).join("\n");
  return new IgnoreMatcher(text);
}

function maskSecret(s) {
  if (s.length <= 8) return "****";
  return s.slice(0, 4) + "…" + "*".repeat(4);
}

function scanContent(root, relPath) {
  const full = path.join(root, relPath);
  let stat;
  try {
    stat = fs.statSync(full);
  } catch {
    return [];
  }
  if (stat.size > MAX_SCAN_BYTES || BINARY_EXT.test(relPath)) return [];
  const text = readIfExists(full);
  if (text === null || text.includes("\0")) return [];

  const hits = [];
  const lines = text.split("\n");
  lines.forEach((line, idx) => {
    if (line.length > 2000) return;
    if (line.includes("echeck-ignore")) return; // Inline ignore: add an echeck-ignore comment on the line
    for (const pat of SECRET_PATTERNS) {
      const m = line.match(pat.regex);
      if (m) {
        hits.push({ line: idx + 1, type: pat.name, preview: maskSecret(m[0]) });
        break;
      }
    }
  });
  return hits;
}

/**
 * Check a project.
 * @param {string} root Project root directory
 * @param {{scan?: boolean, scanTests?: boolean}} options
 * @returns {{root: string, filesChecked: number, sensitiveFiles: string[], findings: Array}}
 */
function check(root, options = {}) {
  const { scan = true, scanTests = false } = options;
  root = path.resolve(root);

  const allFiles = walk(root);
  // .echeckignore: same syntax as .gitignore; listed paths are not checked at all
  const echeckIgnore = new IgnoreMatcher(readIfExists(path.join(root, ".echeckignore")) || "");
  const files = allFiles.filter((f) => !echeckIgnore.ignores(f));
  const skipped = { echeckignore: allFiles.length - files.length, tests: 0 };
  const gitignore = loadMatcher(root, [".gitignore", path.join(".git", "info", "exclude")]);
  const hasDockerfile = files.some((f) => /(^|\/)(Dockerfile|docker-compose\.ya?ml)/i.test(f));
  const dockerignoreText = readIfExists(path.join(root, ".dockerignore"));
  const dockerignore = new IgnoreMatcher(dockerignoreText || "");

  const pkgText = readIfExists(path.join(root, "package.json"));
  let pkg = null;
  if (pkgText) {
    try {
      pkg = JSON.parse(pkgText);
    } catch {
      pkg = null;
    }
  }
  // npm publish rules: with a "files" field only those are published; otherwise .npmignore, then .gitignore
  let npmMatcher = null;
  if (pkg && !Array.isArray(pkg.files)) {
    const npmignoreText = readIfExists(path.join(root, ".npmignore"));
    npmMatcher = npmignoreText !== null ? new IgnoreMatcher(npmignoreText) : gitignore;
  }

  const tracked = gitTrackedFiles(root);
  const findings = [];
  const sensitiveFiles = [];

  for (const rel of files) {
    const kind = sensitiveKind(rel);
    if (!kind) continue;
    sensitiveFiles.push(rel);

    const ignoredByGit = gitignore.ignores(rel);
    if (tracked && tracked.has(rel)) {
      findings.push({
        severity: "error",
        code: "tracked",
        file: rel,
        message: kind + " is tracked by git (adding it to .gitignore now will not untrack it). Run: git rm --cached " + rel + " and rotate any exposed secrets.",
      });
    } else if (!ignoredByGit) {
      findings.push({
        severity: "error",
        code: "not-gitignored",
        file: rel,
        message: kind + " is not covered by .gitignore and could be committed by the next git add.",
      });
    }

    if (hasDockerfile && !dockerignore.ignores(rel)) {
      findings.push({
        severity: "warning",
        code: "not-dockerignored",
        file: rel,
        message: kind + " is not covered by .dockerignore and may be copied into the image by COPY . .",
      });
    }

    if (npmMatcher && !npmMatcher.ignores(rel)) {
      findings.push({
        severity: "warning",
        code: "not-npmignored",
        file: rel,
        message: kind + " is not excluded by .npmignore / .gitignore and may be published by npm publish. Consider adding a \"files\" allowlist to package.json.",
      });
    }
  }

  let scanned = 0;
  if (scan) {
    for (const rel of files) {
      if (sensitiveKind(rel)) continue; // Sensitive files naturally contain secrets; handled above
      if (gitignore.ignores(rel)) continue; // Ignored files are not committed, so they cannot leak
      if (!scanTests && isTestFile(rel)) {
        skipped.tests += 1;
        continue;
      }
      scanned += 1;
      for (const hit of scanContent(root, rel)) {
        findings.push({
          severity: "error",
          code: "secret-in-source",
          file: rel,
          line: hit.line,
          message: "Possible " + hit.type + " (" + hit.preview + ") hard-coded in source.",
        });
      }
    }
  }

  return { root, filesChecked: files.length, filesScanned: scanned, skipped, sensitiveFiles, findings };
}

/**
 * Append missing rules to .gitignore. Returns the added rules; existing content is never changed.
 */
function fix(root, result) {
  root = path.resolve(root);
  const gitignorePath = path.join(root, ".gitignore");
  const existing = readIfExists(gitignorePath);
  const matcher = new IgnoreMatcher(existing || "");
  const hasPackageJson = fs.existsSync(path.join(root, "package.json"));

  const toAdd = [];
  for (const rec of RECOMMENDED_IGNORE) {
    if (rec.pattern === "node_modules/" && !hasPackageJson) continue;
    if (rec.probe === null) continue;
    if (!matcher.ignores(rec.probe)) toAdd.push(rec.pattern);
  }
  if (toAdd.includes(".env.*")) toAdd.push("!.env.example");

  const withRecommended = new IgnoreMatcher((existing || "") + "\n" + toAdd.join("\n"));
  for (const finding of result.findings) {
    if (finding.code !== "not-gitignored") continue;
    if (!withRecommended.ignores(finding.file)) {
      toAdd.push("/" + finding.file);
      withRecommended.add("/" + finding.file);
    }
  }

  if (toAdd.length === 0) return [];

  const needsNewline = existing && !existing.endsWith("\n");
  const block = (needsNewline ? "\n" : "") + (existing ? "\n" : "") + "# added by echeck-cli\n" + toAdd.join("\n") + "\n";
  fs.appendFileSync(gitignorePath, block);
  return toAdd;
}

module.exports = { check, fix, sensitiveKind, isTestFile, IgnoreMatcher };
