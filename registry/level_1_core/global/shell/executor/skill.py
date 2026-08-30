def main(inputs: dict) -> dict:
    """Executes system shell commands safely using cross-platform PlatformAdapter."""
    cmd = inputs.get("command", inputs.get("payload", ""))
    from autopoiesis.core.platform import PlatformAdapter
    proc = PlatformAdapter.run_command(str(cmd))
    return {
        "status": "success" if proc.returncode == 0 else "error",
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr
    }
