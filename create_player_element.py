from bs4 import BeautifulSoup

def create_player_element(info):
    """Creates the new <object>/<embed> structure for Flash/Ruffle."""
    if not info:
        return None
    container = BeautifulSoup('<div id="game-container"></div>', 'html.parser').div
    obj_tag = BeautifulSoup(f'''
        <object width="{info['width']}" height="{info['height']}">
            <param name="movie" value="{info['swf']}" />
            <param name="allowScriptAccess" value="always" />
            <param name="quality" value="high" />
            <param name="autoplay" value="on" />
            <param name="unmuteOverlay" value="hidden" />
            <embed src="{info['swf']}" width="{info['width']}" height="{info['height']}" allowScriptAccess="always" quality="high" autoplay="on" unmuteOverlay="hidden" type="application/x-shockwave-flash"></embed>
        </object>
    ''', 'html.parser').object
    container.append(obj_tag)
    return container
