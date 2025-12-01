@echo off
echo Starting Branch B Remote Server...
call conda activate ulma
set PYTHONPATH=%PYTHONPATH%;%~dp0
python -m ulma_agents.branch_b.server
pause

