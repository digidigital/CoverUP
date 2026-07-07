"""
Automatic detection of sensitive content for CoverUP PDF.

This module finds text that matches built-in patterns (emails, phone numbers,
IDs, IBANs, credit cards) or user-supplied keywords, and turns each hit into a
redaction rectangle in original-image pixel coordinates so it can be handed to
:meth:`ImageContainer.add_rectangle`.

Two text sources are supported and share the same matching/grouping logic:

* **Digital PDFs** — text and per-character boxes come from ``pypdfium2``
  (no extra dependency). See :func:`find_boxes_digital`.
* **Scanned pages / images** — text comes from Tesseract OCR. See
  :func:`coverup.ocr.find_boxes_ocr`, which reuses :func:`match_units` here.

A "unit" is a ``(char, (left, top, right, bottom))`` pair whose box is already
in image pixels with a top-left origin. Both sources produce a list of units;
:func:`match_units` does the rest, so the matching rules stay identical
regardless of where the text came from.
"""

import re

# Built-in detectors. Order matters only for display; overlapping hits from
# different patterns are merged later so the same text is never barred twice.
#
# Patterns are deliberately a little greedy: for redaction it is safer to cover
# slightly too much than to leak part of a sensitive value.
PATTERN_DEFS = {
    'email': r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}',
    # Spanish DNI/NIF (8 digits + letter) and NIE (X/Y/Z + 7 digits + letter).
    'dni_nie': r'\b(?:[XYZxyz][ \-]?)?\d{7,8}[ \-]?[A-Za-z]\b',
    # Spanish CIF (company tax ID): org-type letter + 7 digits + control char.
    'cif': r'\b[ABCDEFGHJNPQRSUVWabcdefghjnpqrsuvw][ \-]?\d{7}[ \-]?[0-9A-Ja-j]\b',
    # IBAN: 2 letters + 2 check digits + up to 30 grouped alphanumerics.
    'iban': r'\b[A-Z]{2}\d{2}(?:[ ]?[A-Za-z0-9]{2,4}){2,8}\b',
    # Credit-card-like runs of 13-19 digits, optionally space/dash grouped.
    'creditcard': r'\b(?:\d[ \-]?){13,19}\b',
    # Phone numbers: optional +/00 country code then 8-12 grouped digits.
    'phone': r'(?:(?:\+|00)\d{1,3}[ .\-]?)?(?:\d[ .\-]?){8,11}\d',
    # Postal/street addresses: a street-type word through the rest of the line
    # (street name, number, floor, postcode, town). Deliberately greedy — for
    # redaction it is safer to cover the whole address line.
    'address': r'\b(?:calle|c/|avda?\.?|avenida|av\.?|plaza|pl\.?|paseo|p[ºo]\.?|'
               r'camino|carretera|ctra\.?|ronda|traves[ií]a|glorieta|callej[oó]n|'
               r'urbanizaci[oó]n|urb\.?|pol[ií]gono)\b[^\n]{2,80}',
}

# Patterns relaxed for the OCR path, where common character confusions break an
# exact match (e.g. Tesseract reading "@" as "O"). Used only on OCR'd text via
# ``ocr_tolerant=True`` so the digital-PDF path stays strict. Redaction only
# needs the *location*, so tolerating a misread keeps sensitive data covered.
PATTERN_DEFS_OCR = {
    'email': r'[A-Za-z0-9._%+\-]+[@oO0©][A-Za-z0-9.\-]+\.[A-Za-z]{2,}',
}

# Default amount of padding (in pixels at 144 DPI) added around each detected
# box so the bar fully covers ascenders/descenders and anti-aliased edges.
DEFAULT_PADDING = 2


def available_patterns():
    """Return the list of built-in pattern keys (for building the UI)."""
    return list(PATTERN_DEFS.keys())


def _compile(patterns, keywords, ocr_tolerant=False):
    """Build a single combined regex from the chosen presets and keywords.

    Args:
        patterns: Iterable of keys from :data:`PATTERN_DEFS`.
        keywords: Iterable of literal strings to match case-insensitively.
        ocr_tolerant: When True, use the relaxed :data:`PATTERN_DEFS_OCR`
            variant for any pattern that has one (for matching OCR'd text).

    Returns:
        A compiled ``re.Pattern`` (case-insensitive), or ``None`` if nothing
        was selected.
    """
    parts = []
    for key in patterns or ():
        frag = None
        if ocr_tolerant:
            frag = PATTERN_DEFS_OCR.get(key)
        if frag is None:
            frag = PATTERN_DEFS.get(key)
        if frag:
            parts.append(frag)
    for kw in keywords or ():
        kw = kw.strip()
        if kw:
            parts.append(re.escape(kw))
    if not parts:
        return None
    return re.compile('|'.join(f'(?:{p})' for p in parts), re.IGNORECASE)


def _group_into_lines(boxes):
    """Split a run of character boxes into one bounding box per text line.

    A match such as a phone number written with spaces stays on one line, but a
    keyword that wraps, or a greedy pattern that bridges two lines, would
    otherwise yield a single rectangle spanning the whole block. Grouping by
    vertical position keeps each emitted rectangle tight to its line.

    Args:
        boxes: List of ``(left, top, right, bottom)`` pixel boxes, in reading
               order.

    Yields:
        ``(left, top, right, bottom)`` bounding boxes, one per detected line.
    """
    line = []
    line_top = line_bottom = None
    for box in boxes:
        l, t, r, b = box
        mid = (t + b) / 2
        if line and not (line_top <= mid <= line_bottom):
            yield _union(line)
            line = []
            line_top = line_bottom = None
        line.append(box)
        line_top = t if line_top is None else min(line_top, t)
        line_bottom = b if line_bottom is None else max(line_bottom, b)
    if line:
        yield _union(line)


def _union(boxes):
    """Return the bounding box that contains all the given boxes."""
    lefts, tops, rights, bottoms = zip(*boxes)
    return (min(lefts), min(tops), max(rights), max(bottoms))


def match_units(units, patterns=None, keywords=None, padding=DEFAULT_PADDING,
                ocr_tolerant=False):
    """Find pattern/keyword hits in a list of text units and return rectangles.

    Args:
        units: List of ``(char, (left, top, right, bottom))`` pairs whose boxes
               are in image pixels (top-left origin), in reading order. A unit
               may use ``None`` for its box (e.g. a synthetic space between OCR
               words); such units take part in the text but contribute no box.
        patterns: Iterable of keys from :data:`PATTERN_DEFS` to enable.
        keywords: Iterable of literal keyword strings to match.
        padding: Pixels to grow each rectangle on every side.
        ocr_tolerant: When True, use relaxed pattern variants for OCR'd text.

    Returns:
        list[tuple]: ``(start_xy, end_xy)`` rectangles in original-image pixel
        coordinates, where ``start`` is the top-left and ``end`` the
        bottom-right corner. Overlapping hits are merged so text is never
        barred twice. Empty if nothing matched.
    """
    regex = _compile(patterns, keywords, ocr_tolerant=ocr_tolerant)
    if regex is None or not units:
        return []

    text = ''.join(u[0] for u in units)
    if not text.strip():
        return []

    # Merge overlapping/adjacent match spans so the same characters aren't
    # covered by several rectangles from different patterns.
    spans = []
    for m in regex.finditer(text):
        s, e = m.start(), m.end()
        if e <= s:
            continue
        if spans and s <= spans[-1][1]:
            spans[-1] = (spans[-1][0], max(spans[-1][1], e))
        else:
            spans.append((s, e))

    rectangles = []
    for s, e in spans:
        boxes = [units[i][1] for i in range(s, e) if units[i][1] is not None]
        if not boxes:
            continue
        for l, t, r, b in _group_into_lines(boxes):
            rectangles.append((
                (int(l - padding), int(t - padding)),
                (int(r + padding), int(b + padding)),
            ))
    return rectangles


def _digital_units(textpage, page_height_px, scale):
    """Build text units from a pdfium text page in image-pixel coordinates.

    pdfium reports character boxes as ``(left, bottom, right, top)`` in PDF
    points with a bottom-left origin. The page was rasterised at ``scale``
    (pixels per point), so a point maps to ``scale`` pixels and the y-axis is
    flipped about the rendered image height.

    Args:
        textpage: An open ``pypdfium2`` text page.
        page_height_px: Height of the rendered page image, in pixels.
        scale: Render scale (pixels per PDF point).

    Returns:
        list[tuple]: ``(char, (left, top, right, bottom))`` units in pixels.
    """
    units = []
    n = textpage.count_chars()
    for i in range(n):
        ch = textpage.get_text_range(i, 1)
        if not ch:
            continue
        l, bot, r, top = textpage.get_charbox(i)
        # PDF points (bottom-left origin) -> image pixels (top-left origin).
        px_box = (
            l * scale,
            page_height_px - top * scale,
            r * scale,
            page_height_px - bot * scale,
        )
        for c in ch:
            units.append((c, px_box))
    return units


def find_boxes_digital(source_path, page_index, scale, image_height_px,
                       patterns=None, keywords=None, password=None,
                       padding=DEFAULT_PADDING):
    """Detect sensitive text on a digital PDF page and return redaction boxes.

    Opens the page's text layer with ``pypdfium2`` (no OCR), so it only finds
    text that is actually encoded in the PDF. Scanned/image-only pages yield no
    matches here — use :func:`coverup.ocr.find_boxes_ocr` for those.

    Args:
        source_path: Path to the source PDF.
        page_index: 0-based page index.
        scale: Render scale used at import (pixels per PDF point).
        image_height_px: Height of the rendered page image, in pixels.
        patterns: Iterable of keys from :data:`PATTERN_DEFS`.
        keywords: Iterable of literal keyword strings.
        password: PDF password, if the document is encrypted.
        padding: Pixels to grow each rectangle on every side.

    Returns:
        list[tuple]: ``(start_xy, end_xy)`` rectangles in original-image pixel
        coordinates. Empty if nothing matched or the page has no text layer.
    """
    import pypdfium2 as pdfium

    pdf = page = textpage = None
    try:
        if password:
            pdf = pdfium.PdfDocument(source_path, password=password)
        else:
            pdf = pdfium.PdfDocument(source_path)
        page = pdf[page_index]
        textpage = page.get_textpage()
        units = _digital_units(textpage, image_height_px, scale)
        return match_units(units, patterns, keywords, padding)
    finally:
        for obj in (textpage, page, pdf):
            if obj is not None:
                try:
                    obj.close()
                except Exception:
                    pass


def page_has_text(source_path, page_index, password=None):
    """Return True if the given PDF page has an extractable text layer.

    Used to decide whether digital detection is worthwhile or OCR is needed.
    """
    import pypdfium2 as pdfium

    pdf = page = textpage = None
    try:
        if password:
            pdf = pdfium.PdfDocument(source_path, password=password)
        else:
            pdf = pdfium.PdfDocument(source_path)
        page = pdf[page_index]
        textpage = page.get_textpage()
        return textpage.count_chars() > 0
    except Exception:
        return False
    finally:
        for obj in (textpage, page, pdf):
            if obj is not None:
                try:
                    obj.close()
                except Exception:
                    pass
