
from click.testing import CliRunner
from src.main import cli

def test_version_command():
    """Test the --version command."""
    runner = CliRunner()
    result = runner.invoke(cli, ['--version'])
    assert result.exit_code == 0
    assert 'Bank Statement Processor, version 1.0.0' in result.output
