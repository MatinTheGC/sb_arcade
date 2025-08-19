import os
import json
from patch_html_file import patch_html_file

# --- Configuration ---
# Assuming this script is in 'python/', the archive is in 'python/flash_game_archive/'
ARCHIVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'flash_game_archive')
GAMES_DIR = os.path.join(ARCHIVE_DIR, 'games')
JSON_PATH = os.path.join(ARCHIVE_DIR, 'games.json')

def main():
    """Main function to find and patch all game index.html files."""
    print("--- Starting Game Page Patcher ---")
    if not os.path.isdir(GAMES_DIR):
        print(f"[ERROR] Games directory not found at: {GAMES_DIR}")
        return
    if not os.path.exists(JSON_PATH):
        print(f"[ERROR] games.json not found at: {JSON_PATH}")
        print("Please run generate_json.py first.")
        return

    patched_count = 0
    total_count = 0
    game_folders = sorted(os.listdir(GAMES_DIR))

    for game_slug in game_folders:
        game_dir = os.path.join(GAMES_DIR, game_slug)
        if os.path.isdir(game_dir):
            index_path = os.path.join(game_dir, 'index.html')
            if os.path.exists(index_path):
                total_count += 1
                if patch_html_file(index_path):
                    patched_count += 1

    print("\n--- Patcher Summary ---")
    print(f"Processed {total_count} game pages.")
    print(f"Successfully patched {patched_count} files.")
    print("Process complete.")

if __name__ == "__main__":
    main()
