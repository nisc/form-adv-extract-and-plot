#!/usr/bin/env python3
"""Script to measure performance of adv_extract.py and related scripts.

This script automatically discovers and tests all Python scripts matching the pattern
'adv_extract*.py' in the current directory. It runs each script multiple times to
get reliable performance measurements and provides detailed statistics.

Usage:
    python test_performance.py

The script will:
1. Find all adv_extract*.py files in the current directory
2. Run each script multiple times and measure execution time
3. Calculate performance statistics (mean, std dev, min, max)
4. Compare performance between different scripts if multiple exist
"""

import glob
import statistics
import subprocess
import time


def find_adv_extract_scripts() -> list:
    """Find all adv_extract*.py scripts in the current directory.

    This function uses glob to find all Python files that start with 'adv_extract'
    and end with '.py'. This allows testing of multiple variants like:
    - adv_extract.py (main script)
    - adv_extract_v2.py (alternative version)
    - adv_extract_optimized.py (optimized version)
    - etc.

    Returns:
        List of script filenames, sorted alphabetically
    """
    # Use glob to find all files matching the pattern
    scripts = glob.glob("adv_extract*.py")
    # Sort alphabetically for consistent ordering
    return sorted(scripts)


def run_test(script_name: str, num_runs: int = 3) -> list:
    """Run script multiple times and measure execution time.

    This function executes a Python script multiple times and measures how long
    each execution takes. It captures both stdout and stderr to detect errors.
    Multiple runs help account for system variability and provide more reliable
    performance measurements.

    Args:
        script_name: Name of the script to run (e.g., "adv_extract.py")
        num_runs: Number of times to run the script (default: 3)

    Returns:
        List of execution times in seconds for each run
    """
    times = []

    for i in range(num_runs):
        print(f"\nRun {i+1}/{num_runs}")

        # Record start time before execution
        start_time = time.time()

        # Execute the script as a subprocess
        # capture_output=True captures both stdout and stderr
        # text=True returns strings instead of bytes
        result = subprocess.run(["python", script_name], capture_output=True, text=True)

        # Record end time after execution
        end_time = time.time()
        execution_time = end_time - start_time
        times.append(execution_time)

        # Display results for this run
        print(f"Execution time: {execution_time:.2f} seconds")
        print(f"Exit code: {result.returncode}")

        # Check if the script ran successfully
        if result.returncode != 0:
            print("Error output:")
            print(result.stderr)
        else:
            print("Success!")

    return times


def print_results(script_name: str, times: list):
    """Print performance test results with detailed statistics.

    This function calculates and displays detailed performance statistics
    for a script, including mean, standard deviation, minimum, and maximum
    execution times. This helps identify both average performance and variability.

    Args:
        script_name: Name of the script that was tested
        times: List of execution times from multiple runs

    Returns:
        Average execution time (useful for comparisons)
    """
    # Calculate statistical measures
    avg_time = statistics.mean(times)
    # Standard deviation requires at least 2 values
    std_dev = statistics.stdev(times) if len(times) > 1 else 0
    min_time = min(times)
    max_time = max(times)

    # Display formatted results
    print(f"\n{script_name} Results")
    print("=" * 50)
    print(f"Number of runs: {len(times)}")
    print(f"Average execution time: {avg_time:.2f} seconds")
    print(f"Standard deviation: {std_dev:.2f} seconds")
    print(f"Minimum time: {min_time:.2f} seconds")
    print(f"Maximum time: {max_time:.2f} seconds")
    print("=" * 50)

    return avg_time


def main():
    """Main function to orchestrate performance testing of all adv_extract scripts.

    This function coordinates the entire testing process:
    1. Discovers all adv_extract*.py scripts
    2. Tests each script multiple times
    3. Calculates and displays performance statistics
    4. Compares performance between different scripts if multiple exist
    """
    print("Starting performance testing for adv_extract scripts...")

    # Step 1: Find all adv_extract scripts in the current directory
    scripts = find_adv_extract_scripts()

    # Check if any scripts were found
    if not scripts:
        print("No adv_extract*.py scripts found!")
        print("Make sure you have at least one script named adv_extract*.py in the current directory.")
        return

    print(f"Found {len(scripts)} script(s): {', '.join(scripts)}")

    # Dictionary to store results for each script
    results = {}

    # Step 2: Test each script individually
    for script in scripts:
        print(f"\n{'='*60}")
        print(f"Testing {script}...")
        print(f"{'='*60}")

        # Run the script multiple times and get timing data
        times = run_test(script)
        # Calculate and display statistics, store average time
        avg_time = print_results(script, times)
        results[script] = avg_time

    # Step 3: Compare results if multiple scripts were tested
    if len(scripts) > 1:
        print(f"\n{'='*60}")
        print("PERFORMANCE COMPARISON")
        print(f"{'='*60}")

        # Sort scripts by performance (fastest first)
        sorted_results = sorted(results.items(), key=lambda x: x[1])

        # Extract fastest and slowest scripts
        fastest_script, fastest_time = sorted_results[0]
        slowest_script, slowest_time = sorted_results[-1]

        # Display comparison results
        print(f"Fastest: {fastest_script} ({fastest_time:.2f}s)")
        print(f"Slowest: {slowest_script} ({slowest_time:.2f}s)")

        # Calculate and display performance improvement percentage
        if len(sorted_results) > 1:
            improvement = ((slowest_time - fastest_time) / slowest_time) * 100
            print(f"Performance difference: {improvement:.1f}% faster")

    # Final summary
    print(f"\n{'='*60}")
    print("TESTING COMPLETE")
    print(f"{'='*60}")


# Standard Python idiom to run the main function when script is executed directly
if __name__ == "__main__":
    main()
