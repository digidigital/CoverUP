"""
UI layout and icon definitions for CoverUP PDF.
"""

import os
import FreeSimpleGUI as sg

from coverup.utils import (
    get_script_root, find_fonts_folder, make_icons, draw_character, parse_page_range
)
from coverup.i18n import _


# Material Symbols glyphs for UI-icons
GLYPHS = {
    "left":          "",
    "right":         "",
    "zoom_in":       "",
    "zoom_out":      "",
    "close":         "",
    "save_pdf":      "",
    "open_file":     "",
    "undo":          "",
    "redo":          "",
    "about":         "",
    "eraser_off":    "",
    "eraser":        "",
    "inkdrop_white": "",
    "inkdrop_black": "",
    "delete_all":    "",
    "cut":           "",
    "low_quality":   "",
    "high_quality":  "",
    "multipage_off": "",
    "multipage_on":  "",
    "export_range":  "",
    "redact_single": "",
    "redact_all":    "",
    "redact_ask":    "",
}

REDACT_INACTIVE_COLOR = '#C8C8C8'

# mode -> (event key of the clickable icon, glyph name, active color)
REDACT_MODES = {
    'single': ('RMODE_single', 'redact_single', '#1E88E5'),
    'all':    ('RMODE_all',    'redact_all',    '#43A047'),
    'ask':    ('RMODE_ask',    'redact_ask',    '#FB8C00'),
}

REDACT_DEFAULT_MODE = 'single'

SIDEBAR_WIDTH_FRACTION = 0.2


def get_fontpath():
    """Get the path to the Material Symbols font file."""
    script_root = get_script_root()
    fonts_dir = find_fonts_folder(script_root)
    fontpath = os.path.join(fonts_dir, "MaterialSymbolsOutlined[FILL,GRAD,opsz,wght].ttf")

    if not os.path.exists(fontpath):
        raise FileNotFoundError(f"Font file not found: {fontpath}")

    return fontpath


def create_icons(fontpath):
    """Create the icons dictionary from the glyphs."""
    icons = make_icons(GLYPHS, fontpath)
    for mode, (_key, glyph, color) in REDACT_MODES.items():
        icons[glyph + '_active'] = draw_character(GLYPHS[glyph], fontpath, color=color)
        icons[glyph + '_off'] = draw_character(GLYPHS[glyph], fontpath, color=REDACT_INACTIVE_COLOR)
    return icons


def _img_to_xbm(img, name, x_hot, y_hot):
    """Serialise a 1-bit PIL image to XBM text (with a hotspot)."""
    w, h = img.size
    px = img.load()
    row_bytes = (w + 7) // 8
    values = []
    for y in range(h):
        for byte_i in range(row_bytes):
            byte = 0
            for bit in range(8):
                x = byte_i * 8 + bit
                if x < w:
                    if px[x, y]:
                        byte |= (1 << bit)
            values.append(byte)
    body = ', '.join('0x{:02x}'.format(v) for v in values)
    return (
        '#define {n}_width {w}\n'
        '#define {n}_height {h}\n'
        '#define {n}_x_hot {xh}\n'
        '#define {n}_y_hot {yh}\n'
        'static unsigned char {n}_bits[] = {{\n {b}\n}};\n'
    ).format(n=name, w=w, h=h, xh=x_hot, yh=y_hot, b=body)


def make_pan_cursor(cache_dir):
    """Build an open-hand bitmap cursor and return its Tk cursor spec.

    Many cursor themes (e.g. KDE Breeze) map the named ``hand1``/``hand2``
    cursors to a plain arrow, so an "open hand" can't come from a stock cursor
    name. Instead we render an open palm (``back_hand`` glyph) from the Material
    Symbols font into an XBM cursor written to ``cache_dir``.

    Returns a Tk cursor spec ``'@source mask black white'``, or ``PAN_CURSOR``
    as a fallback if rendering fails.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageFilter
        size = 24
        font = ImageFont.truetype(get_fontpath(), 22)
        try:
            font.set_variation_by_axes([1, 0, 24, 700])
        except Exception:
            pass
        base = Image.new('L', (size, size), 0)
        draw = ImageDraw.Draw(base)
        glyph = '\ue764'
        bb = draw.textbbox((0, 0), glyph, font=font)
        gw, gh = bb[2] - bb[0], bb[3] - bb[1]
        draw.text(
            ((size - gw) // 2 - bb[0], (size - gh) // 2 - bb[1]),
            glyph, font=font, fill=255
        )
        silhouette = base.point(lambda p: 255 if p > 110 else 0)
        mask = silhouette.filter(ImageFilter.MaxFilter(3))
        src_path = os.path.join(cache_dir, 'coverup_hand.xbm')
        msk_path = os.path.join(cache_dir, 'coverup_hand_mask.xbm')
        with open(src_path, 'w') as fh:
            fh.write(_img_to_xbm(silhouette, 'hand', size // 2, size // 2))
        with open(msk_path, 'w') as fh:
            fh.write(_img_to_xbm(mask, 'handmask', size // 2, size // 2))
        return '@{} {} black white'.format(src_path, msk_path)
    except Exception:
        return PAN_CURSOR


def create_app_icon(fontpath):
    """Create the application window icon."""
    return draw_character('\uf82b', fontpath, font_size=110, width=128, height=128,
                          icon_background=True)


def create_layout(icons, image_bg_color='gray'):
    """Create the main window layout."""
    graph_layout = [[
        sg.Graph(
            canvas_size=(2, 2),
            background_color='silver',
            graph_bottom_left=(0, -2),
            graph_top_right=(2, 0),
            expand_x=False,
            expand_y=False,
            key='-GRAPH-',
            enable_events=True,
            drag_submits=True
        )
    ]]

    sidebar_bg = '#4d4d4d'
    section_font = ('Helvetica', 8, 'bold')
    section_color = '#A9AFB4'

    mode_icons = []
    for mode, (event_key, glyph, _color) in REDACT_MODES.items():
        is_default = mode == REDACT_DEFAULT_MODE
        icon_data = icons[glyph + ('_active' if is_default else '_off')]
        mode_icons.append(
            sg.Image(icon_data, key=event_key, tooltip=_('tooltip_redact_' + mode),
                     pad=((8, 4), 2) if not mode_icons else ((4, 4), 2),
                     enable_events=True, background_color=sidebar_bg)
        )

    sidebar = [
        [sg.Text(_('tools_section').upper(), font=section_font, text_color=section_color,
                 background_color=sidebar_bg, pad=((8, 6), (10, 2)))],
        [
            sg.Image(icons['inkdrop_black'], key='CHANGE_COLOR', tooltip=_('tooltip_color'),
                     pad=((8, 4), 2), enable_events=True, background_color=sidebar_bg),
            sg.Image(icons['eraser_off'], key='EDIT_MODE', tooltip=_('tooltip_eraser'),
                     pad=((4, 4), 2), enable_events=True, background_color=sidebar_bg),
            sg.Image(icons['delete_all'], key='DELETE_ALL', tooltip=_('tooltip_delete_all'),
                     pad=((4, 6), 2), enable_events=True, background_color=sidebar_bg),
        ],
        [sg.Text(_('apply_section').upper(), font=section_font, text_color=section_color,
                 background_color=sidebar_bg, pad=((8, 6), (12, 2)))],
        mode_icons,
        [sg.Text(_('redact_status_' + REDACT_DEFAULT_MODE), key='-REDACT_MODE-',
                 font=('Helvetica', 8), text_color='#FFD54F',
                 background_color=sidebar_bg, pad=((8, 6), (2, 0)))],
        [sg.Button(_('btn_auto_redact'), key='AUTO_REDACT', expand_x=True,
                   tooltip=_('tooltip_auto_redact'), pad=((8, 6), (12, 4)))],
        [sg.Text(_('thumbs_section').upper(), font=section_font, text_color=section_color,
                 background_color=sidebar_bg, pad=((8, 6), (12, 2)))],
        [sg.Column([], key='-THUMBS-', background_color=sidebar_bg, scrollable=True,
                   vertical_scroll_only=True, expand_x=True, expand_y=True,
                   pad=(0, 0), size=(210, 560),
                   sbar_background_color='darkgrey', sbar_arrow_color='silver')],
    ]

    layout = [
        [
            sg.Image(icons['open_file'], key='LOAD_PDF', tooltip=_('tooltip_open'),
                     pad=((6, 0), 0), enable_events=True, background_color=image_bg_color),
            sg.Image(icons['save_pdf'], key='SAVE_PDF', tooltip=_('tooltip_save'),
                     pad=0, enable_events=True, background_color=image_bg_color),
            sg.Image(icons['undo'], key='UNDO', tooltip=_('tooltip_undo'),
                     pad=((14, 0), 0), enable_events=True, background_color=image_bg_color),
            sg.Image(icons['redo'], key='REDO', tooltip=_('tooltip_redo'),
                     pad=0, enable_events=True, background_color=image_bg_color),
            sg.Push(background_color='gray'),
            sg.Image(icons['left'], key='BACK', tooltip=_('tooltip_prev'),
                     pad=0, enable_events=True, background_color=image_bg_color),
            sg.Input(visible=False, focus=True),
            sg.Input(size=(4, 2), readonly=False, focus=False, change_submits=False,
                     enable_events=True, justification='center', key='-PAGE_NUM-'),
            sg.Text('/', background_color='gray'),
            sg.Text('0', key='-PAGE_TOTAL-', justification='left', background_color='gray'),
            sg.Image(icons['right'], key='FORTH', tooltip=_('tooltip_next'),
                     pad=0, enable_events=True, background_color=image_bg_color),
            sg.Push(background_color='gray'),
            sg.Image(icons['zoom_in'], key='ZOOM_IN', tooltip=_('tooltip_zoom_in'),
                     pad=0, enable_events=True, background_color=image_bg_color),
            sg.Text('100%', key='-ZOOM_LEVEL-', size=(5, 1), justification='center',
                    background_color='gray', text_color='white'),
            sg.Image(icons['zoom_out'], key='ZOOM_OUT', tooltip=_('tooltip_zoom_out'),
                     pad=0, enable_events=True, background_color=image_bg_color),
            sg.Push(background_color='gray'),
            sg.Image(icons['about'], key='ABOUT', tooltip=_('tooltip_about'),
                     pad=0, enable_events=True, background_color=image_bg_color),
            sg.Push(background_color='gray'),
        ],
        [
            sg.Pane(
                [
                    sg.Column(sidebar, background_color=sidebar_bg, vertical_alignment='top',
                              pad=(0, 0), expand_y=True, key='-SIDEBAR-'),
                    sg.Column(
                        [[
                            sg.Column(
                                layout=graph_layout,
                                background_color='silver',
                                size=(2, 2),
                                pad=0,
                                expand_x=True,
                                expand_y=True,
                                scrollable=True,
                                sbar_trough_color='lightgrey',
                                sbar_background_color='darkgrey',
                                sbar_relief=sg.RELIEF_RAISED,
                                sbar_arrow_color='silver',
                                key='-GRAPH_COLUMN-',
                            )
                        ]],
                        background_color='silver',
                        pad=0,
                        expand_x=True,
                        expand_y=True,
                        key='-GRAPH_WRAP-',
                    ),
                ],
                orientation='horizontal',
                handle_size=8,
                border_width=0,
                relief=sg.RELIEF_FLAT,
                background_color=sidebar_bg,
                expand_x=True,
                expand_y=True,
                key='-PANE-',
            )
        ],
        [
            sg.ProgressBar(
                100,
                key='-PROGRESS-',
                orientation='horizontal',
                bar_color=('green', 'white'),
                size_px=(50, 5),
                pad=(0, 5),
                expand_x=True,
                visible=False,
            )
        ],
    ]

    return layout


def page_scope_rows(prefix, total_pages, current_page):
    """Rows for the shared "which pages" selector used by dialogs.

    Produces the radio group [All / Current page / Selection + range input]
    with keys ``-{prefix}_ALL-``, ``-{prefix}_CURRENT-``, ``-{prefix}_SEL-``
    and ``-{prefix}_RANGE-``. Pair with :func:`handle_scope_event` and
    :func:`read_page_scope`.
    """
    return [
        [sg.Radio(_('export_all', total=total_pages), prefix + 'GRP', default=True,
                  key=f'-{prefix}_ALL-', enable_events=True)],
        [sg.Radio(_('export_current', page=current_page + 1), prefix + 'GRP',
                  key=f'-{prefix}_CURRENT-', enable_events=True)],
        [sg.Radio(_('export_selection'), prefix + 'GRP', key=f'-{prefix}_SEL-',
                  enable_events=True),
         sg.Input('', size=(16, 1), key=f'-{prefix}_RANGE-', disabled=True,
                  tooltip=_('range_prompt', total=total_pages))],
    ]


def handle_scope_event(dialog, event, values, prefix):
    """Sync the range input with the scope radios. True if event was consumed."""
    if event in (f'-{prefix}_ALL-', f'-{prefix}_CURRENT-', f'-{prefix}_SEL-'):
        dialog[f'-{prefix}_RANGE-'].update(disabled=not values[f'-{prefix}_SEL-'])
        return True
    return False


def read_page_scope(values, prefix, total_pages, current_page):
    """Return the selected 0-based page indices from a scope selector."""
    if values[f'-{prefix}_ALL-']:
        return list(range(total_pages))
    if values[f'-{prefix}_CURRENT-']:
        return [current_page]
    return parse_page_range(values[f'-{prefix}_RANGE-'], total_pages)


TOOL_CURSORS = {'draw': 'crosshair', 'erase': 'left_ptr'}
PAN_CURSOR = 'hand1'


def set_tool(window, icons, tool):
    """Activate a canvas tool ('draw' or 'erase').

    Sets the matching mouse cursor and highlights the erase button so the active
    tool is obvious. Returns the tool for assignment.
    """
    window['-GRAPH-'].set_cursor(TOOL_CURSORS.get(tool, 'crosshair'))
    window['EDIT_MODE'].update(data=icons['eraser'] if tool == 'erase' else icons['eraser_off'])
    return tool


def toggle_quality(window, icons, output_quality):
    """Toggle output quality setting."""
    output_quality = 'low' if output_quality == 'high' else 'high'
    quality_icon = icons['low_quality'] if output_quality == 'low' else icons['high_quality']
    window['TOGGLE_QUALITY'].update(data=quality_icon)
    return output_quality


def toggle_color(window, icons, fill_color):
    """Toggle fill color between black and white."""
    fill_color = 'white' if fill_color == 'black' else 'black'
    color_icon = icons['inkdrop_black'] if fill_color == 'black' else icons['inkdrop_white']
    window['CHANGE_COLOR'].update(data=color_icon)
    return fill_color


def set_redact_mode(window, icons, redact_mode):
    """Select which pages a newly drawn bar is applied to.

    Modes:
        'single' - apply the bar to the current page only (default).
        'all'    - replicate the bar onto every page.
        'ask'    - prompt for a page range each time a bar is drawn.

    Colour-codes the selected mode's icon (others are muted grey) and updates
    the explanatory status line below the icons. Returns the mode for
    assignment.
    """
    for mode, (event_key, glyph, _color) in REDACT_MODES.items():
        selected = mode == redact_mode
        window[event_key].update(data=icons[glyph + ('_active' if selected else '_off')])
    window['-REDACT_MODE-'].update(_('redact_status_' + redact_mode))
    return redact_mode
