import re
import sys
import subprocess
from pathlib import Path
from typing import Optional


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
    def _tokenize_command(cmd_string: str) -> list[str]:
        """Tokenizes a command string into a list respecting quoted substrings."""
        pattern = r'"([^"]*)"|\'([^\']*)\'|(\S+)'
        tokens = []
        for match in re.finditer(pattern, cmd_string):
            token = next(g for g in match.groups() if g is not None)
            tokens.append(token)
        return tokens

    @staticmethod
    def sanitize_path(path_str: str | Path) -> Path:
        """Sanitizes and resolves path into an absolute Path object."""
        return Path(path_str).resolve()

    @classmethod
    def run_command(
        cls,
        cmd_string: str,
        cwd: str | Path | None = None,
        timeout: float | None = None,
        shell: bool = True,
        preexec_fn: Optional[callable] = None,
    ) -> subprocess.CompletedProcess[str]:
        """Executes shell command safely across operating systems using subprocess.

        Args:
            cmd_string: Command string to execute.
            cwd: Working directory.
            timeout: Execution timeout in seconds.
            shell: If True, wrap in platform shell (pwsh/bash). If False, execute directly as tokenized list.
            preexec_fn: Function to call in child process before exec (Unix only, for resource limits).
        """
        work_dir = cls.sanitize_path(cwd) if cwd else None

        if shell:
            cmd_tokens = cls.get_shell_command(cmd_string)
        else:
            cmd_tokens = cls._tokenize_command(cmd_string)

        # preexec_fn is not supported on Windows
        if sys.platform == "win32":
            preexec_fn = None

        return subprocess.run(
            cmd_tokens,
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            preexec_fn=preexec_fn,
        )
