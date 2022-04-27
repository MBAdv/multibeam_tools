"""Functions for swath coverage plotting in NOAA / MAC echosounder assessment tools"""

try:
	from PySide2 import QtWidgets, QtGui
	from PySide2.QtGui import QDoubleValidator
	from PySide2.QtCore import Qt, QSize
except ImportError as e:
	print(e)
	from PyQt5 import QtWidgets, QtGui
	from PyQt5.QtGui import QDoubleValidator
	from PyQt5.QtCore import Qt, QSize

import multibeam_tools.libs.parseEM
from multibeam_tools.libs.file_fun import *
from multibeam_tools.libs.swath_fun import *

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib import colors
from matplotlib import colorbar
from matplotlib import patches
from mpl_toolkits.axes_grid1.inset_locator import inset_axes

from scipy.interpolate import interp1d
from time import process_time
import pickle


def setup(self):
	# initialize other necessities
	# self.print_updates = True
	self.print_updates = False
	self.det = {}  # detection dict (new data)
	self.det_archive = {}  # detection dict (archive data)
	self.spec = {}  # dict of theoretical coverage specs
	self.filenames = ['']  # initial file list
	self.input_dir = ''  # initial input dir
	self.output_dir = os.getcwd()  # save output in cwd unless otherwise selected
	self.clim_last_user = {'depth': [0, 1000], 'backscatter': [-50, -10]}
	self.last_cmode = 'depth'
	self.cbar_ax1 = None  # initial colorbar for swath plot
	self.cbar_ax2 = None  # initial colorbar for data rate plot
	self.cbar_ax3 = None  # initial colorbar for ping interval plot
	self.cbar_ax4 = None  # initial colorbar for parameter tracking plot
	self.legendbase = None  # initial legend
	self.cbar_font_size = 8  # colorbar/legend label size
	self.cbar_title_font_size = 8  # colorbar/legend title size
	self.cbar_loc = 1  # set upper right as default colorbar/legend location
	self.n_points_max_default = 50000  # default maximum number of points to plot in order to keep reasonable speed
	self.n_points_max = 50000
	# self.n_points_plotted = 0
	# self.n_points_plotted_arc = 0
	self.dec_fac_default = 1  # default decimation factor for point count
	self.dec_fac = 1
	self.rtp_angle_buffer_default = 0  # default runtime angle buffer
	self.rtp_angle_buffer = 0  # +/- deg from runtime parameter swath angle limit to filter RX angles
	self.x_max = 0.0
	self.z_max = 0.0
	self.model_list = ['EM 2040', 'EM 302', 'EM 304', 'EM 710', 'EM 712', 'EM 122', 'EM 124']
	self.cmode_list = ['Depth', 'Backscatter', 'Ping Mode', 'Pulse Form', 'Swath Mode', 'Frequency', 'Solid Color']
	self.top_data_list = []
	self.clim_list = ['All data', 'Filtered data', 'Fixed limits']
	self.sis4_tx_z_field = 'S1Z'  # .all IP datagram field name for TX array Z offset (meters +down from origin)
	self.sis4_waterline_field = 'WLZ'  # .all IP datagram field name for waterline Z offset (meters +down from origin
	self.depth_ref_list = ['Waterline', 'Origin', 'TX Array', 'Raw Data']
	self.subplot_adjust_top = 0.9  # scale of subplots with super title on figure
	self.title_str = ''
	self.std_fig_width_inches = 12
	self.std_fig_height_inches = 12
	self.c_all_data_rate = []
	self.c_all_data_rate_arc = []
	self.ship_name = 'R/V Unsinkable II'
	self.model_updated = False
	self.ship_name_updated = False
	self.cruise_name_updated = False
	self.sn_updated = False
	self.ping_int_min = 0.25  # default pint interval xmin (second swaths in dual-swath are present but won't appear)
	self.ping_int_max = 60  # default ping interval xmax (first pings after long gaps are present but won't appear)
	self.skm_time = {}
	self.sounding_fname = ''
	self.sounding_fname_default = 'hover over sounding for filename'
	self.z_all = []
	self.y_all = []
	self.trend_bin_centers = []
	self.trend_bin_means = []
	self.trend_bin_centers_arc = []
	self.trend_bin_means_arc = []
	self.param_list = ['datetime', 'ping_mode', 'pulse_form', 'swath_mode',
					   'max_port_deg', 'max_stbd_deg', 'max_port_m', 'max_stbd_m']
	self.param_state = dict((k,[]) for k in self.param_list)
	self.param_changes = dict((k,[]) for k in self.param_list)

def init_all_axes(self):
	init_swath_ax(self)
	init_data_ax(self)
	init_time_ax(self)
	# init_param_ax(self)
	# self.cbar_dict = {'swath': {'cax': self.cbar_ax1, 'ax': self.swath_ax, 'clim': self.clim, 'loc': 1, 'tickloc': 'left'},
	# 				  'data_rate': {'cax': self.cbar_ax2, 'ax': self.data_rate_ax1, 'clim': self.clim, 'loc': 2, 'tickloc': 'right'},
	# 				  'ping_interval': {'cax': self.cbar_ax3, 'ax': self.data_rate_ax2, 'clim': self.clim, 'loc': 1, 'tickloc': 'left'}}

	self.cbar_dict = {'swath': {'cax': self.cbar_ax1, 'ax': self.swath_ax, 'clim': self.clim, 'loc': 1, 'tickloc': 'left'},
					  'ping_interval': {'cax': self.cbar_ax3, 'ax': self.data_rate_ax2, 'clim': self.clim, 'loc': 1, 'tickloc': 'left'}}

	add_grid_lines(self)
	update_axes(self)


def init_swath_ax(self):  # set initial swath parameters
	self.pt_size = np.square(float(self.pt_size_cbox.currentText()))
	self.pt_alpha = np.divide(float(self.pt_alpha_cbox.currentText()), 100)

	self.swath_ax = self.swath_figure.add_subplot(121)
	self.hist_ax = self.swath_figure.add_subplot(212, sharey=self.swath_ax)  # sounding histogram, link y axis for zoom
	# self.swath_canvas.draw()

	self.x_max = 1
	self.z_max = 1
	self.dr_max = 1000
	self.pi_max = 10
	self.x_max_custom = self.x_max  # store future custom entries
	self.z_max_custom = self.z_max
	self.dr_max_custom = self.dr_max
	self.pi_max_custom = self.pi_max
	self.max_x_tb.setText(str(self.x_max))
	self.max_z_tb.setText(str(self.z_max))
	self.max_dr_tb.setText(str(self.dr_max))
	self.max_pi_tb.setText(str(self.pi_max))
	update_color_modes(self)
	self.clim = []
	self.clim_all_data = []
	self.cset = []
	self.cruise_name = ''
	self.n_wd_max = 8
	self.nominal_angle_line_interval = 15  # degrees between nominal angle lines
	self.nominal_angle_line_max = 75  # maximum desired nominal angle line
	self.swath_ax_margin = 1.1  # scale axes to multiple of max data in each direction
	# add_grid_lines(self)
	# update_axes(self)
	self.color = QtGui.QColor(0, 0, 0)  # set default solid color to black for new data
	self.color_arc = QtGui.QColor('darkGray')
	self.color_cbox_arc.setCurrentText('Solid Color')


def init_data_ax(self):  # set initial data rate plot parameters
	self.data_rate_ax1 = self.data_figure.add_subplot(121, label='1')
	self.data_rate_ax2 = self.data_figure.add_subplot(122, label='2', sharey=self.data_rate_ax1)

	# # set up annotations
	# self.annot = self.data_rate_ax1.annotate("", xy=(0, 0), xytext=(20, 20), textcoords="offset points",
	# 										 bbox=dict(boxstyle="round", fc="w"),
	# 										 arrowprops=dict(arrowstyle="->"))
	# self.annot.set_visible(False)

def init_time_ax(self):  # set initial timing plot parameters
	self.time_ax1 = self.time_figure.add_subplot(111, label='1')
	# self.time_ax2 = self.time_figure.add_subplot(212, label='2', sharey=self.time_ax1)

# def init_param_ax(self):  # set initial runtime parameter tracking plot
	# self.param_ax1 = self.param_figure.add_subplot(111, label='1')

def add_cov_files(self, ftype_filter, input_dir='HOME', include_subdir=False, ):
	# add files with extensions in ftype_filter from input_dir and subdir if desired
	fnames = add_files(self, ftype_filter, input_dir, include_subdir)
	update_file_list(self, fnames)

def remove_cov_files(self, clear_all=False):
	# remove selected files or clear all files, update det and spec dicts accordingly
	removed_files = remove_files(self, clear_all)
	get_current_file_list(self)

	if self.filenames == []:  # all files have been removed
		self.det = {}
		self.det_archive = {}
		self.spec = {}
		update_log(self, 'Cleared all files')
		self.current_file_lbl.setText('Current File [0/0]:')
		self.calc_pb.setValue(0)
		self.cruise_name_updated = False
		self.model_updated = False
		self.ship_name_updated = False

	else:
		remove_data(self, removed_files)

	update_show_data_checks(self)
	refresh_plot(self, call_source='remove_files')  # refresh with updated (reduced or cleared) detection data


def remove_data(self, removed_files):
	# remove data in specified filenames from detection and spec dicts
	for f in removed_files:
		fname = f.text().split('/')[-1]

		try:  # try to remove detections associated with this file
			# get indices of soundings in det dict with matching .all or .kmall filenames
			if self.det and any(fext in fname for fext in ['.all', '.kmall']):
				i = [j for j in range(len(self.det['fname'])) if self.det['fname'][j] == fname]
				for k in self.det.keys():  # loop through all keys and remove values at these indices
					self.det[k] = np.delete(self.det[k], i).tolist()

			elif self.det_archive and '.pkl' in fname:  # remove archive data
				self.det_archive.pop(fname, None)

			elif self.spec and '.txt' in fname:  # remove spec data
				self.spec.pop(fname, None)

		except:  # will fail if det dict has not been created yet (e.g., if calc_coverage has not been run)
			update_log(self, 'Failed to remove soundings from ' + fname)


def update_show_data_checks(self):
	# update show data checkboxes and reset detection dictionaries if all files of a given type are removed
	get_current_file_list(self)
	fnames_all = [f for f in self.filenames if '.all' in f]
	fnames_kmall = [f for f in self.filenames if '.kmall' in f]
	fnames_pkl = [f for f in self.filenames if '.pkl' in f]
	fnames_txt = [f for f in self.filenames if '.txt' in f]

	if len(fnames_all + fnames_kmall) == 0:  # all new files have been removed
		self.det = {}
		self.show_data_chk.setChecked(False)

	if len(fnames_pkl) == 0:  # all archives have been removed
		self.det_archive = {}
		self.show_data_chk_arc.setChecked(False)

	if len(fnames_txt) == 0:  # all spec files have been removed
		self.spec = {}
		self.spec_chk.setChecked(False)


def refresh_plot(self, print_time=True, call_source=None, sender=None, validate_filters=True):
	# update swath plot with new data and options
	n_plotted = 0
	n_plotted_arc = 0
	self.legend_handles = []
	self.legend_handles_data_rate = []
	self.legend_handles_solid = []
	tic = process_time()

	# update_system_info(self)
	self.pt_size = np.square(float(self.pt_size_cbox.currentText()))
	self.pt_alpha = np.divide(float(self.pt_alpha_cbox.currentText()), 100)

	if validate_filters:
		if not validate_filter_text(self):  # validate user input, do not refresh until all float(input) works for all input
			update_log(self, '***WARNING: Invalid/missing filter input (highlighted in yellow); '
							 'valid input required to refresh plot')
			self.tabs.setCurrentIndex(1)  # show filters tab
			return

	print('************* REFRESH PLOT *****************')
	# sorting out how senders are handled when called with connect and lambda
	if self.sender():
		sender = self.sender().objectName()
		print('received a sending button =', sender)
	elif not sender:
		sender = 'NA'

	if sender:
		print('***REFRESH_PLOT activated by sender:', sender)

	if call_source:
		print('***REFRESH_PLOT called by function:', call_source)

	clear_plot(self)

	# update top data plot combobox based on show_data checks
	if sender in ['show_data_chk', 'show_data_chk_arc', 'calc_coverage_btn', 'load_archive_btn']:
		last_top_data = self.top_data_cbox.currentText()
		self.top_data_cbox.clear()
		show_data_dict = {self.show_data_chk: 'New data', self.show_data_chk_arc: 'Archive data'}
		self.top_data_cbox.addItems([v for k, v in show_data_dict.items() if k.isChecked()])
		self.top_data_cbox.setCurrentIndex(max([0, self.top_data_cbox.findText(last_top_data)]))

	# if sending button is returnPressed in min or max clim_tb, update dict of user clim for this mode
	update_clim_tb = sender in ['color_cbox', 'color_cbox_arc', 'top_data_cbox']
	update_color_modes(self, update_clim_tb)

	# update clim_all_data with limits of self.det
	if self.top_data_cbox.currentText() == 'New data':  # default: plot any archive data first as background
		print('in refresh plot, calling show_archive first to allow new data on top')
		n_plotted_arc = show_archive(self)
		print('n_plotted_arc = ', n_plotted_arc)

	if self.det:  # default: plot any available new data
		print('\ncalling plot_coverage with new data')
		n_plotted = plot_coverage(self, self.det, is_archive=False)
		print('n_plotted = ', n_plotted)

		print('calling plot_data_rate')
		plot_data_rate(self, self.det, is_archive=False)

		try:
			print('calling plot_time_diff')
			plot_time_diff(self)

		except:
			print('*** failed to plot time diff')

	if self.top_data_cbox.currentText() == 'Archive data':  # option: plot archive data last on top of any new data
		print('calling show_archive')
		n_plotted_arc = show_archive(self)
		print('n_plotted_arc = ', n_plotted_arc)

	plot_hist(self)  # plot histogram of soundings versus depth
	update_axes(self)  # update axes to fit all loaded data
	add_grid_lines(self)  # add grid lines
	add_WD_lines(self)  # add water depth-multiple lines over coverage
	add_nominal_angle_lines(self)  # add nominal swath angle lines over coverage
	add_legend(self)  # add legend or colorbar
	add_spec_lines(self)  # add specification lines if loaded
	self.swath_canvas.draw()  # final update for the swath canvas
	self.data_canvas.draw()  # final update for the data rate canvas

	toc = process_time()
	refresh_time = toc - tic
	if print_time:
		print('got refresh_time=', refresh_time)
		# update_log(self, 'testing')
		# update_log(self, 'testing')
		update_log(self, 'Updated plot (' + str(n_plotted) + ' new, ' +
				   str(n_plotted_arc) + ' archive soundings; ' + "%.2f" % refresh_time + ' s)')


def update_color_modes(self, update_clim_tb=False):
	# update color modes for the new data and archive data
	self.color_cbox.setEnabled(self.show_data_chk.isChecked())
	self.cmode = self.color_cbox.currentText()  # get the currently selected color mode
	self.cmode = self.cmode.lower().replace(' ', '_')  # format for comparison to list of modes below
	print('self.cmode is now', self.cmode)
	self.scbtn.setEnabled(self.show_data_chk.isChecked() and self.cmode == 'solid_color')

	# enable archive color options if 'show archive' is checked
	self.color_cbox_arc.setEnabled(self.show_data_chk_arc.isChecked())
	self.cmode_arc = self.color_cbox_arc.currentText()  # get the currently selected color mode
	self.cmode_arc = self.cmode_arc.lower().replace(' ', '_')  # format for comparison to list of modes below
	self.scbtn_arc.setEnabled(self.show_data_chk_arc.isChecked() and self.cmode_arc == 'solid_color')

	# determine expected dominant color mode (i.e., data on top) based on show_data checks and top data selection
	cmode_final = [self.cmode * int(self.show_data_chk.isChecked()),
				   self.cmode_arc * int(self.show_data_chk_arc.isChecked())]
	self.cmode_final = cmode_final[int(self.top_data_cbox.currentText() == 'Archive data')]

	# enable colorscale limit text boxes as appopriate
	for i, tb in enumerate([self.min_clim_tb, self.max_clim_tb]):
		tb.setEnabled(self.clim_cbox.currentText() == 'Fixed limits' and \
					  self.cmode_final in ['depth', 'backscatter'])

	if self.cmode_final in ['depth', 'backscatter']:
		if update_clim_tb:  # update text boxes last values if refresh_plot was called by change in cmode
			self.min_clim_tb.setText(str(self.clim_last_user[self.cmode_final][0]))
			self.max_clim_tb.setText(str(self.clim_last_user[self.cmode_final][1]))

		# if refresh_plot was called for any other reason, store user clims that apply for loaded/shown data
		# store these user-defined limits for future reference if data (new or archive) exists and is shown
		elif (self.det and self.top_data_cbox.currentText() == 'New data' and self.show_data_chk.isChecked()) or \
				(self.det_archive and self.top_data_cbox.currentText() == 'Archive data' and
				 self.show_data_chk_arc.isChecked()):
			self.clim_last_user[self.cmode_final] = [float(self.min_clim_tb.text()),
													 float(self.max_clim_tb.text())]

	# get initial clim_all_data from detection dict for reference (and update) in next plot loop
	self.clim_all_data = []  # reset clim_all_data, then update if appropriate for cmode and data availability
	if self.det and self.cmode in ['depth', 'backscatter']:
		clim_dict = {'depth': 'z', 'backscatter': 'bs'}
		temp_all = self.det[clim_dict[self.cmode] + '_port'] + self.det[clim_dict[self.cmode] + '_stbd']

		if temp_all:  # update clim_all_data only if data are available for this colormode
			if self.cmode == 'backscatter':
				temp_all = (np.asarray(temp_all) / 10).tolist()

			self.clim_all_data = [min(temp_all), max(temp_all)]


def update_show_data_checks(self):
	# update show data checkboxes and reset detection dictionaries if all files of a given type are removed
	get_current_file_list(self)
	fnames_all = [f for f in self.filenames if '.all' in f]
	fnames_kmall = [f for f in self.filenames if '.kmall' in f]
	fnames_pkl = [f for f in self.filenames if '.pkl' in f]
	fnames_txt = [f for f in self.filenames if '.txt' in f]

	if len(fnames_all + fnames_kmall) == 0:  # all new files have been removed
		self.det = {}
		self.show_data_chk.setChecked(False)

	if len(fnames_pkl) == 0:  # all archives have been removed
		self.det_archive = {}
		self.show_data_chk_arc.setChecked(False)

	if len(fnames_txt) == 0:  # all spec files have been removed
		self.spec = {}
		self.spec_chk.setChecked(False)


def plot_coverage(self, det, is_archive=False, print_updates=False, det_name='detection dictionary'):
	# plot the parsed detections from new or archive data dict; return the number of points plotted after filtering
	# tic = process_time()
	print('\nstarting PLOT_COVERAGE with', ['NEW', 'ARCHIVE'][int(is_archive)], 'data')
	# consolidate data from port and stbd sides for plotting
	try:
		y_all = det['y_port'] + det['y_stbd']  # acrosstrack distance from TX array (.all) or origin (.kmall)

	except:
		y_all = det['x_port'] + det['x_stbd']  # older archives stored acrosstrack distance as x, not y
		det['y_port'] = deepcopy(det['x_port'])
		det['y_stbd'] = deepcopy(det['x_stbd'])
		# print('retrieved/set acrosstrack "y" values from archive detection dict "x" keys with old naming convention')

	z_all = det['z_port'] + det['z_stbd']  # depth from TX array (.all) or origin (.kmall)
	bs_all = det['bs_port'] + det['bs_stbd']  # reported backscatter amplitude
	fname_all = det['fname'] + det['fname']

	# calculate simplified swath angle from raw Z, Y data to use for angle filtering and comparison to runtime limits
	# Kongsberg angle convention is right-hand-rule about +X axis (fwd), so port angles are + and stbd are -
	angle_all = (-1 * np.rad2deg(np.arctan2(y_all, z_all))).tolist()  # multiply by -1 for Kongsberg convention

	# warn user if detection dict does not have all required offsets for depth reference adjustment (e.g., old archives)
	if (not all([k in det.keys() for k in ['tx_x_m', 'tx_y_m', 'aps_x_m', 'aps_y_m', 'wl_z_m']]) and
			self.ref_cbox.currentText().lower() != 'raw data'):
			update_log(self, 'Warning: ' + det_name + ' does not include all fields required for depth reference '
													  'adjustment (e.g., possibly an old archive format); no depth '
													  'reference adjustment will be made')

	# get file-specific, ping-wise adjustments to bring Z and Y into desired reference frame
	dx_ping, dy_ping, dz_ping = adjust_depth_ref(det, depth_ref=self.ref_cbox.currentText().lower())

	# print('dz_ping has len', len(dz_ping))
	# print('got dy_ping=', dy_ping)
	# print('got dz_ping=', dz_ping)
	# print('first 20 of xline[z]=', z_all[0:20])
	# print('first 20 of dz =', dz_ping[0:20])
	# print('got dy_ping=', dy_ping)
	# print('got dz_ping=', dz_ping)
	z_all = [z + dz for z, dz in zip(z_all, dz_ping + dz_ping)]  # add dz (per ping) to each z (per sounding)
	y_all = [y + dy for y, dy in zip(y_all, dy_ping + dy_ping)]  # add dy (per ping) to each y (per sounding)

	if print_updates:
		for i in range(len(angle_all)):
			if any(np.isnan([angle_all[i], bs_all[i]])):
				print('NAN in (i,y,z,angle,BS):',
					  i, y_all[i], z_all[i], angle_all[i], bs_all[i])

	# update x and z max for axis resizing during each plot call
	self.x_max = max([self.x_max, np.nanmax(np.abs(np.asarray(y_all)))])
	self.z_max = max([self.z_max, np.nanmax(np.asarray(z_all))])

	# after updating axis limits, simply return w/o plotting if toggle for this data type (current/archive) is off
	if ((is_archive and not self.show_data_chk_arc.isChecked())
			or (not is_archive and not self.show_data_chk.isChecked())):
		print('returning from plotter because the toggle for this data type is unchecked')
		return

	# set up indices for optional masking on angle, depth, bs; all idx true until fail optional filter settings
	# all soundings masked for nans (e.g., occasional nans in EX0908 data)
	idx_shape = np.shape(np.asarray(z_all))
	angle_idx = np.ones(idx_shape)
	depth_idx = np.ones(idx_shape)
	bs_idx = np.ones(idx_shape)
	rtp_angle_idx = np.ones(idx_shape)  # idx of angles that fall within the runtime params for RX beam angles
	rtp_cov_idx = np.ones(idx_shape)  # idx of soundings that fall within the runtime params for max coverage
	real_idx = np.logical_not(np.logical_or(np.isnan(y_all), np.isnan(z_all)))  # idx true for NON-NAN soundings

	if print_updates:
		print('number of nans found in y_all and z_all=', np.sum(np.logical_not(real_idx)))
		# print('len of xall before filtering:', len(y_all))

	if self.angle_gb.isChecked():  # get idx satisfying current swath angle filter based on depth/acrosstrack angle
		lims = [float(self.min_angle_tb.text()), float(self.max_angle_tb.text())]
		angle_idx = np.logical_and(np.abs(np.asarray(angle_all)) >= lims[0],
								   np.abs(np.asarray(angle_all)) <= lims[1])

	if self.depth_gb.isChecked():  # get idx satisfying current depth filter
		lims = [float(self.min_depth_tb.text()), float(self.max_depth_tb.text())]
		if is_archive:
			lims = [float(self.min_depth_arc_tb.text()), float(self.max_depth_arc_tb.text())]

		depth_idx = np.logical_and(np.asarray(z_all) >= lims[0], np.asarray(z_all) <= lims[1])

	if self.bs_gb.isChecked():  # get idx satisfying current backscatter filter; BS in 0.1 dB, multiply lims by 10
		# lims = [10 * float(self.min_bs_tb.text()), 10 * float(self.max_bs_tb.text())]
		lims = [float(self.min_bs_tb.text()), float(self.max_bs_tb.text())]  # parsed BS is converted to dB
		bs_idx = np.logical_and(np.asarray(bs_all) >= lims[0], np.asarray(bs_all) <= lims[1])

	if self.rtp_angle_gb.isChecked():  # get idx of angles outside the runtime parameter swath angle limits
		self.rtp_angle_buffer = float(self.rtp_angle_buffer_tb.text())

		try:  # try to compare angles to runtime param limits (port pos., stbd neg. per Kongsberg convention)
			if 'max_port_deg' in det and 'max_stbd_deg' in det:  # compare angles to runtime params if available
				rtp_angle_idx_port = np.less_equal(np.asarray(angle_all),
												   np.asarray(2 * det['max_port_deg']) + self.rtp_angle_buffer)
				rtp_angle_idx_stbd = np.greater_equal(np.asarray(angle_all),
													  -1 * np.asarray(2 * det['max_stbd_deg']) - self.rtp_angle_buffer)
				rtp_angle_idx = np.logical_and(rtp_angle_idx_port, rtp_angle_idx_stbd)  # update rtp_angle_idx

				if print_updates:
					print('set(max_port_deg)=', set(det['max_port_deg']))
					print('set(max_stbd_deg)=', set(det['max_stbd_deg']))
					print('sum of rtp_angle_idx=', sum(rtp_angle_idx))

			else:
				update_log(self, 'Runtime parameters for swath angle limits not available in ' +
						   ('archive' if is_archive else 'current') + ' data; no filtering applied for ' +
						   'RX angles against user-defined limits during acquisition')

		except RuntimeError:
			update_log(self, 'Failure comparing RX beam angles to runtime params; no angle filter applied')

	if self.rtp_cov_gb.isChecked():  # get idx of soundings with coverage near runtime param cov limits
		self.rx_cov_buffer = float(self.rtp_cov_buffer_tb.text())

		try:  # try to compare coverage to runtime param limits (port neg., stbd pos. per Kongsberg convention)
			if 'max_port_m' in det and 'max_stbd_m' in det:  # compare coverage to runtime params if available
				# coverage buffer is negative; more negative, more aggressive filtering
				rtp_cov_idx_port = np.greater_equal(np.asarray(y_all),
													-1 * np.asarray(2 * det['max_port_m']) - self.rx_cov_buffer)
				rtp_cov_idx_stbd = np.less_equal(np.asarray(y_all),
												 np.asarray(2 * det['max_stbd_m']) + self.rx_cov_buffer)
				rtp_cov_idx = np.logical_and(rtp_cov_idx_port, rtp_cov_idx_stbd)

				if print_updates:
					print('set(max_port_m)=', set(det['max_port_m']))
					print('set(max_stbd_m)=', set(det['max_stbd_m']))
					print('sum of rtp_cov_idx=', sum(rtp_cov_idx))

			else:
				update_log(self, 'Runtime parameters for swath coverage limits not available in ' +
						   ('archive' if is_archive else 'current') + ' data; no filtering applied for ' +
						   'coverage against user-defined limits during acquisition')

		except RuntimeError:
			update_log(self, 'Failure comparing coverage to runtime params; no coverage filter applied')

	# apply filter masks to x, z, angle, and bs fields
	filter_idx = np.logical_and.reduce((angle_idx, depth_idx, bs_idx, rtp_angle_idx, rtp_cov_idx, real_idx))

	# get color mode and set up color maps and legend
	cmode = [self.cmode, self.cmode_arc][is_archive]  # get user selected color mode for local use

	print('cmode after first assignment is', cmode)

	# set the color map, initialize color limits and set for legend/colorbars (will apply to last det data plotted)
	self.cmap = 'rainbow'
	self.clim = []
	self.cset = []
	self.legend_label = ''
	self.last_cmode = cmode  # reset every plot call; last (top) plot updates for add_legend and update_color_limits

	# print('before getting c_all, len of z_all, y_all, bs_all =', len(z_all), len(y_all), len(bs_all))

	# set color maps based on combobox selection after filtering data
	if cmode == 'depth':
		c_all = z_all  # set color range to depth range
		print('cmode is depth, len c_all=', len(c_all))

		if len(c_all) > 0:  # if there is at least one sounding, set clim and store for future reference
			self.clim = [min(c_all), max(c_all)]
			self.last_depth_clim = deepcopy(self.clim)

		else:  # use last known depth clim to avoid errors in scatter
			self.clim = deepcopy(self.last_depth_clim)

		self.cmap = self.cmap + '_r'  # reverse the color map so shallow is red, deep is blue
		self.legend_label = 'Depth (m)'

	elif cmode == 'backscatter':
		# c_all = [int(bs) / 10 for bs in bs_all]  # convert to int, divide by 10 (BS reported in 0.1 dB)
		c_all = [int(bs*10)/10 for bs in bs_all]  # BS stored in dB; convert to 0.1 precision
		print('cmode is backscatter, len c_all=', len(c_all))
		# print('c_all =', c_all)
		self.clim = [-50, -10]

		# use backscatter filter limits for color limits
		if self.bs_gb.isChecked() and self.clim_cbox.currentText() == 'Filtered data':
			self.clim = [float(self.min_bs_tb.text()), float(self.max_bs_tb.text())]

		self.legend_label = 'Reported Backscatter (dB)'

	elif np.isin(cmode, ['ping_mode', 'pulse_form', 'swath_mode', 'frequency']):
		# modes are listed per ping; append ping-wise setting to correspond with y_all, z_all, angle_all, bs_all
		mode_all = det[cmode] + det[cmode]
		# mode_all = np.asarray(mode_all)[filter_idx].tolist()  # filter mode_all as applied for z, x, bs, angle, etc.
		print('heading into cmode selection with mode_all=', mode_all)

		if cmode == 'ping_mode':  # define dict of depth modes (based on EM dg format 01/2020) and colors

			print('cmode = ping mode and self.model_name is', self.model_name)

			c_set = {'Very Shallow': 'red', 'Shallow': 'darkorange', 'Medium': 'gold',
					 'Deep': 'limegreen', 'Deeper': 'darkturquoise', 'Very Deep': 'blue',
					 'Extra Deep': 'indigo', 'Extreme Deep': 'black'}
			self.legend_label = 'Depth Mode'

			# EM2040 .all files store frequency mode in the ping mode field; replace color set accordingly
			print('ahead of special EM2040 ping mode c_set:')
			print('self.model_name =', self.model_name)
			print('set(mode_all) =', [mode for mode in set(mode_all)])
			if self.model_name.find('2040') > -1 and any([mode.find('kHz') > -1 for mode in set(mode_all)]):
				print('***using frequency info for ping mode***')
				c_set = {'400 kHz': 'red', '300 kHz': 'darkorange', '200 kHz': 'gold'}
				self.legend_label = 'Freq. (EM 2040, SIS 4)'
				update_log(self, 'Ping mode color scale set to frequency mode (EM 2040, SIS 4 format)')

		elif cmode == 'pulse_form':  # define dict of pulse forms and colors
			c_set = {'CW': 'red', 'Mixed': 'limegreen', 'FM': 'blue'}  # set of pulse forms
			self.legend_label = 'Pulse Form'

		elif cmode == 'swath_mode':  # define dict of swath modes and colors
			# Dual Swath is parsed as Fixed or Dynamic but generalized here
			# c_set = {'Single Swath': 'red', 'Dual Swath (Fixed)': 'limegreen', 'Dual Swath (Dynamic)': 'blue'}
			c_set = {'Single Swath': 'red', 'Dual Swath': 'blue'}
			self.legend_label = 'Swath Mode'

		elif cmode == 'frequency':  # define dict of frequencies
			c_set = {'400 kHz': 'red', '300 kHz': 'darkorange', '200 kHz': 'gold',
					 '70-100 kHz': 'limegreen', '40-100 kHz': 'darkturquoise', '40-70 kHz': 'blue',
					 '30 kHz': 'indigo', '12 kHz': 'black', 'NA': 'white'}
			self.legend_label = 'Frequency'

		# get integer corresponding to mode of each detection; as long as c_set is consistent, this should keep
		# color coding consistent for easier comparison of plots across datasets with different modes present
		# some modes incl. parentheses as parsed, e.g., 'Dual Swath (Dynamic)' and 'Dual Swath (Fixed)'; entries are
		# split/stripped in mode_all to the 'base' mode, e.g., 'Dual Swath' for comparison to simpler c_set dict
		mode_all_base = [m.split('(')[0].strip() for m in mode_all]

		print('c_set =', c_set)
		print('mode all base = ', mode_all_base)

		c_all = [c_set[mb] for mb in mode_all_base]
		# print('colr mode is ping, pulse, or swath --> len of new c_all is', len(c_all))
		# print('c_all= at time of assignment=', c_all)
		self.clim = [0, len(c_set.keys()) - 1]  # set up limits based on total number of modes for this cmode
		self.cset = c_set  # store c_set for use in legend labels

	else:  # cmode is a solid color
		c_all = np.ones_like(y_all)  # make a placeholder c_all for downsampling process

	# add clim from this dataset to clim_all_data for reference if color modes are same for new and archive data
	if cmode != 'solid_color':
		# print('** after filtering, just updated clim_all_data from', self.clim_all_data)
		if self.cmode == self.cmode_arc:
			self.clim_all_data += self.clim
			self.clim = [min(self.clim_all_data), max(self.clim_all_data)]
	# print('to', self.clim_all_data)
	# print('and updated min/max to self.clim=', self.clim)

	# store the unfiltered, undecimated, unsorted color data for use by plot_data_rate
	if is_archive:
		self.c_all_data_rate_arc = deepcopy(c_all)
	else:
		self.c_all_data_rate = deepcopy(c_all)

	# print('before applying filters, len of c_all is', len(c_all))

	# filter the data after storing the color data for plot_data_rate
	y_all = np.asarray(y_all)[filter_idx].tolist()
	z_all = np.asarray(z_all)[filter_idx].tolist()
	angle_all = np.asarray(angle_all)[filter_idx].tolist()
	bs_all = np.asarray(bs_all)[filter_idx].tolist()
	c_all = np.asarray(c_all)[filter_idx].tolist()  # FAILS WHEN FILTERING AND COLORING BY PING PULSE OR SWATH MODE
	self.fnames_all = np.asarray(fname_all)[filter_idx].tolist()

	if print_updates:
		print('AFTER APPLYING IDX: len y_all, z_all, angle_all, bs_all, c_all=',
			  len(y_all), len(z_all), len(angle_all), len(bs_all), len(c_all))

	# get post-filtering number of points to plot and allowable maximum from default or user input (if selected)
	self.n_points = len(y_all)
	self.n_points_max = self.n_points_max_default

	if self.pt_count_gb.isChecked() and self.max_count_tb.text():  # override default only if explicitly set by user
		self.n_points_max = float(self.max_count_tb.text())

	# default dec fac to meet n_points_max, regardless of whether user has checked box for plot point limits
	if self.n_points_max == 0:
		update_log(self, 'Max plotting sounding count set equal to zero')
		self.dec_fac_default = np.inf
	else:
		self.dec_fac_default = float(self.n_points / self.n_points_max)

	if self.dec_fac_default > 1 and not self.pt_count_gb.isChecked():  # warn user if large count may slow down plot
		update_log(self, 'Large filtered sounding count (' + str(self.n_points) + ') may slow down plotting')

	# get user dec fac as product of whether check box is checked (default 1)
	self.dec_fac_user = max(self.pt_count_gb.isChecked() * float(self.dec_fac_tb.text()), 1)
	self.dec_fac = max(self.dec_fac_default, self.dec_fac_user)

	if self.dec_fac_default > self.dec_fac_user:  # warn user if default max limit was reached
		update_log(self, 'Decimating' + (' archive' if is_archive else '') +
				   ' data by factor of ' + "%.1f" % self.dec_fac +
				   ' to keep plotted point count under ' + "%.0f" % self.n_points_max)

	elif self.pt_count_gb.isChecked() and self.dec_fac_user > self.dec_fac_default and self.dec_fac_user > 1:
		# otherwise, warn user if their manual dec fac was applied because it's more aggressive than max count
		update_log(self, 'Decimating' + (' archive' if is_archive else '') +
				   ' data by factor of ' + "%.1f" % self.dec_fac +
				   ' per user input')

	# print('before decimation, c_all=', c_all)

	if self.dec_fac > 1:
		# print('dec_fac > 1 --> attempting interp1d')
		idx_all = np.arange(len(y_all))  # integer indices of all filtered data
		idx_dec = np.arange(0, len(y_all) - 1, self.dec_fac)  # desired decimated indices, may be non-integer

		# interpolate indices of colors, not color values directly
		f_dec = interp1d(idx_all, idx_all, kind='nearest')  # nearest neighbor interpolation function of all indices
		idx_new = [int(i) for i in f_dec(idx_dec)]  # list of decimated integer indices
		# print('idx_new is now', idx_new)
		y_all = [y_all[i] for i in idx_new]
		z_all = [z_all[i] for i in idx_new]
		c_all = [c_all[i] for i in idx_new]
		# print('idx_new=', idx_new)

	self.n_points = len(y_all)

	print('self n_points = ', self.n_points)

	# plot y_all vs z_all using colormap c_all
	if cmode == 'solid_color':  # plot solid color if selected
		# get new or archive solid color, convert c_all to array to avoid warning
		c_all = colors.hex2color([self.color.name(), self.color_arc.name()][int(is_archive)])
		c_all = np.tile(np.asarray(c_all), (len(y_all), 1))

		# print('cmode is solid color, lengths are', len(y_all), len(z_all), len(c_all))
		local_label = ('Archive data' if is_archive else 'New data')
		solid_handle = self.swath_ax.scatter(y_all, z_all, s=self.pt_size, c=c_all,
											marker='o', alpha=self.pt_alpha, linewidths=0,
											label=local_label)
		self.swath_canvas.draw()
		self.legend_handles_solid.append(solid_handle)  # store solid color handle

	else:  # plot other color scheme, specify vmin and vmax from color range

		print('cmode is', cmode)

		if cmode in ['ping_mode', 'swath_mode', 'pulse_form', 'frequency']:  # generate patches for legend with modes
			self.legend_handles = [patches.Patch(color=c, label=l) for l, c in self.cset.items()]

		if self.clim_cbox.currentText() == 'Filtered data':  # update clim from filters applied in active color mode
			update_log(self, 'Updating color scale to cover applied filter limits')

			if self.depth_gb.isChecked() and cmode == 'depth':
				# use enabled depth filter limits for color limits; include new, archive, or all limits, as checked
				z_lims_new = [float(self.min_depth_tb.text()), float(self.max_depth_tb.text())] * \
							 int(self.cmode == 'depth' and self.show_data_chk.isChecked())
				z_lims_arc = [float(self.min_depth_arc_tb.text()), float(self.max_depth_arc_tb.text())] * \
							 int(self.cmode_arc == 'depth' and self.show_data_chk_arc.isChecked())
				z_lims_checked = z_lims_new + z_lims_arc
				self.clim = [min(z_lims_checked), max(z_lims_checked)]

			if self.bs_gb.isChecked() and cmode == 'backscatter':  # use enabled bs filter limits for color limits
				self.clim = [float(self.min_bs_tb.text()), float(self.max_bs_tb.text())]

			self.clim_all_data += self.clim  # update clim_all_data in case same color mode is applied to both

		elif self.clim_cbox.currentText() == 'Fixed limits':  # update color limits from user entries
			self.clim = [float(self.min_clim_tb.text()), float(self.max_clim_tb.text())]

		# same color mode for new and archive: use clim_all_data
		elif self.cmode == self.cmode_arc and self.show_data_chk.isChecked() and self.show_data_chk_arc.isChecked():
			# new and archive data showing with same color mode; scale clim to all data (ignore filters for clim)
			update_log(self, 'Updating color scale to cover new and archive datasets with same color mode')
			self.clim = [min(self.clim_all_data), max(self.clim_all_data)]

		# after all filtering and color updates, finally plot the data
		print('now calling scatter with self.clim=', self.clim)
		# if len(z_all) == 0:
		# 	self.clim = []
		# self.mappable = self.swath_ax.scatter(y_all, z_all, s=self.pt_size, c=c_all,
		# 									  marker='o', alpha=self.pt_alpha, linewidths=0,
		# 									  vmin=self.clim[0], vmax=self.clim[1], cmap=self.cmap)

		self.h_swath = self.swath_ax.scatter(y_all, z_all, s=self.pt_size, c=c_all,
											 marker='o', alpha=self.pt_alpha, linewidths=0,
											 vmin=self.clim[0], vmax=self.clim[1], cmap=self.cmap)

		# data = numpy.random.random(100)
		# bins = numpy.linspace(0, 1, 10)
		# digitized = numpy.digitize(data, bins)
		# bin_means = [data[digitized == i].mean() for i in range(1, len(bins))]

		# bins = np.append(np.arange(0, max(z_all), 100), max(z_all))

		# save filtered coverage data for processing to export trend for Gap Filler
		if is_archive:
			self.y_all_arc = y_all
			self.z_all_arc = z_all
		if not is_archive:
			self.y_all = y_all
			self.z_all = z_all

		print('calling calc_coverage_trend from plot_coverage')
		calc_coverage_trend(self, z_all, y_all, is_archive)

	# toc = process_time()
	# plot_time = toc - tic

	return len(z_all)


def validate_filter_text(self):
	# validate user inputs before trying to apply filters and refresh plot
	valid_filters = True
	tb_list = [self.min_angle_tb, self.max_angle_tb,
			   self.min_depth_tb, self.max_depth_tb, self.min_depth_arc_tb, self.max_depth_arc_tb,
			   self.min_bs_tb, self.max_bs_tb, self.rtp_angle_buffer_tb, self.rtp_cov_buffer_tb]

	for tb in tb_list:
		try:
			float(tb.text())
			tb.setStyleSheet('background-color: white')

		except:
			tb.setStyleSheet('background-color: yellow')
			valid_filters = False

	# print('\nvalid_filters=', valid_filters)

	return valid_filters


def add_ref_filter_text(self):
	# add text for depth ref and filters applied
	ref_str = 'Reference: ' + self.ref_cbox.currentText()
	depth_fil = ['None', self.min_depth_tb.text() + ' to ' + self.max_depth_tb.text() + ' m']
	depth_arc_fil = ['None', self.min_depth_arc_tb.text() + ' to ' + self.max_depth_arc_tb.text() + ' m']
	angle_fil = ['None', self.min_angle_tb.text() + ' to ' + self.max_angle_tb.text() + '\u00b0']
	bs_fil = ['None', ('+' if float(self.min_bs_tb.text()) > 0 else '') + self.min_bs_tb.text() + ' to ' +
			  ('+' if float(self.max_bs_tb.text()) > 0 else '') + self.max_bs_tb.text() + ' dB']
	rtp_angle_fil = ['None', ('+' if float(self.rtp_angle_buffer_tb.text()) > 0 else '') + \
					 self.rtp_angle_buffer_tb.text() + '\u00b0']  # user limit +/- buffer
	rtp_cov_fil = ['None', ('-' if float(self.rtp_cov_buffer_tb.text()) > 0 else '') + \
				   self.rtp_cov_buffer_tb.text() + ' m']  # user limit - buffer
	fil_dict = {'Angle filter: ': angle_fil[self.angle_gb.isChecked()],
				'Depth filter (new): ': depth_fil[self.depth_gb.isChecked()],
				'Depth filter (archive): ': depth_arc_fil[self.depth_gb.isChecked()],
				'Backscatter filter: ': bs_fil[self.bs_gb.isChecked()],
				'Runtime angle buffer: ': rtp_angle_fil[self.rtp_angle_gb.isChecked()],
				'Runtime coverage buffer: ': rtp_cov_fil[self.rtp_cov_gb.isChecked()]}

	for fil in fil_dict.keys():
		ref_str += '\n' + fil + fil_dict[fil]

	ref_str += '\nMax. point count: ' + str(int(self.n_points_max))
	ref_str += '\nDecimation factor: ' + "%.1f" % self.dec_fac

	if self.show_ref_fil_chk.isChecked():
		self.swath_ax.text(0.02, 0.98, ref_str,
						   # 'Ref: ' + self.ref_cbox.currentText(),
						   ha='left', va='top', fontsize=8, transform=self.swath_ax.transAxes,
						   bbox=dict(facecolor='white', edgecolor=None, linewidth=0, alpha=1))


def calc_coverage(self):
	# calculate swath coverage from new .all files and update the detection dictionary
	self.y_all = []
	self.z_all = []

	try:
		fnames_det = list(set(self.det['fname']))  # make list of unique filenames already in det dict

	except:
		fnames_det = []  # self.det has not been created yet
		self.det = {}

	fnames_new = get_new_file_list(self, ['.all', '.kmall'], fnames_det)  # list new .all files not in det dict
	num_new_files = len(fnames_new)

	if num_new_files == 0:
		update_log(self, 'No new .all or .kmall file(s) added.  Please add new file(s) and calculate coverage.')

	else:
		# update_log('Calculating coverage from ' + str(num_new_files) + ' new file(s)')
		update_log(self, 'Calculating coverage from ' + str(num_new_files) + ' new file(s)')
		QtWidgets.QApplication.processEvents()  # try processing and redrawing the GUI to make progress bar update
		data_new = {}
		self.skm_time = {}

		# update progress bar and log
		self.calc_pb.setValue(0)  # reset progress bar to 0 and max to number of files
		self.calc_pb.setMaximum(len(fnames_new))

		i = 0  # counter for successfully parsed files (data_new index)

		for f in range(len(fnames_new)):
			fname_str = fnames_new[f].rsplit('/')[-1]
			self.current_file_lbl.setText('Parsing new file [' + str(f+1) + '/' + str(num_new_files) + ']:' + fname_str)
			QtWidgets.QApplication.processEvents()
			ftype = fname_str.rsplit('.', 1)[-1]

			try:  # try to parse file
				if ftype == 'all':
					data_new[i] = parseEMswathwidth(self, fnames_new[f], print_updates=self.print_updates)

				elif ftype == 'kmall':
					km = kmall_data(fnames_new[f])  # kmall_data class inherits kmall, adds extract_dg method
					km.verbose = 0
					km.index_file()
					km.report_packet_types()

					# extract required datagrams
					km.extract_dg('MRZ')  # sounding data
					km.extract_dg('IOP')  # runtime params
					km.extract_dg('IIP')  # installation params
					# km.extract_dg('FCF')  # TESTING backscatter calibration file
					km.extract_dg('SKM')  # TESTING Seapath timing extraction for Revelle SAT

					km.closeFile()

					data_new[i] = {'fname': fnames_new[f], 'XYZ': km.mrz['sounding'],
								   'HDR': km.mrz['header'], 'RTP': km.mrz['pingInfo'],
								   'IOP': km.iop, 'IP': km.iip}  #, 'SKM': km.skm}

					print('after parsing and storing kmall_data...')
					# data_new[i]['XYZ'][0]['start_bytes'] = km.mrz['start_bytes']
					print('XYZ[0].keys are', data_new[i]['XYZ'][0].keys())
					print('km.mrz.keys are ', km.mrz.keys())
					print('km.mrz[start_byte] =', km.mrz['start_byte'])

					ping_bytes = [0] + np.diff(km.mrz['start_byte']).tolist()
					print('ping_bytes = ', ping_bytes)
					print('ping_bytes has len', len(ping_bytes))
					print('len XYZ = ', len(data_new[i]['XYZ']))

					for p in range(len(data_new[i]['XYZ'])):  # store ping start byte
						data_new[i]['XYZ'][p]['bytes_from_last_ping'] = ping_bytes[p]

						print('ping ', p, 'has n_soundings =', len(data_new[i]['XYZ'][p]['z_reRefPoint_m']))

					# data_new[i]['XYZ']['start_byte'] = km.mrz['start_byte']

					# data_new[i]['XYZ']['start_bytes'] = km.mrz['start_bytes']
					# print('data_new[i][XYZ][start_bytes]=', data_new[i]['XYZ']['start_bytes'])
					# print('in kmall_data, km.mrz = ', km.mrz)

					# data_new[i]['XYZ']['start_bytes']
					# print('data_new[IP]=', data_new[i]['IP'])
					# print('IP text =', data_new[i]['IP']['install_txt'])

					print('\n\n\n***got km.skm with keys =', km.skm.keys())

					dt_dg_header_minus_seapath_sample = []
					num_SKM = len(km.skm['header'])

					SKM_header_datetime = [km.skm['header'][i]['dgdatetime'] for i in range(num_SKM)]
					SKM_sample_datetime = [km.skm['sample'][i]['KMdefault']['datetime'][0] for i in range(num_SKM)]

					self.skm_time[i] = {'fname': fnames_new[f],
										'SKM_header_datetime': SKM_header_datetime,
										'SKM_sample_datetime': SKM_sample_datetime}

					# print('\n\n***got SKM_header_datetime =', SKM_header_datetime)
					# print('\n\n***got SKM_sample_datetime =', SKM_sample_datetime)
					# print('lengths are: ', len(SKM_header_datetime), len(SKM_sample_datetime))
					print(km.skm['header'][0]['dgdatetime'])
					print(km.skm['sample'][0]['KMdefault']['datetime'][0])

				else:
					update_log(self, 'Warning: Skipping unrecognized file type for ' + fname_str)

				data_new[i]['fsize'] = os.path.getsize(fnames_new[f])
				print('stored file size ', data_new[i]['fsize'])
				fname_wcd = fnames_new[f].replace('.kmall', '.kmwcd').replace('.all', '.wcd')
				print('looking for watercolumn file: ', fname_wcd)
				try:  # try to get water column file size (.kmwcd for .kmall. or .wcd for .all)
					data_new[i]['fsize_wc'] = os.path.getsize(fname_wcd)
					print('stored water column file size', data_new[i]['fsize_wc'], ' for file', fnames_new[f])
				except:
					print('failed to get water column file size for file ', fname_wcd)
					data_new[i]['fsize_wc'] = np.nan

				update_log(self, 'Parsed file ' + fname_str)
				i += 1  # increment successful file counter

			except:  # failed to parse this file
				update_log(self, 'No swath data parsed for ' + fname_str)

			update_prog(self, f + 1)

		self.data_new = interpretMode(self, data_new, print_updates=self.print_updates)  # True)
		det_new = sortDetectionsCoverage(self, data_new, print_updates=self.print_updates)  # True)

		if len(self.det) is 0:  # if detection dict is empty with no keys, store new detection dict
			self.det = det_new

		else:  # otherwise, append new detections to existing detection dict
			for key, value in det_new.items():  # loop through the new data and append to existing self.det
				self.det[key].extend(value)

		update_log(self, 'Finished calculating coverage from ' + str(num_new_files) + ' new file(s)')
		self.current_file_lbl.setText('Current File [' + str(f + 1) + '/' + str(num_new_files) +
									  ']: Finished calculating coverage')

		# update system information from detections
		# update_system_info(self, force_update=True)
		update_system_info(self, self.det, force_update=True, fname_str_replace='_trimmed')

		# set show data button to True (and cause refresh that way) or refresh plot directly, but not both
		if not self.show_data_chk.isChecked():
			self.show_data_chk.setChecked(True)
		else:
			refresh_plot(self, print_time=True, call_source='calc_coverage')

	# update system information from detections
	# update_system_info(self, force_update=True)

	self.calc_coverage_btn.setStyleSheet("background-color: none")  # reset the button color to default

	sort_det_time(self)  # sort all detections by time for runtime parameter logging/searching

	print('all det dict fields are: ', self.det.keys())
	print('sanity checking angles example --> set of all max_port_deg: ', [str(mpd) for mpd in set(self.det['max_port_deg'])])

def parseEMswathwidth(self, filename, print_updates=False):
	# if print_updates:
	# print("\nParsing file:", filename)

	# Open and read the .all file
	# filename = '0248_20160911_191203_Oden.all'
	f = open(filename, 'rb')
	raw = f.read()
	len_raw = len(raw)

	# initialize data dict with remaining datagram fields
	data = {'fname': filename, 'XYZ': {}, 'RTP': {}, 'RRA': {}, 'IP': {}, 'POS': {}}

	# Declare counters for dg starting byte counter and dg processing counter
	dg_start = 0  # datagram (starting with STX = 2) starts at byte 4
	dg_count = 0
	parse_prog_old = -1

	loop_num = 0

	last_dg_start = 0  # store number of bytes since last XYZ88 datagram

	# Assign and parse datagram
	# while dg_start <= len_raw:  # and dg_count < 10:
	while True:
		loop_num = loop_num + 1

		# print progress update
		parse_prog = round(10 * dg_start / len_raw)
		if parse_prog > parse_prog_old:
			print("%s%%" % (parse_prog * 10) + ('\n' if parse_prog == 10 else ''), end=" ", flush=True)
			parse_prog_old = parse_prog

		if dg_start + 4 >= len_raw:  # break if EOF
			break

		dg_len = struct.unpack('I', raw[dg_start:dg_start + 4])[0]  # get dg length (before start of dg at STX)

		# skip to next iteration if dg length is insufficient to check for STX, ID, and ETX, or dg end is beyond EOF
		if dg_len < 3:
			dg_start = dg_start + 4
			continue

		dg_end = dg_start + 4 + dg_len

		if dg_end > len_raw:
			dg_start = dg_start + 4
			continue

		# if dg_end <= len_raw:  # try to read dg if len seems reasonable and not EOF
		dg = raw[dg_start + 4:dg_end]  # get STX, ID, and ETX
		dg_STX = dg[0]
		dg_ID = dg[1]
		dg_ETX = dg[-3]

		# continue unpacking only if STX and ETX are valid and dg_ID is Runtime Param or XYZ datagram
		if dg_STX == 2 and dg_ETX == 3:

			# print('found valid STX and ETX in loop number', loop_num)

			if dg_ID in [73, 105]:
				# print(len(data['IP_start'].keys()))
				data['IP'][len(data['IP'])] = multibeam_tools.libs.parseEM.IP_dg(dg)
				# if dg_ID == 73:
				# update_log(self, 'Found TX Z offset = ' + str(data['IP'][len(data['IP']) - 1]['S1Z']) +
				# 		   ' m and Waterline offset = ' + str(data['IP'][len(data['IP']) - 1]['WLZ']) + ' m')

			# print('in file ', filename, 'just parsed an IP datagram:', data['IP'])

			# Parse POSITION datagram
			if dg_ID == 80:
				data['POS'][len(data['POS'])] = multibeam_tools.libs.parseEM.POS_dg(dg)

			# Parse RUNTIME PARAM datagram PYTHON 3
			if dg_ID == 82:
				data['RTP'][len(data['RTP'])] = multibeam_tools.libs.parseEM.RTP_dg(dg)
				# print('just parsed data[RTP][end] =', data['RTP'][-1])

			# Parse XYZ 88 datagram PYTHON 3
			if dg_ID == 88:
				XYZ_temp = multibeam_tools.libs.parseEM.XYZ_dg(dg, parse_outermost_only=True)
				if XYZ_temp != []:  # store only if valid soundings are found (parser returns empty otherwise)
					data['XYZ'][len(data['XYZ'])] = XYZ_temp

					# store last RTP MODE for each ping
					data['XYZ'][len(data['XYZ'])-1]['MODE'] = data['RTP'][len(data['RTP'])-1]['MODE']
					data['XYZ'][len(data['XYZ'])-1]['MAX_PORT_M'] = data['RTP'][len(data['RTP'])-1]['MAX_PORT_SWATH']
					data['XYZ'][len(data['XYZ'])-1]['MAX_PORT_DEG'] = data['RTP'][len(data['RTP'])-1]['MAX_PORT_COV']
					data['XYZ'][len(data['XYZ'])-1]['MAX_STBD_M'] = data['RTP'][len(data['RTP'])-1]['MAX_STBD_SWATH']
					data['XYZ'][len(data['XYZ'])-1]['MAX_STBD_DEG'] = data['RTP'][len(data['RTP'])-1]['MAX_STBD_COV']

					# soundings referenced to Z of TX array, X and Y of active positioning system;
					# store last TX Z and waterline offset, plus active positioning system acrosstrack offset
					data['XYZ'][len(data['XYZ'])-1]['TX_X_M'] = data['IP'][len(data['IP'])-1]['S1X']
					data['XYZ'][len(data['XYZ'])-1]['TX_Y_M'] = data['IP'][len(data['IP'])-1]['S1Y']
					data['XYZ'][len(data['XYZ'])-1]['TX_Z_M'] = data['IP'][len(data['IP'])-1]['S1Z']
					data['XYZ'][len(data['XYZ'])-1]['WL_Z_M'] = data['IP'][len(data['IP'])-1]['WLZ']
					# print('APS number =', data['IP'][len(data['IP']) - 1]['APS'])
					APS_num = int(data['IP'][len(data['IP'])-1]['APS']+1)  # act pos num (0-2): dg field P#Y (1-3)
					data['XYZ'][len(data['XYZ'])-1]['APS_X_M'] = \
						data['IP'][len(data['IP'])-1]['P' + str(APS_num) + 'X']
					data['XYZ'][len(data['XYZ'])-1]['APS_Y_M'] = \
						data['IP'][len(data['IP'])-1]['P' + str(APS_num) + 'Y']
					data['XYZ'][len(data['XYZ'])-1]['APS_Z_M'] = \
						data['IP'][len(data['IP'])-1]['P' + str(APS_num) + 'Z']

					# store bytes since last ping
					data['XYZ'][len(data['XYZ'])-1]['BYTES_FROM_LAST_PING'] = dg_start - last_dg_start

					# print('last_dg_start, dg_start, and difference (bytes since last ping) = ',
					# 	  last_dg_start, dg_start, data['XYZ'][len(data['XYZ']) - 1]['BYTES_FROM_LAST_PING'])

					last_dg_start = dg_start  # update ping byte gap tracker

				if print_updates:
					print('ping', len(data['XYZ']), 'swath limits (port/stbd):',
						  data['XYZ'][len(data['XYZ'])-1]['MAX_PORT_DEG'], '/',
						  data['XYZ'][len(data['XYZ'])-1]['MAX_STBD_DEG'], 'deg and',
						  data['XYZ'][len(data['XYZ'])-1]['MAX_PORT_M'], '/',
						  data['XYZ'][len(data['XYZ'])-1]['MAX_STBD_M'], 'meters')


			# parse RRA 78 datagram to get RX beam angles
			if dg_ID == 78:
				# MODIFY RRA PARSER WITH PARSE_OUTERMOST_ONLY OPTION
				data['RRA'][len(data['RRA'])] = multibeam_tools.libs.parseEM.RRA_78_dg(dg)
			# RX_angles[len(RX_angles)] = RRA_temp['RX_ANGLE']

			# if there was a valid STX and ETX, jump to end of dg and continue on next iteration
			dg_start = dg_start + dg_len + 4
			continue

		# if no condition was met to read and jump ahead not valid, move ahead by 1 and continue search
		# (will start read dg_len at -4 on next loop)
		dg_start = dg_start + 1
	# print('STX or ETX not valid, moving ahead by 1 to new dg_start', dg_start)

	# loop through the XYZ and RRA data, store angles re RX array associated with each outermost sounding
	# if parsing outermost soundings only, the number of RRA datagrams may exceed num of XYZ datagrams if some XYZ dg
	# did not have valid soundings (return []); check RRA PING_COUNTER against XYZ PING_COUNTER to make new RRA ping
	# index reference for copying RX angles in following loop
	pXYZ = [data['XYZ'][p]['PING_COUNTER'] for p in range(len(data['XYZ']))]
	pRRA = [p for p in range(len(data['RRA'])) if data['RRA'][p]['PING_COUNTER'] in pXYZ]
	# print('pXYZ has len and =', len(pXYZ), pXYZ)
	# print('pRRA has len and =', len(pRRA), pRRA)

	for p in range(len(data['XYZ'])):
		# data['XYZ'][p]['RX_ANGLE_PORT'] = data['RRA'][p]['RX_ANGLE'][data['XYZ'][p]['RX_BEAM_IDX_PORT']]/100
		# data['XYZ'][p]['RX_ANGLE_STBD'] = data['RRA'][p]['RX_ANGLE'][data['XYZ'][p]['RX_BEAM_IDX_STBD']]/100

		# use reduced RRA ping reference indices to ensure samel PING_COUNTER for XYZ and RRA dg
		data['XYZ'][p]['RX_ANGLE_PORT'] = data['RRA'][pRRA[p]]['RX_ANGLE'][data['XYZ'][p]['RX_BEAM_IDX_PORT']] / 100
		data['XYZ'][p]['RX_ANGLE_STBD'] = data['RRA'][pRRA[p]]['RX_ANGLE'][data['XYZ'][p]['RX_BEAM_IDX_STBD']] / 100

		data['XYZ'][p]['RX_ANGLE'] = [data['XYZ'][p]['RX_ANGLE_PORT'], data['XYZ'][p]['RX_ANGLE_STBD']]  # store both

		if print_updates:
			print('ping', p, 'has RX angles port/stbd IDX',
				  data['XYZ'][p]['RX_BEAM_IDX_PORT'], '/', data['XYZ'][p]['RX_BEAM_IDX_STBD'], ' and ANGLES ',
				  data['XYZ'][p]['RX_ANGLE_PORT'], '/',
				  data['XYZ'][p]['RX_ANGLE_STBD'])

	del data['RRA']  # outermost valid RX angles have been stored in XYZ, RRA is no longer needed
	# del data['RTP']

	# for dg_num in data['RTP'].keys():
	# for field in data['RTP'][dg_num].keys():
	print('data has fields ', data.keys())
	print('.ALL RTP fields for first stored datagram =', data['RTP'][0].keys())

	if print_updates:
		print("\nFinished parsing file:", filename)
		fields = [f for f in data.keys() if f != 'fname']
		for field in fields:
			print(field, len(data[field]))

	return data


# def interpretMode(self, data, print_updates):
# 	# interpret runtime parameters for each ping and store in XYZ dict prior to sorting
# 	# nominal frequencies for most models; EM712 .all (SIS 4) assumed 40-100 kHz (40-70/70-100 options in SIS 5)
# 	# EM2040 frequencies for SIS 4 stored in ping mode; EM2040 frequencies for SIS 5 are stored in runtime parameter
# 	# text and are updated in sortDetectionsAccuracy if available; NA is used as a placeholder here
#
# 	freq_dict = {'122': '12 kHz', '124': '12 kHz',
# 				 '302': '30 kHz', '304': '30 kHz',
# 				 '710': '70-100 kHz', '712': '40-100 kHz',
# 				 '2040': 'NA'}
#
# 	for f in range(len(data)):
# 		missing_mode = False
# 		ftype = data[f]['fname'].rsplit('.', 1)[1]
#
# 		if ftype == 'all':  # interpret .all modes from binary string
# 			# KM ping modes for 1: EM3000, 2: EM3002, 3: EM2000,710,300,302,120,122, 4: EM2040
# 			# See KM runtime parameter datagram format for models listed
# 			# list of models that originally used this datagram format AND later models that produce .kmall
# 			# that may have been converted to .all using Kongsberg utilities during software transitions; note that
# 			# EM2040 is a special case, and use of this list may depend on mode being interpreted below
# 			all_model_list = [710, 712, 300, 302, 304, 120, 122, 124]
#
# 			mode_dict = {'3000': {'0000': 'Nearfield (4 deg)', '0001': 'Normal (1.5 deg)', '0010': 'Target Detect'},
# 						 '3002': {'0000': 'Wide TX (4 deg)', '0001': 'Normal TX (1.5 deg)'},
# 						 '9999': {'0000': 'Very Shallow', '0001': 'Shallow', '0010': 'Medium',
# 								  '0011': 'Deep', '0100': 'Very Deep', '0101': 'Extra Deep'},
# 						 '2040': {'0000': '200 kHz', '0001': '300 kHz', '0010': '400 kHz'}}
#
# 			# pulse and swath modes for EM2040, 710/12, 302, 122, and later models converted from .kmall to .all
# 			pulse_dict = {'00': 'CW', '01': 'Mixed', '10': 'FM'}
# 			pulse_dict_2040C = {'0': 'CW', '1': 'FM'}
# 			swath_dict = {'00': 'Single Swath', '01': 'Dual Swath (Fixed)', '10': 'Dual Swath (Dynamic)'}
#
# 			# loop through all pings
# 			for p in range(len(data[f]['XYZ'])):
# 				# print('binary mode as parsed = ', data[f]['XYZ'][p]['MODE'])
# 				bin_temp = "{0:b}".format(data[f]['XYZ'][p]['MODE']).zfill(8)  # binary str
# 				ping_temp = bin_temp[-4:]  # last 4 bytes specify ping mode based on model
# 				model_temp = str(data[f]['XYZ'][p]['MODEL']).strip()
#
# 				# check model to reference correct key in ping mode dict
# 				if np.isin(data[f]['XYZ'][p]['MODEL'], all_model_list + [2000, 1002]):
# 					model_temp = '9999'  # set model_temp to reference mode_list dict for all applicable models
#
# 				data[f]['XYZ'][p]['PING_MODE'] = mode_dict[model_temp][ping_temp]
#
# 				# interpret pulse form and swath mode based on model
# 				# print('working on modes for model: ', data[f]['XYZ'][p]['MODEL'])
#
# 				if np.isin(data[f]['XYZ'][p]['MODEL'], all_model_list + [2040]):  # reduced models for swath and pulse
# 					data[f]['XYZ'][p]['SWATH_MODE'] = swath_dict[bin_temp[-8:-6]]  # swath mode from binary str
# 					data[f]['XYZ'][p]['PULSE_FORM'] = pulse_dict[bin_temp[-6:-4]]  # pulse form from binary str
#
# 					if data[f]['XYZ'][p]['MODEL'] == 2040:  # EM2040 .all format stores freq mode in ping mode
# 						# print('assigning EM2040 frequency from ping mode for .all format')
# 						data[f]['XYZ'][p]['FREQUENCY'] = data[f]['XYZ'][p]['PING_MODE']
#
# 					else:
# 						# print('assigning non-EM2040 frequency from model for .all format')
# 						data[f]['XYZ'][p]['FREQUENCY'] = freq_dict[str(data[f]['XYZ'][p]['MODEL'])]
#
# 				elif data[f]['XYZ'][p]['MODEL'] == '2040C':  # special cases for EM2040C
# 					data[f]['XYZ'][p]['SWATH_MODE'] = pulse_dict_2040C[bin_temp[-7:-6]]  # swath mode from binary str
# 					data[f]['XYZ'][p]['FREQUENCY'] = 'NA'  # future: parse from binary (format: 180 kHz + bin*10kHz)
#
# 				else:  # specify NA if not in model list for this interpretation
# 					data[f]['XYZ'][p]['PULSE_FORM'] = 'NA'
# 					data[f]['XYZ'][p]['SWATH_MODE'] = 'NA'
# 					data[f]['XYZ'][p]['FREQUENCY'] = 'NA'
# 					missing_mode = True
#
# 				if print_updates:
# 					ping = data[f]['XYZ'][p]
# 					print('file', f, 'ping', p, 'is', ping['PING_MODE'], ping['PULSE_FORM'], ping['SWATH_MODE'])
#
# 		elif ftype == 'kmall':  # interpret .kmall modes from parsed fields
# 			# depth mode list for AUTOMATIC selection; add 100 for MANUAL selection (e.g., '101': 'Shallow (Manual))
# 			mode_dict = {'0': 'Very Shallow', '1': 'Shallow', '2': 'Medium', '3': 'Deep',
# 						 '4': 'Deeper', '5': 'Very Deep', '6': 'Extra Deep', '7': 'Extreme Deep'}
#
# 			# pulse and swath modes for .kmall (assumed not model-dependent, applicable for all SIS 5 installs)
# 			pulse_dict = {'0': 'CW', '1': 'Mixed', '2': 'FM'}
#
# 			# depth, pulse in pingInfo from MRZ dg; swath mode, freq in IOP dg runtime text (sortDetectionsCoverage)
# 			# swath_dict = {'0': 'Single Swath', '1': 'Dual Swath'}
#
# 			for p in range(len(data[f]['XYZ'])):
# 				# get depth mode from list and add qualifier if manually selected
# 				manual_mode = data[f]['RTP'][p]['depthMode'] >= 100  # check if manual selection
# 				mode_idx = str(data[f]['RTP'][p]['depthMode'])[-1]  # get last character for depth mode
# 				data[f]['XYZ'][p]['PING_MODE'] = mode_dict[mode_idx] + (' (Manual)' if manual_mode else '')
# 				data[f]['XYZ'][p]['PULSE_FORM'] = pulse_dict[str(data[f]['RTP'][p]['pulseForm'])]
#
# 				# store default frequency based on model, update from runtime param text in sortCoverageDetections
# 				# data[f]['XYZ'][p]['FREQUENCY'] = freq_dict[str(data[f]['XYZ'][p]['MODEL'])]
# 				# print('looking at SIS 5 model: ', data[f]['HDR'][p]['echoSounderID'])
# 				data[f]['XYZ'][p]['FREQUENCY'] = freq_dict[str(data[f]['HDR'][p]['echoSounderID'])]
#
# 				if print_updates:
# 					ping = data[f]['XYZ'][p]
# 					print('file', f, 'ping', p, 'is', ping['PING_MODE'], ping['PULSE_FORM'], ping['SWATH_MODE'])
#
# 		else:
# 			print('UNSUPPORTED FTYPE --> NOT INTERPRETING MODES!')
#
# 		if missing_mode:
# 			update_log(self, 'Warning: missing mode info in ' + data[f]['fname'].rsplit('/', 1)[-1] +
# 					   '\nPoint color options may be limited due to missing mode info')
#
# 	if print_updates:
# 		print('\nDone interpreting modes...')
#
# 	return data


# def sortDetections(self, data, print_updates=False):
def sortDetectionsCoverage(self, data, print_updates=False):
	# sort through .all and .kmall data dict and pull out outermost valid soundings, BS, and modes for each ping
	det_key_list = ['fname', 'model', 'datetime', 'date', 'time', 'sn',
					'y_port', 'y_stbd', 'z_port', 'z_stbd', 'bs_port', 'bs_stbd', 'rx_angle_port', 'rx_angle_stbd',
					'ping_mode', 'pulse_form', 'swath_mode', 'frequency',
					'max_port_deg', 'max_stbd_deg', 'max_port_m', 'max_stbd_m',
					'tx_x_m', 'tx_y_m', 'tx_z_m',  'aps_x_m', 'aps_y_m', 'aps_z_m', 'wl_z_m',
					'bytes', 'fsize', 'fsize_wc']  #, 'skm_hdr_datetime', 'skm_raw_datetime']
					# yaw stabilization mode, syn

	det = {k: [] for k in det_key_list}

	# examine detection info across swath, find outermost valid soundings for each ping
	# here, each det entry corresponds to two outermost detections (port and stbd) from one ping, with parameters that
	# are applied for both soundings; detection sorting in the accuracy plotter extends the detection dict for all valid
	# detections in each ping, with parameters extended for each (admittedly inefficient, but easy for later sorting)
	for f in range(len(data)):  # loop through all data
		if print_updates:
			print('Finding outermost valid soundings in file', data[f]['fname'])

		# set up keys for dict fields of interest from parsers for each file type (.all or .kmall)
		ftype = data[f]['fname'].rsplit('.', 1)[1]
		key_idx = int(ftype == 'kmall')  # keys in data dicts depend on parser used, get index to select keys below
		det_int_threshold = [127, 0][key_idx]  # threshold for valid sounding (.all  <128 and .kmall == 0)
		det_int_key = ['RX_DET_INFO', 'detectionType'][key_idx]  # key for detect info depends on ftype
		depth_key = ['RX_DEPTH', 'z_reRefPoint_m'][key_idx]  # key for depth
		across_key = ['RX_ACROSS', 'y_reRefPoint_m'][key_idx]  # key for acrosstrack distance
		bs_key = ['RX_BS', 'reflectivity1_dB'][key_idx]  # key for backscatter in dB
		bs_scale = [0.1, 1][key_idx]  # backscatter scale in X dB; multiply parsed value by this factor for dB
		# bs_key = ['RS_BS', 'reflectivity2_dB'][key_idx]  # key for backscatter in dB TESTING KMALL REFLECTIVITY 2
		angle_key = ['RX_ANGLE', 'beamAngleReRx_deg'][key_idx]  # key for RX angle re RX array

		for p in range(len(data[f]['XYZ'])):  # loop through each ping
			det_int = data[f]['XYZ'][p][det_int_key]  # get detection integers for this ping
			# print('********* ping', p, '************')
			# print('det_int=', det_int)
			# find indices of port and stbd outermost valid detections (detectionType = 0 for KMALL)
			idx_port = 0  # start at port outer sounding
			idx_stbd = len(det_int) - 1  # start at stbd outer sounding

			while det_int[idx_port] > det_int_threshold and idx_port < len(det_int) - 1:
				idx_port = idx_port + 1  # move port idx to stbd if not valid

			while det_int[idx_stbd] > det_int_threshold and idx_stbd > 0:
				idx_stbd = idx_stbd - 1  # move stdb idx to port if not valid

			if idx_port >= idx_stbd:
				print('XYZ datagram for ping', p, 'has no valid soundings... continuing to next ping')
				continue

			if print_updates:
				print('Found valid dets in ping', p, 'PORT i/Y/Z=', idx_port,
					  np.round(data[f]['XYZ'][p][across_key][idx_port]),
					  np.round(data[f]['XYZ'][p][depth_key][idx_port]),
					  '\tSTBD i/Y/Z=', idx_stbd,
					  np.round(data[f]['XYZ'][p][across_key][idx_stbd]),
					  np.round(data[f]['XYZ'][p][depth_key][idx_stbd]))

			# append swath data from appropriate keys/values in data dicts
			det['fname'].append(data[f]['fname'].rsplit('/')[-1])  # store fname for each swath
			det['y_port'].append(data[f]['XYZ'][p][across_key][idx_port])
			det['y_stbd'].append(data[f]['XYZ'][p][across_key][idx_stbd])
			det['z_port'].append(data[f]['XYZ'][p][depth_key][idx_port])
			det['z_stbd'].append(data[f]['XYZ'][p][depth_key][idx_stbd])
			det['bs_port'].append(data[f]['XYZ'][p][bs_key][idx_port]*bs_scale)
			det['bs_stbd'].append(data[f]['XYZ'][p][bs_key][idx_stbd]*bs_scale)
			det['rx_angle_port'].append(data[f]['XYZ'][p][angle_key][idx_port])
			det['rx_angle_stbd'].append(data[f]['XYZ'][p][angle_key][idx_stbd])
			det['ping_mode'].append(data[f]['XYZ'][p]['PING_MODE'])
			det['pulse_form'].append(data[f]['XYZ'][p]['PULSE_FORM'])
			det['fsize'].append(data[f]['fsize'])
			det['fsize_wc'].append(data[f]['fsize_wc'])
			# det['swath_mode'].append(data[f]['XYZ'][p]['SWATH_MODE'])

			if ftype == 'all':  # .all store date and time from ms from midnight
				det['model'].append(data[f]['XYZ'][p]['MODEL'])
				det['sn'].append(data[f]['XYZ'][p]['SYS_SN'])
				dt = datetime.datetime.strptime(str(data[f]['XYZ'][p]['DATE']), '%Y%m%d') + \
					 datetime.timedelta(milliseconds=data[f]['XYZ'][p]['TIME'])
				det['datetime'].append(dt)
				det['date'].append(dt.strftime('%Y-%m-%d'))
				det['time'].append(dt.strftime('%H:%M:%S.%f'))
				det['swath_mode'].append(data[f]['XYZ'][p]['SWATH_MODE'])
				det['frequency'].append(data[f]['XYZ'][p]['FREQUENCY'])
				det['max_port_deg'].append(data[f]['XYZ'][p]['MAX_PORT_DEG'])
				det['max_stbd_deg'].append(data[f]['XYZ'][p]['MAX_STBD_DEG'])
				det['max_port_m'].append(data[f]['XYZ'][p]['MAX_PORT_M'])
				det['max_stbd_m'].append(data[f]['XYZ'][p]['MAX_STBD_M'])
				det['tx_x_m'].append(data[f]['XYZ'][p]['TX_X_M'])
				det['tx_y_m'].append(data[f]['XYZ'][p]['TX_Y_M'])
				det['tx_z_m'].append(data[f]['XYZ'][p]['TX_Z_M'])
				det['wl_z_m'].append(data[f]['XYZ'][p]['WL_Z_M'])
				det['aps_x_m'].append(data[f]['XYZ'][p]['APS_X_M'])
				det['aps_y_m'].append(data[f]['XYZ'][p]['APS_Y_M'])
				det['aps_z_m'].append(data[f]['XYZ'][p]['APS_Z_M'])
				det['bytes'].append(data[f]['XYZ'][p]['BYTES_FROM_LAST_PING'])

			elif ftype == 'kmall':  # .kmall store date and time from datetime object
				det['model'].append(data[f]['HDR'][p]['echoSounderID'])
				det['datetime'].append(data[f]['HDR'][p]['dgdatetime'])
				det['date'].append(data[f]['HDR'][p]['dgdatetime'].strftime('%Y-%m-%d'))
				det['time'].append(data[f]['HDR'][p]['dgdatetime'].strftime('%H:%M:%S.%f'))
				det['aps_x_m'].append(0)  # not needed for KMALL; append 0 as placeholder
				det['aps_y_m'].append(0)  # not needed for KMALL; append 0 as placeholder
				det['aps_z_m'].append(0)  # not needed for KMALL; append 0 as placeholder

				# get first installation parameter datagram, assume this does not change in file
				ip_text = data[f]['IP']['install_txt'][0]

				# get TX array offset text: EM304 = 'TRAI_TX1' and 'TRAI_RX1', EM2040P = 'TRAI_HD1', not '_TX1' / '_RX1'
				ip_tx1 = ip_text.split('TRAI_')[1].split(',')[0].strip()  # all heads/arrays split by comma
				det['tx_x_m'].append(float(ip_tx1.split('X=')[1].split(';')[0].strip()))  # get TX array X offset
				det['tx_y_m'].append(float(ip_tx1.split('Y=')[1].split(';')[0].strip()))  # get TX array Y offset
				det['tx_z_m'].append(float(ip_tx1.split('Z=')[1].split(';')[0].strip()))  # get TX array Z offset
				det['wl_z_m'].append(float(ip_text.split('SWLZ=')[-1].split(',')[0].strip()))  # get waterline Z offset

				# get serial number from installation parameter: 'SN=12345'
				sn = ip_text.split('SN=')[1].split(',')[0].strip()
				det['sn'].append(sn)

				# det['bytes'].append(0)  # bytes since last ping not handled yet for KMALL
				# det['bytes'].append(data[f]['XYZ'][p]['BYTES_FROM_LAST_PING'])
				det['bytes'].append(data[f]['XYZ'][p]['bytes_from_last_ping'])
				# print('at byte logging step, data[f][XYZ][p] =', data[f]['XYZ'][p])

				# det['bytes'].append(data[f]['XYZ'][p]['start_byte'])

				# print('just appended KMALL bytes: ', det['bytes'][-1])

				# get index of latest runtime parameter timestamp prior to ping of interest; default to 0 for cases
				# where earliest pings in file might be timestamped earlier than first runtime parameter datagram
				# print('working on data f IOP dgdatetime:', data[f]['IOP']['dgdatetime'])
				# print('IOP is', data[f]['IOP'])
				# print('IOP keys are:', data[f]['IOP'].keys())
				# IOP_idx = max([i for i, t in enumerate(data[f]['IOP']['dgdatetime']) if
				# 			   t <= data[f]['HDR'][p]['dgdatetime']], default=0)
				# print('IOP dgdatetime =', data[f]['IOP']['header'][0]['dgdatetime'])
				# print('HDR dgdatetime =', data[f]['HDR'][p]['dgdatetime'])


				### ORIGINAL METHOD
				# IOP_times = [data[f]['IOP']['header'][j]['dgdatetime'] for j in range(len(data[f]['IOP']['header']))]
				# IOP_idx = max([i for i, t in enumerate(IOP_times) if
				# 			   t <= data[f]['HDR'][p]['dgdatetime']], default=0)
				#
				# # if data[f]['IOP']['dgdatetime'][IOP_idx] > data[f]['HDR'][p]['dgdatetime']:
				# # 	print('*****ping', p, 'occurred before first runtime datagram; using first RTP dg in file')
				#
				# if data[f]['IOP']['header'][IOP_idx]['dgdatetime'] > data[f]['HDR'][p]['dgdatetime']:
				# 	print('*****ping', p, 'occurred before first runtime datagram; using first RTP dg in file')
				########

				#### TEST FROM SWATH ACC SORTING
				IOP_headers = data[f]['IOP']['header']  # get list of IOP header dicts in new kmall module output
				IOP_datetimes = [IOP_headers[d]['dgdatetime'] for d in range(len(IOP_headers))]
				# print('got IOP datetimes =', IOP_datetimes)

				# print('working on ping header times')
				# print('data[f][HDR] =', data[f]['HDR'])
				# print('HDR ping dgdatetime is', data[f]['HDR'][p]['dgdatetime'])

				# MRZ_headers = data[f]['HDR']['header']
				MRZ_headers = data[f]['HDR']
				MRZ_datetimes = [MRZ_headers[d]['dgdatetime'] for d in range(len(MRZ_headers))]

				# find index of last IOP datagram before current ping, default to first if
				IOP_idx = max([i for i, t in enumerate(IOP_datetimes) if
							   t <= MRZ_datetimes[p]], default=0)

				if IOP_datetimes[IOP_idx] > MRZ_datetimes[p]:
					print('*****ping', p, 'occurred before first runtime datagram; using first RTP dg in file')
				##### END TEST FROM SWATH ACC SORTING


				# get runtime text from applicable IOP datagram, split and strip at keywords and append values
				# rt = data[f]['IOP']['RT'][IOP_idx]  # get runtime text for splitting
				rt = data[f]['IOP']['runtime_txt'][IOP_idx]

				# print('rt = ', rt)

				# dict of keys for detection dict and substring to split runtime text at entry of interest
				rt_dict = {'max_port_deg': 'Max angle Port:', 'max_stbd_deg': 'Max angle Starboard:',
						   'max_port_m': 'Max coverage Port:', 'max_stbd_m': 'Max coverage Starboard:'}

				# iterate through rt_dict and append value from split/stripped runtime text
				# print('starting runtime parsing for kmall file')
				for k, v in rt_dict.items():  # parse only parameters that can be converted to floats
					try:
						det[k].append(float(rt.split(v)[-1].split('\n')[0].strip()))

					except:
						det[k].append('NA')

				# parse swath mode text
				try:
					dual_swath_mode = rt.split('Dual swath:')[-1].split('\n')[0].strip()
					# print('kmall dual_swath_mode =', dual_swath_mode)
					if dual_swath_mode == 'Off':
						swath_mode = 'Single Swath'

					else:
						swath_mode = 'Dual Swath (' + dual_swath_mode + ')'

				except:
					swath_mode = 'NA'

				det['swath_mode'].append(swath_mode)

				# parse frequency from runtime parameter text, if available
				try:
					# print('trying to split runtime text')
					frequency_rt = rt.split('Frequency:')[-1].split('\n')[0].strip().replace('kHz', ' kHz')
					# print('frequency string from runtime text =', frequency_rt)

				except:  # use default frequency stored from interpretMode
					# print('using default frequency')
					pass
					# frequency = 'NA'

				# store parsed freq if not empty, otherwise store default
				frequency = frequency_rt if frequency_rt else data[f]['XYZ'][p]['FREQUENCY']
				det['frequency'].append(frequency)

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

		# print('using bs_key =', bs_key, ' --> bs_port, bs_stbd:', det['bs_port'], det['bs_stbd'])

	if print_updates:
		print('\nDone sorting detections...')

	print('leaving sortDetectionsCoverage with det[frequency] =', det['frequency'])

	return det


# def update_system_info(self, force_update=False):
# 	# update model, serial number, ship, cruise based on availability in parsed data and/or custom fields
# 	if self.custom_info_gb.isChecked():  # use custom info if checked
# 		self.ship_name = self.ship_tb.text()
# 		self.cruise_name = self.cruise_tb.text()
# 		self.model_name = self.model_cbox.currentText()
#
# 	else:  # get info from detections if available
# 		try:  # try to grab ship name from filenames (conventional file naming with ship info after third '_')
# 			temp_ship_name = self.det['fname'][0]  # first fname, remove trimmed suffix/file ext, keep name after 3rd _
# 			self.ship_name = ' '.join(temp_ship_name.replace('_trimmed', '').split('.')[0].split('_')[3:])
#
# 		except:
# 			self.ship_name = 'Ship Name N/A'  # if ship name not available in filename
#
# 		if not self.ship_name_updated or force_update:
# 			self.ship_tb.setText(self.ship_name)  # update custom info text box
# 			update_log(self, 'Updated ship name to ' + self.ship_tb.text() + ' (first file name ending)')
# 			self.ship_name_updated = True
#
# 		try:  # try to get cruise name from Survey ID field in
# 			self.cruise_name = self.data_new[0]['IP_start'][0]['SID'].upper()  # update cruise ID with Survey ID
#
# 		except:
# 			self.cruise_name = 'Cruise N/A'
#
# 		if not self.cruise_name_updated or force_update:
# 			self.cruise_tb.setText(self.cruise_name)  # update custom info text box
# 			update_log(self, 'Updated cruise name to ' + self.cruise_tb.text() + ' (first survey ID found)')
# 			self.cruise_name_updated = True
#
#
# 		try:
# 			# self.model_name = 'EM ' + str(self.data_new[0]['IP_start'][0]['MODEL'])
# 			self.model_name = 'EM ' + str(self.det['model'][0])
#
# 			if not self.model_updated or force_update:
# 				self.model_cbox.setCurrentIndex(self.model_cbox.findText(self.model_name))
# 				update_log(self, 'Updated model to ' + self.model_cbox.currentText() + ' (first model found)')
# 				self.model_updated = True
#
# 		except:
# 			self.model_name = 'Model N/A'


def update_axes(self):
	# adjust x and y axes and plot title
	# update_system_info(self)
	update_system_info(self, self.det, force_update=False, fname_str_replace='_trimmed')
	update_plot_limits(self)
	update_hist_axis(self)
	# update_data_axis(self)

	# set y limits to match across all plots
	self.swath_ax.set_ylim(0, self.swath_ax_margin * self.z_max)  # set depth axis to 0 and 1.1 times max(z)
	self.data_rate_ax1.set_ylim(0, self.swath_ax_margin * self.z_max)  # set data rate yaxis to same as swath_ax
	self.data_rate_ax2.set_ylim(0, self.swath_ax_margin * self.z_max)  # set ping rate yaxis to same as swath_ax
	self.hist_ax.set_ylim(0, self.swath_ax_margin * self.z_max)  # set hist axis to same as swath_ax

	# update x limits
	print('in update_axes, setting new xlims with dr_max and pi_max =', self.dr_max, self.pi_max)
	self.swath_ax.set_xlim(-1 * self.swath_ax_margin * self.x_max, self.swath_ax_margin * self.x_max)
	self.data_rate_ax1.set_xlim(0, self.swath_ax_margin * self.dr_max)
	self.data_rate_ax2.set_xlim(0, self.swath_ax_margin * self.pi_max)

	# self.title_str = 'Swath Width vs. Depth\n' + self.model_name + ' - ' + self.ship_name + ' - ' + self.cruise_name
	# self.title_str_data = 'Data Rate vs. Depth\n' + self.model_name + ' - ' + self.ship_name + ' - ' + self.cruise_name

	# update plot title with default or custom combination of system info fields
	if self.custom_info_gb.isChecked():  # include custom system info that is checked on
		sys_info_list = [['', self.model_name][self.show_model_chk.isChecked()],
						 ['', self.ship_name][self.show_ship_chk.isChecked()],
						 ['', self.cruise_name][self.show_cruise_chk.isChecked()]]
		print('got sys_info_list = ', sys_info_list)
		sys_info_str = ' - '.join([str for str in sys_info_list if str is not ''])

	else:  # otherwise, default to all system info in the title
		sys_info_str = ' - '.join([self.model_name, self.ship_name, self.cruise_name])

	self.title_str = 'Swath Width vs. Depth\n' + sys_info_str
	self.title_str_data = 'Data Rate vs. Depth\n' + sys_info_str

	self.swath_figure.suptitle(self.title_str)
	self.data_figure.suptitle(self.title_str_data)

	self.swath_ax.set(xlabel='Swath Coverage (m)', ylabel='Depth (m)')
	self.hist_ax.set(xlabel='Pings')  #ylabel='Depth (m)')
	self.data_rate_ax1.set(xlabel='Data rate (MB/hr, from ping-to-ping bytes/s)', ylabel='Depth (m)')
	self.data_rate_ax2.set(xlabel='Ping interval (s, first swath of ping cycle)', ylabel='Depth (m)')
	self.time_ax1.set(xlabel='SKM datagram header time',
					  ylabel='Time diff (ms, SKM dg hdr - KM binary sample 0)')

	self.swath_ax.invert_yaxis()  # invert the y axis (and shared histogram axis)
	self.data_rate_ax1.invert_yaxis()
	# self.data_rate_ax2.invert_yaxis()  # shared with data_rate_ax1

	add_ref_filter_text(self)


def update_plot_limits(self):
	# expand custom limits to accommodate new data
	self.x_max_custom = max([self.x_max, self.x_max_custom])
	self.z_max_custom = max([self.z_max, self.z_max_custom])
	self.dr_max_custom = max([self.dr_max, self.dr_max_custom])
	self.pi_max_custom = max([self.pi_max, self.pi_max_custom])

	# if self.x_max > self.x_max_custom or self.z_max > self.z_max_custom:
	# 	self.plot_lim_gb.setChecked(False)
	# 	self.x_max_custom = max([self.x_max, self.x_max_custom])
	# 	self.z_max_custom = max([self.z_max, self.z_max_custom])

	if self.x_max > self.x_max_custom or self.z_max > self.z_max_custom or \
			self.dr_max > self.dr_max_custom or self.pi_max > self.pi_max_custom:
		self.plot_lim_gb.setChecked(False)
		self.x_max_custom = max([self.x_max, self.x_max_custom])
		self.z_max_custom = max([self.z_max, self.z_max_custom])
		self.dr_max_custom = max([self.dr_max, self.dr_max_custom])
		self.pi_max_custom = max([self.pi_max, self.pi_max_custom])

	if self.plot_lim_gb.isChecked():  # use custom plot limits if checked
		self.x_max_custom = int(self.max_x_tb.text())
		self.z_max_custom = int(self.max_z_tb.text())
		self.dr_max_custom = int(self.max_dr_tb.text())
		self.pi_max_custom = int(self.max_pi_tb.text())
		self.x_max = self.x_max_custom / self.swath_ax_margin  # divide custom limit by axis margin (multiplied later)
		self.z_max = self.z_max_custom / self.swath_ax_margin
		self.dr_max = self.dr_max_custom / self.swath_ax_margin
		self.pi_max = self.pi_max_custom / self.swath_ax_margin

	else:  # revert to automatic limits from the data if unchecked, but keep the custom numbers in text boxes
		self.plot_lim_gb.setChecked(False)
		self.max_x_tb.setText(str(int(self.x_max_custom)))
		self.max_z_tb.setText(str(int(self.z_max_custom)))
		self.max_dr_tb.setText(str(int(self.dr_max_custom)))
		self.max_pi_tb.setText(str(int(self.pi_max_custom)))


	print('leaving update_plot_limits with self.dr_max and pi_max =', self.dr_max, self.pi_max)


def update_hist_axis(self):
	# update the sounding distribution axis and scale the swath axis accordingly
	show_hist = self.show_hist_chk.isChecked()
	n_cols = np.power(10, int(self.show_hist_chk.isChecked()))  # 1 or 10 cols for gridspec, hist in last col if shown
	gs = gridspec.GridSpec(1, n_cols)

	# print('n_cols =', n_cols)

	# update swath axis with gridspec (slightly different indexing if n_cols > 1)
	if self.show_hist_chk.isChecked():
		self.swath_ax.set_position(gs[0:n_cols-1].get_position(self.swath_figure))
		self.swath_ax.set_subplotspec(gs[0:n_cols-1])

	else:
		self.swath_ax.set_position(gs[0].get_position(self.swath_figure))
		self.swath_ax.set_subplotspec(gs[0])

	# update hist axis with gridspec and visibility (always last column)
	self.hist_ax.set_visible(show_hist)
	self.hist_ax.set_position(gs[n_cols - 1].get_position(self.swath_figure))
	self.hist_ax.set_subplotspec(gs[n_cols - 1])
	self.hist_ax.yaxis.tick_right()
	self.hist_ax.yaxis.set_label_position("right")
	plt.setp(self.hist_ax.get_yticklabels(), visible=False)  # hide histogram depth labels for space, tidiness

	# update x axis to include next order of magnitude
	(xmin, xmax) = self.hist_ax.get_xlim()
	xmax_log = np.power(10, np.ceil(np.log10(xmax)))
	self.hist_ax.set_xlim(xmin, xmax_log)


def update_solid_color(self, field):  # launch solid color dialog and assign to designated color attribute
	temp_color = QtWidgets.QColorDialog.getColor()
	setattr(self, field, temp_color)  # field is either 'color' (new data) or 'color_arc' (archive data)
	refresh_plot(self, call_source='update_solid_color')


def add_grid_lines(self):
	# adjust gridlines for swath, histogram, and data rate plots
	for ax in [self.swath_ax, self.hist_ax, self.data_rate_ax1, self.data_rate_ax2, self.time_ax1]:
		if self.grid_lines_toggle_chk.isChecked():  # turn on grid lines
			ax.grid()
			ax.grid(which='both', linestyle='-', linewidth='0.5', color='black')
			ax.minorticks_on()

		else:
			ax.grid(False)  # turn off the grid lines
			ax.minorticks_off()


def add_WD_lines(self):
	# add water-depth-multiple lines
	if self.n_wd_lines_gb.isChecked():  # plot WD lines if checked
		n_wd_lines_max = float(self.n_wd_lines_tb_max.text())
		n_wd_lines_int = float(self.n_wd_lines_tb_int.text())

		try:  # loop through multiples of WD (-port, +stbd) and plot grid lines with text
			for n in range(1, int(np.floor(n_wd_lines_max / n_wd_lines_int) + 1)):
				# print('n=', n)
				for ps in [-1, 1]:  # port/stbd multiplier
					self.swath_ax.plot([0, ps * n * n_wd_lines_int * self.swath_ax_margin * self.z_max / 2],
									   [0, self.swath_ax_margin * self.z_max],
									   'k', linewidth=1)

					x_mag = 0.9 * n * n_wd_lines_int * self.z_max / 2  # set magnitude of text locations to 90% of line end
					y_mag = 0.9 * self.z_max

					# keep text locations on the plot
					if x_mag > 0.9 * self.x_max:
						x_mag = 0.9 * self.x_max
						y_mag = 2 * x_mag / (n * n_wd_lines_int)  # scale y location with limited x location

					self.swath_ax.text(x_mag * ps, y_mag, str(n * n_wd_lines_int) + 'X',
									   verticalalignment='center',
									   horizontalalignment='center',
									   bbox=dict(facecolor='white', edgecolor='none',
												 alpha=1, pad=0.0))

		except:
			update_log(self, 'Failure plotting WD lines')


def add_nominal_angle_lines(self):
	# add lines approximately corresponding to nominal swath angles; these are based on plot
	# geometry only and are not RX angles (e.g., due to attitude and refraction)
	if self.angle_lines_gb.isChecked():  # plot swath angle lines if checked
		try:  # loop through beam lines (-port,+stbd) and plot grid lines with text
			angle_lines_max = float(self.angle_lines_tb_max.text())
			angle_lines_int = float(self.angle_lines_tb_int.text())
			for n in range(1, int(np.floor(angle_lines_max / angle_lines_int) + 1)):
				# repeat for desired number of beam angle lines, skip 0
				for ps in [-1, 1]:  # port/stbd multiplier
					x_line_mag = self.swath_ax_margin * self.z_max * np.tan(n * angle_lines_int * np.pi / 180)
					y_line_mag = self.swath_ax_margin * self.z_max
					self.swath_ax.plot([0, ps * x_line_mag], [0, y_line_mag], 'k', linewidth=1)
					x_label_mag = 0.9 * x_line_mag  # set magnitude of text locations to 90% of line end
					y_label_mag = 0.9 * y_line_mag

					# keep text locations on the plot
					if x_label_mag > 0.9 * self.x_max:
						x_label_mag = 0.9 * self.x_max
						y_label_mag = x_label_mag / np.tan(n * angle_lines_int * np.pi / 180)

					self.swath_ax.text(x_label_mag * ps, y_label_mag,
									   str(int(n * angle_lines_int)) + '\xb0',
									   verticalalignment='center', horizontalalignment='center',
									   bbox=dict(facecolor='white', edgecolor='none', alpha=1, pad=0.0))

		except:
			update_log(self, 'Failure plotting the swath angle lines')


def add_legend(self):
	# make legend or colorbar corresponding to clim (depth, backscatter) or cset (depth, swath, pulse mode)
	# for simplicity in handling the legend handles/labels for all combos of [plot axis, data loaded, color mode, and
	# data plotted on top], first apply the same legend to all plots, then update legends for the data rate plot with
	# solid color handles if the user has opted to not match color modes across all plots
	if self.colorbar_chk.isChecked() and self.clim:
		if self.cset:  # clim and cset not empty --> make legend with discrete colors for ping, pulse, or swath mode
			for subplot, params in self.cbar_dict.items():  # set colorbars for each subplot
				if params['cax']:
					params['cax'].remove()

				cbar = params['ax'].legend(handles=self.legend_handles, title=self.legend_label,
										   fontsize=self.cbar_font_size, title_fontsize=self.cbar_title_font_size,
										   loc=params['loc'])
										   # loc=self.cbar_loc)

				params['cax'] = cbar  # store this colorbar

		else:  # cset is empty --> make colorbar for depth or backscatter
			tickvalues = np.linspace(self.clim[0], self.clim[1], 11)
			ticklabels = [str(round(10 * float(tick)) / 10) for tick in tickvalues]

			for subplot, params in self.cbar_dict.items():  # set colorbars for each subplot
				if params['cax']:
					params['cax'].remove()
				# cbaxes = inset_axes(params['ax'], width="2%", height="30%", loc=self.cbar_loc)
				# cbaxes = inset_axes(params['ax'], width=0.20, height="30%", loc=self.cbar_loc)
				cbaxes = inset_axes(params['ax'], width=0.20, height="30%", loc=params['loc'])

				cbar = colorbar.ColorbarBase(cbaxes, cmap=self.cmap, orientation='vertical',
											 norm=colors.Normalize(self.clim[0], self.clim[1]),
											 ticks=tickvalues, ticklocation=params['tickloc']) #''left')

				cbar.ax.tick_params(labelsize=self.cbar_font_size)  # set font size for entries
				cbar.set_label(label=self.legend_label, size=self.cbar_title_font_size)
				cbar.set_ticklabels(ticklabels)

				# invert colorbar axis if last data plotted on top is colored by depth (regardless of background data)
				if self.last_cmode == 'depth':
					cbar.ax.invert_yaxis()  # invert for depth using rainbow_r colormap; BS is rainbow

				params['cax'] = cbar  # store this colorbar


	else:  # solid color for swath plot and data rate plots; FUTURE: add custom text options, useful for comparisons
		print('adding solid color legend to swath ax')
		for subplot, params in self.cbar_dict.items():  # set colorbars for each subplot
			if params['cax']:
				params['cax'].remove()

			# sort legend handles and add legend
			h_dict = sort_legend_labels(self, params['ax'])
			cbar = params['ax'].legend(handles=h_dict.values(), labels=h_dict.keys(),
									   fontsize=self.cbar_font_size, title_fontsize=self.cbar_title_font_size,
									   loc=params['ax'])
									   # loc=self.cbar_loc)

			# cbar = params['ax'].legend(handles=handles, labels=labels,
			# 						   fontsize=self.cbar_font_size, title_fontsize=self.cbar_title_font_size,
			# 						   loc=self.cbar_loc)

			params['cax'] = cbar  # store this colorbar

	# replace data rate plot legends w/ solid color handles if not applying/matching color modes from swath plot
	if not self.match_data_cmodes_chk.isChecked():
		for subplot, params in self.cbar_dict.items():  # set colorbars for each subplot
			if params['ax'] in [self.data_rate_ax1, self.data_rate_ax2]:  # update only data rate axes, not swath ax
				if params['cax']:
					params['cax'].remove()

				# sort legend handles and add legend
				h_dict = sort_legend_labels(self, params['ax'])

				cbar = params['ax'].legend(handles=h_dict.values(), labels=h_dict.keys(),
										   fontsize=self.cbar_font_size, title_fontsize=self.cbar_title_font_size,
										   loc=params['loc'])
										   # loc=self.cbar_loc)

				params['cax'] = cbar  # store this colorbar

				# future: remove empty patches if data was not plotted (all nan, e.g., old archive format)
				# temp_patches = params['cax'].get_patches()
				# print('temp_patches are:', temp_patches)


def sort_legend_labels(self, ax):
	# get reverse sort indices of legend labels to order 'New' and 'Archive' labels/handles, if loaded
	handles, labels = ax.get_legend_handles_labels()
	sort_idx = sorted(range(len(labels)), key=lambda i: labels[i], reverse=True)
	handles = [handles[i] for i in sort_idx]
	labels = [labels[i] for i in sort_idx]
	h_dict = dict(zip(labels, handles))  # make dict of labels and handles to eliminate duplicates

	# future: remove entries that have empty patches / no plotted data
	# return handles, labels
	return h_dict


def save_plot(self):
	# save a .PNG of the coverage plot with a suggested figure name based on system info and plot settings
	fig_str_base = 'swath_width_vs_depth_' + self.model_name.replace('MODEL ', 'MODEL_').replace(" ", "") + "_" + \
				   "_".join([s.replace(" ", "_") for s in [self.ship_name, self.cruise_name]]) + \
				   '_ref_to_' + self.ref_cbox.currentText().lower().replace(" ", "_")

	# sort out the color mode based on which dataset is displayed on top
	color_modes = [self.color_cbox.currentText(), self.color_cbox_arc.currentText()]
	color_str = color_modes[int(self.top_data_cbox.currentText() == 'Archive data')].lower().replace(" ", "_")
	fig_str = fig_str_base + '_color_by_' + color_str

	# sort out whether archive is shown and where
	if self.show_data_chk_arc.isChecked() and self.det_archive:
		if not self.show_data_chk.isChecked():
			fig_str += '_archive_only'

		else:
			fig_str += '_with_archive'

			if self.top_data_cbox.currentText() == 'Archive data':
				fig_str += '_on_top'

	if self.show_hist_chk.isChecked():
		fig_str += '_with_hist'

	fig_name = "".join([c for c in fig_str if c.isalnum() or c in ['-', '_']]) + '.png'  # replace any lingering / \ etc
	# fig_name_data = fig_str_base + '_data_rate.png'  # fig name for data rate plots
	current_path = self.output_dir.replace('\\', '/')
	plot_path = QtWidgets.QFileDialog.getSaveFileName(self, 'Save coverage figure', current_path + '/' + fig_name)
	fname_out = plot_path[0]
	fname_out_data = fname_out.replace('.png', '_data_rate.png')

	if self.standard_fig_size_chk.isChecked():
		orig_size_swath = self.swath_figure.get_size_inches()
		orig_size_data = self.data_figure.get_size_inches()
		update_log(self, 'Resizing image to save... please wait...')
		self.swath_figure.set_size_inches(12, 12)
		self.data_figure.set_size_inches(12, 12)

	self.swath_figure.savefig(fname_out,
							  dpi=600, facecolor='w', edgecolor='k',
							  orientation='portrait', papertype=None, format=None,
							  transparent=False, bbox_inches=None, pad_inches=0.1,
							  frameon=None, metadata=None, bbox='tight')

	self.data_figure.savefig(fname_out_data,
							  dpi=600, facecolor='w', edgecolor='k',
							  orientation='portrait', papertype=None, format=None,
							  transparent=False, bbox_inches=None, pad_inches=0.1,
							  frameon=None, metadata=None, bbox='tight')

	if self.standard_fig_size_chk.isChecked():
		update_log(self, 'Resetting original image size... please wait...')
		self.swath_figure.set_size_inches(orig_size_swath[0], orig_size_swath[1], forward=True)  # forward resize to GUI
		self.data_figure.set_size_inches(orig_size_data[0], orig_size_data[1], forward=True)
		refresh_plot(self, call_source='save_plot')

	update_log(self, 'Saved figure ' + fname_out.rsplit('/')[-1])


def clear_plot(self):
	# clear plot and reset bounds
	self.swath_ax.clear()
	self.hist_ax.clear()
	self.data_rate_ax1.clear()
	self.data_rate_ax2.clear()
	self.x_max = 1
	self.z_max = 1


def archive_data(self):
	# save (pickle) the detection dictionary for future import to compare performance over time
	archive_name = QtWidgets.QFileDialog.getSaveFileName(self, 'Save data...', os.getenv('HOME'),
														 '.PKL files (*.pkl)')

	if not archive_name[0]:  # abandon if no output location selected
		update_log(self, 'No archive output file selected.')
		return

	else:  # archive data to selected file
		fname_out = archive_name[0]
		det_archive = self.det  # store new dictionary that can be reloaded / expanded in future sessions
		det_archive['model_name'] = self.model_name
		det_archive['ship_name'] = self.ship_name
		det_archive['cruise_name'] = self.cruise_name
		output = open(fname_out, 'wb')
		pickle.dump(det_archive, output)
		output.close()
		update_log(self, 'Archived data to ' + fname_out.rsplit('/')[-1])


def load_archive(self):
	# load previously-pickled swath coverage data files and add to plot
	add_cov_files(self, 'Saved swath coverage data (*.pkl)')  # add .pkl files to qlistwidget

	try:  # try to make list of unique archive filenames (used as keys) already in det_archive dict
		fnames_arc = list(set(self.det_archive.keys()))
		print('made list of unique archive filenames already in det_archive dict:', fnames_arc)

	except:
		fnames_arc = []  # self.det_archive has not been created yet
		self.det_archive = {}

	try:
		# fnames_new_pkl = self.get_new_file_list(['.pkl'], fnames_arc)  # list new .pkl files not included in det dict
		fnames_new_pkl = get_new_file_list(self, ['.pkl'], fnames_arc)  # list new .pkl files not included in det dict

		print('returned fnames_new_pkl=', fnames_new_pkl)
	except:
		update_log(self, 'Error loading archive files')
		pass

	for f in range(len(fnames_new_pkl)):  # load archives, append to self.det_archive
		# try to load archive data and extend the det_archive
		fname_str = fnames_new_pkl[f].split('/')[-1]  # strip just the file string for key in det_archive dict
		det_archive_new = pickle.load(open(fnames_new_pkl[f], 'rb'))
		self.det_archive[fname_str] = det_archive_new
		update_log(self, 'Loaded archive ' + fname_str)

	# set show data archive button to True (and cause refresh that way) or refresh plot directly, but not both
	if not self.show_data_chk_arc.isChecked():
		print('setting show_data_chk_arc to True')
		self.show_data_chk_arc.setChecked(True)  # checking show_data_chk_arc will start refresh
		print('show_data_chk_arc is now', self.show_data_chk_arc.isChecked())

	else:
		refresh_plot(self)


def show_archive(self):
	n_plotted = 0
	# print('made it to show_archive with self.det_archive=', self.det_archive)
	# plot archive data underneath 'current' swath coverage data
	try:  # loop through det_archive dict (each key is archive fname, each val is dict of detections)
		# print('in show_archive all keys are:', self.det_archive.keys())
		archive_key_count = 0
		for k in self.det_archive.keys():
			print('in show_archive with k=', k, ' and keys = ', self.det_archive[k].keys())
			n_points = plot_coverage(self, self.det_archive[k], is_archive=True, det_name=k)  # plot det_archive
			n_plotted += n_points
			print('n_plotted in show_archive =', n_plotted, ', calling plot_data_rate')

			plot_data_rate(self, self.det_archive[k], is_archive=True, det_name=k)  # plot det_archive data rate

			print('in show_archive, back from plot_data_rate')

			# print('in show_archive, n_plotted is now', n_plotted)
			self.swath_canvas.draw()
			self.data_canvas.draw()
			archive_key_count += 1
	except:
		error_msg = QtWidgets.QMessageBox()
		error_msg.setText('No archive data loaded.  Please load archive data.')

	return n_plotted


def load_spec(self):
	# load a text file with theoretical performance to be plotted as a line
	add_cov_files(self, 'Theoretical coverage curve (*.txt)')  # add .pkl files to qlistwidget
	fnames_new_spec = get_new_file_list(self, ['.txt'])  # list new .all files not included in det dict

	self.spec = {}

	fnames_new_spec = sorted(fnames_new_spec)

	for i in range(len(fnames_new_spec)):
		# try to load archive data and extend the det_archive
		fname_str = fnames_new_spec[i].split('/')[-1]  # strip just the file string for key in spec dict
		update_log(self, 'Parsing ' + fname_str)

		try:  # try reading file
			f = open(fnames_new_spec[i], 'r')
			data = f.readlines()

		except:
			print('***WARNING: Error reading file', fname_str)

		if len(data) <= 0:  # skip if text file is empty
			print('***WARNING: No data read from file', fname_str)

		else:  # try to read spec name from header and z, x data as arrays
			specarray = np.genfromtxt(fnames_new_spec[i], skip_header=1, delimiter=',')
			self.spec[fname_str] = {}
			self.spec[fname_str]['spec_name'] = data[0].replace('\n', '')  # header includes name of spec
			self.spec[fname_str]['z'] = specarray[:, 0]  # first column is depth in m
			self.spec[fname_str]['x'] = specarray[:, 1]  # second column is total coverage in m

		self.spec_chk.setChecked(True)
		refresh_plot(self, call_source='load_spec')


def add_spec_lines(self):
	# add the specification lines to the plot, if loaded
	if self.spec_chk.isChecked():  # plot spec lines if checked
		try:  # loop through beam lines (-port,+stbd) and plot spec lines with text
			for k in self.spec.keys():
				for ps in [-1, 1]:  # port/stbd multiplier
					x_line_mag = self.spec[k]['x'] / 2
					y_line_mag = self.spec[k]['z']
					self.swath_ax.plot(ps * x_line_mag, y_line_mag, 'r', linewidth=2)

		except:
			update_log(self, 'Failure plotting the specification lines')


def plot_data_rate(self, det, is_archive=False, det_name='detection dictionary'):
	# plot data rate and ping rate from loaded data (only new detections at present)
	print('\nstarting DATA RATE plot for', det_name, ' with len of self.c_all_data_rate =', len(self.c_all_data_rate))

	# return w/o plotting if toggle for this data type (current/archive) is off
	if ((is_archive and not self.show_data_chk_arc.isChecked())
			or (not is_archive and not self.show_data_chk.isChecked())):
		print('returning from data rate plotter because the toggle for this data type is unchecked')
		return

	c_all = deepcopy([self.c_all_data_rate, self.c_all_data_rate_arc][is_archive])
	print('in data rate, is_archive=', is_archive, 'and len(c_all) =', len(c_all))

	# split c_all according to color mode: if numeric, take the mean across port and stbd halves of the list to
	# correspond with z_mean; if alpha mode (e.g., depth mode, where color is 'limegreen'), then take just the first
	# half under of the color list under the assumption that port/stbd soundings from the same ping are associated
	# with the same mode / color value
	idx_split = int(len(c_all)/2)  # index between stbd and port soundings in color data from coverage plot
	try:  # try taking numeric mean (e.g., depth, backscatter)
		c_mean = np.mean([c_all[0:idx_split], c_all[idx_split:]], axis=0)

	except:  # if numeric mean fails, assume text color info
		c_mean = c_all[0:idx_split]

	z_mean = np.mean([np.asarray(det['z_port']), np.asarray(det['z_stbd'])], axis=0)  # this might not be used in final

	# get scale factor for wcd file sizes (first half of sou
	wcd_fac = np.divide(np.asarray(det['fsize_wc']), np.asarray(det['fsize']))  #[0:idx_split]
	print('got wcd_dr_scale with len =', len(wcd_fac), ' = ', wcd_fac)

	# get the datetime for each ping (different formats for older archives)
	try:
		print('trying the newer format')
		time_str = [' '.join([det['date'][i], det['time'][i]]) for i in range(len(det['date']))]
		time_obj = [datetime.datetime.strptime(t, '%Y-%m-%d %H:%M:%S.%f') for t in time_str]
		print('parsed ping time_obj using recent format %Y-%m-%d %H:%M:%S.%f')

	except:
		# date and time might be in old format YYYYMMDD and milliseconds since midnight
		time_obj = [datetime.datetime.strptime(str(date), '%Y%m%d') + datetime.timedelta(milliseconds=ms)
					for date, ms in zip(det['date'], det['time'])]
		print('parsed ping time_obj using older format %Y%m%d + ms since midnight')
		print('first ten times: ', [datetime.datetime.strftime(t, '%Y-%m-%d %H:%M:%S.%f') for t in time_obj[0:10]])

	if not time_obj:
		update_log(self, 'Warning: ' + det_name + ' time format is not recognized (e.g., possibly an old archive '
												  'format); data rate and ping interval will not be plotted')

	sort_idx = np.argsort(time_obj)  # sort indices of ping times (len = ping count)
	time_sorted = [time_obj[i] for i in sort_idx]
	z_mean_sorted = [z_mean[i] for i in sort_idx]
	c_mean_sorted = [c_mean[i] for i in sort_idx]
	fnames_sorted = [det['fname'][i] for i in sort_idx]  # sort filenames by ping sort
	wcd_fac_sorted = [wcd_fac[i] for i in sort_idx]

	# check whether detection dict has the byte field to calculate data rate (older archives may not)
	print('det.keys =', det.keys())
	if 'bytes' in det.keys():
		print('in plot_data_rate, found bytes field with len=', len(det['bytes']), 'in ', det_name)
		if all([b == 0 for b in det['bytes']]):
			# interim .kmall format logging 0 for bytes field; skip this!
			bytes_sorted = (np.nan * np.ones_like(np.asarray(det['bytes']))).tolist()
			update_log(self, 'Warning: ' + det_name + ' bytes between ping datagrams = 0 for all pings (e.g., possibly '
													  'an interim .kmall placeholder in this plotter); data rate will '
													  'not be plotted')

		else:
			bytes_sorted = [det['bytes'][i] for i in sort_idx]

	else:  # bytes field not available; make a nan list for plotting
		print('in plot_data_rate, did not find bytes field in ', det_name)
		bytes_sorted = (np.nan*np.ones(len(det['fname']))).tolist()
		update_log(self, 'Warning: ' + det_name + ' does not included bytes between ping datagrams (e.g., possibly an '
												  'old archive format); data rate will not be plotted')

	# calculate final data rates (no value for first time difference, add a NaN to start to keep same lengths as others
	diff_seconds = [(time_sorted[i] - time_sorted[i-1]).total_seconds() for i in range(1, len(time_sorted))]
	dt_s_list = [np.nan] + diff_seconds
	dt_s = np.asarray(dt_s_list)
	dt_s_final = deepcopy(dt_s)

	# the data rate calculated from swath 1 to swath 2 in dual-swath mode is extremely high due to the short time
	# between time stamps; instead of allowing this to throw off the results, combine the total bytes and time so that
	# the data rate is calculated from first swath to first swath; this is fundamentally different from simply ignoring
	# swaths with short time intervals (e.g., less than 0.1 s) because in that case the data rate may be calculated
	# using only time intervals from the second swath to the first swath, which means the bytes in the first swath (and
	# the relatively short interval between swath 1 and swath 2) are not factored into the data rate calculation,
	# causing it to be lower than reality; the method of summing all bytes and time between first swaths should work
	# for single and dual swath modes

	# step 1: identify the second swaths, if present; if the time difference is less than 1/10th of the previous value,
	# assume it is a second swath in dual swath mode; this is a different approach than checking for a time interval
	# that is greater than 10X the previous value, which would identify swath 1 in dual swath mode but fail in single
	idx_swath_2 = np.append(False, np.less(np.divide(dt_s_final[1:], dt_s_final[0:-1]), 0.1)).astype(int)
	idx_swath_1 = np.logical_not(idx_swath_2).astype(int)
	print('idx_swath_1 =', idx_swath_1)
	print('idx_swath_2 =', idx_swath_2)
	print('bytes_sorted =', bytes_sorted)
	print('dt_s_final =', dt_s_final)

	# step 2: add all bytes since last first swath (i.e., ping cycle data sum, regardless of single or dual swath)
	swath_2_bytes = np.multiply(np.asarray(bytes_sorted), idx_swath_2)  # array of bytes from swath 2 only
	ping_int_bytes = np.add(np.multiply(np.asarray(bytes_sorted), idx_swath_1), np.append(swath_2_bytes[1:], 0))

	# step 3: add all time since last first swath (i.e., ping interval, regardless of single or dual swath)
	swath_2_time = np.multiply(dt_s_final, idx_swath_2)  # array of dt sec from swath 2 only
	ping_int_time = np.add(np.multiply(dt_s_final, idx_swath_1), np.append(swath_2_time[1:], 0))

	# step 4: get data rate between pings
	ping_int_dr = np.divide(ping_int_bytes, ping_int_time)*3600/1000000

	print('ping_int_bytes has len = ', len(ping_int_bytes), ' and = ', ping_int_bytes)
	print('ping_int_time has len = ', len(ping_int_time), ' and = ', ping_int_time)
	print('ping_int_dr has len = ', len(ping_int_dr), ' and = ', ping_int_dr)

	# set time interval thresholds to ignore swaths occurring sooner or later (i.e., second swath in dual swath mode or
	# first ping at start of logging, or after missing several pings, or after gap in recording, etc.)
	# dt_min_threshold = 0.25
	# dt_max_threshold = 35.0
	dt_min_threshold = [self.ping_int_min, float(self.min_ping_int_tb.text())][int(self.ping_int_gb.isChecked())]
	dt_max_threshold = [self.ping_int_max, float(self.max_ping_int_tb.text())][int(self.ping_int_gb.isChecked())]

	outlier_idx = np.logical_or(np.less(dt_s, dt_min_threshold), np.greater(dt_s, dt_max_threshold))
	dt_s_final[outlier_idx] = np.nan  #
	ping_int_dr[outlier_idx] = np.nan  # exclude ping intervals outside desired range
	# print('ping interval outlier idx total nans = ', np.sum(outlier_idx))
	# print('len(ping_int_dr=', len(ping_int_dr))
	# print('len c_all_sorted before setting nans =', len(c_mean_sorted))

	# the data rate results may have two distinct sets of results for a given depth due to the order of datagrams logged
	# in the raw file; for instance, depending on ping rate, there may be one extra position datagram present between
	# some sets of pings and not others, resulting in two distinct trends in the data rate vs depth curve(s); as a test,
	# try a running average window through the data rate time series (so as to average across only pings near each other
	# in time, and not inadvertantly average across pings at the same depth that may have been collected under different
	# runtime parameters and, thus, real time data rates)
	dr = ping_int_dr

	window_len = min(100, len(dr))
	dr_smoothed = np.array([np.nanmean(dr[i:i+window_len]) for i in range(len(dr))])
	dr_smoothed_wcd = np.multiply(dr_smoothed, wcd_fac_sorted)
	dr_smoothed_total = np.add(dr_smoothed, dr_smoothed_wcd)

	print('dr_smoothed = ', dr_smoothed)
	print('dr_smoothed_wcd =', dr_smoothed_wcd)
	print('dr_smoothed_total =', dr_smoothed_total)

	print('len(dr_smoothed) and len(dr_smoothed_wcd) =', len(dr_smoothed), len(dr_smoothed_wcd))
	print('lens of dr_smoothed, dt_s_final, c_mean_sorted, z_mean_sorted, and fnames_sorted = ', len(dr_smoothed),
		  len(dr_smoothed_wcd), len(dt_s_final), len(c_mean_sorted), len(z_mean_sorted), len(fnames_sorted))

	# add filename annotations
	self.fnames_sorted = fnames_sorted
	print('first 30 values:', dr_smoothed[0:30], dt_s_final[0:30], self.fnames_sorted[0:30],
		  c_mean_sorted[0:30], z_mean_sorted[0:30])

	cmode = [self.cmode, self.cmode_arc][int(is_archive)]
	local_label = ('Archive data' if is_archive else 'New data')

	# update x limits for axis resizing during each plot call
	self.dr_max = max([self.dr_max, np.nanmax(np.abs(np.asarray(dr_smoothed)))])
	self.pi_max = max([self.pi_max, np.nanmax(np.abs(np.asarray(dt_s_final)))])

	if self.match_data_cmodes_chk.isChecked() and self.last_cmode != 'solid_color':

		self.h_data_rate_smoothed = self.data_rate_ax1.scatter(dr_smoothed, z_mean_sorted,
															   s=self.pt_size, c=c_mean_sorted, marker='o',
															   label=local_label,
															   vmin=self.clim[0], vmax=self.clim[1], cmap=self.cmap,
															   alpha=self.pt_alpha, linewidths=0)

		self.h_data_rate_smoothed_total = self.data_rate_ax1.scatter(dr_smoothed_total, z_mean_sorted,
																	 s=self.pt_size, c=c_mean_sorted, marker='+',
																	 label=local_label,
																	 vmin=self.clim[0], vmax=self.clim[1], cmap=self.cmap,
																	 alpha=self.pt_alpha, linewidths=0)

		self.h_ping_interval = self.data_rate_ax2.scatter(dt_s_final, z_mean_sorted,
														  s=self.pt_size, c=c_mean_sorted, marker='o',
														  label=local_label,
														  vmin=self.clim[0], vmax=self.clim[1], cmap=self.cmap,
														  alpha=self.pt_alpha, linewidths=0)

		# self.legend_handles_data_rate.append(h_data_rate)  # append handles for legend with 'New data' or 'Archive data'
		self.legend_handles_data_rate = [h for h in self.legend_handles]  # save swath legend handle info for data plots


	else:  # use solid colors for data rate plots (new/archive) if not applying the swath plot color modes
		if is_archive:  # use archive solid color
			c_mean_sorted = np.tile(np.asarray(colors.hex2color(self.color_arc.name())), (len(z_mean_sorted), 1))

		else:  # get new data solid color
			c_mean_sorted = np.tile(np.asarray(colors.hex2color(self.color.name())), (len(z_mean_sorted), 1))

		self.h_data_rate_smoothed = self.data_rate_ax1.scatter(dr_smoothed, z_mean_sorted,
															   s=self.pt_size, c=c_mean_sorted,
															   label=local_label, marker='o',
															   alpha=self.pt_alpha, linewidths=0)

		self.h_data_rate_smoothed_total = self.data_rate_ax1.scatter(dr_smoothed_total, z_mean_sorted,
																	 s=self.pt_size, c=c_mean_sorted,
																	 label=local_label, marker='+',
																	 alpha=self.pt_alpha, linewidths=0)

		self.h_ping_interval = self.data_rate_ax2.scatter(dt_s_final, z_mean_sorted,
														  s=self.pt_size, c=c_mean_sorted,
														  label=local_label,
														  marker='o', alpha=self.pt_alpha, linewidths=0)

		self.legend_handles_data_rate.append(self.h_data_rate_smoothed)  # append handles for legend with 'New data' or 'Archive data'
		# self.legend_handles_data_rate.append(self.h_data_rate_smoothed)  # append handles for legend with 'New data' or 'Archive data'

	# set data rate x max based on actual values
	# self.data_rate_ax1.set_xlim(0.0, np.ceil(np.nanmax(dr_smoothed))*1.1)
	try:
		# self.data_rate_ax1.set_xlim(0.0, np.ceil(np.nanmax(dr_smoothed_total))*1.1)  # try to accommodate wcd total
		self.data_rate_ax1.set_xlim(0.0, self.max_dr*self.swath_ax_margin)  # try to accommodate wcd total

	except:
		self.data_rate_ax1.set_xlim(0.0, np.ceil(np.nanmax(dr_smoothed))*1.1)  # if total with wcd is all nans


	# self.data_rate_ax1.set_ylim(self.swath_ax.get_ylim()[1])  # match depth limit

	# set ping interval x max based on actual values or the filter values
	# ping_int_xlim = [np.nanmax(dt_s_final), float(self.max_ping_int_tb.text())][int(self.ping_int_gb.isChecked())]
	# self.data_rate_ax2.set_xlim(0.0, np.ceil(ping_int_xlim)*1.1)  # add 10% upper xlim margin
	# self.data_rate_ax2.set_ylim(self.swath_ax.get_ylim()[1])  # match depth limit

	self.data_canvas.draw()
	plt.show()


# def plot_data_rate(self, det, is_archive=False, det_name='detection dictionary'):
# 	# plot data rate and ping rate from loaded data (only new detections at present)
# 	# plot data rate with ping-wise data rate for all soundings; this matches the depth range and color limits of the
# 	# coverage plot, but may lead to distinctly different trends in the plot when the port and stbd depths differ but are
# 	# plotted with the same data rate
#
# 	print('\nstarting DATA RATE plot for', det_name, ' with len of self.c_all_data_rate =', len(self.c_all_data_rate))
#
# 	# return w/o plotting if toggle for this data type (current/archive) is off
# 	if ((is_archive and not self.show_data_chk_arc.isChecked())
# 			or (not is_archive and not self.show_data_chk.isChecked())):
# 		print('returning from data rate plotter because the toggle for this data type is unchecked')
# 		return
#
# 	c_all = deepcopy([self.c_all_data_rate, self.c_all_data_rate_arc][is_archive])
#
# 	# calc data rates, then duplicate to apply to port and stbd soundings so data rate depths match coverage depths
# 	print('in data rate, is_archive=', is_archive, 'and len(c_all) =', len(c_all))
#
# 	# get the datetime for each ping (different formats for older archives)
# 	try:
# 		print('trying the newer format')
# 		time_str = [' '.join([det['date'][i], det['time'][i]]) for i in range(len(det['date']))]
# 		time_obj = [datetime.datetime.strptime(t, '%Y-%m-%d %H:%M:%S.%f') for t in time_str]
# 		print('parsed ping time_obj using recent format %Y-%m-%d %H:%M:%S.%f')
#
# 	except:
# 		# date and time might be in old format YYYYMMDD and milliseconds since midnight
# 		time_obj = [datetime.datetime.strptime(str(date), '%Y%m%d') + datetime.timedelta(milliseconds=ms)
# 					for date, ms in zip(det['date'], det['time'])]
# 		print('parsed ping time_obj using older format %Y%m%d + ms since midnight')
# 		print('first ten times: ', [datetime.datetime.strftime(t, '%Y-%m-%d %H:%M:%S.%f') for t in time_obj[0:10]])
#
# 	if not time_obj:
# 		update_log(self, 'Warning: ' + det_name + ' time format is not recognized (e.g., possibly an old archive '
# 												  'format); data rate and ping interval will not be plotted')
#
# 	sort_idx = np.argsort(time_obj)  # sort indices of ping times (len = ping count)
# 	time_sorted = [time_obj[i] for i in sort_idx]
# 	z_all_sorted = [det['z_port'][i] for i in sort_idx] + [det['z_stbd'][i] for i in sort_idx]
# 	c_all_idx_split = int(len(sort_idx)/2)
# 	# c_all_port = [c_all[i] for i in sort_idx]  # sort color for port soundings
# 	# c_all_stbd = [c_all[i] for i in np.add(sort_idx, c_all_idx_split).tolist()]  # sort color for stbd soundings
# 	c_all_sorted = c_all
# 	fnames_sorted = [det['fname'][i] for i in sort_idx]  # sort filenames by ping sort
# 	fnames_all_sorted = fnames_sorted + fnames_sorted  # duplicate sorted filenames to correspond with soundings
#
# 	# check whether detection dict has the byte field to calculate data rate (older archives may not)
# 	print('det.keys =', det.keys())
# 	if 'bytes' in det.keys():
# 		print('in plot_data_rate, found bytes field with len=', len(det['bytes']), 'in ', det_name)
# 		if all([b == 0 for b in det['bytes']]):
# 			# interim .kmall format logging 0 for bytes field; skip this!
# 			# bytes_sorted = (np.nan * np.ones_like(z_mean_sorted)).tolist()
# 			bytes_sorted = (np.nan * np.ones_like(np.asarray(det['bytes']))).tolist()
# 			update_log(self, 'Warning: ' + det_name + ' bytes between ping datagrams = 0 for all pings (e.g., possibly '
# 													  'an interim .kmall placeholder in this plotter); data rate will '
# 													  'not be plotted')
#
# 		else:
# 			bytes_sorted = [det['bytes'][i] for i in sort_idx]
#
# 	else:  # bytes field not available; make a nan list for plotting
# 		print('in plot_data_rate, did not find bytes field in ', det_name)
# 		bytes_sorted = (np.nan*np.ones(len(det['fname']))).tolist()
# 		update_log(self, 'Warning: ' + det_name + ' does not included bytes between ping datagrams (e.g., possibly an '
# 												  'old archive format); data rate will not be plotted')
#
# 	# calculate final data rates (no value for first time difference, add a NaN to start to keep same lengths as others
# 	diff_seconds = [(time_sorted[i] - time_sorted[i-1]).total_seconds() for i in range(1, len(time_sorted))]
# 	# dt_s_list = [diff_seconds[1]] + diff_seconds
# 	dt_s_list = [np.nan] + diff_seconds
# 	dt_s = np.asarray(dt_s_list)
# 	dt_s_final = deepcopy(dt_s)
#
# 	# the data rate calculated from swath 1 to swath 2 in dual-swath mode is extremely high due to the short time
# 	# between time stamps; instead of allowing this to throw off the results, combine the total bytes and time so that
# 	# the data rate is calculated from first swath to first swath; this is fundamentally different from simply ignoring
# 	# swaths with short time intervals (e.g., less than 0.1 s) because in that case the data rate may be calculated
# 	# using only time intervals from the second swath to the first swath, which means the bytes in the first swath (and
# 	# the relatively short interval between swath 1 and swath 2) are not factored into the data rate calculation,
# 	# causing it to be lower than reality; the method of summing all bytes and time between first swaths should work
# 	# for single and dual swath modes
#
# 	# step 1: identify the second swaths, if present; if the time difference is less than 1/10th of the previous value,
# 	# assume it is a second swath in dual swath mode; this is a different approach than checking for a time interval
# 	# that is greater than 10X the previous value, which would identify swath 1 in dual swath mode but fail in single
# 	idx_swath_2 = np.append(False, np.less(np.divide(dt_s_final[1:], dt_s_final[0:-1]), 0.1)).astype(int)
# 	idx_swath_1 = np.logical_not(idx_swath_2).astype(int)
# 	print('idx_swath_1 =', idx_swath_1)
# 	print('idx_swath_2 =', idx_swath_2)
# 	print('bytes_sorted =', bytes_sorted)
# 	print('dt_s_final =', dt_s_final)
#
# 	# step 2: add all bytes since last first swath (i.e., ping cycle data sum, regardless of single or dual swath)
# 	swath_2_bytes = np.multiply(np.asarray(bytes_sorted), idx_swath_2)  # array of bytes from swath 2 only
# 	ping_int_bytes = np.add(np.multiply(np.asarray(bytes_sorted), idx_swath_1), np.append(swath_2_bytes[1:], 0))
#
# 	# step 3: add all time since last first swath (i.e., ping interval, regardless of single or dual swath)
# 	swath_2_time = np.multiply(dt_s_final, idx_swath_2)  # array of dt sec from swath 2 only
# 	ping_int_time = np.add(np.multiply(dt_s_final, idx_swath_1), np.append(swath_2_time[1:], 0))
#
# 	# step 4: get data rate between pings
# 	ping_int_dr = np.divide(ping_int_bytes, ping_int_time)*3600/1000000
#
# 	print('ping_int_bytes has len = ', len(ping_int_bytes), ' and = ', ping_int_bytes)
# 	print('ping_int_time has len = ', len(ping_int_time), ' and = ', ping_int_time)
# 	print('ping_int_dr has len = ', len(ping_int_dr), ' and = ', ping_int_dr)
#
# 	# set time interval thresholds to ignore swaths occurring sooner or later (i.e., second swath in dual swath mode or
# 	# first ping at start of logging, or after missing several pings, or after gap in recording, etc.)
# 	dt_min_threshold = [self.ping_int_min, float(self.min_ping_int_tb.text())][int(self.ping_int_gb.isChecked())]
# 	dt_max_threshold = [self.ping_int_max, float(self.max_ping_int_tb.text())][int(self.ping_int_gb.isChecked())]
#
# 	outlier_idx = np.logical_or(np.less(dt_s, dt_min_threshold), np.greater(dt_s, dt_max_threshold))
# 	print('ping interval outlier idx total nans = ', np.sum(outlier_idx))
#
# 	dt_s_final[outlier_idx] = np.nan  #
# 	ping_int_dr[outlier_idx] = np.nan  # exclude ping intervals outside desired range
#
# 	print('len(ping_int_dr=', len(ping_int_dr))
# 	print('len c_all_sorted before setting nans =', len(c_all_sorted))
#
# 	data_rate_bytes_per_hr_reduced = np.divide(bytes_sorted, dt_s_final)*3600/1000000  # convert bytes/s to MB/hr
#
# 	# the data rate results may have two distinct trends for a given depth due to the order of datagrams logged
# 	# in the raw file; for instance, depending on ping rate, there may be one extra position datagram present between
# 	# some sets of pings and not others, resulting in two distinct trends in the data rate vs depth curve(s); as a test,
# 	# try a running average window through the data rate time series (so as to average across only pings near each other
# 	# in time, and not inadvertantly average across pings at the same depth that may have been collected under different
# 	# runtime parameters and, thus, real time data rates)
# 	dr = ping_int_dr
#
# 	window_len = min(100, len(dr))
# 	dr_smoothed = np.array([np.nanmean(dr[i:i+window_len]) for i in range(len(dr))])
#
# 	print('len(dr_smoothed) =', len(dr_smoothed))
#
# 	idx_nan = np.where(np.isnan(dr))[0]
# 	idx_real = np.where(np.logical_not(np.isnan(dr)))[0]  # idx of real results in data rate (ping count)
#
# 	print('got idx_nan =', idx_nan)
# 	print('got idx_real =', idx_real)
# 	dr_final = dr_smoothed
# 	dt_final = dt_s_final
#
# 	dr_final_all = np.append(dr_final, dr_final)  # duplicate/append data rate results to match len of all soundings
# 	dt_final_all = np.append(dt_final, dt_final)  # duplicate/append data rate results to match len of all soundings
#
# 	c_final_all = c_all_sorted
# 	z_final_all = z_all_sorted
# 	fnames_final_all = np.asarray(fnames_all_sorted)
#
# 	print('lens of dr_final_all, dt_final_all, c_final_all, z_final_all, and fnames_final_all = ',
# 		  len(dr_final_all), len(dt_final_all), len(c_final_all), len(z_final_all), len(fnames_final_all))
#
# 	self.fnames_sorted = fnames_final_all.tolist()
# 	print('first 30 values:', dr_final_all[0:30], dt_final_all[0:30], self.fnames_sorted[0:30],
# 		  c_final_all[0:30], z_final_all[0:30])
#
# 	cmode = [self.cmode, self.cmode_arc][int(is_archive)]
# 	local_label = ('Archive data' if is_archive else 'New data')
#
# 	if self.match_data_cmodes_chk.isChecked() and self.last_cmode != 'solid_color':
# 		# use the colors provided/updated by the latest plot_coverage call
# 		self.h_data_rate_smoothed = self.data_rate_ax1.scatter(dr_final_all, z_final_all,
# 															   s=self.pt_size, c=c_final_all, marker='o',
# 															   label=local_label,
# 															   vmin=self.clim[0], vmax=self.clim[1], cmap=self.cmap,
# 															   alpha=self.pt_alpha, linewidths=0)
#
# 		self.h_ping_interval = self.data_rate_ax2.scatter(dt_final_all, z_final_all,
# 														  s=self.pt_size, c=c_final_all, marker='o',
# 														  label=local_label,
# 														  vmin=self.clim[0], vmax=self.clim[1], cmap=self.cmap,
# 														  alpha=self.pt_alpha, linewidths=0)
#
# 		# self.legend_handles_data_rate.append(h_data_rate)  # append handles for legend with 'New data' or 'Archive data'
# 		self.legend_handles_data_rate = [h for h in self.legend_handles]  # save swath legend handle info for data plots
#
#
# 	else:  # use solid colors for data rate plots (new/archive) if not applying the swath plot color modes
# 		if is_archive:  # use archive solid color
# 			c_all_sorted = np.tile(np.asarray(colors.hex2color(self.color_arc.name())), (len(z_final_all), 1))
#
# 		else:  # get new data solid color
# 			c_all_sorted = np.tile(np.asarray(colors.hex2color(self.color.name())), (len(z_final_all), 1))
#
# 		self.h_data_rate_smoothed = self.data_rate_ax1.scatter(dr_final_all, z_final_all,
# 															   s=self.pt_size, c=c_all_sorted,
# 															   label=local_label, marker='o',
# 															   alpha=self.pt_alpha, linewidths=0)
#
# 		self.h_ping_interval = self.data_rate_ax2.scatter(dt_final_all, z_final_all,
# 														  s=self.pt_size, c=c_all_sorted,
# 														  label=local_label,
# 														  marker='o', alpha=self.pt_alpha, linewidths=0)
#
# 		self.legend_handles_data_rate.append(self.h_data_rate_smoothed)  # append handles for legend with 'New data' or 'Archive data'
#
# 	# set data rate x max based on actual values
# 	self.data_rate_ax1.set_xlim(0.0, np.ceil(np.nanmax(dr_final_all))*1.1)
# 	self.data_rate_ax1.set_ylim(self.swath_ax.get_ylim()[1])  # match depth limit
#
# 	# set ping interval x max based on actual values or the filter values
# 	ping_int_xlim = [np.nanmax(dt_s_final), float(self.max_ping_int_tb.text())][int(self.ping_int_gb.isChecked())]
# 	self.data_rate_ax2.set_xlim(0.0, np.ceil(ping_int_xlim)*1.1)  # add 10% upper xlim margin
# 	self.data_rate_ax2.set_ylim(self.swath_ax.get_ylim()[1])  # match depth limit
#
# 	self.data_canvas.draw()
# 	plt.show()


# def update_annot(self, ind):  # adapted from SO example
# 	print('madee it to UPDATE_ANNOT')
# 	pos = self.h_data_rate_smoothed.get_offsets()[ind["ind"][0]]
# 	self.annot.xy = pos
# 	text = "{}, {}".format(" ".join(list(map(str,ind["ind"]))),
# 						   " ".join([self.fnames_sorted[n] for n in ind["ind"]]))
# 	print('got text:', text)
# 	self.annot.set_text(text)
# 	self.annot.get_bbox_patch().set_facecolor(cmap(norm(c[ind["ind"][0]])))
# 	self.annot.get_bbox_patch().set_alpha(0.4)
# 	print('leaving update_annot')
#
#
# def hover(self, event):  # adapted from SO example
# 	print('made it to HOVER')
# 	vis = self.annot.get_visible()
# 	if event.inaxes == ax:
# 		cont, ind = self.h_data_rate_smoothed.contains(event)
# 		if cont:
# 			update_annot(ind)
# 			self.annot.set_visible(True)
# 			self.data_canvas.draw_idle()
# 		else:
# 			if vis:
# 				self.annot.set_visible(False)
# 				self.data_canvas.draw_idle()
#
# 	# plt.show()


def plot_time_diff(self):
	print('\n\n\n****** in plot_time_diff')

	print('self.skm_time has keys =', self.skm_time.keys())

	for f in self.skm_time.keys():

		print('plotting skm_time for f = ', f)

		print('self.skm_time[f] =', self.skm_time[f])
		print('self.skm_time[f][SKM_header_datetime] =', self.skm_time[f]['SKM_header_datetime'])

		hdr_dt = self.skm_time[f]['SKM_header_datetime']
		raw_dt = self.skm_time[f]['SKM_sample_datetime']
		skm_time_diff_ms = [1000*(hdr_dt[i] - raw_dt[i]).total_seconds() for i in range(len(hdr_dt))]

		# print('got skm_time_diff =', skm_time_diff)

		# skm_time_diff = [self.skm_time[f]['SKM_header_datetime'][i] - self.skm_time[f]['SKM_sample_datetime']
		print('len(skm_time_diff_ms) =', len(skm_time_diff_ms))

		print('got first ten skm_time_diff_ms =', skm_time_diff_ms[0:10])

		# print(' convert to seconds =', skm_time_diff.total_seconds())

		# print('convert to milliseconds =', 1000*skm_time_diff.total_seconds())

		self.time_ax1.plot(self.skm_time[f]['SKM_header_datetime'], skm_time_diff_ms)

def plot_hist(self):
	# plot histogram of soundings versus depth for new and archive data
	z_all_new = []
	z_all_arc = []
	hist_data = []  # list of hist arrays
	labels = []  # label list
	clist = []  # color list

	# add new data only if it exists and is displayed
	if all(k in self.det for k in ['z_port', 'z_stbd']) and self.show_data_chk.isChecked():
		z_all_new.extend(self.det['z_port'] + self.det['z_stbd'])
		labels.append('New')
		clist.append('black')
		hist_data.append(np.asarray(z_all_new))

	if self.show_data_chk_arc.isChecked():  # try to add archive data only if displayed
		for k in self.det_archive.keys():  # loop through all files in det_archive, if any, and add data
			z_all_arc.extend(self.det_archive[k]['z_port'] + self.det_archive[k]['z_stbd'])
		labels.append('Arc.')
		clist.append('darkgray')
		hist_data.append(np.asarray(z_all_arc))

	# print('heading to hist plot, hist_data=', hist_data, 'and clist=', clist)

	z_range = (0, self.swath_ax_margin * self.z_max)  # match z range of swath plot
	if hist_data and clist:
		self.hist_ax.hist(hist_data, range=z_range, bins=30, color=clist, histtype='bar',
						  orientation='horizontal', label=labels, log=True, rwidth=0.40*len(labels))

		if self.colorbar_chk.isChecked():  # add colorbar
			self.hist_legend = self.hist_ax.legend(fontsize=self.cbar_font_size, loc=self.cbar_loc, borderpad=0.03)

			for patch in self.hist_legend.get_patches():  # reduce size of patches to fit on narrow subplot
				patch.set_width(5)
				patch.set_x(10)

def calc_coverage_trend(self, z_all, y_all, is_archive):
	print('attempting to process and export trend for Gap Filler')

	try:
		print('trying to calculate means and medians')
		# bins = np.linspace(min(self.z_all), max(self.z_all), 11)
		bins = np.linspace(min(z_all), max(z_all), 11)
		dz = np.mean(np.diff(bins))
		print('got bins = ', bins, 'with dz = ', dz)
		# y_all_abs = np.abs(self.y_all)
		y_all_abs = np.abs(y_all)

		print('got y_all_abs =', y_all_abs)
		# z_all_dig = np.digitize(self.z_all, bins)
		z_all_dig = np.digitize(z_all, bins)

		print('got z_all_dig =', z_all_dig)
		trend_bin_means = [y_all_abs[z_all_dig == i].mean() for i in range(1, len(bins))]
		# bin_medians = [np.median(y_all_abs[z_all_dig == i]) for i in range(1, len(bins))]
		print('got bin_means = ', trend_bin_means)
		trend_bin_centers = [i + dz/2 for i in bins[:-1]]

		if self.show_coverage_trend_chk.isChecked():
			c_trend = ['black', 'gray'][is_archive]
			trend_bin_means_plot = trend_bin_means + ([-1*i for i in trend_bin_means])
			trend_bin_centers_plot = 2*trend_bin_centers
			self.h_trend = self.swath_ax.scatter(trend_bin_means_plot, trend_bin_centers_plot,
								  marker='o', s=10, c=c_trend)
			# self.h_trend = self.swath_ax.scatter(trend_bin_means, trend_bin_centers,
			# 					  marker='o', s=10, c=c_trend)
			# self.swath_ax.scatter([-1*i for i in trend_bin_means], trend_bin_centers,
			# 					  marker='o', s=10, c=c_trend)

		if is_archive:
			self.trend_bin_centers_arc = trend_bin_centers
			self.trend_bin_means_arc = trend_bin_means

		else:
			self.trend_bin_centers = trend_bin_centers
			self.trend_bin_means = trend_bin_means

	except RuntimeError:
		print('error calculating or plotting Gap Filler coverage')

def export_gap_filler_trend(self):
	# export coverage trend for Gap Filler
	print('attempting to process and export trend for Gap Filler')
	is_archive = str(self.export_gf_cbox.currentText()) == 'Archive'
	print('is_archive =', is_archive)
	z = [self.trend_bin_centers, self.trend_bin_centers_arc][is_archive]
	y = [self.trend_bin_means, self.trend_bin_means_arc][is_archive]

	print('in export_gap_filler_trend, z = ', z, ' and y =', y)

	if z and y:
	# if self.trend_bin_means and self.trend_bin_centers:
	# 	nwd = 2 * np.asarray(self.trend_bin_means) / np.asarray(self.trend_bin_centers)  # calculate water depth multiple
		nwd = 2 * np.asarray(y) / np.asarray(z)  # calculate water depth multiple
		# print('bin centers = ', self.trend_bin_centers)
		# print('bin centers = ')
		# print('bin means = ', self.trend_bin_means)
		print('nwd = ', nwd)

		update_log(self, 'Calculated coverage trend from filtered data')

		trend_name = '_'.join([self.ship_name, self.model_name]) + '_' + [self.cruise_name, 'archive'][is_archive]
		trend_name = "".join([c for c in trend_name if c.isalnum() or c in ['-', '_']]) + '.txt'  # remove any / \ etc

		current_path = self.output_dir.replace('\\', '/')
		trend_path = QtWidgets.QFileDialog.getSaveFileName(self, 'Save trend file', current_path + '/' + trend_name)
		fname_out = trend_path[0]

		print('trend fname_out = ', fname_out)
		# trend_z = np.round([0] + self.trend_bin_centers + [10000]).tolist()
		trend_z = np.round([0] + z + [10000]).tolist()
		trend_y = np.round([5] + nwd.tolist() + [0], decimals=1).tolist()

		print('trend_z =', trend_z)
		print('trend_y =', trend_y)

		trend_fid = open(fname_out, 'w')
		trend_fid.writelines([str(z) + ' ' + str(y) + '\n' for z, y in zip(trend_z, trend_y)])
		trend_fid.close()

	else:
		update_log(self, 'No coverage data available for trend export')

def update_param_log(self, entry, font_color='black'):  # update the acquisition param log
		self.param_log.setTextColor(font_color)
		self.param_log.append(entry)
		QtWidgets.QApplication.processEvents()

def sort_det_time(self):  # sort detections by time (after new files are added)
	print('starting sort_det_time')
	datetime_orig = deepcopy(self.det['datetime'])
	for k, v in self.det.items():
		print('...sorting ', k)
		# self.det[k] = [x for _, x in sorted(zip(self.det['datetime'], self.det[k]))]  #potentially not sorting properly after sorting the 'datetime' field!
		self.det[k] = [x for _, x in sorted(zip(datetime_orig, self.det[k]))]

	print('done sorting detection times')

	# update_param_log(self, 'Acquisition parameters for first ping and all subsequent changes in plotted data:')
	# get_param(self, i=0, update_log=True)

	get_param_changes(self, search_dict={}, update_log=True, include_initial=True,
					  header='\n***COVERAGE RECALCULATED*** Initial settings and all changes in plotted data:\n')

def get_param(self, i=0, nearest='next', update_log=False):  # get the parameters in effect at time dt (datetime)

	if isinstance(i, datetime.datetime):  # datetime format for search
		print('search criterion is datetime object --> will look for params at nearest time (nearest=', nearest, ')')

		if nearest == 'next':  # find first parameter time equal to or after requested time
			j = min([np.argmax(np.asarray(self.det['datetime']) >= i), len(self.det['datetime']) - 1])

		elif nearest == 'prior':  # find last parameter time prior to or equal to requested time
			j = max([0, np.argmax(np.asarray(self.det['datetime']) <= i)])

	elif isinstance(i, int):  # find parameter at given index
		print('search criterion is integer --> will get params at this index')

		if i < 0:
			print('requested index (', i, ') is less than 0; resetting to 0')
			j = 0

		elif i >= len(self.det['datetime']):
			print('requested index (', i, ') exceeds num of pings (', str(len(self.det['datetime'])), ')')
			j = len(self.det['datetime']) -1
			print('setting j to last ping index (', j, ')')

		else:
			j = i

	else:  # requested index not supported
		print('param search index i=', i, 'is not supported (datetime or integer only!)')

	print('found index j=', j)

	self.param_state = dict((k, [self.det[k][j]]) for k in self.param_list)
	print('made self.param_state at j=', j, ' --> ', self.param_state)

	if update_log:
		update_param_log(self, format_param_str(self))

def format_param_str(self, param_dict=[], i=0):  # format fields of params dict for printing / updating log
	if not param_dict:  # default to current param state dict if not specified
		param_dict = deepcopy(self.param_state)
		i = 0

	time_str = param_dict['datetime'][i].strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]  # time string truncated to ms
	param_list = [str(param_dict[k][i]) for k in ['ping_mode', 'pulse_form', 'swath_mode']]
	lim_deg_str = '/'.join([str(float(param_dict[k][i])) for k in ['max_port_deg', 'max_stbd_deg']])
	lim_m_str = '/'.join([str(float(param_dict[k][i])) for k in ['max_port_m', 'max_stbd_m']])

	# format all fields in desired order with delimiters/spacing
	param_list.extend([lim_deg_str, lim_m_str])
	param_log_str = time_str + ': ' + ', '.join([k for k in param_list])

	print(param_log_str)

	return param_log_str

def get_param_changes(self, search_dict={}, update_log=False, header='', include_initial=True):
	# step 1: find changes in params in detection dict (default: report ANY changes satisfying the user's options)
	# step 2: if necessary, confirm ALL user options are satisfied (e.g., find times of specific configurations)

	print('\n*** in get_param_changes, search_dict =', search_dict)

	if search_dict:  # get summary of search criteria to update header in log
		search_str_list = []
		self.param_cond_cbox.currentText().split()[0]
		header = '\n***NEW SEARCH*** Times of changes that satisfy ' + self.param_cond_cbox.currentText().split()[0] +\
				 ' of the following acquisition parameters:\n'

		for p in search_dict.keys():
			search_str_list.append(' '.join([p, search_dict[p]['condition'], search_dict[p]['value']]))
			search_str = ', '.join([s for s in search_str_list if s.find('datetime') < 0])

	else:  # default search for all params of interest if not specified
		search_dict = dict((k, {'value': 'All', 'condition': '=='}) for k in self.param_list)
		print('in get_param_changes, search_dict was not specified --> made search_dict = ', search_dict)

		search_str = ', '.join([p for p in search_dict.keys() if p is not 'datetime'])


	if header == '':  # assume new search header if no header is specified
		header = '\n***NEW SEARCH*** Initial settings and ALL CHANGES to acquisition parameters:\n'
					 # ', '.join([p for p in search_dict.keys() if p is not 'datetime'])

	header = header + search_str  # add search criteria to header

	update_param_log(self, header)

	idx_change = []
	for param, crit in search_dict.items():  # find CHANGES for each parameter of interest, then sort
		print('****** SEARCHING DETECTION DICT FOR PARAMETER, CRIT = ', param, crit)
		if param == 'datetime':  # skip datetime, which changes for every entry
			print('skipping datetime')
			continue

		p_last = self.det[param][0]
		print('first setting = ', p_last)

		# find ALL changes to this parameter, then reduce to those that satisfy the user criteria (ANY or ALL match)
		if param in ['ping_mode', 'swath_mode', 'pulse_form']:  # may need to reduce, e.g., 'Deep (Manual)' to 'Deep'
			idx_temp = [i for i in range(1, len(self.det[param])) if
						self.det[param][i].rsplit('(')[0].strip() != self.det[param][i-1].rsplit('(')[0].strip()]

		else:  # otherwise, compare directly
			idx_temp = [i for i in range(1, len(self.det[param])) if self.det[param][i] != self.det[param][i-1]]

		print('found idx_temp_param for ALL CHANGES =', idx_temp)

		if crit['value'] != 'All':  # find changes that satisfy user options for this setting (e.g., ping_mode == Deep)
			include_initial=False  # do not print initial state (default) unless it matches the search criteria (TBD)
			idx_temp.append(0)  # add index=0 to search initial state for user criteria (will be sorted later)

			print('searching all changes for times when ', param, crit['condition'], crit['value'])

			if param in ['ping_mode', 'swath_mode', 'pulse_form']:  # find modes MATCHING (no other conditions supported yet)
				idx_temp = [i for i in idx_temp if self.det[param][i].rsplit("(")[0].strip() == crit['value']]
				print('updated idx_temp to ', idx_temp)

			elif param in ['max_port_deg', 'max_stbd_deg', 'max_port_m', 'max_stbd_m']:
				print('working on comparing swath limits...')

				if crit['condition'] == '==':
					print('looking for swath limits that EQUAL the user value')
					idx_temp = [i for i in idx_temp if float(self.det[param][i]) == float(crit['value'])]
					print('updated idx_temp = ', idx_temp)

				elif crit['condition'] == '<=':
					print('looking for swath limits that are LESS THAN OR EQUAL TO the user value')
					idx_temp = [i for i in idx_temp if float(self.det[param][i]) <= float(crit['value'])]
					print('updated idx_temp = ', idx_temp)

				elif crit['condition'] == '>=':
					print('looking for swath limits that are GREATER THAN OR EQUAL RO the user value')
					idx_temp = [i for i in idx_temp if float(self.det[param][i]) >= float(crit['value'])]
					print('updated idx_temp = ', idx_temp)

				else:
					print('this condition was not found --> ', crit['condition'])

		print('param fits criteria at idx=', idx_temp, ':', ' --> '.join([str(self.det[param][j]) for j in idx_temp]))

		idx_change.extend(idx_temp)

	idx_change_set = sorted([i for i in set(idx_change)])  # sorted unique indices of ANY changes (default to report)

	idx_match_all = []  # if necessary, review times to see whether ALL search criteria are satisfied
	if self.param_cond_cbox.currentText().split()[0].lower() == 'all':  # user wants ALL search criteria satisfied
		print('looking for change indices that satisfy ALL search criteria')
		for i in idx_change_set:  # review the parameters of interest at each time and keep if ALL are satisfied
			all_match = True
			get_param(self, i)
			print('Comparing ALL params for index ', i, 'where param_state =', self.param_state)

			for param, crit in search_dict.items():  # verify all params match user options at this index
				print('searching param, crit =', param, crit)

				if crit['value'] != 'All':  # check specific parameter matches (all_match stays true if "All" allowed
					print('SPECIFIC crit[value] =', crit['value'])

					if param in ['ping_mode', 'swath_mode', 'pulse_form']:
						all_match = self.det[param][i].rsplit("(")[0].strip() == crit['value']

					elif param in ['max_port_deg', 'max_stbd_deg', 'max_port_m', 'max_stbd_m']:
						if crit['condition'] == '==':
							all_match = float(self.det[param][i]) == float(crit['value'])

						elif crit['condition'] == '<=':
							all_match = float(self.det[param][i]) <= float(crit['value'])

						elif crit['condition'] == '>=':
							all_match = float(self.det[param][i]) >= float(crit['value'])

				print('    just finished comparison, all_match =', all_match)

				if not all_match:  # break the param search loop on this index if anything does not match
					print('**** params do not all match at index', i)
					break

			if all_match:
				idx_match_all.append(i)  # append this index only if everything matched (param search loop was not broken)
				print('all matched, updated idx_match_all to', idx_match_all)

		idx_change_set = sorted([i for i in set(idx_match_all)])  # sorted unique indices when ALL parameters match

	for p in self.param_list:  # update the param change dict
		self.param_changes[p] = [self.det[p][i] for i in idx_change_set]

	print('got idx_change = ', idx_change)
	print('got idx_change_set = ', idx_change_set)
	print('updated self.param_changes =', self.param_changes)

	if include_initial:  # print the initial state if desired
		get_param(self, i=0, update_log=True)

	if update_log:
		print('starting to update log')
		if len(self.param_changes['datetime']) > 0:
			for i in range(len(self.param_changes['datetime'])):
				print('calling update_param_log')
				update_param_log(self, format_param_str(self, param_dict=self.param_changes, i=i))

			update_param_log(self, 'End of search results...')

		else:
			update_param_log(self, 'No results...')


def update_param_search(self, update_log=True):  # update runtime param search criteria selected by the user
	self.param_dict = {'ping_mode': {'chk': self.p1_chk.isChecked(), 'value': self.p1_cbox.currentText(), 'condition': '=='},
					   'swath_mode': {'chk': self.p2_chk.isChecked(), 'value': self.p2_cbox.currentText(), 'condition': '=='},
					   'pulse_form': {'chk': self.p3_chk.isChecked(), 'value': self.p3_cbox.currentText(), 'condition': '=='},
					   'max_port_deg': {'chk': self.p4_chk.isChecked(), 'value': self.p4_tb.text(), 'condition': self.p4_cbox.currentText()},
					   'max_stbd_deg': {'chk': self.p4_chk.isChecked(), 'value': self.p4_tb.text(), 'condition': self.p4_cbox.currentText()},
					   'max_port_m': {'chk': self.p5_chk.isChecked(), 'value': self.p5_tb.text(), 'condition': self.p5_cbox.currentText()},
					   'max_stbd_m': {'chk': self.p5_chk.isChecked(), 'value': self.p5_tb.text(), 'condition': self.p5_cbox.currentText()}}

	print('made self.param_dict =', self.param_dict)

	if self.param_search_gb.isChecked():  # make a custom search dict to pass to get_param_changes
		search_dict = {}
		for param, crit in self.param_dict.items():
			if crit['chk']:
				search_dict[param] = crit
				print('search_dict is now', search_dict)

	else:  # user has not specified parameters; search all parameters
		print('going to use the default param_list')
		search_dict = deepcopy(self.param_dict)

	get_param_changes(self, search_dict=search_dict, update_log=True)


def save_param_log(self):
	# save the acquisition parameter search log to a text file
	# param_log_name = QtWidgets.QFileDialog.getSaveFileName(self, 'Save parameter log...', os.getenv('HOME'),
	# 													   '.TXT files (*.txt)')
	param_log_name = QtWidgets.QFileDialog.getSaveFileName(self, 'Save parameter log...', 'runtime_parameter_log.txt',
														   '.TXT files (*.txt)')

	if not param_log_name[0]:  # abandon if no output location selected
		update_log(self, 'No parameter log output file selected.')
		return

	else:  # save param log to text file
		fname_out = param_log_name[0]

		with open(fname_out, 'w') as param_log_file:
			param_log_file.write(str(self.param_log.toPlainText()))

		update_log(self, 'Saved parameter log to ' + fname_out.rsplit('/')[-1])
		update_param_log(self, '\n*** SAVED PARAMETER LOG *** --> ' + fname_out)

