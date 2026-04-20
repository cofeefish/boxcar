@ECHO off
cd ..
cd ..

"C:\Program Files\LibreWolf\librewolf.exe" -private-window http://192.168.0.67:1741/
.venv\Scripts\python.exe boxcar/scripts/main.py

pause