def main(inputs: dict) -> dict:
    """Process inspection and PID querying."""
    process_name = inputs.get("process_name", "")
    import sys
    from autopoiesis.core.platform import PlatformAdapter
    if sys.platform == "win32":
        cmd = f"Get-Process -Name '{process_name}'" if process_name else "Get-Process | Select-Object -First 10"
    else:
        cmd = f"ps aux | grep {process_name}" if process_name else "ps aux | head -n 10"
    proc = PlatformAdapter.run_command(cmd)
    return {"status": "success", "output": proc.stdout}
