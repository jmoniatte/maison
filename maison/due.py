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
from .todos import Todo, due_todos, load_todos, mark_emailed, to_email, when


def lines(todos: list[Todo], today: date) -> list[str]:
    """A line per todo, its date, its name and how far it is, the names padded so the distances line up."""
    width = max((len(todo.name) for todo in todos), default=0)
    return [f"{todo.due_on.isoformat()}  {todo.name:<{width}}  {when(todo, today)}" for todo in todos]


def due_phrase(todo: Todo, today: date) -> str:
    """"due today", "due tomorrow", "due in 6 months", "due 3 days ago"."""
    how_far = when(todo, today)
    if how_far in ("Today", "Tomorrow", "Yesterday"):
        return f"due {how_far.lower()}"
    return f"due {how_far}" if how_far.endswith(" ago") else f"due in {how_far}"


def email(todo: Todo, today: date, config: EmailConfig) -> EmailMessage:
    """One todo's email: how far its due date is in the subject, then its name, due date and note."""
    message = EmailMessage()
    message["Subject"] = f"{todo.name}: {due_phrase(todo, today)}"
    message["From"] = config.sender
    message["To"] = config.to
    body = [todo.name, f"Due {todo.due_on.isoformat()} ({due_phrase(todo, today)})"]
    if todo.note:
        body += ["", todo.note]
    message.set_content("\n".join(body) + "\n")
    return message


def send(message: EmailMessage, config: EmailConfig) -> None:
    with smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=30) as smtp:
        smtp.login(config.username, config.password)
        smtp.send_message(message)


def run(database: sqlite3.Connection, config: Config, send_email: bool, today: date) -> str:
    """Print the todos due, or email each todo with something to say; give what to print."""
    todos = {todo.id: todo for todo in load_todos(database)}
    if not send_email:
        return "\n".join(lines(due_todos(list(todos.values()), today), today))
    for notice in to_email(database, today):
        send(email(todos[notice.todo_id], today, config.email), config.email)
        # Only once sent: a failed send leaves this todo, and those after it, for the next run
        mark_emailed(database, notice, today)
    return ""


def main(argv: Sequence[str]) -> None:
    parser = argparse.ArgumentParser(prog="maison due", description="Print the todos due or overdue, or email them, one email each.")
    parser.add_argument("--email", action="store_true", help="email each todo whose reminder or due date has come, once each")
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
