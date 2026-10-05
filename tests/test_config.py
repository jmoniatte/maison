import tempfile
import unittest
from pathlib import Path

from maison.config import DEFAULT_DATABASE, Config, EmailConfig, load_config


class ConfigTest(unittest.TestCase):
    def setUp(self) -> None:
        self.path = Path(self.enterContext(tempfile.TemporaryDirectory())) / "maison" / "config.yaml"

    def load(self, text: str) -> Config:
        self.path.parent.mkdir(exist_ok=True)
        self.path.write_text(text)
        return load_config(self.path)

    def test_reads_the_theme_and_a_missing_or_broken_file_means_defaults(self) -> None:
        self.assertEqual(load_config(self.path), Config())
        self.assertEqual(self.load("theme: one-light\n"), Config(theme="one-light"))
        unknown = self.load("theme: onelight\n")
        self.assertEqual(len(unknown.warnings), 1)
        self.assertIn("'onelight' is not installed", unknown.warnings[0])
        broken = self.load("theme: [unclosed\n")
        self.assertEqual(broken.theme, Config().theme)
        self.assertIn("not valid YAML", broken.warnings[0])
        self.assertEqual(self.load("- a list\n").warnings, ["Config file must contain a mapping of settings"])

    def test_database_path_defaults_to_dropbox_and_expands_the_home_folder(self) -> None:
        self.assertEqual(Config().database_path, Path.home() / "Dropbox" / "data" / "maison.sqlite3")
        self.assertEqual(self.load("database_path: ' ~/money.sqlite3 '\n").database_path, Path.home() / "money.sqlite3")
        wrong = self.load("database_path: 42\n")
        self.assertEqual(wrong.database_path, DEFAULT_DATABASE)
        self.assertEqual(wrong.warnings, [f"database_path: must be a file path, using {DEFAULT_DATABASE}"])

    def test_email_needs_to_from_and_password_and_defaults_to_fastmail(self) -> None:
        config = self.load("email:\n  to: me@fastmail.com\n  from: me@fastmail.com\n  password: secret\n")
        self.assertEqual(config.email, EmailConfig("me@fastmail.com", "me@fastmail.com", "me@fastmail.com", "secret", "smtp.fastmail.com", 465))
        missing = self.load("email:\n  to: me@fastmail.com\n")
        self.assertIsNone(missing.email)
        self.assertEqual(missing.warnings, ["email: from, password missing, emails are off"])


if __name__ == "__main__":
    unittest.main()
