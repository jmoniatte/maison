import sqlite3
import unittest
from datetime import date

from maison.database import migrate
from maison.money import Account, Balance, Year, add_balance, amount, by_owner, delete_balance, load_accounts, money, parse_amount, same_account, typed, update_balance, percent, return_years, totals


def account(*balances, currency="usd") -> Account:
    """An account with balances given as (date, cash_flow, balance)."""
    return Account(1, "joint", "Vanguard", "Brokerage", "", currency, [Balance(i, date.fromisoformat(day), "", flow, value) for i, (day, flow, value) in enumerate(balances)])


class MoneyTest(unittest.TestCase):
    def test_periods_take_the_gain_out_of_the_cash_flow(self) -> None:
        brokerage = account(("2024-01-01", 1000, 1000), ("2024-06-30", 500, 1650), ("2024-12-31", 0, 1485))
        periods = brokerage.periods
        self.assertEqual([(p.start_balance, p.cash_flow, p.end_balance, p.gain) for p in periods], [(0, 1000, 1000, 0), (1000, 500, 1650, 150), (1650, 0, 1485, -165)])
        self.assertEqual([p.return_rate for p in periods], [0, 0.1, -0.1])
        self.assertEqual(periods[0].start_date, date(2024, 1, 1))
        self.assertEqual(brokerage.balance, 1485)

    def test_the_return_per_year_is_the_lifes_as_a_steady_rate_after_a_year(self) -> None:
        # 21% over two years is 10% a year
        two_years = account(("2022-01-01", 1000, 1000), ("2023-01-01", 0, 1100), ("2024-01-01", 0, 1210))
        self.assertAlmostEqual(two_years.yearly_return, 0.1, places=3)
        self.assertIsNone(account(("2024-01-01", 1000, 1000), ("2024-12-31", 0, 1100)).yearly_return)
        self.assertIsNone(account().yearly_return)

    def test_years_add_up_the_periods_that_end_in_them_and_take_the_dashboards_returns(self) -> None:
        brokerage = account(("2022-01-01", 1000, 1000), ("2022-12-31", 0, 1100), ("2024-06-30", 100, 1300))
        self.assertEqual(
            [(y.year, y.start_balance, y.cash_flow, y.gain, y.end_balance) for y in brokerage.years],
            # 2023 has no balance: it keeps the one before
            [(2024, 1100, 100, 100, 1300), (2023, 1100, 0, 0, 1100), (2022, 0, 1000, 100, 1100)],
        )
        self.assertEqual([y.return_rate for y in brokerage.years], [brokerage.return_rate(year) for year in (2024, 2023, 2022)])
        self.assertEqual(brokerage.life, Year(None, 0, 1100, 200, 1300, brokerage.return_rate()))
        self.assertEqual(account().years, [])

    def test_returns_compound_over_a_year_with_slack_or_the_whole_life(self) -> None:
        brokerage = account(("2023-12-28", 1000, 1000), ("2024-06-30", 0, 1100), ("2025-01-03", 0, 1210), ("2025-06-30", 0, 1331))
        # The periods from Dec 28 to Jan 3 count for 2024
        self.assertAlmostEqual(brokerage.return_rate(2024), 0.21)
        self.assertAlmostEqual(brokerage.return_rate(), 0.331)
        self.assertIsNone(brokerage.return_rate(2020))
        self.assertIsNone(account().return_rate())
        # A period with nothing to earn on, here the first with no cash flow, does not count
        self.assertAlmostEqual(account(("2024-01-01", 0, 0), ("2024-02-01", 100, 110)).return_rate(), 0.1)

    def test_years_totals_and_numbers(self) -> None:
        brokerage = account(("2021-01-01", 10, 10), ("2025-01-01", 0, 20))
        retraite = account(("2026-01-01", 5, 5), currency="eur")
        self.assertEqual(return_years([brokerage, retraite]), [2026, 2025, 2021])
        self.assertEqual(return_years([brokerage, retraite], count=1), [2026])
        self.assertEqual(totals([brokerage, retraite, brokerage]), {"usd": 40, "eur": 5})
        self.assertEqual((amount(1234567.5), amount(-1234.4), amount(-0.4), amount(12.345, 2)), ("1,234,568", "-1,234", "0", "12.35"))
        # The amount then the currency's symbol, or its code when it has none
        self.assertEqual(
            [money(1234.6, "usd"), money(-1234, "USD"), money(500, "eur"), money(12, "chf"), money(12, "")],
            ["1,235 $", "-1,234 $", "500 €", "12 CHF", "12"],
        )
        self.assertEqual((percent(0.1234), percent(-0.0004), percent(None)), ("12.3%", "0.0%", ""))

    def test_by_owner_puts_joint_first_then_the_others_by_name_and_no_owner_last(self) -> None:
        def owned(id, owner):
            return Account(id, owner, "", "", "", "usd")

        accounts = [owned(1, "elliot"), owned(2, "Joint"), owned(3, "claire"), owned(4, "joint"), owned(5, "")]
        self.assertEqual([(owner, [a.id for a in group]) for owner, group in by_owner(accounts)], [("joint", [2, 4]), ("claire", [3]), ("elliot", [1]), ("", [5])])

    def test_an_account_read_again_is_found_by_its_id(self) -> None:
        brokerage, other = account(), Account(2, "", "", "IRA", "", "usd")
        read_again = [Account(2, "", "", "IRA", "", "usd"), account()]
        self.assertIs(same_account(read_again, brokerage), read_again[1])
        self.assertIs(same_account(read_again, other), read_again[0])
        self.assertIsNone(same_account(read_again[:1], brokerage))
        self.assertIsNone(same_account(read_again, None))

    def test_the_full_name_has_the_institution_when_there_is_one(self) -> None:
        self.assertEqual(account().full_name, "Brokerage @ Vanguard")
        self.assertEqual(Account(1, "", "", "IRA", "", "usd").full_name, "IRA")

    def test_amounts_are_filled_in_as_typed_and_read_with_commas_spaces_and_symbols(self) -> None:
        self.assertEqual([typed(1000), typed(393527.53), typed(-12.5), typed(0)], ["1,000", "393,527.53", "-12.50", "0"])
        self.assertEqual([parse_amount(text) for text in ("1,234.5", "-12 $", "€ 3", "0", "", "abc")], [1234.5, -12, 3, 0, None, None])

    def test_a_new_balance_follows_the_last_one_on_or_before_its_day_and_is_recorded(self) -> None:
        brokerage = account(("2024-01-01", 1000, 1000), ("2024-02-01", 0, 1100))
        self.assertEqual([brokerage.balance_on(date(2023, 12, 1)), brokerage.balance_on(date(2024, 2, 1)), brokerage.balance_on(date(2024, 1, 15))], [0, 1100, 1000])
        database = sqlite3.connect(":memory:")
        database.row_factory = sqlite3.Row
        migrate(database)
        database.execute("INSERT INTO accounts (owner, institution, name, currency) VALUES ('joint', 'Vanguard', 'Brokerage', 'usd')")
        new_id = add_balance(database, load_accounts(database)[0], Balance(0, date(2024, 3, 1), "Deposit", 50, 1200))
        self.assertEqual(tuple(database.execute("SELECT id, account_id, date, description, cash_flow, balance FROM balances").fetchone()), (new_id, 1, "2024-03-01", "Deposit", 50, 1200))
        # Changed, then deleted
        update_balance(database, Balance(new_id, date(2024, 3, 2), "Statement", 0, 1250))
        self.assertEqual(load_accounts(database)[0].balances, [Balance(new_id, date(2024, 3, 2), "Statement", 0, 1250)])
        delete_balance(database, Balance(new_id, date(2024, 3, 2), "Statement", 0, 1250))
        self.assertEqual(load_accounts(database)[0].balances, [])
        # Changing a balance, it follows the one before, not itself
        self.assertEqual(brokerage.balance_on(date(2024, 2, 1), leaving_out=brokerage.balances[1]), 1000)

    def test_load_accounts_reads_balances_by_date_then_id(self) -> None:
        database = sqlite3.connect(":memory:")
        database.row_factory = sqlite3.Row
        migrate(database)
        database.executescript("""
            INSERT INTO accounts (owner, institution, name, reference, currency) VALUES ('joint', 'Vanguard', 'Brokerage', NULL, 'usd'), ('claire', 'Vanguard', '529 Claire', '1', 'usd');
            INSERT INTO balances (account_id, date, description, cash_flow, balance) VALUES
                (1, '2024-02-01', 'Statement', 0, 120), (1, '2024-01-01', 'Initial deposit', 100, 100), (1, '2024-02-01', NULL, 10, 130);
        """)
        brokerage, claire = load_accounts(database)
        self.assertEqual(brokerage.reference, "")
        self.assertEqual([(b.date, b.description, b.balance) for b in brokerage.balances], [(date(2024, 1, 1), "Initial deposit", 100), (date(2024, 2, 1), "Statement", 120), (date(2024, 2, 1), "", 130)])
        self.assertEqual((claire.balances, claire.balance), ([], 0))


if __name__ == "__main__":
    unittest.main()
