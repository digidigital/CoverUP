"""
ImageContainer class for managing PDF page images and redaction rectangles.

This module provides the ImageContainer class which wraps a PIL Image with
additional functionality for managing redaction rectangles, zoom levels,
and export operations.

Each page of a loaded document is represented by an ImageContainer instance.
"""

import gc
import io
from concurrent.futures import ProcessPoolExecutor, wait as wait_futures

from PIL import Image, ImageDraw

from coverup.utils import get_worker_count
from coverup.i18n import _


def _finalize_page_worker(args):
    """
    Worker function for parallel page finalization. Runs in separate process.

    Args:
        args: Tuple of (page_index, image_bytes, rectangles, format, quality, scale, page_size)

    Returns:
        Tuple of (page_index, finalized_image_bytes, page_size) or (page_index, None, error_msg)
    """
    page_index, image_bytes, rectangles, img_format, quality, scale, page_size = args
    image = None
    input_buffer = None
    output_buffer = None
    try:
        # Reconstruct PIL image from bytes
        input_buffer = io.BytesIO(image_bytes)
        image = Image.open(input_buffer)
        # Load image data into memory so we can close the buffer
        image.load()

        # Draw rectangles on image
        draw = ImageDraw.Draw(image)
        for rect in rectangles:
            # rect format: (start_coords, end_coords, color, graph_id)
            draw.rectangle(xy=[rect[0], rect[1]], fill=rect[2])

        # Convert to RGB for JPEG
        if img_format in ('JPEG', 'JPG'):
            rgb_image = image.convert('RGB')
            image.close()
            image = rgb_image

        # Scale if needed
        if scale != 1:
            new_width = int(image.width * scale)
            new_height = int(image.height * scale)
            scaled_image = image.resize((new_width, new_height), resample=Image.Resampling.LANCZOS)
            image.close()
            image = scaled_image

        # Save to bytes
        output_buffer = io.BytesIO()
        if img_format in ('JPEG', 'JPG'):
            image.save(output_buffer, format='JPEG', quality=quality, optimize=True)
        else:
            image.save(output_buffer, format='PNG')

        result_bytes = output_buffer.getvalue()
        return (page_index, result_bytes, page_size)
    except Exception as e:
        return (page_index, None, str(e))
    finally:
        # Ensure all resources are released
        if image is not None:
            try:
                image.close()
            except Exception:
                pass
        if input_buffer is not None:
            try:
                input_buffer.close()
            except Exception:
                pass
        if output_buffer is not None:
            try:
                output_buffer.close()
            except Exception:
                pass


class ImageContainer:
    """
    Container for images of PDF pages with redaction rectangle support.

    Manages a single page image along with its redaction rectangles,
    zoom state, and provides methods for drawing, exporting, and
    manipulating the page content.

    Attributes:
        image: Original PIL Image of the page.
        size: Tuple of (height_pt, width_pt) for PDF output dimensions.
        height_in_pt: Height in PDF points for export.
        width_in_pt: Width in PDF points for export.
        scaled_image: Current scaled version of the image for display.
        id: Graph element ID when displayed.
        rectangles: List of redaction rectangles as
                    [(start_coords, end_coords, color, graph_id), ...].

    Class Attributes:
        zoom_factor: Shared zoom level (percentage) across all instances.
    """

    zoom_factor = 100

    def __init__(self, image, size=(0, 0), rectangles=None):
        """
        Initialize an ImageContainer.

        Args:
            image: PIL Image object for this page.
            size: Tuple of (height_pt, width_pt) for PDF dimensions.
            rectangles: Optional list of existing rectangles.
        """
        self.image = image
        self.size = size
        self.height_in_pt = size[0]
        self.width_in_pt = size[1]
        self.scaled_image = self.image
        self.id = None

        # List of rectangles: [(start_coords, end_coords, color, graph_id), ...]
        self.rectangles = list() if rectangles is None else rectangles

    def close(self):
        """Release all image resources held by this container."""
        # Close scaled image if it's different from original
        if self.scaled_image is not None and self.scaled_image is not self.image:
            try:
                self.scaled_image.close()
            except Exception:
                pass
            self.scaled_image = None
        # Close the original image
        if self.image is not None:
            try:
                self.image.close()
            except Exception:
                pass
            self.image = None

    def increase_zoom(self, number=20):
        """Zoom in on the image. Returns new zoom_factor."""
        ImageContainer.zoom_factor += number
        if ImageContainer.zoom_factor > 240:
            ImageContainer.zoom_factor = 240
        else:
            self.scale_image()
        return [ImageContainer.zoom_factor]

    def decrease_zoom(self, number=20):
        """Zoom out of the image. Returns new zoom_factor."""
        ImageContainer.zoom_factor -= number
        if ImageContainer.zoom_factor < 20:
            ImageContainer.zoom_factor = 20
        else:
            self.scale_image()
        return [ImageContainer.zoom_factor]

    def scale_image(self):
        """Scale original size image for display in Graph element."""
        # Close previous scaled image if it's not the original
        if self.scaled_image is not self.image:
            try:
                self.scaled_image.close()
            except Exception:
                pass
        width, height = self.image.size
        newwidth = int(width * ImageContainer.zoom_factor / 100)
        newheight = int(height * ImageContainer.zoom_factor / 100)
        self.scaled_image = self.image.resize((newwidth, newheight), resample=Image.Resampling.BILINEAR)

    def undo(self, window):
        """Go back in history. Remove last rectangle and redraw rectangles."""
        if len(self.rectangles) > 0:
            delete_id = self.rectangles.pop()
            window['-GRAPH-'].delete_figure(delete_id[3])
        return self

    def data(self):
        """Return bytes of scaled image."""
        with io.BytesIO() as output:
            self.scaled_image.save(output, format='PNG')
            data = output.getvalue()
            # Note: Don't cache - causes memory issues with large documents
            return data

    def jpg(self, image, image_quality=85, scale=1):
        """
        Return bytes of compressed JPEG image.

        Args:
            image: PIL Image to compress.
            image_quality: JPEG quality (1-100). Higher = better quality, larger file.
            scale: Scale factor for resizing (e.g., 0.64 for 96 DPI from 150 DPI).

        Returns:
            bytes: JPEG image data.
        """
        scaled_image = None
        with io.BytesIO() as output:
            if scale == 1:
                image_to_save = image
            else:
                scaled_image = image.resize(
                    (int(image.width * scale), int(image.height * scale)),
                    resample=Image.Resampling.LANCZOS
                )
                image_to_save = scaled_image
            image_to_save.save(output, format='JPEG', quality=image_quality, optimize=True)
            data = output.getvalue()
        # Close scaled image if we created one
        if scaled_image is not None:
            scaled_image.close()
        return data

    def refresh(self):
        """Update the scaled image and return self."""
        self.scale_image()
        return self

    def finalized_image(self, format='PIL', image_quality=92, scale=1):
        """
        Return a copy of the imported image with all rectangles drawn.

        Args:
            format: Output format - 'PIL' returns PIL Image, 'JPEG'/'JPG' returns bytes.
            image_quality: JPEG quality (1-100). Default 92 for high quality.
            scale: Scale factor for DPI adjustment. Use 0.64 for ~96 DPI from 150 DPI import.

        Returns:
            PIL Image or bytes depending on format parameter.
        """
        final_image = self.draw_rectangles_on_image(self.image.copy())
        if format in ('JPEG', 'JPG'):
            rgb_image = final_image.convert('RGB')
            final_image.close()  # Close the original copy
            result = self.jpg(rgb_image, image_quality, scale)
            rgb_image.close()  # Close the RGB conversion
            return result
        else:
            return final_image

    def draw_rectangles_on_image(self, image):
        """Draw the rectangles in self.rectangles on image."""
        draw = ImageDraw.Draw(image)

        for rectangle in self.rectangles:
            draw.rectangle(xy=[rectangle[0], rectangle[1]], fill=rectangle[2])
        return image

    def draw_rectangles_on_graph(self, window):
        """Draw all rectangles in the rectangles list to the graph in the correct scale."""
        # Delete old graph figures before redrawing to prevent accumulation
        for rectangle in self.rectangles:
            if rectangle[3] is not None:
                try:
                    window['-GRAPH-'].delete_figure(rectangle[3])
                except Exception:
                    pass

        new_rectangles = list()

        for rectangle in self.rectangles:
            factor = ImageContainer.zoom_factor / 100
            scaled_start_point = [int(x * factor) for x in rectangle[0]]
            scaled_end_point = [int(x * factor) for x in rectangle[1]]
            fill = rectangle[2]

            rectangle_id = window['-GRAPH-'].draw_rectangle(
                (scaled_start_point[0], -scaled_start_point[1]),
                (scaled_end_point[0], -scaled_end_point[1]),
                fill_color=fill,
                line_color=fill,
                line_width=None
            )

            new_rectangles.append((rectangle[0], rectangle[1], fill, rectangle_id))

        self.rectangles = new_rectangles

    def draw_rectangle(self, window, start_point, end_point, fill='black'):
        """Draw a rectangle on graph and add it to the rectangles list."""
        try:
            factor = ImageContainer.zoom_factor / 100

            computed_startpoint_x = int((start_point[0]) / factor)
            computed_startpoint_y = int((start_point[1]) / factor)

            computed_endpoint_x = int((end_point[0]) / factor)
            computed_endpoint_y = int((end_point[1]) / factor)

            start_point_in_original = (computed_startpoint_x, computed_startpoint_y)
            end_point_in_original = (computed_endpoint_x, computed_endpoint_y)

            rectangle_id = window['-GRAPH-'].draw_rectangle(
                (start_point[0], -start_point[1]),
                (end_point[0], -end_point[1]),
                fill_color=fill,
                line_color=fill,
                line_width=None
            )
            self.rectangles.append((start_point_in_original, end_point_in_original, fill, rectangle_id))

        except ValueError:
            pass
        return self


def export_rectangles(pages):
    """
    Export all rectangles from all pages for serialization.

    Args:
        pages: List of ImageContainer instances.

    Returns:
        list: List of rectangle lists, one per page, or None if no rectangles exist
              or if pages is empty/None.
    """
    if not pages:
        return None

    try:
        rectangles = [page.rectangles for page in pages]
        contains_rectangles = [bool(item) for item in rectangles]
        if any(contains_rectangles):
            return rectangles
        else:
            return None
    except (AttributeError, TypeError):
        return None


def close_all_pages(pages):
    """
    Close all ImageContainer instances and release their image resources.

    Call this before loading a new document to prevent memory leaks.

    Args:
        pages: List of ImageContainer instances.
    """
    if not pages:
        return

    for page in pages:
        if hasattr(page, 'close'):
            try:
                page.close()
            except Exception:
                pass

    # Clear the list
    pages.clear()
    gc.collect()


def delete_all_rectangles(pages, delete_workfile_func):
    """
    Delete all rectangles from all pages.

    Args:
        pages: List of ImageContainer instances.
        delete_workfile_func: Callback function to delete the associated workfile.

    Returns:
        bool: True if successful, False if pages was empty or None.
    """
    if not pages:
        return False

    try:
        for page in pages:
            if hasattr(page, 'rectangles'):
                page.rectangles = []

        if callable(delete_workfile_func):
            delete_workfile_func()

        return True
    except Exception:
        return False


def finalize_pages_chunked(pages, img_format='JPEG', quality=92, scale=1,
                           chunk_size=50, progress_callback=None):
    """
    Finalize pages in chunks using multiprocessing, yielding results progressively.

    This generator processes pages in chunks to limit memory usage. Each chunk is
    prepared, processed in parallel, and yielded before moving to the next chunk.
    This prevents holding all pages in memory simultaneously.

    Progress is reported in two phases per page:
    - Phase 1 (0.5 per page): Preparation/serialization
    - Phase 2 (0.5 per page): Parallel processing

    Args:
        pages: List of ImageContainer instances.
        img_format: Output format ('JPEG' or 'PNG').
        quality: JPEG quality (1-100).
        scale: Scale factor for DPI adjustment.
        chunk_size: Number of pages to process per chunk (default: 50).
        progress_callback: Optional callback(completed, total) for progress updates.
                          Called with float values to support half-page increments.

    Yields:
        Tuples of (image_bytes, page_size) in page order.

    Raises:
        ValueError: If pages is empty/None or if any page fails to process.
    """
    if not pages:
        raise ValueError(_('error_no_pages'))

    total_pages = len(pages)
    max_workers = get_worker_count(max_tasks=min(chunk_size, total_pages))
    completed_total = 0.0

    # Process pages in chunks
    for chunk_start in range(0, total_pages, chunk_size):
        chunk_end = min(chunk_start + chunk_size, total_pages)
        chunk_pages = pages[chunk_start:chunk_end]

        # Prepare arguments for this chunk (Phase 1: ~50% of work per page)
        worker_args = []
        for i, page in enumerate(chunk_pages):
            page_idx = chunk_start + i

            # Convert image to bytes (use context manager for proper cleanup)
            with io.BytesIO() as buffer:
                page.image.save(buffer, format='JPEG')
                image_bytes = buffer.getvalue()

            # Extract rectangle data (without graph_id which isn't needed)
            rectangles = [(r[0], r[1], r[2], None) for r in page.rectangles]

            worker_args.append((
                page_idx,
                image_bytes,
                rectangles,
                img_format,
                quality,
                scale,
                (page.height_in_pt, page.width_in_pt)
            ))

            # Clear reference to allow GC of this page's bytes before next iteration
            del image_bytes
            del rectangles

            # Report preparation progress (half credit per page)
            completed_total += 0.5
            if progress_callback:
                progress_callback(completed_total, total_pages)

        # Clear reference to chunk_pages slice
        del chunk_pages

        # Process this chunk in parallel (Phase 2: ~50% of work per page)
        chunk_results = [None] * (chunk_end - chunk_start)

        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_finalize_page_worker, args): args[0] for args in worker_args}

            # Clear worker_args immediately after submitting - executor has copies
            del worker_args
            gc.collect()

            pending = set(futures.keys())

            while pending:
                done, pending = wait_futures(pending, timeout=0.05)

                for future in done:
                    result = future.result()
                    page_idx = result[0]
                    chunk_idx = page_idx - chunk_start

                    if result[1] is None:
                        raise ValueError(_('error_page_process_failed', page=page_idx + 1, error=result[2]))

                    chunk_results[chunk_idx] = (result[1], result[2])

                    # Report processing progress (remaining half credit per page)
                    completed_total += 0.5
                    if progress_callback:
                        progress_callback(completed_total, total_pages)

            # Clear futures dict
            del futures

        # Yield results from this chunk in order, then release memory
        for i, result in enumerate(chunk_results):
            yield result
            # Clear each result after yielding to free memory immediately
            chunk_results[i] = None

        # Force garbage collection after each chunk
        # This is critical for large documents to prevent memory exhaustion
        del chunk_results
        gc.collect()
