"""
PyInstaller hook support for CoverUP.

This module provides hook directories for PyInstaller >= 5.0.
"""

from typing import List
import os
import sys

# Add the module directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))


def get_hook_dirs() -> List[str]:
    """
    Return the path to the hooks directory for PyInstaller.

    This function is called by PyInstaller via the pyinstaller40 entry point.

    Returns:
        list: A list containing the absolute path to the hooks directory.
    """
    return [os.path.join(os.path.dirname(__file__), 'pyinstaller_hooks')]
