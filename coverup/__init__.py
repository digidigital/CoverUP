"""
CoverUP PDF - A tool for redacting PDF files and images.

CoverUP is a privacy-focused tool for redacting sensitive information in PDF
documents and images. It converts PDF pages to images during import, ensuring
that text cannot be copied and hidden layers are not exposed.

Main features:
    - Import PDF, PNG, and JPG files
    - Draw black or white redaction bars
    - Password-protected PDF support
    - Session persistence
    - High-quality and compressed export modes

Package structure:
    - main: Application entry point and event loop
    - image_container: ImageContainer class for page/rectangle management
    - document_loader: PDF and image loading functionality
    - workfile: Session persistence (save/load work sessions)
    - ui: User interface layout and icons
    - utils: Utility functions

Example usage:
    >>> from coverup.main import main
    >>> main()  # Launch the GUI

    # Or from command line:
    $ coverup document.pdf
    $ python -m coverup
"""

__version__ = "0.4.0"
__author__ = "Björn Seipel"
__email__ = "support@digidigital.de"
__license__ = "GPL-3.0"
__all__ = ["__version__", "__author__", "__email__", "__license__"]
