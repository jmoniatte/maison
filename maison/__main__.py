import argparse
import sys
from collections.abc import Sequence

from tui_kit.start import start

from . import __version__, due
from .app import DEFAULT_MODE, MODES, MaisonApp


def main(argv: Sequence[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    # Before tui-kit's start, which needs a terminal: it runs from a timer too
    if argv[:1] == ["due"]:
        due.main(argv[1:])
        return
    parser = argparse.ArgumentParser(
        description="Home tools in the terminal: todos and money.",
        epilog="maison due [--email] prints the todos due, or emails their reminders.",
    )
    parser.add_argument("--version", action="version", version=f"maison {__version__}")
    parser.add_argument(
        "mode",
        nargs="?",
        choices=list(MODES),
        default=DEFAULT_MODE,
        help=f"the tab to open on (default: {DEFAULT_MODE})",
    )
    args = parser.parse_args(argv)
    start("maison", lambda: MaisonApp(args.mode))


if __name__ == "__main__":
    main()
