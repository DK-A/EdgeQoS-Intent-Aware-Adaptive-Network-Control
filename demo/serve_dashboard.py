#!/usr/bin/env python3
"""
demo/serve_dashboard.py - Enterprise EdgeQoS Operations Controller
Serves the professional gateway telemetry console on http://localhost:8080
and exposes REST automation endpoints for all verification stages (S1, S2, S3, S6, All).
"""

import http.server
import socketserver
import os
import json
import subprocess
import threading
import time

PORT = 8080
DIRECTORY = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(DIRECTORY, ".."))

task_lock = threading.Lock()
task_state = {
    "running": False,
    "task": "",
    "logs": [],
    "returncode": None,
    "start_time": 0.0,
    "progress_pct": 0
}

def execute_command_thread(task_name, cmd):
    global task_state
    with task_lock:
        task_state["running"] = True
        task_state["task"] = task_name
        task_state["logs"] = [f"[*] Initiating {task_name}...", f"[*] Command: {cmd}"]
        task_state["returncode"] = None
        task_state["start_time"] = time.time()
        task_state["progress_pct"] = 10

    try:
        p = subprocess.Popen(
            cmd,
            shell=True,
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        for line in iter(p.stdout.readline, ''):
            if line:
                clean_line = line.rstrip()
                with task_lock:
                    task_state["logs"].append(clean_line)
                    if len(task_state["logs"]) > 250:
                        task_state["logs"].pop(0)
                    if "Stage S2" in clean_line:
                        task_state["progress_pct"] = 35
                    elif "Stage S3" in clean_line:
                        task_state["progress_pct"] = 65
                    elif "SUCCESS" in clean_line or "PASSED" in clean_line:
                        task_state["progress_pct"] = 90
        p.wait()
        with task_lock:
            task_state["returncode"] = p.returncode
            task_state["progress_pct"] = 100
            task_state["logs"].append(f"[+] Task {task_name} completed with exit code {p.returncode}")
    except Exception as e:
        with task_lock:
            task_state["logs"].append(f"[-] Execution error: {e}")
            task_state["returncode"] = -1
    finally:
        with task_lock:
            task_state["running"] = False

class EdgeQoSDashboardHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self):
        if self.path == "/api/telemetry":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_cors_headers()
            self.end_headers()
            
            telemetry_path = os.path.join(PROJECT_ROOT, "results", "live_telemetry.json")
            if os.path.exists(telemetry_path):
                try:
                    with open(telemetry_path, "r") as f:
                        data = f.read()
                    self.wfile.write(data.encode("utf-8"))
                    return
                except Exception:
                    pass
            # Default state
            fallback = {
                "active": False,
                "rtt_ms": 20.50,
                "shaper_rate_mbps": 95.0,
                "tin_counters": {"tin_0": 50, "tin_1": 0, "tin_2": 50, "tin_3": 50},
                "guard_status": "READY"
            }
            self.wfile.write(json.dumps(fallback).encode("utf-8"))
            return

        elif self.path == "/api/exec/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_cors_headers()
            self.end_headers()
            with task_lock:
                status_copy = dict(task_state)
            self.wfile.write(json.dumps(status_copy).encode("utf-8"))
            return

        elif self.path == "/" or self.path == "/dashboard":
            self.path = "/edgeqos_dashboard.html"
            return super().do_GET()
        else:
            return super().do_GET()

    def do_POST(self):
        if self.path == "/api/exec":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
            try:
                req = json.loads(body)
            except Exception:
                req = {}

            action = req.get("action", "")
            global task_state
            with task_lock:
                if task_state["running"]:
                    self.send_response(409)
                    self.send_header("Content-Type", "application/json")
                    self.send_cors_headers()
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "A task is already running", "task": task_state["task"]}).encode("utf-8"))
                    return

            cmd = None
            task_name = ""
            if action == "run_all":
                cmd = "bash scripts/run_all_prepi_stages.sh && python3 scripts/run_stage_s3_collapse.py"
                task_name = "Full Verification Suite (Stages S1, S2, S3 & Collapse)"
            elif action == "collapse":
                cmd = "python3 scripts/run_stage_s3_collapse.py"
                task_name = "Scenario SC2: Capacity Collapse & Buffer Drain"
            elif action == "trace":
                cmd = "python3 scripts/run_stage_s2_trace.py"
                task_name = "Stage S2: Kernel Multi-Tin Flow Steering Trace"
            elif action == "verify":
                cmd = "make verify"
                task_name = "Full EdgeQoS Core Verification Suite (Tests + Sim)"
            elif action == "tin_mapping":
                cmd = "python3 scripts/test_tin_mapping.py"
                task_name = "Kernel CAKE diffserv4 Tin Mapping Verification"
            elif action == "privacy":
                cmd = "python3 tests/test_privacy.py"
                task_name = "Test T-PRIV: Protocol-Aware Zero-DPI Inspection"
            elif action == "setup":
                cmd = "bash scripts/setup_netns_topo.sh"
                task_name = "Rebuild 4-Namespace Testbed Topology"
            elif action == "teardown":
                cmd = "bash scripts/teardown_netns_topo.sh"
                task_name = "Teardown Testbed Namespaces"
            else:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid action"}).encode("utf-8"))
                return

            t = threading.Thread(target=execute_command_thread, args=(task_name, cmd), daemon=True)
            t.start()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({"status": "started", "task": task_name}).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

def start_server():
    socketserver.TCPServer.allow_reuse_address = True
    try:
        with socketserver.TCPServer(("", PORT), EdgeQoSDashboardHandler) as httpd:
            print(f"==================================================")
            print(f"[+] EdgeQoS Enterprise Operations Console Live!")
            print(f"[+] Direct Control URL: http://localhost:{PORT}")
            print(f"==================================================")
            httpd.serve_forever()
    except OSError as e:
        print(f"[-] Port {PORT} busy or error: {e}")

if __name__ == "__main__":
    start_server()
