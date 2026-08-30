import sys
import shutil
import subprocess
import logging
from typing import Optional

logger = logging.getLogger("autopoiesis.core.wmux")


class AgentWindowManager:
    """Manages terminal process multiplexing across Windows and Unix platforms.

    Uses `wt.exe split-pane` on Windows (win32), `libtmux` on Unix/macOS,
    and degrades gracefully to standard background logging if tmux/wt are unavailable.
    """

    def __init__(self, session_name: str = "autopoiesis_engine"):
        self.session_name = session_name
        self.use_tmux = False
        self.use_wt = False
        self.tmux_server = None
        self.tmux_session = None

        if sys.platform == "win32":
            if shutil.which("wt.exe") or shutil.which("wt"):
                self.use_wt = True
        else:
            if shutil.which("tmux"):
                try:
                    import libtmux
                    self.tmux_server = libtmux.Server()
                    self.tmux_session = self.tmux_server.find_where({"session_name": session_name})
                    if not self.tmux_session:
                        self.tmux_session = self.tmux_server.new_session(session_name=session_name)
                    self.use_tmux = True
                except Exception as e:
                    logger.warning(f"libtmux initialization failed: {e}. Degrading to background logging.")

    def spawn_worker_pane(self, worker_name: str, command: str) -> bool:
        """Spawns a new worker pane or window executing the command."""
        logger.info(f"Spawning worker '{worker_name}': {command}")

        if self.use_wt:
            try:
                # Spawn split-pane in Windows Terminal
                wt_cmd = ["wt.exe", "split-pane", "-p", "Command Prompt", "cmd.exe", "/k", f"echo Starting Worker: {worker_name} && {command}"]
                subprocess.Popen(wt_cmd)
                return True
            except Exception as e:
                logger.warning(f"Failed to spawn Windows Terminal pane: {e}")

        if self.use_tmux and self.tmux_session:
            try:
                window = self.tmux_session.attached_window
                pane = window.split_window(vertical=False)
                pane.send_keys(f"echo 'Starting Worker: {worker_name}'", enter=True)
                pane.send_keys(command, enter=True)
                return True
            except Exception as e:
                logger.warning(f"Failed to spawn tmux pane: {e}")

        # Graceful degradation fallback: Log command to standard output/background log
        logger.info(f"[Fallback Log Worker: {worker_name}] Executing background command: {command}")
        return True
