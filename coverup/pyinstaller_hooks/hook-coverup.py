"""
PyInstaller hook for CoverUP package.

This hook ensures that the Fonts directory and other data files
are properly collected when building with PyInstaller.
"""

from PyInstaller.utils.hooks import collect_data_files

# Collect data files from the coverup package (includes fonts directory)
datas = collect_data_files('coverup')

# Hidden imports that PyInstaller might miss. pytesseract is imported lazily
# inside coverup.ocr, so list it explicitly to be safe.
hiddenimports = ['PIL', 'tkinter', 'pytesseract']
