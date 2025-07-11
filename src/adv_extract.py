#!/usr/bin/env python3
"""Script to extract specific column values from ADV filing data files.

This script processes ADV filing data CSV files to extract specific metrics for
configured firms. It supports multiple matching strategies (SEC ID, CRD ID, or both)
and can handle data overwrites and default values for missing fiscal years.
"""

import glob
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd  # type: ignore
import yaml

from adv_downloader import ADVDownloader

# Define input and output directories
INPUT_DIR = Path("input")
CSV_OUTPUT_DIR = Path("output/csvs")

# Create output directories if they don't exist
CSV_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Global cache for configuration to avoid repeated loading
_CONFIG_CACHE = None
_ALL_FIRMS_CACHE = None


def load_configuration():
    """Load configuration from YAML files."""
    global _CONFIG_CACHE, _ALL_FIRMS_CACHE

    # Return cached configuration if already loaded
    if _CONFIG_CACHE is not None and _ALL_FIRMS_CACHE is not None:
        return _CONFIG_CACHE, _ALL_FIRMS_CACHE

    # Load configuration from YAML file
    with open("adv_extract_settings.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Load firms and overwrites from main firms file
    with open("adv_extract_firms.yaml", "r", encoding="utf-8") as f:
        firms_config = yaml.safe_load(f)
        all_firms = firms_config["FIRMS"]
        # Load OVERWRITES if present
        if "OVERWRITES" in firms_config:
            config["OVERWRITES"] = firms_config["OVERWRITES"]

    # Load additional firms from adv_extract_firms-*.yaml files
    for firm_file in glob.glob("adv_extract_firms-*.yaml"):
        try:
            with open(firm_file, "r", encoding="utf-8") as f:
                if additional_firms := yaml.safe_load(f):
                    if "FIRMS" in additional_firms:
                        all_firms.extend(additional_firms["FIRMS"])
                        print(f"Loaded additional firms from {firm_file}")
        except Exception as e:
            print(f"Warning: Could not load {firm_file}: {e}")

    # Cache the results
    _CONFIG_CACHE = config
    _ALL_FIRMS_CACHE = all_firms

    return config, all_firms


def check_and_download_files() -> list[Path]:
    """Check if input files exist, download if not."""
    csv_files = list(INPUT_DIR.rglob("IA_ADV_Base_*.csv"))

    if not csv_files:
        # Load configuration to get download URLs
        config, _ = load_configuration()

        # Use the consolidated downloader with config
        downloader = ADVDownloader(INPUT_DIR, config)
        if not downloader.download_and_extract_all_files(config.get("DOWNLOAD_URLS", {})):
            sys.exit(1)

        # Check again after download attempt
        csv_files = list(INPUT_DIR.rglob("IA_ADV_Base_*.csv"))
        if not csv_files:
            print(f"Still no CSV files found after download. Please check the {INPUT_DIR} directory.")
            sys.exit(1)

    print(f"Found {len(csv_files)} ADV filing data CSV files.")
    return csv_files


def process_files(
    sec_id: str, crd_id: str, default_values: Optional[Dict[str, Dict[str, Any]]] = None
) -> pd.DataFrame:
    """Process all CSV files and return a DataFrame with the results.

    This function searches through all ADV filing data files to find records
    matching the specified SEC ID and/or CRD ID, extracts the target columns,
    and organizes the data by fiscal year.

    Args:
        sec_id: SEC ID to search for
        crd_id: CRD ID to search for
        default_values: Dictionary of default values by fiscal year

    Returns:
        DataFrame with filing data, indexed by fiscal year
    """
    # Load configuration
    config, all_firms = load_configuration()

    # Extract configuration values
    SEC_ID_COLUMN = config["SEC_ID_COLUMN"]
    CRD_ID_COLUMN = config["CRD_ID_COLUMN"]
    MATCHING_STRATEGY = config["MATCHING_STRATEGY"]
    DATE_COLUMNS = config["DATE_COLUMNS"]
    TARGET_COLUMNS = config["TARGET_COLUMNS"]
    OVERWRITES = config["OVERWRITES"]

    # Combine date columns with target columns for processing
    ALL_COLUMNS = DATE_COLUMNS + TARGET_COLUMNS

    # Pre-compile the file pattern
    FILE_PATTERN = "IA_ADV_Base_*.csv"

    # Get all CSV files recursively from input directory
    csv_files = list(INPUT_DIR.rglob(FILE_PATTERN))

    if not csv_files:
        print(f"No CSV files found in {INPUT_DIR} or its subdirectories")
        return pd.DataFrame()

    # Process all files and collect data
    all_data = []
    for file_path in sorted(csv_files):
        try:
            # Read only needed columns for better performance and memory usage
            df = pd.read_csv(
                file_path,
                encoding="latin1",
                low_memory=False,
                usecols=ALL_COLUMNS + [SEC_ID_COLUMN, CRD_ID_COLUMN, "FilingID"],
            )

            # Convert target columns to integers in one operation
            # This ensures consistent data types and handles missing values
            df[TARGET_COLUMNS] = df[TARGET_COLUMNS].apply(pd.to_numeric, errors="coerce").astype("Int64")

            # Find matching row based on matching strategy
            # Different strategies allow for flexible firm identification
            mask = {
                "SEC_ONLY": df[SEC_ID_COLUMN] == sec_id,
                "CRD_ONLY": df[CRD_ID_COLUMN] == crd_id,
                "BOTH": (df[SEC_ID_COLUMN] == sec_id) & (df[CRD_ID_COLUMN] == crd_id),
            }[MATCHING_STRATEGY]

            if not mask.any():
                continue

            # Handle multiple matches by selecting the most recent filing
            if mask.sum() > 1:
                matches = df[mask]
                # Get all filing IDs for reporting
                filing_ids = [str(row.get("FilingID", "N/A")) for _, row in matches.iterrows()]
                # Take the last filing instead of skipping (most recent)
                row = matches.iloc[-1].to_dict()  # Convert to dictionary to avoid SettingWithCopyWarning
                selected_id = str(row.get("FilingID", "N/A"))
                print(
                    f"Multiple FilingIDs in {file_path.name}: {', '.join(filing_ids)} (using {selected_id})"
                )
            else:
                # Get the matching row and select target columns
                row = df[mask].iloc[0].to_dict()  # Convert to dictionary to avoid SettingWithCopyWarning

            # Apply any overwrites for this filing
            # This allows manual correction of specific filing data
            filing_id = str(row.get("FilingID", "N/A"))  # Convert to string to ensure matching
            if filing_id in OVERWRITES:
                for col, value in OVERWRITES[filing_id].items():
                    if col in row:
                        print(f"\nOverwriting {col} from {row[col]} to {value}\n")
                        row[col] = value

            # Extract data for all required columns, using pd.NA for missing values
            data = {col: row[col] if col in row else pd.NA for col in ALL_COLUMNS}
            all_data.append(data)

        except Exception:  # pylint: disable=W0718
            # Skip files that can't be processed and continue with others
            continue

    # Handle case where no data was found
    if not all_data:
        strategy_str = {"SEC_ONLY": "SEC ID", "CRD_ONLY": "CRD ID", "BOTH": "SEC ID and CRD ID"}[
            MATCHING_STRATEGY
        ]
        print(f"No data found for {strategy_str} in any files")
        if not default_values:
            return pd.DataFrame()

        # Create DataFrame from default values when no actual data is available
        default_data = []
        for fiscal_year, values in default_values.items():
            data = {}
            # Initialize with None instead of pd.NA to avoid type issues
            for col in ALL_COLUMNS:
                data[col] = None
            data.update(values)
            # Convert fiscal year string to a proper date for Execution Date column
            if "Execution Date" in ALL_COLUMNS:
                try:
                    # Assume fiscal year is a string like "2023" and convert to date
                    data["Execution Date"] = pd.to_datetime(f"{fiscal_year}-01-01")
                except (ValueError, TypeError):
                    data["Execution Date"] = None
            default_data.append(data)

        df = pd.DataFrame(default_data)
        df = df.set_index("Execution Date")
        print(f"Using default values for fiscal years: {list(default_values.keys())}")
        return df

    # Convert collected data to DataFrame and set index
    df = pd.DataFrame(all_data)

    # Convert execution dates to fiscal years
    # For ADV filings, fiscal year is typically the year before the execution date
    execution_dates = pd.to_datetime(df["Execution Date"], errors="coerce")
    # For all dates, fiscal year is the previous year
    fiscal_years = []
    for date in execution_dates:
        if pd.notna(date):
            fiscal_years.append(date.year - 1)
        else:
            fiscal_years.append(None)

    # Set the index using set_index instead of direct assignment
    df = df.set_index(pd.Index(fiscal_years))

    # Group by fiscal year and keep only the latest filing for each year
    # This handles cases where multiple filings exist for the same fiscal year
    df = df.groupby(df.index).last()

    # For fiscal years with no data but with default values, add them
    # This ensures complete time series even when some years are missing
    if default_values:
        existing_years = set(df.index)
        for fiscal_year in default_values.keys():
            if fiscal_year not in existing_years:
                data = {col: pd.NA for col in ALL_COLUMNS}
                data.update(default_values[fiscal_year])
                # Create a DataFrame for the new row and concatenate
                new_row_df = pd.DataFrame([data], index=[fiscal_year])
                df = pd.concat([df, new_row_df])

    # Sort by fiscal year (ascending) for consistent output
    df = df.sort_index(ascending=True)

    # Rename index to Fiscal Year for clarity
    df.index.name = "Fiscal Year"

    return df


def main():
    """Main function to process files and output results for multiple firms.

    This function orchestrates the entire data extraction process:
    1. Loads configuration and firm definitions
    2. Processes each firm's data using the specified matching strategy
    3. Outputs results to CSV files in the output/csvs directory
    """
    # Load configuration
    config, all_firms = load_configuration()

    # Extract configuration values
    MATCHING_STRATEGY = config["MATCHING_STRATEGY"]

    # Load firms from main firms file
    FIRM_IDS = [(f["name"], f["sec_id"], f["crd_id"], f["default_values"]) for f in all_firms]

    strategy_str = {"SEC_ONLY": "SEC ID", "CRD_ONLY": "CRD ID", "BOTH": "SEC ID and CRD ID"}[
        MATCHING_STRATEGY
    ]
    print(f"\nUsing matching strategy: {strategy_str}")

    # Check and download files if needed (only once at the beginning)
    check_and_download_files()

    # Process each configured firm
    for firm_name, sec_id, crd_id, default_values in FIRM_IDS:
        # Use max year from default_values as most recent year if available, else set to None
        most_recent_year = None
        if default_values:
            try:
                most_recent_year = max(int(y) for y in default_values.keys())
            except Exception:
                pass
        if most_recent_year is not None:
            filename = (
                "adv_data_"
                + str(firm_name)
                + "_"
                + str(sec_id)
                + "_"
                + str(crd_id)
                + "_"
                + str(most_recent_year)
                + ".csv"
            )
            output_file = CSV_OUTPUT_DIR / filename
            if output_file.exists():
                print(f"Skipping {firm_name} (output {output_file.name} already exists)")
                continue

        print(f"\n{'=' * 100}\n\nProcessing {firm_name} (SEC_ID {sec_id} and CRD_ID {crd_id})\n")

        # Process files and get DataFrame
        df = process_files(sec_id, crd_id, default_values)
        if df.empty:
            print(f"No data found for {strategy_str} and no default values provided")
            continue

        # Get the most recent fiscal year from the data for the filename
        most_recent_year = df.index.max()

        # Save to CSV in output/csvs directory with descriptive filename
        output_file = CSV_OUTPUT_DIR / f"adv_data_{firm_name}_{sec_id}_{crd_id}_{most_recent_year}.csv"
        df.to_csv(output_file)
        print(f"\nData written to {output_file}")


if __name__ == "__main__":
    main()
