#!/usr/bin/env python3
"""
Simple HTTP server for MEL/MMEL Dashboard v2.

The dashboard allows users to drag & drop audit JSON files directly.

Usage:
    python serve.py [port]

Default port is 8080.
"""

import http.server
import socketserver
import os
import sys
from pathlib import Path

# Configuration
DEFAULT_PORT = 8080
DASHBOARD_DIR = Path(__file__).parent.absolute()


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    """Custom handler that serves from dashboard directory."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DASHBOARD_DIR), **kwargs)

    def log_message(self, format, *args):
        """Custom log format."""
        print(f"[{self.log_date_time_string()}] {args[0]}")

    def end_headers(self):
        """Add CORS headers."""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT

    print()
    print("=" * 60)
    print("  MoA_MEL - Audit Dashboard v2")
    print("=" * 60)
    print()
    print(f"  Dashboard:  {DASHBOARD_DIR}")
    print()

    # Check for audit files
    project_root = DASHBOARD_DIR.parent
    audit_dir = project_root / "output" / "audit"
    if audit_dir.exists():
        audit_files = list(audit_dir.glob("*.json"))
        if audit_files:
            print("  Fichiers d'audit disponibles:")
            for f in audit_files:
                print(f"    • {f.name}")
            print()
            print(f"  Glissez-déposez un fichier JSON dans le dashboard")
            print(f"  ou sélectionnez-le via le bouton 'Charger'")
    print()

    os.chdir(DASHBOARD_DIR)

    with socketserver.TCPServer(("", port), DashboardHandler) as httpd:
        print(f"🚀 Server: http://localhost:{port}")
        print()
        print("Press Ctrl+C to stop")
        print("-" * 60)

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\nServer stopped.")


if __name__ == "__main__":
    main()
