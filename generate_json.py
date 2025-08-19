import os
import requests
import json
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# --- Configuration ---
BASE_URL = "https://www.thesbcommunity.com/games/"
# The script is in python/, so we navigate to python/flash_game_archive/
ARCHIVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'flash_game_archive')
GAMES_DIR = os.path.join(ARCHIVE_DIR, 'games')
OUTPUT_JSON_PATH = os.path.join(ARCHIVE_DIR, 'games.json')
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

        print(f"Found {len(game_map)} game name mappings online.")
        return game_map
    except requests.exceptions.RequestException as e:
        print(f"Error fetching the main games page: {e}")
        return None

def generate_games_json(game_map):
    """
    Scans the local games directory and creates a games.json file
    with the slug and friendly name for each game.
    """
    if not game_map:
        print("Game map is empty. Cannot generate JSON file.")
        return

    if not os.path.isdir(GAMES_DIR):
        print(f"[ERROR] Games directory not found at: {GAMES_DIR}")
        return

    print(f"\nScanning for local games in '{os.path.relpath(GAMES_DIR)}'...")
    games_data = []

    # Get all subdirectories in the games directory
    local_games = [d for d in os.listdir(GAMES_DIR) if os.path.isdir(os.path.join(GAMES_DIR, d))]

    for game_slug in local_games:
        # We only want to list games that were successfully archived and have an index page.
        if not os.path.exists(os.path.join(GAMES_DIR, game_slug, 'index.html')):
            print(f"  -> Skipping '{game_slug}' because it does not contain an index.html file.")
            continue

        # Use the friendly name from the map, or create a fallback name from the slug.
        friendly_name = game_map.get(game_slug)
        if not friendly_name:
            print(f"  -> WARNING: No friendly name found for '{game_slug}'. Using folder name as fallback.")
            # Simple transformation: replace hyphens/underscores with spaces and title-case it.
            friendly_name = game_slug.replace('-', ' ').replace('_', ' ').title()

        games_data.append({
            "slug": game_slug,
            "name": friendly_name
        })

    print(f"Found {len(games_data)} valid local games to include in the list.")

    try:
        with open(OUTPUT_JSON_PATH, 'w', encoding='utf-8') as f:
            # Use indent=2 for readability
            json.dump(games_data, f, indent=2, ensure_ascii=False)
        print(f"\nSuccessfully created '{os.path.relpath(OUTPUT_JSON_PATH)}'.")
    except Exception as e:
        print(f"\n[ERROR] Failed to write to JSON file: {e}")


if __name__ == "__main__":
    print("--- Generating Game List JSON ---")
    online_game_map = get_game_name_map()
    if online_game_map:
        generate_games_json(online_game_map)
