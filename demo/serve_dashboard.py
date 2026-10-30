#!/usr/bin/env python3
"""
demo/serve_dashboard.py - Local Web Server for EdgeQoS Interactive Dashboard
Serves edgeqos_dashboard.html on http://localhost:8080 and provides /api/telemetry.
"""

import http.server
import socketserver
import os
import json
import subprocess
import threading

PORT = 8080
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

class EdgeQoSDashboardHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_GET(self):
        if self.path == "/api/telemetry":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            
            telemetry_path = os.path.join(DIRECTORY, "..", "results", "live_telemetry.json")
            if os.path.exists(telemetry_path):
                try:
                    with open(telemetry_path, "r") as f:
                        data = f.read()
                    self.wfile.write(data.encode("utf-8"))
                    return
                except Exception:
                    pass
            # Fallback if bridge is not running yet
            fallback = {
                "active": False,
                "rtt_ms": 20.50,
                "shaper_rate_mbps": 95.0,
                "tin_counters": {"tin_0": 50, "tin_1": 0, "tin_2": 50, "tin_3": 50},
                "guard_status": "READY"
            }
            self.wfile.write(json.dumps(fallback).encode("utf-8"))
        elif self.path == "/" or self.path == "/dashboard":
            self.path = "/edgeqos_dashboard.html"
            return super().do_GET()
        else:
            return super().do_GET()

def start_server():
    socketserver.TCPServer.allow_reuse_address = True
    try:
        with socketserver.TCPServer(("", PORT), EdgeQoSDashboardHandler) as httpd:
            print(f"==================================================")
            print(f"[+] EdgeQoS Interactive Dashboard Server Live!")
            print(f"[+] URL: http://localhost:{PORT}")
            print(f"==================================================")
            httpd.serve_forever()
    except OSError as e:
        print(f"[-] Port {PORT} busy or error: {e}")

if __name__ == "__main__":
    start_server()
