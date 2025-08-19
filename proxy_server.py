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


class CachingProxyHandler(http.server.SimpleHTTPRequestHandler):
    """
    A custom request handler that serves local files if they exist.
    If a file is not found locally, it attempts to download it from the
    original website, save it to the correct local path, and then serve it.
    """
    # Class attributes to be set by the server runner
    server_root_path = None
    proxy_enabled = True
    ntfy_reporting_enabled = True

    def translate_path(self, path):
        """Translate a /-separated PATH to the local filename syntax."""
        # Use the configured server_root_path instead of the current working directory
        path = path.split('?', 1)[0]
        path = path.split('#', 1)[0]
        # Don't forget explicit quoting in case raw path contains %-escapes
        path = os.path.normpath(requests.utils.unquote(path))
        words = path.split('/')
        words = filter(None, words)
        path = self.server_root_path
        for word in words:
            if os.path.dirname(word) or word in (os.curdir, os.pardir):
                # Ignore components that are not a simple file/directory name
                continue
            path = os.path.join(path, word)
        return path

    def do_GET(self):
        """Handle GET requests."""
        local_path = self.translate_path(self.path)

        # Case 1: The file exists locally. Serve it immediately.
        if os.path.exists(local_path) and os.path.isfile(local_path):
            # print(f"[LOCAL] Serving: {self.path}") # Too verbose
            super().do_GET()
            return

        # Let the base handler deal with directory listing requests.
        if os.path.isdir(local_path):
            # print(f"[LOCAL] Handling directory request: {self.path}") # Too verbose
            super().do_GET()
            return

        # Case 2: The file does not exist. Try to fetch it from the remote server if proxying is enabled.
        if not self.proxy_enabled:
            print(f"[ERROR] Proxying disabled. File not found locally: {self.path}")
            self.send_error(404, "File not found locally and proxying is disabled.")
            return

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

            # If the file was not found locally but successfully fetched from the remote server,
            # and ntfy reporting is enabled, send a notification.
            if self.ntfy_reporting_enabled:
                ntfy_topic = "SpongeBob404" # This topic is for successfully proxied 404s
                ntfy_url = f"https://ntfy.sh/{ntfy_topic}"
                try:
                    # Send the full remote URL as the plaintext body of the notification.
                    ntfy_response = requests.post(ntfy_url, data=remote_url.encode('utf-8'))
                    ntfy_response.raise_for_status()  # Check for HTTP errors from ntfy.sh
                    print(f"        [NTFY] Notification sent for successfully proxied 404: {remote_url}")
                except requests.exceptions.RequestException as ntfy_e:
                    print(f"        [NTFY] FAILED to send ntfy.sh notification for {self.path}: {ntfy_e}")

            # Ensure the local directory structure exists before saving.
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            # Save the file to the local path for future requests.
            with open(local_path, 'wb') as f:
                f.write(content)
            print(f"        Success! Saved to '{os.path.relpath(local_path, self.server_root_path)}'")

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
