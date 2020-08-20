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
# import datetime
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
from multibeam_tools.libs.swath_fun import *
from common_data_readers.python.kongsberg.kmall import kmall
from time import process_time
from scipy.interpolate import interp1d
from copy import deepcopy
import struct


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
	self.clim_last_user = {'depth': [0, 1000], 'backscatter': [-50, -20]}
	self.last_cmode = 'depth'
	self.cbarbase = None  # initial colorbar
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
	self.cmode_list = ['Depth', 'Backscatter', 'Ping Mode', 'Pulse Form', 'Swath Mode', 'Solid Color']
	self.top_data_list = []
	self.clim_list = ['All data', 'Filtered data', 'Fixed limits']
	self.sis4_tx_z_field = 'S1Z'  # .all IP datagram field name for TX array Z offset (meters +down from origin)
	self.sis4_waterline_field = 'WLZ'  # .all IP datagram field name for waterline Z offset (meters +down from origin
	self.depth_ref_list = ['Waterline', 'Origin', 'TX Array', 'Raw Data']


def init_swath_ax(self):  # set initial swath parameters
	self.swath_ax = self.swath_figure.add_subplot(111)
	self.x_max = 1
	self.z_max = 1
	self.x_max_custom = self.x_max  # store future custom entries
	self.z_max_custom = self.z_max
	self.max_x_tb.setText(str(self.x_max))
	self.max_z_tb.setText(str(self.z_max))
	update_color_modes(self)
	self.clim = []
	self.clim_all_data = []
	self.cset = []
	self.cruise_name = ''
	self.n_wd_max = 8
	self.nominal_angle_line_interval = 15  # degrees between nominal angle lines
	self.nominal_angle_line_max = 75  # maximum desired nominal angle line
	self.swath_ax_margin = 1.1  # scale axes to multiple of max data in each direction
	add_grid_lines(self)
	update_axes(self)
	self.color = QtGui.QColor(0, 0, 0)  # set default solid color to black for new data
	self.color_arc = QtGui.QColor('darkGray')
	self.color_cbox_arc.setCurrentText('Solid Color')


def add_cov_files(self, ftype_filter, input_dir='HOME', include_subdir=False, ):
	# add files with extensions in ftype_filter from input_dir and subdir if desired
	fnames = add_files(self, ftype_filter, input_dir, include_subdir)
	update_file_list(self, fnames)


def remove_cov_files(self, clear_all=False):
	# remove selected files or clear all files, update det and spec dicts accordingly
	removed_files = remove_files(self, clear_all)

	if clear_all:  # clear all
		self.det = {}
		self.det_archive = {}
		self.spec = {}
		update_log(self, 'Cleared all files')
		self.current_file_lbl.setText('Current File [0/0]:')
		self.calc_pb.setValue(0)

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
	tic = process_time()

	if validate_filters:
		if not validate_filter_text(self):  # validate user input, do not refresh until all float(input) works for all input
			update_log(self, '***WARNING: Invalid filter input; valid input required to refresh plot')
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
		print('in refresh plot, calling show_archive to allow new data on top')
		n_plotted_arc = show_archive(self)
		print('n_plotted_arc = ', n_plotted_arc)

	if self.det:  # default: plot any available new data
		print('calling plot_coverage')
		n_plotted = plot_coverage(self, self.det, False)
		print('n_plotted = ', n_plotted)

	if self.top_data_cbox.currentText() == 'Archive data':  # option: plot archive data last on top of any new data
		print('calling show_archive')
		n_plotted_arc = show_archive(self)
		print('n_plotted_arc = ', n_plotted_arc)

	update_axes(self)  # update axes to fit all loaded data
	add_grid_lines(self)  # add grid lines
	add_WD_lines(self)  # add water depth-multiple lines over coverage
	add_nominal_angle_lines(self)  # add nominal swath angle lines over coverage
	add_legend(self)  # add legend or colorbar
	add_spec_lines(self)  # add specification lines if loaded
	self.swath_canvas.draw()  # final update for the swath canvas

	toc = process_time()
	refresh_time = toc - tic
	if print_time:
		print('got refresh_time=', refresh_time)
		# update_log(self, 'testing')
		update_log(self, 'Updated plot (' + str(n_plotted) + ' new, ' +
				   str(n_plotted_arc) + ' archive soundings; ' + "%.2f" % refresh_time + ' s)')


def update_color_modes(self, update_clim_tb=False):
	# update color modes for the new data and archive data
	self.color_cbox.setEnabled(self.show_data_chk.isChecked())
	self.cmode = self.color_cbox.currentText()  # get the currently selected color mode
	self.cmode = self.cmode.lower().replace(' ', '_')  # format for comparison to list of modes below
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


def plot_coverage(self, det, is_archive=False, print_updates=False, depth_ref='origin'):
	# plot the parsed detections from new or archive data dict; return the number of points plotted after filtering
	# tic = process_time()

	# if print_updates:
	print('\nstarting PLOT_COVERAGE with', ['NEW', 'ARCHIVE'][int(is_archive)], 'data')

	# consolidate data from port and stbd sides for plotting
	y_all = det['y_port'] + det['y_stbd']  # acrosstrack distance from TX array (.all) or origin (.kmall)
	z_all = det['z_port'] + det['z_stbd']  # depth from TX array (.all) or origin (.kmall)
	bs_all = det['bs_port'] + det['bs_stbd']  # reported backscatter amplitude

	# calculate simplified swath angle from raw Z, Y data to use for angle filtering and comparison to runtime limits
	# Kongsberg angle convention is right-hand-rule about +X axis (fwd), so port angles are + and stbd are -
	angle_all = (-1 * np.rad2deg(np.arctan2(y_all, z_all))).tolist()  # multiply by -1 for Kongsberg convention

	# get file-specific, ping-wise adjustments to bring Z and Y into desired reference frame
	dx_ping, dy_ping, dz_ping = adjust_depth_ref(det, depth_ref=self.ref_cbox.currentText().lower())

	print('dz_ping has len', len(dz_ping))
	# print('got dy_ping=', dy_ping)
	# print('got dz_ping=', dz_ping)
	print('first 20 of xline[z]=', z_all[0:20])
	print('first 20 of dz =', dz_ping[0:20])
	# print('got dy_ping=', dy_ping)
	# print('got dz_ping=', dz_ping)
	z_all = [z + dz for z, dz in zip(z_all, dz_ping + dz_ping)]  # add dz (per ping) to each z (per sounding)
	y_all = [y + dy for y, dy in zip(y_all, dy_ping + dy_ping)]  # add dy (per ping) to each y (per sounding)

	# DEPRECATED: original RX beam angle method (results in uneven filtering, depending on RX array angles and attitude)
	# some early archives do not include RX beam angles and/or runtime parameters for user-defined swath limits;
	# if RX angles are not available, calculate approximate angles from sounding X and Z; note that refraction,
	# attitude, and install angles will cause differences from the RX angles parsed from file (re: RX array)
	# try:
	# 	rx_angle_all = det['rx_angle_port'] + det['rx_angle_stbd']
	# 	if print_updates:
	# 		print('rx_angles found --> rx_angle_all[0:50]=', rx_angle_all[0:50])
	# 		print('rx_angles found --> rx_angle_all[-50:]=', rx_angle_all[-50:])
	#
	# except:
	# 	# Kongsberg angle convention is right-hand-rule about +X axis (fwd), so port angles are + and stbd are -
	# 	# if RX angles not available, substitute angles calculated from depth and acrosstrack distance
	# 	rx_angle_all = deepcopy(angle_all)
	#
	# 	update_log(self, 'No RX beam angles' + (' in archive data' if is_archive else '') +
	# 			   '; calculating approx. angles from X and Z')
	#
	# 	if print_updates:
	# 		print('copied rx_angle_all = angle_all with len', len(rx_angle_all))
	# 		print('rx_angles copied --> rx_angle_all[0:50]=', rx_angle_all[0:50])
	# 		print('rx_angles copied --> rx_angle_all[-50:]=', rx_angle_all[-50:])

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
		print('len of xall before filtering:', len(y_all))

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
		lims = [10 * float(self.min_bs_tb.text()), 10 * float(self.max_bs_tb.text())]
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
				# rtp_cov_idx_port = np.greater_equal(np.asarray(y_all),
				# 									-1 * np.asarray(2 * det['max_port_m']) + self.rx_cov_buffer)
				rtp_cov_idx_port = np.greater_equal(np.asarray(y_all),
													-1 * np.asarray(2 * det['max_port_m']) - self.rx_cov_buffer)
				# rtp_cov_idx_stbd = np.less_equal(np.asarray(y_all),
				# 								 np.asarray(2 * det['max_stbd_m']) - self.rx_cov_buffer)
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

	# if print_updates:
	# 	print('sum(filter_idx)=', np.sum(filter_idx))
	# 	print('BEFORE APPLYING IDX: len y_all, z_all, angle_all, bs_all=',
	# 		  len(y_all), len(z_all), len(angle_all), len(bs_all))

	if print_updates:
		print('sum(filter_idx)=', np.sum(filter_idx))
		print('BEFORE APPLYING IDX: len y_all, z_all, angle_all, bs_all=',
			  len(y_all), len(z_all), len(angle_all), len(bs_all))

	y_all = np.asarray(y_all)[filter_idx].tolist()
	z_all = np.asarray(z_all)[filter_idx].tolist()
	# rx_angle_all = np.asarray(rx_angle_all)[filter_idx].tolist()  # RX angle is not used after filtering
	angle_all = np.asarray(angle_all)[filter_idx].tolist()
	bs_all = np.asarray(bs_all)[filter_idx].tolist()

	if print_updates:
		print('AFTER APPLYING IDX: len y_all, z_all, angle_all, bs_all=',
			  len(y_all), len(z_all), len(angle_all), len(bs_all))

	# after filtering, get color mode and set up color maps and legend
	cmode = [self.cmode, self.cmode_arc][is_archive]  # get user selected color mode for local use

	# set point size; slider is on [1-11] for small # of discrete steps; square slider value for real pt size
	pt_size = np.square(float(self.pt_size_cbox.currentText()))
	pt_alpha = np.divide(float(self.pt_alpha_cbox.currentText()), 100)

	# set the color map, initialize color limits and set for legend/colorbars (will apply to last det data plotted)
	self.cmap = 'rainbow'
	self.clim = []
	# self.cset = None
	self.cset = []
	self.legend_label = ''
	self.last_cmode = cmode  # reset every plot call; last (top) plot updates for add_legend and update_color_limits

	# set color maps based on combobox selection after filtering data
	if cmode == 'depth':
		c_all = z_all  # set color range to depth range

		if len(c_all) > 0:  # if there is at least one sounding, set clim and store for future reference
			self.clim = [min(c_all), max(c_all)]
			self.last_depth_clim = deepcopy(self.clim)

		else:  # use last known depth clim to avoid errors in scatter
			self.clim = deepcopy(self.last_depth_clim)

		self.cmap = self.cmap + '_r'  # reverse the color map so shallow is red, deep is blue
		self.legend_label = 'Depth (m)'

	elif cmode == 'backscatter':
		c_all = [int(bs) / 10 for bs in bs_all]  # convert to int, divide by 10 (BS reported in 0.1 dB)
		self.clim = [-50, -20]

		# use backscatter filter limits for color limits
		if self.bs_gb.isChecked() and self.clim_cbox.currentText() == 'Filtered data':
			self.clim = [float(self.min_bs_tb.text()), float(self.max_bs_tb.text())]

		self.legend_label = 'Reported Backscatter (dB)'

	elif np.isin(cmode, ['ping_mode', 'pulse_form', 'swath_mode']):
		# modes are listed per ping; append ping-wise setting to correspond with y_all, z_all, angle_all, bs_all
		mode_all = det[cmode] + det[cmode]
		mode_all = np.asarray(mode_all)[filter_idx].tolist()  # filter mode_all as applied for z, x, bs, angle, etc.
		print('heading into cmode selection with mode_all=', mode_all)

		if cmode == 'ping_mode':  # define dict of depth modes (based on EM dg format 01/2020) and colors
			c_set = {'Very Shallow': 'red', 'Shallow': 'darkorange', 'Medium': 'gold',
					 'Deep': 'limegreen', 'Deeper': 'darkturquoise', 'Very Deep': 'blue',
					 'Extra Deep': 'indigo', 'Extreme Deep': 'black'}
			self.legend_label = 'Depth Mode'

		elif cmode == 'pulse_form':  # define dict of pulse forms and colors
			c_set = {'CW': 'red', 'Mixed': 'limegreen', 'FM': 'blue'}  # set of pulse forms
			self.legend_label = 'Pulse Form'

		elif cmode == 'swath_mode':  # define dict of swath modes and colors
			# Dual Swath is parsed as Fixed or Dynamic but generalized here
			# c_set = {'Single Swath': 'red', 'Dual Swath (Fixed)': 'limegreen', 'Dual Swath (Dynamic)': 'blue'}
			c_set = {'Single Swath': 'red', 'Dual Swath': 'blue'}
			self.legend_label = 'Swath Mode'

		# get integer corresponding to mode of each detection; as long as c_set is consistent, this should keep
		# color coding consistent for easier comparison of plots across datasets with different modes present
		# some modes incl. parentheses as parsed, e.g., 'Dual Swath (Dynamic)' and 'Dual Swath (Fixed)'; entries are
		# split/stripped in mode_all to the 'base' mode, e.g., 'Dual Swath' for comparison to simpler c_set dict
		mode_all_base = [m.split('(')[0].strip() for m in mode_all]
		c_all = [c_set[mb] for mb in mode_all_base]
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

	# downsample using nearest neighbor interpolation (non-random approach to handle non-integer decimation factor)
	# idx_dec = np.aran(0,len(y_all),1)

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

	# original method, could not handle text color modes
		# print('idx_all has len', len(idx_all), 'and =', idx_all)
		# print('idx_dec has len', len(idx_dec), 'and =', idx_dec)
		# print('num nans in y_all:', np.sum(np.isnan(np.asarray(y_all))))
		# print('num nans in z_all:', np.sum(np.isnan(np.asarray(z_all))))
		# print('num nans in c_all:', np.sum(np.isnan(np.asarray(c_all))))
		# y_dec = interp1d(idx_all, y_all, kind='nearest')
		# z_dec = interp1d(idx_all, z_all, kind='nearest')
		# c_dec = interp1d(idx_all, c_all, kind='nearest')

		# apply final decimation and update log with plotting point count
		# y_all = y_dec(idx_dec).tolist()
		# z_all = z_dec(idx_dec).tolist()
		# c_all = c_dec(idx_dec).tolist()

	self.n_points = len(y_all)

	# plot y_all vs z_all using colormap c_all
	if cmode == 'solid_color':  # plot solid color if selected
		# get new or archive solid color, convert c_all to array to avoid warning
		c_all = colors.hex2color([self.color.name(), self.color_arc.name()][int(is_archive)])
		c_all = np.tile(np.asarray(c_all), (len(y_all), 1))

		print('cmode is solid color, lengths are', len(y_all), len(z_all), len(c_all))
		self.mappable = self.swath_ax.scatter(y_all, z_all, s=pt_size, c=c_all,
											  marker='o', alpha=pt_alpha, linewidths=0)
		self.swath_canvas.draw()

	else:  # plot other color scheme, specify vmin and vmax from color range
		if cmode in ['ping_mode', 'swath_mode', 'pulse_form']:  # generate patches for legend with modes
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
		self.mappable = self.swath_ax.scatter(y_all, z_all, s=pt_size, c=c_all,
											  marker='o', alpha=pt_alpha, linewidths=0,
											  vmin=self.clim[0], vmax=self.clim[1], cmap=self.cmap)

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

		# update progress bar and log
		self.calc_pb.setValue(0)  # reset progress bar to 0 and max to number of files
		self.calc_pb.setMaximum(len(fnames_new))

		for f in range(len(fnames_new)):
			fname_str = fnames_new[f].rsplit('/')[-1]
			self.current_file_lbl.setText('Parsing new file [' + str(f+1) + '/' + str(num_new_files) + ']:' + fname_str)
			QtWidgets.QApplication.processEvents()
			ftype = fname_str.rsplit('.', 1)[-1]

			if ftype == 'all':
				# data_new[f] = parseEMswathwidth.parseEMswathwidth(fnames_new[f], print_updates=self.print_updates)
				data_new[f] = parseEMswathwidth(self, fnames_new[f], print_updates=self.print_updates)

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

		self.data_new = interpretMode(self, data_new, print_updates=self.print_updates)  # True)
		det_new = sortDetections(self, data_new, print_updates=self.print_updates)  # True)

		if len(self.det) is 0:  # if detection dict is empty with no keys, store new detection dict
			self.det = det_new

		else:  # otherwise, append new detections to existing detection dict
			for key, value in det_new.items():  # loop through the new data and append to existing self.det
				self.det[key].extend(value)

		update_log(self, 'Finished calculating coverage from ' + str(num_new_files) + ' new file(s)')
		self.current_file_lbl.setText('Current File [' + str(f + 1) + '/' + str(num_new_files) +
									  ']: Finished calculating coverage')

		# set show data button to True (and cause refresh that way) or refresh plot directly, but not both
		if not self.show_data_chk.isChecked():
			self.show_data_chk.setChecked(True)
		else:
			refresh_plot(self, print_time=True, call_source='calc_coverage')

	self.calc_coverage_btn.setStyleSheet("background-color: none")  # reset the button color to default


def parseEMswathwidth(self, filename, print_updates=False):
	# if print_updates:
	# print("\nParsing file:", filename)

	# Open and read the .all file
	# filename = '0248_20160911_191203_Oden.all'
	f = open(filename, 'rb')
	raw = f.read()
	len_raw = len(raw)

	# initialize data dict with remaining datagram fields
	data = {'fname': filename, 'XYZ': {}, 'RTP': {}, 'RRA': {}, 'IP': {}}

	# Declare counters for dg starting byte counter and dg processing counter
	dg_start = 0  # datagram (starting with STX = 2) starts at byte 4
	dg_count = 0
	parse_prog_old = -1

	loop_num = 0

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

			# Parse RUNTIME PARAM datagram PYTHON 3
			if dg_ID == 82:
				data['RTP'][len(data['RTP'])] = multibeam_tools.libs.parseEM.RTP_dg(dg)

			# Parse XYZ 88 datagram PYTHON 3
			if dg_ID == 88:
				XYZ_temp = multibeam_tools.libs.parseEM.XYZ_dg(dg, parse_outermost_only=True)
				if XYZ_temp != []:  # store only if valid soundings are found (parser returns empty otherwise)
					data['XYZ'][len(data['XYZ'])] = XYZ_temp

					# store last RTP MODE for each ping
					data['XYZ'][len(data['XYZ']) - 1]['MODE'] = data['RTP'][len(data['RTP']) - 1]['MODE']
					data['XYZ'][len(data['XYZ']) - 1]['MAX_PORT_M'] = data['RTP'][len(data['RTP']) - 1][
						'MAX_PORT_SWATH']
					data['XYZ'][len(data['XYZ']) - 1]['MAX_PORT_DEG'] = data['RTP'][len(data['RTP']) - 1][
						'MAX_PORT_COV']
					data['XYZ'][len(data['XYZ']) - 1]['MAX_STBD_M'] = data['RTP'][len(data['RTP']) - 1][
						'MAX_STBD_SWATH']
					data['XYZ'][len(data['XYZ']) - 1]['MAX_STBD_DEG'] = data['RTP'][len(data['RTP']) - 1][
						'MAX_STBD_COV']

					# soundings referenced to Z of TX array, X and Y of active positioning system;
					# store last TX Z and waterline offset, plus active positioning system acrosstrack offset
					data['XYZ'][len(data['XYZ']) - 1]['TX_X_M'] = data['IP'][len(data['IP']) - 1]['S1X']
					data['XYZ'][len(data['XYZ']) - 1]['TX_Y_M'] = data['IP'][len(data['IP']) - 1]['S1Y']
					data['XYZ'][len(data['XYZ']) - 1]['TX_Z_M'] = data['IP'][len(data['IP']) - 1]['S1Z']
					data['XYZ'][len(data['XYZ']) - 1]['WL_Z_M'] = data['IP'][len(data['IP']) - 1]['WLZ']
					# print('APS number =', data['IP'][len(data['IP']) - 1]['APS'])
					APS_num = int(data['IP'][len(data['IP']) - 1]['APS'] + 1)  # act pos num (0-2): dg field P#Y (1-3)
					data['XYZ'][len(data['XYZ']) - 1]['APS_X_M'] = \
						data['IP'][len(data['IP']) - 1]['P' + str(APS_num) + 'X']
					data['XYZ'][len(data['XYZ']) - 1]['APS_Y_M'] = \
						data['IP'][len(data['IP']) - 1]['P' + str(APS_num) + 'Y']

				if print_updates:
					print('ping', len(data['XYZ']), 'swath limits (port/stbd):',
						  data['XYZ'][len(data['XYZ']) - 1]['MAX_PORT_DEG'], '/',
						  data['XYZ'][len(data['XYZ']) - 1]['MAX_STBD_DEG'], 'deg and',
						  data['XYZ'][len(data['XYZ']) - 1]['MAX_PORT_M'], '/',
						  data['XYZ'][len(data['XYZ']) - 1]['MAX_STBD_M'], 'meters')

			# parse RRA 78 datagram to get RX beam angles
			if dg_ID == 78:
				# MODIFY RRA PARSER WITH PARSE_OUTERMOST_ONLY OPTION
				data['RRA'][len(data['RRA'])] = multibeam_tools.libs.parseEM.RRA_78_dg(
					dg)  # speed this up to parse RX angles only!
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
	del data['RTP']

	if print_updates:
		print("\nFinished parsing file:", filename)
		fields = [f for f in data.keys() if f != 'fname']
		for field in fields:
			print(field, len(data[field]))

	return data


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


def sortDetections(self, data, print_updates=False):
	# sort through KMALL pings and pull out outermost valid soundings, BS, and mode
	det_key_list = ['fname', 'date', 'time', 'y_port', 'y_stbd', 'z_port', 'z_stbd', 'bs_port', 'bs_stbd',
					'ping_mode', 'pulse_form', 'swath_mode',
					'max_port_deg', 'max_stbd_deg', 'max_port_m', 'max_stbd_m',
					'rx_angle_port', 'rx_angle_stbd', 'tx_x_m', 'tx_y_m', 'tx_z_m', 'wl_z_m', 'aps_x_m', 'aps_y_m']
	det = {k: [] for k in det_key_list}

	# examine detection info across swath, find outermost valid soundings for each ping
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
			det['bs_port'].append(data[f]['XYZ'][p][bs_key][idx_port])
			det['bs_stbd'].append(data[f]['XYZ'][p][bs_key][idx_stbd])
			det['rx_angle_port'].append(data[f]['XYZ'][p][angle_key][idx_port])
			det['rx_angle_stbd'].append(data[f]['XYZ'][p][angle_key][idx_stbd])
			det['ping_mode'].append(data[f]['XYZ'][p]['PING_MODE'])
			det['pulse_form'].append(data[f]['XYZ'][p]['PULSE_FORM'])
			det['swath_mode'].append(data[f]['XYZ'][p]['SWATH_MODE'])

			if ftype == 'all':  # .all store date and time from ms from midnight
				dt = datetime.datetime.strptime(str(data[f]['XYZ'][p]['DATE']), '%Y%m%d') + \
					 datetime.timedelta(milliseconds=data[f]['XYZ'][p]['TIME'])
				det['date'].append(dt.strftime('%Y-%m-%d'))
				det['time'].append(dt.strftime('%H:%M:%S.%f'))
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


			elif ftype == 'kmall':  # .kmall store date and time from datetime object
				det['date'].append(data[f]['HDR'][p]['dgdatetime'].strftime('%Y-%m-%d'))
				det['time'].append(data[f]['HDR'][p]['dgdatetime'].strftime('%H:%M:%S.%f'))
				det['aps_x_m'].append(0)  # not needed for KMALL; append 0 as placeholder
				det['aps_y_m'].append(0)  # not needed for KMALL; append 0 as placeholder

				# get first installation parameter datagram, assume this does not change in file
				ip_text = data[f]['IP']['install_txt'][0]
				# get TX array offset text: EM304 = 'TRAI_TX1' and 'TRAI_RX1', EM2040P = 'TRAI_HD1', not '_TX1' / '_RX1'
				ip_tx1 = ip_text.split('TRAI_')[1].split(',')[0].strip()  # all heads/arrays split by comma
				det['tx_x_m'].append(float(ip_tx1.split('X=')[1].split(';')[0].strip()))  # get TX array X offset
				det['tx_y_m'].append(float(ip_tx1.split('Y=')[1].split(';')[0].strip()))  # get TX array Y offset
				det['tx_z_m'].append(float(ip_tx1.split('Z=')[1].split(';')[0].strip()))  # get TX array Z offset
				det['wl_z_m'].append(float(ip_text.split('SWLZ=')[-1].split(',')[0].strip()))  # get waterline Z offset

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
						det[k].append(float(rt.split(v)[-1].split('\n')[0].strip()))

					except:
						det[k].append('NA')

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


def update_system_info(self):
	# update model, serial number, ship, cruise based on availability in parsed data and/or custom fields
	if self.custom_info_gb.isChecked():  # use custom info if checked
		self.ship_name = self.ship_tb.text()
		self.cruise_name = self.cruise_tb.text()
		self.model_name = self.model_cbox.currentText()

	else:  # get info from detections if available
		try:  # try to grab ship name from filenames (conventional file naming)
			self.ship_name = self.det['fname'][0]  # try getting ship name from first detection filename
			self.ship_name = self.ship_name[self.ship_name.rfind('_') + 1:-4]  # assumes fname ends in _SHIPNAME.all

		except:
			self.ship_name = 'SHIP NAME N/A'  # if ship name not available in filename

		try:  # try to grab cruise name from Survey ID field in
			self.cruise_name = self.data_new[0]['IP_start'][0]['SID'].upper()  # update cruise ID with Survey ID

		except:
			self.cruise_name = 'CRUISE N/A'

		try:
			self.model_name = 'EM ' + str(self.data_new[0]['IP_start'][0]['MODEL'])

		except:
			self.model_name = 'MODEL N/A'


def update_axes(self):
	# adjust x and y axes and plot title
	update_system_info(self)
	update_plot_limits(self)
	self.swath_ax.set_ylim(0, self.swath_ax_margin * self.z_max)  # set depth axis to 0 and 1.1 times max(z)
	self.swath_ax.set_xlim(-1 * self.swath_ax_margin * self.x_max,
						   self.swath_ax_margin * self.x_max)  # set x axis to +/-1.1 times max(abs(x))
	self.title_str = 'Swath Width vs. Depth\n' + self.model_name + ' - ' + self.ship_name + ' - ' + self.cruise_name
	self.swath_ax.set(xlabel='Swath Coverage (m)', ylabel='Depth (m)', title=self.title_str)
	self.swath_ax.invert_yaxis()  # invert the y axis
	add_ref_filter_text(self)


def update_plot_limits(self):
	# expand custom limits to accommodate new data
	self.x_max_custom = max([self.x_max, self.x_max_custom])
	self.z_max_custom = max([self.z_max, self.z_max_custom])

	if self.x_max > self.x_max_custom or self.z_max > self.z_max_custom:
		self.plot_lim_gb.setChecked(False)
		self.x_max_custom = max([self.x_max, self.x_max_custom])
		self.z_max_custom = max([self.z_max, self.z_max_custom])

	if self.plot_lim_gb.isChecked():  # use custom plot limits if checked
		self.x_max_custom = int(self.max_x_tb.text())
		self.z_max_custom = int(self.max_z_tb.text())
		self.x_max = self.x_max_custom / self.swath_ax_margin  # divide custom limit by axis margin (multiplied later)
		self.z_max = self.z_max_custom / self.swath_ax_margin

	else:  # revert to automatic limits from the data if unchecked, but keep the custom numbers in text boxes
		self.plot_lim_gb.setChecked(False)
		self.max_x_tb.setText(str(int(self.x_max_custom)))
		self.max_z_tb.setText(str(int(self.z_max_custom)))


def update_solid_color(self, field):  # launch solid color dialog and assign to designated color attribute
	temp_color = QtWidgets.QColorDialog.getColor()
	setattr(self, field, temp_color)  # field is either 'color' (new data) or 'color_arc' (archive data)
	refresh_plot(self, call_source='update_solid_color')


def add_grid_lines(self):
	if self.grid_lines_toggle_chk.isChecked():  # turn on grid lines
		self.swath_ax.grid()
		self.swath_ax.minorticks_on()
		self.swath_ax.grid(which='both', linestyle='-', linewidth='0.5', color='black')

	else:
		self.swath_ax.grid(False)  # turn off the grid lines
		self.swath_ax.minorticks_off()


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
	if self.cbarbase:  # remove colorbar or legend if it exists
		self.cbarbase.remove()
		self.cbarbase = None

	if self.colorbar_chk.isChecked() and self.clim:
		if self.cset:  # clim and cset not empty --> make legend with discrete colors for ping, pulse, or swath mode
			self.cbarbase = self.swath_ax.legend(handles=self.legend_handles,
												 title=self.legend_label,
												 fontsize=self.cbar_font_size,
												 title_fontsize=self.cbar_title_font_size,
												 loc=self.cbar_loc)

		else:  # cset is empty --> make colorbar for depth or backscatter
			cbaxes = inset_axes(self.swath_ax, width="2%", height="30%", loc=self.cbar_loc)
			tickvalues = np.linspace(self.clim[0], self.clim[1], 11)
			ticklabels = [str(round(10 * float(tick)) / 10) for tick in tickvalues]
			self.cbarbase = colorbar.ColorbarBase(cbaxes, cmap=self.cmap, orientation='vertical',
												  norm=colors.Normalize(self.clim[0], self.clim[1]),
												  ticks=tickvalues,
												  ticklocation='left')

			self.cbarbase.ax.tick_params(labelsize=self.cbar_font_size)  # set font size for entries
			self.cbarbase.set_label(label=self.legend_label, size=self.cbar_title_font_size)
			self.cbarbase.set_ticklabels(ticklabels)

			# invert colorbar axis if last data plotted on top is colored by depth (regardless of background data)
			if self.last_cmode == 'depth':
				self.cbarbase.ax.invert_yaxis()  # invert for depth using rainbow_r colormap; BS is rainbow

	else:  # FUTURE: add custom text option in legend for datasets using solid color, useful for comparison plots
		pass


def save_plot(self):
	# save a .PNG of the coverage plot with a suggested figure name based on system info and plot settings
	fig_str = 'swath_width_vs_depth_' + self.model_name.replace(" ", "") + "_" + \
			  "_".join([s.replace(" ", "_") for s in [self.ship_name, self.cruise_name]]) + \
			  '_ref_to_' + self.ref_cbox.currentText().lower().replace(" ", "_")

	# sort out the color mode based on which dataset is displayed on top
	color_modes = [self.color_cbox.currentText(), self.color_cbox_arc.currentText()]
	color_str = color_modes[int(self.top_data_cbox.currentText() == 'Archive data')].lower().replace(" ", "_")
	fig_str += '_color_by_' + color_str

	# sort out whether archive is shown and where
	if self.show_data_chk_arc.isChecked() and self.det_archive:
		if not self.show_data_chk.isChecked():
			fig_str += '_archive_only'

		else:
			fig_str += '_with_archive'

			if self.top_data_cbox.currentText() == 'Archive data':
				fig_str += '_on_top'

	fig_name = "".join([c for c in fig_str if c.isalnum() or c in ['-', '_']]) + '.png'  # replace any lingering / \ etc
	current_path = self.output_dir.replace('\\', '/')
	plot_path = QtWidgets.QFileDialog.getSaveFileName(self, 'Save coverage figure', current_path + '/' + fig_name)
	fname_out = plot_path[0]

	if self.standard_fig_size_chk.isChecked():
		orig_size = self.swath_figure.get_size_inches()
		update_log(self, 'Resizing image to save')
		self.swath_figure.set_size_inches(8, 10)

	self.swath_figure.savefig(fname_out,
							  dpi=600, facecolor='w', edgecolor='k',
							  orientation='portrait', papertype=None, format=None,
							  transparent=False, bbox_inches=None, pad_inches=0.1,
							  frameon=None, metadata=None, bbox='tight')

	if self.standard_fig_size_chk.isChecked():
		update_log(self, 'Resetting original image size')
		self.swath_figure.set_size_inches(orig_size[0], orig_size[1], forward=True)  # forward resize to GUI
		refresh_plot(self, call_source='save_plot')

	update_log(self, 'Saved figure ' + fname_out.rsplit('/')[-1])


def clear_plot(self):
	# clear plot and reset bounds
	self.swath_ax.clear()
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
		self.show_data_chk_arc.setChecked(True)
		print('show_data_chk_arc is now', self.show_data_chk_arc.isChecked())


# else:
#     refresh_plot(self, print_time=True, call_source='load_archive')
# refresh_plot(self, print_time=True, call_source='load_archive')

def show_archive(self):
	n_plotted = 0
	# plot archive data underneath 'current' swath coverage data
	try:  # loop through det_archive dict (each key is archive fname, each val is dict of detections)
		# print('in show_archive all keys are:', self.det_archive.keys())
		archive_key_count = 0
		for k in self.det_archive.keys():
			# print('in show_archive with count = ', archive_key_count, ' and k=', k)
			# self.plot_coverage(self.det_archive[k], is_archive=True)  # plot det_archive
			n_points = plot_coverage(self, self.det_archive[k], is_archive=True)  # plot det_archive
			n_plotted += n_points
			print('in show_archive, n_plotted is now', n_plotted)

			self.swath_canvas.draw()
			archive_key_count += 1
	except:
		error_msg = QtWidgets.QMessageBox()
		error_msg.setText('No archive data loaded.  Please load archive data.')

	return n_plotted


def load_spec(self):
	# load a text file with theoretical performance to be plotted as a line
	add_cov_files(self, 'Theoretical coverage curve (*.txt)')  # add .pkl files to qlistwidget
	# fnames_new_spec = self.get_new_file_list(['.txt'])  # list new .all files not included in det dict
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
