import sys
import os
import shutil
import collections # Keep for MainWindow._generate_directory_preview_summary
from pathlib import Path # Keep for MainWindow._generate_directory_preview_summary

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QTreeView, QFileSystemModel,
    QSplitter, QMenu, QInputDialog, QMessageBox, QComboBox,
    QHeaderView,
    QSpacerItem, QSizePolicy, QFileDialog, QAbstractItemView,
    QPlainTextEdit, QStackedWidget
)
from PySide6.QtGui import (
    QAction, QClipboard, QCursor, QGuiApplication, QPalette, QColor, QIcon,
    QPixmap, QPainter
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
    print("WARNING: PySide6.QtSvg module not found. SVG preview will not be available. "
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
            file_path_abs = self.filePath(index)
            normcased_file_path_from_model = os.path.normcase(os.path.normpath(file_path_abs))

            if not self.isDir(index) and self.main_window and self.main_window.current_project_id:
                if self.main_window._selections_for_display_dirty:
                    # print(f"# DEBUG (FSModel.data): Rebuilding inclusion cache...")
                    effective_selections = self.main_window.get_effective_selections_for_display()
                    self._cached_selection_details = self.main_window.get_detailed_inclusion_map(effective_selections)
                    # if self._cached_selection_details:
                    #     print(f"# DEBUG (FSModel.data): Cache rebuilt. {len(self._cached_selection_details)} files marked (normcased).")
                    # else:
                    #     print(f"# DEBUG (FSModel.data): Cache rebuilt. No files marked.")
                    self.main_window._selections_for_display_dirty = False

                if normcased_file_path_from_model in self._cached_selection_details:
                    return f"{original_name} *"
            return original_name
        return super().data(index, role)

    def refresh_display_indicators(self):
        # print("# DEBUG (FSModel): refresh_display_indicators called")
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
        self.current_project_path = None # This will store the normcased project path
        self.current_highlighter = None
        self._selections_for_display_dirty = True
        db_manager.init_db()
        self.setup_ui()
        self.hover_widget = HoverIcon()
        self._load_initial_positions()
        self.load_projects()
        self.load_active_project()
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
                                  self.hover_widget.ICON_AREA_HEIGHT + 2 + 20)
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
            print(f"Warning: Could not parse saved GUI position. Using default.")
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
        top_bar_layout = QHBoxLayout()
        self.project_combo = QComboBox()
        self.project_combo.currentIndexChanged.connect(self.project_selected_by_combo)
        top_bar_layout.addWidget(QLabel("Active Project:"))
        top_bar_layout.addWidget(self.project_combo, 1)
        new_project_button = QPushButton("New Project")
        new_project_button.clicked.connect(self.new_project_dialog)
        top_bar_layout.addWidget(new_project_button)
        delete_project_button = QPushButton("Delete Project")
        delete_project_button.clicked.connect(self.delete_current_project)
        top_bar_layout.addWidget(delete_project_button)
        self.delete_project_button = delete_project_button
        self.manage_cat_button = QPushButton("Manage Categories")
        self.manage_cat_button.clicked.connect(self.manage_categories_dialog)
        top_bar_layout.addWidget(self.manage_cat_button)
        main_layout.addLayout(top_bar_layout)
        splitter = QSplitter(Qt.Horizontal)
        left_pane = QWidget()
        left_layout = QVBoxLayout(left_pane)
        self.fs_model = ContextStatusFileSystemModel(self)
        initial_root_path = QDir.currentPath()
        self.fs_model.setRootPath(initial_root_path)
        self.fs_model.setFilter(QDir.AllDirs | QDir.Files | QDir.NoDotAndDotDot)
        self.tree_view = QTreeView()
        self.tree_view.setModel(self.fs_model)
        self.tree_view.setRootIndex(self.fs_model.index(self.fs_model.rootPath()))
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
        preview_layout.addWidget(QLabel("Preview:"))
        self.preview_stack = QStackedWidget()
        self.file_preview_edit = QPlainTextEdit()
        self.file_preview_edit.setReadOnly(True)
        self.file_preview_edit.setStyleSheet(
            "QPlainTextEdit { background-color: #1E1E1E; color: #D4D4D4; "
            "selection-background-color: #0078D7; selection-color: #FFFFFF; "
            "font-family: 'Consolas', 'Monaco', 'Menlo', 'Courier New', monospace; font-size: 9pt; }"
            "QPlainTextEdit::placeholderText { color: #A0A0A0; }"
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
        main_layout.addWidget(splitter, 1)
        bottom_bar_layout = QHBoxLayout()
        bottom_bar_layout.addWidget(QLabel("Export Category:"))
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
        self._show_preview_for_path(None)
        self.update_ui_for_project_state()

    def on_prompt_text_changed(self):
        if self.current_project_id:
            self.prompt_save_timer.start(1000)

    def save_prompt_guide_to_db(self):
        if self.current_project_id and self.prompt_edit.toPlainText() is not None:
            db_manager.update_project_prompt(self.current_project_id, self.prompt_edit.toPlainText())

    def load_projects(self):
        # print("# DEBUG (MainWindow.load_projects): Called")
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
        # print("# DEBUG (MainWindow.load_active_project): Called")
        active_project_data = db_manager.get_active_project()
        if active_project_data:
            project_id_to_activate = active_project_data['id']
            idx = self.project_combo.findData(project_id_to_activate)
            if idx != -1:
                self.project_combo.setCurrentIndex(idx)
                if self.project_combo.currentIndex() == idx and self.current_project_id != project_id_to_activate:
                    self.update_project_details(project_id_to_activate)
            else:
                self.clear_project_context()
                if self.project_combo.count() > 0 and self.project_combo.itemData(0) is not None:
                    self.project_combo.setCurrentIndex(0)
        elif self.project_combo.count() > 0 and self.project_combo.itemData(0) is not None:
            self.project_combo.setCurrentIndex(0)
        else:
            self.clear_project_context()

    def project_selected_by_combo(self, index):
        project_id = self.project_combo.itemData(index)
        # print(f"# DEBUG (MainWindow.project_selected_by_combo): Project ID: {project_id}")
        self.update_project_details(project_id)

    def update_project_details(self, project_id):
        # print(f"# DEBUG (MainWindow.update_project_details): Project ID: {project_id}")
        if project_id is None:
            self.clear_project_context()
            return

        project = db_manager.get_project_by_id(project_id)
        if project:
            self.current_project_id = project['id']
            self.current_project_path = os.path.normcase(os.path.normpath(project['path']))
            # print(f"# DEBUG (MainWindow.update_project_details): Set current_project_path to (normcased): '{self.current_project_path}'")

            self.prompt_edit.blockSignals(True)
            self.prompt_edit.setText(project['prompt_guide'] or "")
            self.prompt_edit.blockSignals(False)

            if os.path.isdir(project['path']): # Check original path for isdir
                self.fs_model.setRootPath(project['path'])
                self.tree_view.setRootIndex(self.fs_model.index(project['path']))
            else:
                QMessageBox.warning(self, "Project Path Error",
                                    f"Project path not found: {project['path']}\n"
                                    "Reverting to default. Update project settings.")
                fallback_path = QDir.currentPath()
                self.fs_model.setRootPath(fallback_path)
                self.tree_view.setRootIndex(self.fs_model.index(fallback_path))
            db_manager.set_active_project(self.current_project_id)
        else:
            self.clear_project_context()

        self.update_ui_for_project_state()
        self.load_selected_items()
        self.load_categories_for_export()
        self._show_preview_for_path(None)

    def clear_project_context(self):
        # print("# DEBUG (MainWindow.clear_project_context): Called")
        self.current_project_id = None
        new_root_path = QDir.currentPath()
        self.current_project_path = os.path.normcase(os.path.normpath(new_root_path))
        self.prompt_edit.blockSignals(True)
        self.prompt_edit.clear()
        self.prompt_edit.blockSignals(False)
        self.fs_model.setRootPath(new_root_path)
        self.tree_view.setRootIndex(self.fs_model.index(new_root_path))
        db_manager.set_active_project(None)
        self.update_ui_for_project_state()
        self.load_selected_items()
        self.load_categories_for_export()
        self._show_preview_for_path(None)

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
                        self.project_combo.setCurrentIndex(idx)
                else:
                    QMessageBox.warning(self, "Error", f"Could not create project '{name}'. It might already exist.")
        elif ok and not name.strip():
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
            self.load_projects()
            self.load_active_project()

    def manage_categories_dialog(self):
        if not self.current_project_id:
            QMessageBox.information(self, "No Project", "Please select or create a project first.")
            return
        dialog = ManageCategoriesDialog(self.current_project_id, parent_main_window=self)
        dialog.exec()
        # print("# DEBUG (MainWindow.manage_categories_dialog): Dialog closed, refreshing tree indicators.")
        self.refresh_file_tree_display_indicators()

    def load_categories_for_export(self):
        # print("# DEBUG (MainWindow.load_categories_for_export): Called")
        self.export_category_combo.blockSignals(True)
        self.export_category_combo.clear()
        self.export_category_combo.addItem("All Categories", None)
        if self.current_project_id:
            categories = db_manager.get_categories(self.current_project_id)
            for cat in categories:
                self.export_category_combo.addItem(cat['name'], cat['id'])
        self.export_category_combo.blockSignals(False)
        self.refresh_file_tree_display_indicators()

    def update_ui_for_project_state(self):
        has_project = self.current_project_id is not None
        self.prompt_edit.setEnabled(has_project)
        self.selected_items_list.setEnabled(has_project)
        self.drop_context_button.setEnabled(has_project)
        if hasattr(self, 'preview_stack'):
            self.preview_stack.setEnabled(has_project)
        if hasattr(self, 'delete_project_button'):
            self.delete_project_button.setEnabled(has_project)
        if hasattr(self, 'manage_cat_button'):
            self.manage_cat_button.setEnabled(has_project)
        self.export_category_combo.setEnabled(has_project)

    def tree_context_menu(self, position):
        if not self.current_project_id: return
        index = self.tree_view.indexAt(position)
        menu = QMenu()
        if not index.isValid():
            if self.current_project_path and os.path.isdir(self.current_project_path):
                root_path_for_db = self.current_project_path # Already normcased
                existing_root_selection = db_manager.get_selection_by_path(self.current_project_id, root_path_for_db)
                if existing_root_selection:
                    menu.addAction("Project Root (.) Options", lambda: self.add_or_update_selection(root_path_for_db, True, existing_root_selection))
                    menu.addAction("Assign/Change Category for Project Root (.)", lambda: self.assign_category_to_selection_dialog(root_path_for_db))
                    menu.addAction("Remove Project Root (.) from Context", lambda: self.remove_selected_path(root_path_for_db))
                else:
                    menu.addAction("Add Project Root (.) to Context", lambda: self.add_or_update_selection(root_path_for_db, True, None))
        else:
            path_from_model = self.fs_model.filePath(index)
            normcased_path = os.path.normcase(os.path.normpath(path_from_model))
            is_dir = self.fs_model.isDir(index)
            existing_selection = db_manager.get_selection_by_path(self.current_project_id, normcased_path)
            if existing_selection:
                action_text = "Directory Options (File Types)" if is_dir else "Item Options"
                menu.addAction(action_text, lambda: self.add_or_update_selection(normcased_path, is_dir, existing_selection))
                menu.addAction("Assign/Change Category", lambda: self.assign_category_to_selection_dialog(normcased_path))
                menu.addAction("Remove from Context", lambda: self.remove_selected_path(normcased_path))
            else:
                action_text = "Add Directory to Context" if is_dir else "Add File to Context"
                menu.addAction(action_text, lambda: self.add_or_update_selection(normcased_path, is_dir))
        if not menu.isEmpty():
            menu.exec(self.tree_view.viewport().mapToGlobal(position))

    def add_or_update_selection(self, path, is_dir, existing_selection=None):
        # print(f"# DEBUG (MainWindow.add_or_update_selection): Path: '{path}', IsDir: {is_dir}")
        if not self.current_project_id:
            QMessageBox.warning(self, "No Project Active", "Cannot add selection: no project is active.")
            return
        file_types = None
        category_id = existing_selection['category_id'] if existing_selection else None
        path_for_db = os.path.normcase(os.path.normpath(path)) # Ensure it's normcased for DB

        if is_dir:
            current_types = ""
            if existing_selection and existing_selection['file_types']:
                current_types = existing_selection['file_types']
            elif not existing_selection: # Default types for new directory selections
                current_types = ".py,.js,.dart,.html,.htm,.yaml,.json,.txt,.md,.h,.hpp,.cs,.java,.go,.php,.rb,.swift,.kt,.rs,CMakeLists.txt,Makefile,Dockerfile"
            types_str, ok = QInputDialog.getText(self, "Include File Types (Directory)",
                                                 "Comma-separated (e.g., .py,.txt) or exact filenames.\nEmpty for ALL files (recursive).",
                                                 text=current_types)
            if not ok: return
            file_types = types_str.strip() if types_str.strip() else None
        db_manager.add_selection(self.current_project_id, path_for_db, is_dir, category_id, file_types)
        self.load_selected_items()

    def handle_dropped_item_signal(self, path, is_dir):
        normcased_path = os.path.normcase(os.path.normpath(path))
        # print(f"# DEBUG (MainWindow.handle_dropped_item_signal): Path: '{path}', Normcased: '{normcased_path}', IsDir: {is_dir}")
        if not self.current_project_id:
            QMessageBox.warning(self, "No Active Project", "Please select or create a project first.")
            return
        existing_selection = db_manager.get_selection_by_path(self.current_project_id, normcased_path)
        self.add_or_update_selection(normcased_path, is_dir, existing_selection)

    def assign_category_to_selection_dialog(self, path):
        # print(f"# DEBUG (MainWindow.assign_category_to_selection_dialog): Path (normcased): '{path}'")
        if not self.current_project_id: return
        categories = db_manager.get_categories(self.current_project_id)
        cat_names = ["<No Category>"] + [c['name'] for c in categories]
        current_selection = db_manager.get_selection_by_path(self.current_project_id, path) # path is already normcased
        if not current_selection:
            QMessageBox.warning(self, "Error", f"Could not find selection data for path:\n{path}")
            return
        current_cat_id = current_selection['category_id']
        current_idx = 0
        if current_cat_id:
            for i, cat in enumerate(categories):
                if cat['id'] == current_cat_id:
                    current_idx = i + 1; break
        item_display_name = os.path.basename(path)
        if path == self.current_project_path : # self.current_project_path is normcased
            item_display_name = ". (Project Root)"
        cat_name, ok = QInputDialog.getItem(self, "Assign Category", f"Category for:\n{item_display_name}",
                                            cat_names, current_idx, False)
        if ok:
            new_category_id = None
            if cat_name != "<No Category>":
                for cat in categories:
                    if cat['name'] == cat_name: new_category_id = cat['id']; break
            db_manager.update_selection_category(self.current_project_id, path, new_category_id) # path is normcased
            self.load_selected_items()

    def remove_selected_path(self, path):
        # print(f"# DEBUG (MainWindow.remove_selected_path): Path (normcased): '{path}'")
        if self.current_project_id:
            db_manager.remove_selection(self.current_project_id, path) # path is normcased
            self.load_selected_items()

    def load_selected_items(self):
        # print("# DEBUG (MainWindow.load_selected_items): Called")
        self.selected_items_list.clear()
        if not self.current_project_id:
            self._show_preview_for_path(None)
            self.refresh_file_tree_display_indicators()
            return

        selections = db_manager.get_selections(self.current_project_id) # Gets normcased paths
        # print(f"# DEBUG (MainWindow.load_selected_items): Fetched {len(selections)} selections from DB.")
        from PySide6.QtWidgets import QListWidgetItem # Keep local import
        for sel_idx, sel in enumerate(selections):
            sel_normcased_path = sel['path'] # This is already normcased from DB
            # print(f"# DEBUG (MainWindow.load_selected_items): Item {sel_idx}: DB path (normcased)='{sel_normcased_path}'")

            item_display_path = ""
            if self.current_project_path and os.path.isdir(self.current_project_path): # self.current_project_path is normcased
                if sel_normcased_path == self.current_project_path: item_display_path = "."
                elif sel_normcased_path.startswith(self.current_project_path + os.sep):
                    try: item_display_path = os.path.relpath(sel_normcased_path, self.current_project_path)
                    except ValueError: item_display_path = os.path.basename(sel_normcased_path) # Fallback if relpath fails
                else: item_display_path = f"{os.path.basename(sel_normcased_path)} (External)" # Should be rare now
            else: # Fallback if project path isn't set or valid
                item_display_path = os.path.basename(sel_normcased_path)

            display_text_final = ""
            if sel['is_directory']:
                file_types_display = sel['file_types'] if sel['file_types'] else "ALL"
                if item_display_path == ".": display_text_final = f". (Dir: {file_types_display})"
                else: display_text_final = f"{item_display_path}{os.sep} (Dir: {file_types_display})"
            else: display_text_final = item_display_path
            
            # --- MODIFICATION START ---
            if sel['category_name']: # Only add category if it exists
                display_text_final += f"  [{sel['category_name']}]"
            # --- MODIFICATION END ---

            item = QListWidgetItem(display_text_final)
            item.setData(Qt.UserRole, sel_normcased_path) # Store normcased path
            item.setToolTip(sel_normcased_path) # Show full normcased path on hover
            self.selected_items_list.addItem(item)
        
        if not selections: # If list is empty after loading
             self._show_preview_for_path(None) # Clear preview

        self.refresh_file_tree_display_indicators()


    def selected_item_context_menu(self, position):
        item = self.selected_items_list.itemAt(position)
        if not item or not self.current_project_id: return

        normcased_path_from_user_role = item.data(Qt.UserRole) # This is normcased
        # print(f"# DEBUG (MainWindow.selected_item_context_menu): Path from UserRole (normcased): '{normcased_path_from_user_role}'")

        if not normcased_path_from_user_role or not isinstance(normcased_path_from_user_role, str):
             QMessageBox.warning(self, "Error", f"Invalid path data in selected item: {normcased_path_from_user_role}")
             return

        selection_data = db_manager.get_selection_by_path(self.current_project_id, normcased_path_from_user_role)
        # print(f"# DEBUG (MainWindow.selected_item_context_menu): DB query for normcased path '{normcased_path_from_user_role}' returned: {selection_data}")

        menu = QMenu()
        menu_item_display_name = os.path.basename(normcased_path_from_user_role)
        if normcased_path_from_user_role == self.current_project_path: # self.current_project_path is normcased
             menu_item_display_name = ". (Project Root)"

        # Always allow removal
        remove_action = menu.addAction(f"Remove '{menu_item_display_name}' from Context")
        remove_action.triggered.connect(lambda: self.remove_selected_path(normcased_path_from_user_role))

        if selection_data: # Only add other options if we have full selection data
            assign_cat_action = menu.addAction(f"Assign/Change Category for '{menu_item_display_name}'")
            assign_cat_action.triggered.connect(lambda: self.assign_category_to_selection_dialog(normcased_path_from_user_role))
            if selection_data['is_directory']:
                edit_types_action = menu.addAction(f"Edit Directory Options for '{menu_item_display_name}'")
                edit_types_action.triggered.connect(lambda: self.add_or_update_selection(normcased_path_from_user_role, True, selection_data))
        else:
            # This case implies an issue, e.g., item in list but not in DB (should be rare)
            # The "Remove" action is still available.
            # A warning might have already been shown if `get_selection_by_path` returned None and was critical.
            # For the context menu, just providing "Remove" is a safe fallback.
            print(f"# WARNING (MainWindow.selected_item_context_menu): No full selection data for '{normcased_path_from_user_role}'. Offering limited menu.")


        if menu.isEmpty(): # Should not happen if Remove is always added
            return

        menu.exec(self.selected_items_list.mapToGlobal(position))


    def _is_binary_file_for_preview(self, file_path):
        if any(file_path.lower().endswith(ext) for ext in self.BINARY_EXTENSIONS):
            return True
        try:
            with open(file_path, 'rb') as f_check:
                chunk = f_check.read(1024)
                if b'\x00' in chunk: return True
        except Exception: return True # If we can't even check, assume binary to be safe
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
            # Attempt to read with UTF-8, replace errors
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            return False, content
        except UnicodeDecodeError:
            return True, f"File: {os.path.basename(file_path)}\n\n(Cannot decode file - may be binary or non-UTF-8)"
        except Exception as e:
            return True, f"File: {os.path.basename(file_path)}\n\n(Error reading file for preview: {e})"

    def _generate_directory_preview_summary(self, dir_path):
        p = Path(dir_path) # Use pathlib for easier traversal
        try:
            num_files, num_subdirs = 0, 0
            ext_counts = collections.defaultdict(int)
            # Recursively iterate through all items in the directory
            for item in p.rglob('*'): # rglob for recursive
                if item.is_file():
                    num_files += 1
                    ext_counts[item.suffix.lower() if item.suffix else "<no_extension>"] += 1
                elif item.is_dir():
                    num_subdirs += 1
            
            summary = [f"Directory: {os.path.basename(dir_path)} (at {dir_path})",
                       f"Contains: {num_files} files, {num_subdirs} subdirectories (recursively)."]
            if ext_counts:
                # Sort extensions by count (desc) then name (asc)
                sorted_ext = sorted(ext_counts.items(), key=lambda x: (-x[1], x[0]))
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
        # Clear previous syntax highlighter if any
        if self.current_highlighter:
            self.current_highlighter.setDocument(None)
            self.current_highlighter = None
        
        self.image_preview_label.clear() # Clear image preview
        self.file_preview_edit.clear()   # Clear text preview

        if not path:
            self.file_preview_edit.setPlaceholderText("Click a file or directory in the tree or selected items list to preview its content or summary.")
            self.preview_stack.setCurrentWidget(self.file_preview_edit)
            return

        if not os.path.exists(path):
            self.file_preview_edit.setPlainText(f"Path does not exist: {path}")
            self.preview_stack.setCurrentWidget(self.file_preview_edit)
            return

        _, ext = os.path.splitext(path)
        ext = ext.lower() # Normalize extension to lowercase

        # Get the current size of the preview area for scaling images
        preview_size = self.preview_stack.size() # This is the QStackedWidget's size
        if not (preview_size.isValid() and preview_size.width() > 0 and preview_size.height() > 0):
            # Fallback if size is not yet determined (e.g., during init)
            preview_size = QSize(300, 300) # A reasonable default

        if os.path.isfile(path):
            # Handle Raster Images (PNG, JPG, etc.)
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
                return

            # Handle SVG Images
            elif ext in self.SVG_IMAGE_EXTENSIONS:
                if SVG_SUPPORT_AVAILABLE and QSvgRenderer:
                    renderer = QSvgRenderer(path)
                    if not renderer.isValid():
                        self.file_preview_edit.setPlainText(f"File: {os.path.basename(path)}\n\n(Invalid SVG)")
                        self.preview_stack.setCurrentWidget(self.file_preview_edit)
                    else:
                        svg_size = renderer.defaultSize()
                        if not (svg_size.isValid() and svg_size.width() > 0 and svg_size.height() > 0) :
                            svg_size = preview_size # Use preview area size if SVG has no default

                        # Determine target size for rendering, scaled to fit preview_size
                        target_size = svg_size
                        if svg_size.width() > preview_size.width() or svg_size.height() > preview_size.height():
                            target_size = svg_size.scaled(preview_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        
                        if not (target_size.isValid() and target_size.width() > 0 and target_size.height() > 0):
                            target_size = QSize(min(preview_size.width(),100), min(preview_size.height(),100))


                        img = QPixmap(target_size)
                        img.fill(Qt.transparent) # Ensure transparent background for SVG
                        painter = QPainter(img)
                        renderer.render(painter, QRectF(img.rect())) # Render onto QPixmap
                        painter.end()
                        self.image_preview_label.setPixmap(img)
                        self.preview_stack.setCurrentWidget(self.image_preview_label)
                else: # SVG support not available
                    self.file_preview_edit.setPlainText(f"File: {os.path.basename(path)}\n\n(SVG preview unavailable - QtSvg module missing)")
                    self.preview_stack.setCurrentWidget(self.file_preview_edit)
                return

            # Handle Text-based files
            is_message_only, content = self._read_file_content_for_preview(path)
            self.file_preview_edit.setPlainText(content)
            self.preview_stack.setCurrentWidget(self.file_preview_edit)
            if not is_message_only: # If actual content was read (not a binary/error message)
                # Apply syntax highlighting if it's a supported text file type
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
        else: # Not a file or directory (e.g., broken symlink)
            self.file_preview_edit.setPlainText(f"Not a file or directory: {path}")
            self.preview_stack.setCurrentWidget(self.file_preview_edit)

    @Slot(QModelIndex, QModelIndex)
    def _handle_tree_view_selection(self, current, previous):
        if current.isValid():
            self._show_preview_for_path(self.fs_model.filePath(current))

    @Slot(object, object) # QListWidgetItem, QListWidgetItem
    def _handle_selected_items_list_selection(self, current, previous):
        if current: # current is QListWidgetItem
            self._show_preview_for_path(current.data(Qt.UserRole)) # UserRole stores the path
        else: # No item selected
            self._show_preview_for_path(None)


    def get_effective_selections_for_display(self):
        # print("# DEBUG (MainWindow.get_effective_selections_for_display): Called")
        if not self.current_project_id:
            return []
        
        category_id_filter = self.export_category_combo.currentData() # This can be None for "All Categories"
        # print(f"# DEBUG (MainWindow.get_effective_selections_for_display): Export Category ID Filter: {category_id_filter}")
        
        # Fetch selections. If category_id_filter is None, db_manager.get_selections should handle it
        # by returning all selections for the project. If it's an ID, it filters by that ID.
        selections = db_manager.get_selections(self.current_project_id, category_id_filter)
        # print(f"# DEBUG (MainWindow.get_effective_selections_for_display): Found {len(selections)} selections (paths are normcased).")
        return selections


    def get_detailed_inclusion_map(self, effective_selections):
        # print(f"# DEBUG (MainWindow.get_detailed_inclusion_map): Called with {len(effective_selections)} selections.")
        included_files_map = {} # Stores {normcased_absolute_file_path: True}
        
        # Ensure current_project_path is valid before proceeding, as it's used for os.walk context
        # However, selections can be outside the project path, so this check is more about context.
        if not self.current_project_path or not os.path.isdir(self.current_project_path): # current_project_path is normcased
            # This doesn't necessarily mean an error if all selections are external,
            # but os.walk behavior on a non-existent path would be problematic.
            # The primary loop iterates `effective_selections`, which handles paths directly.
            # print(f"# DEBUG (MainWindow.get_detailed_inclusion_map): Project path '{self.current_project_path}' not valid or not a dir. Proceeding with selection paths directly.")
            pass # Continue, as individual selection paths are checked.

        for sel_idx, sel in enumerate(effective_selections):
            sel_normcased_path = sel['path'] # Already normcased from DB
            # print(f"# DEBUG (MainWindow.get_detailed_inclusion_map): Processing selection {sel_idx}: '{sel_normcased_path}', IsDir: {sel['is_directory']}")

            if not os.path.exists(sel_normcased_path): # Critical check for each selection
                # print(f"# WARNING (MainWindow.get_detailed_inclusion_map): Path for selection {sel_idx} ('{sel_normcased_path}') does not exist. Skipping.")
                continue

            if sel['is_directory']:
                # Parse file_types string for this directory selection
                extensions_to_include = []
                exact_filenames_to_include_normcased = []
                include_all_files = True # Default if file_types is None or empty

                if sel['file_types']: # If not None and not empty string
                    include_all_files = False # Specific filters are present
                    for ft_item_raw in sel['file_types'].split(','):
                        ft_item = ft_item_raw.strip()
                        if not ft_item: continue # Skip empty parts
                        if ft_item.startswith('.'):
                            extensions_to_include.append(ft_item.lower()) # Store extensions lowercase
                        else:
                            exact_filenames_to_include_normcased.append(os.path.normcase(ft_item))
                    # print(f"# DEBUG (MainWindow.get_detailed_inclusion_map): Dir '{sel_normcased_path}' filters: Exts={extensions_to_include}, Names={exact_filenames_to_include_normcased}")


                # Walk the directory (using the normcased path from selection)
                for root, dirnames, filenames in os.walk(sel_normcased_path):
                    # Filter out commonly ignored directory names from further traversal
                    # This is for os.walk's own traversal, not for the context.txt tree summary.
                    # context_generator.DEFAULT_TREE_IGNORED_NAMES is used for the summary.
                    # A similar list might be useful here if certain subdirs should always be skipped for content.
                    dirnames[:] = [d for d in dirnames if d not in context_generator.DEFAULT_TREE_IGNORED_NAMES and not d.startswith('.')]

                    for f_name_original_case in filenames:
                        f_path_abs_normcased = os.path.normcase(os.path.normpath(os.path.join(root, f_name_original_case)))
                        f_name_normcased = os.path.normcase(f_name_original_case) # Normcase filename for matching

                        should_include_this_file = False
                        if include_all_files:
                            should_include_this_file = True
                        else:
                            if f_name_normcased in exact_filenames_to_include_normcased:
                                should_include_this_file = True
                            elif any(f_name_normcased.endswith(ext) for ext in extensions_to_include):
                                should_include_this_file = True
                        
                        if should_include_this_file:
                            included_files_map[f_path_abs_normcased] = True
                            # print(f"# DEBUG (MainWindow.get_detailed_inclusion_map): Added file by dir filter: '{f_path_abs_normcased}'")
            
            else: # It's a single file selection
                included_files_map[sel_normcased_path] = True # Add the normcased path of the file
                # print(f"# DEBUG (MainWindow.get_detailed_inclusion_map): Added single file: '{sel_normcased_path}'")
        
        # print(f"# DEBUG (MainWindow.get_detailed_inclusion_map): Total {len(included_files_map)} unique files marked for inclusion.")
        return included_files_map


    def refresh_file_tree_display_indicators(self):
        # print("# DEBUG (MainWindow.refresh_file_tree_display_indicators): Called")
        if hasattr(self.fs_model, 'refresh_display_indicators'):
            self.fs_model.refresh_display_indicators() # Call custom method if exists
        elif isinstance(self.fs_model, QFileSystemModel): # Fallback for standard model
            self.fs_model.layoutChanged.emit() # Generic way to request a refresh


    def drop_context(self):
        if not self.current_project_id or not self.current_project_path: # current_project_path is normcased
            QMessageBox.warning(self, "Error", "No active project selected.")
            return

        # Fetch the original-case project path from DB for file operations
        project_data = db_manager.get_project_by_id(self.current_project_id)
        if not project_data or not project_data['path']:
            QMessageBox.critical(self, "Critical Error", "Could not retrieve project path from database.")
            return
        original_project_path_from_db = project_data['path'] # This is the original case path

        if not os.path.isdir(original_project_path_from_db):
            QMessageBox.warning(self, "Error", f"Project path is invalid or not a directory: {original_project_path_from_db}")
            return

        prompt_text = self.prompt_edit.toPlainText()
        QGuiApplication.clipboard().setText(prompt_text)

        # Determine anchor for notification (main window or hover icon)
        anchor_widget = self
        if not self.isVisible() or self.isMinimized():
            if self.hover_widget and self.hover_widget.isVisible():
                anchor_widget = self.hover_widget

        # Get selections based on the current export category filter
        export_category_filter_id = self.export_category_combo.currentData() # Can be None for "All"
        selections_for_context = db_manager.get_selections(self.current_project_id, export_category_filter_id)
        # These selections from DB have normcased paths.

        if not selections_for_context:
            self.notification_widget.show_message(
                "Prompt copied to clipboard.\nNo files/directories selected for context.txt under the current filter.",
                anchor_widget=anchor_widget
            )
            # Save positions even if no context file is generated
            if self.isVisible() and not self.isMinimized(): self.save_gui_position()
            elif self.hover_widget and self.hover_widget.isVisible(): self.hover_widget.save_current_position() # Use hover_widget's own save
            return

        context_file_leaf_name = "context.txt"
        try:
            # Consolidate all binary-like extensions
            binary_like_extensions = list(set(
                self.BINARY_EXTENSIONS + 
                self.RASTER_IMAGE_EXTENSIONS + 
                self.SVG_IMAGE_EXTENSIONS
            ))

            # Generate context file data
            # Pass the original-case project path for context_generator, as it might be used for display or relative path construction
            # Selections still contain normcased paths for internal logic.
            context_lines = context_generator.generate_context_file_data(
                original_project_path_from_db, 
                selections_for_context, # These have normcased paths
                binary_like_extensions,
                context_file_leaf_name
            )
        except Exception as e:
            QMessageBox.critical(self, "Context Generation Error", f"An error occurred while generating the context data: {e}")
            print(f"Context generation error: {e}")
            return

        # Define full path for context.txt using the original-case project path
        context_file_full_path = os.path.join(original_project_path_from_db, context_file_leaf_name)

        try:
            with open(context_file_full_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(context_lines))
            
            self.notification_widget.show_message(
                f"Context file generated: {context_file_leaf_name}\nPrompt copied to clipboard.",
                anchor_widget=anchor_widget
            )
            
            # Refresh file tree to show the new/updated context.txt
            self.refresh_file_tree_display_indicators() # General refresh for asterisks
            
            # Attempt to select and scroll to the generated context.txt in the tree view
            if self.fs_model and self.tree_view:
                # We need the model index for the original-case path
                context_file_model_index = self.fs_model.index(context_file_full_path)
                if context_file_model_index.isValid():
                    self.tree_view.setCurrentIndex(context_file_model_index)
                    self.tree_view.scrollTo(context_file_model_index, QAbstractItemView.PositionAtCenter)
                    # Also trigger preview update for the newly selected context.txt
                    self._show_preview_for_path(context_file_full_path) 
                else:
                    # If index not found (e.g., tree not fully populated or path issue),
                    # still try to show preview directly.
                    # print(f"Info: context.txt index not found for: '{context_file_full_path}'. Forcing preview.")
                    self._show_preview_for_path(context_file_full_path)

        except Exception as e:
            QMessageBox.critical(self, "Error Saving Context File", f"Could not save '{context_file_leaf_name}': {e}")
            print(f"Error saving '{context_file_leaf_name}': {e}")

        # Save positions after action
        if self.isVisible() and not self.isMinimized(): self.save_gui_position()
        elif self.hover_widget and self.hover_widget.isVisible(): self.hover_widget.save_current_position()


    def collapse_to_hover_icon(self):
        self.save_gui_position() # Save main window position before hiding
        self.hide()
        db_manager.set_app_setting(LAST_UI_MODE_KEY, 'hover') # Record that we are in hover mode

        # Try to load and set the hover icon's last known position
        try:
            hover_x_str = db_manager.get_app_setting(HOVER_POS_X_KEY)
            hover_y_str = db_manager.get_app_setting(HOVER_POS_Y_KEY)
            if hover_x_str is not None and hover_y_str is not None:
                self.hover_widget.move(QPoint(int(hover_x_str), int(hover_y_str)))
            else:
                self._center_hover_icon_on_primary_screen() # Fallback to centering
        except (ValueError, TypeError) as e:
            print(f"Warning: Could not parse saved hover icon position on collapse ({e}). Using default.")
            self._center_hover_icon_on_primary_screen()
        except Exception as e: # Catch any other potential errors during position loading
            print(f"Error loading hover icon position on collapse: {e}. Using default.")
            self._center_hover_icon_on_primary_screen()
        
        self.hover_widget.show()

    def show_main_window_from_hover(self, hover_screen): # hover_screen is QScreen object
        if self.hover_widget:
            self.hover_widget.save_current_position() # Save hover icon's position before hiding it
            self.hover_widget.hide()
        
        db_manager.set_app_setting(LAST_UI_MODE_KEY, 'gui') # Record that we are in GUI mode

        # Try to load and set the main GUI's last known position
        gui_restored_to_saved_pos = False
        try:
            gui_x_str = db_manager.get_app_setting(GUI_POS_X_KEY)
            gui_y_str = db_manager.get_app_setting(GUI_POS_Y_KEY)
            if gui_x_str is not None and gui_y_str is not None:
                self.move(QPoint(int(gui_x_str), int(gui_y_str)))
                gui_restored_to_saved_pos = True
        except (ValueError, TypeError) as e:
            print(f"Warning: Could not parse saved GUI position on expand ({e}). Using default.")
        except Exception as e:
            print(f"Error loading GUI position on expand: {e}. Using default.")

        if not gui_restored_to_saved_pos:
            # Fallback positioning logic if saved position wasn't loaded
            target_screen = hover_screen or QGuiApplication.primaryScreen() # Use provided screen or primary
            if target_screen:
                screen_geometry = target_screen.availableGeometry()
                # Center the window on the target screen
                self.move(screen_geometry.center() - self.rect().center())
            else:
                self._center_on_primary_screen() # Absolute fallback

        self.show()
        self.activateWindow() # Bring to front
        self.raise_()         # Ensure it's on top of other windows


    def close_application_from_hover(self):
        if self.hover_widget:
            self.hover_widget.save_current_position() # Save hover icon position
        self.close() # Trigger the main window's closeEvent

    def closeEvent(self, event):
        # Ensure any pending prompt guide changes are saved
        if self.prompt_save_timer.isActive():
            self.prompt_save_timer.stop()
            self.save_prompt_guide_to_db()

        # Save current UI state (position and mode)
        if self.isVisible() and not self.isMinimized(): # If main GUI is visible
            self.save_gui_position()
            db_manager.set_app_setting(LAST_UI_MODE_KEY, 'gui')
        else: # If main GUI is hidden (implies hover icon was likely active or app was minimized)
            if self.hover_widget and self.hover_widget.isVisible(): # If hover icon is explicitly visible
                 self.hover_widget.save_current_position() # Use hover_widget's own save
                 db_manager.set_app_setting(LAST_UI_MODE_KEY, 'hover')
            else: # Main window hidden, hover icon also hidden (e.g. minimized from hover)
                  # We need to decide what the 'last mode' should be.
                  # If it was previously 'hover', keep it as 'hover'. Otherwise, 'gui'.
                  last_known_mode = db_manager.get_app_setting(LAST_UI_MODE_KEY)
                  if last_known_mode == 'hover':
                      # If it was hover mode, ensure hover position is saved (might be redundant but safe)
                      self.save_hover_icon_position() # MainWindow saves its knowledge of hover pos
                  else: # Default to saving GUI position and mode if last mode wasn't explicitly hover
                      self.save_gui_position()
                      db_manager.set_app_setting(LAST_UI_MODE_KEY, 'gui')


        # Clean up child widgets that might persist
        if hasattr(self, 'notification_widget') and self.notification_widget:
            self.notification_widget.close() # Ensure notification is closed
        
        if hasattr(self, 'hover_widget') and self.hover_widget:
            # self.hover_widget.close() # This might re-trigger saves, let QApplication handle its closure
            pass


        super().closeEvent(event) # Call base class closeEvent
        if event.isAccepted():
            QApplication.instance().quit() # Ensure application quits fully


if __name__ == '__main__':
    app = QApplication(sys.argv)

    # Set application icon
    icon_path = "contextdropper.png" # Ensure this icon exists or handle absence
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    else:
        print(f"Warning: Application icon '{icon_path}' not found.")

    # Apply a base style (Fusion is good for consistency across platforms)
    app.setStyle("Fusion")

    # Dark theme palette (example, can be customized further)
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.WindowText, Qt.white)
    dark_palette.setColor(QPalette.Base, QColor(35, 35, 35)) # Background for text entry widgets
    dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53)) # Used for alternating row colors
    dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
    dark_palette.setColor(QPalette.ToolTipText, Qt.black) # Ensure tooltip text is readable
    dark_palette.setColor(QPalette.Text, Qt.white)
    dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ButtonText, Qt.white)
    dark_palette.setColor(QPalette.BrightText, Qt.red)
    dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218)) # Selection color
    dark_palette.setColor(QPalette.HighlightedText, Qt.black) # Text color for selected items
    dark_palette.setColor(QPalette.PlaceholderText, QColor(128,128,128)) # Color for placeholder text
    app.setPalette(dark_palette)

    # Global stylesheet for tooltips (if needed beyond palette)
    app.setStyleSheet("QToolTip { color: #000000; background-color: #ffffff; border: 1px solid black; }")


    # Initialize database (ensure it exists and tables are created)
    if not os.path.exists(db_manager.DATABASE_NAME):
        print(f"Database '{db_manager.DATABASE_NAME}' not found. Initializing...")
        db_manager.init_db() # Creates DB and tables
    else:
        print(f"Database '{db_manager.DATABASE_NAME}' found. Ensuring schema is up-to-date...")
        db_manager.init_db() # Ensures tables exist, doesn't alter existing ones by default

    window = MainWindow()

    # Determine initial mode (GUI or Hover) based on saved setting
    if window.initial_mode == "hover":
        # If starting in hover mode, don't show main window initially
        # The collapse_to_hover_icon method will show the hover icon
        window.collapse_to_hover_icon()
    else:
        window.show() # Show main GUI window

    sys.exit(app.exec())
