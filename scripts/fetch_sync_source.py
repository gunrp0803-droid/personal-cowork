#!/usr/bin/env python3
"""Fetch a pinned Personal Cowork skill snapshot without executing remote code."""
import argparse
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path, PurePosixPath

REPOSITORY = "https://github.com/gunrp0803-droid/personal-cowork.git"
SKILL_PREFIX = "skills/personal-cowork/"
MAX_FILE = 1024 * 1024
MAX_TOTAL = 4 * MAX_FILE


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(directory, *arguments):
    return subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "-c", "protocol.file.allow=never",
         "-C", str(directory), *arguments], check=True, capture_output=True, timeout=45
    ).stdout


def safe_destination(path):
    path = path.expanduser().absolute()
    require(not any(item.is_symlink() for item in [path, *path.parents]),
            "destination must not use symlinks")
    return path.resolve()


def entry(record):
    metadata, path_bytes = record.split(b"\t", 1)
    mode, kind, blob_bytes = metadata.split()
    path = path_bytes.decode("utf-8")
    blob = blob_bytes.decode("ascii")
    parts = PurePosixPath(path).parts
    require(mode in (b"100644", b"100755") and kind == b"blob",
            "snapshot accepts regular files only")
    require(bool(re.fullmatch(r"[0-9a-f]{40,64}", blob)), "invalid blob ID")
    require(path == "plugin.json" or path.startswith(SKILL_PREFIX), "file outside sync scope")
    require(not path.startswith("/") and "\\" not in path
            and all(part not in ("", ".", "..") for part in path.split("/"))
            and all(part not in (".git", ".env", "__pycache__") for part in parts),
            "unsafe source path")
    return path, blob


def path_key(path):
    return unicodedata.normalize("NFC", path).casefold()


def fetch(mirror, output):
    mirror, output = safe_destination(mirror), safe_destination(output)
    require(not output.exists(), "snapshot destination already exists; use a fresh directory")
    require(not output.is_relative_to(mirror) and not mirror.is_relative_to(output),
            "snapshot and mirror must not overlap")
    mirror.parent.mkdir(parents=True, exist_ok=True)
    if not mirror.exists():
        mirror.mkdir()
        git(mirror, "init", "--bare")
        git(mirror, "remote", "add", "origin", REPOSITORY)
    require(git(mirror, "rev-parse", "--is-bare-repository").strip() == b"true",
            "sync mirror must be a bare repository")
    require(git(mirror, "remote", "get-url", "origin").decode().strip() == REPOSITORY,
            "sync mirror origin mismatch")
    git(mirror, "fetch", "--depth=1", "--filter=blob:none", "origin", "+refs/heads/main:refs/heads/main")
    commit = git(mirror, "rev-parse", "refs/heads/main").decode().strip()
    require(bool(re.fullmatch(r"[0-9a-f]{40}", commit)), "invalid source commit")
    records = git(mirror, "ls-tree", "-rz", "--full-tree", commit,
                  "plugin.json", "skills/personal-cowork").split(b"\0")
    require(len(records) <= 201, "too many sync source files")
    files, path_keys, total = {}, set(), 0
    for record in records:
        if not record:
            continue
        path, blob = entry(record)
        key = path_key(path)
        require(key not in path_keys, "source paths collide on a portable filesystem")
        path_keys.add(key)
        size = int(git(mirror, "cat-file", "-s", blob).strip())
        total += size
        require(0 < size <= MAX_FILE and total <= MAX_TOTAL, "source exceeds size limit")
        content = git(mirror, "cat-file", "blob", blob)
        require(len(content) == size, "source blob size mismatch")
        content.decode("utf-8")
        files[path] = content
    require("plugin.json" in files and SKILL_PREFIX + "SKILL.md" in files,
            "required sync sources missing")
    manifest = json.loads(files["plugin.json"])
    require(manifest.get("name") == "personal-cowork", "source plugin identity mismatch")
    output.mkdir(parents=True)
    for path, content in files.items():
        target = output / path
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(content)
    return {"source": str(output), "repository": REPOSITORY, "branch": "main",
            "source_commit": commit, "files": sorted(files), "bytes": total}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mirror", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(fetch(args.mirror, args.output), ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print("error: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
