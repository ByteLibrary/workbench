#!/usr/bin/env bash
# Runs the doctor (src/doctor) with the Python and packages pinned in this repository, from anywhere,
# including shells where mise is not activated. Its options: mise run doctor -- --help.
source "$(dirname "$0")/lib.sh"
exec uv run --quiet --frozen --project "$REPOSITORY_DIR" doctor "$@"
