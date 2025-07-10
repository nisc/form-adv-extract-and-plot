#!/bin/bash

# ADV Extract and Plot Script
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check Python
check_python() {
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed or not in PATH"
        exit 1
    fi
    print_success "Python 3 found: $(python3 --version)"
}

# Install dependencies
install_dependencies() {
    print_status "Installing dependencies..."
    if [[ -f "requirements.txt" ]]; then
        pip install -r requirements.txt
    else
        pip install pandas pyyaml numpy matplotlib
    fi
    print_success "Dependencies installed"
}

# Ensure input directory exists
ensure_input_directory() {
    [[ -d "input" ]] || mkdir -p input
}

# Show results
show_results() {
    print_status "Output files:"
    [[ -d "output/csvs" ]] && ls -la output/csvs/*.csv 2>/dev/null || \
        print_warning "No CSV files generated"
    [[ -d "output/plots" ]] && ls -la output/plots/*.png 2>/dev/null || \
        print_warning "No plot files generated"
}

# Help
show_help() {
    echo "Usage: $0 [--extract] [--plot] [--perftest]"
    echo "  --extract   Run only the extractor"
    echo "  --plot      Run only the plotter"
    echo "  --perftest  Run performance testing script"
    echo "  (default: both extract and plot if no option is given)"
    exit 0
}

# Parse arguments
RUN_EXTRACT=false
RUN_PLOT=false
RUN_PERFTEST=false

if [[ $# -eq 0 ]]; then
    RUN_EXTRACT=true
    RUN_PLOT=true
else
    for arg in "$@"; do
        case $arg in
            --extract) RUN_EXTRACT=true ;;
            --plot) RUN_PLOT=true ;;
            --perftest) RUN_PERFTEST=true ;;
            -h|--help) show_help ;;
            *) print_error "Unknown argument: $arg"; show_help ;;
        esac
    done
fi

# Main execution
echo "=========================================="
echo "    ADV Extract and Plot Script"
echo "=========================================="

check_python
install_dependencies

if $RUN_EXTRACT; then
    ensure_input_directory
    print_status "Starting ADV data extraction..."
    python3 src/adv_extract.py
    print_success "Extraction complete"
fi

if $RUN_PLOT; then
    print_status "Starting ADV data plotting..."
    python3 src/adv_plot.py
    print_success "Plotting complete"
fi

if $RUN_PERFTEST; then
    print_status "Starting performance testing..."
    python3 src/adv_extract_perftest.py
    print_success "Performance testing complete"
fi

if $RUN_EXTRACT || $RUN_PLOT; then
    show_results
fi

echo "=========================================="
print_success "Pipeline completed successfully!"
echo "=========================================="
