# -*- coding: utf-8 -*-
"""
Created on Sat Sep 15 13:30:15 2018
@author: kjerram

Multibeam Echosounder Assessment Toolkit: Kongsberg BIST plotter

Read Kongsberg Built-In Self-Test (BIST) files for assessing
EM multibeam system performance and hardware health.

Note: this was developed primarily using EM302, EM710, and EM122 BIST files in SIS 4 format;
other formats and features will require additional work

N_RX_boards is typically 4; in some cases, this will be 2; this is currently set
manually, and will eventually be detected automatically.

EM2040 RX Noise BIST files may include columns corresponding to frequency, not RX board;
additional development is needed to handle this smoothly, especially between SIS 4 and SIS 5 formats.

Some factory limits for 'acceptable' BIST levels are parsed from the text file; limits for
RX impedance are not automatically detected; these can be found in the BIST text file and
manually adjusted in the plot_rx_z function in read_bist.py (or GUI as feature is added):

                # declare standard spec impedance limits
                RXrecmin = 600
                RXrecmax = 1000
                RXxdcrmin = 250
                RXxdcrmax = 1200

All impedance tests are meant as proxies for hardware health and not as replacement
for direct measurement with Kongsberg tools.

self.BIST_list = ["N/A or non-BIST", "TX Channels Z", "RX Channels Z", "RX Noise Level", "RX Noise Spectrum"]

- Test 1: TX Channels Impedance - plot impedance of TX channels at the transducer,
measured through the TRU with the TX Channels Impedance BIST. Input is a text file
saved from a telnet session running all TX Channels BISTs for the system (these
results are not saved to text file when running BISTs in the SIS interface).

- Test 1: RX Channels Impedance - plot impedance of RX channels measured at the
receiver (upper plot) and at the transducer (lower plot, measured through the receiver).
Input is a standard BIST text file saved from the Kongsberg SIS interface.

- Test 3: RX Noise - plot noise levels perceived by the RX system across all channels.
Input is a RX Noise BIST text file, ideally with multiple (10-20) BISTs saved to
one text file.  Each text file should correspond to the RX noise conditions of interest.
For instance, vessel-borne noise can be assessed across a range of speeds by running
10-20 BISTs at each speed, holding a constant heading at each, and logging one text
file per speed.  Individual tests may be compromised by transient noises, such as
swell hitting the hull; increasing test count will help to reduce the impact of
these events on the average noise plots.

- Test 4: RX Spectrum - similar to Test 3 (RX Noise) plotting, with RX Spectrum BIST
data collected at different speeds and headings

Additional development is pending to handle the various speed/heading options for
multiple RX Noise/Spectrum tests


"""
try:
    from PySide2 import QtWidgets, QtGui
    from PySide2.QtGui import QDoubleValidator
    from PySide2.QtCore import Qt, QSize
except ImportError as e:
    print(e)
    from PyQt5 import QtWidgets, QtGui
    from PyQt5.QtGui import QDoubleValidator
    from PyQt5.QtCore import Qt, QSize
import os
import sys
import datetime
# import multibeam_tools.libs.readBIST
import multibeam_tools.libs.read_bist
import numpy as np
import copy
import itertools
import re


__version__ = "0.1.2"


class PushButton(QtWidgets.QPushButton):
    # generic push button class
    def __init__(self, text='PushButton', width=50, height=20, name='NoName', tool_tip='', parent=None):
        super(PushButton, self).__init__()
        self.setText(text)
        self.setFixedSize(int(width), int(height))
        self.setObjectName(name)
        self.setToolTip(tool_tip)


class CheckBox(QtWidgets.QCheckBox):
    # generic checkbox class
    def __init__(self, text='CheckBox', set_checked=False, name='NoName', tool_tip='', parent=None):
        super(CheckBox, self).__init__()
        self.setText(text)
        self.setObjectName(name)
        self.setToolTip(tool_tip)
        self.setChecked(set_checked)


class LineEdit(QtWidgets.QLineEdit):
    # generic line edit class
    def __init__(self, text='', width=100, height=20, name='NoName', tool_tip='', parent=None):
        super(LineEdit, self).__init__()
        self.setText(text)
        self.setFixedSize(int(width), int(height))
        self.setObjectName(name)
        self.setToolTip(tool_tip)


class ComboBox(QtWidgets.QComboBox):
    # generic combobox class
    def __init__(self, items=[], width=100, height=20, name='NoName', tool_tip='', parent=None):
        super(ComboBox, self).__init__()
        self.addItems(items)
        self.setFixedSize(int(width), int(height))
        self.setObjectName(name)
        self.setToolTip(tool_tip)


class Label(QtWidgets.QLabel):
    # generic label class
    def __init__(self, text='', width=100, height=20, name='NoName', alignment=None, parent=None):
        super(Label, self).__init__()
        self.setText(text)
        # self.setFixedSize(int(width), int(height))
        self.resize(int(width), int(height))
        self.setObjectName(name)
        self.setAlignment(alignment)

class BoxLayout(QtWidgets.QVBoxLayout):
    # generic class to add widgets or layouts oriented in layout_dir
    def __init__(self, items=[], layout_dir='v', parent=None):
        super(BoxLayout, self).__init__()
        # set direction based on logical of layout_dir = top to bottom ('v') or left to right ('h')
        self.setDirection([QtWidgets.QBoxLayout.TopToBottom, QtWidgets.QBoxLayout.LeftToRight][layout_dir == 'h'])

        for i in items:
            if isinstance(i, QtWidgets.QWidget):
                self.addWidget(i)
            else:
                self.addLayout(i)


class MainWindow(QtWidgets.QMainWindow):
    media_path = os.path.join(os.path.dirname(__file__), "media")

    def __init__(self, parent=None):
        super(MainWindow, self).__init__()

        # set up main window
        self.mainWidget = QtWidgets.QWidget(self)
        self.setCentralWidget(self.mainWidget)
        self.setMinimumWidth(900)
        self.setMinimumHeight(500)
        self.setWindowTitle('BIST Plotter v.%s' % __version__)
        self.setWindowIcon(QtGui.QIcon(os.path.join(self.media_path, "icon.png")))

        if os.name == 'nt':  # necessary to explicitly set taskbar icon
            import ctypes
            current_app_id = 'MAC.BISTPlotter.' + __version__  # arbitrary string
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(current_app_id)

        # initialize other necessities
        self.filenames = ['']
        self.input_dir = ''
        self.output_dir = os.getcwd()
        self.missing_fields = []
        self.conflicting_fields = []
        self.model_updated = False
        self.sn_updated = False
        self.date_updated = False
        self.warn_user = True
        self.speed_list = []

        # list of available test types; RX Noise is only available vs. speed, not heading at present
        # RX Noise Spectrum is not available yet; update accordingly
        self.bist_list = ["N/A or non-BIST", "TX Channels Z", "RX Channels Z", "RX Noise Level", "RX Noise Spectrum"]

        # set up layouts of main window
        self.set_left_layout()
        self.set_right_layout()
        self.set_main_layout()

        # set initial custom speed list
        self.update_speed_info()

        # set up file control actions
        self.add_file_btn.clicked.connect(lambda: self.add_files('Kongsberg BIST .txt(*.txt)'))
        self.get_indir_btn.clicked.connect(self.get_input_dir)
        self.get_outdir_btn.clicked.connect(self.get_output_dir)
        self.rmv_file_btn.clicked.connect(self.remove_files)
        self.clr_file_btn.clicked.connect(lambda: self.remove_files(clear_all=True))
        self.show_path_chk.stateChanged.connect(self.show_file_paths)


        # set up BIST selection and plotting actions
        self.select_type_btn.clicked.connect(self.select_bist)
        self.clear_type_btn.clicked.connect(self.clear_bist)
        # self.verify_bist_btn.clicked.connect(self.verify_system_info)
        self.plot_bist_btn.clicked.connect(self.plot_bist)
        # self.custom_info_chk.stateChanged(self.custom_info_gb.setEnabled(self.custom_info_chk.isChecked()))

        # set up user system info actions
        self.model_cbox.activated.connect(self.update_system_info)
        self.sn_tb.textChanged.connect(self.update_system_info)
        self.ship_tb.textChanged.connect(self.update_system_info)
        self.date_tb.textChanged.connect(self.update_system_info)
        self.warn_user_chk.stateChanged.connect(self.verify_system_info)

        self.spd_min_tb.textChanged.connect(self.update_speed_info)
        self.spd_max_tb.textChanged.connect(self.update_speed_info)
        self.spd_int_tb.textChanged.connect(self.update_speed_info)
        self.num_tests_tb.textChanged.connect(self.update_speed_info)

    def set_right_layout(self):
        # set layout with file controls on right, sources on left, and progress log on bottom
        btnh = 20  # height of file control button
        btnw = 110  # width of file control button

        # set the custom info control buttons
        self.sys_info_lbl = QtWidgets.QLabel('Default: any info in BIST will be used;'
                                             '\nmissing fields require user input')

        self.warn_user_chk = CheckBox('Check selected files for missing\nor conflicting system info',
                                      True, 'warn_user_chk',
                                      'Turn off warnings only if you are certain the system info is consistent', self)

        self.sys_info_lbl.setStyleSheet('font: 8pt')
        model_tb_lbl = Label('Model:', 100, 20, 'model_tb_lbl', (Qt.AlignRight | Qt.AlignVCenter), self)
        self.model_cbox = ComboBox(['EM 2040', 'EM 302', 'EM 304', 'EM 710', 'EM 712', 'EM 122', 'EM 124'],
                                   100, 20, 'model', 'Select the EM model (required)', self)
        model_info_layout = BoxLayout([model_tb_lbl, self.model_cbox], 'h', self)

        sn_tb_lbl = Label('Serial No.:', 100, 20, 'sn_tb_lbl', (Qt.AlignRight | Qt.AlignVCenter), self)
        self.sn_tb = LineEdit('999', 100, 20, 'sn', 'Enter the serial number (required)', self)
        sn_info_layout = BoxLayout([sn_tb_lbl, self.sn_tb], 'h', self)

        ship_tb_lbl = Label('Ship Name:', 100, 20, 'ship_tb_lbl', (Qt.AlignRight | Qt.AlignVCenter), self)
        self.ship_tb = LineEdit('R/V Unsinkable II', 100, 20, 'ship', 'Enter the ship name (optional)', self)
        ship_info_layout = BoxLayout([ship_tb_lbl, self.ship_tb], 'h', self)

        cruise_tb_lbl = Label('Cruise Name:', 100, 20, 'cruise_tb_lbl', (Qt.AlignRight | Qt.AlignVCenter), self)
        self.cruise_tb = LineEdit('A 3-hour tour', 100, 20, 'cruise_name', 'Enter the cruise name (optional)', self)
        cruise_info_layout = BoxLayout([cruise_tb_lbl, self.cruise_tb], 'h', self)

        date_tb_lbl = Label('Date (yyyy/mm/dd):', 115, 20, 'date_tb_lbl', (Qt.AlignRight | Qt.AlignVCenter), self)
        self.date_tb = LineEdit('yyyy/mm/dd', 75, 20, 'date', 'Enter the date (required; BISTs over multiple days will '
                                                              'use dates in files, if available)', self)
        date_info_layout = BoxLayout([date_tb_lbl, self.date_tb], 'h')

        # set the custom info button layout
        custom_info_layout = BoxLayout([self.sys_info_lbl, model_info_layout, sn_info_layout, ship_info_layout,
                                        cruise_info_layout, date_info_layout, self.warn_user_chk], 'v', self)

        # set the custom info groupbox
        self.custom_info_gb = QtWidgets.QGroupBox('System Information')
        self.custom_info_gb.setLayout(custom_info_layout)
        self.custom_info_gb.setFixedWidth(200)

        # add file control buttons and file list
        self.add_file_btn = PushButton('Add Files', btnw, btnh, 'add_files', 'Add BIST .txt files', self)
        self.get_indir_btn = PushButton('Add Directory', btnw, btnh, 'add_dir',
                                        'Add a directory with BIST .txt files', self)
        self.include_subdir_btn = CheckBox('Include subdirectories', False, 'include_subdir_chk',
                                           'Include subdirectories when adding a directory', self)
        self.get_outdir_btn = PushButton('Select Output Dir.', btnw, btnh, 'get_outdir',
                                         'Select the output directory (see current output directory below)', self)
        self.rmv_file_btn = PushButton('Remove Selected', btnw, btnh, 'rmv_files', 'Remove selected files', self)
        self.clr_file_btn = PushButton('Remove All Files', btnw, btnh, 'clr_file_btn', 'Remove all files', self)
        self.show_path_chk = CheckBox('Show file paths', False, 'show_paths_chk', 'Show paths in file list', self)

        # set the file control button layout
        file_btn_layout = BoxLayout([self.add_file_btn, self.get_indir_btn, self.get_outdir_btn, self.rmv_file_btn,
                                     self.clr_file_btn, self.include_subdir_btn, self.show_path_chk],
                                    'v', self)

        # set the BIST selection buttons
        type_cbox_lbl = Label('Select BIST type:', 100, 20, 'type_cbox_lbl', (Qt.AlignLeft | Qt.AlignVCenter), self)
        # type_cbox_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.type_cbox = ComboBox(self.bist_list[1:-1], btnw, btnh, 'bist_cbox',
                                  'Select a BIST type for file verification and plotting', self)
        self.select_type_btn = PushButton('Select BISTs', btnw, btnh, 'select_type',
                                          'Filter and select source files by the chosen BIST type', self)
        self.clear_type_btn = PushButton('Clear Selected', btnw, btnh, 'clear_type', 'Clear file selection', self)
        self.plot_bist_btn = PushButton('Plot Selected', btnw, btnh, 'plot_bist',
                                        'Plot selected, verified files (using current system information above, '
                                        'if not available in BIST)', self)

        # set the BIST options layout
        plot_btn_layout = BoxLayout([type_cbox_lbl, self.type_cbox, self.select_type_btn, self.clear_type_btn,
                                     self.plot_bist_btn], 'v', self)

        # set options for getting RX Noise vs speed string from filename, custom speed vector, and/or sorting
        spd_str_tb_lbl = Label('Filename speed string:', 120, 20, 'spd_str_tb_lbl',
                               (Qt.AlignRight | Qt.AlignVCenter), self)
        self.spd_str_tb = LineEdit('_08_kts', 60, 20, 'spd_str_tb',
                                   'Enter an example string for the test speed noted in the filename (e.g., "_08_kts")'
                                   'for each BIST text file.  This string is used to search for speed in each '
                                   'filename, not used as speed directly.  The user will be warned if speeds cannot be '
                                   'parsed for all files.  Using a consistent filename format will help greatly.'
                                   '\n\nSIS 4 RX Noise BISTs do not include speed, so the user must note the test speed '
                                   'in the text filename, e.g., default naming of "BIST_FILE_NAME_02_kt.txt" or '
                                   '"_120_RPM.txt", etc. '
                                   '\n\nSIS 5 BISTs include speed over ground, which is parsed and used by default, '
                                   'if available. The user may assign a custom speed list in any case if speed is not '
                                   'available in the filename or applicable for the desired plot.', self)

        spd_str_layout = BoxLayout([spd_str_tb_lbl, self.spd_str_tb], 'h', self)

        spd_unit_lbl = Label('Speed units:', 100, 20, 'spd_unit_lbl', (Qt.AlignRight | Qt.AlignVCenter), self)
        self.spd_unit_cbox = ComboBox(['SOG (kts)', 'RPM', '% Handle'], 100, 20, 'spd_unit_cbox', 'Select the speed units', self)
        spd_unit_layout = BoxLayout([spd_unit_lbl, self.spd_unit_cbox], 'h', self)

        spd_min_tb_lbl = Label('Minimum speed:', 120, 20, 'spd_min_tb_lbl', (Qt.AlignRight | Qt.AlignVCenter), self)
        self.spd_min_tb = LineEdit('0', 40, 20, 'spd_min_tb', 'Enter the minimum speed', self)
        self.spd_min_tb.setValidator(QDoubleValidator(0, np.inf, 1))
        spd_min_layout = BoxLayout([spd_min_tb_lbl, self.spd_min_tb], 'h', self)

        spd_max_tb_lbl = Label('Maximum speed:', 120, 20, 'spd_max_tb_lbl', (Qt.AlignRight | Qt.AlignVCenter), self)
        self.spd_max_tb = LineEdit('12', 40, 20, 'spd_max_tb', 'Enter the maximum speed', self)
        self.spd_max_tb.setValidator(QDoubleValidator(0, np.inf, 1))
        spd_max_layout = BoxLayout([spd_max_tb_lbl, self.spd_max_tb], 'h', self)

        spd_int_tb_lbl = Label('Speed interval:', 120, 20, 'spd_int_tb_lbl', (Qt.AlignRight | Qt.AlignVCenter), self)
        self.spd_int_tb = LineEdit('2', 40, 20, 'spd_min_tb', 'Enter the speed interval', self)
        self.spd_int_tb.setValidator(QDoubleValidator(0, np.inf, 1))
        spd_int_layout = BoxLayout([spd_int_tb_lbl, self.spd_int_tb], 'h', self)

        num_tests_tb_lbl = Label('Num. tests per speed:', 120, 20, 'num_tests_tb_lbl',
                                 (Qt.AlignRight | Qt.AlignVCenter), self)
        self.num_tests_tb = LineEdit('10', 40, 20, 'num_tests_tb', 'Enter the number of tests at each speed', self)
        self.num_tests_tb.setValidator(QDoubleValidator(0, np.inf, 0))
        spd_num_layout = BoxLayout([num_tests_tb_lbl, self.num_tests_tb], 'h', self)

        total_num_speeds_tb_lbl = Label('Total num. speeds:', 120, 20, 'total_num_speeds_tb_lbl',
                                        (Qt.AlignRight | Qt.AlignVCenter), self)
        self.total_num_speeds_tb = LineEdit('7', 40, 20, 'total_num_speeds_tb',
                                            'Total number of speeds in custom info', self)
        self.total_num_speeds_tb.setEnabled(False)
        total_spd_num_layout = BoxLayout([total_num_speeds_tb_lbl, self.total_num_speeds_tb], 'h', self)

        total_num_tests_tb_lbl = Label('Total num. tests:', 120, 20, 'total_num_tests_tb_lbl',
                                       (Qt.AlignRight | Qt.AlignVCenter), self)
        self.total_num_tests_tb = LineEdit('70', 40, 20, 'total_num_tests_tb',
                                           'Total number of tests in custom info', self)
        self.total_num_tests_tb.setEnabled(False)
        total_test_num_layout = BoxLayout([total_num_tests_tb_lbl, self.total_num_tests_tb], 'h', self)

        self.final_speeds_hdr = 'Speed list: '
        self.final_speeds_lbl = Label(self.final_speeds_hdr + str(self.speed_list), 100, 20, 'final_speeds_lbl',
                                      (Qt.AlignLeft | Qt.AlignVCenter), self)
        self.final_speeds_lbl.setWordWrap(True)

        custom_spd_layout = BoxLayout([spd_min_layout, spd_max_layout, spd_int_layout, spd_num_layout,
                                       total_spd_num_layout, total_test_num_layout, self.final_speeds_lbl], 'v', self)

        self.custom_speed_gb = QtWidgets.QGroupBox('Use custom speed list')
        self.custom_speed_gb.setLayout(custom_spd_layout)
        self.custom_speed_gb.setCheckable(True)
        self.custom_speed_gb.setChecked(False)

        speed_layout = BoxLayout([spd_str_layout, spd_unit_layout, self.custom_speed_gb], 'v', self)

        # set up tabs
        self.tabs = QtWidgets.QTabWidget()

        # set up tab 1: plot options
        self.tab1 = QtWidgets.QWidget()
        self.tab1.layout = file_btn_layout
        self.tab1.layout.addStretch()
        self.tab1.setLayout(self.tab1.layout)

        # set up tab 2: filtering options
        self.tab2 = QtWidgets.QWidget()
        self.tab2.layout = plot_btn_layout
        self.tab2.layout.addStretch()
        self.tab2.setLayout(self.tab2.layout)

        # set up tab 3: advanced options
        self.tab3 = QtWidgets.QWidget()
        self.tab3.layout = speed_layout
        self.tab3.layout.addStretch()
        self.tab3.setLayout(self.tab3.layout)

        # add tabs to tab layout
        self.tabs.addTab(self.tab1, 'Files')
        self.tabs.addTab(self.tab2, 'Plot')
        self.tabs.addTab(self.tab3, 'Speed')

        self.tabw = 200  # set fixed tab width
        self.tabs.setFixedWidth(self.tabw)

        # stack file_control_gb and plot_control_gb
        self.right_layout = QtWidgets.QVBoxLayout()
        self.right_layout.addWidget(self.custom_info_gb)
        self.right_layout.addWidget(self.tabs)

    def set_left_layout(self):
        # add table showing selected files
        self.file_list = QtWidgets.QListWidget()
        self.file_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)

        # set layout of file list
        self.file_list_layout = QtWidgets.QVBoxLayout()
        self.file_list_layout.addWidget(self.file_list)

        # set file list group box
        self.file_list_gb = QtWidgets.QGroupBox('Sources')
        self.file_list_gb.setLayout(self.file_list_layout)
        self.file_list_gb.setMinimumWidth(550)
        self.file_list_gb.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding,
                                        QtWidgets.QSizePolicy.MinimumExpanding)

        # add activity log widget
        self.log = QtWidgets.QTextEdit()
        # self.log.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding,
        #                        QtWidgets.QSizePolicy.MinimumExpanding)
        self.log.setStyleSheet("background-color: lightgray")
        self.log.setReadOnly(True)
        self.update_log('*** New BIST plotting log ***')

        # add progress bar for total file list
        self.current_fnum_lbl = QtWidgets.QLabel('Current file count:')
        self.current_outdir_lbl = QtWidgets.QLabel('Current output directory: ' + self.output_dir)

        self.calc_pb_lbl = QtWidgets.QLabel('Total Progress:')
        self.calc_pb = QtWidgets.QProgressBar()
        self.calc_pb.setGeometry(0, 0, 200, 30)
        self.calc_pb.setMaximum(100)  # this will update with number of files
        self.calc_pb.setValue(0)

        # set progress bar layout
        self.calc_pb_layout = QtWidgets.QHBoxLayout()
        self.calc_pb_layout.addWidget(self.calc_pb_lbl)
        self.calc_pb_layout.addWidget(self.calc_pb)

        self.prog_layout = QtWidgets.QVBoxLayout()
        self.prog_layout.addWidget(self.current_fnum_lbl)
        self.prog_layout.addWidget(self.current_outdir_lbl)
        self.prog_layout.addLayout(self.calc_pb_layout)

        # set the log layout
        self.log_layout = QtWidgets.QVBoxLayout()
        self.log_layout.addWidget(self.log)
        self.log_layout.addLayout(self.prog_layout)

        # set the log group box widget with log layout
        self.log_gb = QtWidgets.QGroupBox('Activity Log')
        self.log_gb.setLayout(self.log_layout)
        self.log_gb.setMinimumWidth(550)

        # set the left panel layout with file controls on top and log on bottom
        self.left_layout = QtWidgets.QVBoxLayout()
        self.left_layout.addWidget(self.file_list_gb)
        self.left_layout.addWidget(self.log_gb)  # add log group box

    def set_main_layout(self):  # set the main layout with file controls on left and swath figure on right
        main_layout = QtWidgets.QHBoxLayout()
        main_layout.addLayout(self.left_layout)
        main_layout.addLayout(self.right_layout)
        self.mainWidget.setLayout(main_layout)

    def add_files(self, ftype_filter, input_dir='HOME', include_subdir=False):  # add all files of specified type in directory
        if input_dir == 'HOME':  # select files manually if input_dir not specified as optional argument
            fnames = QtWidgets.QFileDialog.getOpenFileNames(self, 'Open files...', os.getenv('HOME'), ftype_filter)
            fnames = fnames[0]  # keep only the filenames in first list item returned from getOpenFileNames

        else:  # get all files satisfying ftype_filter in input_dir
            fnames = []

            if include_subdir:  # walk through all subdirectories
                for dirpath, dirnames, filenames in os.walk(input_dir):
                    for filename in [f for f in filenames if f.endswith(ftype_filter)]:
                        fnames.append(os.path.join(dirpath, filename))

            else:  # step through all files in this directory only (original method)
                for f in os.listdir(input_dir):
                    if os.path.isfile(os.path.join(input_dir, f)):  # verify it's a file
                        if os.path.splitext(f)[1] == ftype_filter:  # verify ftype_filter extension
                            fnames.append(os.path.join(input_dir, f))  # add whole path, same as getOpenFileNames

        # get updated file list and add selected files only if not already listed
        self.get_current_file_list()
        fnames_new = [fn for fn in fnames if fn not in self.filenames]
        fnames_skip = [fs for fs in fnames if fs in self.filenames]

        if len(fnames_skip) > 0:  # skip any files already added, update log
            self.update_log('Skipping ' + str(len(fnames_skip)) + ' file(s) already added')

        for f in range(len(fnames_new)):  # add the new files only after verifying BIST type
            bist_type, sis_ver_found = multibeam_tools.libs.read_bist.verify_bist_type(fnames_new[f])
            print(bist_type, sis_ver_found)

            if 0 not in bist_type:  # add files only if plotters are available for tests in file (test types  > 0)
                # add item with full file path data, set text according to show/hide path button
                [path, fname] = fnames_new[f].rsplit('/', 1)
                # print('path=', path)
                # print('fname=', fname)
                # add file only if name exists prior to ext (may slip through splitext check if adding directory)
                if fname.rsplit('.', 1)[0]:
                    new_item = QtWidgets.QListWidgetItem()
                    new_item.setData(1, fnames_new[f].replace('\\','/'))  # set full file path as data, role 1
                    new_item.setText((path + '/') * int(self.show_path_chk.isChecked()) + fname)  # set text, show path
                    self.file_list.addItem(new_item)
                    # self.update_log('Added ' + fname)  # fnames_new[f].rsplit('/',1)[-1])
                    bist_types_found = [self.bist_list[idx_found] for idx_found in bist_type]
                    self.update_log('Added ' + fnames_new[f].split('/')[-1] +
                                    ' (SIS ' + str(sis_ver_found) + ': ' +
                                    ', '.join(bist_types_found) + ')')

                else:
                    self.update_log('Skipping empty filename ' + fname)

            else:  # skip non-verified BIST types
                self.update_log('Skipping ' + fnames_new[f].split('/')[-1] + ' (' + self.bist_list[0] + ')')

        self.get_current_file_list()  # update self.file_list and file count
        self.current_fnum_lbl.setText('Current file count: ' + str(len(self.filenames)))

    def show_file_paths(self):
        # show or hide path for all items in file_list according to show_paths_chk selection
        for i in range(self.file_list.count()):
            [path, fname] = self.file_list.item(i).data(1).rsplit('/', 1)  # split full file path from item data, role 1
            self.file_list.item(i).setText((path+'/')*int(self.show_path_chk.isChecked()) + fname)

    def get_input_dir(self):
        try:
            self.input_dir = QtWidgets.QFileDialog.getExistingDirectory(self, 'Add directory', os.getenv('HOME'))
            self.update_log('Added directory: ' + self.input_dir)

            # get a list of all .txt files in that directory, '/' avoids '\\' in os.path.join in add_files
            self.update_log('Adding files in directory: ' + self.input_dir)
            self.add_files(ftype_filter='.txt', input_dir=self.input_dir+'/',
                           include_subdir=self.include_subdir_btn.isChecked())

        except ValueError:
            self.update_log('No input directory selected.')
            self.input_dir = ''
            pass

    def get_output_dir(self):  # get output directory for saving plots
        try:
            new_output_dir = QtWidgets.QFileDialog.getExistingDirectory(self, 'Select output directory',
                                                                        os.getenv('HOME'))

            if new_output_dir is not '':  # update output directory if not cancelled
                self.output_dir = new_output_dir
                self.update_log('Selected output directory: ' + self.output_dir)
                self.current_outdir_lbl.setText('Current output directory: ' + self.output_dir)

        except:
            self.update_log('No output directory selected.')
            pass

    def remove_files(self, clear_all=False):  # remove selected files
        self.get_current_file_list()
        selected_files = self.file_list.selectedItems()

        if clear_all:  # clear all
            self.file_list.clear()
            self.filenames = []
            self.update_log('All files have been removed.')

        elif self.filenames and not selected_files:  # files exist but nothing is selected
            self.update_log('No files selected for removal.')
            return

        else:  # remove only the files that have been selected
            for f in selected_files:
                fname = f.text().split('/')[-1]
                self.file_list.takeItem(self.file_list.row(f))
                self.update_log('Removed ' + fname)

    def get_current_file_list(self):  # get current list of files in qlistwidget
        list_items = []
        for f in range(self.file_list.count()):
            list_items.append(self.file_list.item(f))

        # self.filenames = [f.text() for f in list_items]  # convert to text
        self.filenames = [f.data(1) for f in list_items]  # return list of full file paths stored in item data, role 1

        # self.filenames = [f.data(1) for f in list_items]  # return list of full file paths stored in item data, role 1
        self.current_fnum_lbl.setText('Current file count: ' + str(len(self.filenames)))

    # def get_new_file_list(self, fext='', flist_old=None):
    def get_new_file_list(self, fext=[''], flist_old=[]):
        # determine list of new files with file extension fext that do not exist in flist_old
        # flist_old may contain paths as well as file names; compare only file names
        self.get_current_file_list()
        fnames_ext = [fn for fn in self.filenames if any(ext in fn for ext in fext)]  # fnames (w/ paths) matching ext
        fnames_old = [fn.split('/')[-1] for fn in flist_old]  # file names only (no paths) from flist_old
        fnames_new = [fn for fn in fnames_ext if fn.split('/')[-1] not in fnames_old]  # check if fname in fnames_old

        return fnames_new  # return the fnames_new (with paths)

    def select_bist(self):
        # verify BIST types in current file list and select those matching current BIST type in combo box
        self.clear_bist()  # update file list and clear all selections before re-selecting those of desired BIST type
        bist_count = 0  # count total selected files

        for f in range(len(self.filenames)):  # loop through file list and select if matches BIST type in combo box
            # bist_type, sis_ver_found = multibeam_tools.libs.read_bist.verify_bist_type(self.file_list.item(f).text())
            bist_type, sis_ver_found = multibeam_tools.libs.read_bist.verify_bist_type(self.file_list.item(f).data(1))

            # check whether selected test index from combo box  is available in this file
            if int(self.type_cbox.currentIndex()+1) in bist_type:  # currentIndex+1 because bist_list starts at 0 = N/A
                self.file_list.item(f).setSelected(True)
                bist_count = bist_count+1

        if bist_count == 0:  # update log with selection total
            self.update_log('No ' + self.type_cbox.currentText() + ' files available for selection')

        else:
            self.update_log('Selected ' + str(bist_count) + ' ' + self.type_cbox.currentText() + ' file(s)')

        if self.warn_user_chk.isChecked():  # if desired, check the system info in selected files
            self.verify_system_info()

    def clear_bist(self):
        self.get_current_file_list()
        for f in range(len(self.filenames)):
            self.file_list.item(f).setSelected(False)  # clear any pre-selected items before re-selecting verified ones

    def update_system_info(self):  # get updated/stripped model, serial number, ship, cruise, and date
        self.model_number = self.model_cbox.currentText().replace('EM', '').strip()  # get model from name list
        self.sn = self.sn_tb.text().strip()
        self.ship_name = self.ship_tb.text().strip()
        self.cruise_name = self.cruise_tb.text().strip()
        self.date_str = self.date_tb.text().strip()

        # reset the text color after clicking/activating/entering user info
        sender_button = self.sender()
        sender_button.setStyleSheet('color: black')

        # print('current list of missing fields is:', self.missing_fields)
        # remove the user-updated field from the list of missing fields
        if sender_button.objectName() in self.missing_fields:
            self.missing_fields.remove(sender_button.objectName())
            # self.plot_bist_btn.setEnabled(False)

    def verify_system_info(self):  # prompt user for missing fields or warn if different
        self.missing_fields = []
        self.conflicting_fields = []
        self.model_updated = False
        self.sn_updated = False
        self.date_updated = False

        # self.update_sys_info_colors()

        # reset all user fields to black
        # for widget in [self.model_cbox, self.sn_tb, self.date_tb]:  # set text to red for all missing fields
        #         widget.setStyleSheet('color: red')

        # get list of currently selected files
        # fnames_sel = [self.file_list.item(f).text() for f in range(self.file_list.count())
        #               if self.file_list.item(f).isSelected()]
        fnames_sel = [self.file_list.item(f).data(1) for f in range(self.file_list.count())
                      if self.file_list.item(f).isSelected()]

        if self.file_list.count() > 0:
            if self.warn_user_chk.isChecked():
                if not fnames_sel:  # prompt user to select files if none selected
                    self.update_log('Please select BIST type and click Select BISTs to verify system info')
                else:
                    # elif self.warn_user_chk.isChecked():
                    self.update_log('Checking ' + str(len(fnames_sel)) + ' files for model, serial number, and date')

        for fname in fnames_sel:  # loop through files, verify BIST type, and plot if matches test type
            fname_str = fname[fname.rfind('/') + 1:].rstrip()
            # get SIS version for later use in parsers, store in BIST dict (BIST type verified at file selection)
            _, sis_ver_found = multibeam_tools.libs.read_bist.verify_bist_type(fname)  # get SIS ver for RX Noise parser

            # get available system info in this file
            sys_info = multibeam_tools.libs.read_bist.check_system_info(fname, sis_version=sis_ver_found)

            if not sys_info or any(not v for v in sys_info.values()):  # warn user if missing system info in file
                if sys_info:
                    missing_fields = ', '.join([k for k, v in sys_info.items() if not v])
                    self.update_log('***WARNINGS: Missing system info (' + missing_fields + ') in file ' + fname)
                else:
                    self.update_log('***WARNING: Missing all system info in file ' + fname)

                # continue

            # update user entry fields to any info available in BIST, store conflicting fields if different
            if sys_info['model']:
                print('BIST has model=', sys_info['model'])
                model = sys_info['model']
                if sys_info['model'].find('2040') > -1:
                    model = '2040'  # store full 2040 model name in sys_info, but just use 2040 for model comparison

                if not self.model_updated:  # update model with first model found
                    # self.model_cbox.setCurrentIndex(self.model_cbox.findText('EM '+sys_info['model']))
                    self.model_cbox.setCurrentIndex(self.model_cbox.findText('EM '+model))
                    self.update_log('Updated model to ' + self.model_cbox.currentText() + ' (first model found)')
                    self.model_updated = True

                # elif 'EM '+sys_info['model'] != self.model_cbox.currentText():  # model was updated but new model found
                elif 'EM '+model != self.model_cbox.currentText():  # model was updated but new model found

                    # self.update_log('***WARNING: New model (EM ' + sys_info['model'] + ') detected in ' + fname_str)
                    self.update_log('***WARNING: New model (EM ' + model + ') detected in ' + fname_str)
                    self.conflicting_fields.append('model')

            if sys_info['sn']:
                if not self.sn_updated:  # update serial number with first SN found
                    self.sn_tb.setText(sys_info['sn'])
                    self.update_log('Updated serial number to ' + self.sn_tb.text() + ' (first S/N found)')
                    self.sn_updated = True

                elif sys_info['sn'] != self.sn_tb.text().strip():  # serial number was updated but new SN found
                    self.update_log('***WARNING: New serial number (' + sys_info['sn'] + ') detected in ' + fname_str)
                    self.conflicting_fields.append('sn')

            if sys_info['date']:
                if not self.date_updated:  # update date with first date found
                    self.date_tb.setText(sys_info['date'])
                    self.update_log('Updated date to ' + self.date_tb.text() + ' (first date found)')
                    self.date_updated = True

                elif sys_info['date'] != self.date_tb.text().strip():  # date was updated but new date found
                    self.update_log('***WARNING: New date (' + sys_info['date'] + ') detected in ' + fname_str)
                    self.conflicting_fields.append('date')

            # store missing fields, reduce to set after looping through files and disable/enable plot button
            self.missing_fields.extend([k for k in ['model', 'sn', 'date'] if not sys_info[k]])
            # print('self.missing fields =', self.missing_fields)
            # print('self.conflicting fields =', self.conflicting_fields)

        # after reading all files, reduce set of missing fields and disable/enable plot button accordingly
        self.missing_fields = [k for k in set(self.missing_fields)]
        self.conflicting_fields = [k for k in set(self.conflicting_fields)]

        # if self.missing_fields or self.conflicting_fields:
        self.update_sys_info_colors()
        if self.warn_user_chk.isChecked() and any(self.missing_fields or self.conflicting_fields):
            user_warning = QtWidgets.QMessageBox.question(self, 'System info check',
                'Red field(s) are either:\n\n' +
                '          1) not available from the selected BIST(s), or\n' +
                '          2) available but conflicting across selected BISTs\n\n' +
                'Please confirm these fields or update file selection before plotting.\n' +
                'System info shown will be used for any fields not found in a file, but will not replace fields parsed '
                'successfully (even if conflicting).',
                QtWidgets.QMessageBox.Ok)

    def update_sys_info_colors(self):  # update the user field colors to red/black based on missing/conflicting info
        for widget in [self.model_cbox, self.sn_tb, self.date_tb]:  # set text to red for all missing fields
            widget.setStyleSheet('color: black')  # reset field to black before checking missing/conflicting fields
            if widget.objectName() in self.missing_fields + self.conflicting_fields:
                widget.setStyleSheet('color: red')

    def plot_bist(self):
        # get list of selected files and send each to the appropriate plotter
        bist_test_type = self.type_cbox.currentText()
        self.update_log('Plotting selected ' + bist_test_type + ' BIST files')

        if self.type_cbox.currentIndex() == 2:
            if self.custom_speed_gb.isChecked():
                self.update_log('RX Noise vs. Speed: Custom speeds entered by user will override any speeds parsed '
                                'from files or filenames, and will be applied in order of files loaded')
            else:
                self.update_log('RX Noise vs. Speed: Speeds will be parsed from filename (SIS 4) or file (SIS 5), '
                                'if available')

        self.get_current_file_list()
        self.update_system_info()

        # housekeeping for updating each parsed BIST dict with system info (assume correct from user; add check later)
        freq = multibeam_tools.libs.read_bist.get_freq(self.model_number)  # get nominal freq to use if not parsed
        swell_str = '_into_swell'  # identify the RX Noise/Spectrum file heading into the swell by '_into_swell.txt'
        rxn_test_type = 1  # vs speed only for now; add selection, parsers, and plotters for heading tests later
        bist_count = 0  # reset
        bist_fail_list = []

        # set up dicts for parsed data; currently setup to work with read_bist with minimal modification as first step
        bist_list_index = self.bist_list.index(bist_test_type)
        bist = multibeam_tools.libs.read_bist.init_bist_dict(bist_list_index)
        fnames_sel = [self.file_list.item(f).data(1) for f in range(self.file_list.count())
                      if self.file_list.item(f).isSelected()]

        if not fnames_sel:
            self.update_log('Please select at least one BIST to plot...')

        for fname in fnames_sel:  # loop through files, verify BIST type, and plot if matches test type
            self.update_log('Parsing ' + fname)
            fname_str = fname[fname.rfind('/') + 1:].rstrip()

            # get SIS version for later use in parsers, store in BIST dict (BIST type verified at file selection)
            _, sis_ver_found = multibeam_tools.libs.read_bist.verify_bist_type(fname)  # get SIS ver for RX Noise parser

            print('in BIST plotter, found SIS version:', sis_ver_found)

            # get available system info in this file
            sys_info = multibeam_tools.libs.read_bist.check_system_info(fname, sis_version=sis_ver_found)
            print('sys_info return =', sys_info)

            bist_temp = []

            try:  # try parsing the files according to BIST type
                if bist_test_type == self.bist_list[1]:  # TX Channels
                    bist_temp = multibeam_tools.libs.read_bist.parse_tx_z(fname, sis_version=sis_ver_found)

                elif bist_test_type == self.bist_list[2]:  # RX Channels
                    # check model and skip EM2040 variants (model combobox is updated during verification step,
                    # so this can be checked even if model is not available in sys_info)
                    # print('sys info model is', sys_info['model'],' with type', type(sys_info['model']))

                    # skip 2040 (FUTURE: RX Channels for all freq)
                    if sys_info['model']:
                        if sys_info['model'].find('2040') > -1:
                            self.update_log('***WARNING: RX Channels plot N/A for EM2040 variants: ' + fname_str)
                            bist_fail_list.append(fname)
                            continue

                    elif self.model_cbox.currentText().find('2040') > -1:
                        self.update_log('***WARNING: Model not parsed from file and EM2040 selected; '
                                        'RX Channels plot not yet available for EM2040 variants: ' + fname_str)
                        bist_fail_list.append(fname)
                        continue

                    bist_temp = multibeam_tools.libs.read_bist.parse_rx_z(fname, sis_version=sis_ver_found)

                elif bist_test_type == self.bist_list[3]:  # RX Noise
                    bist_temp = multibeam_tools.libs.read_bist.parse_rx_noise(fname, sis_version=sis_ver_found)

                    # print('in main script, BIST_temp[test]=', bist_temp['test'])
                    # print('with type', type(bist_temp['test']))
                    # print('with size', np.size(bist_temp['test']))
                    # print('and len', len(bist_temp['test']))

                    # get speed or heading of test from filename
                    if rxn_test_type == 1:  # RX noise vs speed; get speed from fname "_6_kts.txt", "_9p5_kts.txt"
                        if bist_temp['speed'] == []:  # try to get speed from filename if not parsed from BIST
                            # self.update_log('Parsing speeds from SIS 4 filenames (e.g., "_6_kts.txt", "_9p5_kts.txt")')
                            try:
                                temp_speed = float(999.9)  # placeholder speed

                                if not self.custom_speed_gb.isChecked():
                                    # continue trying to get speed from filename if custom speed is not checked
                                    temp = ["".join(x) for _, x in itertools.groupby(self.spd_str_tb.text(), key=str.isdigit)]
                                    print('********parsing speed based on example spd_str = ', self.spd_str_tb.text())
                                    print('temp =', temp)

                                    # take all characters between first and last elements in temp, if not digits
                                    if not temp[-1].isdigit():
                                        temp_speed = fname.rsplit(temp[-1], 1)[0]  # split at non-digit char following speed
                                        print('splitting fname at non-digit char following speed: temp_speed=', temp_speed)
                                    else:
                                        temp_speed = fname.rsplit(".", 1)[0]  # or split at start of file extension
                                        print('splitting fname temp speed at file ext: temp_speed=', temp_speed)

                                    print('after first step, temp_speed=', temp_speed)

                                    if not temp[0].isdigit():
                                        temp_speed = temp_speed.rsplit(temp[0], 1)[-1]  # split at non-digit char preceding spd
                                    else:
                                        temp_speed = temp_speed.rsplit("_", 1)[-1]  # or split at last _ preceding speed

                                    print('after second step, temp_speed=', temp_speed)
                                    temp_speed = float(temp_speed.replace(" ","").replace("p", "."))  # replace
                                    print('parsed temp_speed = ', temp_speed)

                                bist_temp['speed'] = temp_speed  # store updated speed if

                                # testing to assign one speed per test rather than one speed per file
                                bist_temp['speed_bist'] = [temp_speed for i in range(len(bist_temp['test']))]
                                print('bist_temp[speed_bist] =', bist_temp['speed_bist'])

                            except ValueError:
                                self.update_log('***WARNING: Error parsing speeds from filenames; '
                                                'check example speed characters!')
                                self.update_log('***SIS v4 RX Noise file names must include speed, '
                                                '.e.g., "_6_kts.txt" or "_9p5_kts.txt"')
                                bist_fail_list.append(fname)
                                continue

                    elif rxn_test_type == 2:  # RX noise vs heading; get hdg, file idx into swell from fname
                        if bist_temp['hdg'] == []:
                            self.update_log('Parsing headings from filenames')
                            try:
                                if fname_str.find(swell_str) > -1:
                                    bist_temp['file_idx_into_swell'] = bist_count
                                # get heading from fname "..._hdg_010.txt" or "...hdg_055_into_swell.txt"
                                bist_temp['hdg'] = float(fname.replace(swell_str, '').rsplit("_")[-1].rsplit(".")[0])
                            except ValueError:
                                self.update_log('***WARNING: Error parsing headings from filenames; check formats!')
                                bist_fail_list.append(fname)
                                continue

                # elif bist_test_type == self.bist_list[4]:  # RX Spectrum
                #     bist_temp = multibeam_tools.libs.read_bist.parseRXSpectrum(fname)  # SPECTRUM PARSER NOT WRITTEN

                else:
                    print("Unknown test type: ", bist_test_type)

                if bist_temp == []:
                    self.update_log('***WARNING: No data parsed in ' + fname)
                    bist_fail_list.append(fname)
                    continue  # do not try to append

            except ValueError:
                self.update_log('***WARNING: Error parsing ' + fname)
                bist_fail_list.append(fname)
                pass  # do not try to append

            else:  # try to append data if no exception during parsing
                # print('no exceptions during parsing, checking bist_temp for file', fname_str)
                try:
                    # add user fields if not parsed from BIST file (availability depends on model and SIS ver)
                    # this can be made more elegant once all modes are working
                    print('*********** ----> checking info, at start:')
                    print('bist_temp[frequency]=', bist_temp['frequency'])
                    print('bist_temp[model]=', bist_temp['model'])
                    print('bist_temp[sn]=', bist_temp['sn'])
                    print('bist_temp[date]=', bist_temp['date'])
                    print('bist_temp[time]=', bist_temp['time'])

                    if bist_temp['frequency'] == []:  # add freq if empty (e.g., most SIS 4 BISTs); np array if read
                        bist_temp['frequency'] = [freq]  # add nominal freq for each file in case order changes

                    if not bist_temp['date']:  # add date if not parsed (incl. in SIS 5, but not all SIS 4 or TX chan)
                        self.update_log('***WARNING: no date parsed from file ' + fname_str)

                        if sys_info['date']:  # take date from sys_info if parsed
                            bist_temp['date'] = sys_info['date']

                        else:  # otherwise, try to get from filename or take from user input
                            try:
                                bist_temp['date'] = re.match('\d{8}', fname_str).group()
                                self.update_log('Assigning date (' + bist_temp['date'] + ') from filename')

                            except:
                                if self.date_str.replace('/', '').isdigit():  # user date if modified from yyyy/mm/dd
                                    bist_temp['date'] = self.date_str.replace('/','')
                                    self.update_log('Assigning date (' + bist_temp['date'] + ') from user input')

                        if bist_temp['date'] == []:
                            self.update_log('***WARNING: no date assigned to ' + fname_str + '\n' +
                                            '           This file may be skipped if date/time are required\n' +
                                            '           Update filenames to include YYYYMMDD (or enter date ' +
                                            'in user input field if all files are on the same day)')

                    if not bist_temp['time']:  # add time if not parsed (incl. in SIS 5, but not all SIS 4 or TX chan)
                        self.update_log('***WARNING: no time parsed from file ' + fname_str)

                        if sys_info['time']:  # take date from sys_info if parsed
                            bist_temp['time'] = sys_info['time']

                        else:  # otherwise, try to get from filename or take from user input
                            try:  # assume date and time in filename are YYYYMMDD and HHMMSS with _ or - in between
                                time_str = re.search(r"[_-]\d{6}", fname_str).group()
                                bist_temp['time'] = time_str.replace('_', "").replace('-', "")
                                self.update_log('Assigning time (' + bist_temp['time'] + ') from filename')

                            except:
                                self.update_log('***WARNING: no time assigned to ' + fname_str + '\n' +
                                                '           This file may be skipped if date/time are required\n' +
                                                '           Update filenames to include time, e.g., YYYYMMDD-HHMMSS')

                    if bist_temp['model'] == []:  # add model if not parsed
                        if sys_info['model']:
                            bist_temp['model'] = sys_info['model']
                        else:
                            bist_temp['model'] = self.model_number

                    if bist_temp['sn'] == []:  # add serial number if not parsed
                        if sys_info['sn']:
                            bist_temp['sn'] = sys_info['sn']  # add serial number if not parsed from system info
                        else:
                            bist_temp['sn'] = self.sn

                    print('************ after checking, bist_temp info is now:')
                    print('bist_temp[frequency]=', bist_temp['frequency'])
                    print('bist_temp[model]=', bist_temp['model'])
                    print('bist_temp[sn]=', bist_temp['sn'])
                    print('bist_temp[date]=', bist_temp['date'])

                    # store other fields
                    bist_temp['sis_version'] = sis_ver_found  # store SIS version
                    bist_temp['ship_name'] = self.ship_tb.text()  # store ship name
                    bist_temp['cruise_name'] = self.cruise_tb.text()  # store cruise name

                    # append dicts
                    # print('in parser, bist =', bist)
                    # print('in parser, bist_temp=', bist_temp)
                    bist = multibeam_tools.libs.read_bist.appendDict(bist, bist_temp)
                    bist_count += 1  # increment counter if no issues parsing or appending

                except ValueError:
                    self.update_log('***WARNING: Error appending ' + fname)
                    bist_fail_list.append(fname)

        if bist['filename']:  # try plotting only if at least one BIST was parsed successfully
            if len(bist_fail_list) > 0:
                self.update_log('The following BISTs will not be plotted:')
                for i in range(len(bist_fail_list)):
                    self.update_log('     ' + str(i + 1) + ". " + bist_fail_list[i])

            self.update_log('Plotting ' + str(bist_count) + ' ' + self.type_cbox.currentText() + ' BIST files...')

            if bist_test_type == self.bist_list[1]:  # TX Channels
                for ps in [1, 2]:  # loop through and plot both available styles of TX Z plots, then plot history
                    f_out = multibeam_tools.libs.read_bist.plot_tx_z(bist, plot_style=ps, output_dir=self.output_dir)
                self.update_log('Saved ' + str(len(f_out)) + ' ' + self.bist_list[1] + ' plot(s) in ' + self.output_dir)

                # plot TX Z history
                f_out = multibeam_tools.libs.read_bist.plot_tx_z_history(bist, output_dir=self.output_dir)
                if f_out:
                    self.update_log('Saved TX Z history plot ' + f_out + ' in ' + self.output_dir)
                else:
                    self.update_log('No TX Z history plot saved (check log for missing date/time warnings)')

            elif bist_test_type == self.bist_list[2]:  # RX Channels
                multibeam_tools.libs.read_bist.plot_rx_z(bist, save_figs=True, output_dir=self.output_dir)

                # if self.plot_rx_z_history.isChecked()
                    # include RX Z history plot
                multibeam_tools.libs.read_bist.plot_rx_z_annual(bist, save_figs=True, output_dir=self.output_dir)
                multibeam_tools.libs.read_bist.plot_rx_z_history(bist, save_figs=True, output_dir=self.output_dir)

            elif bist_test_type == self.bist_list[3]:  # RX Noise
                if rxn_test_type == 1:  # plot speed test
                    speed_list = []

                    if self.custom_speed_gb.isChecked():
                        # apply speed list from custom entries; assumes BISTs are loaded and selected in order of
                        # increasing speed corresponding to these custom speed params; there is no other way to check!
                        self.update_speed_info()
                        speed_list = np.repeat(self.speed_list, int(self.num_tests_tb.text()))
                        print('using custom speed list=', speed_list)

                    if len(set((bist['frequency'][0]))) == 1:  # single frequency detected, single plot
                        print('single frequency found in RX Noise test')
                        multibeam_tools.libs.read_bist.plot_rx_noise_speed(bist, save_figs=True,
                                                                           output_dir=self.output_dir,
                                                                           sort_by='speed',
                                                                           speed=speed_list,
                                                                           speed_unit=self.spd_unit_cbox.currentText())

                    else:  # multiple frequencies (e.g., SIS5 EM2040); split up RXN columns accordingly before plotting
                        print('multiple frequencies found in RX Noise test')
                        freq_list = bist['frequency'][0]  # freq list for each BIST; assume identical across all files
                        print('freq_list=', freq_list)
                        print('bist=', bist)

                        # loop through each frequency, reduce RXN data for each freq and call plotter for that subset
                        for f in range(len(freq_list)):
                            print('f=', f)
                            bist_freq = copy.deepcopy(bist)  # copy, pare down columns for each frequency
                            print('bist_freq=', bist_freq)
                            bist_freq['rxn'] = []
                            bist_freq['rxn_mean'] = []

                            for s in range(len(bist['speed'])):  # loop through all speeds, keep column of interest
                                print('s=', s)
                                rxn_array_z = [np.array(bist['rxn'][s][0][:, f])]  # array of RXN data for spd and freq
                                bist_freq['rxn'].append(rxn_array_z)  # store in frequency-specific BIST dict
                                bist_freq['frequency'] = [[freq_list[f]]]  # plotter expects list of freq

                            multibeam_tools.libs.read_bist.plot_rx_noise_speed(bist_freq, save_figs=True,
                                                                               output_dir=self.output_dir,
                                                                               sort_by='speed',
                                                                               speed=speed_list)

                elif rxn_test_type == 2:
                    print('RX Noise vs Heading plotter not available yet...')

            elif bist_test_type == self.bist_list[4]:  # RX Spectrum
                print('RX Spectrum parser and plotter are not available yet...')

        else:
            self.update_log('No BISTs to plot')

    def update_log(self, entry):  # update the activity log
        self.log.append(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' ' + entry)
        QtWidgets.QApplication.processEvents()

    def update_prog(self, total_prog):
        self.calc_pb.setValue(total_prog)
        QtWidgets.QApplication.processEvents()

    def update_speed_info(self):
        try:
            spd_min = float(self.spd_min_tb.text())
            spd_max = float(self.spd_max_tb.text())
            spd_int = float(self.spd_int_tb.text())
            spd_num = np.floor((spd_max-spd_min)/spd_int) + 1

            print('min, max, int, num=', spd_min, spd_max, spd_int, spd_num)
            self.speed_list = np.arange(0, spd_num)*spd_int + spd_min
            self.speed_list.round(decimals=1)

            print('speed_list=', self.speed_list)

            # print('num_speeds=', num_speeds)
            self.total_num_speeds_tb.setText(str(np.size(self.speed_list)))
            self.total_num_tests_tb.setText(str(int(spd_num*float(self.num_tests_tb.text()))))
            self.final_speeds_lbl.setText(self.final_speeds_hdr +
                                          np.array2string(self.speed_list, precision=1, separator=','))

        except:
            pass


class NewPopup(QtWidgets.QWidget):  # new class for additional plots
    def __init__(self):
        QtWidgets.QWidget.__init__(self)


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)

    main = MainWindow()
    main.show()

    sys.exit(app.exec_())
