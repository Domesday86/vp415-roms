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