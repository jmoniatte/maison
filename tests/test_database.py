import sqlite3
import tempfile
import unittest
from pathlib import Path

from maison.database import MIGRATIONS, migrate, open_database, version

# The tables a fin database has, as read from fin.sqlite3 with sqlite_master
FIN_SCHEMA = """
CREATE TABLE "schema_migrations" ("version" varchar NOT NULL PRIMARY KEY);
CREATE TABLE "accounts" ("id" integer PRIMARY KEY AUTOINCREMENT NOT NULL, "owner" varchar, "bank" text, "name" text, "reference" text, "currency" text);
CREATE TABLE "balances" ("id" integer PRIMARY KEY AUTOINCREMENT NOT NULL, "account_id" integer NOT NULL, "date" date NOT NULL, "description" text, "cash_flow" decimal(10,2) NOT NULL, "balance" decimal(10,2) NOT NULL);
INSERT INTO schema_migrations VALUES ('20240101064423'), ('20240106064351');
INSERT INTO accounts (owner, bank, name, reference, currency) VALUES ('Jean', 'Ubiquity', '401k', 'ABC-1', 'USD');
INSERT INTO balances (account_id, date, description, cash_flow, balance) VALUES (1, '2019-10-24', 'Initial deposit', 393527.53, 393527.53);
"""


def schema(connection: sqlite3.Connection) -> dict:
    """Each table's columns (name, type, not null, default, primary key) and whether its id autoincrements."""
    return {
        table: {
            "columns": [tuple(row)[1:] for row in connection.execute(f"PRAGMA table_info({table})")],
            "autoincrement": "AUTOINCREMENT" in connection.execute("SELECT sql FROM sqlite_master WHERE name = ?", (table,)).fetchone()[0],
        }
        for table in ("accounts", "balances")
    }


class DatabaseTest(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_a_new_database_gets_fins_tables_with_institution_for_bank_in_one_file(self) -> None:
        connection = open_database(self.dir / "data" / "maison.sqlite3")
        self.assertEqual(version(connection), len(MIGRATIONS))
        fin = sqlite3.connect(":memory:")
        fin.executescript(FIN_SCHEMA.replace('"bank"', '"institution"').replace("(owner, bank,", "(owner, institution,"))
        self.assertEqual(schema(connection), schema(fin))
        self.assertEqual(connection.execute("PRAGMA journal_mode").fetchone()[0], "delete")
        # Nothing to back up: there was no data
        self.assertEqual(sorted(path.name for path in (self.dir / "data").iterdir()), ["maison.sqlite3"])
        connection.close()
        fin.close()

    def test_a_fin_database_runs_only_the_migrations_after_fins_and_is_backed_up_once(self) -> None:
        path = self.dir / "fin.sqlite3"
        with sqlite3.connect(path) as fin:
            fin.executescript(FIN_SCHEMA)
        fin.close()

        connection = open_database(path)
        self.assertEqual(version(connection), len(MIGRATIONS))
        self.assertEqual(tuple(connection.execute("SELECT description, balance FROM balances").fetchone()), ("Initial deposit", 393527.53))
        # bank is now institution, its values kept
        self.assertEqual(tuple(connection.execute("SELECT institution, name FROM accounts").fetchone()), ("Ubiquity", "401k"))
        # Left alone, like everything else fin made
        self.assertEqual(connection.execute("SELECT count(*) FROM schema_migrations").fetchone()[0], 2)
        backup = self.dir / "fin.backup-v0.sqlite3"
        with sqlite3.connect(backup) as copy:
            self.assertEqual(copy.execute("SELECT count(*), PRAGMA_user_version.user_version FROM balances, PRAGMA_user_version").fetchone(), (1, 0))
        copy.close()
        connection.close()

        # Up to date: opening again changes nothing and backs up nothing
        before = path.read_bytes()
        backup.unlink()
        open_database(path).close()
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse(backup.exists())

    def test_interest_balances_become_statements_and_the_others_keep_their_description(self) -> None:
        connection = sqlite3.connect(":memory:")
        for sql in MIGRATIONS[:3]:
            connection.executescript(sql)
        connection.execute("PRAGMA user_version = 3")
        connection.executescript("""
            INSERT INTO balances (account_id, date, description, cash_flow, balance) VALUES
                (1, '2024-01-01', 'Initial deposit', 100, 100), (1, '2024-02-01', 'Interest', 0, 110), (1, '2024-03-01', NULL, 0, 120);
        """)
        migrate(connection)
        self.assertEqual([row[0] for row in connection.execute("SELECT description FROM balances ORDER BY id")], ["Initial deposit", "Statement", None])
        connection.close()


if __name__ == "__main__":
    unittest.main()
