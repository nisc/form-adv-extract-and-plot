#!/usr/bin/env python3
"""Script to plot total regulatory AUM and Headcount data from ADV filing data files.

This script creates various charts and visualizations from ADV filing data including:
- Total and normalized regulatory AUM
- Total and Investment Professional headcount metrics
- Combined charts with dual y-axes
- Year-over-year growth calculations
- Per-employee metrics

The script supports multiple firms and can generate different plot types based on configuration.
"""

import glob
import os
import platform
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import matplotlib.patheffects as path_effects
import matplotlib.pyplot as plt
import pandas as pd  # type: ignore
from matplotlib.axes import Axes
from matplotlib.ticker import FuncFormatter

# Configuration constants
START_YEAR = 2017  # First year to include in plots
PLOT_FOLDER = "output/plots"  # Output directory for generated plots

# Create output directories if they don't exist
Path(PLOT_FOLDER).mkdir(parents=True, exist_ok=True)

# Plot selection switch - set to True to include each plot
PLOT_SELECTION = {
    "raum_total": True,  # Total Regulatory AUM
    "raum_normalized": True,  # Normalized Regulatory AUM
    "total_hc": True,  # Total Headcount
    "ip_hc": True,  # Investment Professional Headcount
    "ip_percentage": True,  # Investment Professional Share
    "hc_combo": True,  # Single Company Headcount Chart (Total + Investment Professional + % Mix)
    "raum_combo": True,  # Single Company RAUM Chart (Total, per Employee, per Investment Professional)
    "raum_per_total": True,  # RAUM per Employee
    "raum_per_ip": True,  # RAUM per Investment Professional
}

# Plot types that use combo charts (dual y-axes)
COMBO_PLOTS = {"hc_combo", "raum_combo"}


def calculate_annual_averages(current_values: pd.Series, previous_values: pd.Series) -> pd.Series:
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


def calculate_yoy_growth(values: pd.Series) -> pd.Series:
    """Calculate year-over-year growth percentage.

    This function computes the percentage change from the previous year,
    which is useful for showing growth trends in the data.

    Args:
        values: Series of values

    Returns:
        Series of Y/Y growth percentages (NaN for first year)
    """
    return ((values - values.shift(1)) / values.shift(1)) * 100


def add_data_labels(
    ax: Axes,
    years: pd.Series,
    values: pd.Series,
    label_format: Callable,
    offset: Tuple[int, int] = (0, 10),
    fontsize: int = 7,
) -> None:
    """Add data labels to a plot with white outline for readability.

    Always positions labels above the data points.
    """
    for x, y in zip(years, values):
        if pd.notna(y):
            txt = ax.annotate(
                label_format(y),
                (x, y),
                textcoords="offset points",
                xytext=(offset[0], 6),
                ha="center",
                fontsize=fontsize,
                zorder=20,
            )
            txt.set_path_effects(
                [
                    path_effects.Stroke(linewidth=2, foreground="white"),
                    path_effects.Normal(),
                ]
            )


def add_yoy_growth(
    ax: Axes, years: pd.Series, values: pd.Series, offset: Tuple[int, int] = (0, -15), fontsize: int = 6
) -> None:
    """Add year-over-year growth annotations with white outline for readability.

    Always positions growth labels below the data points.
    """
    yoy_growth = calculate_yoy_growth(values)
    for i, (x, y, growth) in enumerate(zip(years, values, yoy_growth)):
        if pd.notna(y) and pd.notna(growth) and i > 0:  # Skip first year (no growth)
            txt = ax.annotate(
                f"({growth:+.1f}%)",
                (x, y),
                textcoords="offset points",
                xytext=(offset[0], -11),
                ha="center",
                fontsize=fontsize,
                color="gray",
                alpha=0.8,
                zorder=20,
            )
            txt.set_path_effects(
                [
                    path_effects.Stroke(linewidth=2, foreground="white"),
                    path_effects.Normal(),
                ]
            )


def plot_combo_chart(
    ax: Axes,
    years: pd.Series,
    primary_data: pd.Series,
    secondary_data: pd.Series,
    primary_config: Dict[str, Any],
    secondary_config: Dict[str, Any],
    secondary_years: Optional[pd.Series] = None,
) -> Tuple[Axes, Any, Any]:
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
        secondary_years: Optional different years for secondary data (e.g., mid-year points)

    Returns:
        tuple: (ax2, line1, line2) - secondary axis and both line objects
    """
    # Plot primary data on the main axis
    line1 = ax.plot(
        years, primary_data, marker="o", label=primary_config["label"], linewidth=2, markersize=6, zorder=5
    )

    # Create secondary y-axis and plot secondary data
    ax2 = ax.twinx()
    secondary_x = secondary_years if secondary_years is not None else years
    line2 = ax2.plot(
        secondary_x,
        secondary_data,
        marker="s",
        label=secondary_config["label"],
        linewidth=2,
        linestyle="--",
        color=secondary_config.get("color", "purple"),
        markersize=6,
        zorder=5,
    )

    # Add data labels to primary series only
    add_data_labels(ax, years, primary_data, primary_config["label_format"])

    # Adjust secondary y-axis range to reduce overlap
    secondary_range = ax2.get_ylim()
    secondary_span = secondary_range[1] - secondary_range[0]
    scale_factor = 0.8
    new_secondary_min = secondary_range[0] - (secondary_span * scale_factor * 0.1)
    new_secondary_max = secondary_range[1] + (secondary_span * scale_factor * 0.1)
    ax2.set_ylim(new_secondary_min, new_secondary_max)

    # Hide tick labels and ticks on secondary y-axis
    ax2.tick_params(axis="y", labelright=False, right=False)

    return ax2, line1[0], line2[0]


def get_user_firm_selection(csv_files: List[str]) -> List[str]:
    """Prompt user to select which firms to plot when multiple CSV files are found.

    Args:
        csv_files: List of CSV file paths

    Returns:
        List of selected CSV file paths
    """
    if len(csv_files) <= 1:
        return csv_files

    print(f"\nFound {len(csv_files)} firm data files:")
    firm_names = []
    for i, file_path in enumerate(csv_files, 1):
        firm_name = os.path.basename(file_path).split("_")[2]
        firm_names.append(firm_name)
        print(f"{i}. {firm_name}")

    print('\nEnter the numbers of firms to plot (e.g. "all" or "2-4, 6, 8-9"):')

    while True:
        try:
            user_input = input("Selection: ").strip()
            if not user_input:
                print("Please enter at least one number.")
                continue

            # Handle "all" selection
            if user_input.lower() == "all":
                selected_indices = list(range(len(csv_files)))
                selected_files = csv_files
                selected_names = firm_names
                print(f"\nSelected firms: {', '.join(selected_names)}")
                return selected_files

            # Parse user input - handle commas, spaces, or mixed separators
            selected_indices = []
            for part in user_input.replace(",", " ").split():
                part = part.strip()
                if not part:
                    continue

                # Handle range format
                if "-" in part:
                    try:
                        start, end = part.split("-", 1)
                        start_idx = int(start.strip())
                        end_idx = int(end.strip())

                        if start_idx > end_idx:
                            print(f"Invalid range: {part}. Start must be <= end.")
                            continue

                        if 1 <= start_idx <= len(csv_files) and 1 <= end_idx <= len(csv_files):
                            # Convert to 0-based indices and include end
                            for idx in range(start_idx - 1, end_idx):
                                if idx not in selected_indices:
                                    selected_indices.append(idx)
                        else:
                            print(
                                f"Invalid range: {part}. Please enter numbers between 1 and {len(csv_files)}."
                            )
                            continue
                    except ValueError:
                        print(f"Invalid range format: '{part}'. Use format like '2-4'.")
                        continue
                else:
                    # Handle single number
                    try:
                        index = int(part)
                        if 1 <= index <= len(csv_files):
                            idx = index - 1  # Convert to 0-based index
                            if idx not in selected_indices:
                                selected_indices.append(idx)
                        else:
                            print(
                                f"Invalid selection: {index}. "
                                f"Please enter numbers between 1 and {len(csv_files)}."
                            )
                            continue
                    except ValueError:
                        print(f"Invalid input: '{part}'. Please enter valid numbers.")
                        continue

            if not selected_indices:
                print("No valid selections made. Please try again.")
                continue

            # Return selected files
            selected_files = [csv_files[i] for i in selected_indices]
            selected_names = [firm_names[i] for i in selected_indices]
            print(f"\nSelected firms: {', '.join(selected_names)}")
            return selected_files

        except KeyboardInterrupt:
            print("\nSelection cancelled.")
            sys.exit(1)
        except Exception as e:
            print(f"Error processing selection: {e}")
            continue


def get_next_plot_filename(base_pattern: str, folder: str) -> str:
    """Find the next available filename with incrementing counter in the given folder.

    Args:
        base_pattern: Filename pattern with {:03d} placeholder for counter
                     (e.g., 'adv_plot_multi_{:03d}.png' or 'adv_plot_Voleon_{:03d}.png')
        folder: Directory to search for existing files

    Returns:
        str: Next available filename path (not overwriting any existing file)
    """
    existing_files = os.listdir(folder)
    regex = re.compile(base_pattern.replace("{:03d}", r"(\d{3})"))
    max_num = 0
    for fname in existing_files:
        m = regex.fullmatch(fname)
        if m:
            try:
                num = int(m.group(1))
                if num > max_num:
                    max_num = num
            except Exception:
                continue
    next_num = max_num + 1
    return os.path.join(folder, base_pattern.format(next_num))


def load_and_plot_data(start_year: int = START_YEAR) -> None:
    """Load AUM and Headcount data from CSV files and create plots.

    This is the main function that orchestrates the entire plotting process:
    1. Loads data from CSV files generated by src/adv_extract.py
    2. Processes and calculates various metrics
    3. Creates plots based on the PLOT_SELECTION configuration
    4. Saves and displays the results

    Args:
        start_year: First year to include in the plots
    """
    # Get all CSV files from output/csvs directory
    output_dir = "output/csvs"
    all_csv_files = sorted(glob.glob(os.path.join(output_dir, "adv_data_*.csv")))

    if not all_csv_files:
        print("No CSV files found in output/csvs directory")
        sys.exit(1)

    # Get user selection for which firms to plot
    csv_files = get_user_firm_selection(all_csv_files)
    company_count = len(csv_files)

    # Determine output filename based on number of firms
    if company_count == 1:
        firm_name = os.path.basename(csv_files[0]).split("_")[2]
        base_pattern = f"adv_plot_{firm_name}_{{:03d}}.png"
        output_file = get_next_plot_filename(base_pattern, PLOT_FOLDER)
    else:
        base_pattern = "adv_plot_multi_{:03d}.png"
        output_file = get_next_plot_filename(base_pattern, PLOT_FOLDER)

    # Create figure with subplots based on selection
    enabled_plots = [name for name, enabled in PLOT_SELECTION.items() if enabled]

    if company_count > 1:
        # Only show non-combo charts for multiple firms
        enabled_plots = [name for name in enabled_plots if name not in COMBO_PLOTS]
        print("Note: Only non-combo charts are shown when more than one firm is selected.")
    else:
        # For a single firm, only show combo charts
        enabled_plots = [name for name in ["raum_combo", "hc_combo"] if name in enabled_plots]
        print("Note: Only combo charts are shown when a single firm is selected.")

    num_plots = len(enabled_plots)
    if num_plots == 0:
        print("No plots selected in PLOT_SELECTION")
        return

    # Ensure minimum height for readability and adjust margins based on number of plots
    min_height = 5
    plot_height = max(3.5, min_height / num_plots)

    # For single company charts, increase chart area height
    if company_count == 1:
        plot_height *= 1.2

    # Adjust margins based on number of plots
    if num_plots <= 2:
        gridspec_kw = {"hspace": 0.485, "top": 0.90, "bottom": 0.12, "left": 0.12, "right": 0.92}
    else:
        gridspec_kw = {"hspace": 0.515, "top": 0.94, "bottom": 0.06, "left": 0.12, "right": 0.92}

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
        df = df.sort_values("Fiscal Year")
        df["Fiscal Year"] = df["Fiscal Year"].astype(int)

        # Filter data to start from specified year
        mask = df["Fiscal Year"] >= start_year
        years = df.loc[mask, "Fiscal Year"]

        if years.empty:
            continue

        # Add years to the set of all years for consistent x-axis
        all_years.update(years)

        # Extract key metrics for calculations
        ip_hc = df.loc[mask, "5B1"]  # Investment Professional headcount
        total_hc = df.loc[mask, "5A"]  # Total headcount
        aum_values = df.loc[mask, "5F2a"]  # Regulatory AUM

        # Calculate averages between current and previous year for per-employee metrics
        # This provides more accurate metrics than using point-in-time values
        prev_aum = aum_values.shift(1)
        prev_total_hc = total_hc.shift(1)
        prev_ip_hc = ip_hc.shift(1)
        avg_aum = calculate_annual_averages(aum_values, prev_aum)
        avg_total_hc = calculate_annual_averages(total_hc, prev_total_hc)
        avg_ip_hc = calculate_annual_averages(ip_hc, prev_ip_hc)

        # Plot data for each enabled plot type
        for plot_name in enabled_plots:
            ax = plot_axes[plot_name]

            # Handle different plot types
            if plot_name == "raum_total":
                plot_years, plot_values = years, aum_values
                ax.plot(
                    plot_years, plot_values, marker="o", label=firm_name, linewidth=2, markersize=6, zorder=5
                )
                add_data_labels(
                    ax, plot_years, plot_values, lambda y: f"${y/1e9:.1f}B" if y >= 1e9 else f"${y/1e6:.1f}M"
                )
                if company_count == 1:
                    add_yoy_growth(ax, plot_years, plot_values)
                title = f"{firm_name}: Total Regulatory AUM" if company_count == 1 else "Total Regulatory AUM"
                ax.set_title(title, fontsize=14, pad=15)
                ax.yaxis.set_major_formatter(
                    FuncFormatter(lambda x, p: f"${x/1e9:.1f}B" if x >= 1e9 else f"${x/1e6:.0f}M")
                )

            elif plot_name == "raum_normalized":
                plot_data = _get_aum_data(df, start_year)
                if plot_data is None:
                    continue
                plot_years, plot_values = plot_data
                ax.plot(
                    plot_years, plot_values, marker="o", label=firm_name, linewidth=2, markersize=6, zorder=5
                )
                add_data_labels(ax, plot_years, plot_values, lambda y: f"{int(y):,}")
                if company_count == 1:
                    add_yoy_growth(ax, plot_years, plot_values)
                title = (
                    f"{firm_name}: Normalized Regulatory AUM (First Year = 100)"
                    if company_count == 1
                    else "Normalized Regulatory AUM (First Year = 100)"
                )
                ax.set_title(title, fontsize=14, pad=15)

            elif plot_name == "total_hc":
                plot_years, plot_values = years, total_hc
                ax.plot(
                    plot_years, plot_values, marker="o", label=firm_name, linewidth=2, markersize=6, zorder=5
                )
                add_data_labels(ax, plot_years, plot_values, lambda y: f"{int(y):,}")
                if company_count == 1:
                    add_yoy_growth(ax, plot_years, plot_values)
                title = f"{firm_name}: Total Headcount" if company_count == 1 else "Total Headcount"
                ax.set_title(title, fontsize=14, pad=15)

            elif plot_name == "ip_hc":
                plot_years, plot_values = years, ip_hc
                ax.plot(
                    plot_years, plot_values, marker="o", label=firm_name, linewidth=2, markersize=6, zorder=5
                )
                add_data_labels(ax, plot_years, plot_values, lambda y: f"{int(y):,}")
                if company_count == 1:
                    add_yoy_growth(ax, plot_years, plot_values)
                title = (
                    f"{firm_name}: Investment Professional Headcount"
                    if company_count == 1
                    else "Investment Professional Headcount"
                )
                ax.set_title(title, fontsize=14, pad=15)

            elif plot_name == "ip_percentage":
                plot_years, plot_values = years, (ip_hc / total_hc) * 100
                ax.plot(
                    plot_years, plot_values, marker="o", label=firm_name, linewidth=2, markersize=6, zorder=5
                )
                add_data_labels(ax, plot_years, plot_values, lambda y: f"{y:.1f}%")
                if company_count == 1:
                    add_yoy_growth(ax, plot_years, plot_values)
                title = (
                    f"{firm_name}: Investment Professional Share"
                    if company_count == 1
                    else "Investment Professional Share"
                )
                ax.set_title(title, fontsize=14, pad=15)

            elif plot_name == "hc_combo":
                # Special handling for combined headcount chart with dual y-axes
                primary_config = {"label": "Total HC", "label_format": lambda y: f"{int(y):,}"}
                secondary_config = {
                    "label": "IP HC (%)",
                    "label_format": lambda y: f"{y:.1f}%",
                    "color": "teal",
                }

                # Plot the combo chart with dual y-axes
                ax2, line1, line2 = plot_combo_chart(
                    ax, years, total_hc, (ip_hc / total_hc) * 100, primary_config, secondary_config
                )

                # Add data labels for IP HC (%) series (secondary axis)
                add_data_labels(ax2, years, (ip_hc / total_hc) * 100, lambda y: f"{y:.1f}%")

                # Add Investment Professional Headcount on primary axis
                line3 = ax.plot(
                    years,
                    ip_hc,
                    marker="s",
                    label="IP HC",
                    linewidth=2,
                    color="green",
                    markersize=6,
                    zorder=5,
                )
                add_data_labels(ax, years, ip_hc, lambda y: f"{int(y):,}")

                # Add year-over-year growth annotations for headcount metrics
                if company_count == 1:
                    add_yoy_growth(ax, years, total_hc)
                    add_yoy_growth(ax, years, ip_hc)

                # Create legend with all three series in specified order
                lines = [line1, line3[0], line2]
                labels = [line.get_label() for line in lines]
                ax.legend(
                    lines,
                    labels,
                    fontsize=10,
                    loc="lower center",
                    ncol=3,
                    bbox_to_anchor=(0.5, 1.0),
                    borderaxespad=0.0,
                    frameon=False,
                )

                title = "Headcount (Total vs. Investment Professionals)"
                if company_count == 1:
                    title = f"{firm_name}: {title}"
                ax.set_title(title, fontsize=14, pad=21)

            elif plot_name == "raum_combo":
                # Special handling for combined RAUM chart with dual y-axes
                mid_years = [y - 0.5 for y in years]
                raum_per_ip = avg_aum / avg_ip_hc
                raum_per_total = avg_aum / avg_total_hc

                primary_config = {
                    "label": "RAUM",
                    "label_format": lambda y: f"${y/1e9:.1f}B" if y >= 1e9 else f"${y/1e6:.1f}M",
                }
                secondary_config_ip = {
                    "label": "RAUM/IP (mid-year)",
                    "label_format": lambda y: f"{y/1e6:.1f}M",
                    "color": "purple",
                }

                # Plot the combo chart with dual y-axes (RAUM and RAUM/IP)
                ax2, line1, line2 = plot_combo_chart(
                    ax, years, aum_values, raum_per_ip, primary_config, secondary_config_ip, mid_years
                )

                # Plot RAUM/Employee on secondary axis with distinct marker and color
                line3 = ax2.plot(
                    mid_years,
                    raum_per_total,
                    marker="^",
                    label="RAUM/Employee (mid-year)",
                    linewidth=2,
                    color="orange",
                    markersize=6,
                    linestyle="-",
                    zorder=5,
                    alpha=1.0,
                )

                # Adjust secondary axis to include all data from both series
                ax2.relim()
                ax2.autoscale_view()
                all_secondary_data = list(raum_per_ip) + list(raum_per_total)
                valid_data = [x for x in all_secondary_data if not pd.isna(x)]
                if valid_data:
                    ax2.set_ylim(min(valid_data) * 0.9, max(valid_data) * 1.1)

                # Add data labels for each secondary series
                add_data_labels(ax2, mid_years, raum_per_ip, secondary_config_ip["label_format"])
                add_data_labels(ax2, mid_years, raum_per_total, lambda y: f"{y/1e6:.1f}M")

                # Add year-over-year growth annotations for all metrics
                if company_count == 1:
                    add_yoy_growth(ax, years, aum_values)
                    add_yoy_growth(ax2, mid_years, raum_per_ip)
                    add_yoy_growth(ax2, mid_years, raum_per_total)

                # Create legend with all three series
                lines = [line1, line3[0], line2]
                labels = [line.get_label() for line in lines]
                ax.legend(
                    lines,
                    labels,
                    fontsize=10,
                    loc="lower center",
                    ncol=3,
                    bbox_to_anchor=(0.5, 1.0),
                    borderaxespad=0.0,
                    frameon=False,
                )

                prefix = f"{firm_name}: " if company_count == 1 else ""
                ax.set_title(
                    f"{prefix}Regulatory AUM (Total, per Employee, per Investment Professional)",
                    fontsize=14,
                    pad=21,
                )

            elif plot_name == "raum_per_total":
                plot_years, plot_values = [y - 0.5 for y in years], avg_aum / avg_total_hc
                ax.plot(
                    plot_years, plot_values, marker="o", label=firm_name, linewidth=2, markersize=6, zorder=5
                )
                add_data_labels(ax, plot_years, plot_values, lambda y: f"${y/1e6:.1f}M")
                if company_count == 1:
                    add_yoy_growth(ax, plot_years, plot_values)
                title = (
                    f"{firm_name}: Regulatory AUM per Employee (mid-year)"
                    if company_count == 1
                    else "Regulatory AUM per Employee (mid-year)"
                )
                ax.set_title(title, fontsize=14, pad=15)
                ax.yaxis.set_major_formatter(FuncFormatter(lambda x, p: f"${x/1e6:.0f}M"))

            elif plot_name == "raum_per_ip":
                plot_years, plot_values = [y - 0.5 for y in years], avg_aum / avg_ip_hc
                ax.plot(
                    plot_years, plot_values, marker="o", label=firm_name, linewidth=2, markersize=6, zorder=5
                )
                add_data_labels(ax, plot_years, plot_values, lambda y: f"${y/1e6:.1f}M")
                if company_count == 1:
                    add_yoy_growth(ax, plot_years, plot_values)
                title = (
                    f"{firm_name}: Regulatory AUM per Investment Professional (mid-year)"
                    if company_count == 1
                    else "Regulatory AUM per Investment Professional (mid-year)"
                )
                ax.set_title(title, fontsize=14, pad=15)
                ax.yaxis.set_major_formatter(FuncFormatter(lambda x, p: f"${x/1e6:.0f}M"))

    # Handle case where no data was found
    if not all_years:
        print(f"No data found from {start_year} onwards for any firm")
        return

    # Configure all axes with consistent formatting
    years_range = range(start_year, max(all_years) + 1)
    for plot_name, ax in plot_axes.items():
        # Set common properties for all plots
        ax.set_xticks(years_range)
        ax.tick_params(axis="x", rotation=45)
        ax.tick_params(axis="y", labelleft=False, left=False)
        ax.grid(True, linestyle="--", alpha=0.7)
        ax.set_axisbelow(True)

        # Only set legend for non-combo charts (combo charts handle their own legends)
        if plot_name not in COMBO_PLOTS:
            handles, labels = ax.get_legend_handles_labels()
            if handles:
                ax.legend(
                    fontsize=10,
                    loc="lower center",
                    ncol=len(handles),
                    bbox_to_anchor=(0.5, 1.0),
                    borderaxespad=0.0,
                    frameon=False,
                )
                ax.set_title(ax.get_title(), fontsize=14, pad=21)

        ax.set_xlim(start_year - 0.2, max(all_years) + 0.2)

        # Set titles and labels
        if not ax.get_title():
            # Set default titles for multi-company charts
            default_titles = {
                "raum_total": "Total Regulatory AUM",
                "raum_normalized": "Normalized Regulatory AUM (First Year = 100)",
                "total_hc": "Form ADV: Total Headcount",
                "ip_hc": "Form ADV: Investment Professional Headcount",
                "ip_percentage": "Form ADV: Investment Professional Share",
                "raum_per_total": "Regulatory AUM per Employee (mid-year)",
                "raum_per_ip": "Regulatory AUM per Investment Professional (mid-year)",
            }
            if plot_name in default_titles:
                ax.set_title(default_titles[plot_name], fontsize=14, pad=15)

    # Save the plot with high resolution and open in default OS viewer
    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    plt.close()  # Close the plot to free memory

    # Open the image using the appropriate command for the OS
    if platform.system() == "Darwin":  # macOS
        subprocess.run(["open", output_file], check=False)
    elif platform.system() == "Windows":
        subprocess.run(["start", output_file], shell=True, check=False)
    else:  # Linux
        subprocess.run(["xdg-open", output_file], check=False)


def _get_aum_data(df: pd.DataFrame, start_year: int) -> Optional[Tuple[pd.Series, pd.Series]]:
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


if __name__ == "__main__":
    load_and_plot_data()
