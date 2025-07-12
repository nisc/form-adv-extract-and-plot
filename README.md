# Form ADV Data Extractor and Plotter

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/)
[![Linting: flake8](https://img.shields.io/badge/linting-flake8-yellowgreen)](https://flake8.pycqa.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Extract and plot SEC Form ADV Part 1 filing data for investment advisory firms.

## Overview

This tool processes historical SEC Form ADV Part 1 filings to extract key metrics including employee counts, client demographics, regulatory assets under management (RAUM), and custody information. It generates detailed visualizations for both single-firm analysis and multi-firm comparisons.

## Features

- **20+ metrics**: Employee counts, RAUM, client demographics (easily extendable via YAML)
- **Charting**: Combo charts for single firms, individual charts for firm comparisons
- **Auto-download**: SEC filing data
- **Flexible matching**: SEC ID, CRD ID, or both

## Data Extracted

| Category | Field | Description | Form Field |
|----------|-------|-------------|------------|
| **Filing Information** | Submission Date | Date the filing was submitted | DateSubmitted |
| | Execution Date | Date the filing was executed | Execution Date |
| **Employee Counts** | Total Employees | Total number of employees | 5A |
| | Investment Professionals | Number of investment adviser representatives | 5B1 |
| **Client Counts** | High Net Worth Individuals | Number of high net worth individual clients | 5C1 |
| | Other Individuals | Number of other individual clients | 5C2 |
| | Investment Advisers | Number of other investment adviser clients | 5D1f |
| | Non-US Clients | Number of non-US clients | 5F2d |
| | US Clients | Number of US clients | 5F2f |
| | Private Fund Clients | Number of private fund clients | 9A2b |
| | Pooled Vehicle Clients | Number of other pooled investment vehicle clients | 9B2b |
| **Regulatory AUM** | Total RAUM | Total regulatory assets under management | 5F2a |
| | RAUM by Client Type | Regulatory AUM by client category | 5D3f |
| | US Client RAUM | RAUM from US clients | 5F2c, 5F3 |
| | Non-US Client RAUM | RAUM from non-US clients | 5F2b, 5F2e |
| | Private Fund RAUM | RAUM from private funds | 9A2a |
| | Pooled Vehicle RAUM | RAUM from other pooled investment vehicles | 9B2a |
| **Custody Information** | Private Fund Custody | Assets and clients from private funds | 9A2a, 9A2b |
| | Pooled Vehicle Custody | Assets and clients from pooled vehicles | 9B2a, 9B2b |

> **Note:** The set of extracted fields can be easily expanded by editing the configuration file (`adv_extract_settings.yaml`).

## Charts Produced

- **RAUM Trends**: Total and normalized regulatory assets under management
- **Headcount Metrics**: Total employees and investment professional counts
- **Per-Employee Ratios**: RAUM per employee and per investment professional

## Example Output

### Single Firm Analysis
When analyzing a single firm, combo charts are generated showing multiple metrics on the same plot:

<a href="output/plots/samples/adv_plot_single.png" target="_blank">
<img src="output/plots/samples/adv_plot_single.png" alt="Single Firm Analysis" width="800" style="cursor: pointer;" title="Click to view full size">
</a>

### Multi-Firm Comparison
When comparing multiple firms, individual charts are generated for each metric:

<a href="output/plots/samples/adv_plot_multi.png" target="_blank">
<img src="output/plots/samples/adv_plot_multi.png" alt="Multi-Firm Comparison" width="800" style="cursor: pointer;" title="Click to view full size">
</a>

## Project Structure

```
form-adv-extract-and-plot/
├── src/                           # Python source code
│   ├── adv_downloader.py          # SEC website download module
│   ├── adv_extract.py             # Extract data from ADV files
│   ├── adv_extract_perftest.py    # Performance testing script
│   └── adv_plot.py                # Generate plots from extracted data
├── input/                         # ADV filing data CSV files
├── output/                        # Generated output files
│   ├── csvs/                      # Extracted data files
│   └── plots/                     # Generated plots
├── docs/                          # Documentation and examples
├── adv_extract_settings.yaml      # Main configuration
├── adv_extract_firms.yaml         # Firm definitions and default values
├── requirements.txt               # Python dependencies
├── pyproject.toml                 # Project configuration
└── run.sh                         # Bash script to run the pipeline
```

## Quick Start

### Prerequisites

- Python 3.8+
- pip package manager

### Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd form-adv-extract-and-plot
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

### Usage

1. **Configure firms:** Edit `adv_extract_firms.yaml` to define the firms you want to analyze

2. **Download and extract data:**

**Option 1: Run the complete pipeline (Recommended)**
```bash
./run.sh
```
This bash script automatically:
- Checks prerequisites and dependencies
- Downloads SEC filing data (if not present)
- Runs data extraction
- Generates plots
- Provides status updates throughout the process

**Option 2: Run individual steps manually**

   ```bash
   python src/adv_extract.py
   ```
   > **Note:** The extractor will automatically download SEC filing data if no CSV files are found in the `input/` directory.

3. **Generate plots:**
   ```bash
   python src/adv_plot.py
   ```

4. **Test performance (optional):**
   ```bash
   python src/adv_extract_perftest.py
   ```

## Output Files

- **CSV files**: `output/csvs/adv_data_<firm>_<sec_id>_<crd_id>_<year>.csv`
- **Plots**: `output/plots/adv_plot_<firmname>_<counter>.png` (single firm) or `output/plots/adv_plot_multi_<counter>.png` (multiple firms) with auto-incrementing counters

## Configuration

### Firm Configuration (`adv_extract_firms.yaml`)

Define firms to analyze with their SEC and CRD identifiers:

```yaml
FIRMS:
  - name: "Example Firm"
    sec_id: "801-12345"
    crd_id: 123456
    default_values:
      2024:
        5A: 1000
        5F2a: 50000000000
        # ... other fields
```

> **Note:** Data corrections for known errors in source files (the `OVERWRITES` block) are located at the end of `adv_extract_firms.yaml`.

### Settings Configuration (`adv_extract_settings.yaml`)

Configure extraction parameters, target columns, and matching strategies:

- **Matching Strategy**: Choose between SEC ID only, CRD ID only, or both
- **Target Columns**: Define which Form ADV fields to extract
- **Download URLs**: Configure automatic data acquisition sources

## Current Limitations

- The latest filing year is not extracted automatically, as it is only available in PDF format. This data must be entered manually in `adv_extract_firms.yaml`. (A PDF parser is planned for future releases.)

## License

MIT License - see [LICENSE](LICENSE) file for details.
