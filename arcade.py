import os
import sys
import subprocess
import requests
import zipfile
import shutil
import time
import socket
import threading
import http.server
import socketserver
import webbrowser
import platform
from functools import partial
from tqdm import tqdm

# --- Configuration ---
GITHUB_ARCHIVE_REPO_OWNER = "TheSpongeBobCommunity"  # IMPORTANT: Update with actual GitHub repo owner
GITHUB_ARCHIVE_REPO_NAME = "flash-game-archive"  # IMPORTANT: Update with actual GitHub repo name
ARCHIVE_RELEASE_TAG = "v1.0.0" # IMPORTANT: Update with the actual release tag on GitHub (e.g., "v1.0.0")

# Derived paths based on script location
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ARCHIVE_DIR_NAME = "flash_game_archive"
LOCAL_ARCHIVE_ROOT_DIR = os.path.join(SCRIPT_DIR, ARCHIVE_DIR_NAME) # This is where the game content will be
SETUP_HTML_FILE_NAME = "setup.html"
SETUP_HTML_TEMP_PATH = os.path.join(SCRIPT_DIR, SETUP_HTML_FILE_NAME) # Path for setup.html during setup phase

PROXY_SERVER_SCRIPT = os.path.join(SCRIPT_DIR, "python", "proxy_server.py")
MAIN_PROXY_SERVER_PORT = 8004 # Default port for the main proxy server
TEMP_SERVER_PORT = 8005 # A different port for the setup server to avoid conflict

# --- Helper Functions ---

def install_dependencies():
    """Installs necessary Python packages using pip."""
    print("Checking and installing Python dependencies...")
    # Add 'selenium' back as it's needed by archive.py, though arcade.py doesn't directly use it
    # We include tqdm for the download progress bar
    required_packages = ["requests", "beautifulsoup4", "selenium-wire", "selenium", "tqdm"]
    for package in required_packages:
        try:
            # Check if package is importable first
            __import__(package.split('-')[0]) # Import base name (e.g., 'selenium' from 'selenium-wire')
            print(f"  -> {package} is already installed.")
        except ImportError:
            print(f"  -> {package} not found. Installing...")
            try:
                # Use --break-system-packages for environments that might need it (e.g., venv on some Linux)
                # This makes it more robust for users who are not aware of virtual environments.
                subprocess.check_call([sys.executable, "-m", "pip", "install", package, "--break-system-packages"])
                print(f"  -> {package} installed successfully.")
            except subprocess.CalledProcessError as e:
                print(f"  -> Error installing {package}: {e}")
                print("Please try running \'pip install -r requirements.txt --break-system-packages\' manually if this persists.")
                sys.exit(1)
            except Exception as e:
                print(f"  -> An unexpected error occurred while installing {package}: {e}")
                sys.exit(1)
    print("All dependencies checked.")

def get_latest_release_download_url(owner, repo, tag):
    """Fetches the download URL for a specific release's zip from GitHub."""
    api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/tags/{tag}"
    print(f"Fetching GitHub release info from {api_url} for tag \'{tag}\'...")
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        release_info = response.json()
        # Look for the source zipball (usually named source.zip or similar, or the repo name + .zip)
        zip_url = release_info.get("zipball_url")
        if zip_url:
            print(f"Found zipball URL: {zip_url}")
            return zip_url
        else:
            print(f"No zipball URL found for tag {tag}. Checking assets...")
            for asset in release_info.get("assets", []):
                if asset["name"].endswith(".zip"):
                    print(f"Found asset zip: {asset['browser_download_url']}")
                    return asset["browser_download_url"]
            print(f"No .zip archive found in release {tag} of {owner}/{repo}.")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching release info from GitHub: {e}")
        print("Please ensure the repository and tag are correct and you have an internet connection.")
        return None

def download_and_extract_archive():
    """Downloads and extracts the game archive into the SCRIPT_DIR."""
    # Check if the archive directory already exists and is not empty
    if os.path.exists(LOCAL_ARCHIVE_ROOT_DIR) and os.path.isdir(LOCAL_ARCHIVE_ROOT_DIR) and os.listdir(LOCAL_ARCHIVE_ROOT_DIR):
        print(f"Archive directory \'{ARCHIVE_DIR_NAME}\' already exists and is not empty. Skipping download and extraction.")
        return True

    print(f"Downloading archive from: {ARCHIVE_ZIP_URL}")
    zip_filename = os.path.join(SCRIPT_DIR, "temp_archive.zip")
    try:
        with requests.get(ARCHIVE_ZIP_URL, stream=True, timeout=300) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            block_size = 8192 # 8 KiB
            progress_bar = tqdm(total=total_size, unit='iB', unit_scale=True, desc="Downloading Archive")
            with open(zip_filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=block_size):
                    f.write(chunk)
                    progress_bar.update(len(chunk))
            progress_bar.close()
        print(f"Downloaded \'{zip_filename}\'.")

        print(f"Extracting archive to \'{SCRIPT_DIR}\' (stripping top-level directory if present)...")
        with zipfile.ZipFile(zip_filename, 'r') as zip_ref:
            # Assume GitHub zipballs have a single top-level directory (e.g., repo-name-tag/)
            # We want to extract its *contents* directly into SCRIPT_DIR.
            namelist = zip_ref.namelist()
            if not namelist:
                raise zipfile.BadZipFile("Zip archive is empty.")

            first_dir = namelist[0].split('/')[0] + '/' if '/' in namelist[0] else '' # Get the top-level dir name (e.g., 'repo-v1.0.0/')

            for member in namelist:
                if member.startswith(first_dir):
                    # Strip the top-level directory prefix
                    dest_path_suffix = member[len(first_dir):]
                    if not dest_path_suffix: # Skip the top-level directory itself
                        continue

                    # Construct the full destination path in SCRIPT_DIR
                    dest_path = os.path.join(SCRIPT_DIR, dest_path_suffix)

                    if member.endswith('/'): # It's a directory
                        os.makedirs(dest_path, exist_ok=True)
                    else: # It's a file
                        os.makedirs(os.path.dirname(dest_path), exist_ok=True) # Ensure parent dir exists
                        with zip_ref.open(member) as source, open(dest_path, "wb") as target:
                            shutil.copyfileobj(source, target)
        print("Archive extracted successfully.")

        # Clean up the temporary zip file
        if os.path.exists(zip_filename):
            os.remove(zip_filename)
            print(f"Removed temporary zip file: {zip_filename}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error downloading archive: {e}")
        print("Please check the archive URL and your internet connection.")
        return False
    except zipfile.BadZipFile as e:
        print(f"Error: Downloaded file is not a valid zip file or corrupted: {e}")
        if os.path.exists(zip_filename):
            os.remove(zip_filename)
        return False
    except Exception as e:
        print(f"An unexpected error occurred during archive download/extraction: {e}")
        return False

def check_internet_connection(host="8.8.8.8", port=53, timeout=3):
    """Checks for an active internet connection by trying to connect to a known host."""
    print("Checking internet connection...")
    try:
        socket.create_connection((host, port), timeout=timeout)
        print("  -> Internet connection is active.")
        return True
    except OSError:
        print("  -> No internet connection detected.")
        return False

# --- Setup Server ---
setup_complete_signal = threading.Event()
setup_server_instance = None # To hold the server object for graceful shutdown

class SetupHandler(http.server.SimpleHTTPRequestHandler):
    """Custom handler for the setup.html page, capable of signaling completion."""
    def do_GET(self):
        # Specific URL to signal setup completion
        if self.path == "/setup_complete":
            print("\nSetup completion signal received.")
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"Setup Complete. You can close this browser tab.")
            setup_complete_signal.set() # Signal the main thread
            # Request server shutdown (run in a new thread to avoid blocking response)
            if setup_server_instance:
                threading.Thread(target=setup_server_instance.shutdown).start()
        else:
            # Serve other files normally from the directory where setup.html resides (SCRIPT_DIR)
            # The base SimpleHTTPRequestHandler already uses self.directory set by partial.
            super().do_GET()

    def log_message(self, format, *args):
        # Suppress HTTP server logging for cleaner output in the console
        pass

def run_setup_server():
    """Starts a temporary HTTP server to serve setup.html."""
    global setup_server_instance
    if not os.path.exists(SETUP_HTML_TEMP_PATH):
        print(f"Error: setup.html not found at {SETUP_HTML_TEMP_PATH}. Cannot run setup.")
        return False

    print(f"\nStarting temporary setup server on http://localhost:{TEMP_SERVER_PORT}...")
    handler_class = partial(SetupHandler, directory=SCRIPT_DIR) # Serve from SCRIPT_DIR
    try:
        setup_server_instance = socketserver.TCPServer(("", TEMP_SERVER_PORT), handler_class)
        # Start server in a new thread so the main thread can wait for the signal
        server_thread = threading.Thread(target=setup_server_instance.serve_forever)
        server_thread.daemon = True # Allow main program to exit even if thread is running
        server_thread.start()

        # Open the setup page in the user's default browser
        setup_url = f"http://localhost:{TEMP_SERVER_PORT}/{SETUP_HTML_FILE_NAME}"
        print(f"Please open {setup_url} in your browser to complete initial setup.")
        webbrowser.open(setup_url)

        # Wait until the setup page signals completion
        setup_complete_signal.wait() # This will block until set() is called by SetupHandler

        print("Setup server shutting down.")
        # setup_server_instance.shutdown() is triggered by the handler, no need to call it directly here.
        server_thread.join(timeout=5) # Wait for the server thread to finish gracefully
        return True
    except OSError as e:
        print(f"ERROR: Could not start setup server on port {TEMP_SERVER_PORT}. Port might be in use. ({e})")
        print("Please close any applications using that port and try again.")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred while starting setup server: {e}")
        sys.exit(1)

def start_proxy_server(offline_mode=False):
    """Starts the main game proxy server."""
    print("\n--- Starting Flash Game Archive Proxy Server ---")

    # Dynamically import run_server from proxy_server.py
    # Add the directory containing proxy_server.py to sys.path temporarily
    sys.path.insert(0, os.path.dirname(PROXY_SERVER_SCRIPT))
    try:
        from proxy_server import run_server as run_proxy_server
    except ImportError as e:
        print(f"ERROR: Could not import \'proxy_server.py\': {e}")
        print("Please ensure proxy_server.py is in the \'python\' subdirectory relative to arcade.py.")
        sys.exit(1)
    finally:
        sys.path.pop(0) # Remove it after import

    print(f"Proxy server will serve games from: {LOCAL_ARCHIVE_ROOT_DIR}")
    print(f"Proxy port: {MAIN_PROXY_SERVER_PORT}")
    try:
        run_proxy_server(
            server_root=LOCAL_ARCHIVE_ROOT_DIR,
            proxy_enabled=not offline_mode,
            ntfy_reporting_enabled=not offline_mode,
            port=MAIN_PROXY_SERVER_PORT
        )
    except KeyboardInterrupt:
        print("\nLauncher stopped by user.")
    except Exception as e:
        print(f"An error occurred while running the main proxy server: {e}")
        print(f"You can manually start the server by navigating to \'{LOCAL_ARCHIVE_ROOT_DIR}\' and running \'python -m http.server {MAIN_PROXY_SERVER_PORT}\' if you wish to serve only local files, or \'python proxy_server.py\' from the \'python\' directory if you installed dependencies.")

def main():
    print("--- SpongeBob Flash Game Archiver Launcher ---")

    # 1. Install dependencies
    install_dependencies()

    # 2. Check for archive and download/extract if necessary
    print("\n--- Archive Setup ---")
    if not download_and_extract_archive():
        print("Failed to prepare the archive. Exiting.")
        sys.exit(1)
    else:
        print(f"Archive found/ready at \'{LOCAL_ARCHIVE_ROOT_DIR}\'.")

    # 3. Run initial setup (if setup.html exists in SCRIPT_DIR)
    if os.path.exists(SETUP_HTML_TEMP_PATH):
        print("\n--- Initial Setup Required ---")
        print("This seems to be your first run or the setup was not completed.")
        if not run_setup_server():
            print("Setup process failed or was interrupted. Exiting.")
            sys.exit(1)

        print("Setup completed successfully.")
        # Delete setup.html after completion
        try:
            os.remove(SETUP_HTML_TEMP_PATH)
            print(f"Deleted {SETUP_HTML_FILE_NAME}.")
        except Exception as e:
            print(f"Error deleting {SETUP_HTML_FILE_NAME}: {e}")
    else:
        print("\n--- Setup Complete (Previously) ---")

    # 4. Check internet connection for proxy mode
    print("\n--- Network Check ---")
    is_online = check_internet_connection()
    disable_proxy_fetching = False
    disable_ntfy_reporting = False

    if not is_online:
        print("\nWARNING: You are currently OFFLINE.")
        print("Some games might not be fully archived locally yet. Our smart proxy technology normally downloads them on-the-fly.")
        print("These downloads are typically one-time; subsequent access will load from your local machine.")
        print("However, it\'s recommended to always be connected, otherwise some games might act weirdly due to missing files.")
        user_choice = input("Do you wish to continue without an internet connection (this will disable asset downloading and reporting)? (y/N): ").strip().lower()
        if user_choice == 'y':
            disable_proxy_fetching = True
            disable_ntfy_reporting = True
            print("Proceeding in OFFLINE mode. Dynamic asset fetching and reporting disabled.")
        else:
            print("Exiting. Please connect to the internet to ensure full functionality.")
            sys.exit(0)
    else:
        print("Internet connection detected. Running in online mode (with asset downloading and reporting enabled).")

    # 5. Start the main proxy server
    start_proxy_server(offline_mode=disable_proxy_fetching) # Pass the state of proxy fetching

if __name__ == "__main__":
    main()
