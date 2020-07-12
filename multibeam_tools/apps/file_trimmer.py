# -*- coding: utf-8 -*-
"""

Multibeam Echosounder Assessment Toolkit: Kongsberg .all file trimmer

Generate trimmed .all files with only the datagrams required for processing (in QPS Qimera, at present)
File size reduction is intended to improve data transfer to shore for remote support; not intended for compression of
data sets for routine processing and/or archiving purposes
File size reduction ratio will depend on presence of unnecessary datagrams in original .all files

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
import datetime
import os
import struct
import sys

# add path to external module common_data_readers for pyinstaller
sys.path.append('C:\\Users\\kjerram\\Documents\\GitHub')

from common_data_readers.python.kongsberg.kmall import kmall



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


class MainWindow(QtWidgets.QMainWindow):
    media_path = os.path.join(os.path.dirname(__file__), "media")

    def __init__(self, parent=None):
        super(MainWindow, self).__init__()

        # set up main window
        self.mainWidget = QtWidgets.QWidget(self)
        self.setCentralWidget(self.mainWidget)
        self.setMinimumWidth(800)
        self.setMinimumHeight(500)
        self.setWindowTitle('File Trimmer v.%s' % __version__)
        self.setWindowIcon(QtGui.QIcon(os.path.join(self.media_path, "icon.png")))

        if os.name == 'nt':  # necessary to explicitly set taskbar icon
            import ctypes
            current_app_id = 'MAC.FileTrimmer.' + __version__  # arbitrary string
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(current_app_id)

        # initialize other necessities
        self.filenames = ['']
        self.input_dir = ''
        self.output_dir = ''
        self.output_dir_old = ''
        self.fname_suffix_default = 'trimmed'
        self.fsize_all_orig = 0
        self.fsize_all_trim = 0
        self.fcount_trimmed = 0
        self.fcount_skipped = 0

        # set up dict of processing paths for options list
        self.proc_list = {'QPS Qimera': 'qimera', 'Caris HIPS/SIPS': 'caris', 'MB System': 'mb_system'}

        self.proc_path = 'qimera'

        # set of datagrams required from each file type for different processing paths
        self.dg_ID = {}

        # .all datagram types required for each processing path (numbers are datagram IDs assigned by Kongsberg)
        self.dg_ID['all'] = {'qimera': {65: 'ATT', 68: 'DEPTH', 71: 'SSS', 72: 'HDG', 73: 'IP START', 78: 'RRA_78',
                                        80: 'POS', 82: 'RTP', 85: 'SSP', 88: 'XYZ_88', 105: 'IP STOP'}}

        # .kmall datagram types required for each processing path (numbers are arbitrary, just keeping same dict format)
        ##### NOTE THIS IS PRELIMINARY FOR TESTING!!! ###
        self.dg_ID['kmall'] = {'qimera': {1: 'IIP', 2: 'IOP', 3: 'SPO', 4: 'SKM', 5: 'SVP', 6: 'SVT', 7: 'SCL',
                                          8: 'SDE', 9: 'SHI', 10: 'SHA', 11: 'MRZ', 12: 'MWC', 13: 'CPO', 14: 'MSC'}}

        # set up layouts of main window
        # self.set_top_layout()
        self.set_main_layout()
        self.update_suffix()

        # self.dg_ID_all = {65: 'ATT',
        #                   68: 'DEPTH',
        #                   71: 'SSS',
        #                   72: 'HDG',
        #                   73: 'IP START',
        #                   78: 'RRA_78',
        #                   80: 'POS',
        #                   82: 'RTP',
        #                   85: 'SSP',
        #                   88: 'XYZ_88',
        #                   105: 'IP STOP'}
        # 49:'PU',
        # 66:'BIST',
        # 67:'CLOCK',
        # 83:'SEABED_IMAGE_83',
        # 89:'SEABED_IMAGE_89',
        # 102:'RRA_102',
        # 107:'WATERCOLUMN',
        # 110:'ATT_VEL'}

        # set up file control actions
        self.add_file_btn.clicked.connect(lambda: self.add_files('Kongsberg (*.all *.kmall)'))
        self.get_indir_btn.clicked.connect(self.get_input_dir)
        self.rmv_file_btn.clicked.connect(self.remove_files)
        self.clr_file_btn.clicked.connect(self.clear_files)
        self.get_outdir_btn.clicked.connect(self.get_output_dir)
        self.trim_file_btn.clicked.connect(self.trim_files)
        self.advanced_options_gb.clicked.connect(self.update_suffix)
        self.fname_suffix_tb.textChanged.connect(self.update_suffix)
        self.show_path_chk.stateChanged.connect(self.show_file_paths)
        self.overwrite_chk.stateChanged.connect(self.check_output_options)
        self.raw_fname_chk.stateChanged.connect(self.check_output_options)


    def set_main_layout(self):
        # set layout with file controls on right, sources on left, and progress log on bottom
        btnh = 20  # height of file control button
        btnw = 100  # width of file control button

        # add file control buttons
        self.add_file_btn = PushButton('Add Files', btnw, btnh, 'add_file_btn', 'Add files', self)
        self.get_indir_btn = PushButton('Add Directory', btnw, btnh, 'get_indir_btn', 'Add a directory', self)
        self.get_outdir_btn = PushButton('Select Output Dir.', btnw, btnh, 'get_outdir_btn',
                                         'Select the output directory (see current directory below)', self)
        self.rmv_file_btn = PushButton('Remove Selected', btnw, btnh, 'rmv_file_btn', 'Remove selected files', self)
        self.clr_file_btn = PushButton('Remove All Files', btnw, btnh, 'clr_file_btn', 'Remove all files', self)
        self.trim_file_btn = PushButton('Trim Files', btnw, btnh, 'trim_file_btn', 'Trim files in source list', self)
        self.show_path_chk = CheckBox('Show file paths', False, 'show_paths_chk')

        self.overwrite_chk = CheckBox('Overwrite existing files', False, 'overwrite_chk',
                                      'Overwrite existing files in the output directory.'
                                      '\n\nThis can be useful if files were inadvertantly trimmed before completion '
                                      'and updated versions need to be created with the same name.'
                                      '\n\nPLEASE READ BEFORE PROCEEDING:'
                                      '\n\nBy default (unchecked), files are skipped if the same filename exists in '
                                      'the output directory.'
                                      '\n\nThe user can elect to overwrite existing files with the same name in the '
                                      'output directory OR keep the source filename (no suffix), but not both.'
                                      '\n\nAdditionally, files are always skipped if the source directory matches the '
                                      'output directory. These steps are taken to add an extra layer of protection for '
                                      'the original data.'
                                      '\n\nWARNING: IT US UP TO THE USER TO ENSURE ORIGINAL FILES ARE NOT OVERWRITTEN!')

        self.raw_fname_chk = CheckBox('Keep source filename', False, 'raw_filename_chk',
                                      'Keep the source filename (with no suffix).'
                                      '\n\nThis can be useful if the processing project requires trimmed filenames '
                                      'that match the original files, allowing the project file references to be '
                                      'updated to the original files in the future (e.g., after the full cruise '
                                      'data package is downloaded on shore).'
                                      '\n\nPLEASE READ BEFORE PROCEEDING:'
                                      '\n\nBy default (unchecked), trimmed files require a suffix to distinguish '
                                      'from the original files.'
                                      '\n\nThe user can elect to keep the source file name OR overwrite existing files '
                                      'with the same name in the output directory, but not both.'
                                      '\n\nAdditionally, files are always skipped if the source directory matches '
                                      'the output directory. These steps are taken to add an extra layer of '
                                      'protection for the original data.'
                                      '\n\nWARNING: IT US UP TO THE USER TO ENSURE ORIGINAL FILES ARE NOT OVERWRITTEN!')

        # set up custom file suffix options
        custom_info_lbl = QtWidgets.QLabel('(alphanumeric, -, and _ only;\nno file extensions or padding)')
        fname_suffix_tb_lbl = QtWidgets.QLabel('Suffix:')
        self.fname_suffix_tb = QtWidgets.QLineEdit(self.fname_suffix_default)
        self.fname_suffix_tb.setFixedHeight(20)
        self.fname_suffix_tb.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding,
                                           QtWidgets.QSizePolicy.MinimumExpanding)
        self.fname_suffix_tb.setEnabled(True)
        self.fname_suffix_final_header = 'Output: '
        self.fname_suffix_final_lbl = QtWidgets.QLabel(self.fname_suffix_final_header)

        fname_suffix_layout = QtWidgets.QHBoxLayout()
        fname_suffix_layout.addWidget(fname_suffix_tb_lbl)
        fname_suffix_layout.addWidget(self.fname_suffix_tb)

        custom_info_layout = QtWidgets.QVBoxLayout()
        custom_info_layout.addWidget(custom_info_lbl)
        custom_info_layout.addLayout(fname_suffix_layout)
        custom_info_layout.addWidget(self.fname_suffix_final_lbl)

        advanced_options_layout = QtWidgets.QVBoxLayout()
        advanced_options_layout.addLayout(custom_info_layout)
        advanced_options_layout.addWidget(self.raw_fname_chk)
        advanced_options_layout.addWidget(self.overwrite_chk)

        self.advanced_options_gb = QtWidgets.QGroupBox('Advanced output options')
        self.advanced_options_gb.setLayout(advanced_options_layout)
        self.advanced_options_gb.setCheckable(True)
        self.advanced_options_gb.setChecked(False)
        self.advanced_options_gb.setSizePolicy(QtWidgets.QSizePolicy.Maximum,
                                               QtWidgets.QSizePolicy.Maximum)

        # set the file control button layout
        file_btn_layout = QtWidgets.QVBoxLayout()
        file_btn_layout.addWidget(self.add_file_btn)
        file_btn_layout.addWidget(self.get_indir_btn)
        file_btn_layout.addWidget(self.get_outdir_btn)
        file_btn_layout.addWidget(self.rmv_file_btn)
        file_btn_layout.addWidget(self.clr_file_btn)
        file_btn_layout.addWidget(self.trim_file_btn)
        file_btn_layout.addWidget(self.show_path_chk)
        file_btn_layout.addWidget(self.advanced_options_gb)
        file_btn_layout.addStretch()

        # disable trim button until output directory is selected
        self.trim_file_btn.setEnabled(False)

        # set the file control button groupbox
        self.file_control_gb = QtWidgets.QGroupBox('File Control')
        self.file_control_gb.setLayout(file_btn_layout)

        # add table showing selected files
        self.file_list = QtWidgets.QListWidget()
        self.file_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.file_list.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.MinimumExpanding)
        self.file_list.setIconSize(QSize(0, 0))  # set icon size to 0,0 or file names (from item.data) will be indented

        # set layout of file list
        self.file_list_layout = QtWidgets.QVBoxLayout()
        self.file_list_layout.addWidget(self.file_list)

        # set file list group box
        self.file_list_gb = QtWidgets.QGroupBox('Sources')
        self.file_list_gb.setLayout(self.file_list_layout)

        self.file_layout = QtWidgets.QHBoxLayout()
        self.file_layout.addWidget(self.file_list_gb)
        self.file_layout.addWidget(self.file_control_gb)

        # add activity log widget
        self.log = QtWidgets.QTextEdit()
        self.log.setSizePolicy(QtWidgets.QSizePolicy.Minimum,
                               QtWidgets.QSizePolicy.Minimum)
        self.log.setStyleSheet("background-color: lightgray")
        self.log.setReadOnly(True)
        self.update_log('*** New .all file trimming log ***')

        # add progress bar for total file list
        self.current_outdir_lbl = QtWidgets.QLabel('Current output directory:')
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
        self.prog_layout.addWidget(self.current_outdir_lbl)
        self.prog_layout.addLayout(self.calc_pb_layout)

        # set the log layout
        self.log_layout = QtWidgets.QVBoxLayout()
        self.log_layout.addWidget(self.log)
        self.log_layout.addLayout(self.prog_layout)

        # set the log group box widget with log layout
        self.log_gb = QtWidgets.QGroupBox('Activity Log')
        self.log_gb.setLayout(self.log_layout)
        self.log_gb.setMinimumWidth(800)

        # set the left panel layout with file controls on top and log on bottom
        main_layout = QtWidgets.QVBoxLayout()
        main_layout.addLayout(self.file_layout)  # add file list group box
        main_layout.addWidget(self.log_gb)  # add log group box
        self.mainWidget.setLayout(main_layout)

    def add_files(self, ftype_filter, input_dir='HOME'):
        # select files with desired type, add to list box
        if input_dir == 'HOME':  # select files manually if input_dir not specified as optional argument
            fnames = QtWidgets.QFileDialog.getOpenFileNames(self, 'Open files...', os.getenv('HOME'), ftype_filter)
            fnames = fnames[0]  # keep only the filenames in first list item returned from getOpenFileNames

        else:  # get all files satisfying ftype_filter in input_dir
            fnames = []
            for f in os.listdir(input_dir):  # step through all files in this directory
                if os.path.isfile(os.path.join(input_dir, f)):  # verify it's a file
                    if os.path.splitext(f)[1] in ftype_filter:  # verify ftype_filter extension
                        fnames.append(os.path.join(input_dir, f))  # add whole path, same convention as getOpenFileNames

        self.get_current_file_list()  # get updated file list and add selected files only if not already listed
        fnames_new = [fn for fn in fnames if fn not in self.filenames]
        fnames_skip = [fs for fs in fnames if fs in self.filenames]

        if len(fnames_skip) > 0:  # skip any files already added, update log
            self.update_log('Skipping ' + str(len(fnames_skip)) + ' file(s) already added')

        for f in range(len(fnames_new)):  # add the new files only
            # add item with full file path data, set text according to show/hide path button
            [path, fname] = fnames_new[f].rsplit('/', 1)
            if fname.rsplit('.', 1)[0]:  # add file only if name exists prior to extension (may slip through splitext check if adding directory)
                new_item = QtWidgets.QListWidgetItem()
                new_item.setData(1, fnames_new[f])  # set full file path as data, role 1
                new_item.setText((path+'/')*int(self.show_path_chk.isChecked()) + fname)  # set text, show or hide path
                self.file_list.addItem(new_item)
                self.update_log('Added ' + fname)  #fnames_new[f].rsplit('/',1)[-1])
            else:
                self.update_log('Skipping empty filename ' + fname)

        if fnames_new:
            self.update_log('Finished adding ' + str(len(fnames_new)) + ' new file' +
                            ('s' if len(fnames_new) > 1 else ''))

            if self.output_dir:  # if output directory is selected, reenable trim button after files are loaded
                self.trim_file_btn.setEnabled(True)

    def show_file_paths(self):
        # show or hide path for all items in file_list according to show_paths_chk selection
        for i in range(self.file_list.count()):
            [path, fname] = self.file_list.item(i).data(1).rsplit('/', 1)  # split full file path from item data, role 1
            self.file_list.item(i).setText((path+'/')*int(self.show_path_chk.isChecked()) + fname)

    def get_input_dir(self):
        # get directory of files to load
        try:
            self.input_dir = QtWidgets.QFileDialog.getExistingDirectory(self, 'Add directory',
                                                                        os.getenv('HOME'))
            self.update_log('Added directory: ' + self.input_dir)

            # get a list of all .txt files in that directory, '/' avoids '\\' in os.path.join in add_files
            self.update_log('Adding files in directory: ' + self.input_dir)
            self.add_files(['.all', '.kmall'], input_dir=self.input_dir + '/')

        except:
            self.update_log('No input directory selected.')
            self.input_dir = ''
            pass

    def get_output_dir(self):
        # get output directory
        try:
            self.output_dir_old = self.output_dir
            self.output_dir = QtWidgets.QFileDialog.getExistingDirectory(self, 'Select output directory',
                                                                         os.getenv('HOME'))

            if self.output_dir:  # update user and enable trim button if successful
                self.update_log('Selected output directory: ' + self.output_dir)
                self.current_outdir_lbl.setText('Current output directory: ' + self.output_dir)
                self.trim_file_btn.setEnabled(True)

            elif not self.output_dir_old:  # warn user if not selected but keep trim button enabled and old output dir
                self.update_log('No output directory selected')

        except:
            # warn user if failed and disable trim button until output directory is selected
            self.update_log('Failure selecting output directory')
            self.output_dir = ''
            self.trim_file_btn.setEnabled(False)
            pass

    def remove_files(self, clear_all=False):  # remove selected files
        self.get_current_file_list()
        selected_files = self.file_list.selectedItems()

        if clear_all:  # clear all
            self.file_list.clear()
            self.filenames = []

        elif self.filenames and not selected_files:  # files exist but nothing is selected
            self.update_log('No files selected for removal.')
            return

        else:  # remove only the files that have been selected
            for f in selected_files:
                fname = f.text().split('/')[-1]
                self.file_list.takeItem(self.file_list.row(f))
                self.update_log('Removed ' + fname)

        # update log if all files removed
        self.get_current_file_list()
        fnames_all = [f for f in self.filenames if '.all' in f]
        fnames_kmall = [f for f in self.filenames if '.kmall' in f]

        if len(fnames_all + fnames_kmall) == 0:
            self.trim_file_btn.setChecked(False)
            self.update_log('All files have been removed.')

    def clear_files(self):
        # clear all files from the file list and plot
        self.remove_files(clear_all=True)
        self.calc_pb.setValue(0)
        self.remove_files(clear_all=True)
        self.trim_file_btn.setEnabled(False)

    def update_suffix(self):
        # enable the custom suffix text box and format the user text as needed for acceptable file name suffix
        self.fname_suffix_tb.setEnabled(self.advanced_options_gb.isChecked())
        suffix_str = self.fname_suffix_tb.text()  # if custom suffix is checked, get text from user

        # if self.custom_info_gb.isChecked():
        if self.advanced_options_gb.isChecked():
            if not suffix_str.isspace() and suffix_str != '':
                suffix_str = self.fname_suffix_tb.text()  # if custom suffix is checked, get text from user
                # keep only alphanum. and acceptable chars
                suffix_str = ''.join([c for c in suffix_str if c.isalnum() or c in ['_', '-', ' ', '.']])
                self.fname_suffix = '_'.join(suffix_str.split()).replace(".", "")  # replace whitespace, remove all .s
                self.fname_suffix_final_lbl.setStyleSheet("color: black")

            else:  # warn user if text box is empty and use default
                self.fname_suffix = self.fname_suffix_default
                self.fname_suffix_final_lbl.setStyleSheet("color: red")

        else:  # use default suffix if not checked or nothing entered
            self.fname_suffix = self.fname_suffix_default
            self.fname_suffix_final_lbl.setStyleSheet("color: black")

        # finalize the fname suffix (.all only for now) and show the final result to user
        self.fname_suffix_final_lbl.setText(self.fname_suffix_final_header +
                                            '_' + self.fname_suffix + '.[extension]')

    def get_current_file_list(self):  # get current list of files in qlistwidget
        list_items = []
        for f in range(self.file_list.count()):
            list_items.append(self.file_list.item(f))

        # self.filenames = [f.text() for f in list_items]  # convert to text
        self.filenames = [f.data(1) for f in list_items]  # return list of full file paths stored in item data, role 1

    def get_new_file_list(self, fext=[''], flist_old=[]):
        # determine list of new files with file extension fext that do not exist in flist_old
        # flist_old may contain paths as well as file names; compare only file names
        self.get_current_file_list()
        fnames_ext = [fn for fn in self.filenames if any(ext in fn for ext in fext)] # fnames (w/ paths) matching ext
        fnames_old = [fn.split('/')[-1] for fn in flist_old]  # file names only (no paths) from flist_old
        fnames_new = [fn for fn in fnames_ext if fn.split('/')[-1] not in fnames_old]  # check if fname in fnames_old

        return (fnames_new)  # return the fnames_new (with paths)

    def update_log(self, entry):  # update the activity log
        self.log.append(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' ' + entry)
        QtWidgets.QApplication.processEvents()

    def check_output_options(self):
        sending_button = self.sender()
        if sending_button:
            print('***CHECK OUTPUT OPTIONS activated by sender:', str(sending_button.objectName()))

        if self.overwrite_chk.isChecked() and self.raw_fname_chk.isChecked():
            # disable the trim button if user attempts to overwrite existing data AND keep the source filename
            self.trim_file_btn.setEnabled(False)
            self.update_log('WARNING: Cannot overwrite existing files AND keep source filenames. '
                            'Please select only one option (or neither).')

        else:
            # enable trim button if a) user elects to allow overwriting w/o source fname OR
            # b) keep source fname w/o allowing overwriting OR c) neither option
            self.trim_file_btn.setEnabled(True)

        if sending_button.isChecked():
            user_warning = QtWidgets.QMessageBox.question(self, 'Trimmed file output check',
                                                          'WARNING: User is responsible for protecting original data!'
                                                          '\n\nBefore trimming files, please double-check the selected '
                                                          'option for keeping the source filename OR overwriting '
                                                          'existing files in the output directory.'
                                                          '\n\nRaw source file names may be used for output files if '
                                                          'the overwrite option is not selected.'
                                                          '\n\nLikewise, output filenames that already exist may be '
                                                          'overwritten with new trimmed files if a suffix is appended '
                                                          'to distinguish from the source files.'
                                                          '\n\nConfirm the source and output directories to ensure '
                                                          'that the original raw data will not be impacted.'
                                                          '\n\nRegardless of user options, any source files found to '
                                                          'exist in the output directory will be skipped.  A different '
                                                          'output directory must be selected for these source files '
                                                          'to help reduce risk of overwriting data.',
                                                          QtWidgets.QMessageBox.Ok)

        if self.raw_fname_chk.isChecked():
            self.fname_suffix_tb.setEnabled(False)
            self.fname_suffix_final_lbl.setText(self.fname_suffix_final_header + 'SOURCE FILENAME')
            self.fname_suffix_final_lbl.setStyleSheet("color: red")
            self.fname_suffix == ''

        else:
            self.fname_suffix_tb.setEnabled(True)
            self.update_suffix()

    def trim_files(self):
        self.update_log('Starting trimming process with the following user options:')
        self.update_log('\t1. Output directory is:\n\t\t' + self.output_dir)
        self.update_log('\t2. Output filenames will be ' +
                        ('the SOURCE filenames' if self.raw_fname_chk.isChecked() else
                         'APPENDED with "_' + self.fname_suffix + '"'))
        self.update_log('\t3. Files with the same trimmed output name will be ' +
                        ('OVERWRITTEN ' if self.overwrite_chk.isChecked() else 'SKIPPED '))

        # update file size trackers
        self.fcount_trimmed = 0
        self.fcount_skipped = 0
        self.fsize_all_orig = 0
        self.fsize_all_trim = 0

        # write new files with all desired datagrams found in originals
        # dg_ID_list = list(self.dg_ID.keys())
        # dg_ID_list = list(self.dg_ID[self.proc_path][])

        # get list of added files that do not already exist as trimmed versions in the output directory
        if self.output_dir:
            fnames_outdir = os.listdir(self.output_dir)  # get list of all files in output directory
        else:
            self.update_log('Please select an output directory')

        # print('initial fnames_outdir from os.listdir=', fnames_outdir)
        fnames = self.get_new_file_list(['.all', '.kmall'])  # get updated list of input files

        if self.overwrite_chk.isChecked():
            # set new filename list to all files and overwrite any existing files
            fnames_outdir = []  # if overwriting allowed, empty fnames_outdir so get_new_file_list returns all sources

        # print('fnames_outdir updated to', fnames_outdir)
        fnames_new = self.get_new_file_list(['.all', '.kmall'], fnames_outdir)  # get list of new files not in out dir
        # print('fnames_new =', fnames_new)
        source_dir_set = set([f.rsplit('/', 1)[0] for f in fnames_new])  # get source dirs to check against output_dir

        if self.output_dir in source_dir_set:
            self.update_log('WARNING: At least one source file found in the selected output directory;\n' +
                            '\t\tto reduce the potential for catastrophe, trimmed files cannot be written\n' +
                            '\t\tto the same source directory (please select another output directory for\n' +
                            '\t\tthese files, which will be skipped here; see log after trimming)')

        if len(fnames_new) == 0:  # if all source files already exist in output dir, warn user and return
            self.update_log('Output directory includes all source files; no files will be written')
            return()

        else:  # loop through all files and write new trimmed versions
            fcount_skipped = len(fnames) - len(fnames_new)

            if fcount_skipped > 0:
                self.fcount_skipped += fcount_skipped
                self.update_log('Skipping ' + str(fcount_skipped) +
                                ' source file' + ('s' if fcount_skipped > 1 else '') +
                                ' found in the selected output directory')

            self.update_log('Trimming ' + str(len(fnames_new)) +
                            ' source file' + ('s' if len(fnames_new) > 1 else '') +
                            ' from outside the selected output directory\n')

            # update progress bar and log
            f = 0
            self.calc_pb.setValue(f)  # reset progress bar to 0 and max to number of files
            self.calc_pb.setMaximum(len(fnames_new))

            # write trimmed version for each new file (initial code from Kongsberg, modified by UNH CCOM)
            for fpath_in in fnames_new:
                self.write_reduced_EM_file(fpath_in) #self.fname_suffix, self.output_dir) #, dg_ID_list)
                f = f + 1
                self.update_prog(f)

            self.update_log('Finished writing ' + str(self.fcount_trimmed) + ' new trimmed file' +
                            ('s' if self.fcount_trimmed > 1 else '') +
                            ' (skipped ' + str(self.fcount_skipped) + ' file' +
                            ('' if self.fcount_skipped == 1 else 's') + ' with name or directory conflicts' +
                            ('; see log)' if self.fcount_skipped > 0 else ')'))

            if self.fcount_trimmed > 0:
                self.update_log('Total file size reduction for ' + str(self.fcount_trimmed) + ' file' +
                                ('s: ' if self.fcount_trimmed > 1 else ': ') +
                                str(round(100*(1-(self.fsize_all_trim/self.fsize_all_orig)))) + '%' +
                                ' (' + str(round(self.fsize_all_orig/1000)) + ' KB to '
                                + str(round(self.fsize_all_trim/1000)) + ' KB)')

    def write_reduced_EM_file(self, fpath_in):  # fname_suffix, output_dir): #dg_keep_list):
        # write the new EM .all file with only the requested datagrams (if present in original .all file)
        # set up the output full file path including suffix to check existence
        fpath_in = os.path.abspath(fpath_in)
        fname_in = os.path.basename(fpath_in)
        fdir_in = os.path.dirname(fpath_in)

        if self.raw_fname_chk.isChecked():  # set fname_out to fname_in if source filename option is checked
            fname_out = fname_in

        else:  # otherwise, generate fname_out with fname_suffix
            fname_out = fname_in.rsplit('.', 1)[0] + '_' + self.fname_suffix + '.' + fname_in.rsplit('.', 1)[1]

        fpath_out = os.path.join(self.output_dir, fname_out)
        fpath_out = os.path.abspath(fpath_out)
        fname_out = os.path.basename(fpath_out)
        fdir_out = os.path.dirname(fpath_out)

        # print('fpath_in=', fpath_in)
        # print('fname_in=', fname_in)
        # print('fdir_in=', fdir_in)
        #
        # print('fpath_out=', fpath_out)
        # print('fname_out=', fname_out)
        # print('fdir_out=', fdir_out)
        #
        # print('output dir = ', self.output_dir)

        # avoid writing over the original data (must check full output path); both of these conditions should be avoided
        # by the 'original' name checking step in trim_files, but are checked again here for extra caution

        if fdir_in == fdir_out: #s.path.abspath(fpath_out)self.output_dir:  # return if the 'new' version would be written to same directory
            # even with other warnings, under no circumstances may files be written to the source directory!
            self.update_log('Skipping ' + fpath_in +
                            '\n\t\t--->(source file directory is same as output directory; '
                            'select different output directory)')
            self.fcount_skipped += 1
            return()

        elif os.path.exists(fpath_out):  # if not in same directory, check if intended output fname already exists
            if not self.overwrite_chk.isChecked():  # output fname exists; return if the overwrite option is not checked
                self.update_log('Skipping ' + fpath_in +
                                '\n\t\t--->(output filename already exists in output directory;'
                                'consider the overwrite option if necessary)')
                self.fcount_skipped += 1
                return ()

            else:  # continue only if overwrite option is checked
                self.update_log('***Overwriting ' + fpath_out)

        # otherwise, read input file and write output file only if there is no chance of writing over original data
        print('trying to get size of fpath_in=', fpath_in)
        fsize_orig = os.path.getsize(fpath_in)  # get original file size
        self.fsize_all_orig += fsize_orig  # add to

        file_ext = fpath_in.rsplit('.',1)[1]
        print('found fpath_in ', fpath_in, ' with file_ext =', file_ext)

        if file_ext == 'all':  # step through .all file, check datagram, write required datagrams to new file
            dg_keep_list = self.dg_ID['all'][self.proc_path].keys()  # use keys from dict of datagrams for .all
            print('dg_keep_list=', dg_keep_list)
            print('working on .all file ', fpath_in)
            fid_out = open(fpath_out, "wb")  # create output file
            fid_in = open(fpath_in, "rb")  # open source file
            raw = fid_in.read()  # read source
            len_raw = len(raw)
            dg_start = 0  # datagram length field precedes datagram (dg is between STX and ETX, inclusive)

            while True:  # parse datagrams and copy those on the list
                if dg_start + 4 >= len_raw:  # break if EOF
                    break

                dg_len = struct.unpack('I', raw[dg_start:dg_start + 4])[0]  # get dg length (before start of dg at STX)

                # continue to next iteration if dg length is insufficient to check for STX, ID, and ETX
                if dg_len < 3:
                    dg_start = dg_start + 4
                    continue

                dg_end = dg_start + 4 + dg_len  # if length is OK, get expected end location, including length field

                # continue to next iteration if dg_end is beyond EOF
                if dg_end > len_raw:
                    dg_start = dg_start + 4
                    continue

                # try to read dg starting with STX if len seems reasonable and not EOF
                dg = raw[dg_start + 4:dg_end]  # get STX, ID, and ETX
                dg_STX = dg[0]
                dg_ID = dg[1]
                dg_ETX = dg[-3]

                # continue unpacking only if STX and ETX are valid
                if dg_STX == 2 and dg_ETX == 3:
                    if dg_ID in dg_keep_list:  # write datagram to output file if on the list
                        fid_out.write(raw[dg_start:dg_end])

                    dg_start = dg_start + dg_len + 4  # reset pointer to end of datagram if this had valid STX and ETX
                    continue

                # if not valid, move ahead by 1 and continue search
                dg_start = dg_start + 1

            # close input, output files and return
            fid_in.close()
            fid_out.close()

        elif file_ext == 'kmall':  # use kmall module to parse, ********* FIGURE OUT HOW TO WRITE FROM KMALL *****
            dg_keep_list = self.dg_ID['kmall'][self.proc_path].values()  # use keys from dict of datagrams for .all
            print('dg_keep_list=', dg_keep_list)

            fid_out = open(fpath_out, "wb")
            print('working on .kmall file ', fpath_in)
            ####### DO KMALL STUFF #########
            km = kmall.kmall(fpath_in)
            km.verbose = 0
            km.index_file()
            km.report_packet_types()
            # print('km.Index has type', type(km.Index), 'and looks like:')
            # print(km.Index)
            km.closeFile()

            # reduce the dataframe to include only MessageTypes in the required datagram list dg_list
            df = km.Index
            df = df[df['MessageType'].str.contains('|'.join(dg_keep_list))]
            print('df after filter = ', df)

            # read in source file
            fid_in = open(fpath_in, "rb")
            raw = fid_in.read()

            # loop through the filtered/reduced dataframe of datagrams to keep and write chunks to the new file
            for i in range(df.shape[0]):
                dg_info = df.iloc[i]
                dg_start = dg_info['ByteOffset']
                dg_end = dg_start + dg_info['MessageSize']
                # print('*** FILTERED datagram number', i, 'is type=', dg_info['MessageType'],
                #       'offset=', dg_start, 'len=', dg_info['MessageSize'], 'and dg_end=', dg_end)
                fid_out.write(raw[dg_start:dg_end])

            # close output file
            fid_out.close()
            print('closed .kmall input and output files!')

        self.fcount_trimmed += 1

        # get trimmed file size and update log
        fsize_trim = os.path.getsize(fpath_out)
        self.fsize_all_trim += fsize_trim
        self.update_log('Trimmed ' + fpath_in +
                        '\n\t                   to ' + fpath_out +
                        '\n\t                   ' +
                        'File size reduction: ' + str(round(100*(1-(fsize_trim/fsize_orig)))) + '%' +
                        ' (' + str(round(fsize_orig/1000)) + ' KB to ' + str(round(fsize_trim/1000)) + ' KB)\n')
        return ()

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
