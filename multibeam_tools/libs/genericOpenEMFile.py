
# testing just to see what the RX DET INFO field is... does it tell us if Lambert's Law option
# was checked in Runtime Parameters?

import struct
import multibeam_tools.libs.readEM
from tkinter import filedialog

fnames = filedialog.askopenfilenames(filetypes=[("Kongsberg .all files", "*.all")])

data = {}

for f in range(len(fnames)):
    data[f] = multibeam_tools.libs.readEM.parseEMfile(fnames[f],
                                                    parse_list = [88,89],
                                                    print_updates = True,
                                                    parse_outermost_only = False)

    print(data[f].keys())

    # print(data[f]['SBI'][0]['TVG_CROSSOVER'])
    # print(data[f]['XYZ'][0]['RX_DET_INFO'])

    for p in range(len(data[f]['XYZ'])):
        data[f]['XYZ'][p]['MODE'] = data[f]['RTP'][0]['MODE']

data = multibeam_tools.libs.readEM.interpretMode(data)

for f in range(len(data)):
    # print(fnames[f], 'has ping mode', data[f]['XYZ'][0]['PING_MODE'])

    print(fnames[f].split('/')[-1], 'starts in mode', data[f]['XYZ'][0]['PING_MODE'],
          'with TVG crossover angle', data[f]['XYZ'][0]['TVG_CROSSOVER'])
    # for i in range(len(data['SBI'])):
    #     print('the TVG crossover angle in ping', i, 'is')
    #     print(data['SBI'][i]['TVG_CROSSOVER'])


    # for i in range(len(data['XYZ'])):
    #     print('the first RX_DET_INFO entry in ping', i, 'is')
        # print(data['XYZ'][i]['RX_DET_INFO'][0])

        # byte = data['XYZ'][i]['RX_DET_INFO'][0]
        # # convert the byte to an integer representation
        # byte = ord(byte)
        # # now convert to string of 1s and 0s
        # byte = bin(byte)[2:].rjust(8, '0')
        # # now byte contains a string with 0s and 1s
        # for bit in byte:
        #     print bit