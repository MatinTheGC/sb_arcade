import os
import re
from bs4 import BeautifulSoup, Comment
from extract_game_info import extract_game_info
from create_player_element import create_player_element

# --- Templates ---

# The new CSS to be injected into each game's index.html
CSS_TEMPLATE = """
        body {
            margin: 0;
            padding: 20px;
            /* Add padding to the bottom to avoid overlap with the fixed controls */
            padding-bottom: 80px;
            background-color: #222;
            color: #eee;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            min-height: calc(100vh - 100px); /* 40px top/bottom padding + 60px controls height */
            font-family: sans-serif;
            text-align: center;
        }
        #game-container {
            margin-bottom: 20px;
            box-shadow: 0 0 15px rgba(0,0,0,0.5);
        }
        #custom-game-controls {
            /* Pinned to the bottom */
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            display: flex;
            gap: 10px;
            justify-content: center;
            align-items: center;
            background-color: rgba(20, 20, 20, 0.9);
            padding: 15px 0;
            box-shadow: 0 -5px 15px rgba(0,0,0,0.4);
            border-top: 1px solid #444;
            z-index: 1000;
        }
        #custom-game-controls button {
            background-color: #555;
            color: white;
            border: 2px solid #777;
            border-radius: 50%; /* Make buttons circular */
            padding: 0;
            font-size: 1.5rem; /* Larger icon size */
            cursor: pointer;
            transition: background-color 0.2s;
            width: 50px; /* Fixed width */
            height: 50px; /* Fixed height */
            display: flex;
            justify-content: center;
            align-items: center;
            line-height: 1;
        }
        #custom-game-controls button#disable-ruffle-btn {
            width: auto; /* Allow this button to be wider */
            border-radius: 5px; /* Revert to rectangle */
            padding: 10px 15px;
            font-size: 1rem;
        }
        #custom-game-controls button:hover {
            background-color: #666;
        }
        #custom-game-controls button:disabled {
            background-color: #333;
            color: #888;
            cursor: not-allowed;
        }
        p {
             margin-top: 15px;
             max-width: 800px;
        }
        #donations-btn {
            background-color: #007bff;
            border-color: #0056b3;
        }
        #donations-btn:hover {
            background-color: #0056b3;
        }
        /* Modal Styles */
        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.7);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 2000;
            opacity: 0;
            visibility: hidden;
            transition: opacity 0.3s, visibility 0.3s;
        }
        .modal-overlay.visible {
            opacity: 1;
            visibility: visible;
        }
        .modal-content-wrapper {
             max-width: 600px;
             width: 90%;
        }
        .modal-content {
            background: #333;
            padding: 30px;
            border-radius: 10px;
            max-height: 70vh;
            overflow-y: auto;
            box-shadow: 0 5px 20px rgba(0,0,0,0.5);
            transform: scale(0.9);
            transition: transform 0.3s;
            color: #eee;
            text-align: left;
        }
        .modal-content h2 { color: #00aaff; }
        .modal-content ul { list-style: none; padding-left: 0; }
        .modal-content li { background: #444; margin: 5px 0; padding: 10px; border-radius: 5px; word-wrap: break-word; }
        .modal-content code { background: #222; padding: 2px 5px; border-radius: 3px; }
        .modal-overlay.visible .modal-content {
            transform: scale(1);
        }
        .modal-close-btn {
            background: #8b0000;
            color: white;
            border: 2px solid #c00;
            border-radius: 5px;
            padding: 10px 20px;
            font-size: 1rem;
            cursor: pointer;
            transition: background-color 0.2s;
            display: block;
            margin: 20px auto 0;
        }
        .modal-close-btn:hover {
            background: #c00;
        }

        /* View Transitions API CSS */
        html {
            view-transition-name: root;
        }

        /* Default fade effect for root transitions (e.g., home to game, initial load) */
        ::view-transition-old(root),
        ::view-transition-new(root) {
            animation-duration: 0.6s;
            animation-fill-mode: forwards;
        }

        /* Specific elements for inter-game navigation to enable custom transitions */
        /* These will have their view-transition-name attribute applied dynamically by JS */
        #game-container, #player {
            /* This is a placeholder; actual name will be set by JS if it's the player div */
            /* view-transition-name: game-content; */
        }
        #custom-game-controls {
            view-transition-name: game-controls; /* This will always be present for persistence */
        }

        /* Animations for game content sliding */
        /* These animations will be dynamically applied based on direction */
        @keyframes slide-in-right {
            from { transform: translateX(100%); }
            to { transform: translateX(0%); }
        }
        @keyframes slide-out-left {
            from { transform: translateX(0%); }
            to { transform: translateX(-100%); }
        }
        @keyframes slide-in-left {
            from { transform: translateX(-100%); }
            to { transform: translateX(0%); }
        }
        @keyframes slide-out-right {
            from { transform: translateX(0%); }
            to { transform: translateX(100%); }
        }

        /* Apply slide animations based on data-transition-direction on HTML element */
        html[data-transition-direction="next"]::view-transition-old(game-content) {
            animation-name: slide-out-left;
        }
        html[data-transition-direction="next"]::view-transition-new(game-content) {
            animation-name: slide-in-right;
        }
        html[data-transition-direction="prev"]::view-transition-old(game-content) {
            animation-name: slide-out-right;
        }
        html[data-transition-direction="prev"]::view-transition-new(game-content) {
            animation-name: slide-in-left;
        }

        /* Fade animations for controls during inter-game navigation */
        /* This makes them "fade" as if persistent by transitioning their opacity */
        ::view-transition-old(game-controls) {
            animation: fade-out 0.3s ease-in-out forwards;
        }
        ::view-transition-new(game-controls) {
            animation: fade-in 0.3s ease-in-out forwards;
        }

        @keyframes fade-out {
            from { opacity: 1; }
            to { opacity: 0; }
        }
        @keyframes fade-in {
            from { opacity: 0; }
            to { opacity: 1; }
        }
"""

# The new JavaScript block for the controls.
JS_TEMPLATE = """
    <script id="custom-controls-script">
        document.addEventListener('DOMContentLoaded', () => {
            const prevBtn = document.getElementById('prev-game-btn');
            const nextBtn = document.getElementById('next-game-btn');
            const homeBtn = document.getElementById('home-btn'); // Added Home button
            const zoomInBtn = document.getElementById('zoom-in-btn');
            const zoomOutBtn = document.getElementById('zoom-out-btn');
            const disableRuffleBtn = document.getElementById('disable-ruffle-btn');
            const donationsBtn = document.getElementById('donations-btn');
            const modalOverlay = document.getElementById('donations-modal-overlay');
            const modalContentEl = document.getElementById('donations-modal-content');
            const modalCloseBtn = document.getElementById('donations-modal-close');

            homeBtn.addEventListener('click', () => {
                window.location.href = '/';
            });

            // --- Donations Modal Logic ---

            if (donationsBtn) {
                donationsBtn.addEventListener('click', () => {
                    fetch('/donations.json') // Assumes donations.json is at the root
                        .then(response => {
                            if (!response.ok) throw new Error('Could not fetch donations file.');
                            return response.json();
                        })
                        .then(data => {
                            let contentHtml = `<h2>${data.title}</h2>`;
                            data.paragraphs.forEach(p => {
                                contentHtml += `<p>${p}</p>`;
                            });
                            if (data.wallets && data.wallets.length > 0) {
                                contentHtml += '<h3>Crypto Wallets:</h3><ul>';
                                data.wallets.forEach(wallet => {
                                    contentHtml += `<li><strong>${wallet.currency}:</strong><br><code>${wallet.address}</code></li>`;
                                });
                                contentHtml += '</ul>';
                            }
                            modalContentEl.innerHTML = contentHtml;
                            modalOverlay.classList.add('visible');
                        })
                        .catch(error => {
                            console.error('Failed to load donations info:', error);
                            modalContentEl.innerHTML = '<h2>Error</h2><p>Could not load donation information. Please try again later.</p>';
                            modalOverlay.classList.add('visible');
                        });
                });
            }
            if (modalCloseBtn) {
                modalCloseBtn.addEventListener('click', () => modalOverlay.classList.remove('visible'));
            }
            if (modalOverlay) {
                modalOverlay.addEventListener('click', (event) => {
                    if (event.target === modalOverlay) {
                        modalOverlay.classList.remove('visible');
                    }
                });
            }
            // --- End Donations Modal Logic ---

            // --- Ruffle Toggle Button Logic ---
            if (disableRuffleBtn) {
                const isRuffleDisabled = localStorage.getItem('ruffleDisabled') === 'true';

                // Set initial button text
                disableRuffleBtn.textContent = isRuffleDisabled ? 'Enable Ruffle' : 'Disable Ruffle';

                disableRuffleBtn.addEventListener('click', () => {
                    const currentlyDisabled = localStorage.getItem('ruffleDisabled') === 'true';
                    const message = currentlyDisabled
                        ? "Enabling Ruffle will reload the page. This is required for games to run in most modern browsers. Proceed?"
                        : "Warning: Disabling Ruffle may prevent games from running in modern browsers like Chrome, Firefox, or Edge unless you have a special browser with native Flash Player support.\\n\\nAre you sure you want to disable Ruffle?";

                    if (confirm(message)) {
                        // Toggle the setting in localStorage
                        localStorage.setItem('ruffleDisabled', String(!currentlyDisabled));
                        // Reload the page for the change to take effect
                        window.location.reload();
                    }
                });
            }
            // --- End Ruffle Toggle Logic ---

            const pathParts = window.location.pathname.split('/');
            // Handles both file:/// and http:// paths by finding the 'games' directory
            const gamesDirIndex = pathParts.findIndex(part => part === 'games');
            const currentGameSlug = pathParts[gamesDirIndex + 1];

            let currentZoom = 100;

            if (zoomInBtn) {
                zoomInBtn.addEventListener('click', () => {
                    currentZoom += 10;
                    document.body.style.zoom = `${currentZoom}%`;
                });
            }

            if (zoomOutBtn) {
                zoomOutBtn.addEventListener('click', () => {
                    currentZoom = Math.max(50, currentZoom - 10); // Don't zoom out too much
                    document.body.style.zoom = `${currentZoom}%`;
                });
            }

            fetch('/games.json')
                .then(response => {
                    if (!response.ok) throw new Error('Network response was not ok');
                    return response.json();
                })
                .then(games => {
                    // Ensure consistent sort order
                    games.sort((a, b) => a.name.localeCompare(b.name));

                    const gameIndex = games.findIndex(game => game.slug === currentGameSlug);

                    if (gameIndex === -1) {
                        console.error('Could not find current game in games.json');
                        prevBtn.disabled = true;
                        nextBtn.disabled = true;
                        return;
                    }

                    const prevGame = games[(gameIndex - 1 + games.length) % games.length];
                    const nextGame = games[(gameIndex + 1) % games.length];

                    prevBtn.disabled = false;
                    nextBtn.disabled = false;

                    prevBtn.addEventListener('click', () => {
                        window.location.href = `../${prevGame.slug}/`;
                    });

                    nextBtn.addEventListener('click', () => {
                        window.location.href = `../${nextGame.slug}/`;
                    });
                })
                .catch(error => {
                    console.error('Failed to load game list for navigation:', error);
                    prevBtn.disabled = true;
                    nextBtn.disabled = true;
                });
        });
    </script>
"""

# The HTML for the new control bar.
CONTROLS_HTML = """
    <div id="custom-game-controls">
        <button id="home-btn" title="Home">🏠</button>
        <button id="prev-game-btn" title="Previous Game" disabled>«</button>
        <button id="next-game-btn" title="Next Game" disabled>»</button>
        <button id="zoom-in-btn" title="Zoom In">+</button>
        <button id="zoom-out-btn" title="Zoom Out">-</button>
        <button id="donations-btn" title="Donations">❤️</button>
        <button id="disable-ruffle-btn">Disable Ruffle</button>
    </div>
"""

# The HTML for the donations modal.
MODAL_HTML = """
    <div class="modal-overlay" id="donations-modal-overlay">
        <div class="modal-content-wrapper">
            <div class="modal-content" id="donations-modal-content">
                <!-- Content will be loaded from JSON -->
            </div>
            <button class="modal-close-btn" id="donations-modal-close">Close</button>
        </div>
    </div>
"""

# This script conditionally writes the Ruffle script tag to the document.
# This allows the user to disable Ruffle via localStorage.
RUFFLE_LOADER_JS = """
<script id="ruffle-loader-script">
    // This script must run before the DOM is fully loaded to prevent Ruffle from auto-starting.
    (function() {
        if (localStorage.getItem('ruffleDisabled') === 'true') {
            console.log("Ruffle is disabled via user setting. Skipping Ruffle script injection.");
        } else {
            // The path is relative to the game's index.html file.
            document.write('<script src="../../shared/ruffle/ruffle.js"></scr' + 'ipt>');
        }
    })();
</script>
"""

def patch_html_file(file_path):
    """Applies all patches to a single index.html file."""
    print(f"-> Processing '{os.path.relpath(file_path)}'...")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        soup = BeautifulSoup(content, 'html.parser')

        # === IDEMPOTENCY/CLEANUP STEP ===
        print("  - Cleaning up any previous patches...")
        if soup.find(id="custom-game-controls"): soup.find(id="custom-game-controls").decompose()
        if soup.find('script', id="custom-controls-script"): soup.find('script', id="custom-controls-script").decompose()
        if soup.find('script', id="ruffle-loader-script"): soup.find('script', id="ruffle-loader-script").decompose()
        if soup.find('style', id="custom-styles"): soup.find('style', id="custom-styles").decompose()
        if soup.find(id="donations-modal-overlay"): soup.find(id="donations-modal-overlay").decompose()
        old_comment = soup.find(string=lambda text: isinstance(text, Comment) and "Patched by" in text)
        if old_comment: old_comment.extract()
        # Remove any static ruffle.js script tag, as we replace it with our conditional loader.
        static_ruffle_script = soup.find('script', src=re.compile(r'ruffle\.js$'))
        if static_ruffle_script: static_ruffle_script.decompose()

        # === PATCHING LOGIC ===
        player_container = soup.find('div', id='player') or soup.find('div', id='game-container')
        if not player_container:
            print("  - ERROR: Could not find player container ('player' or 'game-container'). Skipping.")
            return False

        if player_container.get('id') == 'player':
            print("  - Applying first-time patch: converting Ruffle JS to <object> tag...")
            game_info = extract_game_info(soup)
            if not game_info:
                print("  - WARNING: Could not extract game info (swf, width, height). Skipping.")
                return False
            new_player_element = create_player_element(game_info)
            player_container.replace_with(new_player_element)
            player_container = new_player_element
            if soup.body:
                for script_tag in soup.body.find_all('script'):
                    if script_tag.string and 'RufflePlayer.newest()' in script_tag.string:
                        script_tag.decompose()

        head = soup.find('head')
        if head:
            old_style = soup.find('style')
            if old_style and not old_style.get('id'): old_style.decompose()
            new_style_tag = soup.new_tag('style', id="custom-styles")
            new_style_tag.string = CSS_TEMPLATE
            head.append(new_style_tag)

        body = soup.find('body')
        if body:
            controls_soup = BeautifulSoup(CONTROLS_HTML, 'html.parser')
            player_container.insert_before(controls_soup)

            # Inject the donations modal structure.
            modal_soup = BeautifulSoup(MODAL_HTML, 'html.parser')
            body.insert(0, modal_soup)

            # Inject the Ruffle loader script, which runs immediately.
            loader_soup = BeautifulSoup(RUFFLE_LOADER_JS, 'html.parser')
            body.append(loader_soup.script)

            # Inject the controls script, which runs after the DOM is loaded.
            js_soup = BeautifulSoup(JS_TEMPLATE, 'html.parser')
            body.append(js_soup.script)

        soup.body.insert(0, Comment(" Patched by patch_game_pages.py "))

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(str(soup))
        print("  - Success: Patched file.")
        return True

    except Exception as e:
        print(f"  - ERROR: An unexpected error occurred: {e}")
        return False
