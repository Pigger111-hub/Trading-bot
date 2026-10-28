@echo off
setlocal
cd /d "%~dp0.."
if not exist "%~dp0frontend\dist\index.html" (
  echo Frontend is not built. See dashboard\README.md.
  exit /b 1
)
echo Read-only Batch 001 dashboard: http://127.0.0.1:8765
echo Stop this foreground server with Ctrl+C. No scheduler or trading process is started.
uv run --project "%~dp0backend" --locked --no-sync uvicorn dashboard_api.app:app --host 127.0.0.1 --port 8765 --no-access-log
