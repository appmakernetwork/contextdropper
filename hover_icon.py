import sys
import os
import shutil  # Not used directly here, but kept for context
import collections  # Not used directly here, but kept for context
from pathlib import Path  # Not used directly here, but kept for context 
import random
import math

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QPushButton,
    QLabel,
)
from PySide6.QtGui import (
    QPainter,
    QColor,
    QPixmap,
    QGuiApplication,
    QCursor,
)
from PySide6.QtCore import (
    Qt,
    QTimer,
    Signal,
    QPoint,
    QRect,
    QPointF,
    QByteArray,
    QSize,
)

try:
    from PySide6.QtSvg import QSvgRenderer

    SVG_SUPPORT_AVAILABLE = True
except ImportError:
    QSvgRenderer = None
    SVG_SUPPORT_AVAILABLE = False 
    print(
        "WARNING: PySide6.QtSvg module not found. SVG confetti icons "
        "cannot be used. Please install it (e.g., pip install PySide6-Addons)."
    )

# -----------------------------------------------------------------------------
# Confetti particle configuration
# -----------------------------------------------------------------------------
CONFETTI_PARTICLE_COUNT = 10
CONFETTI_INITIAL_SPEED_MIN = 0.8
CONFETTI_INITIAL_SPEED_MAX = 1.5
CONFETTI_GRAVITY = -0.01
CONFETTI_DRAG = 0.985
CONFETTI_LIFE_MS_MIN = 600
CONFETTI_LIFE_MS_MAX = 1400
CONFETTI_ROTATION_SPEED_MAX = 5.0
CONFETTI_SCALE_START = 0.7
CONFETTI_SCALE_END = 1.0
CONFETTI_FADE_START_RATIO = 0.75

CONFETTI_COLORS = [
    QColor(116, 95, 211, 220),  # Medium Orchid (Purple)
    QColor(65, 105, 225, 220),  # Royal Blue (Blue)
    QColor(123, 104, 238, 220), # Medium Slate Blue (Purplish)
    QColor(211, 211, 211, 220), # Light Gray
    QColor(105, 105, 105, 220), # Dim Gray (Dark Gray)
]

PARTICLE_ICON_RENDER_SIZE = QSize(16, 16) 

SVG_ICON_DATA_TEMPLATE = """
<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 24 24\" width=\"{width}px\" height=\"{height}px\" fill=\"{color}\">
    <path d=\"M0 0h24v24H0z\" fill=\"none\"/>
    <path d=\"M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z\"/>
</svg>
"""

# These pixmaps are generated once to avoid doing SVG rendering every animation
_PRE_RENDERED_CONFETTI_PIXMAPS: list[QPixmap] = []


def _prepare_confetti_pixmaps() -> None:
    """Render small coloured clipboard icons once for reuse."""
    if not SVG_SUPPORT_AVAILABLE:
        return

    if _PRE_RENDERED_CONFETTI_PIXMAPS:
        return  # Already prepared

    for q_color in CONFETTI_COLORS: 
        color_hex = q_color.name()
        svg = SVG_ICON_DATA_TEMPLATE.format(
            width=PARTICLE_ICON_RENDER_SIZE.width(),
            height=PARTICLE_ICON_RENDER_SIZE.height(),
            color=color_hex,
        )
        ba = QByteArray(svg.encode())
        renderer = QSvgRenderer(ba)
        if not renderer.isValid():
            continue 
        px = QPixmap(PARTICLE_ICON_RENDER_SIZE)
        px.fill(Qt.transparent)
        p = QPainter(px)
        renderer.render(p)
        p.end()
        _PRE_RENDERED_CONFETTI_PIXMAPS.append(px)


class _ConfettiParticle:
    """Simple data object representing a single confetti piece."""

    def __init__(self, origin: QPointF):
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(CONFETTI_INITIAL_SPEED_MIN, CONFETTI_INITIAL_SPEED_MAX) 
        self.pos = QPointF(origin)
        self.vel = QPointF(speed * math.cos(angle), speed * math.sin(angle))
        self.rotation = random.uniform(0, 360)
        self.rotation_speed = random.uniform(-CONFETTI_ROTATION_SPEED_MAX, CONFETTI_ROTATION_SPEED_MAX)
        self.life_total = random.uniform(CONFETTI_LIFE_MS_MIN, CONFETTI_LIFE_MS_MAX)
        self.life_left = self.life_total
        self.opacity = 1.0
        self.scale = CONFETTI_SCALE_START
        self.pixmap: QPixmap | None = (
            random.choice(_PRE_RENDERED_CONFETTI_PIXMAPS) if _PRE_RENDERED_CONFETTI_PIXMAPS else None
        ) 

    def advance(self, dt_ms: int) -> bool:
        """Update particle state; return False when it expires."""
        self.life_left -= dt_ms
        if self.life_left <= 0:
            return False

        # Motion
        self.pos += self.vel 
        self.vel.setY(self.vel.y() + CONFETTI_GRAVITY)
        self.vel *= CONFETTI_DRAG

        # Rotation
        self.rotation = (self.rotation + self.rotation_speed) % 360

        # Scale & opacity
        ratio = max(0.0, self.life_left / self.life_total)
        self.scale = CONFETTI_SCALE_END + (CONFETTI_SCALE_START - CONFETTI_SCALE_END) * math.sqrt(ratio)
        self.opacity = 1.0 if ratio >= CONFETTI_FADE_START_RATIO else ratio / CONFETTI_FADE_START_RATIO 
        return True


class _ConfettiOverlay(QWidget):
    """Transient, click‑through window that renders confetti outside the hover icon."""

    def __init__(self, parent_icon: 'HoverIcon') -> None:  # type: ignore  # forward ref
        super().__init__(None)  # Top‑level window
        self._parent_icon = parent_icon
        # MODIFIED LINE: Removed Qt.WindowStaysOnTopHint
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground) 
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

        # A square area large enough for the particles to travel (~3× icon size)
        self._size = 8 * parent_icon.width()
        self.setFixedSize(self._size, self._size)

        # Position overlay so that its centre aligns with the icon centre in *global* coords
        global_center = parent_icon.mapToGlobal(parent_icon.icon_display_rect.center())
        self.move(global_center.x() - self._size // 2, global_center.y() - self._size // 2) 

        # Particle setup
        _prepare_confetti_pixmaps()
        self._particles: list[_ConfettiParticle] = []
        origin_local = QPointF(self._size / 2, self._size / 2)
        for _ in range(CONFETTI_PARTICLE_COUNT):
            self._particles.append(_ConfettiParticle(origin_local))

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._advance) 
        self._timer.start()

    # ------------------------------------------------------------------
    # Animation
    # ------------------------------------------------------------------
    def _advance(self) -> None:
        dt = self._timer.interval()
        self._particles = [p for p in self._particles if p.advance(dt)]
        if not self._particles:
            self.close()
            return
        self.update() 

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802 (Qt camelCase)
        if not self._particles:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        for particle in self._particles:
            if not particle.pixmap:
                continue 
            p.save()
            p.setOpacity(particle.opacity)
            p.translate(particle.pos)
            p.rotate(particle.rotation)
            p.scale(particle.scale, particle.scale)
            w = particle.pixmap.width()
            h = particle.pixmap.height()
            p.drawPixmap(-w // 2, -h // 2, particle.pixmap) 
            p.restore()
        p.end()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def closeEvent(self, event):  # noqa: N802
        # Let the parent know the overlay is gone so another can be spawned.
        if self._parent_icon and hasattr(self._parent_icon, "_confetti_overlay"): 
            self._parent_icon._confetti_overlay = None  # type: ignore[attr-defined]
        super().closeEvent(event)


# -----------------------------------------------------------------------------
# Hover icon widget
# -----------------------------------------------------------------------------
class HoverIcon(QWidget):
    drop_context_requested = Signal()
    maximize_requested = Signal(object)  # Emits the screen
    close_application_requested = Signal()

    DRAG_THRESHOLD = 5
    LONG_PRESS_DURATION = 300

    ICON_IMAGE_PATH = "contextdropper_transparent.png"
    ICON_DISPLAY_WIDTH = 64
    ICON_DISPLAY_HEIGHT = 64
    ICON_AREA_HEIGHT = 64

    def __init__(self): 
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowOpacity(0.8)

        # Ensure the SVG pixmaps are prepared once for the whole app
        _prepare_confetti_pixmaps()

        # ------------------------------------------------------------------
        # Icon graphic (fallback if missing)
        # ------------------------------------------------------------------
        self.icon_pixmap = QPixmap(self.ICON_IMAGE_PATH) 
        if self.icon_pixmap.isNull():
            fallback = QPixmap(self.ICON_DISPLAY_WIDTH, self.ICON_DISPLAY_HEIGHT)
            fallback.fill(Qt.transparent)
            p = QPainter(fallback)
            p.setBrush(QColor(0, 122, 204, 150))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QRect(0, 0, self.ICON_DISPLAY_WIDTH, self.ICON_DISPLAY_HEIGHT))
            p.end() 
            self.icon_pixmap = fallback

        icon_area_width = 60
        self.icon_display_rect = QRect(
            (icon_area_width - self.ICON_DISPLAY_WIDTH) // 2,
            (self.ICON_AREA_HEIGHT - self.ICON_DISPLAY_HEIGHT) // 2,
            self.ICON_DISPLAY_WIDTH,
            self.ICON_DISPLAY_HEIGHT,
        ) 

        # ------------------------------------------------------------------
        # Control buttons (hidden until hover)
        # ------------------------------------------------------------------
        button_height = 20
        buttons_y = self.ICON_AREA_HEIGHT + 5
        self.setFixedSize(icon_area_width, self.ICON_AREA_HEIGHT + 5 + button_height)

        common_style = (
            "QPushButton { background-color: rgba(100,100,100,180); " 
            "color: white; border-radius: 5px; " 
            "font-size: 12px;} "
            "QPushButton:hover { background-color: rgba(120,120,120,220);}"
        )
        btn_w = icon_area_width // 2 - 2

        self.maximize_button = QPushButton("🗖", self)
        self.maximize_button.setFixedSize(btn_w, button_height)
        self.maximize_button.move((icon_area_width // 2) - btn_w - 1, buttons_y)
        self.maximize_button.setStyleSheet(common_style)
        self.maximize_button.clicked.connect(self._emit_maximize_with_screen)
        self.maximize_button.hide()

        self.close_button = QPushButton("X", self) 
        self.close_button.setFixedSize(btn_w, button_height)
        self.close_button.move((icon_area_width // 2) + 1, buttons_y)
        self.close_button.setStyleSheet(common_style)
        self.close_button.clicked.connect(self.close_application_requested.emit)
        self.close_button.hide()

        # ------------------------------------------------------------------
        # Interaction state
        # ------------------------------------------------------------------
        self._is_dragging = False
        self._drag_start_offset = QPoint() 
        self._mouse_press_pos_local = QPoint()
        self._long_press_timer = QTimer(self)
        self._long_press_timer.setSingleShot(True)
        self._long_press_timer.setInterval(self.LONG_PRESS_DURATION)
        self._long_press_timer.timeout.connect(self._initiate_drag_from_long_press)
        self._is_potential_click = False

        # Hover show/hide buttons timers
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.timeout.connect(self._show_control_buttons)
        self._leave_timer = QTimer(self) 
        self._leave_timer.setSingleShot(True)
        self._leave_timer.timeout.connect(self._hide_control_buttons_if_needed)

        # Reference to active confetti overlay (if any)
        self._confetti_overlay: _ConfettiOverlay | None = None 

    # ------------------------------------------------------------------
    # Confetti trigger
    # ------------------------------------------------------------------
    def _start_confetti_animation(self) -> None:
        if self._confetti_overlay is not None:
            self._confetti_overlay.close()
            self._confetti_overlay = None
        self._confetti_overlay = _ConfettiOverlay(self)
        self._confetti_overlay.show()

    # ------------------------------------------------------------------
    # Painting (just the icon, confetti handled by overlay)
    # ------------------------------------------------------------------ 
    def paintEvent(self, event):  # noqa: N802 (Qt camelCase)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.drawPixmap(self.icon_display_rect, self.icon_pixmap)
        p.end()

    # ------------------------------------------------------------------
    # Drag / click handling
    # ------------------------------------------------------------------
    def _initiate_drag_from_long_press(self):
        if self._is_potential_click:
            self._is_dragging = True
            self._is_potential_click = False 

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._mouse_press_pos_local = event.position().toPoint()
            self._drag_start_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._is_dragging = False
            self._is_potential_click = True
            self._long_press_timer.start() 
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):  # noqa: N802
        if event.buttons() == Qt.LeftButton:
            if not self._is_dragging and self._is_potential_click:
                delta = (
                    event.position().toPoint() - self._mouse_press_pos_local 
                ).manhattanLength()
                if delta > self.DRAG_THRESHOLD:
                    self._long_press_timer.stop()
                    self._is_dragging = True
                    self._is_potential_click = False 
            if self._is_dragging:
                self.move(event.globalPosition().toPoint() - self._drag_start_offset)
                event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._long_press_timer.stop() 
            if self._is_potential_click and not self._is_dragging:
                # Only trigger if released on the icon graphic (not on hidden area)
                if self.icon_display_rect.contains(event.position().toPoint()):
                    self._start_confetti_animation()
                    self.drop_context_requested.emit() 
            self._is_dragging = False
            self._is_potential_click = False
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    # ------------------------------------------------------------------
    # Hover‑controlled buttons
    # ------------------------------------------------------------------
    def enterEvent(self, event):  # noqa: N802
        self._leave_timer.stop() 
        self._hover_timer.start(300)
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802
        self._hover_timer.stop()
        if not (self.maximize_button.underMouse() or self.close_button.underMouse()):
            self._leave_timer.start(200)
        super().leaveEvent(event)

    def _show_control_buttons(self):
        self.maximize_button.show()
        self.close_button.show()

    def _hide_control_buttons_if_needed(self):
        if not ( 
            self.rect().contains(self.mapFromGlobal(QCursor.pos()))
            or self.maximize_button.underMouse()
            or self.close_button.underMouse()
        ):
            self.maximize_button.hide()
            self.close_button.hide()

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------
    def _emit_maximize_with_screen(self):
        screen = self.screen() or QGuiApplication.primaryScreen() 
        self.maximize_requested.emit(screen)


# -----------------------------------------------------------------------------
# Quick manual test
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    icon = HoverIcon()
    icon.show()

    # Centre on primary screen
    s = QGuiApplication.primaryScreen()
    if s:
        geo = s.availableGeometry()
        icon.move(geo.center() - icon.rect().center())

    icon.drop_context_requested.connect(lambda: print("Drop context requested"))
    icon.maximize_requested.connect(lambda sc: print(f"Maximize on {sc}"))
    icon.close_application_requested.connect(app.quit)

    sys.exit(app.exec())