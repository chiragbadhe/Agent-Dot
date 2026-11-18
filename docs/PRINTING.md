# Printing

The files in `hardware/print/3mf/` are laid out for a **Bambu Lab A1** and made for a **4.0 mm lid** (MacBook Pro M4 Pro). For another laptop, measure the lid at its top edge and rebuild with `LAPTOP_T` ([CAD.md](CAD.md#rebuilding-the-print-files)).

Bambu Studio will say *"The 3mf is not from Bambu Lab, load geometry data only"*. That is normal. Then choose your printer, filament and the settings below.

| Plate | Material | Parts |
|---|---|---|
| `6_AgentDot_v12_onepiece_PETG.3mf` | PETG, **white or light colour** | body, cover, 2 end plugs (one spare) |
| `6b_TPU_pads_v12.3mf` | TPU 95A | lid pads and battery pad, 2 sets |

The same parts are in `hardware/print/stl/` as STLs, already in print orientation.

## Settings

| Part | Settings |
|---|---|
| Body, cover, end plugs (PETG) | 0.20 mm layers, 3–4 walls, 15 % infill, **supports off**, **5 mm brim** on the body and the end plugs |
| Pads (TPU 95A) | your printer's TPU defaults |

Every part prints without supports. The orientations are already set:

- **Body**: stands on the top of its LED box, with the controller box pointing up. It is tall and narrow, hence the brim.
- **Cover**: lies on its back.
- **End plugs**: stand on end.

Print the body in **white or a light colour**: the inside of the LED box reflects the pixel's light onto the diffuser. A dark body gives a dimmer, patchier glow.

## After printing

1. Clear any stringing from the two USB-C openings, the switch slot and the wire hole.
2. Test-fit a USB-C cable in both openings.
3. Check the cover drops in 1.6 mm low and slides up under the top ledge.

Assembly: [hardware/README.md](../hardware/README.md#assembly) · full walkthrough: [BUILD_GUIDE.md](BUILD_GUIDE.md).
