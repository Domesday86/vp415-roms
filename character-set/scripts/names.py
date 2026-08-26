"""Character names, in code order, from Table 1 of the MB88303 datasheet."""

NAMES = (
    ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M",
     "raised dot", "under-bracket", "BLANK"] +
    ["N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z",
     "colon  :", "solid block", "left paren  ("] +
    ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
     "question  ?", "exclamation  !", "apostrophe  '", "period  .",
     "BACKGROUND", "right paren  )"] +
    ["arrow up", "arrow down", "arrow left", "arrow right",
     "plus  +", "minus  -", "asterisk  *", "slash  /", "equals  =",
     "ampersand  &", "kanji NEN (year)", "kanji GETSU (month)",
     "kanji NICHI (day)", "comma  ,", "tilde  ~", "telephone"]
)

SPECIAL = {
    0x0F: "printed as a dashed outline - a marker, not a dot pattern (all dots clear)",
    0x2E: "printed as an open outline - selects the black background block (all dots clear)",
}


def art(byte):
    """one row of a glyph as dots and hashes"""
    return "".join("#" if (byte >> (4 - c)) & 1 else "." for c in range(5))
