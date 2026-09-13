#!/usr/bin/env python3
"""Convert Slackware .FNT console bitmap fonts (8x16, 256 glyphs, CP437)
to monospace TrueType fonts.

FNT layout: 4096 bytes, 256 records of 16 bytes each; record N is glyph N
stored top-to-bottom, 1 byte per row, 8 px per row, MSB = leftmost pixel.

Usage:  python fnt2ttf.py [-o OUTDIR] [FNT ...]
"""
import argparse
import collections
import os

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

GLYPHS_PER_FILE = 256
GLYPH_H = 16
GLYPH_W = 8
EM = 16  # 1 unit = 1 pixel

# letters used to locate the baseline (mode of their bottom ink row)
BASELINE_PROBES = b"abcdefghjkmnpqrstuvwxyz" \
                  b"ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def load_fnt(path):
    data = open(path, "rb").read()
    expected = GLYPHS_PER_FILE * GLYPH_H
    if len(data) < expected:
        raise ValueError(f"{path}: expected {expected} bytes, got {len(data)}")
    return [data[i * GLYPH_H:(i + 1) * GLYPH_H] for i in range(GLYPHS_PER_FILE)]


def ink_extent(glyph_rows):
    """Return (min_row, max_row) of ink, or None if blank."""
    rows = [i for i, b in enumerate(glyph_rows) if b != 0]
    return (min(rows), max(rows)) if rows else None


def detect_baseline(glyphs):
    """Baseline = most common bottom ink row among the probe letters."""
    bottoms = []
    for c in BASELINE_PROBES:
        ext = ink_extent(glyphs[c])
        if ext:
            bottoms.append(ext[1])
    if not bottoms:
        raise ValueError("no probe glyphs have ink")
    return collections.Counter(bottoms).most_common(1)[0][0]


def glyph_to_pen(glyph_rows, baseline):
    """Turn bitmap rows into TT contours: one rectangle per horizontal ink run.

    Font coords: the FNT baseline row must sit on the font baseline (y=0),
    so the em box is exactly 16 px tall with FNT row 0 at the top (y=ascent)
    and row 15 at the bottom (y=-descent). FNT row r occupies the font band
    [baseline - r, baseline - r + 1), i.e. top_edge = baseline + 1 - r.
    """
    pen = TTGlyphPen(None)
    asc = baseline + 1
    for r, b in enumerate(glyph_rows):
        if b == 0:
            continue
        c = 0
        while c < GLYPH_W:
            if b & (1 << (GLYPH_W - 1 - c)):
                c0 = c
                while c < GLYPH_W and (b & (1 << (GLYPH_W - 1 - c))):
                    c += 1
                y_top = asc - r
                y_bot = asc - (r + 1)
                x0, x1 = c0, c
                # closed rectangle contour (TrueType, on-curve points only)
                pen.moveTo((x0, y_bot))
                pen.lineTo((x0, y_top))
                pen.lineTo((x1, y_top))
                pen.lineTo((x1, y_bot))
                pen.closePath()
            else:
                c += 1
    return pen.glyph()


def build_ttf(src, out_path, family):
    glyphs = load_fnt(src)
    baseline = detect_baseline(glyphs)
    ascent = baseline + 1      # font units from baseline to em-box top
    descent = GLYPH_H - 1 - baseline  # font units from baseline to em-box bottom

    # code -> unicode via CP437
    cmap = {}
    for code in range(1, GLYPHS_PER_FILE):
        ch = bytes([code]).decode("cp437")
        cmap[ord(ch)] = f"u{ord(ch):04X}"

    glyph_order = [".notdef"] + [cmap[k] for k in sorted(cmap)]
    glyph_set = {".notdef": glyph_to_pen(glyphs[0], baseline)}
    for code in range(1, GLYPHS_PER_FILE):
        name = cmap[ord(bytes([code]).decode("cp437"))]
        glyph_set[name] = glyph_to_pen(glyphs[code], baseline)

    fb = FontBuilder(EM, isTTF=True)
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyph_set)
    # Left side bearing must equal each glyph's xMin so the ink lands in the
    # correct column.  With lsb=0, a glyph like '│' (xMin=3) gets its ink
    # snapped 3px left by FreeType/DirectWrite grid-fitting, which breaks the
    # box-drawing corner junctions.
    hmetrics = {}
    for name, g in glyph_set.items():
        xmin = g.xMin if g.numberOfContours > 0 else 0
        hmetrics[name] = (GLYPH_W, xmin)
    fb.setupHorizontalMetrics(hmetrics)
    fb.setupHorizontalHeader(ascent=ascent, descent=-descent)
    fb.setupOS2(sTypoAscender=ascent, sTypoDescender=-descent,
                usWinAscent=ascent, usWinDescent=descent,
                usWeightClass=400, usWidthClass=5,
                sxHeight=7, sCapHeight=baseline - 1)
    # FontBuilder leaves OS/2.fsSelection at 0; set USE_TYPO_METRICS so the
    # typo metrics (which we set correctly) are the ones Windows uses.
    fb.font["OS/2"].fsSelection = 0x40
    # FontBuilder's default head.flags (0x0003) claims embedded bitmap strikes
    # (bit 0) even though we ship no EBDT/EBLC — a validator flags that.
    fb.font["head"].flags = 0x0000
    fb.font["head"].lowestRecPPEM = 8
    # nameID 2 (styleName) is REQUIRED by Windows Font Viewer; without it the
    # file is rejected as "not a valid font file" even though GDI/DirectWrite
    # tolerate it.  nameID 3 (uniqueFontIdentifier) is also expected.
    fb.setupNameTable({
        "familyName": family,
        "styleName": "Regular",
        "fullName": f"{family} Regular",
        "psName": family.replace(" ", ""),
        "uniqueFontIdentifier": f"{family.replace(' ', '')}; v1.000",
        "version": "Version 1.000",
        "copyright": "Copyright (c) 2026",
        "description": (f"Monospace 8x16 TrueType conversion of the "
                        f"Slackware console bitmap font {os.path.basename(src)} "
                        f"(CP437, 256 glyphs)."),
    })
    fb.setupPost()
    fb.save(out_path)
    return ascent, descent


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("fnts", nargs="*", default=["RO.FNT", "RL.FNT"])
    ap.add_argument("-o", "--outdir", default="out")
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    for fnt in args.fnts:
        stem = os.path.splitext(os.path.basename(fnt))[0]
        family = f"Slackware {stem} 8x16"
        out = os.path.join(args.outdir, f"{stem}.ttf")
        ascent, descent = build_ttf(fnt, out, family)
        print(f"{fnt} -> {out}  ({family}; ascent {ascent} descent {descent})")


if __name__ == "__main__":
    main()
