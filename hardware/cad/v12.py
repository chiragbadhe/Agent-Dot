# Agent Dot v12 - the one-piece variant (recommended).
# Overrides applied on top of the defaults in agent_dot.FCMacro. Every v12 script loads this file.
VOVR = dict(
    LED_LAYOUT='single',   # one RGB pixel lying flat at the back of the LED box
    C5_H=6.0,              # LED box height above the lid pad (mm)
    C5_ON_PLATE=True,      # LED box floor is the clamp plate
    TOP_T=1.6,             # clamp plate thickness
    C60_L=32.0, CLAMP_W=32.0,   # LED box / clamp width = controller box width
    FINGER_W=3.0,          # front clamp fingers
    C60_WIN_X=11.0,        # light window half-width
    LS_W=10.0,             # strip width the pixel is cut from
    ONE_PIECE=True,        # LED unit + controller box = ONE print
    BOARD='supermini',     # ESP32-S3/C3 SuperMini + TP4056 USB-C charger
)
VTAG = 'v12_onepiece'
