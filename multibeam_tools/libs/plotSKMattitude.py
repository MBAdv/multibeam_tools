# simple plotter for SKM datagrams: attitude and attitude velocity

import os

try:
    from PySide2 import QtWidgets, QtGui
    from PySide2.QtGui import QDoubleValidator
    from PySide2.QtCore import Qt, QSize
except ImportError as e:
    print(e)
    from PyQt5 import QtWidgets, QtGui
    from PyQt5.QtGui import QDoubleValidator
    from PyQt5.QtCore import Qt, QSize

import matplotlib.pyplot as plt
from kmall.KMALL import kmall


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
			# print('got dg_offsets = ', dg_offsets)

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

pathname = 'C:/Users/kjerram/Desktop/OKEANOS EXPLORER/EX2309/EM304 troubleshooting/'
# filenames = ['0011_20230108_043302_ATLANTIS_TESTING.kmall']  # short file for quick testing
# filenames = ['0011_20230108_043302_ATLANTIS_TESTING.kmall', '0011_20230108_043302_ATLANTIS_TESTING.kmall']

filenames = ['0016_20231201_130039_EX2309_MB.kmall',
			 '0017_20231201_140039_EX2309_MB.kmall',
			 '0018_20231201_142837_EX2309_MB.kmall']

# filename = 'C:/Users/kjerram/Desktop/OKEANOS EXPLORER/EX2309/EM304 troubleshooting/0016_20231201_130039_EX2309_MB.kmall'

# Future: GUI to select files
# ftype_filter = 'Kongsberg KMALL (*.kmall)'
# fnames = QtWidgets.QFileDialog.getOpenFileNames(self, 'Open files...', os.getenv('HOME'), ftype_filter)
# fnames = fnames[0]  # keep only the filenames in first list item returned from getOpenFileNames

for f in range(len(filenames)):
	fname = os.path.join(pathname, filenames[f])

	km = kmall_data(fname)  # kmall_data class inheriting kmall class and adding extract_dg method
	km.index_file()
	km.report_packet_types()
	km.extract_dg('SKM')
	km.closeFile()

	# concatenate datetime and roll rate
	num_SKM = len(km.skm['sample'])
	SKM_header_datetime = [km.skm['header'][j]['dgdatetime'] for j in range(num_SKM)]
	SKM_sample_datetime = [km.skm['sample'][j]['KMdefault']['datetime'][0] for j in range(num_SKM)]

	if f == 0:
		SKM_sample_time = []
		SKM_sample_roll = []
		SKM_sample_roll_rate = []

	for j in range(num_SKM):
		SKM_sample_time.extend(km.skm['sample'][j]['KMdefault']['datetime'])
		SKM_sample_roll.extend(km.skm['sample'][j]['KMdefault']['roll_deg'])
		SKM_sample_roll_rate.extend(km.skm['sample'][j]['KMdefault']['rollRate'])

	print('survived with datetime / roll_rate lengths: ', len(SKM_sample_time), len(SKM_sample_roll_rate))

# make a plot of all the data
plt.plot(SKM_sample_time, SKM_sample_roll, 'r', label='Roll (deg)', linewidth=1)
plt.plot(SKM_sample_time, SKM_sample_roll_rate, 'b', label='Roll rate (deg/s)', linewidth=1)

plt.title('SKM Datagram: Roll Rate (deg/s)')
plt.grid(axis='both', which='minor')
plt.grid(axis='both', which='major')
plt.legend(loc="upper left")
plt.show()
