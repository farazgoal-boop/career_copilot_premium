@echo off
del /q "temp_timestamp_audit.ps1" 2>nul
del /q "temp_rebuild_and_sync.ps1" 2>nul
del /q "temp_verify_ready.ps1" 2>nul
del /q "temp_verify_ready.cmd" 2>nul
del /q "temp_rebuild_setup.cmd" 2>nul
del /q "temp_run_rebuild.ps1" 2>nul
del /q "temp_run_verify.ps1" 2>nul
echo CLEANUP_DONE
