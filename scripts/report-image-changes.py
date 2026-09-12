#!/usr/bin/env python3
"""Write a GitHub Actions summary of dependency and Debian package changes."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


def load_manifest(path, required=False):
    manifest = Path(path)
    if not manifest.exists():
        if required:
            raise FileNotFoundError(path)
        return None
    return json.loads(manifest.read_text())


def short_digest(value):
    if not value:
        return "unknown"
    if value.startswith("sha256:"):
        return "sha256:" + value.removeprefix("sha256:")[:12] + "…"
    return value[:12] + ("…" if len(value) > 12 else "")


def base_value(manifest):
    base = manifest.get("base", {})
    tag = base.get("tag", "unknown")
    digest = short_digest(base.get("digest"))
    return f"{tag}@{digest}"


def java_value(manifest):
    java = manifest.get("java", {})
    version = java.get("version", "unknown")
    major = java.get("major")
    return f"{version} (Java {major})" if major is not None else version


def dependency_values(manifest):
    return {
        "FHEM base image": base_value(manifest),
        "signal-cli": manifest.get("signal", {}).get("version", "unknown"),
        "libsignal": manifest.get("libsignal", {}).get("version", "unknown"),
        "Java": java_value(manifest),
        "APT refresh period": manifest.get("apt_refresh_period", "unknown"),
        "Source revision": short_digest(manifest.get("source_revision")),
    }


def dependency_changes(previous, current):
    current_values = dependency_values(current)
    if previous is None:
        return [(name, None, value) for name, value in current_values.items()]
    previous_values = dependency_values(previous)
    return [
        (name, previous_values.get(name), value)
        for name, value in current_values.items()
        if previous_values.get(name) != value
    ]


def package_versions(image):
    command = "dpkg-query -W -f='${binary:Package}\\t${Version}\\n'"
    result = subprocess.run(
        ["docker", "run", "--rm", "--network", "none", "--entrypoint", "/bin/sh",
         image, "-c", command],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    packages = {}
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        name, version = line.split("\t", 1)
        packages[name] = version
    return packages


def package_changes(previous, current):
    names = sorted(set(previous) | set(current))
    return [
        (name, previous.get(name), current.get(name))
        for name in names
        if previous.get(name) != current.get(name)
    ]


def pull_image(image):
    result = subprocess.run(
        ["docker", "pull", image],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return result.returncode == 0, result.stdout.strip()


def code(value):
    if value is None:
        return "—"
    return "`" + str(value).replace("`", "\\`") + "`"


def markdown_table(headers, rows):
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(code(value) for value in row) + " |" for row in rows)
    return lines


def build_summary(current, previous=None, current_image=None, previous_image=None):
    lines = ["## Image changes", ""]
    deps = dependency_changes(previous, current)

    if previous is None:
        lines.append("No previous publication manifest was available; showing the current dependency baseline.")
        lines.append("")
        lines.extend(markdown_table(["Component", "Previous", "Current"], deps))
    elif deps:
        lines.append(f"### Dependency changes ({len(deps)})")
        lines.append("")
        lines.extend(markdown_table(["Component", "Previous", "Current"], deps))
    else:
        lines.append("No dependency changes since the previous successful publication.")

    lines.append("")

    if current_image is None:
        lines.append("No candidate image was built, so no Debian package comparison was needed.")
        return "\n".join(lines) + "\n"

    if previous_image is None:
        lines.append("Debian package comparison skipped because no previous image was specified.")
        return "\n".join(lines) + "\n"

    pulled, output = pull_image(previous_image)
    if not pulled:
        lines.append(
            f"Debian package comparison unavailable because the previous image {code(previous_image)} "
            "could not be pulled."
        )
        if output:
            lines.extend(["", "<details><summary>docker pull output</summary>", "", "```text",
                          output[-4000:], "```", "</details>"])
        return "\n".join(lines) + "\n"

    try:
        previous_packages = package_versions(previous_image)
        current_packages = package_versions(current_image)
    except (subprocess.CalledProcessError, ValueError) as error:
        lines.append(f"Debian package comparison failed: {code(error)}")
        return "\n".join(lines) + "\n"

    packages = package_changes(previous_packages, current_packages)
    if packages:
        upgraded = sum(old is not None and new is not None for _, old, new in packages)
        added = sum(old is None for _, old, _ in packages)
        removed = sum(new is None for _, _, new in packages)
        lines.append(
            f"### Debian package changes ({len(packages)}) — "
            f"{upgraded} changed, {added} added, {removed} removed"
        )
        lines.append("")
        lines.extend(markdown_table(["Package", "Previous", "Current"], packages))
    else:
        lines.append("No Debian package changes compared with the currently published image.")

    return "\n".join(lines) + "\n"


def write_summary(text):
    target = os.getenv("GITHUB_STEP_SUMMARY")
    if target:
        with open(target, "a", encoding="utf-8") as stream:
            stream.write(text)
    else:
        print(text, end="")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--current-manifest", default=".build/dependencies.json")
    parser.add_argument("--previous-manifest", default=".build/published.json")
    parser.add_argument("--current-image")
    parser.add_argument("--previous-image")
    args = parser.parse_args()

    try:
        current = load_manifest(args.current_manifest, required=True)
        previous = load_manifest(args.previous_manifest)
    except (OSError, json.JSONDecodeError) as error:
        print(f"Unable to read dependency manifests: {error}", file=sys.stderr)
        return 1

    summary = build_summary(
        current,
        previous,
        current_image=args.current_image,
        previous_image=args.previous_image,
    )
    write_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
