#!/usr/bin/env python3
"""Version checker for SpongeBob Flash Game Archive.
Forces updates when newer versions are available by checking against a remote version file.
"""

import os
import sys
import requests
import webbrowser
from typing import Optional, Tuple
import threading

# Current version of the archive
CURRENT_VERSION = "1.0"  # Update this when releasing new versions

# URL to the remote versions.txt file (replace with your actual hosting URL)
VERSIONS_URL = "https://raw.githubusercontent.com/MatinTheGC/sb_arcade/mom/versions.txt"

def fetch_latest_version() -> Optional[Tuple[str, str]]:
    """Fetches the latest version info from remote versions.txt.
    Returns (version, magnet) tuple if successful, None if failed."""
    try:
        response = requests.get(VERSIONS_URL, timeout=10)
        response.raise_for_status()
        
        # Parse versions file (format: version::magnet)
        latest_version = None
        latest_magnet = None
        
        for line in response.text.splitlines():
            if not line.strip():
                continue
            try:
                version, magnet = line.strip().split("::", 1)
                # Keep track of highest version seen
                if latest_version is None or float(version) > float(latest_version):
                    latest_version = version
                    latest_magnet = magnet
            except ValueError:
                continue
                
        if latest_version and latest_magnet:
            return latest_version, latest_magnet
        return None
        
    except Exception as e:
        print(f"Failed to fetch version info: {e}")
        return None

def show_update_instructions(new_version: str, magnet_link: str):
    """Shows update instructions in browser."""
    instructions = f"""
    <html>
    <head><meta charset='utf-8'><title>Update Required — SpongeBob Flash Game Archive</title></head>
    <body style='font-family:Arial,Helvetica,sans-serif;line-height:1.5;padding:30px'>
    <h1>Update Required</h1>
    <p>A new version ({new_version}) of the SpongeBob Flash Game Archive is available!</p>
    <p>Your current version ({CURRENT_VERSION}) must be updated to continue.</p>
    
    <h2>Update Instructions</h2>
    <ol>
        <li>Use your torrent client to download the new archive using the magnet link below</li>
        <li>Replace your current <code>flash_game_archive</code> folder with the newly downloaded one</li>
        <li>Run <code>RUN_THIS.py</code> again</li>
    </ol>
    
    <h3>Magnet Link</h3>
    <textarea style="width:100%;height:100px;margin:20px 0">{magnet_link}</textarea>
    
    <p>After updating, you can close this page and restart the archive launcher.</p>
    </body>
    </html>
    """
    
    try:
        instructions_path = os.path.join(os.path.dirname(__file__), 'UPDATE_INSTRUCTIONS.html')
        with open(instructions_path, 'w', encoding='utf-8') as f:
            f.write(instructions)
        file_url = 'file://' + os.path.abspath(instructions_path).replace('\\', '/')
        webbrowser.open(file_url)
    except Exception as e:
        # Fallback to console if we can't create/open HTML
        print("\n=== UPDATE REQUIRED ===")
        print(f"New version available: {new_version}")
        print(f"Current version: {CURRENT_VERSION}")
        print("\nMagnet link for new version:")
        print(magnet_link)
        print("\nPlease:")
        print("1. Use the magnet link above with your torrent client")
        print("2. Replace your flash_game_archive folder with the new one")
        print("3. Run RUN_THIS.py again")

def main(has_internet: bool = True):
    """Main version check routine."""
    if not has_internet:
        print("No internet connection detected. Skipping version check.")
        return True
        
    # Fetch latest version info
    latest = fetch_latest_version()
    if not latest:
        print("Failed to fetch version information. Continuing with current version.")
        return True
        
    latest_version, latest_magnet = latest
    
    # Compare versions
    try:
        if float(latest_version) > float(CURRENT_VERSION):
            print(f"\nNEW VERSION AVAILABLE: {latest_version}")
            print("Current version is outdated. Update required to continue.")
            show_update_instructions(latest_version, latest_magnet)
            def delete_file():
                try:
                    os.remove(os.path.join(os.path.dirname(__file__), 'UPDATE_INSTRUCTIONS.html'))
                except:
                    pass
            timer = threading.Timer(15.0, delete_file)
            timer.start()
            return False
    except ValueError:
        print("Failed to compare versions. Continuing with current version.")
        return True
        
    return True

if __name__ == '__main__':
    if not main():
        sys.exit(1)
