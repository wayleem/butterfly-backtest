# PowerShell script to configure Windows Firewall for Theta Terminal WSL access
# Run this script as Administrator on Windows

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "Configuring Windows Firewall for Theta Terminal WSL Access" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "[ERROR] This script must be run as Administrator!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Right-click PowerShell and select 'Run as Administrator', then run this script again." -ForegroundColor Yellow
    Write-Host ""
    pause
    exit 1
}

Write-Host "[OK] Running as Administrator" -ForegroundColor Green
Write-Host ""

# Check if Theta Terminal is running
Write-Host "Checking if Theta Terminal is running..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:25503/" -TimeoutSec 2 -UseBasicParsing
    Write-Host "[OK] Theta Terminal is running on port 25503" -ForegroundColor Green
} catch {
    Write-Host "[WARNING] Cannot connect to Theta Terminal on localhost:25503" -ForegroundColor Yellow
    Write-Host "Make sure Theta Terminal is running before testing WSL access" -ForegroundColor Yellow
}
Write-Host ""

# Check if rule already exists
Write-Host "Checking for existing firewall rule..." -ForegroundColor Yellow
$existingRule = Get-NetFirewallRule -DisplayName "Theta Terminal WSL Access" -ErrorAction SilentlyContinue

if ($existingRule) {
    Write-Host "[INFO] Firewall rule already exists. Removing old rule..." -ForegroundColor Yellow
    Remove-NetFirewallRule -DisplayName "Theta Terminal WSL Access"
    Write-Host "[OK] Old rule removed" -ForegroundColor Green
}
Write-Host ""

# Create new firewall rule
Write-Host "Creating firewall rule to allow WSL access to port 25503..." -ForegroundColor Yellow
try {
    New-NetFirewallRule `
        -DisplayName "Theta Terminal WSL Access" `
        -Description "Allow WSL2 to access Theta Terminal REST API on port 25503" `
        -Direction Inbound `
        -LocalPort 25503 `
        -Protocol TCP `
        -Action Allow `
        -Enabled True `
        -Profile Any

    Write-Host "[OK] Firewall rule created successfully!" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Failed to create firewall rule: $_" -ForegroundColor Red
    pause
    exit 1
}
Write-Host ""

# Display the rule
Write-Host "Firewall rule details:" -ForegroundColor Cyan
Get-NetFirewallRule -DisplayName "Theta Terminal WSL Access" | Format-List DisplayName,Description,Direction,Action,Enabled
Write-Host ""

# Test from Windows localhost
Write-Host "Testing connection from Windows..." -ForegroundColor Yellow
try {
    $testUrl = "http://localhost:25503/"
    $response = Invoke-WebRequest -Uri $testUrl -TimeoutSec 5 -UseBasicParsing
    Write-Host "[OK] Connection successful from Windows" -ForegroundColor Green
} catch {
    Write-Host "[WARNING] Could not test connection: $_" -ForegroundColor Yellow
}
Write-Host ""

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "Configuration Complete!" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Go to your WSL terminal" -ForegroundColor White
Write-Host "2. Test the connection with:" -ForegroundColor White
Write-Host "   curl http://10.255.255.254:25503/" -ForegroundColor Cyan
Write-Host "3. You should see the Theta Terminal welcome message" -ForegroundColor White
Write-Host ""
Write-Host "If you still can't connect, try:" -ForegroundColor Yellow
Write-Host "- Restart Theta Terminal" -ForegroundColor White
Write-Host "- Check Windows Defender Firewall is enabled" -ForegroundColor White
Write-Host "- Ensure no other firewall software is blocking the connection" -ForegroundColor White
Write-Host ""
pause
