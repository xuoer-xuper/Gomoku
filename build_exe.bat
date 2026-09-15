@echo off
cd /d "%~dp0"
python -m pip install -e ".[dev]"
python -m PyInstaller --noconfirm --clean --windowed --onefile --name Gomoku --paths src --collect-submodules gomoku --exclude-module pygame --exclude-module pygame_ce src\gomoku\__main__.py
echo.
echo 生成结果: dist\Gomoku.exe
echo 把这个 exe 发给朋友即可，无需安装 Python。
pause
