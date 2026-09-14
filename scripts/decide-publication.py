#!/usr/bin/env python3
"""Decide whether a tested candidate image has meaningful runtime changes."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


PERL_MODULES = (
    "Readonly::XS",
    "List::MoreUtils",
    "Crypt::Rijndael",
    "Crypt::Random",
    "Crypt::Bcrypt",
    "Crypt::PBKDF2",
    "LWP::UserAgent",
    "MIME::Base64",
    "Time::HiRes",
    "Digest::MD5",
    "base",
    "IO::File",
    "Net::SIP",
    "Protocol::DBus",
    "Math::Round",
    "AI::FANN",
)

RUNTIME_FILES = (
    "/docker/pre-start.sh",
    "/etc/dbus-1/system.d/org.asamk.Signal.conf",
    "/usr/share/dbus-1/system-services/org.asamk.Signal.service",
)


def load_manifest(path, required=False):
    file = Path(path)
    if not file.exists():
        if required:
            raise FileNotFoundError(path)
        return None
    return json.loads(file.read_text())


def runtime_dependency_values(manifest):
    if manifest is None:
        return {}
    return {
        "FHEM base image": (
            manifest.get("base", {}).get("tag"),
            manifest.get("base", {}).get("digest"),
        ),
        "signal-cli artifact": (
            manifest.get("signal", {}).get("version"),
            manifest.get("signal", {}).get("sha256"),
        ),
        "libsignal artifact": (
            manifest.get("libsignal", {}).get("version"),
            manifest.get("libsignal", {}).get("sha256"),
        ),
        "Java artifact": (
            manifest.get("java", {}).get("version"),
            manifest.get("java", {}).get("sha256"),
        ),
    }


def changes(previous, current):
    names = sorted(set(previous) | set(current))
    return [
        (name, previous.get(name), current.get(name))
        for name in names
        if previous.get(name) != current.get(name)
    ]


def run_in_image(image, entrypoint, args):
    result = subprocess.run(
        ["docker", "run", "--rm", "--network", "none", "--entrypoint", entrypoint, image, *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit status {result.returncode}"
        raise RuntimeError(f"{entrypoint} failed in {image}: {detail}")
    return result.stdout


def package_versions(image):
    output = run_in_image(
        image,
        "/bin/sh",
        ["-c", "dpkg-query -W -f='${binary:Package}\\t${Version}\\n'"],
    )
    result = {}
    for line in output.splitlines():
        if line.strip():
            name, version = line.split("\t", 1)
            result[name] = version
    return result


def perl_module_versions(image):
    # Read versions from module source metadata instead of requiring the modules.
    # Requiring XS modules can fail while merely inspecting an older image if an
    # optional/transitive runtime dependency is not loadable in the probe process.
    module_list = " ".join(PERL_MODULES)
    program = (
        "use Module::Metadata; "
        f"my @modules = qw({module_list}); "
        "for my $module (@modules) { "
        "my $info = Module::Metadata->new_from_module($module); "
        "die \"$module: metadata not found\\n\" unless $info; "
        "my $version = $info->version; "
        "$version = 'unknown' unless defined $version; "
        "print \"$module\\t$version\\n\"; "
        "}"
    )
    output = run_in_image(
        image,
        "/usr/bin/perl",
        ["-I", "/usr/src/app/3rdparty/lib/perl5", "-e", program],
    )
    result = {}
    for line in output.splitlines():
        if line.strip():
            name, version = line.split("\t", 1)
            result[name] = version
    return result


def runtime_file_fingerprints(image):
    files = " ".join(RUNTIME_FILES)
    command = (
        f"for file in {files}; do "
        "if [ -f \"$file\" ]; then "
        "printf '%s\\t' \"$file\"; "
        "sha256sum \"$file\" | awk '{printf \"%s@\", $1}'; "
        "stat -c '%a:%u:%g' \"$file\"; "
        "else printf '%s\\tMISSING\\n' \"$file\"; fi; "
        "done"
    )
    output = run_in_image(image, "/bin/sh", ["-c", command])
    result = {}
    for line in output.splitlines():
        if line.strip():
            name, fingerprint = line.split("\t", 1)
            result[name] = fingerprint
    return result


def image_config(image):
    result = subprocess.run(
        ["docker", "image", "inspect", image, "--format", "{{json .Config}}"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit status {result.returncode}"
        raise RuntimeError(f"docker image inspect failed for {image}: {detail}")
    config = json.loads(result.stdout)
    keys = (
        "Env",
        "Entrypoint",
        "Cmd",
        "WorkingDir",
        "User",
        "ExposedPorts",
        "Volumes",
        "Healthcheck",
        "StopSignal",
    )
    return {key: config.get(key) for key in keys}


def image_state(image):
    return {
        "Debian packages": package_versions(image),
        "Perl/CPAN modules": perl_module_versions(image),
        "custom runtime files": runtime_file_fingerprints(image),
        "container configuration": image_config(image),
    }


def pull_image(image):
    result = subprocess.run(
        ["docker", "pull", image],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stdout.strip() or f"docker pull failed for {image}")


def analyze(current_manifest, previous_manifest, current_image, previous_image):
    if previous_manifest is None:
        return True, {"baseline": [("Previous publication", None, "not available")]}

    pull_image(previous_image)
    previous_state = image_state(previous_image)
    current_state = image_state(current_image)

    details = {}
    dependency_diff = changes(
        runtime_dependency_values(previous_manifest),
        runtime_dependency_values(current_manifest),
    )
    if dependency_diff:
        details["runtime dependencies"] = dependency_diff

    for category in previous_state:
        diff = changes(previous_state[category], current_state[category])
        if diff:
            details[category] = diff

    return bool(details), details


def code(value):
    if value is None:
        return "—"
    if isinstance(value, (list, tuple, dict)):
        value = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return "`" + str(value).replace("`", "\\`") + "`"


def summary(publish_required, details):
    lines = ["## Publication decision", ""]
    if publish_required:
        lines.append("**Publish required: yes.** Meaningful runtime changes were detected.")
    else:
        lines.append(
            "**Publish required: no.** The tested candidate is runtime-equivalent to the "
            "currently published image, so `:automated` will not be moved."
        )
    lines.append("")

    if not publish_required:
        lines.append(
            "Checked: runtime dependency artifacts, Debian package versions, Perl/CPAN module "
            "versions, custom runtime file content/permissions, and container runtime configuration."
        )
        lines.append("")
        return "\n".join(lines) + "\n"

    for category, rows in details.items():
        lines.append(f"### {category} ({len(rows)})")
        lines.append("")
        lines.extend([
            "| Item | Previous | Current |",
            "| --- | --- | --- |",
        ])
        for name, previous, current in rows:
            lines.append(f"| {code(name)} | {code(previous)} | {code(current)} |")
        lines.append("")

    return "\n".join(lines) + "\n"


def write_summary(text):
    target = os.getenv("GITHUB_STEP_SUMMARY")
    if target:
        with open(target, "a", encoding="utf-8") as stream:
            stream.write(text)
    else:
        print(text, end="")


def write_output(publish_required):
    target = os.getenv("GITHUB_OUTPUT")
    if not target:
        raise RuntimeError("GITHUB_OUTPUT is not set")
    with open(target, "a", encoding="utf-8") as stream:
        stream.write(f"publish={'true' if publish_required else 'false'}\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--current-manifest", default=".build/dependencies.json")
    parser.add_argument("--previous-manifest", default=".build/published.json")
    parser.add_argument("--current-image", required=True)
    parser.add_argument("--previous-image", required=True)
    args = parser.parse_args()

    try:
        current = load_manifest(args.current_manifest, required=True)
        previous = load_manifest(args.previous_manifest)
        publish_required, details = analyze(
            current,
            previous,
            args.current_image,
            args.previous_image,
        )
        text = summary(publish_required, details)
        write_summary(text)
        write_output(publish_required)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError, RuntimeError) as error:
        write_summary(
            "## Publication decision\n\n"
            "**Publication blocked.** Runtime equality could not be verified.\n\n"
            f"Error: {code(error)}\n"
        )
        print(f"Unable to determine publication state: {error}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
