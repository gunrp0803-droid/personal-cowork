# Repository guidance

This repository contains the Personal Cowork skill, its standard-library task-state helper, plugin metadata, examples, and tests. Keep changes inside the user's requested project scope.

## Updates and GitHub

The repository owner requested a public GitHub repository and commit/push after each requested project update on 2026-10-01. This authorization covers completed updates requested by that user in this project.

- Finish the authorized changes, run the checks relevant to them, and inspect the final diff before committing.
- Commit and push each completed update to the existing remote and current verified branch without asking for the same permission again.
- Confirm the remote belongs to this project, and verify local and remote commit hashes after pushing.
- Include only this update's intended files. Preserve unrelated or unfinished work. Do not create empty commits.
- Keep credentials, personal machine paths, runtime task records, and private task inputs out of commits.
- Do not force-push, merge pull requests, create releases, or publish to plugin catalogs unless separately authorized.
- If the remote has changed, resolve that state safely before pushing and report any blocker. Do not claim a failed push succeeded.

This policy applies when carrying out requested updates. It does not create a background watcher or authorize arbitrary changes to other repositories.

## Validation and documentation

- The task-state helper supports Python 3.9+ using only the standard library.
- For helper changes, run `python3 -m unittest discover -s tests -v` from the repository root.
- Keep plugin asset and skill reference paths valid, and check affected installation instructions after metadata changes.
- Distinguish source changes, tests, host discovery, account installation, external saves, and publication in reports.
- `verification/` contains dated evidence; normalized paths preserve privacy. Do not present this snapshot as a fresh probe or imply the helper verifies the truth of supplied evidence.

Use clear, concise Korean for the owner. Commit messages should describe the actual change, for example `feat: 작업 실행 및 상태 검증 스킬 추가`.
