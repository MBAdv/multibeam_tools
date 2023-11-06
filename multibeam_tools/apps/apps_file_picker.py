# -*- coding: utf-8 -*-
"""

Multibeam Echosounder Assessment Toolkit: APPS Processing File Picker

Purpose:
Select iXblue INS and GNSS files for processing with the APPS software package.

Process:
The user selects the intended survey time frame and directories with INS and GNSS files.
The app highlights the INS and GNSS files that can be expected to match the survey time frame.

"""
import re
import string

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
		self.start_time_utc = ''
		self.end_time_utc = ''

		# set up and layout main window
		self.setup()
		self.set_main_layout()

		# set up file control actions
		self.add_master_dir_btn.clicked.connect(lambda: self.add_master_dir())

		self.add_EM_dir_btn.clicked.connect(lambda:
											  self.add_apps_files(self.file_formats['em']['list'], input_dir=[],
																  include_subdir=self.incl_EM_subdir_chk.isChecked(),
																  file_list=self.EM_file_list,
																  show_path_chk=self.show_EM_path_chk))

		self.add_INS_dir_btn.clicked.connect(lambda:
											 self.add_apps_files(self.file_formats['ins']['list'], input_dir=[],
																 include_subdir=self.incl_INS_subdir_chk.isChecked(),
																 file_list=self.INS_file_list,
																 show_path_chk=self.show_INS_path_chk))
		self.add_GNSS_dir_btn.clicked.connect(lambda:
											  self.add_apps_files(self.file_formats['gnss']['list'], input_dir=[],
																  include_subdir=self.incl_GNSS_subdir_chk.isChecked(),
																  file_list=self.GNSS_file_list,
																  show_path_chk=self.show_GNSS_path_chk))

		self.add_EM_files_btn.clicked.connect(lambda: self.add_apps_files(self.file_formats['em']['desc'],
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
		self.rmv_files_btn.clicked.connect(lambda: self.remove_apps_files())
		self.clr_files_btn.clicked.connect(lambda: self.remove_apps_files(clear_all=True))

	def setup(self):
		self.det = {}  # detection dict (new data) used for parsing EM files
		self.info = {'em':{'fname':[], 'start':[], 'stop':[]},
					 'ins':{'fname':[], 'start':[], 'stop':[]},
					 'gnss':{'fname':[], 'start':[], 'stop':[]}}

		self.plot_info = {'em':{'color':'blue', 'y_height': 3, 'y_width': 1},
						  'ins':{'color':'red', 'y_height': 2, 'y_width': 1},
						  'gnss':{'color':'orange', 'y_height': 1, 'y_width': 1},
						  'sbet':{'color':'green', 'y_height': 0, 'y_width': 1}}  # dict with plot controls

		self.file_formats ={'em':{'list':['.all', '.kmall'], 'desc':'Kongsberg (*.all *.kmall)'},
							'ins':{'list':['.log'], 'desc': 'PHINS (*.log)'},
							'gnss':{'list':['.21_', '.22_'], 'desc':'Septentrio (*.2*)'}}


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
		self.find_apps_files_btn = PushButton('Find APPS Files', btnw, btnh, 'find_apps_files_btn', 'Find files for APPS processing')
		self.grid_lines_toggle_chk = CheckBox('Show grid lines', True, 'show_grid_lines_chk', 'Show grid lines')
		self.rmv_files_btn = PushButton('Remove Selected', btnw, btnh, 'rem_files_btn', 'Remove selected files')
		self.clr_files_btn = PushButton('Clear All Files', btnw, btnh, 'clr_files_btn', 'Clear all files')

		# add INS file list
		self.INS_file_list = QtWidgets.QListWidget()
		self.INS_file_list.setObjectName('INS file list')
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
		self.GNSS_file_list.setObjectName('GNSS file list')
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
		self.EM_file_list.setObjectName('EM file list')
		self.EM_file_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
		self.EM_file_list.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.MinimumExpanding)
		self.EM_file_list.setIconSize(QSize(0, 0))  # set icon size to 0,0 or file names (from item.data) are indented
		em_btn_layout = BoxLayout([BoxLayout([self.add_EM_dir_btn, self.add_EM_files_btn], 'v'),
								   BoxLayout([self.incl_EM_subdir_chk, self.show_EM_path_chk], 'v')], 'h')
		em_layout = BoxLayout([em_btn_layout, self.EM_file_list], 'v')
		em_layout.addStretch()
		em_gb = GroupBox('EM Sources (Optional)', em_layout, False, False, 'em_file_list_gb')

		# add file picking button layout
		find_apps_files_layout = BoxLayout([self.add_master_dir_btn, self.find_apps_files_btn,
											self.rmv_files_btn, self.clr_files_btn], 'v')
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
		self.ax1 = self.time_figure.add_subplot(111)
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
		self.update_axes()


	def update_axes(self):
		self.ax1.set_ylim(0, 4.0)
		# getting errors exceeding max number of ticks, maybe creating too large of a span?
		# try starting with 1 day and updating xlim only if data available
		default_min = datetime.datetime(1,1,1)
		default_max = datetime.datetime(1,1,2)
		self.ax1.set_xlim(mdates.date2num(default_min), mdates.date2num(default_max))

		data_start = []
		data_stop = []
		for k in self.info.keys():
			if self.info[k]['start'] != []:
				data_start.append(min(self.info[k]['start']))
				data_stop.append(max(self.info[k]['stop']))

		print('got data_start =', data_start)
		print('got data_stop = ', data_stop)

		if data_start != [] and data_stop != []:
			print('\n**** setting xlim to data_start and _stop...')
			self.ax1.set_xlim(min(data_start), max(data_stop))

		# self.ax1.set_xlim(start_min, stop_max)
		self.ax1.set_ylim(0, 4.0)
		self.ax1.set_yticks([0.5, 1.5, 2.5, 3.5])
		self.ax1.set_yticklabels(['SBET', 'GNSS', 'INS', 'EM'])
		self.ax1.margins(0.5)
		self.ax1.set_xlabel('Time (Assumed UTC)', fontsize=8)

		self.ax1.minorticks_on()
		# self.ax1.grid(axis='x', which='minor', linestyle='-', linewidth='0.5', color='black')
		self.ax1.grid(axis='x', which='major', linestyle='-', linewidth='1.0', color='black')
		# self.ax1.use_sticky_edges = True
		# ax.margins(float(self.axis_margin_tb.text())/100)
		self.ax1.autoscale(True)

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
		self.update_buttons()


	def show_source_file_paths(self, file_list, show_path_chk):
		# show or hide path for all items in file_list according to show_paths_chk selection
		for i in range(file_list.count()):
			[path, fname] = file_list.item(i).data(1).rsplit('/', 1)  # split full file path from item data, role 1
			file_list.item(i).setText((path+'/')*int(show_path_chk.isChecked()) + fname)


	def add_master_dir(self):  # select one survey directory and find all files for each source within
		try:
			# master_dir = QtWidgets.QFileDialog.getExistingDirectory(self, 'Add directory', os.getenv('HOME'))
			master_dir = QtWidgets.QFileDialog.getExistingDirectory(self, 'Add directory', 'C:\\Users\\kjerram\\Desktop')
			print('got master_dir =', master_dir)

			if master_dir:
				self.update_log('Added survey directory: ' + master_dir)
				self.update_log('Adding files in survey directory: ' + master_dir)

				self.update_log('Adding EM files from ' + master_dir)
				self.add_apps_files(self.file_formats['em']['list'], input_dir=master_dir, include_subdir=True,
									file_list=self.EM_file_list, show_path_chk=self.show_EM_path_chk)
				self.update_log('Adding INS files from ' + master_dir)
				self.add_apps_files(self.file_formats['ins']['list'], input_dir=master_dir, include_subdir=True,
									file_list=self.INS_file_list, show_path_chk=self.show_INS_path_chk)
				self.update_log('Adding GNSS files from ' + master_dir)
				self.add_apps_files(self.file_formats['gnss']['list'], input_dir=master_dir, include_subdir=True,
									file_list=self.GNSS_file_list, show_path_chk=self.show_GNSS_path_chk)

			else:
				self.update_log('No survey directory selected.')

		except:
			self.update_log('Error selecting survey directory.')

		self.update_buttons()


	def find_apps_files(self):  # sort through files for each data type
		self.cont = {'ins':{}, 'gnss':{}}  # dict for tracking continuity of each nav data source
		self.info['sbet'] = {}  # add dict to info for plotting final SBET coverage results

		# self.get_em_time()  # step 1: get EM data times
		for flist in [self.EM_file_list, self.INS_file_list, self.GNSS_file_list]:
			self.get_times(flist)  # step 1: get data times for each file type

		for source in ['em', 'ins', 'gnss']:
			self.sort_times(source=source)

		for source in ['ins', 'gnss']:
			self.cont[source]['start'], self.cont[source]['stop'] =\
				self.find_gaps(starts=self.info[source]['start'],
							   stops=self.info[source]['stop'],
							   threshold_s=1)

		print('after finding gaps, self.cont =', self.cont)

		self.info['sbet']['start'], self.info['sbet']['stop'] =\
			self.find_full_coverage_times(starts=[self.cont['ins']['start'], self.cont['gnss']['start']],
										  stops=[self.cont['ins']['stop'], self.cont['gnss']['stop']])

		self.info['sbet']['fname'] = ['SBET segment ' + str(i) for i in range(len(self.info['sbet']['start']))]
		print('after checking full coverage, self.info[sbet] =', self.cont)

		self.update_plot()
		self.update_buttons()

		# step 5: prompt user for segment of interest
		# step 6: export file list (or other method) iden


	def get_times(self, file_list=None):  # get survey times from any new files in the provided file list
		self.file_list = file_list  # set file_list for use in get_new_file_list
		file_list_key = file_list.objectName().split()[0].lower()
		fnames_old = list(set(self.info[file_list_key]['fname']))
		fnames_new = get_new_file_list(self, flist_old=fnames_old)
		num_new_files = len(fnames_new)

		if num_new_files == 0:
			update_log(self, 'No new files in the ' + self.file_list.objectName())

		else:
			update_log(self, 'Scanning ' + str(num_new_files) + ' new file(s) in the ' + self.file_list.objectName())
			QtWidgets.QApplication.processEvents()  # try processing and redrawing the GUI to make progress bar update
			f = 0  # placeholder if no fnames_new
			tic1 = process_time()

			for f in range(len(fnames_new)):
				fname_str = os.path.basename(fnames_new[f])
				ftype = os.path.splitext(fname_str)[1]
				# print('got ftype =', ftype)

				try:  # try to parse file
					if ftype == '.all':  # read .all file
						self.get_all_time(fnames_new[f])

					elif ftype == '.kmall':  # read .all file
						self.get_kmall_time(fnames_new[f])

					elif ftype in self.file_formats['ins']['list']:  # read .log file
						self.get_ins_time(fnames_new[f])

					elif ftype in self.file_formats['gnss']['list']:  # read .22* file
						self.get_gnss_time(fnames_new[f])

					else:
						update_log(self, 'Warning: Skipping unrecognized file type for ' + fname_str)
						continue

					update_log(self, 'Parsed file ' + fname_str)

				except:  # failed to parse this file
					update_log(self, 'No times parsed for ' + fname_str)

			toc1 = process_time()
			refresh_time = toc1 - tic1
			print('parsing ', ftype, ' files took', refresh_time, ' s')

			update_log(self, 'Finished scanning ' + str(num_new_files) + ' new  ' + ftype + ' file(s)')


	def get_all_time(self, filename):  # extract first and last datagram times from ALL file
		em = readALLswath(self, filename, print_updates=False, parse_outermost_only=True, parse_params_only=True)
		dt = [datetime.datetime.strptime(str(em['XYZ'][p]['DATE']), '%Y%m%d') + \
			  datetime.timedelta(milliseconds=em['XYZ'][p]['TIME']) for p in range(len(em['XYZ']))]
		self.info['em']['fname'].append(os.path.basename(filename))
		self.info['em']['start'].append(min(dt))
		self.info['em']['stop'].append(max(dt))


	def get_kmall_time(self, filename):  # extract first and last datagram times from KMALL file
		# self.verbose = True
		km = kmall_data(filename)  # kmall_data class inheriting kmall class and adding extract_dg method
		km.index_file()  # get message times
		self.info['em']['fname'].append(os.path.basename(filename))
		self.info['em']['start'].append(datetime.datetime.utcfromtimestamp(min(km.msgtime)))
		self.info['em']['stop'].append(datetime.datetime.utcfromtimestamp(max(km.msgtime)))


	def get_ins_time(self, filename):  # get start and stop times for INS file
		# get the start time and log part number from fname (e.g., DRIX8-_Postpro_2022-07-23_180341_part2.log)
		try:
			fname_nums = re.findall(r'\d+', os.path.basename(filename))
			# part_num = fname_nums[-1]  # assume the log part number is the very last number
			dt_nums = fname_nums[-5:-1]
			dt_str = '-'.join(dt_nums)
			dt_start = datetime.datetime.strptime(dt_str, "%Y-%m-%d-%H%M%S")
			dt_stop = dt_start + datetime.timedelta(hours=1)
			self.info['ins']['fname'].append(os.path.basename(filename))
			self.info['ins']['start'].append(dt_start)
			self.info['ins']['stop'].append(dt_stop)  # ******** ASSUME ONE HOUR LOGS UNTIL MORE INTELLIGENT PARSING!!!

		except:
			update_log(self, 'Failed time extraction for INS file ' + os.path.basename(filename))


	def get_gnss_time(self, filename):  # get start and stop times for GNSS file
		# get the start time from day number and start hour from letter (e.g., drix191d.22_ is 2022-07-10 03:00)
		try:
			fname_nums = re.findall(r'\d+', os.path.basename(filename))
			fname_alpha = re.findall('[a-zA-Z]+', os.path.basename(filename))
			# print('turned GNSS filename ', filename, ' into fname_nums =', fname_nums, ' and fname_alpha ', fname_alpha)
			dt_year = datetime.datetime.now().year  # assume current year for getting day number
			day_num = int(fname_nums[0])
			dt_date = datetime.datetime(dt_year, 1, 1) + datetime.timedelta(day_num - 1)  # python index?!
			hour_num = string.ascii_lowercase.index(fname_alpha[-1])  # use last letter in filename as start hour index
			dt_start = dt_date + datetime.timedelta(hours=hour_num)
			dt_stop = dt_start + datetime.timedelta(hours=1)
			# print('got dt_start and dt_stop = ', dt_start, dt_stop)
			self.info['gnss']['fname'].append(os.path.basename(filename))
			self.info['gnss']['start'].append(dt_start)
			self.info['gnss']['stop'].append(dt_stop)  # ******** ASSUME ONE HOUR LOGS UNTIL MORE INTELLIGENT PARSING!!!

		except:
			update_log(self, 'Failed time extraction for GNSS file ' + os.path.basename(filename))


	def sort_times(self, source='', key='start'):  # sort fields in dict[source] by 'start' time (after new files are added)
		datetime_orig = deepcopy(self.info[source][key])
		for k, v in self.info[source].items():
			self.info[source][k] = [x for _, x in sorted(zip(datetime_orig, self.info[source][k]))]


	def find_gaps(self, starts=[], stops=[], threshold_s=1):  # find continuous stretches for pairs of start/stop times
		# starts, stops are lists of datetime objs; threshold_s is max gap in seconds to be considered continuous
		threshold_dt = datetime.timedelta(seconds=threshold_s)
		break_idx = [i for i in range(0, len(starts)-1) if starts[i+1] - stops[i] > threshold_dt] + [len(stops)-1]
		start_idx = [0] + [i + 1 for i in break_idx[:-1]]  # indices of starts of continuous stretches, incl first time
		cont_starts = [starts[i] for i in start_idx]  # start times for continuous stretches
		cont_breaks = [stops[i] for i in break_idx]  # break times for continuous stretches

		for j, k in zip(cont_starts, cont_breaks):
			print('continuous stretch from ',
				  datetime.datetime.strftime(j, '%Y-%m-%d %H:%M:%S.%f'), ' to ',
				  datetime.datetime.strftime(k, '%Y-%m-%d %H:%M:%S.%f'))

		return cont_starts, cont_breaks

		# NOTE: AT PRESENT, ALL INS AND GNSS FILES ARE ASSUMED TO BE 1 HOUR DURATION UNTIL MORE INTELLIGENTLY PARSED
		# THIS LEADS TO SOME CASES WHERE AN ASSUMED END TIME FOR ONE FILE IS WELL AFTER THE START TIME PARSED FROM THE
		# FILENAME OF THE ENSUING FILE... SO THIS IS STRICTLY A TEST OF THE CONTINUOUS COVERAGE GIVEN THE START/STOP
		# TIMES PROVIDED, NOT A TEST OF WHETHER THE START/STOP TIMES ARE CORRECT OR LOGICAL!
		# IN OTHER WORDS, BECAUSE OF THE ASSUMED 1 HOUR DURATIONS FOR FILES AT THIS POINT, IT MAY APPEAR THAT THERE IS
		# 'MULTIPLE' COVERAGE FOR INS OR GNSS FILES WHEN SUCCESSIVE FILE DURATIONS WERE LESS THAN ONE HOUR


	def find_full_coverage_times(self, starts=[[]], stops=[[]]):  # find times where all sources are present
		# starts/stops are lists of lists with start and stop times for each data source; there must be N lists of
		# start times and N lists of stop times representing at least N >= 2 data sources for comparison, i.e., to
		# determine time spans when all N data sources are available; it's assumed that the order of lists are
		# consistent for starts and stops, e.g., if the first data source has 10 pairs, the first list in starts and
		# the first list in stops both have 10 values, followed by the lists for the second data source, etc.
		n_sources = len(starts)
		starts_all = [s for start_list in starts for s in start_list]
		stops_all = [s for stop_list in stops for s in stop_list]
		times_all = starts_all + stops_all
		times_all_sorted = sorted(times_all)
		cov_all = [1]*len(starts_all) + [-1]*len(stops_all)
		cov_sort_order = np.argsort(times_all)
		cov_sorted = [cov_all[s] for s in cov_sort_order]
		cov_sum = np.cumsum(cov_sorted).tolist()

		# find start times for full coverage, and assume only possible change after each is toward incomplete coverage
		cov_start_idx = [i for i, cs in enumerate(cov_sum) if cs == n_sources]  # indices for when full coverage starts
		cov_break_idx = [i+1 for i in cov_start_idx]  # assuming full coverage is reduced at each subsequent change
		print('cov_start_idx =', cov_start_idx)
		print('cov_break_idx =', cov_break_idx)

		cov_starts = [times_all_sorted[i] for i in cov_start_idx]
		cov_breaks = [times_all_sorted[i] for i in cov_break_idx]
		print('got cov_starts =', cov_starts)
		print('got cov_breaks =', cov_breaks)
		#### OPTIONAL: Add a gap threshold test step with find_gaps, applied to the 'full coverage' time spans found

		return cov_starts, cov_breaks


	def plot_time(self, k=''):  # plot times for data key k (e.g., 'em') and facecolor fc
		fnames_parsed = [f for f in set(self.info[k]['fname'])]
		print(fnames_parsed)
		for f in fnames_parsed:
			try:
				f_idx = self.info[k]['fname'].index(f)
			except:
				print('ERROR getting f_idx ')

			# convert datetimes to numbers for use with broken_barh plot
			start_time_num = mdates.date2num(self.info[k]['start'][f_idx])
			stop_time_num = mdates.date2num(self.info[k]['stop'][f_idx])
			len_time_num = stop_time_num-start_time_num
			color_str = self.plot_info[k]['color']

			self.ax1.broken_barh([(start_time_num, len_time_num)],
								 (self.plot_info[k]['y_height'], self.plot_info[k]['y_width']),
								 facecolors=color_str)

		self.time_figure.set_tight_layout(True)
		# self.time_canvas.draw()
		# self.ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
		# self.ax1.xaxis.set_major_locator(mdates.DayLocator(interval=1))
		try:
			self.ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
			self.ax1.xaxis.set_major_locator(mdates.DayLocator(interval=1))
			self.ax1.set_ylim(0, 4.0)

			self.time_canvas.draw()
			self.time_figure.autofmt_xdate()
		except:
			update_log(self, 'WARNING: time span exceeds x-axis tick maximum count; dates may not appear correctly')

		plt.show()


	def remove_apps_files(self, clear_all=False, update_plot=False):
		# remove selected files or clear all files, update det and spec dicts accordingly
		for file_list in [self.EM_file_list, self.INS_file_list, self.GNSS_file_list]:
			self.file_list = file_list
			selected_files = self.file_list.selectedItems()

			if clear_all or selected_files != []:  # try to remove files from this list only if selected or clearing all
				removed_files = remove_files(self, clear_all)
				get_current_file_list(self)  # update the file list to see

				if self.filenames == []:  # all files have been removed, update data for this type and refresh plots
					file_list_key = file_list.objectName().split()[0].lower()
					print('got file_list_key =', file_list_key)
					print('self.info[file_list_ley = ', self.info[file_list_key])
					for k,v in self.info[file_list_key].items():
						self.info[file_list_key][k].clear()

					update_log(self, 'Cleared all files from ' + self.file_list.objectName())

				else:  # remove data associated only with removed files
					self.remove_data(removed_files)

		print('after removing files and before updating plot, self.info is ', self.info)
		self.update_plot()
		print('back from update_plot')
		self.update_buttons()

	def remove_data(self, removed_files):
		# remove data in specified filenames from detection and spec dicts
		print('in remove_data with removed_files =', removed_files)

		for f in removed_files:
			fname = os.path.basename(f.text())  #.split('/')[-1]  # get filename from removed_files object
			ftype = os.path.splitext(fname)[1]

			try:  # removed_files is a file list object
				for k,v in self.file_formats.items():  # find info dict key associated with this file format
					# print('working on k,v = ', k, v)
					if ftype in v['list']:  # if format found for this data type, find index of fname in the info dict
						# print('found ftype in v[list] =', ftype)
						if fname in self.info[k]['fname']:   # skip if filename was added to filelist but not parsed yet
							i = self.info[k]['fname'].index(fname)  # find index of matching filename
							for j in self.info[k].keys():  # loop through all keys and remove values at these indices
								self.info[k][j].pop(i)
								# print('for k, j, self.info[k][j] is now ', self.info[k][j])

			except:  # failed to remove this file
				update_log(self, 'WARNING: Error removing data for ' + fname)


	def clear_plot(self):  # clear plot and reset bounds
		self.ax1.clear()
		self.ax1.xlim(0, 1.0)
		self.update_axes()


	def update_plot(self):  # update plot by refreshing all data keys
		self.ax1.clear()
		self.update_axes()

		for k in self.info.keys():
			print('in update_plot, calling plot_time with key=', k)
			self.plot_time(k)  # update plot



		self.update_axes()
		# self.time_canvas.draw()

	def update_buttons(self, recalc_acc=False):
		# enable or disable file selection and calc_accuracy buttons depending on loaded files
		# print('\n\n\nupdating buttons... turning button to NONE')
		self.find_apps_files_btn.setStyleSheet("background-color: none")

		for file_list in [self.EM_file_list, self.INS_file_list, self.GNSS_file_list]:
			self.file_list = file_list  # this gets used later in get_new_file_list and get_current_file_list
			file_list_key = file_list.objectName().split()[0].lower()
			# print('looking at file_list_key =', file_list_key)
			fnames_old = list(set(self.info[file_list_key]['fname']))
			# print('got fnames_old =', fnames_old)
			fnames_new = get_new_file_list(self, flist_old=fnames_old)
			# print('got fnames_new =', fnames_new)

			if len(fnames_new) > 0:
				# print('TURNING BUTTON YELLOW')
				self.find_apps_files_btn.setStyleSheet("background-color: yellow")

	# def get_selected_file_list(self):
	# 	# determine list of selected files with full file paths from current file list, not just text from GUI file list
	# 	# [path, fname] = self.file_list.item(i).data(1).rsplit('/', 1)
	# 	self.get_current_file_list()
	# 	flist_sel = [f.text().split('/')[-1] for f in self.file_list.selectedItems()]  # selected fnames without paths
	# 	fnames_sel = [fn for fn in self.filenames if fn.split('/')[-1] in flist_sel]  # full paths of selected files
	#
	# 	return fnames_sel  # return the fnames_new (with paths)

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
