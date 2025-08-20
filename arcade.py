#!/usr/bin/env python3
"""
Combined launcher that:
 - preserves the original flash archive setup and proxy server behavior
 - attempts to download the archive via a magnet (Transmission RPC)
   optionally fetching a fresh magnet from a URL; falls back to hardcoded magnet
 - if magnet download doesn't make progress in 60s, falls back to downloading a ZIP
   and extracting the contained `flash_game_archive` folder to the sibling directory
 - fetches tracker lists from multiple online sources and writes a trackers.txt
 - starts a dedicated seeder subprocess that keeps seeding the folder via Transmission RPC
 - keeps the setup flow and creates a ".setupdone" sentinel instead of deleting setup.html

Note: This script requires Transmission daemon available and the Python package
`transmission-rpc`. It will attempt to pip-install required Python packages when missing.

"""

from __future__ import annotations
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
import json
from functools import partial
from tqdm import tqdm

# ------------------ Configuration (edit as needed) ------------------
GITHUB_ARCHIVE_REPO_OWNER = "TheSpongeBobCommunity"  # kept for legacy references
GITHUB_ARCHIVE_REPO_NAME = "flash-game-archive"
ARCHIVE_RELEASE_TAG = "v1.0.0"

# Hardcoded fallback magnet (user's original). Replace with your actual magnet if needed.
HARDCODED_MAGNET = "magnet:?xt=urn:btih:EXAMPLEHASH&dn=flash_game_archive"
# URL to try to fetch a fresh magnet (expected to return a plain magnet URI as text)
MAGNET_LOOKUP_URL = "https://example.com/current_magnet.txt"

# ZIP fallback (if magnet fails to start downloading within TIMEOUT_START_SECONDS)
ARCHIVE_ZIP_FALLBACK_URL = "https://example.com/flash_game_archive.zip"
TIMEOUT_START_SECONDS = 60

# Tracker sources to fetch (will be deduplicated)
TRACKER_SOURCES = [
    "https://raw.githubusercontent.com/ngosang/trackerslist/refs/heads/master/trackers_all.txt",
    "https://cf.trackerslist.com/all.txt",
    "https://ngosang.github.io/trackerslist/trackers_all.txt",
    "https://cdn.jsdelivr.net/gh/ngosang/trackerslist@master/trackers_all.txt",
]

# Paths and ports
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ARCHIVE_DIR_NAME = "flash_game_archive"
LOCAL_ARCHIVE_ROOT_DIR = os.path.join(SCRIPT_DIR, ARCHIVE_DIR_NAME)
SETUP_HTML_FILE_NAME = "setup.html"
SETUP_HTML_TEMP_PATH = os.path.join(SCRIPT_DIR, SETUP_HTML_FILE_NAME)
SETUPDONE_PATH = os.path.join(SCRIPT_DIR, ".setupdone")
PROXY_SERVER_SCRIPT = os.path.join(SCRIPT_DIR, "python", "proxy_server.py")
MAIN_PROXY_SERVER_PORT = 8004
TEMP_SERVER_PORT = 8005

# Transmission / seeding
TRANSMISSION_RPC_HOST = "127.0.0.1"
TRANSMISSION_RPC_PORT = 9091
TRANSMISSION_RPC_USER = "transmission"
TRANSMISSION_RPC_PASS = "transmission"
SEEDER_SCRIPT = os.path.join(SCRIPT_DIR, "_seeder_process.py")

# --------------------------------------------------------------------


def ensure_package_installed(pkg_name: str, import_name: str | None = None):
    """Ensure a package is installed in the running environment; try to pip install if missing."""
    import_name = import_name or pkg_name
    try:
        __import__(import_name)
        return True
    except Exception:
        print(f"Package '{pkg_name}' not installed; attempting to install via pip...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg_name])
            return True
        except Exception as e:
            print(f"Failed to install {pkg_name}: {e}")
            return False


# ------------------ Original helper functions (archive + setup) ------------------

def install_dependencies():
    """Installs necessary Python packages using pip."""
    print("Checking and installing Python dependencies...")
    required_packages = ["requests", "beautifulsoup4", "selenium-wire", "selenium", "tqdm", "transmission-rpc", "torf"]
    for package in required_packages:
        base = package.split('-')[0]
        try:
            __import__(base)
            print(f"  -> {package} is already installed.")
        except ImportError:
            print(f"  -> {package} not found. Installing...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                print(f"  -> {package} installed successfully.")
            except subprocess.CalledProcessError as e:
                print(f"  -> Error installing {package}: {e}")
                print("Please try running 'pip install -r requirements.txt' manually if this persists.")
                sys.exit(1)

    print("All dependencies checked.")


def check_internet_connection(url="https://google.com", timeout=3):
    print("Checking internet connection...")
    try:
        requests.get(url, timeout=timeout)
        print("  -> Internet connection is active.")
        return True
    except:
        print("  -> No internet connection detected.") 
        return False


# ------------------ Archive download / magnet logic ------------------


def fetch_magnet_from_url(url: str) -> str | None:
    """Fetch a magnet URI (raw text) from a provided URL. Returns the magnet string or None."""
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        txt = r.text.strip()
        if txt.startswith('magnet:'):
            print('Fetched magnet from URL:', url)
            return txt
        print('Fetched content but it did not look like a magnet:', txt[:80])
    except Exception as e:
        print('Failed to fetch magnet from', url, '-', e)
    return None


def download_zip_and_extract_flash_archive(zip_url: str, extract_target_parent: str = SCRIPT_DIR) -> bool:
    """Download ZIP and extract nested flash_game_archive folder to extract_target_parent/flash_game_archive."""
    tmp_zip = os.path.join(SCRIPT_DIR, 'temp_archive.zip')
    try:
        print('Downloading ZIP fallback from:', zip_url)
        with requests.get(zip_url, stream=True, timeout=300) as r:
            r.raise_for_status()
            total = int(r.headers.get('content-length', 0) or 0)
            with open(tmp_zip, 'wb') as f, tqdm(total=total, unit='iB', unit_scale=True, desc='Downloading ZIP') as pbar:
                for chunk in r.iter_content(chunk_size=8192):
                    if not chunk:
                        continue
                    f.write(chunk)
                    pbar.update(len(chunk))
        print('Downloaded ZIP to', tmp_zip)

        with zipfile.ZipFile(tmp_zip, 'r') as z:
            # find member that contains flash_game_archive/ at some depth
            candidates = [m for m in z.namelist() if m.replace('\\', '/').endswith('/') or True]
            # We'll extract everything, then move the nested flash_game_archive if found
            z.extractall(SCRIPT_DIR)

        # Search extracted tree for a folder named flash_game_archive
        found = None
        for root, dirs, files in os.walk(SCRIPT_DIR):
            if ARCHIVE_DIR_NAME in dirs:
                candidate = os.path.join(root, ARCHIVE_DIR_NAME)
                # Don't pick the already-correct path if it exists
                if os.path.abspath(candidate) == os.path.abspath(LOCAL_ARCHIVE_ROOT_DIR):
                    found = candidate
                    break
                found = candidate
                break

        if not found:
            print('Could not find', ARCHIVE_DIR_NAME, 'inside downloaded ZIP extraction. Extraction root:', SCRIPT_DIR)
            return False

        # If found and not at desired location, move it
        if os.path.abspath(found) != os.path.abspath(LOCAL_ARCHIVE_ROOT_DIR):
            if os.path.exists(LOCAL_ARCHIVE_ROOT_DIR):
                print('Removing existing archive dir at', LOCAL_ARCHIVE_ROOT_DIR)
                shutil.rmtree(LOCAL_ARCHIVE_ROOT_DIR)
            print('Moving', found, 'to', LOCAL_ARCHIVE_ROOT_DIR)
            shutil.move(found, LOCAL_ARCHIVE_ROOT_DIR)
        else:
            print('Archive already in correct location:', LOCAL_ARCHIVE_ROOT_DIR)

        # clean up tmp zip
        try:
            os.remove(tmp_zip)
        except Exception:
            pass
        return True
    except Exception as e:
        print('Failed to download or extract ZIP fallback:', e)
        try:
            if os.path.exists(tmp_zip):
                os.remove(tmp_zip)
        except Exception:
            pass
        return False


# ------------------ Trackers fetching ------------------

def fetch_and_save_trackers(out_path: str):
    print('Fetching tracker lists from known sources...')
    trackers = []
    for url in TRACKER_SOURCES:
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            for line in r.text.splitlines():
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                trackers.append(line)
            print('  -> fetched', len(r.text.splitlines()), 'lines from', url)
        except Exception as e:
            print('  -> failed to fetch from', url, '-', e)

    # deduplicate and save
    unique = []
    seen = set()
    for t in trackers:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    print('Total unique trackers:', len(unique))
    try:
        with open(out_path, 'w', encoding='utf-8') as f:
            for t in unique:
                f.write(t + '\n')
        print('Trackers saved to', out_path)
        return True
    except Exception as e:
        print('Failed to save trackers to', out_path, '-', e)
        return False


# ------------------ Transmission integration (magnet / torrent add + seeder) ------------------

def ensure_transmission_client():
    try:
        import transmission_rpc
    except Exception:
        print('transmission-rpc missing; attempting to install...')
        if not ensure_package_installed('transmission-rpc'):
            raise RuntimeError('transmission-rpc is required but could not be installed')
        import transmission_rpc

    client = transmission_rpc.Client(host=TRANSMISSION_RPC_HOST, port=TRANSMISSION_RPC_PORT,
                                     username=TRANSMISSION_RPC_USER, password=TRANSMISSION_RPC_PASS)
    return client


def add_magnet_and_wait_for_start(client, magnet: str, timeout: int = TIMEOUT_START_SECONDS) -> tuple[bool, object | None]:
    """Add magnet to Transmission and wait up to timeout seconds for initial activity.
    Returns (started_flag, torrent_obj_or_None).
    """
    try:
        print('Adding magnet to Transmission RPC...')
        tor = client.add_torrent(magnet)
    except Exception as e:
        print('Failed to add magnet via RPC:', e)
        return False, None

    # Poll for short time for progress or peers
    start = time.time()
    while time.time() - start < timeout:
        try:
            # refresh torrent state
            tlist = client.get_torrents()
            # try to find our torrent by hash or name; match magnet hash if available
            for t in tlist:
                if getattr(t, 'magnet_uri', None) and magnet.split('&')[0] in getattr(t, 'magnet_uri', ''):
                    tor_obj = t
                    break
                # fallback name match
                if getattr(t, 'name', None) and 'flash_game_archive' in getattr(t, 'name', '').lower():
                    tor_obj = t
                    break
            else:
                tor_obj = None

            if tor_obj:
                percent = getattr(tor_obj, 'progress', None) or getattr(tor_obj, 'percentDone', None) or 0
                # Some transmission-rpc versions expose percent_done as float 0.0-1.0 or percentDone as 0-100
                try:
                    if percent and percent < 1 and percent > 0:  # fraction
                        print('Download started; progress:', percent)
                        return True, tor_obj
                    if percent and percent >= 1:  # percent style
                        print('Download started; progress percent:', percent)
                        return True, tor_obj
                except Exception:
                    pass

                # Also check peers or status
                st = getattr(tor_obj, 'status', None)
                if st and st.lower() not in ('stopped', 'error'):
                    print('Torrent status indicates activity:', st)
                    return True, tor_obj
        except Exception as e:
            print('Error while polling torrent status:', e)
        time.sleep(1)

    print(f'No download activity detected within {timeout} seconds for magnet. Falling back to ZIP fallback later.')
    return False, None


def write_seeder_script(seeder_script_path: str):
    """Write a tiny helper script that will run as a separate process and keep seeding the archive via Transmission RPC."""
    code = f"""#!/usr/bin/env python3
from time import sleep
import sys
import os
try:
    import transmission_rpc
except Exception:
    print('seeder: transmission-rpc missing; seeder exiting')
    sys.exit(1)

host = '{TRANSMISSION_RPC_HOST}'
port = {TRANSMISSION_RPC_PORT}
user = '{TRANSMISSION_RPC_USER}'
pw = '{TRANSMISSION_RPC_PASS}'
archive_path = r'{LOCAL_ARCHIVE_ROOT_DIR}'

client = transmission_rpc.Client(host=host, port=port, username=user, password=pw)
print('seeder: connected to Transmission RPC at', host, port)

# Ensure any .torrent files in archive_path are added and set to seed
for root, dirs, files in os.walk(archive_path):
    for f in files:
        if f.endswith('.torrent'):
            p = os.path.join(root, f)
            try:
                print('seeder: adding torrent file', p)
                client.add_torrent(p, download_dir=archive_path)
            except Exception as e:
                print('seeder: failed to add', p, e)

# Keep the process alive; Transmission daemon handles seeding in background.
while True:
    try:
        sleep(30)
    except KeyboardInterrupt:
        break
"""
    try:
        with open(seeder_script_path, 'w', encoding='utf-8') as f:
            f.write(code)
        os.chmod(seeder_script_path, 0o755)
        print('Wrote seeder helper script to', seeder_script_path)
        return True
    except Exception as e:
        print('Failed to write seeder script:', e)
        return False


def start_seeder_subprocess(seeder_script_path: str):
    """Start the seeder helper script as a detached subprocess so it continues after this script exits."""
    if not os.path.exists(seeder_script_path):
        if not write_seeder_script(seeder_script_path):
            print('Could not create seeder helper; skipping seeder subprocess.')
            return False

    if sys.platform == 'win32':
        CREATE_NO_WINDOW = 0x08000000
        DETACHED_PROCESS = 0x00000008
        try:
            proc = subprocess.Popen([sys.executable, seeder_script_path], creationflags=DETACHED_PROCESS | CREATE_NO_WINDOW)
            print('Started seeder subprocess (detached) with PID', getattr(proc, 'pid', None))
            return True
        except Exception as e:
            print('Failed to start detached seeder on Windows:', e)
            return False
    else:
        try:
            proc = subprocess.Popen([sys.executable, seeder_script_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, close_fds=True)
            print('Started seeder subprocess (unix-style) with PID', getattr(proc, 'pid', None))
            return True
        except Exception as e:
            print('Failed to start seeder subprocess:', e)
            return False


# ------------------ Setup server and proxy server logic (kept from original) ------------------
setup_complete_signal = threading.Event()
setup_server_instance = None

class SetupHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/setup_complete":
            print("\nSetup completion signal received.")
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"Setup Complete. You can close this browser tab.")
            setup_complete_signal.set()
            if setup_server_instance:
                threading.Thread(target=setup_server_instance.shutdown).start()
        else:
            super().do_GET()
    def log_message(self, format, *args):
        pass


def run_setup_server():
    global setup_server_instance
    if not os.path.exists(SETUP_HTML_TEMP_PATH):
        print(f"Error: setup.html not found at {SETUP_HTML_TEMP_PATH}. Cannot run setup.")
        return False
    print(f"\nStarting temporary setup server on http://localhost:{TEMP_SERVER_PORT}...")
    handler_class = partial(SetupHandler, directory=SCRIPT_DIR)
    try:
        setup_server_instance = socketserver.TCPServer(("", TEMP_SERVER_PORT), handler_class)
        server_thread = threading.Thread(target=setup_server_instance.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        setup_url = f"http://localhost:{TEMP_SERVER_PORT}/{SETUP_HTML_FILE_NAME}"
        print(f"Please open {setup_url} in your browser to complete initial setup.")
        webbrowser.open(setup_url)
        setup_complete_signal.wait()
        print("Setup server shutting down.")
        server_thread.join(timeout=5)
        return True
    except OSError as e:
        print(f"ERROR: Could not start setup server on port {TEMP_SERVER_PORT}. Port might be in use. ({e})")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred while starting setup server: {e}")
        sys.exit(1)


def start_proxy_server(offline_mode=False):
    print("\n--- Starting Flash Game Archive Proxy Server ---")
    sys.path.insert(0, os.path.dirname(PROXY_SERVER_SCRIPT))
    try:
        from proxy_server import run_server as run_proxy_server
    except ImportError as e:
        print(f"ERROR: Could not import 'proxy_server.py': {e}")
        print("Please ensure proxy_server.py is in the 'python' subdirectory relative to arcade.py.")
        sys.exit(1)
    finally:
        sys.path.pop(0)

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
        print(f"You can manually start the server by navigating to '{LOCAL_ARCHIVE_ROOT_DIR}' and running 'python -m http.server {MAIN_PROXY_SERVER_PORT}' if you wish to serve only local files, or 'python proxy_server.py' from the 'python' directory if you installed dependencies.")


# ------------------ Main flow combining everything ------------------

def main():
    print("--- SpongeBob Flash Game Archiver Launcher (with Transmission seeding) ---")
    
        # 6) Network check and start proxy
    is_online = check_internet_connection()
    disable_proxy_fetching = False
    disable_ntfy_reporting = False

    if not is_online:
        print('\nWARNING: You are currently OFFLINE.')
        user_choice = input("Do you wish to continue without an internet connection (this will disable asset downloading and reporting)? (y/N): ").strip().lower()
        if user_choice == 'y':
            disable_proxy_fetching = True
            disable_ntfy_reporting = True
            print('Proceeding in OFFLINE mode. Dynamic asset fetching and reporting disabled.')
        else:
            print('Exiting. Please connect to the internet to ensure full functionality.')
            sys.exit(0)
    else:
        print('Internet connection detected. Running in online mode (with asset downloading and reporting enabled).')

    # 1) Ensure Python deps
    install_dependencies()

    # 2) Prepare trackers file
    trackers_path = os.path.join(SCRIPT_DIR, 'trackers.txt')
    fetch_and_save_trackers(trackers_path)

    # 3) Try to fetch magnet from URL, else fall back to hardcoded
    magnet = None
    m = fetch_magnet_from_url(MAGNET_LOOKUP_URL)
    if m:
        magnet = m
    else:
        print('Using hardcoded fallback magnet.')
        magnet = HARDCODED_MAGNET

    # 4) If archive already present, skip magnet/torrent download
    if os.path.exists(LOCAL_ARCHIVE_ROOT_DIR) and os.path.isdir(LOCAL_ARCHIVE_ROOT_DIR) and os.listdir(LOCAL_ARCHIVE_ROOT_DIR):
        print(f"Archive '{ARCHIVE_DIR_NAME}' already exists at {LOCAL_ARCHIVE_ROOT_DIR}. Skipping download.")
    else:
        # Attempt magnet download via Transmission
        try:
            client = ensure_transmission_client()
            started, tor_obj = add_magnet_and_wait_for_start(client, magnet, timeout=TIMEOUT_START_SECONDS)
            if started:
                print('Magnet torrent appears to have started. Waiting until files are present or Transmission has created content...')
                # Wait for a short grace period for files to appear under download-dir
                time.sleep(5)
                # We assume Transmission will download into its configured download dir; if that directory
                # is not LOCAL_ARCHIVE_ROOT_DIR we cannot easily move it here. For robust control, you should
                # set download-dir explicitly when adding the torrent. Re-add with download_dir pointing to SCRIPT_DIR.
                try:
                    # re-add with download_dir set to SCRIPT_DIR to ensure files are placed under our control
                    client.remove_torrent(tor_obj.id, delete_data=False)
                except Exception:
                    pass
                try:
                    tor2 = client.add_torrent(magnet, download_dir=SCRIPT_DIR)
                    print('Re-added torrent with download_dir set to', SCRIPT_DIR)
                except Exception:
                    pass
                # Start seeder subprocess that will add any .torrent files and keep running
                start_seeder_subprocess(SEEDER_SCRIPT)
            else:
                # Magnet didn't start downloading within timeout; fallback to ZIP
                print('Magnet failed to start within timeout; falling back to ZIP download/extract...')
                ok = download_zip_and_extract_flash_archive(ARCHIVE_ZIP_FALLBACK_URL)
                if not ok:
                    print('ZIP fallback failed. Exiting.')
                    sys.exit(1)
                # After extraction, start seeder (add any .torrent files and keep seeding)
                start_seeder_subprocess(SEEDER_SCRIPT)
        except Exception as e:
            print('Error while attempting magnet-based download:', e)
            print('Attempting ZIP fallback...')
            if not download_zip_and_extract_flash_archive(ARCHIVE_ZIP_FALLBACK_URL):
                print('ZIP fallback failed. Exiting.')
                sys.exit(1)
            start_seeder_subprocess(SEEDER_SCRIPT)

    # 5) Run setup server if setup.html exists (first-run)
    if os.path.exists(SETUP_HTML_TEMP_PATH) and not os.path.exists(SETUPDONE_PATH):
        print('\n--- Initial Setup Required ---')
        if not run_setup_server():
            print('Setup process failed or was interrupted. Exiting.')
            sys.exit(1)
        print('Setup completed successfully.')
        # Instead of deleting setup.html, create a .setupdone sentinel
        try:
            open(SETUPDONE_PATH, 'a').close()
            print('Created setup done sentinel at', SETUPDONE_PATH)
        except Exception as e:
            print('Failed to create setup done sentinel:', e)
    else:
        print('\n--- Setup Complete (Previously) ---')

    # 7) Start proxy server (this call will block until stopped)
    start_proxy_server(offline_mode=disable_proxy_fetching)


if __name__ == '__main__':
    main()
