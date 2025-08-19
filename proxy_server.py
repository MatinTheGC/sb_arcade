import http.server
import socketserver
import os
import requests
from urllib.parse import urljoin
import mimetypes

# --- Configuration ---
PORT = 8004
# The server will root itself in the 'flash_game_archive/flash_game_archive' directory,
# which should be in the same directory as this script.
SERVER_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), 'flash_game_archive'))
REMOTE_BASE_URL = "https://www.thesbcommunity.com/"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"


class CachingProxyHandler(http.server.SimpleHTTPRequestHandler):
    """
    A custom request handler that serves local files if they exist.
    If a file is not found locally, it attempts to download it from the
    original website, save it to the correct local path, and then serve it.
    """
    def do_GET(self):
        """Handle GET requests."""
        # translate_path uses the current working directory, which we set before starting the server.
        local_path = self.translate_path(self.path)

        # Case 1: The file exists locally. Serve it immediately.
        if os.path.exists(local_path) and os.path.isfile(local_path):
            print(f"[LOCAL] Serving: {self.path}")
            super().do_GET()
            return

        # Let the base handler deal with directory listing requests.
        if os.path.isdir(local_path):
            print(f"[LOCAL] Handling directory request: {self.path}")
            super().do_GET()
            return

        # Case 2: The file does not exist. Try to fetch it from the remote server.
        print(f"[PROXY] Not found locally: {self.path}. Attempting to download...")

        # Construct the full remote URL. self.path starts with '/', so we strip it.
        remote_url = urljoin(REMOTE_BASE_URL, self.path.lstrip('/'))
        print(f"        Fetching from: {remote_url}")

        try:
            # Make the request to the remote server.
            headers = {'User-Agent': USER_AGENT}
            response = requests.get(remote_url, headers=headers, stream=True, timeout=30)
            response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)

            # Successfully fetched, now get the content.
            content = response.content

            # Ensure the local directory structure exists before saving.
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            # Save the file to the local path for future requests.
            with open(local_path, 'wb') as f:
                f.write(content)
            print(f"        Success! Saved to '{os.path.relpath(local_path, SERVER_ROOT)}'")

            # Now, serve the newly downloaded file to the browser.
            self.send_response(200)
            content_type = mimetypes.guess_type(local_path)[0] or 'application/octet-stream'
            self.send_header('Content-type', content_type)
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        except requests.exceptions.RequestException as e:
            # Case 3: The file couldn't be fetched from the remote server either.
            print(f"[PROXY] FAILED to fetch {remote_url}: {e}")
            self.send_error(404, "File not found locally or on the remote server.")

def run_server():
    """Sets up and runs the HTTP server."""
    # SimpleHTTPRequestHandler serves files relative to the current working directory.
    # We must change to our intended root directory.
    try:
        os.chdir(SERVER_ROOT)
        print(f"Serving files from: {os.getcwd()}")
    except FileNotFoundError:
        print(f"[ERROR] The server root directory was not found.")
        print(f"        Attempted path: {SERVER_ROOT}")
        print("        Please ensure the 'flash_game_archive/flash_game_archive' directory exists")
        print("        and that this script is located in the parent 'python' directory.")
        return

    # Create and start the server.
    with socketserver.TCPServer(("", PORT), CachingProxyHandler) as httpd:
        print(f"\n--- Caching Proxy Server Running ---")
        print(f"URL: http://localhost:{PORT}")
        print(f"Any missing files requested by the browser will be downloaded on-the-fly.")
        print(f"Press Ctrl+C to stop the server.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer shutting down.")
            httpd.shutdown()

if __name__ == "__main__":
    run_server()