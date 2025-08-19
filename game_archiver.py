#!/usr/bin/env python3
"""
Simple Spongebob Flash game archiver prototype.

Features implemented:
- Discover game links from a main page (naive anchor filter).
- Launch headless Edge via Selenium and capture network requests (performance logs + CDP).
- Wait a configurable time while the page runs to capture dynamically loaded assets.
- Download discovered assets, deduplicate into a `common` folder using content hash.
- Create a minimal per-game `index.html` wrapper that loads local Ruffle and the main SWF.
- Create a launcher `index.html` listing games.
- Optionally start a simple Python HTTP server to host the archive.

Notes / assumptions:
- You have Edge installed and a matching `msedgedriver.exe` (you said it's in this folder).
- This script is a pragmatic, best-effort prototype. Some games may require extra patching; the script creates a simple wrapper that works with many Ruffle-hosted SWFs.

Usage:
    python game_archiver.py --main-url https://thesbcommunity.com --output ./archive --driver ./msedgedriver.exe

"""

import argparse
import hashlib
import json
import os
import re
import shutil
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from tqdm import tqdm


SWF_EXTS = ('.swf', '.xml', '.js', '.wasm', '.json')


def discover_games(main_url):
    """Fetch main page and extract candidate game links."""
    print(f"Discovering games from {main_url}")
    resp = requests.get(main_url, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    links = set()
    for a in soup.find_all('a', href=True):
        href = a['href']
        # naive: include links that look like game pages
        if 'game' in href.lower() or '/games/' in href.lower() or href.lower().endswith('.html'):
            if href.startswith('http'):
                links.add(href)
            else:
                links.add(requests.compat.urljoin(main_url, href))
    print(f"Found {len(links)} candidate links")
    return sorted(links)


def capture_assets(game_url, driver_path, wait_seconds=40):
    """Launch headless Edge, open the URL, wait, and collect network requests via performance logs."""
    print(f"Capturing assets for {game_url} (will wait {wait_seconds}s)")
    options = Options()
    options.use_chromium = True
    # headless new is more stable in newer selenium/edge
    options.add_argument('--headless=new')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

    service = Service(executable_path=os.path.abspath(driver_path))
    driver = webdriver.Edge(service=service, options=options)

    try:
        # enable network via CDP to improve capture
        try:
            driver.execute_cdp_cmd('Network.enable', {})
        except Exception:
            pass

        driver.get(game_url)
        # give the page some time to load initial assets
        time.sleep(3)
        # optionally attempt to click play buttons if present (best-effort)
        try:
            # common play button selectors
            for sel in ['button.play', '.play-button', '[data-play]']:
                els = driver.find_elements(By.CSS_SELECTOR, sel)
                if els:
                    els[0].click()
                    break
        except Exception:
            pass

        # wait while the game runs
        time.sleep(wait_seconds)

        logs = []
        try:
            logs = driver.get_log('performance')
        except Exception:
            # fallback: use browser logs
            try:
                logs = driver.get_log('browser')
            except Exception:
                logs = []

        urls = set()
        for entry in logs:
            try:
                msg = json.loads(entry['message'])['message']
                if msg.get('method') == 'Network.requestWillBeSent':
                    url = msg['params']['request']['url']
                    if url.startswith('http'):
                        urls.add(url)
            except Exception:
                continue

        # also attempt to scan the DOM for common embeds
        page = driver.page_source
        for m in re.findall(r"[\'\"](https?://[^\'\"]+\.(?:swf|xml|js|wasm|json))[\'\"]", page, flags=re.I):
            urls.add(m)

        print(f"Captured {len(urls)} unique URLs for {game_url}")
        return sorted(urls)
    finally:
        driver.quit()


def download_and_dedupe(urls, game_dir, common_dir, seen_hashes):
    os.makedirs(game_dir, exist_ok=True)
    os.makedirs(common_dir, exist_ok=True)
    downloaded = []
    session = requests.Session()
    for url in tqdm(urls, desc=f"Downloading {os.path.basename(game_dir)}"):
        try:
            resp = session.get(url, timeout=30)
            if resp.status_code != 200:
                continue
            data = resp.content
            h = hashlib.sha256(data).hexdigest()
            ext = Path(url).suffix or ''
            # determine filename
            fname = Path(url).name
            if not fname:
                fname = h[:12] + ext
            # dedupe by content hash
            if h in seen_hashes:
                # find existing file path
                existing = seen_hashes[h]
                # create relative symlink or copy
                dest = os.path.join(game_dir, os.path.basename(existing))
                if not os.path.exists(dest):
                    shutil.copy2(existing, dest)
                downloaded.append(dest)
                continue
            # new file
            # choose where to put: if ext looks like common (js, wasm, json) put in common
            put_common = ext.lower() in ('.js', '.wasm', '.json') or 'ruffle' in fname.lower()
            if put_common:
                dest = os.path.join(common_dir, fname)
            else:
                dest = os.path.join(game_dir, fname)
            # ensure unique filename
            base, e = os.path.splitext(dest)
            i = 1
            while os.path.exists(dest):
                dest = f"{base}_{i}{e}"
                i += 1
            with open(dest, 'wb') as f:
                f.write(data)
            seen_hashes[h] = dest
            downloaded.append(dest)
        except Exception as e:
            # skip failing downloads
            continue
    return downloaded


def make_game_wrapper(game_dir, main_swf, common_rel='../common'):
    """Create a minimal index.html that loads ruffle and the SWF locally."""
    index_path = os.path.join(game_dir, 'index.html')
    ruffle_js = os.path.join(common_rel, 'ruffle.js')
    html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>{os.path.basename(game_dir)}</title>
  <script src="{ruffle_js}"></script>
  <style>body{{background:#000;margin:0;display:flex;align-items:center;justify-content:center;height:100vh}}#player{{width:800px;height:600px}}</style>
</head>
<body>
  <div id="player"></div>
  <script>
    (function(){{
      try{{
        const ruffle = window.RufflePlayer && window.RufflePlayer.newest ? window.RufflePlayer.newest() : null;
        if(!ruffle){{
          document.getElementById('player').innerText = 'Ruffle not available';
          return;
        }}
        const player = ruffle.createPlayer();
        document.getElementById('player').appendChild(player);
        player.style.width = '800px';
        player.style.height = '600px';
        player.load('{os.path.basename(main_swf)}');
      }}catch(e){{
        console.error(e);
        document.getElementById('player').innerText = 'Error initializing player';
      }}
    }})();
  </script>
</body>
</html>
"""
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(html)
    return index_path


def create_launcher(output_dir):
    out = os.path.join(output_dir, 'index.html')
    games = []
    for entry in sorted(os.listdir(output_dir)):
        p = os.path.join(output_dir, entry)
        if os.path.isdir(p) and entry != 'common':
            games.append(entry)
    lines = ["<!doctype html>", "<html><head><meta charset=\"utf-8\"><title>Games Launcher</title></head><body>", "<h1>Downloaded games</h1>", "<ul>"]
    for g in games:
        lines.append(f"<li><a href=\"{g}/index.html\">{g}</a></li>")
    lines += ["</ul>", "</body></html>"]
    with open(out, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    return out


def serve_folder(folder, port=8000):
    cwd = os.getcwd()
    os.chdir(folder)
    handler = SimpleHTTPRequestHandler
    httpd = HTTPServer(('0.0.0.0', port), handler)
    print(f"Serving {folder} at http://0.0.0.0:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        os.chdir(cwd)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--main-url', required=True)
    parser.add_argument('--output', default='./archive')
    parser.add_argument('--driver', default='./msedgedriver.exe')
    parser.add_argument('--wait', type=int, default=40)
    parser.add_argument('--serve', action='store_true')
    args = parser.parse_args()

    out = os.path.abspath(args.output)
    common_dir = os.path.join(out, 'common')
    os.makedirs(out, exist_ok=True)
    os.makedirs(common_dir, exist_ok=True)

    links = discover_games(args.main_url)

    seen_hashes = {}

    for url in links:
        # small heuristic to skip non-game pages
        if not any(part in url.lower() for part in ('game', 'play', '/games/', '.swf')):
            continue
        safe_name = re.sub(r'[^A-Za-z0-9_-]', '_', url).strip('_')[:80]
        game_dir = os.path.join(out, safe_name)
        os.makedirs(game_dir, exist_ok=True)

        urls = capture_assets(url, args.driver, wait_seconds=args.wait)
        if not urls:
            print(f"No assets captured for {url}, skipping")
            continue

        downloaded = download_and_dedupe(urls, game_dir, common_dir, seen_hashes)
        # try to pick a main swf for the wrapper
        main_swf = None
        for p in downloaded:
            if p.lower().endswith('.swf'):
                main_swf = p
                break
        if not main_swf:
            # attempt to find swf in original URLs
            for u in urls:
                if u.lower().endswith('.swf'):
                    # copy from seen hashes
                    continue
        if main_swf:
            # ensure main_swf is inside game_dir (it might be in common)
            if not main_swf.startswith(game_dir):
                # copy into game dir for local load
                dest = os.path.join(game_dir, os.path.basename(main_swf))
                if not os.path.exists(dest):
                    shutil.copy2(main_swf, dest)
                main_swf = dest
            make_game_wrapper(game_dir, main_swf, common_rel='../common')
        else:
            print(f"No SWF found for {url}; created game folder with downloaded assets for manual patching.")

    create_launcher(out)

    print("All done. Archive is in:", out)
    if args.serve:
        try:
            serve_folder(out, port=8000)
        except Exception as e:
            print('Failed to start server:', e)


if __name__ == '__main__':
    main()
