#!/usr/bin/env bash
# Runs the doctor (src/doctor) with the Python and packages pinned in this repository, from anywhere,
# including shells where mise is not activated. Its options: mise run doctor -- --help.
source "$(dirname "$0")/lib.sh"
# uv and Python are pinned in workbench's mise.toml, so they are looked up from its folder.
cd "$REPOSITORY_DIR" || exit
exec uv run --quiet --frozen doctor "$@"
