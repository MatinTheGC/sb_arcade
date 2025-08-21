import http.server
import socketserver
import os
import requests
from urllib.parse import urljoin
import mimetypes

# --- Configuration ---
PORT = 8004
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
REMOTE_BASE_URL = "https://www.thesbcommunity.com/"


from urllib.parse import unquote
import posixpath
import shutil
import threading

# NTFY reporting endpoint. Defaults to the requested topic if not provided
DEFAULT_NTFY = 'https://ntfy.sh/SpongeBob404'
NTFY_ENDPOINT = os.environ.get('SB_NTFY_URL', DEFAULT_NTFY).strip()

# Optional upstream proxy (try this before REMOTE_BASE_URL). Leave empty to skip.
UPSTREAM_PROXY_URL = os.environ.get('SB_UPSTREAM_PROXY', '').strip()


def report_ntfy_async(message: str, title: str = "Missing asset found"):
    """Best-effort non-blocking POST to NTFY endpoint with a short message."""
    if not NTFY_ENDPOINT:
        return
    def _send():
        try:
            # Send plain text body; do not raise on failure
            requests.post(NTFY_ENDPOINT, data=message.encode('utf-8'), timeout=5, headers={'Title': title})
        except Exception:
            pass
    threading.Thread(target=_send, daemon=True).start()

class CachingProxyHandler(http.server.SimpleHTTPRequestHandler):
    server_root_path = None
    proxy_enabled = True
    ntfy_reporting_enabled = True

    def fetch_and_cache_remote(self, base_url: str, rel_path: str, full_local_path: str) -> bool:
        """Attempt to fetch the remote asset by joining base_url + rel_path and save it to full_local_path.
        Returns True if fetched and saved, False otherwise.
        """
        if not base_url:
            return False
        # Build remote URL using posix join semantics
        remote_url = urljoin(base_url, rel_path.lstrip('/'))
        headers = {'User-Agent': USER_AGENT}
        tmp_path = None
        try:
            r = requests.get(remote_url, headers=headers, stream=True, timeout=10)
            if r.status_code != 200:
                return False
            # Ensure local directory exists
            os.makedirs(os.path.dirname(full_local_path), exist_ok=True)
            # Stream to a temp file then move
            tmp_path = full_local_path + '.download'
            with open(tmp_path, 'wb') as fh:
                shutil.copyfileobj(r.raw, fh)
            os.replace(tmp_path, full_local_path)
            return True
        except Exception:
            # Quietly fail and cleanup
            try:
                if tmp_path and os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            return False

    def translate_path(self, path):
        """
        Translate a URL path to a local filesystem path under self.server_root_path.
        This is URL-aware and protects against directory escapes.
        """
        # Strip query/fragment
        path = path.split('?', 1)[0].split('#', 1)[0]
        # URL-unquote
        path = unquote(path)

        # Remove leading slash so split yields components (posix style)
        if path.startswith('/'):
            path = path[1:]

        # Normpath using posix rules (handles repeated slashes, etc.)
        path = posixpath.normpath(path)

        # Break into safe components, ignore '.' and '..'
        parts = [p for p in path.split('/') if p and p not in (os.curdir, os.pardir)]

        # Ensure server_root_path is absolute
        server_root = os.path.abspath(self.server_root_path)

        # Construct final filesystem path
        final_path = os.path.join(server_root, *parts) if parts else server_root
        final_path = os.path.normpath(final_path)

        # Security check: ensure final_path is inside server_root
        try:
            if os.path.commonpath([server_root, final_path]) != server_root:
                # Something attempted to escape the root — return the root instead.
                final_path = server_root
        except Exception:
            # Fallback: ensure absolute path is used
            final_path = server_root

        return final_path

    def do_GET(self):
        # Try to serve locally first (files or directories)
        local_path = self.translate_path(self.path)
        if os.path.exists(local_path):
            # If the path exists locally (file or directory), let the base handler serve it
            return super().do_GET()

        # If proxying disabled, return 404
        if not self.proxy_enabled:
            self.send_error(404, "Not Found")
            return

        # Attempt to fetch from upstream proxy (if configured) then REMOTE_BASE_URL
        rel_path = self.path.split('?', 1)[0].lstrip('/')
        sources = []
        if UPSTREAM_PROXY_URL:
            sources.append(UPSTREAM_PROXY_URL)
        sources.append(REMOTE_BASE_URL)

        fetched = False
        fetched_from = None
        for src in sources:
            if self.fetch_and_cache_remote(src, rel_path, local_path):
                fetched = True
                fetched_from = src
                break

        if fetched:
            # Notify only when a remote source provided the file and local lacked it
            if self.ntfy_reporting_enabled and fetched_from:
                try:
                    # Build the reported URL (which the upstream provided)
                    reported_url = urljoin(fetched_from, rel_path)
                    report_ntfy_async(reported_url, title="Archive: missing file fetched")
                except Exception:
                    pass
            # Serve the newly cached file
            return super().do_GET()
        else:
            # Nothing found upstream — do not notify (per requirements)
            self.send_error(404, "Not Found")

def run_server(server_root, proxy_enabled=True, ntfy_reporting_enabled=True, port=PORT):
    """Sets up and runs the HTTP server."""

    CachingProxyHandler.server_root_path = server_root
    CachingProxyHandler.proxy_enabled = proxy_enabled
    CachingProxyHandler.ntfy_reporting_enabled = ntfy_reporting_enabled
    
    print(f"URL: http://localhost:{port}")

    if not os.path.isdir(server_root):
        print(f"[ERROR] The server root directory was not found.")
        return

    # Create and start the server. Use a threaded server to handle concurrent requests.
    with socketserver.ThreadingTCPServer(("", port), CachingProxyHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            httpd.shutdown()

if __name__ == "__main__":
    # Example usage for standalone run:
    # Assuming 'flash_game_archive' is one level up from 'python' or in the same directory as this script.
    default_server_root = os.path.abspath(os.path.join(os.path.dirname(__file__), 'flash_game_archive'))
    run_server(server_root=default_server_root)