# context_generator.py
# Handles the generation of context.txt content.

import os
from pathlib import Path # For robust path manipulation
import collections

# Default names to ignore when generating the project tree summary.
# The actual context.txt filename will be added to this list dynamically.
DEFAULT_TREE_IGNORED_NAMES = [
    '__pycache__', 'node_modules', 'target', 'build', '.venv', 'venv',
    '.git', 'dist', '.DS_Store'
]

def generate_project_tree_summary(project_path, selections_for_summary, context_txt_leaf_name="context.txt"):
    """
    Generates a textual summary of the project structure, focusing on selected items.
    Args:
        project_path (str): The absolute path to the project's root directory (original case).
        selections_for_summary (list): A list of dictionaries, where each dictionary
                                       represents a selected item and contains at least
                                       'path' (normcased), 'is_directory', and 'file_types'.
        context_txt_leaf_name (str): The leaf name of the context file (e.g., "context.txt")
                                     to ensure it's marked as ignored in the tree.
    Returns:
        str: A string representing the project tree summary.
    """
    summary_lines = []
    # Stores {normcased_relative_path: selection_details} for quick lookup
    relative_selected_paths_data = {}

    if not os.path.isdir(project_path):
        return f"Error: Project path '{project_path}' is not a valid directory."

    normcased_project_path = os.path.normcase(os.path.normpath(project_path))
    normalized_original_project_path = os.path.normpath(project_path)

    for sel_data in selections_for_summary:
        s_path_normcased = sel_data['path'] # This is already normcased from DB

        if s_path_normcased.startswith(normcased_project_path + os.sep) or s_path_normcased == normcased_project_path:
            try:
                # Create relative path from normcased selection against normcased project path
                rel_s_path = os.path.relpath(s_path_normcased, normcased_project_path)
            except ValueError:
                rel_s_path = s_path_normcased # Fallback

            if rel_s_path == ".":
                rel_s_path = "" # Root selection relative path is empty string

            normcased_rel_s_path = os.path.normcase(rel_s_path)
            relative_selected_paths_data[normcased_rel_s_path] = {
                'is_directory': sel_data['is_directory'],
                'file_types': sel_data['file_types']
            }

    outside_project_selections = []
    for sel in selections_for_summary:
        sel_path_normcased = sel['path']
        if not (sel_path_normcased.startswith(normcased_project_path + os.sep) or \
                sel_path_normcased == normcased_project_path):
            outside_project_selections.append(sel)

    tree_ignored_names = DEFAULT_TREE_IGNORED_NAMES[:] + [context_txt_leaf_name]

    def is_file_included_by_directory_filter(normcased_file_rel_path, file_name_original_case):
        """
        Checks if a file is included due to a filter on any of its selected ancestor directories.
        Args:
            normcased_file_rel_path (str): Normcased relative path of the file.
            file_name_original_case (str): Original case filename.
        Returns:
            bool: True if included by a directory filter, False otherwise.
        """
        path_obj = Path(normcased_file_rel_path)
        
        # Iterate from the immediate parent directory upwards to the project root
        # path_obj.parts gives ('src', 'subdir', 'file.py')
        # We want to check ancestors: 'src/subdir', then 'src', then '' (root)
        for i in range(len(path_obj.parts) - 1, -1, -1): # -1 to also check project root ("")
            if i == 0: # Ancestor is the project root itself
                ancestor_rel_path_normcased = "" 
            else:
                # Path(*path_obj.parts[:i]) constructs the path from the first 'i' parts
                # .as_posix() ensures '/' separators, then normcase for consistent key format
                ancestor_rel_path_normcased = os.path.normcase(Path(*path_obj.parts[:i]).as_posix())

            if ancestor_rel_path_normcased in relative_selected_paths_data:
                dir_selection_details = relative_selected_paths_data[ancestor_rel_path_normcased]
                
                if dir_selection_details['is_directory']: # Ensure it's a selected directory
                    file_types_str = dir_selection_details['file_types']
                    
                    if file_types_str is None: # None means "ALL" files in this selected directory
                        return True 
                    
                    allowed_extensions = []
                    exact_filenames_normcased = []
                    for ft_raw in file_types_str.split(','):
                        ft = ft_raw.strip()
                        if not ft: continue
                        if ft.startswith('.'): # Extension
                            allowed_extensions.append(ft.lower()) # Extensions are typically lowercase
                        else: # Exact filename
                            exact_filenames_normcased.append(os.path.normcase(ft))
                    
                    file_name_normcased = os.path.normcase(file_name_original_case)
                    
                    if file_name_normcased in exact_filenames_normcased:
                        return True
                    if any(file_name_normcased.endswith(ext) for ext in allowed_extensions):
                        return True
        return False

    def build_tree(current_dir_abs_original_case, current_dir_rel_original_case, prefix=""):
        try:
            entries = []
            raw_entries = os.listdir(current_dir_abs_original_case)
            for entry_name_original_case in raw_entries:
                entry_rel_path_for_check_original_case = os.path.join(current_dir_rel_original_case, entry_name_original_case) if current_dir_rel_original_case else entry_name_original_case
                normcased_entry_rel_path_for_check = os.path.normcase(entry_rel_path_for_check_original_case)
                is_explicitly_selected_entry = normcased_entry_rel_path_for_check in relative_selected_paths_data

                if not entry_name_original_case.startswith('.') and entry_name_original_case not in tree_ignored_names:
                    entries.append(entry_name_original_case)
                elif entry_name_original_case.startswith('.') and is_explicitly_selected_entry :
                     entries.append(entry_name_original_case)
                elif entry_name_original_case in tree_ignored_names and is_explicitly_selected_entry:
                     entries.append(entry_name_original_case)
            entries.sort()
        except OSError:
            summary_lines.append(f"{prefix}└── [Error listing directory: {os.path.basename(current_dir_abs_original_case)}]")
            return

        for i, entry_name_original_case in enumerate(entries):
            is_last = (i == len(entries) - 1)
            entry_abs_path_original_case = os.path.join(current_dir_abs_original_case, entry_name_original_case)
            entry_rel_path_original_case = os.path.join(current_dir_rel_original_case, entry_name_original_case) if current_dir_rel_original_case else entry_name_original_case
            normcased_entry_rel_path = os.path.normcase(entry_rel_path_original_case)

            connector = "└── " if is_last else "├── "
            line = prefix + connector + entry_name_original_case # Display original case

            is_dir_entry = os.path.isdir(entry_abs_path_original_case)
            is_selected_explicitly = normcased_entry_rel_path in relative_selected_paths_data
            
            should_mark_asterisk = False
            if is_selected_explicitly:
                # If it's a directory selected explicitly, it gets marked.
                # If it's a file selected explicitly, it gets marked.
                should_mark_asterisk = True
            elif not is_dir_entry: # It's a file, not explicitly selected
                # Check if it's included by an ancestor directory's filter
                if is_file_included_by_directory_filter(normcased_entry_rel_path, entry_name_original_case):
                    should_mark_asterisk = True
            
            if should_mark_asterisk:
                line += " [*]"
                # If the item itself is an explicitly selected directory, add its filter info
                if is_selected_explicitly and is_dir_entry: # Redundant check for is_dir_entry, but safe
                    dir_details = relative_selected_paths_data[normcased_entry_rel_path]
                    if dir_details['is_directory']: # Should always be true if is_selected_explicitly and is_dir_entry
                        ft = dir_details['file_types']
                        line += f" (Dir: {ft if ft else 'ALL'})"
            elif is_dir_entry: # Directory not marked with '*', check for '[...]'
                is_ancestor_of_selected = any(
                    sel_rel_key.startswith(normcased_entry_rel_path + os.sep) for sel_rel_key in relative_selected_paths_data
                )
                if is_ancestor_of_selected:
                    line += " [...]"
            
            summary_lines.append(line)

            if is_dir_entry:
                is_ancestor_of_selected_for_recursion = any(
                    sel_rel_key.startswith(normcased_entry_rel_path + os.sep) for sel_rel_key in relative_selected_paths_data
                )
                should_recurse = is_selected_explicitly or is_ancestor_of_selected_for_recursion
                if should_recurse or len(prefix) < 12 :
                    new_prefix = prefix + ("    " if is_last else "│   ")
                    build_tree(entry_abs_path_original_case, entry_rel_path_original_case, new_prefix)

    project_base_name = os.path.basename(project_path)
    root_marker = ""
    if "" in relative_selected_paths_data: # Project root itself is selected
        root_marker = " [*]"
        if relative_selected_paths_data[""]['is_directory']:
            ft = relative_selected_paths_data[""]['file_types']
            root_marker += f" (Dir: {ft if ft else 'ALL'})"

    summary_lines.append(f"{project_base_name}{os.sep}{root_marker}")
    build_tree(normalized_original_project_path, "", "  ")

    if outside_project_selections:
        summary_lines.append("\n----- Other Selected Items (Outside Project Root) -----")
        sorted_outside_selections = sorted(outside_project_selections, key=lambda s: s['path'])
        for sel_info in sorted_outside_selections:
            display_ops_path = sel_info['path'] # This is normcased
            if sel_info['is_directory']:
                ft_display = sel_info['file_types'] if sel_info['file_types'] else "ALL"
                summary_lines.append(f"{display_ops_path} [*] (Dir: {ft_display})")
            else:
                summary_lines.append(f"{display_ops_path} [*]")
    return "\n".join(summary_lines)


def generate_context_file_data(project_path, selections, binary_extensions, context_txt_leaf_name="context.txt"):
    """
    Generates the complete content for the context.txt file.
    Args:
        project_path (str): The absolute path to the project's root directory (original case).
        selections (list): A list of selection dictionaries from the database (paths are normcased).
        binary_extensions (list): A list of file extensions to treat as binary.
        context_txt_leaf_name (str): The name of the context file being generated.
    Returns:
        list: A list of strings, where each string is a line for the context.txt file.
    """
    context_content_lines = []
    normalized_original_project_path = os.path.normpath(project_path)
    normcased_project_path = os.path.normcase(normalized_original_project_path)
    context_txt_abs_path_normcased = os.path.normcase(os.path.join(normalized_original_project_path, context_txt_leaf_name))

    context_content_lines.append("----- Project Structure (Files included in context file indicated with *) -----")
    summary_tree_str = generate_project_tree_summary(project_path, selections, context_txt_leaf_name)
    context_content_lines.append(summary_tree_str)
    context_content_lines.append("----- End Project Structure -----\n")

    files_to_include = {}  # Stores {normcased_absolute_path -> display_path_for_header}

    for sel in selections:
        sel_path_normcased = sel['path'] 

        if not os.path.exists(sel_path_normcased):
            print(f"Warning: Selected path does not exist, skipping: {sel_path_normcased}")
            header_path_for_warning = sel_path_normcased
            if sel_path_normcased.startswith(normcased_project_path + os.sep):
                try:
                    header_path_for_warning = os.path.relpath(sel_path_normcased, normcased_project_path)
                except ValueError: pass
            context_content_lines.append(f"----- Warning: Selected path not found: {header_path_for_warning} -----")
            continue

        if sel['is_directory']:
            allowed_extensions = []
            exact_filenames_normcased = [] 
            if sel['file_types']:
                for ft_raw in sel['file_types'].split(','):
                    ft = ft_raw.strip()
                    if not ft: continue
                    if ft.startswith('.'):
                        allowed_extensions.append(ft.lower())
                    else:
                        exact_filenames_normcased.append(os.path.normcase(ft))

            for root_normcased, dirs, files_original_case in os.walk(sel_path_normcased):
                dirs[:] = [d for d in dirs if d not in DEFAULT_TREE_IGNORED_NAMES and not d.startswith('.')]
                for file_name_original_case in files_original_case:
                    full_file_path_abs_normcased = os.path.normcase(os.path.normpath(os.path.join(root_normcased, file_name_original_case)))
                    file_name_normcased = os.path.normcase(file_name_original_case)

                    if full_file_path_abs_normcased == context_txt_abs_path_normcased:
                        continue

                    include_file = False
                    if not allowed_extensions and not exact_filenames_normcased: # No filters = include all
                        include_file = True
                    elif file_name_normcased in exact_filenames_normcased:
                        include_file = True
                    elif any(file_name_normcased.endswith(ext) for ext in allowed_extensions):
                        include_file = True

                    if include_file:
                        display_path_for_header = full_file_path_abs_normcased 
                        if full_file_path_abs_normcased.startswith(normcased_project_path + os.sep):
                            try: # Attempt to reconstruct original-case relative path for display
                                original_case_rel_path = os.path.relpath(full_file_path_abs_normcased.replace(normcased_project_path, normalized_original_project_path, 1), normalized_original_project_path)
                                display_path_for_header = original_case_rel_path
                            except ValueError: 
                                 display_path_for_header = os.path.relpath(full_file_path_abs_normcased, normcased_project_path)
                        elif sel_path_normcased != normcased_project_path : 
                             display_path_for_header = f"EXTERNAL:{os.path.basename(full_file_path_abs_normcased)} (from {os.path.basename(sel_path_normcased)}{os.sep}...)"
                        files_to_include[full_file_path_abs_normcased] = display_path_for_header
        else:  # Single file selection
            if sel_path_normcased == context_txt_abs_path_normcased:
                continue
            
            display_path_for_header = sel_path_normcased
            if sel_path_normcased.startswith(normcased_project_path + os.sep):
                try:
                    original_case_rel_path = os.path.relpath(sel_path_normcased.replace(normcased_project_path, normalized_original_project_path, 1), normalized_original_project_path)
                    display_path_for_header = original_case_rel_path
                except ValueError:
                    display_path_for_header = os.path.relpath(sel_path_normcased, normcased_project_path)
            elif sel_path_normcased != normcased_project_path: 
                display_path_for_header = f"EXTERNAL:{os.path.basename(sel_path_normcased)}"
            files_to_include[sel_path_normcased] = display_path_for_header

    sorted_file_paths_abs_normcased = sorted(files_to_include.keys(), key=lambda p_normcased: files_to_include[p_normcased])

    for file_path_abs_normcased in sorted_file_paths_abs_normcased:
        display_rel_path_for_header = files_to_include[file_path_abs_normcased]
        try:
            is_binary = any(file_path_abs_normcased.endswith(ext.lower()) for ext in binary_extensions)
            if not is_binary:
                try:
                    with open(file_path_abs_normcased, 'rb') as f_check:
                        if b'\x00' in f_check.read(1024): is_binary = True
                except Exception: is_binary = True

            if is_binary:
                context_content_lines.append(f"----- File: {display_rel_path_for_header} (Skipped Binary File) -----")
                context_content_lines.append(f"----- End File: {display_rel_path_for_header} -----\n")
                # print(f"Skipped binary file: {display_rel_path_for_header}") # Redundant with context file
                continue

            with open(file_path_abs_normcased, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            context_content_lines.append(f"----- File: {display_rel_path_for_header} -----")
            context_content_lines.append(content.strip())
            context_content_lines.append(f"----- End File: {display_rel_path_for_header} -----\n")
        except Exception as e:
            context_content_lines.append(f"----- Error reading file: {display_rel_path_for_header} -----")
            context_content_lines.append(f"Error: {str(e)}")
            context_content_lines.append(f"----- End Error: {display_rel_path_for_header} -----\n")
            print(f"Error reading {display_rel_path_for_header} (normcased path: {file_path_abs_normcased}): {e}")

    return context_content_lines
