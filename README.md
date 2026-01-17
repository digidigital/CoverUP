# CoverUP PDF Redaction Software

**CoverUP** is a free software, developed in Python, designed to provide a secure and straightforward method for redacting PDF files. It enables users to conceal sensitive text passages by overlaying them with black or white bars.

Users can import PDF documents into CoverUP, which are then converted into images. This conversion process ensures that the text cannot be copied from the document or indexed without OCR, enhancing the security of your information. Additionally, invisible layers within the PDF are not converted, providing an extra layer of security.

It also supports the import of PNG and JPG files, in addition to PDFs.

Given that image-based PDFs can become quite large, **CoverUP** offers two modes: a high-quality mode that maintains the visual fidelity of the document, and a compressed mode that reduces file size at the expense of some visual quality.

Whether you're dealing with a single page or an entire document, **CoverUP** provides a flexible and easy solution for all your PDF redaction needs.

---

![A screenshot of PDF redaction Software | Ein Screenshot der Software zum Schwärzen von PDF-Dokumenten](https://raw.githubusercontent.com/digidigital/CoverUP/main/Screenshots/CoverUP_screenshot.png)

---

Visit the [CoverUP PDF Microsite](https://coverup.digidigital.de) - This software is a [digidigital](https://digidigital.de) project.

## Features

- Import PDF, PNG, and JPG files
- Draw black or white redaction bars over sensitive content
- Password-protected PDF support
- High-quality and compressed export modes
- Session persistence - continue where you left off
- Undo functionality for corrections
- Zoom in/out for precise redaction
- Command-line file argument support
- Export single pages or entire documents
- **Multi-language support** (25 languages including English, German, Spanish, French, Chinese, and more)

## Installation

### Linux - Snap Store

[![Get it from the Snap Store](https://snapcraft.io/static/images/badges/en/snap-store-black.svg)](https://snapcraft.io/coverup)

[![coverup](https://snapcraft.io/coverup/badge.svg)](https://snapcraft.io/coverup)

```bash
sudo snap install coverup
```

### Python Package (pip)

```bash
pip install coverup-pdf
```

### Windows / Other

[Windows Installer and other download options](https://github.com/digidigital/CoverUP/releases/latest)

## Usage

### Graphical Interface

Simply launch **CoverUP** and use the toolbar to:
1. Open a PDF or image file
2. Draw redaction bars by clicking and dragging
3. Use the eraser tool to remove bars
4. Save the redacted document

### Command Line

```bash
# Open a file directly
coverup document.pdf

# Open an image
coverup screenshot.png

# Show version
coverup --version
```

## Development

### Requirements

- Python 3.9+
- Dependencies listed in `requirements.txt`

### Setup

```bash
# Clone the repository
git clone https://github.com/digidigital/CoverUP.git
cd CoverUP

# Install dependencies
pip install -r requirements.txt

# Run from source
python CoverUP.py

# Or install as package
pip install -e .
coverup
```

### Building Packages

#### Python Package (PyPI)

```bash
# Install build tools
pip install build twine

# Build the package
python -m build

# Upload to PyPI (requires PyPI credentials)
twine upload dist/*
```

#### Snap

```bash
# Install snapcraft
sudo snap install snapcraft --classic

# Build the snap
snapcraft

# Install locally for testing
sudo snap install coverup_*.snap --dangerous
```

#### Windows (PyInstaller)

```bash
# Install PyInstaller
pip install pyinstaller

# Build executable
pyinstaller --onefile --windowed --icon=CoverUP.ico CoverUP.py
```

### Internationalization (i18n)

CoverUP supports 25 languages. The UI automatically detects the system language and displays translations accordingly.

**Supported languages:** English, German, Spanish, French, Italian, Portuguese, Romanian, Dutch, Swedish, Danish, Norwegian, Icelandic, Polish, Czech, Slovak, Bulgarian, Serbian, Croatian, Slovenian, Greek, Turkish, Lithuanian, Latvian, Estonian, Chinese, Hindi

Translations are stored in `coverup/translations.py`. To add or modify translations, edit the `TRANSLATIONS` dictionary in that file.

## License

This project is licensed under the GPL-3.0 License - see the [LICENSE](LICENSE) file for details.

## FOSS Credits

- [FreeSimpleGUI](https://github.com/spyoungtech/FreeSimpleGui) - GUI framework
- [pypdfium2](https://github.com/pypdfium2-team/pypdfium2) - PDF rendering
- [fpdf2](https://py-pdf.github.io/fpdf2/) - PDF creation
- [Pillow](https://python-pillow.org/) - Image processing
- [Material Symbols](https://fonts.google.com/icons) - UI icons

---

# Schwärzen von PDF Dokumenten mit CoverUP

**CoverUP** ist eine kostenlose Software, die in Python entwickelt wurde, um eine sichere und unkomplizierte Methode zur Schwärzung von PDF-Dateien bereitzustellen. Sie ermöglicht es den Benutzern, sensible Textpassagen zu verbergen, indem sie diese mit schwarzen oder weißen Balken überlagern.

Benutzer können PDF-Dokumente in **CoverUP** importieren, die dann in Bilder umgewandelt werden. Dieser Umwandlungsprozess stellt sicher, dass der Text nicht ohne zusätzliche Texterkennung kopiert oder indexiert werden kann, was die Sicherheit der Informationen erhöht. Zusätzlich werden unsichtbare Schichten innerhalb der PDF nicht konvertiert, was eine zusätzliche Sicherheitsebene gegen versehentliche Veröffentlichung bietet.

Es unterstützt auch den Import von PNG- und JPG-Dateien, zusätzlich zu PDFs.

Da bildbasierte PDFs recht groß werden können, bietet CoverUP zwei Exportoptonen an: einen Modus in hoher Qualität, der die visuelle Genauigkeit des Dokuments weitestgehend beibehält, und einen komprimierten Modus, der die Dateigröße der exportierten PDF-Datei auf Kosten von visueller Qualität reduziert.

Ob Sie mit einer einzelnen Seite oder einem gesamten Dokument arbeiten, **CoverUP** bietet eine flexible und einfache Lösung für alle Ihre Bedürfnisse zur Schwärzung von PDFs.

## Installation

### Linux - Snap Store

[![Get it from the Snap Store](https://snapcraft.io/static/images/badges/en/snap-store-black.svg)](https://snapcraft.io/coverup)

```bash
sudo snap install coverup
```

### Python-Paket (pip)

```bash
pip install coverup-pdf
```

### Windows / Andere

[Windows Installer und andere Downloadoptionen](https://github.com/digidigital/CoverUP/releases/latest)

