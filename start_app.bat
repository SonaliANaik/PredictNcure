@echo off
:: Activate conda environment
CALL "C:\Users\Shrut\Anaconda3\Scripts\conda.exe" activate disease_env

:: Install dependencies
pip install -r requirements.txt --quiet

:: Ensure database exists
python create_db.py

:: Start Flask backend (Waitress) — login page
python login_app.py

pause