"""Check the renewal schedule migration without touching system cron."""
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest


POSTINST = Path(__file__).resolve().parent.parent / "debian/postinst"


class RenewalMigrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.schedule = self.directory / "confconsole-dehydrated"
        self.postinst = self.directory / "postinst"
        self.postinst.write_text(POSTINST.read_text().replace(
            "/etc/cron.daily/confconsole-dehydrated", str(self.schedule),
        ))

    def configure(self, *args):
        subprocess.run(["sh", str(self.postinst), "configure", *args], check=True)

    def test_mode_repair_applies_only_before_2_2_4(self):
        for version, mode, expected in (
            ("2.2.3+13", 0o644, 0o755),
            ("2.2.4", 0o644, 0o644),
            ("2.2.7", 0o644, 0o644),
            ("2.2.7", 0o755, 0o755),
            ("", 0o644, 0o644),
        ):
            with self.subTest(version=version, mode=mode):
                self.schedule.write_text("existing renewal settings\n")
                self.schedule.chmod(mode)
                self.configure(version)
                self.assertEqual(stat.S_IMODE(self.schedule.stat().st_mode), expected)
                self.assertEqual(self.schedule.read_text(), "existing renewal settings\n")

    def test_absent_schedule_stays_absent(self):
        for version in ((), ("2.2.3+13",), ("2.2.7",)):
            with self.subTest(version=version):
                self.configure(*version)
                self.assertFalse(self.schedule.exists())

    def test_legacy_configure_skips_custom_symlink(self):
        target = self.directory / "custom"
        target.touch(mode=0o644)
        self.schedule.symlink_to(target)
        self.configure("2.2.3+13")
        self.assertTrue(self.schedule.is_symlink())
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o644)
