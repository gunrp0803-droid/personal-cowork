# Repository guidance

This repository contains the Personal Cowork skill, its standard-library task-state helper, plugin metadata, examples, and tests. Keep changes inside the user's requested project scope.

## Updates and GitHub

The repository owner requested a public GitHub repository and commit/push after each requested project update on 2026-10-01. This authorization covers completed updates requested by that user in this project.

- Finish the authorized changes, run the checks relevant to them, and inspect the final diff before committing.
- Commit and push each completed update to the existing remote and current verified branch without asking for the same permission again.
- Confirm the remote belongs to this project, and verify local and remote commit hashes after pushing.
- After a successful push of a requested update to this repository's `main`, run the owner's authorized account-plugin synchronization as the final step of the same task. Read the existing private sync configuration and `after-push-instructions.md` in the owner's task workspace under `work/plugin-sync/`; follow `docs/automatic-updates.md`. Verify the account read-back before reporting synchronization as complete. If blocked, report the push and the exact sync blocker separately.
- Include only this update's intended files. Preserve unrelated or unfinished work. Do not create empty commits.
- Keep credentials, personal machine paths, runtime task records, and private task inputs out of commits.
- Do not force-push, merge pull requests, create releases, or publish to plugin catalogs unless separately authorized.
- If the remote has changed, resolve that state safely before pushing and report any blocker. Do not claim a failed push succeeded.

This policy applies when carrying out requested updates. It does not create a background watcher or authorize arbitrary changes to other repositories.

The owner separately requested GitHub-to-ChatGPT updates for their existing private Personal Cowork plugin on 2026-10-01, then replaced hourly polling with synchronization immediately after the agent's verified commit/push. The hourly heartbeat is paused. Do not restart periodic monitoring or create a replacement schedule. Synchronize the included skill through Plugin Creator only after this agent successfully pushes a requested update to this repository's `main`, preserving the selected plugin ID, private audience, metadata, and default prompts. Runtime configuration, the saved procedure, and backend IDs stay outside the public repository. A documentation-only push still runs the comparison; identical managed files require no new release. This authorization does not cover other plugins, public catalog publication, new integrations, or executing scripts obtained from future remote commits. Follow `docs/automatic-updates.md`; verify each saved release before advancing sync state.

## Validation and documentation

- The task-state helper supports Python 3.9+ using only the standard library.
- For helper changes, run `python3 -m unittest discover -s tests -v` from the repository root.
- Keep plugin asset and skill reference paths valid, and check affected installation instructions after metadata changes.
- Distinguish source changes, tests, host discovery, account installation, external saves, and publication in reports.
- `verification/` contains dated evidence; normalized paths preserve privacy. Do not present this snapshot as a fresh probe or imply the helper verifies the truth of supplied evidence.

Use clear, concise Korean for the owner. Commit messages should describe the actual change, for example `feat: 작업 실행 및 상태 검증 스킬 추가`.
