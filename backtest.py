#!/usr/bin/env python3
"""
Long Iron Butterfly Options Backtest for SPY

This script backtests a long iron butterfly strategy on SPY options with realistic
costs (commissions and bid/ask slippage).

Strategy: Buy ATM-3 call, Sell ATM call, Sell ATM put, Buy ATM+3 put
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from collections import defaultdict
import sys

# ============================================================================
# CONFIGURABLE PARAMETERS - Modify these to test different strategies
# ============================================================================

# Entry parameters
MIN_DTE = 28                    # Minimum days to expiration
MAX_DTE = 40                    # Maximum days to expiration
TARGET_DTE = 35                 # Preferred DTE (will choose closest to this)
WING_WIDTH = 3                  # Distance of wings from ATM (in dollars)
MIN_REWARD_RISK = 10.0          # Minimum reward/risk ratio to enter
MAX_SPREAD_PCT = 30             # Max total bid-ask spread as % of net debit
MIN_VOLUME = 50                 # Minimum total volume across all 4 legs
MIN_OPEN_INTEREST = 100         # Minimum total OI across all 4 legs

# Exit parameters
PROFIT_TARGET_PCT = 10          # Take profit at 10% of entry cost
LOSS_LIMIT_PCT = 20             # Stop loss at 20% of entry cost
FORCE_EXIT_DTE = 7              # Force close position at this DTE

# Position sizing
MAX_POSITIONS = 1               # Maximum concurrent positions

# Cost parameters
COMMISSION_PER_CONTRACT = 0.65  # Commission per contract (each leg)
SLIPPAGE_PCT = 0.01             # Additional slippage percentage (1%)
CONTRACTS_PER_BUTTERFLY = 1     # Number of butterfly spreads to trade

# Output parameters
TRADE_LOG_FILE = "trade_log.csv"
EQUITY_CURVE_FILE = "equity_curve.png"

# ============================================================================
# DATA LOADING AND VALIDATION
# ============================================================================

def load_options_data(filepath):
    """Load options data from CSV file."""
    print(f"Loading data from {filepath}...")

    try:
        df = pd.read_csv(filepath)
    except FileNotFoundError:
        print(f"Error: File '{filepath}' not found.")
        sys.exit(1)

    # Validate required columns
    required_cols = ['date', 'expiration', 'strike', 'type', 'bid', 'ask',
                     'volume', 'open_interest', 'delta']
    missing_cols = set(required_cols) - set(df.columns)
    if missing_cols:
        print(f"Error: Missing required columns: {missing_cols}")
        sys.exit(1)

    # Convert date columns to datetime
    df['date'] = pd.to_datetime(df['date'])
    df['expiration'] = pd.to_datetime(df['expiration'])

    # Calculate DTE
    df['dte'] = (df['expiration'] - df['date']).dt.days

    # Standardize option type
    df['type'] = df['type'].str.lower()

    print(f"Loaded {len(df):,} option records")
    print(f"Date range: {df['date'].min()} to {df['date'].max()}")
    print(f"Unique dates: {df['date'].nunique()}")

    return df

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def calculate_spot_price(options_df, date, expiration):
    """
    Calculate spot price using put-call parity from ATM options.

    NOTE: This function is currently unused but available for alternative ATM
    determination methods (e.g., finding strike nearest to calculated spot).

    We use: S = K + (C - P) where K is strike, C is call price, P is put price
    """
    # Filter to calls and puts for this date/expiration
    mask = (options_df['date'] == date) & (options_df['expiration'] == expiration)
    calls = options_df[mask & (options_df['type'] == 'call')].copy()
    puts = options_df[mask & (options_df['type'] == 'put')].copy()

    if len(calls) == 0 or len(puts) == 0:
        return None

    # For each strike, calculate implied spot using put-call parity
    # Use mid prices for better estimate
    calls['mid'] = (calls['bid'] + calls['ask']) / 2
    puts['mid'] = (puts['bid'] + puts['ask']) / 2

    # Merge calls and puts on strike
    merged = calls[['strike', 'mid', 'delta']].merge(
        puts[['strike', 'mid']],
        on='strike',
        suffixes=('_call', '_put')
    )

    if len(merged) == 0:
        return None

    # Calculate implied spot for each strike
    merged['implied_spot'] = merged['strike'] + (merged['mid_call'] - merged['mid_put'])

    # Use the strike closest to 50 delta for most accurate estimate
    merged['delta_diff'] = abs(merged['delta'] - 0.5)
    best_row = merged.loc[merged['delta_diff'].idxmin()]

    return best_row['implied_spot']

def find_atm_strike(options_df, date, expiration):
    """
    Find ATM strike using call delta closest to 0.50.
    """
    mask = (
        (options_df['date'] == date) &
        (options_df['expiration'] == expiration) &
        (options_df['type'] == 'call')
    )
    calls = options_df[mask].copy()

    if len(calls) == 0:
        return None

    # Find strike with delta closest to 0.50
    calls['delta_diff'] = abs(calls['delta'] - 0.5)
    atm_call = calls.loc[calls['delta_diff'].idxmin()]

    return atm_call['strike']

def get_option_quote(options_df, date, expiration, strike, opt_type):
    """
    Get bid/ask quote for a specific option.
    """
    mask = (
        (options_df['date'] == date) &
        (options_df['expiration'] == expiration) &
        (options_df['strike'] == strike) &
        (options_df['type'] == opt_type)
    )

    option = options_df[mask]

    if len(option) == 0:
        return None

    if len(option) > 1:
        # If multiple matches, take first (shouldn't happen with clean data)
        option = option.iloc[0:1]

    return {
        'bid': option['bid'].iloc[0],
        'ask': option['ask'].iloc[0],
        'volume': option['volume'].iloc[0],
        'open_interest': option['open_interest'].iloc[0],
        'mid': (option['bid'].iloc[0] + option['ask'].iloc[0]) / 2
    }

def build_butterfly(options_df, date, expiration, atm_strike):
    """
    Build long iron butterfly structure.

    Long butterfly:
    - Buy 1 call at (ATM - wing_width)
    - Sell 1 call at ATM
    - Sell 1 put at ATM
    - Buy 1 put at (ATM + wing_width)

    Returns None if any leg is missing, otherwise returns butterfly dict.
    """
    long_call_strike = atm_strike - WING_WIDTH
    short_call_strike = atm_strike
    short_put_strike = atm_strike
    long_put_strike = atm_strike + WING_WIDTH

    # Get quotes for all 4 legs
    long_call = get_option_quote(options_df, date, expiration, long_call_strike, 'call')
    short_call = get_option_quote(options_df, date, expiration, short_call_strike, 'call')
    short_put = get_option_quote(options_df, date, expiration, short_put_strike, 'put')
    long_put = get_option_quote(options_df, date, expiration, long_put_strike, 'put')

    # Check if all legs exist
    if None in [long_call, short_call, short_put, long_put]:
        return None

    # Calculate net debit (we're buying this butterfly, so we pay to enter)
    # Buy call = pay ask, Sell call = receive bid
    # Sell put = receive bid, Buy put = pay ask
    entry_cost = (
        long_call['ask'] +      # Buy call (pay ask)
        (-short_call['bid']) +  # Sell call (receive bid)
        (-short_put['bid']) +   # Sell put (receive bid)
        long_put['ask']         # Buy put (pay ask)
    )

    # Apply slippage to entry cost (increases cost)
    entry_slippage = entry_cost * SLIPPAGE_PCT
    entry_cost_with_slippage = entry_cost + entry_slippage

    # Add commissions for entry (4 legs)
    entry_commission = 4 * COMMISSION_PER_CONTRACT

    # Scale by number of contracts
    net_debit = (entry_cost_with_slippage + entry_commission) * CONTRACTS_PER_BUTTERFLY

    # Calculate max profit and max loss (per butterfly, before scaling)
    # Max profit occurs when price = ATM at expiration
    # Max profit = wing_width - net_debit_per_butterfly
    net_debit_per_butterfly = (entry_cost_with_slippage + entry_commission)
    max_profit_per_butterfly = WING_WIDTH - net_debit_per_butterfly
    max_loss_per_butterfly = net_debit_per_butterfly

    # Scale by number of contracts
    max_profit = max_profit_per_butterfly * CONTRACTS_PER_BUTTERFLY
    max_loss = max_loss_per_butterfly * CONTRACTS_PER_BUTTERFLY

    # Reward/risk ratio
    reward_risk = max_profit / max_loss if max_loss > 0 else 0

    # Calculate total bid-ask spread
    total_spread = (
        (long_call['ask'] - long_call['bid']) +
        (short_call['ask'] - short_call['bid']) +
        (short_put['ask'] - short_put['bid']) +
        (long_put['ask'] - long_put['bid'])
    )
    spread_pct = (total_spread / abs(net_debit)) * 100 if net_debit != 0 else float('inf')

    # Calculate total volume and open interest
    total_volume = (
        long_call['volume'] + short_call['volume'] +
        short_put['volume'] + long_put['volume']
    )
    total_oi = (
        long_call['open_interest'] + short_call['open_interest'] +
        short_put['open_interest'] + long_put['open_interest']
    )

    return {
        'long_call_strike': long_call_strike,
        'short_call_strike': short_call_strike,
        'short_put_strike': short_put_strike,
        'long_put_strike': long_put_strike,
        'long_call': long_call,
        'short_call': short_call,
        'short_put': short_put,
        'long_put': long_put,
        'entry_cost': entry_cost,
        'entry_commission': entry_commission,
        'net_debit': net_debit,
        'max_profit': max_profit,
        'max_loss': max_loss,
        'reward_risk': reward_risk,
        'total_spread': total_spread,
        'spread_pct': spread_pct,
        'total_volume': total_volume,
        'total_oi': total_oi
    }

def calculate_butterfly_value(options_df, date, expiration, butterfly):
    """
    Calculate current market value of butterfly position.

    To exit, we reverse the trades:
    - Sell the long call (at bid)
    - Buy back the short call (at ask)
    - Buy back the short put (at ask)
    - Sell the long put (at bid)
    """
    long_call = get_option_quote(
        options_df, date, expiration,
        butterfly['long_call_strike'], 'call'
    )
    short_call = get_option_quote(
        options_df, date, expiration,
        butterfly['short_call_strike'], 'call'
    )
    short_put = get_option_quote(
        options_df, date, expiration,
        butterfly['short_put_strike'], 'put'
    )
    long_put = get_option_quote(
        options_df, date, expiration,
        butterfly['long_put_strike'], 'put'
    )

    # Check if all legs still exist
    if None in [long_call, short_call, short_put, long_put]:
        return None

    # Calculate exit value (reversing the position)
    exit_value = (
        long_call['bid'] +      # Sell call (receive bid)
        (-short_call['ask']) +  # Buy back call (pay ask)
        (-short_put['ask']) +   # Buy back put (pay ask)
        long_put['bid']         # Sell put (receive bid)
    )

    # Apply slippage to exit value (decreases value received)
    exit_slippage = abs(exit_value) * SLIPPAGE_PCT
    exit_value_with_slippage = exit_value - exit_slippage

    # Subtract exit commissions
    exit_commission = 4 * COMMISSION_PER_CONTRACT

    # Scale by number of contracts
    net_exit_value = (exit_value_with_slippage - exit_commission) * CONTRACTS_PER_BUTTERFLY

    return net_exit_value

# ============================================================================
# BACKTEST ENGINE
# ============================================================================

def run_backtest(options_df):
    """
    Run the backtest on historical options data.
    """
    print("\n" + "="*80)
    print("STARTING BACKTEST")
    print("="*80)

    # Get unique trading dates
    dates = sorted(options_df['date'].unique())

    # Track state
    current_position = None
    trades = []
    equity_curve = []
    current_equity = 0

    print(f"\nScanning {len(dates)} trading days...\n")

    for date in dates:
        # Get available options for this date
        daily_options = options_df[options_df['date'] == date]

        # Get available expirations in target DTE range
        expirations = daily_options[
            (daily_options['dte'] >= MIN_DTE) &
            (daily_options['dte'] <= MAX_DTE)
        ]['expiration'].unique()

        # If we have a position, check for exit conditions
        if current_position is not None:
            pos = current_position
            pos_dte = (pos['expiration'] - date).days

            # Calculate current value
            current_value = calculate_butterfly_value(
                daily_options, date, pos['expiration'], pos
            )

            should_exit = False
            exit_reason = None

            if current_value is None:
                # Options expired or data missing - force exit
                should_exit = True
                exit_reason = "Missing data"
                current_value = 0  # Assume worthless
            else:
                # Calculate P&L
                pnl = current_value - pos['net_debit']
                pnl_pct = (pnl / pos['net_debit']) * 100

                # Check exit conditions
                if pnl_pct >= PROFIT_TARGET_PCT:
                    should_exit = True
                    exit_reason = f"Profit target ({pnl_pct:.1f}%)"
                elif pnl_pct <= -LOSS_LIMIT_PCT:
                    should_exit = True
                    exit_reason = f"Stop loss ({pnl_pct:.1f}%)"
                elif pos_dte <= FORCE_EXIT_DTE:
                    should_exit = True
                    exit_reason = f"Force exit at {pos_dte} DTE"

            if should_exit:
                # Close position
                pnl = current_value - pos['net_debit']
                pnl_pct = (pnl / pos['net_debit']) * 100

                trades.append({
                    'entry_date': pos['entry_date'],
                    'exit_date': date,
                    'expiration': pos['expiration'],
                    'entry_dte': pos['entry_dte'],
                    'exit_dte': pos_dte,
                    'atm_strike': pos['short_call_strike'],
                    'entry_cost': pos['net_debit'],
                    'exit_value': current_value,
                    'pnl': pnl,
                    'pnl_pct': pnl_pct,
                    'reward_risk': pos['reward_risk'],
                    'exit_reason': exit_reason
                })

                current_equity += pnl

                print(f"{date.strftime('%Y-%m-%d')}: CLOSED position | "
                      f"P&L: ${pnl:+.2f} ({pnl_pct:+.1f}%) | "
                      f"Reason: {exit_reason}")

                current_position = None

        # If no position and we can trade, look for entry
        if current_position is None and len(expirations) > 0:
            # Find expiration closest to target DTE
            exp_dtes = []
            for exp in expirations:
                dte = (exp - date).days
                exp_dtes.append((exp, dte, abs(dte - TARGET_DTE)))

            # Sort by distance from target DTE
            exp_dtes.sort(key=lambda x: x[2])
            best_expiration, best_dte, _ = exp_dtes[0]

            # Find ATM strike (using delta method - call with delta closest to 0.50)
            atm = find_atm_strike(daily_options, date, best_expiration)
            if atm is None:
                continue

            # Build butterfly
            butterfly = build_butterfly(daily_options, date, best_expiration, atm)
            if butterfly is None:
                continue

            # Check entry filters
            if butterfly['reward_risk'] < MIN_REWARD_RISK:
                continue

            if butterfly['spread_pct'] > MAX_SPREAD_PCT:
                continue

            if butterfly['total_volume'] < MIN_VOLUME:
                continue

            if butterfly['total_oi'] < MIN_OPEN_INTEREST:
                continue

            # Enter position
            current_position = {
                'entry_date': date,
                'expiration': best_expiration,
                'entry_dte': best_dte,
                **butterfly
            }

            print(f"{date.strftime('%Y-%m-%d')}: OPENED position | "
                  f"DTE: {best_dte} | ATM: ${atm:.2f} | "
                  f"Cost: ${butterfly['net_debit']:.2f} | "
                  f"R/R: {butterfly['reward_risk']:.1f}")

        # Record equity
        equity_curve.append({
            'date': date,
            'equity': current_equity
        })

    # Close any remaining position at last date
    if current_position is not None:
        print(f"\nWarning: Position still open at end of backtest - closing at final value")
        final_value = calculate_butterfly_value(
            options_df[options_df['date'] == dates[-1]],
            dates[-1],
            current_position['expiration'],
            current_position
        )
        if final_value is None:
            final_value = 0

        pnl = final_value - current_position['net_debit']
        pnl_pct = (pnl / current_position['net_debit']) * 100

        trades.append({
            'entry_date': current_position['entry_date'],
            'exit_date': dates[-1],
            'expiration': current_position['expiration'],
            'entry_dte': current_position['entry_dte'],
            'exit_dte': (current_position['expiration'] - dates[-1]).days,
            'atm_strike': current_position['short_call_strike'],
            'entry_cost': current_position['net_debit'],
            'exit_value': final_value,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'reward_risk': current_position['reward_risk'],
            'exit_reason': 'End of backtest'
        })

        current_equity += pnl

    return trades, equity_curve

# ============================================================================
# PERFORMANCE ANALYTICS
# ============================================================================

def calculate_statistics(trades, equity_curve):
    """
    Calculate performance statistics from trade history.
    """
    if len(trades) == 0:
        print("\nNo trades executed during backtest period.")
        return

    df_trades = pd.DataFrame(trades)
    df_equity = pd.DataFrame(equity_curve)

    # Basic statistics
    total_trades = len(df_trades)
    winning_trades = len(df_trades[df_trades['pnl'] > 0])
    losing_trades = len(df_trades[df_trades['pnl'] < 0])
    win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0

    # P&L statistics
    total_pnl = df_trades['pnl'].sum()
    avg_pnl = df_trades['pnl'].mean()
    avg_winner = df_trades[df_trades['pnl'] > 0]['pnl'].mean() if winning_trades > 0 else 0
    avg_loser = df_trades[df_trades['pnl'] < 0]['pnl'].mean() if losing_trades > 0 else 0

    # Expected value per trade
    ev_per_trade = total_pnl / total_trades if total_trades > 0 else 0

    # Calculate max drawdown
    df_equity['cummax'] = df_equity['equity'].cummax()
    df_equity['drawdown'] = df_equity['equity'] - df_equity['cummax']
    max_drawdown = df_equity['drawdown'].min()
    max_drawdown_pct = (max_drawdown / df_equity['cummax'].max() * 100) if df_equity['cummax'].max() > 0 else 0

    # Sharpe ratio (annualized)
    # Calculate daily returns
    daily_returns = df_equity['equity'].diff().dropna()
    if len(daily_returns) > 0 and daily_returns.std() > 0:
        sharpe = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)  # Annualized
    else:
        sharpe = 0

    # Print statistics
    print("\n" + "="*80)
    print("BACKTEST RESULTS")
    print("="*80)
    print(f"\nTrade Statistics:")
    print(f"  Total Trades:        {total_trades}")
    print(f"  Winning Trades:      {winning_trades}")
    print(f"  Losing Trades:       {losing_trades}")
    print(f"  Win Rate:            {win_rate:.2f}%")
    print(f"\nP&L Statistics:")
    print(f"  Total P&L:           ${total_pnl:,.2f}")
    print(f"  Average P&L:         ${avg_pnl:,.2f}")
    print(f"  Average Winner:      ${avg_winner:,.2f}")
    print(f"  Average Loser:       ${avg_loser:,.2f}")
    print(f"  Expected Value:      ${ev_per_trade:,.2f} per trade")
    print(f"\nRisk Metrics:")
    print(f"  Sharpe Ratio:        {sharpe:.2f}")
    print(f"  Max Drawdown:        ${max_drawdown:,.2f} ({max_drawdown_pct:.1f}%)")
    print(f"\nAverage Metrics:")
    print(f"  Avg Entry DTE:       {df_trades['entry_dte'].mean():.1f} days")
    print(f"  Avg Hold Time:       {(df_trades['entry_dte'] - df_trades['exit_dte']).mean():.1f} days")
    print(f"  Avg Reward/Risk:     {df_trades['reward_risk'].mean():.2f}")
    print(f"\nExit Reasons:")
    for reason in df_trades['exit_reason'].value_counts().items():
        print(f"  {reason[0]}: {reason[1]}")

    print("\n" + "="*80)

    return df_trades, df_equity

def save_trade_log(df_trades):
    """Save detailed trade log to CSV."""
    if df_trades is None or len(df_trades) == 0:
        return

    df_trades.to_csv(TRADE_LOG_FILE, index=False)
    print(f"\nTrade log saved to: {TRADE_LOG_FILE}")

def plot_equity_curve(df_equity):
    """Generate equity curve and drawdown chart."""
    if df_equity is None or len(df_equity) == 0:
        return

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    # Equity curve
    ax1.plot(df_equity['date'], df_equity['equity'], linewidth=2, color='blue')
    ax1.axhline(y=0, color='gray', linestyle='--', linewidth=1)
    ax1.set_ylabel('Cumulative P&L ($)', fontsize=12)
    ax1.set_title('Butterfly Strategy - Equity Curve', fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3)

    # Drawdown
    ax2.fill_between(df_equity['date'], df_equity['drawdown'], 0,
                     color='red', alpha=0.3)
    ax2.plot(df_equity['date'], df_equity['drawdown'], linewidth=2, color='darkred')
    ax2.set_ylabel('Drawdown ($)', fontsize=12)
    ax2.set_xlabel('Date', fontsize=12)
    ax2.set_title('Drawdown', fontsize=14, fontweight='bold')
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(EQUITY_CURVE_FILE, dpi=150, bbox_inches='tight')
    print(f"Equity curve saved to: {EQUITY_CURVE_FILE}")

    # Don't show plot in non-interactive mode
    # plt.show()

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function."""
    # Check for CSV file argument
    if len(sys.argv) < 2:
        print("Usage: python backtest.py <path_to_options_data.csv>")
        print("\nExample: python backtest.py data/spy_options.csv")
        sys.exit(1)

    csv_file = sys.argv[1]

    # Load data
    options_df = load_options_data(csv_file)

    # Run backtest
    trades, equity_curve = run_backtest(options_df)

    # Calculate and display statistics
    df_trades, df_equity = calculate_statistics(trades, equity_curve)

    # Save outputs
    save_trade_log(df_trades)
    plot_equity_curve(df_equity)

    print("\nBacktest complete!")

if __name__ == "__main__":
    main()
