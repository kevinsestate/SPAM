@echo off
echo Starting SPAM Backend Server...
cd backend
python -m venv venv 2>nul
call venv\Scripts\activate
pip install -r requirements.txt --quiet
python main.py
pause

