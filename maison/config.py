from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from tui_kit.config import read_theme
from tui_kit.theme import TERMINAL_THEME

CONFIG_FILE = Path.home() / ".config" / "maison" / "config.yaml"
# In Dropbox, so every computer sees the same data
DEFAULT_DATABASE = Path.home() / "Dropbox" / "data" / "maison.sqlite3"


@dataclass
class Config:
    """Optional settings, written by hand; the app itself writes only the theme."""

    # Set with t in the app; "terminal" reads the terminal's own colours, otherwise any
    # scheme in tui-kit (see tui_kit.theme.list_themes()).
    theme: str = TERMINAL_THEME
    # The SQLite file; created, with its tables, when missing
    database_path: Path = DEFAULT_DATABASE
    # What in the config file was left out, and why; the footer shows these
    warnings: list[str] = field(default_factory=list)


def load_config(path: Path = CONFIG_FILE) -> Config:
    """Read the config file if there is one; a missing file just means defaults."""
    config = Config()
    if not path.exists():
        return config

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as error:
        config.warnings.append(f"Config file is not valid YAML: {error}")
        return config
    if not isinstance(data, Mapping):
        config.warnings.append("Config file must contain a mapping of settings")
        return config

    config.theme, warning = read_theme(data.get("theme"))
    if warning:
        config.warnings.append(warning)
    _read_database_path(data.get("database_path"), config)
    return config


def _read_database_path(value: object, config: Config) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not value.strip():
        config.warnings.append(f"database_path: must be a file path, using {config.database_path}")
        return
    config.database_path = Path(value.strip()).expanduser()
