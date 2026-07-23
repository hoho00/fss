@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0"

set "PYTHON=%~dp0.venv\Scripts\python.exe"

rem ngrok 대시보드에 표시된 본인 고정 Dev Domain으로 변경
set "NGROK_URL=https://여기에-본인주소.ngrok-free.app"

if not exist "%PYTHON%" (
    echo [오류] 가상환경 Python을 찾을 수 없습니다.
    echo %PYTHON%
    pause
    exit /b 1
)

where ngrok.exe >nul 2>&1
if not errorlevel 1 (
    set "NGROK=ngrok.exe"
) else (
    if exist "%~dp0ngrok.exe" (
        set "NGROK=%~dp0ngrok.exe"
    ) else (
        echo [오류] ngrok.exe를 찾을 수 없습니다.
        echo ngrok을 PATH에 등록하거나 프로젝트 폴더에 넣어주세요.
        pause
        exit /b 1
    )
)

echo FSS 서버를 시작합니다...

start "FSS Uvicorn" cmd /k ""%PYTHON%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

timeout /t 2 /nobreak >nul

echo ngrok을 시작합니다...
start "FSS ngrok" cmd /k ""%NGROK%" http 8000 --url "%NGROK_URL%""

echo.
echo FSS와 ngrok 실행을 요청했습니다.
timeout /t 2 /nobreak >nul
exit /b 0
