# echeck-cli

English | [繁體中文](README.zh-TW.md)

A zero-dependency CLI and library that checks your secrets (`.env` files, private keys, credentials) are covered by `.gitignore` / `.dockerignore` / `.npmignore`, are not tracked by git, and are not hard-coded in your source code.

The command is `echeck`.

## What it checks

| Code | Level | Description |
| --- | --- | --- |
| `tracked` | error | A sensitive file is already tracked by git (it is in your history) |
| `not-gitignored` | error | A sensitive file is not covered by `.gitignore` |
| `secret-in-source` | error | Source code seems to contain a hard-coded AWS / GitHub / Slack / Discord / Stripe key, private key block or password |
| `not-dockerignored` | warning | The project has a Dockerfile but `.dockerignore` does not exclude a sensitive file |
| `not-npmignored` | warning | The project can be published with `npm publish` but a sensitive file is not excluded |

Files treated as sensitive: `.env`, `.env.*` (except `.env.example`), `*.pem`, `*.key`, `*.p12`, `id_rsa` and friends, `credentials.json`, `.npmrc`, `.pypirc`, `*.tfstate`, and more.

## Install and use

```bash
# run without installing (checks the current folder)
npx echeck-cli

# or install globally
npm install -g echeck-cli
echeck ./my-project
```

### Options

```
--fix         Add missing rules to .gitignore automatically
--no-scan     Skip scanning source files for hard-coded secrets
--scan-tests  Also scan the contents of test folders / test files (skipped by default)
--json        Print the result as JSON (useful in CI)
--strict      Treat warnings as failures too
-v, --version Show the version
-h, --help    Show this help
```

Exit codes: `0` no problems, `1` problems found, `2` error.

### Silencing false positives

Content scanning only looks at patterns, so fake credentials in tests can look like real secrets. There are three ways to deal with that:

1. **Test folders are skipped by default.** The *contents* of `test/`, `tests/`, `__tests__/`, `spec/`, `fixtures/`, `*.test.js`, `test_*.py` and similar are not scanned. Sensitive files inside them (such as a `.env`) are still checked. Use `--scan-tests` to include them.
2. **Inline ignore.** Add an `echeck-ignore` comment to skip a single line:
   ```python
   PASSWORD = "test1234"  # echeck-ignore
   ```
3. **`.echeckignore`.** Create it in the project root, using the same syntax as `.gitignore`. Listed paths are not checked at all:
   ```
   # example projects and demo data
   demo/
   docs/examples/
   ```

### Example output

```
[error] .env
       .env file is tracked by git (adding it to .gitignore now will not untrack it). Run: git rm --cached .env and rotate any exposed secrets.
[warn]  .env
       .env file is not covered by .dockerignore and may be copied into the image by COPY . .
[error] src/a.js:1
       Possible GitHub Token (ghp_…****) hard-coded in source.
```

Only the first 4 characters of a detected secret are shown; it is never printed in full.

### Use it in CI or before committing

```bash
# package.json
"scripts": { "check:secrets": "echeck --strict" }
```

## Use as a library

```js
const { check, fix } = require("echeck-cli");

const result = check("./my-project", { scan: true });
console.log(result.findings);

if (result.findings.length > 0) {
  const added = fix("./my-project", result); // returns the rules that were added
}
```

`check()` returns `{ root, filesChecked, filesScanned, skipped, sensitiveFiles, findings }`.
Options: `{ scan: true, scanTests: false }`.
Each finding has `severity`, `code`, `file` and `message`; content-scan findings also have `line`.

## Limitations

- Only the `.gitignore` in the project root (and `.git/info/exclude`) is read. `.gitignore` files in subfolders are not handled.
- Content scanning uses regular expressions for common formats, so it can miss things or report false positives. It is not a replacement for a dedicated secret scanner.
- `--fix` only *adds* rules. It does not run `git rm --cached` for you, and it cannot rotate secrets that have already leaked.
- If a secret has already been pushed to a remote, updating `.gitignore` is not enough. Revoke and replace the secret immediately.

## Development

```bash
npm test   # uses node:test, requires Node.js 18+
```

## License

MIT
