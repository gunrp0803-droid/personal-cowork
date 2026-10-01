#!/usr/bin/env python3
"""Build portable archives and conversation context; does not install anything."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import quote
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "personal-cowork"
PUBLIC = "https://github.com/gunrp0803-droid/personal-cowork/blob/main/skills/personal-cowork/"
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "work", "outputs", "dist"}
SKIP_SUFFIXES = {".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar", ".sha256",
                 ".pyc", ".pyo", ".pem", ".key", ".p12", ".pfx", ".tmp"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sources(directory, output):
    files = []
    for base, folders, names in os.walk(directory, followlinks=False):
        folders[:] = sorted(name for name in folders if name not in SKIP_DIRS
                            and not (Path(base) / name).is_symlink()
                            and not (Path(base) / name).resolve().is_relative_to(output))
        for name in sorted(names):
            path = Path(base) / name
            lowered = name.lower()
            if (path.is_symlink() or not path.is_file() or name == ".DS_Store"
                    or lowered.startswith((".env", "id_rsa", "id_ed25519", ".build-"))
                    or any(word in lowered for word in ("secret", "credential", "api_key", "token", "private_key", "password"))
                    or path.suffix.lower() in SKIP_SUFFIXES):
                continue
            files.append(path)
    return sorted(files)


def public_links(text, origin):
    def replace(match):
        target = match.group(2)
        if target.startswith(("#", "http://", "https://", "mailto:")):
            return match.group(0)
        file, separator, anchor = target.partition("#")
        resolved = (origin / file).resolve()
        require(resolved.is_relative_to(SKILL) and resolved.is_file(),
                f"invalid local Markdown reference: {target}")
        return f"[{match.group(1)}]({PUBLIC}{quote(resolved.relative_to(SKILL).as_posix())}{separator}{anchor})"
    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", replace, text)


def context(version):
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    front = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
    require(front is not None, "SKILL.md requires valid flat name/description frontmatter")
    fields = [line.split(":", 1) for line in front[1].splitlines()]
    require(len(fields) == 2 and all(len(field) == 2 and field[1].strip() for field in fields),
            "invalid SKILL.md frontmatter")
    metadata = {key.strip(): value.strip() for key, value in fields}
    require(set(metadata) == {"name", "description"} and metadata["name"] == "personal-cowork",
            "invalid SKILL.md frontmatter")
    body = public_links(text[front.end():].strip(), SKILL)
    reference = SKILL / "references" / "task-state.md"
    require("references/task-state.md" in text, "SKILL.md must reference task-state.md")
    resource = public_links(reference.read_text(encoding="utf-8").strip(), reference.parent)
    return (f"# Personal Cowork {version} — ChatGPT conversation context\n\n"
            "Attach or paste this file as conversation context. It does not install a skill or plugin. "
            "Available tools and permissions still apply; helper examples require an accessible local helper.\n\n"
            f"[Canonical skill]({PUBLIC}SKILL.md)\n\n{body}\n\n---\n\n"
            f"Included reference: [task-state.md]({PUBLIC}references/task-state.md)\n\n{resource}\n")


def write_atomic(target, writer):
    require(not target.is_symlink() and (not target.exists() or target.is_file()),
            f"output target must be a regular file: {target}")
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".build-", suffix=".tmp", delete=False) as stream:
        temporary = Path(stream.name)
    try:
        writer(temporary)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return {"path": str(target), "bytes": target.stat().st_size,
            "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}


def archive(target, files, source):
    def write(path):
        with ZipFile(path, "w", compression=ZIP_DEFLATED) as bundle:
            for file in files:
                bundle.write(file, "personal-cowork/" + file.relative_to(source).as_posix())
    result = write_atomic(target, write)
    result["members"] = len(files)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist", help="output directory (default: repository/dist)")
    args = parser.parse_args()
    try:
        output = args.output.expanduser().resolve()
        require(not output.is_relative_to(SKILL) and not SKILL.is_relative_to(output),
                "output directory must not overlap the skill source")
        version = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))["version"]
        require(isinstance(version, str) and bool(re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?", version)),
                "plugin.json requires a safe semantic version")
        exported = context(version)
        plugin_files, skill_files = sources(ROOT, output), sources(SKILL, output)
        output.mkdir(parents=True, exist_ok=True)
        prefix = "personal-cowork-"
        result = {"version": version, "installation_performed": False,
                  "plugin": archive(output / f"personal-cowork-{version}.zip", plugin_files, ROOT),
                  "skill": archive(output / f"{prefix}skill-{version}.zip", skill_files, SKILL),
                  "chatgpt_context": write_atomic(output / f"{prefix}chatgpt-context-{version}.md",
                                                  lambda path: path.write_text(exported, encoding="utf-8"))}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
