"""CLI sanity tests."""
from click.testing import CliRunner
from linkwatch.cli import main

def test_cli_help():
    runner = CliRunner()
    res = runner.invoke(main, ["--help"])
    assert res.exit_code == 0
    assert "TARGET_URL" in res.output
