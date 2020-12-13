from PyQt5 import QtGui, QtWidgets, QtCore


class Highlighter(QtGui.QSyntaxHighlighter):

    def __init__(self, parent=None, language=None):
        super(Highlighter, self).__init__(parent)
        self.py_constants = ['False', 'True', 'None', 'NotImplemented', 'Ellipsis']
        self.py_builtins = ['abs', 'all', 'any', 'basestring', 'bool',
                            'callable', 'chr', 'classmethod', 'cmp', 'compile',
                            'complex', 'delattr', 'dict', 'dir', 'divmod',
                            'enumerate', 'eval', 'execfile', 'exit', 'file',
                            'filter', 'float', 'frozenset', 'getattr', 'globals',
                            'hasattr', 'hex', 'id', 'int', 'isinstance',
                            'issubclass', 'iter', 'len', 'list', 'locals', 'map',
                            'max', 'min', 'object', 'oct', 'open', 'ord', 'pow',
                            'property', 'range', 'reduce', 'repr', 'reversed',
                            'round', 'set', 'setattr', 'slice', 'sorted',
                            'staticmethod', 'str', 'sum', 'super', 'tuple', 'type',
                            'vars', 'zip']
        self.py_keywords = ['and', 'as', 'assert', 'break', 'class', 'continue', 'def', 'del', 'elif', 'else', 'except',
                            'exec', 'finally', 'for', 'from', 'global', 'if', 'import', 'in', 'is', 'lambda', 'not',
                            'or', 'pass', 'print', 'raise', 'return', 'try', 'while', 'with', 'yield']
        self.cpp_keywords = ['char', 'class', 'const', 'double', 'enum', 'explicit', 'friend', 'inline', 'int', 'long',
                             'namespace', 'operator', 'private', 'protected', 'public', 'short', 'signals', 'signed',
                             'slots', 'static', 'struct', 'template', 'typedef', 'typename', 'union', 'unsigned',
                             'virtual', 'void', 'volatile', 'bool']
        self.highlight_rules = []
        self.base_format = QtGui.QTextCharFormat()
        self.base_format.setFontFamily('fira_code')
        self.base_format.setFontPointSize(14)
        self.keyword_format = QtGui.QTextCharFormat(self.base_format)
        self.keyword_format.setFontWeight(QtGui.QFont.Bold)
        self.keyword_format.setForeground(QtCore.Qt.darkBlue)
        self.set_language(language)

    def set_language(self, language: str = None):
        if language == 'py':
            self.highlight_python()
        elif language == 'cpp':
            self.highlight_cpp()
        self.rehighlight()

    def highlight_cpp(self):
        for i in self.cpp_keywords:
            self.highlight_rules.append((QtCore.QRegularExpression('\\b' + i + '\\b'), self.keyword_format))

        class_format = QtGui.QTextCharFormat(self.base_format)
        class_format.setFontWeight(QtGui.QFont.Bold)
        class_format.setForeground(QtCore.Qt.darkMagenta)
        self.highlight_rules.append((QtCore.QRegularExpression('\\bQ[A-Za-z]+\\b'), class_format))

        quotation_format = QtGui.QTextCharFormat(self.base_format)
        quotation_format.setForeground(QtCore.Qt.darkGreen)
        self.highlight_rules.append((QtCore.QRegularExpression('\".*\"'), quotation_format))

        function_format = QtGui.QTextCharFormat(self.base_format)
        function_format.setFontItalic(True)
        function_format.setForeground(QtCore.Qt.blue)
        self.highlight_rules.append((QtCore.QRegularExpression('\\b[A-Za-z0-9_]+(?=\\()'), function_format))

        single_line_comment_format = QtGui.QTextCharFormat(self.base_format)
        single_line_comment_format.setForeground(QtCore.Qt.gray)
        self.highlight_rules.append((QtCore.QRegularExpression('//[^\n]*'), single_line_comment_format))

        single_line_comment_format1 = QtGui.QTextCharFormat(self.base_format)
        single_line_comment_format1.setForeground(QtCore.Qt.darkGreen)
        self.highlight_rules.append((QtCore.QRegularExpression('<.*>'), single_line_comment_format1))

        multi_line_comment_format = QtGui.QTextCharFormat(self.base_format)
        multi_line_comment_format.setForeground(QtCore.Qt.red)

    def highlight_python(self):
        for i in self.py_keywords + self.py_builtins + self.py_constants:
            self.highlight_rules.append((QtCore.QRegularExpression('\\b' + i + '\\b'), self.keyword_format))

        comment_format = QtGui.QTextCharFormat(self.base_format)
        comment_format.setForeground(QtCore.Qt.darkGreen)
        self.highlight_rules.append((QtCore.QRegularExpression('#.*'), comment_format))

    def highlightBlock(self, text: str):
        text_length = len(text)
        prev_state = self.previousBlockState()
        self.setFormat(0, text_length, self.base_format)

        for reg, format in self.highlight_rules:
            match_iterator = reg.globalMatch(text)
            while match_iterator.hasNext():
                match = match_iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), format)

    def rehighlight(self):
        QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.WaitCursor))
        QtGui.QSyntaxHighlighter.rehighlight(self)
        QtWidgets.QApplication.restoreOverrideCursor()
