@echo off
rem grimoire - run a framework rite with whatever Python 3.10+ this machine has.
rem   grimoire <rite> [arguments...]   e.g. grimoire validate --summary
rem   grimoire --list
rem Finds python3, python, or the py launcher and hands off to grimoire.py
rem beside this file, which resolves the framework and runs rites\<rite>.py.
setlocal
set "launcher=%~dp0grimoire.py"

where python3 >nul 2>nul
if not errorlevel 1 (
    python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
    if not errorlevel 1 (
        python3 "%launcher%" %*
        exit /b %errorlevel%
    )
)
where python >nul 2>nul
if not errorlevel 1 (
    python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
    if not errorlevel 1 (
        python "%launcher%" %*
        exit /b %errorlevel%
    )
)
where py >nul 2>nul
if not errorlevel 1 (
    py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
    if not errorlevel 1 (
        py -3 "%launcher%" %*
        exit /b %errorlevel%
    )
)
echo grimoire: Python 3.10 or newer is required but was not found ^(tried python3, python, py -3^) 1>&2
exit /b 127
