def parseZTX2(fname, SISversion=int(4)):
    Z = init_BIST_dict(1)  # set up TX Channels Z dict
    found_channels = False

    try:  # try reading file
        f = open(fname, "r")
        data = f.readlines()

    except ValueError:
        print('***WARNING: Error reading file', fname)

    if len(data) <= 0:  # skip if text file is empty
        print('***WARNING: No data read from file', fname)
        return ()

    # Check to make sure its not a PU Params or System Report text file
    if any(substr in data[0] for substr in ["Database", "Datagram", "CPU"]):
        print("***WARNING: Skipping non-BIST file: ", fname)
        return ()

    try:  # try parsing the data for all tests in text file
        header_str = ["Transmitter impedance rack:"]  # start of SIS 4 TX Channels test
        ch_hdr_str = "Ch:"  # start of SIS 4 channel data

        if SISversion is 5:
            header_str = ["TX channels", "Impedance limits"]  # strings before each batch of TX Z channel data in SIS 5
            ch_hdr_str = "Ch"  # start of SIS 5 channel data
            limit_str = "Impedance limits"  # start of impedance limit data; also repeats before each iteration of TX Z
            model_str = "EM"  # start of model number (within header str)

        i = 0
        while i < len(data):  # step through file and store channel data when found
            if any(substr in data[i] for substr in header_str):  # find any TX Z header strings preceding ch. data
                temp_str = data[i]

                if SISversion == 4:  # SIS 4: get rack and slot version from header
                    rack_num = temp_str[temp_str.find(":") + 1:temp_str.find(":") + 4]
                    rack_num = int(rack_num.strip().rstrip())
                    slot_num = temp_str[temp_str.rfind(":") + 1:temp_str.rfind("\n")]
                    slot_num = int(slot_num.strip().rstrip()) - 1  # subtract 1 for python indexing

                else:  # SIS 5: get slot numbers for SIS 5 (e.g., 36 rows = 36 channels, 10 columns = 10 slots/boards)
                    if temp_str.find(model_str) > -1:  # check for model_str in TX channels header, get number after EM
                        model_num = temp_str[temp_str.rfind(model_str)+2:].strip()
                        Z['model'] = model_num

                        if model_num.find('2040') > -1:  # no numeric TX Z data in EM2040 BISTs; return empty
                            return []

                        else:  # for SIS 5, store mean frequency for this model (not explicitly stated in BIST)
                            freq_str = getEMfreq(model_num)  # get nominal
                            freq = np.mean([float(n) for n in freq_str.replace('kHz', '').strip().split('-')])

                    while data[i].find(limit_str) == -1:  # loop until impedance limits string is found
                        i += 1
                    temp_str = data[i]
                    # z_limits = temp_str[temp_str.find('[')+1:temp_str.rfind(']')]  # FUTURE: store limits for plot cbar
                    # print('found z_limits=', z_limits)

                while data[i].find(ch_hdr_str) == -1:  # loop until channel info header is found (SIS5 has whitespace)
                    if SISversion == 5 and len(data[i].split()) > 0:  # SIS 5 format includes row of slot/board numbers
                        slot_num = len(data[i].split())  # slot_num is slot count in row for SIS 5; slot ID for SIS 4
                        rack_num = 9999  # placeholder for print statements for SIS 5, parsed for SIS 4
                    i += 1

                # print('TRYING to parse rack', rack_num, ' slot number (SIS4) / slot count (SIS5)', slot_num)
                # print('found TX Z channel header=', ch_hdr_str, ' on line i =', i)

                # channel header string is found; start to read channels
                j = 0  # reset line counter while reading channels
                c = 0  # reset channel counter

                Z_temp = []
                phase_temp = []
                f_temp = []
                Umag_temp = []

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

                                if SISversion == 4:
                                    Z_temp.append(float(ch_str[ch_str.find("Z=") + 2:ch_str.find("(")].strip().rstrip()))  # parse impedance
                                    f_temp.append(float(ch_str[ch_str.find("f=") + 2:ch_str.find("kHz")].strip().rstrip()))  # parse frequency
                                    Umag_temp.append(float(ch_str[ch_str.rfind("=") + 1:].strip().rstrip()))  # parse Umag
                                    phase_temp.append(float(ch_str[ch_str.find("(") + 1:ch_str.find("deg")].strip().rstrip()))  # parse impedance phase

                                else:  # SIS 5: each /row includes N_slots of Z data for each channel
                                    # store Z for all boards (e.g., 10 entries in "Ch  1  96.6  93.9 .....  93.0"
                                    # print('in SIS 5 parser, ch_str is', ch_str, ' and -1*len(slot_num)=', -1*len(slot_num))
                                    # in SIS 5 (but not SIS 4), TX Z values > 1000 are logged as, e.g., 1.1k;
                                    # convert 1.1k to 1100 and take last slot_num entries from the channel string
                                    Z_temp.append([float(z.replace('k', ''))*1000 if z.find('k') > -1 else
                                                   float(z) for z in ch_str.split()[-1*slot_num:]])
                                    f_temp.append(freq)  # store nominal frequency from getEMfreq
                                    Umag_temp.append(np.nan)  # store NaNs until SIS 5 parser is finished
                                    phase_temp.append(np.nan)  # store NaNs until SIS 5 parser is finished

                                c += 1  # increment channel channel after parsing

                        j += 1  # increment line counter

                    else:
                        i = i+j  # reset index to end of channel search (use j counter to handle whitespace between ch)
                        break

                # reshape the arrays and store
                Z_temp = np.array(Z_temp)  # SIS 5: keep as array with rows = channels and columns = boards parsed

                if SISversion == 4:  # SIS 4: reshape into rows = channels for single board parsed so far
                    Z_temp = Z_temp.reshape(len(Z_temp), 1)

                f_temp = np.array(f_temp).reshape(len(f_temp), 1)
                Umag_temp = np.array(Umag_temp).reshape(len(Umag_temp), 1)
                phase_temp = np.array(phase_temp).reshape(len(phase_temp), 1)

                if found_channels is False:  # initiate storage (unknown number of channels until now)
                    ZTX = Z_temp
                    FTX = f_temp
                    UTX = Umag_temp
                    PTX = phase_temp
                    found_channels = True

                else:  # concatenate new Z_temp onto ZTX array
                    ZTX = np.concatenate((ZTX, Z_temp), axis=1)
                    FTX = np.concatenate((FTX, f_temp), axis=1)
                    UTX = np.concatenate((UTX, Umag_temp), axis=1)
                    PTX = np.concatenate((PTX, phase_temp), axis=1)
                    continue

            else:
                i += 1  # increment to next line if TX Z not found
                continue

        if found_channels is True:
            # set up output dict for impedance data
            Z['filename'] = fname
            Z['TX'] = ZTX
            Z['frequency'] = FTX
            Z['Umag'] = UTX
            Z['phase'] = PTX

            return Z
        else:
            print('No Z TX data found in file', fname)
            return []

    except ValueError:
        print('***WARNING: Error parsing TX Z in', fname)

    return []
