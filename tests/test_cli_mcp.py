from unittest.mock import patch

from typer.testing import CliRunner

from dimcause.cli import app

runner = CliRunner()


@patch("dimcause.protocols.mcp_server.run")
def test_mcp_serve_stdio_transport_calls_runner(mock_run):
    result = runner.invoke(app, ["mcp", "serve", "--transport", "stdio"])

    assert result.exit_code == 0
    mock_run.assert_called_once_with(transport="stdio")


@patch("dimcause.protocols.mcp_server.run")
def test_mcp_serve_http_transport_calls_runner(mock_run):
    result = runner.invoke(app, ["mcp", "serve", "--transport", "http"])

    assert result.exit_code == 0
    assert "HTTP, 端口 14243" in result.stdout
    mock_run.assert_called_once_with(transport="http")


def test_mcp_serve_rejects_invalid_transport():
    result = runner.invoke(app, ["mcp", "serve", "--transport", "bad"])

    assert result.exit_code == 2
    assert "Invalid value" in result.output
    assert "stdio" in result.output
    assert "http" in result.output
