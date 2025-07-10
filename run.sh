#!/bin/bash

# ADV Extract and Plot Script
# This script runs the ADV data extractor followed by the plotter

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if Python is available
check_python() {
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed or not in PATH"
        exit 1
    fi
    print_success "Python 3 found: $(python3 --version)"
}

# Function to check if required files exist
check_required_files() {
    local missing_files=()

    if [[ ! -f "src/adv_extract.py" ]]; then
        missing_files+=("src/adv_extract.py")
    fi

    if [[ ! -f "src/adv_plot.py" ]]; then
        missing_files+=("src/adv_plot.py")
    fi

    if [[ ! -f "adv_extract_settings.yaml" ]]; then
        missing_files+=("adv_extract_settings.yaml")
    fi

    if [[ ! -f "adv_extract_firms.yaml" ]]; then
        missing_files+=("adv_extract_firms.yaml")
    fi

    if [[ ${#missing_files[@]} -gt 0 ]]; then
        print_error "Missing required files: ${missing_files[*]}"
        exit 1
    fi

    print_success "All required files found"
}

# Function to check if input directory exists
check_input_directory() {
    if [[ ! -d "input" ]]; then
        print_warning "Input directory 'input' not found"
        print_status "Creating input directory..."
        mkdir -p input
        print_warning "Please add your ADV CSV files to the 'input' directory and run the script again"
        exit 1
    fi

    # Check if there are any CSV files in the input directory
    if ! ls input/*.csv 1> /dev/null 2>&1; then
        print_warning "No CSV files found in input directory"
        print_status "Please add your ADV CSV files to the 'input' directory and run the script again"
        exit 1
    fi

    print_success "Input directory and CSV files found"
}

# Function to install dependencies if needed
install_dependencies() {
    print_status "Checking Python dependencies..."

    # Function to try activating existing virtual environment
    try_activate_venv() {
        if [[ -d ".venv" ]]; then
            print_status "Found .venv directory, attempting to activate..."
            if source .venv/bin/activate 2>/dev/null; then
                print_success "Successfully activated .venv"
                return 0
            else
                print_warning "Failed to activate .venv"
                return 1
            fi
        elif [[ -d "venv" ]]; then
            print_status "Found venv directory, attempting to activate..."
            if source venv/bin/activate 2>/dev/null; then
                print_success "Successfully activated venv"
                return 0
            else
                print_warning "Failed to activate venv"
                return 1
            fi
        else
            print_warning "No virtual environment found"
            return 1
        fi
    }

    # Function to create new virtual environment
    create_venv() {
        print_status "Creating new virtual environment..."
        if python3 -m venv .venv; then
            print_success "Created .venv virtual environment"
            if source .venv/bin/activate; then
                print_success "Activated new virtual environment"
                return 0
            else
                print_error "Failed to activate new virtual environment"
                return 1
            fi
        else
            print_error "Failed to create virtual environment"
            return 1
        fi
    }

    # Function to install requirements
    install_requirements() {
        if [[ -f "requirements.txt" ]]; then
            print_status "Installing dependencies from requirements.txt..."
            if pip install -r requirements.txt; then
                print_success "Dependencies installed from requirements.txt"
                return 0
            else
                print_warning "Failed to install from requirements.txt, trying common dependencies..."
                if pip install pandas pyyaml numpy matplotlib; then
                    print_success "Common dependencies installed"
                    return 0
                else
                    print_error "Failed to install dependencies"
                    return 1
                fi
            fi
        else
            print_warning "requirements.txt not found, installing common dependencies..."
            if pip install pandas pyyaml numpy matplotlib; then
                print_success "Common dependencies installed"
                return 0
            else
                print_error "Failed to install common dependencies"
                return 1
            fi
        fi
    }

    # Try to activate existing virtual environment first
    if try_activate_venv; then
        # Check if required packages are already installed
        print_status "Checking if required packages are installed..."
        if python3 -c "import pandas, yaml, numpy, matplotlib" 2>/dev/null; then
            print_success "Required packages are already installed"
            return 0
        else
            print_warning "Required packages not found in activated environment"
            install_requirements
        fi
    else
        # Try to create new virtual environment
        if create_venv; then
            install_requirements
        else
            print_warning "Failed to create virtual environment, installing globally..."
            install_requirements
        fi
    fi
}

# Function to run the extractor
run_extractor() {
    print_status "Starting ADV data extraction..."

    if python3 src/adv_extract.py; then
        print_success "ADV data extraction completed successfully"
    else
        print_error "ADV data extraction failed"
        exit 1
    fi
}

# Function to run the plotter
run_plotter() {
    print_status "Starting ADV data plotting..."

    if python3 src/adv_plot.py; then
        print_success "ADV data plotting completed successfully"
    else
        print_error "ADV data plotting failed"
        exit 1
    fi
}

# Function to show results
show_results() {
    print_status "Checking output files..."

    csv_files_found=false
    plot_files_found=false

    if [[ -d "output/csvs" ]] && ls output/csvs/*.csv 1> /dev/null 2>&1; then
        print_success "CSV files generated in output/csvs/"
        ls -la output/csvs/*.csv
        csv_files_found=true
    fi

    if [[ -d "output/plots" ]] && ls output/plots/*.png 1> /dev/null 2>&1; then
        print_success "Plot files generated in output/plots/"
        ls -la output/plots/*.png
        plot_files_found=true
    fi

    if $csv_files_found || $plot_files_found; then
        print_success "Process completed successfully!"
    else
        print_warning "No output files were generated"
    fi
}

# Parse command line arguments
show_help() {
    echo "Usage: $0 [--extract] [--plot]"
    echo "  --extract   Run only the extractor"
    echo "  --plot      Run only the plotter"
    echo "  (default: both steps are run if no option is given)"
    exit 0
}

RUN_EXTRACT=false
RUN_PLOT=false

if [[ $# -eq 0 ]]; then
    RUN_EXTRACT=true
    RUN_PLOT=true
else
    for arg in "$@"; do
        case $arg in
            --extract)
                RUN_EXTRACT=true
                ;;
            --plot)
                RUN_PLOT=true
                ;;
            -h|--help)
                show_help
                ;;
            *)
                print_error "Unknown argument: $arg"
                show_help
                ;;
        esac
    done
    # If only one is set, the other remains false
    # If both are set, both run
fi

# Main execution
main() {
    echo "=========================================="
    echo "    ADV Extract and Plot Script"
    echo "=========================================="

    # Check prerequisites
    check_python
    check_required_files

    # Only check input directory if extracting
    if $RUN_EXTRACT; then
        check_input_directory
    fi

    # Install dependencies
    install_dependencies

    print_status "Starting ADV extract and plot pipeline..."

    if $RUN_EXTRACT; then
        run_extractor
        print_status "Extraction complete."
    fi

    if $RUN_PLOT; then
        print_status "Starting plotting..."
        run_plotter
    fi

    # Show results if either step ran
    if $RUN_EXTRACT || $RUN_PLOT; then
        show_results
    fi

    echo "=========================================="
    print_success "Pipeline completed successfully!"
    echo "=========================================="
}

# Run main function
main "$@"
