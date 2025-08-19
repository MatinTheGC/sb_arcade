import os
import requests
import time
from bs4 import BeautifulSoup
from seleniumwire import webdriver
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
# Using local msedgedriver.exe, so manager is not needed.
from urllib.parse import urljoin, urlparse
import http.server
import socketserver
import threading
from concurrent.futures import ThreadPoolExecutor


# --- Configuration ---
BASE_URL = "https://www.thesbcommunity.com/games/"
OUTPUT_DIR = "flash_game_archive"
GAMES_DIR = os.path.join(OUTPUT_DIR, "games")
SHARED_DIR = os.path.join(OUTPUT_DIR, "shared")
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

# --- Global cache for downloaded files ---
downloaded_files = {} # url -> local_path

def setup_driver():
    """Sets up a visible Edge WebDriver with selenium-wire."""
    print("Setting up visible Edge WebDriver with selenium-wire...")
    edge_options = EdgeOptions()
    # edge_options.add_argument("--headless") # Removed for visibility
    edge_options.add_argument(f"user-agent={USER_AGENT}")

    edge_options.add_experimental_option('excludeSwitches', ['enable-logging'])

    # Options for selenium-wire to make request interception more reliable
    seleniumwire_options = {
        'disable_encoding': True,
        'verify_ssl': False
    }

    try:
        # Use an absolute path to the driver to avoid PATH issues
        driver_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "msedgedriver.exe")
        service = EdgeService(executable_path=driver_path)
        driver = webdriver.Edge(
            service=service,
            options=edge_options,
            seleniumwire_options=seleniumwire_options
        )
        return driver
    except Exception as e:
        print(f"Error setting up WebDriver: {e}")
        print("Please ensure you have Microsoft Edge and selenium-wire installed (`pip install selenium-wire`).")
        return None

def download_file(url, save_path):
    """Downloads a file from a URL to a specific path."""
    if url in downloaded_files:
        print(f"'{os.path.basename(url)}' already downloaded. Skipping.")
        return downloaded_files[url]

    try:
        print(f"Downloading '{os.path.basename(url)}' to '{os.path.relpath(save_path)}'...")
        headers = {'User-Agent': USER_AGENT}
        response = requests.get(url, headers=headers, stream=True, timeout=90)
        response.raise_for_status()

        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        downloaded_files[url] = save_path
        print(f"  -> Success: Saved to '{os.path.relpath(save_path)}'")
        return save_path
    except requests.exceptions.RequestException as e:
        print(f"Error downloading {url}: {e}")
        return None

def get_game_links():
    """Fetches all game links from the main games page."""
    print(f"Fetching game links from {BASE_URL}...")
    try:
        response = requests.get(BASE_URL, headers={'User-Agent': USER_AGENT})
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        links = set()
        # Find all tables and get links from them
        for table in soup.find_all('table'):
            for a in table.find_all('a', href=True):
                href = a['href']
                if href and '/games/' in href and not href.endswith('/games/'):
                    full_url = urljoin(BASE_URL, href)
                    if full_url not in links:
                        links.add(full_url)

        print(f"\nFound {len(links)} unique game links in total.")
        return sorted(list(links))
    except requests.exceptions.RequestException as e:
        print(f"Error fetching the main games page: {e}")
        return []

def download_ruffle_player():
    """Scrapes the ruffle directory and downloads all its contents."""
    ruffle_dir_url = "https://www.thesbcommunity.com/games/ruffle/"
    local_ruffle_dir = os.path.join(SHARED_DIR, "ruffle")

    if os.path.exists(local_ruffle_dir) and os.listdir(local_ruffle_dir):
        print("Ruffle player files already seem to exist. Skipping download.")
        return

    print(f"Downloading the complete Ruffle player from {ruffle_dir_url}...")
    os.makedirs(local_ruffle_dir, exist_ok=True)

    try:
        response = requests.get(ruffle_dir_url, headers={'User-Agent': USER_AGENT})
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find all links in the Apache-style directory listing
        for a in soup.find_all('a', href=True):
            href = a['href']
            # A simple filter to avoid parent directory links ('../') and query strings
            if '?' not in href and href != '../':
                file_url = urljoin(ruffle_dir_url, href)
                file_name = os.path.basename(urlparse(file_url).path)
                if file_name:
                    download_file(file_url, os.path.join(local_ruffle_dir, file_name))
        print("Ruffle player download complete.")
    except requests.exceptions.RequestException as e:
        print(f"  -> Critical Error: Could not download Ruffle player: {e}")


def generate_game_html(game_dir, game_name, swf_file, width, height, ruffle_path):
    """Generates an index.html file for a downloaded game."""
    relative_swf_path = os.path.basename(swf_file)
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{game_name}</title>
    <style>
        body {{ margin: 0; padding: 0; background-color: #000; display: flex; justify-content: center; align-items: center; height: 100vh; }}
        object, embed {{ outline: none; }}
    </style>
</head>
<body>
    <div id="player" style="width: {width}px; height: {height}px;"></div>
    <script>
    window.RufflePlayer = window.RufflePlayer || {{}};
    window.RufflePlayer.config = {{
        "autoplay": "on",
        "unmuteOverlay": "hidden",

    }};
    </script>
    <script src="{ruffle_path}"></script>
    <script>
        window.RufflePlayer = window.RufflePlayer || {{}};
        window.addEventListener("load", (event) => {{
            const ruffle = window.RufflePlayer.newest();
            const player = ruffle.createPlayer();
            const container = document.getElementById("player");
            container.appendChild(player);
            player.style.width = "{width}px";
            player.style.height = "{height}px";
            player.load({ url: "{relative_swf_path}", allowScriptAccess: true });
        }});
    </script>
</body>
</html>
"""
    with open(os.path.join(game_dir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(html_content)

def archive_game(driver, game_url):
    """Archives a single game: downloads assets and creates an HTML file."""
    try:
        game_name = game_url.strip('/').split('/')[-1]
        print(f"\n--- Processing game: {game_name} ---")
        game_dir = os.path.join(GAMES_DIR, game_name)
        if not os.path.exists(game_dir):
            print(f"Creating directory: '{game_dir}'")
            os.makedirs(game_dir, exist_ok=True)

        # Block requests to ruffle.js so we can load it manually after injecting the config.
        print("  -> Blocking automatic loading of ruffle.js")
        def interceptor(request):
            if 'ruffle.js' in request.url:
                request.abort()
        driver.request_interceptor = interceptor

        # Clear captured requests from previous pages
        del driver.requests

        print(f"Navigating to {game_url}...")
        driver.get(game_url)

        # Clear the interceptor now that the initial page load is done.
        del driver.request_interceptor

        print("  -> Manually injecting config and loading ruffle.js...")
        driver.execute_script("""
            window.RufflePlayer = window.RufflePlayer || {};
            window.RufflePlayer.config = {
                "autoplay": "on",
                "unmuteOverlay": "hidden",
            };
            const ruffleScript = document.createElement('script');
            ruffleScript.src = 'https://www.thesbcommunity.com/games/ruffle/ruffle.js';
            document.body.appendChild(ruffleScript);
        """)

        print("Waiting 90 seconds for game to auto-load and capture assets...")
        time.sleep(90)

        asset_urls = set()
        print("Scanning captured network requests for assets...")
        for request in driver.requests:
            if request.response: # Ensure we have a response
                url = request.url
                # Filter for game assets from the target domain, ignore data URIs
                if 'thesbcommunity.com' in url and not url.startswith('data:'):
                    asset_urls.add(url)

        if not asset_urls:
            print(f"Could not find any first-party assets for {game_url}. Skipping.")
            return

        print(f"Found {len(asset_urls)} unique assets to download.")

        # Try to identify the main SWF file
        swf_files = [u for u in asset_urls if u.endswith('.swf')]
        main_swf_url = None
        if len(swf_files) == 1:
            main_swf_url = swf_files[0]
        elif len(swf_files) > 1:
            # Heuristic: main swf often contains the game name in its path
            potential_mains = [u for u in swf_files if game_name in u]
            if len(potential_mains) == 1:
                main_swf_url = potential_mains[0]
            else: # Fallback if heuristic is inconclusive
                print(f"Multiple SWF files found, guessing '{os.path.basename(swf_files[0])}' is the main one.")
                main_swf_url = swf_files[0]

        if not main_swf_url:
            print(f"Could not identify a main .swf file for {game_url} from network logs. Skipping.")
            return

        print(f"Found {len(asset_urls)} game assets. Downloading...")
        for url in asset_urls:
            file_name = os.path.basename(urlparse(url).path)
            if not file_name:
                print(f"  -> Skipping asset with no filename: {url}")
                continue
            if not os.path.splitext(file_name)[1]:
                print(f"  -> Skipping asset with no file extension: {file_name}")
                continue
            # Determine the correct save directory
            url_path = urlparse(url).path
            if "/ruffle/" in url_path:
                save_dir = os.path.join(SHARED_DIR, "ruffle")
            elif "/common/" in url_path:
                save_dir = SHARED_DIR
            else:
                save_dir = game_dir
            download_file(url, os.path.join(save_dir, file_name))

        local_swf_path = os.path.join(game_dir, os.path.basename(main_swf_url))

        # Get width and height from the page source as a fallback
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        width, height = '800', '600' # Default size
        player_tag = soup.find('object') or soup.find('embed')
        if player_tag:
            if 'width' in player_tag.attrs:
                width = player_tag['width']
            if 'height' in player_tag.attrs:
                height = player_tag['height']

        # Ruffle player is now downloaded once in main(). We just need to point to it.
        ruffle_local_path = os.path.join(SHARED_DIR, "ruffle", "ruffle.js")
        relative_ruffle_path = os.path.relpath(ruffle_local_path, game_dir).replace('\\', '/')
        generate_game_html(game_dir, game_name, local_swf_path, width, height, relative_ruffle_path)
        print(f"Successfully archived {game_name}")

    except Exception as e:
        import traceback
        print(f"An error occurred while processing {game_url}: {e}")
        traceback.print_exc()

def process_game_url(game_url):
    """Worker function: sets up a driver, archives a game, and quits."""
    time.sleep(1) # Stagger browser startups to reduce initial load
    driver = setup_driver()
    if not driver:
        print(f"Skipping {game_url} due to WebDriver setup failure.")
        return
    try:
        archive_game(driver, game_url)
    except Exception as e:
        import traceback
        print(f"An uncaught exception occurred while processing {game_url}: {e}")
        traceback.print_exc()
    finally:
        print(f"Closing WebDriver for {game_url}.")
        driver.quit()


def run_server():
    """Starts a simple HTTP server, finding an open port if necessary."""
    os.chdir(OUTPUT_DIR)
    port = 8000
    Handler = http.server.SimpleHTTPRequestHandler

    # Create a root index page for easy navigation
    with open("index.html", "w", encoding="utf-8") as f:
        f.write("<!DOCTYPE html><html><head><title>Flash Game Archive</title><style>body{{font-family:sans-serif; background-color:#f0f0f0;}} ul{{list-style:none; padding:0;}} li{{margin:5px 0;}} a{{text-decoration:none; color:#0066cc;}}</style></head><body>")
        f.write("<h1>SpongeBob Flash Game Archive</h1><ul>")
        game_folders = sorted([d for d in os.listdir("games") if os.path.isdir(os.path.join("games", d))])
        for game in game_folders:
            f.write(f'<li><a href="games/{game}/index.html" target="_blank">{game.replace("-", " ").title()}</a></li>')
        f.write("</ul></body></html>")

    # Find an available port and start the server
    while port < 9000:
        try:
            with socketserver.TCPServer(("", port), Handler) as httpd:
                print(f"\\nStarting server at http://localhost:{port}")
                print("Navigate to the URL above in your browser to play the games.")
                print("Press Ctrl+C to stop the server.")
                httpd.serve_forever()
            return # Exit function after server is stopped
        except OSError:
            print(f"Port {port} is in use, trying next...")
            port += 1

    print("Could not find an open port between 8000 and 8999.")

def main():
    """Main function to run the archiver."""
    print("--- SpongeBob Flash Game Archiver ---")
    print(f"Creating base output directory: {OUTPUT_DIR}")
    os.makedirs(GAMES_DIR, exist_ok=True)
    os.makedirs(SHARED_DIR, exist_ok=True)

    download_ruffle_player()

    game_links = get_game_links()
    if not game_links:
        print("No game links found. Exiting.")
        return

    print("Filtering game list...")
    skip_games = ["bubbleball", "dutchman"]
    links_to_process = [
        link for link in game_links if not any(skip in link for skip in skip_games)
    ]
    print(f"Skipped {len(game_links) - len(links_to_process)} non-SWF games.")
    print(f"Found {len(links_to_process)} games to process.")

    # Run up to 2 browsers in parallel
    executor = ThreadPoolExecutor(max_workers=4)
    try:
        executor.map(process_game_url, links_to_process)
    except KeyboardInterrupt:
        print("\n--- Ctrl+C detected. Shutting down browsers gracefully... ---")
        # Do not wait for tasks to complete, cancel futures
        executor.shutdown(wait=False, cancel_futures=True)

    print("\\n--- Archiving Complete ---")

    try:
        run_server()
    except KeyboardInterrupt:
        print("\\nServer stopped.")
    except Exception as e:
        print(f"Could not start server: {e}")
        print(f"You can manually start a server in the '{{OUTPUT_DIR}}' directory.")
        print("For example, run: python -m http.server")

if __name__ == "__main__":
    main()
