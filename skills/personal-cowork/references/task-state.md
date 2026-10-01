# Persistent task state

Use this only for multi-step work that benefits from durable checkpoints. The helper is a Python 3 standard-library CLI; it does not execute the actual work or call an AI service. A single lead agent writes each task. Helpers and subagents return evidence to that writer.

Locate `scripts/task_state.py` relative to this skill directory, not the task workspace. Replace the example script and workspace paths with observed absolute paths. The generated state lives in the workspace, never in the installed plugin.

## Start

```sh
python3 /path/to/personal-cowork/scripts/task_state.py init \
  --workspace /path/to/task-workspace \
  --goal "Create a report from the provided CSV" \
  --step "Inspect and reconcile the source records" \
  --step "Create and inspect the report" \
  --criterion "Report totals match the source records" \
  --criterion "Report file exists and required sections were inspected"
```

`--workspace` must identify an existing directory; create an authorized task directory first if needed. `init` returns a JSON object containing the absolute `state` path. Use that returned path for subsequent commands; do not derive an ID. Set the actual criteria before execution, and choose steps large enough to represent meaningful milestones.

## Update from actual evidence

```sh
python3 /path/to/personal-cowork/scripts/task_state.py step \
  --state /path/to/task.json --id 1 --status in_progress

python3 /path/to/personal-cowork/scripts/task_state.py step \
  --state /path/to/task.json --id 1 --status done \
  --evidence "Read source CSV and reconciled the included rows"

python3 /path/to/personal-cowork/scripts/task_state.py check \
  --state /path/to/task.json --id 1 --status passed \
  --evidence "Independently calculated total agrees with the final report"

python3 /path/to/personal-cowork/scripts/task_state.py artifact \
  --state /path/to/task.json --path outputs/report.md \
  --description "Final report inspected for required content"
```

`done`, `passed`, and `failed` require nonempty evidence. Evidence should name the actual check and result; avoid vague text such as "looks good". `--path` is workspace-relative and must resolve to a nonempty file inside that workspace. It registers byte size and SHA-256. Re-register after a legitimate final edit. Paths escaping the workspace, including through a symlink, are rejected.

If required input is missing, leave the affected step `pending` and use its `--evidence` to record the blocker and next action. Do not mark the task finished. The helper does not ask the user or arrange a future wakeup; use the host's supported mechanisms when the task requires them.

## Resume and finish

```sh
python3 /path/to/personal-cowork/scripts/task_state.py show \
  --state /path/to/task.json

python3 /path/to/personal-cowork/scripts/task_state.py finish \
  --state /path/to/task.json
```

`show` reads the saved goal, next unfinished work, evidence, and artifacts. Recheck actual artifacts and external state before continuing. If a source changed, return affected steps to `pending` and record the affected criteria as `failed` with a reason before redoing them. This helper has a fixed task goal and step/criterion list; when the user changes the goal or that list, start a fresh task and reference the previous state in the new evidence instead of editing JSON by hand.

`finish` accepts only tasks whose steps are all done and whose criteria are all passed, each with evidence. Registered files must exist, remain nonempty, and retain their fingerprints. Register local deliverables before finishing; a no-file task can finish with verified steps and criteria alone. After completion, helper mutations are rejected. The helper cannot judge whether recorded evidence is true or whether content is correct; the executing agent must perform those checks.

## Without Python

When filesystem tools exist but Python does not, keep a concise `work/cowork/task.md` with:

- Goal and input locations.
- Authorized scope and acceptance criteria.
- Steps with pending / in progress / done and evidence.
- Checks with pending / passed / failed and evidence.
- Artifact paths, performed verification, and next action or blocker.

Use supported tools to verify files before completion. Do not claim the CLI's fingerprint gate ran. If no writable filesystem exists, use the host's plan/conversation state and disclose the persistence limit only when it matters.
