import re

def extract_game_info(soup):
    """Extracts SWF file, width, and height from the Ruffle script in the HTML."""
    script_tags = soup.find_all('script')
    for script in script_tags:
        if script.string and 'player.load' in script.string:
            url_match = re.search(r'url:\\s*"(.*?)"', script.string)
            width_match = re.search(r'player.style.width\\s*=\\s*"(.*?)"', script.string)
            height_match = re.search(r'player.style.height\\s*=\\s*"(.*?)"', script.string)

            if url_match and width_match and height_match:
                return {
                    "swf": url_match.group(1),
                    "width": width_match.group(1),
                    "height": height_match.group(1)
                }
    return None
