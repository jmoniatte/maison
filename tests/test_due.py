import sqlite3
import unittest
from datetime import date, timedelta
from unittest.mock import patch

from maison.config import Config, EmailConfig
from maison.database import migrate
from maison.due import run
from maison.todos import Todo, save_todo

TODAY = date(2026, 10, 4)
EMAIL = EmailConfig("me@example.com", "maison@example.com", "maison@example.com", "secret")


class DueTest(unittest.TestCase):
    def setUp(self) -> None:
        self.database = sqlite3.connect(":memory:", isolation_level=None)
        self.database.row_factory = sqlite3.Row
        self.addCleanup(self.database.close)
        migrate(self.database)
        save_todo(self.database, Todo(0, "Change furnace filter", due_on=TODAY - timedelta(days=3), reminders=(7,)))
        save_todo(self.database, Todo(0, "Renew passport", due_on=TODAY + timedelta(days=150), reminders=(180,)))
        save_todo(self.database, Todo(0, "Clean gutters", due_on=TODAY + timedelta(days=300), reminders=(14,)))
        # No date: never listed
        save_todo(self.database, Todo(0, "Paint the office", reminders=(7,)))
        self.config = Config(email=EMAIL)

    def test_prints_the_tasks_due_and_overdue(self) -> None:
        self.assertEqual(
            run(self.database, self.config, False, TODAY).splitlines(),
            ["2026-10-01  Change furnace filter  3 days ago", "2027-03-03  Renew passport         5 months"],
        )

    def test_emails_each_reminder_once_with_the_overdue_tasks_and_retries_a_failed_send(self) -> None:
        with patch("maison.due.send", side_effect=OSError("down")), self.assertRaises(OSError):
            run(self.database, self.config, True, TODAY)
        with patch("maison.due.send") as send:
            run(self.database, self.config, True, TODAY)
            run(self.database, self.config, True, TODAY)
        self.assertEqual(send.call_count, 1)
        message, config = send.call_args.args
        self.assertEqual((message["Subject"], message["To"], config), ("Reminders: 2 todos", "me@example.com", EMAIL))
        self.assertEqual(
            message.get_content(),
            "Coming up:\n  2027-03-03  Renew passport  5 months\n\nOverdue:\n  2026-10-01  Change furnace filter  3 days ago\n",
        )
        # The gutters' reminder fires later, with the filter and the passport overdue by then
        with patch("maison.due.send") as send:
            run(self.database, self.config, True, TODAY + timedelta(days=290))
        self.assertEqual(send.call_args.args[0]["Subject"], "Reminders: 3 todos")


if __name__ == "__main__":
    unittest.main()
