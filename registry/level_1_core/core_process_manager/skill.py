def main(inputs: dict) -> dict:
    """Process management: list, kill, and spawn background processes."""
    import os
    import signal
    import subprocess

    action = inputs.get("action", "list")
    pid = inputs.get("pid")
    command = inputs.get("command")

    if action == "list":
        if os.name == "nt":
            cmd = "tasklist /FO CSV /NH"
        else:
            cmd = "ps -eo pid,comm,%cpu,%mem --no-headers"
        from autopoiesis.core.platform import PlatformAdapter
        proc = PlatformAdapter.run_command(cmd)
        return {"status": "success", "output": proc.stdout}

    if action == "kill" and pid:
        try:
            os.kill(int(pid), signal.SIGTERM)
            return {"status": "success", "killed_pid": int(pid)}
        except ProcessLookupError:
            return {"status": "error", "error": f"Process {pid} not found"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    if action == "spawn" and command:
        try:
            subprocess.Popen(command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return {"status": "success", "spawned": command}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    return {"status": "error", "error": f"Unsupported action: {action}"}
