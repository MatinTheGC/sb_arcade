import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re

# --- Configuration ---
BASE_URL = "https://www.thesbcommunity.com/games/"
GAMES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'flash_game_archive', 'games')
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

def get_game_name_map():
    """
    Fetches the main games page and creates a map of
    game slugs (folder names) to their friendly display names.
    """
    print(f"Fetching game list from {BASE_URL}...")
    game_map = {}
    try:
        response = requests.get(BASE_URL, headers={'User-Agent': USER_AGENT})
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find all links within tables, which is where the game links are
        for table in soup.find_all('table'):
            for a in table.find_all('a', href=True):
                href = a['href']
                # Filter for actual game links
                if href and '/games/' in href and not href.endswith('/games/'):
                    # Extract the slug from the URL (e.g., 'sb_3dracer')
                    slug = urlparse(href).path.strip('/').split('/')[-1]
                    # Get the friendly name from the link's text
                    friendly_name = a.get_text(strip=True)
                    if slug and friendly_name:
                        game_map[slug] = friendly_name

        print(f"Found {len(game_map)} game name mappings.")
        return game_map
    except requests.exceptions.RequestException as e:
        print(f"Error fetching the main games page: {e}")
        return None

def update_game_titles(game_map):
    """
    Iterates through the local game directories and updates the <title>
    tag in their respective index.html files.
    """
    if not game_map:
        print("Game map is empty. Cannot update titles.")
        return

    if not os.path.isdir(GAMES_DIR):
        print(f"[ERROR] Games directory not found at: {GAMES_DIR}")
        return

    print(f"\nScanning for games in '{os.path.relpath(GAMES_DIR)}' to update titles...")
    updated_count = 0
    skipped_count = 0
    not_found_count = 0

    local_games = [d for d in os.listdir(GAMES_DIR) if os.path.isdir(os.path.join(GAMES_DIR, d))]

    for game_slug in local_games:
        index_path = os.path.join(GAMES_DIR, game_slug, 'index.html')

        if game_slug not in game_map:
            print(f"  -> WARNING: No friendly name found online for local folder '{game_slug}'.")
            not_found_count += 1
            continue

        friendly_name = game_map[game_slug]

        if not os.path.exists(index_path):
            # It's possible a folder exists but the game wasn't archived successfully
            continue

        try:
            with open(index_path, 'r+', encoding='utf-8') as f:
                content = f.read()

                # Use regex for a more robust replacement that doesn't rely on perfect HTML parsing
                # and preserves the original document structure better than BeautifulSoup's output.
                new_content, count = re.subn(
                    r'(<title>)(.*?)(</title>)',
                    fr'\1{friendly_name}\3',
                    content,
                    flags=re.IGNORECASE | re.DOTALL
                )

                if count == 0:
                    print(f"  -> WARNING: No <title> tag found in '{os.path.relpath(index_path)}'.")
                    skipped_count += 1
                elif content != new_content:
                    print(f"Updating title for '{game_slug}' to '{friendly_name}'")
                    f.seek(0)
                    f.write(new_content)
                    f.truncate()
                    updated_count += 1
                # If content is the same, no update is needed.

        except Exception as e:
            print(f"  -> ERROR: Could not process file '{os.path.relpath(index_path)}': {e}")
            skipped_count += 1

    print("\n--- Title Update Summary ---")
    print(f"Successfully updated: {updated_count} titles.")
    print(f"Skipped (no title tag or error): {skipped_count} files.")
    print(f"Local folders not found online: {not_found_count}.")
    print("Process complete.")


if __name__ == "__main__":
    game_name_map = get_game_name_map()
    if game_name_map:
        update_game_titles(game_name_map)
