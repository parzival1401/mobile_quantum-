"""All game constants — never hardcode these in logic files."""

# ── Screen ────────────────────────────────────────────────────────────────────
SW           = 800
SH           = 680
GAME_H       = 600
HUD_H        = 80
FPS          = 60
WINDOW_TITLE = "Quantum Maze"

# ── Grid ──────────────────────────────────────────────────────────────────────
ROWS   = 17
COLS   = 18
CELL   = 32
MAZE_W = COLS * CELL                     # 576
MAZE_H = ROWS * CELL                     # 544
MAZE_X0 = (SW - MAZE_W) // 2            # 112  (centred in 800-wide window)
MAZE_Y0 = (GAME_H - MAZE_H) // 2        # 28   (centred in 600-tall game area)

START_CELL = (0, 0)
EXIT_CELL  = (ROWS - 1, COLS - 1)

# ── Wall bitmasks ─────────────────────────────────────────────────────────────
N = 1
S = 2
E = 4
W = 8

# ── Colours ───────────────────────────────────────────────────────────────────
BG               = (13,  13,  26)
WALL_C           = (42,  42,  74)
FLOOR_C          = (20,  20,  40)
PLAYER_C         = (0,  229, 255)
PLAYER_CENTER_C  = (200, 240, 255)
EXIT_C           = (139,  92, 246)
RAY_C            = (255, 248, 220)
RAY_GLOW_C       = (200, 180, 100)
FOG_C            = (0,    0,   0)
FOG_ALPHA        = 210
HUD_BG           = (8,    8,  20)
SLIDER_TRACK_C   = (30,  30,  55)
SLIDER_HANDLE_C  = (0,  229, 255)
SLIDER_LABEL_C   = (120, 120, 180)
BUTTON_BG        = (20,  20,  50)
BUTTON_FG        = (0,  229, 255)
BUTTON_TEXT_C    = (200, 240, 255)
TEXT_C           = (180, 180, 210)
WIN_TEXT_C       = (0,  229, 255)
FLASH_C          = (255, 255, 255)
PARTICLE_C_START = (0,  229, 255)
PARTICLE_C_END   = (139,  92, 246)

# ── Player ────────────────────────────────────────────────────────────────────
PLAYER_RADIUS    = int(CELL * 0.30)     # ≈ 9 px
PLAYER_MOVE_TIME = 0.10                 # seconds, cell-to-cell slide
JUMP_DURATION    = 0.25                 # seconds, quantum jump tween
JUMP_COOLDOWN    = 1.00                 # seconds after each jump
AMBIENT_RADIUS   = int(CELL * 1.5)     # 48 px fog-of-war circle

# ── Ray ───────────────────────────────────────────────────────────────────────
RAY_MAX_DIST = CELL * 14               # max ray length in pixels
RAY_STEP     = 4                       # pixels per ray step

# ── Exit portal ───────────────────────────────────────────────────────────────
EXIT_BASE_RADIUS = int(CELL * 0.38)
EXIT_PULSE_RANGE = 3
EXIT_PULSE_FREQ  = 1.5

# ── Effects ───────────────────────────────────────────────────────────────────
FLASH_DURATION    = 0.20
SCANLINE_DURATION = 0.133
N_PARTICLES       = 12
PARTICLE_LIFETIME = 0.40
PARTICLE_SPEED_MIN = 40
PARTICLE_SPEED_MAX = 120
PARTICLE_RADIUS   = 3

# ── Scoring ───────────────────────────────────────────────────────────────────
COLLAPSE_PENALTY = 5.0

# ── Seeds ─────────────────────────────────────────────────────────────────────
DEFAULT_SEED = 42
