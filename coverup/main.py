#!/usr/bin/env python3
"""
CoverUP PDF - Main application entry point.

A tool for redacting PDF files and images.
Licensed under GPL-3.0
(c) 2024 - 2026 Björn Seipel
"""

import gc
import io
import os
import sys
import shutil
import argparse
import subprocess
import tkinter as tk
from pathlib import Path
from multiprocessing import freeze_support

import FreeSimpleGUI as sg
from fpdf import FPDF
from appdirs import user_data_dir

from coverup import __version__
from coverup import textsearch, ocr
from coverup.image_container import ImageContainer, delete_all_rectangles, finalize_pages_chunked, close_all_pages
from coverup.document_loader import load_document
from coverup.workfile import WorkfileManager
from coverup.utils import parse_page_range
from coverup.ui import (
    get_fontpath, create_icons, create_app_icon, create_layout,
    set_tool, toggle_color, set_redact_mode,
    page_scope_rows, handle_scope_event, read_page_scope,
    SIDEBAR_WIDTH_FRACTION, TOOL_CURSORS, make_pan_cursor
)
from coverup.i18n import _, _plural


def _native_file_dialog(save, title, start_dir, default_name, filters, parent_winid=None):
    """Open the desktop's native file chooser on Linux (KDE/GNOME).

    On Linux, tkinter's file dialog is the dated Tk widget rather than the
    desktop's native browser, so prefer ``kdialog`` (KDE/Plasma) or ``zenity``
    (GNOME and others) when available.

    Args:
        save: True for a "save as" dialog, False for "open".
        title: Dialog window title.
        start_dir: Initial directory (falls back to the user's home).
        default_name: Suggested file name for save dialogs.
        filters: List of (description, "pattern1 pattern2") tuples.
        parent_winid: X11 window id of the main window. When given, kdialog is
            anchored to it (transient/modal) so the dialog stays on top of the
            app instead of appearing behind it.

    Returns:
        str: The chosen path, or '' if the user cancelled, or None if no native
             tool is available (the caller should fall back to tkinter). Always
             None on Windows/macOS, where tkinter already uses the native dialog.
    """
    if sys.platform.startswith('win') or sys.platform == 'darwin':
        return None

    start_dir = start_dir or os.path.expanduser('~')
    try:
        if shutil.which('kdialog'):
            start = os.path.join(start_dir, default_name) if default_name else start_dir
            mode = '--getsavefilename' if save else '--getopenfilename'
            kfilter = '\n'.join(f"{pats}|{desc}" for desc, pats in filters)
            cmd = ['kdialog', mode, start, kfilter, '--title', title]
            if parent_winid:
                cmd += ['--attach', str(parent_winid)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.stdout.strip() if result.returncode == 0 else ''

        if shutil.which('zenity'):
            cmd = ['zenity', '--file-selection', f'--title={title}']
            if save:
                cmd += ['--save', '--confirm-overwrite']
                cmd.append(f"--filename={os.path.join(start_dir, default_name or '')}")
            else:
                cmd.append(f"--filename={start_dir}/")
            for desc, pats in filters:
                cmd.append(f"--file-filter={desc} | {pats}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.stdout.strip() if result.returncode == 0 else ''
    except Exception:
        return None

    return None


def pick_open_file(title, initial_folder, filters, parent_winid=None):
    """Choose a file to open, using the native browser when possible."""
    start = str(initial_folder) if initial_folder else None
    native = _native_file_dialog(False, title, start, None, filters, parent_winid)
    if native is not None:
        return native
    return sg.popup_get_file(
        title, initial_folder=initial_folder, grab_anywhere=True, keep_on_top=True,
        no_window=True, show_hidden=True, file_types=tuple(filters)
    )


def pick_save_file(title, start_dir, default_name, default_ext, filters, parent_winid=None):
    """Choose a destination path to save to, using the native browser when possible."""
    native = _native_file_dialog(True, title, start_dir, default_name, filters, parent_winid)
    if native is not None:
        if native and default_ext and not os.path.splitext(native)[1]:
            native += default_ext
        return native
    return sg.popup_get_file(
        title, no_window=True, show_hidden=True, keep_on_top=True, save_as=True,
        file_types=tuple(filters), default_extension=default_ext, default_path=default_name
    )


def _do_load_file(
        load_path: str,
        import_ppi: int,
        window,
        workfile_manager,
        images: list,
        fill_color: str,
        output_quality: str,
        icons: dict,
        pointer_cursor: str,
        drawing_cursor: str
) -> tuple:
    """Load a document, update the UI, and return updated state.

    Returns:
        (images, file_path, current_page, fill_color, output_quality)
    Raises:
        Any exception from load_document — cursor is always restored via finally.
    """
    window.set_cursor('watch')
    window['-GRAPH-'].set_cursor('watch')
    window['-PROGRESS-'].update(current_count=0, visible=True)
    window.refresh()

    try:
        # Erase graph and close existing images before loading new document
        window['-GRAPH-'].erase()
        close_all_pages(images)
        gc.collect()

        ImageContainer.zoom_factor = 100
        window['-ZOOM_LEVEL-'].update('100%')

        new_images, file_path, current_page, new_fill_color, new_output_quality = load_document(
            load_path, import_ppi, window, workfile_manager
        )

        # Apply restored settings if available
        if new_fill_color and fill_color != new_fill_color:
            fill_color = toggle_color(window, icons, fill_color)
        if new_output_quality:
            output_quality = new_output_quality

        current_page = flip_to_page(window, new_images, current_page)
        window.set_title(_('app_title_with_file', filename=os.path.basename(file_path)))

        return (new_images, file_path, current_page, fill_color, output_quality)
    finally:
        window['-PROGRESS-'].update(current_count=0, visible=False)
        window.set_cursor(pointer_cursor)
        window['-GRAPH-'].set_cursor(drawing_cursor)


def prompt_page_range(window, total_pages, prompt_key='range_prompt'):
    """Ask the user which pages an action should apply to.

    Args:
        window: The GUI window (used for centering the dialog).
        total_pages: Number of pages available.
        prompt_key: Translation key for the prompt text.

    Returns:
        list[int]: Sorted 0-based page indices, or None if the user cancelled.
                   May be empty if the input matched no valid pages.
    """
    win_loc_x, win_loc_y = window.current_location()
    win_w, win_h = window.current_size_accurate()
    text = sg.popup_get_text(
        _(prompt_key, total=total_pages),
        title=_('range_title'),
        default_text=_('range_all_keyword'),
        location=(win_loc_x + win_w / 2 - 175, win_loc_y + win_h / 2 - 90),
        keep_on_top=True
    )
    if text is None:
        return None
    return parse_page_range(text, total_pages)


def prompt_export_target(window, total_pages, current_page, output_quality):
    """Dialog asking which pages to export and at what quality.

    Uses the shared page-scope selector plus a quality radio group (the
    quality choice lives here, at the moment it matters, instead of as a
    global toolbar toggle).

    Returns:
        tuple: ``(target, quality)`` where ``target`` is a sorted list of
        0-based page indices (possibly empty if a selection matched nothing)
        or ``None`` if the user cancelled, and ``quality`` is ``'high'`` or
        ``'low'`` (unchanged when cancelled).
    """
    win_loc_x, win_loc_y = window.current_location()
    win_w, win_h = window.current_size_accurate()

    layout = [
        [sg.Text(_('export_target_title'))],
        *page_scope_rows('EXP', total_pages, current_page),
        [sg.HorizontalSeparator()],
        [sg.Text(_('export_quality_label'))],
        [sg.Radio(_('export_quality_high'), 'EXPQGRP',
                  default=output_quality == 'high', key='-EXP_Q_HIGH-')],
        [sg.Radio(_('export_quality_low'), 'EXPQGRP',
                  default=output_quality == 'low', key='-EXP_Q_LOW-')],
        [sg.Push(), sg.Button(_('btn_ok'), key='-EXP_OK-'),
         sg.Button(_('btn_cancel'), key='-EXP_CANCEL-')],
    ]

    dlg = sg.Window(
        _('export_target_title'),
        layout,
        keep_on_top=True,
        modal=True,
        finalize=True,
        location=(int(win_loc_x + win_w / 2 - 180), int(win_loc_y + win_h / 2 - 140))
    )

    result = None
    quality = output_quality
    while True:
        ev, vals = dlg.read()
        if ev in (sg.WINDOW_CLOSED, '-EXP_CANCEL-'):
            result = None
            break
        elif handle_scope_event(dlg, ev, vals, 'EXP'):
            continue
        elif ev == '-EXP_OK-':
            result = read_page_scope(vals, 'EXP', total_pages, current_page)
            quality = 'low' if vals['-EXP_Q_LOW-'] else 'high'
            break

    dlg.close()
    return result, quality


def detect_on_page(page, patterns, keywords, force_ocr, ocr_lang):
    """Find sensitive-content rectangles on a single page.

    Chooses the cheapest accurate source: the digital text layer (no extra
    dependency) for PDF pages that actually carry text, falling back to OCR for
    scanned PDFs, imported images, or when the user forces OCR.

    Args:
        page: The :class:`ImageContainer` to scan.
        patterns: Iterable of keys from :data:`textsearch.PATTERN_DEFS`.
        keywords: Iterable of literal keyword strings.
        force_ocr: When True, skip the digital text layer and always OCR.
        ocr_lang: Tesseract language string for the OCR path.

    Returns:
        list[tuple]: ``(start_xy, end_xy)`` rectangles in original-image pixel
        coordinates, ready for :meth:`ImageContainer.add_rectangle`.
    """
    src = page.source_path
    is_pdf = bool(src) and src.lower().endswith('.pdf')

    if is_pdf and not force_ocr:
        try:
            if textsearch.page_has_text(src, page.page_index, page.password):
                return textsearch.find_boxes_digital(
                    src, page.page_index, page.render_scale, page.image.height,
                    patterns=patterns, keywords=keywords, password=page.password
                )
        except Exception:
            pass  # fall through to OCR

    if ocr.is_available():
        return ocr.find_boxes_ocr(page.image, patterns=patterns,
                                  keywords=keywords, lang=ocr_lang)
    return []


def prompt_auto_redact(window, total_pages, current_page):
    """Dialog to configure automatic detection of sensitive content.

    Lets the user pick which built-in patterns to detect, add free-text
    keywords, choose the page scope, and (when Tesseract is present) force OCR
    and select the OCR language.

    Returns:
        dict | None: ``{'patterns', 'keywords', 'target', 'force_ocr',
        'ocr_lang'}`` or ``None`` if cancelled. ``target`` is a sorted list of
        0-based page indices.
    """
    win_loc_x, win_loc_y = window.current_location()
    win_w, win_h = window.current_size_accurate()

    ocr_ok = ocr.is_available()
    ocr_langs = ocr.available_languages() or ['eng']
    # The combo is single-select, so default to the single system-locale code
    # (which is always in the list), not the combined 'xxx+eng' string.
    default_lang = ocr.system_language()
    # OCR model quality, shown with friendly labels mapped back to codes.
    model_display = {'fast': _('ocr_model_fast'), 'best': _('ocr_model_best')}
    model_codes = {v: k for k, v in model_display.items()}
    cur_model = ocr.get_ocr_model()

    pattern_keys = textsearch.available_patterns()
    pattern_rows = [
        [sg.Checkbox(_('pat_' + key), key='-PAT_' + key + '-', default=True, size=(20, 1))
         for key in pattern_keys[i:i + 2]]
        for i in range(0, len(pattern_keys), 2)
    ]
    pattern_rows.append([sg.Text(_('auto_keywords_label')),
                         sg.Input('', size=(26, 1), key='-AUTO_KW-')])

    ocr_rows = [
        [sg.Text(_('auto_ocr_lang')),
         sg.Combo(ocr_langs, default_value=default_lang, key='-AUTO_LANG-',
                  readonly=True, size=(9, 1), disabled=not ocr_ok),
         sg.Text(_('ocr_model_label')),
         sg.Combo(list(model_display.values()), default_value=model_display[cur_model],
                  key='-AUTO_MODEL-', readonly=True, size=(16, 1), disabled=not ocr_ok)],
        [sg.Checkbox(_('auto_force_ocr'), key='-AUTO_OCR-', default=False,
                     disabled=not ocr_ok)],
    ]

    layout = [
        [sg.Text(_('auto_title'), font=('Helvetica', 11, 'bold'))],
        [sg.Frame(_('auto_detect_label'), pattern_rows, expand_x=True)],
        [sg.Frame(_('auto_scope_label'),
                  page_scope_rows('AUTO', total_pages, current_page), expand_x=True)],
        [sg.Frame('OCR', ocr_rows, expand_x=True)],
        [sg.Push(), sg.Button(_('btn_ok'), key='-AUTO_OK-'),
         sg.Button(_('btn_cancel'), key='-AUTO_CANCEL-')],
    ]

    dlg = sg.Window(
        _('auto_title'),
        layout,
        keep_on_top=True,
        modal=True,
        finalize=True,
        location=(int(win_loc_x + win_w / 2 - 200), int(win_loc_y + win_h / 2 - 220))
    )

    result = None
    while True:
        ev, vals = dlg.read()
        if ev in (sg.WINDOW_CLOSED, '-AUTO_CANCEL-'):
            result = None
            break
        elif handle_scope_event(dlg, ev, vals, 'AUTO'):
            continue
        elif ev == '-AUTO_OK-':
            patterns = [key for key in textsearch.available_patterns()
                        if vals.get('-PAT_' + key + '-')]
            keywords = [k.strip() for k in (vals.get('-AUTO_KW-') or '').split(',')
                        if k.strip()]
            if not patterns and not keywords:
                sg.popup(_('auto_nothing_selected'), keep_on_top=True)
                continue
            # Persist the chosen OCR model quality for future downloads.
            ocr.set_ocr_model(model_codes.get(vals.get('-AUTO_MODEL-'), cur_model))
            target = read_page_scope(vals, 'AUTO', total_pages, current_page)
            result = {
                'patterns': patterns,
                'keywords': keywords,
                'target': target,
                'force_ocr': bool(vals.get('-AUTO_OCR-')),
                'ocr_lang': vals.get('-AUTO_LANG-') or default_lang,
            }
            break

    dlg.close()
    return result


def export_pages_to_pdf(window, pages, save_file_path, output_quality,
                        pointer_cursor, drawing_cursor):
    """Render the given pages with their redactions and write them to a PDF.

    Uses chunked parallel processing to limit memory use, and handles the
    progress bar, busy cursor and memory cleanup. Works for any number of
    pages (whole document, a sub-range or a single page).

    The output carries no document metadata (no title/author/creator/producer),
    so it never identifies the tool or the user. fpdf2 still stamps a neutral
    CreationDate, which cannot be cleanly suppressed.

    Args:
        window: The GUI window.
        pages: List of ImageContainer instances to export, in output order.
        save_file_path: Destination PDF path.
        output_quality: 'high' or 'low'.
        pointer_cursor: Cursor to restore on the window when done.
        drawing_cursor: Cursor to restore on the graph when done.

    Returns:
        int: Number of pages written.

    Raises:
        Exception: Propagated from the export pipeline; caller shows the popup.
    """
    out_pdf = FPDF(unit="pt")

    window.set_cursor('watch')
    window['-GRAPH-'].set_cursor('watch')
    window['-PROGRESS-'].update(current_count=0, visible=True)
    window.refresh()

    # Quality settings:
    # HIGH: JPEG 90 at full resolution (200 DPI)
    # LOW:  JPEG 85 at 55% scale (~110 DPI)
    quality = 90 if output_quality == 'high' else 85
    scale = 1 if output_quality == 'high' else 0.55

    total_pages = len(pages)

    try:
        # Progress callback for chunked processing (0-90%)
        def update_progress(completed, total):
            window['-PROGRESS-'].update(current_count=int(completed * 90 / total))
            window.refresh()

        # Use smaller chunks (50 pages) to limit memory usage
        for img_bytes, page_size in finalize_pages_chunked(
            pages,
            img_format='JPEG',
            quality=quality,
            scale=scale,
            chunk_size=50,
            progress_callback=update_progress
        ):
            out_pdf.add_page(format=page_size)
            out_pdf.image(img_bytes, x=0, y=0, w=out_pdf.w)
            del img_bytes  # Release image bytes immediately after adding to PDF
            del page_size

        # Writing PDF to disk (90-100%)
        window['-PROGRESS-'].update(current_count=95)
        window.refresh()

        out_pdf.output(save_file_path)

        window['-PROGRESS-'].update(current_count=100)
        window.refresh()

        return total_pages
    finally:
        # Ensure cleanup even on error
        del out_pdf
        gc.collect()
        window['-PROGRESS-'].update(current_count=0, visible=False)
        window.set_cursor(pointer_cursor)
        window['-GRAPH-'].set_cursor(drawing_cursor)


def find_scroll_canvas(column_element):
    """Return (canvas, frame_id) for a scrollable sg.Column.

    A scrollable Column normally exposes ``.Widget.canvas`` / ``.Widget.frame_id``,
    but when the column is nested inside an ``sg.Pane`` those convenience
    attributes are not set, so fall back to locating the inner tk Canvas and its
    frame window-item from the widget tree.
    """
    widget = column_element.Widget
    canvas = getattr(widget, 'canvas', None)
    frame_id = getattr(widget, 'frame_id', None)
    if canvas is not None and frame_id is not None:
        return (canvas, frame_id)

    stack = [widget]
    while stack:
        w = stack.pop()
        if isinstance(w, tk.Canvas) and w.cget('yscrollcommand'):
            ids = w.find_all()
            for i in ids:
                if w.type(i) == 'window':
                    return (w, i)
            if ids:
                return (w, ids[0])
        stack.extend(w.winfo_children())
    return (None, None)


def configure_canvas(event, canvas, frame_id, images, current_page):
    """Adjust canvas size. Necessary to update scrollbars."""
    if canvas is None or frame_id is None:
        return
    try:
        canvas.itemconfig(frame_id, width=images[current_page].scaled_image.width + 40)
    except IndexError:
        pass


def configure_frame(event, canvas):
    """Adjust scrollregion. Necessary to update scrollbars."""
    if canvas is None:
        return
    canvas.configure(scrollregion=canvas.bbox("all"))


def flip_to_page(window, images, page):
    """Update graph with next/previous image. Update page number display."""
    try:
        page = int(page)
    except ValueError:
        page = 0
    if page < 0:
        page = len(images) - 1
    if page > len(images) - 1:
        page = 0

    img = images[page]
    scale_graph_to_image(window, img.refresh().image)
    load_image_to_graph(window, img)
    window['-PAGE_NUM-'].update(value=int(page) + 1)
    return page


def load_image_to_graph(window, image, location=(0, 0)):
    """Load image to Graph element and adjust position."""
    window['-GRAPH-'].erase()
    id = window['-GRAPH-'].draw_image(data=image.data(), location=location)

    scale_graph_to_image(window, image.scaled_image)
    image.draw_rectangles_on_graph(window)
    image.id = id
    return id


def scale_graph_to_image(window, image):
    """Adjust Graph element size to the image (e.g. zoom actions)."""
    window['-GRAPH-'].Widget.config(width=image.width, height=image.height)


def main():
    """Main application entry point."""
    freeze_support()

    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description=_('cli_description'),
        prog='CoverUP'
    )
    parser.add_argument(
        'file',
        nargs='?',
        default=None,
        help=_('cli_file_help')
    )
    parser.add_argument(
        '--version', '-v',
        action='store_true',
        help=_('cli_version_help')
    )
    args = parser.parse_args()

    # Handle --version flag
    if args.version:
        print(f"CoverUP PDF {__version__}")
        sys.exit(0)

    # Store CLI file path for loading after window is created
    cli_file_path = args.file

    # Initialize
    about_text = _('about_text', version=__version__) + '\n\n' + _('hint_pan')

    first_load = True
    history_length = 30
    import_ppi = 200
    images = []
    file_path = None
    fill_color = 'black'
    current_page = 0
    drawing = False
    start_point = (0, 0)
    end_point = (0, 0)
    output_quality = 'high'
    edit_mode = 'draw'
    redact_mode = 'single'
    pointer_cursor = 'arrow' if sg.running_windows() else 'left_ptr'
    drawing_cursor = 'crosshair'
    image_bg_color = 'gray'
    temp_rectangle = None  # Track temporary drawing rectangle

    # Load fonts and create icons
    fontpath = get_fontpath()
    app_icon = create_app_icon(fontpath)
    icons = create_icons(fontpath)

    # Check for / create datadir
    datadir = user_data_dir('CoverUP', 'digidigital')
    try:
        if not os.path.exists(datadir):
            os.makedirs(datadir)
    except Exception:
        pass

    # Initialize workfile manager
    workfile_manager = WorkfileManager(datadir, history_length)

    # Create layout
    layout = create_layout(icons, image_bg_color)

    sg.theme('LightBlue2')

    # Create window at top-left corner
    window = sg.Window(
        _('app_title'),
        layout,
        icon=app_icon,
        element_justification="center",
        background_color='grey',
        size=(1300, 900),
        resizable=True,
        finalize=True,
        location=(0, 0)
    )

    # Set WM_CLASS for proper taskbar icon matching (Linux/Flatpak)
    try:
        window.TKroot.wm_class('coverup', 'coverup')
    except Exception:
        pass  # Ignore on non-Linux platforms

    # Detect changes of window size. The scroll Column is nested inside an
    # sg.Pane, so locate its canvas/frame from the widget tree.
    canvas, frame_id = find_scroll_canvas(window['-GRAPH_COLUMN-'])
    window.bind('<Configure>', 'Configure_Event')

    # Keyboard shortcuts
    window.bind('<Control-o>', 'LOAD_PDF')
    window.bind('<Control-s>', 'SAVE_PDF')
    window.bind('<Control-e>', 'SAVE_PDF')
    window.bind('<Control-m>', 'REDACT_CYCLE')
    window.bind('<Control-z>', 'UNDO')
    window.bind('<Control-y>', 'REDO')
    window.bind('<Control-Shift-Z>', 'REDO')
    window.bind('<Prior>', 'BACK')
    window.bind('<Next>', 'FORTH')
    window.bind('<Control-Left>', 'BACK')
    window.bind('<Control-Right>', 'FORTH')
    window.bind('<plus>', 'ZOOM_IN')
    window.bind('<equal>', 'ZOOM_IN')
    window.bind('<KP_Add>', 'ZOOM_IN')
    window.bind('<minus>', 'ZOOM_OUT')
    window.bind('<KP_Subtract>', 'ZOOM_OUT')
    window.bind('<F1>', 'ABOUT')
    window.bind('<Control-q>', 'EXIT')

    # Mouse-wheel scrolling / zooming and middle-button panning
    graph_widget = window['-GRAPH-'].Widget
    pan_cursor = make_pan_cursor(datadir)

    def _on_wheel(event):
        up = getattr(event, 'num', None) == 4 or getattr(event, 'delta', 0) > 0
        down = getattr(event, 'num', None) == 5 or getattr(event, 'delta', 0) < 0
        ctrl = bool(getattr(event, 'state', 0) & 4)
        if ctrl:
            # Ctrl + wheel zooms
            if up:
                window.write_event_value('ZOOM_IN', None)
                return
            if down:
                window.write_event_value('ZOOM_OUT', None)
                return
            return
        # Plain wheel scrolls the canvas vertically
        if canvas is not None:
            if up:
                canvas.yview_scroll(-3, 'units')
                return
            if down:
                canvas.yview_scroll(3, 'units')
                return
            return

    def _pan_press(event):
        if canvas is not None:
            canvas.scan_mark(event.x_root, event.y_root)
            window['-GRAPH-'].set_cursor(pan_cursor)

    def _pan_motion(event):
        if canvas is not None:
            canvas.scan_dragto(event.x_root, event.y_root, gain=1)

    def _pan_release(event):
        window['-GRAPH-'].set_cursor(TOOL_CURSORS.get(edit_mode, 'crosshair'))

    for _w in (graph_widget, canvas):
        if _w is None:
            continue
        _w.bind('<Button-4>', _on_wheel, add='+')
        _w.bind('<Button-5>', _on_wheel, add='+')
        _w.bind('<MouseWheel>', _on_wheel, add='+')

    if graph_widget is not None:
        graph_widget.bind('<ButtonPress-3>', _pan_press, add='+')
        graph_widget.bind('<B3-Motion>', _pan_motion, add='+')
        graph_widget.bind('<ButtonRelease-3>', _pan_release, add='+')

    # Keep the sidebar at a fixed fraction of the window width
    pane_widget = window['-PANE-'].Widget
    sidebar_fraction = SIDEBAR_WIDTH_FRACTION
    last_window_width = 0
    try:
        window.refresh()
        last_window_width = window.size[0]
        pane_widget.sash_place(0, int(last_window_width * sidebar_fraction), 0)
    except Exception:
        pass

    def _remember_sidebar_fraction(_event=None):
        nonlocal sidebar_fraction
        try:
            w = window.size[0]
            if w > 1:
                sidebar_fraction = pane_widget.sash_coord(0)[0] / w
        except Exception:
            pass

    pane_widget.bind('<ButtonRelease-1>', _remember_sidebar_fraction)

    # --- Page thumbnails (sidebar navigator) ------------------------------
    # FreeSimpleGUI has no way to clear a container, so thumbnail rows are
    # created once via extend_layout and then reused: on each load we update
    # the image/label of the slots we need and hide any surplus.
    thumb_slots = []  # list of (img_key, txt_key, row_key)
    thumb_bg = '#4d4d4d'

    def make_thumb_data(pil_image, max_w=150, max_h=190):
        thumb = pil_image.copy()
        thumb.thumbnail((max_w, max_h))
        with io.BytesIO() as b:
            thumb.save(b, format='PNG')
            return b.getvalue()

    def rebuild_thumbnails():
        """Populate the thumbnail strip for the currently loaded pages."""
        needed = len(images)
        for i in range(len(thumb_slots), needed):
            ik, tk, rk = f'-THUMB_IMG_{i}-', f'-THUMB_TXT_{i}-', f'-THUMB_ROW_{i}-'
            row = [sg.Column(
                [[sg.Image(key=ik, enable_events=True, background_color=thumb_bg, pad=(0, 0))],
                 [sg.Text('', key=tk, text_color='white', background_color=thumb_bg,
                          font=('Helvetica', 8), pad=(0, (0, 6)))]],
                key=rk, background_color=thumb_bg, element_justification='center',
                pad=(2, 2))]
            try:
                window.extend_layout(window['-THUMBS-'], [row])
            except Exception:
                break
            thumb_slots.append((ik, tk, rk))

        for i, (ik, tk, rk) in enumerate(thumb_slots):
            try:
                if i < needed:
                    window[ik].update(data=make_thumb_data(images[i].image), visible=True)
                    window[tk].update(f'{i + 1}', visible=True)
                    window[rk].update(visible=True)
                else:
                    window[rk].update(visible=False)
            except Exception:
                pass
        try:
            window['-THUMBS-'].contents_changed()
        except Exception:
            pass

    # Initialise the redaction mode indicator
    redact_mode = set_redact_mode(window, icons, redact_mode)

    # Load file from command line argument if provided
    if cli_file_path:
        try:
            images, file_path, current_page, fill_color, output_quality = _do_load_file(
                cli_file_path, import_ppi, window, workfile_manager, images,
                fill_color, output_quality, icons, pointer_cursor, drawing_cursor
            )
            first_load = False
            rebuild_thumbnails()
        except Exception as e:
            window['-PAGE_TOTAL-'].update('0')
            window['-PROGRESS-'].update(current_count=0)
            sg.popup(_('error_loading'), str(e))

    # Main event loop
    while True:
        event, values = window.read()

        if event in (sg.WINDOW_CLOSED, 'EXIT'):
            break

        elif event == 'Configure_Event':
            configure_canvas(event, canvas, frame_id, images, current_page)
            configure_frame(event, canvas)
            # Maintain the sidebar fraction across window resizes
            try:
                w = window.size[0]
                if w > 1 and abs(w - last_window_width) > 2:
                    last_window_width = w
                    pane_widget.sash_place(0, int(w * sidebar_fraction), 0)
            except Exception:
                pass

        elif event == 'CHANGE_COLOR':
            fill_color = toggle_color(window, icons, fill_color)

        elif event == 'EDIT_MODE':
            edit_mode = 'draw' if edit_mode == 'erase' else 'erase'
            edit_mode = set_tool(window, icons, edit_mode)

        elif event == 'RMODE_all':
            redact_mode = set_redact_mode(window, icons, 'all')

        elif event == 'RMODE_single':
            redact_mode = set_redact_mode(window, icons, 'single')

        elif event == 'RMODE_ask':
            redact_mode = set_redact_mode(window, icons, 'ask')

        elif event == 'REDACT_CYCLE':
            cycle = ['single', 'all', 'ask']
            redact_mode = set_redact_mode(
                window, icons, cycle[(cycle.index(redact_mode) + 1) % len(cycle)]
            )

        elif event == 'ABOUT':
            win_loc_x, win_loc_y = window.current_location()
            win_w, win_h = window.current_size_accurate()
            sg.popup_no_titlebar(
                about_text,
                grab_anywhere=False,
                location=(win_loc_x + win_w/2 - 185, win_loc_y + win_h/2 - 200),
                keep_on_top=True,
                background_color='silver',
                button_color='grey'
            )

        elif event == 'LOAD_PDF':
            workfile_manager.save(images, current_page, fill_color, output_quality)

            # Open home-folder when first time loading a pdf
            if first_load:
                # Prefer SNAP_REAL_HOME if available
                snap_real = os.environ.get("SNAP_REAL_HOME")
                home_folder = Path(snap_real) if snap_real else Path.home()
            else:
                home_folder = None

            load_file_path = pick_open_file(
                _('dialog_load_file'),
                home_folder,
                [
                    (_('filetype_all'), '*.pdf *.PDF *.jpg *.JPG *.jpeg *.JPEG *.png *.PNG *.tif *.TIF *.tiff *.TIFF'),
                    (_('filetype_pdf'), '*.pdf *.PDF'),
                    (_('filetype_image'), '*.jpg *.JPG *.jpeg *.JPEG *.png *.PNG *.tif *.TIF *.tiff *.TIFF')
                ],
                parent_winid=window.TKroot.winfo_id()
            )

            if load_file_path:
                try:
                    images, file_path, current_page, fill_color, output_quality = _do_load_file(
                        load_file_path, import_ppi, window, workfile_manager, images,
                        fill_color, output_quality, icons, pointer_cursor, drawing_cursor
                    )
                    first_load = False
                    rebuild_thumbnails()
                except Exception as e:
                    window['-PAGE_TOTAL-'].update('0')
                    window['-PROGRESS-'].update(current_count=0)
                    sg.popup(_('error_occurred'), str(e))

        # Actions to be executed only when images / PDF files have been loaded
        elif images:
            if event == '-PAGE_NUM-':
                try:
                    page = int(values['-PAGE_NUM-'])
                    current_page = flip_to_page(window, images, page - 1)
                except ValueError:
                    pass

            elif isinstance(event, str) and event.startswith('-THUMB_IMG_'):
                # Jump to the clicked page thumbnail.
                try:
                    pidx = int(event[len('-THUMB_IMG_'):-1])
                    if 0 <= pidx < len(images):
                        current_page = flip_to_page(window, images, pidx)
                except ValueError:
                    pass

            elif event == 'ZOOM_IN':
                images[current_page].increase_zoom()
                scale_graph_to_image(window, images[current_page].scaled_image)
                load_image_to_graph(window, images[current_page])
                window['-ZOOM_LEVEL-'].update(f"{ImageContainer.zoom_factor}%")

            elif event == 'ZOOM_OUT':
                images[current_page].decrease_zoom()
                scale_graph_to_image(window, images[current_page].scaled_image)
                load_image_to_graph(window, images[current_page])
                window['-ZOOM_LEVEL-'].update(f"{ImageContainer.zoom_factor}%")

            elif event == 'FORTH':
                current_page = flip_to_page(window, images, current_page + 1)

            elif event == 'BACK':
                current_page = flip_to_page(window, images, current_page - 1)

            elif event == 'UNDO':
                images[current_page].undo(window)

            elif event == 'REDO':
                images[current_page].redo(window)

            elif event == 'SAVE_PDF':
                # Ask which pages to export and at what quality
                target, output_quality = prompt_export_target(
                    window, len(images), current_page, output_quality
                )
                if target is None:
                    continue
                if not target:
                    sg.popup(_('error_no_pages_selected'), keep_on_top=True)
                    continue

                export_pages = [images[i] for i in target]

                # Pre-fill with the loaded filename
                suffix = _('suffix_redacted') if len(target) == len(images) else _('suffix_range')
                default_filename = ""
                if file_path:
                    base_name = os.path.splitext(os.path.basename(file_path))[0]
                    default_filename = f"{base_name}{suffix}.pdf"

                save_dir = os.path.dirname(file_path) if file_path else None
                save_file_path = pick_save_file(
                    _('dialog_save_pdf'),
                    save_dir,
                    default_filename,
                    ".pdf",
                    [(_('filetype_pdf'), '*.pdf *.PDF')],
                    parent_winid=window.TKroot.winfo_id()
                )

                if save_file_path:
                    try:
                        total_pages = export_pages_to_pdf(
                            window, export_pages, save_file_path,
                            output_quality, pointer_cursor, drawing_cursor
                        )

                        workfile_manager.save(images, current_page, fill_color, output_quality)

                        # Show success message
                        window['-PROGRESS-'].update(current_count=0)
                        saved_filename = os.path.basename(save_file_path)
                        win_loc_x, win_loc_y = window.current_location()
                        win_w, win_h = window.current_size_accurate()
                        sg.popup_no_titlebar(
                            _plural('save_success', 'save_success_plural', total_pages,
                                    filename=saved_filename),
                            location=(win_loc_x + win_w/2 - 185, win_loc_y + win_h/2 - 200),
                            keep_on_top=True,
                            background_color='silver',
                            button_color='grey'
                        )

                    except Exception as e:
                        window['-PROGRESS-'].update(current_count=0)
                        sg.popup(_('error_occurred'), str(e))

            elif event == 'AUTO_REDACT':
                cfg = prompt_auto_redact(window, len(images), current_page)
                if cfg is None:
                    continue
                target = cfg['target']
                if not target:
                    sg.popup(_('error_no_pages_selected'), keep_on_top=True)
                    continue

                win_loc_x, win_loc_y = window.current_location()
                win_w, win_h = window.current_size_accurate()
                center = (int(win_loc_x + win_w / 2 - 185), int(win_loc_y + win_h / 2 - 200))

                window.set_cursor('watch')
                window['-GRAPH-'].set_cursor('watch')
                window['-PROGRESS-'].update(current_count=0, visible=True)
                total_added = 0
                pages_hit = 0
                try:
                    for idx, p in enumerate(target):
                        window['-PROGRESS-'].update(current_count=int((idx + 1) * 100 / len(target)))
                        window.refresh()
                        boxes = detect_on_page(
                            images[p], cfg['patterns'], cfg['keywords'],
                            cfg['force_ocr'], cfg['ocr_lang']
                        )
                        if boxes:
                            pages_hit += 1
                        for start_xy, end_xy in boxes:
                            images[p].add_rectangle(start_xy, end_xy, fill_color)
                            total_added += 1
                except Exception as e:
                    sg.popup(_('error_occurred'), str(e), keep_on_top=True)
                finally:
                    window['-PROGRESS-'].update(current_count=0, visible=False)
                    window.set_cursor(pointer_cursor)
                    window['-GRAPH-'].set_cursor(drawing_cursor)

                # Redraw the current page so any new bars on it become visible.
                current_page = flip_to_page(window, images, current_page)

                if total_added:
                    workfile_manager.save(images, current_page, fill_color, output_quality)
                    sg.popup_no_titlebar(
                        _plural('auto_done', 'auto_done_plural', total_added, pages=pages_hit),
                        location=center, keep_on_top=True,
                        background_color='silver', button_color='grey'
                    )
                else:
                    sg.popup_no_titlebar(
                        _('auto_none'), location=center, keep_on_top=True,
                        background_color='silver', button_color='grey'
                    )

            # Draw on Graph
            elif event == '-GRAPH-' and edit_mode == 'draw':
                x, y = values['-GRAPH-']
                y = -y  # Flip y-coordinate
                # Begin drawing
                if not drawing:
                    start_point = (int(x), int(y))
                    drawing = True

                # Draw a temporary red rectangle during drawing as position indicator
                else:
                    if temp_rectangle is not None:
                        try:
                            window['-GRAPH-'].delete_figure(temp_rectangle)
                        except Exception:
                            pass
                        temp_rectangle = None
                    end_point = (x, y)
                    if start_point[0] < end_point[0] and start_point[1] < end_point[1]:
                        temp_rectangle = window['-GRAPH-'].draw_rectangle(
                            (start_point[0], -start_point[1]),
                            (end_point[0], -end_point[1]),
                            fill_color='red',
                            line_color='red',
                            line_width=None
                        )

            # Conclude drawing
            elif event == '-GRAPH-+UP':
                drawing = False
                x, y = values['-GRAPH-']

                if edit_mode == 'draw':
                    if temp_rectangle is not None:
                        try:
                            window['-GRAPH-'].delete_figure(temp_rectangle)
                        except Exception:
                            pass
                        temp_rectangle = None
                    if start_point[0] < end_point[0] and start_point[1] < end_point[1]:
                        y = -y  # Flip y-coordinate
                        end_point = (x, y)

                        start_orig, end_orig = images[current_page].draw_rectangle(
                            window, start_point, end_point, fill=fill_color
                        )

                        # Replicate the bar onto other pages depending on the mode
                        if redact_mode != 'single' and start_orig is not None:
                            if redact_mode == 'all':
                                target = list(range(len(images)))
                            else:
                                target = prompt_page_range(window, len(images))

                            if target:
                                # The bar was already drawn on the current page; if it
                                # is not part of the target, remove it again.
                                if current_page not in target:
                                    images[current_page].undo(window)
                                for p in target:
                                    if p != current_page:
                                        images[p].add_rectangle(start_orig, end_orig, fill_color)
                                workfile_manager.save(images, current_page, fill_color, output_quality)

                elif edit_mode == 'erase':
                    figures = window['-GRAPH-'].get_figures_at_location((x, y))
                    edit_mode = set_tool(window, icons, 'draw')
                    if (figures and len(figures) > 1 and
                            0 <= current_page < len(images) and
                            images[current_page].rectangles):
                        try:
                            window['-GRAPH-'].delete_figure(figures[-1])
                            images[current_page].rectangles = [
                                item for item in images[current_page].rectangles
                                if item[3] != figures[-1]
                            ]
                        except Exception:
                            pass

            elif event == 'DELETE_ALL':
                win_loc_x, win_loc_y = window.current_location()
                win_w, win_h = window.current_size_accurate()

                result = sg.popup_ok_cancel(
                    _('confirm_delete_all'),
                    no_titlebar=True,
                    location=(win_loc_x + win_w/2 - 185, win_loc_y + win_h/2 - 200),
                    keep_on_top=True,
                    background_color='silver',
                    button_color='grey'
                )

                if result == 'OK':
                    try:
                        delete_all_rectangles(images, workfile_manager.delete)
                        current_page = flip_to_page(window, images, current_page)
                        workfile_manager.save(images, current_page, fill_color, output_quality)
                    except Exception:
                        pass

    # Save workfile only if we have loaded images
    if images:
        try:
            workfile_manager.save(images, current_page, fill_color, output_quality)
        except Exception:
            pass  # Don't crash on exit if save fails

    window.close()


if __name__ == "__main__":
    main()
