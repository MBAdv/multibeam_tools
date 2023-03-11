# -*- coding: utf-8 -*-
"""

Multibeam Echosounder Assessment Toolkit: ECDIS Converter

Export waypoint text files to ECDIS .lst format

Input: simple .txt file(s) of waypoints in [lat lon] format, with one waypoint per line

Each waypoint must be decimal degrees or decimal minutes, positive for N/E and negative for S/W.
Latitude is listed before longitude (future: option to flip order).

Acceptable waypoint formats include lat lon in decimal degrees or decimal minutes:

DD.DDD: 23.500 -145.600
DD MM.MMM: 23 30.000 -145 36.000

A label may be included at the start of a line (default: waypoint number will be assigned if no label is provided).

If provided, labels must not include spaces or special characters that could be construed as delimiters.

Space-, tab-, and comma-delimited files are acceptable.

It is assumed that only [optional label], lat, and lon are included in each line of the text file.
This results in a maximum of five fields when using decimal minutes. Lines with more than five fields will be skipped.


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
# import struct
import sys

# add path to external module common_data_readers for pyinstaller
sys.path.append('C:\\Users\\kjerram\\Documents\\GitHub')

from multibeam_tools.libs.gui_widgets import *

__version__ = "0.0.0"  # next release with concatenation option


class MainWindow(QtWidgets.QMainWindow):
    media_path = os.path.join(os.path.dirname(__file__), "media")

    def __init__(self, parent=None):
        super(MainWindow, self).__init__()

        # set up main window
        self.mainWidget = QtWidgets.QWidget(self)
        self.setCentralWidget(self.mainWidget)
        self.setMinimumWidth(800)
        self.setMinimumHeight(500)
        self.setWindowTitle('ECDIS Converter v.%s' % __version__)
        self.setWindowIcon(QtGui.QIcon(os.path.join(self.media_path, "icon.png")))

        if os.name == 'nt':  # necessary to explicitly set taskbar icon
            import ctypes
            current_app_id = 'MAC.ECDISConverter.' + __version__  # arbitrary string
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(current_app_id)

        # initialize other necessities
        self.filenames = ['']
        self.input_dir = ''
        self.output_dir = ''
        self.output_dir_old = ''
        self.fcount_skipped = 0

        # set up layouts of main window
        self.set_main_layout()

        # set up file control actions
        self.add_file_btn.clicked.connect(lambda: self.add_files('waypoints (*.txt)'))
        # self.add_file_btn.clicked.connect(lambda: self.add_files('Kongsberg (*.all)'))  # .kmall trim method not ready
        self.get_indir_btn.clicked.connect(self.get_input_dir)
        self.rmv_file_btn.clicked.connect(self.remove_files)
        self.clr_file_btn.clicked.connect(self.clear_files)
        self.get_outdir_btn.clicked.connect(self.get_output_dir)
        self.convert_btn.clicked.connect(self.convert_files)
        self.show_path_chk.stateChanged.connect(self.show_file_paths)

    def set_main_layout(self):
        # set layout with file controls on right, sources on left, and progress log on bottom
        btnh = 20  # height of file control button
        btnw = 100  # width of file control button

        # add file control buttons
        self.add_file_btn = PushButton('Add Files', btnw, btnh, 'add_file_btn', 'Add files')
        self.get_indir_btn = PushButton('Add Directory', btnw, btnh, 'get_indir_btn', 'Add a directory')
        self.get_outdir_btn = PushButton('Select Output Dir.', btnw, btnh, 'get_outdir_btn',
                                         'Select the output directory (see current directory below)')
        self.rmv_file_btn = PushButton('Remove Selected', btnw, btnh, 'rmv_file_btn', 'Remove selected files')
        self.clr_file_btn = PushButton('Remove All Files', btnw, btnh, 'clr_file_btn', 'Remove all files')
        self.convert_btn = PushButton('Convert Files', btnw, btnh, 'convert_btn', 'Convert files in source list')
        self.show_path_chk = CheckBox('Show file paths', False, 'show_paths_chk')
        self.overwrite_chk = CheckBox('Overwrite files', False, 'overwrite_chk',
                                      'Overwrite existing ECDIS files with the same name.')

        # set the file control options
        file_btn_layout = BoxLayout([self.add_file_btn, self.get_indir_btn, self.get_outdir_btn,
                                     self.rmv_file_btn, self.clr_file_btn, self.convert_btn, self.show_path_chk, self.overwrite_chk], 'v')
        file_btn_layout.addStretch()
        self.file_control_gb = QtWidgets.QGroupBox('File Control')
        self.file_control_gb.setLayout(file_btn_layout)

        # set right layout with proc path on top, file control, and advanced options below
        right_layout = BoxLayout([self.file_control_gb], 'v')

        # add file list
        self.file_list = QtWidgets.QListWidget()
        self.file_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.file_list.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.MinimumExpanding)
        self.file_list.setIconSize(QSize(0, 0))  # set icon size to 0,0 or file names (from item.data) will be indented
        self.file_list_layout = BoxLayout([self.file_list], 'v')
        self.file_list_gb = QtWidgets.QGroupBox('Sources')
        self.file_list_gb.setLayout(self.file_list_layout)
        self.file_layout = BoxLayout([self.file_list_gb, right_layout], 'h')

        # add activity log widget
        self.log = QtWidgets.QTextEdit()
        self.log.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding,
                               QtWidgets.QSizePolicy.MinimumExpanding)
        self.log.setStyleSheet("background-color: lightgray")
        self.log.setReadOnly(True)
        self.update_log('*** New ECDIS converter log ***\n'
                        '\nFor best results, ensure .txt files follow the expected style:\n'
                        '\t1. One waypoint per line with a consistent format\n'
                        '\t2. DD.DDD or DD MM.MMM format (+/-, no hemisphere label)\n'\
                        '\t3. Order is [optional_label], lat, lon\n'\
                        '\t4. Space-, tab-, or comma-delimited\n'
                        '\t5. Labels should not includes spaces or special characters\n'
                        '\nExamples of some acceptable formats:\n'
                        '\tWP_1 23.456 -67.891\n'
                        '\t45 52.317 13 12.660\n'
                        '\t12.5654224,39.4324278\n'
                        '\tStartHere  -62     13.49   9 57.42\n'
                        '\tEnd_survey,34,21.545,-89,56.274\n'
                        '\nWaypoints will be numbered if labels are not included\n')

        # add progress bar below file list
        self.current_outdir_lbl = QtWidgets.QLabel('Current output directory:')
        self.calc_pb_lbl = QtWidgets.QLabel('Total Progress:')
        self.calc_pb = QtWidgets.QProgressBar()
        self.calc_pb.setGeometry(0, 0, 200, 30)
        self.calc_pb.setMaximum(100)  # this will update with number of files
        self.calc_pb.setValue(0)
        self.calc_pb_layout = BoxLayout([self.calc_pb_lbl, self.calc_pb], 'h')
        self.prog_layout = BoxLayout([self.current_outdir_lbl, self.calc_pb_layout], 'v')

        # set the log and prog bar layout
        self.log_layout = BoxLayout([self.log, self.prog_layout], 'v')
        self.log_gb = QtWidgets.QGroupBox('Activity Log')
        self.log_gb.setLayout(self.log_layout)
        self.log_gb.setMinimumWidth(800)
        self.log_gb.setMinimumHeight(400)

        # set the main layout with file list on left, file control on right, and log on bottom
        main_layout = BoxLayout([self.file_layout, self.log_gb], 'v')
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


    def show_file_paths(self):
        # show or hide path for all items in file_list according to show_paths_chk selection
        for i in range(self.file_list.count()):
            [path, fname] = self.file_list.item(i).data(1).rsplit('/', 1)  # split full file path from item data, role 1
            self.file_list.item(i).setText((path+'/')*int(self.show_path_chk.isChecked()) + fname)

    def get_input_dir(self):
        # get directory of files to load
        try:
            self.input_dir = QtWidgets.QFileDialog.getExistingDirectory(self, 'Add directory', os.getenv('HOME'))
            self.update_log('Added directory: ' + self.input_dir)

            # get a list of all .txt files in that directory, '/' avoids '\\' in os.path.join in add_files
            self.update_log('Adding files in directory: ' + self.input_dir)
            self.add_files(['.txt'], input_dir=self.input_dir + '/')

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

            elif not self.output_dir_old:  # warn user if not selected but keep trim button enabled and old output dir
                self.update_log('No output directory selected')

        except:
            # warn user if failed and disable trim button until output directory is selected
            self.update_log('Failure selecting output directory')
            self.output_dir = ''
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
        fnames_txt = [f for f in self.filenames if '.txt' in f]

        if len(fnames_txt) == 0:
            self.update_log('All files have been removed.')

    def clear_files(self):  # clear all files from the file list and plot
        self.calc_pb.setValue(0)
        self.remove_files(clear_all=True)

    def get_current_file_list(self):  # get current list of files in qlistwidget
        list_items = []
        for f in range(self.file_list.count()):
            list_items.append(self.file_list.item(f))

        self.filenames = [f.data(1) for f in list_items]  # return list of full file paths stored in item data, role 1

    def get_new_file_list(self, fext=[''], flist_old=[]):
        # determine list of new files with file extension fext that do not exist in flist_old
        # flist_old may contain paths as well as file names; compare only file names
        self.get_current_file_list()
        fnames_ext = [fn for fn in self.filenames if any(ext in fn for ext in fext)]  # fnames (w/ paths) matching ext
        fnames_old = [fn.split('/')[-1] for fn in flist_old]  # file names only (no paths) from flist_old
        fnames_new = [fn for fn in fnames_ext if fn.split('/')[-1] not in fnames_old]  # check if fname in fnames_old

        return fnames_new  # return the fnames_new (with paths)

    def get_selected_file_list(self):
        # determine list of selected files with full file paths from current file list, not just text from GUI file list
        self.get_current_file_list()
        flist_sel = [f.text().split('/')[-1] for f in self.file_list.selectedItems()]  # selected fnames without paths
        fnames_sel = [fn for fn in self.filenames if fn.split('/')[-1] in flist_sel]  # full paths of selected files

        return fnames_sel  # return the fnames_new (with paths)

    def update_log(self, entry):  # update the activity log
        self.log.append(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' ' + entry)
        QtWidgets.QApplication.processEvents()

    def convert_files(self):  # convert waypoint text files to ECDIS .lst format
        self.update_log('Starting conversions process...')

        # update file size trackers
        self.fcount_converted = 0
        self.fcount_skipped = 0

        fnames = self.get_new_file_list(['.txt'])  # get updated list of input files
        self.update_log('Converting ' + str(len(fnames)) + ' file' + ('s' if len(fnames) > 1 else '') + '\n')

        # update progress bar and log
        f = 0
        self.calc_pb.setValue(f)  # reset progress bar to 0 and max to number of files
        self.calc_pb.setMaximum(len(fnames))

        # write trimmed version for each new file (initial code from Kongsberg, modified by UNH CCOM)
        for fpath_in in fnames:
            self.convert_to_LST(fpath_in)
            f = f + 1
            self.update_prog(f)

        self.update_log('Finished processing ' + str(f) + ' file' + ('s' if f > 1 else '') + '\n')


    def convert_to_LST(self, fpath_in):  # read .txt and make .lst
        fpath_in = os.path.abspath(fpath_in)
        fname_in = os.path.basename(fpath_in)
        fdir_in = os.path.dirname(fpath_in)
        fname_out = fname_in.rsplit('.', 1)[0] + '_ECDIS.lst'

        if self.output_dir:  # write files to selected output directory if selected
            fpath_out = os.path.join(self.output_dir, fname_out)

        else:  # write files back to each source file location if an output directory is not selected
            fpath_out = os.path.join(fdir_in, fname_out)  # create new ECDIS file at same location as input text file

        fpath_out = os.path.abspath(fpath_out)
        fname_out = os.path.basename(fpath_out)

        if os.path.exists(fpath_out):  # check if intended output fname already exists
            if not self.overwrite_chk.isChecked():  # output fname exists; return if the overwrite option is not checked
                self.update_log('***Skipping file because ECDIS output already exists: ' + fname_in)
                self.update_log('***Select "Overwrite files" to overwrite existing ECDIS files.\n')

                self.fcount_skipped += 1
                return ()

            # else:  # continue only if overwrite option is checked
                # self.update_log('***Overwriting ' + fname_out + '\n')

        file_ext = fpath_in.rsplit('.',1)[1]
        # print('found fpath_in ', fpath_in, ' with file_ext =', file_ext)

        fid_in = open(fpath_in, 'r')  # open source file
        fid_out = open(fpath_out, 'w')  # create output file

        # ECDIS parameters
        lane_deviation_0_01NM = '2'  # lane deviation in 0.01 NM
        turn_rad_0_01NM = '1'  # turn radius in 0.01 NM
        speed_0_1kt = '60'  # speed in 0.1 kt; 6 kts initial test speed FKt SAT
        stop_time_minutes = '0'  # waypoint stop time in minutes
        route_type = 'L'  # G = great circle, L = Loxodrome
        warning_type = 'N'  # warning type T = time, D = distance, N = none
        warning_min_NM = '0'  # warning in minutes or NM

        wp_num = 1
        txt_line_num = 0

        for line in fid_in:  # read each line, convert to ECDIS format, and write to .lst file
            txt_line_num += 1  # increment line counter for text file
            # strip and split space- or comma-delimited line; append '0' to list in case uncertainty field is not avail
            temp = line.replace(',', ' ').strip().rstrip().split()
            label = str(wp_num)  # placeholder label based on waypoint number; replaced with text label if found later

            if len(temp) % 2 == 1:  # odd number of fields, assume first field is a label
                label = temp[0]
                # print('got label = ', label)

            if len(temp) in [2, 3]:  # assume lat lon in DD.DDD format, possibly with labels
                lat_D = float(temp[-2].split('.')[0])
                # print('lat_D is', lat_D)
                lat_M = 60*abs(float(temp[-2]) - lat_D)
                # print('lat_M is', lat_M)
                lon_D = float(temp[-1].split('.')[0])
                # print('lon_D is', lon_D)
                lon_M = 60*abs(float(temp[-1]) - lon_D)
                # print('lon_M is', lon_M)

            elif len(temp) in [4,5]:  # assume label lat lon in DD.DDD format
                lat_D = float(temp[-4])
                lat_M = float(temp[-3])
                lon_D = float(temp[-2])
                lon_M = float(temp[-1])

            elif len(temp) == 0:  # nothing to see here
                continue

            else:  # this line has the wrong number of fields... skip it and warn the user
                self.update_log('***WARNING***: error parsing text file line ' + str(txt_line_num) + ': ' + line + \
                                '\n\tThis line will not be included in the ECDIS file!' + \
                                '\n\tSee first message in this log window for format requirements.\n')
                continue

            # get hemisphere from sign
            lat_hem = ['S', 'N']
            lon_hem = ['W', 'E']
            ECDIS_lat_hem = lat_hem[int(lat_D > 0)]
            ECDIS_lon_hem = lon_hem[int(lon_D > 0)]

            # format D M strings with zero padding required for ECDIS format
            lat_D_str = '{:02.0f}'.format(abs(lat_D))
            lat_M_str = '{:02.3f}'.format(lat_M)
            lon_D_str = '{:03.0f}'.format(abs(lon_D))
            lon_M_str = '{:02.3f}'.format(lon_M)

            # smash together for DDDMM.MMM format
            ECDIS_lat = lat_D_str + lat_M_str
            ECDIS_lon = lon_D_str + lon_M_str

            ECDIS_str1 = ','.join([ECDIS_lat, ECDIS_lat_hem, ECDIS_lon, ECDIS_lon_hem])
            ECDIS_str2 = ','.join([lane_deviation_0_01NM, turn_rad_0_01NM, speed_0_1kt])
            ECDIS_str3 = ','.join([stop_time_minutes, route_type, warning_type, warning_min_NM])

            # write first line with header info (first parts of first wp, code 9 instead of 8, based on FKt example)
            if wp_num == 1:
                fid_out.write('$PTLKR,0,0,' + fname_in.split('.')[0] + '\n')
                fid_out.write('$PTLKP,8,' + ECDIS_str1 + ',' + ECDIS_str2 + '\n')   # .lst header based on wp 1

            # write waypoint data
            fid_out.write('$PTLKP,9,' + ECDIS_str1 + ',' + ECDIS_str2 + ',' + ECDIS_str3 + '\n')

            # write waypoint info
            fid_out.write('$PTLKI,' + label + '\n')

            wp_num += 1  # increment for next waypoint

        fid_in.close()
        fid_out.close()
        self.fcount_converted += 1

        # get update log
        self.update_log('Converted ' + fname_in +
                        '\n\t                       to ' + fname_out + '\n')

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
