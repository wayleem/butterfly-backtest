# Running the Download Script on Windows

Since Theta Terminal is running on Windows and you're trying to run the Python script from WSL, you have two options:

## Option 1: Run Everything on Windows (RECOMMENDED)

This is the simplest approach and avoids firewall issues.

### Steps:

1. **Install Python on Windows** (if not already installed)
   - Download from: https://www.python.org/downloads/
   - Make sure to check "Add Python to PATH" during installation

2. **Install dependencies on Windows**
   ```powershell
   # Open PowerShell or Command Prompt
   cd C:\Users\wayle\code\startup\butterfly

   pip install requests pandas tqdm
   ```

3. **Copy the files to Windows**
   The files are already in WSL at: `/home/wayleem/code/startup/butterfly/`

   From Windows, they're accessible at:
   ```
   \\wsl$\Ubuntu\home\wayleem\code\startup\butterfly\
   ```

   Copy these files to a Windows directory:
   ```powershell
   # Example: Copy to your Windows user directory
   mkdir C:\Users\wayle\ThetaDownload
   copy \\wsl$\Ubuntu\home\wayleem\code\startup\butterfly\download_spy_options.py C:\Users\wayle\ThetaDownload\
   copy \\wsl$\Ubuntu\home\wayleem\code\startup\butterfly\run_download_windows.bat C:\Users\wayle\ThetaDownload\
   ```

4. **Start Theta Terminal** (if not already running)
   ```powershell
   cd C:\Users\wayle\Downloads
   java -jar ThetaTerminalv3.jar wayleemh@gmail.com CCmonster228!
   ```

   Keep this window open!

5. **Run the download script**

   Option A - Using the batch file:
   ```powershell
   cd C:\Users\wayle\ThetaDownload
   .\run_download_windows.bat
   ```

   Option B - Directly with Python:
   ```powershell
   cd C:\Users\wayle\ThetaDownload
   python download_spy_options.py
   ```

## Option 2: Configure WSL to Access Windows Theta Terminal

This requires Windows Firewall configuration.

### Steps:

1. **Find your Windows IP from WSL**
   ```bash
   cat /etc/resolv.conf | grep nameserver | awk '{print $2}'
   # Example output: 10.255.255.254
   ```

2. **Update the script to use Windows IP**
   Edit `download_spy_options.py` and change:
   ```python
   THETA_BASE_URL = "http://10.255.255.254:25503"  # Use your Windows IP
   ```

3. **Configure Windows Firewall**

   Open PowerShell as Administrator and run:
   ```powershell
   # Allow WSL to access Theta Terminal port
   New-NetFirewallRule -DisplayName "Theta Terminal WSL" -Direction Inbound -LocalPort 25503 -Protocol TCP -Action Allow
   ```

4. **Test connection from WSL**
   ```bash
   curl "http://10.255.255.254:25503/v3/list/roots"
   ```

   Should return JSON with stock roots.

5. **Run the script from WSL**
   ```bash
   cd /home/wayleem/code/startup/butterfly
   python3 download_spy_options.py
   ```

## Troubleshooting

### "Cannot connect to Theta Terminal"

**Check if Theta Terminal is running:**
```powershell
# From Windows PowerShell:
curl http://localhost:25503/v3/list/roots
```

Should return JSON data. If not, Theta Terminal isn't running.

**Start Theta Terminal:**
```powershell
cd C:\Users\wayle\Downloads
java -jar ThetaTerminalv3.jar wayleemh@gmail.com CCmonster228!
```

### "ModuleNotFoundError: No module named 'requests'"

Install dependencies:
```powershell
# On Windows:
pip install requests pandas tqdm

# Or from WSL:
pip install -r requirements.txt
```

### Script runs but no data downloaded

Check the log file `download.log` for specific errors:
```powershell
# Windows:
type download.log

# WSL:
cat download.log
```

## Recommended Approach

**Option 1 (Windows)** is recommended because:
- ✅ No firewall configuration needed
- ✅ Faster (no WSL networking overhead)
- ✅ Simpler troubleshooting
- ✅ Direct access to Theta Terminal

## File Locations After Download

The output files will be created in the same directory as the script:

- `spy_options_2022_2024.csv` - The main data file
- `download.log` - Detailed logs
- `download_checkpoint.json` - Resume checkpoint (can be deleted when complete)

## Estimated Download Time

- **Full range (2022-01-01 to 2024-11-11)**: 2-4 hours
- Progress is saved every 10 days, so you can stop and resume anytime

## Next Steps After Download

Once complete, you can copy the CSV back to WSL if needed:
```powershell
# From Windows to WSL
copy C:\Users\wayle\ThetaDownload\spy_options_2022_2024.csv \\wsl$\Ubuntu\home\wayleem\code\startup\butterfly\
```

Or just use it directly from Windows for your backtesting.
