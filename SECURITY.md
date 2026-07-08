# Security Policy

## Scope

This is an evals harness, not a production service. The most sensitive thing it
touches is **your Anthropic API key**, used only in the `live`/`judge` modes.

- No key is bundled with the repo, and none is needed for the offline suite.
- You supply your own key via the environment or a local `.env`, which is
  gitignored and must never be committed.
- CI runs [gitleaks](https://github.com/gitleaks/gitleaks) on every push and PR,
  and contributors can enable the same scan locally with `pre-commit` (see
  [`.pre-commit-config.yaml`](.pre-commit-config.yaml)).

The `command`, `http`, and `module` adapters intentionally execute a command,
network call, or Python import **that you supply**. Only point them at code you
trust; running an untrusted `--cmd`/`--url`/`--target` runs untrusted code. Eval
JSON files, by contrast, are pure data and never execute code.

## Reporting a vulnerability

Please **do not** open a public issue for a security problem. Instead, use
GitHub's private **"Report a vulnerability"** flow (Security → Advisories) on
this repository, or email the maintainer listed on the GitHub profile.

Include what it affects, steps to reproduce, and any suggested fix. We aim to
acknowledge reports within a few days.

## If you leak a key

If an API key is ever committed or otherwise exposed, **rotate it immediately**
in the [Anthropic console](https://console.anthropic.com/) — rotation, not a
revert, is what actually protects you, since the old commit remains in history.
