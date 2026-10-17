# Agent guide: ByteLibrary workspace

This directory is the ByteLibrary workspace. It is **not** a git repository: every subdirectory is a
separate repository of the ByteLibrary GitHub organization, named exactly like it on GitHub.

Written by `development-environment/scripts/write-workspace-files.sh`. Change it there, not here.

## Start here
- `organization-handbook/` is the source of truth for domain, architecture, decisions and
  conventions. Read its `AGENTS.md` and `llms.txt` before working in any repository.
- Each repository has its own `AGENTS.md` with repository-specific instructions.

## Strict rules
The strict rules in `organization-handbook/AGENTS.md` apply everywhere, in particular:
- Never add co-author trailers or any agent or tool attribution.
- Never name a specific AI agent, assistant or AI vendor in anything you write.

## Working across repositories
- Run git commands inside the repository they concern. Never commit changes to two repositories as
  if they were one change; open one pull request per repository and link them.
- New repositories are created on GitHub first, then cloned here, then filled:
  `gh repo create ByteLibrary/<name> --private ...` followed by `gh repo clone ByteLibrary/<name>`.
  Repositories are private unless the user says otherwise.

## GitHub access
- `gh` and git use a token that can only access the ByteLibrary organization.
- `gh` must run with `GH_CONFIG_DIR=$HOME/.config/gh-bytelibrary`. Interactive shells get it from the
  workspace `mise.toml`; if your shell does not have it set, set it on each `gh` command.
- git needs nothing extra: repositories under this directory are configured to use the same token.
