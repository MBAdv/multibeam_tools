# -*- coding: utf-8 -*-
"""

Multibeam Echosounder Assessment Toolkit: Kongsberg .all backscatter blowout trimmer

Generate trimmed .all files with all original datagrams except those for pings with abnormally high or low mean
backscatter in the seabed image datagram (referred to here as 'blowouts'.  The raw range and angle (78), XYZ (88), and
seabed image (89) datagrams are removed for these blowouts.

This was originally intened to remove intermittent bad pings observed during backscatter calibration for an EM302 and
is not intended for general backscatter filtering or data compression.  The trimmed files are intended for special
backscatter processing and not necessarily for general data archiving, as the raw data is altered and file names are
changed.

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
import multibeam_tools.libs.readEM
import multibeam_tools.libs.parseEM
import numpy as np

__version__ = "0.0.1"

class MainWindow(QtWidgets.QMainWindow):
    media_path = os.path.join(os.path.dirname(__file__), "media")

    def __init__(self, parent=None):
        super(MainWindow, self).__init__()

        # set up main window
        self.mainWidget = QtWidgets.QWidget(self)
        self.setCentralWidget(self.mainWidget)
        self.setMinimumWidth(550)
        self.setMinimumHeight(500)
        self.setWindowTitle('Backscatter Blowout Trimmer v.%s' % __version__)
        self.setWindowIcon(QtGui.QIcon(os.path.join(self.media_path, "icon.png")))

        # initialize other necessities
        self.filenames = ['']
        self.output_dir = ''
        self.fname_suffix_default = 'BS_trimmed'

        # set up layouts of main window
        self.set_main_layout()
        self.update_suffix()

        # set up file control actions
        self.add_file_btn.clicked.connect(lambda: self.add_files('Kongsberg .all(*.all)'))
        self.rmv_file_btn.clicked.connect(self.remove_files)
        self.clr_file_btn.clicked.connect(self.clear_files)
        self.get_outdir_btn.clicked.connect(self.get_output_dir)
        self.trim_file_btn.clicked.connect(self.trim_files)
        self.custom_info_chk.stateChanged.connect(self.update_suffix)
        self.fname_suffix_tb.textChanged.connect(self.update_suffix)
        # self.custom_info_chk.stateChanged(self.custom_info_gb.setEnabled(self.custom_info_chk.isChecked()))

    def set_main_layout(self):
        # set layout with file controls on right, sources on left, and progress log on bottom
        file_button_height = 20  # height of file control button
        file_button_width = 100  # width of file control button

        # add file control buttons and file list
        self.add_file_btn = QtWidgets.QPushButton('Add Files')
        self.get_outdir_btn = QtWidgets.QPushButton('Select Output Dir.')
        self.rmv_file_btn = QtWidgets.QPushButton('Remove Selected')
        self.clr_file_btn = QtWidgets.QPushButton('Clear All Files')
        self.trim_file_btn = QtWidgets.QPushButton('Trim Files')

        # format file control buttons
        self.add_file_btn.setFixedSize(file_button_width, file_button_height)
        self.get_outdir_btn.setFixedSize(file_button_width, file_button_height)
        self.rmv_file_btn.setFixedSize(file_button_width, file_button_height)
        self.clr_file_btn.setFixedSize(file_button_width, file_button_height)
        self.trim_file_btn.setFixedSize(file_button_width, file_button_height)

        # add checkbox and set layout for custom filename suffix
        self.custom_info_chk = QtWidgets.QCheckBox('Append custom filename suffix\n'
                                                   '(alphanumeric, -, and _ only;\n'
                                                   'no file extensions or padding)')
        self.fname_suffix_tb_lbl = QtWidgets.QLabel('Suffix:')
        self.fname_suffix_tb = QtWidgets.QLineEdit()
        # self.fname_suffix_tb.setFixedSize(110, 20)
        self.fname_suffix_tb.setFixedHeight(20)
        self.fname_suffix_tb.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding,
                                           QtWidgets.QSizePolicy.MinimumExpanding)
        self.fname_suffix_tb.setText(self.fname_suffix_default)
        self.fname_suffix_tb.setEnabled(False)
        # self.fname_suffix_warning = QtWidgets.QLabel('(alphanumeric only, no extension)')
        self.fname_suffix_final_header = 'Output filename ending: '
        self.fname_suffix_final_lbl = QtWidgets.QLabel(self.fname_suffix_final_header)

        fname_suffix_layout = QtWidgets.QHBoxLayout()
        fname_suffix_layout.addWidget(self.fname_suffix_tb_lbl)
        fname_suffix_layout.addWidget(self.fname_suffix_tb)


        custom_info_layout = QtWidgets.QVBoxLayout()
        custom_info_layout.addWidget(self.custom_info_chk)
        custom_info_layout.addLayout(fname_suffix_layout)
        # custom_info_layout.addWidget(self.fname_suffix_warning)
        custom_info_layout.addWidget(self.fname_suffix_final_lbl)

        self.custom_info_gb = QtWidgets.QGroupBox()
        self.custom_info_gb.setLayout(custom_info_layout)
        self.custom_info_gb.setSizePolicy(QtWidgets.QSizePolicy.Maximum,
                                          QtWidgets.QSizePolicy.Maximum)

        # set the file control button layout
        file_btn_layout = QtWidgets.QVBoxLayout()
        file_btn_layout.addWidget(self.add_file_btn)
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
        # self.log_gb.setFixedWidth(800)
        self.log_gb.setMinimumWidth(800)

        # set the left panel layout with file controls on top and log on bottom
        main_layout = QtWidgets.QVBoxLayout()
        main_layout.addLayout(self.file_layout)  # add file list group box
        main_layout.addWidget(self.log_gb)  # add log group box
        self.mainWidget.setLayout(main_layout)

    def add_files(self, ftype_filter):  # select files with desired type, add to list box
        fnames = QtWidgets.QFileDialog.getOpenFileNames(self, 'Open files...', os.getenv('HOME'), ftype_filter)
        self.get_current_file_list()  # get updated file list and add selected files only if not already listed
        fnames_new = [fn for fn in fnames[0] if fn not in self.filenames]
        fnames_skip = [fs for fs in fnames[0] if fs in self.filenames]

        if len(fnames_skip) > 0:  # skip any files already added, update log
            self.update_log('Skipping ' + str(len(fnames_skip)) + ' file(s) already added')

        for f in range(len(fnames_new)):  # add the new files only
            self.file_list.addItem(fnames_new[f])
            self.update_log('Added ' + fnames_new[f].split('/')[-1])

        if len(fnames_new) > 0:  # and ftype_filter == 'Kongsberg .all(*.all)':
            if self.output_dir == '':
                self.get_outdir_btn.setStyleSheet("background-color: yellow")  # set button yellow if not selected yet

            else:
                self.trim_file_btn.setStyleSheet(
                    "background-color: yellow")  # set button yellow if new .all files loaded

    def remove_files(self):  # remove selected files
        self.get_current_file_list()
        selected_files = self.file_list.selectedItems()
        fnames_all = [f for f in self.filenames if '.all' in f]

        if len(fnames_all) == 0:  # all .all files have been removed
            self.update_log('All files have been removed.')

        elif not selected_files:  # files exist but nothing is selected
            self.update_log('No files selected for removal.')
            return

        else:  # remove only the files that have been selected
            for f in selected_files:
                fname = f.text().split('/')[-1]
                self.file_list.takeItem(self.file_list.row(f))
                self.update_log('Removed ' + fname)

    def clear_files(self):
        self.file_list.clear()  # clear the file list display
        self.filenames = []  # clear the list of (paths + files) passed to calc_coverage
        self.update_log('Cleared all files')
        self.calc_pb.setValue(0)
        self.remove_files()

    def get_output_dir(self):
        # may want to add warning about using the same input/output directories!

        try:
            self.output_dir = QtWidgets.QFileDialog.getExistingDirectory(self, 'Select output directory',
                                                                         os.getenv('HOME'))
            self.update_log('Selected output directory: ' + self.output_dir)
            self.get_outdir_btn.setStyleSheet("background-color: none")
            self.trim_file_btn.setEnabled(True)
            self.trim_file_btn.setStyleSheet("background-color: yellow")
            self.current_outdir_lbl.setText('Current output directory: ' + self.output_dir)

        except:
            self.update_log('No output directory selected.')
            self.output_dir = ''
            self.trim_file_btn.setEnabled(False)
            self.trim_file_btn.setStyleSheet("background-color: none")
            pass

    def update_suffix(self):
        # enable the custom suffix text box and format the user text as needed for acceptable file name suffix
        self.fname_suffix_tb.setEnabled(self.custom_info_chk.isChecked()) # enable text box if checked
        # try to format user entry if checked, not empty, and not all whitespace
        if (self.custom_info_chk.isChecked() and
            not self.fname_suffix_tb.text().isspace() and
            self.fname_suffix_tb.text() != ''):
            suffix_str = self.fname_suffix_tb.text()  # if custom suffix is checked, get text from user
            # keep only alphanum. and acceptable chars (allow . for now, split later to ensure correct file extension)
            suffix_str = ''.join([c for c in suffix_str if c.isalnum() or c in ['_', '-', ' ', '.']])
            suffix_str = '_'.join(suffix_str.split())  # replace any whitespace with _
            self.fname_suffix = suffix_str.split('.')[0]  # remove any file extension

            # warn user if text box contains unallowed characters
            if self.fname_suffix != self.fname_suffix_tb.text():
                self.fname_suffix_tb.setStyleSheet("background-color: yellow")
            else:
                self.fname_suffix_tb.setStyleSheet("background-color: none")

        else:  # use default suffix if not checked or nothing entered
            self.fname_suffix = self.fname_suffix_default

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
        # write new files with all desired datagrams found in originals
        # get list of added files that do not already exist as trimmed versions in the output directory
        try:
            fnames_trimmed = os.listdir(self.output_dir)
        except:
            fnames_trimmed = []

        fnames_trimmed_orig = [f.replace(self.fname_suffix, '') for f in fnames_trimmed]
        fnames_new_all = self.get_new_file_list('.all', fnames_trimmed_orig)

        if len(fnames_new_all) > 0:  # loop through all files and write new trimmed versions
            self.update_log('Found ' + str(len(fnames_new_all)) + ' new .all files not yet trimmed in output directory')

            # update progress bar and log
            f = 0
            self.calc_pb.setValue(f)  # reset progress bar to 0 and max to number of files
            self.calc_pb.setMaximum(len(fnames_new_all))

            # write trimmed version for each new file (code from Kongsberg, modified by UNH CCOM)
            for fpath_in in fnames_new_all:
                fname_str = fpath_in.split('/')[-1]
                self.update_log('Trimming file ' + fname_str)
                # self.write_reduced_EM_file(fpath_in, self.fname_suffix, self.output_dir, dg_ID_list)
                self.write_fixed_EM_file(fpath_in, self.fname_suffix, self.output_dir)

                f = f + 1
                self.update_prog(f)

            self.update_log('Finished trimming files')
            self.trim_file_btn.setStyleSheet("background-color: none")  # reset the button color to default

    def write_fixed_EM_file(self, fpath_in, fname_suffix, output_dir):
        # write the new EM .all file without the pings that have extremely high or low backscatter values
        # set up the output full file path including suffix to check existence
        fname_in = os.path.basename(fpath_in)
        fname_out = fname_in.rsplit('.')[0] + '_' + fname_suffix + '.' + fname_in.rsplit('.')[1]
        fpath_out = os.path.join(output_dir, fname_out)
        self.update_log('Writing ' + fpath_in + '\n\t to --->' + fpath_out)

        # avoid writing over the original data (must check full output path)
        if os.path.exists(fpath_out):  # return if the 'new' version already exists in output directory
            self.update_log('Skipping ' + fpath_in + '\n\t(trimmed version already exists in output directory)')
            return ()

        # otherwise, read input file and write output file
        fid_in = open(fpath_in, 'rb')
        fid_out = open(fpath_out, "wb")
        raw = fid_in.read()
        len_raw = len(raw)
        dg_start = 0  # datagram length field precedes datagram (dg is between STX and ETX, inclusive)

        dg_count = 0 # datagram counter
        rra_count = 0 # raw range angle 78 counter
        xyz_count = 0 # xyz88 counter
        sbi_count = 0 # seabed image counter
        blowout_count = 0

        while True:  # parse datagrams and copy those on the list
            if dg_start + 4 >= len_raw:  # break if EOF
                break

            dg_len = struct.unpack('I', raw[dg_start:dg_start + 4])[0]  # get dg length (before start of dg at STX)

            # continue to next iteration if dg length is insuffient to check for STX, ID, and ETX
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
                    # SBI = multibeam_tools.libs.readEM()

                if dg_ID == 78: # get fid_out pointer location at start of rra78 write
                    last_rra_write_start = fid_out.tell()

                if dg_ID == 88: # wait for next seabed image 89 datagram
                    last_xyz_write_start = fid_out.tell()

                fid_out.write(raw[dg_start:dg_end])
                dg_start = dg_start + dg_len + 4  # reset pointer to end of datagram if this had valid STX and ETX
                dg_count = dg_count + 1

                # print('found datagram ID', dg_ID, 'at datagram number', dg_count)

                if dg_ID == 78:
                    rra_count = rra_count + 1
                    # print('FOUND RRA78 number', rra_count, 'at datagram number', dg_count)

                if dg_ID == 88:
                    xyz_count = xyz_count + 1
                    # print('FOUND XYZ88 number', xyz_count, 'at datagram number', dg_count)
                    # print('wrote to output starting at ', last_xyz_write_start)
                    # print('dg_len in loop was', dg_len) # f.write length is dg_len + 4

                if dg_ID == 89:
                    sbi_count = sbi_count + 1
                    # print('FOUND SEABED IMAGE 89 number', sbi_count, 'at datagram number', dg_count)

                    SBI = multibeam_tools.libs.parseEM.SBI_89_dg(dg)  # parse the SBI datagram

                    # print(np.mean(SBI['AMPLITUDE']))
                    mean_amplitude = np.mean(SBI['AMPLITUDE'])
                    print('ping number', sbi_count, 'has amp', mean_amplitude)
                    # at this point, the thresholds are set by trial and error for the system
                    # amp below -450 (raw units in dg, not interpreted into dB) look abnormal in FMGT
                    if mean_amplitude > 0 or mean_amplitude < -400: # warn user of blowout
                        self.update_log('Blowout detected with mean amplitude ' + str(np.round(mean_amplitude)) +
                                        ' at ping ' + str(sbi_count))
                        fid_out.seek(last_rra_write_start) # seek start of most recent RRA datagram in output
                        fid_out.truncate() # truncate file, then carry on
                        blowout_count = blowout_count + 1

                continue

            # if not valid, move ahead by 1 and continue search
            dg_start = dg_start + 1

        self.update_log('Total pings : ' + str(sbi_count))
        self.update_log('Total blowouts: ' + str(blowout_count))
        self.update_log('Total pings after removal of blowouts: ' + str(sbi_count - blowout_count))
        # close input, output files and return
        fid_in.close()
        fid_out.close()
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
