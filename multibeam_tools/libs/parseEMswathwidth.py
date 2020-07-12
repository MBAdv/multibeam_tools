# Stripped-down parser for only the outermost valid soundings for swath coverage plotting

import struct
import multibeam_tools.libs.parseEM

def parseEMswathwidth(filename, print_updates=False):
    # def parseEMfile(self, filename, parse_list = 0, print_updates = False, update_prog_bar = False):

    # if print_updates:
    print("\nParsing file:", filename)

    # Open and read the .all file
    # filename = '0248_20160911_191203_Oden.all'
    f = open(filename, 'rb')
    raw = f.read()
    len_raw = len(raw)

    # initialize data dict with remaining datagram fields
    data = {'fname': filename, 'XYZ': {}, 'RTP': {}, 'RRA': {}}
    # RX_angles = {}

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
            print("%s%%" % (parse_prog * 10), end=" ", flush=True)
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
                    data['XYZ'][len(data['XYZ']) - 1]['MAX_PORT_M'] = data['RTP'][len(data['RTP'])-1]['MAX_PORT_SWATH']
                    data['XYZ'][len(data['XYZ']) - 1]['MAX_PORT_DEG'] = data['RTP'][len(data['RTP'])-1]['MAX_PORT_COV']
                    data['XYZ'][len(data['XYZ']) - 1]['MAX_STBD_M'] = data['RTP'][len(data['RTP'])-1]['MAX_STBD_SWATH']
                    data['XYZ'][len(data['XYZ']) - 1]['MAX_STBD_DEG'] = data['RTP'][len(data['RTP'])-1]['MAX_STBD_COV']

                if print_updates:
                    print('ping', len(data['XYZ']), 'swath limits (port/stbd):',
                          data['XYZ'][len(data['XYZ'])-1]['MAX_PORT_DEG'], '/',
                          data['XYZ'][len(data['XYZ'])-1]['MAX_STBD_DEG'], 'deg and',
                          data['XYZ'][len(data['XYZ'])-1]['MAX_PORT_M'], '/',
                          data['XYZ'][len(data['XYZ'])-1]['MAX_STBD_M'], 'meters')


            # parse RRA 78 datagram to get RX beam angles
            if dg_ID == 78:
                # MODIFY RRA PARSER WITH PARSE_OUTERMOST_ONLY OPTION
                data['RRA'][len(data['RRA'])] = multibeam_tools.libs.parseEM.RRA_78_dg(dg)  # speed this up to parse RX angles only!
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
        data['XYZ'][p]['RX_ANGLE_PORT'] = data['RRA'][pRRA[p]]['RX_ANGLE'][data['XYZ'][p]['RX_BEAM_IDX_PORT']]/100
        data['XYZ'][p]['RX_ANGLE_STBD'] = data['RRA'][pRRA[p]]['RX_ANGLE'][data['XYZ'][p]['RX_BEAM_IDX_STBD']]/100

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
