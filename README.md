# CoverUP PDF Redaction Software
**CoverUP** is a free software, developed in Python, designed to provide a secure and straightforward method for redacting PDF files and their subsequent optical character recognition (OCR).

This version is fork of the original work at https://github.com/digidigital/CoverUP. Two major changes are OCR of documents and the possibility to specify name of the document along the program name. This enables to open files in a file manager or from a command line.

Name of the actual app to be used is `pdfanon` on Linux or `pdfanon.exe` on Windows.

A PDF document, which is opened in `pdfanon`, is first converted into images and all textual information is removed. Users can then conceal sensitive text passages visible in the images by overlaying them with black or white bars. Finally, when saving the document, the overlayed parts of the images are deleted and the remaining visible text is OCR-ed.

The OCR feature requires that the [Tesseract OCR engine](https://github.com/tesseract-ocr/tesseract) is installed on the system.

## Installation on Linux
Installation requires administration rights. If you are not a `sudo` user, ask the administrator to install the software.

Steps:

1. Download content of this repository (either using `git` or the provided `zip` file).
2. Unzip the zip file, if using it.
3. Enter the created directory and run the `install.sh` script. The `pdfanon` script will be placed in the `/usr/local/bin` directory.

**Comment 1**: do not delete the directory after installation. It contains the code.

**Comment 2**: If you want to hide the directory by adding . (dot) as the first character of its name. Do that prior to running the script.

**Comment 3**: The script was developed on a debian-like system and tested on recent Ubuntu (python 3.12) and older Mint (python 2.8). If you want to use it on e. g. a rpm-based system, you need to do some changes in the script (changing `apt` for `rpm` and perhaps other).

## Installation on Windows
Installation requires administration rights. If you do not have them, ask the administrator to install the software.

Steps:

1. Install Python
1. Install `TesseractOCR` from [Github](https://github.com/UB-Mannheim/tesseract/wiki).  During installation select the needed languages
1. Add path to `TeseractOCR` (most likely `C:\Program Files\Tesseract-OCR`) in the `Path` system variable.
1. Download the most recent zip file from a [Google Drive folder](https://drive.google.com/drive/folders/14RA-n_7WmSg0xD_fU9nXR7hTFqagBHL5?usp=sharing), extract the `pdfanon.exe` file and place it somewhere, where the system can find it, e.g. in the `C:\Program Files\Tesseract-OCR` directory.
1. If required, set you default OCR language by setting the `COVERUP_OCR_LANG` environment variable.

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

## Specification of the OCR languages

Default OCR language is `slk` (Slovak), which is hardcoded in the `CoverUP.py` file. Documents in English seem to be OCR-ed correctly as well. On Linux languages installed by the `install.sh` script are eng, slk, ces, deu and fra, more can be added by the `apt` program (or similar). On Windows additional languages can be installed by the `TesseractOCR` installation program.

Currently, there is no possibility to select language from the program itself.

One can specify OCR language by setting the `COVERUP_OCR_LANG` environment variable, for example by adding the line
```
export COVERUP_OCR_LANG=deu
```
to the user's `.bashrc` file if using the `bash` shell or performing an equivalent action for other shells or on Windows. Refer to `tesseract` documentation to get the proper code for your specific language.

In order to set the language temporarily, in `bash` you can run it by
```
export COVERUP_OCR_LANG=deu; pdfanon file.pdf
```
The actually used OCR language and file name are displayed in the program's title bar.
