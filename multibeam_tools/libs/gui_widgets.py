"""Commonly used widgets for NOAA / MAC echosounder assessment tools"""


try:
    from PySide2 import QtWidgets, QtGui
    from PySide2.QtGui import QDoubleValidator
    from PySide2.QtCore import Qt, QSize
except ImportError as e:
    print(e)
    from PyQt5 import QtWidgets, QtGui
    from PyQt5.QtGui import QDoubleValidator
    from PyQt5.QtCore import Qt, QSize


class PushButton(QtWidgets.QPushButton):
    # generic push button class
    def __init__(self, text='PushButton', width=50, height=20, name='NoName', tool_tip=''):
        super(PushButton, self).__init__()
        self.setText(text)
        self.setFixedSize(int(width), int(height))
        self.setObjectName(name)
        self.setToolTip(tool_tip)


class CheckBox(QtWidgets.QCheckBox):
    # generic checkbox class
    def __init__(self, text='CheckBox', set_checked=False, name='NoName', tool_tip='', width=0, height=0):
        super(CheckBox, self).__init__()
        self.setText(text)
        self.setObjectName(name)
        self.setToolTip(tool_tip)
        self.setChecked(set_checked)

        if height > 0:
            self.setFixedHeight(height)

        if width > 0:
            self.setFixedWidth(width)


class LineEdit(QtWidgets.QLineEdit):
    # generic line edit class
    def __init__(self, text='', width=100, height=20, name='NoName', tool_tip=''):
        super(LineEdit, self).__init__()
        self.setText(text)
        self.setFixedSize(int(width), int(height))
        self.setObjectName(name)
        self.setToolTip(tool_tip)


class ComboBox(QtWidgets.QComboBox):
    # generic combobox class
    def __init__(self, items=[], width=100, height=20, name='NoName', tool_tip=''):
        super(ComboBox, self).__init__()
        self.addItems(items)
        self.setFixedSize(int(width), int(height))
        self.setObjectName(name)
        self.setToolTip(tool_tip)


class Label(QtWidgets.QLabel):
    # generic label class
    def __init__(self, text, width=100, height=20, name='NoName', alignment=(Qt.AlignLeft | Qt.AlignVCenter)):
        super(Label, self).__init__()
        self.setText(text)
        # self.setFixedSize(int(width), int(height))
        self.resize(int(width), int(height))
        self.setObjectName(name)
        self.setAlignment(alignment)


class BoxLayout(QtWidgets.QVBoxLayout):
    # generic class to add widgets or layouts oriented in layout_dir
    def __init__(self, items=[], layout_dir='v', add_stretch=False, alignment=(Qt.AlignLeft | Qt.AlignVCenter)):
        super(BoxLayout, self).__init__()
        # set direction based on logical of layout_dir = top to bottom ('v') or left to right ('h')
        self.setDirection([QtWidgets.QBoxLayout.TopToBottom, QtWidgets.QBoxLayout.LeftToRight][layout_dir == 'h'])

        for i in items:
            if isinstance(i, QtWidgets.QWidget):
                self.addWidget(i)
                self.setAlignment(alignment)
            else:
                self.addLayout(i)
                self.setAlignment(alignment)

        if add_stretch:
            self.addStretch()


class TextEdit(QtWidgets.QTextEdit):
    # generic class for a processing/activity log or text editor
    def __init__(self, stylesheet="background-color: lightgray", readonly=True, name='NoName'):
        super(TextEdit, self).__init__()
        self.setSizePolicy(QtWidgets.QSizePolicy.Minimum,
                               QtWidgets.QSizePolicy.Minimum)
        self.setStyleSheet(stylesheet)
        self.setReadOnly(readonly)
        self.setObjectName(name)


class GroupBox(QtWidgets.QGroupBox):
    # generic class for a groupbox
    def __init__(self, title='', layout=None, set_checkable=False, set_checked=False, name='NoName'):
        super(GroupBox, self).__init__()
        self.setTitle(title)
        self.setLayout(layout)
        self.setCheckable(set_checkable)
        self.setChecked(set_checked)
        self.setObjectName(name)
        # self.setToolTip(tool_tip)


class FileList(QtWidgets.QListWidget):
    # generic class for a file list
    def __init__(self):
        super(FileList, self).__init__()
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.Minimum)
        self.setIconSize(QSize(0, 0))  # set icon size to 0,0 or file names (from item.data) will be indented


class RadioButton(QtWidgets.QRadioButton):
    # generic class for a radio button
    def __init__(self, text='RadioButton', set_checked=False, name='NoName', tool_tip=''):
        super(RadioButton, self).__init__()
        self.setText(text)
        self.setObjectName(name)
        self.setToolTip(tool_tip)
        self.setChecked(set_checked)


class CheckBoxComboBox(QtWidgets.QHBoxLayout):
    # generic class for a checkbox with text and combobox in a horizontal layout
    def __init__(self, label='CheckBoxComboBox', set_checked=False, name='NoName', tool_tip='', items=[], width=100, height=20):
        super(CheckBoxComboBox, self).__init__()
        cbox = ComboBox(items, width, height, name)
        chk = CheckBox(label, set_checked, name, tool_tip)
        self.addWidget(chk)
        self.addWidget(cbox)

class CheckBoxTextBox(QtWidgets.QHBoxLayout):
    # generic class for a checkbox with text and text box in a horizontal layout
    def __init__(self, label='CheckBoxTextBox', set_checked=False, name='NoName', tool_tip='', text='', width=100, height=20):
        super(CheckBoxComboBox, self).__init__()
        self.cbox = ComboBox(items, width, height, name)
        self.chk = CheckBox(text, set_checked, name, tool_tip)
        self.addWidget(self.chk)
        self.addWidget(self.cbox)