# -*- coding: utf-8 -*-
"""

Multibeam Echosounder Assessment Toolkit: Attitude Plotter


"""
import numpy as np

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
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
# from multibeam_tools.libs.swath_coverage_lib import *
from multibeam_tools.libs.gui_widgets import *

from kmall.KMALL import kmall


__version__ = "0.0.1"  # TESTING


class MainWindow(QtWidgets.QMainWindow):
	media_path = os.path.join(os.path.dirname(__file__), "media")

	def __init__(self, parent=None):
		super(MainWindow, self).__init__()

		# set up main window
		self.mainWidget = QtWidgets.QWidget(self)
		self.setCentralWidget(self.mainWidget)
		self.setMinimumWidth(800)
		self.setMinimumHeight(600)
		self.setWindowTitle('Attitude Plotter v.%s' % __version__)
		self.setWindowIcon(QtGui.QIcon(os.path.join(self.media_path, "icon.png")))

		if os.name == 'nt':  # necessary to explicitly set taskbar icon
			import ctypes
			current_app_id = 'MAC.AttitudePlotter.' + __version__  # arbitrary string
			ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(current_app_id)

		# initialize other necessities
		self.filenames = ['']
		self.input_dir = ''
		self.output_dir = ''
		self.output_dir_old = ''
		self.fcount_skipped = 0

		# set up three layouts of main window
		self.set_left_layout()
		self.set_center_layout()
		self.init_all_axes()

		# set up layouts of main window
		self.set_main_layout()

		# set up file control actions
		self.add_file_btn.clicked.connect(lambda: self.add_files('Kongsberg KMALL files (*.kmall)'))
		self.get_indir_btn.clicked.connect(self.get_input_dir)
		self.rmv_file_btn.clicked.connect(self.remove_files)
		self.clr_file_btn.clicked.connect(self.clear_files)
		self.plot_att_btn.clicked.connect(self.plot_attitude)
		self.show_path_chk.stateChanged.connect(self.show_file_paths)

	def init_all_axes(self):
		self.init_att_ax()
		# add_grid_lines(self)
		# update_axes(self)

	def init_att_ax(self):  # set initial swath parameters
		# fig, ax = plt.subplots(3, 1, sharex=True, sharey=True)
		self.roll_ax = self.att_figure.add_subplot(311)
		self.rollrate_ax = self.roll_ax.twinx()
		self.pitch_ax = self.att_figure.add_subplot(312, sharex=self.roll_ax)
		self.pitchrate_ax = self.pitch_ax.twinx()
		self.hdg_ax = self.att_figure.add_subplot(313, sharex=self.roll_ax)
		self.yawrate_ax = self.hdg_ax.twinx()

		self.roll_ax.set_ylabel('Roll (Red)')
		self.rollrate_ax.set_ylabel('Roll Rate (Blue)')
		self.pitch_ax.set_ylabel('Pitch (Red)')
		self.pitchrate_ax.set_ylabel('Pitch Rate (Blue)')
		self.hdg_ax.set_ylabel('Heading (Red)')
		self.yawrate_ax.set_ylabel('Yaw Rate (Blue)')

		self.att_figure.suptitle('Attitude and Attitude Velocity')


	def set_left_layout(self):
		# set layout with file controls on right, sources on left, and progress log on bottom
		btnh = 20  # height of file control button
		btnw = 100  # width of file control button

		# add file control buttons
		self.add_file_btn = PushButton('Add Files', btnw, btnh, 'add_file_btn', 'Add files')
		self.get_indir_btn = PushButton('Add Directory', btnw, btnh, 'get_indir_btn', 'Add a directory')
		# self.get_outdir_btn = PushButton('Select Output Dir.', btnw, btnh, 'get_outdir_btn',
		#                                  'Select the output directory (see current directory below)')
		self.rmv_file_btn = PushButton('Remove Selected', btnw, btnh, 'rmv_file_btn', 'Remove selected files')
		self.clr_file_btn = PushButton('Remove All Files', btnw, btnh, 'clr_file_btn', 'Remove all files')
		self.plot_att_btn = PushButton('Plot Attitude', btnw, btnh, 'plot_att_btn', 'Plot attitude from source list')
		self.show_path_chk = CheckBox('Show file paths', False, 'show_paths_chk')

		# set the file control options
		file_btn_layout = BoxLayout([self.add_file_btn, self.get_indir_btn, self.rmv_file_btn, self.clr_file_btn,
									 self.plot_att_btn, self.show_path_chk], 'v')
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
		self.update_log('*** New Attitude Plotter log ***\n')

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
		# main_layout = BoxLayout([self.file_layout, self.log_gb], 'v')
		# self.mainWidget.setLayout(main_layout)

		# set the left panel layout with file controls on top and log on bottom
		self.left_layout = BoxLayout([self.file_layout, self.log_gb, self.prog_layout], 'v')

	def set_center_layout(self):
		# set center layout with swath coverage plot
		self.att_canvas_height = 12
		self.att_canvas_width = 10
		self.att_figure = Figure(figsize=(self.att_canvas_width, self.att_canvas_height))  # figure instance
		self.att_canvas = FigureCanvas(self.att_figure)  # canvas widget that displays the figure
		self.att_canvas.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding,
									  QtWidgets.QSizePolicy.MinimumExpanding)
		self.att_toolbar = NavigationToolbar(self.att_canvas, self)  # swath plot toolbar
		self.att_layout = BoxLayout([self.att_toolbar, self.att_canvas], 'v')

	def set_main_layout(self):
		# set the main layout with file controls on left and swath figure on right
		# self.mainWidget.setLayout(BoxLayout([self.left_layout, self.swath_layout, self.right_layout], 'h'))
		self.mainWidget.setLayout(BoxLayout([self.left_layout, self.att_layout], 'h'))

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
				new_item.setText(
					(path + '/') * int(self.show_path_chk.isChecked()) + fname)  # set text, show or hide path
				self.file_list.addItem(new_item)
				self.update_log('Added ' + fname)  # fnames_new[f].rsplit('/',1)[-1])
			else:
				self.update_log('Skipping empty filename ' + fname)

		if fnames_new:
			self.update_log('Finished adding ' + str(len(fnames_new)) + ' new file' +
							('s' if len(fnames_new) > 1 else ''))

	def show_file_paths(self):
		# show or hide path for all items in file_list according to show_paths_chk selection
		for i in range(self.file_list.count()):
			[path, fname] = self.file_list.item(i).data(1).rsplit('/', 1)  # split full file path from item data, role 1
			self.file_list.item(i).setText((path + '/') * int(self.show_path_chk.isChecked()) + fname)

	def get_input_dir(self):
		# get directory of files to load
		try:
			self.input_dir = QtWidgets.QFileDialog.getExistingDirectory(self, 'Add directory', os.getenv('HOME'))
			self.update_log('Added directory: ' + self.input_dir)

			# get a list of all .txt files in that directory, '/' avoids '\\' in os.path.join in add_files
			self.update_log('Adding files in directory: ' + self.input_dir)
			self.add_files(['.kmall'], input_dir=self.input_dir + '/')

		except:
			self.update_log('No input directory selected.')
			self.input_dir = ''
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
		fnames_kmall = [f for f in self.filenames if '.kmall' in f]

		if len(fnames_kmall) == 0:
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

	def update_prog(self, total_prog):
		self.calc_pb.setValue(total_prog)
		QtWidgets.QApplication.processEvents()

	def plot_attitude(self):
		self.get_current_file_list()

		fnames_kmall = [f for f in self.filenames if '.kmall' in f]

		# update progress bar and log
		self.calc_pb.setValue(0)  # reset progress bar to 0 and max to number of files
		self.calc_pb.setMaximum(max([1, len(fnames_kmall)]))  # set max value to at least 1 to avoid hanging when 0/0

		for f in range(len(fnames_kmall)):
			fname = fnames_kmall[f]
			# print('fname is ', fname.rsplit('/', 1)[-1])
			self.update_log('Scanning attitude for ' + fname.rsplit('/', 1)[-1])
			km = kmall_data(fname)  # kmall_data class inheriting kmall class and adding extract_dg method
			km.index_file()
			km.report_packet_types()
			km.extract_dg('SKM')
			km.closeFile()

			# concatenate datetime and roll rate
			num_SKM = len(km.skm['sample'])
			# SKM_header_datetime = [km.skm['header'][j]['dgdatetime'] for j in range(num_SKM)]
			# SKM_sample_datetime = [km.skm['sample'][j]['KMdefault']['datetime'][0] for j in range(num_SKM)]

			# if f == 0:
				# SKM_sample_time = []
				# SKM_sample_roll = []
				# SKM_sample_roll_rate = []

				# attitude = np.array([])

			for j in range(num_SKM):

				# print('j =', j)
				# SKM_sample_time.extend(np.array(km.skm['sample'][j]['KMdefault']['datetime']))
				# SKM_sample_roll.extend(km.skm['sample'][j]['KMdefault']['roll_deg'])
				# SKM_sample_roll_rate.extend(km.skm['sample'][j]['KMdefault']['rollRate'])

				samples = np.vstack((np.asarray(km.skm['sample'][j]['KMdefault']['datetime']),
									 np.asarray(km.skm['sample'][j]['KMdefault']['roll_deg']),
									 np.asarray(km.skm['sample'][j]['KMdefault']['rollRate']),
									 np.asarray(km.skm['sample'][j]['KMdefault']['pitch_deg']),
									 np.asarray(km.skm['sample'][j]['KMdefault']['pitchRate']),
									 np.asarray(km.skm['sample'][j]['KMdefault']['heading_deg']),
									 np.asarray(km.skm['sample'][j]['KMdefault']['yawRate'])))

				# print('size of samples after converting to array = ', np.shape(samples))

				if j == 0:  # copy samples as first data in attitude array

					attitude = samples.copy()

					# print('size of attitude after initializing = ', np.shape(attitude))

				else:
					# print('size of attitude before concatenating = ', np.shape(attitude))

					attitude = np.concatenate((attitude, samples), axis=1)

					# print('size of attitude after concatenating = ', np.shape(attitude))

			self.update_prog(f + 1)

		self.update_log('Plotting attitude time series...')

			# print('survived with datetime / roll_rate lengths: ', len(SKM_sample_time), len(SKM_sample_roll_rate))

		# make a plot of all the data
		# self.roll_ax.plot(SKM_sample_time, SKM_sample_roll, 'r', label='Roll (deg)', linewidth=1)
		# self.roll_ax.plot(SKM_sample_time, SKM_sample_roll_rate, 'b', label='Roll rate (deg/s)', linewidth=1)

		self.roll_ax.plot(attitude[0], attitude[1], 'r', label='Roll (deg)', linewidth=1)
		self.rollrate_ax.plot(attitude[0], attitude[2], 'b', label='Roll rate (deg/s)', linewidth=1)
		self.pitch_ax.plot(attitude[0], attitude[3], 'r', label='Pitch (deg)', linewidth=1)
		self.pitch_ax.plot(attitude[0], attitude[4], 'b', label='Pitch rate (deg/s)', linewidth=1)
		self.hdg_ax.plot(attitude[0], attitude[5], 'r', label='Heading (deg)', linewidth=1)
		self.yawrate_ax.plot(attitude[0], attitude[6], 'b', label='Yaw rate (deg/s)', linewidth=1)

		self.roll_ax.grid(axis='both', which='minor')
		self.roll_ax.grid(axis='both', which='major')
		self.pitch_ax.grid(axis='both', which='minor')
		self.pitch_ax.grid(axis='both', which='major')
		self.hdg_ax.grid(axis='both', which='minor')
		self.hdg_ax.grid(axis='both', which='major')

		self.att_canvas.draw()

		# self.roll_ax.grid('SKM Datagram: Roll Rate (deg/s)')

		# plt.legend(loc="upper left")
		# plt.show()


class kmall_data(kmall):
	# test class inheriting kmall class with method to extract any datagram (based on extract attitude method)
	def __init__(self, filename, dg_name=None):
		super(kmall_data, self).__init__(filename)  # pass the filename to kmall module (only argument required)

	def extract_dg(self, dg_name):  # extract dicts of datagram types, store in kmall_data class
		# dict of allowable dg_names and associated dg IDs; based on extract_attitude method in kmall module
		dg_types = {'IOP': self.read_EMdgmIOP,
					'IIP': self.read_EMdgmIIP,
					'MRZ': self.read_EMdgmMRZ,
					'SKM': self.read_EMdgmSKM}

		if self.Index is None:
			print('*** indexing file! ***')
			self.index_file()

		if self.FID is None:
			self.OpenFiletoRead()

		# for each datagram type, get offsets, read datagrams, and store in key (e.g., MRZ stored in kjall.mrz)
		if dg_name == 'MRZinfo':  # extract ping info ONLY, and keep same format for output (kmall.mrz)
			dg_offsets = [x for x, y in zip(self.msgoffset, self.msgtype) if y == "b'#MRZ'"]
			mrzinfo = list()
			for offset in dg_offsets:  # read just header and ping info (adapted from read_EMdgmMRZ in kmall module)
				self.FID.seek(offset, 0)
				start = self.FID.tell()
				dg = {}
				dg['header'] = self.read_EMdgmHeader()
				self.FID.seek(16, 1)  # skip readEMdgmMpartition (2H = 4) and readEMdgmMbody (2H8B = 12)
				dg['pingInfo'] = self.read_EMdgmMRZ_pingInfo()

				# Seek to end of the packet
				self.FID.seek(start + dg['header']['numBytesDgm'], 0)
				dg['start_byte'] = offset

				# print('parsed = ', parsed)
				mrzinfo.append(dg)

			# convert list of dicts to dict of lists
			mrzinfo_final = self.listofdicts2dictoflists(mrzinfo)
			setattr(self, 'mrz', mrzinfo_final)  # kmall.mrz will include ping info only, not full soundings

		elif dg_name in list(dg_types):  # extract whole datagrams
			print('dg_name =', dg_name, ' is in dg_types')
			print('searching for ', "b'#" + dg_name + "'")
			dg_offsets = [x for x, y in zip(self.msgoffset, self.msgtype) if y == "b'#" + dg_name + "'"]  # + "]
			# print('got dg_offsets = ', dg_offsets)

			dg = list()
			for offset in dg_offsets:  # store all datagrams of this type
				self.FID.seek(offset, 0)
				parsed = dg_types[dg_name]()
				parsed['start_byte'] = offset
				# print('parsed = ', parsed)
				dg.append(parsed)

			# convert list of dicts to dict of lists
			print('setting attribute with dg_name.lower()=', dg_name.lower())
			dg_final = self.listofdicts2dictoflists(dg)
			setattr(self, dg_name.lower(), dg_final)

		self.FID.seek(0, 0)

		return

	def extract_pinginfo(self):  # extract dicts of datagram types, store in kmall_data class
		# dict of allowable dg_names and associated dg IDs; based on extract_attitude method in kmall module
		if self.Index is None:
			self.index_file()

		if self.FID is None:
			self.OpenFiletoRead()

		# get offsets for MRZ datagrams (contain pingInfo to be used for sorting/searching runtime params)
		dg_offsets = [x for x, y in zip(self.msgoffset, self.msgtype) if y == "b'#MRZ'"]
		print('got dg_offsets = ', dg_offsets)

		pinginfo = list()
		for offset in dg_offsets:  # read just header and ping info (copied from read_EMdgmMRZ method in kmall module
			self.FID.seek(offset, 0)
			start = self.FID.tell()
			dg = {}
			dg['header'] = self.read_EMdgmHeader()
			dg['pingInfo'] = self.read_EMdgmMRZ_pingInfo()

			# Seek to end of the packet.
			self.FID.seek(start + dg['header']['numBytesDgm'], 0)
			dg['start_byte'] = offset

			# print('parsed = ', parsed)
			pinginfo.append(dg)

		# convert list of dicts to dict of lists
		pinginfo_final = self.listofdicts2dictoflists(dg)
		setattr(self, 'mrz', pinginfo_final)  # kmall.mrz will include ping info only, not full soundings

		self.FID.seek(0, 0)

		return

class NewPopup(QtWidgets.QWidget): # new class for additional plots
    def __init__(self):
        QtWidgets.QWidget.__init__(self)


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)

    main = MainWindow()
    main.show()

    sys.exit(app.exec_())
