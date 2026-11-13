"use strict";

// A zero-dependency .gitignore matcher covering the commonly used syntax
// Supports: comments, negation (!), directory-only (trailing /), anchoring (leading or inner /), *, ?, **, [abc]

function escapeRegex(ch) {
  return ch.replace(/[.+^${}()|\\]/g, "\\$&");
}

function globToRegexSource(glob) {
  let out = "";
  let i = 0;
  while (i < glob.length) {
    const ch = glob[i];
    if (ch === "*") {
      if (glob[i + 1] === "*") {
        const prevSlash = i === 0 || glob[i - 1] === "/";
        const nextSlash = glob[i + 2] === "/";
        const atEnd = i + 2 === glob.length;
        if (prevSlash && nextSlash) {
          out += "(?:.*/)?"; // "**/" matches zero or more directories
          i += 3;
          continue;
        }
        if (prevSlash && atEnd) {
          out += ".*"; // trailing "/**"
          i += 2;
          continue;
        }
        out += "[^/]*";
        i += 2;
        continue;
      }
      out += "[^/]*";
    } else if (ch === "?") {
      out += "[^/]";
    } else if (ch === "[") {
      const end = glob.indexOf("]", i + 2);
      if (end === -1) {
        out += "\\[";
      } else {
        let body = glob.slice(i + 1, end);
        if (body[0] === "!") body = "^" + body.slice(1);
        out += "[" + body.replace(/\\/g, "\\\\") + "]";
        i = end;
      }
    } else if (ch === "\\" && i + 1 < glob.length) {
      out += escapeRegex(glob[i + 1]);
      i += 1;
    } else {
      out += escapeRegex(ch);
    }
    i += 1;
  }
  return out;
}

function parseRule(rawLine) {
  let line = rawLine.replace(/\r$/, "");
  if (line === "" || line.startsWith("#")) return null;

  // Strip trailing whitespace that is not escaped
  line = line.replace(/(?<!\\)\s+$/, "");
  if (line === "") return null;

  let negated = false;
  if (line.startsWith("!")) {
    negated = true;
    line = line.slice(1);
  } else if (line.startsWith("\\!") || line.startsWith("\\#")) {
    line = line.slice(1);
  }

  let dirOnly = false;
  if (line.endsWith("/")) {
    dirOnly = true;
    line = line.slice(0, -1);
  }
  if (line === "") return null;

  const anchored = line.includes("/");
  if (line.startsWith("/")) line = line.slice(1);

  const src = globToRegexSource(line);
  // Unanchored rules can match at any depth
  const prefix = anchored ? "^" : "^(?:.*/)?";
  const regex = new RegExp(prefix + src + "$");
  return { negated, dirOnly, regex, raw: rawLine };
}

class IgnoreMatcher {
  constructor(text) {
    this.rules = [];
    if (text) this.add(text);
  }

  add(text) {
    for (const line of String(text).split("\n")) {
      const rule = parseRule(line);
      if (rule) this.rules.push(rule);
    }
    return this;
  }

  // Does a single path match the rules? The last matching rule wins
  _matchPath(p, isDir) {
    let ignored = false;
    for (const rule of this.rules) {
      if (rule.dirOnly && !isDir) continue;
      if (rule.regex.test(p)) ignored = !rule.negated;
    }
    return ignored;
  }

  // relPath uses "/" separators and is relative to the project root.
  // If a parent directory is ignored, everything inside it is ignored too (same as git).
  ignores(relPath, isDir = false) {
    const normalized = relPath.replace(/\\/g, "/").replace(/^\.\//, "");
    const parts = normalized.split("/");
    for (let i = 1; i < parts.length; i++) {
      if (this._matchPath(parts.slice(0, i).join("/"), true)) return true;
    }
    return this._matchPath(normalized, isDir);
  }
}

module.exports = { IgnoreMatcher, parseRule };
