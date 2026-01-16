"""
Document loading functionality for CoverUP PDF.

This module handles loading PDF and image files, with optional multiprocessing
support for faster PDF page rendering on multi-core systems.
"""

import io
import os
from concurrent.futures import ProcessPoolExecutor, wait as wait_futures

import FreeSimpleGUI as sg
import pypdfium2 as pdfium
from PIL import Image

from coverup.image_container import ImageContainer
from coverup.utils import is_valid_file_type, get_worker_count
from coverup.i18n import _


def _render_pdf_page(args):
    """
    Render a single PDF page to image bytes. Worker function for multiprocessing.

    This function runs in a separate process and must be picklable.
    It opens the PDF file independently to avoid pickling issues with PdfDocument.

    Args:
        args: Tuple of (file_path, page_index, scale, password)

    Returns:
        Tuple of (page_index, image_bytes, page_size) where image_bytes is PNG data.
    """
    file_path, page_index, scale, password = args
    try:
        if password:
            pdf = pdfium.PdfDocument(file_path, password=password)
        else:
            pdf = pdfium.PdfDocument(file_path)

        page = pdf[page_index]
        pil_image = page.render(scale=scale).to_pil()
        page_size = page.get_size()

        # Convert PIL image to bytes for pickling
        import io
        buffer = io.BytesIO()
        pil_image.save(buffer, format='JPEG')
        image_bytes = buffer.getvalue()

        return (page_index, image_bytes, page_size)
    except Exception as e:
        return (page_index, None, str(e))


def load_document(load_file_path, import_ppi, window, workfile_manager, show_restore_prompt=True):
    """
    Load a PDF or image file and return the loaded data.

    Args:
        load_file_path: Path to the file to load
        import_ppi: PPI setting for import
        window: The GUI window object
        workfile_manager: WorkfileManager instance for session handling
        show_restore_prompt: Whether to show the restore work session prompt

    Returns:
        tuple: (images_list, file_path, current_page, fill_color_change, quality_change)
               fill_color_change and quality_change are the values to set, or None if no change needed

    Raises:
        FileNotFoundError: If the file doesn't exist
        ValueError: If the file type is not supported or PDF is encrypted without password
    """
    if not load_file_path or not os.path.isfile(load_file_path):
        raise FileNotFoundError(_('error_file_not_found', path=load_file_path))

    if not is_valid_file_type(load_file_path):
        ext = os.path.splitext(load_file_path)[1]
        raise ValueError(_('error_unsupported_type', ext=ext))

    images_list = []
    loaded_page = 0
    new_fill_color = None
    new_output_quality = None

    # Import PDF files
    if load_file_path.lower().endswith('.pdf'):
        pdf = None
        pdf_password = None  # Track password for multiprocessing

        # Try to open the PDF, handle encrypted files
        try:
            pdf = pdfium.PdfDocument(load_file_path)
        except pdfium.PdfiumError as e:
            # Check if the error is due to password protection
            if "password" in str(e).lower() or "encrypted" in str(e).lower():
                # Prompt for password
                win_loc_x, win_loc_y = window.current_location()
                win_w, win_h = window.current_size_accurate()
                password = sg.popup_get_text(
                    _('password_prompt'),
                    title=_('password_title'),
                    location=(win_loc_x + win_w/2 - 150, win_loc_y + win_h/2 - 75),
                    keep_on_top=True,
                    password_char='*'
                )
                if password:
                    try:
                        pdf = pdfium.PdfDocument(load_file_path, password=password)
                        pdf_password = password  # Store for multiprocessing
                    except pdfium.PdfiumError:
                        raise ValueError(_('error_incorrect_password'))
                else:
                    raise ValueError(_('error_password_required'))
            else:
                raise

        if pdf is None:
            raise ValueError(_('error_pdf_open_failed'))

        total_pages = len(pdf)
        window['-PAGE_TOTAL-'].update(total_pages)
        scale = int(import_ppi / 72)

        # Use cores-1 workers (leaves one core for UI), limited by page count
        max_workers = get_worker_count(max_tasks=total_pages)

        # Prepare arguments for worker processes
        render_args = [
            (load_file_path, i, scale, pdf_password)
            for i in range(total_pages)
        ]

        # Pre-allocate list to maintain page order
        results = [None] * total_pages
        completed = 0

        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_render_pdf_page, args): args[1] for args in render_args}
            pending = set(futures.keys())

            # Poll for completed futures with timeout to keep GUI responsive
            while pending:
                # Use short timeout to allow GUI updates
                done, pending = wait_futures(pending, timeout=0.05)

                for future in done:
                    result = future.result()

                    if result[1] is None:
                        # Error occurred
                        raise ValueError(_('error_page_render_failed', page=result[0] + 1, error=result[2]))

                    # Convert bytes back to PIL Image
                    pil_image = Image.open(io.BytesIO(result[1]))
                    results[result[0]] = ImageContainer(pil_image, result[2])

                    completed += 1
                    window['-PROGRESS-'].update(current_count=int(completed * 100 / total_pages))
                    window.refresh()

        images_list = results

    # Import single images
    elif load_file_path.lower().endswith(('.jpg', '.jpeg', '.png')):
        window['-PAGE_TOTAL-'].update(1)
        import_image = Image.open(load_file_path, mode='r')

        # Fit large images ppi-wise in DIN A4 format with about import_ppi dpi
        width, height = import_image.size

        a4_short_side = round(8.267 * import_ppi)
        a4_long_side = round(11.693 * import_ppi)

        # Portrait
        if height >= width:
            if width/height >= 210/297:
                # A4 portrait or short side longer
                scale_factor = a4_short_side / width
            else:
                # A4 portrait long side longer
                scale_factor = a4_long_side / height

        # Landscape
        else:
            if width/height >= 297/210:
                # A4 landscape or long side longer
                scale_factor = a4_long_side / width
            else:
                # A4 landscape short side longer
                scale_factor = a4_short_side / height

        # Scale images larger than A4 at import_ppi only
        if scale_factor < 1:
            width = int(width * scale_factor)
            height = int(height * scale_factor)
            new_image = import_image.resize((width, height), resample=Image.Resampling.LANCZOS)
        else:
            new_image = import_image.copy()

        import_image.close()

        # pagesize in ppi @ 72 ppi for pdf output
        width_ppi = int(width/import_ppi*72)
        height_ppi = int(height/import_ppi*72)

        images_list.append(ImageContainer(new_image, (width_ppi, height_ppi)))

    # Set file_path for workfile functions
    workfile_manager.set_file_path(load_file_path)

    # Check for previous work session
    work_data = workfile_manager.load()
    if show_restore_prompt and work_data and work_data['pages'] == len(images_list):
        win_loc_x, win_loc_y = window.current_location()
        win_w, win_h = window.current_size_accurate()
        result = sg.popup_ok_cancel(
            _('confirm_restore_session'),
            no_titlebar=True,
            location=(win_loc_x+win_w/2-185, win_loc_y+win_h/2-200),
            keep_on_top=True,
            background_color='silver',
            button_color='grey'
        )
        try:
            if result == 'OK':
                for rectangles, page in zip(work_data['rectangles'], images_list):
                    page.rectangles = [
                        [tuple(rectangle[0]), tuple(rectangle[1]), rectangle[2], rectangle[3]]
                        for rectangle in rectangles
                    ]
                loaded_page = int(work_data['current_page'])
                new_fill_color = work_data['fill_color']
                new_output_quality = work_data['output_quality']
            else:
                workfile_manager.delete()
        except Exception:
            pass

    return images_list, load_file_path, loaded_page, new_fill_color, new_output_quality
