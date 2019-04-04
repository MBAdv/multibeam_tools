
# From Kongsberg manual:
# A "datagram" begins with STX, ID and ends with ETX, CHECKSUM
# This script adheres to this definition

# This script does NOT parse watercolumn or seabed image datagrams

import sys, parseEM, utm, numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
from scipy import interpolate

def parseEMfile(filename, parse_list = 0, print_updates = False, parse_outermost_only = False):
#def parseEMfile(self, filename, parse_list = 0, print_updates = False, update_prog_bar = False):

    print("\nParsing file:", filename)
    
    # Open and read the .all file
    # filename = '0248_20160911_191203_Oden.all'
    f = open(filename, 'rb')
    raw = f.read()
    len_raw = len(raw)

    # Declare lists for keeping track of datagram types available to parse
    dg_list = {'PU': 		49,\
               'ATT':       65,\
               'T':         67,\
               'IP_start':  73,\
               'RRA_78': 	78,\
               'POS': 		80,\
               'RTP':		82,\
               'SSP':		85,\
               'XYZ':		88,\
               'IP_stop':	105}
    
    # review optional input list of datagram IDs to parse (default is parse_list = 0, meaning parse all)
    parse_list_min = [73, 82] # set minimum parse list including IP_START (73) and RUNTIME PARAMETERS (82)
    
    if parse_list != 0: # if optional parse_list is specified, reduce dg_list to unique set of parse_list and parse_list_min
        for field, value in list(dg_list.items()): # loop through dg_list, remove if not requested
            if not np.isin(value, parse_list + parse_list_min):
                del dg_list[field]

    if print_updates:
        print('\nDatagram parsing list:')
        for field, value in dg_list.items():
            print(field, value)

    data = {}	# initialize data dict with remaining datagram fields
    data['fname'] = filename
    for field in dg_list.keys():
        data[field] = {}

    # Declare lists for datagram TOC and each type of parsed data
    dg_TOC = []
    dg_fail = []

    # Declare counters for dg starting byte counter and dg processing counter
    dg_start = 0
    dg_count = 0
    parse_prog_old = -1
    
    # Assign and parse datagram
    while dg_start <= len_raw: #  and dg_count < 10:

        # print progress update
        parse_prog = round(10*dg_start/len_raw)
        if parse_prog > parse_prog_old:
            print("%s%%" % (parse_prog*10), end=" ", flush = True)
            parse_prog_old = parse_prog

        # Select datagram and validate	
        [dg_validity, valid_dg_TOC] = parseEM.validate_dg(raw, dg_start, len_raw)
		        
        # Parse valid datagrams
        if dg_validity == 1:
            dg_TOC.append(valid_dg_TOC)
            dg_count = dg_count + 1
            dg_start = valid_dg_TOC[-2]
            dg_len = valid_dg_TOC[-1]
            dg_ID = valid_dg_TOC[0]
            dg = raw[dg_start:dg_start+dg_len]
    
            # parse valid dg if dg_ID is on the list
            if np.isin(dg_ID, list(dg_list.values())):
    
                # Parse PU STATUS datagram
                if dg_ID == 49:
                    data['PU'][len(data['PU'])] = parseEM.PU_dg(dg)
                    
    				# Parse ATTITUDE datagram
                if dg_ID == 65:
                    data['ATT'][len(data['ATT'])] = parseEM.ATT_dg(dg)
    				
                # Parse CLOCK datagram
                if dg_ID == 67:
                    data['T'][len(data['T'])] = parseEM.CLOCK_dg(dg)
    				
    				# Parse DEPTH datagram (EM3002 ONLY)
    				# WARNING: for EM3002 only (write parser as needed for old data)
    				# if dg_ID == 68:
    				# 	depth.update(parse.depth_dg(dg))
    				
    				# Parse INSTALL PARAM START datagram PYTHON 3
                if dg_ID == 73:
                    # print(len(data['IP_start'].keys()))
                    data['IP_start'][len(data['IP_start'])] = parseEM.IP_dg(dg)
                    # print(len(data['IP_start'].keys()))
    
                # Parse RAW RANGE ANGLE 78 datagram
                if dg_ID == 78:
                    data['RRA_78'][len(data['RRA_78'])] = parseEM.RRA_78_dg(dg)
                    # sys.exit() # exit after first datagram to test print
    				
                # Parse POSITION datagram PYTHON 3
                if dg_ID == 80:
                    data['POS'][len(data['POS'])] = parseEM.POS_dg(dg)
                    # print(len(data['POS'].keys()))
    				
                # Parse RUNTIME PARAM datagram PYTHON 3
                if dg_ID == 82:
                    data['RTP'][len(data['RTP'])] = parseEM.RTP_dg(dg)
    
                # Parse SSP datagram PYTHON 3
                if dg_ID == 85:
                    data['SSP'][len(data['SSP'])] = parseEM.SSP_dg(dg)
    
                # Parse XYZ 88 datagram PYTHON 3
                if dg_ID == 88:
#                    if parse_outermost_only is True:
                    data['XYZ'][len(data['XYZ'])] = parseEM.XYZ_dg(dg, parse_outermost_only) # new parser for outermost valid soundings only
#                    else:
#                        data['XYZ'][len(data['XYZ'])] = parseEM.XYZ_dg(dg)
                        
                    # store last RTP MODE for each ping
                    data['XYZ'][len(data['XYZ'])-1]['MODE'] = data['RTP'][len(data['RTP'])-1]['MODE']
    
                # BEAM_ANGLE datagram (f) (EM120, EM300, EM1002, EM2000, EM3000, EM3002)
                # WARNING: SUPERCEDED BY RRA 78 in 2004 (write parser as needed for old data)
                # if dg_ID == 102:
                # 	raw_range_angle_f.append(parseEM.raw_range_angle_f_dg(dg))
    							
    				# Parse INSTALL PARAM STOP datagram PYTHON 3
                if dg_ID == 105:
                    data['IP_stop'][len(data['IP_stop'])] = parseEM.IP_dg(dg)
    				
    				# Increment counter for each ID
    				# for index in range(len(dg_ID_NUMBERS)):
    				# 	if dg_ID_NUMBERS[index] == valid_dg_TOC[0]:
    				# 		dg_ID_COUNT[index] = dg_ID_COUNT[index] + 1
    
            # advance dg_start to end of valid datagram
            if dg_start + dg_len <= len_raw:
                dg_start = dg_start + dg_len
            
        # otherwise, continue search for next valid dg
        else:
            if dg_start + 1 <= len_raw + 1:
                dg_start = dg_start + 1 # increment dg_start by 1 byte
                
            if dg_start + 1 > len_raw + 1:
                break # break if end of file
		

    if print_updates:
        print("\nFinished parsing file:", filename)
        print('\nDatagram count:')

        for field in data.keys():
            print(field, len(data[field]))

    return(data)


#%% interpret mode field and return ping mode 
def interpretMode(data, print_updates = False):
    # KM ping modes for 1: EM3000, 2: EM3002, 3: EM2000,710,300,302,120,122, 4: EM2040
    # See KM runtime parameter datagram format for models listed
    mode_list = {'3000':{'0000':'Nearfield (4 deg)','0001':'Normal (1.5 deg)','0010':'Target Detect'},
                 '3002':{'0000':'Wide TX (4 deg)','0001':'Normal TX (1.5 deg)'},
                 '9999':{'0000':'Very Shallow','0001':'Shallow','0010':'Medium',
                 '0011':'Deep','0100':'Very Deep','0101':'Extra Deep'},
                 '2040':{'0000':'200 kHz','0001':'300 kHz','0010':'400 kHz'}
                 }

    # pulse and swath modes for EM2040, 710, 302, and 122 only
    pulse_list = {'00':'CW','01':'Mixed','10':'FM'}
    swath_list = {'00':'Single Swath','01':'Dual Swath (Fixed)', '10':'Dual Swath (Dynamic)'}

    # loop through all pings
    for f in range(len(data)):
        for p in range(len(data[f]['XYZ'])):
            data[f]['XYZ'][p]['MODE_BIN'] = "{0:b}".format(data[f]['XYZ'][p]['MODE']).zfill(8) # binary str
            
            # interpret ping mode based on model
            ping_temp = data[f]['XYZ'][p]['MODE_BIN'][-4:]
            model_temp = data[f]['XYZ'][p]['MODEL']
            
            if np.isin(data[f]['XYZ'][p]['MODEL'], [2000, 710, 1002, 300, 302, 120, 122]): # check model for ping mode
                model_temp = '9999' # set temp model just to reference mode_list dict		
                
            data[f]['XYZ'][p]['PING_MODE'] = mode_list[model_temp][ping_temp]

            # interpret pulse form and swath mode based on model
            if np.isin(data[f]['XYZ'][p]['MODEL'], [2040, 710, 302, 122]):
                pulse_temp = data[f]['XYZ'][p]['MODE_BIN'][-6:-4]
                swath_temp = data[f]['XYZ'][p]['MODE_BIN'][-8:-6]

                data[f]['XYZ'][p]['PULSE_FORM'] = pulse_list[pulse_temp]
                data[f]['XYZ'][p]['SWATH_MODE'] = swath_list[swath_temp]

            else:
                data[f]['XYZ'][p]['PULSE_FORM'] = 'NA'
                data[f]['XYZ'][p]['SWATH_MODE'] = 'NA'

            if print_updates:
                print('file', f, 'ping', p, 'is',\
                      data[f]['XYZ'][p]['PING_MODE'],\
                      data[f]['XYZ'][p]['PULSE_FORM'],\
                      data[f]['XYZ'][p]['SWATH_MODE'])

#    if print_updates:   
    print('\nDone interpreting modes...')   

    return(data)


#%% verify consistent model, serial number, ping mode, pulse form, and swath mode in a set of files
def verifyMode(data):
    consistent_RTP = True
    model =         data[0]['XYZ'][0]['MODEL']
    sn =            data[0]['XYZ'][0]['SYS_SN']
    ping_mode =     data[0]['XYZ'][0]['PING_MODE']
    pulse_mode =    data[0]['XYZ'][0]['PULSE_FORM']
    swath_mode =    data[0]['XYZ'][0]['SWATH_MODE']
    
    print('Verifying consistent system and runtime parameters from first ping: EM', str(model), ' (S/N ', str(sn), ') ', \
          ping_mode, ' / ', pulse_mode, ' / ', swath_mode, sep = '')
    
    for f in range(len(data)):
        for p in range(len(data[f]['XYZ'])):
            # check for any changes (MODEL and SYS_SN are integers, modes are strings)
            if (data[f]['XYZ'][p]['MODEL'] != model                 or \
                data[f]['XYZ'][p]['SYS_SN'] != sn                   or \
                data[f]['XYZ'][p]['PING_MODE'] is not ping_mode     or \
                data[f]['XYZ'][p]['PULSE_FORM'] is not pulse_mode   or \
                data[f]['XYZ'][p]['SWATH_MODE'] is not swath_mode):
                
                print('WARNING: New system parameters detected in file ', str(f), ', ping ', str(p), ': EM', \
                      str(data[f]['XYZ'][p]['MODEL']), ' (S/N ', str(data[f]['XYZ'][p]['SYS_SN']), ') ', \
                      data[f]['XYZ'][p]['PING_MODE'], ' / ', data[f]['XYZ'][p]['PULSE_FORM'], ' / ', data[f]['XYZ'][p]['SWATH_MODE'], sep = '')
                consistent_RTP = False
                break
            
    if consistent_RTP:
        print('Consistent system and runtime parameters.')
    else:
        print('WARNING: Inconsistent system and runtime parameters!')

    return(consistent_RTP, (model, sn, ping_mode, pulse_mode, swath_mode))

#%% convert XYZ88 datagram fields into lat, lon, depth
def convertXYZ(data, print_updates = False, plot_soundings = False, Z_pos_up = False):
    from readEM import convertEMpos

    # Depth is relative to the TX array depth at time of ping (TX_TRANS_Z in data dict)
    # Horizontal position is acrosstrack and alongtrack distance relative to vessel
    # positioning reference point (RX_ACROSS and RX_ALONG in data dict)
    # Position needs to be corrected for heading at TX time (HEADING in data struct).
    # Parsed distances are in m and heading is in 0.01 deg.
    # From Kongsberg EM datagram format for XYZ 88 (doc. 850-160692/U, p. 44, note 2):
    # "The beam data are given re the transmit transducer or sonar head depth and the
    # horizontal location (x,y) of the active positioning system’s reference point. Heave,
    # roll, pitch, sound speed at the transducer depth and ray bending through the water
    # column have been applied."
    
    # NOTE: Ping position is interpolated (and extrapolated when necessary) from ship position within each file
    # to avoid interpolating over gaps greater than 1 sec (e.g., for accuracy crosslines with turn files omitted)
    #
    # Compared to a more sophisticated method of checking neighboring files' position records, this
    # simpler approach may result in slight discrepancies for the earliest and latest ping times that
    # happen to fall outside the position time series limits when the vessel is changing course rapidly
    
    # Set multiplier Z_flip = -1 to convert Z to positive UP (default: Kongsberg is Z positive DOWN; Z_flip = 1 if Z_pos_up = False)
    Z_flip = 1-(2*int(Z_pos_up))    
    
    # plot ship track as a base for soundings plot
    if plot_soundings:
        fig, ax = plt.subplots() # create new figure
    
    for f in range(len(data)): # loop through all files in data dict
        
        parse_prog_old = -1
        
        if print_updates:
            print('\nConverting soundings in file:', data[f]['fname'])
            
        # convert ship position record for this file only (avoid interpolation between files in case of gaps)
        datatemp = {}
        datatemp[0] = dict(data[f]) # format datatemp as dict with size 1 for input to convertEMpos
        dt_pos, lat_pos, lon_pos = convertEMpos(datatemp)
        
        if plot_soundings: # plot ship track for base of soundings plot
            ax.plot(lon_pos, lat_pos,  'k', linewidth = 1)
        
        dt_pos_unix = [datetime.timestamp(t) for t in dt_pos] # convert dt_pos to list for interpolation

        N_pings = len(data[f]['XYZ'])
        
        for p in range(N_pings): # loop through each ping
            
            parse_prog = round(10*p/N_pings)
            if parse_prog > parse_prog_old:
                print("%s%%" % (parse_prog*10), end=" ", flush = True)
                parse_prog_old = parse_prog
            
            X = data[f]['XYZ'][p]['RX_ALONG'] # X is positive forward in Kongsberg reference frame
            Y = data[f]['XYZ'][p]['RX_ACROSS'] # Y is positive to starboard in Kongsberg reference frame
            Z = data[f]['XYZ'][p]['RX_DEPTH'] # Z is positive down in Kongsberg reference frame
            
            # rotate X (fwd) and Y (stbd) in ship frame into dE and dN from ship reference location
            hdg = data[f]['XYZ'][p]['HEADING']/100 # convert parsed heading in 0.01 deg into whole deg relative to North
            R = np.sqrt(np.square(X) + np.square(Y)) # calculate horizontal radius from position reference to sounding
            az_ship = np.arctan2(X,Y)*180/np.pi # calculate azimuth (deg) from ship +Y axis (the ship's Cartesian angle ref) to sounding
            az_geo = az_ship - hdg # calculate azimuth (deg) from east (geographic Cartesian angle ref) by subtracting ship heading
    
            dE = R*np.cos(az_geo*np.pi/180) # calculate easting (m) relative to ship reference (positive E)
            dN = R*np.sin(az_geo*np.pi/180) # calculate northing (m) relative to ship reference (positive N)
                   
            # convert ping time in ms since midnight to H, M, S, then python datetime
            year =  int(str(data[f]['XYZ'][p]['DATE'])[0:4])
            month = int(str(data[f]['XYZ'][p]['DATE'])[4:6])
            day =   int(str(data[f]['XYZ'][p]['DATE'])[6:8])
            minutes, seconds = np.divmod(np.divide(data[f]['XYZ'][p]['TIME'],1000), 60) # calc seconds
            hours, minutes = np.divmod(minutes, 60)
            seconds, microseconds = np.divmod(seconds, 1)
            dt_ping = datetime(year, month, day, int(hours), int(minutes), int(seconds), int(round(microseconds*1000000)))
            dt_ping_unix = datetime.timestamp(dt_ping)
            
            # calculate ping position by interpolating (and extrapolating if necessary) ping time on position time series
            interp_lat = interpolate.interp1d(dt_pos_unix, lat_pos, fill_value = 'extrapolate')
            interp_lon = interpolate.interp1d(dt_pos_unix, lon_pos, fill_value = 'extrapolate')
            lat_ping = interp_lat(dt_ping_unix)
            lon_ping = interp_lon(dt_ping_unix)
            # determine ship's position in E, N, UTM and add dE, dN
            # NOTE: this handles UTM zone changes between pings, but could
            # be sped up by checking for consistent UTM (typical case) in file, rather than each ping
        
            if plot_soundings: # plot position of ship reference at ping time
                ax.plot(lon_ping, lat_ping, marker = '*', color = 'r') # plot ping position
        
            # convert ping position to UTM and add dN, dE for sounding positions in 
            Eping, Nping, zone_number, zone_letter = utm.from_latlon(lat_ping, lon_ping)
            N = Nping + dN
            E = Eping + dE
            
            # store sounding positions in UTM, assuming whole swath is in same zone!
            data[f]['XYZ'][p]['SOUNDING_N'] = N.tolist()
            data[f]['XYZ'][p]['SOUNDING_E'] = E.tolist()
            data[f]['XYZ'][p]['SOUNDING_UTM_ZONE'] = str(zone_number) + ' ' + zone_letter
            
            # convert lat, lon for all soundings
            temp_lat, temp_lon = [],[]
            
            for s in range(len(dN)): # loop through all pings and append lat/lon list
                lat_s, lon_s = utm.to_latlon(E[s],N[s],zone_number,zone_letter)
                temp_lat.append(lat_s)
                temp_lon.append(lon_s)
                
            # store lat, lon, and depth with transducer offset at ping time
            data[f]['XYZ'][p]['SOUNDING_LAT'] = temp_lat            
            data[f]['XYZ'][p]['SOUNDING_LON'] = temp_lon   
            
            # add transducer Z at ping time, multiply by Z_flip per optional input Z_pos_up (Kongsberg default is Z positive DOWN)
            data[f]['XYZ'][p]['SOUNDING_Z'] = list(Z_flip*np.add(Z,data[f]['XYZ'][p]['TX_TRANS_Z']))        

    # plot every dssoundings on top of trackline figure
    dp = 100 # skip dp pings to avoid overwhelming plots
    if plot_soundings:
        for f in range(len(data)):
            for p in np.arange(0,len(data[f]['XYZ']),dp):
                ax.plot(data[f]['XYZ'][p]['SOUNDING_LON'], data[f]['XYZ'][p]['SOUNDING_LAT'], '.', color = 'b')
    
    if print_updates:
        print('\nDone with XYZ conversion...')   
    
    return(data)

    
#%% convert and sort datetime, lat, lon from parsed EM data struct
def convertEMpos(data, print_updates = False):
    from datetime import datetime
    lat = []
    lon = []
    time = []
    datestr = []
    
    for f in range(len(data)): # loop through all files in data
        if print_updates:
            print('Converting position and time in ', data[f]['fname'])
        for p in range(len(data[f]['POS'])): # loop through all position datagrams in file
            datestr.append(str(data[f]['POS'][p]['DATE']))      # date in YYYYMMDD
            time =  np.append(time, data[f]['POS'][p]['TIME'])  # time in ms since midnight
            lat =   np.append(lat, data[f]['POS'][p]['LAT'])    # lat in lat*2*10^7
            lon =   np.append(lon, data[f]['POS'][p]['LON'])    # lon in lon*1*10^7
            
    # convert time in ms since midnight to H, M, S, convert all to python datetime
    minutes, seconds = np.divmod(np.divide(time,1000), 60) # calc seconds
    hours, minutes = np.divmod(minutes, 60) # calc minutes and hours

    # make datetime list out of all time fields
    slist = np.round(seconds, decimals = 3).astype('str').tolist()
    mlist = minutes.astype('int').astype('str').tolist()
    hlist = hours.astype('int').astype('str').tolist()
    dt = []
    
    for t in range(len(datestr)):
        # EM time fields are not zero-padded, so separate by : for datetime interpretation
        tempdatestr = datestr[t] + ' ' + hlist[t] + ':' + mlist[t] + ':' + slist[t] 
        dt.append(datetime.strptime(tempdatestr, '%Y%m%d %H:%M:%S.%f'))
        
    # reformat lat/lon, get sorting order from datetime, make list for text export
    lat = np.divide(lat,20000000) # divide by 2x10^7 per dg format, format as array
    lon = np.divide(lon,10000000) # divide by 1x10^7 per dg format, format as array
    dtsortidx = np.argsort(dt) # get chronological sort order from position timestamps in case files not ordered
    
    # apply datetime sort order to lat/lon arrays, sort datetime
    lat = lat[dtsortidx]
    lon = lon[dtsortidx]
    dt.sort()
    
    return(dt, lat, lon) # datetime object and lat, lon arrays
    
#%% sort through pings and pull out outermost valid soundings, BS, and mode
def sortDetections(data, print_updates = False):

    det = {'fname':[],'date':[],'time':[],'x_port':[],'x_stbd':[],'z_port':[],'z_stbd':[],'bs_port':[],'bs_stbd':[],
           'ping_mode':[],'pulse_form':[],'swath_mode':[],'mode_bin':[]}

    # examine detection info across swath, find outermost valid soundings for each ping
    for f in range(len(data)): # loop through all data
        if print_updates:
            print('Finding outermost valid soundings in file', data[f]['fname'])

        for p in range(len(data[f]['XYZ'])): # loop through each ping
            det_int = data[f]['XYZ'][p]['RX_DET_INFO'] # det info integers across swath
            # find indices of port and stbd outermost valid detections
            # leading bit of det info field is 0 for valid detections, integer < 128
            idx_port = 0				# start at port outer sounding
            idx_stbd = len(det_int)-1	# start at stbd outer sounding

            while det_int[idx_port] >= 128 and idx_port <= len(det_int):
#                print('at port index', idx_port, 'the det_int is', det_int[idx_port])
                idx_port = idx_port + 1 # move port idx to stbd if not valid

            while det_int[idx_stbd] >= 128 and idx_stbd >= 0:
#                print('at stbd index', idx_stbd, 'the det_int is', det_int[idx_stbd])
                idx_stbd = idx_stbd - 1 # move stdb idx to port if not valid

            if print_updates:
                print('Found valid detections in ping', p, 'at port/stbd indices', idx_port, '/', idx_stbd)

            det['fname'].append(data[f]['fname'].rsplit('/')[-1]) # store filename for each swath for later reference during file list updates
            det['date'].append(data[f]['XYZ'][p]['DATE'])
            det['time'].append(data[f]['XYZ'][p]['TIME'])
            det['x_port'].append(data[f]['XYZ'][p]['RX_ACROSS'][idx_port])
            det['x_stbd'].append(data[f]['XYZ'][p]['RX_ACROSS'][idx_stbd])
            det['z_port'].append(data[f]['XYZ'][p]['RX_DEPTH'][idx_port])
            det['z_stbd'].append(data[f]['XYZ'][p]['RX_DEPTH'][idx_stbd])
            det['bs_port'].append(data[f]['XYZ'][p]['RX_BS'][idx_port])
            det['bs_stbd'].append(data[f]['XYZ'][p]['RX_BS'][idx_stbd])
            det['ping_mode'].append(data[f]['XYZ'][p]['PING_MODE'])
            det['pulse_form'].append(data[f]['XYZ'][p]['PULSE_FORM'])
            det['swath_mode'].append(data[f]['XYZ'][p]['SWATH_MODE'])
            det['mode_bin'].append("{0:b}".format(data[f]['XYZ'][p]['MODE']).zfill(8)) # binary str
            
#            print('just added sounding from ', det['fname'][-1])

    return(det)

#%% plot swath coverage
def plotCoverage(data, det, fnames, colormode = 'backscatter', cruise_ID = 'a three hour tour', N_WD_max = 8):
    # optional arguments:
    #   colormode: default for 'backscatter', optional for 'ping_mode', 'pulse_form', 'swath_mode'
    #   cruise_ID: default for survey ID recorded in first IP_start datagram, optional string input (e.g., '2016 Arctic')
    #   N_WD_max: number of water depth multiples to grid (default 8 for typical multibeam) 
    
    # consolidate data for plotting
    x_all = 	det['x_port'] + det['x_stbd']
    z_all = 	det['z_port'] + det['z_stbd']

    # configure colormap by backscatter (default), ping mode, swath mode, or pulse form
    bs_all = det['bs_port'] + det['bs_stbd']
    c_all = []
    c_all = [int(bs)/10 for bs in bs_all] # convert to int, divide by 10 (BS reported in 0.1 dB)
    
    if colormode is not 'backscatter': # process optional colormode input
        if np.isin(colormode, ['ping_mode', 'pulse_form', 'swath_mode']): # check option list
            c_all = det[colormode] + det[colormode] # set c_all to appended lists of colormode key from det dict
            
            c_set = set(c_all) # unique
            print(c_set)
            
        else:
            print('Invalid colormode:', colormode)
       
    fig, ax = plt.subplots() # create new figure
    
    # color by backscatter (default)
    if colormode is 'backscatter':
        ax.scatter(x_all, z_all, c = c_all, marker = '.', vmin=-50, vmax=-20, cmap='rainbow') # specify vmin and vmax
     
    # format axes
    ax.set_ylim(0, 1.1*max(z_all)) # set depth axis to 0 and 1.1 times max(z)    
    ax.set_ylim(ax.get_ylim()[::-1]) # reverse y-axis direction
    x_max = int(max([abs(x) for x in x_all])) # find greatest athwartship distance
    ax.set_xlim(-1.1*x_max, 1.1*x_max) # set x axis to +/-1.1 times max(abs(x))
    
    # add water-depth-multiple lines
    z_max = max(ax.get_ylim())
    
    # loop through multiples of WD (-port,+stbd) and plot grid lines with text 
    for n in range(1,N_WD_max+1):   # add 1 for indexing, do not include 0X WD
        for ps in [-1,1]:           # port/stbd multiplier
            ax.plot([0, ps*n*z_max/2],[0,z_max], 'k', linewidth = 1)
            x_mag = 0.9*n*z_max/2 # set magnitude of text locations to 90% of line end
            y_mag = 0.9*z_max
            
            # keep text locations on the plot
            if x_mag > 0.9*x_max:
                x_mag = 0.9*x_max
                y_mag = 2*x_mag/n # scale y location with limited x location
                
            ax.text(x_mag*ps, y_mag, str(n) + 'X',
                    verticalalignment = 'center', horizontalalignment = 'center',
                    bbox=dict(facecolor='white', edgecolor = 'none', alpha=1, pad = 0.0))

    # formatting labels
    shipname = fnames[0]
    shipname = shipname[shipname.rfind('_')+1:-4]
    
    # format cruise ID if not specified in optional argument
    if cruise_ID == 'a three hour tour':
        cruise_ID = data[0]['IP_start'][0]['SID'].upper()
        
    system_ID = 'EM' + str(data[0]['IP_start'][0]['MODEL'])
    title_str = 'Swath Width vs. Depth\n' + shipname + ' - ' + cruise_ID + ' - ' + system_ID
    ax.set(xlabel='Swath Coverage (m)', ylabel='Depth (m)', title=title_str)

    ax.grid()
    ax.minorticks_on()
    ax.grid(which='minor', linestyle='-', linewidth='0.5', color='black')


#    ax.set_aspect('equal')
#
#    # set colorscale to ping mode
#    for p in range(len(det['mode_bin'])):
#        # print(det['mode_bin'][p][-4:])
#        cmap_temp.append(int(det['mode_bin'][p][-4:]))
#
##    print(cmap_temp)
##    print(cmap)
#    fig, ax = plt.subplots()
#    ax.scatter(det['x_port'], det['z_port'], color=cmap(norm(det['ping_mode'])))
#    ax.scatter(det['x_stbd'], det['z_stbd'], color=cmap(norm(det['ping_mode'])))
#    
#    # plt.scatter(det['x_port'], det['z_port'], c=color, s = 50)
#    # plt.scatter(det['x_stbd'], det['z_stbd'], c=color, s = 50)
#    # ax = plt.gca()
#    # TESTING COLORS BY BS OR MODE
#    # plt.scatter(x, y, s=500, c=color)
#    ax.set_ylim(ax.get_ylim()[::-1])
#    plt.show()