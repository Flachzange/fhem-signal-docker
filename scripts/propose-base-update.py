#!/usr/bin/env python3
"""Propose explicitly documented stable threaded base tags; never merge them."""
import base64
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("resolver", ROOT / "scripts/resolve-dependencies.py")
resolver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resolver)


def gh(*args):
    return subprocess.check_output(["gh", *args], text=True).strip()


def main():
    repo = os.environ["GH_REPO"]
    current = resolver.base_reference()
    metadata = resolver.get_json("https://api.github.com/repos/fhem/fhem-docker")
    readme = resolver.get_json(
        "https://api.github.com/repos/fhem/fhem-docker/contents/README.md?ref="
        + metadata["default_branch"]
    )
    text = base64.b64decode(readme["content"]).decode()
    candidates = set(re.findall(
        r"docker pull (ghcr\.io/fhem/fhem-docker:\d+-threaded-[a-z]+)", text
    ))
    # Compare only stable lanes explicitly advertised by the upstream README.
    debian = {"bullseye": 11, "bookworm": 12, "trixie": 13, "forky": 14, "duke": 15}

    def rank(image):
        match = re.fullmatch(r".+:(\d+)-threaded-([a-z]+)", image)
        if not match or match[2] not in debian:
            raise ValueError(f"Unknown base tag ordering; review required: {image}")
        return int(match[1]), debian[match[2]]

    newer = [image for image in candidates if rank(image) > rank(current)]
    if not newer:
        print("No newer threaded base lane advertised upstream.")
        return
    target = max(newer, key=rank)
    tag = target.rsplit(":", 1)[1]
    branch = "automation/fhem-base-" + tag
    default = gh("api", f"repos/{repo}", "--jq", ".default_branch")
    prs = json.loads(gh("pr", "list", "--repo", repo, "--state", "all",
                       "--head", branch, "--base", default, "--json", "number"))
    if prs:
        print("A proposal for this lane already exists (including declined proposals).")
        return
    subprocess.run(["docker", "manifest", "inspect", target],
                   check=True, stdout=subprocess.DEVNULL)
    sha = gh("api", f"repos/{repo}/git/ref/heads/{default}", "--jq", ".object.sha")
    branches = json.loads(gh("api", f"repos/{repo}/git/matching-refs/heads/{branch}"))
    if not any(item["ref"] == "refs/heads/" + branch for item in branches):
        gh("api", f"repos/{repo}/git/refs", "-f", "ref=refs/heads/" + branch, "-f", "sha=" + sha)
    old = json.loads(gh("api", f"repos/{repo}/contents/Dockerfile?ref={branch}"))
    content = base64.b64decode(old["content"]).decode()
    updated = content.replace("ARG BASE_IMAGE=" + current, "ARG BASE_IMAGE=" + target, 1)
    if updated != content:
        gh("api", "--method", "PUT", f"repos/{repo}/contents/Dockerfile",
           "-f", "branch=" + branch, "-f", "sha=" + old["sha"],
           "-f", "message=Propose FHEM base " + tag,
           "-f", "content=" + base64.b64encode(updated.encode()).decode())
    elif "ARG BASE_IMAGE=" + target not in content:
        raise ValueError("Proposal branch has unexpected base; manual review required")
    body = (
        f"Upstream now documents {target} as a threaded base image.\n\n"
        f"This changes only the selected base lane from {current} to {target}. "
        "Digest updates within the selected lane remain automatic.\n\n"
        "Review the upstream migration notes and run the Docker workflow manually "
        f"on branch {branch} before merging. GitHub does not normally trigger "
        "pull_request workflows for PRs created with GITHUB_TOKEN. The manual "
        "branch run builds and tests without publishing. "
        "An existing FHEM volume is not updated by this change.\n"
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md") as file:
        file.write(body)
        file.flush()
        print(gh("pr", "create", "--repo", repo, "--head", branch, "--base", default,
                 "--draft", "--title", "Update FHEM base to " + tag, "--body-file", file.name))


if __name__ == "__main__":
    main()
