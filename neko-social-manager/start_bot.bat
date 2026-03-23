@echo off
cd /d "C:\Users\d.hoxha\Desktop\blotato\neko-social-manager"
:loop
echo [%time%] Starte NEKO Bot...
python main.py
echo [%time%] Bot gestoppt. Neustart in 5 Sekunden...
timeout /t 5 /nobreak
goto loop
