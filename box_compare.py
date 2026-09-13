"""Definitive issue-#2 check: render the 3x3 box two ways at exactly 16px:
  (A) source FNT, 1:1 (exact pixels, no rasterizer) -- the ground truth
  (B) the TTF via FreeType (PIL) -- what a terminal actually shows
If (A) and (B) match, the boxes meet up. If (B) has gaps, it's grid-fitting."""
import os
from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont

TTF = os.path.abspath("out/RO.ttf")
t = TTFont(TTF)
asc = t["hhea"].ascent
data = open(os.path.abspath("RO.FNT"), "rb").read()
H = 16

TL,TR,BL,BR = 0xDA,0xBF,0xC0,0xD9
Hh,V = 0xC4,0xB3
grid = [[TL,Hh,TR],[V,0x20,V],[BL,Hh,BR]]
def ch(c): return bytes([c]).decode("cp437")

# (A) source FNT box, 1:1 (24 wide x 48 tall)
def fnt_box():
    out = [[0]*24 for _ in range(48)]
    for r,row in enumerate(grid):
        for c,code in enumerate(row):
            g = data[code*H:(code+1)*H]
            for y in range(H):
                b = g[y]
                for i in range(8):
                    if b & (1<<(7-i)):
                        out[r*H+y][c*8+i] = 1
    return out

# (B) TTF via FreeType at 16px
def ttf_box():
    W,Hh2 = 24, 48
    img = Image.new("L",(W,Hh2),0)
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(TTF,16)
    for r,row in enumerate(grid):
        for c,code in enumerate(row):
            if code==0x20: continue
            # draw with top-left of em box at (c*8, r*16)
            d.text((c*8, r*16), ch(code), font=font, fill=255, anchor="la")
    px = img.load()
    return [[1 if px[x,y]>96 else 0 for x in range(W)] for y in range(Hh2)]

A = fnt_box()
B = ttf_box()

def dump(label, m):
    print(f"\n{label}:")
    for row in m:
        print("  " + "".join("#" if v else "." for v in row))

dump("(A) SOURCE FNT box, 16px exact (ground truth)", A)
dump("(B) TTF via FreeType 16px (what terminal shows)", B)

# diff
diffs = sum(1 for y in range(48) for x in range(24) if A[y][x]!=B[y][x])
print(f"\nPixel differences A vs B: {diffs} / {24*48}")
if diffs == 0:
    print("==> IDENTICAL: the boxes meet up exactly at 16px. No grid-fitting issue.")
else:
    print("==> DIFFER: the differences are below (only rows with differences):")
    for y in range(48):
        if any(A[y][x]!=B[y][x] for x in range(24)):
            print(f"  y={y:2}  A: " + "".join("#" if v else "." for v in A[y]))
            print(f"  y={y:2}  B: " + "".join("#" if v else "." for v in B[y]))
