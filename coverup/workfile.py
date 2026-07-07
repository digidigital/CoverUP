"""
Workfile management for session persistence in CoverUP PDF.

This module provides the WorkfileManager class that handles saving and loading
of work sessions. Work sessions are stored as JSON files in the user's data
directory, keyed by a SHA-256 hash of the original file path (older releases
used MD5; those files are still found on load).

Session data includes:
    - Rectangle positions and colors for each page
    - Current page number
    - Fill color and output quality settings
"""

import os
import json

from coverup.utils import encode_filepath, encode_filepath_legacy, delete_oldest_files
from coverup.image_container import export_rectangles


_VALID_FILL_COLORS = {'black', 'white'}
_VALID_QUALITIES = {'high', 'low'}


def _is_point(value):
    """True if value is a 2-item list/tuple of finite numbers."""
    return (isinstance(value, (list, tuple)) and len(value) == 2
            and all(isinstance(v, (int, float)) and not isinstance(v, bool)
                    for v in value))


def _validate_work_data(work_data):
    """Validate and normalise work data loaded from disk.

    Workfiles are plain JSON in a user-writable directory, so their content is
    not trusted: every field that later reaches drawing or indexing code is
    checked here. Returns the normalised dict, or None if the structure is not
    a valid work session.
    """
    if not isinstance(work_data, dict):
        return None

    rectangles = work_data.get('rectangles')
    pages = work_data.get('pages')
    if (not isinstance(rectangles, list)
            or not isinstance(pages, int) or isinstance(pages, bool)
            or len(rectangles) != pages):
        return None

    normalised_pages = []
    for page_rects in rectangles:
        if not isinstance(page_rects, list):
            return None
        normalised = []
        for rect in page_rects:
            if (not isinstance(rect, (list, tuple)) or len(rect) < 3
                    or not _is_point(rect[0]) or not _is_point(rect[1])
                    or rect[2] not in _VALID_FILL_COLORS):
                return None
            # Graph ids from a previous session are meaningless (and deleting
            # a stale id could remove an unrelated canvas figure), so drop them.
            normalised.append([list(rect[0]), list(rect[1]), rect[2], None])
        normalised_pages.append(normalised)
    work_data['rectangles'] = normalised_pages

    current_page = work_data.get('current_page')
    if (not isinstance(current_page, int) or isinstance(current_page, bool)
            or not 0 <= current_page < pages):
        work_data['current_page'] = 0
    if work_data.get('fill_color') not in _VALID_FILL_COLORS:
        work_data['fill_color'] = None
    if work_data.get('output_quality') not in _VALID_QUALITIES:
        work_data['output_quality'] = None
    return work_data


class WorkfileManager:
    """
    Manages saving and loading of work sessions.

    Work sessions allow users to continue redacting a document where they
    left off. Session files are stored in the application's data directory
    and are automatically cleaned up when the history limit is exceeded.

    Attributes:
        datadir: Directory path for storing workfiles.
        history_length: Maximum number of workfiles to retain.
        file_path: Current document file path (used for workfile naming).
    """

    def __init__(self, datadir, history_length=30):
        """
        Initialize the WorkfileManager.

        Args:
            datadir: Directory path for storing workfiles.
            history_length: Maximum number of workfiles to retain (default: 30).
        """
        self.datadir = datadir
        self.history_length = history_length
        self.file_path = None

    def _workfile_paths(self):
        """Return (current, legacy) workfile paths for the current document."""
        current = os.path.join(self.datadir, encode_filepath(self.file_path))
        legacy = os.path.join(self.datadir, encode_filepath_legacy(self.file_path))
        return current, legacy

    def set_file_path(self, file_path):
        """
        Set the current file path for workfile operations.

        Args:
            file_path: Path to the currently loaded document.
        """
        self.file_path = file_path

    def save(self, images, current_page, fill_color, output_quality):
        """
        Save the current work session to a workfile.

        Args:
            images: List of ImageContainer objects with rectangle data.
            current_page: Currently displayed page index.
            fill_color: Current fill color ('black' or 'white').
            output_quality: Current quality setting ('high' or 'low').
        """
        if not self.file_path or not self.datadir:
            return

        if not images:
            self.delete()
            return

        rectangles = export_rectangles(images)
        if rectangles is not None:
            workfile, legacy_workfile = self._workfile_paths()
            work_data = {
                'rectangles': rectangles,
                'pages': len(images),
                'current_page': current_page,
                'fill_color': fill_color,
                'output_quality': output_quality
            }
            try:
                with open(workfile, 'w', encoding='utf-8') as f:
                    json.dump(work_data, f, ensure_ascii=False, indent=4)
                if os.path.isfile(legacy_workfile):
                    os.remove(legacy_workfile)
                delete_oldest_files(self.datadir, self.history_length)
            except Exception:
                pass
        else:
            self.delete()

    def delete(self):
        """
        Delete the current workfile.

        Called when the user starts over or when there are no rectangles to save.
        """
        if not self.file_path:
            return

        try:
            for workfile in self._workfile_paths():
                if os.path.isfile(workfile):
                    os.remove(workfile)
        except Exception:
            pass

    def load(self):
        """
        Load work data from the workfile if it exists.

        Returns:
            dict: Work session data containing 'rectangles', 'pages',
                  'current_page', 'fill_color', and 'output_quality',
                  or None if no workfile exists or its content is not a
                  valid work session.
        """
        if not self.file_path:
            return None

        try:
            for workfile in self._workfile_paths():
                if os.path.isfile(workfile):
                    with open(workfile, 'r', encoding='utf-8') as f:
                        work_data = json.load(f)
                    return _validate_work_data(work_data)
            return None
        except Exception:
            return None
