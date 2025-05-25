import sqlite3
import os

DATABASE_NAME = 'context_dropper.db'

# Default AI prompt guide for new projects
DEFAULT_NEW_PROJECT_PROMPT = """[2-4 Sentence description of this project goes here]
I need your help with the following task progressing this project forwards. When providing code changes, please output the complete content of any modified files in their entirety. Do not provide only snippets or diffs; I need the full file content to easily replace my existing files. 
My question is:"""

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
            path TEXT NOT NULL, -- Store original case for display, normcase for comparison if needed elsewhere
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
    # Path column will now use COLLATE NOCASE for case-insensitive comparisons and uniqueness
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS selections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            path TEXT NOT NULL COLLATE NOCASE, -- Full path, case-insensitive
            is_directory INTEGER NOT NULL, -- 0 for file, 1 for directory
            category_id INTEGER,
            file_types TEXT, -- Comma-separated, e.g., ".py,.txt,.md" (for directories)
            FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE,
            FOREIGN KEY (category_id) REFERENCES categories (id) ON DELETE SET NULL,
            UNIQUE (project_id, path) -- Uniqueness will also be case-insensitive due to COLLATE NOCASE on path
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
    # print(f"Database '{DATABASE_NAME}' initialized with updated schema (selections.path COLLATE NOCASE).")

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
def add_project(name, path, prompt_guide=DEFAULT_NEW_PROJECT_PROMPT):
    """
    Adds a new project to the database.
    Args:
        name (str): The name of the project.
        path (str): The root path of the project.
        prompt_guide (str, optional): The initial AI prompt guide.
                                      Defaults to DEFAULT_NEW_PROJECT_PROMPT.
    Returns:
        int or None: The ID of the newly created project, or None if an error occurred.
    """
    conn = get_db_connection()
    try:
        # Store the original path for projects, normcasing is mainly for selections uniqueness/lookup
        # However, for consistency in how project paths are handled if they were ever used in complex lookups,
        # normcasing here too might be safer, but for display, original is often preferred.
        # For now, let's keep project.path as original, as it's mostly for display and setting root.
        # If we find issues, we can normcase project.path as well.
        conn.execute("INSERT INTO projects (name, path, prompt_guide) VALUES (?, ?, ?)",
                     (name, os.path.normpath(path), prompt_guide)) # normpath for cleanup
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    except sqlite3.IntegrityError:
        # print(f"Project with name '{name}' already exists.")
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
    conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
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
        # print(f"Category '{name}' already exists for this project.")
        return None
    finally:
        conn.close()

def get_categories(project_id):
    conn = get_db_connection()
    categories = conn.execute("SELECT * FROM categories WHERE project_id = ? ORDER BY name", (project_id,)).fetchall()
    conn.close()
    return categories

def remove_category_and_uncategorize_items(category_id):
    conn = get_db_connection()
    try:
        conn.execute("UPDATE selections SET category_id = NULL WHERE category_id = ?", (category_id,))
        conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Error removing category {category_id} and uncategorizing items: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

# --- Selection Functions ---
def add_selection(project_id, path, is_directory, category_id=None, file_types=None):
    conn = get_db_connection()
    # Path is already normcased by the caller (MainWindow) before being passed here.
    # And the table column `selections.path` is `COLLATE NOCASE`.
    # So, direct insertion of the (already normcased) path is fine.
    # os.path.normpath is still good for cleaning slashes, etc.
    clean_path = os.path.normpath(path) # Path is already normcased by caller
    # print(f"# DB_DEBUG: add_selection - ProjID={project_id}, Path='{clean_path}', IsDir={is_directory}")
    try:
        conn.execute("""
            INSERT INTO selections (project_id, path, is_directory, category_id, file_types)
            VALUES (?, ?, ?, ?, ?)
        """, (project_id, clean_path, is_directory, category_id, file_types))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.execute("""
            UPDATE selections SET category_id = ?, file_types = ?, is_directory = ?
            WHERE project_id = ? AND path = ? 
        """, (category_id, file_types, is_directory, project_id, clean_path)) # Path comparison will be case-insensitive
        conn.commit()
        # print(f"# DB_DEBUG: Updated selection: ProjID={project_id}, Path='{clean_path}'")
    finally:
        conn.close()

def get_selections(project_id, category_id=None):
    conn = get_db_connection()
    query = """
        SELECT s.id, s.project_id, s.path, s.is_directory, s.category_id, s.file_types, c.name as category_name
        FROM selections s
        LEFT JOIN categories c ON s.category_id = c.id
        WHERE s.project_id = ?
    """
    params = [project_id]
    if category_id is not None:
        query += " AND s.category_id = ?"
        params.append(category_id)
    # Paths retrieved will be as stored; comparison in WHERE clause is case-insensitive.
    selections = conn.execute(query, params).fetchall()
    conn.close()
    return selections

def get_selection_by_path(project_id, path):
    conn = get_db_connection()
    # Path is already normcased by the caller.
    # The WHERE path = ? comparison will be case-insensitive due to COLLATE NOCASE.
    clean_path = os.path.normpath(path)
    # print(f"# DB_DEBUG: get_selection_by_path - Querying ProjID={project_id}, Path='{clean_path}'")
    selection = conn.execute("SELECT * FROM selections WHERE project_id = ? AND path = ?", (project_id, clean_path)).fetchone()
    conn.close()
    return selection

def remove_selection(project_id, path):
    conn = get_db_connection()
    # Path is already normcased by the caller.
    # The WHERE path = ? comparison will be case-insensitive.
    clean_path = os.path.normpath(path)
    # print(f"# DB_DEBUG: remove_selection - Removing ProjID={project_id}, Path='{clean_path}'")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM selections WHERE project_id = ? AND path = ?", (project_id, clean_path))
    conn.commit()
    # if cursor.rowcount > 0:
        # print(f"# DB_DEBUG: Successfully removed {cursor.rowcount} row(s) for path '{clean_path}'")
    # else:
        # print(f"# DB_DEBUG: No rows removed for path '{clean_path}'. It might not exist or case mismatch (pre-COLLATE NOCASE data).")
    conn.close()

def update_selection_category(project_id, path, category_id):
    """
    Updates the category_id for a specific selection.
    Args:
        project_id (int): The ID of the project.
        path (str): The normcased path of the selection.
        category_id (int or None): The new category ID, or None to uncategorize.
    """
    conn = get_db_connection()
    # Path is already normcased by the caller.
    clean_path = os.path.normpath(path)
    # print(f"# DB_DEBUG: update_selection_category - Updating ProjID={project_id}, Path='{clean_path}', CatID={category_id}")
    try:
        # The SQL statement requires 3 placeholders: category_id, project_id, path
        # The parameters should be in the order: (new_category_id, project_id_for_where, path_for_where)
        conn.execute("UPDATE selections SET category_id = ? WHERE project_id = ? AND path = ?",
                     (category_id, project_id, clean_path)) # Corrected parameter order and count
        conn.commit()
        # print(f"# DB_DEBUG: Successfully updated category for path '{clean_path}'")
    except sqlite3.Error as e:
        print(f"Error updating selection category for path '{clean_path}': {e}")
        conn.rollback() # Rollback on error
    finally:
        conn.close()

if __name__ == '__main__':
    if not os.path.exists(DATABASE_NAME):
        print(f"Database '{DATABASE_NAME}' not found. Initializing with new schema...")
        init_db()
    else:
        # print(f"Database '{DATABASE_NAME}' already exists. Ensuring schema is up-to-date...")
        # Calling init_db() on an existing DB won't change schema of existing tables by default.
        # For the COLLATE NOCASE change to take effect on an existing DB,
        # the table would need to be altered or recreated.
        # Simplest for user is to delete the DB file if issues persist.
        init_db()
