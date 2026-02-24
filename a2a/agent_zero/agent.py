import requests
import json
import sys
import subprocess
import time
from datetime import datetime

# --- CONFIGURATION (KITT SOVEREIGN DEFAULTS) ---
OLLAMA_URL = "http://localhost:11434/api/generate"
MCP_URL = "http://localhost:8000"
MODEL = "llama3.2:latest"
AGENT_ID = "agent_zero"
HEARTBEAT_INTERVAL = 60  # Seconds

class AgentZero:
    def __init__(self):
        pass

    def get_real_telemetry(self):
        """The Eyes: Grabs actual server load and memory."""
        try:
            uptime = subprocess.check_output("uptime", shell=True).decode().strip()
            docker_count = subprocess.check_output("docker ps -q | wc -l", shell=True).decode().strip()
            return f"Server Load: {uptime} | Active Containers: {docker_count}"
        except:
            return "Telemetry Error: Blind."

    def log_to_journal(self, message):
        """Writes to systemd journal (via stdout)."""
        # We flush stdout to ensure it hits the logs immediately
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        sys.stdout.flush()

    def run_daemon(self):
        """The Infinite Loop: Monitor -&gt; Log -&gt; Sleep"""
        self.log_to_journal("--- AGENT ZERO DAEMON STARTED ---")
        
        while True:
            try:
                # 1. Gather Data
                telemetry = self.get_real_telemetry()
                
                # 2. Heartbeat Log
                self.log_to_journal(f"HEARTBEAT: {telemetry}")
                
                # 3. Wait (This prevents the crash loop)
                time.sleep(HEARTBEAT_INTERVAL)
                
            except KeyboardInterrupt:
                self.log_to_journal("Stopping via Signal.")
                break
            except Exception as e:
                self.log_to_journal(f"CRITICAL ERROR: {e}")
                time.sleep(5)

if __name__ == "__main__":
    agent = AgentZero()
    agent.run_daemon()
