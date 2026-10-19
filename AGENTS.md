# Agent guide: workbench

Bash scripts that set up the development workspace. Rules and conventions are in the
[handbook](https://github.com/ByteLibrary/handbook); read its `AGENTS.md`
first. Its strict rules apply here.

## This repository
- `setup.sh` runs the scripts in `scripts/` in order. Every script must stay **idempotent**: running it
  again changes nothing that is already correct.
- `scripts/lib.sh` holds shared settings and helpers. Paths and names are defined there once.
- Scripts never change anything outside the workspace without telling the user, and ask before
  changing existing user configuration.
- Files in `workspace/` are copied into the workspace root. Keep the workspace `AGENTS.md`
  tool-agnostic and short.
- When adding a check or a setup step, update the tables in `README.md` in the same change.
- Verify changes with `bash -n` and, when available, `shellcheck`; then run `scripts/doctor.sh`.
