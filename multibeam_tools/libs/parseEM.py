# Define parsers for Kongsberg .all datagrams

# These functions parse datagrams but do not correct for formatting of fields,
# such as dividing by 100 for heading which is recorded in 0.01 deg as an integer 
# Refer to Kongsberg documentation for descriptions

# These work for now but should be updated with more intelligent parsing methods!

import struct

#%% VALIDATE DATAGRAM (UPDATED FOR PYTHON 3) ########################################################
def validate_dg(data, dg_start, len_data):
    
    # print(type(data))
	if dg_start >= 4 and dg_start <= len_data: # rest of file
		dg_len = struct.unpack('I', data[dg_start-4:dg_start])[0]
		dg_end = dg_start + dg_len
	
	else: # first datagram
		if dg_start < 4:
			dg_start = 4
			dg_len = struct.unpack('I', data[dg_start-4:dg_start])[0]
			dg_end = dg_start + dg_len
		else:
			return [0, [0]]
		
	if dg_end <= len_data and dg_len >= 3:

		dg = data[dg_start:dg_end]	# determine ID if STX and ETX exist
		dg_STX = dg[0]
		dg_ETX = dg[-3]

		
		# determine ID and store dg count, ID, DATE, TIME, start byte, and length in TOC for reference
		if dg_STX == 2 and dg_ETX == 3 and type(dg_len) == int:
			# Return [valid dg_validity, [valid_dg_TOC]]
			dg_ID =		dg[1] 								# ID 1U		
			dg_DATE = 	struct.unpack('I', dg[4:8])[0]		# DATE 4U
			dg_TIME = 	struct.unpack('I', dg[8:12])[0]		# TIME 4U

			valid_dg_TOC = [dg_ID, dg_DATE, dg_TIME, dg_start, dg_len]

			# print('returning valid datagram number', dg_ID)

			return [1, valid_dg_TOC]
		else:
			return [0, [0]]
	else:
		return [0, [0]]
		
#%% PU status datagram (UPDATED FOR PYTHON 3) #######################################################
def PU_dg(dg):

	PU = {}

	PU['STX'] = 			struct.unpack('B', dg[0:1])[0]		# STX 1U
	PU['ID'] = 				struct.unpack('B', dg[1:2])[0]		# ID 1U	
	PU['MODEL'] = 			struct.unpack('H', dg[2:4])[0]		# EM MODEL 2U
	PU['DATE'] = 			struct.unpack('I', dg[4:8])[0]		# DATE 4U	
	PU['TIME'] = 			struct.unpack('I', dg[8:12])[0]		# TIME in ms since midnight 4U
	PU['STATUS_COUNTER'] = 	struct.unpack('H', dg[12:14])[0]	# STATUS COUNTER 2U
	PU['SYS_SN'] = 			struct.unpack('H', dg[14:16])[0]	# SYS SN 2U
	PU['PING_RATE'] =		struct.unpack('H', dg[16:18])[0]	# PING RATE 2U (centiHz)
	PU['PING_COUNTER'] =	struct.unpack('H', dg[18:20])[0]	# PING COUNTER 2U
	PU['PU_LOAD'] =			struct.unpack('I', dg[20:24])[0]	# PU LOAD in % 4U
	PU['UDP_PORT_2'] =		struct.unpack('I', dg[24:28])[0]	# UDP PORT 2 4U
	PU['SERIAL_PORT_1'] =	struct.unpack('I', dg[28:32])[0]	# SERIAL PORT 1 4U
	PU['SERIAL_PORT_2'] =	struct.unpack('I', dg[32:36])[0]	# SERIAL PORT 2 4U
	PU['SERIAL_PORT_3'] =	struct.unpack('I', dg[36:40])[0]	# SERIAL PORT 3 4U
	PU['SERIAL_PORT_4'] =	struct.unpack('I', dg[40:44])[0]	# SERIAL PORT 4 4U
	PU['PPS'] =				struct.unpack('b', dg[44:45])[0]	# PPS (positive num is OK, neg not OK) 1S
	PU['POS_STAT'] =		struct.unpack('b', dg[45:46])[0]	# POS STAT (positive num is OK, neg not OK) 1S
	PU['ATT_STAT'] =		struct.unpack('b', dg[46:47])[0]	# ATT STAT (positive num is OK, neg not OK) 1S
	PU['CLOCK_STAT'] =		struct.unpack('b', dg[47:48])[0]	# CLOCK STAT (positive num is OK, neg not OK) 1S
	PU['HEAD_STAT'] =		struct.unpack('b', dg[48:49])[0]	# HEAD STAT (positive num is OK, neg not OK) 1S
	PU['PU_STAT'] =			struct.unpack('B', dg[49:50])[0]	# PU STAT see KM doc note 11 1U
	PU['HEADING'] =			struct.unpack('H', dg[50:52])[0]	# last received HEADING in 0.01 deg 2U
	PU['ROLL'] = 			struct.unpack('h', dg[52:54])[0]	# last received ROLL in 0.01 deg 2S
	PU['PITCH'] = 			struct.unpack('h', dg[54:56])[0]	# last received PITCH in 0.01 deg 2S
	PU['HEAVE'] =			struct.unpack('h', dg[56:58])[0]	# last receieved HEAVE at sonar head in cm 2S
	PU['SS_TRANS'] = 		struct.unpack('H', dg[58:60])[0]	# SS TRANS in 0.1 m/s 2U
	PU['DEPTH'] = 			struct.unpack('I', dg[60:64])[0]	# last received depth of motion sensor in cm 4U
	PU['ALONG_VEL'] =		struct.unpack('h', dg[64:66])[0]	# ALONG VEL in 0.01 m/s 2S
	PU['ATT_VEL_STAT'] =	struct.unpack('B', dg[66:67])[0]	# ATT VEL STAT see KM note 11 1U
	PU['MAMMAL_RAMP'] =		struct.unpack('B', dg[67:68])[0]	# MAMMAL RAMP high voltage ramp up time in s 1U
	PU['BS_OBLIQUE'] = 		struct.unpack('b', dg[68:69])[0]	# BS OBLIQUE see KM note 7 1S
	PU['BS_NORMAL'] =		struct.unpack('b', dg[69:70])[0]	# BS NORMAL see KM note 7 1S
	PU['FIXED_GAIN'] =		struct.unpack('b', dg[70:71])[0]	# FIXED GAIN see KM note 7 1S
	PU['DEPTH_NORMAL'] =	struct.unpack('B', dg[71:72])[0]	# DEPTH NORMAL in m (spare for EM3000, EM2000) 1U
	PU['RANGE_NORMAL'] =	struct.unpack('H', dg[72:74])[0]	# RANGE NORMAL in m (not incl before Jan 2004) 2U
	PU['PORT_COVERAGE'] =	struct.unpack('B', dg[74:75])[0]	# PORT COVERAGE in deg 1U
	PU['STBD_COVERAGE'] =	struct.unpack('B', dg[75:76])[0]	# STBD COVERAGE in deg 1U
	PU['SS_TRANS_PROF'] =	struct.unpack('H', dg[76:78])[0]	# SS at transducer depth in profile, 0.1 m/s 2U
	PU['YAW_STAB'] =		struct.unpack('h', dg[78:80])[0]	# YAW STAB in 0.1 deg 2S
	PU['VEL_ACROSS'] =		struct.unpack('h', dg[80:82])[0]	# ACROSS VEL in 0.01 m/s (EM3002 PORT COV. ) 2S
	PU['VEL_DOWN'] =		struct.unpack('h', dg[82:84])[0]	# DOWNWARD VEL in 0.01 m/s (EM3002 STBR COV.) 2S
	PU['SPARE'] = 			struct.unpack('B', dg[84:85])[0]	# SPARE 1U
	PU['ETX'] = 			struct.unpack('B', dg[85:86])[0]	# ETX 1U
	PU['CHECKSUM'] = 		struct.unpack('H', dg[86:88])[0]	# CHECKSUM 2U

	# for field, value in PU.items():
	# 	print(field, value)

	return(PU)


#%% ATTITUDE datagram (UPDATED FOR PYTHON 3) ########################################################
def ATT_dg(dg):

	ATT = {}

	ATT['STX'] = struct.unpack('B', dg[0:1])[0]				# STX 1U
	ATT['ID'] = struct.unpack('B', dg[1:2])[0]				# ID 1U	
	ATT['MODEL'] = struct.unpack('H', dg[2:4])[0]			# EM MODEL 2U
	ATT['DATE'] = struct.unpack('I', dg[4:8])[0]			# DATE 4U
	ATT['TIME'] = struct.unpack('I', dg[8:12])[0]			# TIME 4U
	ATT['ATT_COUNTER'] = struct.unpack('H', dg[12:14])[0]	# ATTITUDE COUNTER 2U
	ATT['SYS_SN'] = struct.unpack('H', dg[14:16])[0]		# SYS SN 2U
	ATT['NUM_ENTRIES'] = struct.unpack('H', dg[16:18])[0]	# NUM ENTRIES 2U
	
	ATT_FIELDS = ['TIME', 'STATUS', 'ROLL', 'PITCH', 'HEAVE', 'HDG'] # attitude entry fields

	for i in range(len(ATT_FIELDS)):
		ATT[ATT_FIELDS[i]] = []

	entry_start = 18
	entry_length = 12
	
	for i in range(ATT['NUM_ENTRIES']):
		ATT['TIME'].append(struct.unpack('H', dg[entry_start:entry_start+2])[0])		# 2U ms since record start
		ATT['STATUS'].append(struct.unpack('H', dg[entry_start+2:entry_start+4])[0])	# 2U status see KM doc note
		ATT['ROLL'].append(struct.unpack('h', dg[entry_start+4:entry_start+6])[0])		# 2S roll in 0.01 deg
		ATT['PITCH'].append(struct.unpack('h', dg[entry_start+6:entry_start+8])[0])		# 2S pitch in 0.01 deg
		ATT['HEAVE'].append(struct.unpack('h', dg[entry_start+8:entry_start+10])[0])	# 2S heave in cm 
		ATT['HDG'].append(struct.unpack('H', dg[entry_start+10:entry_start+12])[0])		# 2U heading in 0.01 deg		
		entry_start = entry_start + entry_length
		
	ATT['SENSOR_DESC'] = struct.unpack('B', dg[entry_start:entry_start+1])[0]	# 1U sensor system descriptor
	ATT['ETX'] =			struct.unpack('B', dg[-3:-2])[0]					# ETX 1U
	ATT['CHECKSUM'] = 		struct.unpack('H', dg[-2:])[0]						# CHECKSUM 2U

	# for field, value in ATT.items():
	# 	print(field, value)

	return(ATT)


#%% CLOCK datagram (UPDATED FOR PYTHON 3) ###########################################################
def CLOCK_dg(dg):

	T = {}

	T['STX'] =				struct.unpack('B', dg[0:1])[0]		# STX 1U
	T['ID'] = 				struct.unpack('B', dg[1:2])[0]		# ID 1U	
	T['MODEL'] = 			struct.unpack('H', dg[2:4])[0]		# EM MODEL 2U
	T['DATE'] = 			struct.unpack('I', dg[4:8])[0]		# DATE in YYYYMMDD 4U
	T['TIME'] = 			struct.unpack('I', dg[8:12])[0]		# TIME in ms since midnight 4U
	T['CLOCK_COUNTER'] = 	struct.unpack('H', dg[12:14])[0]	# CLOCK COUNTER 2U
	T['SYS_SN'] = 			struct.unpack('H', dg[14:16])[0]	# SYS SN 2U
	T['DATE_EXTERNAL'] = 	struct.unpack('I', dg[16:20])[0]	# DATE EXTERNAL in YYYYMMDD 4U
	T['TIME_EXTERNAL'] = 	struct.unpack('I', dg[20:24])[0]	# TIME EXTERNAL in ms since midnight 4U
	T['PPS'] = 				struct.unpack('B', dg[24:25])[0]	# PPS activated (1 = active) 1U
	T['ETX'] = 				struct.unpack('B', dg[25:26])[0]	# ETX 1U
	T['CHECKSUM'] = 		struct.unpack('H', dg[26:28])[0]	# CHECKSUM 2U
	
	# Print warnings for invalid data
	if T['TIME'] < 0 or T['TIME'] > 86399999:
		print('TIME outside of valid range')		
	if T['CLOCK_COUNTER'] < 0 or T['CLOCK_COUNTER'] > 65535:
		print('CLOCK_COUNTER outside of valid range')		
	if T['TIME_EXTERNAL'] < 0 or T['TIME_EXTERNAL'] > 86399999:
		print('TIME_EXTERNAL outside of valid range')

	# for field, value in T.items():
	# 	print(field, value)

	return(T)


#%% INSTALLATION PARAMETER (UPDATED FOR PYTHON 3) ###################################################
def IP_dg(dg):

	IP = {} # dict of installation params (IP_ID fields in order of EM datagram format document)

	IP['STX'] = 		struct.unpack('B', dg[0:1])[0]		# STX 1U
	IP['ID'] = 			struct.unpack('B', dg[1:2])[0]		# ID 1U	
	IP['MODEL'] =		struct.unpack('H', dg[2:4])[0]		# EM MODEL 2U
	IP['DATE'] =		struct.unpack('I', dg[4:8])[0]		# DATE 4U
	IP['TIME'] =		struct.unpack('I', dg[8:12])[0]		# TIME 4U
	IP['LINE_NUM'] =	struct.unpack('H', dg[12:14])[0]	# SURV LINE NUM 2U
	IP['SYS_SN'] = 		struct.unpack('H', dg[14:16])[0]	# SYS SN 2U
	IP['HEAD_2_SN'] =	struct.unpack('H', dg[16:18])[0]	# HEAD 2 SN 2U

	IP_ID = ['WLZ', 'SMH', 'HUN', 'HUT',\
		'S1Z', 'S1X', 'S1Y', 'S1H', 'S1R', 'S1P', 'S1N',\
		'S2Z', 'S2X', 'S2Y', 'S2H', 'S2R', 'S2P', 'S2N',\
		'S1S', 'S2S', 'GO1', 'GO2', 'OBO', 'FGD',\
		'TSV', 'RSV', 'BSV', 'PSV', 'DDS', 'OSV',\
		'DSV', 'DSX', 'DSY', 'DSZ', 'DSD', 'DSO', 'DSF', 'DSH',\
		'APS',\
		'P1M', 'P1T', 'P1Z', 'P1X', 'P1Y', 'P1D', 'P1G',\
		'P2M', 'P2T', 'P2Z', 'P2X', 'P2Y', 'P2D', 'P2G',\
		'P3M', 'P3T', 'P3Z', 'P3X', 'P3Y', 'P3D', 'P3G', 'P3S',\
		'MSZ', 'MSX', 'MSY', 'MRP', 'MSD', 'MSR', 'MSP', 'MSG',\
		'NSZ', 'NSX', 'NSY', 'NRP', 'NSD', 'NSR', 'NSP', 'NSG',\
		'GCG', 'MAS', 'SHC', 'AHS', 'ARO', 'API', 'AHE',\
		'CLS', 'CLO', 'VSN', 'VSU', 'VSE', 'VSI', 'VSM',\
		'MCAn', 'MCUn', 'MCIn', 'MCPn', 'CPR', 'ROP', 'SID',\
		'RFN', 'PLL', 'COM']

	for i in range(len(IP_ID)):		# Search for parameter IDs in ASCII datagram and store value

		IP[IP_ID[i]] = 'N/A'
		IP_ID_len = len(IP_ID[i])	# declare length of parameter ID and logical for searching
		IP_ID_search = 1			# param_ID_fmt = param_ID_len*'s'
		str_start = 18
		
		#### NEED TO REWRITE / SIMPLIFY SEARCH FOR IP PARAMS IN ASCII
		while IP_ID_search and str_start + IP_ID_len < len(dg)-4:	# loop through ASCII data

			temp_str = dg[str_start:str_start+IP_ID_len].decode("utf-8") # search for IP ID in temp string

			if IP_ID[i] == temp_str: 	# find IP ID match in IP string
				IP_ID_search = 0		# stop searching for this IP ID
				comma_search = 1		# find comma at end of field
				comma_idx = str_start + IP_ID_len
				
				while comma_search:
					temp_str = dg[comma_idx:comma_idx+1].decode("utf-8") # python 3

					if temp_str == ',':
						comma_search = 0
					else:
						comma_idx = comma_idx + 1
			
				temp_str = dg[str_start + IP_ID_len + 1:comma_idx].decode("utf-8")	# isolate parameter value

				try:								
					temp_float = float(temp_str)			# convert to float if possible
					IP[IP_ID[i]] = temp_float 	# dict
					
				except:
					IP[IP_ID[i]] = temp_str 		# dict
					
			else:
				str_start = str_start + 1

	# Continue with remainder of datagram	
	IP['ETX'] =			struct.unpack('B', dg[-3:-2])[0]	# ETX 1U
	IP['CHECKSUM'] = 	struct.unpack('H', dg[-2:])[0]		# CHECKSUM 2U
		
	# for field, value in IP.items():
		# print(field, value)

	return(IP)


#%% RAW RANGE ANGLE 78 (supercedes RRA (f) from 2004) (UPDATED FOR PYTHON 3) ########################
# Used for EM2040, EM710, EM302, EM122, ME70
def RRA_78_dg(dg):

	RRA = {}

	RRA['STX'] = 			struct.unpack('B', dg[0:1])[0]		# STX 1U
	RRA['ID'] = 			struct.unpack('B', dg[1:2])[0]		# ID 1U	
	RRA['MODEL'] = 			struct.unpack('H', dg[2:4])[0]		# EM MODEL 2U
	RRA['DATE'] = 			struct.unpack('I', dg[4:8])[0]		# DATE 4U
	RRA['TIME'] = 			struct.unpack('I', dg[8:12])[0]		# TIME 4U
	RRA['PING_COUNTER'] = 	struct.unpack('H', dg[12:14])[0]	# PING COUNTER 2U
	RRA['SYS_SN'] = 		struct.unpack('H', dg[14:16])[0]	# SYS SN 2U
	RRA['SS_SURFACE'] =		struct.unpack('H', dg[16:18])[0]	# SURFACE SOUND SPEED in 0.1 m/s
	RRA['NUM_TX_SECTORS'] = struct.unpack('H', dg[18:20])[0]	# NUM TX SECTORS 2U - (Ntx)
	RRA['NUM_RX_BEAMS'] =	struct.unpack('H', dg[20:22])[0]	# NUM RX BEAMS 2U - (N)
	RRA['NUM_VALID_DET'] =	struct.unpack('H', dg[22:24])[0]	# NUM VALID DETECTIONS 2U
	RRA['SAMPLING_FREQ'] =	struct.unpack('f', dg[24:28])[0]	# SAMPLING FREQ IN Hz 4F
	RRA['DSCALE'] =			struct.unpack('I', dg[28:32])[0]	# DSCALE Doppler correction see note 5, 4U

	# declare TX fields
	TX_FIELDS = ['TX_TILT', 'TX_FOCUS_RANGE', 'TX_SIG_LEN', 'TX_SEC_DELAY', 'TX_CENTER_FREQ',\
					'TX_ABS_COEFF', 'TX_WAVEFORM_ID', 'TX_SEC_NUM', 'TX_BANDWIDTH']

	for i in range(len(TX_FIELDS)):
		RRA[TX_FIELDS[i]] = []

	# Store raw range and angle TRANSMIT data from all valid TX sectors in datagram
	entry_start = 32
	entry_length = 24
#	dg_continue = entry_start + (entry_length*RRA['NUM_TX_SECTORS'])
	
	for i in range(RRA['NUM_TX_SECTORS']):
		RRA['TX_TILT'].append(struct.unpack('h', dg[entry_start:entry_start+2])[0])				# 2S tilt re TX array in 0.01 deg
		RRA['TX_FOCUS_RANGE'].append(struct.unpack('H', dg[entry_start+2:entry_start+4])[0])	# 2U focus range in 0.1 m
		RRA['TX_SIG_LEN'].append(struct.unpack('f', dg[entry_start+4:entry_start+8])[0])		# 4F signal length in s
		RRA['TX_SEC_DELAY'].append(struct.unpack('f', dg[entry_start+8:entry_start+12])[0])		# 4F sector delay in s
		RRA['TX_CENTER_FREQ'].append(struct.unpack('f', dg[entry_start+12:entry_start+16])[0])	# 4F center frequency in Hz
		RRA['TX_ABS_COEFF'].append(struct.unpack('H', dg[entry_start+16:entry_start+18])[0])	# 2U mean abs coeff in 0.01 dB/km
		RRA['TX_WAVEFORM_ID'].append(struct.unpack('B', dg[entry_start+18:entry_start+19])[0])	# 1U signal waveform ID
		RRA['TX_SEC_NUM'].append(struct.unpack('B', dg[entry_start+19:entry_start+20])[0])		# 1U sector number
		RRA['TX_BANDWIDTH'].append(struct.unpack('f', dg[entry_start+20:entry_start+24])[0])	# 4F sector bandwidth in Hz
		entry_start = entry_start + entry_length

	# declare RX fields
	RX_FIELDS = ['RX_ANGLE', 'RX_TX_SEC_NUM', 'RX_DET_INFO', 'RX_DET_WINDOW', 'RX_QUAL_FAC',\
					'RX_D_CORR', 'RX_TWTT', 'RX_BS', 'RX_CLEAN_INFO', 'RX_SPARE']

	for i in range(len(RX_FIELDS)):
		RRA[RX_FIELDS[i]] = []
	
	# # Store raw range and angle RECEIVE data from all valid RX beams in datagram	
	entry_length = 16
	
	# dg_continue = entry_start + (entry_length*RRA['NUM_RX_BEAMS'])
	
	for i in range(RRA['NUM_RX_BEAMS']):
		RRA['RX_ANGLE'].append(struct.unpack('h', dg[entry_start:entry_start+2])[0])			# 2S RX beam pointing angle re RX array in 0.01 deg
		RRA['RX_TX_SEC_NUM'].append(struct.unpack('B', dg[entry_start+2:entry_start+3])[0])		# 1U TX sector number associated with RX beam
		RRA['RX_DET_INFO'].append(struct.unpack('B', dg[entry_start+3:entry_start+4])[0])		# 1U RX detection info see KM doc note 3 
		RRA['RX_DET_WINDOW'].append(struct.unpack('H', dg[entry_start+4:entry_start+6])[0])		# 2U RX detection window length in samples
		RRA['RX_QUAL_FAC'].append(struct.unpack('B', dg[entry_start+6:entry_start+7])[0])		# 1U RX quality factor see KM doc note 2
		RRA['RX_D_CORR'].append(struct.unpack('b', dg[entry_start+7:entry_start+8])[0])			# 1S RX Doppler correction see KM doc note 5
		RRA['RX_TWTT'].append(struct.unpack('f', dg[entry_start+8:entry_start+12])[0])			# 4F RX two-way travel time in s see KM doc note 5
		RRA['RX_BS'].append(struct.unpack('h', dg[entry_start+12:entry_start+14])[0])			# 2S RX reflectivity in 0.1 dB
		RRA['RX_CLEAN_INFO'].append(struct.unpack('b', dg[entry_start+14:entry_start+15])[0]) 	# 1S RX realtime cleaning info see KM doc note 4
		RRA['RX_SPARE'].append(struct.unpack('B', dg[entry_start+15:entry_start+16])[0])		
		entry_start = entry_start + entry_length

	RRA['SPARE'] =		struct.unpack('B', dg[entry_start:entry_start+1])[0]	# SPARE 1U
	RRA['ETX'] = 		struct.unpack('B', dg[-3:-2])[0]						# ETX 1U
	RRA['CHECKSUM'] = 	struct.unpack('H', dg[-2:])[0]							# CHECKSUM 2U

	# print('************************************ RRA **************************************')
	# for field, value in RRA.items():
	# 	print(field, value)
	
	return(RRA)


#%% POSITION (UPDATED FOR PYTHON 3) #################################################################
def POS_dg(dg):

	POS = {}

	POS['STX'] = 		struct.unpack('B', dg[0:1])[0]		# STX 1U
	POS['ID'] = 		struct.unpack('B', dg[1:2])[0]		# ID 1U	
	POS['MODEL'] =		struct.unpack('H', dg[2:4])[0]		# EM MODEL 2U
	POS['DATE'] =		struct.unpack('I', dg[4:8])[0]		# DATE 4U
	POS['TIME'] =		struct.unpack('I', dg[8:12])[0]		# TIME 4U
	POS['COUNT'] = 		struct.unpack('H', dg[12:14])[0]	# POSITION COUNTER 2U
	POS['SYS_SN'] = 	struct.unpack('H', dg[14:16])[0]	# SYS SN 2U
	POS['LAT'] =		struct.unpack('i', dg[16:20])[0]	# LAT 4S
	POS['LON'] =		struct.unpack('i', dg[20:24])[0]	# LON 4S
	POS['FIX_QUAL'] =	struct.unpack('H', dg[24:26])[0]	# FIX QUALITY 2U
	POS['SOG'] =		struct.unpack('H', dg[26:28])[0]	# SOG 2U
	POS['COG'] =		struct.unpack('H', dg[28:30])[0]	# COG 2U
	POS['HEADING'] =	struct.unpack('H', dg[32:34])[0]	# HEADING 2U
	POS['SYS_DESC'] =	struct.unpack('B', dg[34:35])[0]	# POS SYS DESC 1U
	POS['INPUT_LEN'] =	struct.unpack('B', dg[35:36])[0]	# BYTES INPUT 1U

	# Unpack pos input string and convert to string
	POS['INPUT_STR'] = dg[36:len(dg)-3].decode("utf-8")
	
	POS['ETX'] = 			struct.unpack('B', dg[-3:-2])[0]	# ETX 1U
	POS['CHECKSUM'] = 		struct.unpack('H', dg[-2:])[0]		# CHECKSUM 2U
	
	# for field, value in POS.items():
	# 	print(field, value)

	return(POS)


#%% RUNTIME PARAM (UPDATED FOR PYTHON 3) ############################################################
def RTP_dg(dg):

	RTP = {}

	RTP['STX'] = 			struct.unpack('B', dg[0:1])[0]		# STX 1U
	RTP['ID'] = 			struct.unpack('B', dg[1:2])[0]		# ID 1U	
	RTP['MODEL'] = 			struct.unpack('H', dg[2:4])[0]		# EM MODEL 2U
	RTP['DATE'] = 			struct.unpack('I', dg[4:8])[0]		# DATE 4U
	RTP['TIME'] = 			struct.unpack('I', dg[8:12])[0]		# TIME 4U
	RTP['PING_COUNTER'] = 	struct.unpack('H', dg[12:14])[0]	# PING COUNTER 2U
	RTP['SYS_SN'] = 		struct.unpack('H', dg[14:16])[0]	# SYS SN 2U
	RTP['OPR_STN_STATUS'] =	struct.unpack('B', dg[16:17])[0]	# OPR_STN_STATUS 1U
	RTP['CPU_STATUS'] =		struct.unpack('B', dg[17:18])[0]	# CPU STATUS 1U
	RTP['BSP_STATUS'] =		struct.unpack('B', dg[18:19])[0]	# BSP STATUS 1U
	RTP['SON_HD_STATUS'] =	struct.unpack('B', dg[19:20])[0]	# SON HD STATUS 1U
	RTP['MODE'] =			struct.unpack('B', dg[20:21])[0]	# MODE 1U
	RTP['FILTER_ID'] =		struct.unpack('B', dg[21:22])[0]	# FILTER ID 1U
	RTP['MIN_DEPTH'] =		struct.unpack('H', dg[22:24])[0]	# MIN DEPTH 2U
	RTP['MAX_DEPTH'] =		struct.unpack('H', dg[24:26])[0]	# MAX DEPTH 2U
	RTP['ABS_COEFF'] =		struct.unpack('H', dg[26:28])[0]	# ABS COEFF 2U
	RTP['TX_PULSE_LEN'] =	struct.unpack('H', dg[28:30])[0]	# TX PULSE LEN 2U
	RTP['TX_BEAMWIDTH'] =	struct.unpack('H', dg[30:32])[0]	# TX BEAMWIDTH 2U
	RTP['TX_POWER'] =		struct.unpack('b', dg[32:33])[0]	# TX POWER 1S
	RTP['RX_BEAMWIDTH'] =	struct.unpack('B', dg[33:34])[0]	# RX BEAMWIDTH 1U
	RTP['RX_BANDWIDTH'] =	struct.unpack('B', dg[34:35])[0]	# RX BANDWIDTH 1U
	RTP['RX_FIXED_GAIN'] =	struct.unpack('B', dg[35:36])[0]	# RX FIXED GAIN 1U
	RTP['TVG_LAW_ANGLE'] =	struct.unpack('B', dg[36:37])[0]	# TVG LAW ANGLE 1U
	RTP['SS_SOURCE'] =		struct.unpack('B', dg[37:38])[0]	# SS SOURCE 1U
	RTP['MAX_PORT_SWATH'] = struct.unpack('H', dg[38:40])[0]	# MAX PORT SWATH 2U
	RTP['BEAM_SPACING'] =	struct.unpack('B', dg[40:41])[0]	# BEAM SPACING 1U
	RTP['MAX_PORT_COV'] =	struct.unpack('B', dg[41:42])[0]	# MAX PORT COV 1U
	RTP['Y_P_STAB_MODE'] =	struct.unpack('B', dg[42:43])[0]	# Y P STAB MODE 1U
	RTP['MAX_STBD_COV'] =	struct.unpack('B', dg[43:44])[0]	# MAX STBR COV 1U
	RTP['MAX_STBD_SWATH'] =	struct.unpack('H', dg[44:46])[0]	# MAX STBR SWATH 2U
	RTP['TX_ALONG_TILT'] = 	struct.unpack('h', dg[46:48])[0]	# TX ALONG TILT 2S
	RTP['FILTER_ID_2'] =	struct.unpack('B', dg[48:49])[0]	# FILTER ID 2
	RTP['ETX'] =			struct.unpack('B', dg[49:50])[0]	# ETX 1U
	RTP['CHECKSUM'] =		struct.unpack('H', dg[50:52])[0]	# CHECKSUM 2U
	
	# print('************************************ RTP **************************************')
	# for field, value in RTP.items():
	# 	print(field, value)

	return(RTP)

		
#%% SOUND SPEED PROFILE (UPDATED FOR PYTHON 3) ######################################################
def SSP_dg(dg):

	SSP = {}

	SSP['STX'] = 			struct.unpack('B', dg[0:1])[0]		# STX 1U
	SSP['ID'] = 			struct.unpack('B', dg[1:2])[0]		# ID 1U	
	SSP['MODEL'] = 			struct.unpack('H', dg[2:4])[0]		# EM MODEL 2U
	SSP['DATE'] = 			struct.unpack('I', dg[4:8])[0]		# DATE 4U
	SSP['TIME'] = 			struct.unpack('I', dg[8:12])[0]		# TIME 4U
	SSP['PROF_COUNTER'] = 	struct.unpack('H', dg[12:14])[0]	# PROF COUNTER 2U
	SSP['SYS_SN'] = 		struct.unpack('H', dg[14:16])[0]	# SYS SN 2U
	SSP['PROFILE_DATE'] = 	struct.unpack('I', dg[16:20])[0]	# PROFILE DATE 4U
	SSP['PROFILE_TIME'] =	struct.unpack('I', dg[20:24])[0]	# PROFILE TIME 4U
	SSP['NUM_ENTRIES'] =	struct.unpack('H', dg[24:26])[0]	# NUM ENTRIES 2U
	SSP['DEPTH_RES'] =		struct.unpack('H', dg[26:28])[0]	# DEPTH RES 2U
	
	entry_start = 28
	entry_length = 8

	SSP['DEPTH'] = []
	SSP['SOUND_SPEED'] = []

	for i in range(SSP['NUM_ENTRIES']):
		SSP['DEPTH'].append(struct.unpack('I', dg[entry_start:entry_start+4])[0])			# 4U
		SSP['SOUND_SPEED'].append(struct.unpack('I', dg[entry_start+4:entry_start+8])[0])	# 4U

		entry_start = entry_start + entry_length	

	SSP['ETX'] = struct.unpack('B', dg[-3:-2])[0]				# ETX 1U
	SSP['CHECKSUM'] = struct.unpack('H', dg[-2:])[0]			# CHECKSUM 2U

	# for i in range(len(SSP['DEPTH'])):
	# 	print(SSP['DEPTH'][i], SSP['SOUND_SPEED'][i])

	# print(SSP)

	return(SSP)

    
#%% XYZ88 (UPDATED FOR PYTHON 3) ####################################################################
# Used for EM2040, EM710, EM122, EM302, ME70
def XYZ_dg(dg, parse_outermost_only = False):
    
    XYZ = {}
    
    XYZ['STX'] = 			struct.unpack('B', dg[0:1])[0]		# STX 1U
    XYZ['ID'] = 			struct.unpack('B', dg[1:2])[0]		# ID 1U	
    XYZ['MODEL'] = 			struct.unpack('H', dg[2:4])[0]		# EM MODEL 2U
    XYZ['DATE'] = 			struct.unpack('I', dg[4:8])[0]		# DATE 4U
    XYZ['TIME'] = 			struct.unpack('I', dg[8:12])[0]		# TIME 4U
    XYZ['PING_COUNTER'] = 	struct.unpack('H', dg[12:14])[0]	# PING COUNTER 2U
    XYZ['SYS_SN'] = 		struct.unpack('H', dg[14:16])[0]	# SYS SN 2U
    XYZ['HEADING'] = 		struct.unpack('H', dg[16:18])[0]	# HEADING AT TX TIME 2U
    XYZ['SS_SURFACE'] =   	struct.unpack('H', dg[18:20])[0]  	# 2U SURFACE SOUND SPEED IN 0.1 m/s
    XYZ['TX_TRANS_Z'] =   	struct.unpack('f', dg[20:24])[0]  	# 4F TRANSMITTER DEPTH AT TX IN m
    XYZ['NUM_RX_BEAMS'] = 	struct.unpack('H', dg[24:26])[0]	# 2U NUMBER OF RX BEAMS IN DATAGRAM
    XYZ['NUM_DETECT'] =		struct.unpack('H', dg[26:28])[0]	# 2U NUMBER OF VALID DETECTIONS
    XYZ['F_SAMPLE'] =		struct.unpack('f', dg[28:32])[0]	# 4F SAMPLING FREQUENCY IN Hz
    XYZ['EM2040_SCAN'] =	struct.unpack('B', dg[32:33])[0]	# 1U SCANNING INFO (EM2040 ONLY)
    XYZ['SPARE2'] =			struct.unpack('BBB', dg[33:36])[0] 	# 3U SPARE AFTER EM2040 SCANNING BYTE
    
    RX_FIELDS = ['RX_DEPTH', 'RX_ACROSS', 'RX_ALONG', 'RX_DET_WIN', 'RX_QUAL_FAC',\
	'RX_IBA', 'RX_DET_INFO', 'RX_CLEAN', 'RX_BS']
    
    for i in range(len(RX_FIELDS)):
        XYZ[RX_FIELDS[i]] = []
    
    entry_start = 36 # start of XYZ entries for beam 0
    entry_length = 20 # length of XYZ entry for each beam
    N_beams_parse = XYZ['NUM_RX_BEAMS'] # number of RX beams to parse
    
    if parse_outermost_only is True: # determine indices of outermost valid soundings and parse only those
#        print('parsing outermost only')
        det_int = [] # detection info integers for all beams across swath
        
        for i in range(XYZ['NUM_RX_BEAMS']): # read RX_DET_INFO for all beams in datagram
            det_int.append(struct.unpack('B', dg[entry_start+16:entry_start+17])[0])	# 1U SEE KM DOC NOTE 
            entry_start = entry_start + entry_length
        
        # find indices of port and stbd outermost valid detections
        # leading bit of det info field is 0 for valid detections (integer < 128)
        idx_port = 0				# start at port outer sounding
        idx_stbd = len(det_int)-1	# start at stbd outer sounding
    
        while det_int[idx_port] >= 128 and idx_port <= len(det_int):
            # print('at port index', idx_port, 'the det_int is', det_int[idx_port])
            idx_port = idx_port + 1 # move port idx to stbd if not valid
    
        while det_int[idx_stbd] >= 128 and idx_stbd >= 0:
            # print('at stbd index', idx_stbd, 'the det_int is', det_int[idx_stbd])
            idx_stbd = idx_stbd - 1 # move stdb idx to port if not valid
        
        # reset file pointers to parse only the outermost valid detections identified above
        entry_start = 36 + (idx_port)*20 # start of entries for farthest port valid sounding
        entry_length = 20*(idx_stbd - idx_port) # length from port valid sounding to start of farthest stbd valid sounding
        N_beams_parse = 2 # parse only the two RX beams associated with these port and stbd indices
    
#    print(N_beams_parse)
#    for i in range(XYZ['NUM_RX_BEAMS']):
    for i in range(N_beams_parse):
#    for i in RX_beam_range:
#        print(i)
        XYZ['RX_DEPTH'].append(struct.unpack('f', dg[entry_start:entry_start+4])[0]) 		# 4F DEPTH IN m
        XYZ['RX_ACROSS'].append(struct.unpack('f', dg[entry_start+4:entry_start+8])[0])		# 4F ACROSSTRACK DISTANCE IN m
        XYZ['RX_ALONG'].append(struct.unpack('f', dg[entry_start+8:entry_start+12])[0])		# 4F ALONGTRACK DISTANC IN m
        XYZ['RX_DET_WIN'].append(struct.unpack('H', dg[entry_start+12:entry_start+14])[0])	# 2U DETECTION WINDOW IN SAMPLES
        XYZ['RX_QUAL_FAC'].append(struct.unpack('B', dg[entry_start+14:entry_start+15])[0])	# 1U QUALITY FACTOR SEE KM NOTE 3
        XYZ['RX_IBA'].append(struct.unpack('b', dg[entry_start+15:entry_start+16])[0])		# 1S INCID. ANGLE ADJ. IN 0.1 DEG
        XYZ['RX_DET_INFO'].append(struct.unpack('B', dg[entry_start+16:entry_start+17])[0])	# 1U SEE KM DOC NOTE 4
        # XYZ['RX_DET_INFO_BIN'].append("{0:b}".format([XYZ]['RX_DET_INFO'][i]).zfill(8))		# store the binary format
        XYZ['RX_CLEAN'].append(struct.unpack('b', dg[entry_start+17:entry_start+18])[0])	# 1S REALTIME CLEANING INFO
        XYZ['RX_BS'].append(struct.unpack('h', dg[entry_start+18:entry_start+20])[0])		# 2S REFLECTIVITY IN 0.1 dB
        
        entry_start = entry_start + entry_length
    
    # reset pointer to end of RX beams to finish parsing rest of dg
    entry_start = 36 + XYZ['NUM_RX_BEAMS']*20 

    XYZ['SPARE'] =		struct.unpack('B', dg[entry_start:entry_start+1])[0] 	# 1U
    XYZ['ETX'] = 		struct.unpack('B', dg[-3:-2])[0]	# ETX 1U
    XYZ['CHECKSUM'] = 	struct.unpack('H', dg[-2:])[0]		# CHECKSUM 2U
    
    return(XYZ)
    
#    #%% XYZ88 (UPDATED FOR PYTHON 3) ####################################################################
## Used for EM2040, EM710, EM122, EM302, ME70
#def XYZ_OUTERMOST_dg(dg):
#    
#    XYZ = {}
#    
#    XYZ['STX'] = 			struct.unpack('B', dg[0:1])[0]		# STX 1U
#    XYZ['ID'] = 			struct.unpack('B', dg[1:2])[0]		# ID 1U	
#    XYZ['MODEL'] = 			struct.unpack('H', dg[2:4])[0]		# EM MODEL 2U
#    XYZ['DATE'] = 			struct.unpack('I', dg[4:8])[0]		# DATE 4U
#    XYZ['TIME'] = 			struct.unpack('I', dg[8:12])[0]		# TIME 4U
#    XYZ['PING_COUNTER'] = 	struct.unpack('H', dg[12:14])[0]	# PING COUNTER 2U
#    XYZ['SYS_SN'] = 		struct.unpack('H', dg[14:16])[0]	# SYS SN 2U
#    XYZ['HEADING'] = 		struct.unpack('H', dg[16:18])[0]	# HEADING AT TX TIME 2U
#    XYZ['SS_SURFACE'] =   	struct.unpack('H', dg[18:20])[0]  	# 2U SURFACE SOUND SPEED IN 0.1 m/s
#    XYZ['TX_TRANS_Z'] =   	struct.unpack('f', dg[20:24])[0]  	# 4F TRANSMITTER DEPTH AT TX IN m
#    XYZ['NUM_RX_BEAMS'] = 	struct.unpack('H', dg[24:26])[0]	# 2U NUMBER OF RX BEAMS IN DATAGRAM
#    XYZ['NUM_DETECT'] =		struct.unpack('H', dg[26:28])[0]	# 2U NUMBER OF VALID DETECTIONS
#    XYZ['F_SAMPLE'] =		struct.unpack('f', dg[28:32])[0]	# 4F SAMPLING FREQUENCY IN Hz
#    XYZ['EM2040_SCAN'] =	struct.unpack('B', dg[32:33])[0]	# 1U SCANNING INFO (EM2040 ONLY)
#    XYZ['SPARE2'] =			struct.unpack('BBB', dg[33:36])[0] 	# 3U SPARE AFTER EM2040 SCANNING BYTE
#    
#    RX_FIELDS = ['RX_DEPTH', 'RX_ACROSS', 'RX_ALONG', 'RX_DET_WIN', 'RX_QUAL_FAC',\
#	'RX_IBA', 'RX_DET_INFO', 'RX_CLEAN', 'RX_BS']
#    
#    for i in range(len(RX_FIELDS)):
#        XYZ[RX_FIELDS[i]] = []
#        
#    entry_start = 36
#    entry_length = 20
#
#    det_int = [] # det info integers across swath
#    # start reading RX_DET_INFO fields only for each datagram
#    for i in range(XYZ['NUM_RX_BEAMS']):
#        det_int.append(struct.unpack('B', dg[entry_start+16:entry_start+17])[0])	# 1U SEE KM DOC NOTE 
#        entry_start = entry_start + entry_length
#    
#    # find indices of port and stbd outermost valid detections
#    # leading bit of det info field is 0 for valid detections (integer < 128)
#    idx_port = 0				# start at port outer sounding
#    idx_stbd = len(det_int)-1	# start at stbd outer sounding
#
##    print('sorting det_info')
#    while det_int[idx_port] >= 128 and idx_port <= len(det_int):
#        # print('at port index', idx_port, 'the det_int is', det_int[idx_port])
#        idx_port = idx_port + 1 # move port idx to stbd if not valid
#
#    while det_int[idx_stbd] >= 128 and idx_stbd >= 0:
#        # print('at stbd index', idx_stbd, 'the det_int is', det_int[idx_stbd])
#        idx_stbd = idx_stbd - 1 # move stdb idx to port if not valid
#    
#    # reset file pointers to parse only the outermost valid detections
#    entry_start = 36 + (idx_port)*20 # start of entries for farthest port valid sounding
#    entry_length = 20*(idx_stbd - idx_port) # length from port valid sounding to start of farthest stbd valid sounding 
#    
##    print
#    for i in range(2): # parse only two outermost valid soundings
##    for i in RX_beam_range:
##        print(i)
#        XYZ['RX_DEPTH'].append(struct.unpack('f', dg[entry_start:entry_start+4])[0]) 		# 4F DEPTH IN m
#        XYZ['RX_ACROSS'].append(struct.unpack('f', dg[entry_start+4:entry_start+8])[0])		# 4F ACROSSTRACK DISTANCE IN m
#        XYZ['RX_ALONG'].append(struct.unpack('f', dg[entry_start+8:entry_start+12])[0])		# 4F ALONGTRACK DISTANC IN m
#        XYZ['RX_DET_WIN'].append(struct.unpack('H', dg[entry_start+12:entry_start+14])[0])	# 2U DETECTION WINDOW IN SAMPLES
#        XYZ['RX_QUAL_FAC'].append(struct.unpack('B', dg[entry_start+14:entry_start+15])[0])	# 1U QUALITY FACTOR SEE KM NOTE 3
#        XYZ['RX_IBA'].append(struct.unpack('b', dg[entry_start+15:entry_start+16])[0])		# 1S INCID. ANGLE ADJ. IN 0.1 DEG
#        XYZ['RX_DET_INFO'].append(struct.unpack('B', dg[entry_start+16:entry_start+17])[0])	# 1U SEE KM DOC NOTE 4
#        # XYZ['RX_DET_INFO_BIN'].append("{0:b}".format([XYZ]['RX_DET_INFO'][i]).zfill(8))		# store the binary format
#        XYZ['RX_CLEAN'].append(struct.unpack('b', dg[entry_start+17:entry_start+18])[0])	# 1S REALTIME CLEANING INFO
#        XYZ['RX_BS'].append(struct.unpack('h', dg[entry_start+18:entry_start+20])[0])		# 2S REFLECTIVITY IN 0.1 dB
#        
#        entry_start = entry_start + entry_length
#        
##    if parse_coverage_only is True: # undo the pointer skip from last iteration of loop
##        entry_start = entry_start - entry_skip
#    
#    entry_start = 36 + XYZ['NUM_RX_BEAMS']*20 # reset pointer to end of soundings to finish parsing 
#    XYZ['SPARE'] =		struct.unpack('B', dg[entry_start:entry_start+1])[0] 	# 1U
#    XYZ['ETX'] = 		struct.unpack('B', dg[-3:-2])[0]	# ETX 1U
#    XYZ['CHECKSUM'] = 	struct.unpack('H', dg[-2:])[0]		# CHECKSUM 2U
#    
#    return(XYZ)

# %% SEABED IMAGE 89 datagram (UPDATED FOR PYTHON 3) ########################################################
def SBI_89_dg(dg):
	SBI = {}

	SBI['STX'] = struct.unpack('B', dg[0:1])[0]  # STX 1U
	SBI['ID'] = struct.unpack('B', dg[1:2])[0]  # ID 1U
	SBI['MODEL'] = struct.unpack('H', dg[2:4])[0]  # EM MODEL 2U
	SBI['DATE'] = struct.unpack('I', dg[4:8])[0]  # DATE 4U
	SBI['TIME'] = struct.unpack('I', dg[8:12])[0]  # TIME 4U
	SBI['PING_COUNTER'] = struct.unpack('H', dg[12:14])[0]  # PING COUNTER 2U
	SBI['SYS_SN'] = struct.unpack('H', dg[14:16])[0]  # SYS SN 2U
	SBI['SAMPLING_FREQ'] =	struct.unpack('f', dg[16:20])[0]	# SAMPLING FREQ IN Hz 4F
	SBI['RANGE_TO_NORMAL'] = struct.unpack('H', dg[20:22])[0]	# RANGE TO NORMAL INCIDENCE IN NUM SAMPLES 2U
	SBI['BSN'] = struct.unpack('h', dg[22:24])[0]			# 2S BS at normal incidence in 0.1 dB
	SBI['BSO'] = struct.unpack('h', dg[24:26])[0]			# 2S BS at oblique incidence in 0.1 dB
	SBI['TX_BEAMWIDTH'] = struct.unpack('H', dg[26:28])[0]	# 2U TX BEAMWIDTH ALONG IN 0.1 DEG
	SBI['TVG_CROSSOVER'] = struct.unpack('H', dg[28:30])[0]	# 2U TVG LAW CROSSOVER ANGLE IN 0.1 DEG
	SBI['NUM_VALID_BEAMS'] = struct.unpack('H', dg[30:32])[0]	# 2U NUM VALID BEAMS

	SBI_FIELDS = ['SORT_DIR', 'DET_INFO', 'NUM_SAMPLES', 'CENTER_SAMPLE_NUM'] # seabed image entry fields

	for i in range(len(SBI_FIELDS)):
		SBI[SBI_FIELDS[i]] = []

	entry_start = 32
	entry_length = 6

	for i in range(SBI['NUM_VALID_BEAMS']):
		SBI['SORT_DIR'].append(struct.unpack('b', dg[entry_start:entry_start+1])[0])  	# 1S sorting direction
		SBI['DET_INFO'].append(struct.unpack('B', dg[entry_start+1:entry_start+2])[0])  # 1U detection info
		SBI['NUM_SAMPLES'].append(struct.unpack('H', dg[entry_start+2:entry_start+4])[0])  # 2U number of samples / beam
		SBI['CENTER_SAMPLE_NUM'].append(struct.unpack('H', dg[entry_start+4:entry_start+6])[0])  # 2U center sample num
		entry_start = entry_start + entry_length

	SBI['AMPLITUDE'] = []

	for i in range(sum(SBI['NUM_SAMPLES'])):
		SBI['AMPLITUDE'].append(struct.unpack('h', dg[entry_start:entry_start+2])[0]) # 2S sample amplitude
		entry_start = entry_start + 2

	SBI['SPARE'] = struct.unpack('B', dg[entry_start:entry_start+1])[0]	# SPARE 1U
	SBI['ETX'] = struct.unpack('B', dg[-3:-2])[0]  # ETX 1U
	SBI['CHECKSUM'] = struct.unpack('H', dg[-2:])[0]  # CHECKSUM 2U

	return (SBI)