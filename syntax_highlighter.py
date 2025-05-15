from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from PySide6.QtCore import QRegularExpression, Qt

# --- Color and Style Definitions ---
# Using common VSCode-like colors
STYLES = {
    'keyword': {'color': QColor("#569CD6")}, # Blue
    'control_flow': {'color': QColor("#C586C0")}, # Purple (for if, else, for, while etc.)
    'operator': {'color': QColor("#D4D4D4")}, # Default text color for operators
    'brace': {'color': QColor("#D4D4D4")},
    'defclass': {'color': QColor("#4EC9B0"), 'font_weight': QFont.Normal}, # Teal for class/def/func names
    'classname': {'color': QColor("#4EC9B0")}, # Teal for general class/type names
    'function_call': {'color': QColor("#DCDCAA")}, # Khaki for function calls
    'string': {'color': QColor("#CE9178")}, # Orange/Brown for strings
    'string_alt': {'color': QColor("#CE9178")}, # Same for alternate strings
    'comment': {'color': QColor("#6A9955"), 'italic': False}, # Green
    'self_this_super': {'color': QColor("#9CDCFE")}, # Light blue for self/this/super
    'numbers': {'color': QColor("#B5CEA8")}, # Light Green/Khaki for numbers disadvantaged
    'decorator_annotation_attribute': {'color': QColor("#DCDCAA")}, # Khaki for decorators, annotations, attributes
    'preprocessor': {'color': QColor("#C586C0")}, # Purple for preprocessor directives
    'html_tag': {'color': QColor("#569CD6")},
    'html_tag_symbol': {'color': QColor("#808080")},
    'html_attr_name': {'color': QColor("#9CDCFE")},
    'html_attr_value': {'color': QColor("#CE9178")},
    'yaml_key': {'color': QColor("#9CDCFE")},
    'json_key': {'color': QColor("#9CDCFE")},
    'boolean_null_nil': {'color': QColor("#569CD6")}, # Blue for true/false/null/nil
    'variable': {'color': QColor("#9CDCFE")}, # Light blue for variables (e.g. PHP $var)
    'symbol': {'color': QColor("#4EC9B0")}, # Teal for symbols (e.g. Ruby :symbol)
    'macro': {'color': QColor("#DCDCAA"), 'font_weight': QFont.Bold }, # Khaki, bold for macros (e.g. Rust println!)
    'lifetime': {'color': QColor("#569CD6")}, # Blue for lifetimes (e.g. Rust 'a)
}

def create_format(style_name_or_direct_color, font_weight=QFont.Normal, italic=False):
    fmt = QTextCharFormat()
    if isinstance(style_name_or_direct_color, str) and style_name_or_direct_color in STYLES:
        style = STYLES[style_name_or_direct_color]
        fmt.setForeground(QColor(style.get('color', "#D4D4D4")))
        fmt.setFontWeight(style.get('font_weight', font_weight))
        fmt.setFontItalic(style.get('italic', italic))
    elif isinstance(style_name_or_direct_color, QColor):
        fmt.setForeground(style_name_or_direct_color)
        fmt.setFontWeight(font_weight)
        fmt.setFontItalic(italic)
    else: # Fallback
        fmt.setForeground(QColor("#D4D4D4"))
    return fmt

# --- Highlighting Rules Definition ---

PYTHON_RULES = [
    (r'\b(and|assert|async|await|break|continue|del|elif|else|except|finally|for|from|global|if|in|is|lambda|nonlocal|not|or|pass|raise|try|while|with|yield)\b', create_format('control_flow')),
    (r'\b(import|class|def|return|from|nonlocal|global|pass|assert|del|lambda|yield|async|await)\b', create_format('keyword')),
    (r'\b(self|cls)\b', create_format('self_this_super')),
    (r'\b(True|False|None)\b', create_format('boolean_null_nil')),
    (r'@[A-Za-z_][A-Za-z0-9_.]*', create_format('decorator_annotation_attribute')),
    (r'def\s+([A-Za-z_][A-Za-z0-9_]*)', create_format('defclass'), 1),
    (r'class\s+([A-Za-z_][A-Za-z0-9_]*)', create_format('classname'), 1),
    (r'#.*', create_format('comment')),
    (r'"(\\"|[^"])*"', create_format('string')),
    (r"'(\\'|[^'])*'", create_format('string')),
    (r'(f|fr|rf|F|FR|RF)"""', create_format('string_alt')),
    (r"(f|fr|rf|F|FR|RF)'''", create_format('string_alt')),
    (r'(f|fr|rf|F|FR|RF)"', create_format('string_alt')),
    (r"(f|fr|rf|F|FR|RF)'", create_format('string_alt')),
    (r'\b([A-Za-z_][A-Za-z0-9_]*)\s*(?=\()', create_format('function_call'), 1),
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
    (r'\b(true|false|null|undefined|NaN|Infinity)\b', create_format('boolean_null_nil')),
    (r'//.*', create_format('comment')),
    (r'"(\\"|[^"])*"', create_format('string')),
    (r"'(\\'|[^'])*'", create_format('string')),
    (r'`[^`]*`', create_format('string_alt')), 
    (r'\b([A-Z][A-Za-z0-9_]*)(?=\s*\()', create_format('classname'),1),
    (r'\b([A-Z][A-Za-z0-9_]*)', create_format('classname')),
    (r'function\s*([A-Za-z_][A-Za-z0-9_]*)?', create_format('keyword')),
    (r'\b(console|document|window|Math|JSON|Object|Array|String|Number|Boolean|Date|RegExp|Promise)\b', create_format('classname')),
    (r'\b([a-zA-Z$_][a-zA-Z0-9$_]*)\s*(?=\()', create_format('function_call'),1),
    (r'\b(0[xX][0-9a-fA-F]+|0[oO][0-7]+|0[bB][01]+|[+-]?\d+(\.\d*)?([eE][+-]?\d+)?)\b', create_format('numbers')),
]
JAVASCRIPT_MULTILINE_DELIMITERS = {
    'block_comment': {'start': QRegularExpression(r'/\*'), 'end': QRegularExpression(r'\*/'), 'state_id': 21, 'format': create_format('comment')}
}

DART_RULES = [
    (r'\b(abstract|as|assert|async|await|break|case|catch|class|const|continue|covariant|default|deferred|do|dynamic|else|enum|export|extends|extension|external|factory|final|finally|for|Function|get|hide|if|implements|import|in|interface|is|late|library|mixin|new|on|operator|part|required|rethrow|return|set|show|static|super|switch|sync|this|throw|try|typedef|var|void|while|with|yield)\b', create_format('keyword')),
    (r'\b(true|false|null)\b', create_format('boolean_null_nil')),
    (r'//.*', create_format('comment')),
    (r'"(\\"|[^"])*"', create_format('string')),
    (r"'(\\'|[^'])*'", create_format('string')),
    (r'@[A-Za-z_][A-Za-z0-9_.]*', create_format('decorator_annotation_attribute')),
    (r'class\s+([A-Za-z_][A-Za-z0-9_]*)', create_format('classname'), 1),
    (r'\b([A-Z][A-Za-z0-9_]*)\b', create_format('classname')), 
    (r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*(?=\()', create_format('function_call'),1),
    (r'\b(0[xX][0-9a-fA-F]+|[+-]?\d+(\.\d*)?([eE][+-]?\d+)?)\b', create_format('numbers')),
]
DART_MULTILINE_DELIMITERS = JAVASCRIPT_MULTILINE_DELIMITERS # Shares block comment style

HTML_RULES = [
    (r'<!--[\s\S]*?-->', create_format('comment')), # HTML comments
    (r'<!DOCTYPE[^>]*>', create_format('decorator_annotation_attribute', font_weight=QFont.Bold)),
    (r'(<[/!]?\s*)([\w:-]+)', create_format('html_tag'), 2), 
    (r'([\w:-]+)(\s*=\s*)(")', create_format('html_attr_name'), 1), 
    (r'([\w:-]+)(\s*=\s*)(\')', create_format('html_attr_name'), 1), 
    (r'(\")(.*?)(\")', create_format('html_attr_value'), 2), 
    (r"(')(.*?)(')", create_format('html_attr_value'), 2), 
    (r'[<>!?/]', create_format('html_tag_symbol')), 
]

YAML_RULES = [
    (r'#.*', create_format('comment')),
    (r'^\s*([\w.-]+)\s*:', create_format('yaml_key'), 1), 
    (r'^\s*-\s+', create_format('keyword')), 
    (r'\b(true|True|TRUE|false|False|FALSE|null|Null|NULL|yes|Yes|YES|no|No|NO|on|On|ON|off|Off|OFF)\b', create_format('boolean_null_nil')),
    (r'"(\\"|[^"])*"', create_format('string')),
    (r"'(\\'|[^'])*'", create_format('string')),
    (r'(&[\w-]+|\*[\w-]+)', create_format('decorator_annotation_attribute')), 
    (r'!![\w/\.%]+', create_format('classname')), 
    (r'\b([+-]?\d+(\.\d*)?([eE][+-]?\d+)?|0[xX][0-9a-fA-F]+|0o[0-7]+)\b', create_format('numbers')),
    (r'[:\[\]\{\},\|>-]', create_format('operator')), 
]

JSON_RULES = [
    (r'"((?:\\"|[^"])*)"(?=\s*:)', create_format('json_key'), 1), 
    (r'"(\\"|[^"])*"', create_format('string')), 
    (r'\b(true|false|null)\b', create_format('boolean_null_nil')),
    (r'\b[+-]?\d+(\.\d*)?([eE][+-]?\d+)?\b', create_format('numbers')),
    (r'[:\[\]\{\},]', create_format('operator')), 
]

# --- New Language Definitions ---

JAVA_RULES = [
    (r'\b(abstract|assert|boolean|break|byte|case|catch|char|class|const|continue|default|do|double|else|enum|exports|extends|final|finally|float|for|goto|if|implements|import|instanceof|int|interface|long|module|native|new|open|opens|package|private|protected|public|provides|requires|return|short|static|strictfp|super|switch|synchronized|this|throw|throws|to|transient|transitive|try|uses|void|volatile|while)\b', create_format('keyword')),
    (r'\b(true|false|null)\b', create_format('boolean_null_nil')),
    (r'//.*', create_format('comment')),
    (r'"(\\"|[^"])*"', create_format('string')),
    (r"'(\\'|[^'])'", create_format('string')), # char literal
    (r'@[A-Za-z_][A-Za-z0-9_.]*', create_format('decorator_annotation_attribute')),
    (r'class\s+([A-Za-z_][A-Za-z0-9_]*)', create_format('classname'), 1),
    (r'interface\s+([A-Za-z_][A-Za-z0-9_]*)', create_format('classname'), 1),
    (r'enum\s+([A-Za-z_][A-Za-z0-9_]*)', create_format('classname'), 1),
    (r'\b([A-Z][A-Za-z0-9_]*)\b', create_format('classname')), # Type names
    (r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*(?=\()', create_format('function_call'),1),
    (r'\b(0[xX][0-9a-fA-F]+[lL]?|[+-]?\d+[lLdDfF]?(\.\d*)?([eE][+-]?\d+)?[lLdDfF]?)\b', create_format('numbers')),
]
JAVA_MULTILINE_DELIMITERS = JAVASCRIPT_MULTILINE_DELIMITERS # /* ... */

CSHARP_RULES = [
    (r'\b(abstract|as|base|bool|break|byte|case|catch|char|checked|class|const|continue|decimal|default|delegate|do|double|else|enum|event|explicit|extern|false|finally|fixed|float|for|foreach|goto|if|implicit|in|int|interface|internal|is|lock|long|namespace|new|null|object|operator|out|override|params|private|protected|public|readonly|ref|return|sbyte|sealed|short|sizeof|stackalloc|static|string|struct|switch|this|throw|true|try|typeof|uint|ulong|unchecked|unsafe|ushort|using|virtual|void|volatile|while|add|alias|ascending|async|await|by|descending|dynamic|equals|from|get|global|group|into|join|let|nameof|on|orderby|partial|remove|select|set|unmanaged|value|var|when|where|yield)\b', create_format('keyword')),
    (r'#\s*(if|else|elif|endif|define|undef|warning|error|line|region|endregion|pragma)\b', create_format('preprocessor')),
    (r'//.*', create_format('comment')),
    (r'"(\\"|[^"])*"', create_format('string')),
    (r'@"[^"]*(""[^"]*)*"', create_format('string_alt')), # Verbatim strings
    (r'\$@"[^"]*(""[^"]*)*"|\$"{[^"]*}*"', create_format('string_alt')), # Interpolated verbatim/regular strings
    (r"'[^']'", create_format('string')), # char literal
    (r'\[\s*[A-Za-z_][A-Za-z0-9_.:]*\s*\]', create_format('decorator_annotation_attribute')), # Attributes
    (r'class\s+([A-Za-z_][A-Za-z0-9_]*)', create_format('classname'), 1),
    (r'interface\s+([A-Za-z_][A-Za-z0-9_]*)', create_format('classname'), 1),
    (r'struct\s+([A-Za-z_][A-Za-z0-9_]*)', create_format('classname'), 1),
    (r'enum\s+([A-Za-z_][A-Za-z0-9_]*)', create_format('classname'), 1),
    (r'\b([A-Z][A-Za-z0-9_<>?]*)\b', create_format('classname')), # Type names, including generics
    (r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*(?=\()', create_format('function_call'),1),
    (r'\b(0[xX][0-9a-fA-F]+[uUlL]?|[+-]?\d+[uUlLdfmDFM]?(\.\d*)?([eE][+-]?\d+)?[uUlLdfmDFM]?)\b', create_format('numbers')),
]
CSHARP_MULTILINE_DELIMITERS = JAVASCRIPT_MULTILINE_DELIMITERS

GO_RULES = [
    (r'\b(break|case|chan|const|continue|default|defer|else|fallthrough|for|func|go|goto|if|import|interface|map|package|range|return|select|struct|switch|type|var)\b', create_format('keyword')),
    (r'\b(true|false|nil|iota)\b', create_format('boolean_null_nil')),
    (r'//.*', create_format('comment')),
    (r'"(\\"|[^"])*"', create_format('string')),
    (r'`[^`]*`', create_format('string_alt')), # Raw string literals
    (r'func\s+([A-Za-z_][A-Za-z0-9_]*)', create_format('defclass'), 1), # Function definition
    (r'type\s+([A-Za-z_][A-Za-z0-9_]*)\s+(struct|interface)', create_format('classname'), 1), # Type definition
    (r'\b([A-Z][A-Za-z0-9_]*)\b', create_format('classname')), # Exported names / Types
    (r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*(?=\()', create_format('function_call'),1),
    (r'\b(0[xX][0-9a-fA-F]+|0[oO]?[0-7]+|[+-]?\d+(\.\d*)?([eE][+-]?\d+)?(i)?)\b', create_format('numbers')), # Includes complex
]
GO_MULTILINE_DELIMITERS = JAVASCRIPT_MULTILINE_DELIMITERS

PHP_RULES = [
    (r'\b(__halt_compiler|abstract|and|array|as|break|callable|case|catch|class|clone|const|continue|declare|default|die|do|echo|else|elseif|empty|enddeclare|endfor|endforeach|endif|endswitch|endwhile|eval|exit|extends|final|finally|fn|for|foreach|function|global|goto|if|implements|include|include_once|instanceof|insteadof|interface|isset|list|match|namespace|new|or|print|private|protected|public|readonly|require|require_once|return|static|switch|throw|trait|try|unset|use|var|while|xor|yield|yield from)\b', create_format('keyword')),
    (r'\b(true|false|null|TRUE|FALSE|NULL)\b', create_format('boolean_null_nil')),
    (r'(#|//).*', create_format('comment')),
    (r'"(\\"|[^"])*"', create_format('string')),
    (r"'(\\'|[^'])*'", create_format('string')),
    (r'<<<([A-Za-z_][A-Za-z0-9_]*)\s*\n(?:.|\n)*?\n\1;', create_format('string_alt')), # Heredoc
    (r"<<<'([A-Za-z_][A-Za-z0-9_]*)'\s*\n(?:.|\n)*?\n\1;", create_format('string_alt')), # Nowdoc
    (r'\$[A-Za-z_][A-Za-z0-9_]*', create_format('variable')),
    (r'class\s+([A-Za-z_][A-Za-z0-9_]*)', create_format('classname'), 1),
    (r'interface\s+([A-Za-z_][A-Za-z0-9_]*)', create_format('classname'), 1),
    (r'trait\s+([A-Za-z_][A-Za-z0-9_]*)', create_format('classname'), 1),
    (r'function\s+([A-Za-z_][A-Za-z0-9_]*)', create_format('defclass'), 1),
    (r'\b([A-Z_][A-Za-z0-9_]*)\b', create_format('classname')), # Constants, some class names
    (r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*(?=\()', create_format('function_call'),1),
    (r'\b(0[xX][0-9a-fA-F]+|0[bB][01]+|0[0-7]*|[+-]?\d+(\.\d*)?([eE][+-]?\d+)?)\b', create_format('numbers')),
]
PHP_MULTILINE_DELIMITERS = JAVASCRIPT_MULTILINE_DELIMITERS

RUBY_RULES = [
    (r'\b(BEGIN|END|alias|and|begin|break|case|class|def|defined\?|do|else|elsif|end|ensure|false|for|if|in|module|next|nil|not|or|redo|rescue|retry|return|self|super|then|true|undef|unless|until|when|while|yield)\b', create_format('keyword')),
    (r'#.*', create_format('comment')),
    (r'"(\\"|[^"])*"', create_format('string')),
    (r"'(\\'|[^'])*'", create_format('string')),
    (r'%[QqWwIirx]?\{[^\}]*\}', create_format('string_alt')), # %q{}, %Q{}, etc.
    (r'%[QqWwIirx]?\[[^\]]*\]', create_format('string_alt')),
    (r'%[QqWwIirx]?\([^\)]*\)', create_format('string_alt')),
    (r'%[QqWwIirx]?<[^>]*>', create_format('string_alt')),
    (r':[A-Za-z_][A-Za-z0-9_!?=]*', create_format('symbol')), # Symbols
    (r'@[A-Za-z_][A-Za-z0-9_]*', create_format('variable')), # Instance variables
    (r'@@[A-Za-z_][A-Za-z0-9_]*', create_format('variable')), # Class variables
    (r'\$[A-Za-z_][A-Za-z0-9_]*', create_format('variable')), # Global variables
    (r'class\s+([A-Z][A-Za-z0-9_:]*)', create_format('classname'), 1),
    (r'module\s+([A-Z][A-Za-z0-9_:]*)', create_format('classname'), 1),
    (r'def\s+([a-zA-Z_][a-zA-Z0-9_!?=]*)', create_format('defclass'), 1),
    (r'\b([A-Z][A-Za-z0-9_:]*)\b', create_format('classname')), # Class/Module names
    (r'\b([a-zA-Z_][a-zA-Z0-9_!?=]*)\s*(?=\(|\s*do\b)', create_format('function_call'),1),
    (r'\b(0[xX][0-9a-fA-F]+|0[bB][01]+|0[dD]?[0-9]+(_[0-9]+)*(\.\d+(_\d+)*)?([eE][+-]?\d+)?)\b', create_format('numbers')),
]
RUBY_MULTILINE_DELIMITERS = {
    'block_comment': {'start': QRegularExpression(r'^=begin'), 'end': QRegularExpression(r'^=end'), 'state_id': 61, 'format': create_format('comment')}
}

SWIFT_RULES = [
    (r'\b(actor|as|associativity|async|await|break|case|catch|class|continue|convenience|default|defer|deinit|didSet|do|dynamic|else|enum|extension|fallthrough|false|fileprivate|final|for|func|get|guard|if|import|in|indirect|infix|init|inout|internal|is|lazy|left|let|mutating|nil|none|nonmutating|open|operator|optional|override|postfix|precedence|prefix|private|protocol|public|repeat|required|rethrows|return|right|safe|self|Self|set|some|static|struct|subscript|super|switch|throws|throw|true|try|typealias|unowned|unsafe|var|weak|where|while|willSet)\b', create_format('keyword')),
    (r'//.*', create_format('comment')),
    (r'#available\b|#colorLiteral\b|#column\b|#dsohandle\b|#else\b|#elseif\b|#endif\b|#error\b|#file\b|#fileID\b|#fileLiteral\b|#filePath\b|#function\b|#if\b|#imageLiteral\b|#keyPath\b|#line\b|#selector\b|#sourceLocation\b|#warning\b', create_format('preprocessor')),
    (r'"(\\"|[^"])*"', create_format('string')),
    (r'"""(.|\n)*?"""', create_format('string_alt')), # Multiline strings
    (r'@[A-Za-z_][A-Za-z0-9_]*', create_format('decorator_annotation_attribute')), # Attributes
    (r'(class|struct|enum|protocol|extension|actor)\s+([A-Z][A-Za-z0-9_]*)', create_format('classname'), 2),
    (r'func\s+([a-zA-Z_][a-zA-Z0-9_]*)', create_format('defclass'), 1),
    (r'\b([A-Z][A-Za-z0-9_<>?]*)\b', create_format('classname')), # Type names
    (r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*(?=\()', create_format('function_call'),1),
    (r'\b(0[xX][0-9a-fA-F]+(\.[0-9a-fA-F]+)?([pP][+-]?\d+)?|0[oO][0-7]+|0[bB][01]+|[+-]?\d+(\.\d*)?([eE][+-]?\d+)?)\b', create_format('numbers')),
]
SWIFT_MULTILINE_DELIMITERS = JAVASCRIPT_MULTILINE_DELIMITERS

KOTLIN_RULES = [
    (r'\b(abstract|actual|annotation|as|break|by|catch|class|companion|const|constructor|continue|coroutine|crossinline|data|delegate|do|dynamic|else|enum|expect|external|false|final|finally|for|fun|get|if|impl|import|in|infix|init|inline|inner|interface|internal|is|lateinit|noinline|null|object|open|operator|out|override|package|param|private|protected|public|reified|return|sealed|set|super|suspend|tailrec|this|throw|true|try|typealias|typeof|val|var|vararg|when|where|while)\b', create_format('keyword')),
    (r'//.*', create_format('comment')),
    (r'"(\\"|[^"])*"', create_format('string')),
    (r'"""(.|\n)*?"""', create_format('string_alt')), # Raw strings
    (r'@[A-Za-z_][A-Za-z0-9_.:]*(\s*\([^)]*\))?', create_format('decorator_annotation_attribute')), # Annotations
    (r'(class|interface|object|enum)\s+([A-Za-z_][A-Za-z0-9_]*)', create_format('classname'), 2),
    (r'fun\s+([a-zA-Z_][a-zA-Z0-9_<>.]*)', create_format('defclass'), 1),
    (r'\b([A-Z][A-Za-z0-9_<>?]*)\b', create_format('classname')), # Type names
    (r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*(?=\()', create_format('function_call'),1),
    (r'\b(0[xX][0-9a-fA-F]+[uUL]?|0[bB][01]+[uUL]?|[+-]?\d+[uUL]?(\.\d*)?([eE][+-]?\d+)?[fFL]?)\b', create_format('numbers')),
]
KOTLIN_MULTILINE_DELIMITERS = JAVASCRIPT_MULTILINE_DELIMITERS



HIGHLIGHTER_CONFIGS = {
    '.py': {'rules': PYTHON_RULES, 'multiline_delimiters': PYTHON_MULTILINE_DELIMITERS},
    '.js': {'rules': JAVASCRIPT_RULES, 'multiline_delimiters': JAVASCRIPT_MULTILINE_DELIMITERS},
    '.dart': {'rules': DART_RULES, 'multiline_delimiters': DART_MULTILINE_DELIMITERS},
    '.html': {'rules': HTML_RULES, 'multiline_delimiters': {}},
    '.htm': {'rules': HTML_RULES, 'multiline_delimiters': {}},
    '.yaml': {'rules': YAML_RULES, 'multiline_delimiters': {}},
    '.json': {'rules': JSON_RULES, 'multiline_delimiters': {}},
    '.txt': {'rules': [], 'multiline_delimiters': {}}, # No specific rules for plain text

    # Added Languages
    '.java': {'rules': JAVA_RULES, 'multiline_delimiters': JAVA_MULTILINE_DELIMITERS},
    '.cs': {'rules': CSHARP_RULES, 'multiline_delimiters': CSHARP_MULTILINE_DELIMITERS},
    '.go': {'rules': GO_RULES, 'multiline_delimiters': GO_MULTILINE_DELIMITERS},
    '.php': {'rules': PHP_RULES, 'multiline_delimiters': PHP_MULTILINE_DELIMITERS},
    '.rb': {'rules': RUBY_RULES, 'multiline_delimiters': RUBY_MULTILINE_DELIMITERS},
    '.swift': {'rules': SWIFT_RULES, 'multiline_delimiters': SWIFT_MULTILINE_DELIMITERS},
    '.kt': {'rules': KOTLIN_RULES, 'multiline_delimiters': KOTLIN_MULTILINE_DELIMITERS},
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
        
        # Ensure all state IDs are unique if multiple delimiter types exist per language
        # This is a basic check; more robust ID generation might be needed for complex cases
        # For now, the state_ids are manually assigned and assumed unique across a language.

    def highlightBlock(self, text):
        current_block_state_id = self.previousBlockState()
        active_delimiter_key = None

        # Determine if we are inside a multi-line construct from the previous block
        if current_block_state_id > 0:
            for key, delim_config in self.multiline_delimiters.items():
                if delim_config['state_id'] == current_block_state_id:
                    active_delimiter_key = key
                    break
        
        start_offset = 0
        while start_offset < len(text):
            if active_delimiter_key: # Continuing an active multi-line construct
                delim_config = self.multiline_delimiters[active_delimiter_key]
                end_match = delim_config['end'].match(text, start_offset)
                
                if end_match.hasMatch(): 
                    end_offset = end_match.capturedStart(0) + end_match.capturedLength(0)
                    self.setFormat(start_offset, end_offset - start_offset, delim_config['format'])
                    self.setCurrentBlockState(0) # Exited multi-line construct
                    active_delimiter_key = None
                    start_offset = end_offset
                else: 
                    # Still inside the multi-line construct, format till end of block
                    self.setFormat(start_offset, len(text) - start_offset, delim_config['format'])
                    self.setCurrentBlockState(delim_config['state_id']) # Remain in this state
                    return # Processed entire block within this multi-line construct
            else: # Not currently in a multi-line construct, look for starts or apply single-line rules
                earliest_start_pos = len(text) + 1
                next_delimiter_key_to_activate = None

                for key, delim_config in self.multiline_delimiters.items():
                    start_match = delim_config['start'].match(text, start_offset)
                    if start_match.hasMatch() and start_match.capturedStart(0) < earliest_start_pos:
                        earliest_start_pos = start_match.capturedStart(0)
                        next_delimiter_key_to_activate = key
                
                segment_end = earliest_start_pos if next_delimiter_key_to_activate else len(text)
                
                sub_text = text[start_offset:segment_end]
                if sub_text: 
                    for rule_item in self.rules:
                        expression = rule_item['pattern']
                        nth_group = rule_item['nth_group']
                        iterator = expression.globalMatch(sub_text)
                        while iterator.hasNext():
                            match = iterator.next()
                            cap_start = match.capturedStart(nth_group)
                            cap_len = match.capturedLength(nth_group)
                            if cap_start != -1 and cap_len > 0:
                                self.setFormat(start_offset + cap_start, cap_len, rule_item['format'])
                
                if next_delimiter_key_to_activate:
                    active_delimiter_key = next_delimiter_key_to_activate
                    # Before processing the multi-line part, ensure the delimiter itself is formatted
                    delim_config_to_activate = self.multiline_delimiters[active_delimiter_key]
                    start_match_for_format = delim_config_to_activate['start'].match(text, earliest_start_pos) # Re-match at exact spot
                    if start_match_for_format.hasMatch():
                         self.setFormat(start_match_for_format.capturedStart(0), start_match_for_format.capturedLength(0), delim_config_to_activate['format'])
                    
                    start_offset = earliest_start_pos # Continue processing from the start of this new delimiter
                else:
                    start_offset = len(text) 

        if not active_delimiter_key:
            self.setCurrentBlockState(0)