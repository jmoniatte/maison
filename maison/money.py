"""The accounts and their balances, and the returns worked out from them, as fin did; no Textual."""

import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta

# The owner whose accounts the dashboard lists first
JOINT = "joint"
# Each currency's symbol, shown after the amount; any other currency shows its code there
SYMBOLS = {"usd": "$", "eur": "€", "gbp": "£"}
# How many years the dashboard gives a return for, the latest first
RETURN_YEARS = 5
# The days of an average year, to turn a return over the account's life into one per year
DAYS_PER_YEAR = 365.25
# A year's return takes the periods within it, with this much slack at each end, so a balance
# recorded a few days off the year's first or last day still counts
YEAR_SLACK = timedelta(days=5)


@dataclass(frozen=True)
class Balance:
    """An account's value on a date, after cash_flow went in (or out, when negative)."""

    id: int
    date: date
    description: str
    cash_flow: float
    balance: float


@dataclass(frozen=True)
class Period:
    """From one balance to the next: what the money earned in between, cash flow aside."""

    start_date: date
    end_date: date
    start_balance: float
    cash_flow: float
    end_balance: float

    @property
    def gain(self) -> float:
        """What the money earned (or lost): the change in balance, cash flow aside."""
        return self.end_balance - self.start_balance - self.cash_flow

    @property
    def return_rate(self) -> float | None:
        """The gain over the money there was to earn it; None when there was none."""
        base = self.start_balance + self.cash_flow
        return self.gain / base if base else None


@dataclass(frozen=True)
class Year:
    """What an account did over a year, or over its whole life when year is None: the balances it began
    and ended with, the money put in (or taken out), what the money earned, and its return."""

    year: int | None
    start_balance: float
    cash_flow: float
    gain: float
    end_balance: float
    return_rate: float | None


@dataclass
class Account:
    id: int
    owner: str
    institution: str
    name: str
    reference: str
    currency: str
    # Oldest first
    balances: list[Balance] = field(default_factory=list)

    @property
    def full_name(self) -> str:
        """"Brokerage @ Vanguard", the name alone when there is no institution."""
        return f"{self.name} @ {self.institution}" if self.institution else self.name

    @property
    def balance(self) -> float:
        """The latest balance, 0 before the first."""
        return self.balances[-1].balance if self.balances else 0

    @property
    def periods(self) -> list[Period]:
        """One per balance, the first from nothing on its own date, as fin counted them."""
        periods = []
        start_date, start_balance = None, 0.0
        for balance in self.balances:
            periods.append(Period(start_date or balance.date, balance.date, start_balance, balance.cash_flow, balance.balance))
            start_date, start_balance = balance.date, balance.balance
        return periods

    @property
    def years(self) -> list[Year]:
        """Every year from the first balance's to the last's, the latest first. The amounts come from the
        periods that end in the year; the return is return_rate's, so it matches the dashboard's."""
        years = []
        periods = self.periods
        for year in range(periods[-1].end_date.year, periods[0].end_date.year - 1, -1) if periods else ():
            within = [period for period in periods if period.end_date.year == year]
            # A year with no balance keeps the one before, which is the next year's start
            start = within[0].start_balance if within else years[-1].start_balance
            end = within[-1].end_balance if within else start
            cash_flow = sum(period.cash_flow for period in within)
            years.append(Year(year, start, cash_flow, end - start - cash_flow, end, self.return_rate(year)))
        return years

    @property
    def life(self) -> Year:
        """The account's whole life, from nothing to its latest balance."""
        cash_flow = sum(balance.cash_flow for balance in self.balances)
        return Year(None, 0, cash_flow, self.balance - cash_flow, self.balance, self.return_rate())

    @property
    def yearly_return(self) -> float | None:
        """The return over its life as a steady rate per year, from its first balance to its latest:
        (1 + life) ** (1 / years) - 1. None under a year, where it would mislead, or with no return."""
        life = self.return_rate()
        days = (self.balances[-1].date - self.balances[0].date).days if self.balances else 0
        if life is None or days < DAYS_PER_YEAR or life <= -1:
            return None
        return (1 + life) ** (DAYS_PER_YEAR / days) - 1

    def balance_on(self, day: date, leaving_out: Balance | None = None) -> float:
        """The balance one on day would follow: the last one on or before day, leaving out a balance being
        changed, 0 before the first."""
        before = [balance for balance in self.balances if balance.date <= day and balance != leaving_out]
        return before[-1].balance if before else 0

    def return_rate(self, year: int | None = None) -> float | None:
        """The time-weighted return over year, or over the account's whole life; None with no period in it."""
        periods = self.periods
        if year is not None:
            start, end = date(year, 1, 1) - YEAR_SLACK, date(year, 12, 31) + YEAR_SLACK
            periods = [period for period in periods if period.start_date >= start and period.end_date <= end]
        return twrr(periods)


def twrr(periods: list[Period]) -> float | None:
    """Each period's return compounded; a period with no money to earn on leaves it as it was."""
    if not periods:
        return None
    total = 1.0
    for period in periods:
        if period.return_rate is not None:
            total *= 1 + period.return_rate
    return total - 1


def load_accounts(database: sqlite3.Connection) -> list[Account]:
    """Every account by id, each with its balances oldest first."""
    accounts = {
        row["id"]: Account(row["id"], row["owner"] or "", row["institution"] or "", row["name"] or "", row["reference"] or "", row["currency"] or "")
        for row in database.execute("SELECT * FROM accounts ORDER BY id")
    }
    for row in database.execute("SELECT * FROM balances ORDER BY date, id"):
        account = accounts.get(row["account_id"])
        if account is not None:
            account.balances.append(
                Balance(row["id"], date.fromisoformat(row["date"]), row["description"] or "", row["cash_flow"], row["balance"])
            )
    return list(accounts.values())


def same_account(accounts: list[Account], account: Account | None) -> Account | None:
    """account as read again in accounts, or None when it is gone."""
    return next((found for found in accounts if account and found.id == account.id), None)


def add_balance(database: sqlite3.Connection, account: Account, balance: Balance) -> int:
    """Record balance for account, and give its id; balance.id is not used."""
    cursor = database.execute(
        "INSERT INTO balances (account_id, date, description, cash_flow, balance) VALUES (?, ?, ?, ?, ?)",
        (account.id, balance.date.isoformat(), balance.description, balance.cash_flow, balance.balance),
    )
    return cursor.lastrowid


def update_balance(database: sqlite3.Connection, balance: Balance) -> None:
    """Write balance over the one with its id."""
    database.execute(
        "UPDATE balances SET date = ?, description = ?, cash_flow = ?, balance = ? WHERE id = ?",
        (balance.date.isoformat(), balance.description, balance.cash_flow, balance.balance, balance.id),
    )


def delete_balance(database: sqlite3.Connection, balance: Balance) -> None:
    database.execute("DELETE FROM balances WHERE id = ?", (balance.id,))


def parse_amount(text: str) -> float | None:
    """The amount typed in text, which may have commas, spaces and a currency symbol: "-1,234.5 $" is
    -1234.5. None when it is not a number."""
    cleaned = "".join(char for char in text if char not in ", " and char not in SYMBOLS.values())
    try:
        return float(cleaned)
    except ValueError:
        return None


def by_owner(accounts: list[Account]) -> list[tuple[str, list[Account]]]:
    """The accounts grouped by owner, joint first, then the others by name, then those with no owner;
    each group keeps the accounts' order."""
    groups: dict[str, list[Account]] = {}
    for account in accounts:
        groups.setdefault(account.owner.strip().lower(), []).append(account)
    return sorted(groups.items(), key=lambda group: (group[0] != JOINT, not group[0], group[0]))


def return_years(accounts: list[Account], count: int = RETURN_YEARS) -> list[int]:
    """The latest years with a balance, the latest first."""
    years = {balance.date.year for account in accounts for balance in account.balances}
    return sorted(years, reverse=True)[:count]


def totals(accounts: list[Account]) -> dict[str, float]:
    """The latest balances added up, per currency, in the order the accounts list them."""
    sums: dict[str, float] = {}
    for account in accounts:
        sums[account.currency] = sums.get(account.currency, 0) + account.balance
    return sums


def typed(value: float) -> str:
    """value as one would type it: commas, and the cents only when there are some (393,527.53, 1,000)."""
    return amount(value, 0 if value == round(value) else 2)


def amount(value: float, decimals: int = 0) -> str:
    """value with a comma every three digits: -1,234."""
    # Adding 0.0 turns a -0.0 left by rounding into 0.0, so nothing shows as -0
    value = round(value, decimals) + 0.0
    return f"{value:,.{decimals}f}"


def money(value: float, currency: str) -> str:
    """value then its currency's symbol, or its code when it has none: -1,234 $, 500 €, 12 CHF."""
    return f"{amount(value)} {SYMBOLS.get(currency.lower(), currency.upper())}".rstrip()


def percent(rate: float | None) -> str:
    """rate as a percentage to one decimal, empty for None."""
    return "" if rate is None else f"{amount(rate * 100, 1)}%"
