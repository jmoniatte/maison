# maison

Home tools in the terminal, one tab each. The first tab, Money, keeps track of investment
accounts (a port of fin). It opens on the dashboard: every account's balance and yearly
returns, and the totals per currency. `Enter` or a click opens an account: its details and return
over its life, then three tabs: Transactions, its balances, the latest first, with the gain
and return of each; Balances, a chart of the balance over time; and Returns, a row per year, then
the whole life. `←` and `→` switch. **New Transaction** opens a form for a
new balance: its date, the cash flow put in or taken out, a description and the balance after it,
with the gain and return it makes shown as you type. `Enter` or a click on a transaction opens it in the same form, to change it or delete it.
`Esc`, or **Accounts** at the top, goes back.

## Install

```bash
./install.sh
```

It installs `maison` as a [uv](https://docs.astral.sh/uv/) tool. It needs SSH access to GitHub,
where its shared UI library, [tui-kit](https://github.com/jmoniatte/tui-kit), lives.

## Use

```bash
maison            # opens on Money
maison money
```

Click a tab or press `Tab` to switch. `?` or the **Help** button at the bottom right shows the
shortcuts, `t` picks a theme, `y` copies the text selected with the mouse, and `q`, `Esc` or the
**Exit** button at the bottom left quits. Messages show at the bottom too, in Help's place until
they clear.

## Configuration

Nothing is required. Press `t` to browse the themes: each one applies as the cursor moves,
`enter` keeps it and `esc` restores the one you started on. The choice is written to
`~/.config/maison/config.yaml`, which you can also edit by hand:

```yaml
theme: one-light
database_path: ~/Dropbox/data/maison.sqlite3   # the default
```

The data is kept in that SQLite file, created on the first start. The default is in Dropbox, so
every computer sees the same data.

The default, `terminal`, reads the colours from the terminal itself. The other themes are
[base16 schemes](https://github.com/tinted-theming/schemes) named by their upstream slug.

## Development

```bash
uv run maison
uv run python -m unittest discover -s tests
uv run ruff check .
```

Releases are git tags without a `v` prefix (`0.1.0`); the version is derived from them by
setuptools-scm.
