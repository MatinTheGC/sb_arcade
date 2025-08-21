#!/usr/bin/env python3
"""Simplified launcher that assumes the local archive folder `flash_game_archive`
is already present. All torrenting/ZIP download/seeder logic has been removed.

Behavior:
 - On first-run (when `setup.html` exists and `.setupdone` does not), the script
   runs a minimal HTTP server on the main proxy port that redirects all requests
   to `setup.html` until the user completes setup (the page should call
   /setup_complete). This forces the user to finish setup before any other
   content can be served.
 - After setup is completed the script creates a `.setupdone` sentinel and starts
   the proxy server to serve the local `flash_game_archive` folder (no remote
   fetching).
"""

from __future__ import annotations
import os
import sys
import threading
import http.server
import socketserver
import webbrowser
from functools import partial

# --- Configuration ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ARCHIVE_DIR_NAME = "flash_game_archive"
LOCAL_ARCHIVE_ROOT_DIR = os.path.join(SCRIPT_DIR, ARCHIVE_DIR_NAME)
SETUP_HTML_FILE_NAME = os.path.join(ARCHIVE_DIR_NAME, "setup.html")
SETUP_HTML_TEMP_PATH = os.path.join(SCRIPT_DIR, SETUP_HTML_FILE_NAME)
SETUPDONE_PATH = os.path.join(SCRIPT_DIR, ".setupdone")
PROXY_SERVER_SCRIPT = os.path.join(SCRIPT_DIR, "proxy_server.py")
MAIN_PROXY_SERVER_PORT = 8004

# Tracker sources are kept for backwards compatibility but not required
TRACKER_SOURCES = [
    "https://raw.githubusercontent.com/ngosang/trackerslist/refs/heads/master/trackers_all.txt",
    "https://cf.trackerslist.com/all.txt",
    "https://ngosang.github.io/trackerslist/trackers_all.txt",
    "https://cdn.jsdelivr.net/gh/ngosang/trackerslist@master/trackers_all.txt",
]


def check_internet_connection() -> bool:
    """Returns True if internet connection is available."""
    try:
        import requests
        requests.get("https://google.com", timeout=3)
        return True
    except Exception:
        return False

def _ensure_dependencies_from_requirements() -> bool:
    """Minimal runtime dependency check. Return True if required packages are importable."""
    try:
        import requests  # type: ignore
        from tqdm import tqdm  # type: ignore
        return True
    except Exception:
        print('Missing third-party packages (requests/tqdm). Please run: python -m pip install -r requirements.txt')
        return False


def fetch_and_save_trackers(out_path: str):
    try:
        import requests
    except Exception:
        print('requests not available; skipping tracker fetch')
        return False

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
    try:
        with open(out_path, 'w', encoding='utf-8') as f:
            for t in unique:
                f.write(t + '\n')
        print('Trackers saved to', out_path)
        return True
    except Exception as e:
        print('Failed to save trackers to', out_path, '-', e)
        return False


# ------------------ Setup server logic ------------------
setup_complete_signal = threading.Event()
setup_server_instance = None


class SetupHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # If the browser sends the explicit completion signal, mark setup done
        if self.path == "/setup_complete":
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"Setup Complete. You can close this browser tab.")
            setup_complete_signal.set()
            if setup_server_instance:
                threading.Thread(target=setup_server_instance.shutdown).start()
            return

        # While .setupdone doesn't exist, force serving the setup page only
        if not os.path.exists(SETUPDONE_PATH):
            try:
                with open(SETUP_HTML_TEMP_PATH, 'rb') as fh:
                    content = fh.read()
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            except Exception as e:
                self.send_error(500, f"Failed to read setup file: {e}")
            return

        # Once setup done, behave like a normal file server
        super().do_GET()

    def log_message(self, format, *args):
        # silence access logs
        pass


def run_setup_server():
    global setup_server_instance
    if not os.path.exists(SETUP_HTML_TEMP_PATH):
        print(f"Error: setup.html not found at {SETUP_HTML_TEMP_PATH}. Cannot run setup.")
        return False
    print(f"\nStarting setup server on http://localhost:{MAIN_PROXY_SERVER_PORT}... (setup required)")
    handler_class = partial(SetupHandler, directory=SCRIPT_DIR)
    try:
        setup_server_instance = socketserver.TCPServer(("", MAIN_PROXY_SERVER_PORT), handler_class)
        server_thread = threading.Thread(target=setup_server_instance.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        setup_url = f"http://localhost:{MAIN_PROXY_SERVER_PORT}/{SETUP_HTML_FILE_NAME}"
        print(f"Please open {setup_url} in your browser to complete initial setup.")
        webbrowser.open(setup_url)
        setup_complete_signal.wait()
        print("Setup server shutting down...")
        setup_server_instance.shutdown()
        setup_server_instance.server_close()
        server_thread.join(timeout=5)
        # Add a small delay to ensure the socket is fully released
        import time
        time.sleep(1)
        return True
    except OSError as e:
        print(f"ERROR: Could not start setup server on port {MAIN_PROXY_SERVER_PORT}. Port might be in use. ({e})")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred while starting setup server: {e}")
        sys.exit(1)


def start_proxy_server(offline_mode=False):
    print("\n--- Starting Flash Game Archive Proxy Server ---")
    # Import the project's proxy_server module from the script directory
    sys.path.insert(0, os.path.dirname(PROXY_SERVER_SCRIPT))
    try:
        from proxy_server import run_server as run_proxy_server
    except ImportError as e:
        print(f"ERROR: Could not import 'proxy_server.py': {e}")
        print("Please ensure proxy_server.py is next to arcade.py.")
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
            port=MAIN_PROXY_SERVER_PORT,
        )
    except KeyboardInterrupt:
        print("\nLauncher stopped by user.")
    except Exception as e:
        print(f"An error occurred while running the main proxy server: {e}")
        print(f"You can manually start the server by navigating to '{LOCAL_ARCHIVE_ROOT_DIR}' and running 'python -m http.server {MAIN_PROXY_SERVER_PORT}' if you wish to serve only local files.")


def main():
    print("--- SpongeBob Flash Game Archive Launcher (assumes archive already present) ---")

    if not _ensure_dependencies_from_requirements():
        sys.exit(1)
        
    # Check internet connectivity first
    has_internet = check_internet_connection()
    print("Internet connection:", "available" if has_internet else "not available")
    
    # Run version check
    try:
        import check_version
        if not check_version.main(has_internet):
            sys.exit(1)  # Exit if update is required
    except ImportError:
        print("Warning: check_version.py not found, skipping version check.")

    # Note: tracker fetching is disabled in this launcher (not used anymore)
    # Trackers list is preserved on disk if you need it, but we won't fetch it.

    # Verify archive exists
    if not (os.path.exists(LOCAL_ARCHIVE_ROOT_DIR) and os.path.isdir(LOCAL_ARCHIVE_ROOT_DIR) and os.listdir(LOCAL_ARCHIVE_ROOT_DIR)):
        # Provide a human-readable HTML file with instructions and open it in the user's browser
        msg = f"""
        <html>
        <head><meta charset='utf-8'><title>Archive Missing — SpongeBob Flash Game Archive</title></head>
        <body style='font-family:Arial,Helvetica,sans-serif;line-height:1.5;padding:30px'>
        <h1>Archive folder not found</h1>
        <p>The required <code>flash_game_archive</code> folder was not found next to <code>arcade.py</code>.</p>
        <p>This launcher no longer downloads the archive automatically. Please obtain the archive (for example: by downloading the provided ZIP, or by using the magnet/torrent you received together with this launcher) and place the <strong>flash_game_archive</strong> folder next to <code>arcade.py</code>.</p>
        <h2>Quick steps</h2>
        <ol>
            <li>Unpack the supplied archive so a folder named <code>flash_game_archive</code> sits next to <code>arcade.py</code>.</li>
            <li>Ensure the folder contains the <code>index.html</code> and <code>games/</code> subfolder.</li>
            <li>Rerun this script: <code>python arcade.py</code>.</li>
        </ol>
        <p>If you received a magnet/torrent, the author suggests placing the archive and the launcher together when you distribute them; seeding is optional.</p>
        <p style='margin-top:20px'>After fixing the archive placement, re-run this launcher. You can close this page when ready.</p>
        </body>
        </html>
        """
        try:
            instr_path = os.path.join(SCRIPT_DIR, 'MISSING_ARCHIVE_INSTRUCTIONS.html')
            with open(instr_path, 'w', encoding='utf-8') as fh:
                fh.write(msg)
            file_url = 'file://' + os.path.abspath(instr_path).replace('\\', '/')
            print(f"Archive missing. Opening instructions in your browser: {file_url}")
            webbrowser.open(file_url)
        except Exception as e:
            print(f"ERROR: Archive directory '{LOCAL_ARCHIVE_ROOT_DIR}' not found or empty.")
            print('Also failed to create/open the instructions page:', e)
        sys.exit(1)

    # Force initial setup if needed. The setup server runs on the main proxy port and will block other requests
    if os.path.exists(SETUP_HTML_TEMP_PATH) and not os.path.exists(SETUPDONE_PATH):
        print('\n--- Initial Setup Required ---')
        if not run_setup_server():
            print('Setup process failed or was interrupted. Exiting.')
            sys.exit(1)
        print('Setup completed successfully.')
        try:
            open(SETUPDONE_PATH, 'a').close()
            print('Created setup done sentinel at', SETUPDONE_PATH)
        except Exception as e:
            print('Failed to create setup done sentinel:', e)
            sys.exit(1)
    else:
        print('\n--- Setup Complete (Previously) ---')

    # Start proxy server to serve the local archive (allow remote fetching and NTFY reporting)
    start_proxy_server(offline_mode=False)


if __name__ == '__main__':
    main()
