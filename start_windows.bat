@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3.12 -m venv .venv
  if errorlevel 1 (
    echo Python 3.12 is required. Install it from python.org with the Python launcher enabled.
    pause
    exit /b 1
  )
)
".venv\Scripts\python.exe" -c "import fastapi, sqlalchemy, alembic, plotly, dotenv, multipart, jinja2, uvicorn, httpx, socksio" >nul 2>&1
if errorlevel 1 (
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 (
    pause
    exit /b 1
  )
)
".venv\Scripts\python.exe" -m app.cli serve
pause
