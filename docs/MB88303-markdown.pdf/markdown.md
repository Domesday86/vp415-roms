Advanced Products

FUJITSU

# ■ MB88303

NMOS Television Display Controller (TVDC)

October 1986

Edition 2.0

# Description

The Fujitsu MB88303 NMOS Television Display Controller (TVDC) is an interface LSI that displays 180 alphanumeric characters (20 characters x 9 lines) in white on a TV screen. The characters overlay the picture on the TV screen.

While designed to operate in conjunction with the Fujitsu MB8840/8850 and MB88400/88500 single-chip 4-bit microcomputers, the MB88303 TVDC can also be interfaced to a wide range of 4- and 8-bit microprocessors.

The MB88303 allows simple interface to almost any TV display (raster scan CRT with horizontal and vertical scanning) regardless of interlace or non-interlace scan.

The MB88303 is fabricated with N-channel silicon-gate E/D MOS process, and packaged in a 22-pin plastic DIP. Also, it is powered by a single +5V power supply, and operates over a temperature range of -30°C to +70°C.

# Features

- Character display controller available for NTSC, PAL and SECAN TV sets
- 20 character x 9-line screen format (Max. 180 characters/screen)
- 5x7-dot matrix character format (1-dot horizontal and 2-dot vertical spacings)
- 64-character set
- Programmable character size: 4 widths and 4 heights
- Programmable display start position: 57 horizontal and 64 vertical positions
- Programmable character blinking control

- Automatic inter-dot filling function for improved smoothness
- Black-level background output for improved clarity
- 180 x 7-bit display data RAM
- 448 x 5-bit character generator ROM
- Four control registers
- 3-bit general-purpose open-drain latched output
- On-chip clock generator for external RC-network
- Single +5V power supply
- Wide operating temperature range: -30°C to +70°C
- N-channel silicon-gate E/D MOS process
- 22-pin plastic DIP (Suffix -P)

![img-0.jpeg](img-0.jpeg)

4-81

4

MB88303

# Pin Assignment
And Logic Symbol

![img-1.jpeg](img-1.jpeg)

![img-2.jpeg](img-2.jpeg)

# Block Diagram

![img-3.jpeg](img-3.jpeg)

• THESE REGISTERS ARE DESIGNATED BY ONE ADDRESS AS THE DISPLAY CONTROL REGISTER.

FUJITSU

4-82

MB88303

# Pin Description

|   | Symbol | Pin No. | Type | Function  |
| --- | --- | --- | --- | --- |
|  Power Supply | V_{CC} | 22 | — | +5V power supply pin.  |
|   |  V_{SS} | 11 | — | Ground pin.  |
|  Clock | EX | 9 | I | RC-network externally connected to these pins from On-chip oscillator 6MHz clock generator.  |
|   |  X | 10 | O  |   |
|  Processor Interface | RESET | 1 | I | Reset input: A low level on RESET stops the TVDC and initializes its internal control registers to the following states: Horizontal Display Position Register : Cleared. Vertical Display Position Register : Cleared. Display/Character Control Register : Cleared. (consisting of Horizontal Character Size, Vertical Character Size, and Blinking Registers) General-Purpose Output Register : Set. As a result, the output pins are clamped in the following states: VOW = "L", VOB = "H", DO2 = DO1 = DO0 = "H" The address register and display memory are not affected by RESET. This pin is a non-TTL compatible hysteresis input with an internal pull up.  |
|   |  ADM | 13 | I | Address mode select input for writing data to the internal registers and the display memory: A low level on ADM activates the Direct Address mode. A high level on ADM activates the Address Increment mode. This pin is a TTL compatible input with an internal pull up.  |
|   |  LDI | 12 | I | Write strobe input for multiplexed address/data: Direct Address Mode: At the leading edge of LDI, an 8-bit address on DA7-DA0 is automatically latched into the internal address register. At the trailing edge of LDI, a 7-bit data on DA6-DA0 is written into an internal control register or an internal display memory location that is designated by the address latched at the leading edge. Address Increment Mode: At the leading edge of LDI, the address register is automatically incremented. At the trailing edge of LDI, a 7-bit data on DA6-DA0 is written into an internal control register or a display memory location that is indicated by the address register. This is a non-TTL compatible input with an internal pull up.  |
|   |  DA7-DA0 | 21-14 | I | 8-bit parallel multiplexed address/data input: An address/data on DA7-DA0 is written into the internal registers or the display memory at the LDI transition. The address/data input format is DA7: the most significant bit (MSB) DA0: the least significant bit (LSB) These pins are TTL compatible with internal pull up.  |

FUJITSU

4-83

4

MB88303

Pin Description

(Continued)

Television Interface

|  Symbol | Pin No. | Type | Function  |
| --- | --- | --- | --- |
|  HSYNC | 8 | I | Horizontal synchronization input: HSYNC pulses are supplied by the TV set connected. This signal is the same as the horizontal sync signal of the TV display, which controls display start position. The MB88303 starts to output character bit patterns on the VOW output, triggered by HYSNC pulse. This pin is a non-TTL compatible hysteresis input with an internal pull up.  |
|  VSYNC | 7 | I | Vertical synchronization input: VSYNC pulses are supplied by the TV set connected. This signal is the same as the vertical sync signal of TV display, which controls display starts position. The MB88303 starts to output character bit patterns on the VOW output, triggered by VSYNC pulse. This pin is a non-TTL compatible hysteresis input with an internal pull up.  |
|  VOW | 5 | O | White-level video signal output: The device serially outputs character dot patterns on VOW synchronously with HYSNC pulses. This signal is used for brightness modulation of the TV display. This signal is superimposed on the normal TV video signal. This pin is a TTL compatible output.  |
|  VOB | 6 | O | Black-level video signal output: This signal is supplied to the TV to improve clarity of displayed characters when BLK and BLKB bits of the blinking register are set. This pin is a TTL compatible output.  |
|  DO2-DO0 | 4-2 | O | 3-bit parallel output port: Data written into the general output register appears on pins DO₂-DO₀ These signals are used for other attribute control to TV. These are latched open-drain outputs.  |

FUJITSU

4-84

MB88303

# Functional Description

# Screen Format and Character Format

The MB88303 TVDC supports the display of 9 lines of 20 characters per line, or a total of up to 180 alphanumeric characters, as shown in Figure 1.

The characters are formed in a 5 x 7-dot matrix, with a 1-dot

space between characters and a 2-dot space between lines. Screen Format also shows the relative on-screen size of the displayed elements. Figure 2 shows the character format.

Character Patterns and Codes
The MB88303 has a built-in 5 x 7-dot matrix character

generator ROM. Fig. 6(a) shows internal character patterns in the character generator, which are automatically modified by "filling" function and displayed on the screen as shown in Figure 3(b). The character patterns are encoded as shown in Table 1.

Figure 1. Screen Format

![img-4.jpeg](img-4.jpeg)

![img-5.jpeg](img-5.jpeg)

NOTE:
NUMBERS 0 to 179 INDICATE DISPLAY MEMORY ADDRESSES.

Figure 2. Character Format

![img-6.jpeg](img-6.jpeg)

Note:
Refer to Page 10 for an explanation of the difference between blanks and background.

Table 1. Character Codes

|  CH5-4  |   |   |   |   |
| --- | --- | --- | --- | --- |
|  CH3-0 | 0 | 1 | 2 | 3  |
|  0 | A | N | 0 | !  |
|  1 | B | O | 1 | ;  |
|  2 | C | P | 2 | --  |
|  3 | D | Q | 3 | --  |
|  4 | E | R | 4 | +  |
|  5 | F | S | 5 | -  |
|  6 | G | T | 6 | *  |
|  7 | H | U | 7 | /  |
|  8 | I | V | 8 | =  |
|  9 | J | W | 9 | &  |
|  A | K | X | ? | ※ (kanji)  |
|  B | L | Y | ! | 月 (kanji)  |
|  C | M | Z | (apostrophe) | B (kanji)  |
|  D | (raised dot) | : | (period) | (comma)  |
|  E | □ | ■ | □ (background) | ~  |
|  F | (blank) | [ | ] | (Telephone)  |

FUJITSU

4-85

4

MB88303

Functional Description
(Continued)

Figure 3(a). Internal Character Dot Patterns
(Character Generator ROM Patterns)

![img-7.jpeg](img-7.jpeg)

Figure 3(b). Displayed Character Dot Patterns
(Format with "Filling" Function)

![img-8.jpeg](img-8.jpeg)

FUJITSU

4-86

MB88303

# Functional Description
(Continued)

# Address Structure

All addresses are 8-bit words.
Addresses from 0 [00000000]
to 179 [10110011] indicate the
display memory locations.
Addresses from 180
[10110100] to 183 [10110111]
are used for the control
registers. Figure 4 shows the
memory map. Selected
addresses are input through
pins DA7 to DA0. Addresses
184 above cannot be used.

# Display Memory

The display memory is a 180 x
7-bit RAM. Bits 5 to 0 (CH5-
CH0) are character code
storage; Bit 6 (BC) can be set
to "1" to enable blinking, and
reset to zero to disable
blinking.

Figure 5 shows the word
structure; refer to Character
Codes table for character
codes (see page 5). Selected
character codes and blinking
control bit are input through
pins DA6 to DA0.

# Control Registers

# Horizontal Display Position
Register [HP5 to HP0]

This register (address 180)
stores the horizontal position
of the start of the display on the
TV screen. The values (000000)
to (000110) cannot be used for
the horizontal display position
register. Since the RESET
input clears this register, a
value must be set after every
RESET input. Figure 6 shows
the horizontal display position
register. For the display
starting position control, see
page 9.

# Vertical Display Position
Register [VP5 to VP0]

This register (address 181)
stores vertical position of the
start of the display on the TV
screen. Since the RESET
input clears this register, a
value must be set after every
RESET input. Figure 7 shows
the vertical display position
register. For the display
starting position control see
page 9.

Figure 4. Display Memory & Control Register Map

![img-9.jpeg](img-9.jpeg)

Figure 5. Display Memory Word Format

![img-10.jpeg](img-10.jpeg)

Figure 6. Horizontal Display Position Register Format

![img-11.jpeg](img-11.jpeg)

Figure 7. Vertical Display Position Register Format

![img-12.jpeg](img-12.jpeg)

FUJITSU

4-87

4

MB88303

# Functional Description
(Continued)

# Display Control Register

(1) Horizontal Character Size
Register [HSZ1 and HSZ0]

These bits indicate the width
of the characters. Character
width is selectable from 4
values determined by setting
HSZ1 and HSZ0 as shown in
Table 2. The reset input rests
both bits to zero.

Note: T is the period of
oscillation frequency Q. When
the oscillation frequency is Q
[Hz], the period at that time
T[s] is 1/Q.

(2) Vertical Character Size
Register [VSZ1 and VSZ0]

These bits indicate the height
of the characters. Character
height is selectable from 4
values by setting VSZ1 and
VSZ0 as shown in Table 3.
The reset input rests both bits
to zero.

Note: 1H (horizontal line) =
63.5μs. One screen at
non-interlace scan is 262.5H.

(3) Blinking Register [BLK,
BLKB and BLINK]

— Display Blanking Bit [BLK]

This bit indicates the status of
the characters display. When
BLK is zero, no data is
displayed; to enable display,
set BLK to "1". The reset input
resets BLK to zero.

— Background Blanking Bit
[BLKB]

This bit indicates the status of
the background display. When
BLKB is zero, background is
not displayed regardless of
data content; to enable
background display, set BLKB
to 1. The reset input resets
BLKB to zero.

— Blinking Enable Bit [BLINK]

This bit turns blinking on and
off. When BLINK is zero,
blinking is disabled regardless
of blink control bit value of the
display memory input; when
BLINK is "1", blinking is
enabled, provided that the
blink control bit of the display
memory is set to "1". The reset
input resets BLINK to zero.

Figure 8. Display Control Register Format

![img-13.jpeg](img-13.jpeg)

Table 2. Horizontal Character Size

|  Code |   | Size |   | Size  |   |
| --- | --- | --- | --- | --- | --- |
|  HSZ1 | HSZ0 | Character | Dot | Character (when Q = 6MHz, T = 167ns) | Dot  |
|  0 | 0 | 10T | 2T | 1.67μs | 0.33μs  |
|  0 | 1 | 20T | 4T | 3.34μs | 0.67μs  |
|  1 | 0 | 30T | 6T | 5.01μs | 1.0μs  |
|  1 | 1 | 40T | 8T | 6.68μs | 1.34μs  |

Table 3. Vertical Character Size

|  Code |   | Size  |   |
| --- | --- | --- | --- |
|  VSZ1 | VSZ0 | Character | Dot  |
|  0 | 0 | 14H | 2H  |
|  0 | 1 | 28H | 4H  |
|  1 | 0 | 42H | 6H  |
|  1 | 1 | 56H | 8H  |

Figure 9. General Output Register Format

![img-14.jpeg](img-14.jpeg)

Figure 10(a). Direct Address Mode Timing

![img-15.jpeg](img-15.jpeg)

FUJITSU

4-88

MB88303

# Functional Description
(Continued)

# General Output Register

This is a 3-bit latched output;
data written to DO2 to DO0 is
output to the open drain
terminals DO2 to DO0. The
reset input sets DO2 to DO0
lines to "1".

# Data Input

MB88303 has two modes for
writing data to the control
registers and display memory.
The modes are switched by the
ADM input.

# Direct Address Mode

This mode is enabled when
input to the ADM terminal is
low. When the input signal to
the LDI terminal goes high,
data on DA7 to DA0 are
latched to the address
register. When the LDI
terminal signal goes low,
7 bits of data, DA6 to DA0,
are written to the memory
specified by the memory
address register. Fig. 10(a) is
the timing diagram.

# Address Increment Mode

This mode is enabled when
input to the ADM terminal is
high. When the input signal
to the LDI terminal goes high,
the data currently latched to
the address register are
incremented. When the LDI
terminal signal goes low, 7 bits
of data, DA6 to DA0, are
written to the memory
specified by the address
register after incrementing.
Fig. 10(b) is the timing
diagram.

# Reset

1. The following internal
registers are cleared by
RESET.

Horizontal character size
register: HSZ1 = HSZ0 = "0"

Horizontal display position
register:
HP5 to HP0 = "0"

Vertical character size register:
VSZ1 = VSZ0 = "0"

Vertical display position
register:
VP5 to VP0 = "0"

Blinking register: BLINK =
BLKB = BLK = "0"

Figure 10(b). Address Increment Mode Timing

![img-16.jpeg](img-16.jpeg)

Figure 11. Display Start Position

![img-17.jpeg](img-17.jpeg)

Note: If T(s) is the period when the oscillating frequency
is fc (Hz), H will be equal to one period of the horizontal
synchronization signal.

2. General output register
(DO outputs) is set by
RESET.
DO2 = DO1 = DO0 = "1" ("H")

3. VOW and VOB outputs are
initialized by RESET as
follows:

VOW = "L", VOB = "H" (Blanks
are displayed on the screen.)

No character is displayed on
the TV screen until "BLK" bit
(Bit 4 of Blinking Register) is
set to "1".

4. Address register and
Display data memory are not
affected by RESET.

FUJITSU

4-89

4

MB88303

# Functional Description
(Continued)

# Display Starting Position
Control

The horizontal and vertical
display starting points on the
TV screen are determined by
specifying the position at
which the black background
display begins. This is done
with the values of addresses
HP5 to HP0 and VP5 to VP0
as shown in Fig. 6 and Fig. 7.

The horizontal starting position
HS and the vertical start
position VS may be found
using the following equations:

HS = T × 4 [2⁵ × HP5 + 2⁴ ×
HP4 + 2³ × HP3 + 2² × HP2²
+ 2 × HP1 + HP0) + P]

VS = H × 4 (2⁵ × VP5 + 2⁴ ×
VP4 + 2³ × VP3 + 2² × VP2 + 2 ×
VP1 + VP0)

where: P = width of character,
from Table 4;
T = 1/fc [fc = oscillating
frequency; 6MHz typ.]
H = period of horizontal
synchronization signal
[63.5μs typ.]

# Blinking Control

The MB88303 supports
blinking of any desired
character(s) on the screen.
Blinking affects only those
characters for which the
blinking bit is set to 1. Display
is on for approximately 0.5s
and off for the same period
(vertical synchronization
pulse x 64).

Table 4. P Values

|  HSZ1 | HSZ0 | P  |
| --- | --- | --- |
|  0 | 0 | 9  |
|  0 | 1 | 10  |
|  1 | 0 | 11  |
|  1 | 1 | 12  |

Figure 12(a). Dot Filling Examples

INTERNAL DOT PATTERN

![img-18.jpeg](img-18.jpeg)

DISPLAY DOT PATTERN

![img-19.jpeg](img-19.jpeg)

![img-20.jpeg](img-20.jpeg)

![img-21.jpeg](img-21.jpeg)

Figure 12(b). Simple 5×7 Matrix [Left] &
with "Filling" Function [Right]

![img-22.jpeg](img-22.jpeg)

![img-23.jpeg](img-23.jpeg)

Blinking can be set as follows:

1. Set the blinking enable bit of the display control register to 1.
2. Set the blink control bit to 1 for the position of the display memory corresponding to the character for which blinking is desired.

# "Filling" Function

"Filling" is the process
whereby dot matrix displays
like those in (A) of Fig. 12(a) 's,
are filled out to the form
shown in (B) by the display of
an intermediate dot. As can be
seen from Fig. 12(b) "filling"
results in a smoother and
more pleasing shape than
can be attained with an
ordinary 5 x 7-dot matrix.

FUJITSU

4-90

MB88303

# Functional Description
(Continued)

# Display Output Timing

Fig 13. shows the timing for
VOW and VOB for the
overlayed portion of a display
consisting of the letter "A", a
"blank" (character code 0F),
"background" (character
code 2E), and the letter "B",
with the display blinking and
background blanking set to 1.

Note that the display of the
background changes during
the "BLANK" character when
the VOB line goes high.

# Difference Between Blanks
and Background

Note: In Fig. 14(b) which
shows a screen of characters
overlaying the picture of a

woman, a blank (character
code 0F) displays differently
from background (character
code 2E), depending on
whether VOB is used or not.

In Fig. 14(b) both pictures
display the letter "A", a
"blank", a "background", the
letter "B", and a "blank".

In the right picture of Fig.
14(b), where VOB is on, the
character displays are
bounded by a black frame, so
that the spaces between
characters display as black.
Where a blank is displayed, a
5 x 7-dot portion of the TV
picture is visible. The

background display is
black.

In the left picture of Fig.
14(b), were VOB is off, the TV
picture is visible everywhere
on the screen except where
the characters display in
white. Here, blanks and
background are displayed
identically. Note that the
broken lines have been drawn
in to indicate where the
frames would be displayed if
they were displayed on the
screen.

Figure 13. Display Output Timing

![img-24.jpeg](img-24.jpeg)

Fig 14(a). Display of
TV Picture

Fig 14(b). Display of Character on TV Picture

• VOB OFF

• VOB ON

![img-25.jpeg](img-25.jpeg)

![img-26.jpeg](img-26.jpeg)

![img-27.jpeg](img-27.jpeg)

# Notes:

1. For HSYNC and VSYNC input signals, both cycle and rise/fall times must be constant.
2. Character output during the blanking period of TV should be inhibited. If not, character shapes may change. So, blanks should be written for memory addresses which cannot be displayed on the screen.

FUJITSU

4-91

4

MB88303

Functional Description
(Continued)

Figure 15. Application Example

![img-28.jpeg](img-28.jpeg)

Absolute Maximum
Ratings

|  Parameter | Symbol | Pin | Rating | Unit  |
| --- | --- | --- | --- | --- |
|  Supply Voltage | V_{CC} | V_{CC} | V_{SS} -0.3 to V_{SS} +7.0 | V  |
|  Input Voltage | V_{IN} | EX, RESET, ADM, LDI, DA7-DA0 | V_{SS} -0.3 to V_{SS} +7.0 | V  |
|  Output Voltage | V_{OUT} | VOW, VOB | V_{SS} -0.3 to V_{SS} +7.0 | V  |
|   |   |  DO0-DO2 | V_{SS} -0.3 to V_{SS} +15  |   |
|  Operating Temperature | T_{A} |  | -30 to +70 | °C  |
|  Storage Temperature | T_{stg} |  | -55 to +150 | °C  |
|  Power Dissipation | P_{D} |  | 600 | mW  |

Note: Permanent device damage may occur if ABSOLUTE MAXIMUM RATINGS are exceeded. Functional operation should be restricted to the conditions as detailed in the operational sections of this data sheet. Exposure to absolute maximum rating conditions for extended periods may affect device reliability.

FUJITSU

4-92

MB88303

Recommended Operating Conditions

|  Parameter | Symbol | Pin | Value |   |   | Unit  |
| --- | --- | --- | --- | --- | --- | --- |
|   |   |   |  Min. | Typ. | Max.  |   |
|  Supply Voltage | V_{CC} | V_{CC} | 4.5 | 5.0 | 5.5 | V  |
|   |  V_{SS} | V_{SS} | — | 0 |   |   |
|  Input High Voltage | V_{IH} | DA7-DA0, ADM | 2.0 |  | V_{CC} | V  |
|   |  V_{IHS} | RESET, LDI VSYNC, HSYNC | 3.0 |  | V_{CC} | V  |
|  Input Low Voltage | V_{IL} | DA7-DA0, ADM RESET, LDI VSYNC, HSYNC, EX | -0.3 |  | 0.8 | V  |
|  Operating Temperature | T_{A} |  | -30 |  | +70 | °C  |
|  Operating Clock Frequency | f_{c} | EX, X |  |  | 6.7 | MHz  |

DC Characteristics

(Recommended operating conditions unless otherwise noted.)

|  Parameter | Symbol | Pin | Value |   |   | Unit | Condition  |
| --- | --- | --- | --- | --- | --- | --- | --- |
|   |   |   |  Min. | Typ. | Max.  |   |   |
|  Output High Voltage | V_{OH} | VOW, VOB | 2.4 | — | — | V | V_{CC} = 4.5V, I_{OH} = -200μA  |
|   |   |  DO2-DO0 | Open Drain  |   |   |   |   |
|  Output Low Voltage | V_{OL} | VOW, VOB | — | — | 0.4 | V | V_{CC} = 4.5V, I_{OL} = 1.8mA V_{CC} = 4.5V, I_{OL} = 1.8mA, with 5kΩ external pull-up resistor  |
|   |   |  DO2-DO0 | — | — | 0.4  |   |   |
|  Output Leakage Current | I_{leak} | DO2-DO0 | — | — | 50 | μA | V_{CC} = 5.5V, V_{OH} = 13.2V, at OFF state with with 5KΩ external pull-up resistor  |
|  Input Leakage Current | I_{IL} | RESET, LDI, ADM, VSYNC, HSYNC, DA7-DA0 | — | — | -60 | μA | V_{CC} = 5.5V, V_{IL} = 0.4V  |
|  Supply Current | I_{CC} | V_{CC} | — | 80 | 120 | mA | V_{CC} = 5.5V, All outputs open, f_{c} = 6.7MHz, reset state  |

FUJITSU

4-93

4

MB88303

# AC Characteristics

(Recommended operating conditions unless otherwise noted.)

|  Parameter | Symbol | Pin | Value |   | Unit | Condition  |
| --- | --- | --- | --- | --- | --- | --- |
|   |   |   |  Min. | Max.  |   |   |
|  LDI Pulse Width | t_{WLDI} | LDI | 5 |  | μs | Fig. 15, Fig. 18  |
|  LDI Rise/Fall Time | t_{FLDI} t_{FLDI} | LDI |  | 1 | μs | Fig. 15, Fig. 18  |
|  ADM Setup Time | t_{AS} | ADM | 0.5 |  | μs | Fig. 15, Fig. 18  |
|  ADM Hold Time | t_{AH} | ADM | 2 |  | μs | Fig. 15, Fig. 18  |
|  Address/Data Setup Time | t_{S} | DA0 to DA7 | 0.5 |  | μs | Fig. 15, Fig. 18  |
|  Address/Data Hold Time | t_{H} | DA0 to DA7 | 2 |  | μs | Fig. 15, Fig. 18  |
|  DO Output Delay Time | t_{DD} | DO0 to DO2 |  | 0.6 | μs | Fig. 16, Fig. 18  |
|  RESET Pulse Width | t_{RST} | RESET | 4 |  | μs | Fig. 17, Fig. 18  |
|  RESET Setup Time | t_{RSTS} | RESET | 1 |  | μs | Fig. 17, Fig. 18  |
|  RESET Hold Time | t_{RSTH} | RESET | 3 |  | μs | Fig. 17, Fig. 18  |

Figure 15. Address/Data Input Timing

![img-29.jpeg](img-29.jpeg)

Figure 16. DO Output Timing

![img-30.jpeg](img-30.jpeg)

FUJITSU

4-94

MB88303

Figure 17. RESET Input Timing

![img-31.jpeg](img-31.jpeg)

# Notes:

1. If \( t_{\text{RSTS}} \) spec. (1μs min.) is not met, the MB88303 cannot be reset.
2. If \( t_{\text{RSTH}} \) spec. (3μs min.) is not met, then the TV screen will be disturbed. This is caused by the undefined data on the DA line written into internal registers and display memory at LDI's high-to-low transition during RESET = "L". This case occurs, for example, when RESET goes high just after LDI goes low, shown at top, right diagram. This unacceptable RESET timing is caused when the device is reset separately from the processor connected to the device. However, when LDI level is fixed high or low during reset (i.e. RESET = "L") shown at bottom right diagram, the TV screen is not disturbed.

![img-32.jpeg](img-32.jpeg)

![img-33.jpeg](img-33.jpeg)

Figure 18. AC Test Conditions

# Input Conditions

![img-34.jpeg](img-34.jpeg)

# Timing Reference Levels:

3.0V for a logic "1" (RESET, LDI)
2.0V for a logic "1" (ADM, DA7-DA0)
0.8V for a logic "0"

![img-35.jpeg](img-35.jpeg)

# Output Conditions

# Timing Reference Levels:

2.4V for a logic "1"
0.4V for a logic "0"

# Output Load Circuit:

RL = 4kΩ

CL = 50pF

(including scope and jig capacitances)

*with external 5kΩ pull-up resistor at DO2-DO0 for tDD

FUJITSU

4-95

4

MB88303

Figure 19. RC—Network Oscillator Circuit

![img-36.jpeg](img-36.jpeg)

Note: The clock frequency (fc) has wide variation from device to device. The clock frequency also considerably depends on the ambient temperature and supply voltage.

Therefore, to limit the clock frequency within the specified range, it is required to adjust it with the external resistor in advance.

I/O Circuit Configuration

|  Pin | Type | Circuit Diagram | Characteristics  |
| --- | --- | --- | --- |
|  RESET LDI ADM DA0-DA7 HSYNC VSYNC | Input | APPROX. 500KΩ | **Pull Up Resistor:** I_{IL} ≤ 60μA at V_{CC} = 5.5V, V_{IL} = 0.4V  |
|  DO0-DO2 | Output |  | **High-Voltage Open Drain:** I_{IL} ≤ 0.4V at V_{CC} = 4.5V, V_{OL} = 1.8mA,* I_{leak} ≤ 50μA at V_{CC} = 5.5V, V_{OH} = 13.2V, OFF state,* *with external 5kΩ pull up resistor  |
|  VOW VOB | Output |  | **Pull Up Resistor:** V_{OH} ≥ 2.4V at V_{CC} = 4.5V, I_{OH} = -200μA V_{OL} ≤ 0.4V at V_{CC} = 4.5V, I_{OL} = 1.8mA  |

4-96

MB88303

# Package Dimensions

Dimensions in inches

![img-37.jpeg](img-37.jpeg)

![img-38.jpeg](img-38.jpeg)

(millimeters)

# 22-Lead Plastic

Dual In-Line Package

DIP-22P-M02

![img-39.jpeg](img-39.jpeg)

FUJITSU

4-97

4