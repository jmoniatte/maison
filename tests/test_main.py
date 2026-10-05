import contextlib
import io
import unittest
from unittest.mock import patch

from maison.__main__ import main


class MainTest(unittest.TestCase):
    def test_version_prints_and_exits(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            main(["--version"])
        self.assertEqual(raised.exception.code, 0)
        self.assertTrue(output.getvalue().startswith("maison "))

    def test_the_mode_comes_from_the_command_line_and_defaults_to_todos(self) -> None:
        with (
            patch("maison.__main__.start", side_effect=lambda name, make_app: make_app()) as start,
            patch("maison.__main__.MaisonApp") as app,
        ):
            main([])
            main(["money"])
        self.assertEqual([call.args for call in app.call_args_list], [("todos",), ("money",)])
        self.assertEqual(start.call_args.args[0], "maison")

        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            main(["garden"])
        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
