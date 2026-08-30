def main(inputs: dict) -> dict:
    """Safely executes system command using PlatformAdapter."""
    cmd = inputs.get("command", "")
    from autopoiesis.core.platform import PlatformAdapter
    proc = PlatformAdapter.run_command(cmd)
    return {
        "status": "success" if proc.returncode == 0 else "error",
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr
    }
