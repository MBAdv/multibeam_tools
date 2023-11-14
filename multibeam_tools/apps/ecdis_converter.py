# -*- coding: utf-8 -*-
"""

Multibeam Echosounder Assessment Toolkit: Waypoint Converter

Export waypoint text files to several formats (to be expanded):
ECDIS   .lst
SIS     .asciiplan

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

__version__ = "0.0.4"  # ECDIS (LST, Atlantis CSV, Nuyina RTZ), ASCIIPLAN, TXT exports

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
        self.wp = {}  # dict of waypoint dicts
        self.output_ext = {'SIS': '.asciiplan',
                           'ECDIS_LST': '.lst',
                           'ECDIS_CSV': '.csv',
                           'ECDIS_RTZ': '.rtz',
                           'DDD': '.txt',
                           'DMM': '.txt',
                           'DMS': '.txt',
                           'DDD_labeled': '.txt',
                           'DMM_labeled': '.txt',
                           'DMS_labeled': '.txt',
                           }  # dict of file types and file extensions

        # set up layouts of main window
        self.set_main_layout()

        # set up file control actions
        self.add_file_btn.clicked.connect(lambda: self.add_files('waypoints (*.txt)'))
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
        self.wp_pairs_chk = CheckBox('Waypoint pairs', False, 'wp_pairs_chk',
                                     'Treat waypoints as pairs (e.g., separate survey lines with gaps) if the output'
                                     'format supports this arrangement\n\n'
                                     'This matters for some formats to allow gaps between pairs of waypoints (e.g., '
                                     'separate survey lines in SIS .asciiplan), rather than connecting all segments\n\n'
                                     'This option does not impact sequential waypoint formats (e.g., ECDIS .lst)\n\n'
                                     'Do not select this option for continuous survey lines with connected segments\n\n'
                                     'WARNING: For odd numbers of waypoints, the last waypoint will be ignored if this '
                                     'option is checked (i.e., last waypoint is missing its pair')

        # set the file control options
        file_btn_layout = BoxLayout([self.add_file_btn, self.get_indir_btn, self.get_outdir_btn,
                                     self.rmv_file_btn, self.clr_file_btn, self.convert_btn, self.show_path_chk,
                                     self.overwrite_chk, self.wp_pairs_chk], 'v')
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
        self.update_log('*** New Waypoint Converter log ***\n'
                        '\nFor best results, ensure input .txt files follow the expected style:\n'
                        '\t1. One waypoint per line with a consistent format\n'
                        '\t2. DD.DDD or DD MM.MMM format (+/-, no hemisphere label)\n'\
                        '\t3. Order is [optional_label], lat, lon\n'\
                        '\t4. Space-, tab-, or comma-delimited\n'
                        '\t5. Labels should not includes spaces or special characters\n'
                        '\nExamples of some acceptable input formats:\n'
                        '\tWP_1 23.456 -67.891\n'
                        '\t45 52.317 13 12.660\n'
                        '\t12.5654224,39.4324278\n'
                        '\tStartHere  -62     13.49   9 57.42\n'
                        '\tEnd_survey,34,21.545,-89,56.274\n'
                        '\nWaypoints will be numbered if labels are not included\n'
                        '\nExports include:\n'
                        '\t.txt (DDD, DMM, and DMS)\n'
                        '\t.asciiplan (SIS line planning)\n'
                        '\t.csv, .lst, and .rtz (ECDIS and others)\n'
                        '\nUser warnings:\n'
                        '\t*USERS ARE RESPONSIBLE FOR VERIFYING INPUT AND EXPORT DATA FOR SAFE NAVIGATION*\n'
                        '\t*Waypoints labels are parsed but not applied to ECDIS .rtz export at present*\n'
                        '\t*Generic vessel name, MMSI, IMO, and other params are applied to ECDIS .rtz at present*\n'
                        '\t*ECDIS exports based on examples from users; no guarantee of accuracy or applicability*\n'
                        '\t*Feedback, bug reports, and examples of new formats are welcome at mac-help@unols.org*\n')

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
            if fname.rsplit('.', 1)[0]:  # add only if name exists prior to ext (may slip by splitext if adding dir)
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

    def convert_files(self):  # convert waypoint text files all available output formats
        self.update_log('Starting conversions process...')
        self.fcount_converted = 0
        self.fcount_skipped = 0

        fnames = self.get_new_file_list(['.txt'])  # get updated list of input files
        self.update_log('Converting ' + str(len(fnames)) + ' file' + ('s' if len(fnames) > 1 else '') + '\n')

        f = 0
        self.calc_pb.setValue(f)  # reset progress bar to 0 and max to number of files
        self.calc_pb.setMaximum(len(fnames))

        for fpath_in in fnames:
            fpath_in = os.path.abspath(fpath_in)
            fname_in = os.path.basename(fpath_in)
            self.read_text_wp(fpath_in)
            self.write_ASCIIPLAN(fpath_in)
            self.write_ECDIS_LST(fpath_in)
            self.write_ECDIS_CSV(fpath_in)
            self.write_TXT(fpath_in)
            self.write_ECDIS_RTZ(fpath_in)
            f = f + 1
            self.update_prog(f)
            self.fcount_converted += 1
            self.update_log('Finished converting ' + fname_in + '\n')

        self.update_log('Finished processing ' + str(f) + ' file' + ('s' if f > 1 else '') + '\n')

    def create_fpath_out(self, fpath_in, ftype):  # create the output path for this input file
        fname_in = os.path.basename(fpath_in)
        fdir_in = os.path.dirname(fpath_in)
        fname_out = fname_in.rsplit('.', 1)[0] + '_' + ftype + self.output_ext[ftype]

        if self.output_dir:  # write files to selected output directory if selected
            fpath_out = os.path.join(self.output_dir, fname_out)

        else:  # write files back to each source file location if an output directory is not selected
            fpath_out = os.path.join(fdir_in, fname_out)  # create new file at same location as input text file

        fpath_out = os.path.abspath(fpath_out)

        if os.path.exists(fpath_out):  # check if intended output fname already exists
            if not self.overwrite_chk.isChecked():  # output fname exists; return if the overwrite option is not checked
                self.update_log('***Skipping file because ' + ftype + ' output already exists: ' + fname_in)
                self.update_log('***Select "Overwrite files" to overwrite existing files.\n')

                self.fcount_skipped += 1
                return ()

        return fpath_out

    def read_text_wp(self, fpath_in):  # read .txt files and store waypoints as list
        fpath_in = os.path.abspath(fpath_in)
        fname_in = os.path.basename(fpath_in)
        fid_in = open(fpath_in, 'r')  # open source file
        wp_temp = {'fname': fname_in, 'label': [],
                   'lat_deg': [], 'lat_min': [], 'lat_ddd': [], 'lat_hem': [],
                   'lon_deg': [], 'lon_min': [], 'lon_ddd': [], 'lon_hem': [],
                   'continuous_line': True}

        lat_hem = ['S', 'N']
        lon_hem = ['W', 'E']

        wp_num = 1
        txt_line_num = 0

        for line in fid_in:  # read each line and store in wp_temp dict
            txt_line_num += 1  # increment line counter for text file
            # strip and split space- or comma-delimited line; append '0' to list in case uncertainty field is not avail
            temp = line.replace(',', ' ').strip().rstrip().split()
            label = str(wp_num)  # placeholder label based on waypoint number; replaced with text label if found later

            if len(temp) % 2 == 1:  # odd number of fields, assume first field is a label
                label = temp[0]

            if len(temp) in [2, 3]:  # assume lat lon in DD.DDD format, possibly with a label on each line
                lat_DDD = float(temp[-2])
                lat_D = float(temp[-2].split('.')[0])
                lat_M = 60 * abs(float(temp[-2]) - lat_D)

                lon_DDD = float(temp[-1])
                lon_D = float(temp[-1].split('.')[0])
                lon_M = 60 * abs(float(temp[-1]) - lon_D)

            elif len(temp) in [4, 5]:  # assume label lat lon in DD MM.MM format
                lat_D = float(temp[-4])
                lat_M = float(temp[-3])
                lon_D = float(temp[-2])
                lon_M = float(temp[-1])

                # convert to decimal deg
                lat_DDD = abs(lat_D) + lat_M/60
                if lat_D < 0:
                    lat_DDD *= -1

                lon_DDD = abs(lon_D) + lon_M/60
                if lon_D < 0:
                    lon_DDD *= -1

            elif len(temp) == 0:  # nothing to see here
                continue

            else:  # this line has the wrong number of fields... skip it and warn the user
                self.update_log('***WARNING***: error parsing text file line ' + str(txt_line_num) + ': ' + line + \
                                '\n\tThis line will not be included in the output file!' + \
                                '\n\tSee first message in this log window for format requirements.\n')
                continue

            # store info for this waypoint
            wp_temp['label'].append(label)

            wp_temp['lat_ddd'].append(lat_DDD)
            wp_temp['lat_deg'].append(lat_D)
            wp_temp['lat_min'].append(lat_M)
            wp_temp['lat_hem'].append(lat_hem[int(lat_DDD >= 0)])

            wp_temp['lon_ddd'].append(lon_DDD)
            wp_temp['lon_deg'].append(lon_D)
            wp_temp['lon_min'].append(lon_M)
            wp_temp['lon_hem'].append(lon_hem[int(lon_DDD >= 0)])

            wp_num += 1  # increment for next waypoint

        # get letter corresponding to waypoint for writing alpha-labeled outputs [A,B,C...X,Y,Z,A2,B2,B3... etc.]
        letter_label = [chr(ord('@')+i%26+1) + str(int(i/26)+1) if i >= 26 \
                            else chr(ord('@')+i%26 + 1) for i in range(0,len(wp_temp['label']))]
        print('got letter_label = ', letter_label)
        wp_temp['letter'] = letter_label
        self.wp[fname_in] = wp_temp  # store waypoint dict

        return ()


    def write_TXT(self, fpath_in):  # write text files with DDD, DMM, and DMS formats
        fname_in = os.path.basename(fpath_in)

        try:
            # sequential waypoints, numbered
            fid_ddd = open(self.create_fpath_out(fpath_in, 'DDD'), 'w')
            fid_dmm = open(self.create_fpath_out(fpath_in, 'DMM'), 'w')
            fid_dms = open(self.create_fpath_out(fpath_in, 'DMS'), 'w')

            # sequential waypoint, labeled or lettered if label is not available
            fid_ddd2 = open(self.create_fpath_out(fpath_in, 'DDD_labeled'), 'w')  # labeled A, B, C, etc.
            fid_dmm2 = open(self.create_fpath_out(fpath_in, 'DMM_labeled'), 'w')  # labeled A, B, C, etc.
            fid_dms2 = open(self.create_fpath_out(fpath_in, 'DMS_labeled'), 'w')  # labeled A, B, C, etc.
        except:
            print('No fids for TXT formats')
            return

        wp = self.wp[fname_in]

        for wp_num in range(len(wp['label'])):  # read each waypoint, convert to ECDIS format, and write to .lst file
            lat_sec = wp['lat_min']
            lat_sign = ['-',''][wp['lat_ddd'][wp_num] > 0]  # get sign to fix ambiguity in DD MM format if DD=0
            lon_sign = ['-',''][wp['lon_ddd'][wp_num] > 0]
            lat_sec = '{:0.3f}'.format(60*(wp['lat_min'][wp_num]%1))  # latitude seconds
            lon_sec = '{:0.3f}'.format(60*(wp['lon_min'][wp_num]%1))  # longitude seconds

            # write numbered outputs (alternative wp label is used if parsed from wp input)
            fid_ddd.write('\t'.join([wp['label'][wp_num],\
                                     lat_sign+str(abs(wp['lat_ddd'][wp_num])),\
                                     lon_sign+str(abs(wp['lon_ddd'][wp_num])),\
                                     '\n']))
            fid_dmm.write('\t'.join([wp['label'][wp_num],\
                                     lat_sign+str(abs(int(wp['lat_deg'][wp_num]))),'{:0.4f}'.format(wp['lat_min'][wp_num]),\
                                     lon_sign+str(abs(int(wp['lon_deg'][wp_num]))),'{:0.4f}'.format(wp['lon_min'][wp_num]),\
                                     '\n']))
            fid_dms.write('\t'.join([wp['label'][wp_num],\
                                     lat_sign+str(abs(int(wp['lat_deg'][wp_num]))),str(int(wp['lat_min'][wp_num])),lat_sec,\
                                     lon_sign+str(abs(int(wp['lon_deg'][wp_num]))),str(int(wp['lon_min'][wp_num])),lon_sec,\
                                     '\n']))

            # write lettered outputs
            fid_ddd2.write('\t'.join([wp['letter'][wp_num],
                                      lat_sign+str(abs(wp['lat_ddd'][wp_num])),\
                                      lon_sign+str(abs(wp['lon_ddd'][wp_num])),'\n']))
            fid_dmm2.write('\t'.join([wp['letter'][wp_num],\
                                      lat_sign+str(abs(int(wp['lat_deg'][wp_num]))),'{:0.4f}'.format(wp['lat_min'][wp_num]),\
                                      lon_sign+str(abs(int(wp['lon_deg'][wp_num]))),'{:0.4f}'.format(wp['lon_min'][wp_num]),\
                                      '\n']))
            fid_dms2.write('\t'.join([wp['letter'][wp_num],\
                                      lat_sign+str(abs(int(wp['lat_deg'][wp_num]))),str(int(wp['lat_min'][wp_num])),lat_sec,\
                                      lon_sign+str(abs(int(wp['lon_deg'][wp_num]))),str(int(wp['lon_min'][wp_num])),lon_sec,\
                                      '\n']))
        fid_ddd.close()
        fid_dmm.close()
        fid_dms.close()
        fid_ddd2.close()
        fid_dmm2.close()
        fid_dms2.close()
        self.fcount_converted += 1
        self.update_log('Converted ' + fname_in +
                        '\n\t                       to ' + '_DDD, _DMM, _DMS text formats\n')

        return ()


    def write_ECDIS_CSV(self, fpath_in):  # write ECDIS CSV format (provided by Shannon Hoy on R/V Atlantis, March 2023)
        fname_in = os.path.basename(fpath_in)

        try:
            fid_ecdis_csv = open(self.create_fpath_out(fpath_in, 'ECDIS_CSV'), 'w')
        except:
            print('no FID for ECDIS_CSV format')
            return

        # ECDIS parameters from Atlantis example (descriptions not provided)
        port_NM = '0.10'
        stbd_NM = '0.10'
        arr_rad_NM = '0.10'
        speed_kn = '011.0'
        sail_RL_GC = 'RL'
        rot_deg_min = '105.04'
        turn_rad_NM = '0.10'
        time_zone = '05:00'
        name = 'E'
        current_time = datetime.datetime.strftime(datetime.datetime.now(),"%Y-%m-%d %H:%M:%S")

        wp = self.wp[fname_in]

        for wp_num in range(len(wp['label'])):  # read each waypoint, convert to ECDIS format, and write to .lst file
            # format decimal degree strings
            ECDIS_lat_d = str(int(abs(wp['lat_deg'][wp_num])))  # integer degree
            ECDIS_lat_m = '{:0.3f}'.format(abs(wp['lat_min'][wp_num]))  # min to 3 decimals (max allowed)
            ECDIS_lon_d = str(int(abs(wp['lon_deg'][wp_num])))  # integer degree
            ECDIS_lon_m = '{:0.3f}'.format(abs(wp['lon_min'][wp_num]))  # min to 3 decimals (max allowed)
            ECDIS_wp_num = str(int(wp_num))

            # create sections of each waypoint string per Atlantis example
            ECDIS_str1 = ','.join([ECDIS_wp_num,\
                                   ECDIS_lat_d, ECDIS_lat_m, wp['lat_hem'][wp_num],\
                                   ECDIS_lon_d, ECDIS_lon_m, wp['lon_hem'][wp_num]])
            ECDIS_str2 = ','.join([port_NM, stbd_NM, arr_rad_NM, speed_kn, sail_RL_GC,
                                   rot_deg_min, turn_rad_NM, time_zone, name])

            # write first line with header info from Atlantis example)
            if wp_num == 0:
                fid_ecdis_csv.write('// ROUTE SHEET exported by JRC ECDIS.\n')
                fid_ecdis_csv.write('// << NOTE >> This strings // indicate comment column/cells. ')
                fid_ecdis_csv.write('You can edit freely.\n')
                fid_ecdis_csv.write('// ' + current_time + '<Normal>,SURVEY\n')
                fid_ecdis_csv.write('// WPT No.,LAT,,,LON,,,PORT[NM],STBD[NM],Arr. Rad[NM],')
                fid_ecdis_csv.write('Speed[kn],Sail(RL/GC),ROT[deg/min],Turn Rad[NM],Time Zone,,Name\n')
                ECDIS_str2 = '***,***,***,***,***,***,***,' + time_zone + ',' + name  # first WP has *** for many fields

            fid_ecdis_csv.write(ECDIS_str1 + ',' + ECDIS_str2 + ',\n')  # write wp format from Atlantis exampl

        fid_ecdis_csv.close()
        self.fcount_converted += 1
        self.update_log('Converted ' + fname_in +
                        '\n\t                       to ' + os.path.basename(fid_ecdis_csv.name) + '\n')

        return ()

    def write_ECDIS_LST(self, fpath_in):  # write LST format from self.wp as sequential wp (pairing does not matter)
        fname_in = os.path.basename(fpath_in)

        try:
            fid_ecdis = open(self.create_fpath_out(fpath_in, 'ECDIS_LST'), 'w')
        except:
            print('No fid for ECDIS_LST format')
            return

        # ECDIS parameters
        lane_deviation_0_01NM = '2'  # lane deviation in 0.01 NM
        turn_rad_0_01NM = '1'  # turn radius in 0.01 NM
        speed_0_1kt = '60'  # speed in 0.1 kt; 6 kts initial test speed FKt SAT
        stop_time_minutes = '0'  # waypoint stop time in minutes
        route_type = 'L'  # G = great circle, L = Loxodrome
        warning_type = 'N'  # warning type T = time, D = distance, N = none
        warning_min_NM = '0'  # warning in minutes or NM

        wp = self.wp[fname_in]

        for wp_num in range(len(wp['label'])):  # read each waypoint, convert to ECDIS format, and write to .lst file
            # format D M strings with zero padding required for ECDIS format
            lat_D_str = '{:02.0f}'.format(abs(wp['lat_deg'][wp_num]))
            lat_M_str = '{:02.3f}'.format(wp['lat_min'][wp_num])
            lon_D_str = '{:03.0f}'.format(abs(wp['lon_deg'][wp_num]))
            lon_M_str = '{:02.3f}'.format(wp['lon_min'][wp_num])

            # smash together for DDDMM.MMM format
            ECDIS_lat = lat_D_str + lat_M_str
            ECDIS_lon = lon_D_str + lon_M_str

            ECDIS_str1 = ','.join([ECDIS_lat, wp['lat_hem'][wp_num], ECDIS_lon, wp['lon_hem'][wp_num]])
            ECDIS_str2 = ','.join([lane_deviation_0_01NM, turn_rad_0_01NM, speed_0_1kt])
            ECDIS_str3 = ','.join([stop_time_minutes, route_type, warning_type, warning_min_NM])

            # write first line with header info (first parts of first wp, code 9 instead of 8, based on FKt example)
            if wp_num == 0:
                fid_ecdis.write('$PTLKR,0,0,' + fname_in.split('.')[0] + '\n')
                fid_ecdis.write('$PTLKP,8,' + ECDIS_str1 + ',' + ECDIS_str2 + '\n')  # .lst header based on wp 1

            fid_ecdis.write('$PTLKP,9,' + ECDIS_str1 + ',' + ECDIS_str2 + ',' + ECDIS_str3 + '\n')  # write wp DATA
            fid_ecdis.write('$PTLKI,' + wp['label'][wp_num] + '\n')  # write wp INFO

        fid_ecdis.close()
        self.fcount_converted += 1
        self.update_log('Converted ' + fname_in +
                        '\n\t                       to ' + os.path.basename(fid_ecdis.name) + '\n')

        return ()


    def write_ASCIIPLAN(self, fpath_in):  # write ASCIIPLAN format from self.wp sequentially or as pairs, if selected
        fname_in = os.path.basename(fpath_in)

        try:
            fid_sis = open(self.create_fpath_out(fpath_in, 'SIS'), 'w')
        except:
            print('No fid for SIS format')
            return

        wp = self.wp[fname_in]
        line_num = 0  # line number (will start at 1 in output)
        wp_num = 0  # waypoint number starting at 0 for python indexing

        while wp_num+1 < len(wp['label']): # read each waypoint pair, convert to SIS format, write to .asciiplan file
            line_num += 1  # increment line number

            if wp_num == 0:  # SIS header
                fid_sis.write('DEG\n\n0 0 0 0\n')

            line_str = '_LINE Line_' + str(line_num)  # basic line number (future: add labels for patch tests, etc.)
            time_str = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
            line_hdr = line_str + ' ' + str(line_num) + ' ' + time_str + ' 0'
            wp_start_str = '{:0.8f}'.format(wp['lat_ddd'][wp_num])   + ' ' + '{:0.8f}'.format(wp['lon_ddd'][wp_num])
            wp_end_str =   '{:0.8f}'.format(wp['lat_ddd'][wp_num+1]) + ' ' + '{:0.8f}'.format(wp['lon_ddd'][wp_num+1])
            wp_str = wp_start_str + ' ' + wp_end_str + ' "'

            fid_sis.write(line_hdr + ' ' + wp_str + '\n')

            wp_num += 1 + int(self.wp_pairs_chk.isChecked())  # increment by 1 if sequential, 2 if treating as wp pairs

        fid_sis.close()
        self.fcount_converted += 1
        self.update_log('Converted ' + fname_in +
                        '\n\t                       to ' + os.path.basename(fid_sis.name) + '\n')

        return ()

    def write_ECDIS_RTZ(self, fpath_in):  # write RTZ v1.0 from self.wp as sequential waypoint (I/B Nuyina, Nov 2023)
        fname_in = os.path.basename(fpath_in)
        try:
            fid_rtz = open(self.create_fpath_out(fpath_in, 'ECDIS_RTZ'), 'w')
        except:
            print('No fid for RTZ format')
            return

        # Version parameters; see https://www.cirm.org/rtz/RTZ%20Schema%20version%201_2.xsd for v1.2 reference
        version = '"1.0"'
        encoding = '"UTF-8"'
        xmlns_xsi = '"http://www.w3.org/2001/XMLSchema-instance"'
        xmlns = '"http://www.cirm.org/RTZ/1/0"'
        xsi_schemaLocation = '"http://www.cirm.org/RTZ/1/0"'
        routeName = '"' + fname_in.split('.')[0] + '"'
        vesselName = '"VESSEL"'  # ADD USER INPUT FIELDS FOR VESSEL INFO
        vesselMMSI = '"000000000"'  # ADD USER INPUT FIELDS FOR VESSEL INFO
        vesselIMO = '"0000000"'  # ADD USER INPUT FIELDS FOR VESSEL INFO
        xmlns_xsd = '"http://www.w3.org/2001/XMLSchema"'

        manufacturer = '"SESAME Straits"'
        name = '"SesameRouteInfoExtension"'
        xmlns_extension = '"http://www.straits-stms.com/SESAME/1/0"'
        status_extension = '"Undefined"'
        revision_extension = '"1"'

        # Route parameters (default from Icebreaker Nuyina example provided Nov 2023; FUTURE: ADD USER INPUTS)
        radius_NM = '"0.1100"'  # radius in NM (radius for turn? waypoint completion?)
        radius_start_end = '"1.0000"'  # radius for start or end waypoint
        starboardXTD_NM = '"0.0270"'  # xtrack distance to starboard in NM
        portsideXTD_NM = '"0.0270"'  # xtrack distance to port in NM
        speedMin = '"1.00"'  # lowest cruising speed in kn
        geometryType = '"Loxodrome"'

        wp = self.wp[fname_in]

        for wp_num in range(len(wp['label'])):  # read each waypoint, convert to ECDIS format, and write to .lst file
            lat = '{:0.6f}'.format(wp['lat_ddd'][wp_num])
            lon = '{:0.6f}'.format(wp['lon_ddd'][wp_num])
            label = wp['label'][wp_num]

            # write header info (based on I/B Nuyina example)
            if wp_num == 0:
                fid_rtz.write('<?xml version=' + version + ' encoding=' + encoding + '?>\n\n')
                fid_rtz.write('<route xmlns:xsi=' + xmlns_xsi + ' xmlns=' + xmlns + ' version=' + version +
                              ' xsi:schemaLocation=' + xsi_schemaLocation +'>\n')
                fid_rtz.write('\t<routeInfo routeName=' + routeName + ' vesselName=' + vesselName +
                              ' vesselMMSI=' + vesselMMSI + ' vesselIMO=' + vesselIMO + '>\n')
                fid_rtz.write('\t\t<extensions>\n')
                fid_rtz.write('\t\t\t<routeInfoExtension xmlns:xsd=' + xmlns_xsd + ' xmlns:xsi=' + xmlns_xsi +
                              ' manufacturer=' + manufacturer + ' name=' + name + ' version=' +version +
                              ' xmlns=' + xmlns_extension + '>\n')
                fid_rtz.write('\t\t\t\t<routeInfo status=' + status_extension + ' revision=' + revision_extension +
                              '/>\n')
                fid_rtz.write('\t\t\t</routeInfoExtension>\n')
                fid_rtz.write('\t\t</extensions>\n')
                fid_rtz.write('\t</routeInfo>\n')

                # write start of waypoints
                fid_rtz.write('\t<waypoints>\n')

                # write default waypoint
                fid_rtz.write('\t\t<defaultWaypoint>\n')
                fid_rtz.write('\t\t\t<leg geometryType=' + geometryType + ' starboardXTD=' + starboardXTD_NM +
                            ' portsideXTD=' + portsideXTD_NM + '/>\n')
                fid_rtz.write('\t\t</defaultWaypoint>\n')

            # write current waypoint
            radius = [radius_NM, radius_start_end][int(wp_num in [0, len(wp['label'])-1])]  # start/end radius if nec.
            fid_rtz.write('\t\t<waypoint id="' + str(wp_num+1) + '" radius=' + radius + ' name="' + label + '">\n')
            fid_rtz.write('\t\t\t<position lat="' + lat + '" lon="' + lon + '"/>\n')
            fid_rtz.write('\t\t\t<leg speedMin=' + speedMin + '/>\n')
            fid_rtz.write('\t\t</waypoint>\n')

        # write end of waypoints
        fid_rtz.write('\t</waypoints>\n')
        fid_rtz.write('</route>\n')

        fid_rtz.close()
        self.fcount_converted += 1
        self.update_log('Converted ' + fname_in +
                        '\n\t                       to ' + os.path.basename(fid_rtz.name) + '\n')

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
