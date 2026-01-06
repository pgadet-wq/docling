#!/usr/bin/env python3
"""
Run the MEL/MMEL Audit API server.

Usage:
    python run_api.py [--host HOST] [--port PORT] [--reload]
"""

import argparse
import uvicorn


def main():
    parser = argparse.ArgumentParser(description="Run the MEL/MMEL Audit API")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")

    args = parser.parse_args()

    print(f"""
{'='*60}
  MEL/MMEL Audit API Server
{'='*60}
  Host:     {args.host}
  Port:     {args.port}
  Reload:   {args.reload}

  Swagger:  http://localhost:{args.port}/docs
  ReDoc:    http://localhost:{args.port}/redoc
  Health:   http://localhost:{args.port}/api/v1/health
{'='*60}
""")

    uvicorn.run(
        "mmel_tool.api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info"
    )


if __name__ == "__main__":
    main()
