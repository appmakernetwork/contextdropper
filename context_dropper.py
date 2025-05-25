import sys
import os
import shutil
import collections # Keep for MainWindow._generate_directory_preview_summary
from pathlib import Path # Keep for MainWindow._generate_directory_preview_summary

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QTreeView, QFileSystemModel,
    QSplitter, QMenu, QInputDialog, QMessageBox, QComboBox,
    QHeaderView, QSpacerItem, QSizePolicy, QFileDialog, QAbstractItemView,
    QPlainTextEdit, QStackedWidget, QListWidgetItem
)
from PySide6.QtGui import (
    QAction, QClipboard, QCursor, QGuiApplication, QPalette, QColor, QIcon,
    QPixmap, QPainter, QFont, QTextOption
)
from PySide6.QtCore import (
    Qt, QDir, Slot, QTimer, Signal, QModelIndex, QPoint,
    QRect, QSize, QRectF
)

import db_manager
from hover_icon import HoverIcon
from syntax_highlighter import SyntaxHighlighter
import context_generator

# Import the new UI components module
from ui_dialogs_widgets import ManageCategoriesDialog, DroppableListWidget, NotificationWidget

# Conditional import for QSvgRenderer for SVG image support
try:
    from PySide6.QtSvg import QSvgRenderer
    SVG_SUPPORT_AVAILABLE = True
except ImportError:
    QSvgRenderer = None
    SVG_SUPPORT_AVAILABLE = False
    print("WARNING: PySide6.QtSvg module not found. "
          "SVG preview will not be available. "
          "Install PySide6-Addons or ensure Qt SVG module is available.")


# --- Constants for App Settings Keys ---
GUI_POS_X_KEY = 'gui_pos_x'
GUI_POS_Y_KEY = 'gui_pos_y'
HOVER_POS_X_KEY = 'hover_pos_x'
HOVER_POS_Y_KEY = 'hover_pos_y'
LAST_UI_MODE_KEY = 'last_ui_mode'

class ContextStatusFileSystemModel(QFileSystemModel):
    """
    Custom QFileSystemModel to display an asterisk (*) next to files
    that are marked for inclusion in the context drop.
    """
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self._cached_selection_details = {} # Stores {normcased_abs_file_path: True}

    def data(self, index, role=Qt.DisplayRole):
        """
        Overrides the data method to modify the display name of files.
        """
        if role == Qt.DisplayRole and index.isValid():
            original_name = super().data(index, role)
            # Return original name if root path is empty (no project selected)
            if not self.rootPath(): # Check if root path is empty
                 return original_name

            file_path_abs = self.filePath(index)
            normcased_file_path_from_model = os.path.normcase(os.path.normpath(file_path_abs))

            if not self.isDir(index) and self.main_window and self.main_window.current_project_id:
                if self.main_window._selections_for_display_dirty:
                    effective_selections = self.main_window.get_effective_selections_for_display()
                    self._cached_selection_details = self.main_window.get_detailed_inclusion_map(effective_selections)
                    self.main_window._selections_for_display_dirty = False

                if normcased_file_path_from_model in self._cached_selection_details:
                    return f"{original_name} *"
            return original_name
        return super().data(index, role)

    def refresh_display_indicators(self):
        if self.main_window:
            self.main_window._selections_for_display_dirty = True
        self.layoutChanged.emit()


class MainWindow(QMainWindow):
    BINARY_EXTENSIONS = [
        '.exe', '.dll', '.so', '.dylib', '.jar', '.class', '.pyc', '.o', '.a', '.lib',
        '.zip', '.gz', '.tar', '.rar', '.7z', '.pkg', '.dmg',
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
        '.odt', '.ods', '.odp',
        '.mp3', '.wav', '.ogg', '.mp4', '.avi', '.mkv', '.mov', '.webm',
        '.db', '.sqlite', '.sqlite3', '.mdb', '.accdb',
        '.wasm', '.woff', '.woff2', '.ttf', '.otf', '.eot',
        '.DS_Store'
    ]
    MAX_PREVIEW_SIZE = 1 * 1024 * 1024
    RASTER_IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.ico']
    SVG_IMAGE_EXTENSIONS = ['.svg']

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Context Dropper")
        self.setGeometry(100, 100, 1200, 800)
        self.current_project_id = None
        self.current_project_path = None
        self.current_highlighter = None
        self._selections_for_display_dirty = True
        db_manager.init_db()
        self.setup_ui()
        self.hover_widget = HoverIcon()
        self._load_initial_positions()
        self.load_projects()
        self.load_active_project() # This will call update_ui_for_project_state
        self.hover_widget.drop_context_requested.connect(self.drop_context)
        self.hover_widget.maximize_requested.connect(self.show_main_window_from_hover)
        self.hover_widget.close_application_requested.connect(self.close_application_from_hover)
        self.notification_widget = NotificationWidget()
        self.prompt_save_timer = QTimer(self)
        self.prompt_save_timer.setSingleShot(True)
        self.prompt_save_timer.timeout.connect(self.save_prompt_guide_to_db)
        self.prompt_edit.textChanged.connect(self.on_prompt_text_changed)
        self.initial_mode = "gui"
        last_mode_setting = db_manager.get_app_setting(LAST_UI_MODE_KEY)
        if last_mode_setting == "hover":
            self.initial_mode = "hover"

    def _center_on_primary_screen(self):
        primary_screen = QGuiApplication.primaryScreen()
        if primary_screen:
            screen_geometry = primary_screen.availableGeometry()
            current_size = self.size() if not self.size().isEmpty() else QSize(1200, 800)
            self.setGeometry(
                screen_geometry.x() + (screen_geometry.width() - current_size.width()) // 2,
                screen_geometry.y() + (screen_geometry.height() - current_size.height()) // 2,
                current_size.width(),
                current_size.height()
            )

    def _center_hover_icon_on_primary_screen(self):
        primary_screen = QGuiApplication.primaryScreen()
        if primary_screen and self.hover_widget:
            screen_geometry = primary_screen.availableGeometry()
            icon_size = self.hover_widget.sizeHint() if not self.hover_widget.size().isEmpty() else self.hover_widget.size()
            if icon_size.isEmpty():
                icon_size = QSize(self.hover_widget.ICON_DISPLAY_WIDTH,
                                     self.hover_widget.ICON_AREA_HEIGHT + 2 + 20) # Approx button height
            self.hover_widget.move(
                screen_geometry.x() + (screen_geometry.width() - icon_size.width()) // 2,
                screen_geometry.y() + (screen_geometry.height() - icon_size.height()) // 2
            )

    def _load_initial_positions(self):
        gui_loaded = False
        try:
            gui_x_str = db_manager.get_app_setting(GUI_POS_X_KEY)
            gui_y_str = db_manager.get_app_setting(GUI_POS_Y_KEY)
            if gui_x_str is not None and gui_y_str is not None:
                self.move(QPoint(int(gui_x_str), int(gui_y_str)))
                gui_loaded = True
        except ValueError:
            print(f"Warning: Could not parse saved GUI position. "
"Using default.")
        except Exception as e:
            print(f"Error loading GUI position: {e}. Using default.")
        if not gui_loaded:
            self._center_on_primary_screen()

        hover_loaded = False
        if self.hover_widget:
            try:
                hover_x_str = db_manager.get_app_setting(HOVER_POS_X_KEY)
                hover_y_str = db_manager.get_app_setting(HOVER_POS_Y_KEY)
                if hover_x_str is not None and hover_y_str is not None:
                    self.hover_widget.move(QPoint(int(hover_x_str), int(hover_y_str)))
                    hover_loaded = True
            except ValueError:
                print(f"Warning: Could not parse saved hover icon position. Using default.")
            except Exception as e:
                print(f"Error loading hover icon position: {e}. Using default.")
            if not hover_loaded:
                self._center_hover_icon_on_primary_screen()

    def save_gui_position(self):
        if self.isVisible() and not self.isMinimized():
            current_pos = self.pos()
            db_manager.set_app_setting(GUI_POS_X_KEY, str(current_pos.x()))
            db_manager.set_app_setting(GUI_POS_Y_KEY, str(current_pos.y()))

    def save_hover_icon_position(self):
        if self.hover_widget:
            current_pos = self.hover_widget.pos()
            db_manager.set_app_setting(HOVER_POS_X_KEY, str(current_pos.x()))
            db_manager.set_app_setting(HOVER_POS_Y_KEY, str(current_pos.y()))

    def setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # --- Top Bar ---
        top_bar_layout = QHBoxLayout()
        self.project_combo = QComboBox()
        self.project_combo.currentIndexChanged.connect(self.project_selected_by_combo)
        top_bar_layout.addWidget(QLabel("Active Project:"))
        top_bar_layout.addWidget(self.project_combo, 1)
        self.new_project_button_main = QPushButton("New Project") # Renamed to avoid clash if placeholder is also a button
        self.new_project_button_main.clicked.connect(self.new_project_dialog)
        top_bar_layout.addWidget(self.new_project_button_main)
        self.delete_project_button = QPushButton("Delete Project")
        self.delete_project_button.clicked.connect(self.delete_current_project)
        top_bar_layout.addWidget(self.delete_project_button)
        self.manage_cat_button = QPushButton("Manage Categories")
        self.manage_cat_button.clicked.connect(self.manage_categories_dialog)
        top_bar_layout.addWidget(self.manage_cat_button)
        main_layout.addLayout(top_bar_layout)

        # --- Main Content Area (QStackedWidget) ---
        self.content_stack = QStackedWidget()
        main_layout.addWidget(self.content_stack, 1)

        # --- Page 1: Main Interface (with splitter) ---
        self.main_interface_widget = QWidget()
        main_interface_layout = QHBoxLayout(self.main_interface_widget)
        main_interface_layout.setContentsMargins(0,0,0,0)

        splitter = QSplitter(Qt.Horizontal)

        # Left Pane (File Tree)
        left_pane = QWidget()
        left_layout = QVBoxLayout(left_pane)
        self.fs_model = ContextStatusFileSystemModel(self)
        self.fs_model.setRootPath("")
        self.fs_model.setFilter(QDir.AllDirs | QDir.Files | QDir.NoDotAndDotDot)
        self.tree_view = QTreeView()
        self.tree_view.setModel(self.fs_model)
        self.tree_view.setRootIndex(self.fs_model.index(""))
        self.tree_view.setSortingEnabled(True)
        self.tree_view.sortByColumn(0, Qt.AscendingOrder)
        self.tree_view.setDragEnabled(True)
        self.tree_view.setDragDropMode(QAbstractItemView.DragOnly)
        self.tree_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree_view.setHeaderHidden(False)
        self.tree_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self.tree_context_menu)
        for i in range(1, self.fs_model.columnCount()):
            self.tree_view.setColumnHidden(i, True)
        self.tree_view.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree_view.selectionModel().currentChanged.connect(self._handle_tree_view_selection)
        left_layout.addWidget(self.tree_view)
        splitter.addWidget(left_pane)

        # Right Pane (Prompt, Preview, Selected Items)
        right_pane = QWidget()
        right_layout = QVBoxLayout(right_pane)
        self.right_splitter = QSplitter(Qt.Vertical)

        prompt_group = QWidget()
        prompt_layout = QVBoxLayout(prompt_group)
        prompt_layout.setContentsMargins(0,0,0,0)
        prompt_layout.addWidget(QLabel("AI Prompt Guide:"))
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText("Enter your initial prompt guide here...")
        prompt_layout.addWidget(self.prompt_edit)
        self.right_splitter.addWidget(prompt_group)

        preview_group = QWidget()
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setContentsMargins(0,0,0,0)
        self.preview_title_label = QLabel("File Preview:") # Instance variable
        preview_layout.addWidget(self.preview_title_label)
        self.preview_stack = QStackedWidget()
        self.file_preview_edit = QPlainTextEdit()
        self.file_preview_edit.setReadOnly(True)
        self.file_preview_edit.setStyleSheet(
            "QPlainTextEdit { background-color: #1E1E1E; "
"color: #D4D4D4; "
            "selection-background-color: #0078D7; selection-color: #FFFFFF; "
            "font-family: 'Consolas', 'Monaco', 'Menlo', 'Courier New', monospace; "
            "font-size: 9pt; }"
            "QPlainTextEdit::placeholderText { color: #A0A0A0; "
"}"
        )
        self.preview_stack.addWidget(self.file_preview_edit)
        self.image_preview_label = QLabel()
        self.image_preview_label.setAlignment(Qt.AlignCenter)
        self.image_preview_label.setStyleSheet("background-color: #1E1E1E;")
        self.image_preview_label.setScaledContents(False)
        self.preview_stack.addWidget(self.image_preview_label)
        preview_layout.addWidget(self.preview_stack)
        self.right_splitter.addWidget(preview_group)

        selected_group = QWidget()
        selected_layout = QVBoxLayout(selected_group)
        selected_layout.setContentsMargins(0,0,0,0)
        selected_layout.addWidget(QLabel("Selected Context Items:"))
        self.selected_items_list = DroppableListWidget(selected_group)
        self.selected_items_list.item_dropped_signal.connect(self.handle_dropped_item_signal)
        self.selected_items_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.selected_items_list.customContextMenuRequested.connect(self.selected_item_context_menu)
        self.selected_items_list.currentItemChanged.connect(self._handle_selected_items_list_selection)
        selected_layout.addWidget(self.selected_items_list)
        self.right_splitter.addWidget(selected_group)

        self.right_splitter.setSizes([350, 300, 350])
        right_layout.addWidget(self.right_splitter)
        splitter.addWidget(right_pane)

        splitter.setSizes([400, 800])
        main_interface_layout.addWidget(splitter)
        self.content_stack.addWidget(self.main_interface_widget)

        # --- Page 2: "No Project" Placeholder ---
        self.no_project_widget = QWidget()
        no_project_layout = QVBoxLayout(self.no_project_widget)
        self.placeholder_label = QLabel() # Will be set up with rich text
        self.placeholder_label.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPointSize(16)
        # Font boldness will be handled by rich text for the non-link part
        self.placeholder_label.setFont(font)
        self.placeholder_label.setTextFormat(Qt.RichText)
        self.placeholder_label.setOpenExternalLinks(False) # We handle link activation manually
        self.placeholder_label.linkActivated.connect(self.handle_placeholder_link)
        # Set the text using a method that can be called to update it if needed
        self._update_placeholder_text()
        no_project_layout.addWidget(self.placeholder_label)
        self.content_stack.addWidget(self.no_project_widget)


        # --- Bottom Bar ---
        bottom_bar_layout = QHBoxLayout()
        self.export_category_label = QLabel("Export Category:") # Store reference to label
        bottom_bar_layout.addWidget(self.export_category_label)
        self.export_category_combo = QComboBox()
        self.export_category_combo.currentIndexChanged.connect(self.refresh_file_tree_display_indicators)
        bottom_bar_layout.addWidget(self.export_category_combo)
        bottom_bar_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        self.drop_context_button = QPushButton("Drop Context")
        self.drop_context_button.clicked.connect(self.drop_context)
        bottom_bar_layout.addWidget(self.drop_context_button)
        self.collapse_button = QPushButton("Collapse to Hover Icon")
        self.collapse_button.clicked.connect(self.collapse_to_hover_icon)
        bottom_bar_layout.addWidget(self.collapse_button)
        main_layout.addLayout(bottom_bar_layout)

        self._show_preview_for_path(None) # Initial call

    def _update_placeholder_text(self):
        """Sets the rich text for the placeholder label."""
        # Using a known color from the dark palette for the link for better visibility
        # QPalette().color(QPalette.Link) might also work if palette is set early enough
        link_color = "#569CD6" # A blue color often used for links in dark themes
        self.placeholder_label.setText(
            f'<span style="color: #A0A0A0; '
"font-weight: bold;\">Create a "
            f'<a href="action:new_project" style="color: {link_color}; '
"text-decoration: underline; font-weight: bold;\">new project</a>"
            f' or select an existing one to get started.</span>'
        )

    def handle_placeholder_link(self, link_str):
        """Handles clicks on links in the placeholder label."""
        if link_str == "action:new_project":
            self.new_project_dialog()


    def on_prompt_text_changed(self):
        if self.current_project_id:
            self.prompt_save_timer.start(1000) # ms delay

    def save_prompt_guide_to_db(self):
        if self.current_project_id and self.prompt_edit.toPlainText() is not None:
            db_manager.update_project_prompt(self.current_project_id, self.prompt_edit.toPlainText())

    def load_projects(self):
        self.project_combo.blockSignals(True)
        self.project_combo.clear()
        projects = db_manager.get_projects()
        if not projects:
            self.project_combo.addItem("No projects yet", None)
        else:
            for project in projects:
                self.project_combo.addItem(project['name'], project['id'])
        self.project_combo.blockSignals(False)

    def load_active_project(self):
        active_project_data = db_manager.get_active_project()
        if active_project_data:
            project_id_to_activate = active_project_data['id']
            idx = self.project_combo.findData(project_id_to_activate)
            if idx != -1:
                self.project_combo.setCurrentIndex(idx)
                if self.current_project_id != project_id_to_activate:
                     self.update_project_details(project_id_to_activate)
                elif self.current_project_id == project_id_to_activate :
                    self.update_ui_for_project_state()
            else:
                # Active project in DB not found in combo (e.g. deleted externally)
                db_manager.set_active_project(None)
                self.clear_project_context()
        else:
            # No active project in DB, select first in list if available
            if self.project_combo.count() > 0 and self.project_combo.itemData(0) is not None:
                 self.project_combo.setCurrentIndex(0) # This will trigger project_selected_by_combo
            else: # No projects at all
                 self.clear_project_context()

    def project_selected_by_combo(self, index):
        project_id = self.project_combo.itemData(index)
        self.update_project_details(project_id)

    def update_project_details(self, project_id):
        if project_id is None:
            self.clear_project_context()
            return

        project = db_manager.get_project_by_id(project_id)
        if project:
            self.current_project_id = project['id']
            self.current_project_path = os.path.normcase(os.path.normpath(project['path']))

            self.prompt_edit.blockSignals(True)
            self.prompt_edit.setText(project['prompt_guide'] or "")
            self.prompt_edit.blockSignals(False)

            if os.path.isdir(project['path']):
                self.fs_model.setRootPath(project['path'])
                self.tree_view.setRootIndex(self.fs_model.index(project['path']))
            else:
                QMessageBox.warning(self, "Project Path Error",
                                    f"Project path not found: {project['path']}\n"
                                    "Selected project's directory is not accessible. "
"The file tree will be empty.")
                self.fs_model.setRootPath("")
                self.tree_view.setRootIndex(self.fs_model.index(""))

            db_manager.set_active_project(self.current_project_id)
        else:
            self.clear_project_context() # Project ID was not None, but project not found in DB

        self.update_ui_for_project_state()
        self.load_selected_items()
        self.load_categories_for_export()
        self._show_preview_for_path(None) # Reset preview title

    def clear_project_context(self):
        self.current_project_id = None
        self.current_project_path = None
        self.prompt_edit.blockSignals(True)
        self.prompt_edit.clear()
        self.prompt_edit.blockSignals(False)

        self.fs_model.setRootPath("")
        self.tree_view.setRootIndex(self.fs_model.index(""))

        db_manager.set_active_project(None) # Ensure no active project in DB
        self.update_ui_for_project_state()
        self.load_selected_items() # Will clear list
        self.load_categories_for_export() # Will clear combo
        self._show_preview_for_path(None) # Reset preview title

    def new_project_dialog(self):
        name, ok = QInputDialog.getText(self, "New Project", "Project Name:")
        if ok and name.strip():
            name = name.strip()
            path = QFileDialog.getExistingDirectory(self, "Select Project Home Directory", QDir.homePath())
            if path:
                project_id = db_manager.add_project(name, path)
                if project_id:
                    self.load_projects()
                    idx = self.project_combo.findData(project_id)
                    if idx != -1:
                        self.project_combo.blockSignals(True) # Avoid premature trigger
                        self.project_combo.setCurrentIndex(idx)
                        self.project_combo.blockSignals(False)
                        self.update_project_details(project_id) # Manually update for the new project
                else:
                    QMessageBox.warning(self, "Error", f"Could not create project '{name}'. "
"It might already exist.")
        elif ok and not name.strip(): # OK was pressed, but name is empty
            QMessageBox.warning(self, "Input Error", "Project name cannot be empty.")

    def delete_current_project(self):
        if not self.current_project_id:
            QMessageBox.information(self, "No Project", "No project is active to delete.")
            return

        project_name = self.project_combo.currentText()
        reply = QMessageBox.question(self, "Confirm Delete",
                                     f"Are you sure you want to delete project '{project_name}'?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            db_manager.delete_project(self.current_project_id)
            self.load_projects() # Refresh project list
            self.load_active_project() # Load next active or clear context

    def manage_categories_dialog(self):
        if not self.current_project_id:
            QMessageBox.information(self, "No Project", "Please select or create a project first.")
            return
        dialog = ManageCategoriesDialog(self.current_project_id, parent_main_window=self)
        dialog.exec()
        # Changes in categories might affect display indicators or selected items list
        self.refresh_file_tree_display_indicators()
        # self.load_selected_items() # Already called by ManageCategoriesDialog if parent_main_window is set

    def load_categories_for_export(self):
        self.export_category_combo.blockSignals(True)
        self.export_category_combo.clear()
        self.export_category_combo.addItem("All Categories", None) # UserData is None
        if self.current_project_id:
            categories = db_manager.get_categories(self.current_project_id)
            for cat in categories:
                self.export_category_combo.addItem(cat['name'], cat['id']) # UserData is cat_id
        self.export_category_combo.blockSignals(False)
        self.refresh_file_tree_display_indicators() # Refresh tree based on new filter

    def update_ui_for_project_state(self):
        has_project = self.current_project_id is not None

        if has_project:
            self.content_stack.setCurrentWidget(self.main_interface_widget)
        else:
            self.content_stack.setCurrentWidget(self.no_project_widget)
            self._update_placeholder_text() # Ensure placeholder text is correct

        # Enable/disable components based on project presence
        self.tree_view.setEnabled(has_project)
        self.prompt_edit.setEnabled(has_project)
        self.selected_items_list.setEnabled(has_project)
        if hasattr(self, 'preview_stack'): self.preview_stack.setEnabled(has_project)

        # Set visibility for project-specific buttons and controls
        self.delete_project_button.setVisible(has_project)
        self.manage_cat_button.setVisible(has_project)
        self.export_category_label.setVisible(has_project)
        self.export_category_combo.setVisible(has_project)
        self.drop_context_button.setVisible(has_project)
        self.collapse_button.setVisible(has_project)


        if has_project:
            project_name = self.project_combo.currentText()
            self.setWindowTitle(f"Context Dropper - {project_name}")
        else:
            self.setWindowTitle("Context Dropper")

    def _add_project_root_actions_to_menu(self, menu: QMenu):
        if not self.current_project_id or not self.current_project_path or not os.path.isdir(self.current_project_path):
            return False

        r_path = self.current_project_path # Already normcased
        r_is_dir = True
        existing_root_sel = db_manager.get_selection_by_path(self.current_project_id, r_path)

        if existing_root_sel:
            menu.addAction("Project Root (.): Options...",
                           lambda path=r_path, is_dir=r_is_dir, sel=existing_root_sel: self.add_or_update_selection(path, is_dir, sel))
            menu.addAction("Project Root (.): Assign/Change Category...",
                           lambda path=r_path: self.assign_category_to_selection_dialog(path))
            menu.addAction("Project Root (.): Remove from Context",
                           lambda path=r_path: self.remove_selected_path(path))
        else:
            menu.addAction("Project Root (.): Add to Context",
                           lambda path=r_path, is_dir=r_is_dir: self.add_or_update_selection(path, is_dir, None))
        return True

    def tree_context_menu(self, position: QPoint):
        if not self.current_project_id:
            return

        index = self.tree_view.indexAt(position)
        menu = QMenu()
        item_actions_added = False
        root_actions_added = False

        if index.isValid():
            path_from_model = self.fs_model.filePath(index)
            normcased_path = os.path.normcase(os.path.normpath(path_from_model))
            is_dir = self.fs_model.isDir(index)
            existing_selection = db_manager.get_selection_by_path(self.current_project_id, normcased_path)

            item_display_name = os.path.basename(normcased_path)
            if not item_display_name and normcased_path == self.current_project_path: # Project root itself
                item_display_name = "."
            elif not item_display_name: # Should not happen for valid paths
                 item_display_name = normcased_path # Fallback

            if existing_selection:
                action_text = f"'{item_display_name}': Directory Options..." if is_dir else f"'{item_display_name}': Item Options..."
                menu.addAction(action_text, lambda p=normcased_path, d=is_dir, s=existing_selection: self.add_or_update_selection(p, d, s))
                menu.addAction(f"'{item_display_name}': Assign/Change Category...", lambda p=normcased_path: self.assign_category_to_selection_dialog(p))
                menu.addAction(f"'{item_display_name}': Remove from Context", lambda p=normcased_path: self.remove_selected_path(p))
            else:
                action_text = f"'{item_display_name}': Add Directory to Context" if is_dir else f"'{item_display_name}': Add File to Context"
                menu.addAction(action_text, lambda p=normcased_path, d=is_dir: self.add_or_update_selection(p, d))
            item_actions_added = True

        if item_actions_added and not menu.isEmpty(): # Check if any actions were actually added
            menu.addSeparator()

        root_actions_added = self._add_project_root_actions_to_menu(menu)

        if (item_actions_added or root_actions_added) and not menu.isEmpty():
            menu.exec(self.tree_view.viewport().mapToGlobal(position))


    def add_or_update_selection(self, path, is_dir, existing_selection=None):
        if not self.current_project_id:
            QMessageBox.warning(self, "No Project Active", "Cannot add selection: no project is active.")
            return

        file_types = None # For files, this remains None
        category_id = existing_selection['category_id'] if existing_selection else None
        path_for_db = os.path.normpath(path) # Path is already normcased by caller

        if is_dir:
            current_types = ""
            if existing_selection and existing_selection['file_types']:
                current_types = existing_selection['file_types']
            elif not existing_selection: # Default types for new directory selections
                current_types = ".py,.js,.dart,.html,.htm,.yaml,.json,.txt,.md,.h,.hpp,.cs,.java,.go,.php,.rb,.swift,.kt,.rs,CMakeLists.txt,Makefile,Dockerfile"


            types_str, ok = QInputDialog.getText(self, "Include File Types (Directory)",
                                                 "Comma-separated (e.g., .py,.txt) or exact filenames.\nEmpty for ALL files (recursive).",
                                                 text=current_types)
            if not ok: return # User cancelled
            file_types = types_str.strip() if types_str.strip() else None # Store None if empty, else stripped string

        db_manager.add_selection(self.current_project_id, path_for_db, is_dir, category_id, file_types)
        self.load_selected_items() # Refresh list and tree indicators

    def handle_dropped_item_signal(self, path, is_dir):
        normcased_path = os.path.normcase(os.path.normpath(path))
        if not self.current_project_id:
            QMessageBox.warning(self, "No Active Project", "Please select or create a project first.")
            return
        existing_selection = db_manager.get_selection_by_path(self.current_project_id, normcased_path)
        self.add_or_update_selection(normcased_path, is_dir, existing_selection)


    def assign_category_to_selection_dialog(self, path):
        if not self.current_project_id: return

        categories = db_manager.get_categories(self.current_project_id)
        cat_names = ["<No Category>"] + [c['name'] for c in categories] # Add <No Category> option

        current_selection = db_manager.get_selection_by_path(self.current_project_id, path)
        if not current_selection:
            QMessageBox.warning(self, "Error", f"Could not find selection data for path:\n{path}")
            return

        current_cat_id = current_selection['category_id']
        current_idx = 0 # Default to "<No Category>"
        if current_cat_id:
            for i, cat in enumerate(categories): # categories does not include <No Category>
                if cat['id'] == current_cat_id:
                    current_idx = i + 1 # Offset by 1 due to "<No Category>" at index 0 in cat_names
                    break # Found current category, exit loop

        item_display_name = os.path.basename(path)
        if self.current_project_path and path == self.current_project_path : # Check if it's the project root
            item_display_name = ". (Project Root)"

        cat_name, ok = QInputDialog.getItem(self, "Assign Category", f"Category for:\n{item_display_name}",
                                            cat_names, current_idx, False)
        if ok:
            new_category_id = None # Assume <No Category>
            if cat_name != "<No Category>":
                # Find the ID for the selected category name
                for cat in categories:
                    if cat['name'] == cat_name:
                        new_category_id = cat['id']
                        break
            db_manager.update_selection_category(self.current_project_id, path, new_category_id)
            self.load_selected_items() # Refresh list and tree indicators

    def remove_selected_path(self, path):
        if self.current_project_id:
            db_manager.remove_selection(self.current_project_id, path)
            self.load_selected_items() # Refresh list and tree indicators

    def load_selected_items(self):
        self.selected_items_list.clear()
        if not self.current_project_id:
            self._show_preview_for_path(None) # Reset preview title
            self.refresh_file_tree_display_indicators()
            return

        selections = db_manager.get_selections(self.current_project_id)
        for sel_idx, sel in enumerate(selections):
            sel_normcased_path = sel['path'] # This is already normcased from DB

            item_display_path = ""
            # Determine how to display the path (relative, external, etc.)
            if self.current_project_path and os.path.isdir(self.current_project_path):
                if sel_normcased_path == self.current_project_path:
                    item_display_path = "."
                elif sel_normcased_path.startswith(self.current_project_path + os.sep):
                    try:
                        item_display_path = os.path.relpath(sel_normcased_path, self.current_project_path)
                    except ValueError: # Should not happen if startswith is true
                        item_display_path = os.path.basename(sel_normcased_path)
                else: # Path is outside the current project tree structure
                    item_display_path = f"{os.path.basename(sel_normcased_path)} (External to current project tree)"
            else: # No valid current_project_path to make it relative to
                base_name = os.path.basename(sel_normcased_path)
                if sel_normcased_path == base_name: # e.g. "file.txt" (already just a name)
                    item_display_path = base_name
                else: # e.g. "/abs/path/to/file.txt" or "rel/path/file.txt"
                    item_display_path = f"{sel_normcased_path} (Full Path)"


            display_text_final = ""
            if sel['is_directory']:
                file_types_display = sel['file_types'] if sel['file_types'] else "ALL"
                if item_display_path == ".": # Project root selected as directory
                    display_text_final = f". (Dir: {file_types_display})"
                else:
                    display_text_final = f"{item_display_path}{os.sep} (Dir: {file_types_display})"
            else: # It's a file
                display_text_final = item_display_path

            if sel['category_name']:
                display_text_final += f"  [{sel['category_name']}]"

            item = QListWidgetItem(display_text_final)
            item.setData(Qt.UserRole, sel_normcased_path) # Store full normcased path
            item.setToolTip(sel_normcased_path) # Tooltip shows full path
            self.selected_items_list.addItem(item)

        if not selections: # If the list is empty after loading
             self._show_preview_for_path(None) # Reset preview title

        self.refresh_file_tree_display_indicators()


    def selected_item_context_menu(self, position):
        item = self.selected_items_list.itemAt(position)
        if not item or not self.current_project_id: return

        normcased_path_from_user_role = item.data(Qt.UserRole) # Already normcased

        if not normcased_path_from_user_role or not isinstance(normcased_path_from_user_role, str):
            QMessageBox.warning(self, "Error", f"Invalid path data in selected item: {normcased_path_from_user_role}")
            return

        selection_data = db_manager.get_selection_by_path(self.current_project_id, normcased_path_from_user_role)
        # selection_data could be None if item was somehow de-synced, though unlikely with current logic

        menu = QMenu()
        menu_item_display_name = os.path.basename(normcased_path_from_user_role)
        if self.current_project_path and normcased_path_from_user_role == self.current_project_path:
            menu_item_display_name = ". (Project Root)"

        remove_action = menu.addAction(f"Remove '{menu_item_display_name}' from Context")
        remove_action.triggered.connect(lambda checked=False, p=normcased_path_from_user_role: self.remove_selected_path(p))

        if selection_data: # Only add these if we have DB data for the selection
            assign_cat_action = menu.addAction(f"Assign/Change Category for '{menu_item_display_name}'")
            assign_cat_action.triggered.connect(lambda checked=False, p=normcased_path_from_user_role: self.assign_category_to_selection_dialog(p))

            if selection_data['is_directory']:
                edit_types_action = menu.addAction(f"Edit Directory Options for '{menu_item_display_name}'")
                edit_types_action.triggered.connect(lambda checked=False, p=normcased_path_from_user_role, s=selection_data: self.add_or_update_selection(p, True, s))
        else:
            # This case should ideally not be reached if the list is properly synced with the DB.
            print(f"Warning: No DB selection data found for list item: {normcased_path_from_user_role}")


        if menu.isEmpty(): # Should not happen if remove_action was added
            return
        menu.exec(self.selected_items_list.mapToGlobal(position))


    def _is_binary_file_for_preview(self, file_path):
        if any(file_path.lower().endswith(ext) for ext in self.BINARY_EXTENSIONS):
            return True
        try:
            with open(file_path, 'rb') as f_check:
                chunk = f_check.read(1024) # Read a small chunk
                if b'\x00' in chunk: return True # Presence of null byte often indicates binary
        except Exception: return True # Treat as binary if read fails
        return False

    def _read_file_content_for_preview(self, file_path):
        if self._is_binary_file_for_preview(file_path):
            return True, f"File: {os.path.basename(file_path)}\n\n(Binary file, content not displayed)"
        try:
            file_size = os.path.getsize(file_path)
            if file_size > MainWindow.MAX_PREVIEW_SIZE:
                return True, (f"File: {os.path.basename(file_path)}\n\n"
                              f"(File too large: {file_size // (1024*1024)} MB. "
                              f"Max: {MainWindow.MAX_PREVIEW_SIZE // (1024*1024)} MB)")

            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            return False, content
        except UnicodeDecodeError:
            return True, f"File: {os.path.basename(file_path)}\n\n(Cannot decode file - may be binary or non-UTF-8)"
        except Exception as e:
            return True, f"File: {os.path.basename(file_path)}\n\n(Error reading file for preview: {e})"

    def _generate_directory_preview_summary(self, dir_path):
        p = Path(dir_path)
        try:
            num_files, num_subdirs = 0, 0
            ext_counts = collections.defaultdict(int)

            for item in p.rglob('*'): # Iterate recursively
                if item.is_file():
                    num_files += 1
                    ext_counts[item.suffix.lower() if item.suffix else "<no_extension>"] += 1
                elif item.is_dir():
                    num_subdirs += 1

            summary = [f"Directory: {os.path.basename(dir_path)} (at {dir_path})",
                       f"Contains: {num_files} files, {num_subdirs} subdirectories (recursively)."]
            if ext_counts:
                sorted_ext = sorted(ext_counts.items(), key=lambda x: (-x[1], x[0])) # Sort by count desc, then name asc
                summary.append("File types: " + ", ".join([f"{c} {e if e != '<no_extension>' else 'files w/o ext'}" for e, c in sorted_ext]) + ".")
            elif num_files == 0 and num_subdirs == 0:
                 summary.append("This directory is empty.")
            elif num_files == 0: # Has subdirs but no files
                 summary.append("No files found in this directory or subdirectories.")

            return "\n".join(summary)
        except Exception as e:
            return f"Error scanning directory {dir_path}: {e}"


    def _show_preview_for_path(self, path):
        if not self.preview_stack: return # Should not happen if UI is set up

        if self.current_highlighter:
            self.current_highlighter.setDocument(None) # Disconnect old highlighter
            self.current_highlighter = None

        self.image_preview_label.clear()
        self.file_preview_edit.clear()

        # Update preview title label
        if path and os.path.exists(path) and os.path.isfile(path):
            file_name = os.path.basename(path)
            try:
                file_size_bytes = os.path.getsize(path)
                file_size_kb = file_size_bytes / 1024.0
                self.preview_title_label.setText(f"File Preview: {file_name} - {file_size_kb:.2f} KB")
            except OSError: # File might not be accessible (e.g. permissions)
                self.preview_title_label.setText(f"File Preview: {file_name} - (size unavailable)")
        else: # No path, or path is a directory, or path doesn't exist
            self.preview_title_label.setText("File Preview:")


        if not path: # No item selected or invalid path
            self.file_preview_edit.setPlaceholderText("No project selected, or selected item has no preview.")
            if self.current_project_id: # If a project is active, refine placeholder
                 self.file_preview_edit.setPlaceholderText("Click a file or directory in the tree or selected items list to preview its content or summary.")
            self.preview_stack.setCurrentWidget(self.file_preview_edit)
            return

        if not os.path.exists(path):
            self.file_preview_edit.setPlainText(f"Path does not exist: {path}")
            self.preview_stack.setCurrentWidget(self.file_preview_edit)
            return

        _, ext = os.path.splitext(path)
        ext = ext.lower()

        preview_size = self.preview_stack.size() # Get current size of the preview area
        if not (preview_size.isValid() and preview_size.width() > 0 and preview_size.height() > 0):
            preview_size = QSize(300, 300) # Fallback if size is not yet determined

        if os.path.isfile(path):
            if ext in self.RASTER_IMAGE_EXTENSIONS:
                pixmap = QPixmap(path)
                if pixmap.isNull():
                    self.file_preview_edit.setPlainText(f"File: {os.path.basename(path)}\n\n(Error loading image)")
                    self.preview_stack.setCurrentWidget(self.file_preview_edit)
                else:
                    # Scale pixmap if it's larger than the preview area, maintaining aspect ratio
                    if pixmap.width() > preview_size.width() or pixmap.height() > preview_size.height():
                        pixmap = pixmap.scaled(preview_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.image_preview_label.setPixmap(pixmap)
                    self.preview_stack.setCurrentWidget(self.image_preview_label)
                return # Handled image
            elif ext in self.SVG_IMAGE_EXTENSIONS:
                if SVG_SUPPORT_AVAILABLE and QSvgRenderer:
                    renderer = QSvgRenderer(path)
                    if not renderer.isValid():
                        self.file_preview_edit.setPlainText(f"File: {os.path.basename(path)}\n\n(Invalid SVG)")
                        self.preview_stack.setCurrentWidget(self.file_preview_edit)
                    else:
                        svg_size = renderer.defaultSize()
                        if not (svg_size.isValid() and svg_size.width() > 0 and svg_size.height() > 0) :
                            svg_size = preview_size # Default to preview_size if SVG has no intrinsic size

                        target_size = svg_size
                        # Scale SVG if it's larger than the preview area
                        if svg_size.width() > preview_size.width() or svg_size.height() > preview_size.height():
                            target_size = svg_size.scaled(preview_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

                        if not (target_size.isValid() and target_size.width() > 0 and target_size.height() > 0): # Final fallback
                            target_size = QSize(min(preview_size.width(),100), min(preview_size.height(),100)) # Small default

                        img = QPixmap(target_size)
                        img.fill(Qt.transparent) # Ensure transparent background for SVG
                        painter = QPainter(img)
                        renderer.render(painter, QRectF(img.rect())) # Render onto the QPixmap
                        painter.end()
                        self.image_preview_label.setPixmap(img)
                        self.preview_stack.setCurrentWidget(self.image_preview_label)
                else: # SVG Support not available
                    self.file_preview_edit.setPlainText(f"File: {os.path.basename(path)}\n\n(SVG preview unavailable - QtSvg module missing)")
                    self.preview_stack.setCurrentWidget(self.file_preview_edit)
                return # Handled SVG or SVG support missing

            # If not an image, try to read as text
            is_message_only, content = self._read_file_content_for_preview(path)
            self.file_preview_edit.setPlainText(content)
            self.preview_stack.setCurrentWidget(self.file_preview_edit)
            if not is_message_only: # Apply syntax highlighting if it's actual file content
                supported_syntax_extensions = [
                    '.py', '.js', '.dart', '.html', '.htm', '.yaml', '.json', '.txt', '.md',
                    '.java', '.cs', '.cpp', '.c', '.h', '.hpp', '.go', '.php', '.rb', '.swift', '.kt', '.rs'
                    # Add more as needed, ensure they match SyntaxHighlighter keys
                ]
                if ext in supported_syntax_extensions:
                    self.current_highlighter = SyntaxHighlighter(self.file_preview_edit.document(), ext)
        elif os.path.isdir(path):
            self.file_preview_edit.setPlainText(self._generate_directory_preview_summary(path))
            self.preview_stack.setCurrentWidget(self.file_preview_edit)
        else: # Not a file or directory (e.g., broken link, or something else)
            self.file_preview_edit.setPlainText(f"Not a file or directory: {path}")
            self.preview_stack.setCurrentWidget(self.file_preview_edit)

    @Slot(QModelIndex, QModelIndex)
    def _handle_tree_view_selection(self, current: QModelIndex, previous: QModelIndex):
        if current.isValid() and self.fs_model.rootPath() != "": # Ensure a project is loaded
            self._show_preview_for_path(self.fs_model.filePath(current))
        elif not self.fs_model.rootPath(): # No project loaded
             self._show_preview_for_path(None) # Reset preview including title
        # If current is not valid but a project is loaded, it means selection was cleared in tree.
        # In this case, _show_preview_for_path(None) might also be appropriate if desired,
        # or simply do nothing to keep the last preview. Current behavior: if selection invalid, no change.


    @Slot(object, object)
    def _handle_selected_items_list_selection(self, current: QListWidgetItem, previous: QListWidgetItem):
        if current:
            self._show_preview_for_path(current.data(Qt.UserRole)) # Path stored in UserRole
        else: # Selection cleared in the list
            self._show_preview_for_path(None) # Reset preview including title

    def get_effective_selections_for_display(self):
        if not self.current_project_id:
            return []
        category_id_filter = self.export_category_combo.currentData() # This is the ID, or None for "All"
        selections = db_manager.get_selections(self.current_project_id, category_id_filter)
        return selections

    def get_detailed_inclusion_map(self, effective_selections):
        included_files_map = {} # Stores {normcased_abs_path: True}
        for sel_idx, sel in enumerate(effective_selections):
            sel_normcased_path = sel['path'] # Already normcased from DB

            if not os.path.exists(sel_normcased_path):
                continue # Skip if path doesn't exist

            if sel['is_directory']:
                extensions_to_include = []
                exact_filenames_to_include_normcased = []
                include_all_files_in_dir = True # Default if file_types is None or empty

                if sel['file_types']: # If not None and not empty string
                    include_all_files_in_dir = False
                    for ft_item_raw in sel['file_types'].split(','):
                        ft_item = ft_item_raw.strip()
                        if not ft_item: continue
                        if ft_item.startswith('.'): # Assumed to be an extension
                            extensions_to_include.append(ft_item.lower())
                        else: # Assumed to be an exact filename
                            exact_filenames_to_include_normcased.append(os.path.normcase(ft_item))

                for root, dirnames, filenames in os.walk(sel_normcased_path):
                    # Filter out ignored directory names for recursion
                    dirnames[:] = [d for d in dirnames if d not in context_generator.DEFAULT_TREE_IGNORED_NAMES and not d.startswith('.')]

                    for f_name_original_case in filenames:
                        f_path_abs_normcased = os.path.normcase(os.path.normpath(os.path.join(root, f_name_original_case)))
                        f_name_normcased = os.path.normcase(f_name_original_case)

                        should_include_this_file = False
                        if include_all_files_in_dir:
                            should_include_this_file = True
                        else:
                            if f_name_normcased in exact_filenames_to_include_normcased:
                                should_include_this_file = True
                            elif any(f_name_normcased.endswith(ext) for ext in extensions_to_include):
                                should_include_this_file = True

                        if should_include_this_file:
                            included_files_map[f_path_abs_normcased] = True
            else: # It's a file selection
                included_files_map[sel_normcased_path] = True
        return included_files_map


    def refresh_file_tree_display_indicators(self):
        if hasattr(self.fs_model, 'refresh_display_indicators'):
            self.fs_model.refresh_display_indicators()
        elif isinstance(self.fs_model, QFileSystemModel): # Fallback for standard model if custom not used
            # This will trigger a repaint, which is often enough if data() method is simple
            self.fs_model.layoutChanged.emit()


    def drop_context(self):
        if not self.current_project_id or not self.current_project_path:
            QMessageBox.warning(self, "Error", "No active project selected, or project path is invalid.")
            return

        project_data = db_manager.get_project_by_id(self.current_project_id)
        if not project_data or not project_data['path']:
            QMessageBox.critical(self, "Critical Error", "Could not retrieve project path from database.")
            return

        original_project_path_from_db = project_data['path'] # This is os.path.normpath'd
        if not os.path.isdir(original_project_path_from_db):
            QMessageBox.warning(self, "Error", f"Project path is invalid or not a directory: {original_project_path_from_db}")
            return

        prompt_text = self.prompt_edit.toPlainText()
        QGuiApplication.clipboard().setText(prompt_text)

        anchor_widget = self # Default anchor for notification
        if not self.isVisible() or self.isMinimized(): # If main window is hidden/minimized
            if self.hover_widget and self.hover_widget.isVisible():
                anchor_widget = self.hover_widget # Use hover widget as anchor

        export_category_filter_id = self.export_category_combo.currentData() # ID or None
        selections_for_context = db_manager.get_selections(self.current_project_id, export_category_filter_id)

        if not selections_for_context:
            self.notification_widget.show_message(
                "Prompt copied to clipboard.\nNo files/directories selected for context.txt under the current filter.",
                anchor_widget=anchor_widget
            )
            if self.isVisible() and not self.isMinimized(): self.save_gui_position()
            elif self.hover_widget and self.hover_widget.isVisible(): self.hover_widget.save_current_position()
            return

        context_file_leaf_name = "context.txt"
        try:
            # Combine all known "skippable" extensions for context generation
            binary_like_extensions = list(set(
                self.BINARY_EXTENSIONS +
                self.RASTER_IMAGE_EXTENSIONS +
                self.SVG_IMAGE_EXTENSIONS
            ))

            context_lines = context_generator.generate_context_file_data(
                original_project_path_from_db, # Original case project path for display in context.txt
                selections_for_context,        # Paths in selections are normcased
                binary_like_extensions,
                context_file_leaf_name
            )
        except Exception as e:
            QMessageBox.critical(self, "Context Generation Error", f"An error occurred while generating the context data: {e}")
            print(f"Context generation error: {e}")
            return

        context_file_full_path = os.path.join(original_project_path_from_db, context_file_leaf_name)
        try:
            with open(context_file_full_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(context_lines))

            self.notification_widget.show_message(
                f"Context file generated: {context_file_leaf_name}\nPrompt copied to clipboard.",
                anchor_widget=anchor_widget
            )

            self.refresh_file_tree_display_indicators() # Update * in tree
            # Try to select and scroll to the generated context.txt in the tree view
            if self.fs_model and self.tree_view and self.fs_model.rootPath() != "":
                context_file_model_index = self.fs_model.index(context_file_full_path)
                if context_file_model_index.isValid():
                    self.tree_view.setCurrentIndex(context_file_model_index)
                    self.tree_view.scrollTo(context_file_model_index, QAbstractItemView.PositionAtCenter)
                    # Also update preview to show the newly generated context.txt
                    self._show_preview_for_path(context_file_full_path)
                else: # If index is not valid (e.g.
                     # fs_model not fully synced), still try to show preview
                     self._show_preview_for_path(context_file_full_path)

        except Exception as e:
            QMessageBox.critical(self, "Error Saving Context File", f"Could not save '{context_file_leaf_name}': {e}")
            print(f"Error saving '{context_file_leaf_name}': {e}")

        # Save positions after action
        if self.isVisible() and not self.isMinimized(): self.save_gui_position()
        elif self.hover_widget and self.hover_widget.isVisible(): self.hover_widget.save_current_position()


    def collapse_to_hover_icon(self):
        self.save_gui_position() # Save main window pos before hiding
        self.hide()
        db_manager.set_app_setting(LAST_UI_MODE_KEY, 'hover') # Persist current mode

        # Attempt to load hover icon's last saved position
        try:
            hover_x_str = db_manager.get_app_setting(HOVER_POS_X_KEY)
            hover_y_str = db_manager.get_app_setting(HOVER_POS_Y_KEY)
            if hover_x_str is not None and hover_y_str is not None:
                self.hover_widget.move(QPoint(int(hover_x_str), int(hover_y_str)))
            else: # No saved position, center it
                self._center_hover_icon_on_primary_screen()
        except (ValueError, TypeError) as e: # Catch parsing errors
            print(f"Warning: Could not parse saved hover icon position on collapse ({e}). "
"Using default.")
            self._center_hover_icon_on_primary_screen()
        except Exception as e: # Catch any other errors during loading
            print(f"Error loading hover icon position on collapse: {e}. Using default.")
            self._center_hover_icon_on_primary_screen()

        self.hover_widget.show()

    def show_main_window_from_hover(self, hover_screen: QGuiApplication.primaryScreen()): # hover_screen can be None
        if self.hover_widget:
            self.hover_widget.save_current_position() # Save hover icon pos before hiding it
            self.hover_widget.hide()

        db_manager.set_app_setting(LAST_UI_MODE_KEY, 'gui') # Persist current mode
        gui_restored_to_saved_pos = False
        try:
            gui_x_str = db_manager.get_app_setting(GUI_POS_X_KEY)
            gui_y_str = db_manager.get_app_setting(GUI_POS_Y_KEY)
            if gui_x_str is not None and gui_y_str is not None:
                self.move(QPoint(int(gui_x_str), int(gui_y_str)))
                gui_restored_to_saved_pos = True
        except (ValueError, TypeError) as e:
            print(f"Warning: Could not parse saved GUI position on expand ({e}). "
"Using default.")
        except Exception as e:
            print(f"Error loading GUI position on expand: {e}. Using default.")

        if not gui_restored_to_saved_pos:
            target_screen = hover_screen or QGuiApplication.primaryScreen() # Use hover's screen or primary
            if target_screen:
                screen_geometry = target_screen.availableGeometry()
                # Center main window on the target screen
                self.move(screen_geometry.center() - self.rect().center())
            else: # Absolute fallback
                self._center_on_primary_screen()

        self.show()
        self.activateWindow() # Bring to front
        self.raise_()         # Ensure it's on top

    def close_application_from_hover(self):
        if self.hover_widget:
            self.hover_widget.save_current_position() # Save its position even if closing from hover
        self.close() # This will trigger the main window's closeEvent

    def closeEvent(self, event):
        if self.prompt_save_timer.isActive(): # Ensure pending prompt changes are saved
            self.prompt_save_timer.stop()
            self.save_prompt_guide_to_db()

        # Determine which UI mode was last active to save its position and persist the mode
        if self.isVisible() and not self.isMinimized(): # Main GUI is visible
            self.save_gui_position()
            db_manager.set_app_setting(LAST_UI_MODE_KEY, 'gui')
        else: # Main GUI is not visible (either hover icon is active or app was closed while minimized)
            if self.hover_widget and self.hover_widget.isVisible(): # Hover icon is active
                self.hover_widget.save_current_position()
                db_manager.set_app_setting(LAST_UI_MODE_KEY, 'hover')
            else: # Neither is visible (e.g., closed from minimized state or error)
                  # Check last known mode from settings; if it was hover, assume hover pos is more relevant
                  last_known_mode = db_manager.get_app_setting(LAST_UI_MODE_KEY)
                  if last_known_mode == 'hover':
                    # If we have a hover_widget instance, try to save its pos
                    if self.hover_widget: self.hover_widget.save_current_position()
                    # Keep LAST_UI_MODE_KEY as 'hover'
                  else: # Default to saving GUI position and mode 'gui'
                      self.save_gui_position() # Save GUI pos even if it was minimized
                      db_manager.set_app_setting(LAST_UI_MODE_KEY, 'gui')


        if hasattr(self, 'notification_widget') and self.notification_widget:
            self.notification_widget.close() # Clean up notification widget
        if hasattr(self, 'hover_widget') and self.hover_widget: # Hover widget might not be fully closed yet
            # self.hover_widget.close() # Let its own logic handle closing if necessary, or it's already hidden
            pass # Avoid explicitly closing hover_widget here as it might be handled by app quit

        super().closeEvent(event) # Call base class to allow window to close
        if event.isAccepted():    # If close is not vetoed
            QApplication.instance().quit() # Ensure application quits


if __name__ == '__main__':
    app = QApplication(sys.argv)

    icon_path = "contextdropper.png" # Ensure this is in the correct path or use absolute
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    else:
        print(f"Warning: Application icon '{icon_path}' not found.")

    app.setStyle("Fusion") # Consistent style

    # Dark Theme Palette
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.WindowText, Qt.white)
    dark_palette.setColor(QPalette.Base, QColor(35, 35, 35)) # Text edit backgrounds
    dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53)) # List alternate rows
    dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
    dark_palette.setColor(QPalette.ToolTipText, Qt.black)
    dark_palette.setColor(QPalette.Text, Qt.white)
    dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ButtonText, Qt.white)
    dark_palette.setColor(QPalette.BrightText, Qt.red)
    dark_palette.setColor(QPalette.Link, QColor(42, 130, 218)) # Blue for links
    dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218)) # Selection highlight
    dark_palette.setColor(QPalette.HighlightedText, Qt.black) # Text in selection
    dark_palette.setColor(QPalette.PlaceholderText, QColor(128,128,128)) # Placeholder text color
    app.setPalette(dark_palette)

    # Tooltip style (ensure visibility against dark theme if needed)
    app.setStyleSheet("QToolTip { color: #000000; background-color: #ffffff; border: 1px solid black; }")


    # Initialize database (ensure it exists and schema is up-to-date)
    if not os.path.exists(db_manager.DATABASE_NAME):
        print(f"Database '{db_manager.DATABASE_NAME}' not found. Initializing...")
        db_manager.init_db()
    else:
        print(f"Database '{db_manager.DATABASE_NAME}' found. Ensuring schema is up-to-date...")
        db_manager.init_db() # init_db is safe to call multiple times

    window = MainWindow()

    # Determine initial UI mode (GUI or Hover Icon)
    if window.initial_mode == "hover":
        # If starting in hover mode, main window is created but not shown.
        # Instead, collapse immediately to the hover icon.
        window.collapse_to_hover_icon()
    else:
        window.show()

    sys.exit(app.exec())
