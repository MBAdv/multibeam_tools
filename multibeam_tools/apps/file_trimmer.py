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

__version__ = "0.1.1"


class PushButton(QtWidgets.QPushButton):
    # generic push button class
    def __init__(self, text='PushButton', width=50, height=20, name='NoName', tool_tip='', parent=None):
        super(PushButton, self).__init__()
        self.setText(text)
        self.setFixedSize(int(width), int(height))
        self.setObjectName(name)
        self.setToolTip(tool_tip)

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

        # set up layouts of main window
        # self.set_top_layout()
        self.set_main_layout()
        self.update_suffix()

        # set of datagrams required for Qimera processing
        self.dg_ID = {65: 'ATT',
                      68: 'DEPTH',
                      71: 'SSS',
                      72: 'HDG',
                      73: 'IP START',
                      78: 'RRA_78',
                      80: 'POS',
                      82: 'RTP',
                      85: 'SSP',
                      88: 'XYZ_88',
                      105: 'IP STOP'}
        # 49:'PU',
        # 66:'BIST',
        # 67:'CLOCK',
        # 83:'SEABED_IMAGE_83',
        # 89:'SEABED_IMAGE_89',
        # 102:'RRA_102',
        # 107:'WATERCOLUMN',
        # 110:'ATT_VEL'}

        # set up file control actions
        self.add_file_btn.clicked.connect(lambda: self.add_files('Kongsberg .all(*.all)'))
        self.get_indir_btn.clicked.connect(self.get_input_dir)
        self.rmv_file_btn.clicked.connect(self.remove_files)
        self.clr_file_btn.clicked.connect(self.clear_files)
        self.get_outdir_btn.clicked.connect(self.get_output_dir)
        self.trim_file_btn.clicked.connect(self.trim_files)
        self.custom_info_gb.clicked.connect(self.update_suffix)
        self.fname_suffix_tb.textChanged.connect(self.update_suffix)

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

        # set up custom file suffix options
        custom_info_lbl = QtWidgets.QLabel('(alphanumeric, -, and _ only;\nno file extensions or padding)')
        fname_suffix_tb_lbl = QtWidgets.QLabel('Suffix:')
        self.fname_suffix_tb = QtWidgets.QLineEdit(self.fname_suffix_default)
        self.fname_suffix_tb.setFixedHeight(20)
        self.fname_suffix_tb.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding,
                                           QtWidgets.QSizePolicy.MinimumExpanding)
        self.fname_suffix_tb.setEnabled(False)
        self.fname_suffix_final_header = 'Output: '
        self.fname_suffix_final_lbl = QtWidgets.QLabel(self.fname_suffix_final_header)

        fname_suffix_layout = QtWidgets.QHBoxLayout()
        fname_suffix_layout.addWidget(fname_suffix_tb_lbl)
        fname_suffix_layout.addWidget(self.fname_suffix_tb)

        custom_info_layout = QtWidgets.QVBoxLayout()
        custom_info_layout.addWidget(custom_info_lbl)
        custom_info_layout.addLayout(fname_suffix_layout)
        custom_info_layout.addWidget(self.fname_suffix_final_lbl)

        self.custom_info_gb = QtWidgets.QGroupBox('Append custom filename suffix')
        self.custom_info_gb.setLayout(custom_info_layout)
        self.custom_info_gb.setSizePolicy(QtWidgets.QSizePolicy.Maximum,
                                          QtWidgets.QSizePolicy.Maximum)
        self.custom_info_gb.setCheckable(True)
        self.custom_info_gb.setChecked(False)

        # set the file control button layout
        file_btn_layout = QtWidgets.QVBoxLayout()
        file_btn_layout.addWidget(self.add_file_btn)
        file_btn_layout.addWidget(self.get_indir_btn)
        file_btn_layout.addWidget(self.get_outdir_btn)
        file_btn_layout.addWidget(self.rmv_file_btn)
        file_btn_layout.addWidget(self.clr_file_btn)
        file_btn_layout.addWidget(self.trim_file_btn)
        file_btn_layout.addWidget(self.custom_info_gb)
        file_btn_layout.addStretch()

        # disable trim button until output directory is selected
        self.trim_file_btn.setEnabled(False)

        # set the file control button groupbox
        self.file_control_gb = QtWidgets.QGroupBox('File Control')
        self.file_control_gb.setLayout(file_btn_layout)

        # add table showing selected files
        self.file_list = QtWidgets.QListWidget()
        self.file_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.file_list.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding,
                                     QtWidgets.QSizePolicy.MinimumExpanding)

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
                        fnames.append(
                            os.path.join(input_dir, f))  # add whole path, same convention as getOpenFileNames

        self.get_current_file_list()  # get updated file list and add selected files only if not already listed
        fnames_new = [fn for fn in fnames if fn not in self.filenames]
        fnames_skip = [fs for fs in fnames if fs in self.filenames]

        if len(fnames_skip) > 0:  # skip any files already added, update log
            self.update_log('Skipping ' + str(len(fnames_skip)) + ' file(s) already added')

        for f in range(len(fnames_new)):  # add the new files only
            self.file_list.addItem(fnames_new[f])
            self.update_log('Added ' + fnames_new[f].split('/')[-1])

        if fnames_new:
            self.update_log('Finished adding ' + str(len(fnames_new)) + ' new file' +
                            ('s' if len(fnames_new) > 1 else ''))

            if self.output_dir:  # if output directory is selected, reenable trim button after files are loaded
                self.trim_file_btn.setEnabled(True)

    def remove_files(self, clear_all=False):  # remove selected files
        self.get_current_file_list()
        selected_files = self.file_list.selectedItems()

        # elif not selected_files:  # files exist but nothing is selected
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

        if len(fnames_all) == 0:
            self.trim_file_btn.setChecked(False)
            self.update_log('All files have been removed.')

    def clear_files(self):
        # clear all files from the file list and plot
        self.file_list.clear()  # clear the file list display
        self.filenames = []  # clear the list of (paths + files) passed to calc_coverage
        self.calc_pb.setValue(0)
        self.remove_files(clear_all=True)
        self.trim_file_btn.setEnabled(False)

    def get_input_dir(self):
        # get directory of files to load
        try:
            self.input_dir = QtWidgets.QFileDialog.getExistingDirectory(self, 'Add directory',
                                                                        os.getenv('HOME'))
            self.update_log('Added directory: ' + self.input_dir)

            # get a list of all .txt files in that directory, '/' avoids '\\' in os.path.join in add_files
            self.update_log('Adding files in directory: ' + self.input_dir)
            self.add_files('Kongsberg (*.all *.kmall)',  input_dir=self.input_dir + '/')

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

            elif not self.output_dir_old:  # warn user if not selected but keep trim button enabled and old output directory
                self.update_log('No output directory selected')

        except:
            # warn user if failed and disable trim button until output directory is selected
            self.update_log('Failure selecting output directory')
            self.output_dir = ''
            self.trim_file_btn.setEnabled(False)
            pass

    def update_suffix(self):
        # enable the custom suffix text box and format the user text as needed for acceptable file name suffix
        self.fname_suffix_tb.setEnabled(self.custom_info_gb.isChecked())  # enable text box if checked
        suffix_str = self.fname_suffix_tb.text()  # if custom suffix is checked, get text from user

        if self.custom_info_gb.isChecked():
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
                                            '_' + self.fname_suffix + '.all')

    def get_current_file_list(self):  # get current list of files in qlistwidget
        list_items = []
        for f in range(self.file_list.count()):
            list_items.append(self.file_list.item(f))

        self.filenames = [f.text() for f in list_items]  # convert to text

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
        return (fnames_new)  # return the fnames_new (with paths)

    def update_log(self, entry):  # update the activity log
        self.log.append(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' ' + entry)
        QtWidgets.QApplication.processEvents()

    def trim_files(self):
        # update file size trackers
        self.fcount_trimmed = 0
        self.fcount_skipped = 0
        self.fsize_all_orig = 0
        self.fsize_all_trim = 0

        # write new files with all desired datagrams found in originals
        dg_ID_list = list(self.dg_ID.keys())

        # get list of added files that do not already exist as trimmed versions in the output directory
        try:
            fnames_outdir = os.listdir(self.output_dir)
            print(fnames_outdir)
        except:
            print('fail')
            fnames_outdir = []

        fnames_all = self.get_new_file_list('.all')  # get updated list of all files
        fnames_new_all = self.get_new_file_list('.all', fnames_outdir)  # get list of new files not in output_dir
        source_dir_set = set([f.rsplit('/', 1)[0] for f in fnames_all])  # get source dirs to check against output_dir

        if self.output_dir in source_dir_set:
            self.update_log('WARNING: At least one source file found in the selected output directory;\n' +
                            '\t\tto reduce the potential for catastrophe, trimmed files cannot be written\n' +
                            '\t\tto the same source directory (please select another output directory for\n' +
                            '\t\tthese files, which will be skipped here)')

        if len(fnames_new_all) == 0:  # if all source files already exist in output dir, warn user and return
            self.update_log('Output directory includes all source files (raw or trimmed); no files will be written')
            return()

        else:  # loop through all files and write new trimmed versions
            fcount_skipped = len(fnames_all) - len(fnames_new_all)
            if fcount_skipped > 0:
                self.fcount_skipped += fcount_skipped
                s = 's' if fcount_skipped > 1 else ''
                self.update_log('Skipping ' + str(fcount_skipped) +
                                ' source file' + ('s' if fcount_skipped > 1 else '') +
                                ' that exist' + ('' if fcount_skipped > 1 else 's') +
                                ' in the selected output directory')

            self.update_log('Trimming ' + str(len(fnames_new_all)) +
                            ' source file' + ('s' if len(fnames_new_all) > 1 else '') +
                            ' from outside the selected output directory')

            # update progress bar and log
            f = 0
            self.calc_pb.setValue(f)  # reset progress bar to 0 and max to number of files
            self.calc_pb.setMaximum(len(fnames_new_all))

            # write trimmed version for each new file (code from Kongsberg, modified by UNH CCOM)
            for fpath_in in fnames_new_all:
                self.write_reduced_EM_file(fpath_in, self.fname_suffix, self.output_dir, dg_ID_list)
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

    def write_reduced_EM_file(self, fpath_in, fname_suffix, output_dir, dg_keep_list):
        # write the new EM .all file with only the requested datagrams (if present in original .all file)
        # set up the output full file path including suffix to check existence
        fdir_in = fpath_in.rsplit('/', 1)[0]
        fname_in = os.path.basename(fpath_in)
        fname_out = fname_in.rsplit('.')[0] + '_' + fname_suffix + '.' + fname_in.rsplit('.')[1]
        fpath_out = os.path.join(output_dir, fname_out)

        # avoid writing over the original data (must check full output path); both of these conditions should be avoided
        # by the 'original' name checking step in trim_files, but are checked again here for extra caution
        if os.path.exists(fpath_out):  # return if the 'new' version already exists in output directory
            print('fpath_in=', fpath_in)
            print('fpath_out=', fpath_out)
            self.update_log('Skipping ' + fpath_in + '\n\t(trimmed version already exists in output directory)')
            self.fcount_skipped += 1
            return ()

        elif fdir_in == output_dir:  # return if the 'new' version would be written to same directory
            self.update_log('Skipping ' + fpath_in + '\n\t(source file directory is same as output directory)')
            self.fcount_skipped += 1
            return()

        # otherwise, read input file and write output file only if there is no chance of writing over original data
        fsize_orig = os.path.getsize(fpath_in)  # get original file size
        self.fsize_all_orig += fsize_orig  # add to

        fid_in = open(fpath_in, 'rb')
        fid_out = open(fpath_out, "wb")
        raw = fid_in.read()
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

                # fid_in.seek(dg_start)  # rewind to start of dg len field
                # data = fid_in.read(dg_len + 4)  # read whole datagram
                if dg_ID in dg_keep_list:  # write datagram to output file if on the list
                    fid_out.write(raw[dg_start:dg_end])

                dg_start = dg_start + dg_len + 4  # reset pointer to end of datagram if this had valid STX and ETX
                continue

            # if not valid, move ahead by 1 and continue search
            dg_start = dg_start + 1

        # close input, output files and return
        fid_in.close()
        fid_out.close()

        # self.update_log('Wrote ' + fpath_in + '\n\t                to ' + fpath_out)
        self.fcount_trimmed += 1

        # get trimmed file size and update log
        fsize_trim = os.path.getsize(fpath_out)
        self.fsize_all_trim += fsize_trim
        self.update_log('Trimmed ' + fpath_in +
                        '\n\t                   to ' + fpath_out +
                        '\n\t                   ' +
                        'File size reduction: ' + str(round(100*(1-(fsize_trim/fsize_orig)))) + '%' +
                        ' (' + str(round(fsize_orig/1000)) + ' KB to ' + str(round(fsize_trim/1000)) + ' KB)')
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
