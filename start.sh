#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -f .venv/bin/python ]]; then
  python3 -c 'import sys; assert sys.version_info >= (3,12), "Python 3.12+ is required"'
  python3 -m venv .venv
fi
if ! .venv/bin/python -c 'import fastapi, sqlalchemy, alembic, plotly, dotenv, multipart, jinja2, uvicorn, httpx, socksio' 2>/dev/null; then
  .venv/bin/python -m pip install -r requirements.txt
fi
exec .venv/bin/python -m app.cli serve "$@"
