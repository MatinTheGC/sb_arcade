# SpongeBob Flash Game Archive

A comprehensive offline archive of classic SpongeBob SquarePants Flash games, preserved for future generations to enjoy. This project provides a high-quality, offline-capable collection of Flash games with improved compatibility and quality-of-life features.

## Overview

This archive was created to preserve classic SpongeBob Flash games that were previously scattered across various websites. While inspired by existing collections, this project goes further by:

- Fixing broken assets and dependencies
- Improving game compatibility
- Adding quality-of-life features
- Providing a fully offline-capable archive
- Implementing automatic asset caching

The archive includes a local proxy server that intelligently handles game requests, first attempting to serve content from the local cache, and if needed, fetching and caching missing assets from upstream sources.

## Prerequisites

- Python 3.7 or higher
- pip (Python package installer)
- A web browser
- A BitTorrent client (for downloading the archive)

## Installation

### Download the Archive

1. Go to the [Releases page](https://github.com/MatinTheGC/sb_arcade/releases)
2. Find the latest release and copy the magnet link
3. Open your preferred BitTorrent client and add the magnet link
4. Download the archive and extract it to your desired location

### Windows

1. Open PowerShell or Command Prompt
2. Navigate to the project directory
3. Create and activate a virtual environment (recommended):

   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate
   ```

4. Install required dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

### macOS

1. Clone or download this repository
2. Open Terminal
3. Navigate to the project directory
4. Create and activate a virtual environment (recommended):

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

5. Install required dependencies:

   ```bash
   python3 -m pip install -r requirements.txt
   ```

### Linux

1. Clone or download this repository
2. Open Terminal
3. Navigate to the project directory
4. Create and activate a virtual environment (recommended):

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

5. Install required dependencies:

   ```bash
   python3 -m pip install -r requirements.txt
   ```

## Running the Archive

1. Start the server:

   ```bash
   python RUN_THIS.py
   ```

2. Open your web browser and navigate to:

   ```plaintext
   http://localhost:8004
   ```

3. On first run, you'll be asked to complete the initial setup process.
4. After setup is complete, you can browse and play the games from the main interface.

## Architecture

The project consists of several key components:

- `RUN_THIS.py`: Main launcher script
- `proxy_server.py`: Local proxy server for serving and caching game content
- `flash_game_archive/`: Directory containing the game files and web interface
- Various Python scripts for maintenance and updates

## Technical Details

- The proxy server runs on port 8004 by default
- Uses a caching system to store remote assets locally

## Contributing

Contributions are welcome! Please feel free to submit pull requests or create issues for bugs and feature requests.

## License

**This is an unofficial, fan-made preservation project. All game rights belong to their original creators.**

## Acknowledgments

- Project development assisted by AI tools (Gemini, Claude, and ChatGPT)
- Original game creators and developers
- Flash game preservation community
