@echo off
echo Starting SPAM Frontend...
cd frontend
if not exist node_modules (
    echo Installing dependencies...
    call npm install
)
call npm run dev
pause

