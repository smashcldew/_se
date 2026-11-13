"use strict";

// File names treated as sensitive (matched against the basename)
const SENSITIVE_FILES = [
  { name: ".env file", test: (b) => b === ".env" || /^\.env\.(?!example$|sample$|template$|dist$).+/.test(b) },
  { name: "Private key / certificate", test: (b) => /\.(pem|key|p12|pfx|jks|keystore)$/i.test(b) },
  { name: "SSH private key", test: (b) => /^id_(rsa|dsa|ecdsa|ed25519)$/.test(b) },
  { name: "Cloud / service credentials", test: (b) => /^(credentials\.json|service-account.*\.json|secrets\.(json|ya?ml)|\.htpasswd|\.netrc|\.pgpass)$/i.test(b) },
  { name: "Package registry token", test: (b) => b === ".npmrc" || b === ".pypirc" },
  { name: "Terraform state", test: (b) => /\.tfstate(\.backup)?$/.test(b) || b === "terraform.tfvars" },
];

// Rules a .gitignore should have at minimum (added by --fix)
const RECOMMENDED_IGNORE = [
  { pattern: ".env", probe: ".env" },
  { pattern: ".env.*", probe: ".env.local" },
  { pattern: "!.env.example", probe: null },
  { pattern: "*.pem", probe: "server.pem" },
  { pattern: "*.key", probe: "server.key" },
  { pattern: "node_modules/", probe: "node_modules/x.js" },
];

// Content scanning: common secret formats
const SECRET_PATTERNS = [
  { name: "AWS Access Key ID", regex: /\b(?:AKIA|ASIA)[0-9A-Z]{16}\b/ },
  { name: "GitHub Token", regex: /\bgh[pousr]_[A-Za-z0-9]{36,}\b/ },
  { name: "Slack Token", regex: /\bxox[baprs]-[A-Za-z0-9-]{10,}\b/ },
  { name: "Google API Key", regex: /\bAIza[0-9A-Za-z_-]{35}\b/ },
  { name: "Stripe Secret Key", regex: /\bsk_live_[0-9a-zA-Z]{24,}\b/ },
  { name: "Discord Bot Token", regex: /\b[MN][A-Za-z\d]{23,25}\.[\w-]{6}\.[\w-]{27,}\b/ },
  { name: "private key block", regex: /-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----/ },
  { name: "password / key assignment", regex: /\b(?:password|passwd|secret|api[_-]?key|token)\b\s*[:=]\s*["'][^"'\s]{8,}["']/i },
];

// Directories that are always skipped
const SKIP_DIRS = new Set([".git", "node_modules", ".hg", ".svn", "dist", "build", "coverage", ".next", "__pycache__", ".venv", "venv"]);

module.exports = { SENSITIVE_FILES, RECOMMENDED_IGNORE, SECRET_PATTERNS, SKIP_DIRS };
