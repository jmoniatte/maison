import sqlite3
from pathlib import Path

import tui_kit
from textual import on
from textual.actions import SkipAction
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.notifications import Notification
from textual.widget import Widget
from textual.widgets import Button, TabbedContent, TabPane, Tabs
from tui_kit.base_app import COPY_BINDING, HELP_BINDING, THEME_BINDING, BaseApp
from tui_kit.header_notification import HeaderNotification
from tui_kit.shortcuts import GENERAL

from . import REPOSITORY_URL, __version__
from .click_only import click_only
from .config import CONFIG_FILE, Config, load_config
from .database import open_database
from .screens import MaisonHelpScreen
from .widgets import MoneyView

STYLES_DIR = Path(__file__).parent / "styles"
# tui-kit's stylesheets first, so the app's own rules win where they differ
STYLE_FILES = (*tui_kit.STYLE_FILES, STYLES_DIR / "maison.tcss")
# Each mode by the name given on the command line, as its tab; the first one is the default
MODES = {
    "money": ("Money", MoneyView),
}
DEFAULT_MODE = next(iter(MODES))


class FooterMessage(HeaderNotification):
    """tui-kit's messages, which find this widget wherever it is: here, in the footer, since maison
    has no title bar. Help hides while one shows, so the message ends where Help ends, on the right.
    """

    def show_notification(self, notification: Notification) -> None:
        self._show_help(False)
        super().show_notification(notification)

    def clear_notification(self) -> None:
        super().clear_notification()
        # Once the message is gone from the screen: Help sits over the end of its line, so both at once
        # would show Help over a message not yet cleared
        self.call_after_refresh(self._show_help, True)

    def _show_help(self, shown: bool) -> None:
        # Unless a new message came in meanwhile
        self.screen.query_one("#btn-help").display = shown and not self.display


def load_stylesheet() -> str:
    return "\n".join(path.read_text() for path in STYLE_FILES)


class MaisonApp(BaseApp):
    """Home tools, one tab each: money."""

    TITLE = "maison"
    VERSION = __version__
    REPOSITORY_URL = REPOSITORY_URL
    # Nothing takes focus on its own, so no box swallows ?, t and q; a view with keys gets it when its tab shows
    AUTO_FOCUS = None
    CSS = load_stylesheet()

    BINDINGS = [
        HELP_BINDING,
        THEME_BINDING,
        COPY_BINDING,
        # Before the screen's own tab, which would move focus; skipped under a panel or dialog
        Binding("tab", "next_mode", "Next tab", group=GENERAL, priority=True),
        Binding("q", "quit", "Quit", group=GENERAL),
        # Panels and dialogs bind escape themselves, so it only quits from the mode
        Binding("escape", "quit", show=False),
    ]

    def __init__(self, mode: str = DEFAULT_MODE, config: Config | None = None) -> None:
        self.mode = mode
        self.config = config if config is not None else load_config()
        # The view of the tab on show, told when it hides
        self.shown_view: Widget | None = None
        # None when it cannot be opened; database_error says why
        self.database: sqlite3.Connection | None = None
        self.database_error = ""
        try:
            self.database = open_database(self.config.database_path)
        except (sqlite3.Error, OSError) as error:
            self.database_error = f"Cannot open the database {self.config.database_path}: {error}"
        super().__init__(self.config.theme, CONFIG_FILE)

    def compose(self) -> ComposeResult:
        # No title bar: the tabs say where you are, and the messages sit by the buttons at the bottom
        # The panes' ids differ from their views' own, which a duplicate id would break
        with TabbedContent(initial=f"{self.mode}-mode", id="modes"):
            for name, (label, view) in MODES.items():
                with TabPane(label, id=f"{name}-mode"):
                    yield view(self.config).add_class("mode")
        # Under every tab: a rule, Exit on the left and Help on the right; a message takes Help's place while it shows
        with Vertical(id="app-footer"):
            with Horizontal(id="app-footer-bar"):
                yield click_only(Button("Exit", id="btn-exit", classes="tinted -red"))
                yield click_only(Button("Help", id="btn-help"))
                yield FooterMessage()

    @on(Button.Pressed, "#btn-help")
    def _help(self, event: Button.Pressed) -> None:
        event.stop()
        self.action_help()

    def action_help(self) -> None:
        self.push_screen(MaisonHelpScreen(MODES[self.mode][0], self.shown_view))

    @on(Button.Pressed, "#btn-exit")
    def _exit(self, event: Button.Pressed) -> None:
        event.stop()
        self.exit()

    def on_mount(self) -> None:
        # The mode keeps focus for its keys; tabs switch by click or with tab
        self.mode_tabs.can_focus = False
        self._show_mode(self.query_one("#modes", TabbedContent).active_pane)
        for warning in self.config.warnings:
            self.notify(warning, severity="warning", timeout=10)
        if self.database_error:
            self.notify(self.database_error, severity="error", timeout=10)

    def on_unmount(self) -> None:
        super().on_unmount()
        if self.database is not None:
            self.database.close()

    @property
    def mode_tabs(self) -> Tabs:
        """The row of maison's own tabs, not those a view may hold."""
        return self.query_one("#modes > ContentTabs", Tabs)

    def apply_theme(self, theme_name: str) -> None:
        super().apply_theme(theme_name)
        # refresh_css only re-applies TCSS: a view that bakes its colors into Rich text repaints itself
        for view in self.query(".mode"):
            if hasattr(view, "set_colors"):
                view.set_colors()

    def action_next_mode(self) -> None:
        if len(self.screen_stack) > 1:
            raise SkipAction()
        self.mode_tabs.action_next_tab()

    @on(TabbedContent.TabActivated, "#modes")
    def _mode_activated(self, event: TabbedContent.TabActivated) -> None:
        self._show_mode(event.pane)

    def _show_mode(self, pane: TabPane) -> None:
        self.mode = pane.id.removesuffix("-mode")
        view = pane.children[0]
        # Once per switch: on mount, TabbedContent then says again that the first tab is active
        if view is self.shown_view:
            return
        # A view with keys of its own takes focus; otherwise nothing has it, so no box swallows ?, t and q
        if view.can_focus:
            view.focus()
        else:
            self.screen.set_focus(None)
        # Told here, not by Show and Hide: Textual's partial relayout does not always send Show to a pane
        # that comes back
        if hasattr(self.shown_view, "tab_hidden"):
            self.shown_view.tab_hidden()
        self.shown_view = view
        if hasattr(view, "tab_shown"):
            view.tab_shown()
