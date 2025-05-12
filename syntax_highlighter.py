from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from PySide6.QtCore import QRegularExpression, Qt

# --- Color and Style Definitions ---
# Using common VSCode-like colors
STYLES = {
    'keyword': {'color': QColor("#569CD6")}, # Blue
    'control_flow': {'color': QColor("#C586C0")}, # Purple (for if, else, for, while etc.)
    'operator': {'color': QColor("#D4D4D4")}, # Default text color for operators for now
    'brace': {'color': QColor("#D4D4D4")}, 
    'defclass': {'color': QColor("#4EC9B0"), 'font_weight': QFont.Normal}, # Teal for class/def names
    'classname': {'color': QColor("#4EC9B0")}, # Teal for general class names
    'function_call': {'color': QColor("#DCDCAA")}, # Khaki for function calls
    'string': {'color': QColor("#CE9178")}, # Orange/Brown for strings
    'string_alt': {'color': QColor("#CE9178")}, # Same for alternate strings (e.g. f-strings, template literals)
    'comment': {'color': QColor("#6A9955"), 'italic': False}, # Green
    'self_this': {'color': QColor("#9CDCFE")}, # Light blue for self/this
    'numbers': {'color': QColor("#B5CEA8")}, # Light Green/Khaki for numbers
    'decorator_annotation': {'color': QColor("#DCDCAA")}, # Khaki
    'html_tag': {'color': QColor("#569CD6")}, # Blue for HTML tags
    'html_tag_symbol': {'color': QColor("#808080")}, # Grey for <, >, />
    'html_attr_name': {'color': QColor("#9CDCFE")}, # Light blue for attribute names
    'html_attr_value': {'color': QColor("#CE9178")}, # Orange/Brown for attribute values
    'yaml_key': {'color': QColor("#9CDCFE")}, # Light Blue for YAML keys
    'json_key': {'color': QColor("#9CDCFE")}, # Light Blue for JSON keys (text part)
    'boolean_null': {'color': QColor("#569CD6")}, # Blue for true/false/null
}

def create_format(style_name_or_direct_color, font_weight=QFont.Normal, italic=False):
    fmt = QTextCharFormat()
    if isinstance(style_name_or_direct_color, str) and style_name_or_direct_color in STYLES:
        style = STYLES[style_name_or_direct_color]
        if 'color' in style:
            fmt.setForeground(QColor(style['color']))
        else: # Default color if not specified in style, e.g. for operators
            fmt.setForeground(QColor("#D4D4D4")) # Default text color
        if 'font_weight' in style:
            fmt.setFontWeight(style['font_weight'])
        else:
            fmt.setFontWeight(font_weight)
        if 'italic' in style:
            fmt.setFontItalic(style['italic'])
        else:
            fmt.setFontItalic(italic)
            
    elif isinstance(style_name_or_direct_color, QColor):
        fmt.setForeground(style_name_or_direct_color)
        fmt.setFontWeight(font_weight)
        fmt.setFontItalic(italic)
    else: # Fallback for unknown style name
        fmt.setForeground(QColor("#D4D4D4"))
    return fmt

# --- Highlighting Rules Definition ---
# Rules: list of tuples (pattern_str, format_object_or_name, capture_group_index_for_format)
# Capture group 0 is the whole match. Use 1, 2, etc., for specific parts.

PYTHON_RULES = [
    (r'\b(and|assert|async|await|break|continue|del|elif|else|except|finally|for|from|global|if|in|is|lambda|nonlocal|not|or|pass|raise|try|while|with|yield)\b', create_format('control_flow')),
    (r'\b(import|class|def|return)\b', create_format('keyword')),
    (r'\b(self|cls)\b', create_format('self_this')),
    (r'\b(True|False|None)\b', create_format('boolean_null')),
    (r'@[A-Za-z_][A-Za-z0-9_.]*', create_format('decorator_annotation')),
    (r'def\s+([A-Za-z_][A-Za-z0-9_]*)', create_format('defclass'), 1),
    (r'class\s+([A-Za-z_][A-Za-z0-9_]*)', create_format('classname'), 1),
    (r'#.*', create_format('comment')),
    (r'"(\\"|[^"])*"', create_format('string')),
    (r"'(\\'|[^'])*'", create_format('string')),
    (r'(f|fr|rf|F|FR|RF)"""', create_format('string_alt')), # Start f-string triple double
    (r"(f|fr|rf|F|FR|RF)'''", create_format('string_alt')), # Start f-string triple single
    (r'(f|fr|rf|F|FR|RF)"', create_format('string_alt')),  # Start f-string double
    (r"(f|fr|rf|F|FR|RF)'", create_format('string_alt')),  # Start f-string single
    (r'\b([A-Za-z_][A-Za-z0-9_]*)\s*(?=\()', create_format('function_call'), 1), # Function calls
    (r'\b[+-]?\d+\.\d*([eE][+-]?\d+)?\b', create_format('numbers')),
    (r'\b[+-]?\d+([eE][+-]?\d+)?\b', create_format('numbers')),
    (r'\b0[xX][0-9a-fA-F]+\b', create_format('numbers')),
]
PYTHON_MULTILINE_DELIMITERS = {
    'triple_single': {'start': QRegularExpression(r"'''"), 'end': QRegularExpression(r"'''"), 'state_id': 11, 'format': create_format('string')},
    'triple_double': {'start': QRegularExpression(r'"""'), 'end': QRegularExpression(r'"""'), 'state_id': 12, 'format': create_format('string')},
}

JAVASCRIPT_RULES = [
    (r'\b(break|case|catch|class|const|continue|debugger|default|delete|do|else|export|extends|finally|for|from|function|if|import|in|instanceof|let|new|return|super|switch|this|throw|try|typeof|var|void|while|with|yield|async|await)\b', create_format('keyword')),
    (r'\b(true|false|null|undefined|NaN|Infinity)\b', create_format('boolean_null')),
    (r'//.*', create_format('comment')),
    (r'"(\\"|[^"])*"', create_format('string')),
    (r"'(\\'|[^'])*'", create_format('string')),
    (r'`[^`]*`', create_format('string_alt')), # Template literals
    (r'\b([A-Z][A-Za-z0-9_]*)(?=\s*\()', create_format('classname'),1), # Constructor calls
    (r'\b([A-Z][A-Za-z0-9_]*)', create_format('classname')), # Class names
    (r'function\s*([A-Za-z_][A-Za-z0-9_]*)?', create_format('keyword')), # function keyword
    (r'\b(console|document|window|Math|JSON|Object|Array|String|Number|Boolean|Date|RegExp|Promise)\b', create_format('classname')), # Built-ins
    (r'\b([a-zA-Z$_][a-zA-Z0-9$_]*)\s*(?=\()', create_format('function_call'),1), # Function calls
    (r'\b(0[xX][0-9a-fA-F]+|0[oO][0-7]+|0[bB][01]+|[+-]?\d+(\.\d*)?([eE][+-]?\d+)?)\b', create_format('numbers')),
]
JAVASCRIPT_MULTILINE_DELIMITERS = {
    'block_comment': {'start': QRegularExpression(r'/\*'), 'end': QRegularExpression(r'\*/'), 'state_id': 21, 'format': create_format('comment')}
}

DART_RULES = [
    (r'\b(abstract|as|assert|async|await|break|case|catch|class|const|continue|covariant|default|deferred|do|dynamic|else|enum|export|extends|extension|external|factory|final|finally|for|Function|get|hide|if|implements|import|in|interface|is|late|library|mixin|new|on|operator|part|required|rethrow|return|set|show|static|super|switch|sync|this|throw|try|typedef|var|void|while|with|yield)\b', create_format('keyword')),
    (r'\b(true|false|null)\b', create_format('boolean_null')),
    (r'//.*', create_format('comment')),
    (r'"(\\"|[^"])*"', create_format('string')),
    (r"'(\\'|[^'])*'", create_format('string')),
    (r'@[A-Za-z_][A-Za-z0-9_.]*', create_format('decorator_annotation')),
    (r'class\s+([A-Za-z_][A-Za-z0-9_]*)', create_format('classname'), 1),
    (r'\b([A-Z][A-Za-z0-9_]*)\b', create_format('classname')), # Type names
    (r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*(?=\()', create_format('function_call'),1), # Function calls
    (r'\b(0[xX][0-9a-fA-F]+|[+-]?\d+(\.\d*)?([eE][+-]?\d+)?)\b', create_format('numbers')),
]
DART_MULTILINE_DELIMITERS = JAVASCRIPT_MULTILINE_DELIMITERS

HTML_RULES = [
    (r'<!--.*?-->', create_format('comment')),
    (r'<!DOCTYPE[^>]*>', create_format('decorator_annotation', font_weight=QFont.Bold)),
    (r'(<[/!]?\s*)([\w:-]+)', create_format('html_tag'), 2), # Tag name parts
    (r'([\w:-]+)(\s*=\s*)(")', create_format('html_attr_name'), 1), # Attribute name before "
    (r'([\w:-]+)(\s*=\s*)(\')', create_format('html_attr_name'), 1), # Attribute name before '
    (r'(\")(.*?)(\")', create_format('html_attr_value'), 2), # Attribute value in "
    (r"(')(.*?)(')", create_format('html_attr_value'), 2), # Attribute value in '
    (r'[<>!?/]', create_format('html_tag_symbol')), # Tag angle brackets and slashes
]

YAML_RULES = [
    (r'#.*', create_format('comment')),
    (r'^\s*([\w.-]+)\s*:', create_format('yaml_key'), 1), 
    (r'^\s*-\s+', create_format('keyword')), 
    (r'\b(true|True|TRUE|false|False|FALSE|null|Null|NULL|yes|Yes|YES|no|No|NO|on|On|ON|off|Off|OFF)\b', create_format('boolean_null')),
    (r'"(\\"|[^"])*"', create_format('string')),
    (r"'(\\'|[^'])*'", create_format('string')),
    (r'(&[\w-]+|\*[\w-]+)', create_format('decorator_annotation')), 
    (r'!![\w/\.%]+', create_format('classname')), 
    (r'\b([+-]?\d+(\.\d*)?([eE][+-]?\d+)?|0[xX][0-9a-fA-F]+|0o[0-7]+)\b', create_format('numbers')),
    (r'[:\[\]\{\},\|>-]', create_format('operator')), # YAML structure chars
]

JSON_RULES = [
    (r'"((?:\\"|[^"])*)"(?=\s*:)', create_format('json_key'), 1), 
    (r'"(\\"|[^"])*"', create_format('string')), 
    (r'\b(true|false|null)\b', create_format('boolean_null')),
    (r'\b[+-]?\d+(\.\d*)?([eE][+-]?\d+)?\b', create_format('numbers')),
    (r'[:\[\]\{\},]', create_format('operator')), # JSON structure chars
]

HIGHLIGHTER_CONFIGS = {
    '.py': {'rules': PYTHON_RULES, 'multiline_delimiters': PYTHON_MULTILINE_DELIMITERS},
    '.js': {'rules': JAVASCRIPT_RULES, 'multiline_delimiters': JAVASCRIPT_MULTILINE_DELIMITERS},
    '.dart': {'rules': DART_RULES, 'multiline_delimiters': DART_MULTILINE_DELIMITERS},
    '.html': {'rules': HTML_RULES, 'multiline_delimiters': {}},
    '.htm': {'rules': HTML_RULES, 'multiline_delimiters': {}},
    '.yaml': {'rules': YAML_RULES, 'multiline_delimiters': {}},
    '.json': {'rules': JSON_RULES, 'multiline_delimiters': {}},
}

class SyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, document, language_ext):
        super().__init__(document)
        lang_config = HIGHLIGHTER_CONFIGS.get(language_ext.lower())
        
        self.rules = []
        self.multiline_delimiters = {}

        if lang_config:
            for pattern_str, style_format, *nth_group_opt in lang_config.get('rules', []):
                nth_group = nth_group_opt[0] if nth_group_opt else 0
                self.rules.append({
                    'pattern': QRegularExpression(pattern_str),
                    'format': style_format,
                    'nth_group': nth_group
                })
            self.multiline_delimiters = lang_config.get('multiline_delimiters', {})

    def highlightBlock(self, text):
        # Apply single-line rules
        for rule_item in self.rules:
            expression = rule_item['pattern']
            nth_group = rule_item['nth_group']
            
            iterator = expression.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                start_index = match.capturedStart(nth_group)
                length = match.capturedLength(nth_group)
                if start_index != -1 and length > 0:
                    self.setFormat(start_index, length, rule_item['format'])

        self.setCurrentBlockState(0) 

        # --- Multi-line construct handling ---
        active_delimiter_key = None
        current_block_state_id = self.previousBlockState()
        
        if current_block_state_id > 0: 
            for key, delim_config in self.multiline_delimiters.items():
                if delim_config['state_id'] == current_block_state_id:
                    active_delimiter_key = key
                    break
        
        start_offset = 0
        # Iterate through text segment by segment, delimited by multi-line constructs
        while start_offset < len(text):
            if active_delimiter_key: # Continuing an active multi-line construct
                delim_config = self.multiline_delimiters[active_delimiter_key]
                end_match = delim_config['end'].match(text, start_offset)
                
                if end_match.hasMatch(): 
                    end_offset = end_match.capturedStart(0) + end_match.capturedLength(0)
                    self.setFormat(start_offset, end_offset - start_offset, delim_config['format'])
                    self.setCurrentBlockState(0) 
                    active_delimiter_key = None
                    start_offset = end_offset
                else: 
                    self.setFormat(start_offset, len(text) - start_offset, delim_config['format'])
                    self.setCurrentBlockState(delim_config['state_id'])
                    return 
            else: # Check for new starts of multi-line constructs
                earliest_start_pos = len(text)
                next_delimiter_key_to_activate = None

                for key, delim_config in self.multiline_delimiters.items():
                    start_match = delim_config['start'].match(text, start_offset)
                    if start_match.hasMatch() and start_match.capturedStart(0) < earliest_start_pos:
                        earliest_start_pos = start_match.capturedStart(0)
                        next_delimiter_key_to_activate = key
                
                if next_delimiter_key_to_activate:
                    # Single-line rules already applied to the text before earliest_start_pos
                    start_offset = earliest_start_pos # Move to the start of the new multi-line construct
                    active_delimiter_key = next_delimiter_key_to_activate 
                    # Loop will continue and process this newly activated delimiter
                else:
                    # No more multi-line constructs starting in the rest of this block
                    break # Done with this block