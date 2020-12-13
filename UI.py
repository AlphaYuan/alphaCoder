# coding:utf-8
import os
import sys
import time

import qtawesome
from PyQt5 import QtCore, QtGui, QtWidgets, QtNetwork

import Highlight
from Huffman import Huffman
from PieceTable import PieceTable


class LineNumberArea(QtWidgets.QWidget):

    def __init__(self, parent=None, editor: QtWidgets.QPlainTextEdit = None):
        super(LineNumberArea, self).__init__(parent)
        self.setLayout(QtWidgets.QVBoxLayout())
        self.editor = editor
        self.editor.blockCountChanged.connect(self.line_number_area_width)
        self.editor.updateRequest.connect(self.update_line_number_area)
        self.setStyleSheet('''QWidget{background: white;color: #202020;border: 1px solid #1EAE3D;}''')

    def paintEvent(self, e: QtGui.QPaintEvent):
        if self.isVisible():
            block = self.editor.firstVisibleBlock()
            height = self.editor.fontMetrics().height()
            block_number = block.blockNumber()
            painter = QtGui.QPainter(self)
            painter.fillRect(e.rect(), QtGui.QColor("#ACDED5"))
            # painter.drawRect(0, 0, e.rect().width(), e.rect().height())
            font = self.editor.font()
            current_block = self.editor.textCursor().block().blockNumber() + 1
            condition = True
            while block.isValid() and condition:
                block_geometry = self.editor.blockBoundingGeometry(block)
                offset = self.editor.contentOffset()
                top = block_geometry.translated(offset).top()
                block_number += 1
                rect = QtCore.QRect(0, top, self.width(), height)
                if block_number == current_block:
                    font.setBold(True)
                else:
                    font.setBold(False)
                painter.setFont(font)
                painter.drawText(rect, QtCore.Qt.AlignRight, '%i' % block_number)
                if top > e.rect().bottom():
                    condition = False
                block = block.next()
            painter.end()

    def update_line_number_area(self, rect, dy):
        if self.isVisible():
            if dy:
                self.scroll(0, dy)
            else:
                self.update(0, rect.y(), self.width(), rect.height())

    def line_number_area_width(self):
        digits = 1
        m = max(1, self.editor.blockCount())
        while m >= 10:
            m /= 10
            digits += 1
        space = 3 + self.editor.fontMetrics().width('9') * digits
        self.setFixedWidth(space)


class TextEditor(QtWidgets.QPlainTextEdit):
    tmp_file = QtCore.pyqtSignal(str)
    new_file = QtCore.pyqtSignal()
    filename_change = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super(TextEditor, self).__init__(parent)
        self.pt = PieceTable(self.toPlainText())
        self.filename = ''
        self.language = None

        self.find_field: QtWidgets.QLineEdit()
        self.replace_field: QtWidgets.QLineEdit()

        self.server = None
        self.socket = None

        self.tab_width = 4
        self.setFont(QtGui.QFont('fira_code', 14))
        self.setTabStopWidth(self.fontMetrics().width(' ') * self.tab_width)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        # self.setFocusPolicy(QtCore.Qt.StrongFocus)

    def keyPressEvent1(self, e: QtGui.QKeyEvent) -> None:
        print(e.text(), e.key())
        cursor = self.textCursor()
        cursor_move_length = 0
        print('old pos:', cursor.position())
        # if e.key() == QtCore.Qt.Key_Left:
        #     print('left')
        #     cursor_move_length = -1
        #     cursor.setPosition(cursor.position() + cursor_move_length, QtGui.QTextCursor.MoveAnchor)
        #     # self.setPlainText(self.pt.get_sequence())
        #     self.setTextCursor(cursor)
        #     print('new pos:', cursor.position())
        #     return
        if e.text():
            # self.parent.server.send('1')
            if 32 <= ord(e.text()[0]) <= 126 or e.key() == QtCore.Qt.Key_Return:
                print('ord')
                self.insert(e.text(), cursor.position())
                cursor_move_length = 1
            elif e.key() == QtCore.Qt.Key_Tab:
                self.insert(e.text(), cursor.position())
                cursor_move_length = self.tab_width
            elif e.key() == QtCore.Qt.Key_Backspace:
                print('delete:', self.pt.subsequence(cursor.position() - 1, cursor.position() - 1))
                print(cursor.position())
                self.pt.delete(cursor.position(), cursor.position())
                self.setPlainText(self.pt.get_sequence())
                cursor_move_length = -1

            if cursor_move_length != 0:
                cursor.setPosition(cursor.position() + cursor_move_length, QtGui.QTextCursor.MoveAnchor)
                self.setTextCursor(cursor)
                print('new pos:', cursor.position())
                return
        # print(cursor)
        # print(e)
        t = QtWidgets.QPlainTextEdit.keyPressEvent(self, e)
        print(type(t), t)
        return t

    def keyPressEvent(self, e: QtGui.QKeyEvent) -> None:
        cursor = self.textCursor()  # 获取当前光标
        if e.text():
            if 32 <= ord(e.text()[0]) <= 126:  # 输入普通字符
                self.pt.insert(cursor.position(), e.text())
                self.send_cmd('insert %d %s' % (cursor.position(), e.text()))  # 向其他客户端发送当前的操作
            elif e.key() == QtCore.Qt.Key_Return:  # 输入回车
                self.pt.insert(cursor.position(), '\n')
                self.send_cmd('insert %d %s' % (cursor.position(), '\n'))  # 向其他客户端发送当前的操作
            elif e.key() == QtCore.Qt.Key_Tab:  # 输入制表符
                self.pt.insert(cursor.position(), '\t')
                self.send_cmd('insert %d %s' % (cursor.position(), '\t'))  # 向其他客户端发送当前的操作
            elif e.key() == QtCore.Qt.Key_Backspace or e.text().encode('utf-8') == b'\x08':  # 退格
                self.pt.delete(cursor.position() - 1, cursor.position() - 1)
                self.send_cmd('backspace %d' % cursor.position())  # 向其他客户端发送当前的操作
            elif e.key() == QtCore.Qt.Key_Delete or e.text().encode('utf-8') == b'\x7f':  # 删除后一个字符
                self.pt.delete(cursor.position(), cursor.position())

        return QtWidgets.QPlainTextEdit.keyPressEvent(self, e)

    def mouseReleaseEvent(self, e: QtGui.QMouseEvent) -> None:
        cursor = self.textCursor()
        self.send_cmd('select %d' % cursor.blockNumber())

    def insert(self, text: str, begin: int = 0):
        self.pt.insert(begin, text)
        self.setPlainText(self.pt.get_sequence())

    def undo(self, send=True):
        self.pt.undo()
        self.setPlainText(self.pt.get_sequence())
        if send:
            self.send_cmd('undo 1')

    def redo(self, send=True):
        self.pt.redo()
        self.setPlainText(self.pt.get_sequence())
        if send:
            self.send_cmd('redo 1')

    def _find(self):
        find_dialog = QtWidgets.QDialog(self)
        find_dialog.setWindowTitle('Find')
        main_layout = QtWidgets.QGridLayout()
        find_label = QtWidgets.QLabel('Find:')
        self.find_field = QtWidgets.QLineEdit()
        find_btn = QtWidgets.QPushButton('Find Next')
        find_btn.clicked.connect(self.find_str)
        cancel_btn = QtWidgets.QPushButton('Cancel')
        cancel_btn.clicked.connect(find_dialog.reject)
        find_dialog.setLayout(main_layout)
        main_layout.addWidget(find_label, 0, 0, 2, 2)
        main_layout.addWidget(self.find_field, 0, 2, 2, 2)
        main_layout.addWidget(find_btn, 0, 4, 2, 2)
        main_layout.addWidget(cancel_btn, 3, 4, 2, 2)
        find_dialog.show()

    def _replace(self):
        find_dialog = QtWidgets.QDialog(self)
        find_dialog.setWindowTitle('Find & Replace')
        main_layout = QtWidgets.QGridLayout()
        find_label = QtWidgets.QLabel('Find:')
        self.find_field = QtWidgets.QLineEdit()
        find_btn = QtWidgets.QPushButton('Find Next')
        find_btn.clicked.connect(self.find_str)
        replace_label = QtWidgets.QLabel('Replace:')
        self.replace_field = QtWidgets.QLineEdit()
        replace_btn = QtWidgets.QPushButton('Replace')
        replace_btn.clicked.connect(self.replace)
        replace_all_btn = QtWidgets.QPushButton('Replace All')
        replace_all_btn.clicked.connect(self.replace_all)
        cancel_btn = QtWidgets.QPushButton('Cancel')
        cancel_btn.clicked.connect(find_dialog.reject)
        find_dialog.setLayout(main_layout)
        main_layout.addWidget(find_label, 0, 0, 2, 2)
        main_layout.addWidget(self.find_field, 0, 2, 2, 2)
        main_layout.addWidget(find_btn, 0, 4, 2, 2)
        main_layout.addWidget(replace_label, 2, 0, 2, 2)
        main_layout.addWidget(self.replace_field, 2, 2, 2, 2)
        main_layout.addWidget(replace_btn, 2, 4, 2, 2)
        main_layout.addWidget(replace_all_btn, 4, 4, 2, 2)
        main_layout.addWidget(cancel_btn, 6, 4, 2, 2)
        find_dialog.show()

    def find_str(self, begin=0, send=True):
        if not begin:
            begin = 0
        pattern = self.find_field.text()
        start = time.clock()
        index = self.pt.find(pattern, begin)
        end = time.clock()
        print(len(self.pt.get_sequence()))
        print((end - start))
        self.select_text(index, len(pattern))
        if self.socket and send:
            self.send_cmd('find %d %d' % (index, len(pattern)))
        return index, pattern

    def replace(self, begin=0, send=True):
        if not begin:
            begin = 0
        _, pattern = self.find_str(begin, False)
        text = self.replace_field.text()
        index = self.pt.find(pattern, begin)
        if index == -1:
            self.moveCursor(QtGui.QTextCursor.End)
        else:
            self.pt.replace(index, index + len(pattern) - 1, text)
            self.setPlainText(self.pt.get_sequence())
            self.select_text(index, len(pattern))
            if self.socket and send:
                self.send_cmd('replace %d %d %s' % (index, len(pattern), text))
        return index, pattern, text

    def replace_all(self):
        index, pattern, text = self.replace(0)
        while index + len(pattern) <= len(self.pt.get_sequence()):
            index, _, _ = self.replace(index)
            if index == -1:
                break

    def select_text(self, begin: int, length: int):
        cursor = self.textCursor()
        cursor.setPosition(begin, QtGui.QTextCursor.MoveAnchor)
        cursor.movePosition(QtGui.QTextCursor.NoMove, QtGui.QTextCursor.KeepAnchor, length)
        cursor.select(QtGui.QTextCursor.WordUnderCursor)
        self.setTextCursor(cursor)

    # def find_str1(self, pattern: str = '', begin: int = 0):
    #     pass

    # def replace1(self, begin: int, end: int, text: str):
    #     self.setPlainText(self.pt.replace(begin, end, text))

    def highlight_current_line(self):
        extra_selections = []
        if not self.isReadOnly():
            selection = QtWidgets.QTextEdit.ExtraSelection()
            line_color = QtGui.QColor(QtCore.Qt.yellow).lighter(160)
            selection.format.setBackground(line_color)
            selection.format.setProperty(QtGui.QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            extra_selections.append(selection)

        self.setExtraSelections(extra_selections)

    def highlight_line(self, extra_line=False, block_numbers=[]):
        extra_selections = []
        if not self.isReadOnly():
            selection = QtWidgets.QTextEdit.ExtraSelection()
            line_color = QtGui.QColor(QtCore.Qt.yellow).lighter(160)
            selection.format.setBackground(line_color)
            selection.format.setProperty(QtGui.QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            extra_selections.append(selection)

            if extra_line:
                for block_number in block_numbers:
                    selection = QtWidgets.QTextEdit.ExtraSelection()
                    line_color = QtGui.QColor(QtCore.Qt.yellow).lighter(200)
                    selection.format.setBackground(line_color)
                    selection.format.setProperty(QtGui.QTextFormat.FullWidthSelection, True)
                    block = self.document().findBlockByNumber(block_number)
                    selection.cursor = QtGui.QTextCursor(block)
                    extra_selections.append(selection)

        self.setExtraSelections(extra_selections)

    def get_block_number_by_pos(self, pos):
        block = self.document().findBlock(pos)
        cursor = QtGui.QTextCursor(block)
        print(cursor.blockNumber())
        return cursor.blockNumber()

    def reset(self):
        self.pt = PieceTable()
        self.setPlainText(self.pt.get_sequence())

    def init_tcp(self, is_server, addr):
        if is_server:
            self.server = QtNetwork.QTcpServer(self)
            self.server.listen(QtNetwork.QHostAddress.Any, 8888)
            self.server.newConnection.connect(self.start_new_connection)
        else:
            self.socket = QtNetwork.QTcpSocket(self)
            self.socket.connectToHost(QtNetwork.QHostAddress(addr), 8888)
            self.socket.readyRead.connect(self.recv)

    def start_new_connection(self):
        print('start a new connection')
        if self.socket:
            return
        self.socket = self.server.nextPendingConnection()
        self.socket.readyRead.connect(self.recv)
        init_data = 'init ' + self.filename + ' ' + self.pt.get_sequence()
        self.send_cmd(init_data)

    def close_connection(self):
        if self.socket:
            self.socket.close()
            print('socket closed')
        if self.server:
            self.server.close()
            print('server closed')

    def send_cmd(self, data):
        if self.socket:
            print(data)
            self.socket.write(data.encode('utf-8'))

    def recv(self):
        byte_data = self.socket.readAll()
        data = str(byte_data, encoding='utf-8').split(sep=' ', maxsplit=2)
        command = data[0]
        data_list = data[1:]
        print(command, end='\t')
        if command == 'insert':
            print(data_list)
            pos = int(data_list[0])
            text = data_list[1]
            self.insert(text, pos)
            block_number = self.get_block_number_by_pos(pos)
            self.highlight_line(extra_line=True, block_numbers=[block_number + 1])
        elif command == 'backspace':
            print(data_list)
            old_cursor = self.textCursor()
            pos = int(data_list[0])
            self.pt.delete(pos - 1, pos - 1)
            self.setPlainText(self.pt.get_sequence())
            self.setTextCursor(old_cursor)
            block_number = self.get_block_number_by_pos(pos)
            if block_number < self.blockCount():
                self.highlight_line(extra_line=True, block_numbers=[block_number])
        elif command == 'del':
            print(data_list)
            old_cursor = self.textCursor()
            pos = int(data_list[0])
            self.pt.delete(pos, pos)
            self.setPlainText(self.pt.get_sequence())
            self.setTextCursor(old_cursor)
            block_number = self.get_block_number_by_pos(pos)
            if block_number < self.blockCount():
                self.highlight_line(extra_line=True, block_numbers=[block_number])
        elif command == 'select':
            print(data_list)
            block_number = int(data_list[0])
            self.highlight_line(extra_line=True, block_numbers=[block_number])
        elif command == 'undo':
            print(command)
            self.undo(False)
        elif command == 'redo':
            print(command)
            self.redo(False)
        elif command == 'find':
            pos = int(data_list[0])
            length = int(data_list[1])
            self.select_text(pos, length)
        elif command == 'replace':
            pos = int(data_list[0])
            len_pattern, text = data_list[1].split(sep=' ', maxsplit=1)
            len_pattern = int(len_pattern)
            self.pt.replace(pos, pos + len_pattern - 1, text)
            self.setPlainText(self.pt.get_sequence())
            self.select_text(pos, len_pattern)
        elif command == 'init':
            # if self.filename == '':
            #     self.filename = data_list[0]
            # content = data_list[1]
            # self.reset()
            # self.insert(content, 0)
            # self.tmp_file.emit(content)
            # else:
            #     self.filename = data_list[0]
            #     content = data_list[1]
            #     self.reset()
            #     self.insert(content, 0)
            # self.new_file.emit()
            self.filename = data_list[0]
            content = data_list[1]
            self.reset()
            self.insert(content, 0)
            self.filename_change.emit(self.filename)
            print(self.filename)
        elif command == 'exit':
            self.close_connection()


class AlphaCoder(QtWidgets.QMainWindow):

    def __init__(self, parent=None):
        super().__init__()
        self.setObjectName('MainWindow')
        self.resize(800, 600)
        self.setWindowTitle('alphaCoder')
        self.setWindowOpacity(0.99)
        # self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        # self.setWindowFlag(QtCore.Qt.FramelessWindowHint)
        # self.setWindowFlag(QtCore.Qt.FramelessWindowHint)
        self.filenames = []
        self.languages = []
        self.text_editors = []
        self.line_number_areas = []
        self.highlighters = []
        self.cur_tab = -1

        self.status = self.statusBar()
        self.status.setSizeGripEnabled(False)
        self.status.showMessage('Ready', 5000)

        self.menubar = self.menuBar()
        self.menubar.setStyleSheet('''QMenu{background: #F2F2F2;color: #0E185F;border: 1px solid #1EAE3D;
        selection-background-color: #ACDED5;} ''')
        self.menu_file = self.menubar.addMenu('File')
        self.menu_edit = self.menubar.addMenu('Edit')
        self.menu_help = self.menubar.addMenu('Help')

        self.action_new_file = self.menu_file.addAction('New File')
        self.action_new_file.setShortcut("Ctrl+N")
        self.action_new_file.triggered.connect(self.new_file)
        self.action_new_folder = self.menu_file.addAction('New Folder')
        self.action_new_folder.triggered.connect(self.new_folder)
        self.action_open_file = self.menu_file.addAction('Open File')
        self.action_open_file.setShortcut("Ctrl+O")
        self.action_open_file.triggered.connect(self.open_file)
        self.action_open_folder = self.menu_file.addAction('Open Folder')
        self.action_open_folder.triggered.connect(self.open_folder)
        self.menu_file.addSeparator()
        self.action_save_file = self.menu_file.addAction('Save')
        self.action_save_file.setShortcut('Ctrl+S')
        self.action_save_file.triggered.connect(self.save_file)
        self.action_save_file_as = self.menu_file.addAction('Save as')
        self.action_save_file_as.triggered.connect(self.save_file_as)
        self.menu_file.addSeparator()
        self.action_preference = self.menu_file.addAction('Preference')
        self.action_preference.triggered.connect(self.open_preference)
        self.action_quit = self.menu_file.addAction('Quit')
        self.action_quit.triggered.connect(self.close)

        self.action_redo = self.menu_edit.addAction('Redo')
        self.action_redo.setShortcut('Ctrl+Y')
        self.action_redo.triggered.connect(self.redo)
        self.action_undo = self.menu_edit.addAction('Undo')
        self.action_undo.setShortcut('Ctrl+Z')
        self.action_undo.triggered.connect(self.undo)
        self.menu_edit.addSeparator()
        self.action_find = self.menu_edit.addAction('Find')
        self.action_find.setShortcut('Ctrl+F')
        self.action_find.triggered.connect(self.Find)
        self.action_replace = self.menu_edit.addAction('Replace')
        self.action_replace.setShortcut('Ctrl+R')
        self.action_replace.triggered.connect(self.replace)
        self.menu_edit.addSeparator()
        self.action_copy = self.menu_edit.addAction('Copy')
        self.action_copy.setShortcut('Ctrl+C')
        self.action_copy.triggered.connect(self.copy)
        self.action_cut = self.menu_edit.addAction('Cut')
        self.action_cut.setShortcut('Ctrl+X')
        self.action_cut.triggered.connect(self.cut)
        self.action_paste = self.menu_edit.addAction('Paste')
        self.action_paste.setShortcut('Ctrl+V')
        self.action_paste.triggered.connect(self.paste)

        self.action_help = self.menu_help.addAction('Help')
        self.action_help.triggered.connect(self.help)
        self.action_about = self.menu_help.addAction('About')
        self.action_about.triggered.connect(self.about)

        self.mainWidget = QtWidgets.QWidget()
        self.mainWidget.setObjectName('mainWidget')
        self.mainLayout = QtWidgets.QGridLayout()
        self.mainWidget.setLayout(self.mainLayout)
        self.leftWidget = QtWidgets.QWidget()
        self.leftWidget.setObjectName('leftWidget')
        self.leftWidget.setFixedWidth(80)
        self.leftWidget.setStyleSheet('''QWidget{background:lightyellow;border-top:1px solid white;border-bottom:1px solid white;
        border-left:1px solid white;border-top-left-radius:10px;border-bottom-left-radius:10px;}''')
        # self.leftLayout = QtWidgets.QGridLayout()
        # self.leftWidget.setLayout(self.leftLayout)
        self.rightTabWidget = QtWidgets.QTabWidget()
        self.rightTabWidget.setObjectName('rightTabWidget')
        self.rightTabWidget.setStyleSheet('''QWidget#rightTabWidget{background:gray;border-top:1px solid white;border-bottom:1px solid white;
                border-right:1px solid white;border-top-right-radius:10px;border-bottom-right-radius:10px;
                QTabWidget::pane {border-top: 2px solid #C2C7CB;}
                QTabWidget::tab-bar {left: 5px;}
                QTabBar::tab {background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,stop: 0 #E1E1E1, stop: 0.4 #DDDDDD,
                stop: 0.5 #D8D8D8, stop: 1.0 #D3D3D3);border: 2px solid #C4C4C3;border-bottom-color: #C2C7CB; /* same as the pane color */
                border-top-left-radius: 4px;border-top-right-radius: 4px;min-width: 8ex;padding: 2px;}
                QTabBar::tab:selected, QTabBar::tab:hover {background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,stop: 0 #fafafa, stop: 0.4 #f4f4f4,stop: 0.5 #e7e7e7, stop: 1.0 #fafafa);}
                QTabBar::tab:selected {border-color: #9B9B9B;border-bottom-color: #C2C7CB;}
                QTabBar::tab:!selected {margin-top: 2px;}
                QTabBar::tab:selected {margin-left: -4px;margin-right: -4px;}
                QTabBar::tab:first:selected {margin-left: 0; } 
                QTabBar::tab:last:selected {margin-right: 0; }QTabBar::tab:only-one {margin: 0;}''')
        self.rightTabWidget.setTabsClosable(True)
        self.rightTabWidget.tabCloseRequested.connect(self.close_tab)
        self.mainLayout.addWidget(self.leftWidget, 0, 0, 1, 1)
        self.mainLayout.addWidget(self.rightTabWidget, 0, 1, 1, 1)
        self.mainLayout.setSpacing(0)
        self.setCentralWidget(self.mainWidget)

        self.some_btn()
        # self.toolbar = QtWidgets.QToolBar()
        # self.addToolBar(QtCore.Qt.TopToolBarArea, self.toolbar)
        self.new_tab()

        QtCore.QMetaObject.connectSlotsByName(self)

    def some_btn(self):
        self.btn_file = QtWidgets.QPushButton(self.leftWidget)
        self.btn_file.setGeometry((QtCore.QRect(0, 0, 80, 80)))
        self.btn_file.setObjectName('btn_file')
        self.btn_file.setIcon(qtawesome.icon('fa5s.file'))
        self.btn_file.setIconSize(QtCore.QSize(60, 60))
        # self.btn_file.setStyleSheet('''QPushButton{background:gray;}''')
        self.btn_file.clicked.connect(self.open_file)

        self.btn_terminal = QtWidgets.QPushButton(self.leftWidget)
        self.btn_terminal.setGeometry(QtCore.QRect(0, 90, 80, 80))
        self.btn_terminal.setObjectName('btn_terminal')
        self.btn_terminal.setIcon(qtawesome.icon('fa5s.terminal'))
        self.btn_terminal.setIconSize(QtCore.QSize(60, 60))
        # self.btn_terminal.setStyleSheet('''QPushButton{background:gray;}''') #QPushButton:hover{
        # background:green;}''')
        self.btn_terminal.clicked.connect(self.open_terminal)

        self.btn_run = QtWidgets.QPushButton(self.leftWidget)
        self.btn_run.setGeometry(QtCore.QRect(0, 180, 80, 80))
        self.btn_run.setObjectName('btn_run')
        self.btn_run.setIcon(qtawesome.icon('fa5s.play'))
        self.btn_run.setIconSize(QtCore.QSize(60, 60))
        self.btn_run.clicked.connect(self.run_code)

        self.btn_share = QtWidgets.QPushButton(self.leftWidget)
        self.btn_share.setGeometry(QtCore.QRect(0, 270, 80, 80))
        self.btn_share.setObjectName('btn_share')
        self.btn_share.setIcon(qtawesome.icon('fa5s.share'))
        self.btn_share.setIconSize(QtCore.QSize(60, 60))
        self.btn_share.clicked.connect(self.open_share)
        # self.btn_share.setStyleSheet('''QPushButton{background:gray;}''')  # QPushButton:hover{

    def paintEvent(self, a0: QtGui.QPaintEvent) -> None:
        self.cur_tab = self.rightTabWidget.currentIndex()
        if self.cur_tab == -1:
            return
        self.text_editors[self.cur_tab].setGeometry(
            QtCore.QRect(self.line_number_areas[self.cur_tab].width(), 0,
                         self.rightTabWidget.width() - self.line_number_areas[self.cur_tab].width(),
                         self.rightTabWidget.height()))
        self.line_number_areas[self.cur_tab].setGeometry(
            QtCore.QRect(0, 0, self.line_number_areas[self.cur_tab].width(),
                         self.rightTabWidget.height()))

    def open_share(self):
        ret = QtWidgets.QMessageBox.question(self, 'Server or Client', 'as server?')
        if (ret == QtWidgets.QMessageBox.Yes):
            self.text_editors[self.cur_tab].init_tcp(True, '127.0.0.1')
        else:
            ret1 = QtWidgets.QInputDialog.getText(self, 'Client', 'Input host address:', QtWidgets.QLineEdit.Normal,
                                                  '127.0.0.1')
            if ret1[1] is True:
                self.text_editors[self.cur_tab].init_tcp(False, ret1[0])

    def new_tab(self, content=''):
        new_tab = QtWidgets.QWidget()
        self.rightTabWidget.addTab(new_tab, 'Untitled')
        self.rightTabWidget.setCurrentWidget(new_tab)
        self.cur_tab = self.rightTabWidget.currentIndex()
        text_editor = TextEditor(new_tab)
        text_editor.setObjectName('text_editor')
        text_editor.setStyleSheet('''QPlainTextEdit{background: lightBlue;color: #202020;
                border: 1px solid #1EAE3D;selection-background-color: #505050;selection-color: #ACDED5;
                border-top:1px solid white;border-bottom:1px solid white;
                border-right:1px solid white;border-top-right-radius:10px;border-bottom-right-radius:10px;}''')
        if content:
            text_editor.insert(content, 0)
        text_editor.setGeometry(QtCore.QRect(15, 15, self.geometry().width() - 100, self.geometry().height() - 100))
        text_editor.highlight_current_line()
        text_editor.tmp_file.connect(self.save_tmp_file)
        text_editor.filename_change.connect(self.change_filename)

        highlighter = Highlight.Highlighter(text_editor.document())

        line_number_area = LineNumberArea(new_tab, text_editor)
        line_number_area.setObjectName('line_number_area')
        line_number_area.setGeometry(QtCore.QRect(0, 0, 15, 15))

        text_editor.show()
        line_number_area.show()

        self.text_editors.append(text_editor)
        self.line_number_areas.append(line_number_area)
        self.highlighters.append(highlighter)
        self.languages.append('unknown')
        self.filenames.append('untitled')
        self.update()

    def close_tab(self, index: int):
        text_editor = self.text_editors[index]
        text_editor.send_cmd('exit')
        text_editor.close_connection()
        self.rightTabWidget.removeTab(index)
        self.text_editors.pop(index)
        self.line_number_areas.pop(index)
        self.highlighters.pop(index)
        self.filenames.pop(index)
        self.languages.pop(index)

    def change_filename(self, filename: str):
        print(self.cur_tab, filename)
        self.filenames[self.cur_tab] = filename
        self.rightTabWidget.setTabText(self.rightTabWidget.currentIndex(), filename)
        self.languages[self.cur_tab] = filename.rsplit('.', maxsplit=1)[-1]
        if self.languages[self.cur_tab] == 'c':
            self.languages[self.cur_tab] = 'cpp'
        self.highlighters[self.cur_tab].set_language(self.languages[self.cur_tab])
        self.highlighters[self.cur_tab].rehighlight()

    def save_tmp_file(self, content):
        old_fname = fname = self.text_editors[self.cur_tab].filename
        fname = fname + '.tmp'
        with open(fname, 'w', encoding='UTF-8') as f:
            f.write(content)
        self.new_tab()
        self.filenames[self.cur_tab] = fname
        self.rightTabWidget.setTabText(self.rightTabWidget.currentIndex(), fname)
        fname = old_fname
        self.languages[self.cur_tab] = fname.rsplit('.', maxsplit=1)[-1]
        if self.languages[self.cur_tab] == 'c':
            self.languages[self.cur_tab] = 'cpp'
        self.highlighters[self.cur_tab].set_language(self.languages[self.cur_tab])
        self.text_editors[self.cur_tab].insert(content)

    def new_file(self):
        if self.cur_tab >= 0:
            str = self.text_editors[self.cur_tab].toPlainText()
            if str != '':
                msg = QtWidgets.QMessageBox.question(self, 'Save File?', 'This document is not saved. Save it or not?',
                                                     QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
                if msg == QtWidgets.QMessageBox.Yes:
                    self.save_file_as()
            self.text_editors[self.cur_tab].reset()
        else:
            self.new_tab()

    def new_folder(self):
        pass

    def open_file(self):
        dir = os.path.dirname('.')
        fname = str(QtWidgets.QFileDialog.getOpenFileName(
            self, 'Choose File', dir,
            'ALL(*.*);;Python file(*.py *.pyw);;C/C++ file(*.c *.cpp *.h);;Java file(*.java)')[0])
        if fname:
            fsize = os.path.getsize(fname)
            # print(fsize)
            if fsize > 1e6:
                self.filenames[self.cur_tab] = fname
                self.open_lines_dialog()
                return
            if fname.rsplit('.', maxsplit=1)[-1] == 'ac':
                content = Huffman().decode(fname)
            else:
                try:
                    with open(fname, 'r', encoding='UTF-8') as f:
                        content = f.read()
                except UnicodeDecodeError:
                    with open(fname, 'r', encoding='GBK') as f:
                        content = f.read()
            self.new_tab()
            self.filenames[self.cur_tab] = fname
            self.rightTabWidget.setTabText(self.rightTabWidget.currentIndex(), fname)
            self.languages[self.cur_tab] = fname.rsplit('.', maxsplit=1)[-1]
            if self.languages[self.cur_tab] == 'c':
                self.languages[self.cur_tab] = 'cpp'
            self.highlighters[self.cur_tab].set_language(self.languages[self.cur_tab])
            # self.text_editors[self.cur_tab].setPlainText(content)
            self.text_editors[self.cur_tab].insert(content)
            self.text_editors[self.cur_tab].filename = fname

    def open_folder(self):
        pass

    def save_file(self):
        self.cur_tab = self.rightTabWidget.currentIndex()
        if self.filenames:
            if self.filenames[self.cur_tab] == 'untitled':
                self.save_file_as()
            else:
                content = self.text_editors[self.cur_tab].toPlainText()
                with open(self.filenames[self.cur_tab], 'w') as f:
                    f.write(content)
        else:
            self.save_file_as()

    def save_file_as(self):
        dir = os.path.dirname('.')
        fname = str(QtWidgets.QFileDialog.getSaveFileName(
            self, 'Choose File', dir, 'ALL(*.*);;Compressed file(*.ac);;Python file(*.py *.pyw);;'
                                      'C/C++ file(*.c *.cpp *.h);;Java file(*.java)')[0])
        if fname:
            self.cur_tab = self.rightTabWidget.currentIndex()
            self.filenames[self.cur_tab] = fname
            self.rightTabWidget.setTabText(self.rightTabWidget.currentIndex(), fname)
            self.languages[self.cur_tab] = fname.rsplit('.', maxsplit=1)[-1]
            self.highlighters[self.cur_tab].set_language(self.languages[self.cur_tab])
            content = self.text_editors[self.cur_tab].toPlainText()
            if fname.rsplit('.', maxsplit=1)[-1] == 'ac':
                tmpname = fname.rsplit('.', maxsplit=1)[0] + '.tmp'
                with open(tmpname, 'w') as f:
                    f.write(content)
                Huffman().encode(tmpname)
                os.remove(tmpname)
            else:
                with open(fname, 'w') as f:
                    f.write(content)

    def open_preference(self):
        pass

    def redo(self):
        self.text_editors[self.cur_tab].redo()
        # print('redo')

    def undo(self):
        self.text_editors[self.cur_tab].undo()
        # print('undo')

    def Find(self):
        self.text_editors[self.cur_tab]._find()

    def replace(self):
        self.text_editors[self.cur_tab]._replace()

    def copy(self):
        pass

    def cut(self):
        pass

    def paste(self):
        pass

    def help(self):
        message = QtWidgets.QMessageBox(self)
        message.setText('Help')
        message.show()

    def about(self):
        message = QtWidgets.QMessageBox(self)
        message.setText(
            'About\nThis is a text editor by JiangYuan\nThere is also a simple Python interpreter implemented in Python')
        message.show()

    def maxi_normal(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def open_terminal(self):
        os.system('cmd/c start')

    def run_code(self):
        if self.cur_tab < 0:
            return
        res = None
        if self.languages[self.cur_tab] == 'cpp':
            t = self.filenames[self.cur_tab].rsplit('/', maxsplit=1)
            os.chdir(t[0])
            # start = time.time()
            os.system('gcc ' + t[1] + ' -o ' + 'tmp.exe')
            start = time.time()
            res = os.popen('tmp.exe')
            end = time.time()
        elif self.languages[self.cur_tab] == 'py':
            start = time.time()
            # os.system('python ' + self.filenames[self.cur_tab])
            # os.system('conda activate py33 && python E:/alphaCoder/interpreter/__main__.py --filename '
            #           + self.filenames[self.cur_tab])
            res = os.popen('conda activate py33 && python E:/alphaCoder/interpreter/__main__.py --filename '
                           + self.filenames[self.cur_tab])
            end = time.time()
            # self.new_cmd_tab()
            # self.text_editors[self.cur_tab].insert(os.popen('conda activate py33 && python E:/alphaCoder/interpreter/__main__.py --filename '
            #           + self.filenames[self.cur_tab]))
            # __main__.run_python_file(self.filenames[self.cur_tab], None, None)
        elif self.languages[self.cur_tab] == 'java':
            t = self.filenames[self.cur_tab].rsplit('/', maxsplit=1)
            os.chdir(t[0])
            os.system('javac ' + t[1])
            start = time.time()
            res = os.popen('java ' + t[1].rsplit('.', maxsplit=1)[0])
            end = time.time()

        if res:
            self.new_tab(res.read() + '\n[在%.8fs内执行结束]' % (end - start))
            self.rightTabWidget.setTabText(self.rightTabWidget.currentIndex(), 'Output')

    def open_file_tree(self):
        print('open file tree')

    def open_lines_dialog(self):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle('Certain Lines')
        main_layout = QtWidgets.QGridLayout()
        text_label = QtWidgets.QLabel('The file is too big! Still open all or open certain lines?')
        from_label = QtWidgets.QLabel('from:')
        to_label = QtWidgets.QLabel('to:')
        self.from_lines = QtWidgets.QLineEdit()
        self.to_lines = QtWidgets.QLineEdit()
        all_btn = QtWidgets.QPushButton('Open all')
        all_btn.clicked.connect(self.open_all)
        all_btn.clicked.connect(dialog.close)
        ok_btn = QtWidgets.QPushButton('Open lines')
        ok_btn.clicked.connect(self.open_lines)
        ok_btn.clicked.connect(dialog.close)
        cancel_btn = QtWidgets.QPushButton('Cancel')
        cancel_btn.clicked.connect(dialog.reject)
        dialog.setLayout(main_layout)
        main_layout.addWidget(text_label, 0, 0, 1, 4)
        main_layout.addWidget(from_label, 1, 0, 1, 1)
        main_layout.addWidget(self.from_lines, 1, 1, 1, 1)
        main_layout.addWidget(to_label, 1, 2, 1, 1)
        main_layout.addWidget(self.to_lines, 1, 3, 1, 1)
        main_layout.addWidget(all_btn, 3, 0, 1, 2)
        main_layout.addWidget(ok_btn, 3, 3, 1, 2)
        # main_layout.addWidget(cancel_btn, 3, 3, 1, 1)
        dialog.show()

    def open_all(self):
        fname = self.filenames[self.cur_tab]
        if fname.rsplit('.', maxsplit=1)[-1] == 'ac':
            content = Huffman().decode(fname)
        else:
            try:
                with open(fname, 'r', encoding='UTF-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                with open(fname, 'r', encoding='GBK') as f:
                    content = f.read()
        self.new_tab()
        self.filenames[self.cur_tab] = fname
        self.rightTabWidget.setTabText(self.rightTabWidget.currentIndex(), fname)
        self.languages[self.cur_tab] = fname.rsplit('.', maxsplit=1)[-1]
        if self.languages[self.cur_tab] == 'c':
            self.languages[self.cur_tab] = 'cpp'
        self.highlighters[self.cur_tab].set_language(self.languages[self.cur_tab])
        # self.text_editors[self.cur_tab].setPlainText(content)
        self.text_editors[self.cur_tab].insert(content)
        self.text_editors[self.cur_tab].filename = fname

    def open_lines(self):
        fname = self.filenames[self.cur_tab]
        if fname.rsplit('.', maxsplit=1)[-1] == 'ac':
            content = Huffman().decode(fname)
        else:
            try:
                with open(fname, 'r', encoding='UTF-8') as f:
                    i = 1
                    content = ''
                    while i < int(self.from_lines.text()):
                        i += 1
                        f.readline()
                    while i <= int(self.to_lines.text()):
                        i += 1
                        content += f.readline()
            except UnicodeDecodeError:
                with open(fname, 'r', encoding='GBK') as f:
                    i = 1
                    content = ''
                    while i < int(self.from_lines.text()):
                        i += 1
                        f.readline()
                    while i <= int(self.to_lines.text()):
                        i += 1
                        content += f.readline()
        self.new_tab()
        self.filenames[self.cur_tab] = fname
        self.rightTabWidget.setTabText(self.rightTabWidget.currentIndex(), fname)
        self.languages[self.cur_tab] = fname.rsplit('.', maxsplit=1)[-1]
        if self.languages[self.cur_tab] == 'c':
            self.languages[self.cur_tab] = 'cpp'
        self.highlighters[self.cur_tab].set_language(self.languages[self.cur_tab])
        # self.text_editors[self.cur_tab].setPlainText(content)
        self.text_editors[self.cur_tab].insert(content)
        self.text_editors[self.cur_tab].filename = fname


def run():
    app = QtWidgets.QApplication(sys.argv)
    alphaCoder = AlphaCoder()
    alphaCoder.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    run()
