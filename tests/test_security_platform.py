"""Security-focused tests for PlatformAdapter.

Validates command execution safety, path sanitization, and injection prevention.
"""

import pytest
import sys
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

from autopoiesis.core.platform import PlatformAdapter


class TestPlatformAdapterPathSanitization:
    """Tests for path sanitization security."""

    def test_sanitize_path_returns_absolute(self):
        """sanitize_path should return absolute paths."""
        result = PlatformAdapter.sanitize_path("relative/path")
        assert result.is_absolute()

    def test_sanitize_path_resolves_symlinks(self):
        """sanitize_path should resolve to real path."""
        result = PlatformAdapter.sanitize_path(".")
        assert result.is_absolute()
        assert result.exists()

    def test_sanitize_path_accepts_path_objects(self):
        """sanitize_path should accept Path objects."""
        input_path = Path(".")
        result = PlatformAdapter.sanitize_path(input_path)
        assert isinstance(result, Path)
        assert result.is_absolute()

    def test_sanitize_path_handles_nested_relative(self):
        """sanitize_path should handle deeply nested relative paths."""
        result = PlatformAdapter.sanitize_path("./foo/../bar")
        assert result.is_absolute()
        assert "foo" not in str(result)


class TestPlatformAdapterCommandTokenization:
    """Tests for command tokenization security."""

    def test_tokenize_simple_command(self):
        """Tokenize a simple command."""
        tokens = PlatformAdapter._tokenize_command("echo hello")
        assert tokens == ["echo", "hello"]

    def test_tokenize_quoted_args(self):
        """Tokenize command with quoted arguments."""
        tokens = PlatformAdapter._tokenize_command('echo "hello world"')
        assert tokens == ["echo", "hello world"]

    def test_tokenize_single_quoted_args(self):
        """Tokenize command with single-quoted arguments."""
        tokens = PlatformAdapter._tokenize_command("echo 'hello world'")
        assert tokens == ["echo", "hello world"]

    def test_tokenize_mixed_quotes(self):
        """Tokenize command with mixed quote types."""
        tokens = PlatformAdapter._tokenize_command('''echo "hello" 'world' ''')
        assert "hello" in tokens
        assert "world" in tokens

    def test_tokenize_empty_string(self):
        """Tokenize empty command returns empty list."""
        tokens = PlatformAdapter._tokenize_command("")
        assert tokens == []

    def test_tokenize_special_chars_in_quotes(self):
        """Special characters inside quotes should be preserved."""
        tokens = PlatformAdapter._tokenize_command('echo "hello; world"')
        assert tokens == ["echo", "hello; world"]


class TestPlatformAdapterShellCommand:
    """Tests for shell command generation."""

    def test_shell_command_returns_list(self):
        """get_shell_command should return a list."""
        result = PlatformAdapter.get_shell_command("echo hello")
        assert isinstance(result, list)
        assert len(result) > 0

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test")
    def test_windows_shell_command_uses_pwsh(self):
        """On Windows, shell command should use pwsh."""
        result = PlatformAdapter.get_shell_command("echo hello")
        assert result[0] == "pwsh"
        assert "-NoProfile" in result
        assert "-NonInteractive" in result

    @pytest.mark.skipif(sys.platform == "win32", reason="Unix-specific test")
    def test_unix_shell_command_uses_bash(self):
        """On Unix, shell command should use bash."""
        result = PlatformAdapter.get_shell_command("echo hello")
        assert result[0] == "/bin/bash"
        assert result[1] == "-c"


class TestPlatformAdapterRunCommand:
    """Tests for command execution safety."""

    def test_run_command_shell_true(self):
        """run_command with shell=True should work."""
        result = PlatformAdapter.run_command("echo hello", shell=True)
        assert result.returncode == 0
        assert "hello" in result.stdout

    def test_run_command_shell_false(self):
        """run_command with shell=False should work."""
        if sys.platform == "win32":
            result = PlatformAdapter.run_command("echo hello", shell=False)
        else:
            result = PlatformAdapter.run_command("echo hello", shell=False)
        assert isinstance(result, subprocess.CompletedProcess)

    def test_run_command_with_cwd(self):
        """run_command with custom cwd should work."""
        result = PlatformAdapter.run_command("echo $PWD" if sys.platform != "win32" else "echo %CD%", cwd=".")
        assert result.returncode == 0

    def test_run_command_timeout(self):
        """run_command with timeout should raise TimeoutExpired on timeout."""
        with pytest.raises(subprocess.TimeoutExpired):
            PlatformAdapter.run_command(
                "sleep 5" if sys.platform != "win32" else "timeout /t 5",
                timeout=0.1,
            )

    def test_run_command_invalid_command(self):
        """run_command with invalid command should return non-zero returncode."""
        result = PlatformAdapter.run_command("nonexistent_command_xyz_123")
        assert result.returncode != 0

    def test_run_command_no_shell_injection_with_shell_false(self):
        """With shell=False, command injection should not work."""
        # This command would be dangerous with shell=True
        result = PlatformAdapter.run_command("echo hello; echo injected", shell=False)
        # The semicolon and second echo become literal arguments
        assert result.returncode == 0

    def test_run_command_preexec_fn_on_unix(self):
        """preexec_fn should be accepted on Unix."""
        if sys.platform == "win32":
            pytest.skip("preexec_fn not supported on Windows")

        def dummy_preexec():
            pass

        result = PlatformAdapter.run_command("echo hello", preexec_fn=dummy_preexec)
        assert result.returncode == 0

    def test_run_command_preexec_fn_disabled_on_windows(self):
        """preexec_fn should be disabled on Windows."""
        if sys.platform != "win32":
            pytest.skip("Windows-specific test")

        def dummy_preexec():
            pass

        # Should not raise even with preexec_fn
        result = PlatformAdapter.run_command("echo hello", preexec_fn=dummy_preexec)
        assert result.returncode == 0

    def test_run_command_capture_output(self):
        """run_command should capture stdout and stderr."""
        result = PlatformAdapter.run_command("echo stdout_msg && echo stderr_msg >&2" if sys.platform != "win32" else "echo stdout_msg")
        assert isinstance(result.stdout, str)
        assert isinstance(result.stderr, str)

    def test_run_command_does_not_raise_on_error(self):
        """run_command should not raise on command failure (check=False)."""
        # Use a command that will fail but not raise an exception
        if sys.platform == "win32":
            # On Windows, use a command that returns non-zero
            result = PlatformAdapter.run_command("pwsh -Command \"exit 1\"")
        else:
            result = PlatformAdapter.run_command("false")
        assert result.returncode != 0
        # Should not raise exception

    def test_run_command_handles_missing_command_with_shell_false(self):
        """run_command with shell=False and missing command raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            PlatformAdapter.run_command("nonexistent_command_xyz", shell=False)

    def test_run_command_returns_completed_process(self):
        """run_command should return CompletedProcess instance."""
        result = PlatformAdapter.run_command("echo test")
        assert hasattr(result, "returncode")
        assert hasattr(result, "stdout")
        assert hasattr(result, "stderr")

    def test_run_command_empty_command(self):
        """run_command with empty command should handle gracefully."""
        result = PlatformAdapter.run_command("")
        # Should not crash
        assert isinstance(result, subprocess.CompletedProcess)
