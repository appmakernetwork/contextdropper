# ui_dialogs_widgets.py
# Contains custom dialogs and widgets for the Context Dropper application.

import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QListWidget, QLineEdit, QHBoxLayout,
    QPushButton, QDialogButtonBox, QMessageBox, QListWidgetItem,
    QWidget, QLabel, QGraphicsOpacityEffect
)
from PySide6.QtCore import Qt, Signal, QTimer, QPropertyAnimation, QEasingCurve, QPoint, QRect
from PySide6.QtGui import QGuiApplication # For NotificationWidget positioning

import db_manager # Required for ManageCategoriesDialog

class ManageCategoriesDialog(QDialog):
    """
    A dialog for adding, removing, and managing categories for a project.
    """
    def __init__(self, project_id, parent_main_window=None):
        super().__init__(parent_main_window)
        self.project_id = project_id
        # Store a reference to the main window to call its methods if necessary
        # (e.g., to refresh lists after category changes)
        self.parent_main_window = parent_main_window
        self.setWindowTitle("Manage Categories")
        self.setMinimumWidth(350) # Increased width slightly
        self.setMinimumHeight(300)
        layout = QVBoxLayout(self)

        self.category_list = QListWidget()
        self.category_list.setAlternatingRowColors(True) # Improves readability
        layout.addWidget(self.category_list)
        self.load_categories()

        self.new_category_edit = QLineEdit()
        self.new_category_edit.setPlaceholderText("New category name")
        layout.addWidget(self.new_category_edit)

        buttons_layout = QHBoxLayout()
        add_button = QPushButton("Add Category")
        add_button.clicked.connect(self.add_category)
        buttons_layout.addWidget(add_button)

        remove_button = QPushButton("Remove Selected")
        remove_button.clicked.connect(self.remove_category)
        buttons_layout.addWidget(remove_button)
        layout.addLayout(buttons_layout)

        # Standard OK button to close the dialog
        dialog_buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        dialog_buttons.accepted.connect(self.accept) # Closes dialog
        # dialog_buttons.rejected.connect(self.reject) # QDialog has reject by default with Escape key
        layout.addWidget(dialog_buttons)

    def load_categories(self):
        """
        Loads categories for the current project_id into the list widget.
        """
        self.category_list.clear()
        if not self.project_id: return
        categories = db_manager.get_categories(self.project_id)
        for cat in categories:
            item = QListWidgetItem(cat['name'])
            item.setData(Qt.UserRole, cat['id']) # Store category ID with the item
            self.category_list.addItem(item)

    def add_category(self):
        """
        Adds a new category to the database and refreshes the list.
        """
        name = self.new_category_edit.text().strip()
        if name and self.project_id:
            if db_manager.add_category(self.project_id, name):
                self.load_categories() # Refresh list
                self.new_category_edit.clear()
                # Optionally, inform main window to update other UI elements if needed
                if self.parent_main_window:
                    self.parent_main_window.load_categories_for_export()
                    self.parent_main_window.load_selected_items()
            else:
                QMessageBox.warning(self, "Error", f"Category '{name}' already exists or could not be added.")
        elif not name:
            QMessageBox.warning(self, "Input Error", "Category name cannot be empty.")

    def remove_category(self):
        """
        Removes the selected category from the database and refreshes the list.
        Items in the removed category will become uncategorized.
        """
        selected_item = self.category_list.currentItem()
        if not selected_item:
            QMessageBox.warning(self, "Selection Error", "Please select a category to remove.")
            return

        category_id = selected_item.data(Qt.UserRole)
        category_name = selected_item.text()

        reply = QMessageBox.question(self, "Confirm Remove",
                                     f"Are you sure you want to remove category '{category_name}'?\n"
                                     "Items currently in this category will become uncategorized.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            if db_manager.remove_category_and_uncategorize_items(category_id): # Updated DB manager function
                self.load_categories() # Refresh this dialog's list
                # Inform main window to update its views
                if self.parent_main_window:
                    self.parent_main_window.load_categories_for_export()
                    self.parent_main_window.load_selected_items()
            else:
                QMessageBox.critical(self, "Error", f"Could not remove category '{category_name}'.")


class DroppableListWidget(QListWidget):
    """
    A QListWidget subclass that accepts drag-and-drop operations for files and directories.
    Emits a signal when an item is successfully dropped.
    """
    item_dropped_signal = Signal(str, bool) # path, is_directory

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)       # Enable drop events
        self.setDropIndicatorShown(True)# Show visual indicator where item will be dropped

    def dragEnterEvent(self, event):
        """
        Handles the drag enter event. Accepts the event if it contains URLs.
        """
        if event.mimeData().hasUrls():
            event.acceptProposedAction() # Accept the drag operation
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        """
        Handles the drag move event. Accepts the event if it contains URLs.
        """
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        """
        Handles the drop event. Extracts file/directory paths from URLs and emits a signal.
        """
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.CopyAction) # Indicate a copy operation
            urls = event.mimeData().urls()
            for url in urls:
                path = url.toLocalFile() # Convert URL to local file path
                if path:
                    is_dir = os.path.isdir(path)
                    self.item_dropped_signal.emit(path, is_dir) # Emit signal with path and type
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


class NotificationWidget(QWidget):
    """
    A custom widget for displaying non-intrusive, temporary notifications.
    Notifications fade in and out.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        # Window flags: Tool (doesn't show in taskbar), Frameless, Always On Top
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground) # Enable transparency
        self.setAttribute(Qt.WA_DeleteOnClose)        # Delete widget when closed
        self.setStyleSheet("background:transparent;") # Make base widget transparent

        # Card widget for the actual notification content appearance
        self.card_widget = QWidget(self)
        self.card_widget.setStyleSheet("""
            QWidget {
                background-color: rgb(53, 53, 53); /* Dark background */
                border-radius: 8px;
                border: 1px solid rgb(75, 75, 75); /* Subtle border */
            }
        """)

        card_layout = QVBoxLayout(self.card_widget)
        card_layout.setContentsMargins(15, 10, 15, 10) # Padding inside the card

        self.message_label = QLabel("")
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet(
            "background-color: transparent; color: white; font-size: 10pt; border: none;"
        )
        card_layout.addWidget(self.message_label)

        # Outer layout to manage the card widget (allows for potential shadows or effects later)
        outer_layout = QVBoxLayout(self)
        outer_layout.addWidget(self.card_widget)
        outer_layout.setContentsMargins(0,0,0,0) # No margins for the outer layout itself

        # Opacity effect for fade animations
        self.opacity_effect = QGraphicsOpacityEffect(self.card_widget)
        self.card_widget.setGraphicsEffect(self.opacity_effect)

        # Timer to auto-hide the notification
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._start_fade_out)

        # Animations for fade-in and fade-out
        self.fadeInAnimation = QPropertyAnimation(self.opacity_effect, b"opacity", self)
        self.fadeOutAnimation = QPropertyAnimation(self.opacity_effect, b"opacity", self)


    def _start_fade_out(self):
        """Initiates the fade-out animation."""
        if self.fadeOutAnimation.state() == QPropertyAnimation.Running:
            self.fadeOutAnimation.stop() # Stop if already running

        self.fadeOutAnimation.setDuration(600) # Duration of fade-out
        self.fadeOutAnimation.setStartValue(self.opacity_effect.opacity()) # Start from current opacity
        self.fadeOutAnimation.setEndValue(0.0) # Fade to fully transparent
        self.fadeOutAnimation.setEasingCurve(QEasingCurve.InOutQuad) # Smooth easing
        self.fadeOutAnimation.finished.connect(self.hide) # Hide widget when animation finishes
        self.fadeOutAnimation.start()

    def show_message(self, message, duration_ms=3500, anchor_widget=None):
        """
        Displays the notification with a given message and duration.
        Args:
            message (str): The message to display.
            duration_ms (int): How long the notification stays visible before fading.
            anchor_widget (QWidget, optional): A widget to anchor the notification's screen position.
                                               Defaults to primary screen's top-right.
        """
        # Stop any ongoing animations or timers
        if self.fadeInAnimation.state() == QPropertyAnimation.Running:
            self.fadeInAnimation.stop()
        if self.fadeOutAnimation.state() == QPropertyAnimation.Running:
            self.fadeOutAnimation.stop()
        self.timer.stop()

        self.message_label.setText(message)

        # Adjust size based on content
        NOTIFICATION_WIDTH = 350 # Fixed width for consistency
        self.card_widget.setFixedWidth(NOTIFICATION_WIDTH)
        self.message_label.adjustSize() # Adjust label height based on text
        self.card_widget.adjustSize()   # Adjust card height
        self.adjustSize()               # Adjust overall widget size

        # Determine screen and position
        target_screen = None
        if anchor_widget and anchor_widget.isVisible():
            if not anchor_widget.isMinimized(): # Ensure anchor is not minimized
                s = anchor_widget.screen()
                if s:
                    target_screen = s

        if not target_screen: # Fallback to primary screen
            target_screen = QGuiApplication.primaryScreen()

        if not target_screen: # Absolute fallback if no screen info (should be rare)
            desktop_rect = QGuiApplication.primaryScreen().geometry() if QGuiApplication.primaryScreen() else QRect(0,0,800,600)
            x = desktop_rect.right() - self.width() - 20 # Default to top-right
            y = desktop_rect.top() + 20
            self.move(x, y)
        else:
            screen_geometry = target_screen.availableGeometry() # Use available geometry (respects taskbars)
            margin_x = 20 # Margin from screen edges
            margin_y = 20
            x = screen_geometry.right() - self.width() - margin_x
            y = screen_geometry.top() + margin_y
            self.move(x, y)

        self.opacity_effect.setOpacity(0.0) # Start fully transparent for fade-in
        self.show()
        self.raise_() # Ensure it's on top

        # Start fade-in animation
        self.fadeInAnimation.setDuration(400)
        self.fadeInAnimation.setStartValue(0.0)
        self.fadeInAnimation.setEndValue(0.85) # Slightly transparent even when fully visible
        self.fadeInAnimation.setEasingCurve(QEasingCurve.OutQuad)
        self.fadeInAnimation.start()

        self.timer.start(duration_ms) # Start timer to auto-hide
