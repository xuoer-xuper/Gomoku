@echo off
cd /d "%~dp0"
python -m pip install -e ".[dev]"
python -m PyInstaller --noconfirm --clean --windowed --onefile --name Gomoku --paths src --collect-submodules gomoku --exclude-module pygame --exclude-module pygame_ce src\gomoku\__main__.py
if errorlevel 1 (
  echo 打包失败。
  pause
  exit /b 1
)

if not exist "releases" mkdir releases
for /f "delims=" %%v in ('python -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])"') do set VERSION=%%v
copy /Y "dist\Gomoku.exe" "releases\Gomoku-%VERSION%.exe" >nul
echo.
echo 生成结果: dist\Gomoku.exe
echo 发行副本: releases\Gomoku-%VERSION%.exe
echo 把这个 exe 发给朋友即可，无需安装 Python。
pause
