"""General swath data handling functions for NOAA / MAC echosounder assessment tools"""

import multibeam_tools.libs.parseEM
import struct
import numpy as np
from copy import deepcopy
from kmall.KMALL import kmall
import utm


def readALLswath(self, filename, print_updates=False, parse_outermost_only=False, parse_params_only=False):
	# parse .all swath data and relevant parameters for:
	# 1. coverage (outermost soundings only)
	# 2. accuracy assessment (full swath)
	# 3. runtime and installation parameters only (parameter tracking, no swath data)
	# note that position is returned for all cases
	# note that acquisition parameters and raw range and angle data are copied to the ping data/time, and are not stored
	# separately for these purposes (this is slower/larger, but simpler for sorting in coverage or accuracy testing)
	# likewise, if params only are parsed, the most recent RTP or IP data are copied to the next valid ping time (and
	# ensuing XYZ datagrams are skipped until another param datagram is found; no swath data are parsed or stored)
	print("\nParsing file:", filename)
	f = open(filename, 'rb')
	raw = f.read()
	len_raw = len(raw)

	# initialize data dict with remaining datagram fields
	data = {'fname': filename, 'XYZ': {}, 'RTP': {}, 'RRA': {}, 'IP': {}, 'POS': {}}

	# dicts of 'new' and 'as parsed' names for runtime and installation params (for downstream sorting/plotting steps)
	rtp_fields = {'MODE': 'MODE',
				  'MAX_PORT_M': 'MAX_PORT_SWATH', 'MAX_STBD_M': 'MAX_STBD_SWATH',
				  'MAX_PORT_DEG': 'MAX_PORT_COV', 'MAX_STBD_DEG': 'MAX_STBD_COV'}

	ip_fields = {'TX_X_M': 'S1X', 'TX_Y_M': 'S1Y', 'TX_Z_M': 'S1Z',
				 'TX_R_DEG': 'S1R', 'TX_P_DEG': 'S1P', 'TX_H_DEG': 'S1H',
				 'RX_X_M': 'S2X', 'RX_Y_M': 'S2Y', 'RX_Z_M': 'S2Z',
				 'RX_R_DEG': 'S2R', 'RX_P_DEG': 'S2P', 'RX_H_DEG': 'S2H',
				 'WL_Z_M': 'WLZ'}

	# Declare counters for dg starting byte counter and dg processing counter
	dg_start = 0  # datagram (starting with STX = 2) starts at byte 4
	parse_prog_old = -1
	loop_num = 0
	last_dg_start = 0  # store number of bytes since last XYZ88 datagram
	skip_xyz = parse_params_only

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

			if dg_ID in [73, 82, 105]:
				if print_updates:
					print('-> found dg_ID = 73, 82, or 105 --> changing skip_xyz to FALSE')
				skip_xyz = False

			if dg_ID in [73, 105]:
				# print(len(data['IP_start'].keys()))
				data['IP'][len(data['IP'])] = multibeam_tools.libs.parseEM.IP_dg(dg)

				# if dg_ID == 73:
				# 	update_log(self, 'Found TX Z offset = ' + str(data['IP'][len(data['IP']) - 1]['S1Z']) +
				# 			   ' m and Waterline offset = ' + str(data['IP'][len(data['IP']) - 1]['WLZ']) + ' m')

			# parse RRA 78 datagram to get RX beam angles
			if dg_ID == 78 and not parse_params_only:
				# FUTURE: MODIFY RRA PARSER WITH PARSE_OUTERMOST_ONLY OPTION TO SPEED UP
				if print_updates:
					print('parsing RRA datagram')
				data['RRA'][len(data['RRA'])] = multibeam_tools.libs.parseEM.RRA_78_dg(dg)

			# parse POS 80 datagram
			if dg_ID == 80:
				data['POS'][len(data['POS'])] = multibeam_tools.libs.parseEM.POS_dg(dg)

			# Parse RUNTIME PARAM datagram PYTHON 3
			if dg_ID == 82:
				data['RTP'][len(data['RTP'])] = multibeam_tools.libs.parseEM.RTP_dg(dg)

			# Parse XYZ 88 datagram PYTHON 3
			if dg_ID == 88 and not skip_xyz:  # skip if not needed to store last param update

				XYZ_temp = multibeam_tools.libs.parseEM.XYZ_dg(dg, parse_outermost_only=parse_outermost_only,
															   parse_ping_info_only=parse_params_only)

				if XYZ_temp != []:  # store only if valid soundings are found (parser returns empty otherwise)
					data['XYZ'][len(data['XYZ'])] = XYZ_temp

					# store most recent runtime and installation parameters for each ping
					n_data = len(data['XYZ'])
					n_rtp = len(data['RTP'])
					n_ip = len(data['IP'])
					for new, old in rtp_fields.items():  # store runtime params with new names for downstream use
						data['XYZ'][n_data-1][new] = data['RTP'][n_rtp-1][old]

					for new, old in ip_fields.items():  # store installation params with new names for downstream use
						data['XYZ'][n_data-1][new] = data['IP'][n_ip-1][old]

					# soundings referenced to Z of TX array, X and Y of active positioning system;
					# store active positioning system offsets
					# print('APS number =', data['IP'][len(data['IP']) - 1]['APS'])
					APS_num = int(data['IP'][len(data['IP'])-1]['APS']+1)  # act pos num (0-2): dg field P#Y (1-3)
					data['XYZ'][len(data['XYZ'])-1]['APS_NUM'] = APS_num
					data['XYZ'][len(data['XYZ'])-1]['APS_X_M'] = data['IP'][len(data['IP'])-1]['P' + str(APS_num) + 'X']
					data['XYZ'][len(data['XYZ'])-1]['APS_Y_M'] = data['IP'][len(data['IP'])-1]['P' + str(APS_num) + 'Y']
					data['XYZ'][len(data['XYZ'])-1]['APS_Z_M'] = data['IP'][len(data['IP'])-1]['P' + str(APS_num) + 'Z']

					# store bytes since last ping
					data['XYZ'][len(data['XYZ']) - 1]['BYTES_FROM_LAST_PING'] = dg_start - last_dg_start
					last_dg_start = dg_start  # update ping byte gap tracker

				if print_updates:
					print('XYZ update ', len(data['XYZ']), 'swath limits (port/stbd):',
						  data['XYZ'][len(data['XYZ']) - 1]['MAX_PORT_DEG'], '/',
						  data['XYZ'][len(data['XYZ']) - 1]['MAX_STBD_DEG'], 'deg and',
						  data['XYZ'][len(data['XYZ']) - 1]['MAX_PORT_M'], '/',
						  data['XYZ'][len(data['XYZ']) - 1]['MAX_STBD_M'], 'meters')

				if parse_params_only:  # reset to skip upcoming XYZ datagrams until after another params datagram
					if print_updates:
						print('---> resetting skip_xyz to TRUE after parsing XYZ')
					skip_xyz = True

			# if there was a valid STX and ETX, jump to end of dg and continue on next iteration
			dg_start = dg_start + dg_len + 4
			continue

		# if no condition was met to read and jump ahead not valid, move ahead by 1 and continue search
		# (will start read dg_len at -4 on next loop)
		dg_start = dg_start + 1
	# print('STX or ETX not valid, moving ahead by 1 to new dg_start', dg_start)

	# loop through the XYZ and RRA data, store angles re RX array associated with each outermost sounding;
	# if parsing outermost soundings only, the number of RRA datagrams may exceed num of XYZ datagrams if some XYZ dg
	# did not have valid soundings (return []); check RRA PING_COUNTER against XYZ PING_COUNTER to make new RRA ping
	# index reference for copying RX angles in following loop

	if not parse_params_only:
		pXYZ = [data['XYZ'][p]['PING_COUNTER'] for p in range(len(data['XYZ']))]
		pRRA = [p for p in range(len(data['RRA'])) if data['RRA'][p]['PING_COUNTER'] in pXYZ]
		# print('pXYZ has len and =', len(pXYZ), pXYZ)
		# print('pRRA has len and =', len(pRRA), pRRA)

		for p in range(len(data['XYZ'])):
			# data['XYZ'][p]['RX_ANGLE_PORT'] = data['RRA'][p]['RX_ANGLE'][data['XYZ'][p]['RX_BEAM_IDX_PORT']]/100
			# data['XYZ'][p]['RX_ANGLE_STBD'] = data['RRA'][p]['RX_ANGLE'][data['XYZ'][p]['RX_BEAM_IDX_STBD']]/100

			# use reduced RRA ping reference indices to ensure same PING_COUNTER for XYZ and RRA dg
			if parse_outermost_only:
				data['XYZ'][p]['RX_ANGLE_PORT'] = data['RRA'][pRRA[p]]['RX_ANGLE'][data['XYZ'][p]['RX_BEAM_IDX_PORT']] / 100
				data['XYZ'][p]['RX_ANGLE_STBD'] = data['RRA'][pRRA[p]]['RX_ANGLE'][data['XYZ'][p]['RX_BEAM_IDX_STBD']] / 100

				data['XYZ'][p]['RX_ANGLE'] = [data['XYZ'][p]['RX_ANGLE_PORT'], data['XYZ'][p]['RX_ANGLE_STBD']]  # store both

				if print_updates:
					print('ping', p, 'has RX angles port/stbd IDX',
						  data['XYZ'][p]['RX_BEAM_IDX_PORT'], '/', data['XYZ'][p]['RX_BEAM_IDX_STBD'], ' and ANGLES ',
						  data['XYZ'][p]['RX_ANGLE_PORT'], '/',
						  data['XYZ'][p]['RX_ANGLE_STBD'])

			else:
				data['XYZ'][p]['RX_ANGLE'] = (np.asarray(data['RRA'][pRRA[p]]['RX_ANGLE'])/100).tolist()  # store all angles

		del data['RRA']  # outermost valid RX angles have been stored in XYZ, RRA is no longer needed
	# del data['RTP']

	print('data has fields ', data.keys())
	print('.ALL RTP fields for first stored datagram =', data['RTP'][0].keys())

	if print_updates:
		print("\nFinished parsing file:", filename)
		fields = [f for f in data.keys() if f != 'fname']
		for field in fields:
			print(field, len(data[field]))

	# print('data[POS] =', data['POS'])

	return data


def interpretMode(self, data, print_updates):
	# interpret runtime parameters for each ping and store in XYZ dict prior to sorting
	# nominal frequencies for most models; EM712 .all (SIS 4) assumed 40-100 kHz (40-70/70-100 options in SIS 5)
	# EM2040 frequencies for SIS 4 stored in ping mode; EM2040 frequencies for SIS 5 are stored in runtime parameter
	# text and are updated in sortDetectionsAccuracy if available; NA is used as a placeholder here

	freq_dict = {'122': '12 kHz', '124': '12 kHz',
				 '302': '30 kHz', '304': '30 kHz',
				 '710': '70-100 kHz', '712': '40-100 kHz',
				 '2040': 'NA',
				 '2042': 'NA'}

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
			pulse_dict_2040C = {'0': 'CW', '1': 'FM'}
			swath_dict = {'00': 'Single Swath', '01': 'Dual Swath (Fixed)', '10': 'Dual Swath (Dynamic)'}

			# loop through all pings
			for p in range(len(data[f]['XYZ'])):
				# print('binary mode as parsed = ', data[f]['XYZ'][p]['MODE'])
				bin_temp = "{0:b}".format(data[f]['XYZ'][p]['MODE']).zfill(8)  # binary str
				ping_temp = bin_temp[-4:]  # last 4 bytes specify ping mode based on model
				model_temp = str(data[f]['XYZ'][p]['MODEL']).strip()

				# check model to reference correct key in ping mode dict
				if np.isin(data[f]['XYZ'][p]['MODEL'], all_model_list + [2000, 1002]):
					model_temp = '9999'  # set model_temp to reference mode_list dict for all applicable models

				data[f]['XYZ'][p]['PING_MODE'] = mode_dict[model_temp][ping_temp]

				# interpret pulse form and swath mode based on model
				# print('working on modes for model: ', data[f]['XYZ'][p]['MODEL'])

				if np.isin(data[f]['XYZ'][p]['MODEL'], all_model_list + [2040]):  # reduced models for swath and pulse
					data[f]['XYZ'][p]['SWATH_MODE'] = swath_dict[bin_temp[-8:-6]]  # swath mode from binary str
					data[f]['XYZ'][p]['PULSE_FORM'] = pulse_dict[bin_temp[-6:-4]]  # pulse form from binary str

					if data[f]['XYZ'][p]['MODEL'] == 2040:  # EM2040 .all format stores freq mode in ping mode
						# print('assigning EM2040 frequency from ping mode for .all format')
						data[f]['XYZ'][p]['FREQUENCY'] = data[f]['XYZ'][p]['PING_MODE']

					else:
						# print('assigning non-EM2040 frequency from model for .all format')
						data[f]['XYZ'][p]['FREQUENCY'] = freq_dict[str(data[f]['XYZ'][p]['MODEL'])]

				elif data[f]['XYZ'][p]['MODEL'] == '2040C':  # special cases for EM2040C
					data[f]['XYZ'][p]['SWATH_MODE'] = pulse_dict_2040C[bin_temp[-7:-6]]  # swath mode from binary str
					data[f]['XYZ'][p]['FREQUENCY'] = 'NA'  # future: parse from binary (format: 180 kHz + bin*10kHz)

				else:  # specify NA if not in model list for this interpretation
					data[f]['XYZ'][p]['PULSE_FORM'] = 'NA'
					data[f]['XYZ'][p]['SWATH_MODE'] = 'NA'
					data[f]['XYZ'][p]['FREQUENCY'] = 'NA'
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

			# depth, pulse in pingInfo from MRZ dg; swath mode, freq in IOP dg runtime text (sortDetectionsCoverage or sortDetectionsAccuracy)
			# swath_dict = {'0': 'Single Swath', '1': 'Dual Swath'}

			for p in range(len(data[f]['XYZ'])):
				# get depth mode from list and add qualifier if manually selected
				# print('for ping p=', p, 'depthMode is', data[f]['RTP'][p]['depthMode'])
				manual_mode = data[f]['RTP'][p]['depthMode'] >= 100  # check if manual selection
				mode_idx = str(data[f]['RTP'][p]['depthMode'])[-1]  # get last character for depth mode
				data[f]['XYZ'][p]['PING_MODE'] = mode_dict[mode_idx] + (' (Manual)' if manual_mode else '')
				data[f]['XYZ'][p]['PULSE_FORM'] = pulse_dict[str(data[f]['RTP'][p]['pulseForm'])]

				# store default frequency based on model, update from runtime param text in sortCoverageDetections
				# data[f]['XYZ'][p]['FREQUENCY'] = freq_dict[str(data[f]['XYZ'][p]['MODEL'])]
				# print('looking at SIS 5 model: ', data[f]['HDR'][p]['echoSounderID'])
				data[f]['XYZ'][p]['FREQUENCY'] = freq_dict[str(data[f]['HDR'][p]['echoSounderID'])]

				if print_updates:
					ping = data[f]['XYZ'][p]
					print('file', f, 'ping', p, 'is', ping['PING_MODE'], ping['PULSE_FORM'])

		else:
			print('UNSUPPORTED FTYPE --> NOT INTERPRETING MODES!')

		if missing_mode:
			self.update_log('Warning: missing mode info in ' + data[f]['fname'].rsplit('/', 1)[-1] +
					   '\nPoint color options may be limited due to missing mode info')

	if print_updates:
		print('\nDone interpreting modes...')

	return data


def readKMALLswath(self, filename, print_updates=False, include_skm=False, parse_params_only=False):
	# parse .kmall swath data and relevant parameters for:
	# 1. coverage (outermost soundings only)
	# 2. accuracy assessment (full swath)
	# 3. runtime and installation parameters only (parameter tracking, no swath data)
	# note that position is returned for all cases
	# note that acquisition parameters and raw range and angle data are copied to the ping data/time, and are not stored
	# separately for these purposes (this is slower/larger, but simpler for sorting in coverage or accuracy testing)
	# likewise, if params only are parsed, the most recent RTP or IP data are copied to the next valid ping time (and
	# ensuing XYZ datagrams are skipped until another param datagram is found; no swath data are parsed or stored)

	# FUTURE: return full swath or outermost soundings only, for integration with swath coverage plotter
	km = kmall_data(filename)  # kmall_data class inheriting kmall class and adding extract_dg method
	km.index_file()
	km.report_packet_types()

	# get required datagrams
	print('calling extract_dg')
	km.extract_dg('IOP')  # runtime params
	km.extract_dg('IIP')  # installation params

	if parse_params_only:  # save runtime and installation parameters
		km.extract_dg('MRZinfo')
		data_xyz = {'XYZ': km.mrz['pingInfo']}
		include_skm = False

	else:  # get sounding data, add delta lat/lon to lat/lon of ref point at ping time and store final sounding lat/lon
		km.extract_dg('MRZ')  # extract sounding data
		print('parsed KM file, first ping in km.mrz[pingInfo] =', km.mrz['pingInfo'][0])
		print('in readKMALLswath, kmall file has km.mrz[sounding][0].keys = ', km.mrz['sounding'][0].keys())

		for p in range(len(km.mrz['pingInfo'])):

			num_soundings = len(km.mrz['sounding'][p]['z_reRefPoint_m'])
			if print_updates:
				print('ping ', p, 'has n_soundings =', num_soundings, ' and lat, lon =',
					  km.mrz['pingInfo'][p]['latitude_deg'], km.mrz['pingInfo'][p]['longitude_deg'])

			km.mrz['sounding'][p]['lat'] = (np.asarray(km.mrz['sounding'][p]['deltaLatitude_deg']) +
											km.mrz['pingInfo'][p]['latitude_deg']).tolist()
			km.mrz['sounding'][p]['lon'] = (np.asarray(km.mrz['sounding'][p]['deltaLongitude_deg']) +
											km.mrz['pingInfo'][p]['longitude_deg']).tolist()

			# convert sounding position to UTM
			temp_lat = km.mrz['sounding'][p]['lat']
			temp_lon = km.mrz['sounding'][p]['lon']

			e, n, zone = [], [], []
			for s in range(num_soundings):  # loop through all soundings and append lat/lon list
				e_temp, n_temp, zone_temp, letter_temp = utm.from_latlon(temp_lat[s], temp_lon[s])  # sounding easting, northing
				e.append(e_temp)
				n.append(n_temp)
				zone.append(str(zone_temp) + letter_temp)

			# print('in parseKMALLswath, first few e, n, zone=', e[0:5], '\n', n[0:5], '\n', zone[0:5])

			km.mrz['sounding'][p]['e'] = e
			km.mrz['sounding'][p]['n'] = n
			km.mrz['sounding'][p]['utm_zone'] = zone

		data_xyz = {'XYZ': km.mrz['sounding']}

	data = {'fname': filename.rsplit('/')[-1],
			'HDR': km.mrz['header'],
			'RTP': km.mrz['pingInfo'],
			'IOP': km.iop,
			'IP': km.iip,
			'start_byte': km.mrz['start_byte']}

	data.update(data_xyz)  # add the XYZ data from either course (full swath data or pinginfo only)

	if include_skm:
		km.extract_dg('SKM')  # TESTING motion sensor timing (Seapath / Revelle SAT)
		data['SKM'] = km.skm

	km.closeFile()

	return data


def readASCIIswath(self, filename, utm_zone=''):
# get sounding data and store in a way that makes sorting simple or unnecessary in sortDetectionsAccuracy
	det_key_list = ['fname', 'model', 'datetime', 'date', 'time', 'sn',
					'lat', 'lon', 'x', 'y', 'z', 'z_re_wl', 'n', 'e', 'utm_zone', 'bs', 'rx_angle',
					'ping_mode', 'pulse_form', 'swath_mode', 'frequency',
					'max_port_deg', 'max_stbd_deg', 'max_port_m', 'max_stbd_m',
					'tx_x_m', 'tx_y_m', 'tx_z_m', 'aps_x_m', 'aps_y_m', 'aps_z_m', 'wl_z_m',
					'ping_e', 'ping_n', 'ping_utm_zone']

	data = {k: [] for k in det_key_list}

	ascii_key_list = {'Date Time': 'datetime',
					  'Vessel X': 'ping_e',
					  'Vessel Y': 'ping_n',
					  'Ping': 'ping_num',
					  'Beam': 'beam_num',
					  'Footprint X': 'e',
					  'Footprint Y': 'n',
					  'Footprint Z': 'z'}

	ascii_key_list = ['datetime', 'ping_e', 'ping_n', 'x', 'y', 'z']

	data['fname'] = filename.rsplit('/')[-1]

	print('parsing ASCII soundings data')
	fid_ascii = open(filename, 'r')

	for line in fid_ascii:
		# print('looking at ASCII sounding line = ', line)
		if line[0] != '#':  # skip header
			# print('not a header, parsing line: ', line)
			# temp = line.replace('\n', '').split(",")
			temp = line.replace(',', ' ').strip().rstrip().split()
			data['date'].append(temp[0])  # ping date
			data['time'].append(temp[1])  # ping time
			data['ping_e'].append(temp[2])  # vessel easting
			data['ping_n'].append(temp[3])  # vessel northing
			# data['ping_num'].append(temp[4])  # ping number
			# data['beam_num'].append(temp[5])  # beam number
			data['e'].append(temp[6])  # sounding e
			data['n'].append(temp[7])  # sounding n
			data['z'].append(temp[8])  # sounding z
			data['utm_zone'].append(utm_zone)  # sounding UTM zone is assumed to be same as ref surf input

			# print('len of data is now ', len(data['date']))

		else:
			print('found header.. skipping...')


	print('survived parsing ASCII soundings! --> total sounding count =', len(data['date']))

	# convert ping location to lat lon
	for s in range(len(data['ping_e'])):
		lat, lon = utm.to_latlon(data['e'][s],
								 data['n'][s],
								 northern=utm_zone.find('N'))
		data['ping_lat'].append(lat)
		data['ping_lon'].append(lon)

	#### LEAVE OFF HERE: convert date and time to datetime


	# subtract ship position from sounding locations to get deltaX, deltaY, deltaZ for each
	# get acrosstrack distance from deltaX, deltaY
	# get beam angle from
	# get unique number of pings
	# for p in number of pings
		# get number of soundings
		# convert

	data = {'fname': filename.rsplit('/')[-1],
			'XYZ': [],
			'HDR': [],
			'RTP': [],
			'IOP': [],
			'IP': [],
			'SKM': [],
			'start_byte': 0}

	return data



def adjust_depth_ref(det, depth_ref='raw data'):
	# calculate an alongtrack (dx), acrosstrack (dy), and vertical (dz) adjustment for each entry in detection dict to
	# shift the parsed soundings to the desired reference point ('raw', 'origin', 'tx array', or 'waterline')
	# Note: this considers only installation offsets; it does not account for attitude-induced diffs in ref locations;
	# all adjustments are in the Kongsberg reference frame convention, with +X FWD, +Y STBD, and +Z DOWN; the output
	# is the set of adjustments to add to X, Y, and Z in the Kongsberg frame to shift the reference point, assuming
	# level trim

	if not all([k in det.keys() for k in ['tx_x_m', 'tx_y_m', 'aps_x_m', 'aps_y_m', 'wl_z_m']]):
		print('WARNING: in adjust_depth_ref, resetting depth ref from ', depth_ref,
			  'to "raw data" for this detection dict because not all offsets are available for further transformation')
		depth_ref = 'raw data'

	if depth_ref == 'raw data':
		# use depth reference native to the sonar file if desired, or if fields for further adjustment are not available
		# return dz = 0 for all pings
		print('returning all zeros')
		dx = [0] * len(det['fname'])
		dy = deepcopy(dx)
		dz = deepcopy(dx)

	elif depth_ref == 'tx array':  # adjust to TX array
		print('adjusting to tx array')
		# .ALL depths from TX array: add 0 to Z, adjust X and Y from active pos system to origin then to TX array
		# .KMALL depths from origin: subtract offsets of TX array (positive down, stbd); e.g., if TX array is below and
		# to stbd of origin, subtracting the (positive) array offsets decreases the distances w.r.t. TX, as expected
		offsets = [(-1*det['tx_x_m'][p],
					-1*det['tx_y_m'][p],
					-1*det['tx_z_m'][p]) if det['fname'][p].rsplit('.')[-1] == 'kmall' else
				   (det['aps_x_m'][p] - det['tx_x_m'][p],
					det['aps_y_m'][p] - det['tx_y_m'][p],
					0) for p in range(len(det['fname']))]

		dx, dy, dz = [list(tup) for tup in zip(*offsets)]

	else:  # adjust to origin, then waterline if necessary
		print('adjusting to origin')
		# .ALL depths from TX array: add offsets of TX array (positive down, stbd); e.g., if TX array is below and to
		# stbd of origin, adding the (positive) array offsets increases the distances w.r.t. origin, as expected
		# .KMALL depths from origin: add 0 (no change required)
		# dz has len = number of pings, not number of detections
		# print('calculating dz from file-specific depth ref to origin')
		offsets = [(det['aps_x_m'][p],
					det['aps_y_m'][p],
					det['tx_z_m'][p]) if det['fname'][p].rsplit('.')[-1] == 'all' else
				   (0, 0, 0) for p in range(len(det['fname']))]

		dx, dy, dz = [list(tup) for tup in zip(*offsets)]

		if depth_ref == 'waterline':
			print('now adjusting from origin to waterline')
			# print('calculating dz from origin to waterline, then adding')
			# waterline is positive down; after adjusting depths to origin, subtract waterline offset; e.g., if the
			# waterline is above the origin, subtracting the (negative) WL increases the depths, as expected
			# .ALL depths from TX array: add Z offset of TX array and subtract waterline offset (both positive down)
			# .KMALL depths from origin: subtract waterline offset (positive down)
			dz = [dz1 - dz2 for dz1, dz2 in zip(dz, det['wl_z_m'])]

	return dx, dy, dz


def verifyModelAndModes(det, verify_modes=True):
	# verify system model, serial number, and (optionally) ping mode, pulse form, and swath mode in a set of files
	# sort by time
	# print('sorting detections by time')
	sort_idx = np.argsort(det['datetime'])
	# print('got sort_idx = ', sort_idx)

	# model_sorted = det['model'][sort_idx]
	# sn_sorted = det['sn'])[sort_idx]
	# ping_mode_sorted = np.asarray(det['ping_mode'])[sort_idx]
	# swath_mode_sorted = det['swath_mode'][sort_idx]
	# pulse_form_sorted = det['pulse_form'][sort_idx]

	sys_info_keys = ['model', 'sn', 'ping_mode', 'swath_mode', 'pulse_form']
	sys_info = {k: [np.asarray(det[k])[sort_idx[0]]] for k in sys_info_keys + ['datetime', 'fname']}  # initial values

	# for k in sys_info_keys:  # initialize system info dict with earliest values
	# 	sys_info[k] = [np.asarray(det[k])[sort_idx[0]]]

	# print('starting to verify model and modes through all detections, starting with initial sys_info:', sys_info)

	for s in sort_idx:
		for k in sys_info_keys:
			if det[k][s] != sys_info[k][-1]:
				print('***found new parameter: ', k, ' changed from ', sys_info[k][-1], ' to ', det[k][s])
				for j in sys_info_keys + ['datetime', 'fname']:
					print('appending ', det[j][s], 'at time', det['datetime'][s].strftime('%Y-%m-%d %H:%M:%S.%f'))
					sys_info[j].append(det[j][s])

	# print('finished sorting/checking model and mode info: sys_info is now: ', sys_info)

	return sys_info


class kmall_data(kmall):
	# test class inheriting kmall class with method to extract any datagram (based on extract attitude method)
	def __init__(self, filename, dg_name=None):
		super(kmall_data, self).__init__(filename)  # pass the filename to kmall module (only argument required)

	def extract_dg(self, dg_name):  # extract dicts of datagram types, store in kmall_data class
		print('\n\nin extract_dg with dg_name = ', dg_name)
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
			print('got dg_offsets = ', dg_offsets)

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

		print('leaving extract_dg')
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