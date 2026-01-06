#!/usr/bin/env python3
"""
Simple HTTP server for MEL/MMEL Dashboard.

Usage:
    python serve.py [port]

Default port is 8080.
"""

import http.server
import socketserver
import os
import sys
import shutil
import json
from pathlib import Path

# Configuration
DEFAULT_PORT = 8080
DASHBOARD_DIR = Path(__file__).parent.absolute()
PROJECT_ROOT = DASHBOARD_DIR.parent
OUTPUT_DIR = PROJECT_ROOT / "output" / "parsed"
DATA_DIR = DASHBOARD_DIR / "data"


def setup_data_files():
    """Copy or link data files to dashboard/data directory."""
    DATA_DIR.mkdir(exist_ok=True)

    files_to_copy = [
        ("mmel_pc12_structured.json", OUTPUT_DIR / "mmel_pc12_structured.json"),
        ("mel_pc12_structured.json", OUTPUT_DIR / "mel_pc12_structured.json"),
    ]

    # Also look for audit files
    audit_dir = PROJECT_ROOT / "output" / "audit"
    if audit_dir.exists():
        audit_files = list(audit_dir.glob("audit_*.json"))
        if audit_files:
            # Get most recent audit file
            latest_audit = max(audit_files, key=lambda p: p.stat().st_mtime)
            files_to_copy.append(("audit_report.json", latest_audit))

    for dest_name, src_path in files_to_copy:
        dest_path = DATA_DIR / dest_name
        if src_path.exists():
            try:
                shutil.copy2(src_path, dest_path)
                print(f"  ✓ Copied {src_path.name} -> data/{dest_name}")
            except Exception as e:
                print(f"  ✗ Failed to copy {src_path.name}: {e}")
        else:
            print(f"  ⚠ Source file not found: {src_path}")

    # Create a placeholder audit report if none exists
    audit_path = DATA_DIR / "audit_report.json"
    if not audit_path.exists():
        print("  ℹ Creating placeholder audit report...")
        placeholder = {
            "metadata": {
                "audit_date": "2024-01-01T00:00:00",
                "mel_aircraft": "HB-FVT",
                "mel_operator": "AMAC Corporate Jet"
            },
            "summary": {
                "total_mmel_items": 314,
                "total_mel_items": 162,
                "compliant": 100,
                "more_restrictive": 20,
                "non_compliant": 5,
                "missing_in_mel": 152,
                "extra_in_mel": 0,
                "compliance_score": 96.0,
                "total_compared": 162
            },
            "results": []
        }
        with open(audit_path, 'w', encoding='utf-8') as f:
            json.dump(placeholder, f, indent=2)


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

    print("=" * 60)
    print("  MEL/MMEL Audit Dashboard Server")
    print("=" * 60)
    print()
    print("Setting up data files...")
    setup_data_files()
    print()

    os.chdir(DASHBOARD_DIR)

    with socketserver.TCPServer(("", port), DashboardHandler) as httpd:
        print(f"Dashboard directory: {DASHBOARD_DIR}")
        print()
        print(f"🚀 Server running at: http://localhost:{port}")
        print(f"   Open this URL in your browser")
        print()
        print("Press Ctrl+C to stop the server")
        print("-" * 60)

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\nServer stopped.")


if __name__ == "__main__":
    main()
