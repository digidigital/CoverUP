"""
Utility functions for CoverUP PDF.
"""

import io
import os
import sys
import glob
import hashlib
from multiprocessing import cpu_count

from PIL import Image, ImageDraw, ImageFont


def get_worker_count(max_tasks=None):
    """
    Calculate optimal worker count for multiprocessing.

    Uses cores-1 to leave one core free for the main thread/UI,
    with a minimum of 1 worker.

    Args:
        max_tasks: Optional maximum number of tasks (limits workers to task count).

    Returns:
        int: Number of workers to use.
    """
    cores = cpu_count()
    workers = max(1, cores - 1)

    if max_tasks is not None:
        workers = min(workers, max_tasks)

    return workers


SUPPORTED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png'}


def is_valid_file_type(filepath):
    """Check if the file has a supported extension."""
    if not filepath:
        return False
    ext = os.path.splitext(filepath)[1].lower()
    return ext in SUPPORTED_EXTENSIONS


def get_package_dir():
    """Get the directory of the coverup package."""
    return os.path.dirname(os.path.realpath(__file__))


def get_resource_root():
    """
    Get the root directory for resources (fonts, etc.).

    Handles different execution contexts:
    - Normal Python: Returns the package directory
    - PyInstaller one-file: Returns _MEIPASS (temp extraction directory)
    - PyInstaller one-folder: Returns the directory containing the executable

    The PyInstaller hook (hook-coverup.py) collects data files using
    collect_data_files(), which preserves the package structure.
    Files are placed under 'coverup/fonts/' in the bundle.
    """
    # PyInstaller >= 5.0: _MEIPASS contains extracted files
    if hasattr(sys, "_MEIPASS"):
        # Hook collects to 'coverup/fonts', so look there first
        pyinstaller_path = os.path.join(sys._MEIPASS, "coverup")
        if os.path.isdir(pyinstaller_path):
            return pyinstaller_path
        return sys._MEIPASS

    # PyInstaller one-folder mode
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        # Check if package structure exists next to executable
        pkg_path = os.path.join(exe_dir, "_internal", "coverup")
        if os.path.isdir(pkg_path):
            return pkg_path
        return exe_dir

    # Normal Python execution
    return get_package_dir()


# Backwards compatibility alias
get_script_root = get_resource_root


def find_fonts_folder(root):
    """
    Find the fonts folder within the given root directory.

    Searches in order:
    1. Direct child 'fonts' folder
    2. Recursive search for any 'fonts' folder
    """
    # First check if fonts is directly in the root (package directory)
    direct_path = os.path.join(root, "fonts")
    if os.path.isdir(direct_path):
        return direct_path

    # Otherwise search recursively (for non-standard layouts)
    target = "fonts"
    for dirpath, dirnames, filenames in os.walk(root):
        if os.path.basename(dirpath) == target:
            return dirpath

    raise FileNotFoundError(f"Could not locate resource folder '{target}' under: {root}")


def encode_filepath(filepath):
    """Create an MD5 hash of the filepath for use as a workfile name."""
    hash_object = hashlib.md5(filepath.encode())
    hex_dig = hash_object.hexdigest()
    return hex_dig


def delete_oldest_files(directory_path, file_limit=25):
    """Delete oldest files in a directory to maintain a file limit."""
    files = glob.glob(os.path.join(directory_path, '*'))

    if len(files) > file_limit:
        sorted_files = sorted(files, key=os.path.getctime)
        for file in sorted_files[:-file_limit]:
            os.remove(file)


def to_bytes(image):
    """Convert PIL image to bytes (PNG format)."""
    with io.BytesIO() as output:
        image.save(output, format="PNG")
        return output.getvalue()


def round_corner(radius, fill):
    """Draw a round corner for rounded rectangles."""
    corner = Image.new('RGBA', (radius, radius), "#00000000")
    draw = ImageDraw.Draw(corner)
    draw.pieslice((0, 0, radius * 2, radius * 2), 180, 270, fill=fill)
    return corner


def round_rectangle(size, radius, fill):
    """Draw a rounded rectangle."""
    width, height = size
    rectangle = Image.new('RGBA', size, fill)
    corner = round_corner(radius, fill)
    rectangle.paste(corner, (0, 0))
    rectangle.paste(corner.rotate(90), (0, height - radius))
    rectangle.paste(corner.rotate(180), (width - radius, height - radius))
    rectangle.paste(corner.rotate(270), (width - radius, 0))
    return rectangle


def draw_character(character, font_path, font_size=25, color='white', width=30, height=30,
                   icon_background=False, icon_background_color='dimgray'):
    """Create an icon image from a character using a font."""
    image = Image.new("RGBA", (width, height), "#00000000")

    if icon_background:
        image.paste(round_rectangle((width, height), int(width * 0.2), icon_background_color))

    font = ImageFont.truetype(font_path, font_size)
    draw = ImageDraw.Draw(image)
    text1_x, text1_y, text2_x, text2_y = draw.textbbox([0, 0], text=character, font=font)
    x = (width - text2_x - text1_x) // 2
    y = (height - text2_y - text1_y) // 2
    draw.text((x, y), character, font=font, fill=color)
    return to_bytes(image)


def make_icons(glyph_map, fontpath):
    """Build a dict of icons from a glyph map."""
    icons = {}
    for name, glyph in glyph_map.items():
        icons[name] = draw_character(glyph, fontpath)
    return icons
