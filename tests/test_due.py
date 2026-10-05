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
        save_todo(self.database, Todo(0, "Change furnace filter", "16x25", due_on=TODAY - timedelta(days=3), reminders=(7,)))
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

    def test_emails_each_todo_on_its_own_once_for_each_reminder_and_its_due_date(self) -> None:
        # The filter's reminder and due date have come, the passport's reminder: two emails
        with patch("maison.due.send", side_effect=OSError("down")), self.assertRaises(OSError):
            run(self.database, self.config, True, TODAY)
        with patch("maison.due.send") as send:
            run(self.database, self.config, True, TODAY)
            run(self.database, self.config, True, TODAY)
        self.assertEqual(send.call_count, 2)
        (filter_email, config), (passport_email, _) = (call.args for call in send.call_args_list)
        self.assertEqual((filter_email["Subject"], filter_email["To"], config), ("Change furnace filter: due 3 days ago", "me@example.com", EMAIL))
        self.assertEqual(filter_email.get_content(), "Change furnace filter\nDue 2026-10-01 (due 3 days ago)\n\n16x25\n")
        self.assertEqual(passport_email["Subject"], "Renew passport: due in 5 months")
        # A failed send leaves the todo, and those after it, for the next run
        with patch("maison.due.send", side_effect=[None, OSError("down")]) as send, self.assertRaises(OSError):
            run(self.database, self.config, True, TODAY + timedelta(days=290))
        with patch("maison.due.send") as send:
            run(self.database, self.config, True, TODAY + timedelta(days=290))
        self.assertEqual([call.args[0]["Subject"] for call in send.call_args_list], ["Clean gutters: due in 10 days"])

    def test_every_run_sends_the_days_emails_even_if_sent(self) -> None:
        save_todo(self.database, Todo(0, "Call the plumber", due_on=TODAY))
        with patch("maison.due.send") as send:
            run(self.database, self.config, True, TODAY)
            run(self.database, self.config, True, TODAY)
        subjects = [call.args[0]["Subject"] for call in send.call_args_list]
        # The plumber is due today: on both runs; the filter's and the passport's days have passed: once
        self.assertEqual(subjects.count("Call the plumber: due today"), 2)
        self.assertEqual(len(subjects), 4)


if __name__ == "__main__":
    unittest.main()
