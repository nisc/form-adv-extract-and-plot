#!/usr/bin/env python3
"""Script to plot total regulatory AUM and Headcount data from ADV filing data files.

This script creates various charts and visualizations from ADV filing data including:
- Total and normalized regulatory AUM
- Total and IP headcount metrics
- Combined charts with dual y-axes
- Year-over-year growth calculations
- Per-employee metrics

The script supports multiple firms and can generate different plot types based on configuration.
"""

import glob
import os
import platform
import subprocess
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd  # type: ignore
from matplotlib.ticker import FuncFormatter

# Configuration constants
START_YEAR = 2017  # First year to include in plots
OUTPUT_FILE = "output/plots/adv_plot.png"

# Create output directories if they don't exist
Path("output/plots").mkdir(parents=True, exist_ok=True)

# Plot selection switch - set to True to include each plot
# This allows selective plotting to focus on specific metrics
PLOT_SELECTION = {
    "raum_total": True,  # Total Regulatory AUM
    "raum_normalized": True,  # Normalized Regulatory AUM
    "total_headcount": True,  # Total Headcount
    "ip_headcount": True,  # IP Headcount
    "ip_percentage": True,  # IP Percentage
    "hc_combo": True,  # Combined Headcount Chart (Total + IP + %) - only for single company
    "raum_combo": True,  # Combined RAUM Chart (Total + per IP) - only for single company
    "raum_per_total": True,  # RAUM per Employee
    "raum_per_ip": True,  # RAUM per IP
}


def calculate_annual_averages(current_values, previous_values):
    """Calculate average between current and previous year values.

    This function computes the average of current and previous year values,
    which is useful for calculating per-employee metrics that should use
    average headcount rather than point-in-time values.

    Args:
        current_values: Series of current year values
        previous_values: Series of previous year values

    Returns:
        Series of averages between current and previous year
    """
    return (current_values + previous_values) / 2


def calculate_yoy_growth(values):
    """Calculate year-over-year growth percentage.

    This function computes the percentage change from the previous year,
    which is useful for showing growth trends in the data.

    Args:
        values: Series of values

    Returns:
        Series of Y/Y growth percentages (NaN for first year)
    """
    return ((values - values.shift(1)) / values.shift(1)) * 100


def add_data_labels(ax, years, values, label_format, offset=(0, 10), fontsize=8):
    """Add data labels to a plot.

    This function adds formatted value labels to each data point on a plot,
    making it easier to read exact values without relying on grid lines.

    Args:
        ax: Matplotlib axis
        years: Years data
        values: Values to label
        label_format: Function to format labels
        offset: Text offset (x, y)
        fontsize: Font size for labels
    """
    for x, y in zip(years, values):
        if pd.notna(y):
            ax.annotate(
                label_format(y),
                (x, y),
                textcoords="offset points",
                xytext=offset,
                ha="center",
                fontsize=fontsize,
            )


def add_yoy_growth(ax, years, values, offset=(0, -15), fontsize=7):
    """Add year-over-year growth annotations.

    This function adds growth percentage annotations below data points,
    showing the year-over-year change for each data point.

    Args:
        ax: Matplotlib axis
        years: Years data
        values: Values to calculate growth for
        offset: Text offset (x, y)
        fontsize: Font size for growth labels
    """
    yoy_growth = calculate_yoy_growth(values)
    for i, (x, y, growth) in enumerate(zip(years, values, yoy_growth)):
        if pd.notna(y) and pd.notna(growth) and i > 0:  # Skip first year (no growth)
            growth_text = f"({growth:+.1f}%)"
            ax.annotate(
                growth_text,
                (x, y),
                textcoords="offset points",
                xytext=offset,
                ha="center",
                fontsize=fontsize,
                color="gray",
                alpha=0.8,
            )


def plot_combo_chart(ax, years, primary_data, secondary_data, primary_config, secondary_config, firm_name):
    """Plot a combo chart with dual y-axes.

    This function creates a chart with two y-axes, allowing visualization of
    two different metrics with different scales on the same plot.

    Args:
        ax: Primary matplotlib axis
        years: Years data
        primary_data: Data for primary y-axis
        secondary_data: Data for secondary y-axis
        primary_config: Configuration for primary series
        secondary_config: Configuration for secondary series
        firm_name: Name of the firm

    Returns:
        tuple: (ax2, line1, line2) - secondary axis and both line objects
    """
    # Plot primary data on the main axis
    line1 = ax.plot(years, primary_data, marker="o", label=primary_config["label"], linewidth=2)

    # Create secondary y-axis and plot secondary data
    ax2 = ax.twinx()
    line2 = ax2.plot(
        years,
        secondary_data,
        marker="s",
        label=secondary_config["label"],
        linewidth=2,
        linestyle="--",
        color=secondary_config.get("color", "purple"),
    )

    # Add data labels to both series
    add_data_labels(ax, years, primary_data, primary_config["label_format"])
    add_data_labels(ax2, years, secondary_data, secondary_config["label_format"], offset=(0, -15))

    # Set y-axis labels for both axes
    ax.set_ylabel(primary_config["ylabel"], fontsize=12)
    ax2.set_ylabel(secondary_config["ylabel"], fontsize=12)

    # Adjust secondary y-axis range to reduce overlap with primary axis
    secondary_range = ax2.get_ylim()

    # Scale secondary axis to use a different range that reduces overlap
    secondary_span = secondary_range[1] - secondary_range[0]

    # Use a scaling factor to separate the ranges
    scale_factor = 0.8  # Adjust this to control separation
    new_secondary_min = secondary_range[0] - (secondary_span * scale_factor * 0.1)
    new_secondary_max = secondary_range[1] + (secondary_span * scale_factor * 0.1)

    ax2.set_ylim(new_secondary_min, new_secondary_max)

    return ax2, line1[0], line2[0]


def load_and_plot_data(start_year: int = START_YEAR):
    """Load AUM and Headcount data from CSV files and create plots.

    This is the main function that orchestrates the entire plotting process:
    1. Loads data from CSV files generated by adv_extract.py
    2. Processes and calculates various metrics
    3. Creates plots based on the PLOT_SELECTION configuration
    4. Saves and displays the results

    Args:
        start_year: First year to include in the plots
    """
    # Get all CSV files from output/csvs directory
    output_dir = "output/csvs"
    csv_files = sorted(glob.glob(os.path.join(output_dir, "adv_data_*.csv")))

    if not csv_files:
        print("No CSV files found in output/csvs directory")
        return

    # Create figure with subplots based on selection
    enabled_plots = [name for name, enabled in PLOT_SELECTION.items() if enabled]

    # Count companies to determine if combo charts should be included
    company_count = len(csv_files)
    if company_count > 1:
        # Only show non-combo charts for multiple firms
        enabled_plots = [name for name in enabled_plots if name not in ["hc_combo", "raum_combo"]]
        print("Note: Only non-combo charts are shown when more than one firm is selected.")
    else:
        # For a single firm, only show combo charts (ignore non-combo charts)
        enabled_plots = [name for name in enabled_plots if name in ["hc_combo", "raum_combo"]]
        print("Note: Only combo charts are shown when a single firm is selected.")

    num_plots = len(enabled_plots)

    if num_plots == 0:
        print("No plots selected in PLOT_SELECTION")
        return

    # Ensure minimum height for readability and adjust margins based on number of plots
    min_height = 5
    plot_height = max(3.5, min_height / num_plots)

    # Adjust margins based on number of plots
    if num_plots <= 2:
        # More generous margins for fewer plots
        gridspec_kw = {"hspace": 0.5, "top": 0.92, "bottom": 0.12, "left": 0.12, "right": 0.92}
    else:
        # Standard margins for more plots
        gridspec_kw = {"hspace": 0.4, "top": 0.96, "bottom": 0.06, "left": 0.12, "right": 0.92}

    # Create subplots with appropriate sizing
    _, axes = plt.subplots(num_plots, 1, figsize=(11.52, plot_height * num_plots), gridspec_kw=gridspec_kw)

    # Ensure axes is always a list for consistent processing
    if num_plots == 1:
        axes = [axes]

    # Create mapping of plot names to axes for easy access
    plot_axes = dict(zip(enabled_plots, axes))

    # Track all years to ensure consistent x-axis across all plots
    all_years = set()

    # Process each file (each file represents one company)
    for file_path in csv_files:
        # Extract firm name from filename for labeling
        firm_name = os.path.basename(file_path).split("_")[2]

        # Read CSV file and prepare data
        df = pd.read_csv(file_path)

        # Sort by fiscal year for consistent processing
        df = df.sort_values("Fiscal Year")

        # Convert Fiscal Year to integer for proper numeric operations
        df["Fiscal Year"] = df["Fiscal Year"].astype(int)

        # Filter data to start from specified year
        mask = df["Fiscal Year"] >= start_year
        years = df.loc[mask, "Fiscal Year"]

        if years.empty:
            continue

        # Add years to the set of all years for consistent x-axis
        all_years.update(years)

        # Extract key metrics for calculations
        ip_headcount = df.loc[mask, "5B1"]  # Investment Professional headcount
        total_headcount = df.loc[mask, "5A"]  # Total headcount
        aum_values = df.loc[mask, "5F2a"]  # Regulatory AUM

        # Calculate averages between current and previous year for per-employee metrics
        # This provides more accurate metrics than using point-in-time values
        prev_aum = aum_values.shift(1)
        prev_total_headcount = total_headcount.shift(1)
        prev_ip_headcount = ip_headcount.shift(1)
        avg_aum = calculate_annual_averages(aum_values, prev_aum)
        avg_total_headcount = calculate_annual_averages(total_headcount, prev_total_headcount)
        avg_ip_headcount = calculate_annual_averages(ip_headcount, prev_ip_headcount)

        # Define plot configurations with lambda functions to capture current scope variables
        # This avoids issues with cell variable scope in loops
        plot_configs = {
            "raum_total": {
                "data_func": lambda years=years, aum_values=aum_values: (years, aum_values),
                "label_format": lambda y: f"${y/1e9:.1f}B" if y >= 1e9 else f"${y/1e6:.1f}M",
                "title": "Total Regulatory AUM",
                "ylabel": "Total RAUM ($)",
                "formatter": lambda ax: ax.yaxis.set_major_formatter(
                    FuncFormatter(lambda x, p: f"${x/1e9:.1f}B" if x >= 1e9 else f"${x/1e6:.0f}M")
                ),  # type: ignore
            },
            "raum_normalized": {
                "data_func": lambda df=df, start_year=start_year: _get_aum_data(df, start_year),
                "label_format": lambda y: f"{int(y):,}",
                "title": "Normalized Regulatory AUM (First Year = 100)",
                "ylabel": "Normalized RAUM (First Year = 100)",
                "formatter": None,
            },
            "total_headcount": {
                "data_func": lambda years=years, total_headcount=total_headcount: (years, total_headcount),
                "label_format": lambda y: f"{int(y):,}",
                "title": "Total Form ADV Headcount",
                "ylabel": "Number of Employees",
                "formatter": None,
            },
            "ip_headcount": {
                "data_func": lambda years=years, ip_headcount=ip_headcount: (years, ip_headcount),
                "label_format": lambda y: f"{int(y):,}",
                "title": "Form ADV IP Headcount",
                "ylabel": "Number of Employees",
                "formatter": None,
            },
            "ip_percentage": {
                "data_func": lambda years=years, ip_headcount=ip_headcount, total_headcount=total_headcount: (
                    years,
                    (ip_headcount / total_headcount) * 100,
                ),
                "label_format": lambda y: f"{y:.1f}%",
                "title": "ADV IP Headcount Percentage",
                "ylabel": "IP Percentage (%)",
                "formatter": None,
            },
            "hc_combo": {
                "data_func": lambda years=years, total_headcount=total_headcount, ip_headcount=ip_headcount: (
                    years,
                    total_headcount,
                    ip_headcount,
                    (ip_headcount / total_headcount) * 100,
                ),
                "label_format": lambda y: f"{int(y):,}",
                "title": "ADV Headcount Chart",
                "ylabel": "Number of Employees",
                "formatter": None,
            },
            "raum_combo": {
                "data_func": lambda: get_raum_combo_data(years, aum_values, avg_aum, avg_ip_headcount),
                "label_format": lambda y: f"${y/1e9:.1f}B" if y >= 1e9 else f"${y/1e6:.1f}M",
                "title": "Regulatory AUM Chart",
                "ylabel": "RAUM ($)",
                "formatter": (
                    lambda ax: ax.yaxis.set_major_formatter(
                        FuncFormatter(lambda x, p: (f"${x/1e9:.1f}B" if x >= 1e9 else f"${x/1e6:.0f}M"))
                    )
                ),
            },
            "raum_per_total": {
                "data_func": lambda years=years, avg_aum=avg_aum, avg_total_headcount=avg_total_headcount: (
                    years,
                    avg_aum / avg_total_headcount,
                ),
                "label_format": lambda y: f"${y/1e6:.1f}M",
                "title": "Avg. Regulatory AUM per Employee",
                "ylabel": "Avg. RAUM per Avg. Employee ($)",
                "formatter": lambda ax: ax.yaxis.set_major_formatter(
                    FuncFormatter(lambda x, p: f"${x/1e6:.0f}M")
                ),  # type: ignore
            },
            "raum_per_ip": {
                "data_func": lambda years=years, avg_aum=avg_aum, avg_ip_headcount=avg_ip_headcount: (
                    years,
                    avg_aum / avg_ip_headcount,
                ),
                "label_format": lambda y: f"${y/1e6:.1f}M",
                "title": "Avg. Regulatory AUM per IP",
                "ylabel": "Avg. RAUM per Avg. IP ($)",
                "formatter": lambda ax: ax.yaxis.set_major_formatter(
                    FuncFormatter(lambda x, p: f"${x/1e6:.0f}M")
                ),  # type: ignore
            },
        }

        # Plot data for each enabled plot type
        for plot_name in enabled_plots:
            config = plot_configs[plot_name]
            ax = plot_axes[plot_name]

            # Handle special cases that require custom plotting logic
            if plot_name == "raum_normalized":
                plot_data = config["data_func"]()  # type: ignore
                if plot_data is None:  # No AUM data available
                    continue
                plot_years, plot_values = plot_data
                ax.plot(plot_years, plot_values, marker="o", label=firm_name, linewidth=2)

                # Add data labels
                add_data_labels(ax, plot_years, plot_values, config["label_format"])

                # Add Y/Y growth for single company charts
                if company_count == 1:
                    add_yoy_growth(ax, plot_years, plot_values)

                # Set custom title with firm name
                if company_count == 1:
                    ax.set_title(f"{config['title']} ({firm_name})", fontsize=14, pad=15)
                else:
                    ax.set_title(config["title"], fontsize=14, pad=15)

            elif plot_name == "hc_combo":
                # Special handling for combined headcount chart with dual y-axes
                plot_data = config["data_func"]()  # type: ignore
                if plot_data is None:
                    continue
                plot_years, total_hc, ip_hc, ip_percentage = plot_data

                # Define configurations for the combo chart
                primary_config = {
                    "label": "Total HC",
                    "label_format": lambda y: f"{int(y):,}",
                    "ylabel": "Number of Employees",
                }
                secondary_config = {
                    "label": "IP share (%)",
                    "label_format": lambda y: f"{y:.1f}%",
                    "ylabel": "IP Percentage (%)",
                    "color": "green",
                }

                # Plot the combo chart with dual y-axes
                ax2, line1, line2 = plot_combo_chart(
                    ax, plot_years, total_hc, ip_percentage, primary_config, secondary_config, firm_name
                )

                # Add IP headcount on primary axis
                line3 = ax.plot(plot_years, ip_hc, marker="s", label="IP HC", linewidth=2, color="green")
                add_data_labels(ax, plot_years, ip_hc, lambda y: f"{int(y):,}", offset=(0, -15))

                # Add Y/Y growth for total headcount in combo chart
                if company_count == 1:
                    add_yoy_growth(ax, plot_years, total_hc, offset=(0, -20))

                # Create legend with all three series in specified order
                lines = [line1, line3[0], line2]
                labels = [line.get_label() for line in lines]
                ax.legend(lines, labels, fontsize=10)

                # Set custom title with firm name
                ax.set_title(f"ADV Headcount Chart ({firm_name})", fontsize=14, pad=15)

            elif plot_name == "raum_combo":
                # Special handling for combined RAUM chart with dual y-axes
                plot_data = config["data_func"]()  # type: ignore
                if plot_data is None:
                    continue
                plot_years, aum_values, raum_per_ip = plot_data

                # Define configurations for the combo chart
                primary_config = {
                    "label": "RAUM",
                    "label_format": config["label_format"],
                    "ylabel": "RAUM ($)",
                }
                secondary_config = {
                    "label": "Avg. RAUM/IP",
                    "label_format": lambda y: f"{y/1e6:.1f}M",
                    "ylabel": "RAUM per Avg. IP ($)",
                    "color": "purple",
                }

                # Plot the combo chart with dual y-axes
                ax2, line1, line2 = plot_combo_chart(
                    ax, plot_years, aum_values, raum_per_ip, primary_config, secondary_config, firm_name
                )

                # Add Y/Y growth for AUM
                if company_count == 1:
                    add_yoy_growth(ax, plot_years, aum_values)

                # Create legend with both series
                lines = [line1, line2]
                labels = [line.get_label() for line in lines]
                ax.legend(lines, labels, fontsize=10)

                # Set custom title with firm name
                ax.set_title(f"Regulatory AUM Chart ({firm_name})", fontsize=14, pad=15)

            else:
                # Standard plotting for other charts
                plot_years, plot_values = config["data_func"]()  # type: ignore
                ax.plot(plot_years, plot_values, marker="o", label=firm_name, linewidth=2)

                # Add data labels
                add_data_labels(ax, plot_years, plot_values, config["label_format"])

                # Add Y/Y growth for single company charts
                if company_count == 1:
                    add_yoy_growth(ax, plot_years, plot_values)

                # Set custom title with firm name
                if company_count == 1:
                    ax.set_title(f"{config['title']} ({firm_name})", fontsize=14, pad=15)
                else:
                    ax.set_title(config["title"], fontsize=14, pad=15)

    # Handle case where no data was found
    if not all_years:
        print(f"No data found from {start_year} onwards for any firm")
        return

    # Configure all axes with consistent formatting
    years_range = range(start_year, max(all_years) + 1)
    for plot_name, ax in plot_axes.items():
        config = plot_configs[plot_name]

        # Set common properties for all plots
        ax.set_xticks(years_range)
        ax.tick_params(axis="x", rotation=45)
        ax.grid(True, linestyle="--", alpha=0.7)
        # Only set legend for non-combo charts (combo charts handle their own legends)
        if plot_name not in ["hc_combo", "raum_combo"]:
            ax.legend(fontsize=10)
        ax.set_xlim(start_year - 0.2, max(all_years) + 0.2)

        # Set titles and labels
        # Only set title here if it hasn't been set yet (for multi-company charts)
        if not ax.get_title():
            ax.set_title(config["title"], fontsize=14, pad=15)
        ax.set_ylabel(config["ylabel"], fontsize=12)

        # Apply custom formatter if specified
        if config["formatter"]:
            config["formatter"](ax)  # type: ignore

    # Adjust layout to prevent label cutoff
    plt.tight_layout()

    # Save the plot with high resolution and open in default OS viewer
    plt.savefig(OUTPUT_FILE, dpi=300, bbox_inches="tight")
    plt.close()  # Close the plot to free memory

    # Open the image using the appropriate command for the OS
    if platform.system() == "Darwin":  # macOS
        subprocess.run(["open", OUTPUT_FILE], check=False)
    elif platform.system() == "Windows":
        subprocess.run(["start", OUTPUT_FILE], shell=True, check=False)
    else:  # Linux
        subprocess.run(["xdg-open", OUTPUT_FILE], check=False)


def _get_aum_data(df, start_year):
    """Helper function to get AUM data for normalized plot.

    This function calculates normalized AUM values where the first non-zero
    year is set to 100, allowing for easy comparison of growth trends.

    Args:
        df: DataFrame with AUM data
        start_year: First year to consider

    Returns:
        Tuple of (years, normalized_values) or None if no data available
    """
    # Find first non-zero AUM value from start_year onwards
    non_zero_mask = (df["Fiscal Year"] >= start_year) & (df["5F2a"] > 0)
    if not any(non_zero_mask):
        return None

    # Use first non-zero AUM as baseline (100)
    base_aum = df.loc[non_zero_mask, "5F2a"].iloc[0]
    base_year = df.loc[non_zero_mask, "Fiscal Year"].iloc[0]

    # Only plot AUM data from the first non-zero year onwards
    aum_mask = df["Fiscal Year"] >= base_year
    aum_years = df.loc[aum_mask, "Fiscal Year"]
    aum_values = (df.loc[aum_mask, "5F2a"] / base_aum) * 100

    return aum_years, aum_values


def raum_combo_data_func(years, aum_values, avg_aum, avg_ip_headcount):
    """Helper function for raum_combo plot data calculation."""
    return years, aum_values, avg_aum / avg_ip_headcount


def get_raum_combo_data(years, aum_values, avg_aum, avg_ip_headcount):
    """Helper function for raum_combo plot data.

    This function prepares data for the combined RAUM chart, calculating
    both total AUM and AUM per investment professional.

    Args:
        years: Years data
        aum_values: Total AUM values
        avg_aum: Average AUM values
        avg_ip_headcount: Average IP headcount values

    Returns:
        Tuple of (years, aum_values, raum_per_ip)
    """
    return raum_combo_data_func(years, aum_values, avg_aum, avg_ip_headcount)


if __name__ == "__main__":
    load_and_plot_data()
