import sqlite3
import os

DATABASE_NAME = 'context_dropper.db'

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row # Access columns by name
    return conn

def init_db():
    """Initializes the database with necessary tables if they don't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Projects table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            path TEXT NOT NULL,
            prompt_guide TEXT,
            is_active INTEGER DEFAULT 0
        )
    ''')

    # Categories table (per project)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE,
            UNIQUE (project_id, name)
        )
    ''')

    # Selections table (files/directories chosen for context)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS selections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            path TEXT NOT NULL, -- Full path
            is_directory INTEGER NOT NULL, -- 0 for file, 1 for directory
            category_id INTEGER,
            file_types TEXT, -- Comma-separated, e.g., ".py,.txt,.md" (for directories)
            FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE,
            FOREIGN KEY (category_id) REFERENCES categories (id) ON DELETE SET NULL,
            UNIQUE (project_id, path)
        )
    ''')

    # Application Settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    conn.commit()
    conn.close()
    print(f"Database '{DATABASE_NAME}' initialized.")

# --- App Settings Functions ---
def get_app_setting(key):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row['value'] if row else None

def set_app_setting(key, value):
    conn = get_db_connection()
    try:
        conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)", (key, value))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error setting app setting {key}: {e}")
    finally:
        conn.close()

# --- Project Functions ---
def add_project(name, path, prompt_guide=""):
    conn = get_db_connection()
    try:
        conn.execute("INSERT INTO projects (name, path, prompt_guide) VALUES (?, ?, ?)",
                     (name, path, prompt_guide))
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    except sqlite3.IntegrityError:
        print(f"Project with name '{name}' already exists.")
        return None
    finally:
        conn.close()

def get_projects():
    conn = get_db_connection()
    projects = conn.execute("SELECT * FROM projects ORDER BY name").fetchall()
    conn.close()
    return projects

def get_project_by_id(project_id):
    conn = get_db_connection()
    project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    conn.close()
    return project

def get_active_project():
    conn = get_db_connection()
    project = conn.execute("SELECT * FROM projects WHERE is_active = 1").fetchone()
    conn.close()
    return project

def set_active_project(project_id):
    conn = get_db_connection()
    conn.execute("UPDATE projects SET is_active = 0")
    if project_id:
        conn.execute("UPDATE projects SET is_active = 1 WHERE id = ?", (project_id,))
    conn.commit()
    conn.close()

def update_project_prompt(project_id, prompt_guide):
    conn = get_db_connection()
    conn.execute("UPDATE projects SET prompt_guide = ? WHERE id = ?", (prompt_guide, project_id))
    conn.commit()
    conn.close()

def delete_project(project_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM projects WHERE id = ?", (project_id,)) # Selections/Categories will cascade
    conn.commit()
    conn.close()


# --- Category Functions ---
def add_category(project_id, name):
    conn = get_db_connection()
    try:
        conn.execute("INSERT INTO categories (project_id, name) VALUES (?, ?)", (project_id, name))
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    except sqlite3.IntegrityError:
        print(f"Category '{name}' already exists for this project.")
        return None
    finally:
        conn.close()

def get_categories(project_id):
    conn = get_db_connection()
    categories = conn.execute("SELECT * FROM categories WHERE project_id = ? ORDER BY name", (project_id,)).fetchall()
    conn.close()
    return categories

# --- Selection Functions ---
def add_selection(project_id, path, is_directory, category_id=None, file_types=None):
    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO selections (project_id, path, is_directory, category_id, file_types)
            VALUES (?, ?, ?, ?, ?)
        """, (project_id, path, is_directory, category_id, file_types))
        conn.commit()
    except sqlite3.IntegrityError: # Path already selected, update it
        conn.execute("""
            UPDATE selections SET category_id = ?, file_types = ? WHERE project_id = ? AND path = ?
        """, (category_id, file_types, project_id, path))
        conn.commit()
        print(f"Selection '{path}' updated for project ID {project_id}.")
    finally:
        conn.close()

def get_selections(project_id, category_id=None):
    conn = get_db_connection()
    query = "SELECT s.*, c.name as category_name FROM selections s LEFT JOIN categories c ON s.category_id = c.id WHERE s.project_id = ?"
    params = [project_id]
    if category_id:
        query += " AND s.category_id = ?"
        params.append(category_id)
    
    selections = conn.execute(query, params).fetchall()
    conn.close()
    return selections

def get_selection_by_path(project_id, path):
    conn = get_db_connection()
    selection = conn.execute("SELECT * FROM selections WHERE project_id = ? AND path = ?", (project_id, path)).fetchone()
    conn.close()
    return selection

def remove_selection(project_id, path):
    conn = get_db_connection()
    conn.execute("DELETE FROM selections WHERE project_id = ? AND path = ?", (project_id, path))
    conn.commit()
    conn.close()

def update_selection_category(project_id, path, category_id):
    conn = get_db_connection()
    conn.execute("UPDATE selections SET category_id = ? WHERE project_id = ? AND path = ?",
                 (category_id, project_id, path))
    conn.commit()
    conn.close()

if __name__ == '__main__':
    # Example Usage (run this file directly to initialize DB)
    if not os.path.exists(DATABASE_NAME):
        init_db()
    else:
        print(f"Database '{DATABASE_NAME}' already exists.")
        # You might want to call init_db() anyway if you are adding tables to an existing DB
        # init_db() # Uncomment to ensure new tables are added if DB exists

    # Test app settings
    # set_app_setting('test_setting', 'test_value')
    # print(f"Test setting value: {get_app_setting('test_setting')}")
    # set_app_setting('last_ui_mode', 'gui')
    # print(f"Last UI Mode: {get_app_setting('last_ui_mode')}")