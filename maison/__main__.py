import argparse
from collections.abc import Sequence

from tui_kit.start import start

from . import __version__
from .app import DEFAULT_MODE, MODES, MaisonApp


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Home tools in the terminal: money.")
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
