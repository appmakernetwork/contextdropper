import sys
import os
import shutil
import collections
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QTreeView, QFileSystemModel,
    QSplitter, QMenu, QInputDialog, QMessageBox, QComboBox,
    QHeaderView, QDialog, QLineEdit, QDialogButtonBox, QListWidget, QListWidgetItem,
    QSpacerItem, QSizePolicy, QFileDialog, QAbstractItemView,
    QPlainTextEdit, QGraphicsOpacityEffect
)
from PySide6.QtGui import QAction, QClipboard, QCursor, QGuiApplication, QPalette, QColor, QIcon
from PySide6.QtCore import Qt, QDir, Slot, QTimer, Signal, QModelIndex, QPropertyAnimation, QEasingCurve, QPoint, QRect

import db_manager
from hover_icon import HoverIcon
from syntax_highlighter import SyntaxHighlighter

class ManageCategoriesDialog(QDialog):
    # ... (content of ManageCategoriesDialog as in source: 42-50, no changes needed here) ...
    def __init__(self, project_id, parent=None):
        super().__init__(parent)
        self.project_id = project_id
        self.setWindowTitle("Manage Categories")
        self.setMinimumWidth(300)
        layout = QVBoxLayout(self)

        self.category_list = QListWidget()
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

        dialog_buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        dialog_buttons.accepted.connect(self.accept)
        layout.addWidget(dialog_buttons)

    def load_categories(self):
        self.category_list.clear()
        if not self.project_id: return
        categories = db_manager.get_categories(self.project_id)
        for cat in categories:
            item = QListWidgetItem(cat['name'])
            item.setData(Qt.UserRole, cat['id'])
            self.category_list.addItem(item)

    def add_category(self):
        name = self.new_category_edit.text().strip()
        if name and self.project_id:
            if db_manager.add_category(self.project_id, name):
                self.load_categories()
                self.new_category_edit.clear()
            else:
                QMessageBox.warning(self, "Error", f"Category '{name}' already exists or could not be added.")
        elif not name:
            QMessageBox.warning(self, "Input Error", "Category name cannot be empty.")


    def remove_category(self):
        selected_item = self.category_list.currentItem()
        if not selected_item:
            QMessageBox.warning(self, "Selection Error", "Please select a category to remove.")
            return

        category_id = selected_item.data(Qt.UserRole)
        category_name = selected_item.text()

        reply = QMessageBox.question(self, "Confirm Remove",
                                     f"Are you sure you want to remove category '{category_name}'?\n"
                                     "Items in this category will become uncategorized.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            print(f"Placeholder: Remove category ID {category_id}. Implement in db_manager.")
            QMessageBox.information(self, "Not Fully Implemented",
                                    "Category removal logic in db_manager needs to be completed.\n"
                                    "For now, this only simulates removal from the list if you had a DB function.")

class DroppableListWidget(QListWidget):
    # ... (content of DroppableListWidget as in source: 51-53, no changes needed here) ...
    item_dropped_signal = Signal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.CopyAction)
            urls = event.mimeData().urls()
            for url in urls:
                path = url.toLocalFile()
                if path:
                    is_dir = os.path.isdir(path)
                    self.item_dropped_signal.emit(path, is_dir)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


class NotificationWidget(QWidget):
    # ... (content of NotificationWidget as in source: 54-64, no changes needed here) ...
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setStyleSheet("background:transparent;") 

        self.card_widget = QWidget(self)
        self.card_widget.setStyleSheet("""
            QWidget {
                background-color: rgb(53, 53, 53);
                border-radius: 8px;
                border: 1px solid rgb(75, 75, 75);
            }
        """)

        card_layout = QVBoxLayout(self.card_widget)
        card_layout.setContentsMargins(15, 10, 15, 10)

        self.message_label = QLabel("")
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet(
            "background-color: transparent; color: white; font-size: 10pt; border: none;"
        ) 
        card_layout.addWidget(self.message_label)

        outer_layout = QVBoxLayout(self)
        outer_layout.addWidget(self.card_widget)
        outer_layout.setContentsMargins(0,0,0,0)

        self.opacity_effect = QGraphicsOpacityEffect(self.card_widget)
        self.card_widget.setGraphicsEffect(self.opacity_effect)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._start_fade_out)

        self.fadeInAnimation = QPropertyAnimation(self.opacity_effect, b"opacity", self)
        self.fadeOutAnimation = QPropertyAnimation(self.opacity_effect, b"opacity", self)


    def _start_fade_out(self):
        if self.fadeOutAnimation.state() == QPropertyAnimation.Running:
            self.fadeOutAnimation.stop()
        
        self.fadeOutAnimation.setDuration(600)
        self.fadeOutAnimation.setStartValue(self.opacity_effect.opacity())
        self.fadeOutAnimation.setEndValue(0.0)
        self.fadeOutAnimation.setEasingCurve(QEasingCurve.InOutQuad)
        self.fadeOutAnimation.finished.connect(self.hide)
        self.fadeOutAnimation.start()

    def show_message(self, message, duration_ms=3500, anchor_widget=None):
        if self.fadeInAnimation.state() == QPropertyAnimation.Running:
            self.fadeInAnimation.stop()
        if self.fadeOutAnimation.state() == QPropertyAnimation.Running:
            self.fadeOutAnimation.stop()
        self.timer.stop()

        self.message_label.setText(message)

        NOTIFICATION_WIDTH = 350
        self.card_widget.setFixedWidth(NOTIFICATION_WIDTH)
        self.message_label.adjustSize() 
        self.card_widget.adjustSize()   
        self.adjustSize()                

        target_screen = None
        if anchor_widget and anchor_widget.isVisible():
            if not anchor_widget.isMinimized(): 
                s = anchor_widget.screen()
                if s: 
                    target_screen = s

        if not target_screen: 
            target_screen = QGuiApplication.primaryScreen()
        
        if not target_screen: 
            desktop_rect = QGuiApplication.primaryScreen().geometry() if QGuiApplication.primaryScreen() else QRect(0,0,800,600)
            x = desktop_rect.right() - self.width() - 20
            y = desktop_rect.top() + 20
            self.move(x, y)
        else:
            screen_geometry = target_screen.availableGeometry()
            margin_x = 20
            margin_y = 20
            x = screen_geometry.right() - self.width() - margin_x
            y = screen_geometry.top() + margin_y
            self.move(x, y)

        self.opacity_effect.setOpacity(0.0) 
        self.show() 
        self.raise_()

        self.fadeInAnimation.setDuration(400)
        self.fadeInAnimation.setStartValue(0.0)
        self.fadeInAnimation.setEndValue(0.85) 
        self.fadeInAnimation.setEasingCurve(QEasingCurve.OutQuad)
        self.fadeInAnimation.start()

        self.timer.start(duration_ms)

class MainWindow(QMainWindow):
    BINARY_EXTENSIONS = [
        '.exe', '.dll', '.so', '.dylib', '.jar', '.class', '.pyc', '.o', '.a', '.lib',
        '.zip', '.gz', '.tar', '.rar', '.7z', '.pkg', '.dmg',
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.ico',
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
        '.odt', '.ods', '.odp',
        '.mp3', '.wav', '.ogg', '.mp4', '.avi', '.mkv', '.mov', '.webm',
        '.db', '.sqlite', '.sqlite3', '.mdb', '.accdb',
        '.wasm', '.woff', '.woff2', '.ttf', '.otf', '.eot',
        '.DS_Store'
    ]
    MAX_PREVIEW_SIZE = 1 * 1024 * 1024  # 1 MB

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Context Dropper")
        self.setGeometry(100, 100, 1200, 800)

        self.current_project_id = None
        self.current_project_path = None
        self.current_highlighter = None

        db_manager.init_db() # Ensures tables exist, including app_settings

        self.setup_ui()
        self.load_projects()
        self.load_active_project()

        self.hover_widget = HoverIcon()
        self.hover_widget.drop_context_requested.connect(self.drop_context)
        self.hover_widget.maximize_requested.connect(self.show_main_window_from_hover)
        self.hover_widget.close_application_requested.connect(self.close_application_from_hover)
        
        self.notification_widget = NotificationWidget()

        self.prompt_save_timer = QTimer(self)
        self.prompt_save_timer.setSingleShot(True)
        self.prompt_save_timer.timeout.connect(self.save_prompt_guide_to_db)
        self.prompt_edit.textChanged.connect(self.on_prompt_text_changed)

        # Determine initial mode
        self.initial_mode = "gui" # Default
        last_mode_setting = db_manager.get_app_setting('last_ui_mode')
        if last_mode_setting == "hover":
            self.initial_mode = "hover"
        # The actual show() or collapse() will be called from the main block

    def setup_ui(self):
        # ... (content of setup_ui as in source: 67-77, no changes needed here) ...
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
        self.fs_model = QFileSystemModel()
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
        self.file_preview_edit = QPlainTextEdit()
        self.file_preview_edit.setReadOnly(True)
        
        self.file_preview_edit.setStyleSheet(
            "QPlainTextEdit {"
            "  background-color: #1E1E1E;"
            "  color: #D4D4D4;"
            "  selection-background-color: #0078D7;"
            "  selection-color: #FFFFFF;"
            "}"
            "QPlainTextEdit::placeholderText {"
            "  color: #A0A0A0;"
            "}"
        )
        self._show_preview_for_path(None)
        preview_layout.addWidget(self.file_preview_edit)
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
        bottom_bar_layout.addWidget(self.export_category_combo)
        bottom_bar_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        self.drop_context_button = QPushButton("Drop Context")
        self.drop_context_button.clicked.connect(self.drop_context)
        bottom_bar_layout.addWidget(self.drop_context_button)
        self.collapse_button = QPushButton("Collapse to Hover Icon")
        self.collapse_button.clicked.connect(self.collapse_to_hover_icon)
        bottom_bar_layout.addWidget(self.collapse_button)
        main_layout.addLayout(bottom_bar_layout)

        self.update_ui_for_project_state()
    
    # ... (Methods like on_prompt_text_changed, save_prompt_guide_to_db, load_projects, etc. remain as in source: 77-167)
    # The following methods are copied from the provided context for completeness, assuming no other changes are needed in them.
    def on_prompt_text_changed(self):
        if self.current_project_id:
            self.prompt_save_timer.start(1000)

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
                if self.project_combo.currentIndex() == idx and self.current_project_id != project_id_to_activate: 
                    self.update_project_details(project_id_to_activate) 
            else: 
                self.clear_project_context() 
        elif self.project_combo.count() > 0 and self.project_combo.itemData(0) is not None: 
            first_project_id = self.project_combo.itemData(0)
            self.project_combo.setCurrentIndex(0) 
        else: 
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
            self.current_project_path = project['path']
            self.prompt_edit.blockSignals(True)
            self.prompt_edit.setText(project['prompt_guide'] or "")
            self.prompt_edit.blockSignals(False)

            if os.path.isdir(self.current_project_path):
                self.fs_model.setRootPath(self.current_project_path)
                self.tree_view.setRootIndex(self.fs_model.index(self.fs_model.rootPath()))
            else:
                QMessageBox.warning(self, "Project Path Error",
                                    f"Project path not found: {self.current_project_path}\n"
                                    "Reverting to default view. Please update project settings or select another project.")
                fallback_path = QDir.currentPath()
                self.fs_model.setRootPath(fallback_path)
                self.tree_view.setRootIndex(self.fs_model.index(self.fs_model.rootPath()))
                
            db_manager.set_active_project(self.current_project_id)
        else:
            self.clear_project_context() 

        self.update_ui_for_project_state()
        self.load_selected_items()
        self.load_categories_for_export()
        self._show_preview_for_path(None) 


    def clear_project_context(self):
        self.current_project_id = None
        new_root_path = QDir.currentPath() 
        self.current_project_path = new_root_path 
        self.prompt_edit.blockSignals(True)
        self.prompt_edit.clear()
        self.prompt_edit.blockSignals(False)
        self.fs_model.setRootPath(new_root_path)
        self.tree_view.setRootIndex(self.fs_model.index(self.fs_model.rootPath()))
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
                                     f"Are you sure you want to delete project '{project_name}' and all its associated data (selections, categories)?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            db_manager.delete_project(self.current_project_id)
            self.load_projects()
            self.load_active_project() 

    def manage_categories_dialog(self):
        if not self.current_project_id:
            QMessageBox.information(self, "No Project", "Please select or create a project first.")
            return
        dialog = ManageCategoriesDialog(self.current_project_id, self)
        dialog.exec()
        self.load_categories_for_export() 
        self.load_selected_items() 

    def load_categories_for_export(self):
        self.export_category_combo.blockSignals(True)
        self.export_category_combo.clear()
        self.export_category_combo.addItem("All Categories", None) 
        if self.current_project_id:
            categories = db_manager.get_categories(self.current_project_id)
            for cat in categories:
                self.export_category_combo.addItem(cat['name'], cat['id'])
        self.export_category_combo.blockSignals(False)

    def update_ui_for_project_state(self):
        has_project = self.current_project_id is not None
        self.prompt_edit.setEnabled(has_project)
        self.selected_items_list.setEnabled(has_project)
        self.drop_context_button.setEnabled(has_project)
        if hasattr(self, 'file_preview_edit'):
            self.file_preview_edit.setEnabled(has_project) 
        if hasattr(self, 'delete_project_button'): 
            self.delete_project_button.setEnabled(has_project)
        if hasattr(self, 'manage_cat_button'):
            self.manage_cat_button.setEnabled(has_project)
        self.export_category_combo.setEnabled(has_project)


    def tree_context_menu(self, position):
        if not self.current_project_id: return 
        index = self.tree_view.indexAt(position)
        if not index.isValid(): return

        path = self.fs_model.filePath(index)
        is_dir = self.fs_model.isDir(index)

        menu = QMenu()
        existing_selection = db_manager.get_selection_by_path(self.current_project_id, path)

        if existing_selection:
            action_text = "Item Options"
            if is_dir: action_text = "Directory Options (File Types)"
            update_action = menu.addAction(action_text)
            update_action.triggered.connect(lambda: self.add_or_update_selection(path, is_dir, existing_selection))
            
            assign_cat_action = menu.addAction("Assign/Change Category")
            assign_cat_action.triggered.connect(lambda: self.assign_category_to_selection_dialog(path))

            remove_action = menu.addAction("Remove from Context")
            remove_action.triggered.connect(lambda: self.remove_selected_path(path))
        else:
            action_text = "Add Directory to Context" if is_dir else "Add File to Context"
            add_action = menu.addAction(action_text)
            add_action.triggered.connect(lambda: self.add_or_update_selection(path, is_dir))
        
        menu.exec(self.tree_view.viewport().mapToGlobal(position))

    def add_or_update_selection(self, path, is_dir, existing_selection=None):
        if not self.current_project_id:
            QMessageBox.warning(self, "No Project Active", "Cannot add selection: no project is currently active.")
            return

        file_types = None 
        category_id = existing_selection['category_id'] if existing_selection else None

        if is_dir:
            current_types = ""
            if existing_selection and existing_selection['file_types']:
                current_types = existing_selection['file_types']
            elif not existing_selection: 
                current_types = ".py,.txt,.md,.json,.html,.css,.js,CMakeLists.txt" 
            
            types_str, ok = QInputDialog.getText(self, "Include File Types (Directory)",
                                                 "Comma-separated extensions (e.g., .py,.txt) or exact filenames.\nLeave empty for ALL files in this directory (recursive).",
                                                 text=current_types)
            if not ok: return 
            file_types = types_str.strip() if types_str.strip() else None 

        db_manager.add_selection(self.current_project_id, path, is_dir, category_id, file_types)
        self.load_selected_items() 

    def handle_dropped_item_signal(self, path, is_dir):
        if not self.current_project_id:
            QMessageBox.warning(self, "No Active Project",
                                "Please select or create a project first to add items to its context.")
            return
        existing_selection = db_manager.get_selection_by_path(self.current_project_id, path)
        self.add_or_update_selection(path, is_dir, existing_selection)


    def assign_category_to_selection_dialog(self, path):
        if not self.current_project_id: return

        categories = db_manager.get_categories(self.current_project_id)
        cat_names = ["<No Category>"] + [c['name'] for c in categories] 
        
        current_selection = db_manager.get_selection_by_path(self.current_project_id, path)
        if not current_selection: 
            QMessageBox.warning(self, "Error", "Could not find selection data for this item.")
            return

        current_cat_id = current_selection['category_id']
        current_idx = 0 
        if current_cat_id:
            for i, cat in enumerate(categories): 
                if cat['id'] == current_cat_id:
                    current_idx = i + 1 
                    break
        
        item_display_name = os.path.basename(path)
        cat_name, ok = QInputDialog.getItem(self, "Assign Category", 
                                            f"Select Category for:\n{item_display_name}", 
                                            cat_names, current_idx, False)
        if ok:
            new_category_id = None 
            if cat_name != "<No Category>":
                for cat in categories:
                    if cat['name'] == cat_name:
                        new_category_id = cat['id']
                        break
            db_manager.update_selection_category(self.current_project_id, path, new_category_id)
            self.load_selected_items() 

    def remove_selected_path(self, path):
        if self.current_project_id:
            db_manager.remove_selection(self.current_project_id, path)
            self.load_selected_items()

    def load_selected_items(self):
        self.selected_items_list.clear() 
        if not self.current_project_id:
            self._show_preview_for_path(None) 
            return

        selections = db_manager.get_selections(self.current_project_id)
        for sel in selections:
            display_name = sel['path']
            if self.current_project_path and os.path.isdir(self.current_project_path) and \
               sel['path'].startswith(self.current_project_path) and self.current_project_path != sel['path']:
                try:
                    rel_path = os.path.relpath(sel['path'], self.current_project_path)
                    display_name = rel_path
                except ValueError: 
                    display_name = os.path.basename(sel['path']) 
            else: 
                display_name = os.path.basename(sel['path']) 

            if sel['is_directory']:
                file_types_display = sel['file_types'] if sel['file_types'] else "ALL"
                display_text = f"{display_name}{os.sep} (Dir: {file_types_display})"
            else:
                display_text = display_name

            cat_name = sel['category_name'] or "Uncategorized"
            display_text += f"  [{cat_name}]"

            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, sel['path']) 
            item.setToolTip(sel['path']) 
            self.selected_items_list.addItem(item)
        
        if not selections: 
             self._show_preview_for_path(None)


    def selected_item_context_menu(self, position):
        item = self.selected_items_list.itemAt(position)
        if not item or not self.current_project_id:
            return

        path = item.data(Qt.UserRole) 
        selection_data = db_manager.get_selection_by_path(self.current_project_id, path)
        if not selection_data: 
            QMessageBox.warning(self, "Error", "Could not retrieve selection details for this item.")
            return

        menu = QMenu()
        assign_cat_action = menu.addAction("Assign/Change Category")
        assign_cat_action.triggered.connect(lambda: self.assign_category_to_selection_dialog(path))

        if selection_data['is_directory']:
            edit_types_action = menu.addAction("Edit Directory Options (File Types)")
            edit_types_action.triggered.connect(lambda: self.add_or_update_selection(path, True, selection_data))

        remove_action = menu.addAction("Remove from Context")
        remove_action.triggered.connect(lambda: self.remove_selected_path(path))

        menu.exec(self.selected_items_list.mapToGlobal(position))


    def _is_binary_file_for_preview(self, file_path):
        if any(file_path.lower().endswith(ext) for ext in self.BINARY_EXTENSIONS):
            return True
        try:
            with open(file_path, 'rb') as f_check:
                chunk = f_check.read(1024) 
                if b'\x00' in chunk:
                    return True
        except Exception:
            return True 
        return False

    def _read_file_content_for_preview(self, file_path):
        if self._is_binary_file_for_preview(file_path):
            return True, f"File: {os.path.basename(file_path)}\n\n(Binary file, content not displayed)"

        try:
            file_size = os.path.getsize(file_path)
            if file_size > self.MAX_PREVIEW_SIZE:
                return True, f"File: {os.path.basename(file_path)}\n\n(File is too large for preview: {file_size // (1024*1024)} MB.\nMax preview size: {self.MAX_PREVIEW_SIZE // (1024*1024)} MB)"
            
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f: 
                content = f.read()
            return False, content 
        except UnicodeDecodeError:
            return True, f"File: {os.path.basename(file_path)}\n\n(Cannot decode file content for preview - may be binary or non-UTF-8)"
        except Exception as e:
            return True, f"File: {os.path.basename(file_path)}\n\n(Error reading file for preview: {e})"

    def _generate_directory_preview_summary(self, dir_path):
        p = Path(dir_path)
        try:
            num_files_total = 0
            num_subdirs_total = 0
            ext_counts_total = collections.defaultdict(int)

            for item_path in p.rglob('*'): 
                if item_path.is_file():
                    num_files_total += 1
                    ext = item_path.suffix.lower() if item_path.suffix else "<no_extension>"
                    ext_counts_total[ext] += 1
                elif item_path.is_dir():
                    num_subdirs_total += 1
            
            summary_parts = []
            summary_parts.append(f"Directory: {os.path.basename(dir_path)} (at {dir_path})")
            summary_parts.append(f"Contains: {num_files_total} files and {num_subdirs_total} subdirectories (recursively).")

            if ext_counts_total:
                sorted_extensions = sorted(ext_counts_total.items(), key=lambda item: (-item[1], item[0]))
                ext_str_parts = [f"{count} {ext if ext != '<no_extension>' else 'files w/o extension'}" for ext, count in sorted_extensions]
                summary_parts.append("File types: " + ", ".join(ext_str_parts) + ".")
            elif num_files_total == 0 and num_subdirs_total == 0 :
                summary_parts.append("This directory is empty.")
            elif num_files_total == 0: 
                 summary_parts.append("No files found in this directory or its subdirectories.")
            
            return "\n".join(summary_parts)
        except Exception as e:
            return f"Error scanning directory {dir_path} for preview: {e}"


    def _show_preview_for_path(self, path):
        if not self.file_preview_edit: return

        if self.current_highlighter:
            self.current_highlighter.setDocument(None) 
            self.current_highlighter = None

        if not path:
            self.file_preview_edit.clear()
            self.file_preview_edit.setPlaceholderText("Click a file/folder in the tree or 'Selected Items' list for a preview.")
            return

        if not os.path.exists(path):
            self.file_preview_edit.setPlainText(f"Path does not exist: {path}")
            return

        if os.path.isdir(path):
            summary = self._generate_directory_preview_summary(path)
            self.file_preview_edit.setPlainText(summary)
        elif os.path.isfile(path):
            is_message, content_or_message = self._read_file_content_for_preview(path)
            self.file_preview_edit.setPlainText(content_or_message) 

            if not is_message: 
                _, ext = os.path.splitext(path)
                ext = ext.lower()
                supported_extensions = ['.py', '.js', '.dart', '.html', '.htm', '.yaml', '.json'] 
                if ext in supported_extensions:
                    self.current_highlighter = SyntaxHighlighter(self.file_preview_edit.document(), ext)
        else:
            self.file_preview_edit.setPlainText(f"Path is not a regular file or directory: {path}")


    @Slot(QModelIndex, QModelIndex)
    def _handle_tree_view_selection(self, current_index, previous_index):
        if not current_index.isValid():
            return 
        path = self.fs_model.filePath(current_index)
        self._show_preview_for_path(path)

    @Slot(QListWidgetItem, QListWidgetItem)
    def _handle_selected_items_list_selection(self, current_list_item, previous_list_item):
        if not current_list_item:
            self._show_preview_for_path(None) 
            return
        path = current_list_item.data(Qt.UserRole) 
        self._show_preview_for_path(path)


    def generate_project_tree_summary(self, project_path, selections_for_summary):
        summary = []
        relative_selected_paths_data = {} 

        if not os.path.isdir(project_path): 
             return f"Error: Project path '{project_path}' is not a valid directory."

        normalized_project_path = os.path.normpath(project_path)

        for sel_data in selections_for_summary:
            s_path_norm = os.path.normpath(sel_data['path'])
            if s_path_norm.startswith(normalized_project_path + os.sep) or s_path_norm == normalized_project_path:
                rel_s_path = os.path.relpath(s_path_norm, normalized_project_path)
                if rel_s_path == ".": rel_s_path = "" 
                relative_selected_paths_data[rel_s_path] = {
                    'is_directory': sel_data['is_directory'],
                    'file_types': sel_data['file_types']
                }

        outside_project_selections = [
            os.path.abspath(sel['path']) for sel in selections_for_summary 
            if not os.path.normpath(sel['path']).startswith(normalized_project_path + os.sep) and \
               os.path.normpath(sel['path']) != normalized_project_path
        ]
        
        ignored_names = ['__pycache__', 'node_modules', 'target', 'build', '.venv', 'venv', '.git', 'dist', 'context.txt', '.DS_Store']


        def build_tree(current_dir_abs, current_dir_rel, prefix=""):
            try:
                entries = sorted([
                    e for e in os.listdir(current_dir_abs)
                    if not e.startswith('.') and e not in ignored_names
                ])
            except OSError: 
                summary.append(f"{prefix}└── [Error listing directory: {os.path.basename(current_dir_abs)}]")
                return

            for i, entry_name in enumerate(entries):
                is_last = (i == len(entries) - 1)
                entry_abs_path = os.path.join(current_dir_abs, entry_name)
                entry_rel_path = os.path.join(current_dir_rel, entry_name) if current_dir_rel else entry_name
                
                connector = "└── " if is_last else "├── "
                line = prefix + connector + entry_name

                is_selected_explicitly = entry_rel_path in relative_selected_paths_data
                is_ancestor_of_selected = any(
                    sel_rel.startswith(entry_rel_path + os.sep) for sel_rel in relative_selected_paths_data
                )
                
                if is_selected_explicitly or (os.path.isdir(entry_abs_path) and is_ancestor_of_selected):
                    line += " [*]"
                    if is_selected_explicitly and relative_selected_paths_data[entry_rel_path]['is_directory']:
                        ft = relative_selected_paths_data[entry_rel_path]['file_types']
                        line += f" (Dir: {ft if ft else 'ALL'})"
                
                summary.append(line)

                if os.path.isdir(entry_abs_path):
                    should_recurse = is_selected_explicitly or is_ancestor_of_selected
                    if should_recurse or len(prefix) < 12 : 
                        new_prefix = prefix + ("    " if is_last else "│   ")
                        build_tree(entry_abs_path, entry_rel_path, new_prefix)

        project_base_name = os.path.basename(normalized_project_path)
        root_marker = ""
        if "" in relative_selected_paths_data: 
            root_marker = " [*]"
            if relative_selected_paths_data[""]['is_directory']:
                ft = relative_selected_paths_data[""]['file_types']
                root_marker += f" (Dir: {ft if ft else 'ALL'})"
        
        summary.append(f"{project_base_name}{os.sep}{root_marker}")
        build_tree(normalized_project_path, "", "  ") 
        
        if outside_project_selections:
            summary.append("\n----- Other Selected Items (Outside Project Root) -----")
            for ops_path in sorted(outside_project_selections): 
                sel_info = next((s for s in selections_for_summary if os.path.abspath(s['path']) == ops_path), None)
                if sel_info:
                    display_ops_path = ops_path 
                    if sel_info['is_directory']:
                        ft_display = sel_info['file_types'] if sel_info['file_types'] else "ALL"
                        summary.append(f"{display_ops_path} [*] (Dir: {ft_display})")
                    else:
                        summary.append(f"{display_ops_path} [*]")
                else: 
                    summary.append(f"{ops_path} [*]") 
        
        return "\n".join(summary)


    def drop_context(self):
        if not self.current_project_id or not self.current_project_path:
            QMessageBox.warning(self, "Error", "No active project selected.")
            return
        if not os.path.isdir(self.current_project_path):
            QMessageBox.warning(self, "Error", f"Project path is not a valid directory: {self.current_project_path}")
            return

        prompt_text = self.prompt_edit.toPlainText()
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(prompt_text)

        context_content = []
        export_cat_id = self.export_category_combo.currentData() 
        selections = db_manager.get_selections(self.current_project_id, export_cat_id)
        
        notification_anchor = self if self.isVisible() and not self.isMinimized() else self.hover_widget

        if not selections:
            self.notification_widget.show_message(
                "Prompt copied to clipboard.\nNo files selected for context.txt generation.",
                anchor_widget=notification_anchor
            )
            return

        context_content.append("----- Project Structure (Selected Items Focus) -----")
        summary_tree = self.generate_project_tree_summary(self.current_project_path, selections)
        context_content.append(summary_tree)
        context_content.append("----- End Project Structure -----\n")

        files_to_include = {} 

        normalized_project_path = os.path.normpath(self.current_project_path)
        context_txt_abs_path = os.path.join(normalized_project_path, "context.txt")

        for sel in selections:
            path_abs = os.path.normpath(sel['path'])
            
            if not os.path.exists(path_abs):
                print(f"Warning: Selected path does not exist, skipping: {path_abs}")
                header_path = path_abs
                if path_abs.startswith(normalized_project_path + os.sep):
                    header_path = os.path.relpath(path_abs, normalized_project_path)
                context_content.append(f"----- Warning: Selected path not found: {header_path} -----")
                continue

            if sel['is_directory']:
                allowed_extensions = []
                exact_filenames = []
                if sel['file_types']: 
                    for ft_raw in sel['file_types'].split(','):
                        ft = ft_raw.strip()
                        if not ft: continue
                        if ft.startswith('.'): allowed_extensions.append(ft.lower())
                        else: exact_filenames.append(ft)
                
                for root, dirs, files in os.walk(path_abs):
                    dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', 'node_modules', 'target', 'build', '.venv', 'venv', 'dist'] and not d.startswith('.')]
                    
                    for file_name in files:
                        full_file_path_abs = os.path.normpath(os.path.join(root, file_name))
                        
                        if full_file_path_abs == context_txt_abs_path: 
                            continue

                        include_file = False
                        if not allowed_extensions and not exact_filenames: 
                            include_file = True
                        elif file_name in exact_filenames:
                            include_file = True
                        elif any(file_name.lower().endswith(ext) for ext in allowed_extensions):
                            include_file = True
                        
                        if include_file:
                            file_header_path = full_file_path_abs
                            if full_file_path_abs.startswith(normalized_project_path + os.sep):
                                file_header_path = os.path.relpath(full_file_path_abs, normalized_project_path)
                            else: 
                                file_header_path = f"EXTERNAL:{os.path.basename(full_file_path_abs)} (in {os.path.basename(path_abs)}{os.sep}..., Full: {full_file_path_abs})"
                            files_to_include[full_file_path_abs] = file_header_path
            else: 
                if path_abs == context_txt_abs_path: 
                    continue
                
                file_header_path = path_abs
                if path_abs.startswith(normalized_project_path + os.sep):
                    file_header_path = os.path.relpath(path_abs, normalized_project_path)
                else: 
                    file_header_path = f"EXTERNAL:{os.path.basename(path_abs)} (Full: {path_abs})"
                files_to_include[path_abs] = file_header_path
        
        sorted_file_paths_abs = sorted(files_to_include.keys(), key=lambda p: files_to_include[p])

        for file_path_abs in sorted_file_paths_abs:
            display_rel_path = files_to_include[file_path_abs]
            try:
                is_binary = False
                if any(file_path_abs.lower().endswith(ext) for ext in self.BINARY_EXTENSIONS):
                    is_binary = True
                
                if not is_binary: 
                    try:
                        with open(file_path_abs, 'rb') as f_check: 
                            chunk = f_check.read(1024) 
                            if b'\x00' in chunk: 
                                is_binary = True
                    except Exception: 
                        is_binary = True 
                
                if is_binary:
                    context_content.append(f"----- File: {display_rel_path} (Skipped Binary File) -----")
                    context_content.append(f"----- End File: {display_rel_path} -----\n")
                    print(f"Skipped binary file: {display_rel_path}")
                    continue

                with open(file_path_abs, 'r', encoding='utf-8', errors='ignore') as f: 
                    content = f.read()
                context_content.append(f"----- File: {display_rel_path} -----")
                context_content.append(content.strip()) 
                context_content.append(f"----- End File: {display_rel_path} -----\n")
            except Exception as e:
                context_content.append(f"----- Error reading file: {display_rel_path} -----")
                context_content.append(f"Error: {str(e)}")
                context_content.append(f"----- End Error: {display_rel_path} -----\n")
                print(f"Error reading {display_rel_path}: {e}")
        
        try:
            with open(context_txt_abs_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(context_content))
            
            self.notification_widget.show_message(
                f"Context file created: {os.path.basename(context_txt_abs_path)}\nPrompt copied to clipboard.",
                anchor_widget=notification_anchor
            )
        except Exception as e:
            QMessageBox.critical(self, "Error Saving Context", f"Could not save context.txt: {e}")

    def collapse_to_hover_icon(self):
        main_window_current_screen = self.screen()
        self.hide()
        db_manager.set_app_setting('last_ui_mode', 'hover') # Save mode

        if main_window_current_screen:
            target_screen_geometry = main_window_current_screen.availableGeometry()
        else:
            print("Warning: Main window screen not found on collapse. Defaulting to primary screen for hover icon.")
            target_screen_geometry = QGuiApplication.primaryScreen().availableGeometry()

        hover_x = target_screen_geometry.x() + (target_screen_geometry.width() - self.hover_widget.width()) // 2
        hover_y = target_screen_geometry.y() + (target_screen_geometry.height() - self.hover_widget.height()) // 2
        self.hover_widget.move(QPoint(hover_x, hover_y))
        self.hover_widget.show()

    def show_main_window_from_hover(self, hover_icon_current_screen):
        self.hover_widget.hide()
        self.show()
        db_manager.set_app_setting('last_ui_mode', 'gui') # Save mode

        if hover_icon_current_screen:
            target_screen_geometry = hover_icon_current_screen.availableGeometry()
        else:
            print("Warning: Hover icon screen not provided on expand. Defaulting to primary screen for main window.")
            target_screen_geometry = QGuiApplication.primaryScreen().availableGeometry()

        main_x = target_screen_geometry.x() + (target_screen_geometry.width() - self.width()) // 2
        main_y = target_screen_geometry.y() + (target_screen_geometry.height() - self.height()) // 2
        self.move(QPoint(main_x, main_y))

        self.activateWindow()
        self.raise_()

    def close_application_from_hover(self):
        self.close() 

    def closeEvent(self, event):
        if self.prompt_save_timer.isActive():
            self.prompt_save_timer.stop()
            self.save_prompt_guide_to_db() 
        
        # Save current mode if main window is visible (i.e., closing from GUI mode)
        if self.isVisible():
            db_manager.set_app_setting('last_ui_mode', 'gui')
        # If closing from hover mode, 'hover' was already saved when it collapsed.

        if hasattr(self, 'notification_widget') and self.notification_widget:
            self.notification_widget.close() 
        
        if hasattr(self, 'hover_widget') and self.hover_widget:
            self.hover_widget.close() 
        
        super().closeEvent(event) 
        if event.isAccepted(): 
            QApplication.instance().quit() 

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    icon_path = "contextdropper.png"
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    else:
        print(f"Warning: Application icon '{icon_path}' not found.")


    app.setStyle("Fusion") 
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.WindowText, Qt.white)
    dark_palette.setColor(QPalette.Base, QColor(35, 35, 35)) 
    dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
    dark_palette.setColor(QPalette.ToolTipText, Qt.black) 
    dark_palette.setColor(QPalette.Text, Qt.white)
    dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ButtonText, Qt.white)
    dark_palette.setColor(QPalette.BrightText, Qt.red)
    dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218)) 
    dark_palette.setColor(QPalette.HighlightedText, Qt.black) 
    dark_palette.setColor(QPalette.PlaceholderText, QColor(128, 128, 128)) 
    app.setPalette(dark_palette)
    app.setStyleSheet("QToolTip { color: #000000; background-color: #ffffff; border: 1px solid black; }") 


    if not os.path.exists(db_manager.DATABASE_NAME):
        print(f"Database '{db_manager.DATABASE_NAME}' not found. Initializing...")
        db_manager.init_db() # This will create app_settings if it doesn't exist
    else:
        print(f"Database '{db_manager.DATABASE_NAME}' found.")
        # Call init_db anyway to ensure new tables/columns are added if the schema changed
        db_manager.init_db()


    window = MainWindow() # __init__ now determines self.initial_mode

    if window.initial_mode == "hover":
        # Critical: Ensure hover_widget is created and main window is ready enough
        # before collapsing. The current structure of __init__ should be fine.
        window.collapse_to_hover_icon() # This also calls hover_widget.show()
    else: # "gui" or default
        window.show()

    sys.exit(app.exec())