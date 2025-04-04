# CoverUP PDF Redaction Software
**CoverUP** is a free software, developed in Python, designed to provide a secure and straightforward method for redacting PDF files and their optical character recognition (OCR). It enables users to conceal sensitive text passages by overlaying them with black or white bars.

This version is fork of the original work at https://github.com/digidigital/CoverUP. Two major changes are OCR of documents and the possibility to specify name of the document along the program name. This enables to open files in a file manager or from a command line.

Users can import PDF documents into CoverUP, which are then converted into images. This conversion process ensures that the text cannot be copied from the document or indexed without OCR, enhancing the security of your information. Additionally, invisible layers within the PDF are not converted, providing an extra layer of security.

The OCR feature requires that the [Tesseract OCR engine](https://github.com/tesseract-ocr/tesseract) is installed on the system. One can specify OCR language by setting the `COVERUP_OCR_LANG` environment variable, for example by adding the line
```
export COVERUP_OCR_LANG=deu
```
to the `.bashrc` file if using the `bash` shell or performing an equivalent action on Windows. Refer to `tesseract` documentation to get the proper code for your specific language. If not set, the `eng` language is used. Some languages are deu, fra, ces, slk, spa, pol and many others.

Whether you’re dealing with a single page or an entire document, `CoverUP` provides a flexible and easy solution for all your PDF redaction needs.

Name of the actual app to be used is `pdfanon` on Linux or `pdfanon.exe` on Windows.

## Installation on Linux
1. Download content of this repository (either using `git` or the provided `zip` file).
2. Unzip the zip file, if using it
3. Enter the created directory and run the `install.sh` script. The `pdfanon` script will be placed in the `/usr/local/bin` directory.

**Comment 1**: do not delete the directory after installation. It contains the code.

**Comment 2**: If you want to hide the directory by adding . (dot) as the first character of its name, do that prior to running the script.

**Comment 3**: The scitpt was developed on a debian-like system and tested on recent Ubuntu (python 3.12) and older Mint (python 2.8). If you want to use it on e. g. a rpm-based system, you need to do some changes in the script (changing `apt` for `rpm` and perhps other).

## Installation on Windows
1. Install Python
1. Install `TesseractOCR` from https://github.com/UB-Mannheim/tesseract/wiki.  During installation select the needed languages
1. Add path to `TeseractOCR` (most likely `C:\Program Files\Tesseract-OCR`) in the `Path` system variable.
1. Download the `pdfanon.exe` program from (to be specified) and place it somewhere, where the system can find it, e.g. in the `C:\Program Files\Tesseract-OCR` directory.

## Building the `pdfanon.exe` program
1. Repeat first three steps of the previous section
1. Add path to python programs to the `path` system variable (e.g. `C:\Users\username\AppData\Local\Programs\Python\Python312\Scripts`). If set correctly, the `pip` program should be accessible in the `cmd` window.
1. In a `cmd` window install `pyinstaller` by running `pip install pyinstaller`
1. Download content of this repository (either using `git` or the provided `zip` file).
1. Unzip the zip file, if using it
1. In `cmd` window enter the directory and install dependencies by `pip install -r requirements.txt`
1. In the same window run
<code>
pyinstaller --add-data "Fonts\MaterialSymbolsOutlined[FILL,GRAD,opsz,wght].ttf":Fonts --onefile --windowed --splash splash.png -n pdfanon CoverUP.py
</code>
The `pdfanon.exe` will be placed in the `dist` subdirectory.
