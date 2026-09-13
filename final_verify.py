"""Final verification (correct mapping): rasterize BOTH the TTF contours and
the FNT source into the same 8x16 bitmap grid (row 0 = top), then compare.
This is the definitive 'does the TTF encode the bitmap exactly' check."""
import os
from fontTools.ttLib import TTFont

def ttf_to_bitmap(g):
    """Rasterize TTF contours to an 8x16 bitmap (row 0 = top of em box,
    font y = asc - row).  A bitmap row r is covered if the contour fill
    intersects the band (asc-r-1, asc-r] in font space."""
    H = 16
    # We don't have asc here; pass it in.  We'll rasterize in font space:
    # for each row r (0..15), check if any horizontal scanline within the band
    # is covered.  Simpler: sample the fill at font-y = asc - r - 0.5 for each row.
    # But we don't know asc; the caller passes it.
    raise NotImplementedError

def verify(fnt, ttf):
    data = open(fnt, "rb").read()
    H = 16
    t = TTFont(ttf)
    asc = t["hhea"].ascent
    cmap = t.getBestCmap()
    glyf = t["glyf"]
    hmtx = t["hmtx"]
    exact = 0; fail = []; advs = set()
    for code in range(256):
        u = bytes([code]).decode("cp437"); cp = ord(u)
        gname = cmap.get(cp)
        if gname is None:
            exact += 1; continue
        g = glyf[gname]
        adv, lsb = hmtx[gname]
        advs.add(adv)
        # rasterize TTF into bitmap rows 0..15 (row r: font-y band (asc-r-1, asc-r])
        # A row is "on" if the fill covers any point in that row's band.
        ttf_bm = [[0]*8 for _ in range(H)]
        if g.numberOfContours > 0:
            coords = [(p[0], p[1]) for p in g.coordinates]
            endpts = g.endPtsOfContours
            polys = []
            prev = 0
            for ep in endpts:
                polys.append(coords[prev:ep+1]); prev = ep + 1
            for r in range(H):
                # font-y for this bitmap row center: cy = asc - r - 0.5
                cy = asc - r - 0.5
                for x in range(8):
                    cx = x + 0.5
                    crossings = 0
                    for poly in polys:
                        n = len(poly)
                        for i in range(n):
                            x1, y1 = poly[i]; x2, y2 = poly[(i+1) % n]
                            if (y1 > cy) != (y2 > cy):
                                xint = x1 + (cy - y1) / (y2 - y1) * (x2 - x1)
                                if xint > cx:
                                    crossings += 1
                    if crossings % 2 == 1:
                        ttf_bm[r][x] = 1
        # source bitmap
        src_bm = [[0]*8 for _ in range(H)]
        gdata = data[code*H:(code+1)*H]
        for r in range(H):
            b = gdata[r]
            for c in range(8):
                if b & (1 << (7 - c)):
                    src_bm[r][c] = 1
        if ttf_bm == src_bm:
            exact += 1
        else:
            diff = sum(1 for r in range(H) for c in range(8) if ttf_bm[r][c] != src_bm[r][c])
            fail.append((code, u, diff))
    return exact, fail, advs

for s in ["RO", "RL"]:
    fnt = os.path.abspath(f"{s}.FNT")
    ttf = os.path.abspath(f"out/{s}.ttf")
    exact, fail, advs = verify(fnt, ttf)
    print(f"{s}: {exact}/256 pixel-exact  advance_widths={advs}")
    if fail:
        print("   fails (code, char, diffpx):", fail[:12])
