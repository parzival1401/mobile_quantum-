"""
classical_maze.py — Classical Computer Maze
============================================

Part of the Quantum Exhibition: Classical vs Quantum Computing

Concept
-------
A classical computer is deterministic and binary.  At every moment it must
choose between exactly TWO states: 0 or 1.  This maze embodies that idea:

  • Every move is a binary decision  — Left/Right  OR  Up/Down.
  • The path is always deterministic — one state at a time, no uncertainty.
  • The computer knows exactly where it is and must solve the maze step-by-step.

Contrast this with the Quantum exhibit next to it, where the "player" can be
in a superposition of ALL paths simultaneously until measured.

Controls
--------
  Arrow keys / WASD  — move the player  (one direction at a time)
  R                  — reset / new maze
  ESC                — quit
"""

import sys
import random
import numpy as np

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QFrame,
)
from PyQt6.QtCore import Qt, QTimer, QRect, QPoint
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QFont, QFontDatabase,
    QKeyEvent, QBrush, QPainterPath,
)

# ─────────────────────────────────────────────────────────────────────────────
# Palette — classic green-phosphor terminal
# ─────────────────────────────────────────────────────────────────────────────
BG_COLOR        = QColor(  8,  12,   8)   # near-black
GRID_COLOR      = QColor( 20,  35,  20)   # very dark green grid
WALL_COLOR      = QColor( 30, 180,  50)   # phosphor green walls
PATH_COLOR      = QColor( 15,  60,  20)   # dim trail
PLAYER_COLOR    = QColor( 80, 255, 100)   # bright green player
GOAL_COLOR      = QColor(255, 210,   0)   # gold exit
VISITED_COLOR   = QColor( 18,  50,  22)   # breadcrumb
TEXT_COLOR      = QColor( 60, 220,  80)
DIM_TEXT        = QColor( 30,  80,  40)
ACCENT_COLOR    = QColor( 40, 220,  60)

# ─────────────────────────────────────────────────────────────────────────────
# Maze dimensions
# ─────────────────────────────────────────────────────────────────────────────
COLS, ROWS  = 19, 15      # must be odd for the recursive-backtracker
CELL_PX     = 40          # pixels per maze cell


# ─────────────────────────────────────────────────────────────────────────────
# Maze generator — recursive backtracker (perfect maze, always solvable)
# ─────────────────────────────────────────────────────────────────────────────

def generate_maze(cols: int, rows: int) -> np.ndarray:
    """
    Returns a boolean grid where True = wall, False = open passage.
    Grid size is (2*rows+1) × (2*cols+1) — walls are at even indices.
    """
    grid_h = 2 * rows + 1
    grid_w = 2 * cols + 1
    maze = np.ones((grid_h, grid_w), dtype=bool)   # start all walls

    visited = np.zeros((rows, cols), dtype=bool)

    def cell_to_grid(r, c):
        return 2 * r + 1, 2 * c + 1

    def carve(r, c):
        visited[r, c] = True
        gr, gc = cell_to_grid(r, c)
        maze[gr, gc] = False                        # open the cell itself

        directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
        random.shuffle(directions)

        for dr, dc in directions:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and not visited[nr, nc]:
                # Remove the wall between (r,c) and (nr,nc)
                maze[gr + dr, gc + dc] = False
                carve(nr, nc)

    # Increase Python recursion limit for large mazes
    old_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(old_limit, rows * cols * 4))
    carve(0, 0)
    sys.setrecursionlimit(old_limit)

    return maze


# ─────────────────────────────────────────────────────────────────────────────
# Maze Widget
# ─────────────────────────────────────────────────────────────────────────────

class MazeWidget(QWidget):
    """Renders the maze and handles player movement."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._init_maze()
        self.blink_on   = True
        self.move_count = 0
        self.won        = False

        # Cursor blink
        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._blink)
        self._blink_timer.start(500)

        # Binary rain columns (decorative background)
        self._rain_cols  = [random.randint(0, COLS * 2) for _ in range(12)]
        self._rain_rows  = [random.uniform(0, ROWS * 2) for _ in range(12)]
        self._rain_timer = QTimer(self)
        self._rain_timer.timeout.connect(self._tick_rain)
        self._rain_timer.start(120)

    # ── setup ──────────────────────────────────────────────────────────────

    def _init_maze(self):
        self.maze        = generate_maze(COLS, ROWS)
        self.grid_h, self.grid_w = self.maze.shape

        # Player starts at top-left cell, goal at bottom-right
        self.player      = [1, 1]          # [grid_row, grid_col]
        self.goal        = [self.grid_h - 2, self.grid_w - 2]
        self.visited     = set()
        self.visited.add((1, 1))
        self.move_count  = 0
        self.won         = False

        # Binary path log — last 16 moves as bits
        self.bit_log: list[str] = []

        maze_px_w = self.grid_w * CELL_PX
        maze_px_h = self.grid_h * CELL_PX
        self.setMinimumSize(maze_px_w, maze_px_h)
        self.setFixedSize(maze_px_w, maze_px_h)

    def reset(self):
        self._init_maze()
        self.update()

    # ── timers ─────────────────────────────────────────────────────────────

    def _blink(self):
        self.blink_on = not self.blink_on
        self.update()

    def _tick_rain(self):
        for i in range(len(self._rain_rows)):
            self._rain_rows[i] += 0.7
            if self._rain_rows[i] > self.grid_h * 2:
                self._rain_rows[i] = 0
                self._rain_cols[i] = random.randint(0, self.grid_w * 2)
        self.update()

    # ── keyboard ───────────────────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent):
        if self.won:
            if event.key() in (Qt.Key.Key_R, Qt.Key.Key_Return, Qt.Key.Key_Space):
                self.reset()
            return

        key = event.key()

        # Binary choice pairs:
        #   Up / Down  → vertical axis   (bit 0 = up, bit 1 = down)
        #   Left / Right → horizontal    (bit 0 = left, bit 1 = right)
        move_map = {
            Qt.Key.Key_Up:    (-1,  0, "↑0"),
            Qt.Key.Key_W:     (-1,  0, "↑0"),
            Qt.Key.Key_Down:  ( 1,  0, "↓1"),
            Qt.Key.Key_S:     ( 1,  0, "↓1"),
            Qt.Key.Key_Left:  ( 0, -1, "←0"),
            Qt.Key.Key_A:     ( 0, -1, "←0"),
            Qt.Key.Key_Right: ( 0,  1, "→1"),
            Qt.Key.Key_D:     ( 0,  1, "→1"),
        }

        if key == Qt.Key.Key_R:
            self.reset()
            return

        if key not in move_map:
            return

        dr, dc, bit_label = move_map[key]
        nr, nc = self.player[0] + dr, self.player[1] + dc

        # Check bounds and wall
        if (0 <= nr < self.grid_h and 0 <= nc < self.grid_w
                and not self.maze[nr, nc]):
            self.player = [nr, nc]
            self.visited.add((nr, nc))
            self.move_count += 1
            self.bit_log.append(bit_label)
            if len(self.bit_log) > 32:
                self.bit_log.pop(0)

            # Notify parent to update info panel
            if hasattr(self.parent(), "update_info"):
                self.parent().update_info(self.move_count, self.bit_log)

            if self.player == self.goal:
                self.won = True

        self.update()

    # ── painting ───────────────────────────────────────────────────────────

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # Background
        painter.fillRect(self.rect(), BG_COLOR)

        # Binary rain (decorative, very dim)
        self._draw_rain(painter)

        # Visited trail
        self._draw_visited(painter)

        # Maze walls
        self._draw_walls(painter)

        # Goal
        self._draw_goal(painter)

        # Player
        self._draw_player(painter)

        # Win overlay
        if self.won:
            self._draw_win(painter)

        painter.end()

    def _cell_rect(self, row: int, col: int) -> QRect:
        return QRect(col * CELL_PX, row * CELL_PX, CELL_PX, CELL_PX)

    def _draw_rain(self, p: QPainter):
        font = QFont("Courier", 7)
        p.setFont(font)
        p.setPen(QColor(15, 45, 15))
        bits = "01"
        for i, (rc, rr) in enumerate(zip(self._rain_cols, self._rain_rows)):
            x = int(rc * (CELL_PX // 2))
            y = int(rr * (CELL_PX // 2))
            p.drawText(x, y, bits[i % 2])

    def _draw_visited(self, p: QPainter):
        for (r, c) in self.visited:
            rect = self._cell_rect(r, c)
            p.fillRect(rect, VISITED_COLOR)

    def _draw_walls(self, p: QPainter):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(WALL_COLOR))
        for r in range(self.grid_h):
            for c in range(self.grid_w):
                if self.maze[r, c]:
                    rect = self._cell_rect(r, c)
                    p.fillRect(rect, WALL_COLOR)

        # Subtle grid lines on open cells
        p.setPen(QPen(GRID_COLOR, 1))
        for r in range(0, self.grid_h * CELL_PX, CELL_PX):
            p.drawLine(0, r, self.grid_w * CELL_PX, r)
        for c in range(0, self.grid_w * CELL_PX, CELL_PX):
            p.drawLine(c, 0, c, self.grid_h * CELL_PX)

    def _draw_goal(self, p: QPainter):
        gr, gc = self.goal
        rect = self._cell_rect(gr, gc)
        # Pulsing gold square
        p.fillRect(rect, GOAL_COLOR if self.blink_on else QColor(180, 140, 0))
        p.setPen(QPen(QColor(255, 255, 200), 2))
        font = QFont("Courier", 8, QFont.Weight.Bold)
        p.setFont(font)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "1")

    def _draw_player(self, p: QPainter):
        pr, pc = self.player
        rect   = self._cell_rect(pr, pc)
        inset  = rect.adjusted(6, 6, -6, -6)

        color  = PLAYER_COLOR if self.blink_on else QColor(40, 160, 60)
        p.setBrush(QBrush(color))
        p.setPen(QPen(QColor(200, 255, 200), 1))
        p.drawRoundedRect(inset, 4, 4)

        # "0" label inside player (classical bit = known state)
        p.setPen(QPen(BG_COLOR))
        font = QFont("Courier", 9, QFont.Weight.Bold)
        p.setFont(font)
        p.drawText(inset, Qt.AlignmentFlag.AlignCenter, "0")

    def _draw_win(self, p: QPainter):
        # Semi-transparent overlay
        overlay = QColor(0, 0, 0, 180)
        p.fillRect(self.rect(), overlay)

        p.setPen(QPen(GOAL_COLOR))
        font = QFont("Courier", 18, QFont.Weight.Bold)
        p.setFont(font)
        p.drawText(
            self.rect(),
            Qt.AlignmentFlag.AlignCenter,
            f"SOLUTION FOUND\n{self.move_count} STEPS\n\nPRESS R TO RESET",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Info Panel  (right sidebar)
# ─────────────────────────────────────────────────────────────────────────────

class InfoPanel(QFrame):
    """Displays binary state, move counter, and an explanation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "background-color: #080c08; border-left: 2px solid #1e6432;"
        )
        self.setFixedWidth(260)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 18, 14, 14)
        layout.setSpacing(10)

        # Title
        title = QLabel("CLASSICAL COMPUTER")
        title.setFont(QFont("Courier", 11, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {ACCENT_COLOR.name()}; letter-spacing: 2px;")
        title.setWordWrap(True)
        layout.addWidget(title)

        sub = QLabel("MAZE SIMULATOR v1.0")
        sub.setFont(QFont("Courier", 8))
        sub.setStyleSheet(f"color: {DIM_TEXT.name()};")
        layout.addWidget(sub)

        layout.addWidget(self._separator())

        # State indicator
        layout.addWidget(self._section("CURRENT STATE"))
        self.state_label = QLabel("0  (KNOWN)")
        self.state_label.setFont(QFont("Courier", 13, QFont.Weight.Bold))
        self.state_label.setStyleSheet(f"color: {PLAYER_COLOR.name()};")
        layout.addWidget(self.state_label)

        layout.addWidget(self._separator())

        # Move counter
        layout.addWidget(self._section("STEPS TAKEN"))
        self.moves_label = QLabel("0")
        self.moves_label.setFont(QFont("Courier", 20, QFont.Weight.Bold))
        self.moves_label.setStyleSheet(f"color: {TEXT_COLOR.name()};")
        layout.addWidget(self.moves_label)

        layout.addWidget(self._separator())

        # Binary decision log
        layout.addWidget(self._section("BINARY DECISIONS"))
        self.bit_display = QLabel("—")
        self.bit_display.setFont(QFont("Courier", 9))
        self.bit_display.setStyleSheet(f"color: {TEXT_COLOR.name()};")
        self.bit_display.setWordWrap(True)
        layout.addWidget(self.bit_display)

        layout.addWidget(self._separator())

        # Explanation
        layout.addWidget(self._section("HOW IT WORKS"))
        explanation = QLabel(
            "A classical bit is always\n"
            "EXACTLY 0 or 1.\n\n"
            "Each move is a binary\n"
            "choice:\n"
            "  ← / ↑  =  0\n"
            "  → / ↓  =  1\n\n"
            "The computer knows its\n"
            "exact position at ALL\n"
            "times.\n\n"
            "Only ONE path exists\nat any moment."
        )
        explanation.setFont(QFont("Courier", 8))
        explanation.setStyleSheet(f"color: {DIM_TEXT.name()};")
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        layout.addStretch()

        # Controls hint
        hint = QLabel("WASD / ARROWS = move\nR = new maze")
        hint.setFont(QFont("Courier", 7))
        hint.setStyleSheet(f"color: {DIM_TEXT.name()};")
        layout.addWidget(hint)

    def _separator(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #1e6432;")
        return line

    def _section(self, text: str):
        lbl = QLabel(text)
        lbl.setFont(QFont("Courier", 7, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {DIM_TEXT.name()}; letter-spacing: 1px;")
        return lbl

    def update_info(self, moves: int, bit_log: list):
        self.moves_label.setText(str(moves))

        # Show last 16 bits grouped in 4
        bits_only = "".join("0" if "0" in b else "1" for b in bit_log[-16:])
        grouped   = " ".join(bits_only[i:i+4] for i in range(0, len(bits_only), 4))
        directions = "  ".join(bit_log[-8:])
        self.bit_display.setText(f"{grouped}\n\n{directions}")


# ─────────────────────────────────────────────────────────────────────────────
# Main Window
# ─────────────────────────────────────────────────────────────────────────────

class ClassicalMazeWindow(QMainWindow):
    """Top-level window: maze on the left, info panel on the right."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Classical Computer — Binary Maze  |  Quantum Exhibition")
        self.setStyleSheet("background-color: #080c08;")

        central = QWidget()
        self.setCentralWidget(central)

        h_layout = QHBoxLayout(central)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)

        # Left: maze + bottom label
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        # Top label bar
        top_bar = QLabel(
            "  CLASSICAL COMPUTER  ·  DETERMINISTIC  ·  ONE STATE AT A TIME  ·  BINARY"
        )
        top_bar.setFont(QFont("Courier", 8))
        top_bar.setStyleSheet(
            "color: #1e6432; background-color: #040804;"
            "padding: 5px; border-bottom: 1px solid #1e6432;"
        )
        left_layout.addWidget(top_bar)

        # Maze
        self.maze_widget = MazeWidget(self)
        left_layout.addWidget(self.maze_widget)

        # Bottom bar
        bottom_bar = QLabel(
            "  STATE: KNOWN  ·  PATH: DETERMINISTIC  ·  SUPERPOSITION: NONE"
        )
        bottom_bar.setFont(QFont("Courier", 8))
        bottom_bar.setStyleSheet(
            "color: #1e6432; background-color: #040804;"
            "padding: 5px; border-top: 1px solid #1e6432;"
        )
        left_layout.addWidget(bottom_bar)

        h_layout.addWidget(left_widget)

        # Right: info panel
        self.info_panel = InfoPanel(self)
        h_layout.addWidget(self.info_panel)

        self.adjustSize()
        self.setFixedSize(self.sizeHint())

    # Forward maze events to info panel
    def update_info(self, moves: int, bit_log: list):
        self.info_panel.update_info(moves, bit_log)

    def keyPressEvent(self, event: QKeyEvent):
        self.maze_widget.keyPressEvent(event)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Classical Maze — Quantum Exhibition")

    window = ClassicalMazeWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
