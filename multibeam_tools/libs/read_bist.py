
###############################################################################
# Read BIST file and extract RX Z, TX Z, and RX Noise data
###############################################################################


# -*- coding: utf-8 -*-
"""
Created on Sat Sep 29 11:17:09 2018

@author: kjerram
"""
# import sys, struct, parseEM, math,\
import numpy as np
from matplotlib import pyplot as plt
from matplotlib import gridspec
from matplotlib.ticker import FormatStrFormatter
import datetime
import re
import os
import math


__version__ = "0.1.1"


def get_test_datetime(time_str):
    # Parse test date and time from time string found at start of test record (examples below), return a datetime object
    #------------------------------------------------------------------------------------
    #2020.11.05 21:13:10.673    10012       11      OK
    #
    #--------------20201020-155825-9-Passed-EM124_60-RX-noise-level----EM-124.txt--------------
    #
    test_datetime = []

    try:
        test_date = time_str.replace('-', ' ').split()[0].replace('.', '').replace('/', '')  # remove -./, extract date
        test_time = time_str.replace('-', ' ').split()[1].replace(':', '')  # remove :, extract time, leave ms if present
        test_time = test_time + ('.000' if '.' not in test_time else '')  # add ms if not present for consistent formatting
        test_datetime = datetime.datetime.strptime(test_date + test_time, '%Y%m%d%H%M%S.%f')  # %f is micros, works with ms
    except:
        print('in get_test_datetime, failed to parse time_str:', time_str)

    return(test_datetime)


def parse_rx_z(fname, sis_version=4, sis4_retry=False):
    # Parse RX impedance data (receiver and transducer)
    n_rx_channels = 32  # each RX32 board has 32 channels
    zrx_temp = init_bist_dict(2)  # set up output dict for impedance data

    sys_info = check_system_info(fname)  # get system info and store in dict

    if all([k == [] for k in sys_info.values()]):
        print('all sys_info fields are empty in parse_rx_z; returning with empty zrx_temp')
        return []

    if sys_info['date'].find('2005') > -1:
        print('\n\n\n************************** Year = 2005 in filename:', fname, '\n\n\n\n')
        return[]

    # is_2040 = sys_info['model'].find('2040') > -1
    is_2040 = sys_info['model'] in ['2040', '2045', '2040P']
    print('got is_2040 =', is_2040)
    print('parsing rx_z for file:', fname)
    print('in file', fname, 'sys_info=', sys_info)
    sys_info_datetime = datetime.datetime.strptime(sys_info['date']+sys_info['time'], '%Y/%m/%d%H:%M:%S.%f')

    zrx_temp['filename'] = fname
    zrx_temp['sis_version'] = sis_version

    if sis4_retry:
        zrx_temp['sis_version'] = 4  # some EM2040 BISTs recorded with SIS 4 follow the SIS 5 format for parsing

    for k in sys_info.keys():  # copy sys_info to bist dict
        zrx_temp[k] = sys_info[k]

    # print('zrx_temp with sys_info is', zrx_temp)

    try:  # try reading file
        f = open(fname, "r")
        data = f.readlines()
            
    except ValueError:
        print('***WARNING: Error reading file', fname)

    if len(data) <= 0:  # skip if text file is empty
        print('***WARNING: No data read from file', fname)
        return []
    
    # Check to make sure its not a PU Params or System Report text file
    if any(substr in data[0] for substr in ["Database", "Datagram", "CPU"]):
        print("***WARNING: Skipping non-BIST file: ", fname)
        return []

    # initialize lists of Z, temp, limits for receiver and array
    # SIS 4: EM710 MKII, EM712 include 40-70 and 70-100 kHz tests recorded separately
    # SIS 5: EM712 (Revelle) includes 55 and 84 kHz tests recorded in N_channels_total x N_freq_tests array format
    # these must be initialized separately, not x = y = []
    zrx_test = []
    zrx_array_test = []
    zrx_limits = []
    zrx_array_limits = []
    trx = []
    trx_limits = []

    # store data test-wise
    zrx_test2 = []
    zrx_array_test2 = []
    zrx_limits2 = []
    zrx_array_limits2 = []
    trx2 = []
    trx_limits2 = []

    try:
        # SIS 4 strings preceding data in BIST file
        hdr_str_receiver = "Receiver impedance limits"  # SIS 4 start of SIS 4 RX Channels test for receiver
        limit_str_receiver = "Receiver impedance limits"  # SIS 4 RX Channels impedance limits for receiver
        hdr_str_array = "Transducer impedance limits"  # SIS 4 start of SIS 4 RX Channels test for transducer
        hdr_str_ch = ":"  # string in SIS 4 channel data, e.g., channel 1 --> 1: 852.3 870.2 849.9 855.0
        test_freq_str = " kHz test"  # string identifying the freq range for EM710 (SIS4), 40-70 or 70-100 kHz

        if sis_version is 5:  # strings for SIS 5 format
            hdr_str_receiver = "RX channels"
            param_str_receiver = "Impedance"
            limit_str_receiver = "ohm]"  # limits appear with this string (should also find " kohm]" for SIS 5 EM712)
            hdr_str_ch = "Ch"
            # test_freq_str = " kHz"
            test_freq_str = "Hz"  # EX EM304 MKII '30000 Hz' instead of EM304 MKI '30 kHz'; 'Hz' should be found in both

            # special case for SIS 5 EM2040 (based on SIS 5.6 example file - 2021/01/09)
            if is_2040:
                hdr_str_receiver = "RX channels"
                param_str_receiver = "Signal Amplitude"
                limit_str_receiver = "NOLIMITSIN2040SIS5"  # no RX channels limits in SIS 5 EM2040 BIST example file
                hdr_str_ch = ""
                test_freq_str = "kHz"  # no space before kHz for 2040

        # find the Z values for receiver and transducer
        i = 0  # line number
        t = -1  # test number (first test will have key = 0)
        t_temp = -1  # temperature test number
        # zrx_temp['rx_new'] = {}
        # zrx_temp['rx_array_new'] = {}

        # zrx and zrx_array are stored by test, then sorted by frequency at end
        zrx_test = {}  # storing tests and frequencies, then sorting by frequency at end
        zrx_array_test = {}  # sorting tests and frequencies, then sorting by frequency at end

        # temperature, frequency ranges, units, and limits are stored on the fly per test
        zrx_temp['rx_temp'] = {}
        zrx_temp['freq_range'] = {}
        zrx_temp['rx_units'] = {}
        zrx_temp['rx_limits'] = {}
        zrx_temp['rx_array_limits'] = {}

        test_time_substr = '--------------'

        increment_i = True

        while i < len(data):
            # UPDATES FOR MULTIPLE TESTS PER FILE: GET DATE AND TIME OF EACH TEST ######################################
            # store latest date and time string, if available, before finding the data header; all tests are separated
            # by dashes, with date and time in line (SIS 5) or on next linSIS 4); get date and time independent from
            # SIS version because some SIS 4 EM2040 BISTs may follow SIS 5 format and will be retried if they fail SIS 4

            if i < len(data)-1 and data[i].find(test_time_substr) > -1:
                print('\n\t*******found test_time_substr in line: ', data[i])
                # found substr indicating new test time: add next line to this (stripped of \n) if two conditions:
                # 1. the break line is all dashes (e.g., standard SIS 4 format) AND
                # 2. next line starts with a number (skip test info such as 'RX32')
                #------------------------------------------------------------------------------------
                #2019.10.27 10:10:51.941    230     5    OK
                # time_str = data[i].strip() + (data[i+1].strip() if len(set(data[i].strip())) == 1
                #                                                    and data[i+1].strip()[0].isnumeric() else '')
                # time_str1 = data[i].strip(data[i + 1].strip() if len(set(data[i].strip())) == 1
                #                         and data[i + 1].strip()[0].isnumeric() else '')

                time_str = data[i].strip()

                for i_dt in range(i, i+2):  # try getting time from this line and next line if not found
                    print('datetime search iteration on line:', i_dt)
                    if len(set(data[i_dt].strip())) > 1:
                        print('this line is more than just dashes: ', data[i_dt].strip())
                        time_str_dt = get_test_datetime(data[i_dt].strip())
                        print('got back time_str_dt =', time_str_dt)
                        if time_str_dt:
                            test_datetime = time_str_dt  # update with successfully parsed datetime
                            print('updated test_datetime =', test_datetime)
                            break  # stop looking for the test date time
                        else:
                            test_datetime = sys_info_datetime  # store sys_info_datetime for reference by next test
                            print('stored sys_info_datetime =', test_datetime)

                # print('back in while loop using test_datetime =', test_datetime)
                # if len(set(time_str)) > 1:  # try to parse time_str if it includes more than just dashes
                #     try:  # try splitting and converting to datetime
                #         print('calling get_test_datetime with time_str=', time_str)
                #         test_datetime = get_test_datetime(time_str)
                #
                #     except:  # get_test_datetime failed; maybe not start of test; set sys_info datetime as a backup
                #         test_datetime = []
                #
                #     print('test_datetime is', test_datetime)
                #     if not test_datetime:  # replace with sys info datetime if not parsed
                #         test_datetime = datetime.datetime.strptime(sys_info['date']+sys_info['time'], '%Y/%m/%d%H:%M:%S.%f')
                #         print('set test_datetime from sys_info --> ', test_datetime)

            # get RECEIVER channel impedance, limits, and test frequency
            if data[i].find(hdr_str_receiver) > -1:  # if RX Channels test header is found, start parsing
                print('\n\t***i = ', i, ' --> found RECEIVER header string in', data[i])
                t += 1  # iterate test counter used as key

                # zrx_temp2 = init_bist_dict(2)
                zrx_test[t] = []  # new empty list for receiver data in this test
                zrx_array_test[t] = []  # new empty list for array data in this test

                zrx_temp['test'].append(t)
                print('\n\t***new zrx_temp test number appended: ', zrx_temp['test'])
                zrx_temp['test_datetime'].append(test_datetime)
                print('\t***new zrx_temp test_datetime appended:', zrx_temp['test_datetime'])

                # check SIS 4 EM71X for single (70-100 kHz) or double test (70-100 and 40-70 kHz)
                if sis_version is 4:
                    if data[i-1].find(test_freq_str) > -1:  # check if freq of test is stated on previous line
                        # zrx_temp['freq_range'].append(data[i-1][:data[i-1].find(" kHz")])  # get freq ('40-70 kHz test')
                        zrx_temp['freq_range'][t] = data[i-1][:data[i-1].find(" kHz")]

                    else:
                        freq_str = get_freq(zrx_temp['model'])  # get nominal frequency of this model
                        # zrx_temp['freq_range'].append(freq_str.replace('kHz', '').strip())
                        # zrx_temp['freq_range'][t] = freq_str.replace('kHz', '').strip()
                        zrx_temp['freq_range'][t] = [f for f in freq_str.replace('kHz', '').strip().split()]

                    print('stored freq range = ', zrx_temp['freq_range'][t])

                    while data[i].find(limit_str_receiver) == -1:  # find limit string (SIS 4 is same line, SIS 5 later)
                      i += 1

                    # store zrx limits (first [] in SIS 5)
                    # zrx_limits = data[i][data[i].find("[") + 1:data[i].find("]")].replace("kohm", "").replace("ohm", "")
                    # zrx_limits = [float(x) for x in zrx_limits.split()]
                    lim_temp = data[i][data[i].find("[") + 1:data[i].find("]")].replace("kohm", "").replace("ohm", "")
                    # zrx_limits.append([float(x) for x in lim_temp.split()])  # store list of limits for this freq
                    zrx_temp['rx_limits'][t] = {0: [float(x) for x in lim_temp.split()]}  # store limits for this freq
                    print('stored SIS 4 zrx_temp[rx_limits][t]=', zrx_temp['rx_limits'][t])

                elif sis_version is 5:  # check SIS 5 EM71X for multiple frequencies (e.g., 55 and 84 kHz tests)
                    if is_2040:
                        print('**** this is a 2040 variant ****')
                        #'Signal Amplitude in dB
                        #                        200kHz           300kHz             380kHz
                        #Channel        Low     High    Low     High    Low     High
                        # 0             -2.6    -2.0    -1.6    -2.1    0.5     1.0

                        while data[i].find(test_freq_str) == -1:
                            i += 1

                        print('found 2040 test freq str =', data[i])

                        # for 2040, make LOW and HIGH signal amplitude plots; double freq and units lists accordingly
                        freq_range = sorted([f for f in set(data[i].replace(test_freq_str, '').split())]*2)
                        zrx_temp['freq_range'][t] = [a + b for a, b in zip(freq_range, [' (Low)', ' (High)']*3)]
                        print('setting low and high frequency ranges =', zrx_temp['freq_range'][t])
                        zrx_temp['rx_units'][t] = ['Signal Amplitude (LOW) [dB]', 'Signal Amplitude (HIGH) [dB]']*int(len(zrx_temp['freq_range'][t])/2)
                        print('FOUND FREQ_RANGE = ', zrx_temp['freq_range'][t])
                        print('FOUND RX UNITS = ', zrx_temp['rx_units'][t])
                        # zrx_limits.extend([[-5.0, 1.0]]*len(zrx_temp['freq_range']))  # placeholder lims (N/A in file)
                        n_freq = len(zrx_temp['freq_range'][t])
                        zrx_temp['rx_limits'][t] = {}
                        print('got n_freq = ', n_freq)
                        for f in range(n_freq):
                            zrx_temp['rx_limits'][t][f] = [-5.0, 3.0]  # placeholder lims (N/A)

                        print('stored SIS 5 EM2040 zrx_temp[rx_limits][t]=', zrx_temp['rx_limits'][t])

                    else:
                        print('*** this is not a 2040! ****')
                        while data[i].find(limit_str_receiver) == -1 or data[i].find('Impedance') > -1:
                            i += 1  # iterate past 'RX 1 Impedance [kohm]...' and find limits line with ' kohm]' or ' ohm]'

                        print('FOUND LIMITS STRING = ', data[i])
                        # zrx_limits = data[i].rstrip('')
                        lim_temp = data[i].replace('[', ' ').replace(']', ' ').split()
                        zlim_units = [l for l in lim_temp if l.find('ohm') > -1]
                        print('got zlim_units =', zlim_units)
                        zlim_count = len(zlim_units)
                        # zrx_limits = ['10.5', '17.5', 'kohm', '5.0', '11.0', 'kohm', '-100', '-70', 'deg', '-90', '-60', 'deg']
                        lim_temp = [float(l) for l in lim_temp if not l.isalpha()]
                        lim_temp = lim_temp[0:(2*zlim_count)]  # keep only impedance limits, do not store phase limits
                        print('***ZRX lim_temp is now ', lim_temp)

                        # convert kohm to ohm if necessary and store list of [zlim_low, zlim_high] for each frequency test
                        lim_reduced = [lim_temp[f:f+2] for f in range(0, 2*zlim_count, 2)]
                        print('lim_reduced = ', lim_reduced)
                        print('lim_reduced[0] = ', lim_reduced[0])
                        print('lim_reduced to be extended = ', lim_reduced)
                        # zrx_limits.extend(lim_reduced)
                        zrx_temp['rx_limits'][t] = lim_reduced
                        print('stored SIS 5 non-EM2040 zrx_temp[rx_limits][t]=', zrx_temp['rx_limits'][t])

                        # print('zrx_limits is now', zrx_limits)
                        while data[i].find(test_freq_str) == -1:  # find freq string (SIS 5 may be multiple freq, same line)
                            i += 1

                        # store SIS 5 frequency(ies) from set of frequencies found in header
                        # '    55 kHz                    84 kHz               55 kHz                84 kHz   '
                        # zrx_temp['freq_range'] = sorted([f for f in set(data[i].replace(test_freq_str, '').split())])
                        # zrx_temp['rx_units'] = zlim_units

                        # if units are 'Hz', divide by 1000 and round to get kHz at same level of precision as
                        # frequencies listed in 'kHz'; the freq range must match for comparison in the history plot step
                        temp_freq_range = sorted([f for f in set(data[i].replace(test_freq_str, '').split()) if f.isnumeric()])
                        zrx_temp['freq_range'][t] = [str(round(float(f)/1000)) if data[i].find('kHz') == -1 else f for f in temp_freq_range]

                        # some early EM712 BISTs used 84 kHz instead of 85 kHz (like all later tests); replace 84 with
                        # 85 so that the history plots are consistent
                        print('*** CHECKING FOR 84 kHz in zrx_temp[freq_range] = ', zrx_temp['freq_range'][t])
                        zrx_temp['freq_range'][t] = ['85' if f == '84' else f for f in zrx_temp['freq_range'][t]]
                        print('freq_range is now ', zrx_temp['freq_range'][t])

                        # original method
                        # zrx_temp['freq_range'][t] = sorted([f for f in set(data[i].replace(test_freq_str, '').split())])
                        zrx_temp['rx_units'][t] = zlim_units
                        print('FOUND FREQ_RANGE = ', zrx_temp['freq_range'][t])
                        print('FOUND RX UNITS = ', zrx_temp['rx_units'][t])

                if sis_version == 5 and is_2040:  # for SIS 5 EM2040, after freq info, skip 'Channel' to first data row
                    i += 1  # start at line after freq info
                    while data[i].find('Channel') > -1 or len(data[i].split()) == 0:
                        i += 1

                else:
                    while data[i].find(hdr_str_ch) == -1:  # for all other systems, find first channel string
                        i += 1

                print('FOUND FIRST DATA in line i = ', i, ' with data[i]=', data[i])

                # while True:  # read channels until something other than a channel or whitespace is found
                while i < len(data):
                    ch_count = 0
                    # print('i=', i)
                    ch_str = data[i].replace("*", "")  # replace any * used for marking out of spec channels

                    # from z array outlier parsing
                    # # replace '*' (used for marking out of spec channels) and 'Open' with very high Z value
                    # z_str_array = ch_str.replace("*", "").replace('Open', '999999')[ch_str.find(hdr_str_ch) + 1:]
                    #
                    # # convert Z values > 1000 (logged as, e.g., 1.1k = 1100) to simple number
                    # z_str_array = [float(z.replace('k', '')) * 1000 if z.find('k') > -1 else
                    #                float(z) for z in z_str_array.split()]

                    if len(ch_str.split()) > 0:  # if not just whitespace, check if channel data
                        print('not just whitespace --> ch_str.split() =', ch_str.split())

                        # non-whitespace; break if any alpha chars (2040) or channel string not found (all others)
                        if (is_2040 and any([ch.isalpha() for ch in ch_str.split()])) or \
                            (not is_2040 and ch_str.find(hdr_str_ch) == -1):

                            if data[i].find(test_time_substr) > -1:  # this line might be the next time header
                                print('found test_time_substr in line i =', i, ' --> ', data[i])
                                print('incrementing down one')
                                i -= 1  # increment down one (incremented at end of loop, will start on this line next)

                            # ########### 2023-02-18: TESTING FKt EM712 with 2 RX units
                            # look for 'RX' identifying second unit starting with channel 129
                            # but not hdr_str_receiver at start of BIST run
                            if data[i].find('RX') > -1 and data[i].find(hdr_str_receiver) == -1:  # look for 'RX  2' at start of next RX unit
                                print('FOUND possible second RX unit, looking for next channels starting with 129')
                                while i < len(data):
                                    # if data[i].find(hdr_str_ch) > -1 or data[i].find('129')
                                    if any([ch_check.find('129') > -1 for ch_check in data[i].split()]):
                                        print('found possible second RX unit starting with channel ', data[i])
                                        print('breaking with i =', i)
                                        break
                                    else:
                                        print('did not find possible second RX unit in this line: ', data[i])
                                        i += 1  # increment until next channel

                                continue  # do not break the channel loop


                            print('breaking out of channel loop with i =', i)
                            break

                        # if ch_str.find(hdr_str_ch) > -1:  # look for #: (SIS 4) or Ch (SIS 5) at start of line
                        z_str = ch_str.split()
                        ch_count = z_str[1]
                        print('found z_str = ', z_str)
                        # print('ch_str =', ch_str)

                        # convert Z values > 1000 (logged as, e.g., 1.1k = 1100) to simple number
                        z_str = [str(float(z.replace('k', ''))*1000) if z.find('k') > -1 else z for z in ch_str.split()]
                        print('--> after conversion of outliers > 1000 (k), z_str = ', z_str)

                        if sis_version == 4:  # SIS 4: store floats of one channel from all boards in string
                            for x in z_str[1:]:
                                # zrx_test.append(float(x))
                                # zrx_temp['rx_new'][t].append(float(x))  # append channels for this test
                                zrx_test[t].append(float(x))  # append channels for this test

                        else:  # SIS 5: store floats of one channel across all frequencies in string
                            # print('working on SIS 5 format with zlim_count = ', zlim_count)
                            z_str = z_str[1:]  # ignore first value (channel)
                            # print('z_str after removing channel = ', z_str)

                            if not is_2040:  # non-2040: ignore phase at end of each row; 2040: phase is later in file
                                z_str = z_str[1:(-1*zlim_count)]

                            # print('now looking at reduced z_str = ', z_str)
                            for x in z_str:
                                # print('SIS 5: appending RX Z value = ', x)
                                # zrx_test.append(float(x))
                                # zrx_temp['rx_new'][t].append(float(x))  # append channels for this test
                                zrx_test[t].append(float(x))  # append channels for this test

                            # x = z_str[2]  # works for single frequency test
                            # zrx_test.append(float(x))  # append zrx for one channel, reshape later
                            # print('now looking at reduced z_str = ', z_str[2:(-1*zlim_count)])
                            # for x in z_str[2:(-1*zlim_count)]:
                            #     print('SIS 5: appending RX Z value = ', x)
                            #     zrx_test.append(float(x))

                    i += 1
                    print('incremented i in channel loop to i =', i)

                    # else:   ################# TESTING ###################
                    #     i += 1


                print('just finished channel parsing loop with ', len(zrx_test[t]),
                      'elements in zrx_test[t] =', zrx_test[t])
                print('leaving this loop with i = ', i)



            # parse transducer impedance data, parse limits (on same line as header) and channels (SIS 5 = NaN)
            if i < len(data) and data[i].find(hdr_str_array) > -1:
                print('\n\t***found ARRAY header string in', data[i])
                # zrx_array_limits = data[i][data[i].find("[")+1:data[i].find("]")]
                # zrx_array_limits = [float(x) for x in zrx_array_limits.split()]

                lim_temp = data[i][data[i].find("[")+1:data[i].find("]")]
                # zrx_array_limits.append([float(x) for x in lim_temp.split()])  # store list of limits for each freq
                zrx_temp['rx_array_limits'][t] = [float(x) for x in lim_temp.split()]
                print('zrx_temp[rx_array_limits][t] is now', zrx_temp['rx_array_limits'][t])

                n_freq = len(zrx_temp['freq_range'][t])
                zrx_temp['rx_array_limits'][t] = {}
                print('got n_freq = ', n_freq)
                for f in range(n_freq):
                    zrx_temp['rx_array_limits'][t][f] = [float(x) for x in lim_temp.split()]  # store lims for each freq

                print('stored zrx_temp[rx_array_limits][t]=', zrx_temp['rx_array_limits'][t])

                while data[i].find(hdr_str_ch) == -1:  # find first channel header
                    i = i+1

                while True:  # read channels until something other than a channel or whitespace is found
                    ch_str = data[i]
                    if len(ch_str.split()) > 0:  # if not just whitespace, check if start of channel data
                        if ch_str.find(hdr_str_ch) > -1:  # look for #: (SIS 4) or Ch (SIS 5) at start of line
                            # replace '*' (used for marking out of spec channels) and 'Open' with very high Z value
                            z_str_array = ch_str.replace("*", "").replace('Open', '999999')[ch_str.find(hdr_str_ch)+1:]

                            # convert Z values > 1000 (logged as, e.g., 1.1k = 1100) to simple number
                            z_str_array = [float(z.replace('k', ''))*1000 if z.find('k') > -1 else
                                           float(z) for z in z_str_array.split()]

                            if sis_version == 4:  # SIS 4: store floats of one channel across 4 boards
                                for x in z_str_array:
                                    # zrx_array_test.append(x)
                                    # zrx_temp['rx_array_new'][t].append(float(x))  # append channels for this test
                                    zrx_array_test[t].append(float(x))  # append channels for this test

                            else:  # SIS 5: transducer impedance not available; store NaN
                                # zrx_array_test.append(np.nan)
                                zrx_array_test[t].append(np.nan)

                        else:  # break if not whitespace and not channel data
                            break

                    i += 1  # increment
        
            # SIS 4 ONLY: find temperature data and loop through entries
            if i < len(data) and data[i].find("Temperature") > -1:
                if data[i+2].find("RX") > -1:
                    print('parsing RX TEMPERATURE')
                    t_temp += 1  # iterate temperate test counter used as key in temperature dict
                    zrx_temp['test_temp'].append(t_temp)
                    zrx_temp['test_datetime_temp'].append(test_datetime)
                    print('\n\t***new zrx_temp test_temperature number appended: ', zrx_temp['test_temp'])
                    print('\t***new zrx_temp test_datetime appended:', zrx_temp['test_datetime_temp'])
                    zrx_temp['rx_temp'][t_temp] = []  # new temperature data for this test, not freq-dependent
                    trx_limits_test = data[i+2][data[i+2].find(":")+1:].replace("-", "")
                    # trx_limits = [float(x) for x in trx_limits.split()]
                    # trx_limits.append([float(x) for x in trx_limits_test.split()])  # store list of limits
                    zrx_temp['rx_temp_limits'].append([float(x) for x in trx_limits_test.split()])  # store list of lims

                    # FUTURE: change trx_limits to append list of limits for each freq, as rcvr and xdcr above
                    j = 0

                    while len(data[i+j+3]) > 3:  # read temp until white space with len<=1 (no need for n_rx_boards)
                        t_str = data[i+j+3][3:]
                        # trx.append(float(t_str.split()[0]))
                        # trx_test[t_temp].append(float(t_str.split()[0]))
                        zrx_temp['rx_temp'][t_temp].append(float(t_str.split()[0]))

                        j += 1

                    print('parsed new RX temperature, zrx_temp[rx_temp][t_temp] is now', zrx_temp['rx_temp'][t_temp])

            i += 1  # increment

            # print('at end of while loop, i is ', i)

    except ValueError:
        print("***WARNING: Error parsing ", fname)

    # if data found, reshape and store in temp dict
    # if multiple BISTs in one file, this approach assumes each has the same freq range(s) and limits, if parsed
    if len(zrx_test) > 0:
        # reorganize multi-freq SIS 5 data into consecutive tests
        # n_freq = max([1, len(zrx_temp['freq_range'])])
        # n_freq = max([1, len(zrx_temp)])
        # print('****** last step in parser, got n_freq = ', n_freq)
        # print('zrx_temp[rx_new] = ', zrx_temp['rx_new'])

        # ORIGINAL METHOD for zrx_test with all appended lines, regardless of number of tests/freqs
        # if sis_version == 5 and n_freq > 1:
        # if sis_version == 5:
        #     print('SIS 5 --> multiple frequencies parsed --> resorting by frequency')
        #     zrx_test_by_freq = []
        #     for f in range(n_freq):
        #         zrx_freq = [zrx_test[i] for i in range(f, len(zrx_test), n_freq)]
        #         print('extending zrx_test_by_freq using zrx values for f=', zrx_temp['freq_range'][f], '=', zrx_freq)
        #         zrx_test_by_freq.extend(zrx_freq)  # each zrx_freq list includes all tests for that frequency
        #
        #     zrx_test = zrx_test_by_freq  # resorted list in order of frequencies

        # NEW METHOD
        print('*************** testing new freq sorting method ****************8')
        # if sis_version == 5 and n_freq > 1:
        # if sis_version == 5:

        # print('SIS 5 --> multiple frequencies parsed --> resorting by frequency')
        # for t in range(t+1):
        print('starting ')

        zrx_temp['rx'] = {}
        zrx_temp['rx_array'] = {}
        zrx_temp['rx_temp'] = {}

        for t in zrx_test.keys():
            print('freq range for this test is ', zrx_temp['freq_range'][t])

            n_freq = max([1, len(zrx_temp['freq_range'][t])])
        # for t in zrx_temp['rx_new'].keys():
            print('working on test t =', t, ' with n_freq =', n_freq, ' and freq_range =', zrx_temp['freq_range'][t])
            zrx_test_by_freq_new = []
            # print('zrx_temp[rx_new][t] =', zrx_temp['rx_new'][t])

            # zrx_new = zrx_test[t]
            # zrx_array_new = []  # sort transducer data only if parsed
            # if zrx_array_test[t]:
            #     zrx_array_new = zrx_array_test[t]
            #
            # else:  # assign NaNs for unavailable array impedance fields (e.g., SIS 5 and some SIS 4 BISTs)
            #     zrx_temp['rx_array'] = np.empty(np.shape(zrx_temp['rx']))
            #     zrx_temp['rx_array'][:] = np.nan
            #     # zrx_temp['rx_array_limits'] = [].extend([[np.nan, np.nan]*n_freq])
            #     zrx_temp['rx_array_limits'] = [[np.nan, np.nan] for i in range(n_freq)]

            zrx_temp['rx'][t] = {}
            zrx_temp['rx_array'][t] = {}
            zrx_temp['rx_temp'][t] = {}

            for f in range(n_freq):
                print('working on freq f=', f)
                # zrx_freq_new = [zrx_test_new[i] for i in range(f, len(zrx_test_new), n_freq)]
                print('for t =', t, 'and f =', f, 'zrx_test[t] has len =', len(zrx_test[t]))
                zrx_test_freq = [zrx_test[t][i] for i in range(f, len(zrx_test[t]), n_freq)]
                print('zrx_test_freq has len=', len(zrx_test_freq))
                # reshape data for this test and frequency into shape (n_boards, 32_channels_per_board)
                # zrx_temp['rx_new'][t][f] = np.transpose(np.reshape(np.asarray(zrx_freq_new), (32, -1)))
                print('np.asarray(zrx_test_freq) has shape', np.shape(np.asarray(zrx_test_freq)))
                print('after reshaping, has shape', np.shape(np.reshape(np.asarray(zrx_test_freq), (32, -1))))
                print('after transpose, has shape', np.shape(np.transpose(np.reshape(np.asarray(zrx_test_freq), (32, -1)))))

                #######################################################################################################

                # DEFAULT PRIOR TO FKt TESTING
                # zrx_temp['rx'][t][f] = np.transpose(np.reshape(np.asarray(zrx_test_freq), (32, -1)))

                # TESTING FKt EM712 --> THIS PUTS THE OUTLIER CHANNEL IN THE CORRECT SPOT
                n_rx_boards = int(len(zrx_test_freq)/32)
                print('***ahead of reshape, got n_rx_boards = ', n_rx_boards)
                zrx_temp['rx'][t][f] = np.reshape(np.transpose(np.asarray(zrx_test_freq)), (n_rx_boards, -1))

                #######################################################################################################

                print('\n   ***zrx_temp[rx][t][f] for test', t, ' freq', f, ' has shape=',
                      np.shape(zrx_temp['rx'][t][f]), 'and looks like: ', zrx_temp['rx'][t][f])

                if zrx_array_test[t]:  # sort array data by test and frequency, if parsed
                    print('attempting to sort array data')
                    zrx_array_test_freq = [zrx_array_test[t][i] for i in range(f, len(zrx_array_test[t]), n_freq)]
                    zrx_temp['rx_array'][t][f] = np.transpose(np.reshape(np.asarray(zrx_array_test_freq), (32, -1)))
                    print('\n   ***zrx_temp[rx_array][t][f] for test', t, ' freq', f, ' has shape=',
                          np.shape(zrx_temp['rx_array'][t][f]), 'and looks like: ', zrx_temp['rx_array'][t][f])
                    # zrx_temp['rx_array_limits'] = zrx_array_limits

                else:  # otherwise, assign NaNs
                    print('assigning NaNs for array impedance')
                    zrx_temp['rx_array'][t][f] = np.empty(np.shape(zrx_temp['rx'][t][f]))
                    zrx_temp['rx_array'][t][f][:] = np.nan
                    # zrx_temp['rx_array_limits'][t] = [[np.nan, np.nan] for i in range(n_freq)]

                # if trx_test and trx_limits:  # store temperature data if parsed
                #     zrx_temp['rx_temp'][t][f] = trx_test[t]
                #     zrx_temp['rx_temp_limits'] = trx_limits
                #
                # else:  # assign NaNs for unavailable fields
                #     zrx_temp['rx_temp'][t][f] = np.empty(np.shape(zrx_temp['rx'][t][f]))
                #     zrx_temp['rx_temp'][t][f][:] = np.nan
                #     # zrx_temp['rx_temp_limits'] = [[np.nan, np.nan]*n_freq]
                #     zrx_temp['rx_temp_limits'] = [[np.nan, np.nan] for i in range(n_freq)]



                # print('extending zrx_test_by_freq_new using zrx values for f=', zrx_temp['freq_range'][f], '=', zrx_freq)
                # zrx_test_by_freq_new.extend(zrx_freq_new)  # each zrx_freq list includes all tests for that frequency

                # NEW METHOD: testing sort for frequencies within each test list
                # n_cols_new = int(len(zrx_test_by_freq_new) / n_rx_channels / n_freq)  # len(zrx_temp['freq_range']))
                # print('n_cols_new = ', n_cols_new)

                # transpose step results in shape = [n_tests*n_boards, n_channels*n_freq]
                # zrx_test_freq_new = np.transpose(np.reshape(np.asarray(zrx_test_by_freq_new), (-1, n_cols_new)))
                # print('made it past transpose, shape =', np.shape(zrx_test_freq_new))
                # zrx_temp['rx_new'][t] = zrx_test_freq_new
                # print('\n\t*** shape of zrx_temp[rx_new][t] for test=', t, ' after sorting by freq:', np.shape(zrx_temp['rx_new'][t]))

            # zrx_test = zrx_test_by_freq  # resorted list in order of frequencies


        # # ORIGINAL METHOD: reshape parsed Z data in variable length list as array, transpose for order expected by plotter
        # # row = board, col = channel, extending cols for each test and freq
        # n_cols = int(len(zrx_test)/n_rx_channels/n_freq)  #len(zrx_temp['freq_range']))
        # print('n_cols = ', n_cols)
        #
        # # transpose step results in shape = [n_tests*n_boards, n_channels*n_freq]
        # zrx_temp['rx'] = np.transpose(np.reshape(np.asarray(zrx_test), (-1, n_cols)))
        # print('\n\t*** shape of zrx_temp[rx] after sorting by freq:', np.shape(zrx_temp['rx']))

        # zrx_temp['rx_limits'] = zrx_limits
        # if zrx_array_test:  # store array impedance data if parsed
        #     # like rx data, the rx_array should have shape [n_tests*n_boards, n_channels*n_freq] after transpose
        #     zrx_temp['rx_array'] = np.transpose(np.reshape(np.asarray(zrx_array_test), (-1, n_cols)))
        #     zrx_temp['rx_array_limits'] = zrx_array_limits
        #     print('zrx_temp[rx_array] has shape', np.shape(zrx_temp['rx_array']))
        #     print('storing rx_array_limits =', zrx_array_limits)
        #     print('zrx_temp[rx_array_limits] is now', zrx_temp['rx_array_limits'])
        #
        # else:  # assign NaNs for unavailable array impedance fields (e.g., SIS 5 and some SIS 4 BISTs)
        #     zrx_temp['rx_array'] = np.empty(np.shape(zrx_temp['rx']))
        #     zrx_temp['rx_array'][:] = np.nan
        #     # zrx_temp['rx_array_limits'] = [].extend([[np.nan, np.nan]*n_freq])
        #     zrx_temp['rx_array_limits'] = [[np.nan, np.nan] for i in range(n_freq)]

        # if trx_test and trx_limits:  # store temperature data if parsed
        #     zrx_temp['rx_temp'] = trx_test
        #     zrx_temp['rx_temp_limits'] = trx_limits
        #     zrx_temp['test_temp'] =
        #
        # else:  # assign NaNs for unavailable fields
        #     zrx_temp['rx_temp'] = np.empty(np.shape(zrx_temp['rx']))
        #     zrx_temp['rx_temp'][:] = np.nan
        #     # zrx_temp['rx_temp_limits'] = [[np.nan, np.nan]*n_freq]
        #     zrx_temp['rx_temp_limits'] = [[np.nan, np.nan] for i in range(n_freq)]

        print('leaving parser with zrx_temp[rx_limits] = ', zrx_temp['rx_limits'])
        print('leaving parser with zrx_temp[rx_array_limits] = ', zrx_temp['rx_array_limits'])
        return(zrx_temp)
        
    else:
        print("Error in zrx parser, len(zrx) <= 0")
        return []


def plot_rx_z(z, save_figs=True, output_dir=os.getcwd()):
    # plot RX impedance for each file
    fig_width = 16  # inches for figure width
    supertitle_height = 4  # inches for super title
    supertitle_pad = 1
    subplot_board_height = 0.8  # inches per board (row) of subplot (to be scaled by number of boards for each subplot)
    cbar_size_in = 0.4
    # cbar_width_in = fig_width/2  # inches for colorbar width (horizontal)
    cbar_pad_in = 0.7  # inches for colorbar padding
    n_rx_channels = 32  # assumed fixed

    # loop through RX Z data stored in z['rx'][file_index][test_index][freq_index]

    for i in range(len(z['filename'])):
        # is_2040 = z['model'][i].find('2040') > -1
        print('checking z[model][i] = ', z['model'][i])
        is_2040 = z['model'][i] in ['2040', '2045', '2040P']
        print('got is_2040 =', is_2040)

        # is_2040 = any([z['model'][i].find(m) > -1 for m in ['2040', '2045']])
        print('Plotting', z['filename'][i], ' with f range(s):', print(z['freq_range'][i]))
        print('in plotter, z[rx_limits] =', z['rx_limits'])
        print('\n\t*** in plotter, z[test]=', z['test'])
        sis_version = z['sis_version'][i]

        for t in z['rx'][i].keys():  # loop through all tests in this file
            n_freq = len(z['freq_range'][i][t])  # assumed all tests in this file cover the same frequency range(s)
            print('for test =', t, 'n_freq =', n_freq)

            for f in range(n_freq):  # plot each frequency in this test (corresponding to cols in zrx)
                test_freq = z['freq_range'][i][t][f]
                print('f=', f)
                print('frequency =', test_freq)
                print('shape of zrx data for i, t, f = (', i, t, f, ') = ', np.shape(z['rx'][i][t][f]))

                n_rx_boards = np.shape(z['rx'][i][t][f])[0]

                # get number of RX boards; zrx size is (n_rx_boards, n_channels*n_freq_tests); n_channels is 32/board
                # n_rx_boards = np.divide(np.size(zrx), 32 * n_freq)
                subplot_height = n_rx_boards * subplot_board_height
                # subplot_height_max = 4*subplot_board_height  # 'max' subplot height so fig scales same for 2-4 boards
                subplot_count = [1, 2][int(sis_version == 4 and not is_2040)]
                height_fac1 = [1.1, 0.9][int(n_rx_boards == 4.0)]
                # height_fac2 = [1, 0.6][int(sis_version == 5)]
                height_fac2 = [1, 0.6][int(subplot_count == 1)]
                # cbar_fac = [1, 1.25][int(sis_version == 5)]
                cbar_fac = [1, 1.25][int(subplot_count == 1)]
                print('sis_version =', sis_version)
                print('got subplot_count = ', subplot_count)
                print('got subplot height =', subplot_height)
                print('using height_fac1 and 2 =', height_fac1, height_fac2)

                fig_height = supertitle_height + subplot_count * height_fac1 * height_fac2 * (
                            subplot_height + cbar_size_in + cbar_pad_in)
                print('fig_height, fig_width =', fig_height, fig_width)
                print('got n_rx_boards =', n_rx_boards)

                try:  # try plotting
                    # fig = plt.figure()
                    fig = plt.figure(figsize=(fig_width, fig_height))
                    gs = gridspec.GridSpec(subplot_count, 1, height_ratios=[1] * subplot_count)

                    # top plot: line plot for each slot across all channels, different color for each slot
                    ax1 = plt.subplot(gs[0])
                    ax1.set_aspect('equal')

                    if subplot_count == 2:
                        print('making ax2')
                        ax2 = plt.subplot(gs[1])
                        ax2.set_aspect('equal')

                    fig.set_tight_layout(True)
                    fig.subplots_adjust(left=0.1, right=0.9, bottom=0.1, top=0.9)

                    # fig.tight_layout(rect=[0, 0.03, 1, 0.90])

                    bbox = ax1.get_window_extent().transformed(fig.dpi_scale_trans.inverted())
                    print('got bbox =', bbox)
                    print('bbox width = ', bbox.width)
                    print('bbox height = ', bbox.height)

                    cbar_fraction = cbar_fac * cbar_size_in / bbox.height
                    cbar_pad = cbar_fac * cbar_pad_in / bbox.height

                    print('using cbar_fraction and cbar_pad =', cbar_fraction, cbar_pad)

                    # declare standard spec impedance limits, used if not parsed from BIST file
                    rx_rec_min = 600
                    rx_rec_max = 1000
                    rx_xdcr_min = 250
                    rx_xdcr_max = 1200

                    print('z rx_limits =', z['rx_limits'])
                    print('z rx_limits[i] =', z['rx_limits'][i])
                    print('z rx_limits[i][t] =', z['rx_limits'][i][t])
                    print('z rx_limits[i][t][f] =', z['rx_limits'][i][t][f])
                    print('z rx_array_limits =', z['rx_array_limits'])

                    try:  # get receiver plot color limits from parsed receiver Z limits
                        print('z rx_limits[i][t][f]=', z['rx_limits'][i][t][f])
                        rx_rec_min, rx_rec_max = z['rx_limits'][i][t][f]
                        print('assigned rx_rec_min and max = ', rx_rec_min, rx_rec_max)

                    except:
                        print('Error assigning receiver color limits from z[rx_limits][i][t] for i, t =', i, t)

                    if subplot_count == 2:  # try to get transducer impedance color limits if present
                        try:  # get array plot color limits from parsed array Z limits
                            print('z rx_array_limits[i][t][f] =', z['rx_array_limits'][i][t][f])
                            rx_xdcr_min, rx_xdcr_max = z['rx_array_limits'][i][t][f]
                            print('assigned rx_xdcr_min and max = ', rx_xdcr_min, rx_xdcr_max)

                        except:
                            print('Error assigning array color limits from z[rx_array_limits][i][t] for i, t, f =', i, t, f)

                    # plot the RECEIVER (SIS 4) or COMBINED (SIS 5) Z values; plot individual test data for EM71X
                    # im = ax1.imshow(zrx[:, 32 * f:32 * (f + 1)], cmap='rainbow', vmin=rx_rec_min, vmax=rx_rec_max)
                    # print('shape for zrx[:,32*f:32*(f+1), original method is', np.shape(zrx[:, 32 * f:32 * (f + 1)]))
                    print('setting imshow for ax1 with t = ', t, ' and f = ', f)
                    # print('shape for zrx[n_rx_boards*t:n_rx_boards*(t+1), 32*f:32*(f + 1)], new method is', np.shape(zrx[n_rx_boards*t:n_rx_boards*(t+1), 32*f:32*(f + 1)]))
                    # im = ax1.imshow(zrx[n_rx_boards*t:n_rx_boards*(t+1), 32*f:32*(f + 1)],
                    #                 cmap='rainbow', vmin=rx_rec_min, vmax=rx_rec_max)  # plot test rows and freq cols
                    # print('np.shape of zrx_test =', np.shape(zrx_test))
                    # im = ax1.imshow(zrx_test[:, 32 * f:32 * (f + 1)], cmap='rainbow', vmin=rx_rec_min, vmax=rx_rec_max)
                    im = ax1.imshow(z['rx'][i][t][f], cmap='rainbow', vmin=rx_rec_min, vmax=rx_rec_max)
                    cbar = fig.colorbar(im, orientation='horizontal', ax=ax1, fraction=cbar_fraction, pad=cbar_pad)

                    try:  # get the colorbar units (EM2040 is dB signal strength, not impedance)
                        print('trying to get colorbar label from:')
                        print('z[rx_units] = ', z['rx_units'])
                        print('z[rx_units][i] = ', z['rx_units'][i])
                        print('z[rx_units][i][t] = ', z['rx_units'][i][t])
                        print('z[rx_units][i][t][f] = ', z['rx_units'][i][t][f])
                        # cbar_label = z['rx_units'][i][f] + ('s' if not is_2040 else '')  # convert 'ohms' or leave as 'dB'
                        cbar_label = z['rx_units'][i][t][f] + ('s' if not is_2040 else '')  # convert 'ohms' or leave as 'dB'


                    except:
                        print('Warning: failed to get colorbar label; setting default units')
                        cbar_label = ['ohms', 'Signal Amplitude [dB]'][int(is_2040)]

                    cbar_label = ''.join([str.capitalize(c) if c == 'o' else c for c in cbar_label])  # kOhms or Ohms
                    cbar.set_label(cbar_label)

                    # set ticks and labels
                    x_ticks = np.arange(0, 32, 1)
                    x_ticks_minor = np.arange(-0.5, 32.5, 1)
                    x_tick_labels = [str(x) for x in x_ticks]
                    y_ticks = np.arange(0, n_rx_boards, 1)
                    y_ticks_minor = np.arange(-0.5, n_rx_boards + 0.5, 1)
                    y_tick_labels = [str(y) for y in y_ticks]

                    ax1.set_yticks(y_ticks)
                    ax1.set_xticks(x_ticks)
                    ax1.set_yticklabels(y_tick_labels, fontsize=16)
                    ax1.set_xticklabels(x_tick_labels, fontsize=16)
                    ax1.set_yticks(y_ticks_minor, minor=True)  # set minor axes for gridlines
                    ax1.set_xticks(x_ticks_minor, minor=True)
                    ax1.grid(which='minor', color='k', linewidth=2)  # set minor gridlines
                    ax1.set_ylabel('RX Board', fontsize=16)
                    ax1.set_xlabel('RX Channel', fontsize=16)

                    ax1_title_str = 'RX ' + ['Impedance', 'Signal Amplitude'][int(is_2040)] + \
                                    [': Receiver', ''][int(sis_version == 5)]
                    ax1.set_title(ax1_title_str, fontsize=20)

                    # set axis tick formatter
                    ax1.xaxis.set_major_formatter(FormatStrFormatter('%g'))
                    ax1.yaxis.set_major_formatter(FormatStrFormatter('%g'))

                    if subplot_count == 2:  # plot transducer values if appropriate
                        try:  # plot the rx TRANSDUCER z values; plot individual test data for EM71X
                            im = ax2.imshow(z['rx_array'][i][t][f], cmap='rainbow', vmin=rx_xdcr_min, vmax=rx_xdcr_max)

                        except:
                            print('zrx_array not available for plotting for this frequency range')

                        # im = ax2.imshow(zrx_array_temp, cmap='rainbow', vmin=rx_xdcr_min, vmax=rx_xdcr_max)
                        cbar = fig.colorbar(im, orientation='horizontal', ax=ax2, fraction=cbar_fraction, pad=cbar_pad)
                        cbar.set_label(cbar_label)

                        # set ticks and labels
                        ax2.set_yticks(y_ticks)  # set major axes ticks
                        ax2.set_xticks(x_ticks)
                        ax2.set_yticklabels(y_tick_labels, fontsize=16)
                        ax2.set_xticklabels(x_tick_labels, fontsize=16)
                        ax2.set_yticks(y_ticks_minor, minor=True)
                        ax2.set_xticks(x_ticks_minor, minor=True)
                        ax2.grid(which='minor', color='k', linewidth=2)  # set minor gridlines
                        ax2.set_ylabel('RX Board', fontsize=16)
                        ax2.set_xlabel('RX Channel', fontsize=16)
                        ax2.set_title('RX Impedance: Transducer', fontsize=20)

                        if np.all(np.isnan(z['rx_array'][i][t][f])):  # plot text: no RX array data avail (e.g., SIS 5)
                            ax2.text(16, (n_rx_boards / 2) - 0.5, 'NO TRANSDUCER RX CHANNELS DATA',
                                     fontsize=24, color='red', fontweight='bold',
                                     horizontalalignment='center', verticalalignment='center_baseline')

                        # set axis tick formatter
                        ax2.xaxis.set_major_formatter(FormatStrFormatter('%g'))
                        ax2.yaxis.set_major_formatter(FormatStrFormatter('%g'))

                    # set the super title
                    print('z freq_range i t f =', z['freq_range'][i][t][f])
                    # freq_str = z['freq_range'][i][f] + ' kHz'
                    # freq_str = z['freq_range'][i][t][f] + ' kHz'
                    freq_str = z['freq_range'][i][t][f].replace('.0', '') + ' kHz'

                    freq_str = freq_str.replace('(High) kHz', 'kHz (High)').replace('(Low) kHz', 'kHz (Low)')  # SIS5 EM2040

                    print('in plotter, z[test_datetime] =', z['test_datetime'])
                    print('in plotter, z[test_datetime][i] =', z['test_datetime'][i])
                    print('in plotter, z[test_datetime][i][t] =', z['test_datetime'][i][t])

                    test_time_str = datetime.datetime.strftime(z['test_datetime'][i][t], '%Y/%m/%d %H:%M:%S.%f')[:-3]  # keep ms
                    title_str = 'RX Channels BIST\n' + 'EM' + z['model'][i] + ' (S/N ' + z['sn'][i] + ')\n' + \
                                test_time_str + '\nFrequency: ' + freq_str
                    # title_str = 'RX Channels BIST\n' + 'EM' + z['model'][i] + ' (S/N ' + z['sn'][i] + ')\n' + \
                    #             z['date'][i] + ' ' + z['time'][i] + '\nFrequency: ' + freq_str

                    print('title_str=', title_str)
                    fig.suptitle(title_str, fontsize=20)

                    # save the figure
                    if save_figs is True:
                        fig = plt.gcf()
                        print('** current figure size is:', fig.get_size_inches())
                        print('test_time_str for figure file name: ', test_time_str)
                        fig_name = 'RX_Z_EM' + z['model'][i] + '_SN_' + z['sn'][i] + '_' + \
                                   test_time_str.replace('/', '').replace(':', '').replace('.', '_').replace(' ', '_') + \
                                   '_freq_' + freq_str.replace(' ', '_').replace('(', '').replace(')', '') + '.png'

                        # '_freq_' + z['freq_range'][i][f] + '_kHz' + '.png'
                        print('Saving', fig_name)
                        fig.savefig(os.path.join(output_dir, fig_name), dpi=100)

                    plt.close()

                except ValueError:  # move on if error
                    print("***WARNING: Error plotting ", z['filename'][i], ' test number ', t)


def plot_rx_z_history(z, save_figs=True, output_dir=os.getcwd()):
    # plot lines of all zrx values colored by year to match historic Multibeam Advisory Committee plots
    # new version accommodating multiple freq and tests per file
    # loop through RX Z data stored in z['rx'][file_index][test_index][freq_index]

    # set x ticks and labels on bottom of subplots to match previous MAC figures
    plt.rcParams['xtick.bottom'] = plt.rcParams['xtick.labelbottom'] = True
    plt.rcParams['xtick.top'] = plt.rcParams['xtick.labeltop'] = False

    # get list of all frequencies present
    # get model, sn, time span
    model = z['model'][0]  # reassign model and sn in case last BIST parse failed
    sn = z['sn'][0]

    # get all test times in z['test_datetime'][file_index][test_index]
    test_times = [test_time for file_index in z['test_datetime'] for test_time in file_index]
    print('got test_times = ', test_times)
    # datemin = min(test_times)
    # datemax = max(test_times)
    # print('got datemin, datemax =', datemin, datemax)
    # yrmin = int(min(test_times).strftime('%Y'))
    # yrmax = int(max(test_times).strftime('%Y'))

    yrmin, yrmax = [int(t.strftime('%Y')) for t in [min(test_times), max(test_times)]]

    yrs = [str(yr) for yr in range(yrmin, yrmax + 1)]
    print('got yrmin, yrmax =', yrmin, yrmax)
    print('setting years list =', yrs)

    # get all frequencies in z['rx'][file_index][test_index][freq_index]
    print('trying to get set of all frequencies...')
    test_freqs = []
    for i in range(len(z['filename'])):
        for t in z['freq_range'][i].keys():
            test_freqs.extend([f for f in z['freq_range'][i][t]])

    print('got all test_freqs =', test_freqs)



    f_set = sorted([f for f in set(test_freqs)])
    n_freq = len(f_set)
    print('reduced set of freqs: ', f_set)
    print('number of frequencies detected:', n_freq)

    # n_rx_boards = np.size(z['rx'][0], 0)
    n_rx_boards = np.size(z['rx'][0][0][0], 0)  # assumed constant for all tests
    n_rx_channels = 32  # this should probably always be 32 (boards are 'rx32')
    n_rx_modules = n_rx_channels*n_rx_boards
    print('n_rx_boards is', n_rx_boards)
    print('n_rx_channels is', n_rx_channels)
    print('n_rx_modules is', n_rx_modules)

    colors = plt.cm.rainbow(np.linspace(0, 1, len(yrs)))  # set up line colors over number of years
    zrx_module = np.arange(1, n_rx_modules+1)  # range of RX modules for plotting (unlike channels, this starts at 1)
    # zrx_channel = np.tile(np.arange(0, n_rx_channels), [n_rx_boards, 1])  # array of zrx chans for plotting (start at 0)

    # set axis and label parameters
    axfsize = 16  # axis font size
    # dx_tick = 8
    dx_tick = 2*n_rx_boards
    dy_tick = [50, 1][model.find('2040') > -1]  # use dy tick = 1 dB for 2040 variants RX Z
    dy_tick_array = [150, 1][model.find('2040') > -1]  # same for array, though this is probably not available for 2040

    # loop through the frequency ranges, years and plot zrx and zrx_array lines in same color for that year
    # f_set = list(set(a for b in z['freq_range'] for a in b))  # get unique frequencies in list of lists in z[freq_range]
    # print('f_set is', f_set)

    ################################################ RETHINK HOW TO TRACK LAST BIST FOR EACH FREQUENCY
    # find index of most recent BIST for plotting
    # dt_format = '%Y%m%d%H%M%S'
    dt_format = '%Y%m%d%H%M%S.%f'
    bist_time_str = [z['date'][d] + z['time'][d] for d in range(len(z['date']))]  # BIST FILE TIMES, not test times
    bist_time_obj = [datetime.datetime.strptime(t.replace('/', '').replace(':', ''), dt_format) for t in bist_time_str]

    # bist_time_set = [t for t in set(bist_time_obj)]
    # bist_count_max = len(bist_time_set)

    # bist_time_last = max(bist_time_obj)
    # print('got bist_time_last =', bist_time_last)
    # print('len bist_time_obj =', len(bist_time_obj), 'and bist_count_max =', bist_count_max)

    # idx_last = np.argmax(bist_time_obj)
    # idx_last = []

    for f in range(len(f_set)):  # loop through all frequency sets (may not be parsed in same order)
        bist_count = 0
        print('working on frequency range', f_set[f])  # z['freq_range'][0][f])
        print('-> f=', f)
        # make figure with two subplots
        fig = plt.figure()
        fig.set_size_inches(11, 16)  # previous MAC plots height/width ratio is 1.25
        ax1 = fig.add_subplot(2, 1, 1)
        ax2 = fig.add_subplot(2, 1, 2)
        plt.subplots_adjust(top=0.85)  # try to keep long supertitle from overlapping

        # make list of line artists, reset for each frequency
        legend_labels = []
        legend_artists = []

        # reset placeholders for most recent BIST at each frequency
        bist_test_times = []
        zrx_last = []
        zrx_array_last = []

        for y in range(len(yrs)):  # loop through all years for this freq
            print('working on year =', yrs[y])
            # print('--> y=', y)
            # legend_labels.append(yrs[y])  # store year as label for legend
            for i in range(len(z['filename'])):  # loop through all files and tests
                # print('---> i = ', i)
                for t in z['rx'][i].keys():
                    # print('---->t =', t)

                    # if z['date'][i][:4] == yrs[y]:  # check if this BIST matches current year
                    if z['test_datetime'][i][t].strftime('%Y') == yrs[y]:  # check if test year matches desired year
                        print('year matches')
                        print('z[rx_limits] =', z['rx_limits'])
                        print('z[rx_limits][i] =', z['rx_limits'][i])
                        print('z[rx_limits][i][t] =', z['rx_limits'][i][t])

                        # get limits parsed for this BIST
                        # zrx_limits = z['rx_limits'][i]
                        # zrx_array_limits = z['rx_array_limits'][i]
                        zrx_limits = z['rx_limits'][i][t][f]
                        print('got zrx_limits = ', zrx_limits)

                        zrx_unit = z['rx_units'][i][t][f]
                        print('in history plotter, zrx_unit = ', zrx_unit)

                        # print('trying to get rx_array_limits from ', z['rx_array_limits'])
                        try:
                            zrx_array_limits = z['rx_array_limits'][i][t][f]
                        except:
                            zrx_array_limits = [0, 1]

                        # default dy_tick of 50 (for non-EM2040) may be too large for some systems with tighter limits
                        if np.diff(zrx_limits) < dy_tick:
                            # dy_tick_local = 10
                            dy_tick_local = [10, 1][int(np.diff(zrx_limits) < 10)]

                        else:
                            dy_tick_local = dy_tick

                        if np.diff(zrx_array_limits) < dy_tick_array:
                            # dy_tick_array_local = 10
                            dy_tick_array_local = [10, 1][int(np.diff(zrx_array_limits) < 10)]

                        else:
                            dy_tick_array_local = dy_tick_array

                        print('in history plotter, zrx_limits and zrx_array_limits are', zrx_limits, zrx_array_limits)

                        # loop through all available frequency ranges for this BIST
                        # for j in range(len(z['freq_range'][i])):
                        for j in range(len(z['freq_range'][i][t])):
                            # print('-----> j =', j)
                            # # find idx of data that match this frequency range
                            if z['freq_range'][i][t][j] == f_set[f]:  # check if BIST freq matches freq of interest

                                # if i == idx_last:  # store for final plotting in black if this is most recent data
                                # check whether this bist test time has already been plotted for this freq
                                # (avoid plotting and counting duplicate tests)
                                test_time = z['test_datetime'][i][t]
                                print('looking at test_datetime =', z['test_datetime'][i][t])
                                if test_time in bist_test_times:
                                    print('this test time has already been plotted; continuing')
                                    continue

                                else:  # store this unique test time
                                    bist_test_times.append(test_time)
                                    # print('storing this test time --> bist_test_times is now', bist_test_times)

                                # store impedance data as array for local use if frequency matches
                                # zrx = np.asarray(z['rx'][i])[:, n_rx_channels*j:n_rx_channels*(j+1)]
                                # print('found matching freq for this test, z[rx][i][t][j] is:', z['rx'][i][t][j])
                                zrx = np.asarray(z['rx'][i][t][j])
                                print('found matching freq for this test, zrx is stored as:', zrx)

                                try:
                                    # zrx_array = np.asarray(z['rx_array'][i])[:, n_rx_channels*j:n_rx_channels*(j+1)]
                                    zrx_array = np.asarray(z['rx_array'][i][t][j])

                                except:
                                    print('zrx_array not available for this frequency range')
                                    zrx_array = np.nan*np.ones(np.shape(zrx))

                                if test_time == max(bist_test_times):  # store most recent test data
                                    zrx_last = zrx
                                    zrx_array_last = zrx_array
                                    print('stored zrx data for new most recent test time: ', test_time)

                                # print('**** STORED ZRX.... NOW NEED TO PLOT')
                                # print('the shape of zrx is', np.shape(zrx))
                                # print('the shape of zrx is', np.shape(zrx))

                                # skip if not 32 RX channels (parser err? verify this is the case for all RX xdcr cases)
                                # if zrx.shape[1] == n_rx_channels and zrx_array.shape[1] == n_rx_channels:
                                if all([np.size(z, 1) == n_rx_channels for z in [zrx, zrx_array]]):
                                    # print('*** both arrays have size along dim 1 == n_rx_channels, plotting!')
                                # if np.shape(zrx, 1) == n_rx_channels and np.shape(zrx_array, 1) == n_rx_channels
                                    # plot zrx_array history in top subplot, store artist for legend
                                    # print('using colors[y]=', colors[y])
                                    ax1.plot(zrx_module, zrx.flatten(), color=colors[y], linewidth=2)
                                    print('zrx_array.flatten = ', zrx_array.flatten())
                                    line, = ax2.plot(zrx_module, zrx_array.flatten(), color=colors[y], linewidth=2)

                                    # add legend artist (line) and label (year) if not already added
                                    if yrs[y] not in set(legend_labels):
                                    # if len(legend_artists) < len(legend_labels):
                                        legend_labels.append(yrs[y])  # store year as label for legend
                                        legend_artists.append(line)

                                    print('zrx_limits=', zrx_limits)
                                    print('zrx_array_limits=', zrx_array_limits)

                                    # define x ticks starting at 1 and running through n_rx_modules, with ticks at dx_tick
                                    x_ticks = np.concatenate((np.array([1]), np.arange(dx_tick, n_rx_modules + dx_tick - 1, dx_tick)))
                                    # y_ticks = np.arange(zrx_limits[0], zrx_limits[1] + 1, dy_tick)
                                    y_ticks = np.arange(zrx_limits[0], zrx_limits[1] + 1, dy_tick_local)
                                    # y_ticks_array = np.arange(zrx_array_limits[0], zrx_array_limits[1] + 1, dy_tick_array)
                                    y_ticks_array = np.arange(zrx_array_limits[0],
                                                              zrx_array_limits[1] + 1, dy_tick_array_local)

                                    print('set y_ticks =', y_ticks, 'and y_ticks_array =', y_ticks_array)
                                    # set ylim to parsed spec limits
                                    ax1.set_ylim(zrx_limits)
                                    ax2.set_ylim(zrx_array_limits)

                                    # set yticks for labels and minor gridlines
                                    ax1.set_yticks(y_ticks)
                                    ax1.set_yticks(y_ticks, minor=True)
                                    ax1.yaxis.set_major_formatter(FormatStrFormatter('%.1f'))  # format one decimal

                                    # get ylabel from units and capitalize (kOhms or Ohms)
                                    zrx_unit = ''.join([str.capitalize(c) if c == 'o' else c for c in zrx_unit])
                                    ax1.set_ylabel('Receiver Impedance (' + zrx_unit + ')\n(axis limits = Kongsberg spec.)',
                                                   fontsize=axfsize)

                                    ax2.set_yticks(y_ticks_array)
                                    ax2.set_yticks(y_ticks_array, minor=True)
                                    ax2.yaxis.set_major_formatter(FormatStrFormatter('%.1f'))  # format one decimal
                                    # ax2.set_ylabel('Transducer Impedance (ohms)\n(axis limits = Kongsberg spec.)',
                                    #                fontsize=axfsize)
                                    ax2.set_ylabel('Transducer Impedance (' + zrx_unit + ')\n(axis limits = Kongsberg spec.)',
                                                   fontsize=axfsize)

                                    if np.all(np.isnan(zrx_array)):  # plot text: no RX array impedance data available in BIST
                                        ax2.text((n_rx_modules / 2) - 0.5, (zrx_array_limits[1]-zrx_array_limits[0])/2,
                                                 'NO TRANSDUCER RX CHANNELS DATA',
                                                 fontsize=24, color='red', fontweight='bold',
                                                 horizontalalignment='center', verticalalignment='center_baseline')

                                    for ax in [ax1, ax2]:  # set xlim and aspect for both axes
                                        ax.set_xlim(0, n_rx_modules+1)
                                        ax.set(aspect='auto', adjustable='box')
                                        ax.set_xlabel('RX Module (index starts at 1)', fontsize=axfsize)
                                        ax.set_xticks(x_ticks)
                                        ax.set_xticks(x_ticks, minor=True)
                                        ax.grid(which='minor', color='k', linewidth=1)
                                        ax.tick_params(labelsize=axfsize)
                                        ax.xaxis.set_label_position('bottom')

                                    bist_count = bist_count+1
                                    # print('FINISHED PLOTTING THIS BIST')

                                else:
                                    # print('Skipping ', z['filename'], ' with ', str(zrx.shape[1]), ' RX and ',
                                    #       str(zrx_array.shape[1]), ' channels instead of 32!')
                                    print('Skipping ', z['filename'][i])

        # plot most recent BIST for this frequency
        ax1.plot(zrx_module, zrx_last.flatten(), color='k', linewidth=2)
        line, = ax2.plot(zrx_module, zrx_array_last.flatten(), color='k', linewidth=2)
        legend_artists.append(line)  # add line artist to legend list
        legend_labels.append('Last')

        # set legend
        l1 = ax1.legend(legend_artists, legend_labels,
                        bbox_to_anchor=(1.2, 1), borderaxespad=0,
                        loc='upper right', fontsize=axfsize)
        l2 = ax2.legend(legend_artists, legend_labels,
                        bbox_to_anchor=(1.2, 1), borderaxespad=0,
                        loc='upper right', fontsize=axfsize)
        # legend(bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0.)

        if yrmin == yrmax:
            years_str = 'Year: ' + str(yrmin)
        else:
            years_str = 'Years: ' + str(yrmin) + '-' + str(yrmax)

        # set the super title
        # freq_str = f_set[f] + ' kHz'
        freq_str = f_set[f].replace('.0','') + ' kHz'
        freq_str = freq_str.replace('(High) kHz', 'kHz (High)').replace('(Low) kHz', 'kHz (Low)')  # SIS 5 EM2040

        title_str = 'RX Channels BIST\n' + 'EM' + model + ' (S/N ' + sn + ')\n' + \
                    years_str + ' (' + str(bist_count) + ' BIST' + ('s' if bist_count > 1 else '') + ')\n' + \
                    'Frequency: ' + freq_str
                    # 'Frequency: ' + f_set[f] + ' kHz'
                    # 'Frequency: '+z['freq_range'][i][f]+' kHz'
        t1 = fig.suptitle(title_str, fontsize=20)
        fig.set_size_inches(10, 14)

        # save the figure
        if save_figs is True:
            # fig = plt.gcf()
            # fig.set_size_inches(10, 10)
            fig_name = 'RX_Z_EM' + model + '_SN_' + sn + '_history_' + str(yrmin) + '-' + str(yrmax) + \
                       '_freq_' + freq_str.replace(' ', '_').replace('(', '').replace(')', '') + '.png'
                       # '_freq_' + f_set[f] + '_kHz' + '.png'
                       # '_freq_'+z['freq_range'][i][f]+'_kHz'+'.png'
            print('Saving', fig_name)
            # fig.savefig(fig_name, dpi=100)
            print('*** output_dir =', output_dir)
            print('*** fig_name =', fig_name)

            fig.savefig(os.path.join(output_dir, fig_name), dpi=100,
                        bbox_extra_artists=(t1, l1, l2), bbox_inches='tight')  # add bbox extra artists to avoid cutoff

        plt.close()


# parse TX Channels BIST text file
def parse_tx_z(fname, sis_version=int(4), cbox_model_num=[]):
    z = init_bist_dict(1)  # set up TX Channels Z dict
    found_channels = False

    try:  # try reading file
        f = open(fname, "r")
        data = f.readlines()

    except ValueError:
        print('***WARNING: Error reading file', fname)

    if len(data) <= 0:  # skip if text file is empty
        print('***WARNING: No data read from file', fname)
        return []

    # Check to make sure its not a PU Params or System Report text file
    if any(substr in data[0] for substr in ["Database", "Datagram", "CPU"]):
        print("***WARNING: Skipping non-BIST file: ", fname)
        return []

    try:  # try parsing the data for all tests in text file
        header_str = ["Transmitter impedance rack:"]  # start of SIS 4 TX Channels test
        ch_hdr_str = "Ch:"  # start of SIS 4 channel data
        zlim = []  # placeholder empty Z limits, not available in SIS 4 format; plot_tx_z looks up Z lims if missing

        if sis_version is 5:
            header_str = ["TX channels", "Impedance limits"]  # strings before each batch of TX Z channel data in SIS 5
            ch_hdr_str = "Ch"  # start of SIS 5 channel data
            limit_str = "Impedance limits"  # start of impedance limit data; also repeats before each iteration of TX Z
            model_str = "EM"  # start of model number (within header str)

        i = 0
        while i < len(data):  # step through file and store channel data when found
            # ignore cases where TX Z header string was injected in BIST after the channel data and before phase data
            # if data[i].find('Phase') > -1:
            #     continue
            found_phase_header = False  # flag for SIS 5 case where header_str is present

            # if any(substr in data[i] for substr in header_str):  # find any TX Z header strings preceding ch. data
            # find any TX Z header strings preceding ch. data, but do not confuse with 'TX channels failed' string
            if any(substr in data[i] for substr in header_str) and data[i].find('failed') == -1:

                # if data[i].find('Phase') > -1:
                #     continue

                temp_str = data[i]
                print('got temp_str =', temp_str)

                if sis_version == 4:  # SIS 4: get rack and slot version from header
                    print('***SIS VERSION = 4')
                    rack_num = temp_str[temp_str.find(":") + 1:temp_str.find(":") + 4]
                    rack_num = int(rack_num.strip().rstrip())
                    slot_num = temp_str[temp_str.rfind(":") + 1:temp_str.rfind("\n")]
                    slot_num = int(slot_num.strip().rstrip()) - 1  # subtract 1 for python indexing

                else:  # SIS 5: get slot numbers for SIS 5 (e.g., 36 rows = 36 channels, 10 columns = 10 slots/boards)
                    print('***SIS VERSION = 5')

                    if temp_str.find(model_str) > -1:  # check for model_str in TX channels header, get number after EM
                        print('found model_str', model_str, ' in temp_str', temp_str)
                        model_num = temp_str[temp_str.rfind(model_str)+2:].strip()
                        print('in parse_tx_z, got model_num =', model_num)
                        # z['model'] = model_num

                        # if model_num.find('2040') > -1:  # no numeric TX Z data in EM2040 BISTs; return empty
                        #     print('returning because found model number = 2040 (no TX data)')
                        #     return []

                        # else:  # for SIS 5, store mean frequency for this model (not explicitly stated in BIST)
                        #     freq_str = get_freq(model_num)  # get nominal
                        #     freq = np.mean([float(n) for n in freq_str.replace('kHz', '').strip().split('-')])

                    # EM712 running SIS 4 is mostly SIS 5 format but does not have model number; try to get separately
                    else:  # try to get model number from SIS 4 format
                        print('trying to get model number')
                        sys_info = check_system_info(fname, sis_version=4)
                        model_num = sys_info['model']
                        print('back in parse_tx_z, got model_num =', model_num)

                        if not model_num:  # REVELLE 2022 BIST update - use model number from the user if not in file
                            model_num = cbox_model_num

                    if model_num.find('2040') > -1:  # no numeric TX Z data in EM2040 BISTs; return empty
                        print('returning because found model number = 2040 (no TX data)')
                        return []

                    else:  # for SIS 5, store mean frequency for this model (not explicitly stated in BIST)
                        z['model'] = model_num
                        freq_str = get_freq(model_num)  # get nominal
                        freq = np.mean([float(n) for n in freq_str.replace('kHz', '').strip().split('-')])

                    print('looking for limit str = ', limit_str)
                    while data[i].find(limit_str) == -1:  # loop until impedance limit string is found
                        print('incrementing i from ', i)
                        i += 1
                        if i == len(data):
                            print('*** reached EOF without finding TX limit string; returning [] from parse_tx_z ***')
                            return []

                    temp_str = data[i]
                    zlim_str = temp_str[temp_str.find('[')+1:temp_str.rfind(']')]  # FUTURE: store limits for plot cbar
                    print('found z_limits=', zlim_str)
                    zlim = [float(lim) for lim in zlim_str.split()]
                    print('got zlim =', zlim)

                while data[i].find(ch_hdr_str) == -1:  # loop until channel info header is found (SIS5 has whitespace)

                    if data[i].find('Phase') > -1:
                        # stop looking for the ch_hdr_str and parsing TX Z in cases where the IMPEDANCE header_str was
                        # repeated after channel data and before the start of PHASE data (odd FKt EM712 example)
                        found_phase_header = True
                        print('Found phase header on line ', i+1, '---> setting found_phase_header True')
                        break

                    if sis_version == 5 and len(data[i].split()) > 0:  # SIS 5 format includes row of slot/board numbers
                        slot_num = len(data[i].split())  # slot_num is slot count in row for SIS 5; slot ID for SIS 4
                        rack_num = 9999  # placeholder for print statements for SIS 5, parsed for SIS 4
                    i += 1

                if found_phase_header:
                    print('Found phase header (step 2) ---> incrementing to next line to restart search for header_str')
                    i += 1
                    break
                # if not found_phase_header:  # try parsing only if there is no indication its phase data!

                print('Trying to parse rack number', rack_num, ' and slot number (SIS4) / slot count (SIS5)', slot_num)
                print('found TX Z channel header=', ch_hdr_str, ' on line i =', i)

                # channel header string is found; start to read channels
                j = 0  # reset line counter while reading channels
                c = 0  # reset channel counter

                z_temp = []
                phase_temp = []
                f_temp = []
                umag_temp = []

                while True:  # found header; start reading individual channels
                    ch_str = data[i+j]
                    print('in channel loop with i =', i, 'j =', j, 'c=', c, 'and ch_str=', ch_str)

                    while c < 36:  # TX Channels should have exactly 36 channels per slot (TX36 board)
                        if len(ch_str.split()) > 0:  # if not just whitespace, check if start of channel data
                            if data[i+j].find(ch_hdr_str) > -1:  # look for Ch: (SIS 4) or Ch (SIS 5) at start of line
                                # parse the string for this channel:
                                # Ch:  0   Z=184.0   (8.7 deg)  OK  at f=31.3 kHz Umag=12.3
                                ch_str = data[i+j]
                                # print('Parsing channel', c, 'with ch_str=', ch_str)
                                ch_str = ch_str.replace('*', '')  # remove '*' (SIS 5 FKt EM124 example)
                                # print('Parsing channel', c, 'with ch_str (after removing *) =', ch_str)

                                if sis_version == 4:  # parse impedance, frequency, Umag, and phase
                                    z_temp.append(float(ch_str[ch_str.find("Z=") + 2:
                                                               ch_str.find("(")].strip().rstrip()))
                                    f_temp.append(float(ch_str[ch_str.find("f=") + 2:
                                                               ch_str.find("kHz")].strip().rstrip()))
                                    umag_temp.append(float(ch_str[ch_str.rfind("=") + 1:].strip().rstrip()))
                                    phase_temp.append(float(ch_str[ch_str.find("(") + 1:
                                                                   ch_str.find("deg")].strip().rstrip()))

                                else:  # SIS 5: each /row includes n_slots of Z data for each channel
                                    # store Z for all boards (e.g., 10 entries in "Ch  1  96.6  93.9 .....  93.0"
                                    print('in SIS 5 parser, ch_str is', ch_str, ' and -1*slot_num=', -1*slot_num)
                                    # in SIS 5 (but not SIS 4), TX Z values > 1000 are logged as, e.g., 1.1k;
                                    # convert 1.1k to 1100 and take last slot_num entries from the channel string

                                    z_temp.append([float(z.replace('k', ''))*1000 if z.find('k') > -1 else
                                                   float(z) for z in ch_str.split()[-1*slot_num:]])
                                    # print('****a')
                                    f_temp.append(freq)  # store nominal frequency from get_freq
                                    # print('****b')
                                    umag_temp.append(np.nan)  # store NaNs until SIS 5 parser is finished
                                    # print('****c')
                                    phase_temp.append(np.nan)  # store NaNs until SIS 5 parser is finished
                                    # print('****d')

                                c += 1  # increment channel channel after parsing

                        j += 1  # increment line counter within channel search

                    else:
                        i = i+j  # reset index to end of channel search
                        # i = i+j-1  # reset index to end of channel search TESTING FOR REVELLE BISTS WITH TIGHT SPACING

                        print('BREAKING CHANNEL LOOP')
                        break

                # reshape the arrays and store
                z_temp = np.array(z_temp)  # SIS 5: keep as array with rows = channels and columns = boards parsed

                print('shape of z_temp = ', np.shape(z_temp))

                if sis_version == 4:  # SIS 4: reshape into rows = channels for single board parsed so far
                    z_temp = z_temp.reshape(len(z_temp), 1)

                f_temp = np.array(f_temp).reshape(len(f_temp), 1)
                umag_temp = np.array(umag_temp).reshape(len(umag_temp), 1)
                phase_temp = np.array(phase_temp).reshape(len(phase_temp), 1)

                if found_channels is False:  # initiate storage (unknown number of channels until now)
                    ztx = z_temp
                    ftx = f_temp
                    utx = umag_temp
                    ptx = phase_temp
                    found_channels = True

                else:  # concatenate new z_temp onto ztx array
                    ztx = np.concatenate((ztx, z_temp), axis=1)
                    ftx = np.concatenate((ftx, f_temp), axis=1)
                    utx = np.concatenate((utx, umag_temp), axis=1)
                    ptx = np.concatenate((ptx, phase_temp), axis=1)
                    continue

            else:
                i += 1  # increment to next line if TX Z not found
                continue

        if found_channels is True:
            # set up output dict for impedance data
            z['filename'] = fname
            z['tx'] = ztx
            z['frequency'] = ftx
            z['umag'] = utx
            z['phase'] = ptx
            z['tx_limits'] = zlim

            print('shape of ztx =', np.shape(ztx))

            return z

        else:
            print('No Z TX data found in file', fname)
            return []

    except ValueError:
        print('***WARNING: Error parsing TX Z in', fname)

    return []


def get_tx_z_limits(model):
    # return the factory limits for TX Z based on model (string of EM model number) if not parsed from BIST
    zlim_factory = {'122': [50, 110],
                    '302': [75, 115],
                    '710': [40, 90],
                    '124': [50, 150],
                    '304': [50, 150],
                    '712': [35, 140]}

    if model in zlim_factory:
        return zlim_factory[model]
    else:
        return [60, 120]


# plot TX Channels impedance from Z dict
def plot_tx_z(z, save_figs=True, plot_style=int(1), output_dir=os.getcwd()):
    fig_list = []  # list of figure names successfully created

    for i in range(len(z['filename'])):
        fname_str = z['filename'][i]
        fname_str = fname_str[fname_str.rfind("/") + 1:-4]
        print('Plotting', fname_str)
        try:  # try plotting
            # set min and max Z limits for model
            if z['tx_limits'][i]:
                [zmin, zmax] = z['tx_limits'][i]
                print('got tx z limits parsed from file: ', zmin, zmax)
            else:
                [zmin, zmax] = get_tx_z_limits(z['model'][i])

            # get number of TX channels and slots for setting up axis ticks
            n_tx_chans = np.size(z['tx'][i], 0)
            n_tx_slots = np.size(z['tx'][i], 1)
            print('in plot_tx_z, got n_tx_chans =', n_tx_chans, 'and n_tx_slots =', n_tx_slots)
            grid_cmap = 'rainbow'  # colormap for grid plot'; also tried 'gist_rainbow_r' and 'jet' to match MAC plots

            if plot_style == 1:  # single grid plot oriented vertically
                # set x ticks and labels on bottom of subplots to match previous MAC figures
                plt.rcParams['xtick.bottom'] = plt.rcParams['xtick.labelbottom'] = True
                plt.rcParams['xtick.top'] = plt.rcParams['xtick.labeltop'] = False

                fig, ax = plt.subplots(nrows=1, ncols=1)  # create new figure
                im = ax.imshow(z['tx'][i], cmap=grid_cmap, vmin=zmin, vmax=zmax)
                cbar = fig.colorbar(im, orientation='vertical')
                cbar.set_label(r'Impedance ($\Omega$, f=' + str(z['frequency'][i][0, 0]) + ' kHz)', fontsize=16)

                # set ticks and labels (following modified from stackoverflow)
                dy_tick = 5
                # dx_tick = 4
                dx_tick = [2, 4][n_tx_slots >= 12]  # x tick = 2 if <12 slots (e.g., 2022 AUS Antarctic EM712 w/ SIS 4)
                ax.set_yticks(np.arange(0, n_tx_chans + dy_tick - 1, dy_tick))  # set major axes ticks
                # ax.set_xticks(np.concatenate((np.array([0]),
                #                               np.arange(3, n_tx_slots + dx_tick - 1, dx_tick))))
                ax.set_xticks(np.concatenate((np.array([0]),
                                              np.arange(dx_tick-1, n_tx_slots + dx_tick - 1, dx_tick))))

                ax.set_yticklabels(np.arange(0, 40, 5), fontsize=16)  # set major axes labels
                # ax.set_xticklabels(np.concatenate((np.array([1]), np.arange(4, n_tx_slots+4, 4))), fontsize=16)
                ax.set_xticklabels(np.concatenate((np.array([1]), np.arange(dx_tick, n_tx_slots+dx_tick, dx_tick))),
                                   fontsize=16)

                ax.set_yticks(np.arange(-0.5, (n_tx_chans + 0.5), 1), minor=True)  # set minor axes for gridlines
                ax.set_xticks(np.arange(-0.5, (n_tx_slots + 0.5), 1), minor=True)
                ax.grid(which='minor', color='k', linewidth=2)  # set minor gridlines
                ax.set_xlabel('TX Slot (index starts at 1)', fontsize=16)
                ax.set_ylabel('TX Channel (index starts at 0)', fontsize=16)

                # set the super title
                title_str = 'TX Channels BIST\n' + 'EM' + z['model'][i] + ' (S/N ' + z['sn'][i] + ')\n' + fname_str
                t1 = fig.suptitle(title_str, fontsize=20)
                fig.set_size_inches(10, 12)

            elif plot_style == 2:  # two subplots, line plot on top, grid plot on bottom, matches MAC reports
                # set x ticks and labels on top of subplots to match previous MAC figures
                plt.rcParams['xtick.bottom'] = plt.rcParams['xtick.labelbottom'] = False
                plt.rcParams['xtick.top'] = plt.rcParams['xtick.labeltop'] = True
                ztx = np.transpose(z['tx'][i])  # store transpose of current Z TX data for plotting horizontally
                axfsize = 20  # uniform axis font size
                subplot_height_ratio = 1.5  # top plot will be 1/Nth of total figure height
                fig = plt.figure()
                fig.set_size_inches(11, 16)  # previous MAC plots height/width ratio is 1.25
                gs = gridspec.GridSpec(2, 1, height_ratios=[1, subplot_height_ratio])
                                       # width_ratios=[1])  # set grid for subplots

                # top plot: line plot for each slot across all channels, different color for each slot
                ax1 = plt.subplot(gs[0])
                ztx_channel = np.tile(np.arange(0, n_tx_chans), [n_tx_slots, 1])  # array of ZTX chan nums for plot
                ax1.plot(ztx_channel.transpose(), ztx.transpose())  # plot each row by using transpose

                ax1.set_xlim(-0.5, n_tx_chans-0.5)
                ax1.set_ylim(zmin, zmax)
                ax1.set(aspect='auto', adjustable='box')

                # bottom plot: grid plot
                ax2 = plt.subplot(gs[1])
                im = ax2.imshow(ztx, cmap=grid_cmap, vmin=zmin, vmax=zmax)
                ax2.set_aspect('equal')
                plt.gca().invert_yaxis()  # invert y axis to match previous plots by Paul Johnson

                # set axis ticks for each subplot directly (line plot and grid are handled slightly differently)
                dx_tick = 5
                # dy_tick = 4
                dy_tick = [2, 4][n_tx_slots >= 12]  # y tick = 2 if <12 slots (e.g., 2022 AUS Antarctic EM712 w/ SIS 4)

                # set major axes ticks for labels
                ax1.set_xticks(np.arange(0, n_tx_chans + dx_tick - 1, dx_tick))
                ax1.set_yticks(np.arange(zmin, zmax+1, 10))
                ax2.set_xticks(np.arange(0, n_tx_chans + dx_tick - 1, dx_tick))
                # ax2.set_yticks(np.concatenate((np.array([0]), np.arange(3, n_tx_slots + dy_tick - 1, dy_tick))))
                ax2.set_yticks(np.concatenate((np.array([0]), np.arange(dy_tick-1, n_tx_slots + dy_tick - 1, dy_tick))))

                # set minor axes ticks for gridlines
                ax1.set_xticks(np.arange(0, (n_tx_chans+1), 5), minor=True)
                ax1.set_yticks(np.arange(zmin, zmax+1, 5), minor=True)
                ax2.set_xticks(np.arange(-0.5, (n_tx_chans+0.5), 1), minor=True)
                ax2.set_yticks(np.arange(-0.5, (n_tx_slots+0.5), 1), minor=True)

                # set axis tick labels
                ax1.set_xticklabels(np.arange(0, 40, 5), fontsize=axfsize)
                ax1.set_yticklabels(np.arange(zmin, zmax+1, 10), fontsize=axfsize)  # TX impedance
                ax2.set_xticklabels(np.arange(0, 40, 5), fontsize=axfsize)
                # ax2.set_yticklabels(np.concatenate((np.array([1]), np.arange(4, 28, 4))), fontsize=axfsize)  # TX slot
                # ax2.set_yticklabels(np.concatenate((np.array([1]), np.arange(4, n_tx_slots+4, 4))), fontsize=axfsize)  # TX slot
                ax2.set_yticklabels(np.concatenate((np.array([1]), np.arange(dy_tick, n_tx_slots+dy_tick, dy_tick))),
                                    fontsize=axfsize)  # TX slot

                # set grid on minor axes
                ax1.grid(which='minor', color='k', linewidth=1)  # set minor gridlines
                ax2.grid(which='minor', color='k', linewidth=1)  # set minor gridlines

                # set axis labels
                ax1.set_xlabel('TX Channel (index starts at 0)', fontsize=axfsize)
                ax1.set_ylabel(r'Impedance ($\Omega$, f=' + str(z['frequency'][i][0, 0]) + ' kHz)', fontsize=axfsize)
                ax1.xaxis.set_label_position('top')
                ax2.set_ylabel('TX Slot (index starts at 1)', fontsize=axfsize)
                ax2.set_xlabel('TX Channel (index starts at 0)', fontsize=axfsize)
                ax2.xaxis.set_label_position('top')

                # add colorbar
                cbar = fig.colorbar(im, orientation='horizontal', fraction=0.05, pad=0.05)
                cbar.set_label(r'Impedance ($\Omega$, f=' + str(z['frequency'][i][0, 0]) + ' kHz)', fontsize=16)


                # set the super title
                title_str = 'TX Channels BIST\n' + 'EM' + z['model'][i] + ' (S/N ' + z['sn'][i] + ')\n' + fname_str
                t1 = fig.suptitle(title_str, fontsize=20)
                fig.tight_layout()
                fig.subplots_adjust(top=0.87)

            # save the figure
            if save_figs is True:
                # fig = plt.gcf()
                # fig.set_size_inches(10, 10)
                fig_name = 'TX_Z_EM' + z['model'][i] + '_SN_' + z['sn'][i] + '_from_text_file_' + fname_str +\
                           '_v' + str(plot_style) + '.png'
                # print('output_dir=', output_dir)
                # print('fig_name=', fig_name)
                # fig.savefig(fig_name, dpi=100)
                fig.savefig(os.path.join(output_dir, fig_name), dpi=100,
                            # bbox_extra_artists=t1,
                            bbox_inches='tight')  # include title and cbar in bbox

            plt.close()

            fig_list.append(fig_name)

        except ValueError:  # move on if error
            print("***WARNING: Error plotting ", z['filename'][i])

    return fig_list


def plot_tx_z_history(z, save_figs=True, output_dir=os.getcwd()):
    # plot lines of all zrx values colored by year to match historic Multibeam Advisory Committee plots
    fig_name = []
    # set x ticks and labels on bottom of subplots to match previous MAC figures
    plt.rcParams['xtick.bottom'] = plt.rcParams['xtick.labelbottom'] = True
    plt.rcParams['xtick.top'] = plt.rcParams['xtick.labeltop'] = False

    # print('in plot_tx_z_history, z=', z)

    # get model, sn, time span
    model = z['model'][0]  # reassign model and sn in case last BIST parse failed
    sn = z['sn'][0]
    dates = [d for d in z['date'] if d]  # get dates parsed successfully (empty list if not)
    # times = [t for t in z['time'] if t]  # get times parsed successfully (empty list if not)

    if not dates:  # return if no dates
        print('empty date list in plot_tx_history')
        return()

    yrmin = int(min(dates)[:4])
    yrmax = int(max(dates)[:4])
    yrs = [str(yr) for yr in range(yrmin, yrmax + 1)]

    # get number of TX channels and slots for setting up axis ticks
    n_tx_chans = np.size(z['tx'][0], 0)
    n_tx_slots = np.size(z['tx'][0], 1)
    n_tx_modules = n_tx_chans*n_tx_slots
    print('found n_tx_chans =', n_tx_chans, 'and n_tx_slots=', n_tx_slots)

    colors = plt.cm.rainbow(np.linspace(0, 1, len(yrs)))  # set up line colors over number of years
    ztx_channel = np.arange(n_tx_chans)  # range of TX channels for plotting (starts at 0)
    ztx_module = np.arange(1, n_tx_modules+1)  # range of RX modules for plotting (unlike channels, this starts at 1)

    print('len ztx_module = ', len(ztx_module))

    # set axis and label parameters
    axfsize = 16  # axis font size
    # dx_tick = 36
    # if n_tx_slots > 36:
    dx_tick = max([36, 36*np.floor(n_tx_slots/20)])  # try to reduce crowded labels for 0.5 deg systems w/ 40+ cards
    dy_tick = 10

    print('set of models is: ', set(z['model']))
    print('set of sns is: ', set(z['sn']))

    if z['tx_limits'][0]:  # check whether limits were parsed
        [zmin, zmax] = z['tx_limits'][0]
        print('got tx z limits parsed from file: ', zmin, zmax)
    else:
        [zmin, zmax] = get_tx_z_limits(model)

    freq = get_freq(z['model'][0]).split()[0]
    print('found model = ', z['model'][0], 'and freq=', freq)

    ztx_limits = [zmin, zmax]
    print('z[date]=', z['date'])
    print('z[time]=', z['time'])

    # find index of most recent BIST for plotting
    bist_time_idx = [i for i in range(len(z['filename'])) if z['date'][i] and z['time'][i]]  # get idx of files w/ times
    print('bist_time_idx=', bist_time_idx)
    bist_time_str = [z['date'][i] + z['time'][i] for i in bist_time_idx]
    # bist_time_str = [z['date'][d] + z['time'][d] for d in range(len(z['date'])) if z['date'][d] and z['time'][d]]
    print('attempting to convert time strings: ', [t.replace('/', '').replace(':', '') for t in bist_time_str])

    bist_time_obj = [datetime.datetime.strptime(t.replace('/', '').replace(':', ''), '%Y%m%d%H%M%S.%f')
                     for t in bist_time_str]

    if bist_time_obj:
        idx_last = np.argmax(bist_time_obj)  # index of most recent file with date/time; files w/o will not be plotted
        bist_count = 0
        print('found idx_last = ', idx_last)
    else:
        print('empty time list, cannot determine last BIST in plot_tx_z_history')
        return()

    # make figure with two subplots
    fig = plt.figure()
    # fig.set_size_inches(11, 16)  # previous MAC plots height/width ratio is 1.25
    ax1 = fig.add_subplot(1, 1, 1)
    # ax2 = fig.add_subplot(2, 1, 2)
    plt.subplots_adjust(top=0.85)  # try to keep long supertitle from overlapping

    # make list of line artists, reset for each frequency
    legend_labels = []
    legend_artists = []

    for y in range(len(yrs)):
        print('**** year y =', str(y))
        # for i in range(len(z['date'])):
        for i in bist_time_idx:
            print('i=', str(i), ' --> ', bist_time_obj[i])
            if z['date'][i][:4] == yrs[y]:  # check if this BIST matches current year
                print('year matches (', str(y), ')')
                ztx = np.asarray(z['tx'][i])  # n_cols = n_chans, n_rows = n_slots

                print('---> ztx has size', np.size(ztx))

                if i == bist_time_idx[idx_last]:  # store for final plotting in black if this is most recent data
                    ztx_last = ztx

                # skip if not 36 TX channels (parser err? verify this is the case for all TX xdcr cases)
                if ztx.shape[0] == n_tx_chans:
                    # plot zrx_array history in top subplot, store artist for legend
                    # files with more than one test flatten to N times n_tx_modules in length; plot first test only
                    print('ztx.flatten has size', ztx.flatten().size)
                    # print('n_tx_modules = ', n_tx_modules)
                    line, = ax1.plot(ztx_module, ztx.flatten('C')[0:n_tx_modules], color=colors[y], linewidth=2)
                    # add legend artist (line) and label (year) if not already added
                    if yrs[y] not in set(legend_labels):
                        legend_labels.append(yrs[y])  # store year as label for legend
                        legend_artists.append(line)

                    # print('ztx_limits=', ztx_limits)
                    # print('zrx_array_limits=', zrx_array_limits)

                    # define x ticks starting at 1 and running through n_rx_modules, with ticks at dx_tick
                    print('dx_tick =', dx_tick)
                    print('n_tx_modules =', n_tx_modules)
                    x_ticks = np.concatenate((np.array([1]), np.arange(dx_tick, n_tx_modules + dx_tick - 1, dx_tick)))
                    y_ticks = np.arange(ztx_limits[0], ztx_limits[1] + 1, dy_tick)

                    # set ylim to parsed spec limits
                    ax1.set_ylim(ztx_limits)

                    # set yticks for labels and minor gridlines
                    ax1.set_yticks(y_ticks)
                    ax1.set_yticks(y_ticks, minor=True)
                    ax1.set_ylabel('Transmitter Impedance (ohms)\n(axis limits = Kongsberg spec.)',
                                   fontsize=axfsize)

                    for ax in [ax1]:  # set xlim and aspect for both axes
                        ax.set_xlim(0, n_tx_modules+1)
                        ax.set(aspect='auto', adjustable='box')
                        ax.set_xlabel('TX Module (index starts at 1)', fontsize=axfsize)
                        ax.set_xticks(x_ticks)
                        ax.set_xticks(x_ticks, minor=True)
                        ax.grid(which='minor', color='k', linewidth=1)
                        ax.tick_params(labelsize=axfsize)
                        ax.xaxis.set_label_position('bottom')

                    bist_count = bist_count+1
                    # print('FINISHED PLOTTING THIS BIST')

                else:
                    print('Skipping ', z['filename'], ' with ', str(ztx.shape[1]), ' RX and ',
                          str(ztx_array.shape[1]), ' channels instead of 32!')

    if bist_count > 0:
        line, = ax1.plot(ztx_module, ztx_last.flatten('C'), color='k', linewidth=2)
        # line, = ax2.plot(zrx_module, zrx_array_last.flatten(), color='k', linewidth=2)

    legend_artists.append(line)  # add line artist to legend list
    legend_labels.append('Last')

    # set legend
    l1 = ax1.legend(legend_artists, legend_labels,
                    bbox_to_anchor=(1.2, 1), borderaxespad=0,
                    loc='upper right', fontsize=axfsize)

    if yrmin == yrmax:
        years_str = 'Year: ' + str(yrmin)
    else:
        years_str = 'Years: ' + str(yrmin) + '-' + str(yrmax)

    # set the super title
    title_str = 'TX Channels BIST\n' + 'EM' + model + ' (S/N ' + sn + ')\n' + \
                years_str + ' (' + str(bist_count) + ' BIST' + ('s' if bist_count > 1 else '') + ')\n' + \
                'Frequency: ' + freq + ' kHz'
                # 'Frequency: '+z['freq_range'][i][f]+' kHz'
    t1 = fig.suptitle(title_str, fontsize=20)
    fig.set_size_inches(16, 10)

    # save the figure
    if save_figs is True:
        # fig = plt.gcf()
        # fig.set_size_inches(10, 10)
        fig_name = 'TX_Z_EM' + model + '_SN_' + sn + '_history_' + str(yrmin) + '-' + str(yrmax) + \
                   '_freq_' + freq + '_kHz' + '.png'
                   # '_freq_'+z['freq_range'][i][f]+'_kHz'+'.png'
        print('Saving', fig_name)
        # fig.savefig(fig_name, dpi=100)
        fig.savefig(os.path.join(output_dir, fig_name), dpi=100,
                    bbox_extra_artists=(t1, l1), bbox_inches='tight')  # add bbox extra artists to avoid cutoff

    plt.close()

    return fig_name


# parse RX Noise BIST data from telnet log text file
def parse_rx_noise(fname, sis_version=int(4)):
    print('***starting parse_rx_noise with sis_version =', sis_version)
    sys_info = check_system_info(fname)
    print('got sys_info =', sys_info)

    # set up output dict for impedance data
    rxn = init_bist_dict(3)
    rxn['filename'] = fname
    n_test = 0  # keep track of number of RX Noise tests in this file
    get_speed = False  # do not parse speed until RX Noise header is found (avoid other speeds in SIS 5 file)

    print('1')

    try:  # try reading file
        f = open(fname, "r")
        data = f.readlines()

    except ValueError:
        print('***WARNING: Error reading file', fname)

    print('2')

    if len(data) <= 0:  # skip if text file is empty
        print('***WARNING: No data read from file', fname)
        # return ()
        return []
    
    # Check to make sure its not a PU Params or System Report text file (SIS 4)
    if any(substr in data[0] for substr in ["Database", "Datagram", "CPU"]):
        print("***WARNING: Skipping non-BIST file: ", fname)
        # return()
        return []

    print('3')

    # try parsing the data for all tests in text file
    print('trying to parse RX noise with sis_version = ', sis_version)
    try:
        header_str = "RX NOISE LEVEL"  # start of SIS 4 RX Noise test
        ch_hdr_str = "Board No:"  # start of SIS 4 channel data
        footer_str = "Maximum"  # end of SIS 4 RX Noise test

        # SIS 5 format applies also to some EM2040 variants and EM712 logged in SIS 4 (retry w/ sis_version = 5)
        if sis_version is 5 or sys_info['model'] in ['2040', '2045', '2040P']:
            print('trying SIS 5 format in parser')
            # header_str = "RX noise level"  # start of SIS 5 RX Noise test
            # header_str = ['Noise Test.', 'RX noise level'][int(sis_version == 5)]
            # header_str = ['Noise Test.', 'RX noise level'][int(sis_version == 5) and not sis4_retry]
            header_str = 'Noise Test.'  # start of SIS 5 RX Noise test
            ch_hdr_str = "Channel"  # start of SIS 5 channel data
            footer_str = "Summary"  # end of SIS 5 RX Noise test

        speed_str = "Vessel speed:"  # start of SIS 5 speed entry; will not be found in SIS 4

        print('header_str = ', header_str, ' ch_hdr_str =', ch_hdr_str, 'and footer_str = ', footer_str)

        # find the RX Noise values for receiver and transducer; example formats below
        # SIS 4: look for header for RX NOISE samples and loop through entries
        # RX NOISE LEVEL
        # Board No: 1           2            3            4
        # 0:        52.2       43.4       42.2       41.1   dB
        # 1:        48.3       44.6       40.1       44.9   dB

        # SPECIAL SIS 4 FORMAT: (20190509_detailed_report_bists.txt)
        # ---------------RX NOISE LEVEL ------------------------------------
        # |   Board No: 1                                                     |
        # |   0: 64.6 dB      1: 66.2 dB      2: 65.3 dB       3: 65.8 dB     |
        # ...
        # |   Board No: 2                                                     |
        # |   0: 63.0 dB      1: 63.2 dB      2: 63.1 dB       3: 62.5 dB     |
        # ...
        # |                                                                   |
        # | Maximum noise at Board 2 Channel 31 Level: 70.0 dB                |
        # ------------------------------------------------------------------

        # SIS 4: EM2040: follows SIS 5 format below, but look for 'Noise Test.' as the header string

        # SIS 5: EM2040: look for header, similar to SIS 4 but use frequency instead of board number
        # --------------20190529 - 160322 - 9 - Passed - EM2040P_40 - RX - noise - level - ---EM - 2040P.txt - -------------
        # RX noise level - EM2040P
        #
        # Noise Test.
        # Signal Amplitude in dB
        #
        # Channel         200kHz      300kHz      380kHz
        # 0               42.8        41.8        43.2
        # 1               42.2        41.1        43.0

        # SIS 5: EM304: same as EM2040, but single frequency column

        print('4')

        i = 0
        while i < len(data):
            # print('i')
            if data[i].find(header_str) > -1:  # if header is found, start parsing
                get_speed = True
                while data[i].find(ch_hdr_str) == -1:  # loop until channel info header is found (SIS5 has whitespace)
                    i = i+1

                # parse RX data columns header (SIS 4: RX board no. for 1 freq; SIS 5: frequency of RX Noise test)
                rx_col_str = data[i]
                idx_start = re.search(r"\d", rx_col_str)  # find first digit (board no. or freq) and count cols onward
                rx_cols = rx_col_str[idx_start.start():].split()
                n_rx_columns = int(len(rx_cols))

                i += 1  # increment to next line after channel header
                j = 0  # reset line counter while reading channels
                c = 0  # reset channel counter
                rxn_temp = []

                while True:  # start reading individual channels
                    ch_str = data[i+j]
                    if ch_str.find(footer_str) > -1:  # break if end of channel data indicated by footer string
                        n_rx_rows = c  # store total number of channels parsed
                        i = i+j  # reset index to end of channel search
                        # print('found footer', footer_str, ' in ch_str', ch_str, 'at i =', i, ' and j =', j)
                        # print('breaking')
                        break

                    if len(ch_str.split()) > 0:  # if not just whitespace, parse ch. data, convert, append to rxn_temp
                        # print('found ch_str', ch_str)
                        try:
                            ch_str = ch_str.replace('dB', '').replace('*', '')  # remove 'dB' (SIS 4) or '*' (SIS 5)
                            # rxn_temp.append([float(x) for x in ch_str.split()[1:]])  # split, omit first item (ch. no.)
                            # split channel string, convert any items with decimal to float; ch. number will be omitted

                            ch_str_data = [float(x) for x in ch_str.split() if x.find('.') > -1]

                            if ch_str_data:
                                print('appending', ch_str_data)
                                print('with type:', type(ch_str_data))
                                rxn_temp.append(ch_str_data)
                                sis4_special_case = ch_str.count(':') > 1  # special case if > 1 ch numbers w/ : in row
                                # print('SIS4 special case=', sis4_special_case)

                                c += 1  # update channel count
                                # print('channel counter c updated to c=', c)
                            else:
                                print('no channel data parsed from ch_str=', ch_str)

                        except ValueError:
                            print('error parsing ch_str', ch_str, 'at i =', i, 'and j=', j)

                    j += 1  # update line counter

                # reshape the arrays and store for this test; row = channel or module
                # SIS 4: columns = RX board number for most cases
                # SIS 4 special case: boards
                # SIS 5 EM2040: columns = frequency
                if rx_col_str.find("kHz") > -1:  # if found, store column header freq info (add space before 'kHz')
                    print('columns correspond to frequency; keeping n_rx_rows and n_rx_columns as parsed from file')
                    # print('found rx_col_str with kHz=', rx_col_str)
                    # print('prior to extending, rxn[frequency] is', rxn['frequency'])
                    # rxn['frequency'].extend([item.replace('kHz', ' kHz') for item in rx_cols])

                    # TRY APPENDING, NOT EXTENDING --> clarify frequencies parsed for each test if multi-frequency
                    print('rx_cols =', rx_cols)
                    rxn['frequency'].append([item.replace('kHz', ' kHz') for item in rx_cols])
                    # print('after extending, rxn[frequency] is now', rxn['frequency'])

                else:  # columns are not frequency; reshape into 32 channels (rows) and n_rx_columns as necessary
                    print('columns do not correspond to frequency; reassigning n_rx_rows=32 and n_rx_columns=-1')
                    n_rx_rows = 32
                    n_rx_columns = -1

                print('rxn_temp=', rxn_temp)
                print('np.array(rxn_temp)=', np.array(rxn_temp))
                print('trying to reshape with n_rx_rows=', n_rx_rows, 'and n_rx_columns=', n_rx_columns)
                # rxn_temp = np.array(rxn_temp).reshape(n_rx_rows, n_rx_columns)
                rxn_temp = np.asarray(rxn_temp)

                print('sis4_special_case=', sis4_special_case)

                reshape_order = 'C'  # typical reshape order
                if sis4_special_case:  # try transpose of data before reshape to handle multiple channels per row
                    print('SIS4 special format found, taking transpose')
                    rxn_temp = rxn_temp.flatten()
                    # rxn_temp = rxn_temp.transpose()
                    reshape_order = 'F'  # change reshape order for special case of parsing multiple channels per row

                # print('rxn_temp before reshape=', rxn_temp)
                rxn_temp = rxn_temp.reshape((n_rx_rows, n_rx_columns), order=reshape_order)
                # print('survived reshape with rxn_temp=', rxn_temp)
                rxn['rxn'].append(rxn_temp)
                rxn['test'].append(n_test)  # store test number (start with 0)

                n_test = n_test + 1  # update test number (start with 0, used for indexing in plotter)

                # if rx_col_str.find("kHz") > -1:  # if found, store column header freq info (add space before 'kHz')
                #     rxn['frequency'].extend([item.replace('kHz', ' kHz') for item in rx_cols])

            # if SIS 5 speed is found after RX Noise header, parse and store (Vessel speed: 0.00 [knots])
            print('in parse_rx_noise, get_speed = ', get_speed)
            if data[i].find(speed_str) > -1 and get_speed:
                # rxn['speed'] = float(data[i].split()[-2])
                rxn['speed'].append(float(data[i].split()[-2]))  # for SIS 5 with continuous BIST
                rxn['speed_bist'].append(float(data[i].split()[-2]))
                print('appended rxn[speed_bist]', rxn['speed_bist'])
                get_speed = False  # do not parse another speed until after RX noise header is found

            else:
                print('no speed string found OR get_speed is false')

            i += 1

        # when finished parsing, find the mean noise values across all tests for each module
        # dB must be converted to linear, then averaged, then converted back to dB
        # linear = 10^dB/10 and dB = 10*log10(linear)
        # NOTE: this may not be appropriate for mean across rows that include multiple frequency tests
        rxn['rxn_mean'] = 10*np.log10(np.average(np.power(10, np.divide(rxn['rxn'], 10)), axis=0))

        return rxn
         
    except ValueError:  # move on if error
        print("***WARNING: Error parsing ", fname)
        return []


# plot RX Noise versus speed or azimuth
def plot_rx_noise(rxn, save_figs, output_dir=os.getcwd(), sort='ascending', test_type='speed',
                  param=[], param_unit='SOG (kts)', param_adjust=0.0, param_lims=[], cmap='jet'):
    # declare array for plotting all tests with nrows = n_elements and ncols = n_tests
    # np.size returns number of items if all lists are same length (e.g., AutoBIST script in SIS 4), but returns number
    # of lists if they have different lengths (e.g., files from SIS 5 continuous BIST recording)
    # SIS 4 format: shape of rxn[rxn][0] is (10, 32, 4) --> number of tests (10), 32 elements per RX board, 4 boards
    # SIS 5 format: shape of rxn[rxn][0] is (34, 128, 1) --> number of tests (34), 128 elements per test, 1

    # set up dict of param axis ticks for given units
    print('in plot_rx_noise with test_type', test_type, 'param_unit', param_unit,
          'param_adjust', param_adjust, 'and param_lims', param_lims)


    # y_ticks_top = {'SOG (kts)': 2, 'RPM': 20, 'Handle (%)': 10, 'Pitch (%)': 10, 'Pitch (deg)': 10, 'Azimuth (deg)': 45}
    y_ticks_top = {'SOG (kt)': 2,
                   'STW (kt)': 2,
                   'RPM': 20,
                   'Handle (%)': 10,
                   'Pitch (%)': 10,
                   'Pitch (deg)': 10,
                   'Azimuth (deg)': 45}

    # set x ticks and labels on bottom of subplots to match previous MAC figures
    plt.rcParams['xtick.bottom'] = plt.rcParams['xtick.labelbottom'] = True
    plt.rcParams['xtick.top'] = plt.rcParams['xtick.labeltop'] = False

    n_elements = np.size(rxn['rxn'][0][0])  # number of elements in first test, regardless of SIS version

    print('rxn[test]=', rxn['test'])

    n_tests = np.size(np.hstack(rxn['test']))  # handle uneven list lengths, e.g., SIS 5 continuous BISTs

    # sort the data by param (i.e., sorted params = [rxn['speed'][x] for x in s])
    test_all = np.arange(0.0, n_tests, 1.0)
    print('test_all=', test_all, 'with len=', np.size(test_all))

    # print('********* IN PLOTTER with sort_by=', sort_by, 'and param=', param)
    print('n_elements =', n_elements, 'and n_tests=', n_tests)

    if param != []:  # use custom parameters if given
    # if any(param):  # use custom param axis if given (e.g., to override params parsed from filenames or data)
        param_all = np.asarray(param)
        print('using custom param_all=', param_all)

    elif test_type == 'speed':
        print('test type = speed --> getting param_all from hstacked rxn[speed_bist]')
        param_all = np.array(np.hstack(rxn['speed_bist']))
        print('rxn[speed_bist] = ', rxn['speed_bist'])

    elif test_type == 'azimuth':
        print('test type = azimuth --> getting param_all from hstacked rxn[azimuth_bist]')
        param_all = np.array(np.hstack(rxn['azimuth_bist']))

    else:  # test_type == 'standalone':
        param_all = np.arange(0.0, n_tests, 1.0)  # set param_all to simple test number
        print('test type = standalone (or unknown) --> setting param_all equal to 1:n_tests')

    # else:
    #     print('in RX noise plotter, no parameters provided and unknown test type')

    print('using param_all parsed from files (before any adjustment) =', param_all)

    #
    # else:  # otherwise, use param parsed from filename for each BIST
    #     if test_type == 'speed':
    #         print('test type = speed --> getting param_all from hstacked rxn[speed_bist]')
    #         param_all = np.array(np.hstack(rxn['speed_bist']))
    #
    #     elif test_type == 'azimuth':
    #         print('test type = azimuth --> getting param_all from hstacked rxn[azimuth_bist]')
    #         param_all = np.array(np.hstack(rxn['azimuth_bist']))
    #
    #     elif test_type == 'standalone':
    #         param_all = np.arange(0.0, n_tests, 1.0)  # set param_all effective
    #         print('unknown test_type=', test_type, 'in plot_rx_noise')
    #
    #     print('using param_all parsed from files=', param_all)

    # adjust test parameter
    param_all = np.add(param_all, np.full(np.shape(param_all), param_adjust))
    print('param_all after adjustment is ', param_all)

    # sort by test parameter if appropriate
    s = np.arange(len(param_all))  # default sort order as provided in rxn
    print('default sort order = s = ', s)

    # if sort:
    if sort in ['ascending', 'descending']:
        print('getting sort order for param_all')
        s = np.argsort(param_all, kind='mergesort')  # use mergesort to avoid random/unrepeatable order for same values
        print('got ascending sort order s =', s)

        # if sort == 'descending':
        #     s = s[::-1]
        #     print('got descending sort order =', s)

    if sort in ['descending', 'reverse']:  # 'reverse' will plot in reverse parsing order, e.g., chronological in SIS 5
        s = s[::-1]
        print('got descending sort order =', s)

    if sort is 'reverse':
        print('the fields of rxn are ', rxn.keys())
        print('rxn date is ', rxn['date'])
        print('rxn time is ', rxn['time'])


    print('after any sorting, s =', s)
    print('before applying sort order, param_all =', param_all)
    param_all = param_all[s]  # sort the speeds
    print('after sorting param_all, param_all =', param_all)

    # organize RX Noise tests from all parsed files and params into one array for plotting, sorted by param
    n_rxn = len(rxn['rxn'])  # number of parsing sessions stored in dict (i.e., num files)
    print('*** len(rxn[rxn]) = ', n_rxn)

    rxn_all = np.empty([n_elements, 1])
    for i in range(n_rxn):  # loop through each parsed set and organize RX noise data into rxn_all for plotting
        print('i=', i)
        n_tests_local = np.size(rxn['rxn'][i], axis=0)  # number of tests in this parsing session
        print('i=', i, 'with n_tests_local = ', n_tests_local)
        for j in range(n_tests_local):  # reshape data from each test (SIS 4 is 32 x 4, SIS 5 is 128 x 1) into 128 x 1
            print('j = ', j)
            rxn_local = np.reshape(np.transpose(rxn['rxn'][i][j]), [n_elements, -1])
            rxn_all = np.hstack((rxn_all, rxn_local))  # stack horizontally, column = test number

    # after stacking, remove first empty column and then sort columns by param
    print('shape rxn_all=', rxn_all.shape)
    print('rxn_all =', rxn_all)
    rxn_all = rxn_all[:, 1:]
    print('after removing first column, rxn_all =', rxn_all)
    rxn_all = rxn_all[:, s]

    # plot the RX Noise data organized for imshow; this will have test num xlabel
    plt.close('all')
    axfsize = 16  # uniform axis font size
    subplot_height_ratio = 4  # top plot will be 1/Nth of total figure height

    fig = plt.figure(figsize=(7, 12))  # set figure size with defined grid for subplots
    gs = gridspec.GridSpec(2, 1, height_ratios=[1, subplot_height_ratio])  # set grid for subplots with fixed ratios

    # plot speed vs test number
    ax1 = plt.subplot(gs[0])
    ax1.plot(test_all, param_all, 'r*')
    ax1.set_xlabel('Test Number', fontsize=axfsize)
    # ax1.set_ylabel('SOG (kts)', fontsize=axfsize)

    if test_type == 'azimuth':
        param_unit.replace('(deg)', '(deg, 0 into seas)')

    ax1.set_ylabel(param_unit, fontsize=axfsize)

    # plot rxn vs test number
    ax2 = plt.subplot(gs[1])
    im = ax2.imshow(rxn_all, cmap=cmap, aspect='auto', vmin=30, vmax=70, )
    # im = ax2.imshow(rxn_all, cmap=cmap, aspect='auto', vmin=30, vmax=80, )

    plt.gca().invert_yaxis()  # invert y axis to match previous plots by Paul Johnson
    ax2.set_xlabel('Test Number', fontsize=axfsize)
    ax2.set_ylabel('RX Module (index starts at 0)', fontsize=axfsize)

    # set colorbar
    cbar = fig.colorbar(im, shrink=0.7, orientation='horizontal')
    cbar.set_label(r'RX Noise (dB re 1 $\mu$Pa/$\sqrt{Hz}$)', fontsize=axfsize)
    cbar.ax.tick_params(labelsize=14)

    # set x ticks for both plots based on test count - x ticks start at 0, x labels (test num) start at 1
    x_test_max = np.size(test_all)
    print('***size of test_all is', np.size(test_all))
    x_test_max_count = 10  # max number of ticks on x axis
    x_ticks_round_to = 10  # round ticks to nearest ___
    if n_tests < x_ticks_round_to:
        dx_test = 1
    else:
        dx_test = int(math.ceil(n_tests / x_test_max_count / x_ticks_round_to) * x_ticks_round_to)

    print('using dx_test = ', dx_test)
    x_test = np.concatenate((np.array([0]), np.arange(dx_test - 1, x_test_max, dx_test)))
    x_test_labels = np.concatenate((np.array([1]), np.arange(dx_test, x_test_max, dx_test), np.array([x_test_max])))

    # set ticks, labels, and limits for speed plot
    dy_ticks_top = y_ticks_top[param_unit]  # get dy_tick from input units
    print('dy_ticks_top=', dy_ticks_top)
    print('param_all=', param_all)
    print('max(param_all)=', max(param_all))
    print('param_lims =', param_lims)

    print('***checking param_lims (provided as', param_lims, ')')
    y_param_min = param_lims[0] if param_lims else 0.0
    y_param_max = param_lims[1] if param_lims else max(param_all)

    print('y_param_min, max =', y_param_min, y_param_max)

    # y_ticks_top_max = np.int(max(param_all) + dy_ticks_top / 2)  # max speed + dy_tick/2 for space on plot
    # y_ticks_top = np.concatenate((np.array([0]),
    #                               np.arange(dy_ticks_top, y_ticks_top_max + dy_ticks_top - 1, dy_ticks_top)))
    # y_ticks_top_max = np.int(y_param_max + dy_ticks_top / 2)  # max speed + dy_tick/2 for space on plot
    y_ticks_top_max = int(np.ceil(y_param_max))
    # y_ticks_top_min = np.int(y_param_min + dy_ticks_top / 2) if param_lims else int(0)
    y_ticks_top_min = int(np.floor(y_param_min))


    print('got y_ticks_top_min and max are ', y_ticks_top_min, y_ticks_top_max)

    # y_ticks_top = np.concatenate((np.array([y_ticks_top_min]),
    #                               np.arange(dy_ticks_top,
    #                                         y_ticks_top_max + dy_ticks_top - 1,
    #                                         dy_ticks_top)))

    y_ticks_top = np.concatenate((np.array([y_ticks_top_min]),
                                  np.arange(y_ticks_top_min + dy_ticks_top,
                                            y_ticks_top_max + dy_ticks_top - 1,
                                            dy_ticks_top)))

    print('got y_ticks_top =', y_ticks_top)

    y_ticks_top_labels = [str(y) for y in y_ticks_top.tolist()]

    ax1.set_xlim(-0.5, x_test_max - 0.5)  # set xlim to align points with rxn data columns
    # ax1.set_ylim(-0.5, y_ticks_top_max + 0.5)  # set ylim to show entire range consistently
    ax1.set_ylim(y_ticks_top_min - 0.5, y_ticks_top_max + 0.5)  # set ylim to show entire range consistently

    ax1.set_yticks(y_ticks_top)
    ax1.set_xticks(x_test)
    ax1.set_yticklabels(y_ticks_top_labels, fontsize=16)
    ax1.set_xticklabels(x_test_labels, fontsize=16)
    ax1.grid(True, which='major', axis='both', linewidth=1, color='k', linestyle='--')

    # set ticks, labels, and limits for noise plot
    y_module_max = np.size(rxn_all, 0)
    dy_module = 16  # max modules = multiple of 32, dx_tick is same across two subplots
    y_module = np.concatenate((np.array([0]), np.arange(dy_module - 1, y_module_max + dy_module - 1, dy_module)))
    y_module_labels = [str(y) for y in y_module.tolist()]
    ax2.set_yticks(y_module)
    ax2.set_xticks(x_test)
    ax2.set_yticklabels(y_module_labels, fontsize=16)
    ax2.set_xticklabels(x_test_labels, fontsize=16)
    ax2.grid(True, which='major', axis='both', linewidth=1, color='k', linestyle='--')

    # set the super title
    print('sorting out the date string from rxn[date]=', rxn['date'])
    print('rxn[date][0] = ', rxn['date'][0])

    print('rxn[frequency][0][0] =', rxn['frequency'][0][0])
    # freq_str = ''.join()

    # date_str = rxn['date'][0].replace('/', '-')  # format date string

    try:
        date_str = rxn['date'][0].replace('/', '')  # format date string in case '/' included from parser
        date_str = '-'.join([date_str[0:4], date_str[4:6], date_str[6:]])

    except:
        date_str = 'YYYY-MM-DD'

    title_str = 'RX Noise vs. ' + test_type.capitalize() + '\n' + \
                'EM' + rxn['model'][0] + ' (S/N ' + rxn['sn'][0] + ')\n' + \
                'Date: ' + date_str + '\n' + \
                'Freq: ' + rxn['frequency'][0][0]
    fig.suptitle(title_str, fontsize=16)

    # save the figure
    if save_figs is True:
        fig = plt.gcf()
        #        fig.set_size_inches(10, 10) # do not change RX Noise figure size before saving
        freq_str = rxn['frequency'][0][0].replace(' ', '_')
        param_str = ''
        if test_type in ['speed', 'azimuth']:  # format parameter strings for file name
            if param_unit.find('(') > -1 and param_unit.find(')') > -1:  # units included between parentheses
                param_unit_str = param_unit.replace('(', ')').split(')')[1].replace('%', 'pct')
                print('original param_unit_str = ', param_unit_str)
                param_unit_str = param_unit.replace('(', '').replace(')', '').replace('%', 'pct').split()[::-1]
                param_unit_str = '_'.join([s.lower() for s in param_unit_str])
                print('new param_unit_str = ', param_unit_str)

            else:
                param_unit_str = param_unit.strip().replace(' ', '_')  # no (), keep base unit name

            print('sort is ', sort)

            param_str = '_' + str(np.min(param_all)).replace('.', 'p') + \
                        ('-' + str(np.max(param_all)).replace('.', 'p') if np.size(np.unique(param_all)) > 1 else '') +\
                        '_' + param_unit_str + '_' + sort
                        # (param_unit if test_type == 'speed' else '_deg')

        fig_name = 'RX_noise_vs_' + test_type + '_EM' + rxn['model'][0] + \
                   '_SN_' + rxn['sn'][0] + "_" + date_str.replace('-', '') + \
                   "_" + freq_str + param_str + '_' + cmap + ".png"
        print('Saving', fig_name)
        fig.savefig(os.path.join(output_dir, fig_name), dpi=100)

    plt.close('all')


# return operational frequency range for EM model; update these frequency ranges as appropriate
def get_freq(model):
    print('in get_freq, model=', model)
    model = model.replace('EM','').strip()  # reformat down to just model number
    if model.find('710') > -1:
        freq = '70-100 kHz'
    elif any(variant in model for variant in ['712', '714']):
        freq = '40-100 kHz'
    elif model.find('2040') > -1:  # EM2040 and all variants
        freq = '200-400 kHz'
    elif model.find('304') > -1:
        freq = '26-34 kHz'
    else:
        freq = model[0:2] + ' kHz'  # otherwise, EM302 --> 30 kHz and EM122/124 --> 12 kHz

    print('leaving get_freq with freq =', freq)

    return freq


def init_bist_dict(bist_test_type):
    std_key_list = ['filename', 'model', 'sn', 'date', 'time', 'sis_version', 'frequency', 'ship_name', 'cruise_name']
    bist = {k: [] for k in std_key_list}  # initialize dict with standard info

    if bist_test_type == 1:  # TX Channels
        new_key_list = ['tx', 'umag', 'phase', 'tx_limits']

    elif bist_test_type == 2:  # RX Channels
        new_key_list = ['rx', 'rx_array', 'rx_temp',
                        'rx_limits', 'rx_array_limits', 'rx_temp_limits',
                        'freq_range', 'rx_units', 'rx_array_units',
                        'test', 'test_datetime', 'test_temp', 'test_datetime_temp']

    elif bist_test_type == 3:  # RX Noise
        new_key_list = ['rxn', 'rxn_mean', 'speed', 'hdg_true', 'azimuth', 'azimuth_bist', 'test', 'speed_bist']

    # elif bist == 4:  # RX Spectrum  PARSER NOT WRITTEN YET
    #     new_key_list = []

    bist.update({k: [] for k in new_key_list})  # update dict with keys specific to BIST type

    return bist


# append one dict to another (typically values parsed from one BIST to a dict for all BISTs)
def appendDict(d1,d2):
    for k, v in d2.items():
        d1[k].append(v)

    return d1


def verify_bist_type(fname):
    # verify BIST types present in file to inform user and ensure only appropriate files are selected and parsed
    # current BIST type list (also index in combo box) below; additional BIST types may be added in future
    # 0 = no BIST type determined; do not use for plotting; warn user
    # 1 = TX Channels Impedance (from telnet session logged to text file)
    # 2 = RX Channels Impedance (from BIST initiated and saved in SIS)
    # 3 = RX Noise (from telnet session logged to text file, likely using AutoBIST WSF script to run 10 tests)
    # 4 = RX Spectrum (from telnet session logged to text file, likely using AutoBIST WSF script to run 10 tests)

    bist_type = []  # list of BIST types found in file
    SIS_version = 0  # change to 4 or 5 only if found
    SIS4_list = ['Transmitter impedance', 'Rx Channels', 'RX NOISE LEVEL', 'RX NOISE SPECTRUM']  # case sensitive
    SIS5_list = ['TX channels', 'RX channels', 'RX noise level', 'RX noise spectrum']  # case sensitive
    # special case SIS 4 EM2040 and EM712 formats (various punctuation/capitalization as found in files)
    SIS4_list_special = ['Test of TX Channels', 'Test of RX channels.', 'Noise Test.', 'Spectral noise test:']  # case sensitive

    # NOTE: EM712 BISTs collected in SIS 4 require additional consideration (format is preliminary SIS 5, see SR1701)

    try:  # try reading file
        f = open(fname, "r")
        data = f.readlines()

    except ValueError:
        bist_type.append(0)
        print('***WARNING: Error reading file', fname)
        return bist_type, SIS_version

    if len(data) <= 0:  # skip if text file is empty
        print('***WARNING: No data read from file', fname)
        bist_type.append(0)

    elif any(substr in data[0] for substr in ["Database", "Datagram", "CPU"]):
        # only PU Params and System Report text files include this text in first line
        print("***WARNING: Skipping non-BIST file: ", fname)
        bist_type.append(0)

    # not empty and not PU Params or System Report; BIST data might exist; check for BIST type based on unique text
    # this can be made more elegant once it works reliably with SIS 4 and 5 formats
    else:
        # ################################## ORIGINAL METHOD #####################################
        # # check SIS 4 test list
        # for test_str in SIS4_list:
        #     if any(test_str in substr for substr in data):
        #         print('found SIS 4 substrings: ', test_str)
        #         SIS_version = 4
        #         bist_type.append(SIS4_list.index(test_str) + 1)  # add index in SIS#_list+1 corresponding to BIST_list
        #
        # if not bist_type:  # no SIS 4 formats found; check SIS 5 list
        #     for test_str in SIS5_list:
        #         if any(test_str in substr for substr in data):
        #             print('found SIS 5 substrings: ', test_str)
        #             SIS_version = 5
        #             bist_type.append(SIS5_list.index(test_str) + 1)
        #
        # if not bist_type:  # final check; return 0 (N/A) if nothing found
        #     bist_type.append(0)
        #
        # ###########################################################################################

        # some test substrings occur within others; to avoid overly complicating this search, loop through all lists of
        # substrs found in the various formats; the end goal is to return the set of indices for tests that are present;
        # this is simplified by getting the SIS version separately, not depending on which format list is satisfied
        for test_list in [SIS4_list, SIS4_list_special, SIS5_list]:
            for test_str in test_list:
                if any(test_str in substr for substr in data):
                    print('in verify_bist_type, found test_str: ', test_str)
                    bist_type.append(test_list.index(test_str) + 1)

        bist_type = [bt for bt in set(bist_type)]
        print('after taking set, bist_type =', bist_type)

        # SIS version is 4 if 'Saved: ' (e.g., first line) or 'EMX BIST menu' (e.g., SIS 4 TX Channels through telnet
        # session) are available, independent from set of test substrings
        # SIS_version = [5, 4][any('Saved: ' in substr for substr in data)]
        SIS_version = [5, 4][any('Saved: ' in substr for substr in data) or\
                             any('EMX BIST menu' in substr for substr in data)]

        print('in verify_bist_type, got SIS version = ', SIS_version)

        if not bist_type:  # final check; return 0 (N/A) if nothing found
            bist_type.append(0)

    return bist_type, SIS_version


def check_system_info(fname, sis_version=int(4)):
    _, sis_version = verify_bist_type(fname)  # get SIS version
    sys_key_list = ['date', 'time', 'model', 'sn']  # set up system info dict
    sys_info = {k: [] for k in sys_key_list}

    try:  # try reading file
        f = open(fname, "r")
        data = f.readlines()

    except ValueError:
        print('***WARNING: Error reading file', fname)
        # return sys_info

    if len(data) <= 0:  # skip if text file is empty
        print('***WARNING: No data read from file', fname)

    # Check to make sure its not a PU Params or System Report text file
    if any(substr in data[0] for substr in ["Database", "Datagram", "CPU"]):
        print("***WARNING: Skipping non-BIST file: ", fname)

    if sis_version == 4:  # look for SIS 4 system info in first lines of file (example below)
        print('checking system info for SIS 4, fname=', fname)
        # Saved: 2014.08.28 18:28:42
        # Sounder Type: 302, Serial no.: 101
        header_str = 'Saved: '
        model_str = 'Sounder Type: '
        sn_str = 'Serial no.:'

        i = 0
        while i < len(data):  # search for data and time
            if data[i].find(header_str) > -1:  # if header is found, start parsing
                temp_str = data[i].replace(header_str,'').strip()
                print('*** checking SIS 4 temp_str =', temp_str)
                sys_info['date'] = temp_str.split()[0].replace('.','/') # yyyy/mm/dd for comparison with user entry
                sys_info['time'] = temp_str.split()[1] + '.000'  # add ms for consistency with test time format
                print('got sys_info date and time ', sys_info['date'], sys_info['time'])
                break

            else:
                i += 1

        i = 0
        while i < len(data):  # search for model and serial number
            if data[i].find(model_str) > -1:
                print('sounder info in str =', data[i])
                sounder_info = data[i].split(',')
                # print('breaking this up into sounder_info=', sounder_info)
                sys_info['model'] = sounder_info[0].replace(model_str,'').strip()
                sys_info['sn'] = sounder_info[1].replace(sn_str,'').strip()
                print('got sys_info model and sn ', sys_info['model'], sys_info['sn'])
                break

            else:
                i += 1

    if sis_version == 5:  # look for SIS 5 system info from first test in file (example below)
        print('checking system info for SIS 5, fname=', fname)
        # --------------20200125-112229-15-Passed-EM304_60-Software-date-and-versions----EM-304.txt--------------
        header_str = '--------------'
        i = 0
        while i < len(data):
            if data[i].find(header_str) > -1:  # if header is found, start parsing
                temp_str = data[i].replace('-','').strip()  # remove all dashes
                print('*** checking SIS 5 temp_str =', temp_str)
                sys_info['date'] = temp_str[0:4] + '/' + temp_str[4:6] + '/' + temp_str[6:8]
                # sys_info['time'] = temp_str[8:10] + ':' + temp_str[10:12] + ':' + temp_str[12:14]
                # add ms to file time for consistency with individual test time format
                sys_info['time'] = temp_str[8:10] + ':' + temp_str[10:12] + ':' + temp_str[12:14] + '.000'
                sys_info['model'] = temp_str[temp_str.find('EM')+2:temp_str.find('_')]
                print('got sys_info =', sys_info)
                sys_info['sn'] = -1  # need to consider; some BISTs have PU sn, some have array sns
                temp_str = temp_str[temp_str.find('_') + 1:]  # shorten to portion of string after 'EM###_'
                sn_end = re.search(r'\D', temp_str)
                sys_info['sn'] = temp_str[:sn_end.start(0)]  # cut off at first non-digit in sn string
                print('storing SIS 5 s/n from BIST header (may actually be last two digits of IP address)')
                break

            else:
                i += 1

        # SIS 5 header line s/n is actually last two digits of IP address; search for PU s/n
        # BISTs with 'System Information' section include 'PU serial: 10012'
        # BISTs without 'System Information' might include 'Software date and versions' with 'PU - serial 10012:'
        print('starting search for SIS 5 serial number')
        # pu_str = 'PU serial:'
        i = 0
        while i < len(data):
            # print('looking at line i --> ', data[i])
            # if data[i].find(pu_str) > -1:
            # check if the alpha chars reduce to 'PU serial' (both formats above should work) and grab last number if so
            if ''.join([c for c in data[i] if c.isalpha()]).lower() == 'puserial':  # SysInfo and Software
                print('found ''puserial''; storing number at the end')
                # print(data[i].split(pu_str)[1].strip())
                sys_info['sn'] = ''.join([c for c in data[i] if c.isnumeric()])  # store serial number in this line
                # sys_info['sn'] = data[i].split(pu_str)[1].strip()  # store serial number string
                print('updating serial number to PU serial number = ', sys_info['sn'], '; breaking from check_sys_info')
                break

            else:
                i += 1

    if any(not v for v in sys_info.values()):  # warn user if missing system info in file
        missing_fields = ', '.join([k for k, v in sys_info.items() if not v])
        print('***WARNINGS: Missing system info (' + missing_fields + ') in file ' + fname)

    # print('Date:', sys_info['date'])
    # print('Time:', sys_info['time'])
    # print('Model:', sys_info['model'])
    # print('S/N:', sys_info['sn'])

    return sys_info
