import sys
import os
import shutil
import collections
from pathlib import Path
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

# Attempt to import db_manager for saving position
try:
    import db_manager # Assuming db_manager.py is in the same directory or Python path
except ImportError:
    db_manager = None
    print("WARNING: db_manager could not be imported in hover_icon.py. Hover icon position saving will be impaired if not handled by MainWindow.")

# Constants for App Settings Keys (mirrored from context_dropper.py for direct use if needed)
HOVER_POS_X_KEY = 'hover_pos_x'
HOVER_POS_Y_KEY = 'hover_pos_y'


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
CONFETTI_GRAVITY = -0.01 # Adjusted for upward pop, then fall
CONFETTI_DRAG = 0.985
CONFETTI_LIFE_MS_MIN = 600
CONFETTI_LIFE_MS_MAX = 1400
CONFETTI_ROTATION_SPEED_MAX = 5.0
CONFETTI_SCALE_START = 0.7
CONFETTI_SCALE_END = 1.0
CONFETTI_FADE_START_RATIO = 0.75 # Start fading when 75% of life is left (i.e. 25% elapsed)

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

_PRE_RENDERED_CONFETTI_PIXMAPS: list[QPixmap] = []


def _prepare_confetti_pixmaps() -> None:
    if not SVG_SUPPORT_AVAILABLE:
        return

    if _PRE_RENDERED_CONFETTI_PIXMAPS:
        return

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
    def __init__(self, origin: QPointF):
        angle = random.uniform(math.pi * 1.25, math.pi * 1.75) # Upward cone
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
        self.life_left -= dt_ms
        if self.life_left <= 0:
            return False

        self.pos += self.vel
        self.vel.setY(self.vel.y() - CONFETTI_GRAVITY) # Gravity acts downwards (positive Y is down)
        self.vel *= CONFETTI_DRAG
        self.rotation = (self.rotation + self.rotation_speed) % 360

        life_remaining_ratio = max(0.0, self.life_left / self.life_total)

        self.scale = CONFETTI_SCALE_END + (CONFETTI_SCALE_START - CONFETTI_SCALE_END) * math.sqrt(life_remaining_ratio) # Scale down over time

        if life_remaining_ratio < (1.0 - CONFETTI_FADE_START_RATIO): # If in the "fade out" part of its life
             self.opacity = life_remaining_ratio / (1.0 - CONFETTI_FADE_START_RATIO)
        else:
             self.opacity = 1.0
        return True


class _ConfettiOverlay(QWidget):
    def __init__(self, parent_icon: 'HoverIcon') -> None:
        super().__init__(None)
        self._parent_icon = parent_icon
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowTransparentForInput) # Transparent for input
        self.setAttribute(Qt.WA_TranslucentBackground)

        self._size = 6 * parent_icon.width() # Reduced size slightly
        self.setFixedSize(self._size, self._size)

        global_center = parent_icon.mapToGlobal(parent_icon.icon_display_rect.center())
        self.move(global_center.x() - self._size // 2, global_center.y() - self._size // 2)

        _prepare_confetti_pixmaps()
        self._particles: list[_ConfettiParticle] = []
        origin_local = QPointF(self._size / 2, self._size / 2) # Center of the overlay
        for _ in range(CONFETTI_PARTICLE_COUNT):
            self._particles.append(_ConfettiParticle(origin_local))

        self._timer = QTimer(self)
        self._timer.setInterval(16) # ~60 FPS
        self._timer.timeout.connect(self._advance)
        self._timer.start()

    def _advance(self) -> None:
        dt = self._timer.interval()
        self._particles = [p for p in self._particles if p.advance(dt)]
        if not self._particles:
            self.close() # Auto-close when all particles are dead
            return
        self.update()

    def paintEvent(self, event) -> None:
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

    def closeEvent(self, event):
        if self._parent_icon and hasattr(self._parent_icon, "_confetti_overlay"):
            self._parent_icon._confetti_overlay = None
        super().closeEvent(event)


class HoverIcon(QWidget):
    drop_context_requested = Signal()
    maximize_requested = Signal(object) # object will be QScreen
    close_application_requested = Signal()

    DRAG_THRESHOLD = 5
    LONG_PRESS_DURATION = 300 # ms for long press to initiate drag

    ICON_IMAGE_PATH = "contextdropper_transparent.png"
    ICON_DISPLAY_WIDTH = 64 # Width of the actual icon image display
    ICON_DISPLAY_HEIGHT = 64 # Height of the actual icon image display
    ICON_AREA_HEIGHT = 64 # Total height allocated for the icon part

    # Timer durations
    HOVER_SHOW_DELAY_ENTER = 200 # ms, initial delay to show buttons when mouse enters widget
    HOVER_SHOW_DELAY_MOVE = 100  # ms, quicker delay if mouse moves onto icon while already in widget
    LEAVE_HIDE_DELAY_EXIT = 50   # ms, quick hide when mouse leaves widget entirely
    LEAVE_HIDE_DELAY_INACTIVE = 300 # ms, slower hide if mouse moves to inactive area within widget

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowOpacity(0.8) # Slight transparency
        self.setMouseTracking(True) # Needed for mouseMoveEvent when no buttons are pressed

        _prepare_confetti_pixmaps()

        self.icon_pixmap = QPixmap(self.ICON_IMAGE_PATH)
        if self.icon_pixmap.isNull():
            print(f"Warning: Icon image '{self.ICON_IMAGE_PATH}' not found. Using fallback.")
            fallback = QPixmap(self.ICON_DISPLAY_WIDTH, self.ICON_DISPLAY_HEIGHT)
            fallback.fill(Qt.transparent)
            p = QPainter(fallback)
            p.setBrush(QColor(0, 122, 204, 150)) # A blueish circle
            p.setPen(Qt.NoPen)
            p.drawEllipse(QRect(0, 0, self.ICON_DISPLAY_WIDTH, self.ICON_DISPLAY_HEIGHT))
            p.end()
            self.icon_pixmap = fallback

        if self.icon_pixmap.size() != QSize(self.ICON_DISPLAY_WIDTH, self.ICON_DISPLAY_HEIGHT):
            self.icon_pixmap = self.icon_pixmap.scaled(self.ICON_DISPLAY_WIDTH, self.ICON_DISPLAY_HEIGHT,
                                                       Qt.KeepAspectRatio, Qt.SmoothTransformation)

        icon_area_width = self.ICON_DISPLAY_WIDTH
        self.icon_display_rect = QRect(
            (icon_area_width - self.ICON_DISPLAY_WIDTH) // 2,
            (self.ICON_AREA_HEIGHT - self.ICON_DISPLAY_HEIGHT) // 2,
            self.ICON_DISPLAY_WIDTH,
            self.ICON_DISPLAY_HEIGHT,
        )

        button_height = 20
        buttons_y = self.ICON_AREA_HEIGHT + 2 # Small gap
        self.setFixedSize(icon_area_width, self.ICON_AREA_HEIGHT + 2 + button_height) # Total widget size

        common_style = (
            "QPushButton { background-color: rgba(80,80,80,200); "
            "color: white; border-radius: 5px; border: 1px solid rgba(120,120,120,200);"
            "font-size: 11px; padding: 1px;} "
            "QPushButton:hover { background-color: rgba(100,100,100,230);}"
            "QPushButton:pressed { background-color: rgba(70,70,70,230);}"
        )
        btn_w = icon_area_width // 2 - 2 # Width for each button

        self.maximize_button = QPushButton("🗖", self) # Maximize symbol
        self.maximize_button.setFixedSize(btn_w, button_height)
        self.maximize_button.move(1, buttons_y) # Position first button
        self.maximize_button.setStyleSheet(common_style)
        self.maximize_button.setToolTip("Maximize Context Dropper")
        self.maximize_button.clicked.connect(self._emit_maximize_with_screen)
        self.maximize_button.hide()
        self.maximize_button.setMouseTracking(True) # Track mouse for hover effects

        self.close_button = QPushButton("✕", self) # Close symbol
        self.close_button.setFixedSize(btn_w, button_height)
        self.close_button.move(icon_area_width // 2 + 1, buttons_y) # Position second button
        self.close_button.setStyleSheet(common_style)
        self.close_button.setToolTip("Close Context Dropper")
        self.close_button.clicked.connect(self.close_application_requested.emit)
        self.close_button.hide()
        self.close_button.setMouseTracking(True) # Track mouse for hover effects


        self._is_dragging = False
        self._drag_start_offset = QPoint()
        self._mouse_press_pos_local = QPoint()
        self._long_press_timer = QTimer(self)
        self._long_press_timer.setSingleShot(True)
        self._long_press_timer.setInterval(self.LONG_PRESS_DURATION)
        self._long_press_timer.timeout.connect(self._initiate_drag_from_long_press)
        self._is_potential_click = False

        self._hover_timer = QTimer(self) # Timer to show buttons
        self._hover_timer.setSingleShot(True)
        self._hover_timer.timeout.connect(self._show_buttons_on_hover_timeout)

        self._leave_timer = QTimer(self) # Timer to hide buttons
        self._leave_timer.setSingleShot(True)
        self._leave_timer.timeout.connect(self._hide_buttons_now)

        self._confetti_overlay: _ConfettiOverlay | None = None

    def save_current_position(self):
        """Saves the current icon's top-left position to app settings."""
        if db_manager:
            try:
                current_pos = self.pos()
                db_manager.set_app_setting(HOVER_POS_X_KEY, str(current_pos.x()))
                db_manager.set_app_setting(HOVER_POS_Y_KEY, str(current_pos.y()))
            except Exception as e:
                print(f"HoverIcon: Error saving position: {e}")

    def _start_confetti_animation(self) -> None:
        if self._confetti_overlay is not None:
            self._confetti_overlay.close() 
            self._confetti_overlay = None
        self._confetti_overlay = _ConfettiOverlay(self)
        self._confetti_overlay.show()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.drawPixmap(self.icon_display_rect.topLeft(), self.icon_pixmap)
        p.end()

    def _initiate_drag_from_long_press(self):
        # This is called by _long_press_timer.timeout
        # Ensure that the press was on the icon and a drag hasn't started by movement already
        if self._is_potential_click and not self._is_dragging: 
            # _is_potential_click being true implies the press was on icon_display_rect
            self._is_dragging = True
            self._is_potential_click = False # It's now officially a drag
            QApplication.setOverrideCursor(Qt.SizeAllCursor)
            
            # Stop timers that manage button visibility during drag
            self._hover_timer.stop()
            self._leave_timer.stop()
            self.maximize_button.hide() # Hide buttons on drag start
            self.close_button.hide()


    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Check if press is on the icon_display_rect for click/drag operations
            if self.icon_display_rect.contains(event.position().toPoint()):
                self._mouse_press_pos_local = event.position().toPoint()
                self._drag_start_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                self._is_dragging = False # Explicitly reset _is_dragging for a new interaction
                self._is_potential_click = True # It's a potential click/drag on the icon
                self._long_press_timer.start() # Start timer for potential long-press drag
                event.accept()
            # If press is on buttons, let buttons handle it (event will propagate if not accepted here)
            elif self.maximize_button.isVisible() and self.maximize_button.geometry().contains(event.position().toPoint()):
                super().mousePressEvent(event) # Pass to button
            elif self.close_button.isVisible() and self.close_button.geometry().contains(event.position().toPoint()):
                super().mousePressEvent(event) # Pass to button
            else:
                # Press is outside icon and visible buttons, ignore for icon-specific actions
                super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)


    def mouseMoveEvent(self, event):
        # Check if the left mouse button is pressed
        if event.buttons() == Qt.LeftButton:
            # Scenario 1: Try to START a drag by movement
            # This happens if it was a potential click on the icon, and we are not already dragging,
            # and the mouse has moved beyond the threshold.
            if self._is_potential_click and not self._is_dragging:
                delta = (event.position().toPoint() - self._mouse_press_pos_local).manhattanLength()
                if delta > self.DRAG_THRESHOLD:
                    self._long_press_timer.stop()  # Stop long press if drag starts by movement
                    self._is_dragging = True
                    self._is_potential_click = False  # It's now officially a drag
                    QApplication.setOverrideCursor(Qt.SizeAllCursor)
                    
                    # Stop timers that manage button visibility during drag
                    self._hover_timer.stop()
                    self._leave_timer.stop()
                    self.maximize_button.hide()  # Hide buttons on drag start
                    self.close_button.hide()

            # Scenario 2: CONTINUE an ongoing drag
            # This happens if _is_dragging is already true (set by movement or long press).
            if self._is_dragging: # This check is now independent of _is_potential_click
                self.move(event.globalPosition().toPoint() - self._drag_start_offset)
                event.accept()
                return  # IMPORTANT: Skip further processing (like button visibility) during active drag
        
        # If not dragging (e.g., mouse moving without button pressed, or drag just ended),
        # then handle button visibility updates.
        if not self._is_dragging:
            self._update_button_visibility_on_mouse_hover()
        
        super().mouseMoveEvent(event) # Call base class method


    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._long_press_timer.stop() # Stop long press timer regardless
            
            was_dragging = self._is_dragging # Capture state before reset
            
            # Reset drag state. _is_potential_click is reset based on whether a drag occurred.
            self._is_dragging = False
            
            # Determine if it was a true click on the icon
            # A click occurs if _is_potential_click was true (meaning press was on icon and no drag started yet)
            # AND the release is also on the icon.
            is_click_on_icon = self._is_potential_click and \
                               self.icon_display_rect.contains(event.position().toPoint())
            
            self._is_potential_click = False # Always reset this after a release sequence

            QApplication.restoreOverrideCursor() # Always restore cursor

            if was_dragging:
                self.save_current_position()
                # After drag, cursor might be anywhere. Re-evaluate button visibility.
                self._update_button_visibility_on_mouse_hover() 
                event.accept()
            elif is_click_on_icon: 
                self._start_confetti_animation()
                self.drop_context_requested.emit()
                # After click, re-evaluate button visibility.
                self._update_button_visibility_on_mouse_hover()
                event.accept()
            else:
                # Not a drag, not a click on icon (e.g. click on button, or drag off then release)
                # Still update button visibility based on current cursor.
                self._update_button_visibility_on_mouse_hover()
                super().mouseReleaseEvent(event) # Allow event to propagate if not handled
        else:
            super().mouseReleaseEvent(event)

    def enterEvent(self, event):
        self._leave_timer.stop()  # Stop any pending hide
        self.setWindowOpacity(1.0) # Fully opaque on hover
        self._update_button_visibility_on_mouse_hover() # Initial check on enter
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover_timer.stop() # Stop any pending show check
        self.setWindowOpacity(0.8) # Back to semi-transparent
        # When mouse leaves the widget, always start the hide timer (quick hide)
        if not self._leave_timer.isActive() and (self.maximize_button.isVisible() or self.close_button.isVisible()):
            self._leave_timer.start(self.LEAVE_HIDE_DELAY_EXIT)
        super().leaveEvent(event)

    def _update_button_visibility_on_mouse_hover(self):
        """Manages button visibility based on current mouse position over the widget."""
        if self._is_dragging: # Don't change button visibility while dragging
            return

        cursor_pos_local = self.mapFromGlobal(QCursor.pos())
        
        if not self.rect().contains(cursor_pos_local): # Mouse is outside the widget
            if not self._leave_timer.isActive() and (self.maximize_button.isVisible() or self.close_button.isVisible()):
                self._leave_timer.start(self.LEAVE_HIDE_DELAY_EXIT)
            return

        on_icon = self.icon_display_rect.contains(cursor_pos_local)
        on_maximize = self.maximize_button.isVisible() and self.maximize_button.geometry().contains(cursor_pos_local)
        on_close = self.close_button.isVisible() and self.close_button.geometry().contains(cursor_pos_local)

        if on_icon:
            self._leave_timer.stop() 
            if not self.maximize_button.isVisible(): 
                if not self._hover_timer.isActive():
                     self._hover_timer.start(self.HOVER_SHOW_DELAY_MOVE) 
        elif on_maximize or on_close:
            self._hover_timer.stop() 
            self._leave_timer.stop() 
        else: # Mouse is in widget, but not on icon or buttons (inactive area)
            self._hover_timer.stop() 
            if self.maximize_button.isVisible() or self.close_button.isVisible(): 
                if not self._leave_timer.isActive():
                     self._leave_timer.start(self.LEAVE_HIDE_DELAY_INACTIVE)

    def _show_buttons_on_hover_timeout(self): 
        """Shows buttons if mouse is still over the icon when timer fires."""
        cursor_pos_local = self.mapFromGlobal(QCursor.pos())
        if self.icon_display_rect.contains(cursor_pos_local):
            self.maximize_button.show()
            self.close_button.show()
            self._leave_timer.stop() 
        
    def _hide_buttons_now(self): 
        """Hides buttons after a delay, re-checking cursor position."""
        cursor_pos_local = self.mapFromGlobal(QCursor.pos())
        on_icon = self.icon_display_rect.contains(cursor_pos_local)
        on_maximize = self.maximize_button.isVisible() and self.maximize_button.geometry().contains(cursor_pos_local)
        on_close = self.close_button.isVisible() and self.close_button.geometry().contains(cursor_pos_local)

        if not on_icon and not on_maximize and not on_close:
            self.maximize_button.hide()
            self.close_button.hide()
        
    def _emit_maximize_with_screen(self):
        screen = self.screen() or QGuiApplication.primaryScreen()
        self.maximize_requested.emit(screen)

    def closeEvent(self, event):
        self.save_current_position() 
        if self._confetti_overlay:
            self._confetti_overlay.close()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    if db_manager:
        if not os.path.exists(db_manager.DATABASE_NAME):
            print(f"Database '{db_manager.DATABASE_NAME}' not found for HoverIcon test. Initializing...")
            db_manager.init_db()
        else:
            db_manager.init_db() # Ensure tables exist

    icon = HoverIcon()

    if db_manager:
        try:
            x_str = db_manager.get_app_setting(HOVER_POS_X_KEY)
            y_str = db_manager.get_app_setting(HOVER_POS_Y_KEY)
            if x_str is not None and y_str is not None:
                icon.move(QPoint(int(x_str), int(y_str)))
            else:
                s = QGuiApplication.primaryScreen()
                if s:
                    geo = s.availableGeometry()
                    icon.move(geo.center() - icon.rect().center())
        except Exception as e:
            print(f"Error loading icon position for test: {e}")
            s = QGuiApplication.primaryScreen()
            if s:
                geo = s.availableGeometry()
                icon.move(geo.center() - icon.rect().center())
    else:
        s = QGuiApplication.primaryScreen()
        if s:
            geo = s.availableGeometry()
            icon.move(geo.center() - icon.rect().center())

    icon.show()


    icon.drop_context_requested.connect(lambda: print("Drop context requested"))
    icon.maximize_requested.connect(lambda sc: print(f"Maximize on {sc.name() if sc else 'N/A'}"))
    icon.close_application_requested.connect(app.quit)

    sys.exit(app.exec())
