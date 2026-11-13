"use strict";

const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { execFileSync } = require("node:child_process");
const { check, fix, sensitiveKind, isTestFile } = require("../src/index");

function makeProject(files) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "echeck-cli-"));
  for (const [name, content] of Object.entries(files)) {
    const full = path.join(dir, name);
    fs.mkdirSync(path.dirname(full), { recursive: true });
    fs.writeFileSync(full, content);
  }
  return dir;
}

function codes(result) {
  return result.findings.map((f) => f.code + ":" + f.file);
}

test("sensitiveKind tells sensitive files from example files", () => {
  assert.ok(sensitiveKind(".env"));
  assert.ok(sensitiveKind("app/.env.production"));
  assert.ok(sensitiveKind("server.pem"));
  assert.ok(sensitiveKind("id_rsa"));
  assert.equal(sensitiveKind(".env.example"), null);
  assert.equal(sensitiveKind("index.js"), null);
});

test("a .env without any .gitignore is an error", () => {
  const dir = makeProject({ ".env": "TOKEN=abc" });
  const result = check(dir);
  assert.deepEqual(codes(result), ["not-gitignored:.env"]);
});

test("a .env covered by .gitignore passes", () => {
  const dir = makeProject({ ".env": "TOKEN=abc", ".gitignore": ".env\n" });
  assert.equal(check(dir).findings.length, 0);
});

test("nested .env files are found too", () => {
  const dir = makeProject({ "apps/web/.env.local": "A=1", ".gitignore": "/.env\n" });
  assert.deepEqual(codes(check(dir)), ["not-gitignored:apps/web/.env.local"]);
});

test(".env.example is not a sensitive file", () => {
  const dir = makeProject({ ".env.example": "TOKEN=", ".gitignore": "" });
  assert.equal(check(dir).sensitiveFiles.length, 0);
});

test("a Dockerfile without .dockerignore coverage gives a warning", () => {
  const dir = makeProject({ ".env": "A=1", ".gitignore": ".env\n", Dockerfile: "FROM node\n" });
  const result = check(dir);
  assert.deepEqual(codes(result), ["not-dockerignored:.env"]);
  assert.equal(result.findings[0].severity, "warning");
});

test("npm publish leak warns, but a \"files\" allowlist does not", () => {
  const a = makeProject({ ".env": "A=1", "package.json": "{\"name\":\"x\"}", ".npmignore": "test/\n", ".gitignore": ".env\n" });
  assert.ok(codes(check(a)).includes("not-npmignored:.env"));

  const b = makeProject({ ".env": "A=1", "package.json": "{\"name\":\"x\",\"files\":[\"src\"]}", ".gitignore": ".env\n" });
  assert.equal(check(b).findings.length, 0);
});

test("hard-coded keys are detected and the preview is masked", () => {
  const key = "AKIA" + "ABCDEFGHIJKLMNOP";
  const dir = makeProject({ "src/app.js": "const k = \"" + key + "\";\n", ".gitignore": "" });
  const result = check(dir);
  assert.equal(result.findings.length, 1);
  assert.equal(result.findings[0].code, "secret-in-source");
  assert.equal(result.findings[0].line, 1);
  assert.ok(!result.findings[0].message.includes(key));
});

test("--no-scan skips content scanning", () => {
  const dir = makeProject({ "a.js": "password = \"supersecret123\"\n", ".gitignore": "" });
  assert.equal(check(dir, { scan: false }).findings.length, 0);
  assert.equal(check(dir, { scan: true }).findings.length, 1);
});

test("files ignored by .gitignore are not content-scanned", () => {
  const dir = makeProject({ "local.js": "password = \"supersecret123\"\n", ".gitignore": "local.js\n" });
  assert.equal(check(dir).findings.length, 0);
});

test("fix adds rules, makes the re-check pass and keeps existing content", () => {
  const dir = makeProject({ ".env": "A=1", ".env.local": "B=2", "server.pem": "x", ".gitignore": "dist/" });
  const before = check(dir);
  assert.ok(before.findings.length >= 3);

  const added = fix(dir, before);
  assert.ok(added.includes(".env"));
  assert.ok(added.includes("!.env.example"));

  const text = fs.readFileSync(path.join(dir, ".gitignore"), "utf8");
  assert.ok(text.startsWith("dist/"));
  assert.equal(check(dir).findings.length, 0);

  // Running it again adds nothing
  assert.deepEqual(fix(dir, check(dir)), []);
});

test("a .env tracked by git is reported as tracked", (t) => {
  try {
    execFileSync("git", ["--version"], { stdio: "ignore" });
  } catch {
    t.skip("git is not installed");
    return;
  }
  const dir = makeProject({ ".env": "A=1", ".gitignore": ".env\n" });
  execFileSync("git", ["init", "-q"], { cwd: dir });
  execFileSync("git", ["add", "-f", ".env"], { cwd: dir });
  const result = check(dir);
  assert.deepEqual(codes(result), ["tracked:.env"]);
});

test("isTestFile recognises test folders and test files", () => {
  assert.ok(isTestFile("tests/support.py"));
  assert.ok(isTestFile("Week7/tests/support.py"));
  assert.ok(isTestFile("src/__tests__/a.js"));
  assert.ok(isTestFile("src/app.test.js"));
  assert.ok(isTestFile("test_login.py"));
  assert.ok(!isTestFile("src/app.js"));
  assert.ok(!isTestFile("latest/app.js")); // Only whole folder names are matched
});

test("fake passwords in test folders are ignored unless --scan-tests is used", () => {
  const dir = makeProject({ "Week7/tests/support.py": "password = \"test1234\"\n", ".gitignore": "" });
  const normal = check(dir);
  assert.equal(normal.findings.length, 0);
  assert.equal(normal.skipped.tests, 1);

  const strict = check(dir, { scanTests: true });
  assert.equal(strict.findings.length, 1);
  assert.equal(strict.findings[0].code, "secret-in-source");
});

test(".env files in test folders are still checked (only content scanning is skipped)", () => {
  const dir = makeProject({ "tests/.env": "A=1", ".gitignore": "" });
  assert.deepEqual(codes(check(dir)), ["not-gitignored:tests/.env"]);
});

test("inline echeck-ignore skips only that line", () => {
  const text = "a = \"password = 'abcdefgh1'\" # echeck-ignore\npassword = \"realsecret99\"\n";
  const dir = makeProject({ "app.py": text, ".gitignore": "" });
  const result = check(dir);
  assert.equal(result.findings.length, 1);
  assert.equal(result.findings[0].line, 2);
});

test("paths listed in .echeckignore are not checked at all", () => {
  const dir = makeProject({
    "demo/app.js": "password = \"hunter2hunter2\"\n",
    "demo/.env": "A=1",
    "src/app.js": "password = \"hunter2hunter2\"\n",
    ".gitignore": "",
    ".echeckignore": "# example project\ndemo/\n",
  });
  const result = check(dir);
  assert.deepEqual(codes(result), ["secret-in-source:src/app.js"]);
  assert.equal(result.skipped.echeckignore, 2);
});
