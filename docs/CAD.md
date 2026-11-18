# CAD

All the printed parts come from one parametric **FreeCAD** macro, `hardware/cad/agent_dot.FCMacro`, with the v12 settings in `hardware/cad/v12.py`. Scripts around it check the design, export the print files, write the Bambu plates and render the drawings. Nothing is modelled by hand, so changing a number and re-running the scripts gives you a new, checked set of files.

You need **FreeCAD 0.21 or 1.x**. The scripts run headless with `freecadcmd`; on macOS that is `/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd`. The 3MF and drawing scripts also need Python 3 with `numpy` and `matplotlib`.

## Files (`hardware/cad/`)

| File | What it does |
|---|---|
| `agent_dot.FCMacro` | the model: parameters `P`, geometry functions, `build(P)` |
| `v12.py` | the v12 settings (`VOVR`), loaded by every script below |
| `validate_v12.py` | checks the design; writes `out/validation_report_v12_onepiece.txt` |
| `export_v12.py` | print-oriented STL and STEP files in `out/v12_onepiece/` |
| `make_3mf_v12.py` | Bambu A1 plates from those STLs (plain Python, no FreeCAD) |
| `make_3mf.py` | 3MF helpers used by `make_3mf_v12.py` |
| `render_v12.py` | drawings in `out/views_v12_onepiece/` plus the PDF |

## Rebuilding the print files

```bash
cd hardware/cad
FC=freecadcmd        # macOS: FC=/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd

$FC -c "exec(open('validate_v12.py').read())"   # 1. check  -> must say ALL CHECKS PASSED
$FC -c "exec(open('export_v12.py').read())"     # 2. STL + STEP
python3 make_3mf_v12.py                        # 3. Bambu plates
$FC -c "exec(open('render_v12.py').read())"     # 4. drawings (optional)
```

Everything goes to `hardware/cad/out/`, which git ignores. To publish, copy the results into `hardware/print/`, `hardware/step/`, `hardware/drawings/` and `hardware/validation/`.

### For your laptop

Measure your lid thickness at the top edge, then add it to `v12.py`:

```python
VOVR = dict(..., LAPTOP_T=4.6)
```

Then run the four steps. The clamp gap is always `LAPTOP_T − SQUEEZE` between the TPU pads.

## How the macro is organised

1. **`P`, the parameters.** The groups are listed below.
2. **Helpers.** `box`, `rprism` (a rounded prism), `cyl`, `fuse`, `cut`, `fillet`, `text_solid` and `to_bed` (rotates a part into its print orientation and drops it onto z = 0).
3. **Layout functions** turn parameters into named coordinates (`layout`, `c5_layout`, `layout_sm` for the v12 controller box). Every other function reads positions from these, so nothing is computed twice.
4. **Part builders**: the LED box with the clamp, `make_box_sm` / `make_cover_sm` (the v12 box and cover), `make_end_plug`, `make_pads`, and `make_components*` (models of the electronics, used only for the fit checks and the drawings).
5. **`build(p)`** returns `(L, parts, pads, comps)`. With `BOARD='supermini'` it calls `build_sm`, which joins the LED box, clamp and controller box into one `Body`.

The macro still contains the code paths of the earlier design iterations (they share most functions). `v12.py` selects the current design; the other settings aren't used or published any more.

Coordinates are in mm:

- **X** runs along the lid edge (+X is the user's right).
- **Y** is depth. Y = 0 is the screen glass, −Y points towards the user, and the lid fills Y = 0 … `LAPTOP_T`.
- **Z** is up, with Z = 0 at the lid's top edge.

## Parameters used by v12

Values marked **MEASURE** in the macro are nominal: check them against your parts.

| Group | Parameters | Notes |
|---|---|---|
| Laptop and clamp | `LAPTOP_T`, `SQUEEZE`, `PAD_T`, `TOP_T`, `CLAMP_W`, `FINGER_W`, `LIP_H`, `CAM_GAP` | `CAM_GAP` is the webcam area the clamp must stay clear of |
| LED box | `LED_LAYOUT='single'`, `C5_H`, `C5_ON_PLATE`, `C60_L`, `C60_WIN_X` | one pixel at the back of a 6 mm box |
| Pixel | `PX_W`, `PX_L`, `PX_T`, `PX_MIX`, `LS_W` | `PX_MIX` is the gap between the pixel and the diffuser that blends the light |
| Design switches | `ONE_PIECE=True`, `BOARD='supermini'` | one-piece body, SuperMini + TP4056 |
| Boards | `SM_L/W/PCB`, `TP_L/W/PCB`, `BRD_USB_H`, `BRD_STANDOFF` | `TP_L` sets the longest TP4056 that fits (28 mm) |
| Battery | `BAY_T`, `BAY_W`, `BAY_L`, `BOX_DEPTH`, `TOP_BAND_SM` | the bay takes cells up to 6.0 × 25.5 × 36 mm |
| Switch | `SW2_L/W/H`, `SW2_LEVER`, `SW2_TRAVEL` | MSK-12C02 |
| Cover | `SLIDE`, `LEDGE_H`, `COL_R`, screw sizes | drops 1.6 mm low, slides up under the ledge |
| Branding | `BRAND_LINES` | optional text engraved on the cover (empty = plain) |

## What the validator checks

`validate_v12.py` builds the model and checks:

1. **Parts.** Every part is one valid solid.
2. **Interference.** No two parts overlap, electronics included. The only expected overlaps are screw threads and the TPU pad pre-load.
3. **Electronics.** The battery fits its bay at the maximum size; each board fits its slot and drops in from the back; a real USB-C plug reaches each port; the switch sits in its pocket, moves its full travel and can be reached from outside; the screws clear everything.
4. **LED box.** The box is the right height; the pixel and the diffuser slide in through the end; the diffuser covers the window; the wire hole and the wire band are open.
5. **Cover.** It drops in and slides up, hooks at the top, can't slide sideways, and has at least 3 mm of screw thread.
6. **Laptop.** The pad-to-pad gap equals `LAPTOP_T − SQUEEZE`, and the webcam area is clear.
7. **Printability.** In each part's print orientation, no downward-facing surface spans more than a set bridge length, so no supports are needed.

Every check must pass before print files are published. The current report is `hardware/validation/validation_report_v12_onepiece.txt`.
