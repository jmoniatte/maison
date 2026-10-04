"""The SQLite database: opening it and bringing its tables up to date; no Textual."""

import sqlite3
from pathlib import Path

# In order, never edited once released: PRAGMA user_version is how many of them a database has run.
MIGRATIONS = (
    # 1: accounts, exactly as fin's Rails migration made it
    """
    CREATE TABLE "accounts" ("id" integer PRIMARY KEY AUTOINCREMENT NOT NULL, "owner" varchar, "bank" text, "name" text, "reference" text, "currency" text);
    """,
    # 2: balances, exactly as fin's Rails migration made it: one row per account and date
    """
    CREATE TABLE "balances" ("id" integer PRIMARY KEY AUTOINCREMENT NOT NULL, "account_id" integer NOT NULL, "date" date NOT NULL, "description" text, "cash_flow" decimal(10,2) NOT NULL, "balance" decimal(10,2) NOT NULL);
    """,
    # 3: the firm that holds an account is rarely a bank (a broker, an insurer, a pension fund)
    """
    ALTER TABLE accounts RENAME COLUMN bank TO institution;
    """,
    # 4: a balance that only says what the account is worth was "Interest", but the change in it is
    # dividends and prices too: it is the statement's balance
    """
    UPDATE balances SET description = 'Statement' WHERE description = 'Interest';
    """,
)
# The last migration a fin database already has
FIN_VERSION = 2


def open_database(path: Path) -> sqlite3.Connection:
    """Open the database at path, creating it if needed, and run the migrations it lacks."""
    existed = path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, isolation_level=None)
    connection.row_factory = sqlite3.Row
    # One file, no -wal beside it, so Dropbox syncs the database whole
    connection.execute("PRAGMA journal_mode = DELETE")
    migrate(connection, path if existed else None)
    return connection


def version(connection: sqlite3.Connection) -> int:
    return connection.execute("PRAGMA user_version").fetchone()[0]


def migrate(connection: sqlite3.Connection, backup_path: Path | None = None) -> None:
    """Run the migrations the database lacks, each in its own transaction.

    A fin database has its tables at user_version 0: it is marked as having run the migrations
    it already has, and none of them runs again. With backup_path, the database is copied next
    to it before the first change.
    """
    current = version(connection)
    if current >= len(MIGRATIONS):
        return
    if backup_path is not None:
        backup(connection, backup_path.with_name(f"{backup_path.stem}.backup-v{current}{backup_path.suffix}"))
    if current == 0 and _has_table(connection, "balances"):
        connection.execute(f"PRAGMA user_version = {FIN_VERSION}")
        current = FIN_VERSION
    for number, sql in enumerate(MIGRATIONS[current:], start=current + 1):
        # executescript commits first, so BEGIN and COMMIT make the migration and its number one transaction
        connection.executescript(f"BEGIN; {sql} PRAGMA user_version = {number}; COMMIT;")


def backup(connection: sqlite3.Connection, path: Path) -> None:
    """Copy the database to path, unless a copy is there already."""
    if path.exists():
        return
    with sqlite3.connect(path) as target:
        connection.backup(target)
    target.close()


def _has_table(connection: sqlite3.Connection, name: str) -> bool:
    found = connection.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,))
    return found.fetchone() is not None
