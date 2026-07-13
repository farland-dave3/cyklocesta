@echo off
REM ============================================================
REM  eBike Route Map - pridat trasy (Windows)
REM  Double-click this file to run the GPX pipeline.
REM  It always runs from the folder it lives in (repo root).
REM ============================================================

REM -- UTF-8 console so Czech diacritics (r, i, y) display correctly
chcp 65001 >nul

REM -- Run from this script's own directory (the repo root)
cd /d "%~dp0"

setlocal enabledelayedexpansion

REM -- Find a Python interpreter (prefer the "py" launcher, then "python")
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo.
    echo [CHYBA] Python nebyl nalezen. Nainstaluj Python 3 z https://www.python.org/downloads/
    echo         a pri instalaci zaskrtni "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

:menu
cls
echo ============================================================
echo   eBike Route Map - sprava tras
echo ============================================================
echo.
echo   Pracovni postup:
echo     1. Nakopiruj GPX soubory z Bosch Flow do slozky  raw\
echo     2. Prejmenuj je na tvar:  RRRR-MM-DD Nazev.gpx
echo        (volba [1] nize ti ukaze spravne datum kazde jizdy)
echo     3. Zpracuj je volbou [2]
echo     4. Zkontroluj a odesli do gitu (GitHub Desktop)
echo.
echo ------------------------------------------------------------
echo   [1]  Report  - vypis datumy a statistiky souboru v raw\
echo   [2]  Zpracovat trasy  (raw\ -^> gpx\ + routes.json)
echo   [3]  Prebudovat routes.json  (jen z gpx\)
echo   [4]  Nainstalovat privacy hook  (jednorazove po klonovani)
echo   [0]  Konec
echo ------------------------------------------------------------
echo.
set "choice="
set /p "choice=Vyber a stiskni Enter: "

if "%choice%"=="1" goto report
if "%choice%"=="2" goto process
if "%choice%"=="3" goto rebuild
if "%choice%"=="4" goto hooks
if "%choice%"=="0" goto end
echo Neplatna volba.
timeout /t 2 >nul
goto menu

:report
call :check_raw
if errorlevel 1 goto menu
echo.
echo === Report souboru v raw\ ===
echo.
%PY% -m pipeline report
echo.
pause
goto menu

:process
call :check_raw
if errorlevel 1 goto menu
echo.
echo === Zpracovani tras ===
echo.
%PY% -m pipeline process
echo.
if errorlevel 1 (
    echo [!] Zpracovani skoncilo s chybou/varovanim - prectete si vypis vyse.
) else (
    echo [OK] Hotovo. Zkontroluj git status a odesli gpx\ + routes.json.
)
echo.
pause
goto menu

:rebuild
echo.
echo === Prebudovani routes.json ===
echo.
%PY% -m pipeline rebuild-index
echo.
pause
goto menu

:hooks
echo.
echo === Instalace privacy pre-commit hooku ===
echo.
%PY% pipeline\install_hooks.py
echo.
pause
goto menu

:end
endlocal
exit /b 0

REM ------------------------------------------------------------
REM  Overi, ze v raw\ jsou nejake .gpx soubory.
REM  Vraci errorlevel 1 (a vypise hlasku) pokud je adresar
REM  prazdny nebo neexistuje - jinak vraci 0.
REM ------------------------------------------------------------
:check_raw
dir /b "raw\*.gpx" >nul 2>nul
if errorlevel 1 (
    echo.
    echo [!] Adresar raw\ je prazdny - nejsou v nem zadne .gpx soubory.
    echo     Nakopiruj GPX z Bosch Flow do slozky raw\ a zkus to znovu.
    echo.
    pause
    exit /b 1
)
exit /b 0
