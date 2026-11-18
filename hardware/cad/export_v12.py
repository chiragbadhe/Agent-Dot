# Export the v12 one-piece print set (STL in print orientation + STEP)
#   cd hardware/cad && freecadcmd -c "exec(open('export_v12.py').read())"
import os, shutil
EXPORT_DIR = None
exec(open('agent_dot.FCMacro').read())
import MeshPart, Import
if not globals().get('VOVR'):
    exec(open('v12.py').read())
P.update(VOVR)
ROOT = 'out/' + VTAG
shutil.rmtree(ROOT, ignore_errors=True)
for d in ('STL', 'STEP'):
    os.makedirs(os.path.join(ROOT, d))
def stl(shape, path):
    MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.02, AngularDeflection=0.2, Relative=False).write(path)
L, parts, pads, comps = build(P)
ORI = {'Body': (V(1, 0, 0), 180), 'Enclosure_Cover': (V(1, 0, 0), -90), 'LED_End_Plug': (V(1, 0, 0), 90)}
for n, s in parts.items():
    stl(to_bed(s, ORI[n]), os.path.join(ROOT, 'STL', n + '.stl'))
    s.exportStep(os.path.join(ROOT, 'STEP', n + '.step'))
for n, s in pads.items():
    stl(to_bed(s, PAD_ORIENT[n]), os.path.join(ROOT, 'STL', 'TPU_' + n + '.stl'))
asm = Part.makeCompound(list(parts.values()) + list(pads.values()) + list(comps.values()))
asm.exportStep(os.path.join(ROOT, 'STEP', 'AgentDot_v12_assembly.step'))
print('EXPORT OK', sorted(os.listdir(os.path.join(ROOT, 'STL'))))
