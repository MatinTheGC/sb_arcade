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

class CachingProxyHandler(http.server.SimpleHTTPRequestHandler):
    server_root_path = None
    proxy_enabled = True
    ntfy_reporting_enabled = True

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

        print(f"[DEBUG] translate_path: url_path={self.path!r} -> local_path={final_path!r}")
        return final_path

def run_server(server_root, proxy_enabled=True, ntfy_reporting_enabled=True, port=PORT):
    """Sets up and runs the HTTP server."""

    CachingProxyHandler.server_root_path = server_root
    CachingProxyHandler.proxy_enabled = proxy_enabled
    CachingProxyHandler.ntfy_reporting_enabled = ntfy_reporting_enabled

    if not os.path.isdir(server_root):
        print(f"[ERROR] The server root directory was not found.")
        print(f"        Attempted path: {server_root}")
        print("        Please ensure the specified archive directory exists.")
        return

    # Create and start the server.
    with socketserver.TCPServer(("", port), CachingProxyHandler) as httpd:
        print(f"\n--- Caching Proxy Server Running ---")
        print(f"URL: http://localhost:{port}")
        print(f"Serving files from: {server_root}")
        if proxy_enabled:
            print(f"Any missing files requested by the browser will be downloaded on-the-fly.")
            if ntfy_reporting_enabled:
                print(f"Missing file URLs will be reported for archive completion.")
            else:
                print(f"Missing file URLs will NOT be reported.")
        else:
            print(f"Proxying is DISABLED. Only locally present files will be served.")

        print(f"Press Ctrl+C to stop the server.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer shutting down.")
            httpd.shutdown()

if __name__ == "__main__":
    # Example usage for standalone run:
    # Assuming 'flash_game_archive' is one level up from 'python' or in the same directory as this script.
    default_server_root = os.path.abspath(os.path.join(os.path.dirname(__file__), 'flash_game_archive'))
    run_server(server_root=default_server_root)