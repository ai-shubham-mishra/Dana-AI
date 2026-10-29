# Dana AI: working agreements

These preferences apply to every session in this repo. The agent's own memory lives in `backend/agent/config/AGENTS.md`, and `frontend/AGENTS.md` is Next.js boilerplate. This file covers the repo workflow.

## Branches and issues

- `main` is the release branch. Only the owner merges to `main`. Do not merge to `main`.
- `staging` is the integration branch. Every issue and feature merges to `staging` first, after testing.
- For every new feature or bug fix, open an issue first, then create a branch linked to it:
  `gh issue develop <n> --name feature/<n>-<slug> --base staging` (or `bugfix/<n>-<slug>`). Stacked work may use another branch as `--base`; say so in the issue.
- Every issue must be linked to its working branch when it is created. Also link closed and past issues to their branches.
- Push the branch, open a PR into `staging` whose body contains `Refs #<n>`, and do not close the issue until it is verified.
- Keep scope to this repo only.

## Commits

- Commit often, one logical change per commit.
- Prefix each commit subject with its type and issue number: `(feature) #<n> ...` or `(bugfix) #<n> ...`.
- Include the trailer `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`.
- Never stage unrelated files. Leave pre-existing working-tree changes alone.

## Configuration and secrets

- Never edit, print, or commit `.env` files. Tell the owner which values to add.
- The JWT verification secret is Key Vault secret `JWT-MASTER-TOKEN`. The agent has read-only Key Vault access.

## Documentation

- Keep `README.md` current: architecture, setup, configuration, and the git workflow.
- Do not create other markdown files unless asked.
