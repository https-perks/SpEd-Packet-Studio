from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen


def glyph(width: int, height: int):
    pen = TTGlyphPen(None)
    if width and height:
        pen.moveTo((80, 0))
        pen.lineTo((width - 80, 0))
        pen.lineTo((width - 80, height))
        pen.lineTo((80, height))
        pen.closePath()
    return pen.glyph()


root = Path(__file__).resolve().parent.parent
output = root / "assets" / "fonts" / "SpEdPacketTest.ttf"
output.parent.mkdir(parents=True, exist_ok=True)
order = [".notdef", "space"] + [f"uni{code:04X}" for code in range(32, 127)]
builder = FontBuilder(1000, isTTF=True)
builder.setupGlyphOrder(order)
builder.setupCharacterMap({code: f"uni{code:04X}" for code in range(33, 127)} | {32: "space"})
builder.setupGlyf({name: glyph(600, 700) if name not in {".notdef", "space"} else glyph(0, 0) for name in order})
builder.setupHorizontalMetrics({name: (600, 0) for name in order})
builder.setupHorizontalHeader(ascent=800, descent=-200)
builder.setupNameTable({"familyName": "SpEd Packet Test", "styleName": "Regular",
                        "uniqueFontIdentifier": "SpEdPacketTest-Regular-1", "fullName": "SpEd Packet Test Regular",
                        "psName": "SpEdPacketTest-Regular", "version": "Version 1.0"})
builder.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
builder.setupPost()
builder.save(output)
print(output)
