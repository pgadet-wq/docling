#!/usr/bin/env python3
"""
Simple HTTP server to serve the MEL Audit Dashboard.
Usage: python serve.py [port]
Default port: 8080
"""

import http.server
import socketserver
import os
import sys
import webbrowser
from functools import partial

def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080

    # Change to dashboard directory
    dashboard_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(dashboard_dir)

    handler = partial(http.server.SimpleHTTPRequestHandler, directory=dashboard_dir)

    with socketserver.TCPServer(("", port), handler) as httpd:
        url = f"http://localhost:{port}"
        print(f"\n{'='*60}")
        print(f"  MEL Audit Dashboard Server")
        print(f"{'='*60}")
        print(f"  Serving at: {url}")
        print(f"  Directory:  {dashboard_dir}")
        print(f"{'='*60}")
        print(f"  Press Ctrl+C to stop\n")

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\nServer stopped.")

if __name__ == "__main__":
    main()
