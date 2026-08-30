import sys
import subprocess
from pathlib import Path


class PlatformAdapter:
    """Provides platform-agnostic shell execution and path sanitization.

    Enforces cross-platform compatibility across macOS, Linux, and Windows.
    """

    @staticmethod
    def get_shell_command(cmd_string: str) -> list[str]:
        """Returns platform-specific shell execution command tokens."""
        if sys.platform == "win32":
            return ["pwsh", "-NoProfile", "-NonInteractive", "-Command", f"& {cmd_string}"]
        return ["/bin/bash", "-c", cmd_string]

    @staticmethod
    def sanitize_path(path_str: str | Path) -> Path:
        """Sanitizes and resolves path into an absolute Path object."""
        return Path(path_str).resolve()

    @classmethod
    def run_command(cls, cmd_string: str, cwd: str | Path | None = None, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
        """Executes shell command safely across operating systems using subprocess."""
        cmd_tokens = cls.get_shell_command(cmd_string)
        work_dir = cls.sanitize_path(cwd) if cwd else None
        return subprocess.run(
            cmd_tokens,
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
