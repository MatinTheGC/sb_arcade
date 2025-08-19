SpongeBob Flash Game Archiver

This repository contains a prototype Python script to archive Flash games from thesbcommunity.com.

Quick start

1. Ensure Microsoft Edge is installed and `msedgedriver.exe` matches your Edge version and is placed in this folder.
2. Create a virtualenv and install dependencies:
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt

3. Run the archiver:
   python game_archiver.py --main-url https://thesbcommunity.com --output ./archive --driver .\msedgedriver.exe --serve

Notes
- This tool uses a headless Edge browser to capture network requests while the game runs. It is a best-effort prototype and may need adjustments for certain games.
- You must follow site terms and copyright laws when archiving content.
