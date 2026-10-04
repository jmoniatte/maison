from textual import on
from textual.actions import SkipAction
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import ContentSwitcher
from tui_kit.shortcuts import GENERAL

from ..config import Config
from ..money import Account, add_balance, delete_balance, load_accounts, same_account, update_balance
from ..screens import Deletion
from .account_page import TRANSACTIONS, AccountPage
from .dashboard import AccountsTable, Dashboard

DASHBOARD = "dashboard"
ACCOUNT = "account"


class MoneyView(Vertical):
    """The investment accounts: the dashboard lists them, and opening one shows its balances."""

    BINDINGS = [
        # Escape quits from the dashboard: back skips there, so the app's own escape runs
        Binding("escape,backspace", "back", "Back to the accounts", key_display="esc", group=GENERAL),
    ]
    # The pages' keys, which Help would not find on the view
    HELP_BINDINGS = (AccountsTable.BINDINGS, AccountPage.BINDINGS, BINDINGS)

    def __init__(self, config: Config) -> None:
        super().__init__(id="money")
        # The account whose page is on show, None on the dashboard
        self.account: Account | None = None

    def compose(self) -> ComposeResult:
        with ContentSwitcher(initial=DASHBOARD, id="money-pages"):
            yield Dashboard(id=DASHBOARD)
            yield AccountPage(id=ACCOUNT)

    def tab_shown(self) -> None:
        self.call_next(self.load)

    def set_colors(self) -> None:
        # The returns' colors are baked into the cells
        self.call_next(self.load)

    async def load(self) -> None:
        """Read the accounts again and draw the page on show anew."""
        database = self.app.database
        if database is None:
            self.query_one("#money-pages").display = False
            return
        accounts = load_accounts(database)
        await self.query_one(Dashboard).show(accounts)
        self.account = same_account(accounts, self.account)
        if self.account is None:
            self._show_dashboard()
        else:
            self._show_account(self.account)

    @on(Dashboard.Opened)
    def _opened(self, event: Dashboard.Opened) -> None:
        self._show_account(event.account, TRANSACTIONS)

    @on(AccountPage.Closed)
    def _closed(self) -> None:
        self.action_back()

    @on(AccountPage.Changed)
    async def _changed(self, event: AccountPage.Changed) -> None:
        database, change = self.app.database, event.change
        if isinstance(change, Deletion):
            delete_balance(database, change.balance)
            message = "Transaction deleted"
        elif change.id:
            update_balance(database, change)
            message = "Transaction saved"
        else:
            add_balance(database, event.account, change)
            message = "Transaction added"
        await self.load()
        self.notify(f"{message} for {event.account.name}")

    def action_back(self) -> None:
        if self.account is None:
            raise SkipAction()
        self._show_dashboard()

    def _show_dashboard(self) -> None:
        self.account = None
        self.query_one(ContentSwitcher).current = DASHBOARD
        self.query_one(Dashboard).focus_current()

    def _show_account(self, account: Account, tab: str | None = None) -> None:
        """Show account's page, on tab, or on the tab it was on."""
        self.account = account
        page = self.query_one(AccountPage)
        page.show(account, tab)
        self.query_one(ContentSwitcher).current = ACCOUNT
        page.focus_tab()
