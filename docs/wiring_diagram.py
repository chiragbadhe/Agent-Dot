import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle, Circle

fig, ax = plt.subplots(figsize=(16, 10.5))
ax.set_xlim(0, 160); ax.set_ylim(0, 105); ax.axis('off')
RED, BLK, ORG, GRN, GRY = '#d62728', '#222222', '#ff8c00', '#2ca02c', '#777777'

def comp(x, y, w, h, title, sub, fc):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.4,rounding_size=1.5', fc=fc, ec='#333', lw=1.5))
    ax.text(x + w / 2, y + h - 3, title, ha='center', va='top', fontsize=12, weight='bold')
    ax.text(x + w / 2, y + h - 7.2, sub, ha='center', va='top', fontsize=8.5, color='#444')

def pin(x, y, label, side='r'):
    ax.add_patch(Circle((x, y), 0.9, fc='#ffd700', ec='#333', lw=1, zorder=5))
    ax.text(x + (-2 if side == 'r' else 2), y, label, ha='right' if side == 'r' else 'left', va='center', fontsize=9.5, weight='bold', zorder=6)

def wire(pts, col, lw=3.2, label=None, lp=None):
    xs, ys = zip(*pts)
    ax.plot(xs, ys, color=col, lw=lw, solid_capstyle='round', solid_joinstyle='round', zorder=3)
    if label:
        ax.text(*lp, label, fontsize=8.5, color=col, weight='bold', ha='center', va='center',
                bbox=dict(fc='white', ec='none', pad=0.6), zorder=4)

ax.text(2, 102, 'Agent Dot: wiring diagram', fontsize=18, weight='bold', color='#1b1030')
ax.text(2, 97.8, 'TP4056 USB-C charger  +  1S LiPo 502535 (400 mAh)  +  slide switch  +  ESP32-S3 / C3 SuperMini  +  WS2812B / SK6812 strip (3 LEDs)',
        fontsize=10.5, color='#444')

# battery
comp(4, 12, 26, 20, 'LiPo battery', '3.7 V, 400 mAh (502535)', '#f6e7a6')
pin(30, 26, 'B+'); pin(30, 17, 'B-')
# charger
comp(44, 8, 30, 42, 'TP4056 USB-C', 'charger + protection board', '#cfe3ff')
ax.add_patch(Rectangle((52, 7), 14, 4, fc='#bbb', ec='#333')); ax.text(59, 5, 'USB-C (charging port)', ha='center', fontsize=8.5)
pin(44, 26, 'B+', 'l'); pin(44, 17, 'B-', 'l')
pin(74, 40, 'OUT+'); pin(74, 22, 'OUT-')
# switch
comp(84, 56, 22, 16, 'Slide switch', 'ON / OFF (SPDT)', '#e6e6e6')
pin(84, 62, 'COM', 'l'); pin(106, 62, 'ON')
# ESP32-S3 / C3 SuperMini
comp(116, 18, 34, 36, 'ESP32-S3 / C3 SuperMini', 'USB-C only for programming', '#d6f5d6')
pin(116, 44, '5V', 'l'); pin(116, 26, 'GND', 'l'); pin(150, 40, 'GPIO10'); pin(150, 30, '3V3')
ax.text(140, 30, '(not used)', fontsize=7.5, color=GRY, ha='right', va='center')
# LED strip
comp(112, 74, 44, 18, 'LED strip: WS2812B / SK6812', '3 LEDs, wires soldered at the strip END', '#ead6ff')
for i, x in enumerate((122, 133, 144)):
    ax.add_patch(Rectangle((x - 2.5, 76.5), 5, 5, fc='#fff', ec='#7b3fe4', lw=1.5)); ax.text(x, 79, 'LED', ha='center', va='center', fontsize=6)
pin(112, 90, '5V / VDD', 'l'); pin(112, 84, 'DIN', 'l'); pin(112, 78, 'GND', 'l')

# wires
wire([(30, 26), (44, 26)], RED, label='red', lp=(37, 28.3))
wire([(30, 17), (44, 17)], BLK, label='black', lp=(37, 14.8))
wire([(74, 40), (80, 40), (80, 62), (84, 62)], RED, label='BAT+ (OUT+)', lp=(80, 50))
wire([(106, 62), (110, 62), (110, 44), (116, 44)], ORG, label='switched +', lp=(101, 48))
wire([(110, 62), (110, 90), (112, 90)], ORG)
ax.add_patch(Circle((110, 62), 0.9, fc=ORG, ec=ORG, zorder=5))
# GND bus
wire([(74, 22), (90, 22), (90, 26), (116, 26)], BLK, label='GND (common)', lp=(100, 23.5))
wire([(90, 26), (90, 52), (108, 52), (108, 78), (112, 78)], BLK)
ax.add_patch(Circle((90, 26), 0.9, fc=BLK, ec=BLK, zorder=5))
# data with resistor
wire([(150, 40), (156, 40), (156, 68), (104, 68), (104, 84), (106, 84)], GRN)
ax.add_patch(Rectangle((106, 83), 4.4, 2, fc='#f2d0a0', ec='#333', zorder=6)); wire([(110.4, 84), (112, 84)], GRN)
ax.text(108.2, 86.6, '330 Ω', ha='center', fontsize=8.5, weight='bold')
ax.text(130, 69.8, 'DATA (green): GPIO10 → 330 Ω → DIN', fontsize=8.5, color=GRN, weight='bold', ha='center')
# capacitor across strip power
ax.add_patch(Rectangle((99.3, 79), 2.4, 4, fc='#9ecae1', ec='#333', zorder=6))
wire([(100.5, 83), (100.5, 90), (110, 90)], ORG, lw=1.6); wire([(100.5, 79), (100.5, 76), (108, 76), (108, 78)], BLK, lw=1.6)
ax.text(96.5, 81, '100–470 µF\n(optional)', ha='right', va='center', fontsize=7.5)

# notes
notes = [
 ('1', 'TP4056 charge current: most boards are set to 1 A (1.2 kΩ "R3", marked 122). For a 400 mAh cell, replace it with 3 kΩ (≈400 mA) or 4 kΩ (≈300 mA).'),
 ('2', 'Use the TP4056 OUT+ / OUT- pads for the load (they go through the protection chip). Battery only on B+ / B-.'),
 ('3', 'The switch cuts only the load, so the battery still charges through the TP4056 USB-C when the switch is OFF.'),
 ('4', 'SuperMini runs from the battery on its 5V pin (its on-board 3.3 V regulator does the rest). Program it over its own USB-C with the switch OFF.'),
 ('5', 'LED strip VDD comes from the switched battery line (3.7–4.2 V), not from the 3V3 pin. Cap brightness at ~25% in code.'),
 ('6', 'Data pin: GPIO10 (set LED_PIN). ESP32-C3: avoid GPIO2, 8, 9 and 12-17. ESP32-S3: avoid GPIO0, 3, 45, 46.'),
]
y = 1.5
for n, t in reversed(notes):
    pass
ax.text(2, -3, '', fontsize=1)
fig.text(0.02, 0.005, '\n'.join('%s.  %s' % nt for nt in notes), fontsize=9.2, va='bottom', color='#222', linespacing=1.55)
plt.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.17)
legend = [('red', RED, 'battery +'), ('orange', ORG, 'switched +'), ('black', BLK, 'GND'), ('green', GRN, 'LED data')]
for i, (n, c, d) in enumerate(legend):
    ax.plot([4 + i * 26, 10 + i * 26], [92, 92], color=c, lw=4); ax.text(11.5 + i * 26, 92, d, va='center', fontsize=9.5)
fig.savefig('docs/images/wiring_diagram.png', dpi=160)
fig.savefig('docs/images/wiring_diagram.pdf')
