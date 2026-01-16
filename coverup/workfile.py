"""
Workfile management for session persistence in CoverUP PDF.

This module provides the WorkfileManager class that handles saving and loading
of work sessions. Work sessions are stored as JSON files in the user's data
directory, keyed by an MD5 hash of the original file path.

Session data includes:
    - Rectangle positions and colors for each page
    - Current page number
    - Fill color and output quality settings
"""

import os
import json

from coverup.utils import encode_filepath, delete_oldest_files
from coverup.image_container import export_rectangles


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
            workfile_name = encode_filepath(self.file_path)
            work_data = {
                'rectangles': rectangles,
                'pages': len(images),
                'current_page': current_page,
                'fill_color': fill_color,
                'output_quality': output_quality
            }
            try:
                with open(os.path.join(self.datadir, workfile_name), 'w', encoding='utf-8') as f:
                    json.dump(work_data, f, ensure_ascii=False, indent=4)
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
            workfile = os.path.join(self.datadir, encode_filepath(self.file_path))
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
                  or None if no workfile exists.
        """
        if not self.file_path:
            return None

        try:
            workfile_name = encode_filepath(self.file_path)
            workfile = os.path.join(self.datadir, workfile_name)
            if os.path.isfile(workfile):
                with open(workfile, 'r', encoding='utf-8') as f:
                    work_data = json.load(f)
                return work_data
            else:
                return None
        except Exception:
            return None
