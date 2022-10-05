# -*- coding: utf-8 -*-
"""

Multibeam Echosounder Assessment Toolkit: APPS Processing File Picker

Purpose:
Select iXblue INS and GNSS files for processing with the APPS software package.

Process:
The user selects the intended survey time frame and directories with INS and GNSS files.
The app highlights the INS and GNSS files that can be expected to match the survey time frame.

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

# from common_data_readers.python.kongsberg.kmall import kmall
from multibeam_tools.libs.gui_widgets import *
from multibeam_tools.libs.file_fun import *
from multibeam_tools.libs.swath_fun import *
from multibeam_tools.libs.swath_coverage_lib import sortDetectionsCoverage
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.axis import Axis
from time import process_time
import matplotlib.dates as mdates


__version__ = "0.0.0"  # next release with concatenation option

class MainWindow(QtWidgets.QMainWindow):
	media_path = os.path.join(os.path.dirname(__file__), "media")

	def __init__(self, parent=None):
		super(MainWindow, self).__init__()

		# set up main window
		self.mainWidget = QtWidgets.QWidget(self)
		self.setCentralWidget(self.mainWidget)
		self.setMinimumWidth(600)
		self.setMinimumHeight(500)
		self.setWindowTitle('APPS File Picker v.%s' % __version__)
		self.setWindowIcon(QtGui.QIcon(os.path.join(self.media_path, "icon.png")))

		if os.name == 'nt':  # necessary to explicitly set taskbar icon
			import ctypes
			current_app_id = 'MAC.APPSFilePicker.' + __version__  # arbitrary string
			ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(current_app_id)

		# initialize other necessities
		self.filenames_EM = ['']
		self.filenames_INS = ['']
		self.filenames_GNSS = ['']
		self.input_dir_INS = ''
		self.input_dir_GNSS = ''
		self.start_time_utc = ''
		self.end_time_utc = ''

		# set up and layout main window
		self.setup()
		self.set_main_layout()

		# set up file control actions
		self.add_master_dir_btn.clicked.connect(lambda: self.add_master_dir())

		self.add_EM_dir_btn.clicked.connect(lambda:
											  self.add_apps_files(['.all', '.kmall'], input_dir=[],
																  include_subdir=self.incl_EM_subdir_chk.isChecked(),
																  file_list=self.EM_file_list,
																  show_path_chk=self.show_EM_path_chk))

		self.add_INS_dir_btn.clicked.connect(lambda:
											 self.add_apps_files(['.log'], input_dir=[],
																 include_subdir=self.incl_INS_subdir_chk.isChecked(),
																 file_list=self.INS_file_list,
																 show_path_chk=self.show_INS_path_chk))
		self.add_GNSS_dir_btn.clicked.connect(lambda:
											  self.add_apps_files(['.21_', '.22_'], input_dir=[],
																  include_subdir=self.incl_GNSS_subdir_chk.isChecked(),
																  file_list=self.GNSS_file_list,
																  show_path_chk=self.show_GNSS_path_chk))

		self.add_EM_files_btn.clicked.connect(lambda: self.add_apps_files('Kongsberg (*.all *.kmall)',
																		  file_list=self.EM_file_list,
																		  show_path_chk=self.show_EM_path_chk))

		self.add_INS_files_btn.clicked.connect(lambda: self.add_apps_files('PHINS (*.log)',
																		   file_list=self.INS_file_list,
																		   show_path_chk=self.show_INS_path_chk))

		self.add_GNSS_files_btn.clicked.connect(lambda: self.add_apps_files('Septentrio (*.2*)',
																			file_list=self.GNSS_file_list,
																			show_path_chk=self.show_GNSS_path_chk))

		self.show_EM_path_chk.stateChanged.connect(lambda:
												   self.show_source_file_paths(file_list=self.EM_file_list,
																			   show_path_chk=self.show_EM_path_chk))

		self.show_INS_path_chk.stateChanged.connect(lambda:
													self.show_source_file_paths(file_list=self.INS_file_list,
																				show_path_chk=self.show_INS_path_chk))

		self.show_GNSS_path_chk.stateChanged.connect(lambda:
													 self.show_source_file_paths(file_list=self.GNSS_file_list,
																				 show_path_chk=self.show_GNSS_path_chk))

		self.find_apps_files_btn.clicked.connect(lambda: self.find_apps_files())

	def setup(self):
		self.det = {}  # detection dict (new data) used for parsing EM files
		self.info = {'em':{'fname':[], 'start':[], 'stop':[]},
					 'ins':{'fname':[], 'start':[], 'stop':[]},
					 'gnss':{'fname':[], 'start':[], 'stop':[]}}  # dict for file names and times

	def set_main_layout(self):
		# set layout with file controls on right, sources on left, and progress log on bottom
		btnh = 20  # height of file control button
		btnw = 100  # width of file control button

		# add file control buttons
		self.add_master_dir_btn = PushButton('Add Survey Dir.', btnw, btnh, 'add_master_dir_btn',
											 'Add a single survey directory with all data; all subdirectories will be '
											 'searched and each data type (INS, GNSS, EM) will be added, if available')
		self.add_GNSS_dir_btn = PushButton('Add GNSS Dir.', btnw, btnh, 'add_gnss_dir_btn', 'Add GNSS directory')
		self.add_INS_dir_btn = PushButton('Add INS Dir.', btnw, btnh, 'add_ins_dir_btn', 'Add INS directory')
		self.add_EM_dir_btn = PushButton('Add EM Dir.', btnw, btnh, 'add_em_dir_btn', 'Add EM directory')
		self.add_GNSS_files_btn = PushButton('Add GNSS Files', btnw, btnh, 'add_gnss_files_btn', 'Add GNSS files')
		self.add_INS_files_btn = PushButton('Add INS Files', btnw, btnh, 'add_ins_files_btn', 'Add INS files')
		self.add_EM_files_btn = PushButton('Add EM Files', btnw, btnh, 'add_em_files_btn', 'Add EM files')
		self.show_GNSS_path_chk = CheckBox('Show GNSS file paths', False, 'show_GNSS_path_chk')
		self.show_INS_path_chk = CheckBox('Show INS file paths', False, 'show_INS_path_chk')
		self.show_EM_path_chk = CheckBox('Show EM file paths', False, 'show_EM_path_chk')
		self.incl_GNSS_subdir_chk = CheckBox('Incl. GNSS subdirectories', True, 'incl_GNSS_subdir_chk')
		self.incl_INS_subdir_chk = CheckBox('Incl. INS subdirectories', True, 'incl_INS_subdir_chk')
		self.incl_EM_subdir_chk = CheckBox('Incl. EM subdirectories', True, 'incl_EM_subdir_chk')
		self.find_apps_files_btn = PushButton('Find APPS Files', btnw, btnh, 'find_apps_files_btn', 'Find files for APPS proc.')
		self.grid_lines_toggle_chk = CheckBox('Show grid lines', True, 'show_grid_lines_chk', 'Show grid lines')

		# add INS file list
		self.INS_file_list = QtWidgets.QListWidget()
		self.INS_file_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
		self.INS_file_list.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.MinimumExpanding)
		self.INS_file_list.setIconSize(QSize(0, 0))  # set icon size to 0,0 or file names (from item.data) will be indented
		ins_btn_layout = BoxLayout([BoxLayout([self.add_INS_dir_btn, self.add_INS_files_btn], 'v'),
									BoxLayout([self.incl_INS_subdir_chk, self.show_INS_path_chk], 'v')], 'h')
		ins_layout = BoxLayout([ins_btn_layout, self.INS_file_list], 'v')
		ins_layout.addStretch()
		ins_gb = GroupBox('INS Sources', ins_layout, False, False, 'ins_file_list_gb')

		# add GNSS file list
		self.GNSS_file_list = QtWidgets.QListWidget()
		self.GNSS_file_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
		self.GNSS_file_list.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.MinimumExpanding)
		self.GNSS_file_list.setIconSize(QSize(0, 0))  # set icon size to 0,0 or file names (from item.data) will be indented
		gnss_btn_layout = BoxLayout([BoxLayout([self.add_GNSS_dir_btn, self.add_GNSS_files_btn], 'v'),
									 BoxLayout([self.incl_GNSS_subdir_chk, self.show_GNSS_path_chk], 'v')], 'h')
		gnss_layout = BoxLayout([gnss_btn_layout, self.GNSS_file_list], 'v')
		gnss_layout.addStretch()
		gnss_gb = GroupBox('GNSS Sources', gnss_layout, False, False, 'gnss_file_list_gb')

		# add sonar file layout for time selection
		self.EM_file_list = QtWidgets.QListWidget()
		self.EM_file_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
		self.EM_file_list.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.MinimumExpanding)
		self.EM_file_list.setIconSize(QSize(0, 0))  # set icon size to 0,0 or file names (from item.data) are indented
		em_btn_layout = BoxLayout([BoxLayout([self.add_EM_dir_btn, self.add_EM_files_btn], 'v'),
								   BoxLayout([self.incl_EM_subdir_chk, self.show_EM_path_chk], 'v')], 'h')
		em_layout = BoxLayout([em_btn_layout, self.EM_file_list], 'v')
		em_layout.addStretch()
		em_gb = GroupBox('EM Sources (Optional)', em_layout, False, False, 'em_file_list_gb')

		# add file picking button layout
		find_apps_files_layout = BoxLayout([self.add_master_dir_btn, self.find_apps_files_btn], 'v')
		find_apps_files_layout.addStretch()
		find_apps_files_gb = GroupBox('Find APPS Files', find_apps_files_layout, False, False, 'find_apps_files_gb')

		# add start and stop time fields as an alternative
		self.dt_edit_start = QtWidgets.QDateTimeEdit()
		self.dt_edit_end = QtWidgets.QDateTimeEdit()
		dt_edit_layout = BoxLayout([self.dt_edit_start, self.dt_edit_end], 'v')
		dt_edit_layout.addStretch()
		dt_edit_gb = GroupBox('Time Selection', dt_edit_layout, False, False, 'dt_edit_gb')

		# set upper layouts
		upper_left_layout = BoxLayout([find_apps_files_gb, dt_edit_gb], 'v')
		upper_layout = BoxLayout([upper_left_layout, ins_gb, gnss_gb, em_gb], 'h')

		# add figure instance and layout for horizontal time series coverage plots
		self.time_canvas_height = 2
		self.time_canvas_width = 8
		self.time_figure = Figure(figsize=(self.time_canvas_width, self.time_canvas_height))
		self.time_canvas = FigureCanvas(self.time_figure)
		self.time_canvas.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding,
									   QtWidgets.QSizePolicy.MinimumExpanding)
		self.x_max_time = 0.0
		self.y_max_time = 0.0
		self.time_toolbar = NavigationToolbar(self.time_canvas, self)  # time plot toolbar
		self.time_layout = BoxLayout([self.time_toolbar, self.time_canvas], 'v')

		# add activity log widget
		self.log = TextEdit("background-color: lightgray", True, 'log')
		self.log.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.Minimum)
		update_log(self, '*** New APPS file picking log ***')
		log_gb = GroupBox('Activity Log', BoxLayout([self.log], 'v'), False, False, 'log_gb')
		# set main layout
		main_layout = BoxLayout([upper_layout, self.time_layout, log_gb], 'v')
		self.mainWidget.setLayout(main_layout)
		self.init_time_ax()

	def init_time_ax(self):  # set initial swath parameters
		self.ax1 = self.time_figure.add_subplot(111)
		self.ax1.minorticks_on()
		self.ax1.grid(axis='x', which='minor', linestyle='-', linewidth='0.5', color='black')
		self.ax1.grid(axis='x', which='major', linestyle='-', linewidth='1.0', color='black')
		self.ax1.set_ylim(0, 4.0)
		self.ax1.set_yticks([0.5, 1.5, 2.5, 3.5])
		self.ax1.set_yticklabels(['SBET', 'GNSS', 'INS', 'EM'])
		self.update_axes()
		self.ax1.margins(0.5)

	# self.plot_fake_time_coverage()  # EXAMPLE ONLY

	def update_axes(self):
		self.ax1.set_xlabel('Time (Assumed UTC)', fontsize=8)
		# self.ax1.use_sticky_edges = True
		# ax.margins(float(self.axis_margin_tb.text())/100)
		# self.ax1.autoscale(True)

	def plot_fake_time_coverage(self):
		# PLOT EXAMPLES ONLY
		# self.ax1.hlines(y=3.5, xmin=0.1, xmax=0.8, linewidth=4, color='b')  # sonar time coverage
		# self.ax1.hlines(y=2.5, xmin=0.2, xmax=0.7, linewidth=4, color='r')  # INS time coverage
		# self.ax1.hlines(y=1.5, xmin=0.3, xmax=0.9, linewidth=4, color='g')  # GNSS time coverage
		# self.ax1.hlines(y=0.5, xmin=0.3, xmax=0.7, linewidth=10, color='k')  # OVERLAP time coverage
		self.time_figure.set_tight_layout(True)

	def add_apps_files(self, ftype_filter, input_dir='HOME', include_subdir=False, file_list=None, show_path_chk=None):
		# add APPS files with ext in ftype_filter from input_dir and subdir if desired; select input dir if input_dir=[]
		fnames = add_files(self, ftype_filter, input_dir, include_subdir)
		self.file_list = file_list  # update self.file_list to correct list for use in update_file_list
		self.show_path_chk = show_path_chk
		update_file_list(self, fnames, verbose=False)

	def show_source_file_paths(self, file_list, show_path_chk):
		# show or hide path for all items in file_list according to show_paths_chk selection
		for i in range(file_list.count()):
			[path, fname] = file_list.item(i).data(1).rsplit('/', 1)  # split full file path from item data, role 1
			file_list.item(i).setText((path+'/')*int(show_path_chk.isChecked()) + fname)

	def add_master_dir(self):  # select one survey directory and find all files for each source within
		try:
			self.input_dir = QtWidgets.QFileDialog.getExistingDirectory(self, 'Add directory', os.getenv('HOME'))
			self.update_log('Added survey directory: ' + self.input_dir)
			self.update_log('Adding files in survey directory: ' + self.input_dir)

		except:
			self.update_log('No survey directory selected.')
			self.input_dir = ''
			pass

		self.update_log('Adding EM files from ' + self.input_dir)
		self.add_apps_files(['.all', '.kmall'], input_dir=self.input_dir, include_subdir=True,
							file_list=self.EM_file_list, show_path_chk=self.show_EM_path_chk)
		self.update_log('Adding INS files from ' + self.input_dir)
		self.add_apps_files(['.log'], input_dir=self.input_dir, include_subdir=True,
							file_list=self.INS_file_list, show_path_chk=self.show_INS_path_chk)
		self.update_log('Adding GNSS files from ' + self.input_dir)
		self.add_apps_files(['.21_', '.22_'], input_dir=self.input_dir, include_subdir=True,
							file_list=self.GNSS_file_list, show_path_chk=self.show_GNSS_path_chk)

	def find_apps_files(self):  # sort through files for each data type
		self.get_em_time()  # step 1: get EM data times
		# step 2: get INS data times
		# step 3: get GNSS data times
		# step 4: identify segments of continuous INS and GNSS coverage
		# step 5: prompt user for segment of interest
		# step 6: export file list (or other method) iden

	def get_em_time(self):  # get survey times from EM file list
		self.file_list = self.EM_file_list  # set file_list for use in get_new_file_list
		fnames_new = get_new_file_list(self, ['.all', '.kmall'])
		num_new_files = len(fnames_new)

		if num_new_files == 0:
			update_log(self, 'No new .all or .kmall file(s) added.  Please add new file(s).')

		else:
			update_log(self, 'Scanning times from ' + str(num_new_files) + ' new EM file(s)')
			QtWidgets.QApplication.processEvents()  # try processing and redrawing the GUI to make progress bar update
			# i = 0  # counter for successfully parsed files (data_new index)
			f = 0  # placeholder if no fnames_new
			tic1 = process_time()

			for f in range(len(fnames_new)):
				# print('in get_em_times, f =', f)
				fname_str = fnames_new[f].rsplit('/')[-1]
				# 	'Parsing new file [' + str(f + 1) + '/' + str(num_new_files) + ']:' + fname_str)
				QtWidgets.QApplication.processEvents()
				ftype = fname_str.rsplit('.', 1)[-1]

				try:  # try to parse file
					if ftype == 'all':  # read .all file for coverage (incl. params) or just params
						self.get_all_time(fnames_new[f])

					elif ftype == 'kmall':  # read .all file for coverage (incl. params) or just params
						self.get_kmall_time(fnames_new[f])

					else:
						update_log(self, 'Warning: Skipping unrecognized file type for ' + fname_str)

					update_log(self, 'Parsed file ' + fname_str)
					# i += 1  # increment successful file counter

				except:  # failed to parse this file
					update_log(self, 'No times parsed for ' + fname_str)

			toc1 = process_time()
			refresh_time = toc1 - tic1
			print('parsing EM files took', refresh_time, ' s')

			update_log(self, 'Finished scanning times from ' + str(num_new_files) + ' EM file(s)')
			self.sort_em_time()  # sort all detections by time
			self.plot_em_time()  # find min/max time for each file and plot
			# self.time_canvas.draw()

	def get_all_time(self, filename):  # extract first and last datagram times from ALL file
		em = readALLswath(self, filename, print_updates=False, parse_outermost_only=True, parse_params_only=True)
		# print('got em =', em)
		dt = [datetime.datetime.strptime(str(em['XYZ'][p]['DATE']), '%Y%m%d') + \
			  datetime.timedelta(milliseconds=em['XYZ'][p]['TIME']) for p in range(len(em['XYZ']))]
		self.info['em']['fname'].append(os.path.basename(filename))
		self.info['em']['start'].append(min(dt))
		self.info['em']['stop'].append(max(dt))
		# print('self.info[em] is now', self.info['em'])

	def get_kmall_time(self, filename):  # extract first and last datagram times from KMALL file
		# self.verbose = True
		km = kmall_data(filename)  # kmall_data class inheriting kmall class and adding extract_dg method
		km.index_file()  # get message times
		self.info['em']['fname'].append(os.path.basename(filename))
		self.info['em']['start'].append(datetime.datetime.utcfromtimestamp(min(km.msgtime)))
		self.info['em']['stop'].append(datetime.datetime.utcfromtimestamp(max(km.msgtime)))

	def sort_em_time(self):  # sort detections by time (after new files are added)
		datetime_orig = deepcopy(self.info['em']['start'])
		for k,v in self.info['em'].items():
			self.info['em'][k] = [x for _, x in sorted(zip(datetime_orig, self.info['em'][k]))]

	def plot_em_time(self, gap_threshold_s=15):  # plot time extents for EM files
		fnames_parsed = [f for f in set(self.info['em']['fname'])]
		print(fnames_parsed)
		for f in fnames_parsed:
			try:
				f_idx = self.info['em']['fname'].index(f)
			except:
				print('ERROR getting f_idx ')

			# get start and stop date times for this file
			f_time_min = self.info['em']['start'][f_idx]
			f_time_max = self.info['em']['stop'][f_idx]

			# convert datetimes to numbers for use with broken_barh plot
			f_time_min_num = mdates.date2num(f_time_min)
			f_time_max_num = mdates.date2num(f_time_max)
			f_time_len_num = f_time_max_num-f_time_min_num
			self.ax1.broken_barh([(f_time_min_num, f_time_len_num)], (3, 1), facecolors='tab:blue')

		self.time_figure.set_tight_layout(True)
		# self.time_canvas.draw()
		# self.ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
		# self.ax1.xaxis.set_major_locator(mdates.DayLocator(interval=1))
		try:
			self.ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
			self.ax1.xaxis.set_major_locator(mdates.DayLocator(interval=1))
			self.time_canvas.draw()
			self.time_figure.autofmt_xdate()
		except:
			update_log(self, 'WARNING: time span exceeds x-axis tick maximum count; dates may not appear correctly')

		plt.show()

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
			# self.trim_file_btn.setChecked(False)
			self.trim_file_btn.setEnabled(False)

			self.update_log('All files have been removed.')

	def clear_files(self):
		# clear all files from the file list and plot
		# self.remove_files(clear_all=True)
		self.calc_pb.setValue(0)
		self.remove_files(clear_all=True)
		self.trim_file_btn.setEnabled(False)

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
		fnames_ext = [fn for fn in self.filenames if any(ext in fn for ext in fext)]  # fnames (w/ paths) matching ext
		fnames_old = [fn.split('/')[-1] for fn in flist_old]  # file names only (no paths) from flist_old
		fnames_new = [fn for fn in fnames_ext if fn.split('/')[-1] not in fnames_old]  # check if fname in fnames_old

		return fnames_new  # return the fnames_new (with paths)

	def get_selected_file_list(self):
		# determine list of selected files with full file paths from current file list, not just text from GUI file list
		# [path, fname] = self.file_list.item(i).data(1).rsplit('/', 1)
		self.get_current_file_list()
		flist_sel = [f.text().split('/')[-1] for f in self.file_list.selectedItems()]  # selected fnames without paths
		fnames_sel = [fn for fn in self.filenames if fn.split('/')[-1] in flist_sel]  # full paths of selected files

		return fnames_sel  # return the fnames_new (with paths)

	def update_log(self, entry):  # update the activity log
		self.log.append(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' ' + entry)
		QtWidgets.QApplication.processEvents()


class NewPopup(QtWidgets.QWidget):  # new class for additional plots
	def __init__(self):
		QtWidgets.QWidget.__init__(self)


if __name__ == '__main__':
	app = QtWidgets.QApplication(sys.argv)

	main = MainWindow()
	main.show()

	sys.exit(app.exec_())
