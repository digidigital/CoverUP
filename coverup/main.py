#!/usr/bin/env python3
"""
CoverUP PDF - Main application entry point.

A tool for redacting PDF files and images.
Licensed under GPL-3.0
(c) 2024 - 2026 Björn Seipel
"""

import gc
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime
from multiprocessing import freeze_support

import FreeSimpleGUI as sg
from fpdf import FPDF
from appdirs import user_data_dir

from coverup import __version__
from coverup.image_container import ImageContainer, delete_all_rectangles, finalize_pages_chunked
from coverup.document_loader import load_document
from coverup.workfile import WorkfileManager
from coverup.ui import (
    get_fontpath, create_icons, create_app_icon, create_layout,
    toggle_edit_mode, toggle_quality, toggle_color
)
from coverup.i18n import _, _plural


def configure_canvas(event, canvas, frame_id, images, current_page):
    """Adjust canvas size. Necessary to update scrollbars."""
    try:
        canvas.itemconfig(frame_id, width=images[current_page].scaled_image.width + 40)
    except IndexError:
        pass


def configure_frame(event, canvas):
    """Adjust scrollregion. Necessary to update scrollbars."""
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
    about_text = _('about_text', version=__version__)

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

    # Detect changes of window size
    frame_id = window['-GRAPH_COLUMN-'].Widget.frame_id
    canvas = window['-GRAPH_COLUMN-'].Widget.canvas
    window.bind('<Configure>', 'Configure_Event')

    # Load file from command line argument if provided
    if cli_file_path:
        try:
            window.set_cursor('watch')
            window['-GRAPH-'].set_cursor('watch')
            window.refresh()

            ImageContainer.zoom_factor = 100
            images, file_path, current_page, new_fill_color, new_output_quality = load_document(
                cli_file_path, import_ppi, window, workfile_manager
            )

            # Apply restored settings if available
            if new_fill_color and fill_color != new_fill_color:
                fill_color = toggle_color(window, icons, fill_color)
            if new_output_quality and output_quality != new_output_quality:
                output_quality = toggle_quality(window, icons, output_quality)

            first_load = False
            window['-PROGRESS-'].update(current_count=0)
            current_page = flip_to_page(window, images, current_page)
            window.set_title(_('app_title_with_file', filename=os.path.basename(file_path)))

        except Exception as e:
            window['-PAGE_TOTAL-'].update('0')
            window['-PROGRESS-'].update(current_count=0)
            sg.popup(_('error_loading'), str(e))

        window.set_cursor(pointer_cursor)
        window['-GRAPH-'].set_cursor(drawing_cursor)

    # Main event loop
    while True:
        event, values = window.read()

        if event in (sg.WINDOW_CLOSED, 'EXIT'):
            break

        elif event == 'Configure_Event':
            configure_canvas(event, canvas, frame_id, images, current_page)
            configure_frame(event, canvas)

        elif event == 'CHANGE_COLOR':
            fill_color = toggle_color(window, icons, fill_color)

        elif event == 'TOGGLE_QUALITY':
            output_quality = toggle_quality(window, icons, output_quality)

        elif event == 'EDIT_MODE':
            edit_mode = toggle_edit_mode(window, icons, edit_mode)

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
                first_load = False
                home_folder = Path.home()
            else:
                home_folder = None

            load_file_path = sg.popup_get_file(
                _('dialog_load_file'),
                initial_folder=home_folder,
                grab_anywhere=True,
                keep_on_top=True,
                no_window=True,
                show_hidden=True,
                file_types=(
                    (_('filetype_all'), '*.pdf *.PDF *.jpg *.JPG *.jpeg *.JPEG *.png *.PNG'),
                    (_('filetype_pdf'), '*.pdf *.PDF'),
                    (_('filetype_image'), '*.jpg *.JPG *.jpeg *.JPEG *.png *.PNG')
                )
            )

            if load_file_path:
                try:
                    window.set_cursor('watch')
                    window['-GRAPH-'].set_cursor('watch')
                    window.refresh()

                    ImageContainer.zoom_factor = 100
                    images, file_path, current_page, new_fill_color, new_output_quality = load_document(
                        load_file_path, import_ppi, window, workfile_manager
                    )

                    # Apply restored settings if available
                    if new_fill_color and fill_color != new_fill_color:
                        fill_color = toggle_color(window, icons, fill_color)
                    if new_output_quality and output_quality != new_output_quality:
                        output_quality = toggle_quality(window, icons, output_quality)

                    window['-PROGRESS-'].update(current_count=0)
                    current_page = flip_to_page(window, images, current_page)
                    window.set_title(_('app_title_with_file', filename=os.path.basename(file_path)))

                except Exception as e:
                    window['-PAGE_TOTAL-'].update('0')
                    window['-PROGRESS-'].update(current_count=0)
                    sg.popup(_('error_occurred'), str(e))

                window.set_cursor(pointer_cursor)
                window['-GRAPH-'].set_cursor(drawing_cursor)

        # Actions to be executed only when images / PDF files have been loaded
        elif images:
            if event == '-PAGE_NUM-':
                try:
                    page = int(values['-PAGE_NUM-'])
                    current_page = flip_to_page(window, images, page - 1)
                except ValueError:
                    pass

            elif event == 'ZOOM_IN':
                images[current_page].increase_zoom()
                scale_graph_to_image(window, images[current_page].scaled_image)
                load_image_to_graph(window, images[current_page])

            elif event == 'ZOOM_OUT':
                images[current_page].decrease_zoom()
                scale_graph_to_image(window, images[current_page].scaled_image)
                load_image_to_graph(window, images[current_page])

            elif event == 'FORTH':
                current_page = flip_to_page(window, images, current_page + 1)

            elif event == 'BACK':
                current_page = flip_to_page(window, images, current_page - 1)

            elif event == 'UNDO':
                images[current_page].undo(window)

            elif event == 'SAVE_PDF' or event == 'EXPORT_PAGE':
                # Pre-fill with the loaded filename
                default_filename = ""
                if file_path:
                    base_name = os.path.splitext(os.path.basename(file_path))[0]
                    if event == 'EXPORT_PAGE':
                        default_filename = f"{base_name}{_('suffix_page')}{current_page + 1}.pdf"
                    else:
                        default_filename = f"{base_name}{_('suffix_redacted')}.pdf"

                save_file_path = sg.popup_get_file(
                    _('dialog_save_pdf'),
                    no_window=True,
                    show_hidden=True,
                    keep_on_top=True,
                    save_as=True,
                    file_types=((_('filetype_pdf'), '*.pdf *.PDF'),),
                    default_extension=".pdf",
                    default_path=default_filename
                )

                if save_file_path:
                    try:
                        out_pdf = FPDF(unit="pt")
                        out_pdf.set_creator(f'CoverUp PDF {__version__}')
                        out_pdf.set_creation_date(datetime.today())
                        window.set_cursor('watch')
                        window['-GRAPH-'].set_cursor('watch')
                        window.refresh()

                        # Quality settings:
                        # HIGH: JPEG 90 at full resolution (200 DPI)
                        # LOW:  JPEG 85 at 55% scale (~110 DPI)
                        quality = 90 if output_quality == 'high' else 85
                        scale = 1 if output_quality == 'high' else 0.55

                        if event == 'EXPORT_PAGE':
                            # Single page export
                            window['-PROGRESS-'].update(current_count=25)
                            window.refresh()

                            out_pdf.add_page(format=(
                                images[current_page].height_in_pt,
                                images[current_page].width_in_pt
                            ))

                            window['-PROGRESS-'].update(current_count=50)
                            window.refresh()

                            include_image = images[current_page].finalized_image(
                                'JPEG', image_quality=quality, scale=scale
                            )
                            out_pdf.image(include_image, x=0, y=0, w=out_pdf.w)
                            del include_image  # Release image bytes immediately

                            window['-PROGRESS-'].update(current_count=75)
                            window.refresh()

                            out_pdf.output(save_file_path)
                            total_pages = 1

                        else:
                            # Use chunked parallel processing for multi-page export
                            # This limits memory usage by processing in chunks of 200 pages
                            total_pages = len(images)

                            # Progress callback for chunked processing (0-90%)
                            def update_progress(completed, total):
                                progress = int(completed * 90 / total)
                                window['-PROGRESS-'].update(current_count=progress)
                                window.refresh()

                            # Process chunks and add to PDF as we go
                            # Use smaller chunks (50 pages) to limit memory usage
                            for img_bytes, page_size in finalize_pages_chunked(
                                images,
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

                        # Clean up FPDF object to release memory
                        del out_pdf

                        # Force garbage collection to reclaim memory from large exports
                        gc.collect()

                        window.set_cursor(pointer_cursor)
                        window['-GRAPH-'].set_cursor(drawing_cursor)
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
                        window.set_cursor(pointer_cursor)
                        window['-GRAPH-'].set_cursor(drawing_cursor)
                        sg.popup(_('error_occurred'), str(e))
                    finally:
                        # Ensure cleanup even on error
                        try:
                            del out_pdf
                        except NameError:
                            pass
                        gc.collect()

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

                        images[current_page].draw_rectangle(window, start_point, end_point, fill=fill_color)

                elif edit_mode == 'erase':
                    figures = window['-GRAPH-'].get_figures_at_location((x, y))
                    edit_mode = toggle_edit_mode(window, icons, edit_mode)
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
