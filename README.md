# fnt-to-ttf

Converts the classic Slackware console bitmap fonts (`.FNT`, 8x16) into
monospace TrueType fonts for use in Windows Terminal, code editors, and any
other modern application that wants an authentic retro terminal look.

## Background

Back in 2014 I asked on [LinuxQuestions.org](https://www.linuxquestions.org/questions/slackware-14/converting-classic-slackware-fonts-fnt-to-truetype-fonts-4175536834-print/)
whether anyone had figured out how to convert the classic Slackware `.FNT`
console fonts to TrueType. A working solution eluded me for over a decade —
until, with the help of Hermes Agent running Qwen3.8-27B, one finally turned
up. Delighted.

## The `.FNT` format

Slackware's console bitmap fonts are dead simple:

- 4096 bytes = 256 records of 16 bytes each
- record N is glyph N, stored top-to-bottom, one byte per row
- 8 pixels per row, MSB = leftmost pixel
- the low half (0x00-0x7F) is ASCII; the high half (0x80-0xFF) is CP437
  (box drawing, blocks, accents, Greek)

## Usage

```
python fnt2ttf.py [-o OUTDIR] [FNT ...]
```

Defaults to `RO.FNT` and `RL.FNT`. Each font gets its baseline detected
automatically (mode of the bottom-ink row across the lowercase/uppercase
probe letters) and is emitted with an em box of exactly 16 units, advance
width 8 (true monospace), and a CP437 character map.

Pre-built outputs are checked in under `out/`:

| file | family | metrics |
|------|--------|---------|
| `out/RO.ttf` | Slackware RO 8x16 | ascent 12, descent 4 |
| `out/RL.ttf` | Slackware RL 8x16 | ascent 13, descent 3 |

(RL sits one row lower than RO; that's inherent to the source fonts, not a
conversion choice.)

## Two Windows gotchas (the real bugs)

These cost the most time and will bite any future `.FNT` conversion:

1. **The `name` table must include nameID 2 (styleName).** Windows Font
   Viewer requires it and rejects the file as "not a valid font file"
   without it — even though GDI and DirectWrite both tolerate the omission.
2. **Left side bearing must equal each glyph's `xMin`.** With `lsb = 0`, a
   glyph like `│` (xMin 3) gets its ink snapped 3px left by grid-fitting,
   which breaks the box-drawing corner junctions. This masquerades as a
   "box drawing doesn't meet up" problem but is actually a metrics bug.

## Verification

- `final_verify.py` — rasterizes all 256 TTF glyph contours (own even-odd
  scanline) and compares unit-for-unit against the raw `.FNT` bitmaps.
  Both fonts pass 256/256.
- `box_compare.py` — renders the 3x3 box-drawing sample from the TTF and
  compares it against the source bitmap layout.

## Notes

- The original `.FNT` files are gitignored (`*.FNT`) because I'm not sure
  I have redistribution rights to the Slackware sources. The converted
  `.ttf` outputs and the converter itself are checked in.
- License: MIT, see `LICENSE`.
