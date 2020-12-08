
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


__version__ = "0.1.0"


def parse_rx_z(fname, sis_version=4):
    # Parse RX impedance data (receiver and transducer)
    n_rx_channels = 32  # each RX32 board has 32 channels
    zrx_temp = init_bist_dict(2)  # set up output dict for impedance data
    sys_info = check_system_info(fname)  # get system info and store in dict
    print('in file', fname, 'sys_info=', sys_info)

    zrx_temp['filename'] = fname
    for k in sys_info.keys():  # copy sys_info to bist dict
        zrx_temp[k] = sys_info[k]

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

    try:
        # SIS 4 strings preceding data in BIST file
        hdr_str_receiver = "Receiver impedance limits"  # SIS 4 start of SIS 4 RX Channels test for receiver
        limit_str_receiver = "Receiver impedance limits"  # SIS 4 RX Channels impedance limits for receiver
        hdr_str_array = "Transducer impedance limits"  # SIS 4 start of SIS 4 RX Channels test for transducer
        hdr_str_ch = ":"  # string in SIS 4 channel data, e.g., channel 1 --> 1: 852.3 870.2 849.9 855.0
        test_freq_str = " kHz test"  # string identifying the freq range for EM710 (SIS4), 40-70 or 70-100 kHz

        if sis_version is 5:  # strings for SIS 5 format
            hdr_str_receiver = "RX channels"
            limit_str_receiver = "ohm]"  # limits appear with this string (should also find " kohm]" for SIS 5 EM712)
            hdr_str_ch = "Ch"
            test_freq_str = " kHz"

        # find the Z values for receiver and transducer
        i = 0
        while i < len(data):
            # get RECEIVER channel impedance, limits, and test frequency
            if data[i].find(hdr_str_receiver) > -1:  # if RX Channels test header is found, start parsing
                print('found RECEIVER header string in', data[i])

                # check SIS 4 EM71X for single (70-100 kHz) or double test (70-100 and 40-70 kHz)
                if sis_version is 4:
                    if data[i-1].find(test_freq_str) > -1:  # check if freq of test is stated on previous line
                        zrx_temp['freq_range'].append(data[i-1][:data[i-1].find(" kHz")])  # get freq ('40-70 kHz test')

                    else:
                        freq_str = get_freq(zrx_temp['model'])  # get nominal frequency of this model
                        zrx_temp['freq_range'].append(freq_str.replace('kHz', '').strip())

                    while data[i].find(limit_str_receiver) == -1:  # find limit string (SIS 4 is same line, SIS 5 later)
                      i += 1

                    # store zrx limits (first [] in SIS 5)
                    # zrx_limits = data[i][data[i].find("[") + 1:data[i].find("]")].replace("kohm", "").replace("ohm", "")
                    # zrx_limits = [float(x) for x in zrx_limits.split()]

                    lim_temp = data[i][data[i].find("[") + 1:data[i].find("]")].replace("kohm", "").replace("ohm", "")
                    zrx_limits.append([float(x) for x in lim_temp.split()])  # store list of limits for this freq

                elif sis_version is 5:  # check SIS 5 EM71X for multiple frequencies (e.g., 55 and 84 kHz tests)

                    while data[i].find(limit_str_receiver) == -1 or data[i].find('Impedance') > -1:
                        i += 1  # iterate past 'RX 1 Impedance [kohm]...' and find limits line with ' kohm]' or ' ohm]'

                    print('FOUND LIMITS STRING = ', data[i])
                    # zrx_limits = data[i].rstrip('')
                    lim_temp = data[i].replace('[', ' ').replace(']', ' ').split()
                    zlim_units = [l for l in lim_temp if l.find('ohm') > -1]
                    zlim_count = len(zlim_units)
                    # zrx_limits = ['10.5', '17.5', 'kohm', '5.0', '11.0', 'kohm', '-100', '-70', 'deg', '-90', '-60', 'deg']
                    lim_temp = [float(l) for l in lim_temp if not l.isalpha()]
                    lim_temp = lim_temp[0:(2*zlim_count)]  # keep only impedance limits, do not store phase limits
                    print('ZRX lim_temp is now ', lim_temp)

                    # convert kohm to ohm if necessary and store list of [zlim_low, zlim_high] for each frequency test
                    # lim_temp = [str(float(l)*1000) if zlim_units[int(np.floor(j / 2))] == 'kohm' else l
                    #             for j, l in enumerate(lim_temp)]
                    # print('after converting kohm to ohm, ZRX_lim_temp =', lim_temp)

                    lim_reduced = [lim_temp[f:f+2] for f in range(0, 2*zlim_count, 2)]
                    print('lim_reduced = ', lim_reduced)
                    print('lim_reduced[0] = ', lim_reduced[0])
                    # if zlim_count > 1:
                    # lim_reduced = lim_reduced[0]
                    print('lim_reduced to be extended = ', lim_reduced)
                    zrx_limits.extend(lim_reduced)
                    print('zrx_limits is now', zrx_limits)
                    # zrx_limits.append([lim_temp[f:f+2] for f in range(0, 2*zlim_count, 2)])  # store list of lims / freq
                    #
                    # print('storing zrx_limits as ', zrx_limits)
                    # for f in range(n_freq):
                    #     lim_out.append(lim_temp[(2*f):(2 * i + 2)])

                    # zrx_limits.append([float(x) for x in lim_temp])

                    while data[i].find(test_freq_str) == -1:  # find freq string (SIS 5 may be multiple freq, same line)
                        i += 1

                    # store SIS 5 frequency(ies)
                    # '    55 kHz                    84 kHz               55 kHz                84 kHz   '

                    zrx_temp['freq_range'] = [f for f in set(data[i].replace(test_freq_str, '').split())]
                    zrx_temp['rx_units'] = zlim_units

                    print('FOUND FREQ_RANGE = ', zrx_temp['freq_range'])

                # else:
                #     print('no freq')
                #     freq_str = get_freq(zrx_temp['model'])  # get nominal frequency of this model
                #     zrx_temp['freq_range'].append(freq_str.replace('kHz', '').strip())
                #     zrx_limits = [np.nan, np.nan]

                # while data[i].find(limit_str_receiver) == -1:  # find limit string (SIS 4 is same line, SIS 5 later)
                #     i += 1
                #
                # # store zrx limits (first [] in SIS 5)
                # zrx_limits = data[i][data[i].find("[") + 1:data[i].find("]")].replace("kohm", "").replace("ohm", "")
                # zrx_limits = [float(x) for x in zrx_limits.split()]

                while data[i].find(hdr_str_ch) == -1:  # find first channel header
                    i = i+1

                print('FOUND HEADER STRING in line ', data[i])

                while True:  # read channels until something other than a channel or whitespace is found
                    ch_str = data[i].replace("*", "")  # replace any * used for marking out of spec channels
                    if len(ch_str.split()) > 0:  # if not just whitespace, check if start of channel data
                        if ch_str.find(hdr_str_ch) > -1:  # look for #: (SIS 4) or Ch (SIS 5) at start of line
                            z_str = ch_str.split()

                            # print('found z_str = ', z_str)

                            if sis_version == 4:  # SIS 4: store floats of one channel from all boards in string
                                for x in z_str[1:]:
                                    zrx_test.append(float(x))

                            else:  # SIS 5: store floats of one channel across all frequencies in string
                                # print('working on SIS 5 format with zlim_count = ', zlim_count)
                                # x = z_str[2]  # works for single frequency test
                                # zrx_test.append(float(x))  # append zrx for one channel, reshape later
                                # print('now looking at reduced z_str = ', z_str[2:(-1*zlim_count)])
                                for x in z_str[2:(-1*zlim_count)]:
                                    # print('SIS 5: appending RX Z value = ', x)
                                    zrx_test.append(float(x))

                                # x = z_str[2:-2*zlim_count]  # store from third item (first Z value) to start of phase(s)
                                # zrx_test.extend([float(z) for z in x])

                        else:  # break if not whitespace and not channel data
                            break

                    i += 1

            # SIS 4 ONLY: find transducer impedance data, parse limits (on same line as header) and channels
            if data[i].find(hdr_str_array) > -1:
                print('found ARRAY header string in', data[i])
                # zrx_array_limits = data[i][data[i].find("[")+1:data[i].find("]")]
                # zrx_array_limits = [float(x) for x in zrx_array_limits.split()]

                lim_temp = data[i][data[i].find("[")+1:data[i].find("]")]
                zrx_array_limits.append([float(x) for x in lim_temp.split()])  # store list of limits for each freq
                print('zrx_array_limits is now', zrx_array_limits)

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
                                    zrx_array_test.append(x)

                            else:  # SIS 5: transducer impedance not available; store NaN
                                zrx_array_test.append(np.nan)  # append zrx for one channel, reshape later

                        else:  # break if not whitespace and not channel data
                            break

                    i += 1  # increment
        
            # SIS 4 ONLY: find temperature data and loop through entries
            if data[i].find("Temperature") > -1:
                if data[i+2].find("RX") > -1:
                    trx_limits = data[i+2][data[i+2].find(":")+1:].replace("-", "")
                    trx_limits = [float(x) for x in trx_limits.split()]

                    # FUTURE: change trx_limits to append list of limits for each freq, as rcvr and xdcr above

                    j = 0

                    while len(data[i+j+3]) > 3:  # read temp until white space with len<=1 (no need for n_rx_boards)
                        t_str = data[i+j+3][3:]
                        trx.append(float(t_str.split()[0]))
                        j += 1

            i += 1  # increment

    except ValueError:
        print("***WARNING: Error parsing ", fname)

    # if data found, reshape and store in temp dict
    if len(zrx_test) > 0:
        # reorganize multi-freq SIS 5 data into consecutive tests
        n_freq = len(zrx_temp['freq_range'])
        if sis_version == 5 and n_freq > 1:
            print('SIS 5 --> multiple frequencies parsed --> resorting by frequency')
            zrx_test_by_freq = []
            for f in range(n_freq):
                zrx_freq = [zrx_test[i] for i in range(f, len(zrx_test), n_freq)]
                print('extending zrx_test_by_freq using zrx values for f=', zrx_temp['freq_range'][f], '=', zrx_freq)
                zrx_test_by_freq.extend(zrx_freq)

            zrx_test = zrx_test_by_freq  # resorted list in order of frequencies

        # reshape parsed Z data in variable length list as array, transpose for order expected by plotter
        # row = board, col = channel, extending cols for each test
        n_cols = int(len(zrx_test)/n_rx_channels/n_freq)  #len(zrx_temp['freq_range']))
        print('n_cols = ', n_cols)
        zrx_temp['rx'] = np.transpose(np.reshape(np.asarray(zrx_test), (-1, n_cols)))
        zrx_temp['rx_limits'] = zrx_limits

        print('zrx_temp[rx] =', zrx_temp['rx'])

        print('zrx_temp[rx_limits] = ', zrx_temp['rx_limits'])

        if zrx_array_test:  # store array impedance data if parsed
            zrx_temp['rx_array'] = np.transpose(np.reshape(np.asarray(zrx_array_test), (-1, n_cols)))
            zrx_temp['rx_array_limits'] = zrx_array_limits
            print('storing rx_array_limits =', zrx_array_limits)
            print('zrx_temp[rx_array_limits] is now', zrx_temp['rx_array_limits'])

        else:  # assign NaNs for unavailable array impedance fields (e.g., SIS 5 and some SIS 4 BISTs)
            zrx_temp['rx_array'] = np.empty(np.shape(zrx_temp['rx']))
            zrx_temp['rx_array'][:] = np.nan
            # zrx_temp['rx_array_limits'] = [].extend([[np.nan, np.nan]*n_freq])
            zrx_temp['rx_array_limits'] = [[np.nan, np.nan] for i in range(n_freq)]

        if trx and trx_limits:  # store temperature data if parsed
            zrx_temp['rx_temp'] = trx
            zrx_temp['rx_temp_limits'] = trx_limits

        else:  # assign NaNs for unavailable fields
            zrx_temp['rx_temp'] = np.empty(np.shape(zrx_temp['rx']))
            zrx_temp['rx_temp'][:] = np.nan
            # zrx_temp['rx_temp_limits'] = [[np.nan, np.nan]*n_freq]
            zrx_temp['rx_temp_limits'] = [[np.nan, np.nan] for i in range(n_freq)]

        print('leaving parser with zrx_temp[rx_limits] = ', zrx_temp['rx_limits'])
        print('leaving parser with zrx_temp[rx_array_limits] = ', zrx_temp['rx_array_limits'])


        return(zrx_temp)
        
    else:
        print("Error in zrx parser, len(zrx) <= 0")
        return []

  
def plot_rx_z(z, save_figs=True, output_dir=os.getcwd()):
    # plot RX impedance for each file
    for i in range(len(z['filename'])):
        print('Plotting', z['filename'][i], ' with f range(s):', print(z['freq_range'][i]))
        zrx = np.asarray(z['rx'][i])
        zrx_array = np.asarray(z['rx_array'][i])

        print('in plotter, z[rx_limits] =', z['rx_limits'])

        for f in range(len(z['freq_range'][i])):
            print('f=', f)
            try:  # try plotting
                fig, (ax1, ax2) = plt.subplots(nrows=2)  # create new figure

                # declare standard spec impedance limits, used if not parsed from BIST file
                rx_rec_min = 600
                rx_rec_max = 1000
                rx_xdcr_min = 250
                rx_xdcr_max = 1200

                try:  # get receiver plot color limits from parsed receiver Z limits
                    # print('z rx_limits=', z['rx_limits'][i])
                    # rx_rec_min, rx_rec_max = z['rx_limits'][i]
                    print('z rx_limits[i][f]=', z['rx_limits'][i][f])
                    rx_rec_min, rx_rec_max = z['rx_limits'][i][f]

                    # rx_rec_min = str(float(rx_rec_min)-5000)  # sanity check

                except:
                    print('Error assigning color limits from z[rx_limits][i][f] for i, f =', i, f)

                try:  # get array plot color limits from parsed array Z limits
                    # print('z rx_array_limits=', z['rx_array_limits'][i])
                    # rx_xdcr_min, rx_xdcr_max = z['rx_array_limits'][i]
                    print('z rx_array_limits=', z['rx_array_limits'][i][f])
                    rx_xdcr_min, rx_xdcr_max = z['rx_array_limits'][i][f]

                except:
                    print('Error assigning color limits from z[rx_array_limits][i][f] for i, f =', i, f)

                # plot the rx RECEIVER z values;  plot individual test data for EM71X
                im = ax1.imshow(zrx[:, 32*f:32*(f+1)], cmap='rainbow', vmin=rx_rec_min, vmax=rx_rec_max)

                cbar = fig.colorbar(im, orientation='vertical', ax=ax1)
                # cbar.set_label('Ohms')
                print('in plotter, the z[rx_units] = ', z['rx_units'])

                try:
                    cbar_label = z['rx_units'][i][f] +'s'
                except:
                    cbar_label = 'ohms'

                cbar_label = ''.join([str.capitalize(c) if c == 'o' else c for c in cbar_label])  #kOhms or Ohms
                cbar.set_label(cbar_label)

                # get number of RX boards; zrx size is (n_rx_boards, n_channels*n_freq_tests); n_channels is 32/board
                n_rx_boards = np.divide(np.size(zrx), 32*len(z['freq_range'][i]))

                # set ticks and labels
                x_ticks = np.arange(0, 32, 1)
                x_ticks_minor = np.arange(-0.5, 32.5, 1)
                x_tick_labels = [str(x) for x in x_ticks]
                y_ticks = np.arange(0, n_rx_boards, 1)
                y_ticks_minor = np.arange(-0.5, n_rx_boards+0.5, 1)
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
                ax1.set_title('RX Impedance: Receiver', fontsize=20)

                print()

                try:  # plot the rx TRANSDUCER z values; plot individual test data for EM71X
                    zrx_array_temp = zrx_array[:, 32*f:32*(f+1)]
                except:
                    print('zrx_array not available for plotting for this frequency range')

                im = ax2.imshow(zrx_array_temp, cmap='rainbow', vmin=rx_xdcr_min, vmax=rx_xdcr_max)

                cbar = fig.colorbar(im, orientation='vertical', ax=ax2)
                # cbar.set_label('Ohms')
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

                if np.all(np.isnan(zrx_array)):  # plot text: no RX array impedance data available in BIST (e.g., SIS 5)
                    ax2.text(16, (n_rx_boards/2)-0.5, 'NO TRANSDUCER RX CHANNELS DATA',
                             fontsize=24, color='red', fontweight='bold',
                             horizontalalignment='center', verticalalignment='center_baseline')

                # set axis tick formatter
                ax1.xaxis.set_major_formatter(FormatStrFormatter('%g'))
                ax1.yaxis.set_major_formatter(FormatStrFormatter('%g'))
                ax2.xaxis.set_major_formatter(FormatStrFormatter('%g'))
                ax2.yaxis.set_major_formatter(FormatStrFormatter('%g'))

                # set the super title
                title_str = 'RX Impedance BIST\n' + 'EM' + z['model'][i] + ' (S/N ' + z['sn'][i] + ')\n' + \
                            z['date'][i] + ' ' + z['time'][i] + '\nFrequency: ' + z['freq_range'][i][f] + ' kHz'

                print('title_str=', title_str)
                fig.suptitle(title_str, fontsize=20)

                # save the figure
                if save_figs is True:
                    fig = plt.gcf()
                    fig.set_size_inches(16, 10)
                    fig_name = 'RX_Z_EM' + z['model'][i] + '_SN_' + z['sn'][i] + \
                               '_' + z['date'][i].replace("/","") + '_' + z['time'][i].replace(":","") + \
                               '_freq_' + z['freq_range'][i][f] + '_kHz' + '.png'
                    print('Saving', fig_name)
                    fig.savefig(os.path.join(output_dir, fig_name), dpi=100)

                plt.close()

            except ValueError:  # move on if error
                print("***WARNING: Error plotting ", z['filename'][i])


def plot_rx_z_annual(z, save_figs=True, output_dir=os.getcwd()):
    # take the average of each year, make annual plots

    # set x ticks and labels on bottom of subplots to match previous MAC figures
    plt.rcParams['xtick.bottom'] = plt.rcParams['xtick.labelbottom'] = True
    plt.rcParams['xtick.top'] = plt.rcParams['xtick.labeltop'] = False

    print('\n\n\n************* STARTING PLOT RX Z ANNUAL *******************')
    # get model, sn, time span
    model = z['model'][0]  # reassign model and sn in case last BIST parse failed
    sn = z['sn'][0]
    yrmin = min(z['date'])
    yrmin = int(yrmin[:4])
    yrmax = max(z['date'])
    yrmax = int(yrmax[:4])
    yrs = [str(yr) for yr in range(yrmin, yrmax+1)]

    # testing handling for multi-freq (e.g., Armstrong EM710)
    # print('z[freq_range]=', z['freq_range'])
    # print('list of z[fr]=', flatten(z['freq_range']))
    freq_ranges = [fr for fr in set([f for fr in z['freq_range'] for f in fr])]
    print('*********found frequency ranges:', freq_ranges)

    # n_rx_boards = np.size(z['rx'][0], 0)
    # get number of RX boards; zrx size is (n_rx_boards, n_channels*n_freq_tests); n_channels is 32/board
    # n_rx_boards = np.divide(np.size(z['rx']), 32*len(z['freq_range'][i]))
    n_rx_boards_max = 8  # max number of boards just to initialize arrays
    n_rx_channels = 32

    # declare arrays for means of receiver and transducer array
    zrx_mean = np.array([[[[float(0.0)]*n_rx_channels]*n_rx_boards_max]*len(yrs)]*len(freq_ranges))
    zrx_mean_count = np.array([[[[float(0.0)]*n_rx_channels]*n_rx_boards_max]*len(yrs)]*len(freq_ranges))
    zrx_array_mean = np.array([[[[float(0.0)]*n_rx_channels]*n_rx_boards_max]*len(yrs)]*len(freq_ranges))
    zrx_array_mean_count = np.array([[[[float(0.0)]*n_rx_channels]*n_rx_boards_max]*len(yrs)]*len(freq_ranges))
    zrx_mean_bist_count = np.array([[float(0.0)]*len(yrs)]*len(freq_ranges))

    # step through all frequency ranges and years, find means of corresponding data in spec for board b and channel c
    for f in range(len(freq_ranges)):  # loop through all frequency ranges found
        for y in range(len(yrs)):  # loop through all years found
            # find BISTs matching each year, scroll each frequency, sum boards and channels if in spec, plot
            for i in range(len(z['filename'])):  # loop through every file
                for j in range(len(z['freq_range'][i])):  # loop through all frequency tests in this file
                    # print('searching j=', j, 'and z[freq_range][i][j]=', z['freq_range'][i][j])
                    if z['date'][i][:4] == yrs[y] and z['freq_range'][i][j] == freq_ranges[f]:  # check year and freq
                        # print('found BIST number', i, 'in year', yrs[y], 'freq_range=', freq_ranges[f], 'at index', y)
                        zrx_mean_bist_count[f, y] += 1
                        # zrx_limits = z['rx_limits'][i]
                        zrx_limits = z['rx_limits'][i][j]
                        # zrx_array_limits = z['rx_array_limits'][i]
                        zrx_array_limits = z['rx_array_limits'][i][j]

                        print('in plotter for i =', i, 'and j=', j, 'the zrx_limits are', zrx_limits,
                              'and zrx_array limits are ', zrx_array_limits)

                        n_freq = len(z['freq_range'][i])
                        n_rx_boards = int(np.divide(np.size(z['rx'][i]), 32*n_freq))

                        if n_rx_boards > n_rx_boards_max:
                            print('***WARNING: n_rx_boards =', n_rx_boards, '> n_rx_boards_max = ', n_rx_boards_max)

                        for b in range(n_rx_boards):
                            for c in range(n_rx_channels):
                                print(f,y,i,j,b,c)
                                if zrx_limits[0] <= z['rx'][i][b, j*n_rx_channels+c] <= zrx_limits[1]:
                                    zrx_mean[f, y, b, c] =\
                                        zrx_mean[f, y, b, c] +\
                                        z['rx'][i][b, j*n_rx_channels+c]
                                    zrx_mean_count[f, y, b, c] = zrx_mean_count[f, y, b, c] + 1
                                else:
                                    print('this element outside limits...')

                                if zrx_array_limits[0] <= z['rx_array'][i][b, j*n_rx_channels+c] <= zrx_array_limits[1]:
                                    zrx_array_mean[f, y, b, c] = zrx_array_mean[f, y, b, c] +\
                                                                 z['rx_array'][i][b, j*n_rx_channels+c]
                                    zrx_array_mean_count[f, y, b, c] = zrx_array_mean_count[f, y, b, c] + 1

            # after summing for this year, divide sum by count for each board/channel
            zrx_mean[f, y, :, :] = zrx_mean[f, y, :, :] / zrx_mean_count[f, y, :, :]
            zrx_array_mean[f, y, :, :] = zrx_array_mean[f, y, :, :] / zrx_array_mean_count[f, y, :, :]

            # plot the yearly average if any matches were found
            if zrx_mean_bist_count[f, y] > 0:
                fig, (ax1, ax2) = plt.subplots(nrows=2)  # create new figure

                # plot the RX RECEIVER Z values
                im = ax1.imshow(zrx_mean[f, y, :, :], cmap='rainbow', vmin=zrx_limits[0], vmax=zrx_limits[1])
                cbar = fig.colorbar(im, orientation='vertical', ax=ax1)
                cbar.set_label('Ohms')

                # set ticks and labels
                x_ticks = np.arange(0, 32, 1)
                x_ticks_minor = np.arange(-0.5, 32.5, 1)
                x_tick_labels = [str(x) for x in x_ticks]
                y_ticks = np.arange(0, n_rx_boards, 1)
                y_ticks_minor = np.arange(-0.5, n_rx_boards + 0.5, 1)
                y_tick_labels = [str(y) for y in y_ticks]

                # set ticks and labels
                ax1.set_yticks(y_ticks)
                ax1.set_xticks(x_ticks)
                ax1.set_yticklabels(y_tick_labels, fontsize=16)
                ax1.set_xticklabels(x_tick_labels, fontsize=16)
                ax1.set_yticks(y_ticks_minor, minor=True)  # set minor axes for gridlines
                ax1.set_xticks(x_ticks_minor, minor=True)
                ax1.grid(which='minor', color='k', linewidth=2)  # set minor gridlines
                ax1.set_ylim(n_rx_boards-0.5)
                ax1.set_ylabel('RX Board', fontsize=16)
                ax1.set_xlabel('RX Channel', fontsize=16)
                ax1.set_title('RX Impedance: Receiver', fontsize=20)

                # plot the RX TRANSDUCER Z values
                im = ax2.imshow(zrx_array_mean[f, y, :, :], cmap='rainbow',
                                vmin=zrx_array_limits[0], vmax=zrx_array_limits[1])
                cbar = fig.colorbar(im, orientation='vertical', ax=ax2)
                cbar.set_label('Ohms')

                # set ticks and labels
                ax2.set_yticks(y_ticks)
                ax2.set_xticks(x_ticks)
                ax2.set_yticklabels(y_tick_labels, fontsize=16)
                ax2.set_xticklabels(x_tick_labels, fontsize=16)
                ax2.set_yticks(y_ticks_minor, minor=True)  # set minor axes for gridlines
                ax2.set_xticks(x_ticks_minor, minor=True)
                ax2.grid(which='minor', color='k', linewidth=2)  # set minor gridlines
                ax2.set_ylim(n_rx_boards-0.5)
                ax2.set_ylabel('RX Board', fontsize=16)
                ax2.set_xlabel('RX Channel', fontsize=16)
                ax2.set_title('RX Impedance: Transducer', fontsize=20)
                print('zrx_array_limits = ', zrx_array_limits)

                if np.all(np.isnan(zrx_array_mean[f, y, :, :])):  # plot text: no RX array impedance data available in BIST

                    ax2.text(16, (n_rx_boards / 2) - 0.5, 'NO TRANSDUCER RX CHANNELS DATA',
                             fontsize=24, color='red', fontweight='bold',
                             horizontalalignment='center', verticalalignment='center_baseline')

                # for ax in [ax1, ax2]:  # set xlim and aspect for both axes
                    # ax.set_xlim(-0.5, n_rx_channels + 0.5)
                    # ax.set(aspect='auto', adjustable='box')
                    # ax.set_xlabel('RX Module (index starts at 1)', fontsize=axfsize)
                    # ax.set_xticks(x_ticks)
                    # ax.set_xticks(x_ticks, minor=True)
                    # ax.grid(which='minor', color='k', linewidth=1)
                    # ax.tick_params(labelsize=axfsize)
                    # ax.xaxis.set_label_position('bottom')


                # set the super title
                bist_count = zrx_mean_bist_count[f, y]
                title_str = 'RX Impedance BIST\n' + \
                            'EM' + model + ' (S/N ' + sn + ')\n' + \
                            'Year: ' + yrs[y] + ' (' + str(int(bist_count)) + \
                            ' BIST' + ('s' if bist_count > 1 else '') + ')\n' + \
                            'Frequency: ' + freq_ranges[f] + ' kHz'

                fig.suptitle(title_str, fontsize=20)

                # save the figure
                if save_figs is True:
                    fig = plt.gcf()
                    fig.set_size_inches(16, 10)
                    fig_name = 'RX_Z_EM' + model + '_SN_' + sn + '_annual_mean_' + yrs[y] +\
                               '_freq_' + freq_ranges[f] + '_kHz.png'
                    fig.savefig(os.path.join(output_dir, fig_name), dpi=100)

                plt.close()

            else:
                print('BIST Count = 0 for mean Z plotting in year', yrs[y], 'and freq', freq_ranges[f])
                continue


def plot_rx_z_history(z, save_figs=True, output_dir=os.getcwd()):
    # plot lines of all zrx values colored by year to match historic Multibeam Advisory Committee plots

    # set x ticks and labels on bottom of subplots to match previous MAC figures
    plt.rcParams['xtick.bottom'] = plt.rcParams['xtick.labelbottom'] = True
    plt.rcParams['xtick.top'] = plt.rcParams['xtick.labeltop'] = False

    # get model, sn, time span
    model = z['model'][0]  # reassign model and sn in case last BIST parse failed
    sn = z['sn'][0]
    datemin = min(z['date'])
    yrmin = int(datemin[:4])
    yrmax = max(z['date'])
    yrmax = int(yrmax[:4])
    yrs = [str(yr) for yr in range(yrmin, yrmax + 1)]
    n_freq = len(z['freq_range'][0])
    print('number of frequencies detected:', n_freq)
    n_rx_boards = np.size(z['rx'][0], 0)
    n_rx_channels = 32  # this should probably always be 32 (boards are 'rx32')
    n_rx_modules = n_rx_channels*n_rx_boards  # not size(rx,1) as rx may include 70-100 and 40-70 kHz data for EM71X

    print('n_rx_boards is', n_rx_boards)
    print('n_rx_channels is', n_rx_channels)
    print('n_rx_modules is', n_rx_modules)

    colors = plt.cm.rainbow(np.linspace(0, 1, len(yrs)))  # set up line colors over number of years
    zrx_module = np.arange(1, n_rx_modules+1)  # range of RX modules for plotting (unlike channels, this starts at 1)
    # zrx_channel = np.tile(np.arange(0, n_rx_channels), [n_rx_boards, 1])  # array of zrx chans for plotting (start at 0)

    # set axis and label parameters
    axfsize = 16  # axis font size
    dx_tick = 8
    dy_tick = 50
    dy_tick_array = 150

    # loop through the frequency ranges, years and plot zrx and zrx_array lines in same color for that year
    f_set = list(set(a for b in z['freq_range'] for a in b))  # get unique frequencies in list of lists in z[freq_range]
    # print('f_set is', f_set)

    # find index of most recent BIST for plotting
    bist_time_str = [z['date'][d] + z['time'][d] for d in range(len(z['date']))]
    bist_time_obj = [datetime.datetime.strptime(t.replace('/', '').replace(':', ''), '%Y%m%d%H%M%S')
                     for t in bist_time_str]
    idx_last = np.argmax(bist_time_obj)

    for f in range(len(f_set)):  # loop through all frequency sets (may not be parsed in same order)
        bist_count = 0
        print('f=', str(f))
        # make figure with two subplots
        fig = plt.figure()
        fig.set_size_inches(11, 16)  # previous MAC plots height/width ratio is 1.25
        ax1 = fig.add_subplot(2, 1, 1)
        ax2 = fig.add_subplot(2, 1, 2)
        plt.subplots_adjust(top=0.85)  # try to keep long supertitle from overlapping

        # make list of line artists, reset for each frequency
        legend_labels = []
        legend_artists = []

        print('plotting frequency range', f_set[f])  # z['freq_range'][0][f])
        for y in range(len(yrs)):
            print('y=', str(y))
            # legend_labels.append(yrs[y])  # store year as label for legend

            for i in range(len(z['date'])):
                print('i=', str(i))
                if z['date'][i][:4] == yrs[y]:  # check if this BIST matches current year
                    print('year matches')
                    # get limits parsed for this BIST
                    # zrx_limits = z['rx_limits'][i]
                    # zrx_array_limits = z['rx_array_limits'][i]
                    zrx_limits = z['rx_limits'][i][f]
                    zrx_array_limits = z['rx_array_limits'][i][f]

                    print('in history plotter, zrx_limits and zrx_array_limits are', zrx_limits, zrx_array_limits)

                    if any(np.isnan(zrx_array_limits)):  # replace zrx array limits if nans
                        zrx_array_limits = [0, 1]

                    # loop through all available frequency ranges for this BIST
                    for j in range(len(z['freq_range'][i])):
                        # # find idx of data that match this frequency range
                        print('f is within index range')
                        if z['freq_range'][i][j] == f_set[f]:  # check if BIST freq matches current freq of interest
                            # store impedance data as array for local use if frequency matches
                            zrx = np.asarray(z['rx'][i])[:, n_rx_channels*j:n_rx_channels*(j+1)]

                            try:
                                zrx_array = np.asarray(z['rx_array'][i])[:, n_rx_channels*j:n_rx_channels*(j+1)]

                            except:
                                print('zrx_array not available for this frequency range')
                                zrx_array = np.nan*np.ones(np.shape(zrx))

                            if i == idx_last:  # store for final plotting in black if this is most recent data
                                zrx_last = zrx
                                zrx_array_last = zrx_array

                            # skip if not 32 RX channels (parser err? verify this is the case for all RX xdcr cases)
                            if zrx.shape[1] == n_rx_channels and zrx_array.shape[1] == n_rx_channels:
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
                                y_ticks = np.arange(zrx_limits[0], zrx_limits[1] + 1, dy_tick)
                                y_ticks_array = np.arange(zrx_array_limits[0], zrx_array_limits[1] + 1, dy_tick_array)

                                # set ylim to parsed spec limits
                                ax1.set_ylim(zrx_limits)
                                ax2.set_ylim(zrx_array_limits)

                                # set yticks for labels and minor gridlines
                                ax1.set_yticks(y_ticks)
                                ax1.set_yticks(y_ticks, minor=True)
                                ax1.set_ylabel('Receiver Impedance (ohms)\n(axis limits = Kongsberg spec.)',
                                               fontsize=axfsize)
                                ax2.set_yticks(y_ticks_array)
                                ax2.set_yticks(y_ticks_array, minor=True)
                                ax2.set_ylabel('Transducer Impedance (ohms)\n(axis limits = Kongsberg spec.)',
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
                                print('Skipping ', z['filename'], ' with ', str(zrx.shape[1]), ' RX and ',
                                      str(zrx_array.shape[1]), ' channels instead of 32!')

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
        title_str = 'RX Channels BIST\n' + 'EM' + model + ' (S/N ' + sn + ')\n' + \
                    years_str + ' (' + str(bist_count) + ' BIST' + ('s' if bist_count > 1 else '') + ')\n' + \
                    'Frequency: ' + f_set[f] + ' kHz'
                    # 'Frequency: '+z['freq_range'][i][f]+' kHz'
        t1 = fig.suptitle(title_str, fontsize=20)
        fig.set_size_inches(10, 14)

        # save the figure
        if save_figs is True:
            # fig = plt.gcf()
            # fig.set_size_inches(10, 10)
            fig_name = 'RX_Z_EM' + model + '_SN_' + sn + '_history_' + str(yrmin) + '-' + str(yrmax) + \
                       '_freq_' + f_set[f] + '_kHz' + '.png'
                       # '_freq_'+z['freq_range'][i][f]+'_kHz'+'.png'
            print('Saving', fig_name)
            # fig.savefig(fig_name, dpi=100)
            fig.savefig(os.path.join(output_dir, fig_name), dpi=100,
                        bbox_extra_artists=(t1, l1, l2), bbox_inches='tight')  # add bbox extra artists to avoid cutoff

        plt.close()


# parse TX Channels BIST text file
def parse_tx_z(fname, sis_version=int(4)):
    z = init_bist_dict(1)  # set up TX Channels Z dict
    found_channels = False

    try:  # try reading file
        f = open(fname, "r")
        data = f.readlines()

    except ValueError:
        print('***WARNING: Error reading file', fname)

    if len(data) <= 0:  # skip if text file is empty
        print('***WARNING: No data read from file', fname)
        # return ()
        return []

    # Check to make sure its not a PU Params or System Report text file
    if any(substr in data[0] for substr in ["Database", "Datagram", "CPU"]):
        print("***WARNING: Skipping non-BIST file: ", fname)
        # return ()
        return []

    try:  # try parsing the data for all tests in text file
        header_str = ["Transmitter impedance rack:"]  # start of SIS 4 TX Channels test
        ch_hdr_str = "Ch:"  # start of SIS 4 channel data

        if sis_version is 5:
            header_str = ["TX channels", "Impedance limits"]  # strings before each batch of TX Z channel data in SIS 5
            ch_hdr_str = "Ch"  # start of SIS 5 channel data
            limit_str = "Impedance limits"  # start of impedance limit data; also repeats before each iteration of TX Z
            model_str = "EM"  # start of model number (within header str)

        i = 0
        while i < len(data):  # step through file and store channel data when found
            if any(substr in data[i] for substr in header_str):  # find any TX Z header strings preceding ch. data
                temp_str = data[i]

                if sis_version == 4:  # SIS 4: get rack and slot version from header
                    rack_num = temp_str[temp_str.find(":") + 1:temp_str.find(":") + 4]
                    rack_num = int(rack_num.strip().rstrip())
                    slot_num = temp_str[temp_str.rfind(":") + 1:temp_str.rfind("\n")]
                    slot_num = int(slot_num.strip().rstrip()) - 1  # subtract 1 for python indexing

                else:  # SIS 5: get slot numbers for SIS 5 (e.g., 36 rows = 36 channels, 10 columns = 10 slots/boards)
                    if temp_str.find(model_str) > -1:  # check for model_str in TX channels header, get number after EM
                        model_num = temp_str[temp_str.rfind(model_str)+2:].strip()
                        z['model'] = model_num

                        if model_num.find('2040') > -1:  # no numeric TX Z data in EM2040 BISTs; return empty
                            return []

                        else:  # for SIS 5, store mean frequency for this model (not explicitly stated in BIST)
                            freq_str = get_freq(model_num)  # get nominal
                            freq = np.mean([float(n) for n in freq_str.replace('kHz', '').strip().split('-')])

                    while data[i].find(limit_str) == -1:  # loop until impedance limits string is found
                        i += 1
                    temp_str = data[i]
                    zlim_str = temp_str[temp_str.find('[')+1:temp_str.rfind(']')]  # FUTURE: store limits for plot cbar
                    print('found z_limits=', zlim_str)
                    zlim = [float(lim) for lim in zlim_str.split()]

                while data[i].find(ch_hdr_str) == -1:  # loop until channel info header is found (SIS5 has whitespace)
                    if sis_version == 5 and len(data[i].split()) > 0:  # SIS 5 format includes row of slot/board numbers
                        slot_num = len(data[i].split())  # slot_num is slot count in row for SIS 5; slot ID for SIS 4
                        rack_num = 9999  # placeholder for print statements for SIS 5, parsed for SIS 4
                    i += 1

                # print('TRYING to parse rack', rack_num, ' slot number (SIS4) / slot count (SIS5)', slot_num)
                # print('found TX Z channel header=', ch_hdr_str, ' on line i =', i)

                # channel header string is found; start to read channels
                j = 0  # reset line counter while reading channels
                c = 0  # reset channel counter

                z_temp = []
                phase_temp = []
                f_temp = []
                umag_temp = []

                while True:  # found header; start reading individual channels
                    ch_str = data[i+j]
                    # print('in channel loop with i =', i, 'j =', j, 'c=', c, 'and ch_str=', ch_str)

                    while c < 36:  # TX Channels should have exactly 36 channels per slot (TX36 board)
                        if len(ch_str.split()) > 0:  # if not just whitespace, check if start of channel data
                            if data[i+j].find(ch_hdr_str) > -1:  # look for Ch: (SIS 4) or Ch (SIS 5) at start of line
                                # parse the string for this channel:
                                # Ch:  0   Z=184.0   (8.7 deg)  OK  at f=31.3 kHz Umag=12.3
                                ch_str = data[i+j]
                                # print('Parsing channel', c, 'with ch_str=', ch_str)

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
                                    # print('in SIS 5 parser, ch_str is', ch_str, ' and -1*len(slot_num)=', -1*len(slot_num))
                                    # in SIS 5 (but not SIS 4), TX Z values > 1000 are logged as, e.g., 1.1k;
                                    # convert 1.1k to 1100 and take last slot_num entries from the channel string
                                    z_temp.append([float(z.replace('k', ''))*1000 if z.find('k') > -1 else
                                                   float(z) for z in ch_str.split()[-1*slot_num:]])
                                    f_temp.append(freq)  # store nominal frequency from get_freq
                                    umag_temp.append(np.nan)  # store NaNs until SIS 5 parser is finished
                                    phase_temp.append(np.nan)  # store NaNs until SIS 5 parser is finished

                                c += 1  # increment channel channel after parsing

                        j += 1  # increment line counter within channel search

                    else:
                        i = i+j  # reset index to end of channel search
                        break

                # reshape the arrays and store
                z_temp = np.array(z_temp)  # SIS 5: keep as array with rows = channels and columns = boards parsed

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

            # ##############################################
            # elif z['model'][i] == '122':
            #     zmin = 50
            #     zmax = 110
            # elif z['model'][i] == '302':
            #     zmin = 75
            #     zmax = 115
            # elif z['model'][i] == '710':
            #     zmin = 40
            #     zmax = 90
            # elif z['model'][i] == '124':
            #     zmin = 50
            #     zmax = 150
            # elif z['model'][i] == '304':
            #     zmin = 50
            #     zmax = 150
            # elif z['model'][i] == '712':
            #     zmin = 35
            #     zmax = 140
            # else:  # unknown model
            #     zmin = 60
            #     zmax = 120

            # get number of TX channels and slots for setting up axis ticks
            n_tx_chans = np.size(z['tx'][i], 0)
            n_tx_slots = np.size(z['tx'][i], 1)
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
                dx_tick = 4
                ax.set_yticks(np.arange(0, n_tx_chans + dy_tick - 1, dy_tick))  # set major axes ticks
                ax.set_xticks(np.concatenate((np.array([0]),
                                              np.arange(3, n_tx_slots + dx_tick - 1, dx_tick))))

                ax.set_yticklabels(np.arange(0, 40, 5), fontsize=16)  # set major axes labels
                ax.set_xticklabels(np.concatenate((np.array([1]), np.arange(4, n_tx_slots+4, 4))), fontsize=16)

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
                dy_tick = 4

                # set major axes ticks for labels
                ax1.set_xticks(np.arange(0, n_tx_chans + dx_tick - 1, dx_tick))
                ax1.set_yticks(np.arange(zmin, zmax+1, 10))
                ax2.set_xticks(np.arange(0, n_tx_chans + dx_tick - 1, dx_tick))
                ax2.set_yticks(np.concatenate((np.array([0]), np.arange(3, n_tx_slots + dy_tick - 1, dy_tick))))

                # set minor axes ticks for gridlines
                ax1.set_xticks(np.arange(0, (n_tx_chans+1), 5), minor=True)
                ax1.set_yticks(np.arange(zmin, zmax+1, 5), minor=True)
                ax2.set_xticks(np.arange(-0.5, (n_tx_chans+0.5), 1), minor=True)
                ax2.set_yticks(np.arange(-0.5, (n_tx_slots+0.5), 1), minor=True)

                # set axis tick labels
                ax1.set_xticklabels(np.arange(0, 40, 5), fontsize=axfsize)
                ax1.set_yticklabels(np.arange(zmin, zmax+1, 10), fontsize=axfsize)  # TX impedance
                ax2.set_xticklabels(np.arange(0, 40, 5), fontsize=axfsize)
                ax2.set_yticklabels(np.concatenate((np.array([1]), np.arange(4, 28, 4))), fontsize=axfsize)  # TX slot

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
    # yrmin = int(min(z['date'])[:4])
    # yrmax = int(max(z['date'])[:4])
    yrs = [str(yr) for yr in range(yrmin, yrmax + 1)]

    # get number of TX channels and slots for setting up axis ticks
    n_tx_chans = np.size(z['tx'][0], 0)
    n_tx_slots = np.size(z['tx'][0], 1)
    n_tx_modules = n_tx_chans*n_tx_slots
    print('found n_tx_chans =', n_tx_chans, 'and n_tx_slots=', n_tx_slots)

    colors = plt.cm.rainbow(np.linspace(0, 1, len(yrs)))  # set up line colors over number of years
    ztx_channel = np.arange(n_tx_chans)  # range of TX channels for plotting (starts at 0)
    ztx_module = np.arange(1, n_tx_modules+1)  # range of RX modules for plotting (unlike channels, this starts at 1)
    # zrx_channel = np.tile(np.arange(0, n_rx_channels), [n_rx_boards, 1])  # array of zrx chans for plotting (start at 0)
    # ztx_channel = np.tile(np.arange(0, n_tx_chans), [n_rx_boards, 1])  # array of zrx chans for plotting (start at 0)

    # set axis and label parameters
    axfsize = 16  # axis font size
    dx_tick = 36
    dy_tick = 10

    print('set of models is: ', set(z['model']))
    print('set of sns is: ', set(z['sn']))

    if z['tx_limits'][0]:
        [zmin, zmax] = z['tx_limits'][0]
        print('got tx z limits parsed from file: ', zmin, zmax)
    else:
        [zmin, zmax] = get_tx_z_limits(model)

    # # set min and max Z limits for model
    # if z['model'][0] == '122':
    #     zmin = 50
    #     zmax = 110
    # elif z['model'][0] == '302':
    #     zmin = 75
    #     zmax = 115
    # elif z['model'][0] == '710':
    #     zmin = 40
    #     zmax = 90
    # else:  # unknown model
    #     zmin = 60
    #     zmax = 120

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
    bist_time_obj = [datetime.datetime.strptime(t.replace('/', '').replace(':', ''), '%Y%m%d%H%M%S')
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
        print('y=', str(y))
        # for i in range(len(z['date'])):
        for i in bist_time_idx:
            print('i=', str(i))
            if z['date'][i][:4] == yrs[y]:  # check if this BIST matches current year
                print('year matches')
                ztx = np.asarray(z['tx'][i])  # n_cols = n_chans, n_rows = n_slots

                if i == bist_time_idx[idx_last]:  # store for final plotting in black if this is most recent data
                    ztx_last = ztx

                # skip if not 32 RX channels (parser err? verify this is the case for all RX xdcr cases)
                if ztx.shape[0] == n_tx_chans:
                    # plot zrx_array history in top subplot, store artist for legend
                    # print('using colors[y]=', colors[y])
                    line, = ax1.plot(ztx_module, ztx.flatten('C'), color=colors[y], linewidth=2)
                    # print('ztx_array.flatten = ', ztx_array.flatten('C'))
                    # line, = ax2.plot(ztx_module, ztx_array.flatten(), color=colors[y], linewidth=2)

                    # add legend artist (line) and label (year) if not already added
                    if yrs[y] not in set(legend_labels):
                    # if len(legend_artists) < len(legend_labels):
                        legend_labels.append(yrs[y])  # store year as label for legend
                        legend_artists.append(line)

                    print('ztx_limits=', ztx_limits)
                    # print('zrx_array_limits=', zrx_array_limits)

                    # define x ticks starting at 1 and running through n_rx_modules, with ticks at dx_tick
                    x_ticks = np.concatenate((np.array([1]), np.arange(dx_tick, n_tx_modules + dx_tick - 1, dx_tick)))
                    y_ticks = np.arange(ztx_limits[0], ztx_limits[1] + 1, dy_tick)

                    # set ylim to parsed spec limits
                    ax1.set_ylim(ztx_limits)

                    # set yticks for labels and minor gridlines
                    ax1.set_yticks(y_ticks)
                    ax1.set_yticks(y_ticks, minor=True)
                    ax1.set_ylabel('Transmitter Impedance (ohms)\n(axis limits = Kongsberg spec.)',
                                   fontsize=axfsize)
                    # ax2.set_yticks(y_ticks_array)
                    # ax2.set_yticks(y_ticks_array, minor=True)
                    # ax2.set_ylabel('Transducer Impedance (ohms)\n(axis limits = Kongsberg spec.)',
                    #                fontsize=axfsize)

                    # if np.all(np.isnan(zrx_array)):  # plot text: no RX array impedance data available in BIST
                    #     ax2.text((n_rx_modules / 2) - 0.5, (zrx_array_limits[1]-zrx_array_limits[0])/2,
                    #              'NO TRANSDUCER RX CHANNELS DATA',
                    #              fontsize=24, color='red', fontweight='bold',
                    #              horizontalalignment='center', verticalalignment='center_baseline')


                    for ax in [ax1]: #, ax2]:  # set xlim and aspect for both axes
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
                    print('Skipping ', z['filename'], ' with ', str(zrx.shape[1]), ' RX and ',
                          str(zrx_array.shape[1]), ' channels instead of 32!')

    if bist_count > 0:
        line, = ax1.plot(ztx_module, ztx_last.flatten('C'), color='k', linewidth=2)
        # line, = ax2.plot(zrx_module, zrx_array_last.flatten(), color='k', linewidth=2)

    legend_artists.append(line)  # add line artist to legend list
    legend_labels.append('Last')

    # set legend
    l1 = ax1.legend(legend_artists, legend_labels,
                    bbox_to_anchor=(1.2, 1), borderaxespad=0,
                    loc='upper right', fontsize=axfsize)
    # l2 = ax2.legend(legend_artists, legend_labels,
    #                 bbox_to_anchor=(1.2, 1), borderaxespad=0,
    #                 loc='upper right', fontsize=axfsize)
    # legend(bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0.)

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
    # set up output dict for impedance data
    rxn = init_bist_dict(3)
    rxn['filename'] = fname
    n_test = 0  # keep track of number of RX Noise tests in this file
    get_speed = False  # do not parse speed until RX Noise header is found (avoid other speeds in SIS 5 file)
    
    try:  # try reading file
        f = open(fname, "r")
        data = f.readlines()

    except ValueError:
        print('***WARNING: Error reading file', fname)

    if len(data) <= 0:  # skip if text file is empty
        print('***WARNING: No data read from file', fname)
        # return ()
        return []
    
    # Check to make sure its not a PU Params or System Report text file (SIS 4)
    if any(substr in data[0] for substr in ["Database", "Datagram", "CPU"]):
        print("***WARNING: Skipping non-BIST file: ", fname)
        # return()
        return []
        
    # try parsing the data for all tests in text file
    try:
        header_str = "RX NOISE LEVEL"  # start of SIS 4 RX Noise test
        ch_hdr_str = "Board No:"  # start of SIS 4 channel data
        footer_str = "Maximum"  # end of SIS 4 RX Noise test

        if sis_version is 5:
            header_str = "RX noise level"  # start of SIS 5 RX Noise test
            ch_hdr_str = "Channel"  # start of SIS 5 channel data
            footer_str = "Summary"  # end of SIS 5 RX Noise test

        speed_str = "Vessel speed:"  # start of SIS 5 speed entry; will not be found in SIS 4

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

        i = 0
        while i < len(data):
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
                                # print('appending', ch_str_data)
                                # print('with type:', type(ch_str_data))
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
            if data[i].find(speed_str) > -1 and get_speed:
                # rxn['speed'] = float(data[i].split()[-2])
                rxn['speed'].append(float(data[i].split()[-2]))  # for SIS 5 with continuous BIST
                rxn['speed_bist'].append(float(data[i].split()[-2]))
                get_speed = False  # do not parse another speed until after RX noise header is found

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


# # plot RX Noise versus speed -- REPLACED BY PLOT_RX_NOISE (generic version)
# def plot_rx_noise_speed(rxn, save_figs, output_dir=os.getcwd(), sort_by=None,
#                         speed=[], speed_unit='SOG (kts)', cmap='jet'):
#     # declare array for plotting all tests with nrows = n_elements and ncols = n_tests
#     # np.size returns number of items if all lists are same length (e.g., AutoBIST script in SIS 4), but returns number
#     # of lists if they have different lengths (e.g., files from SIS 5 continuous BIST recording)
#     # SIS 4 format: shape of rxn[rxn][0] is (10, 32, 4) --> number of tests (10), 32 elements per RX board, 4 boards
#     # SIS 5 format: shape of rxn[rxn][0] is (34, 128, 1) --> number of tests (34), 128 elements per test, 1
#
#     # set up dict of speed axis ticks for given units
#     # speed_ticks = {'SOG (kts)': 2, 'RPM': 20, '% Handle': 10}
#     speed_ticks = {'SOG (kts)': 2, 'RPM': 20, 'Handle (%)': 10, 'Pitch (%)': 10, 'Pitch (deg)': 10}
#
#     # set x ticks and labels on bottom of subplots to match previous MAC figures
#     plt.rcParams['xtick.bottom'] = plt.rcParams['xtick.labelbottom'] = True
#     plt.rcParams['xtick.top'] = plt.rcParams['xtick.labeltop'] = False
#
#     n_elements = np.size(rxn['rxn'][0][0])  # number of elements in first test, regardless of SIS version
#
#     print('rxn[test]=', rxn['test'])
#
#     n_tests = np.size(np.hstack(rxn['test']))  # handle uneven list lengths, e.g., SIS 5 continuous BISTs
#
#     # sort the data by speed (i.e., sorted speeds = [rxn['speed'][x] for x in s])
#     test_all = np.arange(0.0, n_tests, 1.0)
#     print('test_all=', test_all, 'with len=', np.size(test_all))
#
#     print('********* IN PLOTTER with sort_by=', sort_by, 'and speed=', speed)
#     print('n_elements =', n_elements, 'and n_tests=', n_tests)
#
#     if any(speed):  # use custom speed axis if given (e.g., to override speeds parsed from filenames or data)
#         speed_all = np.asarray(speed)
#         print('using custom speed_all=', speed_all)
#
#     else:  # otherwise, use speed parsed from filename for each BIST
#         speed_all = np.array(np.hstack(rxn['speed_bist']))
#
#         # speed_bist is for all tests across all frequencies; if
#         print('using speed_all parsed from files=', speed_all)
#
#     if sort_by == 'speed':  # sort by speed
#         s = np.argsort(speed_all, kind='mergesort')  # use mergesort to avoid random/unrepeatable order for same values
#         speed_all = speed_all[s]  # sort the speeds
#         print('sorted by speed with s=', s, ' and type=', type(s))
#
#     # organize RX Noise tests from all parsed files and speeds into one array for plotting, sorted by speed
#     n_rxn = len(rxn['rxn'])  # number of parsing sessions stored in dict (i.e., num files)
#     rxn_all = np.empty([n_elements, 1])
#     for i in range(n_rxn):  # loop through each parsed set and organize RX noise data into rxn_all for plotting
#         n_tests_local = np.size(rxn['rxn'][i], axis=0)  # number of tests in this parsing session
#         for j in range(n_tests_local):  # reshape data from each test (SIS 4 is 32 x 4, SIS 5 is 128 x 1) into 128 x 1
#             rxn_local = np.reshape(np.transpose(rxn['rxn'][i][j]), [n_elements, -1])
#             rxn_all = np.hstack((rxn_all, rxn_local))  # stack horizontally, column = test number
#
#     # after stacking, remove first empty column and then sort columns by speed
#     print('size rxn_all=', rxn_all.shape)
#     print('before removing first column, rxn_all =', rxn_all)
#     rxn_all = rxn_all[:, 1:]
#
#     print('after removing first column, rxn_all =', rxn_all)
#
#     print('now tring to take just the s=', s, '-th column of rxn_all')
#     rxn_all = rxn_all[:, s]
#
#     # plot the RX Noise data organized for imshow; this will have test num xlabel
#     plt.close('all')
#     axfsize = 16  # uniform axis font size
#     subplot_height_ratio = 4  # top plot will be 1/Nth of total figure height
#
#     fig = plt.figure(figsize=(7, 12))  # set figure size with defined grid for subplots
#     gs = gridspec.GridSpec(2, 1, height_ratios=[1, subplot_height_ratio])  # set grid for subplots with fixed ratios
#
#     # plot speed vs test number
#     ax1 = plt.subplot(gs[0])
#     ax1.plot(test_all, speed_all, 'r*')
#     ax1.set_xlabel('Test Number', fontsize=axfsize)
#     # ax1.set_ylabel('SOG (kts)', fontsize=axfsize)
#     ax1.set_ylabel(speed_unit, fontsize=axfsize)
#
#     # plot rxn vs test number
#     ax2 = plt.subplot(gs[1])
#     im = ax2.imshow(rxn_all, cmap=cmap, aspect='auto', vmin=30, vmax=70,)
#     # im = ax2.imshow(rxn_all, cmap=cmap, aspect='auto', vmin=0, vmax=70,)
#
#     plt.gca().invert_yaxis()  # invert y axis to match previous plots by Paul Johnson
#     ax2.set_xlabel('Test Number', fontsize=axfsize)
#     ax2.set_ylabel('RX Module (index starts at 0)', fontsize=axfsize)
#
#     # set colorbar
#     cbar = fig.colorbar(im, shrink=0.7, orientation='horizontal')
#     cbar.set_label(r'RX Noise (dB re 1 $\mu$Pa/$\sqrt{Hz}$)', fontsize=axfsize)
#     cbar.ax.tick_params(labelsize=14)
#
#     # set x ticks for both plots based on test count - x ticks start at 0, x labels (test num) start at 1
#     x_test_max = np.size(test_all)
#     print('***size of test_all is', np.size(test_all))
#     x_test_max_count = 10
#     x_ticks_round_to = 10
#     dx_test = int(math.ceil(n_tests/x_test_max_count/x_ticks_round_to)*x_ticks_round_to)
#     print('using dx_test = ', dx_test)
#     x_test = np.concatenate((np.array([0]), np.arange(dx_test-1, x_test_max, dx_test)))
#     x_test_labels = np.concatenate((np.array([1]), np.arange(dx_test, x_test_max, dx_test), np.array([x_test_max])))
#
#     # set ticks, labels, and limits for speed plot
#     dy_speed = speed_ticks[speed_unit]  # get dy_tick from input units
#     y_speed_max = np.int(max(speed_all) + dy_speed/2)  # max speed + dy_tick/2 for space on plot
#     y_speed = np.concatenate((np.array([0]), np.arange(dy_speed, y_speed_max+dy_speed-1, dy_speed)))
#     y_speed_labels = [str(y) for y in y_speed.tolist()]
#
#     ax1.set_xlim(-0.5, x_test_max-0.5)  # set xlim to align points with rxn data columns
#     ax1.set_ylim(-0.5, y_speed_max+0.5)  # set ylim to show entire range consistently
#     ax1.set_yticks(y_speed)
#     ax1.set_xticks(x_test)
#     ax1.set_yticklabels(y_speed_labels, fontsize=16)
#     ax1.set_xticklabels(x_test_labels, fontsize=16)
#     ax1.grid(True, which='major', axis='both', linewidth=1, color='k', linestyle='--')
#
#     # set ticks, labels, and limits for noise plot
#     y_module_max = np.size(rxn_all,0)
#     dy_module = 16  # max modules = multiple of 32, dx_tick is same across two subplots
#     y_module = np.concatenate((np.array([0]), np.arange(dy_module-1, y_module_max+dy_module-1, dy_module)))
#     y_module_labels = [str(y) for y in y_module.tolist()]
#     ax2.set_yticks(y_module)
#     ax2.set_xticks(x_test)
#     ax2.set_yticklabels(y_module_labels, fontsize=16)
#     ax2.set_xticklabels(x_test_labels, fontsize=16)
#     ax2.grid(True, which='major', axis='both', linewidth=1, color='k', linestyle='--')
#
#     # set the super title
#     print('sorting out the date string from rxn[date]=', rxn['date'])
#     date_str = rxn['date'][0].replace('/', '-')  # format date string
#     title_str_base = 'RX Noise vs. ' + speed_unit  # ('Speed' if 'Pitch' not in speed_unit else 'Pitch')
#     title_str = title_str_base + '\n' + \
#                 'EM' + rxn['model'][0] + ' (S/N ' + rxn['sn'][0] + ')\n' + \
#                 'Date: ' + date_str + '\n' + \
#                 'Freq: ' + rxn['frequency'][0][0]
#     # title_str = 'RX Noise vs. Speed\n' + \
#     #             'EM' + rxn['model'][0] + ' (S/N ' + rxn['sn'][0] + ')\n' + \
#     #             'Date: ' + date_str + '\n' + \
#     #             'Freq: ' + rxn['frequency'][0][0]
#     fig.suptitle(title_str, fontsize=16)
#
#     # save the figure
#     if save_figs is True:
#         fig = plt.gcf()
# #        fig.set_size_inches(10, 10) # do not change RX Noise figure size before saving
#         freq_str = rxn['frequency'][0][0].replace(' ', '_')
#         speed_unit_base = ''.join('' if c in ['(', ')'] else c for c in speed_unit.lower().replace('%', 'pct'))
#         # test2 = ''.join('' if c in ['(', ')'] else c for c in test)
#         fig_name_base = 'RX_noise_vs_' + speed_unit_base.replace(' ', '_')
#         fig_name = fig_name_base + '_EM' + rxn['model'][0] + \
#                    '_SN_' + rxn['sn'][0] + "_" + date_str.replace('-', '') + \
#                    "_" + freq_str + "_" + cmap + ".png"
#         # fig_name = 'RX_noise_vs_speed_EM' + rxn['model'][0] + \
#         #            '_SN_' + rxn['sn'][0] + "_" + date_str.replace('-','') + \
#         #            "_" + freq_str + ".png"
#         print('Saving', fig_name)
#         fig.savefig(os.path.join(output_dir, fig_name), dpi=100)
#
#     plt.close('all')


# plot RX Noise versus speed or azimuth
def plot_rx_noise(rxn, save_figs, output_dir=os.getcwd(), sort=True, test_type='speed',
                  param=[], param_unit='SOG (kts)', cmap='jet'):
    # declare array for plotting all tests with nrows = n_elements and ncols = n_tests
    # np.size returns number of items if all lists are same length (e.g., AutoBIST script in SIS 4), but returns number
    # of lists if they have different lengths (e.g., files from SIS 5 continuous BIST recording)
    # SIS 4 format: shape of rxn[rxn][0] is (10, 32, 4) --> number of tests (10), 32 elements per RX board, 4 boards
    # SIS 5 format: shape of rxn[rxn][0] is (34, 128, 1) --> number of tests (34), 128 elements per test, 1

    # set up dict of param axis ticks for given units
    print('in plot_rx_noise with test_type', test_type, 'and param_unit', param_unit)

    y_ticks_top = {'SOG (kts)': 2, 'RPM': 20, 'Handle (%)': 10, 'Pitch (%)': 10, 'Pitch (deg)': 10, 'Azimuth (deg)': 45}

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

    elif test_type == 'azimuth':
        print('test type = azimuth --> getting param_all from hstacked rxn[azimuth_bist]')
        param_all = np.array(np.hstack(rxn['azimuth_bist']))

    else:  # test_type == 'standalone':
        param_all = np.arange(0.0, n_tests, 1.0)  # set param_all to simple test number
        print('test type = standalone (or unknown) --> setting param_all equal to 1:n_tests')

    # else:
    #     print('in RX noise plotter, no parameters provided and unknown test type')

    # print('using param_all parsed from files=', param_all)
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

    # sort by test parameter if appropriate
    s = np.arange(len(param_all))  # default sort order as provided
    print('default sort order = s = ', s)
    if sort:
        print('getting sort order for param_all')
        s = np.argsort(param_all, kind='mergesort')  # use mergesort to avoid random/unrepeatable order for same values

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
    y_ticks_top_max = np.int(max(param_all) + dy_ticks_top / 2)  # max speed + dy_tick/2 for space on plot
    y_ticks_top = np.concatenate((np.array([0]),
                                  np.arange(dy_ticks_top, y_ticks_top_max + dy_ticks_top - 1, dy_ticks_top)))

    y_ticks_top_labels = [str(y) for y in y_ticks_top.tolist()]

    ax1.set_xlim(-0.5, x_test_max - 0.5)  # set xlim to align points with rxn data columns
    ax1.set_ylim(-0.5, y_ticks_top_max + 0.5)  # set ylim to show entire range consistently
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
                param_unit_str = param_unit.replace('(', ')').split(')')[1].replace('%', '_pct')
            else:
                param_unit_str = param_unit.strip().replace(' ', '_')  # no (), keep base unit name

            param_str = '_' + str(np.min(param_all)).replace('.', 'p') + \
                        ('-' + str(np.max(param_all)).replace('.', 'p') if np.size(np.unique(param_all)) > 1 else '') +\
                        '_' + param_unit_str
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

    return freq


def init_bist_dict(bist_test_type):
    std_key_list = ['filename', 'model', 'sn', 'date', 'time', 'sis_version', 'frequency', 'ship_name', 'cruise_name']
    bist = {k: [] for k in std_key_list}  # initialize dict with standard info

    if bist_test_type == 1:  # TX Channels
        new_key_list = ['tx', 'umag', 'phase', 'tx_limits']

    elif bist_test_type == 2:  # RX Channels
        new_key_list = ['rx', 'rx_array', 'rx_temp',
                        'rx_limits', 'rx_array_limits', 'rx_temp_limits',
                        'freq_range', 'rx_units', 'rx_array_units']

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

    # NOTE: EM712 BISTs collected in SIS 4 require additional consideration (format is preliminary SIS 5, see SR1701)

    try:  # try reading file
        f = open(fname, "r")
        data = f.readlines()

    except ValueError:
        bist_type.append(0)
        print('***WARNING: Error reading file', fname)

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

        # check SIS 4 test list
        for test_str in SIS4_list:
            if any(test_str in substr for substr in data):
                SIS_version = 4
                bist_type.append(SIS4_list.index(test_str)+1)  # add index in SIS#_list+1 corresponding to BIST_list

        if not bist_type:  # no SIS 4 formats found; check SIS 5 list
            for test_str in SIS5_list:
                if any(test_str in substr for substr in data):
                    SIS_version = 5
                    bist_type.append(SIS5_list.index(test_str) + 1)

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

    if sis_version == 4:  # look for SIS 4 system info (example below)
        print('checking system info for SIS 4, fname=', fname)
        # Saved: 2014.08.28 18:28:42
        # Sounder Type: 302, Serial no.: 101

        for i in range(len(data)):
            if data[i].find("Saved: ") > -1:  # find the save date and time
                time_str = data[i][7:].rstrip()
                sys_info['date'] = time_str[0:time_str.find(" ")].replace(".", "/")  # yyyy/mm/dd for comparison with user entry
                sys_info['time'] = time_str[time_str.find(" ") + 1:]  # hh:mm:ss

            if data[i].find("Sounder Type: ") > -1:  # find sounder model
                em = data[i]
                sys_info['model'] = em[em.find(":")+3:em.find(",")].rstrip()
                sys_info['sn'] = em[em.rfind(":")+3:].rstrip()


    if sis_version == 5:  # look for SIS 5 system info (example above)
        print('checking system info for SIS 5, fname=', fname)
        # --------------20200125-112229-15-Passed-EM304_60-Software-date-and-versions----EM-304.txt--------------
        header_str = '--------------'
        i = 0
        while i < len(data):
            if data[i].find(header_str) > -1:  # if header is found, start parsing
                temp_str = data[i].replace('-','').strip()  # remove all dashes
                sys_info['date'] = temp_str[0:4] + '/' + temp_str[4:6] + '/' + temp_str[6:8]
                sys_info['time'] = temp_str[8:10] + ':' + temp_str[10:12] + ':' + temp_str[12:14]
                sys_info['model'] = temp_str[temp_str.find('EM')+2:temp_str.find('_')]
                sys_info['sn'] = -1  # need to consider; some BISTs have PU sn, some have array sns
                temp_str = temp_str[temp_str.find('_') + 1:]  # shorten to portion of string after 'EM###_'
                sn_end = re.search(r'\D', temp_str)
                sys_info['sn'] = temp_str[:sn_end.start(0)]  # cut off at first non-digit in sn string
                print('storing SIS 5 serial number from BIST header (may actually be last two digits of IP address)')
                break

            else:
                i += 1

        # SIS 5 header line serial number is actually last two digits of IP address; search for PU serial number
        pu_str = 'PU serial:'
        i = 0
        while i < len(data):
            if data[i].find(pu_str) > -1:
                sys_info['sn'] = data[i].split(pu_str)[1].strip()  # store serial number string
                print('updating serial number to PU serial number = ', sys_info['sn'])
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
