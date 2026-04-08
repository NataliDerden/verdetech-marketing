@echo off
echo Запуск VerdeTech Marketing...
echo.

pip install -r requirements.txt --quiet

echo Приложение запущено: http://localhost:5000
echo Нажмите Ctrl+C чтобы остановить.
echo.

python app.py
pause
