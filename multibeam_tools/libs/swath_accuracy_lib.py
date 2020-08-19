"""Functions for swath accuracy plotting in NOAA / MAC echosounder assessment tools"""

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
import pickle
import sys
import numpy as np

# add path to external module common_data_readers for pyinstaller
sys.path.append('C:\\Users\\kjerram\\Documents\\GitHub')

from matplotlib import colors
from matplotlib import colorbar
from matplotlib import patches
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
import multibeam_tools.libs.parseEM
from multibeam_tools.libs.file_fun import *
from common_data_readers.python.kongsberg.kmall import kmall
from time import process_time
from scipy.interpolate import interp1d
from copy import deepcopy
import struct

try:
    from PySide2 import QtWidgets, QtGui
    from PySide2.QtGui import QDoubleValidator
    from PySide2.QtCore import Qt, QSize
except ImportError as e:
    print(e)
    from PyQt5 import QtWidgets, QtGui
    from PyQt5.QtGui import QDoubleValidator
    from PyQt5.QtCore import Qt, QSize
import pyproj
import matplotlib.pyplot as plt
import numpy as np
# from matplotlib import colors
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import multibeam_tools.libs.readEM
from scipy.interpolate import griddata
# from multibeam_tools.libs.gui_widgets import *
from multibeam_tools.libs.swath_accuracy_lib import *
from multibeam_tools.libs.swath_fun import *
from multibeam_tools.libs.file_fun import *


def setup(self):
	self.xline = {}
	self.ref_surf = {}
	# initialize other necessities
	# self.print_updates = True
	# self.print_updates = False
	# self.det = {}  # detection dict (new data)
	# self.det_archive = {}  # detection dict (archive data)
	# self.spec = {}  # dict of theoretical coverage specs
	# self.filenames = ['']  # initial file list
	# self.input_dir = ''  # initial input dir
	self.output_dir = os.getcwd()  # save output in cwd unless otherwise selected
	# self.clim_last_user = {'depth': [0, 1000], 'backscatter': [-50, -20]}
	# self.last_cmode = 'depth'
	# self.cbarbase = None  # initial colorbar
	# self.legendbase = None  # initial legend
	# self.cbar_font_size = 8  # colorbar/legend label size
	# self.cbar_title_font_size = 8  # colorbar/legend title size
	# self.cbar_loc = 1  # set upper right as default colorbar/legend location
	# self.n_points_max_default = 50000  # default maximum number of points to plot in order to keep reasonable speed
	# self.n_points_max = 50000
	# # self.n_points_plotted = 0
	# # self.n_points_plotted_arc = 0
	# self.dec_fac_default = 1  # default decimation factor for point count
	# self.dec_fac = 1
	# self.rtp_angle_buffer_default = 0  # default runtime angle buffer
	# self.rtp_angle_buffer = 0  # +/- deg from runtime parameter swath angle limit to filter RX angles
	# self.x_max = 0.0
	# self.z_max = 0.0
	self.model_list = ['EM 2040', 'EM 302', 'EM 304', 'EM 710', 'EM 712', 'EM 122', 'EM 124']
	# self.cmode_list = ['Depth', 'Backscatter', 'Ping Mode', 'Pulse Form', 'Swath Mode', 'Solid Color']
	# self.top_data_list = []
	# self.clim_list = ['All data', 'Filtered data', 'Fixed limits']
	self.depth_ref_list = ['Waterline']  # , 'Origin', 'TX Array', 'Raw Data']
	self.unit_mode = '%WD'  # default plot as % Water Depth; option to toggle alternative meters


def init_swath_ax(self):  # set initial swath parameters
	self.ax1 = self.swath_figure.add_subplot(211)
	self.ax2 = self.swath_figure.add_subplot(212)

	self.x_max_default = 75
	self.x_spacing_default = 15
	self.y_max_std_default = 0.5  # max y range of depth st. dev. plot (top subplot)
	self.y_max_bias_default = 1  # max +/- y range of depth bias (raw, mean, +/- 1 sigma, bottom subplot)

	self.x_max_custom = self.x_max_default  # store future custom entries
	self.x_spacing_custom = self.x_spacing_default
	self.y_max_bias_custom = self.y_max_bias_default
	self.y_max_std_custom = self.y_max_std_default

	self.max_beam_angle_tb.setText(str(self.x_max_default))
	self.angle_spacing_tb.setText(str(self.x_spacing_default))
	self.max_bias_tb.setText(str(self.y_max_bias_default))
	self.max_std_tb.setText(str(self.y_max_std_default))

	self.cruise_name = ''
	self.swath_ax_margin = 1.1  # scale axes to multiple of max data in each direction
	self.fsize_title = 12
	self.fsize_label = 10
	self.lwidth = 1  # line width
	add_grid_lines(self)
	update_axes(self)
	self.color = QtGui.QColor(0, 0, 0)  # set default solid color to black for new data
	self.archive_color = QtGui.QColor('darkGray')


def update_buttons(self):
	# enable or disable file selection and calc_accuracy buttons depending on loaded files
	get_current_file_list(self)
	fnames_ref = [fr for fr in self.filenames if '.xyz' in fr]
	# fnames_dens = [fd for fd in self.filenames if '.xyd' in fd]
	fnames_xline = [fx for fx in self.filenames if '.all' in fx]
	self.add_ref_surf_btn.setEnabled(len(fnames_ref) == 0)  # enable ref surf selection only if none loaded
	# self.add_dens_surf_btn.setEnabled(len(fnames_dens) == 0)  # enable ref surf selection only if none loaded

	# enable calc_accuracy button only if one ref surf and at least one crossline are loaded
	if len(fnames_ref) == 1 and len(fnames_xline) > 0:
		self.calc_accuracy_btn.setEnabled(True)
		# self.calc_accuracy_btn.setStyleSheet("background-color: yellow")
	else:
		self.calc_accuracy_btn.setEnabled(False)
		# self.calc_accuracy_btn.setStyleSheet("background-color: none")


def add_ref_file(self, ftype_filter, input_dir='HOME', include_subdir=False, ):
	# add single reference surface file with extensions in ftype_filter
	fname = add_files(self, ftype_filter, input_dir, include_subdir)
	update_file_list(self, fname)
	update_buttons(self)

def add_dens_file(self, ftype_filter, input_dir='HOME', include_subdir=False, ):
	# add single density surface file with extensions in ftype_filter
	fname = add_files(self, ftype_filter, input_dir, include_subdir)
	update_file_list(self, fname)
	update_buttons(self)

def add_acc_files(self, ftype_filter, input_dir='HOME', include_subdir=False, ):
	# add accuracy crossline files with extensions in ftype_filter from input_dir and subdir if desired
	fnames = add_files(self, ftype_filter, input_dir, include_subdir)
	update_file_list(self, fnames)
	update_buttons(self)


def remove_acc_files(self):  # remove selected files only
	get_current_file_list(self)
	selected_files = self.file_list.selectedItems()
	fnames_ref = [f for f in self.filenames if '.xyz' in f]
	# fnames_dens = [f for f in self.filenames if '.xyd' in f]
	fnames_xline = [f for f in self.filenames if '.all' in f]

	print('in remove_acc_files, fnames_xline is', fnames_xline)

	if len(fnames_xline) + len(fnames_ref) == 0: # all .all and .xyz files have been removed, reset det dicts
	# if len(fnames_xline) == 0:  # if all .all files have been removed, reset det dicts
		self.xline = {}
		# self.bin_beamwise()  # call bin_beamwise with empty xline results to clear plots
#            self.xline_archive = {}

	elif not selected_files: # files exist but nothing is selected
		update_log(self, 'No files selected for removal.')
		return

	else:  # remove only the files that have been selected
		for f in selected_files:
			fname = f.text().split('/')[-1]
#                print('working on fname', fname)
			self.file_list.takeItem(self.file_list.row(f))
			update_log(self, 'Removed ' + fname)

			try: # try to remove detections associated with this file
				if '.all' in fname:
					# print('trying to get indices of det matching .all file', f)
					# get indices of soundings in det dict with matching filenames
					i = [j for j in range(len(self.xline['fname'])) if self.xline['fname'][j] == fname]

					for k in self.xline.keys():  # loop through all keys and remove values at these indices
						print(k)
						self.xline[k] = np.delete(self.xline[k],i).tolist()

				elif '.xyz' in fname:
					self.ref_surf = {}
					self.add_ref_surf_btn.setEnabled(True)  # enable button to add replacement reference surface

				# elif '.xyd' in fname:
				# 	self.ref_surf = {}
				# 	self.add_dens_surf_btn.setEnabled(True)  # enable button to add replacement density surface

			except:  # will fail if detection dict has not been created yet (e.g., if calc_coverage has not been run)
#                    update_log(self, 'Failed to remove soundings stored from ' + fname)
				pass

	# call bin_beamwise() to update results if the single .xyz ref surface or any of the .all files are removed
	bin_beamwise(self)
	update_buttons(self)
	refresh_plot(self)  # refresh with updated (reduced or cleared) detection data

# ###########  FUTURE: UPDATE WITH STREAMLINED FILE REMOVAL SIMILAR TO COVERAGE PLOTTER
#
# def remove_acc_files(self, clear_all=False):
# 	# remove selected files or clear all files, update det and spec dicts accordingly
# 	removed_files = remove_files(self, clear_all)
#
# 	if clear_all:  # clear all
# 		self.det = {}
# 		self.det_archive = {}
# 		self.spec = {}
# 		update_log(self, 'Cleared all files')
# 		self.current_file_lbl.setText('Current File [0/0]:')
# 		self.calc_pb.setValue(0)
#
# 	else:
# 		remove_data(self, removed_files)
#
# 	update_show_data_checks(self)
# 	refresh_plot(self, call_source='remove_files')  # refresh with updated (reduced or cleared) detection data
#
#
# def remove_data(self, removed_files):
# 	# remove data in specified filenames from detection and spec dicts
# 	for f in removed_files:
# 		fname = f.text().split('/')[-1]
#
# 		try:  # try to remove detections associated with this file
# 			# get indices of soundings in det dict with matching .all or .kmall filenames
# 			if self.det and any(fext in fname for fext in ['.all', '.kmall']):
# 				i = [j for j in range(len(self.det['fname'])) if self.det['fname'][j] == fname]
# 				for k in self.det.keys():  # loop through all keys and remove values at these indices
# 					self.det[k] = np.delete(self.det[k], i).tolist()
#
# 			elif self.det_archive and '.pkl' in fname:  # remove archive data
# 				self.det_archive.pop(fname, None)
#
# 			elif self.spec and '.txt' in fname:  # remove spec data
# 				self.spec.pop(fname, None)
#
# 		except:  # will fail if det dict has not been created yet (e.g., if calc_coverage has not been run)
# 			update_log(self, 'Failed to remove soundings from ' + fname)
#


def clear_files(self):
	self.file_list.clear()  # clear the file list display
	self.filenames = []  # clear the list of (paths + files) passed to calc_coverage
	self.xline = {}  # clear current non-archive detections
	self.ref_surf = {}  # clear ref surf data
	bin_beamwise(self)  # call bin_beamwise with empty self.xline to reset all other binned results
	remove_acc_files(self)  # remove files and refresh plot
	update_log(self, 'Cleared all files')
	self.current_file_lbl.setText('Current File [0/0]:')
	self.calc_pb.setValue(0)
	self.add_ref_surf_btn.setEnabled(True)


def calc_accuracy(self):
	# calculate accuracy of soundings from at least one crossline over exactly one reference surface
	update_log(self, 'Starting accuracy calculations')
	parse_ref_surf(self)  # parse the ref surf
	# self.apply_masks() # FUTURE: flag outlier soundings and mask nodes for density, slope
	parse_crosslines(self)  # parse the crossline(s)
	calc_z_final(self)  # adjust sounding depths to desired reference and flip sign as necessary
	convert_crossline_utm(self)  # convert crossline X,Y to UTM zone of reference surface
	calc_dz_from_ref_interp(self)  # interpolate ref surf onto sounding positions, take difference
	bin_beamwise(self)  # bin the results by beam angle
	update_log(self, 'Finished calculating accuracy')
	update_log(self, 'Plotting accuracy results')
	refresh_plot(self)  # refresh the plot


def parse_ref_surf(self):
	# parse the loaded reference surface .xyz file
	# ref grid is assumed UTM projection with meters east, north, depth (+Z up), e.g., export from processing
	self.ref_surf = {}
	# self.get_current_file_list()
	fnames_xyz = get_new_file_list(self, ['.xyz'], [])  # list .xyz files
	num_ref_files = len(fnames_xyz)
	print('fnames_xyz is', fnames_xyz)
	# fnames_xyz = [f for f in self.filenames if '.xyz' in f]  # get all .xyz file names
	# fnames_xyz = [f for f in fnames_new if '.xyz' in f]  # get all .xyz file names

	if len(fnames_xyz) != 1:  # warn user to add exactly one ref grid
		update_log(self, 'Please add one reference grid .xyz file in a UTM projection')
		pass

	else:
		fname_ref = fnames_xyz[0]
		self.ref_surf['fname'] = fname_ref
		print(fname_ref)
		fid_ref = open(fname_ref, 'r')
		e_ref, n_ref, z_ref = [], [], []
		for line in fid_ref:
			temp = line.replace('\n', '').split(",")
			e_ref.append(temp[0])  # easting
			n_ref.append(temp[1])  # northing
			z_ref.append(temp[2])  # up

	# convert to arrays with Z positive up; vertical datum for ref grid and crosslines is assumed same for now
	self.ref_surf['e'] = np.array(e_ref, dtype=np.float32)
	self.ref_surf['n'] = np.array(n_ref, dtype=np.float32)
	self.ref_surf['z'] = -1 * np.abs(np.array(z_ref, dtype=np.float32))  # ensure grid is +Z UP (neg. depths)
	self.ref_surf['utm_zone'] = self.ref_proj_cbox.currentText()
	update_log(self, 'Imported ref grid: ' + fname_ref.split('/')[-1] + ' with ' +
			   str(len(self.ref_surf['z'])) + ' nodes')
	update_log(self, 'Ref grid is assigned UTM zone ' + self.ref_surf['utm_zone'])

	# determine grid size and confirm for user
	ref_dE = np.mean(np.diff(np.sort(np.unique(self.ref_surf['e']))))
	ref_dN = np.mean(np.diff(np.sort(np.unique(self.ref_surf['n']))))

	if ref_dE == ref_dN:
		self.ref_cell_size = ref_dE
		update_log(self, 'Imported ref grid has uniform cell size: ' + str(self.ref_cell_size) + ' m')
	else:
		self.ref_cell_size = np.max([ref_dE, ref_dN])
		update_log(self,
			'WARNING: Uneven grid cell spacing (easting: ' + str(ref_dE) + ', northing: ' + str(ref_dN) + ')')


	######## add density surface if available - this is useful for Qimera .xyz files that do not include density
	# fnames_xyd = get_new_file_list(self, ['.xyd'], [])  # list .xyz files
	# num_dens_files = len(fnames_xyd)
	# print('fnames_xyd is', fnames_xyd)
	# # fnames_xyz = [f for f in self.filenames if '.xyz' in f]  # get all .xyz file names
	# # fnames_xyz = [f for f in fnames_new if '.xyz' in f]  # get all .xyz file names
	#
	# if len(fnames_xyd) != 1:  # warn user to add exactly one density grid
	# 	update_log(self, 'Add one density grid .xyd text file corresponding to the loaded .xyz surface')
	# 	pass
	#
	# else:
	# 	update_log(self, 'Processing reference surface density')
	# 	fname_dens = fnames_xyd[0]
	# 	self.ref_surf['fname_dens'] = fname_dens
	# 	print(fname_dens)
	# 	fid_dens = open(fname_dens, 'r')
	# 	e_dens, n_dens, c_dens = [], [], []
	# 	for line in fid_dens:
	# 		temp = line.replace('\n', '').split(",")
	# 		e_dens.append(temp[0])  # easting
	# 		n_dens.append(temp[1])  # northing
	# 		c_dens.append(temp[2])  # count
	#
	# 	# convert to arrays
	# 	e_dens = np.array(e_dens, dtype=np.float32)
	# 	n_dens = np.array(n_dens, dtype=np.float32)
	# 	c_dens = np.array(c_dens, dtype=np.float32)
	#
	# 	self.ref_surf['density'] = np.zeros_like(self.ref_surf['z'])
	# 	# loop through all nodes in reference surface, attach density
	# 	for i in range(len(self.ref_surf['z'])):
	# 		print(i)
	# 		idx_e = np.where(e_dens == self.ref_surf['e'][i])  #, e_dens)
	# 		idx_n = np.where(n_dens == self.ref_surf['n'][i])  #, n_dens)
	# 		# print(idx_e)
	# 		# print(idx_n)
	# 		# idx_match = np.logical_and(idx_e, idx_n)
	# 		idx_match = set(idx_e[0].tolist() + idx_n[0].tolist())
	# 		# gical_and(idx_e, idx_n)
	#
	# 		# idx_match = np.logical_and(np.isin(self.ref_surf['e'][i], e_dens),
	# 		# 						   np.isin(self.ref_surf['n'][i], n_dens))
	# 		# print(idx_match)
	#
	# 		# if sum(idx_match) == 1:
	# 		if len(idx_match) == 1:
	# 			self.ref_surf['density'][i] = c_dens[idx_match][0]
	#
	#
	# 	print('finished assigning density, first 10 values look like')
	# 	print(self.ref_surf['e'][0:10])
	# 	print(self.ref_surf['n'][0:10])
	# 	print(self.ref_surf['z'][0:10])
	# 	print(self.ref_surf['density'][0:10])

	# convert to arrays
	# self.ref_surf['e'] = np.array(e_ref, dtype=np.float32)
	# self.ref_surf['n'] = np.array(n_ref, dtype=np.float32)
	# self.ref_surf['z'] = np.array(z_ref, dtype=np.float32))
	# update_log(self, 'Imported density grid: ' + fname_dens.split('/')[-1] + ' with ' +
	# 		   str(len(self.ref_surf['z'])) + ' nodes')


def mask_ref_surf(self):
	# mask the reference surface for slope and sounding density, as available
	print('FUTURE: mask the ref surf')
	# as a starting point, calculate simple gradient


def parse_crosslines(self):
	# parse crosslines
	update_log(self, 'Parsing accuracy crosslines')
	try:
		fnames_xline = list(set(self.xline['fname']))  # make list of unique filenames already in detection dict
	except:
		fnames_xline = []  # self.xline has not been created yet; initialize this and self.xline detection dict
		self.xline = {}

	# fnames_new_all = self.get_new_file_list('.all', fnames_xline)  # list new .all files not included in det dict
	fnames_new = get_new_file_list(self, ['.all', '.kmall'], fnames_xline)  # list all files not in xline dict
	num_new_files = len(fnames_new)
	update_log(self, 'Found ' + str(len(fnames_new)) + ' new crossline .all files')

	if num_new_files == 0:
		update_log(self, 'No new .all or .kmall crosslines added.  Please add new file(s) and calculate accuracy')

	else:
		# if len(fnames_new_all) > 0:  # proceed if there is at least one .all file that does not exist in det dict
		update_log(self, 'Calculating accuracy from ' + str(num_new_files) + ' new file(s)')
		# update_log(self, 'Calculating accuracy from ' + str(len(fnames_new_all)) + ' new file(s)')
		QtWidgets.QApplication.processEvents()  # try processing and redrawing the GUI to make progress bar update
		data_new = {}

		# update progress bar and log
		self.calc_pb.setValue(0)  # reset progress bar to 0 and max to number of files
		self.calc_pb.setMaximum(len(fnames_new))

		for f in range(len(fnames_new)):
			# for f in range(len(fnames_new_all)):         # read previously unparsed files
			fname_str = fnames_new[f].rsplit('/')[-1]
			self.current_file_lbl.setText(
				'Parsing new file [' + str(f + 1) + '/' + str(num_new_files) + ']:' + fname_str)
			QtWidgets.QApplication.processEvents()
			ftype = fname_str.rsplit('.', 1)[-1]

			if ftype == 'all':
				# parse IPSTART73, RRA78, POS80, RTP82, XYZ88
				# data_new[f] = multibeam_tools.libs.readEM.parseEMfile(fnames_new[f],
				#                                                       parse_list=[73, 78, 80, 82, 88],
				#                                                       print_updates=False)
				data_new[f] = readALLswath(self, fnames_new[f], print_updates=False, parse_outermost_only=False)

			elif ftype == 'kmall':

				km = kmall.kmall(fnames_new[f])
				km.verbose = 0
				km.index_file()
				km.report_packet_types()
				km.extract_dg('MRZ')
				km.extract_dg('IOP')
				km.extract_dg('IIP')
				# print('km is', km)
				km.closeFile()
				data_new[f] = {'fname': fnames_new[f], 'XYZ': km.mrz['soundings'],
							   'HDR': km.mrz['header'], 'RTP': km.mrz['pinginfo'],
							   'IOP': km.iop, 'IP': km.iip}

				print('data_new[IP]=', data_new[f]['IP'])
				print('IP text =', data_new[f]['IP']['install_txt'])

			else:
				update_log(self, 'Warning: Skipping unrecognized file type for ' + fname_str)

			update_log(self, 'Parsed file ' + fname_str)
			update_prog(self, f + 1)

		# regardless of data source, convert XYZ to lat and lon; maintain depth as reported in file
		self.data_new = multibeam_tools.libs.readEM.convertXYZ(data_new,
															   print_updates=True)  # convert XYZ datagrams to lat, lon, depth

		# self.data = multibeam_tools.libs.readEM.interpretMode(data, print_updates=False) # interpret modes
		self.data_new = interpretMode(self, data_new, print_updates=False)  # interpret modes

		files_OK, EM_params = multibeam_tools.libs.readEM.verifyMode(self.data_new)  # check install and runtime params

		if not files_OK:  # warn user if inconsistencies detected (perhaps add logic later for sorting into user-selectable lists for archiving and plotting)
			update_log(self, 'WARNING! CROSSLINES HAVE INCONSISTENT MODEL, S/N, or RUNTIME PARAMETERS')

		# det_new = multibeam_tools.libs.readEM.sortAccuracyDetections(data_new, print_updates=False)  # sort new accuracy soundings
		det_new = sortAccDetections(self, self.data_new, print_updates=False)  # sort new accuracy soundings

		if len(self.xline) is 0:  # if detection dict is empty, store all new detections
			self.xline = det_new

		else:  # otherwise, append new detections to existing detection dict
			for key, value in det_new.items():  # loop through the new data and append to existing self.xline
				self.xline[key].extend(value)

		update_log(self, 'Finished parsing ' + str(num_new_files) + ' new file(s)')
		self.current_file_lbl.setText('Current File [' + str(f + 1) + '/' + str(num_new_files) +
									  ']: Finished parsing crosslines')

	# else:  # if no .all files are listed
	#     update_log(self, 'No new crossline .all file(s) added')

	#        self.xline['filenames'] = fnames  # store updated file list
	self.calc_accuracy_btn.setStyleSheet("background-color: none")  # reset the button color to default


def interpretMode(self, data, print_updates):
	# interpret runtime parameters for each ping and store in XYZ dict prior to sorting
	for f in range(len(data)):
		missing_mode = False
		ftype = data[f]['fname'].rsplit('.', 1)[1]

		if ftype == 'all':  # interpret .all modes from binary string
			# KM ping modes for 1: EM3000, 2: EM3002, 3: EM2000,710,300,302,120,122, 4: EM2040
			# See KM runtime parameter datagram format for models listed
			# list of models that originally used this datagram format AND later models that produce .kmall
			# that may have been converted to .all using Kongsberg utilities during software transitions; note that
			# EM2040 is a special case, and use of this list may depend on mode being interpreted below
			all_model_list = [710, 712, 300, 302, 304, 120, 122, 124]

			mode_dict = {'3000': {'0000': 'Nearfield (4 deg)', '0001': 'Normal (1.5 deg)', '0010': 'Target Detect'},
						 '3002': {'0000': 'Wide TX (4 deg)', '0001': 'Normal TX (1.5 deg)'},
						 '9999': {'0000': 'Very Shallow', '0001': 'Shallow', '0010': 'Medium',
								  '0011': 'Deep', '0100': 'Very Deep', '0101': 'Extra Deep'},
						 '2040': {'0000': '200 kHz', '0001': '300 kHz', '0010': '400 kHz'}}

			# pulse and swath modes for EM2040, 710/12, 302, 122, and later models converted from .kmall to .all
			pulse_dict = {'00': 'CW', '01': 'Mixed', '10': 'FM'}
			swath_dict = {'00': 'Single Swath', '01': 'Dual Swath (Fixed)', '10': 'Dual Swath (Dynamic)'}

			# loop through all pings
			for p in range(len(data[f]['XYZ'])):
				bin_temp = "{0:b}".format(data[f]['XYZ'][p]['MODE']).zfill(8)  # binary str
				ping_temp = bin_temp[-4:]  # last 4 bytes specify ping mode based on model
				model_temp = data[f]['XYZ'][p]['MODEL']

				# check model to reference correct key in ping mode dict
				if np.isin(data[f]['XYZ'][p]['MODEL'], all_model_list + [2000, 1002]):
					model_temp = '9999'  # set model_temp to reference mode_list dict for all applicable models

				data[f]['XYZ'][p]['PING_MODE'] = mode_dict[model_temp][ping_temp]

				# interpret pulse form and swath mode based on model
				if np.isin(data[f]['XYZ'][p]['MODEL'], all_model_list + [2040]):  # reduced models for swath and pulse
					data[f]['XYZ'][p]['SWATH_MODE'] = swath_dict[bin_temp[-8:-6]]  # swath mode from binary str
					data[f]['XYZ'][p]['PULSE_FORM'] = pulse_dict[bin_temp[-6:-4]]  # pulse form from binary str

				else:  # specify NA if not in model list for this interpretation
					data[f]['XYZ'][p]['PULSE_FORM'] = 'NA'
					data[f]['XYZ'][p]['SWATH_MODE'] = 'NA'
					missing_mode = True

				if print_updates:
					ping = data[f]['XYZ'][p]
					print('file', f, 'ping', p, 'is', ping['PING_MODE'], ping['PULSE_FORM'], ping['SWATH_MODE'])

		elif ftype == 'kmall':  # interpret .kmall modes from parsed fields
			# depth mode list for AUTOMATIC selection; add 100 for MANUAL selection (e.g., '101': 'Shallow (Manual))
			mode_dict = {'0': 'Very Shallow', '1': 'Shallow', '2': 'Medium', '3': 'Deep',
						 '4': 'Deeper', '5': 'Very Deep', '6': 'Extra Deep', '7': 'Extreme Deep'}

			# pulse and swath modes for .kmall (assumed not model-dependent, applicable for all SIS 5 installs)
			pulse_dict = {'0': 'CW', '1': 'Mixed', '2': 'FM'}
			swath_dict = {'0': 'Single Swath', '1': 'Dual Swath'}

			for p in range(len(data[f]['XYZ'])):
				# get depth mode from list and add qualifier if manually selected
				manual_mode = data[f]['RTP'][p]['depthMode'] >= 100  # check if manual selection
				mode_idx = str(data[f]['RTP'][p]['depthMode'])[-1]  # get last character for depth mode
				data[f]['XYZ'][p]['PING_MODE'] = mode_dict[mode_idx] + ('(Manual)' if manual_mode else '')

				# get pulse form from list
				data[f]['XYZ'][p]['PULSE_FORM'] = pulse_dict[str(data[f]['RTP'][p]['pulseForm'])]

				# assumed dual swath if distBtwSwath >0% of req'd dist (0 if unused, assume single swath)
				data[f]['XYZ'][p]['SWATH_MODE'] = swath_dict[str(int(data[f]['RTP'][p]['distanceBtwSwath'] > 0))]

				if print_updates:
					ping = data[f]['XYZ'][p]
					print('file', f, 'ping', p, 'is', ping['PING_MODE'], ping['PULSE_FORM'], ping['SWATH_MODE'])

		else:
			print('UNSUPPORTED FTYPE --> NOT INTERPRETING MODES!')

		if missing_mode:
			update_log(self, 'Warning: missing mode info in ' + data[f]['fname'].rsplit('/', 1)[-1] +
					   '\nPoint color options may be limited due to missing mode info')

	if print_updates:
		print('\nDone interpreting modes...')

	return data


def sortAccDetections(self, data, print_updates=False):
	# sort through KMALL pings and store valid soundings, BS, and mode after converting to XYZ with convertXYZ
	det_key_list = ['fname', 'date', 'time', 'model', 'sn',
					'lat', 'lon', 'x', 'y', 'z', 'z_re_wl', 'n', 'e', 'utm_zone', 'bs',
					'ping_mode', 'pulse_form', 'swath_mode',
					'tx_x_m', 'tx_y_m', 'tx_z_m', 'aps_x_m', 'aps_y_m', 'aps_z_m', 'wl_z_m',
					'rx_angle', 'max_port_deg', 'max_stbd_deg', 'max_port_m', 'max_stbd_m']  # mode_bin

	det = {k: [] for k in det_key_list}

	# examine detection info across swath, find outermost valid soundings for each ping
	for f in range(len(data)):  # loop through all data

		print('in sortAccDetections with data[f] keys =', data[f].keys())
		# set up keys for dict fields of interest from parsers for each file type (.all or .kmall)
		ftype = data[f]['fname'].rsplit('.', 1)[1]
		key_idx = int(ftype == 'kmall')  # keys in data dicts depend on parser used, get index to select keys below
		det_int_threshold = [127, 0][key_idx]  # threshold for valid sounding (.all  <128 and .kmall == 0)
		det_int_key = ['RX_DET_INFO', 'detectionType'][key_idx]  # key for detect info depends on ftype
		depth_key = ['RX_DEPTH', 'z_reRefPoint_m'][key_idx]  # key for depth
		across_key = ['RX_ACROSS', 'y_reRefPoint_m'][key_idx]  # key for acrosstrack distance
		along_key = ['RX_ALONG', 'z_reRefPoint_m'][key_idx]  # key for alongtrack distance
		bs_key = ['RX_BS', 'reflectivity1_dB'][key_idx]  # key for backscatter in dB
		angle_key = ['RX_ANGLE', 'beamAngleReRx_deg'][key_idx]  # key for RX angle re RX array

		for p in range(len(data[f]['XYZ'])):  # loop through each ping
			# print('working on ping number ', p)
			det_int = data[f]['XYZ'][p][det_int_key]  # get detection integers for this ping
			det_idx = [i for i, v in enumerate(det_int) if v <= det_int_threshold]  # indices of all valid detections

			# extend swath data from appropriate keys/values in data dicts
			# future general sorter: accuracy, keep all valid det_int; coverage, reduce for outermost valid det_int
			det['fname'].extend([data[f]['fname'].rsplit('/')[-1]]*len(det_idx))  # store fname for each det

			det['x'].extend([data[f]['XYZ'][p][along_key][i] for i in det_idx])  # as parsed
			det['y'].extend([data[f]['XYZ'][p][across_key][i] for i in det_idx])  # as parsed
			det['z'].extend([data[f]['XYZ'][p][depth_key][i] for i in det_idx])  # as parsed
			det['lat'].extend([data[f]['XYZ'][p]['SOUNDING_LAT'][i] for i in det_idx])
			det['lon'].extend([data[f]['XYZ'][p]['SOUNDING_LON'][i] for i in det_idx])
			det['n'].extend([data[f]['XYZ'][p]['SOUNDING_N'][i] for i in det_idx])
			det['e'].extend([data[f]['XYZ'][p]['SOUNDING_E'][i] for i in det_idx])
			# det['z_re_wl'].extend([data[f]['XYZ'][p]['SOUNDING_Z'][i] for i in det_idx])  # corrected to waterline
			det['utm_zone'].extend([data[f]['XYZ'][p]['SOUNDING_UTM_ZONE']]*len(det_idx))
			det['bs'].extend([data[f]['XYZ'][p][bs_key][i] for i in det_idx])
			det['ping_mode'].extend([data[f]['XYZ'][p]['PING_MODE']]*len(det_idx))
			det['pulse_form'].extend([data[f]['XYZ'][p]['PULSE_FORM']]*len(det_idx))
			det['swath_mode'].extend([data[f]['XYZ'][p]['SWATH_MODE']]*len(det_idx))


			if ftype == 'all':  # .all store date and time from ms from midnight
				dt = datetime.datetime.strptime(str(data[f]['XYZ'][p]['DATE']), '%Y%m%d') + \
					 datetime.timedelta(milliseconds=data[f]['XYZ'][p]['TIME'])
				det['date'].extend([dt.strftime('%Y-%m-%d')]*len(det_idx))
				det['time'].extend([dt.strftime('%H:%M:%S.%f')]*len(det_idx))
				# det['rx_angle'].extend([data[f]['RRA_78'][p][angle_key][i] for i in det_idx])
				det['max_port_deg'].extend([data[f]['XYZ'][p]['MAX_PORT_DEG']]*len(det_idx))
				det['max_stbd_deg'].extend([data[f]['XYZ'][p]['MAX_STBD_DEG']]*len(det_idx))
				det['max_port_m'].extend([data[f]['XYZ'][p]['MAX_PORT_M']]*len(det_idx))
				det['max_stbd_m'].extend([data[f]['XYZ'][p]['MAX_STBD_M']]*len(det_idx))

				# print('in ping', p, 'with data[f][IP_START] =', data[f]['IP_start'])
				det['tx_x_m'].extend([data[f]['XYZ'][p]['TX_X_M']]*len(det_idx))
				det['tx_y_m'].extend([data[f]['XYZ'][p]['TX_Y_M']]*len(det_idx))
				det['tx_z_m'].extend([data[f]['XYZ'][p]['TX_Z_M']]*len(det_idx))
				det['aps_x_m'].extend([data[f]['XYZ'][p]['APS_X_M']]*len(det_idx))
				det['aps_y_m'].extend([data[f]['XYZ'][p]['APS_Y_M']] * len(det_idx))
				det['aps_z_m'].extend([data[f]['XYZ'][p]['APS_Z_M']] * len(det_idx))
				det['wl_z_m'].extend([data[f]['XYZ'][0]['WL_Z_M']]*len(det_idx))

			elif ftype == 'kmall':  # .kmall store date and time from datetime object
				det['date'].extend([data[f]['HDR'][p]['dgdatetime'].strftime('%Y-%m-%d')]*len(det_idx))
				det['time'].extend([data[f]['HDR'][p]['dgdatetime'].strftime('%H:%M:%S.%f')]*len(det_idx))
				det['aps_x_m'].extend([0]*len(det_idx))  # not needed for KMALL; append 0 as placeholder
				det['aps_y_m'].extend([0]*len(det_idx))  # not needed for KMALL; append 0 as placeholder
				det['aps_z_m'].extend([0]*len(det_idx))  # not needed for KMALL; append 0 as placeholder

				# get first installation parameter datagram, assume this does not change in file
				ip_text = data[f]['IP']['install_txt'][0]
				# get TX array offset text: EM304 = 'TRAI_TX1' and 'TRAI_RX1', EM2040P = 'TRAI_HD1', not '_TX1' / '_RX1'
				ip_tx1 = ip_text.split('TRAI_')[1].split(',')[0].strip()  # all heads/arrays split by comma
				det['tx_x_m'].extend([float(ip_tx1.split('X=')[1].split(';')[0].strip())]*len(det_idx))  # get TX array X offset
				det['tx_y_m'].extend([float(ip_tx1.split('Y=')[1].split(';')[0].strip())]*len(det_idx))  # get TX array Y offset
				det['tx_z_m'].extend([float(ip_tx1.split('Z=')[1].split(';')[0].strip())]*len(det_idx))  # get TX array Z offset
				det['wl_z_m'].extend([float(ip_text.split('SWLZ=')[-1].split(',')[0].strip())]*len(det_idx))  # get waterline Z offset

				# get index of latest runtime parameter timestamp prior to ping of interest; default to 0 for cases
				# where earliest pings in file might be timestamped earlier than first runtime parameter datagram
				# print('working on data f IOP dgdatetime:', data[f]['IOP']['dgdatetime'])
				IOP_idx = max([i for i, t in enumerate(data[f]['IOP']['dgdatetime']) if
							   t <= data[f]['HDR'][p]['dgdatetime']], default=0)

				if data[f]['IOP']['dgdatetime'][IOP_idx] > data[f]['HDR'][p]['dgdatetime']:
					print('*****ping', p, 'occurred before first runtime datagram; using first RTP dg in file')

				# get runtime text from applicable IOP datagram, split and strip at keywords and append values
				rt = data[f]['IOP']['RT'][IOP_idx]  # get runtime text for splitting

				# dict of keys for detection dict and substring to split runtime text at entry of interest
				rt_dict = {'max_port_deg': 'Max angle Port:', 'max_stbd_deg': 'Max angle Starboard:',
						   'max_port_m': 'Max coverage Port:', 'max_stbd_m': 'Max coverage Starboard:'}

				# iterate through rt_dict and append value from split/stripped runtime text
				for k, v in rt_dict.items():
					try:
						det[k].extend([float(rt.split(v)[-1].split('\n')[0].strip())]*len(det_idx))

					except:
						det[k].extend(['NA']*len(det_idx))

				if print_updates:
					print('found IOP_idx=', IOP_idx, 'with IOP_datetime=', data[f]['IOP']['dgdatetime'][IOP_idx])
					print('max_port_deg=', det['max_port_deg'][-1])
					print('max_stbd_deg=', det['max_stbd_deg'][-1])
					print('max_port_m=', det['max_port_m'][-1])
					print('max_stbd_m=', det['max_stbd_m'][-1])

			else:
				print('UNSUPPORTED FTYPE --> NOT SORTING DETECTION!')



	if print_updates:
		print('\nDone sorting detections...')

	return det


def calc_z_final(self):
	# adjust sounding depths to desired reference and flip sign as necessary for comparison to ref surf (positive up)
	_, _, dz_ping = adjust_depth_ref(self.xline, depth_ref=self.ref_cbox.currentText().lower())
	# print('dz_ping has len', len(dz_ping))
	# print('first 20 of xline[z]=', self.xline['z'][0:20])
	# print('first 20 of dz_ping =', dz_ping[0:20])
	z_final = [z + dz for z, dz in zip(self.xline['z'], dz_ping)]  # add dz
	self.xline['z_final'] = (-1 * np.asarray(z_final)).tolist()  # flip sign to neg down and store 'final' soundings


def convert_crossline_utm(self):
	# if necessary, convert crossline X,Y to UTM zone of reference surface
	update_log(self, 'Checking UTM zones of ref grid and crossline(s)')
	ref_utm = self.ref_surf['utm_zone']

	# format xline UTM zone for comparison with ref_utm and use with pyproj; replace zone letter with S if southern
	# hemisphere (UTM zone letter C-M) or N if northern hemisphere (else)
	xline_utm = [utm_str.replace(" ", "") for utm_str in self.xline['utm_zone']]
	xline_utm = [utm_str[:-1] + 'S' if utm_str[-1] <= 'M' else utm_str[:-1] + 'N' for utm_str in xline_utm]
	self.xline['utm_zone'] = xline_utm  # replace with new format

	print('ref surf UTM =', ref_utm)
	# print('first 10 xline UTM =', xline_utm[0:10])
	print('detected xline utm zones:', set(xline_utm))
	# get list of xline utm zones that do not match ref surf utm zone
	xline_utm_list = [u for u in set(xline_utm) if u != ref_utm]

	print('non-matching utm zones:', xline_utm_list)

	if len(xline_utm_list) > 0:  # transform soundings from non-matching xline utm zone(s) into ref utm zone
		update_log(self, 'Found crossline soundings in different UTM zone')

		# define projection of reference surface and numpy array for easier indexing
		p2 = pyproj.Proj(proj='utm', zone=ref_utm, ellps='WGS84')
		xline_e = np.asarray(self.xline['e'])
		xline_n = np.asarray(self.xline['n'])
		N_soundings = len(self.xline['utm_zone'])
		print('N_soundings is originally', N_soundings)

		for u in xline_utm_list:  # for each non-matching xline utm zone, convert those soundings to ref utm
			print('working on non-matching utm zone', u)
			p1 = pyproj.Proj(proj='utm', zone=u, ellps='WGS84')  # define proj of xline soundings

			print('first ten xline_utm are:', xline_utm[0:10])

			idx = [s for s in range(N_soundings) if xline_utm[s] == u]  # get indices of soundings with this zone
			# print('length of idx is', str(len(idx)))
			print('first ten xline_utm for idx matches are:', [xline_utm[i] for i in idx[0:10]])

			(xline_e_new, xline_n_new) = pyproj.transform(p1, p2, xline_e[idx], xline_n[idx])  # transform
			xline_e[idx] = xline_e_new
			xline_n[idx] = xline_n_new

			update_log(self, 'Transformed ' + str(len(idx)) + ' soundings (out of '
					   + str(N_soundings) + ') from ' + u + ' to ' + ref_utm)

			print('fixed the eastings to:', xline_e_new)

		# reassign the final coordinates
		self.xline['e'] = xline_e.tolist()
		self.xline['n'] = xline_n.tolist()
		self.xline['utm_zone'] = [ref_utm] * N_soundings

		print('new xline_easting is', self.xline['e'][0:30])
		print('new xline_northing is', self.xline['n'][0:30])
		print('new utm_zone is', self.xline['utm_zone'][0:30])


def calc_dz_from_ref_interp(self):
	# calculate the difference of each sounding from the reference grid (interpolated onto sounding X, Y position)
	update_log(self, 'Calculating ref grid depths at crossline sounding positions')
	print('N ref_surf nodes e =', len(self.ref_surf['e']), 'with first ten =', self.ref_surf['e'][0:10])
	print('N ref_surf nodes n =', len(self.ref_surf['n']), 'with first ten =', self.ref_surf['n'][0:10])
	print('N ref_surf nodes z =', len(self.ref_surf['z']), 'with first ten =', self.ref_surf['z'][0:10])

	print('N xline soundings e =', len(self.xline['e']), 'with first ten =', self.xline['e'][0:10])
	print('N xline soundings n =', len(self.xline['n']), 'with first ten =', self.xline['n'][0:10])
	print('N xline soundings z =', len(self.xline['z']), 'with first ten =', self.xline['z'][0:10])
	print('N xline soundings z_final =', len(self.xline['z_final']), 'with first ten =', self.xline['z_final'][0:10])

	# interpolate the reference grid (linearly) onto the sounding positions
	# note: griddata will interpolate only within the convex hull of the input grid coordinates
	# xline sounding positions outside the convex hull (i.e., off the grid) will return NaN
	self.xline['z_ref_interp'] = griddata((self.ref_surf['e'], self.ref_surf['n']),
										  self.ref_surf['z'],
										  (self.xline['e'], self.xline['n']),
										  method='linear')

	print('z_ref_interp looks like', self.xline['z_ref_interp'][0:30])
	print('xline z_final after flip looks like', self.xline['z_final'][0:30])

	self.xline['num_soundings_on_ref'] = np.sum(~np.isnan(self.xline['z_ref_interp']))  # count non-Nan interp values
	update_log(self, 'Found ' + str(self.xline['num_soundings_on_ref']) + ' crossline soundings on ref grid')

	# calculate dz for xline soundings with non-NaN interpolated reference grid depths
	# note that xline['z'] is positive down as returned from parser; flip sign for differencing from ref surf
	update_log(self, 'Calculating crossline differences from ref grid')
	# self.xline['dz_ref'] = np.subtract(self.xline['z'], self.xline['z_ref_interp'])
	self.xline['dz_ref'] = np.subtract(self.xline['z_final'], self.xline['z_ref_interp'])

	print('xline dz_ref looks like', self.xline['dz_ref'][0:100])

	# store dz as percentage of water depth, with positive dz_ref_wd meaning shallower crossline soundings
	# to retain intuitive plotting appearance, with shallower soundings above deeper soundings
	# e.g., if xline z = -98 and z_ref_interp = -100, then dz_ref = +2; dz_ref_wd should be positive; division of
	# positive bias (up) by reference depth (always negative) yields negative, so must be flipped in sign for plot
	dz_ref_wd = np.array(-1 * 100 * np.divide(np.asarray(self.xline['dz_ref']), np.asarray(self.xline['z_ref_interp'])))
	self.xline['dz_ref_wd'] = dz_ref_wd.tolist()

	print('xline dz_ref_wd looks like', self.xline['dz_ref_wd'][0:100])

	self.ref_surf['z_mean'] = np.nanmean(self.xline['z_ref_interp'])  # mean of ref grid interp values used


def bin_beamwise(self):
	# bin by angle, calc mean and std of sounding differences in that angular bin
	update_log(self, 'Binning soundings by angle')
	self.beam_bin_size = 1  # beam angle bin size (deg)
	self.beam_bin_lim = 75  # max angle (deg)

	self.beam_bin_dz_mean = []  # declare dz mean, std, and sample count
	self.beam_bin_dz_std = []
	self.beam_bin_dz_N = []
	self.beam_bin_dz_wd_mean = []
	self.beam_bin_dz_wd_std = []
	self.beam_range = range(-1 * self.beam_bin_lim, self.beam_bin_lim, self.beam_bin_size)

	# if crossline data AND reference surface are available, convert soundings with meaningful reference surface
	# nodes to array for binning; otherwise, continue to refresh plot with empty results
	if 'z_final' in self.xline and 'z' in self.ref_surf:
		# calculate simplified beam angle from acrosstrack distance and depth
		# depth is used here as negative down re WL, consistent w/ %WD results
		# Kongsberg angle convention is right-hand-rule about +X axis (fwd), so port angles are + and stbd are -
		# however, for plotting purposes with conventional X axes, use neg beam angles to port and pos to stbd, per
		# plotting conventions used elsewhere (e.g., Qimera)
		z_final_pos_down = (-1*np.asarray(self.xline['z_final'])).tolist()
		self.xline['beam_angle'] = np.rad2deg(np.arctan2(self.xline['y'], z_final_pos_down)).tolist()

		# print('size of beam_angle is now', len(self.xline['beam_angle']))
		# print('first 30 beam angles are', self.xline['beam_angle'][0:30])
		# self.xline['beam_angle'] = (-1*np.rad2deg(np.arctan2(self.xline['y'], self.xline['z_re_wl']))).tolist()

		print('found beam_angle in self.xline and z in self.ref_surf')
		beam_array = np.asarray(self.xline['beam_angle'])
		dz_array = np.asarray(self.xline['dz_ref'])
		dz_wd_array = np.asarray(self.xline['dz_ref_wd'])

		for b in self.beam_range:  # loop through all beam bins, calc mean and std for dz results within each bin
			idx = (beam_array >= b) & (beam_array < b + self.beam_bin_size)  # find indices of angles in this bin
			print('Found', str(np.sum(idx)), 'soundings between', str(b), 'and', str(b + self.beam_bin_size), 'deg')
			self.beam_bin_dz_N.append(np.sum(idx))

			if np.sum(idx) > 0:  # calc only if at least one sounding on ref surf within this bin
				self.beam_bin_dz_mean.append(np.nanmean(dz_array[idx]))
				self.beam_bin_dz_std.append(np.nanstd(dz_array[idx]))
				self.beam_bin_dz_wd_mean.append(np.nanmean(dz_wd_array[idx]))  # simple mean of WD percentages
				self.beam_bin_dz_wd_std.append(np.nanstd(dz_wd_array[idx]))
			else:  # store NaN if no dz results are available for this bin
				self.beam_bin_dz_mean.append(np.nan)
				self.beam_bin_dz_std.append(np.nan)
				self.beam_bin_dz_wd_mean.append(np.nan)  # this is the simple mean of WD percentages
				self.beam_bin_dz_wd_std.append(np.nan)

	else:
		print('Error in bin_beamwise')


def plot_accuracy(self):  # plot the accuracy results
	# set point size; slider is on [1-11] for small # of discrete steps
	pt_size = float(self.pt_size_cbox.currentText()) / 10
	pt_alpha = np.divide(float(self.pt_alpha_cbox.currentText()), 100)

	beam_bin_centers = np.asarray([b + self.beam_bin_size / 2 for b in self.beam_range])  # bin centers for plot
	beam_bin_dz_wd_std = np.asarray(self.beam_bin_dz_wd_std)

	# plot standard deviation as %WD versus beam angle
	self.ax1.plot(beam_bin_centers, beam_bin_dz_wd_std, '-', linewidth=self.lwidth, color='b')  # bin mean + st. dev.
	self.ax1.grid(True)

	# plot the raw differences, mean, and +/- 1 sigma as %wd versus beam angle
	self.ax2.scatter(self.xline['beam_angle'], self.xline['dz_ref_wd'],
					 marker='o', color='0.75', s=pt_size, alpha=pt_alpha)
	# raw differences from reference grid, small gray points
	self.ax2.plot(beam_bin_centers, self.beam_bin_dz_wd_mean, '-',
				  linewidth=self.lwidth, color='r')  # beamwise bin mean diff
	self.ax2.plot(beam_bin_centers, np.add(self.beam_bin_dz_wd_mean, self.beam_bin_dz_wd_std), '-',
				  linewidth=self.lwidth, color='b')  # beamwise bin mean + st. dev.
	self.ax2.plot(beam_bin_centers, np.subtract(self.beam_bin_dz_wd_mean, self.beam_bin_dz_wd_std), '-',
				  linewidth=self.lwidth, color='b')  # beamwise bin mean - st. dev.
	self.ax2.grid(True)


def refresh_plot(self, sender=None):
	# update swath plot with new data and options
	clear_plot(self)
	update_plot_limits(self)

	try:
		plot_accuracy(self)  # plot new data if available
	except:
		update_log(self, 'Error plotting data.  Please load files and calculate accuracy.')
		pass

	add_grid_lines(self)  # add grid lines
	update_axes(self)  # update axes to fit all loaded data
	self.swath_canvas.draw()


def update_system_info(self):
	# update model, serial number, ship, cruise based on availability in parsed data and/or custom fields
	if self.custom_info_gb.isChecked():  # use custom info if checked
		self.ship_name = self.ship_tb.text()
		self.cruise_name = self.cruise_tb.text()
		self.model_name = self.model_cbox.currentText()
	else:  # get info from detections if available
		try:  # try to grab ship name from filenames (conventional file naming)
			self.ship_name = self.det['fname'][0]  # try getting ship name from first detection filename
			#                self.ship_name = self.det['filenames'][0] # try getting ship name from detection dict filenames
			self.ship_name = self.ship_name[
							 self.ship_name.rfind('_') + 1:-4]  # assumes filename ends in _SHIPNAME.all
		except:
			self.ship_name = 'SHIP NAME N/A'  # if ship name not available in filename

		try:  # try to grab cruise name from Survey ID field in
			self.cruise_name = self.data[0]['IP_start'][0]['SID'].upper()  # update cruise ID with Survey ID
		except:
			self.cruise_name = 'CRUISE N/A'

		try:
			self.model_name = 'EM ' + str(self.data[0]['IP_start'][0]['MODEL'])
		except:
			self.model_name = 'MODEL N/A'


def update_axes(self):
	# update top subplot axes (std. dev. as %WD)
	update_system_info(self)
	update_plot_limits(self)
	print('survived update_plot_limits')

	# set x axis limits and ticks for both plots
	plt.setp((self.ax1, self.ax2),
			 xticks=np.arange(-1 * self.x_max, self.x_max + self.x_spacing, self.x_spacing),
			 xlim=(-1 * self.x_max, self.x_max))

	# set y axis limits for both plots
	self.ax1.set_ylim(0, self.y_max_std)  # set y axis for std (0 to max, top plot)
	self.ax2.set_ylim(-1 * self.y_max_bias, self.y_max_bias)  # set y axis for total bias+std (bottom plot)

	print('updating the title and axes in update_axes')
	title_str = 'Swath Accuracy vs. Beam Angle\n' + ' - '.join([self.model_name, self.ship_name, self.cruise_name])

	# get set of modes in these crosslines
	if self.xline:  # get set of modes in these crosslines and add to title string
		try:
			modes = [' / '.join([self.xline['ping_mode'][i],
								 self.xline['swath_mode'][i],
								 self.xline['pulse_form'][i]]) for i in range(len(self.xline['ping_mode']))]
			modes_str = ' + '.join(list(set(modes)))

		except:
			modes_str = 'Modes N/A'

		title_str += ' - ' + modes_str

	self.ax1.set(xlabel='Beam Angle (deg, pos. stbd.)', ylabel='Depth Bias Std. Dev (% Water Depth)', title=title_str)
	self.ax2.set(xlabel='Beam Angle (deg, pos. stbd.)', ylabel='Depth Bias (% Water Depth)')
	self.swath_canvas.draw()  # try update the axes labels and title before failing
	print('trying plt.show()')
	add_processing_text(self)


	try:
		plt.show()  # need show() after update; failed until matplotlib.use('qt5agg') added at start

	except:
		print('in update_axes, failed plt.show()')
	# plt.sca(self.ax1)
	# plt.ylabel('Depth Bias Mean (% Water Depth)', fontsize=self.fsize_label)
	# plt.show() # need show() after axis update!
	# self.swath_canvas.draw()
	print('survived update_axes')
	print('*******')


def update_plot_limits(self):
	# update plot limits if custom limits are selected
	if self.plot_lim_gb.isChecked():  # use custom plot limits if checked, store custom values in text boxes
		# self.max_gb.setEnabled(True)
		self.x_max_custom = float(self.max_beam_angle_tb.text())
		self.x_spacing_custom = float(self.angle_spacing_tb.text())
		self.y_max_std_custom = float(self.max_std_tb.text())
		self.y_max_bias_custom = float(self.max_bias_tb.text())

		# assign to current plot limits
		self.x_max = self.x_max_custom
		self.x_spacing = self.x_spacing_custom
		self.y_max_std = self.y_max_std_custom
		self.y_max_bias = self.y_max_bias_custom

	else:  # revert to default limits from the data if unchecked, but keep the custom numbers in text boxes
		# self.max_gb.setEnabled(False)
		self.x_max = self.x_max_default
		self.x_spacing = self.x_spacing_default
		self.y_max_std = self.y_max_std_default
		self.y_max_bias = self.y_max_bias_default

		# set text boxes to latest custom values for easier toggling between custom/default limits
		self.max_beam_angle_tb.setText(str(float(self.x_max_custom)))
		self.angle_spacing_tb.setText(str(float(self.x_spacing_custom)))
		self.max_bias_tb.setText(str(float(self.y_max_bias_custom)))
		self.max_std_tb.setText(str(float(self.y_max_std_custom)))


def add_grid_lines(self):
	if self.grid_lines_toggle_chk.isChecked():  # turn on grid lines
		# for ax in [ax1, ax2]:
		# 	self.ax.grid()
		# 	self.ax.minorticks_on()
		# 	self.ax.grid()
		# 	self.ax.grid(which='minor', linestyle='-', linewidth='0.5', color='black')
		# 	self.ax.grid(which='major', linestyle='-', linewidth='1.0', color='black')

		self.ax1.grid()
		self.ax1.minorticks_on()
		self.ax1.grid(which='minor', linestyle='-', linewidth='0.5', color='black')
		self.ax1.grid(which='major', linestyle='-', linewidth='1.0', color='black')
		self.ax2.grid()
		self.ax2.minorticks_on()
		self.ax2.grid(which='minor', linestyle='-', linewidth='0.5', color='black')
		self.ax2.grid(which='major', linestyle='-', linewidth='1.0', color='black')
		# self.ax2.grid()
		# self.ax2.minorticks_on()
		# self.ax2.grid(which='both', linestyle='-', linewidth='0.5', color='black')

	else:  # turn off the grid lines
		self.ax1.grid(False)
		self.ax1.minorticks_off()
		self.ax2.grid(False)
		self.ax2.minorticks_off()

	self.swath_canvas.draw()  # redraw swath canvas with grid lines


def add_processing_text(self):
	# add text for depth ref and filters applied
	ref_str = 'Vertical reference: ' + self.ref_cbox.currentText()
	ref_surf_str = 'Reference surface: ' + (self.ref_surf['fname'].split('/')[-1] if self.ref_surf else 'N/A')
	utm_zone_str = 'UTM Zone: ' + self.ref_proj_cbox.currentText()
	xline_files_str = 'Num. crosslines: ' + (str(len(list(set(self.xline['fname'])))) if self.xline else '0') + ' files'
	sounding_parsed_str = 'Num. soundings: ' +\
						  (str(len(self.xline['z'])) +
						   ' (' + str(self.xline['num_soundings_on_ref']) + ' on ref. surf.)' if self.xline else '0')
	depth_fil_xline = ['None', self.min_depth_xline_tb.text() + ' to ' + self.max_depth_xline_tb.text() + ' m']
	depth_fil_ref = ['None', self.min_depth_ref_tb.text() + ' to ' + self.max_depth_ref_tb.text() + ' m']
	angle_fil = ['None', self.min_angle_tb.text() + ' to ' + self.max_angle_tb.text() + '\u00b0']
	bs_fil = ['None', ('+' if float(self.min_bs_tb.text()) > 0 else '') + self.min_bs_tb.text() + ' to ' +
			  ('+' if float(self.max_bs_tb.text()) > 0 else '') + self.max_bs_tb.text() + ' dB']
	# rtp_angle_fil = ['None', ('+' if float(self.rtp_angle_buffer_tb.text()) > 0 else '') + \
	# 				 self.rtp_angle_buffer_tb.text() + '\u00b0']  # user limit +/- buffer
	# rtp_cov_fil = ['None', ('-' if float(self.rtp_cov_buffer_tb.text()) > 0 else '') + \
	# 			   self.rtp_cov_buffer_tb.text() + ' m']  # user limit - buffer
	fil_dict = {'Angle filter: ': angle_fil[self.angle_gb.isChecked()],
				'Depth filter (reference): ': depth_fil_xline[self.depth_gb.isChecked()],
				'Depth filter (crossline): ': depth_fil_ref[self.depth_gb.isChecked()],
				'Backscatter filter: ': bs_fil[self.bs_gb.isChecked()]}
				# 'Runtime angle buffer: ': rtp_angle_fil[self.rtp_angle_gb.isChecked()],
				# 'Runtime coverage buffer: ': rtp_cov_fil[self.rtp_cov_gb.isChecked()]}

	for fil in fil_dict.keys():
		ref_str += '\n' + fil + fil_dict[fil]

	# ref_str += '\nMax. point count: ' + str(int(self.n_points_max))
	# ref_str += '\nDecimation factor: ' + "%.1f" % self.dec_fac

	if self.show_ref_fil_chk.isChecked():
		self.ax1.text(0.02, 0.98, ref_str,
						   # 'Ref: ' + self.ref_cbox.currentText(),
						   ha='left', va='top', fontsize=8, transform=self.ax1.transAxes,
						   bbox=dict(facecolor='white', edgecolor=None, linewidth=0, alpha=1))


def save_plot(self):
	# option 1: try to save a .PNG of the swath plot
	plot_path = QtWidgets.QFileDialog.getSaveFileName(self, 'Save plot as...', os.getenv('HOME'),
													  ".PNG file (*.PNG);; .JPG file (*.JPG);; .TIF file (*.TIF)")
	fname_out = plot_path[0]

	self.swath_figure.savefig(fname_out,
							  dpi=600, facecolor='w', edgecolor='k',
							  orientation='portrait', papertype=None, format=None,
							  transparent=False, bbox_inches=None, pad_inches=0.1,
							  frameon=None, metadata=None)

	update_log(self, 'Saved figure ' + fname_out.rsplit('/')[-1])


def clear_plot(self):
	#        print('clear_plot')
	self.ax1.clear()
	self.ax2.clear()
	self.swath_canvas.draw()
# self.x_max = 1
# self.y_max = 1

# def add_IHO_lines(self):
#    # add lines indicating IHO orders
#    if self.wd_lines_toggle_chk.isChecked(): # plot wd lines if checked
# 	   try:
# 		   # loop through multiples of wd (-port,+stbd) and plot grid lines with text
# 		   for n in range(1,self.N_max_wd+1):   # add 1 for indexing, do not include 0X wd
# 			   for ps in [-1,1]:           # port/stbd multiplier
# 				   self.swath_ax.plot([0, ps*n*self.swath_ax_margin*self.y_max/2],\
# 									  [0,self.swath_ax_margin*self.y_max], 'k', linewidth = 1)
# 				   x_mag = 0.9*n*self.y_max/2 # set magnitude of text locations to 90% of line end
# 				   y_mag = 0.9*self.y_max
#
# 				   # keep text locations on the plot
# 				   if x_mag > 0.9*self.x_max:
# 					   x_mag = 0.9*self.x_max
# 					   y_mag = 2*x_mag/n # scale y location with limited x location
#
# 				   self.swath_ax.text(x_mag*ps, y_mag, str(n) + 'X',
# 						   verticalalignment = 'center', horizontalalignment = 'center',
# 						   bbox=dict(facecolor='white', edgecolor = 'none', alpha=1, pad = 0.0))
# 		   self.swath_canvas.draw()
#
# 	   except:
# 		   error_msg = QtWidgets.QMessageBox()
# 		   error_msg.setText('Failure plotting the WD lines...')



