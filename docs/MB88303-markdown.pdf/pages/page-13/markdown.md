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