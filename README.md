# Long Iron Butterfly Options Backtest

A comprehensive Python backtest engine for testing long iron butterfly strategies on SPY options with realistic transaction costs.

## Strategy Overview

**Position Structure:**
- Buy 1 call at (ATM - $3)
- Sell 1 call at ATM
- Sell 1 put at ATM
- Buy 1 put at (ATM + $3)

This creates a long butterfly centered at ATM with $3 wings, which profits when SPY stays near the ATM strike at expiration.

## Features

- Realistic cost modeling (commissions + bid/ask slippage)
- Configurable entry/exit rules
- Comprehensive performance analytics
- Trade-by-trade CSV logging
- Equity curve and drawdown visualization

## Requirements

Install dependencies:

```bash
pip install -r requirements.txt
```

Dependencies:
- pandas >= 1.5.0
- numpy >= 1.23.0
- matplotlib >= 3.6.0
- python-dateutil >= 2.8.0

## CSV Data Format

Your options data CSV must contain these columns:

| Column | Type | Description |
|--------|------|-------------|
| date | date | Trading date (YYYY-MM-DD) |
| expiration | date | Option expiration date (YYYY-MM-DD) |
| strike | float | Strike price |
| type | string | 'call' or 'put' |
| bid | float | Bid price |
| ask | float | Ask price |
| volume | int | Daily trading volume |
| open_interest | int | Open interest |
| delta | float | Option delta (0 to 1 for calls, -1 to 0 for puts) |

Optional columns (not currently used but good to have):
- last, iv, gamma, theta, vega

**Example:**
```csv
date,expiration,strike,type,bid,ask,last,volume,open_interest,iv,delta,gamma,theta,vega
2024-01-02,2024-02-02,450.0,call,5.20,5.40,5.30,1250,5430,0.18,0.52,0.025,-0.12,0.45
2024-01-02,2024-02-02,450.0,put,4.80,5.00,4.90,980,4210,0.19,0.48,0.024,-0.11,0.44
```

## Usage

Basic usage:

```bash
python backtest.py path/to/your/options_data.csv
```

The backtest will:
1. Load your CSV data
2. Scan daily for valid butterfly setups
3. Enter positions when criteria are met
4. Monitor and exit based on P&L or time
5. Print summary statistics
6. Save trade log to `trade_log.csv`
7. Generate equity curve chart to `equity_curve.png`

## Strategy Parameters

All strategy parameters are configurable at the top of `backtest.py`:

### Entry Parameters

```python
MIN_DTE = 28                    # Minimum days to expiration
MAX_DTE = 40                    # Maximum days to expiration
TARGET_DTE = 35                 # Preferred DTE (will choose closest)
WING_WIDTH = 3                  # Distance of wings from ATM ($)
MIN_REWARD_RISK = 10.0          # Minimum R/R ratio to enter
MAX_SPREAD_PCT = 30             # Max bid-ask spread (% of debit)
MIN_VOLUME = 50                 # Minimum total volume (all 4 legs)
MIN_OPEN_INTEREST = 100         # Minimum total OI (all 4 legs)
MAX_POSITIONS = 1               # Max concurrent positions
```

### Exit Parameters

```python
PROFIT_TARGET_PCT = 10          # Take profit at 10% of entry cost
LOSS_LIMIT_PCT = 20             # Stop loss at 20% of entry cost
FORCE_EXIT_DTE = 7              # Force close at this DTE
```

### Cost Parameters

```python
COMMISSION_PER_CONTRACT = 0.65  # Commission per contract
CONTRACTS_PER_BUTTERFLY = 1     # Number of spreads to trade
```

## Entry Logic

The backtest scans daily for butterfly opportunities:

1. **Find valid expirations:** 28-40 DTE range
2. **Select best expiration:** Closest to 35 DTE
3. **Calculate spot price:** Using put-call parity from options prices
4. **Find ATM strike:** Call option with delta closest to 0.50
5. **Build butterfly:** Construct 4-leg spread with $3 wings
6. **Apply filters:**
   - Reward/Risk ratio >= 10.0
   - Total bid-ask spread < 30% of net debit
   - Total volume >= 50 contracts
   - Total open interest >= 100 contracts
   - No existing position (max 1 at a time)

**Entry costs (realistic):**
- Buy legs filled at ask price
- Sell legs filled at bid price
- $0.65 commission per contract (4 legs = $2.60 total)

## Exit Logic

Positions are monitored daily and closed when:

1. **Profit target:** P&L reaches +10% of entry cost
2. **Stop loss:** P&L reaches -20% of entry cost
3. **Time exit:** DTE reaches 7 days or less
4. **Forced exit:** End of data or missing quotes

**Exit costs (realistic):**
- Reverse positions at bid/ask (worse prices)
- $0.65 commission per contract (4 legs = $2.60 total)

## Output Files

### trade_log.csv

Detailed record of every trade with columns:
- entry_date, exit_date
- expiration
- entry_dte, exit_dte
- atm_strike
- entry_cost, exit_value
- pnl, pnl_pct
- reward_risk
- exit_reason

### equity_curve.png

Two-panel chart showing:
- **Top panel:** Cumulative P&L over time
- **Bottom panel:** Drawdown from peak equity

## Performance Metrics

The backtest calculates and displays:

**Trade Statistics:**
- Total trades executed
- Winning trades
- Losing trades
- Win rate (%)

**P&L Statistics:**
- Total P&L
- Average P&L per trade
- Average winner
- Average loser
- Expected value per trade

**Risk Metrics:**
- Sharpe ratio (annualized)
- Maximum drawdown ($)
- Maximum drawdown (%)

**Average Metrics:**
- Average entry DTE
- Average hold time
- Average reward/risk ratio

**Exit Breakdown:**
- Count by exit reason

## Example Output

```
================================================================================
BACKTEST RESULTS
================================================================================

Trade Statistics:
  Total Trades:        42
  Winning Trades:      28
  Losing Trades:       14
  Win Rate:            66.67%

P&L Statistics:
  Total P&L:           $1,245.30
  Average P&L:         $29.65
  Average Winner:      $75.20
  Average Loser:       -$82.15
  Expected Value:      $29.65 per trade

Risk Metrics:
  Sharpe Ratio:        1.45
  Max Drawdown:        -$324.50 (-12.3%)

Average Metrics:
  Avg Entry DTE:       34.8 days
  Avg Hold Time:       18.2 days
  Avg Reward/Risk:     12.5

Exit Reasons:
  Profit target (10.0%): 22
  Stop loss (-20.0%): 14
  Force exit at 7 DTE: 6

================================================================================

Trade log saved to: trade_log.csv
Equity curve saved to: equity_curve.png
```

## Customization Tips

### Testing Different Strategies

1. **Wider wings:** Change `WING_WIDTH = 5` for more credit, lower R/R
2. **Longer hold:** Change `FORCE_EXIT_DTE = 3` to hold closer to expiration
3. **Tighter stops:** Change `LOSS_LIMIT_PCT = 15` to cut losses faster
4. **Bigger profits:** Change `PROFIT_TARGET_PCT = 20` to let winners run

### Testing Different Markets

The code works with any underlying if you have the options data in the same CSV format. Just replace "SPY" references in comments.

### Multiple Contracts

Change `CONTRACTS_PER_BUTTERFLY = 5` to scale position size (affects all P&L calculations).

## Troubleshooting

**"Error: File not found"**
- Check the file path is correct
- Use absolute path or relative to script location

**"Error: Missing required columns"**
- Verify CSV has all required columns spelled correctly
- Column names are case-sensitive

**"No trades executed"**
- Check if data covers enough dates
- Try relaxing entry filters (lower MIN_REWARD_RISK, etc.)
- Verify options data has sufficient liquidity

**"Warning: Position still open at end"**
- This is normal - last position is closed at final date
- Extend data range if you want clean exits

## Notes

- **Realistic costs:** Entry at ask, exit at bid, plus commissions
- **No lookahead bias:** Uses only data available at each date
- **ATM definition:** Call with delta closest to 0.50
- **Spot calculation:** Put-call parity for accuracy
- **Single position:** Max 1 butterfly at a time (prevents over-allocation)

## License

This code is provided as-is for educational and research purposes.
