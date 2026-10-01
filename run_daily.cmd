@echo off
rem Daily: refresh jobs, rebuild the 14-day plan, publish it to the calendar gist.
cd /d "%~dp0"
uv run assistant.py find --days 14 --top 0 > out\last_run.log 2>&1
uv run plan.py --publish >> out\last_run.log 2>&1
