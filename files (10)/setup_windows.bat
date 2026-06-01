@echo off
REM BlockShield Windows setup — run from project root: scripts\setup_windows.bat

echo Creating virtual environment...
python -m venv .venv

echo Installing dependencies...
.venv\Scripts\pip install --upgrade pip
.venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\pip install -e .

echo.
echo ===================================================
echo  Setup complete!
echo  Activate: .venv\Scripts\activate
echo  Run app:  uvicorn app.main:app --reload
echo  Typecheck: pyrefly check
echo  Tests:    pytest tests/ -v
echo ===================================================
pause
