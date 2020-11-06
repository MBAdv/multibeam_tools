"""General swath data handling functions for NOAA / MAC echosounder assessment tools"""

import multibeam_tools.libs.parseEM
import struct
import numpy as np
from copy import deepcopy
from kmall.KMALL import kmall
import utm


def readALLswath(self, filename, print_updates=False, parse_outermost_only=False):
	# parse .all swath data and relevant parameters for coverage or accuracy assessment
	# return full swath or outermost soundings only
	# if print_updates:
	print("\nParsing file:", filename)

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
				# 	update_log(self, 'Found TX Z offset = ' + str(data['IP'][len(data['IP']) - 1]['S1Z']) +
				# 			   ' m and Waterline offset = ' + str(data['IP'][len(data['IP']) - 1]['WLZ']) + ' m')

			# print('in file ', filename, 'just parsed an IP datagram:', data['IP'])

			# Parse RUNTIME PARAM datagram PYTHON 3
			if dg_ID == 82:
				data['RTP'][len(data['RTP'])] = multibeam_tools.libs.parseEM.RTP_dg(dg)

			# Parse XYZ 88 datagram PYTHON 3
			if dg_ID == 88:
				XYZ_temp = multibeam_tools.libs.parseEM.XYZ_dg(dg, parse_outermost_only=parse_outermost_only)
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
					data['XYZ'][len(data['XYZ']) - 1]['APS_X_M'] = data['IP'][len(data['IP']) - 1]['P' + str(APS_num) + 'X']
					data['XYZ'][len(data['XYZ']) - 1]['APS_Y_M'] = data['IP'][len(data['IP']) - 1]['P' + str(APS_num) + 'Y']
					data['XYZ'][len(data['XYZ']) - 1]['APS_Z_M'] = data['IP'][len(data['IP']) - 1]['P' + str(APS_num) + 'Z']

					# store bytes since last ping
					data['XYZ'][len(data['XYZ']) - 1]['BYTES_FROM_LAST_PING'] = dg_start - last_dg_start

					# print('last_dg_start, dg_start, and difference (bytes since last ping) = ',
					# 	  last_dg_start, dg_start, data['XYZ'][len(data['XYZ']) - 1]['BYTES_FROM_LAST_PING'])

					last_dg_start = dg_start  # update ping byte gap tracker


				if print_updates:
					print('ping', len(data['XYZ']), 'swath limits (port/stbd):',
						  data['XYZ'][len(data['XYZ']) - 1]['MAX_PORT_DEG'], '/',
						  data['XYZ'][len(data['XYZ']) - 1]['MAX_STBD_DEG'], 'deg and',
						  data['XYZ'][len(data['XYZ']) - 1]['MAX_PORT_M'], '/',
						  data['XYZ'][len(data['XYZ']) - 1]['MAX_STBD_M'], 'meters')

			# parse RRA 78 datagram to get RX beam angles
			if dg_ID == 78:
				# MODIFY RRA PARSER WITH PARSE_OUTERMOST_ONLY OPTION
				data['RRA'][len(data['RRA'])] = multibeam_tools.libs.parseEM.RRA_78_dg(dg)
			# RX_angles[len(RX_angles)] = RRA_temp['RX_ANGLE']

			# parse POS 80 datagram
			if dg_ID == 80:
				data['POS'][len(data['POS'])] = multibeam_tools.libs.parseEM.POS_dg(dg)

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
	del data['RTP']

	if print_updates:
		print("\nFinished parsing file:", filename)
		fields = [f for f in data.keys() if f != 'fname']
		for field in fields:
			print(field, len(data[field]))

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

		# print('after adjusting to origin, got dx, dy, dz=', dx, dy, dz)
		# print('in adjust_depth_ref, lens =', len(dx), len(dy), len(dz))

		if depth_ref == 'waterline':
			print('now adjusting from origin to waterline')
			# print('calculating dz from origin to waterline, then adding')
			# waterline is positive down; after adjusting depths to origin, subtract waterline offset; e.g., if the
			# waterline is above the origin, subtracting the (negative) WL increases the depths, as expected
			# .ALL depths from TX array: add Z offset of TX array and subtract waterline offset (both positive down)
			# .KMALL depths from origin: subtract waterline offset (positive down)
			# dz = [dz1 + dz2 for dz1, dz2 in zip(dz, det['wl_z_m'])]
			# print('in adjust_depth_ref, det[wl_z_m] has len=', len(det['wl_z_m']), 'and looks like', det['wl_z_m'][0:10])
			dz = [dz1 - dz2 for dz1, dz2 in zip(dz, det['wl_z_m'])]
			# print('just adjusted to waterline, dz has len=', len(dz))

	return dx, dy, dz


def readKMALLswath(self, filename, print_updates=False, parse_outermost_only=False):
	# parse .kmall swath data and relevant parameters for coverage or accuracy assessment
	# FUTURE: return full swath or outermost soundings only, for integration with swath coverage plotter
	km = kmall_data(filename)  # testing: kjall class inheriting kmall class and adding extract_dg method
	km.index_file()
	km.report_packet_types()

	# get required datagrams
	km.extract_dg('MRZ')  # sounding data
	km.extract_dg('IOP')  # runtime params

	print('IOP runtime param datagram extracted from .kmall: ', km.iop)

	km.extract_dg('IIP')  # installation params
	km.closeFile()

	# print('parsed KM file, first ping in km.mrz[pingInfo] =', km.mrz['pingInfo'][0])
	# print('in readKMALLswath, kmall file has km.mrz[sounding][0].keys = ', km.mrz['sounding'][0].keys())

	# add sounding delta lat/lon to lat/lon of reference point at ping time and store final sounding lat/lon
	for p in range(len(km.mrz['pingInfo'])):

		num_soundings = len(km.mrz['sounding'][p]['z_reRefPoint_m'])
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

	data = {'fname': filename.rsplit('/')[-1], 'XYZ': km.mrz['sounding'],
			'HDR': km.mrz['header'], 'RTP': km.mrz['pingInfo'],
			'IOP': km.iop, 'IP': km.iip}

	return data


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
			self.index_file()

		if self.FID is None:
			self.OpenFiletoRead()

		# for each datagram type, get offsets, read datagrams, and store in key (e.g., MRZ stored in kjall.mrz)
		if dg_name in list(dg_types):
			print('dg_name =', dg_name, ' is in dg_types')
			print('searching for ', "b'#" + dg_name + "'")
			dg_offsets = [x for x, y in zip(self.msgoffset, self.msgtype) if y == "b'#" + dg_name + "'"]  # + "]
			# print('got dg_offsets = ', dg_offsets)

			dg = list()
			for offset in dg_offsets:  # store all datagrams of this type
				self.FID.seek(offset, 0)
				parsed = dg_types[dg_name]()
				dg.append(parsed)

			# convert list of dicts to dict of lists
			print('setting attribute with dg_name.lower()=', dg_name.lower())
			dg_final = self.listofdicts2dictoflists(dg)
			setattr(self, dg_name.lower(), dg_final)

		self.FID.seek(0, 0)

		return
