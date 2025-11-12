# WSL Setup Steps - Connect to Windows Theta Terminal

Follow these steps in order to configure WSL to access your Windows-hosted Theta Terminal.

## Step 1: Configure Windows Firewall

Windows Firewall is currently blocking WSL from accessing Theta Terminal on port 25503.

### Instructions:

1. **Copy the PowerShell script to Windows**

   The script is located at:
   ```
   \\wsl$\Ubuntu\home\wayleem\code\startup\butterfly\configure_windows_firewall.ps1
   ```

   Copy it to your Windows desktop or downloads folder.

2. **Run PowerShell as Administrator**

   - Press `Windows + X`
   - Select "Windows PowerShell (Admin)" or "Terminal (Admin)"
   - Click "Yes" on the UAC prompt

3. **Navigate to the script location**
   ```powershell
   cd C:\Users\wayle\Downloads  # Or wherever you saved it
   ```

4. **Run the script**
   ```powershell
   .\configure_windows_firewall.ps1
   ```

   The script will:
   - ✅ Check if you're running as Administrator
   - ✅ Verify Theta Terminal is running
   - ✅ Create a firewall rule to allow WSL access on port 25503
   - ✅ Test the connection

5. **Expected output:**
   ```
   [OK] Running as Administrator
   [OK] Theta Terminal is running on port 25503
   [OK] Firewall rule created successfully!
   Configuration Complete!
   ```

## Step 2: Test Connection from WSL

Once the firewall is configured, test the connection from WSL:

```bash
# Test basic connectivity
curl http://10.255.255.254:25503/

# Expected output:
# "We have upgraded to API v3. Please use API v3 instead..."
```

If you see the message above, **SUCCESS!** WSL can now access Theta Terminal.

If you see "Connection refused":
- Make sure Theta Terminal is still running on Windows
- Restart Theta Terminal
- Re-run the firewall configuration script

## Step 3: Discover Correct v3 API Endpoints

Now we need to find the correct v3 endpoint paths. Run these tests:

```bash
# Test different endpoint patterns
curl "http://10.255.255.254:25503/list/roots"
curl "http://10.255.255.254:25503/v3/list/roots"
curl "http://10.255.255.254:25503/snapshot/roots"
```

One of these should return JSON data with stock symbols. **Note which one works!**

## Step 4: Update the Download Script

Once you find the working endpoint pattern, I'll update the script with:
1. The Windows host IP: `http://10.255.255.254:25503`
2. The correct v3 endpoint paths

**After you complete Steps 1-3, let me know:**
- ✅ Firewall configuration result
- ✅ Which endpoint pattern works
- ✅ Any errors you encounter

Then I'll update the script accordingly!

---

## Troubleshooting

### "Execution of scripts is disabled on this system"

If you get this error when running the PowerShell script:

```powershell
# Run this in PowerShell (as Administrator)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Then try running the script again
```

### Firewall rule created but still can't connect

1. Check if Theta Terminal is bound to all interfaces:
   ```powershell
   netstat -an | findstr "25503"
   ```
   Should show: `0.0.0.0:25503` (not `127.0.0.1:25503`)

2. Restart Theta Terminal:
   ```powershell
   # Stop it (Ctrl+C in the terminal where it's running)
   # Then restart:
   java -jar ThetaTerminalv3.jar wayleemh@gmail.com CCmonster228!
   ```

3. Check if other firewall software is running (Norton, McAfee, etc.)

### Still not working?

Alternative approach - use port forwarding:

```powershell
# On Windows PowerShell (as Administrator):
netsh interface portproxy add v4tov4 listenport=25503 listenaddress=10.255.255.254 connectport=25503 connectaddress=127.0.0.1
```

This forwards WSL connections to Windows localhost.
