@echo off
chcp 65001 >nul
title IPN Hébergement

cd /d "%~dp0"

set PORT=8000
set URL=http://localhost:%PORT%

echo.
echo   ╔══════════════════════════════════════════╗
echo   ║  IPN — Offre en hebergement touristique  ║
echo   ║  Itineraire du Perigord Noir · 2025      ║
echo   ╚══════════════════════════════════════════╝
echo.

:: Vérifier Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo   [ERREUR] Python introuvable. Installez-le depuis python.org
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('python --version') do echo   OK  %%v

:: Environnement virtuel
if not exist ".venv\" (
    echo   Creation de l'environnement virtuel...
    python -m venv .venv
)

call .venv\Scripts\activate.bat

:: Dépendances
python -c "import fastapi" >nul 2>&1
if %errorlevel% neq 0 (
    echo   Installation des dependances ^(premiere fois^)...
    pip install -q fastapi "uvicorn[standard]" httpx pandas openpyxl pydantic python-multipart
    echo   OK  Dependances installees
) else (
    echo   OK  Dependances OK
)

:: Vérifier les fichiers Excel
set MISSING=0
if not exist "data\CCSPN_Re_partion_des_lits_par_type_d_heberg__et_communes_2025.xlsx" set MISSING=1
if not exist "data\CCVV_Re_partion_des_lits_par_type_d_heberg__et_communes_2025.xlsx"  set MISSING=1
if not exist "data\CCPF_Re_partion_des_lits_par_type_d_heberg__et_communes_2025.xlsx"  set MISSING=1

if %MISSING%==1 (
    echo.
    echo   [ERREUR] Fichiers Excel manquants dans data\
    echo   Placez les 3 fichiers Excel et relancez.
    pause
    exit /b 1
)

echo   OK  Fichiers Excel presents

:: Ouvrir le navigateur après 2 s
start /b cmd /c "timeout /t 2 >nul && start %URL%"

echo.
echo   SERVEUR DEMARRE sur %URL%
echo   ─────────────────────────────────────────
echo   Ctrl+C pour arreter
echo.

python -m uvicorn app.main:app --host 0.0.0.0 --port %PORT% --reload --log-level warning

echo.
echo   Serveur arrete.
pause
