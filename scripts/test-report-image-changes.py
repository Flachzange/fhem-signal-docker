import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "report_image_changes", Path(__file__).with_name("report-image-changes.py"))
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


def manifest(signal="0.14.7", libsignal="0.99.1", base_digest="sha256:" + "a" * 64,
             java="25.0.4+101.0.LTS", apt="2026-09-06", source="1" * 40):
    return {
        "base": {"tag": "ghcr.io/fhem/fhem-docker:5-threaded-bookworm", "digest": base_digest},
        "signal": {"version": signal},
        "libsignal": {"version": libsignal},
        "java": {"major": 25, "version": java},
        "apt_refresh_period": apt,
        "source_revision": source,
    }


class ReportImageChangesTests(unittest.TestCase):
    def test_dependency_changes_only_returns_changed_components(self):
        previous = manifest()
        current = manifest(signal="0.14.8", libsignal="0.102.1")
        changes = report.dependency_changes(previous, current)
        self.assertEqual([row[0] for row in changes], ["signal-cli", "libsignal"])

    def test_package_changes_detects_changed_added_and_removed(self):
        previous = {"a": "1", "b": "1", "removed": "1"}
        current = {"a": "2", "b": "1", "added": "1"}
        self.assertEqual(report.package_changes(previous, current), [
            ("a", "1", "2"),
            ("added", None, "1"),
            ("removed", "1", None),
        ])

    def test_summary_for_skipped_build_reports_no_package_comparison(self):
        current = manifest()
        summary = report.build_summary(current, current)
        self.assertIn("No dependency changes", summary)
        self.assertIn("no Debian package comparison was needed", summary)

    @patch.object(report, "pull_image", return_value=(True, ""))
    @patch.object(report, "package_versions")
    def test_summary_includes_debian_package_changes(self, package_versions, _pull_image):
        package_versions.side_effect = [
            {"openssl": "1", "curl": "1"},
            {"openssl": "2", "curl": "1", "nano": "1"},
        ]
        summary = report.build_summary(
            manifest(signal="0.14.8"),
            manifest(),
            current_image="candidate:test",
            previous_image="published:automated",
        )
        self.assertIn("signal-cli", summary)
        self.assertIn("Debian package changes (2)", summary)
        self.assertIn("openssl", summary)
        self.assertIn("nano", summary)


if __name__ == "__main__":
    unittest.main()
