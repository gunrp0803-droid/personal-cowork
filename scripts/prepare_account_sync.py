#!/usr/bin/env python3
"""Prepare a guarded account overlay; never call an API, execute source, or save sync success.

Supply the complete get_plugin_files inventory with relevant UTF-8 contents. Save
state_candidate only after upload and readback verification, replacing its null
release_id with the verified release. Unmanaged files remain intact. No deletion
is supported. This helper is intended to run from a trusted local installation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

NAME = "personal-cowork"
PREFIX = "skills/personal-cowork/"
MANIFESTS = ("plugin.json", ".codex-plugin/plugin.json")
SCHEMA = "personal-cowork.account-sync.v1"
REPOSITORY = "https://github.com/gunrp0803-droid/personal-cowork"
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "work", "outputs", "dist"}
SKIP_SUFFIXES = {".pyc", ".pyo", ".pem", ".key", ".p12", ".pfx", ".zip", ".tmp"}
SEMVER = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
                    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
                    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?\Z")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def safe_path(value):
    require(isinstance(value, str) and value and "\\" not in value and "\0" not in value,
            "file paths must be safe relative POSIX paths")
    path = PurePosixPath(value)
    require(not path.is_absolute() and ".." not in path.parts and str(path) == value and value != ".",
            f"unsafe file path: {value}")
    return value


def local_path(value):
    path = value.expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    require(".." not in path.parts, "source and output paths must not contain '..'")
    require(not any(item.is_symlink() for item in (path, *path.parents)),
            "source and output paths must not use symlink parents")
    return path


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def parse_json(text):
    return json.loads(text, object_pairs_hook=unique_keys)


def semver(value):
    match = SEMVER.fullmatch(value) if isinstance(value, str) else None
    require(match is not None, f"invalid semantic version: {value}")
    prerelease = match[4]
    parts = tuple(prerelease.split(".")) if prerelease else ()
    require(all(not part.isdigit() or part == "0" or not part.startswith("0") for part in parts),
            "prerelease numeric identifiers must not have leading zeros")
    order = tuple((0, int(part)) if part.isdigit() else (1, part) for part in parts)
    return tuple(map(int, match.group(1, 2, 3))), int(prerelease is None), order


def private_file(name):
    lowered = name.lower()
    return (name == ".DS_Store" or lowered.startswith((".env", "id_rsa", "id_ed25519"))
            or any(word in lowered for word in ("secret", "credential", "api_key", "token", "private_key", "password"))
            or Path(name).suffix.lower() in SKIP_SUFFIXES)


def canonical(source):
    manifest_path = source / MANIFESTS[0]
    require(manifest_path.is_file() and not manifest_path.is_symlink(), "source plugin.json must be a regular file")
    manifest = parse_json(manifest_path.read_text(encoding="utf-8"))
    require(isinstance(manifest, dict) and manifest.get("name") == NAME, "source plugin identity mismatch")
    version = manifest.get("version")
    semver(version)
    skill = source / "skills" / NAME
    require(skill.is_dir() and not skill.is_symlink() and not skill.parent.is_symlink(),
            "source skill directories must be real directories")
    files = {}
    for base, folders, names in os.walk(skill, followlinks=False):
        folders[:] = sorted(name for name in folders if name not in SKIP_DIRS and not private_file(name))
        for name in folders:
            require(not (Path(base) / name).is_symlink(), "symlink in canonical skill")
        for name in sorted(names):
            if private_file(name):
                continue
            path = Path(base) / name
            require(path.is_file() and not path.is_symlink(), "canonical skill files must be regular files")
            data = path.read_bytes()
            data.decode("utf-8")  # Account text inventories cannot safely compare binary skill files.
            files[safe_path(path.relative_to(source).as_posix())] = data
    entry = PREFIX + "SKILL.md"
    require(entry in files, "canonical SKILL.md is missing")
    front = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", files[entry].decode("utf-8"), re.DOTALL)
    require(front is not None and len(re.findall(r"^name:\s*personal-cowork\s*$", front[1], re.MULTILINE)) == 1
            and len(re.findall(r"^name:", front[1], re.MULTILINE)) == 1, "canonical skill frontmatter identity mismatch")
    fingerprint = hashlib.sha256()
    for label, data in [("source-version", version.encode("utf-8")), *sorted(files.items())]:
        encoded = label.encode("utf-8")
        fingerprint.update(len(encoded).to_bytes(8, "big") + encoded + len(data).to_bytes(8, "big") + data)
    return version, files, fingerprint.hexdigest()


def inventory(value, plugin_id):
    require(isinstance(value, dict), "inventory must be a JSON object")
    value = value.get("result", value)
    require(isinstance(value, dict) and isinstance(value.get("plugin"), dict), "inventory plugin metadata missing")
    plugin = value["plugin"]
    require(plugin.get("plugin_id") == plugin_id and plugin.get("name") == NAME
            and plugin.get("scope") == "USER" and plugin.get("discoverability") == "PRIVATE",
            "expected exact private USER personal-cowork plugin identity")
    require(isinstance(plugin.get("current_release_id"), str) and bool(plugin["current_release_id"]),
            "current release ID missing")
    semver(plugin.get("version"))
    require(isinstance(value.get("files"), list) and isinstance(value.get("contents"), dict),
            "inventory files and contents are required")
    files = {}
    for item in value["files"]:
        require(isinstance(item, dict), "invalid inventory file record")
        name = safe_path(item.get("path"))
        require(name not in files and type(item.get("size_bytes")) is int and item["size_bytes"] >= 0,
                "duplicate file or invalid byte size")
        files[name] = item["size_bytes"]
    require(all(safe_path(name) in files for name in value["contents"]), "contents contain unlisted files")
    return plugin, files, value["contents"], value.get("next_offset")


def state_record(value, plugin_id):
    require(isinstance(value, dict) and value.get("schema") == SCHEMA and value.get("plugin_id") == plugin_id,
            "sync state schema or plugin identity mismatch")
    require(isinstance(value.get("release_id"), str) and bool(value["release_id"]), "state must record a verified release ID")
    semver(value.get("version"))
    require(isinstance(value.get("payload_hash"), str) and bool(re.fullmatch(r"[0-9a-f]{64}", value["payload_hash"])),
            "invalid state payload hash")
    for field in ("skill_hashes", "manifest_hashes"):
        require(isinstance(value.get(field), dict), f"state {field} missing")
        for name, digest in value[field].items():
            safe_path(name)
            require((name.startswith(PREFIX) if field == "skill_hashes" else name in MANIFESTS)
                    and isinstance(digest, str) and bool(re.fullmatch(r"[0-9a-f]{64}", digest)),
                    "invalid tracked state path or hash")
    require(PREFIX + "SKILL.md" in value["skill_hashes"] and MANIFESTS[0] in value["manifest_hashes"],
            "state must track the canonical skill and root manifest")
    return value


def prepare(source, current, plugin_id, previous=None, commit=None):
    source_version, desired, payload = canonical(source)
    plugin, listed, contents, next_offset = inventory(current, plugin_id)
    previous = state_record(previous, plugin_id) if previous is not None else None
    report = {"status": None, "plugin_id": plugin_id, "expected_release_id": plugin["current_release_id"],
              "source_version": source_version, "source_commit": commit, "payload_hash": payload,
              "current_version": plugin["version"], "archive": None, "state_candidate": None}
    def blocked(status, reason, **extra):
        report.update(status=status, reason=reason, **extra)
        return report, {}
    if next_offset is not None:
        return blocked("blocked_incomplete_inventory", "complete all inventory pages first")
    if previous:
        obsolete = sorted(set(previous["skill_hashes"]) - set(desired))
        if obsolete:
            return blocked("blocked_unsupported_deletion", "overlay API cannot remove formerly managed files", obsolete_paths=obsolete)
    tracked = set(previous["skill_hashes"]) | set(previous["manifest_hashes"]) if previous else set()
    relevant = (set(desired) & set(listed)) | (set(MANIFESTS) & set(listed)) | tracked
    missing = sorted(name for name in relevant if name not in contents or not isinstance(contents[name], str)
                     or len(contents[name].encode("utf-8")) != listed.get(name))
    if MANIFESTS[0] not in listed:
        missing.append(MANIFESTS[0])
    if missing:
        return blocked("blocked_incomplete_inventory", "read relevant text files or obtain the complete archive", missing_paths=missing)
    actual = {name: contents[name].encode("utf-8") for name in relevant}
    manifests = {}
    for name in MANIFESTS:
        if name in actual:
            value = parse_json(actual[name].decode("utf-8"))
            require(isinstance(value, dict) and value.get("name") == NAME, "account manifest identity mismatch")
            semver(value.get("version"))
            manifests[name] = value
    changed = {name: data for name, data in desired.items() if actual.get(name) != data}
    current_versions = [plugin["version"], *[value["version"] for value in manifests.values()]]
    newest = max(current_versions, key=semver)
    same_versions = all(semver(value) == semver(plugin["version"]) for value in current_versions)
    matches = not changed and same_versions and semver(source_version) <= semver(newest)
    # Actual content wins over stale local state after a successful upload whose
    # response/state save was lost. No update is needed even for a lower source version.
    if matches:
        version, overlay = plugin["version"], {}
        report["status"] = "noop"
    else:
        if previous:
            baseline = {**previous["skill_hashes"], **previous["manifest_hashes"]}
            drift = sorted(name for name, digest in baseline.items() if sha(actual[name]) != digest)
            if previous["release_id"] != plugin["current_release_id"] or previous["version"] != plugin["version"] or drift:
                return blocked("conflict", "account changed since the last verified sync", changed_paths=drift,
                               previous_release_id=previous["release_id"])
        core = semver(newest)[0]
        version = source_version if semver(source_version) > semver(newest) else f"{core[0]}.{core[1]}.{core[2] + 1}"
        overlay = dict(changed)
        for name, value in manifests.items():
            value["version"] = version
            if name == MANIFESTS[0] and "repository" not in value:
                value["repository"] = REPOSITORY
            overlay[name] = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        report["status"] = "ready"
    manifest_bytes = {name: overlay.get(name, actual[name]) for name in manifests}
    report.update(version=version, changed_paths=sorted(overlay), preserved_paths=sorted(set(listed) - set(overlay)),
                  state_candidate={"schema": SCHEMA, "plugin_id": plugin_id,
                                   "release_id": plugin["current_release_id"] if not overlay else None,
                                   "version": version, "source_version": source_version, "source_commit": commit,
                                   "payload_hash": payload, "skill_hashes": {name: sha(data) for name, data in sorted(desired.items())},
                                   "manifest_hashes": {name: sha(data) for name, data in manifest_bytes.items()}})
    return report, overlay


def atomic(target, writer):
    require(not target.is_symlink() and (not target.exists() or target.is_file()), "output target must be a regular file")
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".sync-", delete=False) as stream:
        temporary = Path(stream.name)
    try:
        writer(temporary)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def write_archive(path, overlay):
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        for name, data in sorted(overlay.items()):
            entry = ZipInfo(NAME + "/" + safe_path(name), date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type, entry.create_system, entry.external_attr = ZIP_DEFLATED, 3, 0o100644 << 16
            archive.writestr(entry, data)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "current", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--plugin-id", required=True)
    parser.add_argument("--state", type=Path)
    parser.add_argument("--commit", help="optional observed 40-character source commit SHA")
    args = parser.parse_args(argv)
    try:
        source, output = local_path(args.source).resolve(strict=True), local_path(args.output).resolve()
        require(source.is_dir() and not output.is_relative_to(source) and not source.is_relative_to(output),
                "output directory must not overlap the source checkout")
        require(bool(args.plugin_id.strip()), "expected plugin ID is required")
        require(args.commit is None or bool(re.fullmatch(r"[0-9a-fA-F]{40}", args.commit)), "invalid source commit SHA")
        current = parse_json(args.current.read_text(encoding="utf-8"))
        previous = parse_json(args.state.read_text(encoding="utf-8")) if args.state else None
        report, overlay = prepare(source, current, args.plugin_id, previous, args.commit.lower() if args.commit else None)
        output.mkdir(parents=True, exist_ok=True)
        report_path = output / "account-sync-report.json"
        archive_path = output / f"{NAME}-account-sync-{report.get('version', 'blocked')}-{report['payload_hash'][:12]}.zip"
        input_paths = {args.current.resolve(), args.state.resolve() if args.state else None}
        require(report_path not in input_paths and archive_path not in input_paths, "outputs would overwrite inventory or state")
        if overlay:
            atomic(archive_path, lambda path: write_archive(path, overlay))
            report["archive"] = str(archive_path)
            report["archive_sha256"] = sha(archive_path.read_bytes())
        report["report_path"] = str(report_path)
        atomic(report_path, lambda path: path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"))
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] in ("ready", "noop") else 2
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(json.dumps({"status": "error", "reason": str(error)}, ensure_ascii=False))
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
