"""maison due: the todos due, printed or emailed, with no terminal needed; no Textual."""

import argparse
import smtplib
import sqlite3
import sys
from collections.abc import Sequence
from datetime import date
from email.message import EmailMessage

from .config import Config, EmailConfig, load_config
from .database import open_database
from .todos import OVERDUE, Todo, due_todos, fired_reminders, load_todos, mark_emailed, when


def lines(todos: list[Todo], today: date) -> list[str]:
    """A line per todo, its date, its name and how far it is, the names padded so the distances line up."""
    width = max((len(todo.name) for todo in todos), default=0)
    return [f"{todo.due_on.isoformat()}  {todo.name:<{width}}  {when(todo, today)}" for todo in todos]


def email(todos: list[Todo], fired_ids: set[int], today: date, config: EmailConfig) -> EmailMessage:
    """The todos whose reminders fired, then every overdue todo, so none is forgotten."""
    coming = [todo for todo in todos if todo.id in fired_ids and todo.state(today) != OVERDUE]
    overdue = [todo for todo in todos if todo.state(today) == OVERDUE]
    listed = coming + overdue
    message = EmailMessage()
    message["Subject"] = f"Reminder: {listed[0].name}" if len(listed) == 1 else f"Reminders: {len(listed)} todos"
    message["From"] = config.sender
    message["To"] = config.to
    sections = [(title, found) for title, found in (("Coming up", coming), ("Overdue", overdue)) if found]
    message.set_content("\n\n".join(f"{title}:\n" + "\n".join(f"  {line}" for line in lines(found, today)) for title, found in sections) + "\n")
    return message


def send(message: EmailMessage, config: EmailConfig) -> None:
    with smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=30) as smtp:
        smtp.login(config.username, config.password)
        smtp.send_message(message)


def run(database: sqlite3.Connection, config: Config, send_email: bool, today: date) -> str:
    """Print the todos due, or email those whose reminders fired; give what to print."""
    todos = load_todos(database)
    if not send_email:
        return "\n".join(lines(due_todos(todos, today), today))
    fired = fired_reminders(database, today)
    if not fired:
        return ""
    send(email(todos, {todo_id for _, todo_id in fired}, today, config.email), config.email)
    # Only once sent, so a failed send is tried again on the next run
    mark_emailed(database, [reminder_id for reminder_id, _ in fired], today)
    return ""


def main(argv: Sequence[str]) -> None:
    parser = argparse.ArgumentParser(prog="maison due", description="Print the todos due or overdue, or email their reminders.")
    parser.add_argument("--email", action="store_true", help="email the reminders whose day has come, once each")
    args = parser.parse_args(argv)
    config = load_config()
    for warning in config.warnings:
        print(warning, file=sys.stderr)
    if args.email and config.email is None:
        sys.exit("maison due --email needs an email section in ~/.config/maison/config.yaml")
    try:
        database = open_database(config.database_path)
    except (sqlite3.Error, OSError) as error:
        sys.exit(f"Cannot open the database {config.database_path}: {error}")
    try:
        output = run(database, config, args.email, date.today())
    except (smtplib.SMTPException, OSError) as error:
        sys.exit(f"Cannot send the email: {error}")
    finally:
        database.close()
    if output:
        print(output)
