"""Functions for swath accuracy plotting in NOAA / MAC echosounder assessment tools"""
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

from multibeam_tools.libs.file_fun import *
from multibeam_tools.libs.swath_fun import *
from multibeam_tools.libs.readEM import convertXYZ, sort_active_pos_system

import matplotlib.pyplot as plt
# import matplotlib.gridspec as gridspec
from matplotlib import colors
from matplotlib import colorbar
# from matplotlib import patches
from mpl_toolkits.axes_grid1.inset_locator import inset_axes

from scipy.interpolate import griddata
from time import process_time
import pyproj
import re
from scipy.spatial import cKDTree as KDTree
from scipy.ndimage import uniform_filter
from scipy.interpolate import interp1d
from datetime import timedelta


def setup(self):
	# initialize other necessities
	self.print_updates = True
	# self.print_updates = False
	self.xline = {}
	self.ref = {}
	self.xline_track = {}
	self.tide = {}
	self.ref_utm_str = 'N/A'
	# self.det = {}  # detection dict (new data)
	# self.det_archive = {}  # detection dict (archive data)
	# self.spec = {}  # dict of theoretical coverage specs
	# self.filenames = ['']  # initial file list
	# self.input_dir = ''  # initial input dir
	self.output_dir = os.getcwd()  # save output in cwd unless otherwise selected
	# self.clim_last_user = {'depth': [0, 1000], 'backscatter': [-50, -20]}
	# self.last_cmode = 'depth'
	# self.refresh_ref_plot = False
	# self.refresh_acc_plot = False
	self.clim_z = [0, 1]
	self.clim_c = [0, 1]
	self.clim_s = [0, 1]
	self.clim_u = [0, 1]

	self.cbar_ax1 = None  # initial colorbar for ref surf depth subplot
	self.cbar_ax2 = None  # initial colorbar for ref surf slope subplot
	self.cbar_ax3 = None  # initial colorbar for ref surf density subplot
	self.cbar_ax4 = None  # initial colorbar for ref surf uncertainty subplot
	self.cbar_ax5 = None  # initial colorbar for ref surf filtered depth subplot
	self.cbar_ax6 = None  # initial colorbar for ref surf final large plot
	self.tide_cbar_ax = None  # initial colorbar for tide plot
	self.legendbase = None  # initial legend
	self.cbar_font_size = 8  # colorbar/legend label size
	self.cbar_title_font_size = 8  # colorbar/legend title size
	self.cbar_loc = 1  # set upper right as default colorbar/legend location
	self.n_points_max_default = 50000  # default maximum number of points to plot in order to keep reasonable speed
	self.n_points_max = 50000
	self.n_points_plotted = 0
	# # self.n_points_plotted_arc = 0
	self.dec_fac_default = 1  # default decimation factor for point count
	self.dec_fac = 1
	# self.rtp_angle_buffer_default = 0  # default runtime angle buffer
	# self.rtp_angle_buffer = 0  # +/- deg from runtime parameter swath angle limit to filter RX angles
	# self.x_max = 0.0
	# self.z_max = 0.0
	self.model_list = ['EM 2040', 'EM 302', 'EM 304', 'EM 710', 'EM 712', 'EM 122', 'EM 124']
	# self.cmode_list = ['Depth', 'Backscatter', 'Ping Mode', 'Pulse Form', 'Swath Mode', 'Solid Color']
	# self.top_data_list = []
	# self.clim_list = ['All data', 'Filtered data', 'Fixed limits']
	self.data_ref_list = ['Waterline']  # , 'Origin', 'TX Array', 'Raw Data']
	self.tide_unit_dict = {'Meter': float(1), 'Foot': float(0.3048), 'Smoot': float(1/1.702)}  # conversion fac to m
	self.unit_mode = '%WD'  # default plot as % Water Depth; option to toggle alternative meters
	self.tide_applied = False
	# plt.margins(x=0.1, y=0.1)
	self.model_updated = False
	self.ship_name_updated = False
	self.cruise_name_updated = False
	self.sn_updated = False
	self.N_plotted = 0


def init_all_axes(self):
	init_swath_ax(self)
	init_surf_ax(self)
	init_tide_ax(self)
	add_grid_lines(self)
	update_axes(self)


def init_swath_ax(self):  # set initial swath parameters
	self.pt_size = np.square(float(self.pt_size_cbox.currentText()))  # swath plot point size
	self.pt_size_cov = np.square(float(self.pt_size_cov_cbox.currentText()))  # coverage plot point size
	self.pt_alpha = np.divide(float(self.pt_alpha_cbox.currentText()), 100)

	self.ax1 = self.swath_figure.add_subplot(211)
	self.ax2 = self.swath_figure.add_subplot(212)

	self.x_max_default = 75
	self.x_spacing_default = 15
	self.y_max_std_default = 0.5  # max y range of depth st. dev. plot (top subplot)
	self.y_max_bias_default = 1  # max +/- y range of depth bias (raw, mean, +/- 1 sigma, bottom subplot)
	self.axis_margin_default = 5  # % axis margin

	self.x_max_custom = self.x_max_default  # store future custom entries
	self.x_spacing_custom = self.x_spacing_default
	self.y_max_bias_custom = self.y_max_bias_default
	self.y_max_std_custom = self.y_max_std_default
	self.axis_margin_custom = self.axis_margin_default

	self.max_beam_angle_tb.setText(str(self.x_max_default))
	self.angle_spacing_tb.setText(str(self.x_spacing_default))
	self.max_bias_tb.setText(str(self.y_max_bias_default))
	self.max_std_tb.setText(str(self.y_max_std_default))
	self.axis_margin_tb.setText(str(self.axis_margin_default))

	self.cruise_name = ''
	self.swath_ax_margin = 1.1  # scale axes to multiple of max data in each direction
	self.fsize_title = 12
	self.fsize_label = 10
	self.lwidth = 1  # line width
	self.color = QtGui.QColor(0, 0, 0)  # set default solid color to black for new data
	self.archive_color = QtGui.QColor('darkGray')


def init_surf_ax(self):  # set initial ref surf parameters
	self.surf_ax1 = self.surf_figure.add_subplot(221)
	self.surf_ax2 = self.surf_figure.add_subplot(222, sharex=self.surf_ax1, sharey=self.surf_ax1)
	self.surf_ax3 = self.surf_figure.add_subplot(223, sharex=self.surf_ax1, sharey=self.surf_ax1)
	self.surf_ax4 = self.surf_figure.add_subplot(224, sharex=self.surf_ax1, sharey=self.surf_ax1)
	self.surf_ax5 = self.surf_final_figure.add_subplot(111)
	self.surf_ax5.set_aspect(1)

	# setup dict of colorbar parameters; u and z_final are separate colorbars (u added later) plotted on same axis
	self.cbar_dict = {'z': {'cax': self.cbar_ax1, 'ax': self.surf_ax1, 'clim': self.clim_z, 'label': 'Depth (m)'},
					  'c': {'cax': self.cbar_ax2, 'ax': self.surf_ax2, 'clim': self.clim_c, 'label': 'Soundings/Cell'},
					  's': {'cax': self.cbar_ax3, 'ax': self.surf_ax3, 'clim': self.clim_s, 'label': 'Slope (deg)'},
					  'u': {'cax': self.cbar_ax4, 'ax': self.surf_ax4, 'clim': self.clim_u, 'label': 'Uncertainty (m)'},
					  'z_filt': {'cax': self.cbar_ax5, 'ax': self.surf_ax4, 'clim': self.clim_z, 'label': 'Depth (m)'},
					  'z_final': {'cax': self.cbar_ax6, 'ax': self.surf_ax5, 'clim': self.clim_z, 'label': 'Depth (m)'}}


# def init_test_ax(self):  # set initial ref surf parameters
# 	self.surf_ax5 = self.test_figure.add_subplot(111)

	# gs = self.test_figure.add_gridspec(4,4)
	# test with lots of small plots
	# gs = gridspec.GridSpec(nrows=4, ncols=4, figure=self.test_figure)
	# self.test_ax1 = self.test_figure.add_subplot(gs[0, 0])
	# self.test_ax2 = self.test_figure.add_subplot(gs[0, 1])  # sharex=self.test_ax1, sharey=self.test_ax1)
	# self.test_ax3 = self.test_figure.add_subplot(gs[0, 2])  #, sharex=self.test_ax1, sharey=self.test_ax1)
	# self.test_ax4 = self.test_figure.add_subplot(gs[0, 3])  #, sharex=self.test_ax1, sharey=self.test_ax1)
	# self.test_ax5 = self.test_figure.add_subplot(gs[1:, 1:])
	# self.test_ax6 = self.test_figure.add_subplot(gs[1:, 0])  # possible histogram axis for depth, crossline soundings
	# self.test_dict = {'z': {'cax': self.cbar_ax1, 'ax': self.test_ax1, 'clim': self.clim_z, 'label': 'Depth (m)'},
	# 				  'u': {'cax': self.cbar_ax5, 'ax': self.test_ax2, 'clim': self.clim_u, 'label': 'Uncertainty (m)'},
	# 				  'c': {'cax': self.cbar_ax2, 'ax': self.test_ax3, 'clim': self.clim_c, 'label': 'Soundings/Cell'},
	# 				  's': {'cax': self.cbar_ax3, 'ax': self.test_ax4, 'clim': self.clim_s, 'label': 'Slope (deg)'},
	# 				  'z_final': {'cax': self.cbar_ax4, 'ax': self.test_ax5, 'clim': self.clim_z, 'label': 'Depth (m)'}}


def init_tide_ax(self):  # set initial tide plot parameters
	self.tide_ax = self.tide_figure.add_subplot(111)
	self.tide_cbar_dict = {'tide_amp': {'cax': self.tide_cbar_ax, 'ax': self.tide_ax, 'label': 'Amplitude (m)'}}


def update_buttons(self, recalc_acc=False):
	# enable or disable file selection and calc_accuracy buttons depending on loaded files
	print('updating buttons...')
	get_current_file_list(self)
	fnames_ref = [f for f in self.filenames if '.xyz' in f]
	fnames_xline = get_new_file_list(self, ['.all', '.kmall'], [])  # list new .all files not in det dict
	fnames_tide = [f for f in self.filenames if '.tid' in f]

	self.add_ref_surf_btn.setEnabled(len(fnames_ref) == 0)  # enable ref surf selection only if none loaded
	self.add_dens_surf_btn.setEnabled(('z' in self.ref.keys() and 'c' not in self.ref.keys()))  # enable if ref z avail
	self.add_tide_btn.setEnabled(len(fnames_tide) == 0)  # enable tide selection only if none loaded

	# enable calc_accuracy button only if one ref surf and at least one crossline are loaded
	if (len(fnames_ref) == 1 and len(fnames_xline) > 0):
		self.calc_accuracy_btn.setEnabled(True)

		if recalc_acc:
			self.calc_accuracy_btn.setStyleSheet("background-color: yellow")

	else:
		self.calc_accuracy_btn.setEnabled(False)
		self.calc_accuracy_btn.setStyleSheet("background-color: none")


def add_ref_file(self, ftype_filter, input_dir='HOME', include_subdir=False):
	# add single reference surface file with extensions in ftype_filter
	fname = add_files(self, ftype_filter, input_dir, include_subdir, multiselect=False)
	update_file_list(self, fname)
	# try to get UTM zone from filename; zone can be, e.g,, 'UTM-11S', '14N',  w/ or w/o UTM preceding and -, _, or ' '
	# get decimal and hemisphere, strip zero padding and remove spaces for comparison to UTM combobox list
	fname_str = fname[0]
	fname_str = fname_str[fname_str.rfind('/') + 1:].rstrip()

	try:
		utm_idx = -1
		utm_str = re.search(r"[_-]*\s*[0-9]{1,2}[NS]", fname_str).group()
		utm_str = re.search('\d+[NS]', utm_str).group().strip('0').replace(' ', '')
		utm_idx = self.ref_proj_cbox.findText(utm_str)
		print('found utm_str, utm_idx =', utm_str, utm_idx)

	except:
		update_log(self, 'Please select the reference surface UTM zone')
		self.ref_proj_cbox.setCurrentIndex(0)

	if utm_idx > -1:
		update_log(self, 'Found UTM zone from filename: ' + utm_str)
		self.ref_proj_cbox.setCurrentIndex(utm_idx)
		self.ref_utm_str = utm_str
		parse_ref_depth(self)

		if any([f for f in self.filenames if '.xyd' in f]) and 'c' not in self.ref:
			print('processing density file already loaded but not added in self.ref yet (')
			process_dens_file(self)

		make_ref_surf(self)
		refresh_plot(self, refresh_list=['ref'], set_active_tab=1, sender='add_ref_file')

	update_buttons(self, recalc_acc=True)


def update_ref_utm_zone(self):
	# update ref surf UTM zone after user selection, transform crossline data into current zone, and recalc accuracy
	self.ref_utm_str = self.ref_proj_cbox.currentText()  # update with current UTM zone
	self.ref['utm_zone'] = self.ref_proj_cbox.currentText()

	if self.xline:  # crossline data already processed, need to recalc accuracy using updated ref surf
		update_log(self, 'Reference surface UTM zone has been updated; recalculating accuracy with loaded crosslines')
		convert_track_utm(self)  # update track
		calc_accuracy(self, recalc_utm_only=True)  # skip parsing, convert_crossline_utm, recalc stats, refresh plots


	else:
		update_log(self, 'Reference surface has been updated; no crossline data available')
		refresh_plot(self, refresh_list=['ref'], sender='udate_ref_utm_zone (self.xline=FALSE)')


def add_dens_file(self, ftype_filter, input_dir='HOME', include_subdir=False):
	# add single density surface file with extensions in ftype_filter
	fname = add_files(self, ftype_filter, input_dir, include_subdir, multiselect=False)
	update_file_list(self, fname)
	process_dens_file(self)


def process_dens_file(self):
	# process the loaded density file
	# update_buttons(self)
	parse_ref_dens(self)
	make_ref_surf(self)
	update_buttons(self)  # turn off density button if loaded
	refresh_plot(self, refresh_list=['ref'], set_active_tab=1, sender='process_dens_file')


def add_tide_file(self, ftype_filter, input_dir='HOME', include_subdir=False):
	fname = add_files(self, ftype_filter, input_dir, include_subdir, multiselect=False)
	update_file_list(self, fname)
	update_buttons(self, recalc_acc=True)  # turn off tide button if loaded
	process_tide(self)


def process_tide(self, unit_set_by_user=False):
	parse_tide(self, unit_set_by_user=unit_set_by_user)
	# plot_tide(self, set_active_tab=True)
	plot_tide2(self, set_active_tab=True)
	refresh_plot(self, refresh_list=['tide'], set_active_tab=3, sender='add_tide_file')


def add_acc_files(self, ftype_filter, input_dir='HOME', include_subdir=False):
	# add accuracy crossline files with extensions in ftype_filter from input_dir and subdir if desired
	fnames = add_files(self, ftype_filter, input_dir, include_subdir)
	update_file_list(self, fnames)
	update_buttons(self, recalc_acc=True)


def remove_acc_files(self):  # remove selected files only
	# recalc_acc = False
	get_current_file_list(self)
	selected_files = self.file_list.selectedItems()
	# fnames_ref = [f for f in self.filenames if '.xyz' in f]
	# fnames_dens = [f for f in self.filenames if '.xyd' in f]
	# fnames_tide = [f for f in self.filenames if '.tid' in f]
	# fnames_xline = [f for f in self.filenames if f.rsplit('.')[-1] in ['.all', '.kmall']]

	# print('in remove_acc_files, fnames_xline is', fnames_xline)

	# if len(fnames_xline) + len(fnames_ref) == 0:  # all .all and .xyz files have been removed, reset det dicts
	# 	self.xline = {}
	# 	self.ref = {}
	# self.bin_beamwise()  # call bin_beamwise with empty xline results to clear plots
	#            self.xline_archive = {}

	if not selected_files:  # files exist but nothing is selected
		update_log(self, 'No files selected for removal.')
		return

	# elif len(fnames_xline) ==

	else:  # remove only the files that have been selected
		for f in selected_files:
			fname = f.text().split('/')[-1]
			print('working on fname', fname)
			self.file_list.takeItem(self.file_list.row(f))
			update_log(self, 'Removed ' + fname)

			try:  # try to remove detections associated with this file
				if fname.rsplit('.')[-1] in ['all', 'kmall']:
					# get indices of soundings in det dict with matching filenames
					i = [j for j in range(len(self.xline['fname'])) if self.xline['fname'][j] == fname]

					for k in self.xline.keys():  # loop through all keys and remove values at these indices
						print(k)
						self.xline[k] = np.delete(self.xline[k], i).tolist()

					# remove trackline associated with this file
					for k in self.xline_track.keys():
						print('in remove_acc_files, removing xline_track key = ', k)
						# if self.xline_track[k]['fname'] == fname:
						if k == fname:
							print('k == fname, trying to pop')
							# self.xline_track[k].pop()
							self.xline_track.pop(k, None)
							print('success')
						else:
							print('skipping popping this k =', fname)

					# self.xline_track[fname].pop()

				elif '.xyz' in fname:  # remove the single reference surface and reset ref dict

					self.ref = {}
					self.add_ref_surf_btn.setEnabled(True)  # enable button to add replacement reference surface
					self.ref_proj_cbox.setCurrentIndex(0)

				elif '.xyd' in fname:  # remove the single reference density and reset associated ref dict keys
					# self.ref = {}
					# remove density data from ref dict, if it exists
					print('in remove_acc_files, self.ref.keys = ', self.ref.keys())
					for k in ['fname_dens', 'c', 'c_grid']:
						print('in remove_acc_files, popping density key =', k)
						self.ref.pop(k, None)

					self.add_dens_surf_btn.setEnabled(True)  # enable button to add replacement density surface

				elif '.tid' in fname:  # remove the singe tide and reset tide dict
					self.tide = {}
					self.tide_ax.clear()
					self.add_tide_btn.setEnabled(True)
					self.tide_applied = False

			except:  # will fail if detection dict has not been created yet (e.g., if calc_coverage has not been run)
				#                    update_log(self, 'Failed to remove soundings stored from ' + fname)
				pass

		# call bin_beamwise() to update results if any crosslines files are removed (not required to recalc ref surf)
		f_exts = [f.text().split('/')[-1].rsplit('.', 1)[-1] for f in selected_files]
		print('got f_exts =', f_exts)

		# recalculate beamwise results if crossline soundings were removed
		if any([ext in ['all', 'kmall'] for ext in f_exts]) and self.xline:
			print('found all or kmall extension, calling bin_beamwise from remove_files')
			bin_beamwise(self)

		# recalculate accuracy if crossline data exists and the tide files change
		if any([ext in ['tid'] for ext in f_exts]) and self.xline:
			print('found tid extension, calling calc_accuracy from remove_files')
			calc_accuracy(self)

		# recalculate reference surface if depth or density
		if any([ext in ['xyz', 'xyd'] for ext in f_exts]):
			print('at end of remove_acc_files, found xyz or xyd, caling make_ref_surf')
			make_ref_surf(self)

	# reset xline dict if all files have been removed
	get_current_file_list(self)
	print('in remove_acc_files, self.filenames after file removal is', self.filenames)
	fnames_xline = [f for f in self.filenames if f.rsplit('.')[-1] in ['all', 'kmall']]
	print('in remove_acc_files, fnames_xline after file removal is', fnames_xline)
	if len(fnames_xline) == 0:  # all .all and .xyz files have been removed, reset det dicts
		self.xline = {}
		self.xline_track = {}

	update_buttons(self)
	refresh_plot(self, refresh_list=['acc', 'ref', 'tide'], sender='remove_acc_files')  # refresh with updated (reduced or cleared) detection data


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
	self.ref = {}  # clear ref surf data
	self.tide = {}
	bin_beamwise(self)  # call bin_beamwise with empty self.xline to reset all other binned results
	remove_acc_files(self)  # remove files and refresh plot
	update_log(self, 'Cleared all files')
	self.current_file_lbl.setText('Current File [0/0]:')
	self.calc_pb.setValue(0)
	self.add_ref_surf_btn.setEnabled(True)
	self.ref_proj_cbox.setCurrentIndex(0)


def calc_accuracy(self, recalc_utm_only=False, recalc_bins_only=False, recalc_dz_only=False):
	# calculate accuracy of soundings from at least one crossline over exactly one reference surface
	# calc_accuracy is called after all filter updates; skip calc attempt if no crossline files are loaded
	if not get_new_file_list(self, ['.all', '.kmall'], []):
		return
	else:
		update_log(self, 'Starting accuracy calculations')

	force_sys_info_update = not any([recalc_utm_only, recalc_bins_only, recalc_dz_only]) # force sys info update unless skipping

	print('in calc_accuracy with kwargs ', recalc_utm_only, recalc_bins_only, recalc_dz_only)

	if not recalc_bins_only:  # skip if just recalculating bins;
		if not recalc_dz_only:  # skip if just recalculating dz from ref after filtering
			if not recalc_utm_only:  # skip if simply updating UTM zone for existing data; parse crosslines and calc z_final
				if 'c_grid' not in self.ref:
					parse_ref_dens(self)  # parse density data if not available

				num_new_xlines = parse_crosslines(self)  # parse the crossline(s)

				if num_new_xlines > 0 or not self.tide_applied:  # (re)calc z_final if new files or tide has not been applied
					calc_z_final(self)  # adjust sounding depths to desired reference, adjust for tide, and flip sign as necessary

			convert_crossline_utm(self)  # convert crossline X,Y to UTM zone of reference surface

		calc_dz_from_ref_interp(self)  # interpolate ref surf onto sounding positions, take difference

	# after parsing, converting, and calculating dz as necessary, bin results (apply xline filters in binning step)
	bin_beamwise(self)  # bin the results by beam angle
	update_log(self, 'Finished calculating accuracy')
	update_log(self, 'Plotting accuracy results')
	update_system_info(self, self.xline, force_update=force_sys_info_update, fname_str_replace='_trimmed')

	if not recalc_dz_only:  # update mode list if this is the first calc; otherwise, leave mode list unchanged
		update_depth_mode_list(self)

	refresh_plot(self, refresh_list=['acc', 'ref', 'tide'], set_active_tab=0, sender='calc_accuracy')

def update_depth_mode_list(self):  # determine set of available depth modes and update combobox for filtering if desired
	self.depth_mode_list = [mode.split('(')[0].strip() for mode in set([pm for pm in self.xline['ping_mode']])]
	self.depth_mode_cbox.clear()
	self.depth_mode_cbox.addItems(self.depth_mode_list)

def filter_xline(self, print_updates=True):
	# set up indices for optional masking on angle, depth, bs; all idx true until fail optional filter settings
	# all soundings masked for nans (e.g., occasional nans in EX0908 data)
	# print('in filter_xline with fields:', self.xline.keys())

	# set up indices for each filter parameter
	idx_shape = np.shape(np.asarray(self.xline['z']))
	angle_idx = np.ones(idx_shape)  # inx of beam angle
	depth_idx = np.ones(idx_shape)  # idx of depth final (meters) after tide and z reference adjustments
	bs_idx = np.ones(idx_shape)  # idz of reported backscatter (dB)
	dz_ref_idx = np.ones(idx_shape)  # idx of dz from ref (meters)
	dz_ref_wd_idx = np.ones(idx_shape)  # idx of dz from ref (% WD)
	depth_mode_idx = np.ones(idx_shape)  # idx of depth mode matching combo box
	real_idx = np.logical_not(np.logical_or(np.isnan(self.xline['z_final']),
											np.isnan(self.xline['z_final'])))  # idx true for NON-NAN soundings

	if print_updates:
		print('number of xline soundings:', len(self.xline['z_final']))
		print('number of nans found in xline z_final=', np.sum(np.logical_not(real_idx)))

	if self.angle_xline_gb.isChecked():  # get idx satisfying current swath angle filter based on depth/acrosstrack angle
		lims = [float(self.min_angle_xline_tb.text()), float(self.max_angle_xline_tb.text())]
		# swath coverage method uses abs(angle) to accomplish symmetrical angle filtering (e.g., excluding nadir)
		# angle_idx = np.logical_and(np.abs(np.asarray(self.xline['beam_angle'])) >= lims[0],
		# 						   np.abs(np.asarray(self.xline['beam_angle'])) <= lims[1])

		# swath accuracy method uses angle including sign to filter actual beam angles (e.g., port and stbd outer swath)
		angle_idx = np.logical_and(np.asarray(self.xline['beam_angle']) >= lims[0],
								   np.asarray(self.xline['beam_angle']) <= lims[1])

	if self.depth_xline_gb.isChecked():  # get idx satisfying current depth filter
		lims = [-1*float(self.max_depth_xline_tb.text()), -1*float(self.min_depth_xline_tb.text())]
		depth_idx = np.logical_and(np.asarray(self.xline['z_final']) >= lims[0],
								   np.asarray(self.xline['z_final']) <= lims[1])

	if self.dz_gb.isChecked():  # get idx satisfying current depth difference filters
		# print('filtering for depth diff with max dz and max dz wd =', self.max_dz_tb.text(), self.max_dz_wd_tb.text())
		dz_ref_idx = np.abs(self.xline['dz_ref']) <= float(self.max_dz_tb.text())
		dz_ref_wd_idx = np.abs(self.xline['dz_ref_wd']) <= float(self.max_dz_wd_tb.text())

	if self.bs_xline_gb.isChecked():  # get idx satisfying current backscatter filter
		lims = [float(self.min_bs_xline_tb.text()), float(self.max_bs_xline_tb.text())]  # parsed BS is converted to dB
		bs_idx = np.logical_and(np.asarray(self.xline['bs']) >= lims[0],
								np.asarray(self.xline['bs']) <= lims[1])

	if self.depth_mode_gb.isChecked():  # get idx satisfying current depth mode filter
		depth_mode_filter = self.depth_mode_cbox.currentText().strip().lower()
		update_log(self, 'Crosslines will be filtered by depth mode: ' + depth_mode_filter)
		# ping mode may be, e.g., 'Deeper (Manual)', need to compare just mode and not whether Manual
		depth_mode_idx = np.asarray([pm.split('(')[0].strip().lower() == depth_mode_filter for
									 pm in self.xline['ping_mode']])

	# # apply filter masks to x, z, angle, and bs fields
	# self.xline['filter_idx'] = np.logical_and.reduce((angle_idx, depth_idx, bs_idx, dz_ref_idx, dz_ref_wd_idx))
	self.xline['filter_idx'] = np.logical_and.reduce((angle_idx, depth_idx, bs_idx, dz_ref_idx, dz_ref_wd_idx,
													  depth_mode_idx))

	# print('number of soundings passing filter: ', np.sum(self.xline['filter_idx']))

def parse_tide(self, unit_set_by_user=False):  # force_refresh=False):
	# add tide file if available -
	fnames_tide = get_new_file_list(self, ['.tid', '.txt'], [])  # list .tid and .txt files
	# print('fnames_tide is', fnames_tide)

	if len(fnames_tide) != 1:  # warn user to add exactly one tide file
		update_log(self, 'Add one tide text (.tid or .txt) file corresponding to the accuracy crossline location and '
						 'covering the entire crossline data duration.\n\n'
						 'Format should be ''YYYY/MM/DD[/]HH:MM[:SS] tide_amplitude'' with time in the same zone as '
						 'the crossline data (e.g., UTC/GMT)\n\n'
						 'Amplitude is positive up in meters or feet; the vertical datum for the tide file must '
						 'match that of the reference surface for meaningful comparison (e.g., same tide applied during'
						 'processing of the refernce surface should be applied here for the crosslines).')
		pass

	else:
		tic = process_time()
		update_log(self, 'Processing tide file')
		fname_tide = fnames_tide[0]

		self.tide = {}
		self.tide['fname'] = fname_tide.rsplit('/', 1)[1]
		# print('storing tide fname =', self.tide['fname'])
		self.tide['time_obj'], self.tide['amplitude'] = [], []

		# try to get units from filename (assumed meters, look for feet, etc.)
		tide_unit = ''
		try:  # look for any units specified in the filename
			if unit_set_by_user:  # use unit selected by user (override
				update_log(self, 'Tide file amplitude unit set by user to ' + self.tide_unit_cbox.currentText())
				tide_unit = self.tide_unit_cbox.currentText()

			else:  # look for unit in filename, update cbox for user to review/confirm units
				if any([self.tide['fname'].lower().find(u) > -1 for u in ['ft', 'feet', 'foot']]):
					tide_unit = 'Foot'

				elif any([self.tide['fname'].lower().find(u) > -1 for u in ['meter', '_m.']]):
					tide_unit = 'Meter'  # found meters, try to avoid simple m character

				elif self.tide['fname'].lower().find('smoot') > -1 and \
						self.tide['fname'].lower().find('smooth') == -1:
					tide_unit = 'Smoot'  # last case, found smoot but not smooth

				# try to update the combobox if a unit was found in the file and not manually set by user
				if tide_unit:
					update_log(self, 'Found tide unit ' + tide_unit.upper() + ' in tide filename; please verify or update in tide '
																			  'unit selection menu and update units as necessary')
					if tide_unit is not 'Meter':
						update_log(self, 'All data will be converted to meters for analysis')

				else:
					tide_unit = 'Meter'
					update_log(self, 'Tide unit not detected in filename; assumed tide amplitude in METERS')

				print('Looking for matching cbox index...')
				tide_unit_idx = self.tide_unit_cbox.findText(tide_unit)
				print('got index = ', tide_unit_idx)
				if tide_unit_idx >= 0:
					print('trying to set tide unit cbox to detected unit')
					self.tide_unit_cbox.setCurrentIndex(tide_unit_idx)
					print('great success')

		except:
			print('Tide unit search failed in filename: ', self.tide['fname'])

		with open(fname_tide, 'r') as fid_tide:  # read each line of the tide file, strip newline
			tide_list = [line.strip().rstrip() for line in fid_tide]

		fid_tide.close()
		temp_time = []
		temp_tide = []

		time_fmt = ''  # start without assuming tide time format
		print('starting tide time format loop')

		for l in tide_list:
			print('working on l =', l)
			try:  # try parsing and converting each line before adding to temp time and tide lists
				# print('in first try statement')
				# print('l.rsplit = ', l.replace('\t', ' ').rsplit(' ', 1))

				# time_str, amp = l.replace('\t', ' ').rsplit(' ', 1)  # separate tide amp at end from uncertain time str
				# time_str, amp = l.replace('\t', ' ').rsplit('.', 1)

				# TPXO format
				# 37.3730 -123.1850	06.26.2021	01:00:00 -0.056 1299.549

				# some NOAA exports have spaces mixed into the amplitude decimals, which need to be removed to get the
				# proper amplitude

				# print('len(l.split( ) = ', len(l.split(' ')), 'with fields', l.split(' '))
				print('len(l.split( ) = ', len(l.split()), 'with fields', l.split())

				n_fields = len(l.split())
				tpxo_format = False

				if n_fields == 6:  # probably TPXO download format if lots of fields (more than date time amp)
					# TPXO format
					# 37.3730 -123.1850	06.26.2021	01:00:00 -0.056 1299.549
					print('checking TPXO download format')
					try:
						lat, lon, date, time, amp, depth = l.split()
						time_str = ' '.join([date, time]).strip()
						amp = amp.strip()
						print('got results: ', lat, lon, date, time, amp, depth)
						tpxo_format = True
					except:
						print('failed TPXO format')

				elif n_fields == 3:  # probably standard .tid format, but may have many different date time separators (/, :, ., etc.)
					part1, part2 = l.rsplit('.', 1)  # split line at the last decimal
					# print('got part1, part2 = ', part1, part2)
					time_str, amp_int = part1.replace('\t', ' ').rsplit(' ', 1)  # split time str from amplitude whole num
					print('time str after first split is', time_str)
					# time_str2 = ' '.join(time_str.rsplit(' ')[-2:])  # exclude lat lon prior to time in TPXO download format
					# print('time str is now ', time_str2)
					# print('got time_str, amp_int =', time_str, amp_int)
					amp_dec = part2.replace(' ', '')  # remove any spaces in decimal part
					# print('got amp_dec =', amp_dec)
					amp = '.'.join([amp_int, amp_dec])  # rejoin whole number and decimal part of amplitude
					# print('got time_str, amp_int, and amp_dec = ', time_str, amp)

				else:
					update_log(self, 'Tide format not recognized. Please load .tid format or TPXO download tide file.')

				# time_str_reduced = re.sub('[^0-9^.]', '', time_str).strip()  # remove alpha (day name) and :, leave . and ms
				time_str_reduced = re.sub('[^0-9^.^:]', '', time_str).strip()  # remove alpha (day name) and :, leave . and ms

				print('got time_str --> reduced =', time_str, ' --> ', time_str_reduced)

				# if time_fmt:  # if successful time format is known, try that
				try:  # try parsing time string w/ last successful format (first line will fail until format is found)
					dt = datetime.datetime.strptime(time_str_reduced, time_fmt)
					# print('got datetime =', dt)

				except:  # figure out time format and use this format for future lines until it fails
					# list of formats in increasing complexity (may parse incorrectly if starting with most complex)
					# fmt_list = ['%Y%m%d%H%M', '%Y%m%d%H%M%S', '%Y%m%d%H%M%S.%f']  # reduced time_str should match one...
					# fmt_list = ['%Y%m%d%H%M', '%Y%m%d%H%M%S', '%Y%m%d%H%M%S.%f', '%m.%d.%Y%H%M%S']  # reduced time_str should match one...
					fmt_list = ['%Y%m%d%H:%M', '%Y%m%d%H:%M:%S', '%Y%m%d%H:%M:%S.%f', '%m.%d.%Y%H:%M:%S']  # reduced time_str should match one...

					print('time format = ', time_fmt, ' did not work; trying other formats')
					for fmt in fmt_list:
						print('trying tide format', fmt)
						try:
							print('trying to parse time with ', fmt)

							# TPXO download format includes 24:00 that should be converted to 00:00 (and add a day)
							# if fmt == '%m.%d.%Y%H:%M:%S' and time_str_reduced.find('24:') > -1:
							if tpxo_format and time_str_reduced.find('24:') > -1:
								print('found a 24: in time_str_reduced =', time_str_reduced)
								dt = datetime.datetime.strptime(time_str_reduced.replace('24:', '00:'), fmt)
								dt = dt + timedelta(days=1)

							else:
								dt = datetime.datetime.strptime(time_str_reduced, fmt)

							print('successfully parsed with format: ', fmt)
							time_fmt = fmt  # store format if successfully parsed this time string
							print('set time_fmt =', time_fmt)

							update_log(self, 'Found tide time format: ' + time_fmt)
							print('breaking!')

							break

						except:
							print('Tide time format ', fmt, ' did not work for time_str_reduced =', time_str,
								  '--> trying next format in list')

				if dt:  # try to parse the amplitude only if time was successfully parse
					try:
						amp = float(amp)
						temp_time.append(dt)
						temp_tide.append(amp)

					except:
						print('failed to convert amp to float: ', amp)

				else:
					print('Time was not parsed; skipping amplitude')

			except:
				print('failed to parse tide file line =', l, '(possible header)')


		tide_amp_fac = self.tide_unit_dict[self.tide_unit_cbox.currentText()]  # apply selected/updated amplitude unit
		print('for tide units = ', self.tide_unit_cbox.currentText(), ' got amp fac =', tide_amp_fac)

		print('temp_tide =', temp_tide)

		tide_m = np.multiply(temp_tide, tide_amp_fac)

		self.tide['time_obj'] = deepcopy(temp_time)
		self.tide['amplitude'] = deepcopy(tide_m)
		self.tide_applied = False
		# print('final self.tide time and amp are ', self.tide['time_obj'], self.tide['amplitude'])

		# if force_refresh:
		# 	plot_tide(self, set_active_tab=True)
		# 	refresh_plot(self, refresh_list=['tide'], set_active_tab=3, sender='add_tide_file')


def parse_ref_depth(self):
	# parse the loaded reference surface .xyz file; assumes all units are meters in UTM projection
	# .xyz file is assumed comma or space delimited with minimum fields: east, north, depth (+Z up)
	# optional fourth field for uncertainty (e.g., Qimera CUBE surface export), set to 0 if not included

	self.ref = {}
	fnames_xyz = get_new_file_list(self, ['.xyz'], [])  # list .xyz files
	print('fnames_xyz is', fnames_xyz)

	if len(fnames_xyz) != 1:  # warn user to add exactly one ref grid
		update_log(self, 'Please add one reference grid .xyz file in a UTM projection')
		pass

	else:
		fname_ref = fnames_xyz[0]
		self.ref['fname'] = fname_ref.rsplit('/', 1)[1]
		print(fname_ref)
		fid_ref = open(fname_ref, 'r')
		e_ref, n_ref, z_ref, u_ref = [], [], [], []

		for line in fid_ref:
			# strip and split space- or comma-delimited line; append '0' to list in case uncertainty field is not avail
			temp = line.replace(',', ' ').strip().rstrip().split() + ['0']
			e_ref.append(temp[0])  # easting
			n_ref.append(temp[1])  # northing
			z_ref.append(temp[2])  # up
			u_ref.append(temp[3])  # uncertainty (fourth value in line if included; 0 if not)

	print('*** finished parsing .xyz, got first ten uncertainty values:', u_ref[0:10])

	# update log about uncertainty
	update_log(self, 'Uncertainty ' + ('not ' if len(set(u_ref)) == 1 and u_ref[0] == '0' else '') + 'parsed from .xyz')

	# convert to arrays with Z positive up; vertical datum for ref grid and crosslines is assumed same for now
	self.ref['e'] = np.array(e_ref, dtype=np.float32)
	self.ref['n'] = np.array(n_ref, dtype=np.float32)
	self.ref['z'] = -1 * np.abs(np.array(z_ref, dtype=np.float32))  # ensure grid is +Z UP (neg. depths)
	self.ref['utm_zone'] = self.ref_proj_cbox.currentText()
	self.ref['u'] = np.array(u_ref, dtype=np.float32)


	update_log(self, 'Imported ref grid: ' + fname_ref.split('/')[-1] + ' with ' +
			   str(len(self.ref['z'])) + ' nodes')
	update_log(self, 'Ref grid is assigned UTM zone ' + self.ref['utm_zone'])

	ref_de, ref_dn = check_cell_size(self, self.ref['e'], self.ref['n'])

	if ref_de == ref_dn:
		self.ref_cell_size = ref_de
		update_log(self, 'Imported ref grid has uniform cell size: ' + str(self.ref_cell_size) + ' m')

	else:
		self.ref_cell_size = np.max([ref_de, ref_dn])
		update_log(self, 'WARNING: Unequal ref grid cell sizes (E: ' + str(ref_de) + ' m , N: ' + str(ref_dn) + ' m)',
				   font_color="red")

	print('leaving parse_ref_depth with self.ref.keys =', self.ref.keys())


def check_cell_size(self, easting, northing):
	de = np.mean(np.diff(np.sort(np.unique(easting))))
	dn = np.mean(np.diff(np.sort(np.unique(northing))))

	return de, dn


def parse_ref_dens(self):
	# add density surface if available - this is useful for Qimera .xyz files that do not include density
	fnames_xyd = get_new_file_list(self, ['.xyd'], [])  # list .xyz files
	print('fnames_xyd is', fnames_xyd)

	if len(fnames_xyd) != 1:  # warn user to add exactly one density grid
		update_log(self, 'Add one density grid .xyd text file corresponding to the loaded .xyz surface')
		pass

	else:
		tic = process_time()
		update_log(self, 'Processing reference surface density')
		print('parsing/matching density data')
		fname_dens = fnames_xyd[0]
		self.ref['fname_dens'] = fname_dens
		fid_dens = open(fname_dens, 'r')
		e_dens, n_dens, c_dens = [], [], []
		for line in fid_dens:
			# print('parsing density line = ', line)
			# temp = line.replace('\n', '').split(",")
			temp = line.replace(',', ' ').strip().rstrip().split()
			e_dens.append(temp[0])  # easting
			n_dens.append(temp[1])  # northing
			c_dens.append(temp[2])  # count

		# the density layer exports do not always have the same number of nodes! need to match up to nodes...
		e_dens = np.array(e_dens, dtype=np.float32)
		n_dens = np.array(n_dens, dtype=np.float32)
		c_dens = np.array(c_dens, dtype=np.float32)

		# check density grid cell size, warn user if not matching reference grid cell size
		dens_de, dens_dn = check_cell_size(self, e_dens, n_dens)
		if dens_de == dens_dn:
			update_log(self, 'Imported density grid has uniform cell size: ' + str(dens_de) + ' m')

		else:
			update_log(self, 'WARNING: Unequal density grid cell sizes ' +
					   '(E: ' + str(dens_de) + ' m , N: ' + str(dens_dn) + ' m)', font_color="red")

		if any([dens_cell_size != self.ref_cell_size for dens_cell_size in [dens_de, dens_dn]]):
			update_log(self, 'WARNING: Density grid cell size does not match reference grid cell size; assigning '
							 'density values to matching reference surface node positions may cause unexpected results',
					   font_color="red")

		# loop through all nodes in reference surface, attach density value if matching E and N
		self.ref['c'] = np.empty_like(self.ref['z'])
		self.ref['c'][:] = np.nan
		len_ref = len(self.ref['z'])
		parse_prog_old = -1

		for i in range(len(self.ref['z'])):
			parse_prog = round(10 * i / len_ref)
			if parse_prog > parse_prog_old:
				print("%s%%" % (parse_prog * 10) + ('\n' if parse_prog == 10 else ''), end=" ", flush=True)
				parse_prog_old = parse_prog

			idx_e = np.where(e_dens == self.ref['e'][i])  # , e_dens)
			idx_n = np.where(n_dens == self.ref['n'][i])  # , n_dens)
			idx_match = np.intersect1d(idx_e, idx_n)
			if len(idx_match) == 1:
				self.ref['c'][i] = c_dens[idx_match][0]

		update_log(self, 'Imported density grid: ' + fname_dens.split('/')[-1] + ' with ' + str(len(self.ref['c'])) + ' nodes')

		toc = process_time()
		refresh_time = toc - tic
		print('assigning density nodes took', refresh_time, ' s')


def update_ref_slope(self):
	# update slope and plot after changing slope calc params
	calc_ref_slope(self)
	refresh_plot(self, refresh_list=['ref'], sender='update_ref_slope')


def calc_ref_slope(self):
	# calculate representative maximum slope for each node in reference grid
	# 0. make z grid with nearest neighbor interpolation (so empty cells and edges do not cause NaN gradients; this is
	# for gradient/slope calculation only, as these cells will be masked later to match shape of depth grid)
	print('in calc_ref_slope')
	z_grid_temp, z_grid_temp_extent = make_grid(self, self.ref['e'], self.ref['n'], self.ref['z'], self.ref_cell_size,
												mask_original_shape=False, method='nearest')

	# 1. take moving average of z grid with user-selected window size
	z_grid_smooth = uniform_filter(z_grid_temp, size=int(self.slope_win_cbox.currentText()[0]))

	# 2. calculate north-south and east-west gradients; convert to slopes with known cell spacing; assume the maximum
	# absolute value of slope in either direction is representative of the maximum slope in any direction for each node
	grad = np.gradient(z_grid_smooth)
	slope_y = np.rad2deg(np.arctan2(grad[0], self.ref_cell_size))
	slope_x = np.rad2deg(np.arctan2(grad[1], self.ref_cell_size))
	slope_max = np.maximum(np.abs(slope_x), np.abs(slope_y))

	# 3. apply mask from original z_grid (NaN wherever no depth node exists
	slope_max[np.isnan(self.ref['z_grid'])] = np.nan
	self.ref['s_grid'] = slope_max  # store slope grid with same shape as depth and density grids
	self.ref['s'] = slope_max[~np.isnan(slope_max)][:]  # store slopes like easting, northing, depth, dens for filtering
	print('leaving calc_ref_slope')


def make_ref_surf(self):
	# make grids of reference surface depth, density, slope
	# note: this is separate from applying masks from user limits, e.g., adjustable slope filters
	print('calling make_grid from make_ref_surf')
	update_log(self, 'Generating reference grids for plotting and filtering')

	# for dim in ['n', 'e', 'z', 'c']:
	for dim in ['n', 'e', 'z', 'c', 'u']:

		grid_str = dim + '_grid'
		extent_str = dim + '_ref_extent'

		if dim in self.ref and not grid_str in self.ref:  # generate grid, extent for parameter if not done so already
			# update_log(self, 'Generating reference grid for ' + dim)
			print('in make_ref_surf, calling make_grid for dim =', dim, 'with self.ref_cell_size =', self.ref_cell_size)
			grid, extent = make_grid(self, self.ref['e'], self.ref['n'], self.ref[dim], self.ref_cell_size)
			self.ref[grid_str] = deepcopy(grid)
			self.ref[extent_str] = deepcopy(extent)
		else:
			print('grid not generated for dim =', dim, 'because either grid already exists or data not available')

	if 'z_grid' in self.ref and not 's_grid' in self.ref:  # make slope grid masked with original shape of depth grid
		update_log(self, 'Generating reference slope grid')
		calc_ref_slope(self)  # calculate slope using z_grid

	print('leaving make_ref_surf with self.ref.keys = ', self.ref.keys())


def make_grid(self, ax1, ax2, val, spacing, mask_original_shape=True, fill_value=np.nan, method='linear'):
	# generate a grid covering the ax1 and ax2 extents with NaN wherever there is no val
	# ax1, ax2, and val are lists of, e.g., easting, northing, and depth values with same len
	# spacing is the assumed fixed grid size desired in the output grid
	# by default, return Nans where there is no data in the gridded result; set mask_original_shape to False to
	# keep the interpolated result within the convex hull and NaNs outside; set method to 'nearest' to fill grid with
	# nearest value

	# generate a z_grid covering the E and N extents with NaN wherever there is no imported ref depth
	ax1_min, ax1_max, ax2_min, ax2_max = min(ax1), max(ax1), min(ax2), max(ax2)
	try:
		print('in make_grid, ax1_min, max =', ax1_min, ax1_max, ' and ax2_min, max =', ax2_min, ax2_max,
			  'and spacing =', spacing)
		num_ax1 = round((ax1_max - ax1_min) / spacing) + 1  # number of easting nodes in grid if all are spaced equally
		num_ax2 = round((ax2_max - ax2_min) / spacing) + 1  # number of northing nodes in grid if all are spaced equally
		print('in make_grid, got rounded num_ax1, num_ax2 =', num_ax1, num_ax2)
	except:
		print('in make_grid, failed to get num_ax1 and/or num_ax2 from ax min/max and spacing info')

	ax1_nodes, ax2_nodes = np.linspace(ax1_min, ax1_max, num_ax1), np.linspace(ax2_min, ax2_max, num_ax2)
	ax1_grid, ax2_grid = np.meshgrid(ax1_nodes, ax2_nodes, indexing='xy')  # generate arrays for all nodes for griddata

	# grid data (griddata interps within convex hull; remove results outside 'original' shape in next step if desired)
	val_grid = griddata((ax1, ax2), val, (ax1_grid, ax2_grid), method=method, fill_value=fill_value)

	if mask_original_shape:
		# mask griddata results that include convex hull areas outside the imported ref surface data
		# (adapted from SO answer by pv. for fast masking of griddata when convex hull is insufficient)
		tree = KDTree(np.c_[ax1, ax2])
		dist, _ = tree.query(np.c_[ax1_grid.ravel(), ax2_grid.ravel()], k=1)
		dist = dist.reshape(ax1_grid.shape)
		# val_grid[dist > 0.1] = np.nan  # old fixed method lead to strange masking results for imperfectly spaced grids
		print('masking val_grid for original grid shape, setting nans for dist > 1% of grid spacing')
		val_grid[dist > spacing/100] = np.nan

	val_grid = np.flipud(val_grid)  # flipud required to get same orientation as ref surf in proc software
	extent = ax1_min, ax1_max, ax2_min, ax2_max

	print('returning from make_grid with size of val_grid = ', np.size(val_grid), 'and extents =', extent)
	print('first ten values of val_grid are', val_grid[0:10])

	return val_grid, extent


def calc_ref_mask(self):
	# calculate the final reference surface based on depth, density, and slope filters
	z_min = (-1*float(self.max_depth_ref_tb.text()) if self.depth_ref_gb.isChecked() else -1*np.inf)  # +Z down in GUI
	z_max = (-1*float(self.min_depth_ref_tb.text()) if self.depth_ref_gb.isChecked() else np.inf)  # +Z down in GUI
	c_min, c_max = (float(self.min_dens_tb.text()) if self.density_gb.isChecked() else 0), np.inf  # sounding count
	s_min, s_max = 0, (float(self.max_slope_tb.text()) if self.slope_gb.isChecked() else np.inf)  # slope
	u_min, u_max = 0, (float(self.max_u_tb.text()) if self.uncertainty_gb.isChecked() else np.inf)  # uncertainty

	# print('MASKING WITH min/max of z, c, s, and u=', z_min, z_max, c_min, c_max, s_min, s_max, u_min, u_max)

	try:
		print('IN CALC_REF_MASK, self.ref.keys =', self.ref.keys())
		if all([k in self.ref.keys() for k in ['z_grid', 's_grid']]):  # for k in self.ref.keys()]):
			print('in calc_ref_mask, found z_grid and s_grid in self.ref.keys')
			# initialize masks for each grid, true unless filtered
			for mask in ['z_mask', 's_mask', 'c_mask', 'u_mask', 'final_mask']:
				self.ref[mask] = np.nan*np.ones_like(self.ref['z_grid'])

			print('in calc_ref_mask, applying depth and slope criteria to mask')
			self.ref['z_mask'][np.logical_and(self.ref['z_grid'] >= z_min, self.ref['z_grid'] <= z_max)] = 1
			self.ref['s_mask'][np.logical_and(self.ref['s_grid'] >= s_min, self.ref['s_grid'] <= s_max)] = 1

			# uncertainty is set to 0 if not parsed from .xyz file
			print('working on u_mask...')
			self.ref['u_mask'][np.logical_and(self.ref['u_grid'] >= u_min, self.ref['u_grid'] <= u_max)] = 1

			if 'c_grid' in self.ref:  # sounding count may not be loaded
				self.ref['c_mask'][np.logical_and(self.ref['c_grid'] >= c_min, self.ref['c_grid'] <= c_max)] = 1

			else:
				self.ref['c_mask'] = np.ones_like(self.ref['z_grid'])

			self.ref['final_mask'] = self.ref['z_mask']*self.ref['s_mask']*self.ref['c_mask']*self.ref['u_mask']

			for mask in ['z_mask', 's_mask', 'c_mask', 'u_mask', 'final_mask']:
				print('num in ', mask, '=', np.sum(~np.isnan(self.ref[mask])))

		else:
			print('z_grid and/or s_grid not found in self.ref')

	except:
		print('error in calc_ref_mask, possibly because self.ref is nonexistent')


def plot_ref_surf(self):
	# plot reference depth, density, slope, and final masked grids
	print('in plot_ref_surf, calling calc_ref_mask')
	calc_ref_mask(self)  # update masks before plotting
	print('back in plot_ref_surf after calling calc_ref_mask')

	if 'final_mask' not in self.ref.keys():
		update_log(self, 'Final mask not computed; ref surf will not be plotted')
		return

	ones_mask = np.ones_like(self.ref['final_mask'])  # alternative mask to show all data in each grid

	# update subplots with reference surface and masks; all subplots use same extent from depth grid
	if 'z_grid' in self.ref:  # plot depth and final depths if available
		self.clim_z = [np.nanmin(self.ref['z_grid']), np.nanmax(self.ref['z_grid'])]
		self.cbar_dict['z']['clim'] = self.clim_z
		self.cbar_dict['z_filt']['clim'] = self.clim_z
		self.cbar_dict['z_final']['clim'] = self.clim_z

		# subplot depth as parsed or as filtered
		plot_mask = (self.ref['z_mask'] if self.update_ref_plots_chk.isChecked() else ones_mask)
		self.surf_ax1.imshow(self.ref['z_grid']*plot_mask, interpolation='none', cmap='rainbow',
							 vmin=self.clim_z[0], vmax=self.clim_z[1], extent=self.ref['z_ref_extent'])

		# large plot of final masked depth surface
		self.surf_ax5.imshow(self.ref['z_grid']*self.ref['final_mask'], interpolation='none', cmap='rainbow',
							 vmin=self.clim_z[0], vmax=self.clim_z[1], extent=self.ref['z_ref_extent'])

	# plot density if available
	if 'c_grid' in self.ref and 'z_ref_extent' in self.ref:
		print('plotting density')
		self.clim_c = [np.nanmin(self.ref['c_grid']), np.nanmax(self.ref['c_grid'])]
		self.cbar_dict['c']['clim'] = self.clim_c
		# plot density grid as parsed or as filtered
		plot_mask = (self.ref['c_mask'] if self.update_ref_plots_chk.isChecked() else ones_mask)
		self.surf_ax2.imshow(self.ref['c_grid']*plot_mask, interpolation='none', cmap='rainbow',
							 vmin=self.clim_c[0], vmax=self.clim_c[1], extent=self.ref['z_ref_extent'])

	else:
		# self.surf_ax2.clear()
		update_log(self, 'No sounding density data available for plotting/filtering (load .xyd text file of density '
						 'corresponding to reference depth .xyz file)')

	# plot slope if available
	if 's_grid' in self.ref and 'z_ref_extent' in self.ref:
		print('plotting slope')
		self.clim_s = [0, 5]  # fixed slope limits rather than min/max from calcs
		self.cbar_dict['s']['clim'] = self.clim_s
		# plot max slope as calculated or as filtered
		plot_mask = (self.ref['s_mask'] if self.update_ref_plots_chk.isChecked() else ones_mask)
		self.surf_ax3.imshow(self.ref['s_grid']*plot_mask, interpolation='none', cmap='rainbow',
							 vmin=self.clim_s[0], vmax=self.clim_s[1], extent=self.ref['z_ref_extent'])

	if 'u_grid' in self.ref and 'z_ref_extent' in self.ref and self.show_u_plot_chk.isChecked():
		# plot uncertainty if available and selected by user (replaces small "final" masked surface subplot)
		self.clim_u = [np.nanmin(self.ref['u_grid']), np.nanmax(self.ref['u_grid'])]
		self.cbar_dict['u']['clim'] = self.clim_u
		plot_mask = (self.ref['u_mask'] if self.update_ref_plots_chk.isChecked() else ones_mask)
		self.surf_ax4.imshow(self.ref['u_grid'] * plot_mask, interpolation='none', cmap='rainbow',
							 vmin=self.clim_u[0], vmax=self.clim_u[1], extent=self.ref['z_ref_extent'])

	elif 'z_grid' in self.ref:  # otherwise, plot masked final depths
		self.surf_ax4.imshow(self.ref['z_grid'] * self.ref['final_mask'], interpolation='none', cmap='rainbow',
							 vmin=self.clim_z[0], vmax=self.clim_z[1], extent=self.ref['z_ref_extent'])
		print('survived plotting final masked surface in subplot4')

	# add labels to all subplots (update uncertainty title later, if plotted)
	for ax, t in {self.surf_ax1: 'Reference Surface (Depth)', self.surf_ax2: 'Reference Surface (Density)',
				  self.surf_ax3: 'Reference Surface (Slope)', self.surf_ax4: 'Reference Surface (Final)',
				  self.surf_ax5: 'Reference Surface (Final)'}.items():
		ax.set_xlabel('Easting (m, UTM ' + self.ref_utm_str + ')', fontsize=8)
		ax.set_ylabel('Northing (m, UTM ' + self.ref_utm_str + ')', fontsize=8)
		ax.use_sticky_edges = False
		# ax.margins(float(self.axis_margin_tb.text())/100)
		ax.margins(float(self.axis_margin/100))
		ax.autoscale(True)
		# ticks = ax.xaxis.get_major_ticks()

		for tick_ax in [ax.xaxis, ax.yaxis]:
			ticks = tick_ax.get_major_ticks()
			for tick in ticks:
				tick.label.set_fontsize(6)

		ax.set_title(t, fontsize=10)

		if ax == self.surf_ax4 and self.show_u_plot_chk.isChecked():  # update subplot4 uncertainty title
			ax.set_title('Reference Surface (Uncertainty)', fontsize=10)

	# sort out colorbars
	for subplot, params in self.cbar_dict.items():  # set colorbars for each ref surf subplot
		if params['cax'] != None:  # remove all colorbars
			params['cax'].remove()

		if subplot == ['u', 'z_filt'][int(self.show_u_plot_chk.isChecked())]:  # skip u or z_filt plot in subplot4
			params['cax'] = None  # save placeholder cax = None for this ax so removal step doesn't fail on next refresh
			continue

		clim = params['clim']
		cbaxes = inset_axes(params['ax'], width="2%", height="30%", loc=self.cbar_loc)
		tval = np.linspace(clim[0], clim[1], 11)
		cbar = colorbar.ColorbarBase(cbaxes, cmap='rainbow', orientation='vertical',
									 norm=colors.Normalize(clim[0], clim[1]),
									 ticks=tval, ticklocation='left')

		cbar.ax.tick_params(labelsize=self.cbar_font_size)  # set font size for entries
		cbar.set_label(label=params['label'], size=self.cbar_title_font_size)
		# cbar.ax.set_facecolor('white')
		# cbar.set_facecolor('white')
		# cbar.patch.set_color('white')
		# cbar.patch.set_facecolor((1.0,1.0,1.0,1.0))
		# cbar.patch.set_facecolor('white')
		# cbar.patch.set_fill(True)
		# cbar.filled(True)
		# cbar.set_color('white')

		if subplot in ['c']:
			tlab = ['%d' % tick for tick in tval]  # integer sounding count tick labels

		else:
			tlab = ['%0.1f' % float((1 if subplot in ['s', 'u'] else -1)*tick) for tick in tval]

		cbar.set_ticklabels(tlab)
		params['cax'] = cbar

	# plot crossline soundings and trackline if checked
	if 'e' in self.xline and 'n' in self.xline and self.show_xline_cov_chk.isChecked():
		print('starting plot coverage process')
		# nan_idx = np.isnan(self.xline['e'])
		# print('got nan_idx with sum of non-nans=', np.sum(~nan_idx))
		# real_e = np.asarray(self.xline['e'])[~nan_idx].tolist()
		# real_n = np.asarray(self.xline['n'])[~nan_idx].tolist()
		# print('got real_e with len=', len(real_e))
		# print('got real_n with len=', len(real_n))

		# original method with all coverage
		# dec_data = decimate_data(self, data_list=[deepcopy(self.xline['e']), deepcopy(self.xline['n'])])
		# real_e_dec = dec_data[0]
		# real_n_dec = dec_data[1]

		# new method with coverage based on filters
		filter_idx = np.where(self.xline['filter_idx'])[0]
		real_e = (np.asarray(self.xline['e'])[filter_idx]).tolist()
		real_n = (np.asarray(self.xline['n'])[filter_idx]).tolist()

		dec_data = decimate_data(self, data_list=[real_e, real_n])
		real_e_dec = dec_data[0]
		real_n_dec = dec_data[1]

		print('real_e_dec and real_n_dec have lens=', len(real_e_dec), len(real_n_dec))
		self.surf_ax5.scatter(real_e_dec, real_n_dec,
							  s=self.pt_size_cov, c='lightgray', marker='o', alpha=0.1, linewidths=0)
		print('survived scatter call')

		for f in self.xline_track.keys():  # plot soundings on large final surface plot
			self.surf_ax5.scatter(self.xline_track[f]['e'], self.xline_track[f]['n'],
								  s=2, c='black', marker='o', linewidths=2)

		# for ax in [self.surf_ax1, self.surf_ax2, self.surf_ax3, self.surf_ax4]:  # plot soundings on subplots
			# print('working on ax=', ax)
			# if self.show_xline_cov_chk.isChecked():
			# ax.scatter(self.xline['e'], self.xline['n'],
			# 		   s=1, c='lightgray', marker='o', alpha=0.1, linewidths=0)
			# for f in self.xline_track.keys():
			# 	ax.scatter(self.xline_track[f]['e'], self.xline_track[f]['n'],
			# 			   s=2, c='black', marker='o', linewidths=2)

def plot_tide(self, set_active_tab=False):
	# plot imported tide data
	if not all([k in self.tide.keys() for k in ['time_obj', 'amplitude']]):
		print('Tide time and amplitude not available for plotting')
		return

	update_log(self, 'Plotting tide')
	self.tide_ax.plot(self.tide['time_obj'], self.tide['amplitude'],
					  color='black', marker='o', markersize=self.pt_size/10, alpha=self.pt_alpha)

	print('in plot_tide, self.xline.keys = ', self.xline.keys())
	# if all([k in self.xline.keys() for k in ['tide_applied', 'time_obj']]):
	if all([k in self.xline.keys() for k in ['tide_applied', 'datetime']]):
		print('in plot_tide, trying to plot the tide applied')
		print('self.xline[0] =', self.xline[0])

		# get unique ping times by finding where applied tide diff != 0, rather than resorting
		# ping_idx = [self.xline['time_obj'].index(t) for t in set(self.xline['time_obj'])]  # get unique ping times
		# ping_time_set = [self.xline['time_obj'][i] for i in ping_idx]
		print('trying to get set(self.xline[datetime])')
		testing = set(self.xline['datetime'])
		print('got testing = ', testing)
		print('now starting to get ping_idx')
		ping_idx = [self.xline['datetime'].index(t) for t in set(self.xline['datetime'])]  # get unique ping times
		print('1')
		print('len ping_idx =', len(ping_idx))
		ping_time_set = [self.xline['datetime'][i] for i in ping_idx]
		print('2')
		tide_ping_set = [self.xline['tide_applied'][i] for i in ping_idx]
		print('3')
		sort_idx = np.argsort(ping_time_set)
		print('4')
		print('trying to plot ')
		self.tide_ax.plot(np.asarray(ping_time_set)[sort_idx], np.asarray(tide_ping_set)[sort_idx], 'ro',
						  markersize=self.pt_size / 10)
		print('5')
		self.tide_canvas.draw()
		print('7')

	if set_active_tab:
		print('6')
		self.plot_tabs.setCurrentIndex(2)  # make the tide plot active


def plot_tide2(self, set_active_tab=False):
	# plot imported tide data - ALL DATA since sorting takes longer than its worth
	if not all([k in self.tide.keys() for k in ['time_obj', 'amplitude']]):
		print('Tide time and amplitude not available for plotting')
		return

	update_log(self, 'Plotting tide')
	self.tide_ax.plot(self.tide['time_obj'], self.tide['amplitude'],
					  color='black', marker='o', markersize=self.pt_size/10, alpha=self.pt_alpha)

	print('in plot_tide, self.xline.keys = ', self.xline.keys())
	# if all([k in self.xline.keys() for k in ['tide_applied', 'time_obj']]):
	if all([k in self.xline.keys() for k in ['tide_applied', 'datetime']]):
		print('in plot_tide2, trying to plot the tide applied')
		self.tide_ax.plot(np.asarray(self.xline['datetime']), np.asarray(self.xline['tide_applied']), 'ro',
						  markersize=self.pt_size / 10)
		self.tide_canvas.draw()

	if set_active_tab:
		self.plot_tabs.setCurrentIndex(2)  # make the tide plot active


def parse_crosslines(self):
	# parse crosslines
	update_log(self, 'Parsing accuracy crosslines')
	try:
		fnames_xline = list(set(self.xline['fname']))  # make list of unique filenames already in detection dict

	except:
		fnames_xline = []  # self.xline has not been created yet; initialize this and self.xline detection dict
		self.xline = {}
		self.xline_track = {}

	# fnames_new_all = self.get_new_file_list('.all', fnames_xline)  # list new .all files not included in det dict
	fnames_new = get_new_file_list(self, ['.all', '.kmall'], fnames_xline)  # list all files not in xline dict
	num_new_files = len(fnames_new)
	# update_log(self, 'Found ' + str(len(fnames_new)) + ' new crossline .all files')

	if num_new_files == 0:
		update_log(self, 'No new .all or .kmall crosslines added.  Please add new file(s) and calculate accuracy')

	else:
		update_log(self, 'Found ' + str(len(fnames_new)) + ' new crossline .all files')
		# if len(fnames_new_all) > 0:  # proceed if there is at least one .all file that does not exist in det dict
		update_log(self, 'Calculating accuracy from ' + str(num_new_files) + ' new file(s)')
		QtWidgets.QApplication.processEvents()  # try processing and redrawing the GUI to make progress bar update
		data_new = {}
		track_new ={}

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

				# WORKING METHOD
				# data_new[f] = readALLswath(self, fnames_new[f], print_updates=False, parse_outermost_only=False)

				# TESTING METHOD
				print('sending .all file to readALLswath')
				data = readALLswath(self, fnames_new[f], print_updates=False, parse_outermost_only=False)
				# print('got data back from readAllswath with type =', type(data))
				# print('now sending dictionary = {0:data} to convertXYZ')
				converted_data = convertXYZ({0: data}, print_updates=False)  # convertXYZ for dict of parsed .all data
				# converted_data = convertXYZ({0: data}, print_updates=True)  # convertXYZ for dict of parsed .all data
				# print('got back converted_data with type =', type(converted_data))
				# print('now trying to store converted data in data_new[f]')
				data_new[f] = converted_data[0]
				# print('stored converted data, data_new is now', data_new)

				# store xline track data separately from detection data for plotting
				# WARNING: THIS IS OVERWRITING EXISTING TRACKS (e.g., f=0, 1, 2, etc.) WHEN NEW FILES ARE ADDED
				# self.xline_track[f] = {k: data_new[f][k] for k in ['POS', 'IP']}  # store POS and IP for track
				# self.xline_track[f]['fname'] = fname_str
				track_new[f] = {k: data_new[f][k] for k in ['POS', 'IP']}  # store POS and IP for track
				track_new[f]['fname'] = fname_str
				# self.xline_track[fname_str] = {k: data_new[f][k] for k in ['POS', 'IP']}  # store POS and IP for track
				# print('stored track=', self.xline_track[fname_str])

			elif ftype == 'kmall':
				data_new[f] = readKMALLswath(self, fnames_new[f])

				# store RTP with pingInfo lat/lon
				print('storing pingInfo lat/lon as ship track for this kmall file')
				# self.xline_track[f] = {k: data_new[f][k] for k in ['RTP', 'IP']}
				# self.xline_track[f]['fname'] = fname_str
				track_new[f] = {k: data_new[f][k] for k in ['HDR', 'RTP', 'IP']}
				track_new[f]['fname'] = fname_str
				# print('data_new[IP]=', data_new[f]['IP'])
				# print('IP text =', data_new[f]['IP']['install_txt'])

			else:
				update_log(self, 'Warning: Skipping unrecognized file type for ' + fname_str)

			update_log(self, 'Parsed file ' + fname_str)
			update_prog(self, f + 1)

		print('finished parsing, data_new has keys=', data_new.keys(), ' and data_new[0].keys = ', data_new[0].keys())

		# convert XYZ to lat, lon using active pos sensor; maintain depth as reported in file; interpret/verify modes
		# self.data_new = convertXYZ(data_new, print_updates=True)  # for .all files only?
		self.data_new = interpretMode(self, data_new, print_updates=self.print_updates)  # True)
		print('survived interpretMode, self.data_new has keys')
		# print('testing calling sortDetectionsAccuracy before verifying modes')
		det_new = sortDetectionsAccuracy(self, self.data_new, print_updates=True)  # sort new accuracy soundings
		print('survived sortDetectionsAccuracy, det_new has keys', det_new.keys())

		# files_OK, EM_params = verifyMode(self.data_new)  # check install and runtime params
		# if not files_OK:  # warn user if inconsistencies detected (perhaps add logic later for sorting into user-selectable lists for archiving and plotting)
		# 	update_log(self, 'WARNING! CROSSLINES HAVE INCONSISTENT MODEL, S/N, or RUNTIME PARAMETERS')


		# sort ship track
		track_new = sort_xline_track(self, track_new)  # sort crossline track after adding any new files  ---> UPDATE TO KEEP EARLIER TRACKS
		print('got track_new with keys = ', track_new.keys())

		if len(self.xline) == 0 and len(self.xline_track) == 0:  # if detection dict is empty, store all new detections
			print('len of self.xline and self.xline_track == 0, so setting equal to det_new and track_new')

			self.xline = det_new
			self.xline_track = track_new

		# print('det_new =', det_new)
			# print('track_new = ', track_new)

		else:  # otherwise, append new detections to existing detection dict
			for key, value in det_new.items():  # loop through the new data and append to existing self.xline
				print('extending self.xline with key =', key)
				# print('value has type', type(value), 'and = ', value)
				self.xline[key].extend(value)

			# for key, value in track_new[0].items():  # loop through the new track and append to existing self.xline_track
			for key, value in track_new.items():  # loop through the new track fnames append to existing self.xline_track

				print('extending self.xline_track with key =', key)
				# print('value has type', type(value), ' and = ', value)
				self.xline_track[key] = value
				# print('extending self.xline_track with key =', key)

		# sort_xline_track(self)  # sort crossline track after adding any new files  ---> UPDATE TO KEEP EARLIER TRACKS
		# track_new = sort_xline_track(self, track_new)  # sort crossline track after adding any new files  ---> UPDATE TO KEEP EARLIER TRACKS

		# verify consistent system info and runtime params
		sys_info = verifyModelAndModes(self.xline)
		if len(sys_info['datetime']) == 1:
			update_log(self, 'Consistent model, serial number, and modes in all files')

		else:
			log_str = ''
			for i in range(len(sys_info['datetime'])):
				# temp_str = '\n' + ','.join([k + ': ' + str(sys_info[k][i]) for k in sys_info.keys()])
				temp_str = '\n' + ', '.join([str(sys_info[k][i]) for k in \
											 ['fname', 'model', 'sn', 'ping_mode', 'swath_mode', 'pulse_form']])
				log_str += temp_str

			update_log(self, 'Found inconsistent parameters:\n' + \
							 'Filename: Model, S/N, Ping Mode, Swath Mode, Pulse Form\n' + log_str)


		update_log(self, 'Finished parsing ' + str(num_new_files) + ' new file(s)')
		self.current_file_lbl.setText('Current File [' + str(f + 1) + '/' + str(num_new_files) +
									  ']: Finished parsing crosslines')

	self.calc_accuracy_btn.setStyleSheet("background-color: none")  # reset the button color to default

	return num_new_files


def sortDetectionsAccuracy(self, data, print_updates=False):
	# sort through .all and .kmall data dict and store valid soundings, BS, and modes
	# note: .all data must be converted from along/across/depth data to lat/lon with convertXYZ before sorting
	det_key_list = ['fname',  'model', 'datetime', 'date', 'time', 'sn',
					'lat', 'lon', 'x', 'y', 'z', 'z_re_wl', 'n', 'e', 'utm_zone', 'bs', 'rx_angle',
					'ping_mode', 'pulse_form', 'swath_mode', 'frequency',
					'max_port_deg', 'max_stbd_deg', 'max_port_m', 'max_stbd_m',
					'tx_x_m', 'tx_y_m', 'tx_z_m', 'aps_x_m', 'aps_y_m', 'aps_z_m', 'wl_z_m',
					'ping_e', 'ping_n', 'ping_utm_zone']  # mode_bin

	det = {k: [] for k in det_key_list}

	# examine detection info across swath, find outermost valid soundings for each ping
	for f in range(len(data)):  # loop through all data
		if print_updates:
			print('Sorting detections for accuracy, f =', f, ' and data[f] keys =', data[f].keys())
		# set up keys for dict fields of interest from parsers for each file type (.all or .kmall)
		ftype = data[f]['fname'].rsplit('.', 1)[1]
		key_idx = int(ftype == 'kmall')  # keys in data dicts depend on parser used, get index to select keys below
		det_int_threshold = [127, 0][key_idx]  # threshold for valid sounding (.all  <128 and .kmall == 0)
		det_int_key = ['RX_DET_INFO', 'detectionType'][key_idx]  # key for detect info depends on ftype
		depth_key = ['RX_DEPTH', 'z_reRefPoint_m'][key_idx]  # key for depth
		across_key = ['RX_ACROSS', 'y_reRefPoint_m'][key_idx]  # key for acrosstrack distance
		along_key = ['RX_ALONG', 'z_reRefPoint_m'][key_idx]  # key for alongtrack distance
		bs_key = ['RX_BS', 'reflectivity1_dB'][key_idx]  # key for backscatter in dB
		bs_scale = [0.1, 1][key_idx]  # backscatter scale in X dB; multiply parsed value by this factor for dB
		angle_key = ['RX_ANGLE', 'beamAngleReRx_deg'][key_idx]  # key for RX angle re RX array
		lat_key = ['SOUNDING_LAT', 'lat'][key_idx]
		lon_key = ['SOUNDING_LON', 'lon'][key_idx]
		e_key = ['SOUNDING_E', 'e'][key_idx]
		n_key = ['SOUNDING_N', 'n'][key_idx]
		utm_key = ['SOUNDING_UTM_ZONE', 'utm_zone'][key_idx]

		for p in range(len(data[f]['XYZ'])):  # loop through each ping
			# print('working on ping number ', p)
			det_int = data[f]['XYZ'][p][det_int_key]  # get detection integers for this ping
			det_idx = [i for i, v in enumerate(det_int) if v <= det_int_threshold]  # indices of all valid detections

			# extend swath data from appropriate keys/values in data dicts
			# future general sorter: accuracy, keep all valid det_int; coverage, reduce for outermost valid det_int
			det['fname'].extend([data[f]['fname'].rsplit('/')[-1]] * len(det_idx))  # store fname for each det
			det['x'].extend([data[f]['XYZ'][p][along_key][i] for i in det_idx])  # as parsed
			det['y'].extend([data[f]['XYZ'][p][across_key][i] for i in det_idx])  # as parsed
			det['z'].extend([data[f]['XYZ'][p][depth_key][i] for i in det_idx])  # as parsed

			det['lat'].extend([data[f]['XYZ'][p][lat_key][i] for i in det_idx])
			det['lon'].extend([data[f]['XYZ'][p][lon_key][i] for i in det_idx])

			det['n'].extend([data[f]['XYZ'][p][n_key][i] for i in det_idx])
			det['e'].extend([data[f]['XYZ'][p][e_key][i] for i in det_idx])
			# det['bs'].extend([data[f]['XYZ'][p][bs_key][i] for i in det_idx])
			det['bs'].extend([data[f]['XYZ'][p][bs_key][i] * bs_scale for i in det_idx])
			det['ping_mode'].extend([data[f]['XYZ'][p]['PING_MODE']] * len(det_idx))
			det['pulse_form'].extend([data[f]['XYZ'][p]['PULSE_FORM']] * len(det_idx))
			# det['z_re_wl'].extend([data[f]['XYZ'][p]['SOUNDING_Z'][i] for i in det_idx])  # corrected to waterline
			# det['ping_utm_zone'].extend([data[f]['XYZ'][p]['PING_UTM_ZONE']] * len(det_idx))
			# det['ping_e'].extend([data[f]['XYZ'][p]['PING_E']] * len(det_idx))
			# det['ping_n'].extend([data[f]['XYZ'][p]['PING_N']] * len(det_idx))

			if ftype == 'all':  # .all store date and time from ms from midnight
				det['model'].extend([data[f]['XYZ'][p]['MODEL']] * len(det_idx))
				det['sn'].extend([data[f]['XYZ'][p]['SYS_SN']] * len(det_idx))
				dt = datetime.datetime.strptime(str(data[f]['XYZ'][p]['DATE']), '%Y%m%d') + \
					 datetime.timedelta(milliseconds=data[f]['XYZ'][p]['TIME'])
				det['datetime'].extend([dt] * len(det_idx))
				det['date'].extend([dt.strftime('%Y-%m-%d')] * len(det_idx))
				det['time'].extend([dt.strftime('%H:%M:%S.%f')] * len(det_idx))
				det['utm_zone'].extend([data[f]['XYZ'][p][utm_key]] * len(det_idx))  # convertXYZ --> one utmzone / ping
				# det['rx_angle'].extend([data[f]['RRA_78'][p][angle_key][i] for i in det_idx])
				det['swath_mode'].extend([data[f]['XYZ'][p]['SWATH_MODE']] * len(det_idx))
				det['max_port_deg'].extend([data[f]['XYZ'][p]['MAX_PORT_DEG']] * len(det_idx))
				det['max_stbd_deg'].extend([data[f]['XYZ'][p]['MAX_STBD_DEG']] * len(det_idx))
				det['max_port_m'].extend([data[f]['XYZ'][p]['MAX_PORT_M']] * len(det_idx))
				det['max_stbd_m'].extend([data[f]['XYZ'][p]['MAX_STBD_M']] * len(det_idx))
				# print('in ping', p, 'with data[f][IP_START] =', data[f]['IP_start'])
				det['tx_x_m'].extend([data[f]['XYZ'][p]['TX_X_M']] * len(det_idx))
				det['tx_y_m'].extend([data[f]['XYZ'][p]['TX_Y_M']] * len(det_idx))
				det['tx_z_m'].extend([data[f]['XYZ'][p]['TX_Z_M']] * len(det_idx))
				det['aps_x_m'].extend([data[f]['XYZ'][p]['APS_X_M']] * len(det_idx))
				det['aps_y_m'].extend([data[f]['XYZ'][p]['APS_Y_M']] * len(det_idx))
				det['aps_z_m'].extend([data[f]['XYZ'][p]['APS_Z_M']] * len(det_idx))
				det['wl_z_m'].extend([data[f]['XYZ'][0]['WL_Z_M']] * len(det_idx))

			elif ftype == 'kmall':  # .kmall store date and time from datetime object
				det['model'].extend([data[f]['HDR'][p]['echoSounderID']] * len(det_idx))
				det['datetime'].extend([data[f]['HDR'][p]['dgdatetime']] * len(det_idx))
				det['date'].extend([data[f]['HDR'][p]['dgdatetime'].strftime('%Y-%m-%d')] * len(det_idx))
				det['time'].extend([data[f]['HDR'][p]['dgdatetime'].strftime('%H:%M:%S.%f')] * len(det_idx))
				det['utm_zone'].extend([data[f]['XYZ'][p][utm_key][i] for i in det_idx])  # readKMALLswath 1 utm/sounding
				det['aps_x_m'].extend([0] * len(det_idx))  # not needed for KMALL; append 0 as placeholder
				det['aps_y_m'].extend([0] * len(det_idx))  # not needed for KMALL; append 0 as placeholder
				det['aps_z_m'].extend([0] * len(det_idx))  # not needed for KMALL; append 0 as placeholder

				# get first installation parameter datagram in file for s/n and offsets, assume no changes within file
				ip_text = data[f]['IP']['install_txt'][0]
				# get TX array offset text: EM304 = 'TRAI_TX1' and 'TRAI_RX1', EM2040P = 'TRAI_HD1', not '_TX1' / '_RX1'
				ip_tx1 = ip_text.split('TRAI_')[1].split(',')[0].strip()  # all heads/arrays split by comma; use 1st hd
				det['tx_x_m'].extend([float(ip_tx1.split('X=')[1].split(';')[0].strip())] * len(det_idx))  # TX array X
				det['tx_y_m'].extend([float(ip_tx1.split('Y=')[1].split(';')[0].strip())] * len(det_idx))  # TX array Y
				det['tx_z_m'].extend([float(ip_tx1.split('Z=')[1].split(';')[0].strip())] * len(det_idx))  # TX array Z
				det['wl_z_m'].extend([float(ip_text.split('SWLZ=')[-1].split(',')[0].strip())] * len(det_idx))  # WL Z

				# get serial number from installation parameter: 'SN=12345'
				sn = ip_text.split('SN=')[1].split(',')[0].strip()
				det['sn'].extend([sn] * len(det_idx))

				# get index of latest runtime parameter timestamp prior to ping of interest; default to 0 for cases
				# where earliest pings in file might be timestamped earlier than first runtime parameter datagram
				IOP_headers = data[f]['IOP']['header']  # get list of IOP header dicts in new kmall module output
				IOP_datetimes = [IOP_headers[d]['dgdatetime'] for d in range(len(IOP_headers))]
				# print('got IOP datetimes =', IOP_datetimes)

				MRZ_headers = data[f]['HDR']
				MRZ_datetimes = [MRZ_headers[d]['dgdatetime'] for d in range(len(MRZ_headers))]

				# find index of last IOP datagram before current ping, default to first if
				IOP_idx = max([i for i, t in enumerate(IOP_datetimes) if t <= MRZ_datetimes[p]], default=0)

				if IOP_datetimes[IOP_idx] > MRZ_datetimes[p]:
					print('*****ping', p, 'occurred before first runtime datagram; using first RTP dg in file')

				# get runtime text from applicable IOP datagram, split and strip at keywords and append values
				rt = data[f]['IOP']['runtime_txt'][IOP_idx]  # get runtime text for splitting NEW KMALL FORMAT
				# print('IOP_idx = ', IOP_idx)
				print('rt = ', rt)

				# dict of keys for detection dict and substring to split runtime text at entry of interest
				rt_dict = {'max_port_deg': 'Max angle Port:', 'max_stbd_deg': 'Max angle Starboard:',
						   'max_port_m': 'Max coverage Port:', 'max_stbd_m': 'Max coverage Starboard:'}

				# iterate through rt_dict and append coverage limits from split/stripped runtime text
				for k, v in rt_dict.items():
					try:
						det[k].extend([float(rt.split(v)[-1].split('\n')[0].strip())] * len(det_idx))

					except:
						det[k].extend(['NA'] * len(det_idx))

				# parse swath mode text
				try:
					dual_swath_mode = rt.split('Dual swath:')[-1].split('\n')[0].strip()

					# print('kmall dual_swath_mode =', dual_swath_mode)

					depth_mode = rt.split('Depth setting:')[-1].split('\n')[0].strip().lower()
					print('found depth_mode =', depth_mode)
					print('depth_mode in [very deep, extra deep, extreme deep] = ',
						  depth_mode in ['very deep', 'extra deep', 'extreme deep'])

					# if dual_swath_mode == 'Off':
					if dual_swath_mode == 'Off' or depth_mode in ['very deep', 'extra deep', 'extreme deep']:
						swath_mode = 'Single Swath'

					else:
						swath_mode = 'Dual Swath (' + dual_swath_mode + ')'

				except:
					swath_mode = 'NA'

				det['swath_mode'].extend([swath_mode] * len(det_idx))

				# parse frequency from runtime parameter text, if available
				try:
					# print('trying to split runtime text')
					frequency_rt = rt.split('Frequency:')[-1].split('\n')[0].strip().replace('kHz', ' kHz')
					# print('frequency string from runtime text =', frequency_rt)

				except:  # use default frequency stored from interpretMode
					pass

				# store parsed freq if not empty, otherwise store default
				frequency = frequency_rt if frequency_rt else data[f]['XYZ'][p]['FREQUENCY']
				det['frequency'].extend([frequency] * len(det_idx))

				if print_updates:
					# print('found IOP_idx=', IOP_idx, 'with IOP_datetime=', data[f]['IOP']['dgdatetime'][IOP_idx])
					print('found IOP_idx=', IOP_idx, 'with IOP_datetime=', IOP_datetimes[IOP_idx])
					print('max_port_deg=', det['max_port_deg'][-1])
					print('max_stbd_deg=', det['max_stbd_deg'][-1])
					print('max_port_m=', det['max_port_m'][-1])
					print('max_stbd_m=', det['max_stbd_m'][-1])
					print('swath_mode=', det['swath_mode'][-1])

			else:
				print('UNSUPPORTED FTYPE --> NOT SORTING DETECTION!')

	if print_updates:
		print('\nDone sorting detections...')

	# print('leaving sortDetectionsCoverage with det[frequency] =', det['frequency'])

	return det


def calc_z_final(self):
	# adjust sounding depths to desired reference and flip sign as necessary for comparison to ref surf (positive up)
	_, _, dz_ping = adjust_depth_ref(self.xline, depth_ref=self.ref_cbox.currentText().lower())
	_, _, dz_ping_sonar = adjust_depth_ref(self.xline, depth_ref='TX array'.lower())
	# print('got dz_ping =', dz_ping)
	# print('got dz_ping_sonar =', dz_ping_sonar)
	# print('dz_ping has len', len(dz_ping))
	# print('first 20 of xline[z]=', self.xline['z'][0:20])
	# print('first 20 of dz_ping =', dz_ping[0:20])
	# z_final = [z + dz for z, dz in zip(self.xline['z'], dz_ping)]  # add dz

	# adjust reported depths (+DOWN) for tide at ping time (+UP); e.g., if the waterline-adjusted sounding was reported
	# as +10 m (down) when the tide was +1 m (up), the sounding is +9 m (down) from the tide datum
	# print('the first few dz_ping values are', dz_ping[0:10])
	# interpolate tide onto ping time
	# print('in calc_z_final, self.xlines.keys =', self.xline.keys())
	# print('the first few dates are ', self.xline['date'][0:10])
	# print('the first few times are ', self.xline['time'][0:10])
	# ping_times = [datetime.datetime.strptime(d + ' ' + t, '%Y-%m-%d %H:%M:%S.%f') for d, t in
	# 			  zip(self.xline['date'], self.xline['time'])]
	ping_times = self.xline['datetime']
	# print('the first few ping times are now', ping_times[0:10])

	self.tide_applied = False
	# ping_times = self.xlines
	if all([k in self.tide.keys() for k in ['time_obj', 'amplitude']]):
		print('working on tide interpolation onto ping times')
		# interp step needs non-datetime-object axis; use UNIX, assume UTC; sub-second precision not necessary!
		epoch = datetime.datetime.utcfromtimestamp(0)
		print('got epoch = ', epoch)
		tide_times_s = [(dt - epoch).total_seconds() for dt in self.tide['time_obj']]  # tide time in s from 1970
		ping_times_s = [(dt - epoch).total_seconds() for dt in ping_times]

		if ping_times_s[0] < tide_times_s[0] or ping_times_s[-1] > tide_times_s[-1]:
			update_log(self, 'WARNING: ping times found outside the tide record; zero tide will be applied',
					   font_color="red")
			tide_ping = np.zeros_like(self.xline['z'])

		else:
			update_log(self, 'Interpolating tide onto final crossline sounding times')
			tide_ping = np.interp(ping_times_s, tide_times_s, self.tide['amplitude'])
			self.tide_applied = True

		# print('got first few tide_time_s =', tide_times_s[0:10])
		# print('got first few ping_time_s =', ping_times_s[0:10])
		self.xline['tide_applied'] = deepcopy(tide_ping.tolist())
		# self.xline['time_obj'] = deepcopy(ping_times)
		# print('just stored self.xline[tide_applied] --> first few =', self.xline['tide_applied'][0:10])

	else:
		update_log(self, 'WARNING: No tide applied during final Z calculation', font_color="red")
		tide_ping = np.zeros_like(self.xline['z'])

	# print('got tide_ping first few values:', tide_ping[0:10])

	# add dz to bring soundings to waterline and then subtract tide to bring soundings to tide datum; results are +DOWN
	print('first couple Z values prior to adjustment: ', self.xline['z'][0:10])
	z_final = [z + dz - tide for z, dz, tide in zip(self.xline['z'], dz_ping, tide_ping)]  # z from user ref, w/ tide
	z_sonar = [z + dz for z, dz in zip(self.xline['z'], dz_ping_sonar)]  # z obs. from sonar ref for angle calc

	# add waterline adjustment (m +DOWN); a pos. value shifts WL down/lower in the mapping frame and results in
	# shallower final xline depths for processing
	wl_adjustment = [float(self.waterline_tb.text())]*len(z_final)  # get current waterline adjustment (m +down)
	z_final_wl = [z - dwl for z, dwl in zip(z_final, wl_adjustment)]  # z +DOWN after WL adjustment (also z+ DOWN)
	print('first ten wl_adjustment, z_final, and z_final_wl = ', wl_adjustment[:10], z_final[:10], z_final_wl[:10])

	# report final z re waterline and z re sonar
	self.xline['z_final'] = (-1 * np.asarray(z_final_wl)).tolist()  # flip sign to neg down and store 'final' soundings
	self.xline['z_sonar'] = (-1 * np.asarray(z_sonar)).tolist()  # store z from TX array for nominal beam angle calc
	z_sonar_pos_down = (-1 * np.asarray(self.xline['z_sonar'])).tolist()
	self.xline['beam_angle'] = np.rad2deg(np.arctan2(self.xline['y'], z_sonar_pos_down)).tolist()

	print('first couple Z_final values after adjustment: ', self.xline['z_final'][0:10])
	print('first couple Z_sonar values after adjustment: ', self.xline['z_sonar'][0:10])


def convert_crossline_utm(self):
	# if necessary, convert crossline X, Y to UTM zone of reference surface
	update_log(self, 'Checking UTM zones of ref grid and crossline(s)')
	ref_utm = self.ref['utm_zone']

	# format xline UTM zone for comparison with ref_utm and use with pyproj; replace zone letter with S if southern
	# hemisphere (UTM zone letter C-M) or N if northern hemisphere (else)
	xline_utm = [utm_str.replace(" ", "") for utm_str in self.xline['utm_zone']]
	xline_utm = [utm_str[:-1] + 'S' if utm_str[-1] <= 'M' else utm_str[:-1] + 'N' for utm_str in xline_utm]

	self.xline['utm_zone'] = xline_utm  # replace with new format
	print('detected ref surf UTM =', ref_utm, ' and set of xline utm zones =', set(xline_utm))
	xline_utm_list = [u for u in set(xline_utm) if u != ref_utm]  # get list of xline utm zones != ref surf utm zone
	print('non-matching utm zones:', xline_utm_list)

	if len(xline_utm_list) > 0:  # transform soundings from non-matching xline utm zone(s) into ref utm zone
		update_log(self, 'Found crossline soundings in UTM zone (' + ', '.join(xline_utm_list) + \
				   ') other than selected ref. surface UTM zone (' + ref_utm +'); transforming soundings to ' + ref_utm)

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


def convert_track_utm(self):
	# if necessary, convert crossline track X,Y to UTM zone of reference surface
	update_log(self, 'Checking UTM zones of ref grid and crossline track(s)')
	ref_utm = self.ref['utm_zone']
	print('in convert_track_utm, ref_utm=', ref_utm)
	# get set of
	track_utm_set = [u for u in set([self.xline_track[f]['utm_zone'] for f in self.xline_track.keys()]) if u != ref_utm]
	print('track_utm_set =', track_utm_set)

	if len(track_utm_set) == 0:  # return if no conversions are needed
		return

	# update user and continue with conversions as necessary
	update_log(self, 'Found tracklines in UTM zone(s) (' + ', '.join([u for u in track_utm_set]) + ') ' + \
			   'other than selected ref. surface UTM zone (' + ref_utm + '); transforming track to ' + ref_utm)

	p2 = pyproj.Proj(proj='utm', zone=ref_utm, ellps='WGS84')  # define ref surf projection for desired transform output

	for f in self.xline_track.keys():  # check track utm zone for each fname (key) and transform to ref UTM zone if nec.
		print('in file f=', f, 'the xline_track utm zone is', self.xline_track[f]['utm_zone'])
		track_utm = self.xline_track[f]['utm_zone']

		if track_utm != ref_utm:  # one utm zone assigned to each track dict (key = fname)
			track_e = np.asarray(self.xline_track[f]['e'])
			track_n = np.asarray(self.xline_track[f]['n'])
			p1 = pyproj.Proj(proj='utm', zone=track_utm, ellps='WGS84')  # define proj of current track line
			(track_e_new, track_n_new) = pyproj.transform(p1, p2, track_e, track_n)  # transform all track points
			update_log(self, 'Transformed ' + str(len(track_e_new)) + ' track points from ' + \
					   track_utm + ' to ' + ref_utm)

			# reassign the final coordinates
			self.xline_track[f]['e'] = track_e_new.tolist()
			self.xline_track[f]['n'] = track_n_new.tolist()
			self.xline_track[f]['utm_zone'] = ref_utm  # store single UTM zone for whole file

			print('new track easting is', self.xline_track[f]['e'][0:30])
			print('new track northing is', self.xline_track[f]['n'][0:30])
			print('new track utm_zone is', self.xline_track[f]['utm_zone'])


def calc_dz_from_ref_interp(self):
	# calculate the difference of each sounding from the reference grid (interpolated onto sounding X, Y position)
	update_log(self, 'Calculating ref grid depths at crossline sounding positions')
	# print('N ref_surf nodes e =', len(self.ref['e']), 'with first ten =', self.ref['e'][0:10])
	# print('N ref_surf nodes n =', len(self.ref['n']), 'with first ten =', self.ref['n'][0:10])
	# print('N ref_surf nodes z =', len(self.ref['z']), 'with first ten =', self.ref['z'][0:10])
	# print('N xline soundings e =', len(self.xline['e']), 'with first ten =', self.xline['e'][0:10])
	# print('N xline soundings n =', len(self.xline['n']), 'with first ten =', self.xline['n'][0:10])
	# print('N xline soundings z =', len(self.xline['z']), 'with first ten =', self.xline['z'][0:10])
	# print('N xline soundings z_final =', len(self.xline['z_final']), 'with first ten =', self.xline['z_final'][0:10])

	# print('\n\n ******** MASKING REF GRID PRIOR TO DZ CALC *************')

	# get all nodes in masked final reference grid in shape, set nans to inf for interpolating xline soundings
	e_ref = self.ref['e_grid'].flatten()  # use all easting and northing (not nan)
	n_ref = self.ref['n_grid'].flatten()
	z_ref = np.multiply(self.ref['z_grid'], self.ref['final_mask']).flatten()  # mask final ref z_grid
	print('e_final, n_final, z_final have shape', np.shape(e_ref), np.shape(n_ref), np.shape(z_ref))

	if self.xline:
		print('number of INFs in e_final, n_final, z_final, e_xline, n_xline =',
			  [np.sum(np.isinf(thing)) for thing in [e_ref, n_ref, z_ref, self.xline['e'], self.xline['n']]])
	else:
		print('number of INFs in e_final, n_final, z_final =',
			  [np.sum(np.isinf(thing)) for thing in [e_ref, n_ref, z_ref]])
		return

	# linearly interpolate masked reference grid onto xline sounding positions, get mask with NaNs wherever the closest
	# reference grid node is a NaN, apply mask to interpolated xline ref depths such that all xline soundings 'off' the
	# masked ref grid will be nan and excluded from further analysis
	z_ref_interp = griddata((self.ref['e'], self.ref['n']), self.ref['z'], (self.xline['e'], self.xline['n']), method='linear')
	z_ref_interp_mask = griddata((e_ref, n_ref), z_ref, (self.xline['e'], self.xline['n']), method='nearest')
	z_ref_interp_mask[~np.isnan(z_ref_interp_mask)] = 1.0  # set all non-nan values to 1 for masking
	self.xline['z_ref_interp'] = z_ref_interp*z_ref_interp_mask
	self.xline['z_ref_interp_mask'] = z_ref_interp_mask

	print('NUM NANS and INFS in z_ref_interp_mask =',
		  np.sum(np.isnan(self.xline['z_ref_interp'])), np.sum(np.isinf(self.xline['z_ref_interp'])))

	print('NUM XLINE ON FINAL REF SURF: ', np.sum(~np.isnan(self.xline['z_ref_interp'])), '/', np.size(self.xline['z']))
	# print('z_ref_interp looks like', self.xline['z_ref_interp'][0:30])
	# print('xline z_final after flip looks like', self.xline['z_final'][0:30])
	self.xline['num_on_ref'] = np.sum(~np.isnan(self.xline['z_ref_interp']))  # count non-Nan interp values
	update_log(self, 'Found ' + str(self.xline['num_on_ref']) +
			   ' crossline soundings on reference grid (after filtering, if applicable)')

	if self.xline['num_on_ref'] == 0:  # warn user if zero soundings found
		update_log(self, 'WARNING: Verify reference surface UTM zone and update if necessary (0 crossline soundings '
						 'found on reference grid in selected UTM zone ' + self.ref_utm_str + ')', font_color="red")

	# calculate dz for xline soundings with non-NaN interpolated reference grid depths
	# note that xline['z'] is positive down as returned from parser; flip sign for differencing from ref surf
	update_log(self, 'Calculating crossline sounding differences from filtered reference grid')
	self.xline['dz_ref'] = np.subtract(self.xline['z_final'], self.xline['z_ref_interp'])
	# print('xline dz_ref looks like', self.xline['dz_ref'][0:100])

	# store dz as percentage of water depth, with positive dz_ref_wd meaning shoal-bias crossline soundings to retain
	# intuitive plotting appearance, with shallower soundings above deeper soundings
	# e.g., if xline z = -98 and z_ref_interp = -100, then dz_ref = +2; dz_ref_wd should be positive; division of
	# positive bias (up) by reference depth (always negative) yields negative, so must be flipped in sign for plot
	dz_ref_wd = np.array(-1*100*np.divide(np.asarray(self.xline['dz_ref']), np.asarray(self.xline['z_ref_interp'])))
	self.xline['dz_ref_wd'] = dz_ref_wd.tolist()
	print('xline dz_ref_wd looks like', self.xline['dz_ref_wd'][0:100])
	self.ref['z_mean'] = np.nanmean(self.xline['z_ref_interp'])  # mean of ref grid interp values used


def bin_beamwise(self, refresh_plot=False):
	# bin by angle, calc mean and std of sounding differences in that angular bin
	print('starting bin_beamwise')
	self.beam_bin_size = 1  # beam angle bin size (deg)
	self.beam_bin_lim = 75  # max angle (deg)

	self.beam_bin_dz_mean = []  # declare dz mean, std, and sample count
	self.beam_bin_dz_std = []
	self.beam_bin_dz_N = []
	self.beam_bin_dz_wd_mean = []
	self.beam_bin_dz_wd_std = []
	self.beam_bin_dz_wd_zero = []
	self.dz_wd_bin_zero_mean = []  # bin mean value for soundings in this bin for plotting adjustment to zero mean
	self.beam_range = range(-1 * self.beam_bin_lim, self.beam_bin_lim, self.beam_bin_size)

	# if crossline data AND reference surface are available, convert soundings with meaningful reference surface
	# nodes to array for binning; otherwise, continue to refresh plot with empty results
	if self.xline == {}:  # skip if crossline data dict is empty (bin_beamwise was called only to reset stats)
		print('self.xline == {}; bin_beamwise called to reset stats')

	elif 'z_final' in self.xline and 'z' in self.ref:
		filter_xline(self)
		update_log(self, 'Binning soundings by angle')
		# calculate simplified beam angle from acrosstrack distance and depth
		# depth is used here as negative down re WL, consistent w/ %WD results
		# Kongsberg angle convention is right-hand-rule about +X axis (fwd), so port angles are + and stbd are -
		# however, for plotting purposes with conventional X axes, use neg beam angles to port and pos to stbd, per
		# plotting conventions used elsewhere (e.g., Qimera)
		# z_final_pos_down = (-1 * np.asarray(self.xline['z_final'])).tolist()
		# z_sonar_pos_down = (-1 * np.asarray(self.xline['z_sonar'])).tolist()

		# calculate nominal beam angle referenced from a horizontal plane at the arrays (sonar vertical height)
		# FUTURE: adjust y to sonar ref rather than raw ref (sonar in .all, mapping origin in .kmall) for more accurate
		# beam angle calcs; this method will suffice for .kmall as long as the athwartship offset from sonar to origin
		# is small compared to y and z
		# self.xline['beam_angle'] = np.rad2deg(np.arctan2(self.xline['y'], z_final_pos_down)).tolist()
		# self.xline['beam_angle'] = np.rad2deg(np.arctan2(self.xline['y'], z_sonar_pos_down)).tolist()

		# print('size of beam_angle is now', len(self.xline['beam_angle']))
		# print('first 30 beam angles are', self.xline['beam_angle'][0:30])
		# self.xline['beam_angle'] = (-1*np.rad2deg(np.arctan2(self.xline['y'], self.xline['z_re_wl']))).tolist()

		# print('found beam_angle in self.xline and z in self.ref')
		beam_array = np.asarray(self.xline['beam_angle'])
		dz_array = np.asarray(self.xline['dz_ref'])
		dz_wd_array = np.asarray(self.xline['dz_ref_wd'])
		dz_wd_zero_mean_array = np.zeros_like(dz_wd_array)  # adjustments for plotting zero mean

		filter_idx = self.xline['filter_idx']
		# print('filter_idx has size', np.size(filter_idx))

		min_bin_count = 0  # minimum number of soundings per bin; zero if not selected by user

		if self.bin_count_gb.isChecked():
			try:
				min_bin_count = float(self.min_bin_count_tb.text())

			except:
				min_bin_count = 0

		print('prior to binning, set min_bin_count = ', min_bin_count)

		for b in self.beam_range:  # loop through all beam bins, calc mean and std for dz results within each bin
			beam_idx = (beam_array >= b) & (beam_array < b + self.beam_bin_size)  # find indices of angles in this bin

			# print('for beam b, beam_idx has size', np.size(beam_idx))
			idx = np.logical_and(filter_idx, beam_idx)  # filtered soundings in this bin

			# print('Found', str(np.sum(beam_idx)), str(np.sum(idx)),
			# 	  '(unfiltered / filtered) soundings between', str(b), 'and', str(b + self.beam_bin_size), 'deg')
			# print('Found', str(np.sum(idx)), 'soundings between', str(b), 'and', str(b + self.beam_bin_size), 'deg')

			self.beam_bin_dz_N.append(np.sum(idx))

			# if np.sum(idx) > 0:  # calc only if at least one sounding on ref surf within this bin
			if np.sum(idx) > min_bin_count:  # calc only if N soundings on ref surf in this bin

				# THIS CAN BE UPDATED WITH A MINIMUM BIN COUNT SETTING
				# no filter_idx applied
				# self.beam_bin_dz_mean.append(np.nanmean(dz_array[idx]))
				# self.beam_bin_dz_std.append(np.nanstd(dz_array[idx]))
				# self.beam_bin_dz_wd_mean.append(np.nanmean(dz_wd_array[idx]))  # simple mean of WD percentages
				# self.beam_bin_dz_wd_std.append(np.nanstd(dz_wd_array[idx]))

				# apply filter idx
				self.beam_bin_dz_mean.append(np.nanmean(dz_array[idx]))
				self.beam_bin_dz_std.append(np.nanstd(dz_array[idx]))
				self.beam_bin_dz_wd_mean.append(np.nanmean(dz_wd_array[idx]))  # simple mean of WD percentages
				self.beam_bin_dz_wd_std.append(np.nanstd(dz_wd_array[idx]))
				self.beam_bin_dz_wd_zero.append(0)  # store zero for bins with N>0 soundings for plotting zero mean
				dz_wd_zero_mean_array[idx] = self.beam_bin_dz_wd_mean[-1]  # store current bin mean for these soundings

				# if b >= float(self.)

			else:  # store NaN if no dz results are available for this bin
				self.beam_bin_dz_mean.append(np.nan)
				self.beam_bin_dz_std.append(np.nan)
				self.beam_bin_dz_wd_mean.append(np.nan)  # this is the simple mean of WD percentages
				self.beam_bin_dz_wd_std.append(np.nan)
				self.beam_bin_dz_wd_zero.append(np.nan)  # store nan for bins with N=0 soundings for plotting zero mean

		self.dz_wd_bin_zero_mean = dz_wd_zero_mean_array.tolist()  # store adjustments to zero mean for plotting

	else:
		print('Error in bin_beamwise')


def plot_accuracy(self, set_active_tab=False):  # plot the accuracy results
	# set point size; slider is on [1-11] for small # of discrete steps
	# print('in plot_accuracy with xline keys=', self.xline.keys())

	if not all([k in self.xline.keys() for k in ['beam_angle', 'dz_ref_wd']]):
		update_log(self, 'Beam angle and depth difference not found; crossline results will not be plotted')
		return

	beam_bin_centers = np.asarray([b + self.beam_bin_size / 2 for b in self.beam_range])  # bin centers for plot
	beam_bin_dz_wd_std = np.asarray(self.beam_bin_dz_wd_std)  # std as a percent of wd across all bins
	self.N_plotted = 0

	# print('before calling decimate_data, the lens of beam_angle and dz_ref_wd = ', len(self.xline['beam_angle']),
	# 	  len(self.xline['dz_ref_wd']))

	nan_idx = np.isnan(self.xline['dz_ref_wd'])  # index of nans for all sounding dz values
	# print('got nan_idx with sum of non-nans=', np.sum(~nan_idx))
	# real_beam_angle = np.asarray(self.xline['beam_angle'])[~nan_idx].tolist()
	# real_dz_ref_wd = np.asarray(self.xline['dz_ref_wd'])[~nan_idx].tolist()
	# real_dz_ref = np.asarray(self.xline['dz_ref'])[~nan_idx].tolist()

	# apply crossline filter to data
	print('applying crossline filters')
	real_filt_idx = np.logical_and(~nan_idx, self.xline['filter_idx'])  # indices of real, filtered soundings
	real_beam_angle = np.asarray(self.xline['beam_angle'])[real_filt_idx].tolist()  # real, filtered beam angles
	real_dz_ref_wd = np.asarray(self.xline['dz_ref_wd'])[real_filt_idx].tolist()  # real, filtered dz results as %WD
	real_dz_ref = np.asarray(self.xline['dz_ref'])[real_filt_idx].tolist()  # real, filtered dz results in meters

	# calculate mean bias of filtered results across whole swath
	# offsets to apply to each real, filtered sounding to plot with zero mean
	print('size of real_filt_idx is', np.size(real_filt_idx))
	print('len of self.dz_wd_bin_zero_mean is', len(self.dz_wd_bin_zero_mean))
	real_dz_wd_bin_zero_mean = np.asarray(self.dz_wd_bin_zero_mean)[real_filt_idx].tolist()  # real, filtered dz results as %WD when forcing mean to zero
	print('got real_dz_wd_bin_zero_mean =', real_dz_wd_bin_zero_mean)
	print('len of real_dz_wd_bin_zero_mean is', len(real_dz_wd_bin_zero_mean))
	### THIS WORKS FOR CALCULATING MEAN ACROSS ALL BINS
	real_dz_wd_bin_mean_mean = np.mean(real_dz_wd_bin_zero_mean)  # mean of filtered bin biases
	print('got initial value for real_dz_wd_bin_mean_mean = ', real_dz_wd_bin_mean_mean)

	# calculate mean bias of filtered results within user defined swath portion
	# print('getting real_dz_wd_bin_mean as array of')
	# real_filt_user_mean_angle_idx = np.logical_and(real_filt_idx, user_mean_angle_idx)
	# real_dz_wd_bin_user_mean = np.asarray(self.dz_wd_bin_zero_mean)[user_mean_angle_idx].tolist()  # real, filtered dz results as %WD with mean from user-defined swath portion

	# if self.flatten_mean_gb.isChecked():  # calculate mean within user defined swath limits, if checked
	# idx of angles that fall within user defined swath portion to use for mean bias calcs, if desired / checked
	if self.flatten_mean_gb.isChecked():
		print('*** flatten_mean_gb IS CHECKED****')

		if not self.set_zero_mean_chk.isChecked():
			print('***************** set_zero_mean_chk is NOT CHECKED')
			print('\n\n***getting indices of soundings within user defined beam angles')
			user_mean_angle_idx = np.logical_and(np.greater_equal(self.xline['beam_angle'], -1*float(self.mean_bias_angle_lim_tb.text())),
												 np.less_equal(self.xline['beam_angle'], float(self.mean_bias_angle_lim_tb.text())))
			print('got user_mean_angle_idx!')
			real_filt_user_mean_angle_idx = np.logical_and(real_filt_idx, user_mean_angle_idx)
			print('got real_filt_user_mean_angle_idx!')
			real_dz_wd_bin_user_mean = np.asarray(self.dz_wd_bin_zero_mean)[real_filt_user_mean_angle_idx].tolist()  # real, filtered dz results as %WD with mean from user-defined swath portion
			print('got real_dz_wd_bin_user_mean!')
			real_dz_wd_bin_mean_mean = np.mean(real_dz_wd_bin_user_mean)  # store mean within user selected swath limits
			print('survived user defined swath portion mean calc...')

	print('*******got real_dz_wd_bin_mean_mean = ', real_dz_wd_bin_mean_mean)

	# print('got real_beam_angle with len=', len(real_beam_angle), ' and = ', real_beam_angle)
	# print('got real_dz_ref_wd with len=', len(real_dz_ref_wd), ' and = ', real_dz_ref_wd)
	# print('got real_dz_ref with len=', len(real_dz_ref), ' and = ', real_dz_ref)
	# print('got real_dz_wd_bin_mean with len=', len(real_dz_wd_bin_mean), ' and = ', real_dz_wd_bin_mean)
	# print('got real_dz_wd_bin_mean_mean = ', real_dz_wd_bin_mean_mean)

	dec_data = decimate_data(self, data_list=[real_beam_angle, real_dz_ref_wd, real_dz_wd_bin_zero_mean])

	# print('back from decimate_data, dz_dec has len=', len(dec_data))
	real_beam_angle_dec = dec_data[0]
	real_dz_ref_wd_dec = dec_data[1]
	real_dz_wd_bin_zero_mean_dec = dec_data[2]

	real_dz_wd_bin_zero_mean_plot = [x - y for x, y in zip(real_dz_ref_wd_dec, real_dz_wd_bin_zero_mean_dec)]  # offsets to real filtered soundings for flat curve forced to zero mean
	real_dz_wd_bin_flat_mean_plot = [x + real_dz_wd_bin_mean_mean for x in real_dz_wd_bin_zero_mean_plot]  # offsets to real filtered soundings for flat curve preserving mean bias

	# print('beam_angle_dec and dz_ref_wd_dec have lens=', len(real_beam_angle_dec), len(real_dz_ref_wd_dec))
	self.N_plotted = len(real_beam_angle_dec)

	# plot standard deviation as %WD versus beam angle
	self.ax1.plot(beam_bin_centers, beam_bin_dz_wd_std, '-', linewidth=self.lwidth, color='b')  # bin mean + st. dev.

	# plot mean and std trend lines over decimated raw soundings (as %WD)
	if self.flatten_mean_gb.isChecked():  # flatten the mean bias curve

		print('\n\n************* FLATTEN MEAN GROUPBBOX IS CHECKED***************\n\n')

		if self.set_zero_mean_chk.isChecked():  # plot adjustment to zero mean (remove all mean biases)

			print('\n\n################# ZERO MEAN IS CHECKED ######################\n\n')
			# plot the raw differences, mean, and +/- 1 sigma as %wd versus beam angle, forcing the mean bias to zero
			self.ax2.scatter(real_beam_angle_dec, real_dz_wd_bin_zero_mean_plot,
							 marker='o', color='0.75', s=self.pt_size, alpha=self.pt_alpha)

			self.ax2.plot(beam_bin_centers, np.asarray(self.beam_bin_dz_wd_zero), '-',
						  linewidth=self.lwidth, color='r')  # beamwise bin mean diff

			self.ax2.plot(beam_bin_centers, self.beam_bin_dz_wd_std, '-',
						  linewidth=self.lwidth, color='b')  # beamwise bin mean + st. dev.
			self.ax2.plot(beam_bin_centers, np.multiply(-1, self.beam_bin_dz_wd_std), '-',
						  linewidth=self.lwidth, color='b')  # beamwise bin mean - st. dev.

			print('survived zero mean steps...')

		else:  # flatten curve but preserve the total mean across all bins (e.g., an across-the-board waterline error)
			# plot the raw differences, mean, and +/- 1 sigma as %wd versus beam angle, keeping the mean bias

			print('**** ZERO mean is NOT checked... keeping mean from user-defined portion ')
			self.ax2.scatter(real_beam_angle_dec, real_dz_wd_bin_flat_mean_plot,
							 marker='o', color='0.75', s=self.pt_size, alpha=self.pt_alpha)

			self.ax2.plot(beam_bin_centers, np.add(np.asarray(self.beam_bin_dz_wd_zero), real_dz_wd_bin_mean_mean), '-',
						  linewidth=self.lwidth, color='r')  # beamwise bin mean diff

			self.ax2.plot(beam_bin_centers, np.add(real_dz_wd_bin_mean_mean, self.beam_bin_dz_wd_std), '-',
						  linewidth=self.lwidth, color='b')  # beamwise bin mean + st. dev.
			self.ax2.plot(beam_bin_centers, np.subtract(real_dz_wd_bin_mean_mean, self.beam_bin_dz_wd_std), '-',
						  linewidth=self.lwidth, color='b')  # beamwise bin mean - st. dev.

			print('survived flattening without zero mean...')

	else:  # plot the raw differences with no flattening or adjustment of mean biases

		print('\n\n----------> FLATTEN MEAN IS NOT CHECKED\n\n')

		# plot the raw differences, mean, and +/- 1 sigma as %wd versus beam angle
		self.ax2.scatter(real_beam_angle_dec, real_dz_ref_wd_dec,
						 marker='o', color='0.75', s=self.pt_size, alpha=self.pt_alpha)

		# raw differences from reference grid, small gray points
		self.ax2.plot(beam_bin_centers, self.beam_bin_dz_wd_mean, '-',
					  linewidth=self.lwidth, color='r')  # beamwise bin mean diff
		self.ax2.plot(beam_bin_centers, np.add(self.beam_bin_dz_wd_mean, self.beam_bin_dz_wd_std), '-',
					  linewidth=self.lwidth, color='b')  # beamwise bin mean + st. dev.
		self.ax2.plot(beam_bin_centers, np.subtract(self.beam_bin_dz_wd_mean, self.beam_bin_dz_wd_std), '-',
					  linewidth=self.lwidth, color='b')  # beamwise bin mean - st. dev.

		print('survived normal plotting!')

	# update system info with xline detections
	# update_system_info(self, self.det, force_update=True, fname_str_replace='_trimmed')

	if set_active_tab:
		self.plot_tabs.setCurrentIndex(0)  # show accuracy results tab

def decimate_data(self, data_list=[]):
	# decimate data to achieve point count limit or apply user input (if selected)
	# optional input: list of data to decimate (each item is a list with same length)
	# otherwise, return indices to apply for decimation of
	# self.n_points = len(self.xline['dz_ref_wd'])

	if data_list:
		self.n_points = len(data_list[0])
		data_list_out = data_list  # data_list_out will be decimated later if necessary
		# print('in decimate_data, got len(data_list[0]) = ', self.n_points)

	else:
		# print('in decimate_data, no data_list provided')
		self.n_points = len(self.xline['dz_ref_wd'])
		idx_out = [int(i) for i in range(self.n_points)]  # idx_out will be reduced later if necessary
		# print('got n_points = ', self.n_points)

	# print(1)
	self.n_points_max = self.n_points_max_default

	if self.pt_count_gb.isChecked() and self.max_count_tb.text():  # override default only if explicitly set by user
		print('setting n_points_max = max_count_tb.text')
		self.n_points_max = float(self.max_count_tb.text())

	# print(2)
	# default dec fac to meet n_points_max, regardless of whether user has checked box for plot point limits
	if self.n_points_max == 0:
		update_log(self, 'WARNING: Max plotting sounding count set equal to zero', font_color='red')
		self.dec_fac_default = np.inf
		# print(3)
	else:
		# print('setting dec_fac_default!')
		self.dec_fac_default = float(self.n_points / self.n_points_max)

		# print('self.dec_fac_default =', self.dec_fac_default)

	# print(4)
	if self.dec_fac_default > 1 and not self.pt_count_gb.isChecked():  # warn user if large count may slow down plot
		update_log(self, 'Large filtered sounding count (' + str(self.n_points) + ') may slow down plotting')

	# print(5)

	# get user dec fac as product of whether check box is checked (default 1)
	self.dec_fac_user = max(self.pt_count_gb.isChecked() * float(self.dec_fac_tb.text()), 1)
	self.dec_fac = max(self.dec_fac_default, self.dec_fac_user)

	if self.dec_fac_default > self.dec_fac_user:  # warn user if default max limit was reached
		update_log(self, 'Decimating crossline data (for plotting only) by factor of ' + "%.1f" % self.dec_fac +
				   ' to keep plotted point count under ' + "%.0f" % self.n_points_max +
				   '; accuracy results include all soundings, as filtered according to user input')

	elif self.pt_count_gb.isChecked() and self.dec_fac_user > self.dec_fac_default and self.dec_fac_user > 1:
		# otherwise, warn user if their manual dec fac was applied because it's more aggressive than max count
		update_log(self, 'Decimating crossline data (for plotting only) by factor of ' + "%.1f" % self.dec_fac +
				   ' per user input; accuracy results are include all soundings, as filtered according to user input')

	# print('before decimation, c_all=', c_all)

	if self.dec_fac > 1:
		print('dec fac > 1, trying to determine idx_dec')
		# print('dec_fac > 1 --> attempting interp1d')
		# n_points = len(self.xline['dz_ref_wd'])
		idx_all = np.arange(self.n_points)  # integer indices of all filtered data
		idx_dec = np.arange(0, self.n_points - 1, self.dec_fac)  # desired decimated indices, may be non-integer

		# print(6)
		# interpolate indices of colors, not color values directly
		f_dec = interp1d(idx_all, idx_all, kind='nearest')  # nearest neighbor interpolation function of all indices
		idx_out = [int(i) for i in f_dec(idx_dec)]  # list of decimated integer indices

		# print(7)

		# print(8)
		if data_list:
			# print('yes, data_list exists')
			for i, d in enumerate(data_list):
				# print('enumerating i=', i, 'applying idx_out to data_list')
				# print('d = ', d)
				# print('idx_out =', idx_out)
				data_list_out[i] = [d[j] for j in idx_out]
				# print('survived')

		# else:  # if no
		# 	data_list_out = data_list

	# print(9)

	if data_list:  # return list of decimated data if data were provided
		print('returning data_list_out from decimate_data')
		return data_list_out

	else:  # return indices for decimation if data were not provided
		print('returning idx_new from decimate_data')
		return idx_out

	# self.n_points = len(y_all)
	# print('self n_points = ', self.n_points)


def sort_xline_track(self, new_track):
	# pull ship track from dict of parsed crossline track information (different data from .all and .kmall files) and
	# convert to current UTM zone
	# .all files: use active position sensor, full position time series
	# .kmall files: use ping position (assumes active position sensor), ping time only

	track_out = {}  # simplified trackline dict with lat, lon, easting, northing, utm_zone

	refProj = pyproj.Proj(proj='utm', zone=self.ref['utm_zone'], ellps='WGS84')  # define output projection

	for f in range(len(new_track)):
		lat, lon = [], []
		fname = new_track[f]['fname']
		# track_out[fname] = {}

		if '.all' in new_track[f]['fname']:
			temp = {0: dict(new_track[f])}  # reformat dict with key=0 for sort_active_pos_system
			dt_pos, lat, lon, sys_num = sort_active_pos_system(temp, print_updates=True)  # use only active pos

		elif '.kmall' in new_track[f]['fname']:
			# print('new_track[f].keys() = ', new_track[f].keys())
			pingInfo = new_track[f]['RTP']  # temp method using pingInfo lat/lon stored in RTP
			headerInfo = new_track[f]['HDR']
			# print('pingInfo has len =', len(pingInfo))
			# print('headerInfo has len =', len(headerInfo))

			lat = [pingInfo[p]['latitude_deg'] for p in range(len(pingInfo))]
			lon = [pingInfo[p]['longitude_deg'] for p in range(len(pingInfo))]
			dt_pos = [headerInfo[p]['dgdatetime'] for p in range(len(headerInfo))]

			# print('pingInfo[0].keys() = ', pingInfo[0].keys())
			# print('headerInfo[0].keys() = ', headerInfo[0].keys())

			# dt_pos = [pingInfo[p]['dgdatetime'] for p in range(len(pingInfo))]

		else:
			print('in sort_xline_track, not sorting track for f =', f, '-->', new_track[f]['fname'])
			continue

		print('first couple lat, lon are', lat[0:10], lon[0:10])
		temp_out = {}
		temp_out['lat'] = lat
		temp_out['lon'] = lon
		temp_out['datetime'] = dt_pos
		temp_out['e'], temp_out['n'] = refProj(lon, lat)
		temp_out['utm_zone'] = self.ref['utm_zone']

		track_out[fname] = temp_out

		print('for fname =', fname, 'the first 10 track e, n =',
			  track_out[fname]['e'][0:10], track_out[fname]['n'][0:10])

	return track_out


def refresh_plot(self, refresh_list=['ref', 'acc', 'tide'], sender=None, set_active_tab=None):
	# update swath plot with new data and options
	print('refresh_plot called from sender=', sender, ', refresh_list=', refresh_list, ', active_tab=', set_active_tab)
	print('calling clear_plot from refresh_plot')
	clear_plot(self, refresh_list)
	self.pt_size = np.square(float(self.pt_size_cbox.currentText()))  # swath plot point size
	self.pt_size_cov = np.square(float(self.pt_size_cov_cbox.currentText()))  # coverage plot point size
	self.pt_alpha = np.divide(float(self.pt_alpha_cbox.currentText()), 100)

	try:
		update_axes(self)
		add_grid_lines(self)  # add grid lines

		if 'ref' in refresh_list:
			update_plot_limits(self)
			print('1')
			plot_ref_surf(self)
			print('2')
			self.surf_canvas.draw()
			print('3')
			self.surf_final_canvas.draw()
			print('4')
			plt.show()
			print('finished refreshing ref in refresh_list')

		if 'acc' in refresh_list:
			print('a')
			update_plot_limits(self)
			print('b')
			plot_accuracy(self)
			print('c)')
			self.swath_canvas.draw()
			print('d')
			plt.show()
			print('finished refreshing acc in refresh_list')

		if 'tide' in refresh_list:
			# plot_tide(self)
			plot_tide2(self)
			self.tide_canvas.draw()
			plt.show()
			print('finished refreshing tide in refresh_list')


		print('survived calling plot steps from refresh_plot')

	except:
		update_log(self, 'Error in refreshing plot.') #Please load crossline files and calculate accuracy.')


	if set_active_tab != None:  # in refresh_plot, set_active_tab = tab index (boolean elsewhere for specific plots)
		self.plot_tabs.setCurrentIndex(set_active_tab)  # show ref surf tab

	update_buttons(self)


# def update_system_info(self):
# 	# update model, serial number, ship, cruise based on availability in parsed data and/or custom fields
# 	if self.custom_info_gb.isChecked():  # use custom info if checked
# 		self.ship_name = self.ship_tb.text()
# 		self.cruise_name = self.cruise_tb.text()
# 		self.model_name = self.model_cbox.currentText()
# 	else:  # get info from detections if available
# 		try:  # try to grab ship name from filenames (conventional file naming)
# 			self.ship_name = self.det['fname'][0]  # try getting ship name from first detection filename
# 			#                self.ship_name = self.det['filenames'][0] # try getting ship name from detection dict filenames
# 			self.ship_name = self.ship_name[
# 							 self.ship_name.rfind('_') + 1:-4]  # assumes filename ends in _SHIPNAME.all
# 		except:
# 			self.ship_name = 'SHIP NAME N/A'  # if ship name not available in filename
#
# 		try:  # try to grab cruise name from Survey ID field in
# 			self.cruise_name = self.data[0]['IP_start'][0]['SID'].upper()  # update cruise ID with Survey ID
# 		except:
# 			self.cruise_name = 'CRUISE N/A'
#
# 		try:
# 			self.model_name = 'EM ' + str(self.data[0]['IP_start'][0]['MODEL'])
# 		except:
# 			self.model_name = 'MODEL N/A'


def update_axes(self):
	# udpate axes for swath and tide plots; ref surf axes are handled in plot_ref_surf
	# update top subplot axes (std. dev. as %WD)
	# update_system_info(self)
	update_system_info(self, self.xline, force_update=False, fname_str_replace='_trimmed')
	update_plot_limits(self)

	# set x axis limits and ticks for both swath subplots
	plt.setp((self.ax1, self.ax2),
			 xticks=np.arange(-1 * self.x_max, self.x_max + self.x_spacing, self.x_spacing),
			 xlim=(-1 * self.x_max, self.x_max))

	# set y axis limits for both swath subplots
	self.ax1.set_ylim(0, self.y_max_std)  # set y axis for std (0 to max, top plot)
	self.ax2.set_ylim(-1 * self.y_max_bias, self.y_max_bias)  # set y axis for total bias+std (bottom plot)

	title_str = 'Swath Accuracy vs. Beam Angle'
	title_str_surf = 'Reference Surface'
	title_str_tide = 'Tide Applied to Accuracy Crosslines'

	# update plot title with default or custom combination of system info fields
	if self.custom_info_gb.isChecked():  # include custom system info that is checked on
		sys_info_list = [['', self.model_name][self.show_model_chk.isChecked()],
						 ['', self.ship_name][self.show_ship_chk.isChecked()],
						 ['', self.cruise_name][self.show_cruise_chk.isChecked()]]
		print('got sys_info_list = ', sys_info_list)
		sys_info_str = ' - '.join([str for str in sys_info_list if str is not ''])

	else:  # otherwise, default to all system info in the title
		sys_info_str = ' - '.join([self.model_name, self.ship_name, self.cruise_name])

	# get set of modes in these crosslines
	if self.xline:  # get set of modes in these crosslines and add to title string
		try:
			# default set of modes based on all available in crossline files
			# modes = [' / '.join([self.xline['ping_mode'][i],
			# 					 self.xline['swath_mode'][i],
			# 					 self.xline['pulse_form'][i]]) for i in range(len(self.xline['ping_mode']))]

			# set of modes based on filters (e.g., if filtered for mode(s)); np.where returns tuple, use [0] as list
			print('trying to get mode set: np.where(self.xline[filter_idx]) =', np.where(self.xline['filter_idx'])[0])
			modes = [' / '.join([self.xline['ping_mode'][i],
								 self.xline['swath_mode'][i],
								 self.xline['pulse_form'][i]]) for i in np.where(self.xline['filter_idx'])[0]]

			modes_str = ' + '.join(list(set(modes)))

		except:
			modes_str = 'Modes N/A'
	else:
		modes_str = 'Modes N/A'

	if self.ref:
		fname_ref = self.ref['fname']
	else:
		fname_ref = 'Reference file N/A'

	if self.tide:
		fname_tide = self.tide['fname']
	else:
		fname_tide = 'Tide file N/A'

	self.title_str = '\n'.join([title_str, sys_info_str, modes_str])
	self.title_str_ref = '\n'.join([title_str_surf, sys_info_str, fname_ref])
	self.title_str_tide = '\n'.join([title_str_tide, sys_info_str, fname_tide])

	# set axis labels
	self.ax1.set(xlabel='Beam Angle (deg, pos. stbd.)', ylabel='Depth Bias Std. Dev (% Water Depth)')
	self.ax2.set(xlabel='Beam Angle (deg, pos. stbd.)', ylabel='Depth Bias (% Water Depth)')
	self.tide_ax.set(xlabel='Time', ylabel='Tide Ampitude (m from tide file datum, positive up)')

	# set super titles
	self.swath_figure.suptitle(self.title_str)
	self.surf_figure.suptitle(self.title_str_ref)
	self.surf_final_figure.suptitle(self.title_str_ref)
	self.tide_figure.suptitle(self.title_str_tide)

	# add processing text boxes
	add_ref_proc_text(self)
	add_xline_proc_text(self)


	try:
		plt.show()  # need show() after update; failed until matplotlib.use('qt5agg') added at start

	except:
		print('in update_axes, failed plt.show()')

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
		self.axis_margin_custom = float(self.axis_margin_tb.text())

		# assign to current plot limits
		self.x_max = self.x_max_custom
		self.x_spacing = self.x_spacing_custom
		self.y_max_std = self.y_max_std_custom
		self.y_max_bias = self.y_max_bias_custom
		self.axis_margin = self.axis_margin_custom

	else:  # revert to default limits from the data if unchecked, but keep the custom numbers in text boxes
		# self.max_gb.setEnabled(False)
		self.x_max = self.x_max_default
		self.x_spacing = self.x_spacing_default
		self.y_max_std = self.y_max_std_default
		self.y_max_bias = self.y_max_bias_default
		self.axis_margin = self.axis_margin_default

		print('axis margin is now ', self.axis_margin)

		# set text boxes to latest custom values for easier toggling between custom/default limits
		self.max_beam_angle_tb.setText(str(float(self.x_max_custom)))
		self.angle_spacing_tb.setText(str(float(self.x_spacing_custom)))
		self.max_bias_tb.setText(str(float(self.y_max_bias_custom)))
		self.max_std_tb.setText(str(float(self.y_max_std_custom)))
		self.axis_margin_tb.setText(str(float(self.axis_margin_custom)))


def add_grid_lines(self):
	for ax in [self.ax1, self.ax2, self.surf_ax1, self.surf_ax2, self.surf_ax3, self.surf_ax4,
			   self.surf_ax5, self.tide_ax]:
		if self.grid_lines_toggle_chk.isChecked():
			ax.grid()
			ax.minorticks_on()
			ax.grid(which='minor', linestyle='-', linewidth='0.5', color='black')
			ax.grid(which='major', linestyle='-', linewidth='1.0', color='black')

		else:
			ax.grid(False)
			ax.minorticks_off()


def add_xline_proc_text(self):
	# add text for depth ref and filters applied
	proc_str = 'Crossline processing parameters'
	proc_str += '\nSounding reference: ' + self.ref_cbox.currentText()
	proc_str += '\nReference surface: ' + (self.ref['fname'].split('/')[-1] if self.ref else 'N/A')
	proc_str += '\nUTM Zone: ' + self.ref_proj_cbox.currentText()
	proc_str += '\nNum. crosslines: ' + (str(len(list(set(self.xline['fname'])))) if self.xline else '0') + ' files'
	proc_str += '\nNum. soundings: ' + (str(len(self.xline['z'])) + ' (' + str(self.xline['num_on_ref']) +
										' on filtered ref. surf.)' if self.xline else '0')
	proc_str += '\nNum. plotted: ' + (str(self.N_plotted) + ' (filtered soundings)' if self.xline else '0')
	proc_str += '\nTide applied: ' + (self.tide['fname'] if self.tide and self.tide_applied else 'None')
	# make dict of text to include based on user input
	depth_fil_xline = ['None', self.min_depth_xline_tb.text() + ' to ' + self.max_depth_xline_tb.text() + ' m']
	dz_fil = ['None', self.max_dz_tb.text() + ' m or ' + self.max_dz_wd_tb.text() + ' %WD']
	# dz_fil = ['None', self.max_dz_wd_tb.text() + ' %WD']
	angle_fil = ['None', self.min_angle_xline_tb.text() + ' to ' + self.max_angle_xline_tb.text() + '\u00b0']
	bs_fil = ['None', ('+' if float(self.min_bs_xline_tb.text()) > 0 else '') + self.min_bs_xline_tb.text() + ' to ' +
			  ('+' if float(self.max_bs_xline_tb.text()) > 0 else '') + self.max_bs_xline_tb.text() + ' dB']

	fil_dict = {'Angle filter: ': angle_fil[self.angle_xline_gb.isChecked()],
				'Depth filter (crossline): ': depth_fil_xline[self.depth_xline_gb.isChecked()],
				'Backscatter filter: ': bs_fil[self.bs_xline_gb.isChecked()],
				'Max. diff.:': dz_fil[self.dz_gb.isChecked()]}

	for fil in fil_dict.keys():
		proc_str += '\n' + fil + fil_dict[fil]

	if self.show_acc_proc_text_chk.isChecked():
		self.ax1.text(0.02, 0.98, proc_str,
					  ha='left', va='top', fontsize=6, transform=self.ax1.transAxes,
					  bbox=dict(facecolor='white', edgecolor=None, linewidth=0, alpha=0.8))


def add_ref_proc_text(self):
	print('made it to add_ref_proc_text')
	# add text for depth ref and filters applied
	proc_str = 'Reference surface processing parameters'
	# proc_str = 'Vertical reference: ' + self.ref_cbox.currentText()
	proc_str += '\nReference surface: ' + (self.ref['fname'].split('/')[-1] if self.ref else 'N/A')
	proc_str += '\nUTM Zone: ' + self.ref_proj_cbox.currentText()

	# make dict of text to include based on user input
	# depth_fil_xline = ['None', self.min_depth_xline_tb.text() + ' to ' + self.max_depth_xline_tb.text() + ' m']
	depth_fil_ref = ['None', self.min_depth_ref_tb.text() + ' to ' + self.max_depth_ref_tb.text() + ' m']
	slope_win = ['None', self.slope_win_cbox.currentText() + ' cells']
	slope_fil = ['None', '0 to ' + self.max_slope_tb.text() + ' deg']

	fil_dict = {'Depth filter (reference): ': depth_fil_ref[self.depth_ref_gb.isChecked()],
				'Slope smoothing window: ': slope_win[self.slope_gb.isChecked()],
				'Slope filter (reference): ': slope_fil[self.slope_gb.isChecked()]}

	print('made it to end of fil_dict')

	for fil in fil_dict.keys():
		proc_str += '\n' + fil + fil_dict[fil]

	if self.show_ref_proc_text_chk.isChecked():
		self.surf_ax1.text(0.02, 0.98, proc_str,ha='left', va='top', fontsize=6, transform=self.surf_ax1.transAxes,
						   bbox=dict(facecolor='white', edgecolor=None, linewidth=0, alpha=0.8))


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


def clear_plot(self, refresh_list=['ref', 'acc', 'tide']):
	# clear plots in refresh_list
	print('in clear_plot with refresh_list=', refresh_list)
	if 'acc' in refresh_list:
		for ax in [self.ax1, self.ax2]:
			ax.clear()

		self.swath_canvas.draw()

	if 'ref' in refresh_list:
		for ax in [self.surf_ax1, self.surf_ax2, self.surf_ax3, self.surf_ax4, self.surf_ax5]:
			ax.clear()

		self.surf_canvas.draw()

	if 'tide' in refresh_list:
		self.tide_ax.clear()
		self.tide_canvas.draw()


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
