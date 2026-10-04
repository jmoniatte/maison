import asyncio
import tempfile
from datetime import date
import unittest
from pathlib import Path
from unittest.mock import patch

from textual.widgets import Button, ContentSwitcher, DataTable, Input, Static, TabbedContent
from tui_kit.dialog import ConfirmDialog
from tui_kit.help_screen import HelpScreen
from tui_kit.theme_picker import ThemePicker

from maison.app import MODES, FooterMessage, MaisonApp
from maison.config import Config
from maison.database import MIGRATIONS, version
from maison.screens import TransactionScreen
from maison.widgets import MoneyView
from maison.widgets.dashboard import AccountsTable, Dashboard
from maison.widgets.money_table import SectionTitle


def help_keys(app) -> dict[str, list[str]]:
    """Help's keys by column title: General, then the tab's name in capitals."""
    return {
        str(column.query_one(".section-title").render()).replace("GENERAL", "General"): [
            key.render().plain for key in column.query(".shortcut-key")
        ]
        for column in app.screen.query(".shortcuts-section")
    }


def cells(table: DataTable) -> list[list[str]]:
    """The table's rows as the text of each cell, without the padding."""
    return [[str(cell).strip() for cell in table.get_row_at(row)] for row in range(table.row_count)]


def widths(table: DataTable) -> list[int]:
    return [column.width for column in table.columns.values()]


async def add_accounts(app, pilot, sql: str) -> None:
    """Run sql on the app's database, then show the Money tab's accounts again."""
    app.database.executescript(sql)
    await app.query_one(MoneyView).load()
    await pilot.pause()


class AppTest(unittest.TestCase):
    def run_app(self, body, mode="money", size=(80, 24), **config):
        async def main():
            with (
                tempfile.TemporaryDirectory() as tmp,
                patch("maison.app.CONFIG_FILE", Path(tmp) / "config.yaml"),
            ):
                # Never the user's database
                app = MaisonApp(mode, Config(**{"theme": "onedark", "database_path": Path(tmp) / "maison.sqlite3", **config}))
                async with app.run_test(size=size) as pilot:
                    await pilot.pause()
                    await body(app, pilot)

        asyncio.run(main())

    def test_opens_on_money_with_the_tabs_on_the_first_row(self):
        async def body(app, pilot):
            tabs = app.query_one("#modes", TabbedContent)
            self.assertFalse(app.query("#app-header"))
            self.assertEqual(tabs.region.y, 0)
            self.assertEqual([str(tabs.get_tab(f"{name}-mode").label) for name in MODES], ["Money"])
            self.assertEqual(app.mode, "money")
            # No account yet, so no table to take focus
            self.assertIsNone(app.focused)

        self.run_app(body)

    def test_help_lists_the_keys_and_its_button_opens_it(self):
        async def body(app, pilot):
            await pilot.press("question_mark")
            await pilot.pause()
            self.assertIsInstance(app.screen, HelpScreen)
            self.assertEqual(help_keys(app), {"General": ["?", "t", "y", "tab", "q"], "MONEY": ["enter", "← →", "esc"]})
            await pilot.press("escape")
            await pilot.pause()
            self.assertNotIsInstance(app.screen, HelpScreen)
            await pilot.click("#btn-help")
            await pilot.pause()
            self.assertIsInstance(app.screen, HelpScreen)

        self.run_app(body)

    def test_t_opens_the_theme_picker(self):
        async def body(app, pilot):
            await pilot.press("t")
            await pilot.pause()
            self.assertIsInstance(app.screen, ThemePicker)

        self.run_app(body)

    def test_a_message_takes_helps_place_until_it_clears(self):
        async def body(app, pilot):
            help_button = app.query_one("#btn-help", Button)
            app.notify("Saved", timeout=0.2)
            await pilot.pause()
            self.assertEqual(app.query_one(FooterMessage).render().plain, "Saved")
            self.assertFalse(help_button.display)
            await pilot.pause(0.5)
            self.assertTrue(help_button.display)

        self.run_app(body)

    def test_config_warnings_show_in_the_footer(self):
        async def body(app, pilot):
            self.assertIn("broken", app.query_one(FooterMessage).render().plain)

        self.run_app(body, warnings=["broken"])

    def test_the_database_opens_up_to_date_and_one_that_cannot_says_so(self):
        async def body(app, pilot):
            self.assertEqual(version(app.database), len(MIGRATIONS))

        self.run_app(body)

        async def body(app, pilot):
            self.assertIsNone(app.database)
            self.assertIn("Cannot open the database", app.query_one(FooterMessage).render().plain)

        # A file where its folder should be
        with tempfile.NamedTemporaryFile() as file:
            self.run_app(body, database_path=Path(file.name) / "maison.sqlite3")

    def test_the_dashboard_lists_each_owners_accounts_and_opens_one(self):
        async def body(app, pilot):
            await add_accounts(app, pilot, """
                INSERT INTO accounts (owner, institution, name, reference, currency) VALUES
                    ('elliot', 'Vanguard', 'UTMA Elliot', NULL, 'usd'), ('joint', 'Vanguard', 'Brokerage', '81', 'usd'),
                    ('claire', 'Vanguard', 'UTMA Claire', NULL, 'usd'), ('joint', 'AG2R', 'Retraite', NULL, 'eur');
                INSERT INTO balances (account_id, date, description, cash_flow, balance) VALUES
                    (2, '2024-01-01', 'Initial deposit', 1000, 1000), (2, '2024-12-31', 'Statement', 0, 1100),
                    (4, '2025-06-30', 'Deposit', 500, 500), (3, '2025-06-30', 'Deposit', 20, 20), (1, '2025-06-30', 'Deposit', 30, 30);
            """)
            view = app.query_one(MoneyView)
            pages = app.query_one("#money-pages", ContentSwitcher)
            tables = list(app.query(AccountsTable))
            joint, claire, elliot = tables
            # Joint first, then the others by name, each over their own table
            titles = [str(title.render()) for title in app.query_one(Dashboard).query(SectionTitle)]
            self.assertEqual([title.strip("─ ") for title in titles], ["Joint", "Claire", "Elliot"])
            self.assertTrue(titles[0].startswith("── Joint ──"))
            self.assertEqual((pages.current, app.focused), ("dashboard", joint))
            # Each table's labels, with no dashes under them, as wide as the owner's line; the columns as
            # wide in every table, so they line up
            self.assertEqual([str(column.label).strip() for column in joint.columns.values()], ["Institution", "Account", "Balance", "Yr Avg", "2025", "2024", "Life"])
            self.assertEqual(sum(widths(joint)), len(titles[0]))
            self.assertEqual(widths(elliot), widths(joint))
            self.assertEqual(cells(joint), [
                # Under a year of balances, no return per year
                ["Vanguard", "Brokerage", "1,100 $", "", "", "10.0%", "10.0%"],
                ["AG2R", "Retraite", "500 €", "", "0.0%", "", "0.0%"],
                ["-" * width for width in widths(joint)],
                ["Total", "", "1,100 $", "", "", "", ""],
                ["Total", "", "500 €", "", "", "", ""],
            ])
            # The cursor skips the totals and goes on to the next owner's table, and back
            await pilot.press("down", "down")
            self.assertEqual((app.focused, claire.cursor_row), (claire, 0))
            await pilot.press("down", "down", "down")
            self.assertEqual((app.focused, elliot.cursor_row), (elliot, 0))
            await pilot.press("up", "up")
            self.assertEqual((app.focused, joint.cursor_row), (joint, 1))
            await pilot.press("up", "enter")
            await pilot.pause()
            account_table = app.query_one("#account-table", DataTable)
            self.assertEqual((pages.current, app.focused), ("account", account_table))
            # The header: the details on the left, a dash for a missing value, the balance by them
            self.assertEqual(str(app.query_one("#account-details", Static).render()).split("\n"), [
                "Institution   : Vanguard", "Account Name  : Brokerage", "Account Number: 81", "Account Owner : Joint",
            ])
            self.assertEqual(str(app.query_one("#account-balance", Static).render()).split("\n")[0], "Balance       : 1,100 $")
            # It opens on the Transactions tab: its labels over a line of dashes, then the transactions, the latest first
            tabs = app.query_one("#account-tabs", TabbedContent)
            self.assertEqual("".join(str(column.label).split("\n")[1] for column in account_table.columns.values()), "-" * sum(widths(account_table)))
            self.assertEqual(tabs.active, "transactions")
            self.assertEqual(cells(account_table), [
                ["2024-12-31", "Statement", "0", "100", "1,100", "10.0%"],
                ["2024-01-01", "Initial deposit", "1,000", "0", "1,000", "0.0%"],
            ])
            # → shows the Balances tab: a chart of the balance, the highest value on the top row's tick
            # and the lowest on the bottom one's, then the axis and the years
            await pilot.press("right")
            await pilot.pause()
            chart = app.query_one("#balance-chart")
            self.assertEqual((tabs.active, app.focused), ("balances", chart))
            lines = str(chart.render()).split("\n")
            self.assertEqual((lines[0].split()[0], lines[-3].split()[0], lines[-1].split()), ("1,100", "1,000", ["2024"]))
            self.assertEqual({lines[0].split()[1][0], lines[-3].split()[1][0]}, {"┤"})
            self.assertTrue(lines[-2].strip().startswith("└──"))
            # Read again, as when the tab shows, it stays on the same account
            app.database.execute("UPDATE balances SET balance = 1200 WHERE id = 2")
            await view.load()
            await pilot.pause()
            self.assertEqual((view.account.id, pages.current), (2, "account"))
            self.assertEqual(str(app.query_one("#account-balance", Static).render()).split("\n")[0], "Balance       : 1,200 $")
            # On the tab it was on; → shows the returns: a row per year, then the account's life
            self.assertEqual((tabs.active, app.focused), ("balances", chart))
            await pilot.press("right")
            await pilot.pause()
            returns = app.query_one("#returns-table", DataTable)
            self.assertEqual((tabs.active, app.focused), ("returns", returns))
            self.assertEqual(cells(returns), [
                ["2024", "0", "1,000", "200", "1,200", "20.0%"],
                ["-" * width for width in widths(returns)],
                ["Yr Avg", "", "", "", "", ""],
                ["Life", "", "1,000", "200", "1,200", "20.0%"],
            ])
            self.assertEqual(str(app.query_one("#account-balance", Static).render()).split("\n")[1], "Life Return   : 20.0%")
            # → goes round to the transactions, ← back to the returns
            await pilot.press("right")
            await pilot.pause()
            self.assertEqual((tabs.active, app.focused), ("transactions", account_table))
            await pilot.press("left")
            await pilot.pause()
            self.assertEqual(tabs.active, "returns")
            await pilot.press("right")
            await pilot.pause()
            # Escape goes back to the account left, and only quits from the dashboard
            await pilot.press("escape")
            await pilot.pause()
            joint = app.query(AccountsTable).first()
            self.assertEqual((pages.current, app.focused, joint.cursor_row), ("dashboard", joint, 0))
            self.assertTrue(app.is_running)
            # The breadcrumbs: "Accounts" on the dashboard, "Accounts > UTMA Claire" on an account's page,
            # where a click on "Accounts" goes back
            self.assertEqual(str(app.query_one("#accounts-title").render()), "Accounts")
            claire = list(app.query(AccountsTable))[1]
            await pilot.click(claire, offset=(8, 1))
            await pilot.pause()
            self.assertEqual(view.account.name, "UTMA Claire")
            self.assertEqual([str(app.query_one(f"#breadcrumb-{part}").render()) for part in ("accounts", "separator", "account")], ["Accounts", ">", "UTMA Claire"])
            await pilot.click("#breadcrumb-accounts")
            await pilot.pause()
            self.assertEqual((pages.current, app.focused), ("dashboard", claire))
            self.assertFalse(app.query("#btn-back"))
            # As does Backspace, from any tab
            await pilot.click(claire, offset=(8, 1))
            await pilot.pause()
            await pilot.press("right", "backspace")
            await pilot.pause()
            self.assertEqual((pages.current, app.focused), ("dashboard", claire))
            # Another account opens on its transactions again
            await pilot.press("enter")
            await pilot.pause()
            self.assertEqual(tabs.active, "transactions")
            await pilot.press("escape")
            await pilot.pause()
            # A click on the rule or a total opens nothing
            await pilot.click(claire, offset=(8, 2))
            await pilot.click(claire, offset=(8, 3))
            await pilot.pause()
            self.assertEqual(pages.current, "dashboard")
            await pilot.press("escape")
            await pilot.pause()
            self.assertFalse(app.is_running)

        self.run_app(body)

    def test_new_transaction_records_a_balance_from_a_form(self):
        async def body(app, pilot):
            await add_accounts(app, pilot, """
                INSERT INTO accounts (owner, institution, name, currency) VALUES ('joint', 'Vanguard', 'Brokerage', 'usd');
                INSERT INTO balances (account_id, date, description, cash_flow, balance) VALUES (1, '2024-01-01', 'Initial deposit', 1000, 1000);
            """)
            await pilot.press("enter")
            await pilot.pause()
            # Cancel records nothing
            await pilot.click("#btn-new-transaction")
            await pilot.pause()
            self.assertIsInstance(app.screen, TransactionScreen)
            await pilot.press("escape")
            await pilot.pause()
            self.assertNotIsInstance(app.screen, TransactionScreen)
            await pilot.click("#btn-new-transaction")
            await pilot.pause()
            screen = app.screen
            self.assertEqual(str(screen.query_one("#dialog-title").render()), "Brokerage @ Vanguard")
            # Today, no cash flow, focus on the balance; the gain and return show as it is typed
            self.assertEqual((screen.query_one("#date", Input).value, screen.query_one("#cash-flow", Input).value), (date.today().isoformat(), "0"))
            self.assertEqual(app.focused.id, "balance")
            await pilot.press(*"1,100")
            await pilot.pause()
            self.assertEqual(str(screen.query_one("#transaction-preview").render()), "Gain 100    Return 10.0%")
            # A cash flow needs a description
            screen.query_one("#cash-flow", Input).value = "50"
            await pilot.pause()
            await pilot.click("#save-btn")
            await pilot.pause()
            self.assertEqual(str(screen.query_one("#transaction-error").render()), "Enter a description, such as Deposit")
            screen.query_one("#cash-flow", Input).value = "0"
            screen.query_one("#date", Input).value = "2024-02-30"
            # Enter in a field saves too
            screen.query_one("#balance", Input).focus()
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            self.assertEqual(str(screen.query_one("#transaction-error").render()), "The date must be like 2026-10-03")
            screen.query_one("#date", Input).value = "2024-02-01"
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            # Saved, as Statement, and on show at the top of the transactions
            self.assertNotIsInstance(app.screen, TransactionScreen)
            rows = app.database.execute("SELECT date, description, cash_flow, balance FROM balances ORDER BY id").fetchall()
            self.assertEqual([tuple(row) for row in rows][-1], ("2024-02-01", "Statement", 0, 1100))
            self.assertEqual(cells(app.query_one("#account-table", DataTable))[0], ["2024-02-01", "Statement", "0", "100", "1,100", "10.0%"])
            self.assertEqual(app.query_one(FooterMessage).render().plain, "Transaction added for Brokerage")

            # Enter on a transaction opens it, filled in; the gain is over the balance before it
            table = app.query_one("#account-table", DataTable)
            await pilot.press("enter")
            await pilot.pause()
            screen = app.screen
            self.assertEqual([screen.query_one(f"#{field}", Input).value for field in ("date", "cash-flow", "description", "balance")], ["2024-02-01", "0", "Statement", "1,100"])
            self.assertEqual(str(screen.query_one("#transaction-preview").render()), "Gain 100    Return 10.0%")
            # Saving writes over it, and the cursor stays on it
            screen.query_one("#balance", Input).value = "1,150"
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            self.assertEqual(cells(table)[0], ["2024-02-01", "Statement", "0", "150", "1,150", "15.0%"])
            self.assertEqual(app.database.execute("SELECT count(*) FROM balances").fetchone()[0], 2)
            self.assertEqual(app.query_one(FooterMessage).render().plain, "Transaction saved for Brokerage")
            # Delete asks first; Keep, the default, keeps it
            await pilot.click(table, offset=(5, 3))
            await pilot.pause()
            self.assertEqual(table.cursor_row, 1)
            await pilot.click("#delete-btn")
            await pilot.pause()
            self.assertIsInstance(app.screen, ConfirmDialog)
            await pilot.press("enter")
            await pilot.pause()
            self.assertIsInstance(app.screen, TransactionScreen)
            await pilot.click("#delete-btn")
            await pilot.pause()
            await pilot.click("#confirm-btn")
            await pilot.pause()
            await pilot.pause()
            # The initial deposit is gone: the balance left now starts from nothing
            self.assertEqual(cells(table), [["2024-02-01", "Statement", "0", "1,150", "1,150", ""]])
            self.assertEqual(app.query_one(FooterMessage).render().plain, "Transaction deleted for Brokerage")

        self.run_app(body)

    def test_the_dashboard_scrolls_to_the_cursor(self):
        async def body(app, pilot):
            await add_accounts(app, pilot, """
                INSERT INTO accounts (owner, institution, name, currency) VALUES
                    ('joint', 'B', 'J1', 'usd'), ('joint', 'B', 'J2', 'usd'), ('joint', 'B', 'J3', 'usd'), ('claire', 'B', 'C1', 'usd'), ('claire', 'B', 'C2', 'usd');
            """)
            dashboard = app.query_one("#accounts-scroll")
            # Into Claire's table: her line and labels come into view, then her totals under her last account
            await pilot.press("down", "down", "down")
            await pilot.pause()
            claire = list(app.query(AccountsTable))[1]
            self.assertEqual((app.focused, claire.cursor_row), (claire, 0))
            self.assertGreater(dashboard.scroll_y, 0)
            self.assertTrue(dashboard.region.contains_region(app.query_one(Dashboard).query(SectionTitle)[1].region))
            await pilot.press("down")
            await pilot.pause()
            self.assertTrue(dashboard.region.contains_region(claire.region))

        self.run_app(body, size=(80, 16))

    def test_exit_button_and_q_quit(self):
        for quit in ("button", "q", "escape"):
            async def body(app, pilot, quit=quit):
                if quit == "button":
                    self.assertTrue(app.query_one("#btn-exit").has_class("-red"))
                    await pilot.click("#btn-exit")
                else:
                    await pilot.press(quit)
                await pilot.pause()
                self.assertFalse(app.is_running)

            with self.subTest(quit=quit):
                self.run_app(body)


if __name__ == "__main__":
    unittest.main()
