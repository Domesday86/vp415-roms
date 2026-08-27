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