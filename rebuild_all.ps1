$ErrorActionPreference = "Stop"

Write-Host "Cleaning up release and build directories..."
Remove-Item -Recurse -Force "d:\KieuQuy\Documents\KeoBot\release" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "d:\KieuQuy\Documents\KeoBot\backend\dist" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "d:\KieuQuy\Documents\KeoBot\backend\build" -ErrorAction SilentlyContinue

Write-Host "Rebuilding backend with PyInstaller..."
Set-Location "d:\KieuQuy\Documents\KeoBot\backend"
# PyInstaller output can be noisy, but we need it to succeed
& pyinstaller --clean keobot_backend.spec
if ($LASTEXITCODE -ne 0) { throw "Backend build failed with exit code $LASTEXITCODE" }

Write-Host "Validating and building frontend..."
Set-Location "d:\KieuQuy\Documents\KeoBot\frontend"
& npm run typecheck
if ($LASTEXITCODE -ne 0) { throw "Frontend typecheck failed" }

& npm run build
if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }

Write-Host "Building desktop app with Electron Builder..."
Set-Location "d:\KieuQuy\Documents\KeoBot\desktop"
& npm run build
if ($LASTEXITCODE -ne 0) { throw "Desktop build failed" }

Write-Host "Running smoke test..."
& npm run smoke:packaged
if ($LASTEXITCODE -ne 0) { throw "Smoke test failed" }

Write-Host "All tasks completed successfully!"
