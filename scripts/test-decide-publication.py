import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "decide_publication", Path(__file__).with_name("decide-publication.py"))
decide = importlib.util.module_from_spec(spec)
spec.loader.exec_module(decide)


def manifest(
    base_digest="sha256:" + "a" * 64,
    signal_version="0.14.8",
    signal_sha="1" * 64,
    libsignal_version="0.102.1",
    libsignal_sha="2" * 64,
    java_version="25.0.4+101.0.LTS",
    java_sha="3" * 64,
    apt="2026-09-06",
    source="4" * 40,
):
    return {
        "base": {
            "tag": "ghcr.io/fhem/fhem-docker:5-threaded-bookworm",
            "digest": base_digest,
        },
        "signal": {"version": signal_version, "sha256": signal_sha},
        "libsignal": {"version": libsignal_version, "sha256": libsignal_sha},
        "java": {"version": java_version, "sha256": java_sha},
        "apt_refresh_period": apt,
        "source_revision": source,
    }


def state(package="1", perl="1", file_hash="abc@755:0:0", workdir="/tmp"):
    return {
        "Debian packages": {"openssl": package},
        "Perl/CPAN modules": {"Protocol::DBus": perl},
        "custom runtime files": {"/docker/pre-start.sh": file_hash},
        "container configuration": {"WorkingDir": workdir},
    }


class DecidePublicationTests(unittest.TestCase):
    @patch.object(decide, "pull_image")
    @patch.object(decide, "image_state")
    def test_apt_period_and_source_revision_alone_do_not_publish(self, image_state, pull_image):
        previous = manifest()
        current = manifest(apt="2026-09-13", source="5" * 40)
        image_state.side_effect = [state(), state()]

        publish, details = decide.analyze(current, previous, "candidate", "published")

        self.assertFalse(publish)
        self.assertEqual(details, {})
        pull_image.assert_called_once_with("published")

    @patch.object(decide, "pull_image")
    @patch.object(decide, "image_state")
    def test_debian_package_change_requires_publish(self, image_state, _pull_image):
        image_state.side_effect = [state(package="1"), state(package="2")]

        publish, details = decide.analyze(manifest(), manifest(), "candidate", "published")

        self.assertTrue(publish)
        self.assertIn("Debian packages", details)

    @patch.object(decide, "pull_image")
    @patch.object(decide, "image_state")
    def test_perl_module_change_requires_publish(self, image_state, _pull_image):
        image_state.side_effect = [state(perl="1"), state(perl="2")]

        publish, details = decide.analyze(manifest(), manifest(), "candidate", "published")

        self.assertTrue(publish)
        self.assertIn("Perl/CPAN modules", details)

    @patch.object(decide, "run_in_image")
    def test_perl_inventory_parses_all_local_packages(self, run_in_image):
        run_in_image.return_value = "Foo::Direct\t1.2\nBar::Transitive\t0.4\n"

        modules = decide.perl_module_versions("candidate")

        self.assertEqual(modules, {"Foo::Direct": "1.2", "Bar::Transitive": "0.4"})
        program = run_in_image.call_args.args[2][-1]
        self.assertIn("File::Find", program)
        self.assertIn("packages_inside", program)
        self.assertIn("/usr/src/app/3rdparty/lib/perl5", program)

    @patch.object(decide, "pull_image")
    @patch.object(decide, "image_state")
    def test_same_version_but_different_artifact_hash_requires_publish(self, image_state, _pull_image):
        previous = manifest(libsignal_sha="2" * 64)
        current = manifest(libsignal_sha="9" * 64)
        image_state.side_effect = [state(), state()]

        publish, details = decide.analyze(current, previous, "candidate", "published")

        self.assertTrue(publish)
        self.assertIn("runtime dependencies", details)

    @patch.object(decide, "pull_image")
    @patch.object(decide, "image_state")
    def test_custom_runtime_file_change_requires_publish(self, image_state, _pull_image):
        image_state.side_effect = [
            state(file_hash="abc@755:0:0"),
            state(file_hash="def@755:0:0"),
        ]

        publish, details = decide.analyze(manifest(), manifest(), "candidate", "published")

        self.assertTrue(publish)
        self.assertIn("custom runtime files", details)

    @patch.object(decide, "pull_image")
    @patch.object(decide, "image_state")
    def test_container_config_change_requires_publish(self, image_state, _pull_image):
        image_state.side_effect = [state(workdir="/tmp"), state(workdir="/opt/fhem")]

        publish, details = decide.analyze(manifest(), manifest(), "candidate", "published")

        self.assertTrue(publish)
        self.assertIn("container configuration", details)

    def test_missing_previous_manifest_establishes_baseline(self):
        publish, details = decide.analyze(manifest(), None, "candidate", "published")
        self.assertTrue(publish)
        self.assertIn("baseline", details)


if __name__ == "__main__":
    unittest.main()
