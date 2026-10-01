#!/usr/bin/env python3
"""Record Cowork checkpoints; never execute AI, commands, tools, or external actions.

Evidence and check results are supplied by the caller. Passing a recorded check
does not independently prove its semantic truth. File hashes prove byte identity,
not correctness. One writer per task is supported; completed tasks are immutable.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from datetime import datetime, timezone
from uuid import uuid4

SCHEMA = "personal-cowork.task.v1"
TASK_ID = re.compile(r"\d{8}T\d{6}Z-[0-9a-f]{32}\Z")


class StateError(Exception):
    """A rejected operation that must not change the saved state."""


def require(condition, message):
    if not condition:
        raise StateError(message)


def nonempty(value, label):
    require(isinstance(value, str) and bool(value.strip()), f"{label} must be nonempty text")
    return value.strip()


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def relative_path(value):
    nonempty(value, "artifact path")
    path = Path(value)
    require(not path.is_absolute() and ".." not in path.parts,
            "artifact path must be relative to the workspace without '..'")
    require(path.parts and path != Path("."), "artifact path must name a file")
    return path


def ensure_inside(path, workspace):
    require(path.resolve().is_relative_to(workspace), "path escapes the workspace")


def state_location(raw):
    path = Path(raw).expanduser()
    require(".." not in path.parts, "state path must not contain '..'")
    if not path.is_absolute():
        path = Path.cwd() / path
    require(path.name == "task.json" and path.parent.parent.name == "cowork"
            and path.parent.parent.parent.name == "work"
            and bool(TASK_ID.fullmatch(path.parent.name)), "unrecognized state location")
    workspace = path.parent.parent.parent.parent.resolve(strict=True)
    require(workspace.is_dir(), "workspace must be a directory")
    target = workspace / "work" / "cowork" / path.parent.name / "task.json"
    for item in (path.parent.parent.parent, path.parent.parent, path.parent, path):
        require(not item.is_symlink(), "state path and task directories must not be symlinks")
        ensure_inside(item, workspace)
    require(path.resolve() == target, "unrecognized state location")
    return target, workspace


def keys(value, expected, label):
    require(isinstance(value, dict) and set(value) == set(expected), f"invalid {label} fields")


def validate(data, path, workspace):
    keys(data, ("schema", "id", "workspace", "goal", "status", "created_at",
                "updated_at", "steps", "criteria", "artifacts"), "state")
    require(data["schema"] == SCHEMA and data["id"] == path.parent.name,
            "unrecognized state schema or task ID")
    require(data["workspace"] == str(workspace), "state workspace does not match its location")
    nonempty(data["goal"], "goal")
    for field in ("created_at", "updated_at"):
        stamp = datetime.fromisoformat(nonempty(data[field], field))
        require(stamp.tzinfo is not None, f"{field} must include a timezone")
    require(data["status"] in ("active", "completed"), "invalid task status")
    for field, allowed in (("steps", ("pending", "in_progress", "done")),
                           ("criteria", ("pending", "passed", "failed"))):
        items = data[field]
        require(isinstance(items, list) and bool(items), f"{field} must be a nonempty list")
        for index, item in enumerate(items, 1):
            keys(item, ("id", "text", "status", "evidence"), field)
            require(item["id"] == str(index), f"invalid {field} ID")
            nonempty(item["text"], field)
            require(item["status"] in allowed and isinstance(item["evidence"], str),
                    f"invalid {field} status or evidence")
            if item["status"] in ("done", "passed", "failed"):
                nonempty(item["evidence"], "evidence")
        if data["status"] == "completed":
            expected = "done" if field == "steps" else "passed"
            require(all(item["status"] == expected for item in items),
                    "completed task has unfinished checkpoints")
    require(isinstance(data["artifacts"], list), "artifacts must be a list")
    seen = set()
    for item in data["artifacts"]:
        keys(item, ("path", "description", "size", "sha256"), "artifact")
        name = relative_path(item["path"]).as_posix()
        require(item["path"] == name and name not in seen, "duplicate or noncanonical artifact path")
        seen.add(name)
        nonempty(item["description"], "artifact description")
        require(type(item["size"]) is int and item["size"] > 0, "invalid artifact size")
        require(isinstance(item["sha256"], str) and bool(re.fullmatch(r"[0-9a-f]{64}", item["sha256"])),
                "invalid artifact hash")
        ensure_inside(workspace / name, workspace)
        require((workspace / name).resolve() != path, "task state cannot be an artifact")


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "state contains duplicate JSON keys")
        result[key] = value
    return result


def load(raw):
    path, workspace = state_location(raw)
    require(path.is_file() and path.stat().st_size <= 1_048_576, "state must be a file of at most 1 MiB")
    data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_keys)
    validate(data, path, workspace)
    return path, workspace, data


def save(path, workspace, data):
    state_location(str(path))
    validate(data, path, workspace)
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    require(len(payload.encode("utf-8")) <= 1_048_576, "state exceeds 1 MiB")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".task-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def artifact_info(workspace, raw, description):
    relative = relative_path(raw)
    path = workspace / relative
    ensure_inside(path, workspace)
    require(path.is_file(), f"artifact is missing or is not a file: {relative}")
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    require(size > 0, f"artifact is empty: {relative}")
    return {"path": relative.as_posix(), "description": nonempty(description, "description"),
            "size": size, "sha256": digest.hexdigest()}


def init(args):
    workspace = Path(args.workspace).expanduser().resolve(strict=True)
    require(workspace.is_dir(), "workspace must be an existing directory")
    goal = nonempty(args.goal, "goal")
    steps = [nonempty(item, "step") for item in args.step]
    criteria = [nonempty(item, "criterion") for item in args.criterion]
    base = workspace
    for name in ("work", "cowork"):
        base /= name
        require(not base.is_symlink(), "task directories must not be symlinks")
        ensure_inside(base, workspace)
        base.mkdir(exist_ok=True)
    task_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid4().hex
    directory = base / task_id
    directory.mkdir(exist_ok=False)
    path = directory / "task.json"
    stamp = now()
    data = {"schema": SCHEMA, "id": task_id, "workspace": str(workspace), "goal": goal,
            "status": "active", "created_at": stamp, "updated_at": stamp,
            "steps": [{"id": str(i), "text": value, "status": "pending", "evidence": ""}
                      for i, value in enumerate(steps, 1)],
            "criteria": [{"id": str(i), "text": value, "status": "pending", "evidence": ""}
                         for i, value in enumerate(criteria, 1)], "artifacts": []}
    save(path, workspace, data)
    return {"state": str(path), "status": data["status"]}


def update(args):
    path, workspace, data = load(args.state)
    if args.command == "show":
        return {key: data[key] for key in ("id", "goal", "status", "steps", "criteria", "artifacts")}
    require(data["status"] == "active", "completed tasks are immutable; initialize a fresh task")
    if args.command in ("step", "check"):
        field = "steps" if args.command == "step" else "criteria"
        match = next((item for item in data[field] if item["id"] == args.id), None)
        require(match is not None, f"unknown {args.command} ID: {args.id}")
        evidence = args.evidence or ""
        if args.status in ("done", "passed", "failed"):
            evidence = nonempty(evidence, "evidence")
        match.update(status=args.status, evidence=evidence.strip())
    elif args.command == "artifact":
        record = artifact_info(workspace, args.path, args.description)
        require((workspace / record["path"]).resolve() != path, "task state cannot be an artifact")
        data["artifacts"] = [item for item in data["artifacts"] if item["path"] != record["path"]]
        data["artifacts"].append(record)
    elif args.command == "finish":
        require(all(item["status"] == "done" for item in data["steps"]), "all steps must be done")
        require(bool(data["criteria"]) and all(item["status"] == "passed" for item in data["criteria"]),
                "all acceptance criteria must be passed")
        for record in data["artifacts"]:
            current = artifact_info(workspace, record["path"], record["description"])
            require(current == record, f"artifact changed since registration: {record['path']}")
        data["status"] = "completed"
    data["updated_at"] = now()
    save(path, workspace, data)
    return {"state": str(path), "status": data["status"], "operation": args.command}


def parser():
    result = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = result.add_subparsers(dest="command", required=True)
    create = commands.add_parser("init", help="create a fresh task in WORKSPACE/work/cowork")
    create.add_argument("--workspace", required=True)
    create.add_argument("--goal", required=True)
    create.add_argument("--step", action="append", required=True, help="repeat for each planned step")
    create.add_argument("--criterion", action="append", required=True, help="repeat for each acceptance criterion")
    for command in ("show", "step", "check", "artifact", "finish"):
        child = commands.add_parser(command)
        child.add_argument("--state", required=True)
        if command in ("step", "check"):
            child.add_argument("--id", required=True, help="one-based checkpoint ID from show")
            choices = ("pending", "in_progress", "done") if command == "step" else ("passed", "failed")
            child.add_argument("--status", required=True, choices=choices)
            child.add_argument("--evidence", required=command == "check", help="required for done, passed, and failed")
        elif command == "artifact":
            child.add_argument("--path", required=True, help="existing nonempty file, relative to workspace")
            child.add_argument("--description", required=True)
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        result = init(args) if args.command == "init" else update(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (StateError, OSError, ValueError, TypeError, RecursionError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
