def main(inputs: dict) -> dict:
    """Native shell execution wrapper (pwsh on Windows, /bin/bash on Unix)."""
    cmd = inputs.get("command", "")
    from autopoiesis.core.platform import PlatformAdapter
    proc = PlatformAdapter.run_command(cmd)
    return {
        "status": "success" if proc.returncode == 0 else "error",
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr
    }
