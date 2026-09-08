# FHEM Docker with Signalbot support

Extends ghcr.io/fhem/fhem-docker:5-threaded-bookworm with signal-cli,
Temurin Java, a compatible libsignal JNI library, and the existing additional
Debian/Perl packages. The automated build targets **linux/amd64** (TrueNAS x86-64).

## Automatic updates

The Docker workflow checks upstream daily at 21:20 UTC and can be started manually.
It resolves:

- The latest stable release from AsamK/signal-cli (no prereleases).
- The Java major required by the README at that release's exact commit.
- The latest stable Linux x64 Temurin JDK patch for that Java major.
- The libsignal version from libsignal-client-<version>.jar in the release archive.
- That exact JNI release from exquo/signal-libs-build.
- The current digest of the explicitly selected FHEM base tag.

There is no dependency on the Signalbot author's installation script and no
installation/download during container startup. A missing JNI release, changed
README format, checksum mismatch, or failing smoke test prevents publication.
Failed combinations are retried on the next scheduled run.

Each build stores dependencies.json as a workflow artifact and in the image at
/opt/signal/dependencies.json. It records versions, source commit, download URLs,
SHA-256 hashes, base digest and repository revision. Upstream asset hashes are
verified where provided; computed hashes alone are not publisher signatures.
The build verifies the downloaded inputs again before installation.

A fingerprint of these inputs avoids scheduled rebuilds after successful
publication. A missing/evicted success cache merely causes an extra build.
Pushes, PRs and manual runs always build. Debian and CPAN packages are resolved
during a build; they are not fully locked by dependencies.json.

### Weekly Debian package refresh

Every Sunday at 21:20 UTC the workflow builds without Docker layer cache.
APT updates its package indexes and upgrades all installed APT-managed packages
within the configured Debian release, including packages inherited from the FHEM
base. The additional packages are then installed. Existing modified configuration
files are preserved. This does not switch Debian releases or upgrade manually
installed Java/signal-cli through APT.

The dependency fingerprint includes a Sunday-based UTC week. This forces a new
build even with unchanged upstream versions/digest. If the Sunday run fails or is
missed, the following daily run still sees an unpublished weekly fingerprint and
retries. The same weekly value invalidates the Docker APT layer, so retries cannot
reuse the previous week's package layer. A successful build is marked only after
publication and signing. APT upgrade errors stop the build.

Manual workflow runs and PR checks also disable Docker layer cache. Every build
that actually executes the APT layer performs the upgrade. Sunday is 22:20 CET or
23:20 CEST; GitHub's scheduled start may be delayed. All installation happens at
image-build time. The existing offline tests gate publication as before.

## Publication and checks

PRs and manual runs on feature branches build and test without publishing.
Successful main builds publish ghcr.io/flachzange/fhem-signal-docker:main and
:latest; scheduled builds additionally refresh :nightly. Release-tag builds
publish their Git tag. Every published build also has a build-<fingerprint>-<run-id>-<attempt> tag.
The existing cosign signing is retained.

The exact locally tested image is pushed, rather than rebuilding it for publication.
Checks run without network access or production volumes:

- Java and signal-cli startup.
- Real libsignal JNI key generation and serialization round trip.
- Loading Protocol::DBus and AI::FANN in Perl.
- The actual pre-start hook and Signal D-Bus introspection with empty temporary data.

These are compatibility smoke tests, not a test of message delivery or of every
FHEM module. Updating the running TrueNAS container remains a separate operation.

## FHEM base updates

The Dockerfile explicitly selects the current image generation, threaded Perl,
and Debian codename. Its digest is refreshed automatically.

A separate job checks the threaded standard-image tags explicitly advertised in
the upstream FHEM Docker README. New generations/Debian lanes become draft PRs;
they are never automatically merged. This deliberately ignores undocumented
registry/experimental tags. A previously declined proposal is not recreated.

Enable **Settings → Actions → General → Allow GitHub Actions to create and
approve pull requests** for automatic proposals. No additional secret or
third-party update bot is required. PRs created using GITHUB_TOKEN usually do
not trigger another workflow: run the Docker workflow manually on the proposal
branch before merging. Unknown future Debian codenames require updating the
ordering in scripts/propose-base-update.py.

The image generation is not the FHEM application version. An existing /opt/fhem
volume continues to use FHEM's own update mechanism.

## Local build

Requires Docker with Buildx, Python 3.11+ and curl. GH_TOKEN is optional and raises
the GitHub API rate limit. From a clean checkout:

    python3 scripts/resolve-dependencies.py
    docker build --no-cache --build-arg BASE_IMAGE="$(python3 -c 'import json; print(json.load(open(".build/dependencies.json"))["base"]["image"])')" -t fhem-signal:test .

The resolver prepares .build (ignored by Git). Plain docker build requires these
prepared inputs. To repeat a historical image exactly, pull its immutable digest;
the dependency manifest does not lock the Debian/CPAN package repositories.

The included docker-compose.yml is a local example with FHEM and Signal data
volumes. Run the resolver before docker compose build. To use the published
image, replace build: . with image: ghcr.io/flachzange/fhem-signal-docker:main
in your own Compose configuration. Dockerfile.x86 is a legacy file and is not
used by the automated workflow; use Dockerfile for amd64.

Configure the FHEM module with:

    define signal Signalbot

## References

- https://github.com/fhem/fhem-docker
- https://github.com/AsamK/signal-cli
- https://github.com/exquo/signal-libs-build
- https://wiki.fhem.de/wiki/Signalbot

Originally based on the integration work of Holoarts and Adimarantis:
https://github.com/bublath/FHEM-Signalbot.
