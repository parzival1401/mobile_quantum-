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

Controls
--------
  On-screen D-pad buttons  — move the player
  RESET button             — new maze
"""

import sys
import random
import numpy as np

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QFrame, QGridLayout,
)
from PyQt6.QtCore import Qt, QTimer, QRect, QSize
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QFont,
    QKeyEvent, QBrush,
)

# ─────────────────────────────────────────────────────────────────────────────
# Palette — classic green-phosphor terminal
# ─────────────────────────────────────────────────────────────────────────────
BG_COLOR      = QColor(  8,  12,   8)
GRID_COLOR    = QColor( 20,  35,  20)
WALL_COLOR    = QColor( 30, 180,  50)
PLAYER_COLOR  = QColor( 80, 255, 100)
GOAL_COLOR    = QColor(255, 210,   0)
VISITED_COLOR = QColor( 18,  50,  22)
TEXT_COLOR    = QColor( 60, 220,  80)
DIM_TEXT      = QColor( 30,  80,  40)
ACCENT_COLOR  = QColor( 40, 220,  60)

# ─────────────────────────────────────────────────────────────────────────────
# Maze dimensions  (smaller than before)
# ─────────────────────────────────────────────────────────────────────────────
COLS, ROWS = 13, 11   # odd numbers required by recursive-backtracker
CELL_PX    = 24       # pixels per cell


# ─────────────────────────────────────────────────────────────────────────────
# Maze generator
# ─────────────────────────────────────────────────────────────────────────────

def generate_maze(cols: int, rows: int) -> np.ndarray:
    grid_h = 2 * rows + 1
    grid_w = 2 * cols + 1
    maze   = np.ones((grid_h, grid_w), dtype=bool)
    visited = np.zeros((rows, cols), dtype=bool)

    def cell_to_grid(r, c):
        return 2 * r + 1, 2 * c + 1

    def carve(r, c):
        visited[r, c] = True
        gr, gc = cell_to_grid(r, c)
        maze[gr, gc] = False
        dirs = [(0, 1), (0, -1), (1, 0), (-1, 0)]
        random.shuffle(dirs)
        for dr, dc in dirs:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and not visited[nr, nc]:
                maze[gr + dr, gc + dc] = False
                carve(nr, nc)

    old = sys.getrecursionlimit()
    sys.setrecursionlimit(max(old, rows * cols * 4))
    carve(0, 0)
    sys.setrecursionlimit(old)
    return maze


# ─────────────────────────────────────────────────────────────────────────────
# Maze Widget
# ─────────────────────────────────────────────────────────────────────────────

class MazeWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._init_maze()

        self.blink_on = True
        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._blink)
        self._blink_timer.start(500)

        self._rain_cols = [random.randint(0, COLS * 2) for _ in range(8)]
        self._rain_rows = [random.uniform(0, ROWS * 2) for _ in range(8)]
        self._rain_timer = QTimer(self)
        self._rain_timer.timeout.connect(self._tick_rain)
        self._rain_timer.start(150)

    def _init_maze(self):
        self.maze = generate_maze(COLS, ROWS)
        self.grid_h, self.grid_w = self.maze.shape
        self.player    = [1, 1]
        self.goal      = [self.grid_h - 2, self.grid_w - 2]
        self.visited   = {(1, 1)}
        self.move_count = 0
        self.won        = False
        self.bit_log: list[str] = []
        w = self.grid_w * CELL_PX
        h = self.grid_h * CELL_PX
        self.setFixedSize(w, h)

    def reset(self):
        self._init_maze()
        self.update()

    def _blink(self):
        self.blink_on = not self.blink_on
        self.update()

    def _tick_rain(self):
        for i in range(len(self._rain_rows)):
            self._rain_rows[i] += 0.6
            if self._rain_rows[i] > self.grid_h * 2:
                self._rain_rows[i] = 0
                self._rain_cols[i] = random.randint(0, self.grid_w * 2)
        self.update()

    # ── movement ───────────────────────────────────────────────────────────

    def move(self, dr: int, dc: int, bit_label: str):
        if self.won:
            return
        nr, nc = self.player[0] + dr, self.player[1] + dc
        if (0 <= nr < self.grid_h and 0 <= nc < self.grid_w
                and not self.maze[nr, nc]):
            self.player = [nr, nc]
            self.visited.add((nr, nc))
            self.move_count += 1
            self.bit_log.append(bit_label)
            if len(self.bit_log) > 32:
                self.bit_log.pop(0)
            if hasattr(self.parent(), "update_info"):
                self.parent().update_info(self.move_count, self.bit_log)
            if self.player == self.goal:
                self.won = True
        self.update()

    def keyPressEvent(self, event: QKeyEvent):
        if self.won:
            if event.key() in (Qt.Key.Key_R, Qt.Key.Key_Return, Qt.Key.Key_Space):
                self.reset()
            return
        key_map = {
            Qt.Key.Key_Up:    (-1,  0, "↑0"),
            Qt.Key.Key_W:     (-1,  0, "↑0"),
            Qt.Key.Key_Down:  ( 1,  0, "↓1"),
            Qt.Key.Key_S:     ( 1,  0, "↓1"),
            Qt.Key.Key_Left:  ( 0, -1, "←0"),
            Qt.Key.Key_A:     ( 0, -1, "←0"),
            Qt.Key.Key_Right: ( 0,  1, "→1"),
            Qt.Key.Key_D:     ( 0,  1, "→1"),
        }
        if event.key() == Qt.Key.Key_R:
            self.reset()
        elif event.key() in key_map:
            self.move(*key_map[event.key()])

    # ── painting ───────────────────────────────────────────────────────────

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        p.fillRect(self.rect(), BG_COLOR)
        self._draw_rain(p)
        self._draw_visited(p)
        self._draw_walls(p)
        self._draw_goal(p)
        self._draw_player(p)
        if self.won:
            self._draw_win(p)
        p.end()

    def _cell_rect(self, r, c):
        return QRect(c * CELL_PX, r * CELL_PX, CELL_PX, CELL_PX)

    def _draw_rain(self, p):
        p.setFont(QFont("Courier", 6))
        p.setPen(QColor(15, 40, 15))
        for i, (rc, rr) in enumerate(zip(self._rain_cols, self._rain_rows)):
            p.drawText(int(rc * (CELL_PX // 2)), int(rr * (CELL_PX // 2)), "01"[i % 2])

    def _draw_visited(self, p):
        for (r, c) in self.visited:
            p.fillRect(self._cell_rect(r, c), VISITED_COLOR)

    def _draw_walls(self, p):
        for r in range(self.grid_h):
            for c in range(self.grid_w):
                if self.maze[r, c]:
                    p.fillRect(self._cell_rect(r, c), WALL_COLOR)
        p.setPen(QPen(GRID_COLOR, 1))
        for r in range(0, self.grid_h * CELL_PX, CELL_PX):
            p.drawLine(0, r, self.grid_w * CELL_PX, r)
        for c in range(0, self.grid_w * CELL_PX, CELL_PX):
            p.drawLine(c, 0, c, self.grid_h * CELL_PX)

    def _draw_goal(self, p):
        gr, gc = self.goal
        rect = self._cell_rect(gr, gc)
        p.fillRect(rect, GOAL_COLOR if self.blink_on else QColor(180, 140, 0))
        p.setPen(QPen(QColor(255, 255, 200), 1))
        p.setFont(QFont("Courier", 7, QFont.Weight.Bold))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "1")

    def _draw_player(self, p):
        pr, pc = self.player
        rect  = self._cell_rect(pr, pc)
        inset = rect.adjusted(4, 4, -4, -4)
        color = PLAYER_COLOR if self.blink_on else QColor(40, 160, 60)
        p.setBrush(QBrush(color))
        p.setPen(QPen(QColor(200, 255, 200), 1))
        p.drawRoundedRect(inset, 3, 3)
        p.setPen(QPen(BG_COLOR))
        p.setFont(QFont("Courier", 7, QFont.Weight.Bold))
        p.drawText(inset, Qt.AlignmentFlag.AlignCenter, "0")

    def _draw_win(self, p):
        p.fillRect(self.rect(), QColor(0, 0, 0, 180))
        p.setPen(QPen(GOAL_COLOR))
        p.setFont(QFont("Courier", 13, QFont.Weight.Bold))
        p.drawText(
            self.rect(), Qt.AlignmentFlag.AlignCenter,
            f"SOLVED!\n{self.move_count} STEPS",
        )


# ─────────────────────────────────────────────────────────────────────────────
# D-pad button panel
# ─────────────────────────────────────────────────────────────────────────────

BTN_STYLE = """
    QPushButton {
        background-color: #0a1a0a;
        color: #28c840;
        border: 2px solid #1e6432;
        border-radius: 6px;
        font-family: Courier;
        font-size: 18px;
        font-weight: bold;
    }
    QPushButton:pressed {
        background-color: #1e6432;
        color: #80ff80;
    }
"""

RESET_STYLE = """
    QPushButton {
        background-color: #0a1a0a;
        color: #1e9932;
        border: 2px solid #1e6432;
        border-radius: 6px;
        font-family: Courier;
        font-size: 10px;
        font-weight: bold;
        letter-spacing: 2px;
    }
    QPushButton:pressed {
        background-color: #1e6432;
        color: #80ff80;
    }
"""


class DPad(QWidget):
    """D-pad: up/down/left/right buttons + reset."""

    def __init__(self, maze: MazeWidget, parent=None):
        super().__init__(parent)
        self.maze = maze
        self.setStyleSheet("background-color: #080c08;")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 6, 8, 6)
        outer.setSpacing(6)

        # D-pad grid  (3×3, center empty)
        grid = QGridLayout()
        grid.setSpacing(4)

        def btn(label, dr, dc, bit):
            b = QPushButton(label)
            b.setFixedSize(QSize(48, 48))
            b.setStyleSheet(BTN_STYLE)
            b.clicked.connect(lambda: maze.move(dr, dc, bit))
            return b

        grid.addWidget(btn("↑", -1,  0, "↑0"), 0, 1)
        grid.addWidget(btn("←",  0, -1, "←0"), 1, 0)
        grid.addWidget(btn("↓",  1,  0, "↓1"), 2, 1)
        grid.addWidget(btn("→",  0,  1, "→1"), 1, 2)

        outer.addLayout(grid)

        # Reset button
        reset_btn = QPushButton("RESET")
        reset_btn.setFixedHeight(34)
        reset_btn.setStyleSheet(RESET_STYLE)
        reset_btn.clicked.connect(maze.reset)
        outer.addWidget(reset_btn)


# ─────────────────────────────────────────────────────────────────────────────
# Info Panel
# ─────────────────────────────────────────────────────────────────────────────

class InfoPanel(QFrame):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "background-color: #080c08; border-left: 2px solid #1e6432;"
        )
        self.setFixedWidth(210)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 14, 12, 12)
        layout.setSpacing(8)

        title = QLabel("CLASSICAL\nCOMPUTER")
        title.setFont(QFont("Courier", 10, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {ACCENT_COLOR.name()}; letter-spacing: 2px;")
        layout.addWidget(title)

        layout.addWidget(self._sep())
        layout.addWidget(self._section("STATE"))
        self.state_lbl = QLabel("0  (KNOWN)")
        self.state_lbl.setFont(QFont("Courier", 11, QFont.Weight.Bold))
        self.state_lbl.setStyleSheet(f"color: {PLAYER_COLOR.name()};")
        layout.addWidget(self.state_lbl)

        layout.addWidget(self._sep())
        layout.addWidget(self._section("STEPS"))
        self.moves_lbl = QLabel("0")
        self.moves_lbl.setFont(QFont("Courier", 18, QFont.Weight.Bold))
        self.moves_lbl.setStyleSheet(f"color: {TEXT_COLOR.name()};")
        layout.addWidget(self.moves_lbl)

        layout.addWidget(self._sep())
        layout.addWidget(self._section("BIT LOG"))
        self.bit_lbl = QLabel("—")
        self.bit_lbl.setFont(QFont("Courier", 8))
        self.bit_lbl.setStyleSheet(f"color: {TEXT_COLOR.name()};")
        self.bit_lbl.setWordWrap(True)
        layout.addWidget(self.bit_lbl)

        layout.addWidget(self._sep())
        layout.addWidget(self._section("CONCEPT"))
        info = QLabel(
            "Classical bit:\nalways 0 OR 1.\n\n"
            "← ↑ = 0\n→ ↓ = 1\n\n"
            "One definite path.\nNo superposition."
        )
        info.setFont(QFont("Courier", 8))
        info.setStyleSheet(f"color: {DIM_TEXT.name()};")
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addStretch()

    def _sep(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #1e6432;")
        return line

    def _section(self, text):
        lbl = QLabel(text)
        lbl.setFont(QFont("Courier", 7, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {DIM_TEXT.name()}; letter-spacing: 1px;")
        return lbl

    def update_info(self, moves: int, bit_log: list):
        self.moves_lbl.setText(str(moves))
        bits    = "".join("0" if "0" in b else "1" for b in bit_log[-16:])
        grouped = " ".join(bits[i:i+4] for i in range(0, len(bits), 4))
        dirs    = "  ".join(bit_log[-6:])
        self.bit_lbl.setText(f"{grouped}\n{dirs}")


# ─────────────────────────────────────────────────────────────────────────────
# Main Window
# ─────────────────────────────────────────────────────────────────────────────

class ClassicalMazeWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Classical Maze  |  Quantum Exhibition")
        self.setStyleSheet("background-color: #080c08;")

        central = QWidget()
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Left column: top bar + maze + d-pad ──
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        top_bar = QLabel("  CLASSICAL · DETERMINISTIC · BINARY  ")
        top_bar.setFont(QFont("Courier", 7))
        top_bar.setStyleSheet(
            "color: #1e6432; background-color: #040804;"
            "padding: 4px; border-bottom: 1px solid #1e6432;"
        )
        left_layout.addWidget(top_bar)

        self.maze_widget = MazeWidget(self)
        left_layout.addWidget(self.maze_widget)

        self.dpad = DPad(self.maze_widget, self)
        left_layout.addWidget(self.dpad, alignment=Qt.AlignmentFlag.AlignCenter)

        bottom_bar = QLabel("  STATE: KNOWN · SUPERPOSITION: NONE  ")
        bottom_bar.setFont(QFont("Courier", 7))
        bottom_bar.setStyleSheet(
            "color: #1e6432; background-color: #040804;"
            "padding: 4px; border-top: 1px solid #1e6432;"
        )
        left_layout.addWidget(bottom_bar)

        root.addWidget(left)

        # ── Right column: info panel ──
        self.info_panel = InfoPanel(self)
        root.addWidget(self.info_panel)

        self.adjustSize()
        self.setFixedSize(self.sizeHint())

    def update_info(self, moves, bit_log):
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
