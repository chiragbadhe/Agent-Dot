# Bill of materials

## Electronics

| Qty | Part | Notes |
|---|---|---|
| 1 | **ESP32-S3 SuperMini** or **ESP32-C3 SuperMini** | 22.6 × 18.1 mm, USB-C. Bottom slot of the box. |
| 1 | **TP4056 USB-C charger module** with protection (pads: B+, B−, OUT+, OUT−) | **Up to 28 × 17.6 mm** – measure yours. Charges the LiPo. **Change its charge resistor**, see below. |
| 1 | **1S LiPo**, 3.7 V, with protection | **Up to 6.0 × 25.5 × 36 mm**: 502535 (400 mAh), 403035, 602535, 402530 (300 mAh). Use foam for thinner cells. |
| 1 | **WS2812B / SK6812 strip**, 10 mm wide, 5 V | You need **one pixel** (up to 16.9 mm long, ≤ 2.1 mm tall). |
| 1 | **MSK-12C02** micro slide switch | 6.7 × 2.6 × 1.4 mm. Power on/off. |
| 1 | 330 Ω resistor | In series with the LED data line. |
| – | Thin silicone wire (28–30 AWG) | Three wires for the pixel, plus power. |

### TP4056 charge current (important)

Most TP4056 boards charge at **1 A** (resistor R3 = 1.2 kΩ, marked `122`). That is far too much for a 300–400 mAh cell. Replace R3 with:

| R3 | Charge current |
|---|---|
| 3 kΩ | ~400 mA (1 C) |
| 4 kΩ | ~300 mA (gentler, recommended) |

## Printed parts

| Material | Parts | File |
|---|---|---|
| PETG, **white or light** (the inside of the LED box is the reflector) | body, cover, end plug (+ a spare) | `hardware/print/3mf/6_AgentDot_v12_onepiece_PETG.3mf` |
| TPU 95A | lid pads (front ×2, top, rear, rear low) and the battery pad | `hardware/print/3mf/6b_TPU_pads_v12.3mf` |

## Hardware

| Qty | Part |
|---|---|
| 2 | **M2 × 6 mm countersunk (flat-head) screws**, self-tapping for plastic preferred. They hold the cover. Never longer than 6 mm: longer screws reach the laptop. |
| 1 | Diffuser strip, 29 × 3.4 × 1 mm (opal acrylic, frosted PET, white PETG or several layers of tracing paper) |

## Tools

Soldering iron, flush cutters, small Phillips driver, calipers, a 3D printer (files are set up for a Bambu Lab A1, 256 × 256 mm bed).
