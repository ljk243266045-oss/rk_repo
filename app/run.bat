@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
cd /d "%~dp0"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --reload
