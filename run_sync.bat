@echo off
chcp 65001 > nul
title Cloud Save Sync - Dropbox
python "%~dp0sync.py"
pause
