"use strict";

const test = require("node:test");
const assert = require("node:assert");
const { IgnoreMatcher } = require("../src/matcher");

test("plain names and wildcards", () => {
  const m = new IgnoreMatcher(".env\n*.log\n");
  assert.ok(m.ignores(".env"));
  assert.ok(m.ignores("sub/dir/.env"));
  assert.ok(m.ignores("a/debug.log"));
  assert.ok(!m.ignores("env.txt"));
});

test("negation: .env.* but keep .env.example", () => {
  const m = new IgnoreMatcher(".env.*\n!.env.example\n");
  assert.ok(m.ignores(".env.local"));
  assert.ok(m.ignores(".env.production"));
  assert.ok(!m.ignores(".env.example"));
});

test("directory rules: a trailing / matches directories and ignores everything inside", () => {
  const m = new IgnoreMatcher("node_modules/\nsecrets/\n");
  assert.ok(m.ignores("node_modules/pkg/index.js"));
  assert.ok(m.ignores("secrets/a.txt"));
  assert.ok(!m.ignores("node_modules")); // a file is not a directory
  assert.ok(m.ignores("node_modules", true));
});

test("anchored rules: a leading / matches only the root", () => {
  const m = new IgnoreMatcher("/.env\n");
  assert.ok(m.ignores(".env"));
  assert.ok(!m.ignores("app/.env"));
});

test("** can span several directory levels", () => {
  const m = new IgnoreMatcher("config/**/*.key\n**/private.pem\n");
  assert.ok(m.ignores("config/a/b/c.key"));
  assert.ok(m.ignores("config/c.key"));
  assert.ok(m.ignores("x/y/private.pem"));
  assert.ok(m.ignores("private.pem"));
  assert.ok(!m.ignores("other/c.key"));
});

test("comments and blank lines are ignored; ? and [] work", () => {
  const m = new IgnoreMatcher("# comment\n\nfile?.txt\nlog[0-9].txt\n");
  assert.ok(m.ignores("file1.txt"));
  assert.ok(!m.ignores("file12.txt"));
  assert.ok(m.ignores("log3.txt"));
  assert.ok(!m.ignores("logx.txt"));
});

test("later rules win", () => {
  const m = new IgnoreMatcher("*.key\n!public.key\n*.key\n");
  assert.ok(m.ignores("public.key"));
});
