#!/usr/bin/env python3
"""
SPY Options Data Downloader - ThetaData API
Downloads historical options data for SPY from 2022-01-01 to 2024-11-11

Author: Butterfly Trading System
Date: 2025-11-11
"""

import requests
import pandas as pd
import numpy as np
import time
import logging
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
from functools import wraps
from pathlib import Path
from tqdm import tqdm

# ============================================================================
# CONFIGURATION - UPDATE THESE WITH YOUR CREDENTIALS
# ============================================================================

# ThetaData Credentials
THETA_USERNAME = "wayleemh@gmail.com"  # Replace with your ThetaData username
THETA_PASSWORD = "CCmonster228!"  # Replace with your ThetaData password

# Download Parameters
START_DATE = "2022-01-01"
END_DATE = "2024-11-11"
SYMBOL = "SPY"
MIN_DTE = 28  # Minimum days to expiration
MAX_DTE = 40  # Maximum days to expiration

# Output
OUTPUT_FILE = "spy_options_2022_2024.csv"
CHECKPOINT_FILE = "download_checkpoint.json"
LOG_FILE = "download.log"

# API Configuration
# Theta Terminal v3 runs on port 25503
# If running on Windows: use "http://localhost:25503"
# If running in WSL2: Windows Firewall may block access - run script on Windows instead,
#                     or configure firewall to allow WSL, or use Windows host IP
THETA_BASE_URL = "http://100.94.29.12:25503"  # Theta Terminal v3 default
REQUEST_TIMEOUT = 60  # seconds
RATE_LIMIT_CALLS_PER_MINUTE = 100  # Adjust based on your subscription tier
CHECKPOINT_INTERVAL = 10  # Save checkpoint every N days

# ============================================================================
# LOGGING SETUP
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# CUSTOM EXCEPTIONS
# ============================================================================

class ThetaDataError(Exception):
    """Base exception for ThetaData errors."""
    pass

class ThetaConnectionError(ThetaDataError):
    """Terminal not running or connection failed."""
    pass

class ThetaRateLimitError(ThetaDataError):
    """Rate limit exceeded."""
    pass

class ThetaDataNotAvailable(ThetaDataError):
    """Requested data not available."""
    pass

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def rate_limit(calls_per_minute: int = RATE_LIMIT_CALLS_PER_MINUTE):
    """Decorator to rate limit function calls."""
    min_interval = 60.0 / calls_per_minute
    last_called = [0.0]

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_called[0]
            left_to_wait = min_interval - elapsed
            if left_to_wait > 0:
                time.sleep(left_to_wait)

            ret = func(*args, **kwargs)
            last_called[0] = time.time()
            return ret
        return wrapper
    return decorator

def retry_with_exponential_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    exponential_base: float = 2.0,
    max_delay: float = 60.0
):
    """Decorator for retrying with exponential backoff."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)

                except requests.exceptions.ConnectionError as e:
                    if attempt == max_retries - 1:
                        raise ThetaConnectionError(
                            "Cannot connect to Theta Terminal. Is it running?"
                        ) from e

                    logger.warning(f"Connection failed, retrying in {delay:.1f}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                    delay = min(delay * exponential_base, max_delay)

                except requests.exceptions.Timeout as e:
                    if attempt == max_retries - 1:
                        raise ThetaDataError("Request timed out") from e

                    logger.warning(f"Request timed out, retrying in {delay:.1f}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                    delay = min(delay * exponential_base, max_delay)

                except ThetaRateLimitError as e:
                    if attempt == max_retries - 1:
                        raise

                    logger.warning(f"Rate limit hit, waiting {delay:.1f}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                    delay = min(delay * exponential_base, max_delay)

            raise ThetaDataError(f"Max retries ({max_retries}) exceeded")

        return wrapper
    return decorator

# ============================================================================
# CHECKPOINT MANAGEMENT
# ============================================================================

class CheckpointManager:
    """Manages download checkpoints for resumability."""

    def __init__(self, checkpoint_file: str):
        self.checkpoint_file = checkpoint_file
        self.data = self._load()

    def _load(self) -> Dict:
        """Load checkpoint from file."""
        if Path(self.checkpoint_file).exists():
            try:
                with open(self.checkpoint_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load checkpoint: {e}")
                return {}
        return {}

    def save(self, last_date: str, downloaded_data: List[pd.DataFrame]):
        """Save checkpoint."""
        try:
            self.data['last_completed_date'] = last_date
            self.data['num_rows'] = sum(len(df) for df in downloaded_data)
            self.data['timestamp'] = datetime.now().isoformat()

            with open(self.checkpoint_file, 'w') as f:
                json.dump(self.data, f, indent=2)

            logger.info(f"Checkpoint saved: {last_date}")
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")

    def get_last_completed_date(self) -> Optional[str]:
        """Get last successfully completed date."""
        return self.data.get('last_completed_date')

    def clear(self):
        """Clear checkpoint file."""
        if Path(self.checkpoint_file).exists():
            Path(self.checkpoint_file).unlink()

# ============================================================================
# THETADATA CLIENT
# ============================================================================

class ThetaDataClient:
    """ThetaData API client with robust error handling."""

    def __init__(self, base_url: str = THETA_BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()

        # Test connection
        self._test_connection()

    def _test_connection(self):
        """Test if Theta Terminal is running."""
        try:
            response = self.session.get(
                f"{self.base_url}/v3/list/roots",
                timeout=5
            )
            if response.status_code != 200:
                raise ThetaConnectionError("Terminal responded with error")

            logger.info("✓ Successfully connected to Theta Terminal v3")

        except requests.exceptions.ConnectionError:
            logger.error("✗ Cannot connect to Theta Terminal")
            logger.error(f"Make sure it's running: java -jar ThetaTerminal.jar {THETA_USERNAME} {THETA_PASSWORD}")
            raise ThetaConnectionError(
                "Cannot connect to Theta Terminal. "
                f"Start it with: java -jar ThetaTerminal.jar {THETA_USERNAME} {THETA_PASSWORD}"
            )

    @retry_with_exponential_backoff(max_retries=3)
    @rate_limit(calls_per_minute=RATE_LIMIT_CALLS_PER_MINUTE)
    def make_request(
        self,
        endpoint: str,
        params: dict,
        timeout: int = REQUEST_TIMEOUT
    ) -> requests.Response:
        """
        Make API request with error handling.

        Args:
            endpoint: API endpoint path
            params: Query parameters
            timeout: Request timeout in seconds

        Returns:
            Response object

        Raises:
            ThetaConnectionError: Cannot connect to Terminal
            ThetaRateLimitError: Rate limit exceeded
            ThetaDataNotAvailable: Data not available
            ThetaDataError: Other API errors
        """
        url = f"{self.base_url}{endpoint}"

        response = self.session.get(url, params=params, timeout=timeout)

        # Handle different status codes
        if response.status_code == 200:
            return response

        elif response.status_code == 429:
            retry_after = response.headers.get('Retry-After', 60)
            raise ThetaRateLimitError(
                f"Rate limit exceeded. Retry after {retry_after}s"
            )

        elif response.status_code == 404:
            raise ThetaDataNotAvailable(
                "Data not available for requested parameters"
            )

        elif response.status_code >= 500:
            raise ThetaDataError(f"Server error: {response.status_code}")

        else:
            raise ThetaDataError(
                f"API error {response.status_code}: {response.text}"
            )

    def get_expirations(self, root: str = SYMBOL) -> List[datetime]:
        """
        Get available option expirations.

        Args:
            root: Stock symbol

        Returns:
            List of expiration dates
        """
        try:
            response = self.make_request(
                endpoint="/v3/list/expirations",
                params={'root': root},
                timeout=10
            )

            data = response.json()
            expirations = data.get('response', [])

            # Convert to datetime objects
            exp_dates = [
                datetime.strptime(str(exp), '%Y%m%d')
                for exp in expirations
            ]

            return sorted(exp_dates)

        except Exception as e:
            logger.error(f"Failed to get expirations: {e}")
            return []

    def get_eod_quotes(
        self,
        root: str,
        expiration: str,
        date: str
    ) -> Optional[pd.DataFrame]:
        """
        Get end-of-day quotes for all strikes of a given expiration.

        Args:
            root: Stock symbol (e.g., 'SPY')
            expiration: Expiration date in YYYYMMDD format
            date: Trade date in YYYYMMDD format

        Returns:
            DataFrame with quote data or None if not available
        """
        try:
            response = self.make_request(
                endpoint="/v3/history/option/eod",
                params={
                    'root': root,
                    'exp': expiration,
                    'start_date': date,
                    'end_date': date,
                    'format': 'json'  # v3 uses 'format' instead of 'use_csv'
                },
                timeout=REQUEST_TIMEOUT
            )

            data = response.json()

            if not data.get('response'):
                return None

            # Parse contracts
            all_contracts = []
            for contract_data in data['response']:
                contract = contract_data['contract']
                ticks = contract_data.get('ticks', [])

                if not ticks:
                    continue

                # EOD format: [ms_of_day, open, high, low, close, volume, count, date]
                df = pd.DataFrame(ticks, columns=[
                    'ms_of_day', 'open', 'high', 'low', 'close', 'volume', 'count', 'date'
                ])

                # Add contract information
                df['strike'] = contract['strike'] / 1000.0  # Convert from millistrikes
                df['right'] = contract['right']  # 'C' or 'P'
                df['expiration'] = contract['expiration']

                all_contracts.append(df)

            if not all_contracts:
                return None

            return pd.concat(all_contracts, ignore_index=True)

        except ThetaDataNotAvailable:
            return None

        except Exception as e:
            logger.warning(f"Failed to get EOD quotes for {root} exp={expiration} date={date}: {e}")
            return None

    def get_eod_greeks(
        self,
        root: str,
        expiration: str,
        date: str
    ) -> Optional[pd.DataFrame]:
        """
        Get end-of-day Greeks for all strikes of a given expiration.

        Args:
            root: Stock symbol
            expiration: Expiration date in YYYYMMDD format
            date: Trade date in YYYYMMDD format

        Returns:
            DataFrame with Greeks data or None if not available
        """
        try:
            response = self.make_request(
                endpoint="/v3/history/option/greeks_eod",
                params={
                    'root': root,
                    'exp': expiration,
                    'start_date': date,
                    'end_date': date,
                    'format': 'json'  # v3 uses 'format' instead of 'use_csv'
                },
                timeout=REQUEST_TIMEOUT
            )

            data = response.json()

            if not data.get('response'):
                return None

            # Parse contracts
            all_contracts = []
            for contract_data in data['response']:
                contract = contract_data['contract']
                ticks = contract_data.get('ticks', [])

                if not ticks:
                    continue

                # Greeks EOD format: [ms_of_day, open_bid, open_ask, close_bid, close_ask,
                #                     delta, gamma, theta, vega, rho, epsilon, lambda,
                #                     implied_vol, open_interest, date]
                df = pd.DataFrame(ticks, columns=[
                    'ms_of_day', 'open_bid', 'open_ask', 'close_bid', 'close_ask',
                    'delta', 'gamma', 'theta', 'vega', 'rho', 'epsilon', 'lambda',
                    'implied_vol', 'open_interest', 'date'
                ])

                # Add contract information
                df['strike'] = contract['strike'] / 1000.0
                df['right'] = contract['right']
                df['expiration'] = contract['expiration']

                # Adjust vega and rho (they come in basis points)
                df['vega'] = df['vega'] / 100.0
                df['rho'] = df['rho'] / 100.0

                all_contracts.append(df)

            if not all_contracts:
                return None

            return pd.concat(all_contracts, ignore_index=True)

        except ThetaDataNotAvailable:
            return None

        except Exception as e:
            logger.warning(f"Failed to get EOD Greeks for {root} exp={expiration} date={date}: {e}")
            return None

# ============================================================================
# DATA PROCESSOR
# ============================================================================

class DataProcessor:
    """Process and merge options data."""

    @staticmethod
    def merge_quotes_and_greeks(
        quotes_df: pd.DataFrame,
        greeks_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Merge quotes and Greeks DataFrames.

        Args:
            quotes_df: DataFrame with quote data
            greeks_df: DataFrame with Greeks data

        Returns:
            Merged DataFrame
        """
        if quotes_df.empty or greeks_df.empty:
            return pd.DataFrame()

        # Merge on strike, right (call/put), expiration
        merged = quotes_df.merge(
            greeks_df,
            on=['strike', 'right', 'expiration', 'date'],
            how='inner',
            suffixes=('_quote', '_greek')
        )

        return merged

    @staticmethod
    def format_output(df: pd.DataFrame, trade_date: datetime) -> pd.DataFrame:
        """
        Format DataFrame to match required output schema.

        Required columns:
        date, expiration, strike, type, bid, ask, volume, open_interest, iv, delta, gamma, theta, vega

        Args:
            df: Merged DataFrame
            trade_date: Trading date

        Returns:
            Formatted DataFrame
        """
        if df.empty:
            return pd.DataFrame()

        # Create output DataFrame
        output = pd.DataFrame()

        # Date and contract info
        output['date'] = trade_date.strftime('%Y-%m-%d')
        output['expiration'] = pd.to_datetime(df['expiration'], format='%Y%m%d').dt.strftime('%Y-%m-%d')
        output['strike'] = df['strike']
        output['type'] = df['right'].str.lower().replace({'c': 'call', 'p': 'put'})

        # Prices (use close prices from EOD data)
        output['bid'] = df['close_bid']
        output['ask'] = df['close_ask']

        # Volume and open interest
        output['volume'] = df['volume']
        output['open_interest'] = df['open_interest']

        # Greeks
        output['iv'] = df['implied_vol']
        output['delta'] = df['delta']
        output['gamma'] = df['gamma']
        output['theta'] = df['theta']
        output['vega'] = df['vega']

        return output

    @staticmethod
    def validate_data(df: pd.DataFrame) -> Tuple[bool, List[str]]:
        """
        Validate data quality.

        Args:
            df: DataFrame to validate

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []

        if df.empty:
            issues.append("DataFrame is empty")
            return False, issues

        # Check for required columns
        required_cols = ['date', 'expiration', 'strike', 'type', 'bid', 'ask',
                        'volume', 'open_interest', 'iv', 'delta', 'gamma', 'theta', 'vega']

        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            issues.append(f"Missing columns: {missing_cols}")

        # Check for negative prices
        if (df['bid'] < 0).any() or (df['ask'] < 0).any():
            issues.append("Found negative prices")

        # Check bid-ask spread
        if (df['bid'] > df['ask']).any():
            issues.append("Found inverted bid-ask spreads")

        # Check for NaN in critical columns
        critical_cols = ['strike', 'bid', 'ask']
        for col in critical_cols:
            if df[col].isna().any():
                issues.append(f"Found NaN values in {col}")

        # Check strike prices are reasonable
        if (df['strike'] <= 0).any():
            issues.append("Found non-positive strike prices")

        is_valid = len(issues) == 0
        return is_valid, issues

# ============================================================================
# MAIN DOWNLOADER
# ============================================================================

class SPYOptionsDownloader:
    """Main orchestrator for downloading SPY options data."""

    def __init__(
        self,
        start_date: str,
        end_date: str,
        min_dte: int = MIN_DTE,
        max_dte: int = MAX_DTE
    ):
        self.start_date = datetime.strptime(start_date, '%Y-%m-%d')
        self.end_date = datetime.strptime(end_date, '%Y-%m-%d')
        self.min_dte = min_dte
        self.max_dte = max_dte

        self.client = ThetaDataClient()
        self.processor = DataProcessor()
        self.checkpoint = CheckpointManager(CHECKPOINT_FILE)

        self.all_data = []

    def get_trading_days(self) -> List[datetime]:
        """
        Get list of trading days in date range.

        Returns:
            List of datetime objects for trading days
        """
        # Simple approach: all weekdays (excludes weekends but not holidays)
        # For production, use a market calendar library
        current = self.start_date
        trading_days = []

        while current <= self.end_date:
            # Monday=0, Sunday=6
            if current.weekday() < 5:  # Monday to Friday
                trading_days.append(current)
            current += timedelta(days=1)

        return trading_days

    def filter_expirations_by_dte(
        self,
        expirations: List[datetime],
        reference_date: datetime
    ) -> List[datetime]:
        """
        Filter expirations by DTE range.

        Args:
            expirations: List of expiration dates
            reference_date: Reference date for calculating DTE

        Returns:
            Filtered list of expirations
        """
        valid_exps = []
        for exp in expirations:
            dte = (exp - reference_date).days
            if self.min_dte <= dte <= self.max_dte:
                valid_exps.append(exp)

        return valid_exps

    def download_single_date(self, trade_date: datetime) -> Optional[pd.DataFrame]:
        """
        Download options data for a single trading date.

        Args:
            trade_date: Trading date

        Returns:
            DataFrame with all options for that date, or None if no data
        """
        date_str = trade_date.strftime('%Y%m%d')

        # Get available expirations
        expirations = self.client.get_expirations(SYMBOL)
        if not expirations:
            logger.warning(f"No expirations found for {trade_date.strftime('%Y-%m-%d')}")
            return None

        # Filter by DTE
        valid_exps = self.filter_expirations_by_dte(expirations, trade_date)
        if not valid_exps:
            logger.info(f"No expirations in DTE range for {trade_date.strftime('%Y-%m-%d')}")
            return None

        # Download data for each expiration
        date_data = []

        for exp in tqdm(valid_exps, desc=f"  Expirations", leave=False):
            exp_str = exp.strftime('%Y%m%d')
            dte = (exp - trade_date).days

            # Get quotes
            quotes = self.client.get_eod_quotes(SYMBOL, exp_str, date_str)
            if quotes is None:
                continue

            # Get Greeks
            greeks = self.client.get_eod_greeks(SYMBOL, exp_str, date_str)
            if greeks is None:
                continue

            # Merge quotes and Greeks
            merged = self.processor.merge_quotes_and_greeks(quotes, greeks)
            if merged.empty:
                continue

            # Format to output schema
            formatted = self.processor.format_output(merged, trade_date)
            if not formatted.empty:
                date_data.append(formatted)

        if not date_data:
            return None

        # Combine all expirations for this date
        combined = pd.concat(date_data, ignore_index=True)
        return combined

    def download_all(self):
        """Download all data for the date range."""
        logger.info("="*70)
        logger.info(f"SPY Options Data Download")
        logger.info(f"Date Range: {self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')}")
        logger.info(f"DTE Range: {self.min_dte} to {self.max_dte} days")
        logger.info("="*70)

        # Get trading days
        trading_days = self.get_trading_days()
        logger.info(f"Total trading days: {len(trading_days)}")

        # Check for checkpoint
        last_completed = self.checkpoint.get_last_completed_date()
        if last_completed:
            logger.info(f"Resuming from checkpoint: {last_completed}")
            last_date = datetime.strptime(last_completed, '%Y-%m-%d')
            trading_days = [d for d in trading_days if d > last_date]
            logger.info(f"Remaining trading days: {len(trading_days)}")

        # Download data for each date
        failed_dates = []

        with tqdm(total=len(trading_days), desc="Downloading") as pbar:
            for i, trade_date in enumerate(trading_days):
                pbar.set_description(f"Downloading {trade_date.strftime('%Y-%m-%d')}")

                try:
                    # Download data for this date
                    date_data = self.download_single_date(trade_date)

                    if date_data is not None:
                        self.all_data.append(date_data)
                        logger.info(f"✓ {trade_date.strftime('%Y-%m-%d')}: {len(date_data)} rows")
                    else:
                        logger.info(f"○ {trade_date.strftime('%Y-%m-%d')}: No data")

                    # Save checkpoint periodically
                    if (i + 1) % CHECKPOINT_INTERVAL == 0:
                        self.checkpoint.save(
                            trade_date.strftime('%Y-%m-%d'),
                            self.all_data
                        )

                except KeyboardInterrupt:
                    logger.warning("\n⚠ Download interrupted by user")
                    self.checkpoint.save(
                        trade_date.strftime('%Y-%m-%d'),
                        self.all_data
                    )
                    raise

                except Exception as e:
                    logger.error(f"✗ {trade_date.strftime('%Y-%m-%d')}: {e}")
                    failed_dates.append(trade_date)

                pbar.update(1)

        # Report failed dates
        if failed_dates:
            logger.warning(f"\n⚠ Failed to download {len(failed_dates)} dates:")
            for date in failed_dates:
                logger.warning(f"  - {date.strftime('%Y-%m-%d')}")

    def save_to_csv(self, output_file: str):
        """
        Save downloaded data to CSV.

        Args:
            output_file: Output filename
        """
        if not self.all_data:
            logger.error("No data to save!")
            return

        logger.info(f"\nCombining {len(self.all_data)} datasets...")

        # Combine all data
        final_df = pd.concat(self.all_data, ignore_index=True)

        # Validate
        is_valid, issues = self.processor.validate_data(final_df)
        if not is_valid:
            logger.warning("⚠ Data validation issues found:")
            for issue in issues:
                logger.warning(f"  - {issue}")

        # Sort by date, expiration, type, strike
        final_df = final_df.sort_values(
            ['date', 'expiration', 'type', 'strike']
        ).reset_index(drop=True)

        # Save to CSV
        final_df.to_csv(output_file, index=False)

        logger.info("="*70)
        logger.info(f"✓ Successfully saved to {output_file}")
        logger.info(f"  Total rows: {len(final_df):,}")
        logger.info(f"  File size: {Path(output_file).stat().st_size / 1024 / 1024:.2f} MB")
        logger.info(f"  Date range: {final_df['date'].min()} to {final_df['date'].max()}")
        logger.info(f"  Unique dates: {final_df['date'].nunique()}")
        logger.info(f"  Unique expirations: {final_df['expiration'].nunique()}")
        logger.info("="*70)

        # Clear checkpoint
        self.checkpoint.clear()

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main entry point."""
    try:
        # Validate credentials
        if THETA_USERNAME == "your_username_here" or THETA_PASSWORD == "your_password_here":
            logger.error("="*70)
            logger.error("ERROR: Please update THETA_USERNAME and THETA_PASSWORD")
            logger.error("="*70)
            logger.error("Edit the constants at the top of this script:")
            logger.error(f"  THETA_USERNAME = '{THETA_USERNAME}'")
            logger.error(f"  THETA_PASSWORD = '{THETA_PASSWORD}'")
            logger.error("\nFor free tier, use:")
            logger.error("  THETA_USERNAME = 'default'")
            logger.error("  THETA_PASSWORD = 'default'")
            logger.error("="*70)
            return

        # Create downloader
        downloader = SPYOptionsDownloader(
            start_date=START_DATE,
            end_date=END_DATE,
            min_dte=MIN_DTE,
            max_dte=MAX_DTE
        )

        # Download data
        downloader.download_all()

        # Save to CSV
        downloader.save_to_csv(OUTPUT_FILE)

        logger.info("\n✓ Download complete!")

    except ThetaConnectionError as e:
        logger.error("\n" + "="*70)
        logger.error("CONNECTION ERROR")
        logger.error("="*70)
        logger.error(str(e))
        logger.error("\nMake sure Theta Terminal is running:")
        logger.error(f"  java -jar ThetaTerminal.jar {THETA_USERNAME} {THETA_PASSWORD}")
        logger.error("="*70)

    except KeyboardInterrupt:
        logger.info("\n✓ Download saved. Run again to resume from checkpoint.")

    except Exception as e:
        logger.error(f"\n✗ Fatal error: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    main()
