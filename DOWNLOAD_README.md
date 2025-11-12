# SPY Options Data Download Guide

This guide explains how to download historical SPY options data using the ThetaData API.

## Prerequisites

### 1. Install Dependencies

```bash
pip install requests pandas tqdm
```

### 2. Install Java (Required for Theta Terminal)

ThetaData requires Java 17 or higher. Check your version:

```bash
java -version
```

If you need to install Java:

```bash
# Ubuntu/Debian
sudo apt install openjdk-21-jdk openjdk-21-jre

# macOS
brew install openjdk@21

# Windows
# Download from: https://adoptium.net/
```

### 3. Download Theta Terminal

Download the Theta Terminal JAR file:
- https://download-stable.thetadata.us/

Save it to a convenient location (e.g., `~/thetadata/ThetaTerminal.jar`)

### 4. Get ThetaData Account

- Free tier: Use `default` for both username and password
- Paid tier: Sign up at https://thetadata.net and use your credentials

## Setup

### 1. Configure Credentials

Edit `download_spy_options.py` and update these lines at the top:

```python
# ThetaData Credentials
THETA_USERNAME = "your_username_here"  # Replace with your username
THETA_PASSWORD = "your_password_here"  # Replace with your password
```

For free tier:
```python
THETA_USERNAME = "default"
THETA_PASSWORD = "default"
```

### 2. Adjust Download Parameters (Optional)

You can customize these parameters in the script:

```python
START_DATE = "2022-01-01"  # Start date
END_DATE = "2024-11-11"    # End date
MIN_DTE = 28               # Minimum days to expiration
MAX_DTE = 40               # Maximum days to expiration
OUTPUT_FILE = "spy_options_2022_2024.csv"  # Output filename
```

## Usage

### Step 1: Start Theta Terminal

Open a terminal and start Theta Terminal:

```bash
# Navigate to where you saved ThetaTerminal.jar
cd ~/thetadata

# Start the terminal (replace with your credentials)
java -jar ThetaTerminal.jar your_username your_password

# For free tier:
java -jar ThetaTerminal.jar default default
```

**Important:** Keep this terminal window open while downloading. You should see:
```
Theta Terminal started successfully
Server running on http://127.0.0.1:25510
```

### Step 2: Run the Download Script

In a **new terminal window**, run:

```bash
cd /home/wayleem/code/startup/butterfly
python3 download_spy_options.py
```

### Step 3: Monitor Progress

You'll see progress bars and logs:

```
2024-11-11 10:00:00 - INFO - ✓ Successfully connected to Theta Terminal
======================================================================
SPY Options Data Download
Date Range: 2022-01-01 to 2024-11-11
DTE Range: 28 to 40 days
======================================================================
Total trading days: 1042
Downloading 2022-01-03: 100%|██████████| 1042/1042 [2:15:30<00:00]
```

## Output

### CSV File Format

The script generates `spy_options_2022_2024.csv` with these columns:

| Column | Description |
|--------|-------------|
| `date` | Trading date (YYYY-MM-DD) |
| `expiration` | Option expiration date (YYYY-MM-DD) |
| `strike` | Strike price |
| `type` | Option type ('call' or 'put') |
| `bid` | Bid price at EOD |
| `ask` | Ask price at EOD |
| `volume` | Trading volume |
| `open_interest` | Open interest |
| `iv` | Implied volatility |
| `delta` | Delta |
| `gamma` | Gamma |
| `theta` | Theta |
| `vega` | Vega |

### Example Output

```csv
date,expiration,strike,type,bid,ask,volume,open_interest,iv,delta,gamma,theta,vega
2022-01-03,2022-02-04,450.0,call,2.15,2.25,150,5000,0.185,0.45,0.025,-0.08,0.35
2022-01-03,2022-02-04,450.0,put,1.80,1.90,200,4500,0.180,-0.55,0.025,-0.08,0.35
...
```

## Features

### 1. Resume on Interruption

If the download is interrupted (Ctrl+C or error), the script saves a checkpoint. Simply run it again to resume:

```bash
python3 download_spy_options.py
```

You'll see:
```
Resuming from checkpoint: 2022-06-15
Remaining trading days: 523
```

### 2. Error Handling

The script automatically:
- Retries failed requests with exponential backoff
- Handles rate limits
- Skips dates with missing data
- Validates data quality
- Logs all errors to `download.log`

### 3. Progress Tracking

- Overall progress bar for trading days
- Nested progress bar for expirations per day
- Real-time logging of success/failures
- Estimated time remaining

### 4. Data Validation

The script validates:
- No negative prices
- Bid ≤ Ask
- No missing critical data
- Reasonable strike prices

## Troubleshooting

### Connection Error

**Error:**
```
Cannot connect to Theta Terminal. Is it running?
```

**Solution:**
1. Make sure Theta Terminal is running in another terminal
2. Check it's accessible: `curl http://127.0.0.1:25510/v2/list/roots`
3. Restart Theta Terminal if needed

### Rate Limit Error

**Error:**
```
Rate limit exceeded. Retry after 60s
```

**Solution:**
- The script automatically retries after waiting
- If persistent, reduce `RATE_LIMIT_CALLS_PER_MINUTE` in the script
- Free tier: max 30 requests/minute
- Paid tier: check your subscription limits

### No Data for Dates

**Message:**
```
No expirations in DTE range for 2022-01-01
```

**Explanation:**
- This is normal for weekends, holidays, or when no options match the DTE filter
- The script continues to the next date

### Memory Issues

**Error:**
```
MemoryError: Unable to allocate array
```

**Solution:**
1. Reduce date range (download in chunks)
2. Increase system RAM
3. Reduce DTE range to download fewer expirations

## Advanced Configuration

### Change DTE Range

For different strategies, adjust the DTE range:

```python
# For weekly iron condors (7-14 DTE)
MIN_DTE = 7
MAX_DTE = 14

# For monthly strategies (28-35 DTE)
MIN_DTE = 28
MAX_DTE = 35

# For LEAPS (365+ DTE)
MIN_DTE = 365
MAX_DTE = 730
```

### Download Specific Dates

Edit the `get_trading_days()` method to download specific dates:

```python
def get_trading_days(self) -> List[datetime]:
    """Get list of specific dates."""
    return [
        datetime(2024, 1, 15),
        datetime(2024, 2, 15),
        datetime(2024, 3, 15),
    ]
```

### Increase Rate Limit (Paid Tiers)

If you have a paid subscription:

```python
RATE_LIMIT_CALLS_PER_MINUTE = 200  # Adjust based on your tier
```

### Change Checkpoint Frequency

Save checkpoints more or less frequently:

```python
CHECKPOINT_INTERVAL = 5   # Save every 5 days (more frequent)
CHECKPOINT_INTERVAL = 20  # Save every 20 days (less frequent)
```

## Performance Tips

### 1. Run During Off-Peak Hours

ThetaData API is faster during off-peak hours (nights/weekends).

### 2. Use SSD Storage

Save output to SSD for faster I/O when combining large datasets.

### 3. Monitor Terminal Output

Keep an eye on the Theta Terminal window for any errors or warnings.

### 4. Estimated Download Time

- **Full range (2022-2024):** 2-4 hours
- **Per year:** ~40-80 minutes
- **Per month:** ~5-10 minutes

Actual time depends on:
- Internet connection speed
- ThetaData server load
- Your subscription tier rate limits

## File Sizes

Approximate output file sizes:

| Date Range | Rows | File Size |
|------------|------|-----------|
| 1 month | ~50K | ~10 MB |
| 1 year | ~600K | ~120 MB |
| 3 years (2022-2024) | ~1.8M | ~350 MB |

## Integration with Backtest

The output CSV is ready to use with `backtest.py`:

```python
import pandas as pd

# Load the data
df = pd.read_csv('spy_options_2022_2024.csv')

# Filter for specific date range
df['date'] = pd.to_datetime(df['date'])
df = df[(df['date'] >= '2023-01-01') & (df['date'] <= '2023-12-31')]

# Your backtest code here...
```

## Support

### Log Files

Check `download.log` for detailed error messages:

```bash
tail -f download.log
```

### Manual Testing

Test API connection manually:

```bash
# Check if terminal is running
curl http://127.0.0.1:25510/v2/list/roots

# Get SPY expirations
curl "http://127.0.0.1:25510/v2/list/expirations?root=SPY"
```

### Clean Start

To start fresh and clear checkpoints:

```bash
rm download_checkpoint.json
rm download.log
python3 download_spy_options.py
```

## License

This script is part of the Butterfly Trading System.

## References

- ThetaData Documentation: https://http-docs.thetadata.us/
- ThetaData Download: https://download-stable.thetadata.us/
- Butterfly Backtest: See `backtest.py`
