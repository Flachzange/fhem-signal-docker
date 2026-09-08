#!/usr/bin/env python3
"""Resolve upstream releases and prepare verified build inputs; never run installers."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".build"


def get_json(url):
    headers = {"User-Agent": "fhem-signal-docker-dependency-resolver"}
    if urlparse(url).hostname == "api.github.com" and os.getenv("GH_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
    with urlopen(Request(url, headers=headers), timeout=60) as response:
        return json.load(response)


def one(items, description):
    items = list(items)
    if len(items) != 1:
        raise ValueError(f"Expected exactly one {description}; found {len(items)}")
    return items[0]


def java_major(readme):
    values = re.findall(
        r"^\s*[-*]\s+at least Java Runtime Environment \(JRE\)\s+(\d+)\s*$",
        readme, re.MULTILINE,
    )
    return int(one(values, "Java requirement in release README"))


def libsignal_version(names):
    matches = [
        re.fullmatch(r"(?:\./)?signal-cli-[^/]+/lib/libsignal-client-(\d+\.\d+\.\d+)\.jar", n)
        for n in names
    ]
    return one((m.group(1) for m in matches if m), "libsignal-client JAR")


def download(url, target, expected=None):
    if urlparse(url).scheme != "https":
        raise ValueError("Only HTTPS downloads are allowed")
    subprocess.run([
        "curl", "--fail", "--location", "--silent", "--show-error",
        "--retry", "3", "--connect-timeout", "20", "--max-time", "600",
        "--proto", "=https", "--proto-redir", "=https",
        "--output", str(target), url,
    ], check=True)
    with target.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if expected and digest != expected.removeprefix("sha256:"):
        raise ValueError(f"Checksum mismatch: {target.name}")
    return digest


def asset(release, name, target):
    item = one((a for a in release["assets"] if a["name"] == name), name)
    digest = download(item["browser_download_url"], target, item.get("digest"))
    return {"url": item["browser_download_url"], "sha256": digest}


def base_reference():
    return one(re.findall(
        r"^ARG BASE_IMAGE=(ghcr\.io/fhem/fhem-docker:\d+-threaded-[a-z]+)$",
        (ROOT / "Dockerfile").read_text(), re.MULTILINE,
    ), "base image ARG")


def apt_refresh_period(today=None):
    """Sunday-based UTC week; failed weekly builds stay due on later days."""
    if today is None:
        today = datetime.now(timezone.utc).date()
    sunday = today - timedelta(days=(today.weekday() + 1) % 7)
    return sunday.isoformat()


def prepare():
    OUT.mkdir(exist_ok=True)
    release = get_json("https://api.github.com/repos/AsamK/signal-cli/releases/latest")
    tag = release["tag_name"]
    if release["draft"] or release["prerelease"] or not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        raise ValueError(f"Not a stable signal-cli release: {tag}")
    version = tag[1:]
    source = get_json(
        f"https://api.github.com/repos/AsamK/signal-cli/commits/{tag}"
    )["sha"]
    if not re.fullmatch(r"[0-9a-f]{40}", source):
        raise ValueError("Invalid release commit")
    readme_path = OUT / "signal-cli-README.md"
    download(
        f"https://raw.githubusercontent.com/AsamK/signal-cli/{source}/README.md",
        readme_path,
    )
    major = java_major(readme_path.read_text())
    signal = asset(release, f"signal-cli-{version}.tar.gz", OUT / "signal.tar.gz")
    with tarfile.open(OUT / "signal.tar.gz") as archive:
        libversion = libsignal_version(archive.getnames())
    librelease = get_json(
        "https://api.github.com/repos/exquo/signal-libs-build/releases/tags/"
        f"libsignal_v{libversion}"
    )
    native = asset(
        librelease,
        f"libsignal_jni.so-v{libversion}-x86_64-unknown-linux-gnu.tar.gz",
        OUT / "libsignal.tar.gz",
    )
    params = urlencode({
        "architecture": "x64", "os": "linux", "image_type": "jdk",
        "jvm_impl": "hotspot", "heap_size": "normal", "vendor": "eclipse",
        "page_size": 1, "page": 0, "sort_order": "DESC",
    })
    jdks = get_json(
        f"https://api.adoptium.net/v3/assets/feature_releases/{major}/ga?{params}"
    )
    jdk = one(jdks, "latest stable Temurin release")
    binary = one(jdk["binaries"], "Linux x64 JDK")
    package = binary["package"]
    java = {
        "major": major, "version": jdk["version_data"]["semver"],
        "url": package["link"],
        "sha256": download(package["link"], OUT / "java.tar.gz", package["checksum"]),
    }
    base = base_reference()
    inspect = subprocess.check_output(
        ["docker", "buildx", "imagetools", "inspect", base], text=True
    )
    digest = one(re.findall(r"^Digest:\s+(sha256:[0-9a-f]{64})\s*$", inspect, re.MULTILINE),
                 "base image digest")
    lock = {
        "schema": 1, "platform": "linux/amd64",
        "apt_refresh_period": apt_refresh_period(),
        "base": {"tag": base, "digest": digest, "image": base + "@" + digest},
        "signal": {"version": version, "commit": source, **signal},
        "libsignal": {"version": libversion, **native},
        "java": java,
        "source_revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
    }
    canonical = json.dumps(lock, sort_keys=True, separators=(",", ":"))
    fingerprint = hashlib.sha256(canonical.encode()).hexdigest()
    lock["fingerprint"] = fingerprint
    (OUT / "dependencies.json").write_text(json.dumps(lock, indent=2) + "\n")
    with (OUT / "SHA256SUMS").open("w") as stream:
        for key, name in (("signal", "signal.tar.gz"), ("libsignal", "libsignal.tar.gz"),
                          ("java", "java.tar.gz")):
            stream.write(lock[key]["sha256"] + "  " + name + "\n")
    outputs = {
        "base_image": lock["base"]["image"],
        "apt_refresh_period": lock["apt_refresh_period"],
        "fingerprint": fingerprint,
        "signal_version": version,
    }
    if os.getenv("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as stream:
            for key, value in outputs.items():
                stream.write(f"{key}={value}\n")
    print(json.dumps(lock, indent=2))


if __name__ == "__main__":
    prepare()
