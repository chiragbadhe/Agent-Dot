# Agent Dot v12 (one-piece body, ESP32 SuperMini + TP4056, single pixel) - geometric validation
#   cd hardware/cad && freecadcmd -c "exec(open('validate_v12.py').read())"
EXPORT_DIR = None
exec(open('agent_dot.FCMacro').read())
if not globals().get('VOVR'):
    exec(open('v12.py').read())
P.update(VOVR)
p = P
L, parts, pads, comps = build(P)
C = c5_layout(p, L)
B, CV, PL = parts['Body'], parts['Enclosure_Cover'], parts['LED_End_Plug']
out = []
say = out.append
ok_all = True


def check(name, cond, detail=''):
    global ok_all
    ok_all &= bool(cond)
    say('[%s] %s %s' % ('PASS' if cond else 'FAIL', name, detail))


def path_clear(moving, fixed, moves, steps=40):
    s = moving.copy()
    for mv in moves:
        for k in range(steps):
            s.translate(V(*[c / steps for c in mv]))
            for f in fixed:
                if s.BoundBox.intersect(f.BoundBox) and s.common(f).Volume > 1e-3:
                    return False
    return True


say('AGENT DOT v12 - one-piece body + cover, ESP32 SuperMini + TP4056, one LED pixel  (lid %.1f mm)' % p['LAPTOP_T'])
say('=' * 78)
say('\n1. Parts')
for n, s in {**parts, **pads}.items():
    check('%-16s valid single solid' % n, s.isValid() and len(s.Solids) == 1, '(%.0f mm3)' % s.Volume)
check('Only two printed bodies + end plug (body = LED box + clamp + controller box)', set(parts) == {'Body', 'Enclosure_Cover', 'LED_End_Plug'})

say('\n2. Interference (all parts incl. electronics)')
allb = {**parts, **pads, **comps}
names = list(allb)
skip = {frozenset(x) for x in (('LEDs_WS2812B_2020', 'LED_PCB'), ('Switch', 'Switch_actuator'),
                                ('TP4056_PCB', 'TP4056_USB_C'), ('ESP32_SuperMini_PCB', 'ESP32_SuperMini_USB_C'))}
INTENDED = {frozenset(('Enclosure_Cover', 'Pad_Battery')): 'TPU battery pad pre-load'}
bad = []
for i in range(len(names)):
    for j in range(i + 1, len(names)):
        a, b = names[i], names[j]
        if frozenset((a, b)) in skip or not allb[a].BoundBox.intersect(allb[b].BoundBox):
            continue
        v = allb[a].common(allb[b]).Volume
        if v > 1e-3:
            why = 'screw thread engagement' if ('Screw' in a or 'Screw' in b) else INTENDED.get(frozenset((a, b)))
            say('   overlap %-22s x %-22s %.2f mm3  %s' % (a, b, v, why or '<-- UNINTENDED'))
            bad.append(why is None)
check('No unintended interference', not any(bad))

say('\n3. Electronics')
say('   box inside: %.1f W x %.1f H x %.1f D' % (L['int_x1'] - L['int_x0'], L['iz1'] - L['iz0'], L['int_y']))
check('Battery bay takes cells up to 6.0 x %.1f x %.1f mm (with 0.6 mm TPU pad)' % (p['BAY_W'] - 0.5, p['BAY_L'] - 0.5),
      comps['Battery_LiPo'].common(B).Volume < 1e-3 and comps['Battery_LiPo'].common(CV).Volume < 1e-3)
for b in ('TP4056', 'ESP32_SuperMini'):
    pcb, usb = comps[b + '_PCB'], comps[b + '_USB_C']
    check('%s board fits its slot' % b, pcb.common(B).Volume < 1e-3 and usb.common(B).Volume < 1e-3)
    check('%s drops in from the back (cover off)' % b, path_clear(pcb.fuse(usb), [B], [(0, 12, 0)]))
    zc = usb.BoundBox.Center.z; yc = usb.BoundBox.Center.y
    plug = box(L['ex0'] - 9, L['ex0'] - 2.4, yc - 1.25, yc + 1.25, zc - 4.15, zc + 4.15)   # USB-C plug shell 8.3 x 2.5
    check('%s USB-C: plug reaches the port through the left wall' % b,
          path_clear(plug, [B, CV], [(usb.BoundBox.XMin - (L['ex0'] - 2.4) + 5.5, 0, 0)]))
check('TP4056 bay takes boards up to %.0f mm long' % p['TP_L'], L['brd_x0'] + p['TP_L'] <= L['int_x1'] - 0.1)
sw, act = comps['Switch'], comps['Switch_actuator']
check('Micro switch (%.1f x %.1f x %.1f) sits in its pocket' % (p['SW2_L'], p['SW2_W'], p['SW2_H']), sw.common(B).Volume < 1e-3 and sw.common(CV).Volume < 1e-3)
for d in (-p['SW2_TRAVEL'] / 2, p['SW2_TRAVEL'] / 2):
    a2 = act.copy(); a2.translate(V(0, 0, d))
    check('Switch lever free at %+.2f mm of travel' % d, a2.common(B).Volume < 1e-3)
check('Switch lever reachable from outside', act.BoundBox.XMax > L['ex1'] - 0.7 - 0.05, '(lever tip %.2f, recess %.2f)' % (act.BoundBox.XMax, L['ex1'] - 0.7))
check('Switch held in by the cover', not path_clear(sw, [B, CV], [(0, 3, 0)], steps=15))
for n in [k for k in comps if k.startswith('Screw')]:
    g = min(comps[n].distToShape(comps[c])[0] for c in ('ESP32_SuperMini_PCB', 'TP4056_PCB', 'Battery_LiPo', 'Switch'))
    check('%s clears electronics' % n, g > 0.2, '(%.2f)' % g)

say('\n4. LED box (6 mm, one pixel at the back)')
hb = B.common(box(-40, 40, -10, 30, C['z0'], 40)).BoundBox
check('LED box height %.1f mm above the lid pad' % p['C5_H'], abs(hb.ZMax - C['z0'] - p['C5_H']) < 0.01)
px, led = comps['LED_PCB'], comps['LEDs_WS2812B_2020']
check('Pixel (%.0f x %.0f mm) lies at the back, clear of the box' % (p['PX_L'], p['PX_W']), px.common(B).Volume < 1e-3 and led.common(B).Volume < 1e-3)
check('Pixel slides in through the right end (then the end plug)', path_clear(px.fuse(led), [B], [(30, 0, 0)]))
st = comps['Diffuser_Strip']
check('Diffuser slides in through the right end', path_clear(st, [B], [(40, 0, 0)]))
check('Diffuser covers the window', st.BoundBox.ZMin <= C['z_led'] - C['win_h'] / 2 and st.BoundBox.ZMax >= C['z_led'] + C['win_h'] / 2)
say('   light: pixel %.1f mm behind the diffuser; window %.0f x %.1f mm' % (C['y_s0'] - C['y_fl1'], 2 * C['x_win'], C['win_h']))
wy0, wy1 = wire_hole_y(p, L, C)
hole = box(p['PX_L'] / 2 + 0.8, C['x_int'] - 0.8, wy0 + 0.2, wy1 - 0.2, L['iz1'] - 1.0, C['zf'] + 0.4)
check('Wire hole: pixel end -> straight down into the box', hole.common(B).Volume < 1e-3,
      '(%.1f x %.1f mm)' % (C['x_int'] - 0.6 - p['PX_L'] / 2 - 0.6, wy1 - wy0))
band = box(-12, 12, L['iy0'] + 0.3, L['ey1'] - 0.3, L['bat_z1'] + 0.1, L['iz1'] - 0.1)
check('Wire band above the battery is open (%.1f mm)' % (L['iz1'] - L['bat_z1']), band.common(B).Volume < 1e-3)

say('\n5. Cover')
others = [B] + [comps[k] for k in comps if not k.startswith('Screw')]
check('Cover fits: drop %.1f mm low, slide up' % p['SLIDE'], path_clear(CV, others, [(0, 0, -p['SLIDE'] - 0.05), (0, 15, 0)]))
check('Cover hooked at the top', not path_clear(CV, [B], [(0, 3, 0)], steps=30))
check('Cover cannot slide sideways', not path_clear(CV, [B], [(1.0, 0, 0)], steps=10))
eng = L['ey1'] - L['screw_tip']
check('Cover screws: 2 x M2x6, thread in post >= 3 mm', eng >= 3.0, '(%.1f mm)' % eng)

say('\n6. Laptop')
gap = L['y_rp0'] - p['PAD_T'] - (L['y_lip_in'] + p['PAD_T'])
check('Pad-to-pad gap = lid - squeeze', abs(gap - (p['LAPTOP_T'] - p['SQUEEZE'])) < 1e-6, '(%.2f mm)' % gap)
cam = box(-p['CAM_GAP'] / 2 + 0.05, p['CAM_GAP'] / 2 - 0.05, -10, -0.01, -15, -0.01)
check('Webcam keep-out clear', sum(s.common(cam).Volume for s in list(parts.values()) + list(pads.values())) < 1e-3)

say('\n7. Printability (no supports)')
ORI = {'Body': (V(1, 0, 0), 180), 'Enclosure_Cover': (V(1, 0, 0), -90), 'LED_End_Plug': (V(1, 0, 0), 90)}
LIM = {'Body': 13.0, 'Enclosure_Cover': 6.0, 'LED_End_Plug': 6.0}
for n, s in parts.items():
    sb = to_bed(s, ORI[n]); worst = 0
    for fc in sb.Faces:
        try:
            u, v = fc.ParameterRange[0:2], fc.ParameterRange[2:4]
            nn = fc.normalAt((u[0] + u[1]) / 2, (v[0] + v[1]) / 2)
        except Exception:
            continue
        if nn.z < -0.72 and fc.BoundBox.ZMin > 0.05:
            bx, by = fc.BoundBox.XLength, fc.BoundBox.YLength
            worst = max(worst, min(bx, by, fc.Area / max(bx, by, 1e-6)))
    bb = sb.optimalBoundingBox()
    check('%-16s no supports' % n, worst <= LIM[n], '(widest bridge %.1f mm, build %.1f x %.1f x %.1f)' % (worst, bb.XLength, bb.YLength, bb.ZLength))

say('\n8. Size')
a = B.optimalBoundingBox()
say('   one-piece body: %.1f W x %.1f H x %.1f D' % (a.XLength, a.ZLength, a.YLength))
say('   above the lid edge: %.1f mm; behind the lid: %.1f mm; box reaches %.1f mm down' % (hb.ZMax, L['ey2'] - L['y_rp0'], -L['ez0']))
say('\nOVERALL: %s' % ('ALL CHECKS PASSED' if ok_all else 'SOME CHECKS FAILED'))
os.makedirs('out', exist_ok=True)
open('out/validation_report_v12_onepiece.txt', 'w').write('\n'.join(out) + '\n')
print('\n'.join(out))
