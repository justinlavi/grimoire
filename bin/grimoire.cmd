@echo off
rem grimoire - run a framework rite with whatever Python 3.10+ this machine has.
rem   grimoire <rite> [arguments...]   e.g. grimoire validate --summary
rem   grimoire --list
rem Finds python3, python, or the py launcher and hands off to grimoire.py
rem beside this file, which resolves the framework and runs rites\<rite>.py.
rem Each hand-off is a single-line if, not a parenthesized block: a block expands
rem %errorlevel% before its commands run, so a failing rite would exit 0.
setlocal
set "launcher=%~dp0grimoire.py"

where python3 >nul 2>nul
if not errorlevel 1 python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if not errorlevel 1 python3 "%launcher%" %* & call exit /b %%errorlevel%%

where python >nul 2>nul
if not errorlevel 1 python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if not errorlevel 1 python "%launcher%" %* & call exit /b %%errorlevel%%

where py >nul 2>nul
if not errorlevel 1 py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if not errorlevel 1 py -3 "%launcher%" %* & call exit /b %%errorlevel%%

echo grimoire: Python 3.10 or newer is required but was not found ^(tried python3, python, py -3^) 1>&2
exit /b 127
