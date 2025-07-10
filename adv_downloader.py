#!/usr/bin/env python3
"""SEC website download module for accessing public filing data.

This module provides downloading capabilities for SEC Form ADV filing data
using standard web browser interactions to access publicly available information.
"""

import os
import shutil
import time
import zipfile
from pathlib import Path
from typing import Optional

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager

    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False


class ADVDownloader:
    """Handles downloading of SEC Form ADV filing data using standard web browser interactions."""

    def __init__(self, input_dir: Path, config: Optional[dict] = None):
        """Initialize the downloader with the target input directory and optional config."""
        self.input_dir = input_dir
        self.input_dir.mkdir(exist_ok=True)
        self.config = config or {}

    def _get_config_value(self, key: str, default: float) -> float:
        """Get a configuration value with fallback to default."""
        return self.config.get(key, default)

    def _get_timing_config(
        self,
        download_delay_seconds: Optional[float] = None,
        browser_session_wait: Optional[float] = None,
        browser_download_wait: Optional[float] = None,
        max_retries: Optional[int] = None,
    ):
        """Get timing and retry configuration values from config."""
        return {
            "delay_seconds": (
                download_delay_seconds
                if download_delay_seconds is not None
                else self.config.get("DOWNLOAD_DELAY_SECONDS")
            ),
            "session_wait": (
                browser_session_wait
                if browser_session_wait is not None
                else self.config.get("BROWSER_SESSION_WAIT_SECONDS")
            ),
            "download_wait": (
                browser_download_wait
                if browser_download_wait is not None
                else self.config.get("BROWSER_DOWNLOAD_WAIT_SECONDS")
            ),
            "max_retries": max_retries if max_retries is not None else self.config.get("MAX_RETRIES"),
        }

    def _retry_operation(self, operation, max_retries: int, wait_time: float, operation_name: str):
        """Generic retry mechanism for operations that may fail."""
        for attempt in range(max_retries + 1):
            try:
                result = operation()
                if result is not None:
                    return result

                # Operation returned None (failed)
                if attempt < max_retries:
                    print(f"  ⚠️  Attempt {attempt + 1} failed, retrying...")
                    # Exponential backoff
                    backoff_time = wait_time * (2**attempt)
                    time.sleep(backoff_time)
                    continue
                else:
                    raise Exception(f"{operation_name} failed after all retries")

            except Exception as e:
                if attempt < max_retries:
                    print(f"  ⚠️  Attempt {attempt + 1} failed: {e}, retrying...")
                    # Exponential backoff
                    backoff_time = wait_time * (2**attempt)
                    time.sleep(backoff_time)
                    continue
                else:
                    print(f"  🔴 Error in {operation_name} after {max_retries + 1} attempts: {e}")
                    return None

    def download_file(
        self,
        url: str,
        description: str,
        index: int,
        total: int,
        browser_session_wait: Optional[float] = None,
        browser_download_wait: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> Optional[Path]:
        """Download and extract a single file from SEC website."""
        print(f"\n[{index}/{total}] Downloading {description}...")

        timing = self._get_timing_config(
            browser_session_wait=browser_session_wait,
            browser_download_wait=browser_download_wait,
            max_retries=max_retries,
        )
        session_wait = timing["session_wait"]
        download_wait = timing["download_wait"]
        retries = timing["max_retries"]

        def download_operation():
            filename = url.split("/")[-1]
            filepath = self.input_dir / filename

            print(f"  Downloading from: {url}")

            if filepath.exists():
                print(f"    🟢 File already exists: {filename}")
                return self._extract_file(filepath)

            print("  Attempting download via browser...")
            if self._try_browser_download(url, filepath, session_wait, download_wait):
                print("  🟢 Downloaded successfully")
                return self._extract_file(filepath)
            else:
                return None  # Signal failure to retry mechanism

        return self._retry_operation(download_operation, retries, download_wait, f"downloading {description}")

    def download_and_extract_all_files(
        self,
        download_urls: dict,
        download_delay_seconds: Optional[float] = None,
        browser_session_wait: Optional[float] = None,
        browser_download_wait: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> bool:
        """Download and extract all ADV filing data files from SEC website."""
        timing = self._get_timing_config(
            download_delay_seconds, browser_session_wait, browser_download_wait, max_retries
        )
        delay_seconds = timing["delay_seconds"]
        session_wait = timing["session_wait"]
        download_wait = timing["download_wait"]
        retries = timing["max_retries"]

        total_download_size = self._calculate_total_download_size(download_urls)

        print(f"\nNo ADV filing data found in {self.input_dir} directory.")
        print(f"Total download size will be approximately {total_download_size}.")

        if input("\nDo you want to download the ADV filing data files? (Y/n): ").strip().lower() not in [
            "y",
            "yes",
            "",
        ]:
            print("Download cancelled. Please manually download and extract files to the 'input' directory.")
            return False

        print("\nStarting download and extraction process...")

        # Flatten all URLs with descriptions for processing
        all_urls = [(item["url"], item["description"]) for urls in download_urls.values() for item in urls]

        # Download and extract all files sequentially
        downloaded_files = []
        failed_downloads = []

        for i, (url, description) in enumerate(all_urls, 1):
            if extract_dir := self.download_file(
                url, description, i, len(all_urls), session_wait, download_wait, retries
            ):
                downloaded_files.append(extract_dir)
            else:
                failed_downloads.append((url, description))

            # Add delay between downloads for respectful access
            if i < len(all_urls) and delay_seconds > 0:  # Don't delay after the last download
                print(f"  Waiting {delay_seconds} seconds before next download...")
                time.sleep(delay_seconds)

        if failed_downloads:
            print(f"\n⚠️  {len(failed_downloads)} downloads failed. Providing manual download instructions:")
            self.provide_manual_download_instructions(failed_downloads)
            return False

        print(f"\n🟢 All files downloaded and extracted to {self.input_dir} directory.")
        return True

    def _estimate_file_size_from_url(self, url: str) -> float:
        """Estimate file size from description in config."""
        config = getattr(self, "config", {})
        download_urls = config.get("DOWNLOAD_URLS", {})

        for category in download_urls.values():
            for item in category:
                if item.get("url") == url:
                    description = item.get("description", "")
                    return self._parse_size_from_description(description)

        # If not found in config, return 0 to use default timeout
        return 0.0

    def _parse_size_from_description(self, description: str) -> float:
        """Parse file size from description string."""
        if "(" in description and ")" in description:
            size_str = description.split("(")[-1].split(")")[0]
            # Parse common size formats
            if "MB" in size_str:
                return float(size_str.replace("MB", "").strip())
            elif "GB" in size_str:
                return float(size_str.replace("GB", "").strip()) * 1024
        return 0.0

    def _print_file_size(self, message: str, size_bytes: int) -> None:
        """Print file size in appropriate units (MB or GB)."""
        size_gb = size_bytes / (1024**3)
        size_mb = size_bytes / (1024**2)

        if size_gb >= 1:
            print(f"    {message} ({size_gb:.1f} GB)")
        else:
            print(f"    {message} ({size_mb:.1f} MB)")

    def _calculate_download_timeout(self, file_size_mb: float) -> int:
        """Calculate download timeout based on file size."""
        # Base timeout: 30 seconds per MB, minimum 60 seconds, maximum 3600 seconds (1 hour)
        base_timeout_per_mb = 30
        min_timeout = 60
        max_timeout = 3600

        if file_size_mb > 0:
            return min(max(int(file_size_mb * base_timeout_per_mb), min_timeout), max_timeout)
        else:
            return self.config.get("DOWNLOAD_TIMEOUT")

    def _calculate_total_download_size(self, download_urls: dict) -> str:
        """Calculate the total download size for all files."""
        total_size = 0
        for urls in download_urls.values():
            for item in urls:
                # Extract size from description if available
                description = item.get("description", "")
                if "(" in description and ")" in description:
                    size_str = description.split("(")[-1].split(")")[0]
                    # Parse common size formats
                    if "MB" in size_str:
                        size = float(size_str.replace("MB", "").strip())
                        total_size += size
                    elif "GB" in size_str:
                        size = float(size_str.replace("GB", "").strip()) * 1024
                        total_size += size

        if total_size > 1024:
            return f"{total_size/1024:.1f} GB"
        else:
            return f"{total_size:.1f} MB"

    def _try_browser_download(
        self, url: str, filepath: Path, session_wait: float, download_wait: float
    ) -> bool:
        """Download file using standard web browser interactions."""
        if not SELENIUM_AVAILABLE:
            print("    🔴 Selenium not available. Please install: pip install selenium webdriver-manager")
            return False

        try:
            # Configure Chrome options for standard web access
            chrome_options = Options()
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option("useAutomationExtension", False)
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument(
                "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )

            # Add additional headers and settings for better compatibility
            chrome_options.add_argument("--disable-web-security")
            chrome_options.add_argument("--allow-running-insecure-content")
            chrome_options.add_argument("--disable-features=VizDisplayCompositor")

            # Create driver with fixed configuration
            driver = webdriver.Chrome(
                service=webdriver.chrome.service.Service(ChromeDriverManager().install()),
                options=chrome_options,
            )

            # Set timeout limits
            page_load_timeout = self.config.get("PAGE_LOAD_TIMEOUT", 120)
            script_timeout = self.config.get("SCRIPT_TIMEOUT", 60)
            driver.set_page_load_timeout(page_load_timeout)
            driver.set_script_timeout(script_timeout)

            # Configure webdriver
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            try:
                # First visit the SEC homepage to establish session
                print("    Establishing browser session...")
                driver.get("https://www.sec.gov/")
                time.sleep(session_wait)  # Configurable wait for page to load

                # Now try to download the file
                print("    Attempting download via browser...")
                driver.get(url)

                # Check for temporary access issues
                page_source = driver.page_source.lower()
                if "rate threshold exceeded" in page_source or "403" in driver.current_url:
                    print("    ⚠️  Rate limit detected, waiting longer...")
                    time.sleep(download_wait * 2)  # Wait twice as long
                    # Try refreshing the page
                    driver.refresh()
                    time.sleep(download_wait)

                # Wait for download to start or page to load
                time.sleep(download_wait)  # Configurable wait time

                # Check if file was downloaded (look in default download directory)
                download_dir = os.path.expanduser("~/Downloads")
                downloaded_file = None

                # Extract expected filename from URL
                expected_filename = url.split("/")[-1]

                # Calculate dynamic timeout based on file size
                file_size_mb = self._estimate_file_size_from_url(url)
                download_timeout = self._calculate_download_timeout(file_size_mb)
                check_interval = 10  # Check every 10 seconds
                max_checks = download_timeout // check_interval

                print(f"    Estimated file size: {file_size_mb:.1f} MB")
                print(f"    Dynamic timeout: {download_timeout}s ({download_timeout/60:.1f} minutes)")

                for check in range(max_checks):
                    # Look for the specific file in downloads
                    expected_file_path = os.path.join(download_dir, expected_filename)
                    if os.path.exists(expected_file_path):
                        # Check if file is still being downloaded (size is changing)
                        initial_size = os.path.getsize(expected_file_path)
                        time.sleep(2)
                        current_size = os.path.getsize(expected_file_path)

                        if initial_size == current_size:
                            # File size stopped changing, download likely complete
                            downloaded_file = expected_file_path
                            self._print_file_size("Download completed", current_size)
                            break
                        else:
                            self._print_file_size("Download in progress", current_size)

                    time.sleep(check_interval)

                if not downloaded_file:
                    print(f"    ⚠️  Download timeout after {download_timeout} seconds")
                    return False

                if downloaded_file and os.path.exists(downloaded_file):
                    # Move file to our input directory
                    shutil.move(downloaded_file, filepath)
                    return True

            finally:
                driver.quit()

        except Exception as e:
            print(f"    🔴 Browser access failed: {e}")

        return False

    def _extract_file(self, filepath: Path) -> Optional[Path]:
        """Extract a ZIP file and return the extraction directory."""
        if not filepath.exists():
            return None

        # Create subfolder for this ZIP file
        zip_name = filepath.stem  # filename without extension
        extract_dir = self.input_dir / zip_name
        extract_dir.mkdir(exist_ok=True)

        # Extract the file into its own subfolder
        print(f"  Extracting {filepath.name} to {extract_dir.name}/...")
        try:
            with zipfile.ZipFile(filepath, "r") as zip_ref:
                zip_ref.extractall(extract_dir)
            print(f"  🟢 Successfully extracted {filepath.name}")

            # Delete the ZIP file immediately after extraction
            filepath.unlink()
            print(f"  Deleted {filepath.name}")

            return extract_dir
        except Exception as e:
            print(f"  🔴 Error extracting {filepath.name}: {e}")
            return None

    def cleanup_zip_files(self, downloaded_files: list[Path]) -> None:
        """Ask user if they want to delete ZIP files and handle cleanup."""
        if not downloaded_files:
            return

        print(f"\n{len(downloaded_files)} ZIP files were downloaded and extracted.")
        if input("Do you want to delete the ZIP files to save space? (y/N): ").strip().lower() in [
            "y",
            "yes",
        ]:
            for filepath in downloaded_files:
                try:
                    filepath.unlink()
                    print(f"  🟢 Deleted {filepath.name}")
                except Exception as e:
                    print(f"  🔴 Error deleting {filepath.name}: {e}")
            print("🟢 All ZIP files deleted.")
        else:
            print("ZIP files kept in input directory.")

    def provide_manual_download_instructions(self, failed_downloads: list) -> None:
        """Provide manual download instructions for failed downloads."""
        print("\n" + "=" * 80)
        print("MANUAL DOWNLOAD INSTRUCTIONS")
        print("=" * 80)
        print("\n🔴 The automated download failed. Please manually download these files:")

        for url, description in failed_downloads:
            print(f"\n• {description}")
            print(f"  URL: {url}")

        print("\nDownload steps:")
        print("1. Visit each URL in your web browser")
        print(f"2. Save the ZIP files to the '{self.input_dir}' directory")
        print(f"3. Extract the ZIP files in the '{self.input_dir}' directory")
        print("4. Run 'python adv_extract.py' again")

        print("\nAfter manual download, run: python adv_extract.py")
        print("=" * 80)
