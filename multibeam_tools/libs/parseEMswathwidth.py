# Super stripped-down parser for only the outermost valid soundings for swath coverage plotting

import sys, utm, numpy as np
import struct
import multibeam_tools.libs.parseEM
import matplotlib.pyplot as plt
from datetime import datetime
from scipy import interpolate

def parseEMswathwidth(filename, print_updates=False):
    # def parseEMfile(self, filename, parse_list = 0, print_updates = False, update_prog_bar = False):

    if print_updates:
        print("\nParsing file:", filename)

    # Open and read the .all file
    # filename = '0248_20160911_191203_Oden.all'
    f = open(filename, 'rb')
    raw = f.read()
    len_raw = len(raw)

    data = {}  # initialize data dict with remaining datagram fields
    data['fname'] = filename
    data['XYZ'] = {}
    data['RTP'] = {}

    # Declare counters for dg starting byte counter and dg processing counter
    dg_start = 0    # datagram (starting with STX = 2) starts at byte 4
    # dg_start = 0
    dg_count = 0
    parse_prog_old = -1

    loop_num = 0


    # Assign and parse datagram
    # while dg_start <= len_raw:  # and dg_count < 10:
    while True:
        loop_num = loop_num+1
        # print('starting loop_num', loop_num)
        # if dg_start >= len_raw:  # break if EOF

        # print progress update
        parse_prog = round(10 * dg_start / len_raw)
        if parse_prog > parse_prog_old:
            print("%s%%" % (parse_prog * 10), end=" ", flush=True)
            parse_prog_old = parse_prog

        if dg_start + 4 >= len_raw:  # break if EOF
            # print('breaking because EOF with dg_start +4 at', dg_start + 4, '>= len_raw', len_raw)
            break

        # dg_len, [STX, stuff, ETX]
        # dg_len = struct.unpack('I', raw[dg_start - 4:dg_start])[0]     # get dg length (before start of dg at STX)
        dg_len = struct.unpack('I', raw[dg_start:dg_start+4])[0]     # get dg length (before start of dg at STX)

        # skip to next iteration if dg length is insuffient to check for STX, ID, and ETX, or dg end is beyond EOF
        if dg_len < 3:
            dg_start = dg_start + 4
            continue

        dg_end = dg_start + 4 + dg_len

        if dg_end > len_raw:
            dg_start = dg_start + 4
            continue

        # if dg_end <= len_raw:  # try to read dg if len seems reasonable and not EOF
        # print('trying to get dg from ', dg_start + 4, 'to', dg_end)
        dg = raw[dg_start+4:dg_end]  # get STX, ID, and ETX
        # print('dg_type is ', type(dg))
        dg_STX = dg[0]
        dg_ID = dg[1]
        dg_ETX = dg[-3]

        # continue unpacking only if STX and ETX are valid and dg_ID is Runtime Param or XYZ datagram
        if dg_STX == 2 and dg_ETX == 3:

            # print('found valid STX and ETX in loop number', loop_num)

            # Parse RUNTIME PARAM datagram PYTHON 3
            if dg_ID == 82:
                # print('found RTP dg', dg_ID, 'in loop num', loop_num)
                # print('trying to store RTP stuff in index', len(data['RTP']))
                data['RTP'][len(data['RTP'])] = multibeam_tools.libs.parseEM.RTP_dg(dg)

            # Parse XYZ 88 datagram PYTHON 3
            if dg_ID == 88:
                # print('found XYZ dg', dg_ID, 'in loop num', loop_num)
                # print('trying to store XYZ stuff in index', len(data['XYZ']))

                # reduced parser below for outermost valid soundings only
                data['XYZ'][len(data['XYZ'])] = multibeam_tools.libs.parseEM.XYZ_dg(dg, parse_outermost_only = True)

                # store last RTP MODE for each ping
                data['XYZ'][len(data['XYZ']) - 1]['MODE'] = data['RTP'][len(data['RTP']) - 1]['MODE']

            # if there was a valid STX and ETX, jump to end of dg and continue on next iteration
            dg_start = dg_start + dg_len + 4
            continue

        # if no condition was met to read and jump ahead not valid, so move ahead by 1 and continue search
        # (will start read dg_len at -4 on next loop)
        dg_start = dg_start + 1
        # print('STX or ETX not valid, moving ahead by 1 to new dg_start', dg_start)




            # # advance dg_start to end of valid datagram
            # if dg_start + dg_len <= len_raw:
            #     dg_start = dg_start + dg_len

        # otherwise, continue search for next valid dg
        # else:
        #     if dg_start + 1 <= len_raw + 1:
        #         dg_start = dg_start + 1  # increment dg_start by 1 byte
        #
        #     if dg_start + 1 > len_raw + 1:
        #         break  # break if end of file

    if print_updates:
        print("\nFinished parsing file:", filename)
        # print('\nDatagram count:')
        fields = [f for f in data.keys() if f != 'fname']
        for field in fields:
            print(field, len(data[field]))

    return (data)


# # parse the outermost soundings from the XYZ88 datagram
# def XYZ_dg(dg):
#     XYZ = {}
#     XYZ['ID'] = struct.unpack('B', dg[1:2])[0]  # ID 1U
#     XYZ['MODEL'] = struct.unpack('H', dg[2:4])[0]  # EM MODEL 2U
#     XYZ['DATE'] = struct.unpack('I', dg[4:8])[0]  # DATE 4U
#     XYZ['TIME'] = struct.unpack('I', dg[8:12])[0]  # TIME 4U
#     XYZ['SYS_SN'] = struct.unpack('H', dg[14:16])[0]  # SYS SN 2U
#     XYZ['NUM_RX_BEAMS'] = struct.unpack('H', dg[24:26])[0]  # 2U NUMBER OF RX BEAMS IN DATAGRAM
#
#     RX_FIELDS = ['RX_DEPTH', 'RX_ACROSS', 'RX_DET_INFO', 'RX_BS'] # reduce set of RX fields for swath plotting only
#
#     for i in range(len(RX_FIELDS)):
#         XYZ[RX_FIELDS[i]] = []
#
#     entry_start = 36  # start of XYZ entries for beam 0
#     entry_length = 20  # length of XYZ entry for each beam
#     N_beams_parse = XYZ['NUM_RX_BEAMS']  # number of RX beams to parse
#
#     # determine indices of outermost valid soundings and parse only those
#     det_int = []  # detection info integers for all beams across swath
#
#     for i in range(XYZ['NUM_RX_BEAMS']):  # read RX_DET_INFO for all beams in datagram
#         det_int.append(struct.unpack('B', dg[entry_start + 16:entry_start + 17])[0])  # 1U SEE KM DOC NOTE
#         entry_start = entry_start + entry_length
#
#     # find indices of port and stbd outermost valid detections
#     # leading bit of det info field is 0 for valid detections (integer < 128)
#     idx_port = 0  # start at port outer sounding
#     idx_stbd = len(det_int) - 1  # start at stbd outer sounding
#
#     while det_int[idx_port] >= 128 and idx_port <= len(det_int):
#         # print('at port index', idx_port, 'the det_int is', det_int[idx_port])
#         idx_port = idx_port + 1  # move port idx to stbd if not valid
#
#     while det_int[idx_stbd] >= 128 and idx_stbd >= 0:
#         # print('at stbd index', idx_stbd, 'the det_int is', det_int[idx_stbd])
#         idx_stbd = idx_stbd - 1  # move stdb idx to port if not valid
#
#     # reset file pointers to parse only the outermost valid detections identified above
#     entry_start = 36 + (idx_port) * 20  # start of entries for farthest port valid sounding
#     entry_length = 20 * (idx_stbd - idx_port)  # length from port valid sounding to start of farthest stbd valid sounding
#     N_beams_parse = 2  # parse only the two RX beams associated with these port and stbd indices
#
#     #    print(N_beams_parse)
#     #    for i in range(XYZ['NUM_RX_BEAMS']):
#     for i in range(N_beams_parse): # adapted from parser for all beams in order to parse outermost only (N_beams_parse = 2)
#         #    for i in RX_beam_range:
#         #        print(i)
#         XYZ['RX_DEPTH'].append(struct.unpack('f', dg[entry_start:entry_start + 4])[0])  # 4F DEPTH IN m
#         XYZ['RX_ACROSS'].append(struct.unpack('f', dg[entry_start + 4:entry_start + 8])[0])  # 4F ACROSSTRACK DISTANCE IN m
#         XYZ['RX_DET_INFO'].append(struct.unpack('B', dg[entry_start + 16:entry_start + 17])[0])  # 1U SEE KM DOC NOTE 4
#         XYZ['RX_BS'].append(struct.unpack('h', dg[entry_start + 18:entry_start + 20])[0])  # 2S REFLECTIVITY IN 0.1 dB
#
#         entry_start = entry_start + entry_length
#
#     # reset pointer to end of RX beams to finish parsing rest of dg
#     entry_start = 36 + XYZ['NUM_RX_BEAMS'] * 20
#
#     # XYZ['SPARE'] = struct.unpack('B', dg[entry_start:entry_start + 1])[0]  # 1U
#     # XYZ['ETX'] = struct.unpack('B', dg[-3:-2])[0]  # ETX 1U
#     # XYZ['CHECKSUM'] = struct.unpack('H', dg[-2:])[0]  # CHECKSUM 2U
#
#     return (XYZ)