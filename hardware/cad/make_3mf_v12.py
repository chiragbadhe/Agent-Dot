# Bambu Lab A1 plates for v12 (run after export_v12.py):  cd hardware/cad && python3 make_3mf_v12.py
import os, sys
src = open('make_3mf.py').read()
exec(src[:src.index('# ----')].replace("os.makedirs(OUT, exist_ok=True)", ""))
R = 'out/v12_onepiece'
OUT = os.path.join(R, '3MF'); os.makedirs(OUT, exist_ok=True)
def one(n, label):
    v, f = read_stl(os.path.join(R, 'STL', n)); return (label, v, f)
write_3mf('6_AgentDot_v12_onepiece_PETG.3mf', [one('Body.stl', 'Body_LED_box_and_controller_box'), one('Enclosure_Cover.stl', 'Cover'),
          one('LED_End_Plug.stl', 'End_Plug_1'), one('LED_End_Plug.stl', 'End_Plug_spare')],
          'Agent Dot v12 - one-piece body + cover + end plugs (PETG, white or light colour)')
t = []
for n in ('Front_L', 'Front_R', 'Rear', 'Rear_Low', 'Top', 'Battery'):
    for c in (1, 2):
        t.append(one('TPU_Pad_%s.stl' % n, 'Pad_%s_%d' % (n, c)))
write_3mf('6b_TPU_pads_v12.3mf', t, 'Agent Dot v12 - TPU pads (one spare set)')
print(os.listdir(OUT))
