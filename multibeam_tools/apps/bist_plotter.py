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

__version__ = "0.1.0"

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

        # list of available test types; RX Noise is only available vs. speed, not heading at present
        # RX Noise Spectrum is not available yet; update accordingly
        self.bist_list = ["N/A or non-BIST", "TX Channels Z", "RX Channels Z", "RX Noise Level", "RX Noise Spectrum"]

        # set up layouts of main window
        self.set_left_layout()
        self.set_right_layout()
        self.set_main_layout()

        # set up file control actions
        self.add_file_btn.clicked.connect(lambda: self.add_files('Kongsberg BIST .txt(*.txt)'))
        self.get_indir_btn.clicked.connect(self.get_input_dir)
        self.get_outdir_btn.clicked.connect(self.get_output_dir)
        self.rmv_file_btn.clicked.connect(self.remove_files)
        self.rmv_all_btn.clicked.connect(lambda: self.remove_files(remove_all=True))


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

    def set_right_layout(self):
        # set layout with file controls on right, sources on left, and progress log on bottom
        file_button_height = 20  # height of file control button
        file_button_width = 110  # width of file control button

        # add file control buttons and file list
        self.add_file_btn = QtWidgets.QPushButton('Add Files')
        self.add_file_btn.setToolTip('Add BIST .txt files')
        self.get_indir_btn = QtWidgets.QPushButton('Add Directory')
        self.get_indir_btn.setToolTip('Add a directory with BIST .txt files (non-BIST .txt files will be excluded)')
        self.get_outdir_btn = QtWidgets.QPushButton('Select Output Dir.')
        self.get_outdir_btn.setToolTip('Set the output directory (see current output directory below)')
        self.rmv_file_btn = QtWidgets.QPushButton('Remove Selected')
        self.rmv_file_btn.setToolTip('Remove selected files')
        self.rmv_all_btn = QtWidgets.QPushButton('Remove All Files')
        self.rmv_all_btn.setToolTip('Remove all files')

        # format file control buttons
        self.add_file_btn.setFixedSize(file_button_width, file_button_height)
        self.get_indir_btn.setFixedSize(file_button_width, file_button_height)
        self.get_outdir_btn.setFixedSize(file_button_width, file_button_height)
        self.rmv_file_btn.setFixedSize(file_button_width, file_button_height)
        self.rmv_all_btn.setFixedSize(file_button_width, file_button_height)

        # set the file control button layout
        file_btn_layout = QtWidgets.QVBoxLayout()
        file_btn_layout.addWidget(self.add_file_btn)
        file_btn_layout.addWidget(self.get_indir_btn)
        file_btn_layout.addWidget(self.get_outdir_btn)
        file_btn_layout.addWidget(self.rmv_file_btn)
        file_btn_layout.addWidget(self.rmv_all_btn)
        # file_btn_layout.addWidget(self.plot_bist_btn)
        # file_btn_layout.addWidget(self.custom_info_gb)
        # file_btn_layout.addStretch()

        # set the file control button groupbox
        self.file_control_gb = QtWidgets.QGroupBox('File Control')
        self.file_control_gb.setLayout(file_btn_layout)

        # set the BIST selection buttons
        self.type_cbox_lbl = QtWidgets.QLabel('Select BIST type:')
        self.type_cbox = QtWidgets.QComboBox()  # combo box with plot modes
        self.type_cbox.setFixedSize(file_button_width, file_button_height)
        # self.type_cbox.addItems(self.bist_list[1:])  # available BIST plot types
        self.type_cbox.addItems(self.bist_list[1:-1])  # available BIST plot types (exclude RX Spectrum for now)
        self.type_cbox.setToolTip('Select a BIST type for file verification and plotting')


        self.select_type_btn = QtWidgets.QPushButton('Select BISTs')  # button to select files based on BIST type
        self.select_type_btn.setToolTip('Filter and select source files by the chosen test type')
        self.clear_type_btn = QtWidgets.QPushButton('Clear Selected')  # button to select files based on BIST type
        self.clear_type_btn.setToolTip('Clear file selection')
        # self.verify_bist_btn = QtWidgets.QPushButton('Verify Selected')  # button to verify system info in BISTs
        # self.verify_bist_btn.setToolTip('Verify system info for selected files (required before plotting)')
        self.plot_bist_btn = QtWidgets.QPushButton('Plot Selected')
        self.plot_bist_btn.setToolTip('Plot selected, verified files (using current system information above,'
                                      ' if not available in BIST)')
        # self.plot_bist_btn.setEnabled(False)

        # format BIST options buttons
        self.select_type_btn.setFixedSize(file_button_width, file_button_height)
        self.clear_type_btn.setFixedSize(file_button_width, file_button_height)
        # self.verify_bist_btn.setFixedSize(file_button_width, file_button_height)
        self.plot_bist_btn.setFixedSize(file_button_width, file_button_height)

        # set the BIST options layout
        plot_btn_layout = QtWidgets.QVBoxLayout()
        plot_btn_layout.addWidget(self.type_cbox_lbl)
        plot_btn_layout.addWidget(self.type_cbox)
        plot_btn_layout.addWidget(self.select_type_btn)
        plot_btn_layout.addWidget(self.clear_type_btn)
        # plot_btn_layout.addWidget(self.verify_bist_btn)
        plot_btn_layout.addWidget(self.plot_bist_btn)
        # plot_btn_layout.addStretch()

        # set the BIST type control button groupbox
        self.plot_control_gb = QtWidgets.QGroupBox('BIST Options')
        self.plot_control_gb.setLayout(plot_btn_layout)
        # self.plot_control_gb.setFixedWidth(225)


        # set the custom info control buttons
        self.sys_info_lbl = QtWidgets.QLabel('Default: any info in BIST will be used;'
                                             '\nmissing fields require user input')

        self.warn_user_chk = QtWidgets.QCheckBox('Check selected files for missing\n' +
                                                 'or conflicting system info')
        self.warn_user_chk.setChecked(True)
        self.warn_user_chk.setObjectName('warn_user_chk')
        self.warn_user_chk.setToolTip('Turn off warnings only if system info is consistent for BIST(s) being processed')

        self.sys_info_lbl.setStyleSheet('font: 8pt')
        self.model_tb_lbl = QtWidgets.QLabel('Model:')
        self.model_tb_lbl.resize(100, 20)
        self.model_cbox = QtWidgets.QComboBox()  # combo box with color modes
        self.model_cbox.setFixedSize(100, 20)
        self.model_cbox.addItems(['EM 2040', 'EM 302', 'EM 304', 'EM 710', 'EM 712', 'EM 122', 'EM 124'])  # color modes
        self.model_cbox.setObjectName('model')
        self.model_cbox.setToolTip('Select the EM model (required)')
        model_info_layout = QtWidgets.QHBoxLayout()
        model_info_layout.addWidget(self.model_tb_lbl)
        model_info_layout.addWidget(self.model_cbox)

        self.sn_tb_lbl = QtWidgets.QLabel('Serial No.:')
        self.sn_tb_lbl.resize(100, 20)
        self.sn_tb = QtWidgets.QLineEdit()
        self.sn_tb.setFixedSize(100, 20)
        self.sn_tb.setText('999')
        self.sn_tb.setObjectName('sn')
        self.sn_tb.setToolTip('Enter the serial number (required)')
        sn_info_layout = QtWidgets.QHBoxLayout()
        sn_info_layout.addWidget(self.sn_tb_lbl)
        sn_info_layout.addWidget(self.sn_tb)

        self.ship_tb_lbl = QtWidgets.QLabel('Ship Name:')
        self.ship_tb_lbl.resize(100, 20)
        self.ship_tb = QtWidgets.QLineEdit()
        self.ship_tb.setFixedSize(100, 20)
        self.ship_tb.setText('R/V Unsinkable II')
        self.ship_tb.setObjectName('ship')
        self.ship_tb.setToolTip('Enter the ship name (optional)')
        ship_info_layout = QtWidgets.QHBoxLayout()
        ship_info_layout.addWidget(self.ship_tb_lbl)
        ship_info_layout.addWidget(self.ship_tb)

        self.cruise_tb_lbl = QtWidgets.QLabel('Cruise Name:')
        self.cruise_tb_lbl.resize(100, 20)
        self.cruise_tb = QtWidgets.QLineEdit()
        self.cruise_tb.setFixedSize(100, 20)
        self.cruise_tb.setText('A 3-hour tour')
        self.cruise_tb.setObjectName('cruise_name')
        self.cruise_tb.setToolTip('Enter the cruise name (optional)')
        cruise_info_layout = QtWidgets.QHBoxLayout()
        cruise_info_layout.addWidget(self.cruise_tb_lbl)
        cruise_info_layout.addWidget(self.cruise_tb)

        self.date_tb_lbl = QtWidgets.QLabel('Date (yyyy/mm/dd):')
        self.date_tb_lbl.resize(115, 20)
        self.date_tb = QtWidgets.QLineEdit()
        self.date_tb.setFixedSize(75, 20)
        self.date_tb.setText('yyyy/mm/dd')
        self.date_tb.setObjectName('date')
        self.date_tb.setToolTip('Enter the date (required; BISTs over multiple days'
                                ' will use dates in files, if available)')
        date_info_layout = QtWidgets.QHBoxLayout()
        date_info_layout.addWidget(self.date_tb_lbl)
        date_info_layout.addWidget(self.date_tb)

        # set the custom info button layout
        custom_info_layout = QtWidgets.QVBoxLayout()
        custom_info_layout.addWidget(self.sys_info_lbl)
        custom_info_layout.addLayout(model_info_layout)
        custom_info_layout.addLayout(sn_info_layout)
        custom_info_layout.addLayout(ship_info_layout)
        custom_info_layout.addLayout(cruise_info_layout)
        custom_info_layout.addLayout(date_info_layout)
        custom_info_layout.addWidget(self.warn_user_chk)

        # set the custom info groupbox
        self.custom_info_gb = QtWidgets.QGroupBox('System Information')
        self.custom_info_gb.setLayout(custom_info_layout)
        self.custom_info_gb.setFixedWidth(200)

        # self.custom_info_gb.setSizePolicy(QtWidgets.QSizePolicy.Minimum,
        #                                   QtWidgets.QSizePolicy.Minimum)
        # add checkbox and set layout
        # self.custom_info_chk = QtWidgets.QCheckBox('Use custom system information\n(default: parsed if available)')
        # system_info_layout = QtWidgets.QVBoxLayout()
        # system_info_layout.addWidget(self.custom_info_chk)
        # system_info_layout.addWidget(self.custom_info_gb)

        # self.system_info_gb = QtWidgets.QGroupBox('System Information')
        # self.system_info_gb.setLayout(system_info_layout)


        # stack file_control_gb and plot_control_gb
        self.right_layout = QtWidgets.QVBoxLayout()
        self.right_layout.addWidget(self.custom_info_gb)
        self.right_layout.addWidget(self.file_control_gb)
        self.right_layout.addWidget(self.plot_control_gb)
        # self.right_layout.addWidget(self.system_info_gb)
        self.right_layout.addStretch()


    def set_left_layout(self):
        # add table showing selected files
        self.file_list = QtWidgets.QListWidget()
        # self.file_list.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding,
        #                              QtWidgets.QSizePolicy.MinimumExpanding)
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

        # self.file_layout = QtWidgets.QHBoxLayout()
        # self.file_layout.addWidget(self.file_list_gb)
        # self.file_layout.addWidget(self.file_control_gb)
        # self.file_layout.addLayout(self.right_layout)

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
        # self.log_gb.setFixedWidth(800)
        self.log_gb.setMinimumWidth(550)

        # set the left panel layout with file controls on top and log on bottom
        self.left_layout = QtWidgets.QVBoxLayout()
        # left_layout.addLayout(self.file_layout)  # add file list group box
        self.left_layout.addWidget(self.file_list_gb)
        self.left_layout.addWidget(self.log_gb)  # add log group box
        # self.mainWidget.setLayout(left_layout)

    def set_main_layout(self):  # set the main layout with file controls on left and swath figure on right
        main_layout = QtWidgets.QHBoxLayout()
        main_layout.addLayout(self.left_layout)
        main_layout.addLayout(self.right_layout)
        self.mainWidget.setLayout(main_layout)


    def add_files(self, ftype_filter, input_dir='HOME'):  # add all files of specified type in directory
        if input_dir == 'HOME':  # select files manually if input_dir not specified as optional argument
            fnames = QtWidgets.QFileDialog.getOpenFileNames(self, 'Open files...', os.getenv('HOME'), ftype_filter)
            fnames = fnames[0]  # keep only the filenames in first list item returned from getOpenFileNames

        else:  # get all files satisfying ftype_filter in input_dir
            fnames = []
            for f in os.listdir(input_dir):  # step through all files in this directory
                if os.path.isfile(os.path.join(input_dir, f)):  # verify it's a file
                    if os.path.splitext(f)[1] == ftype_filter:  # verify ftype_filter extension
                        fnames.append(os.path.join(input_dir, f))  # add whole path, same convention as getOpenFileNames

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
                self.file_list.addItem(fnames_new[f])
                bist_types_found = [self.bist_list[idx_found] for idx_found in bist_type]
                self.update_log('Added ' + fnames_new[f].split('/')[-1] +
                                ' (SIS ' + str(sis_ver_found) + ': ' +
                                ', '.join(bist_types_found) + ')')

            else:  # skip non-verified BIST types
                self.update_log('Skipping ' + fnames_new[f].split('/')[-1] + ' (' + self.bist_list[0] + ')')

        self.get_current_file_list()  # update self.file_list and file count
        self.current_fnum_lbl.setText('Current file count: ' + str(len(self.filenames)))


    def remove_files(self, remove_all=False):  # remove selected files

        if remove_all is True:  # remove all files
            self.file_list.clear()  # clear the file list display
            self.filenames = []  # clear filenames
            self.calc_pb.setValue(0)

        self.get_current_file_list()  # get updated current list (will be empty if all removed)
        selected_files = self.file_list.selectedItems()
        fnames_all = [f for f in self.filenames if '.txt' in f]

        if len(fnames_all) == 0:  # all files have been removed
            self.update_log('All files have been removed.')

        elif not selected_files:  # files exist but nothing is selected
            self.update_log('No files selected for removal.')
            return

        else:  # remove only the files that have been selected
            for f in selected_files:
                fname = f.text().split('/')[-1]
                self.file_list.takeItem(self.file_list.row(f))
                self.update_log('Removed ' + fname)

        self.get_current_file_list()  # update self.file_list and file count

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

    def get_input_dir(self):
        try:
            self.input_dir = QtWidgets.QFileDialog.getExistingDirectory(self, 'Add directory', os.getenv('HOME'))
            self.update_log('Added directory: ' + self.input_dir)

            # get a list of all .txt files in that directory, '/' avoids '\\' in os.path.join in add_files
            self.update_log('Adding files in directory: ' + self.input_dir)
            self.add_files(ftype_filter='.txt', input_dir=self.input_dir+'/')

        except ValueError:
            self.update_log('No input directory selected.')
            self.input_dir = ''
            pass

    def get_current_file_list(self):  # get current list of files in qlistwidget
        list_items = []
        for f in range(self.file_list.count()):
            list_items.append(self.file_list.item(f))

        self.filenames = [f.text() for f in list_items]  # convert to text
        self.current_fnum_lbl.setText('Current file count: ' + str(len(self.filenames)))


    def get_new_file_list(self, fext='', flist_old=None):
        # determine list of new files with file extension fext that do not exist in flist_old
        # flist_old may contain paths as well as file names; compare only file names
        if flist_old is None:
            flist_old = list()

        self.get_current_file_list()
        fnames_ext = [f for f in self.filenames if fext in f]  # file names (with paths) that match the extension
        fnames_old = [f.split('/')[-1] for f in flist_old]  # file names only (no paths) from flist_old
        fnames_new = [fn for fn in fnames_ext if
                      fn.split('/')[-1] not in fnames_old]  # check if file name (without path) exists in fnames_old
        return fnames_new  # return the fnames_new (with paths)


    def select_bist(self):
        # verify BIST types in current file list and select those matching current BIST type in combo box
        self.clear_bist()  # update file list and clear all selections before re-selecting those of desired BIST type
        bist_count = 0  # count total selected files

        for f in range(len(self.filenames)):  # loop through file list and select if matches BIST type in combo box
            bist_type, sis_ver_found = multibeam_tools.libs.read_bist.verify_bist_type(self.file_list.item(f).text())

            # check whether selected test index from combo box  is available in this file
            if int(self.type_cbox.currentIndex()+1) in bist_type:  # currentIndex+1 because bist_list starts at 0 = N/A
                self.file_list.item(f).setSelected(True)
                bist_count = bist_count+1

        if bist_count == 0:  # update log with selection total
            self.update_log('No ' + self.type_cbox.currentText() + ' files available for selection')

        else:
            self.update_log('Selected ' + str(bist_count) + ' ' + self.type_cbox.currentText() + ' files')

        if self.warn_user_chk.isChecked():  # if desired, check the system info in selected files
            self.verify_system_info()
        # else:


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

        # enable the plot button if there are no missing fields or the warn user button not checked
        # if not self.missing_fields or not self.warn_user_chk.isChecked():
        #     self.plot_bist_btn.setEnabled(True)

        # print('now the current list is', self.missing_fields)

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
        fnames_sel = [self.file_list.item(f).text() for f in range(self.file_list.count())
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
            # self.update_log('Verifying ' + fname_str)

            # get SIS version for later use in parsers, store in BIST dict (BIST type verified at file selection)
            _, sis_ver_found = multibeam_tools.libs.read_bist.verify_bist_type(fname)  # get SIS ver for RX Noise parser

            # get available system info in this file
            sys_info = multibeam_tools.libs.read_bist.check_system_info(fname, sis_version=sis_ver_found)

            # print('sys_info =', sys_info)

            # update user entry fields to any info available in BIST, store conflicting fields if different
            if sys_info['model']:
                if not self.model_updated:  # update model with first model found
                    self.model_cbox.setCurrentIndex(self.model_cbox.findText('EM '+sys_info['model']))
                    self.update_log('Updated model to ' + self.model_cbox.currentText() + ' (first model found)')
                    self.model_updated = True

                elif 'EM ' + sys_info['model'] != self.model_cbox.currentText():  # model was updated but new model found
                    self.update_log('***WARNING: New model (EM ' + sys_info['model'] + ') detected in ' + fname_str)
                    self.conflicting_fields.append('model')

            if sys_info['sn']:
                if not self.sn_updated:  # update serial number with first SN found
                    self.sn_tb.setText(sys_info['sn'])
                    self.update_log('Updated serial number to ' + self.sn_tb.text() + ' (first S/N found)')
                    self.sn_updated = True

                elif sys_info['sn'] != self.sn_tb.text().strip():  # serial number was updated but new SN found
                    self.update_log('***WARNING: New serial number (' + sys_info['sn'] + ') detected in' + fname_str)
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

        # print('missing fields are now:', self.missing_fields)
        # print('conflicting fields are now:', self.conflicting_fields)

        # if self.missing_fields or self.conflicting_fields:  # disable plot button if any fields are missing/conflicting
            # self.plot_bist_btn.setEnabled(False)

        # self.update_sys_info_colors()
        # for widget in [self.model_cbox, self.sn_tb, self.date_tb]:  # set text to red for all missing fields
        #     if widget.objectName() in self.missing_fields + self.conflicting_fields:
        #         widget.setStyleSheet('color: red')

        # print('sys_info return =', sys_info)
        # self.missing_fields = [k for k in ['model', 'sn', 'date'] if not sys_info[k]]

        # if self.missing_fields or self.conflicting_fields:
        self.update_sys_info_colors()
        if self.warn_user_chk.isChecked() and any(self.missing_fields or self.conflicting_fields):
            user_warning = QtWidgets.QMessageBox.question(self, 'System info check',
                'Red field(s) are either:\n\n' +
                '          1) not available from the selected BIST(s), or\n' +
                '          2) available but conflicting across selected BISTs\n\n' +
                'Please confirm these fields or update file selection before plotting.\n' +
                '(The plot button will be enabled after all red fields are confirmed.)', QtWidgets.QMessageBox.Ok)

    # def warn_user_system_info(self):  # if info is available in BIST, confirm it matches user input and warn if not

    def update_sys_info_colors(self):  # update the user field colors to red/black based on missing/conflicting info
        for widget in [self.model_cbox, self.sn_tb, self.date_tb]:  # set text to red for all missing fields
            widget.setStyleSheet('color: black')  # reset field to black before checking missing/conflicting fields
            if widget.objectName() in self.missing_fields + self.conflicting_fields:
                widget.setStyleSheet('color: red')

    def plot_bist(self):
        # get list of selected files and send each to the appropriate plotter
        bist_test_type = self.type_cbox.currentText()
        self.update_log('Plotting selected ' + bist_test_type + ' BIST files')
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

        # if bist_list_index > 0:
        bist = multibeam_tools.libs.read_bist.init_bist_dict(bist_list_index)

        fnames_sel = [self.file_list.item(f).text() for f in range(self.file_list.count())
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
            # print('sys_info return =', sys_info)

            try:  # try parsing the files according to BIST type
                if bist_test_type == self.bist_list[1]:  # TX Channels
                    # bist_temp = multibeam_tools.libs.read_bist.parse_tx_z(fname)
                    bist_temp = multibeam_tools.libs.read_bist.parse_tx_z(fname, sis_version=sis_ver_found)

                elif bist_test_type == self.bist_list[2]:  # RX Channels

                    # check model and skip EM2040 variants (model combobox is updated during verification step,
                    # so this can be checked even if model is not available in sys_info)
                    # print('sys info model is', sys_info['model'],' with type', type(sys_info['model']))
                    # print('current selected model is', self.model_cbox.currentText())
                    # if sys_info['model'].find('2040') > -1:
                    if self.model_cbox.currentText().find('2040') > -1: # skip 2040 (FUTURE: RX Channels for all freq)
                        self.update_log('RX Channels plot N/A for EM2040: ' + fname)
                        bist_fail_list.append(fname)
                        continue
                    else:
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
                                temp_speed = float(fname.rsplit("_")[-2].replace("p", ".").strip())
                                # bist_temp['speed'] = float(fname.rsplit("_")[-2].replace("p", ".").strip())
                                bist_temp['speed'] = temp_speed

                                # testing to assign one speed per test rather than one speed per file
                                bist_temp['speed_bist'] = [temp_speed for i in range(len(bist_temp['test']))]
                                print('bist_temp[speed_bist] =', bist_temp['speed_bist'])
                            except ValueError:
                                self.update_log('***WARNING: Error parsing speeds from filenames; check formats!')
                                self.update_log('***SIS v4 RX Noise file names must include speed, .e.g., "_6_kts.txt" or "_9p5_kts.txt"')
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
                continue  # do not try to append

            else:  # try to append data if no exception during parsing
                # print('no exceptions during parsing, checking bist_temp for file', fname_str)
                try:
                    # add user fields if not parsed from BIST file (availability depends on model and SIS ver)
                    # this can be made more elegant once all modes are working
                    if bist_temp['frequency'] == []:  # add freq if not parsed (e.g., most SIS 4 BISTs)
                        bist_temp['frequency'] = [freq]  # add nominal freq for each file in case order changes

                    if bist_temp['date'] == []:  # add user date if not parsed (incl. in SIS 5, but not SIS 4)
                        bist_temp['date'] = self.date_str

                    if bist_temp['model'] == []:  # add model

                        bist_temp['model'] = self.model_number

                    if bist_temp['sn'] == []:  # add serial number
                        bist_temp['sn'] = self.sn

                    # print('bist_temp[frequency]=', bist_temp['frequency'])
                    # print('bist_temp[model]=', bist_temp['model'])
                    # print('bist_temp[sn]=', bist_temp['sn'])
                    # print('bist_temp[date]=', bist_temp['date'])

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

            # else:
            #     self.update_log('***WARNING: No data parsed for ' + fname)
            #     bist_fail_list.append(fname)
            #     continue

        if bist['filename']:  # try plotting only if at least one BIST was parsed successfully

            if len(bist_fail_list) > 0:
                self.update_log('The following BISTs will not be plotted:')
                for i in range(len(bist_fail_list)):
                    self.update_log('     ' + str(i + 1) + ". " + bist_fail_list[i])

            self.update_log('Plotting ' + str(bist_count) + ' ' + self.type_cbox.currentText() + ' BIST files...')

            if bist_test_type == self.bist_list[1]:  # TX Channels
                figs_out = multibeam_tools.libs.read_bist.plot_tx_z(bist, plot_style=1, output_dir=self.output_dir)
                self.update_log('Saved ' + str(len(figs_out)) + ' ' + self.bist_list[1] + ' plots in ' + self.output_dir)

            elif bist_test_type == self.bist_list[2]:  # RX Channels
                multibeam_tools.libs.read_bist.plot_rx_z(bist, save_figs=True, output_dir=self.output_dir)
                # print('RX Channels plotter not available yet...')

            elif bist_test_type == self.bist_list[3]:  # RX Noise
                if rxn_test_type == 1:  # plot speed test
                    if len(set((bist['frequency'][0]))) == 1:  # single frequency detected, single plot
                        multibeam_tools.libs.read_bist.plot_rx_noise_speed(bist, save_figs=True,
                                                                           output_dir=self.output_dir)

                    else:  # multiple frequencies (e.g., SIS5 EM2040); split up RXN columns accordingly before plotting
                        freq_list = bist['frequency'][0]  # freq list for each BIST; assume identical across all files

                        # loop through each frequency, reduce RXN data for each freq and call plotter for that subset
                        for f in range(len(freq_list)):
                            bist_freq = copy.deepcopy(bist)  # copy, pare down columns for each frequency
                            bist_freq['RXN'] = []
                            bist_freq['RXN_mean'] = []

                            for s in range(len(bist['speed'])):  # loop through all speeds, keep column of interest
                                rxn_array_z = [np.array(bist['RXN'][s][0][:, f])]  # array of RXN data for spd and freq
                                bist_freq['RXN'].append(rxn_array_z)  # store in frequency-specific BIST dict
                                bist_freq['frequency'] = [[freq_list[f]]]  # plotter expects list of freq

                            multibeam_tools.libs.read_bist.plot_rx_noise_speed(bist_freq, save_figs=True,
                                                                               output_dir=self.output_dir)

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


class NewPopup(QtWidgets.QWidget):  # new class for additional plots
    def __init__(self):
        QtWidgets.QWidget.__init__(self)


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)

    main = MainWindow()
    main.show()

    sys.exit(app.exec_())
