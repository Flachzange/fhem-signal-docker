from datetime import date
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "resolver", Path(__file__).with_name("resolve-dependencies.py"))
resolver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resolver)


class ResolverTests(unittest.TestCase):
    def test_weekly_refresh_changes_on_sunday(self):
        self.assertEqual(resolver.apt_refresh_period(date(2026, 9, 12)), "2026-09-06")
        self.assertEqual(resolver.apt_refresh_period(date(2026, 9, 13)), "2026-09-13")
        self.assertEqual(resolver.apt_refresh_period(date(2026, 9, 14)), "2026-09-13")

    def test_weekly_refresh_survives_year_boundary(self):
        self.assertEqual(resolver.apt_refresh_period(date(2027, 1, 1)), "2026-12-27")

    def test_java_requirement_ignores_other_numbers(self):
        text = "signal-cli 0.14.7\n- at least Java Runtime Environment (JRE) 25\nJava 21 examples"
        self.assertEqual(resolver.java_major(text), 25)

    def test_missing_or_ambiguous_java_fails(self):
        for text in ("Java 25", "- at least Java Runtime Environment (JRE) 25\n" * 2):
            with self.assertRaises(ValueError):
                resolver.java_major(text)

    def test_only_runtime_libsignal_jar_counts(self):
        self.assertEqual(resolver.libsignal_version([
            "signal-cli-0.14.7/lib/libsignal-client-0.96.4.jar",
            "signal-cli-0.14.7/lib/libsignal-client-0.96.4-sources.jar",
            "signal-cli-0.14.7/lib/another-1.0.jar",
        ]), "0.96.4")
        self.assertEqual(resolver.libsignal_version([
            "./signal-cli-0.14.7/lib/libsignal-client-0.96.4.jar",
        ]), "0.96.4")

    def test_missing_or_duplicate_libsignal_fails(self):
        for names in ([], ["signal-cli-0.14.7/lib/libsignal-client-0.96.4.jar"] * 2):
            with self.assertRaises(ValueError):
                resolver.libsignal_version(names)


if __name__ == "__main__":
    unittest.main()
