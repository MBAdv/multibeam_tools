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
from common_data_readers.python.kongsberg.kmall import kmall
from time import process_time
from scipy.interpolate import interp1d
from copy import deepcopy
import struct


def setup(self):
	self.xline = {}
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
	# self.sis4_tx_z_field = 'S1Z'  # .all IP datagram field name for TX array Z offset (meters +down from origin)
	# self.sis4_waterline_field = 'WLZ'  # .all IP datagram field name for waterline Z offset (meters +down from origin
	self.depth_ref_list = ['Waterline']  # , 'Origin', 'TX Array', 'Raw Data']


def add_ref_file(self, ftype_filter, input_dir='HOME', include_subdir=False, ):
	# add single reference surface file with extensions in ftype_filter
	fname = add_files(self, ftype_filter, input_dir, include_subdir)
	update_file_list(self, fname)


def add_acc_files(self, ftype_filter, input_dir='HOME', include_subdir=False, ):
	# add accuracy crossline files with extensions in ftype_filter from input_dir and subdir if desired
	fnames = add_files(self, ftype_filter, input_dir, include_subdir)
	update_file_list(self, fnames)


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


def verifyMode(data):
	# verify consistent model, serial number, ping mode, pulse form, and swath mode in a set of files
	consistent_RTP = True
	model = data[0]['XYZ'][0]['MODEL']
	sn = data[0]['XYZ'][0]['SYS_SN']
	ping_mode = data[0]['XYZ'][0]['PING_MODE']
	pulse_mode = data[0]['XYZ'][0]['PULSE_FORM']
	swath_mode = data[0]['XYZ'][0]['SWATH_MODE']

	print('Verifying consistent system and runtime parameters from first ping:\nEM', str(model), ' (S/N ', str(sn),
		  ') ', ping_mode, ' / ', pulse_mode, ' / ', swath_mode, sep='')

	for f in range(len(data)):
		for p in range(len(data[f]['XYZ'])):
			# check for any changes (MODEL and SYS_SN are integers, modes are strings)
			if (data[f]['XYZ'][p]['MODEL'] != model or
					data[f]['XYZ'][p]['SYS_SN'] != sn or
					data[f]['XYZ'][p]['PING_MODE'] is not ping_mode or
					data[f]['XYZ'][p]['PULSE_FORM'] is not pulse_mode or
					data[f]['XYZ'][p]['SWATH_MODE'] is not swath_mode):
				print('WARNING: New system parameters detected in file ', str(f), ', ping ', str(p), ': EM', \
					  str(data[f]['XYZ'][p]['MODEL']), ' (S/N ', str(data[f]['XYZ'][p]['SYS_SN']), ') ', \
					  data[f]['XYZ'][p]['PING_MODE'], ' / ', data[f]['XYZ'][p]['PULSE_FORM'], ' / ',
					  data[f]['XYZ'][p]['SWATH_MODE'], sep='')
				consistent_RTP = False
				break

	if consistent_RTP:
		print('Consistent system and runtime parameters.')
	else:
		print('WARNING: Inconsistent system and runtime parameters!')

	return (consistent_RTP, (model, sn, ping_mode, pulse_mode, swath_mode))




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
			print('working on ping number ', p)
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

			# det['tx_x_m'].extend([data[f]['IP_start'][0]['S1X']]*len(det_idx))
				# det['tx_y_m'].extend([data[f]['IP_start'][0]['S1Y']]*len(det_idx))
				# det['tx_z_m'].extend([data[f]['IP_start'][0]['S1Z']]*len(det_idx))

				# APS_num = int(data[f]['IP_start'][0]['APS'] + 1)  # active position sensor num (0-2): dg field P#Y (1-3)
				# det['aps_x_m'].extend([data[f]['IP_start'][0]['P' + str(APS_num) + 'X']]*len(det_idx))
				# det['aps_y_m'].extend([data[f]['IP_start'][0]['P' + str(APS_num) + 'Y']]*len(det_idx))
				# det['aps_z_m'].extend([data[f]['IP_start'][0]['P' + str(APS_num) + 'Z']]*len(det_idx))

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






