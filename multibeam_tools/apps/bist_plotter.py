# -*- coding: utf-8 -*-
"""
Created on Sat Sep 15 13:30:15 2018
@author: kjerram

Multibeam Echosounder Assessment Toolkit: Kongsberg BIST plotter

Read Kongsberg Built-In Self-Test (BIST) files for assessing
EM multibeam system performance and hardware health.

Note: this was developed primarily using EM302, EM710, and EM122 BIST files in SIS 4 format;
other formats and features will require additional work

N_RX_boards is typically 4; in some cases, this will be 2; this is currently set
manually, and will eventually be detected automatically.

EM2040 RX Noise BIST files may include columns corresponding to frequency, not RX board;
additional development is needed to handle this smoothly, especially between SIS 4 and SIS 5 formats.

Some factory limits for 'acceptable' BIST levels are parsed from the text file; limits for
RX impedance are not automatically detected; these can be found in the BIST text file and
manually adjusted in the plot_rx_z function in read_bist.py (or GUI as feature is added):

                # declare standard spec impedance limits
                RXrecmin = 600
                RXrecmax = 1000
                RXxdcrmin = 250
                RXxdcrmax = 1200

All impedance tests are meant as proxies for hardware health and not as replacement
for direct measurement with Kongsberg tools.

self.BIST_list = ["N/A or non-BIST", "TX Channels Z", "RX Channels Z", "RX Noise Level", "RX Noise Spectrum"]

- Test 1: TX Channels Impedance - plot impedance of TX channels at the transducer,
measured through the TRU with the TX Channels Impedance BIST. Input is a text file
saved from a telnet session running all TX Channels BISTs for the system (these
results are not saved to text file when running BISTs in the SIS interface).

- Test 1: RX Channels Impedance - plot impedance of RX channels measured at the
receiver (upper plot) and at the transducer (lower plot, measured through the receiver).
Input is a standard BIST text file saved from the Kongsberg SIS interface.

- Test 3: RX Noise - plot noise levels perceived by the RX system across all channels.
Input is a RX Noise BIST text file, ideally with multiple (10-20) BISTs saved to
one text file.  Each text file should correspond to the RX noise conditions of interest.
For instance, vessel-borne noise can be assessed across a range of speeds by running
10-20 BISTs at each speed, holding a constant heading at each, and logging one text
file per speed.  Individual tests may be compromised by transient noises, such as
swell hitting the hull; increasing test count will help to reduce the impact of
these events on the average noise plots.

- Test 4: RX Spectrum - similar to Test 3 (RX Noise) plotting, with RX Spectrum BIST
data collected at different speeds and headings

Additional development is pending to handle the various speed/heading options for
multiple RX Noise/Spectrum tests


"""
try:
    from PySide2 import QtWidgets, QtGui
    from PySide2.QtGui import QDoubleValidator
    from PySide2.QtCore import Qt, QSize, QEvent
except ImportError as e:
    print(e)
    from PyQt5 import QtWidgets, QtGui
    from PyQt5.QtGui import QDoubleValidator
    from PyQt5.QtCore import Qt, QSize, QEvent
import os
import sys
import datetime
# import multibeam_tools.libs.readBIST
import multibeam_tools.libs.read_bist
import numpy as np
import copy
import itertools
import re
from multibeam_tools.libs.gui_widgets import *
from multibeam_tools.libs.file_fun import remove_files


__version__ = "0.2.3"  # PENDING: now handles missing TX Channels data; FUTURE: handle multiple TX Channels per file
# __version__ = "9.9.9"


class MainWindow(QtWidgets.QMainWindow):
    media_path = os.path.join(os.path.dirname(__file__), "media")

    def __init__(self, parent=None):
        super(MainWindow, self).__init__()

        # set up main window
        self.mainWidget = QtWidgets.QWidget(self)
        self.setCentralWidget(self.mainWidget)
        self.setMinimumWidth(850)
        self.setMinimumHeight(850)
        self.setWindowTitle('BIST Plotter v.%s' % __version__)
        self.setWindowIcon(QtGui.QIcon(os.path.join(self.media_path, "icon.png")))

        if os.name == 'nt':  # necessary to explicitly set taskbar icon
            import ctypes
            current_app_id = 'MAC.BISTPlotter.' + __version__  # arbitrary string
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(current_app_id)

        # initialize other necessities
        self.filenames = ['']
        self.input_dir = ''
        self.output_dir = os.getcwd()
        self.missing_fields = []
        self.conflicting_fields = []
        self.model_updated = False
        self.sn_updated = False
        self.date_updated = False
        self.warn_user = True
        self.param_list = []

        self.noise_params = {'SOG (kt)': '_08_kts',
                             'STW (kt)': '_08_kts',
                             'RPM': '_100_RPM',
                             'Handle (%)': '_50_pct',
                             'Pitch (%)': '_50_pct',
                             'Pitch (deg)': '_30_deg',
                             'Azimuth (deg)': '_045T_270S'}

        self.default_prm_str = '_08_kts'
        self.prm_unit_cbox_last_index = 0
        self.prm_str_tb_last_text = '_08_kts'
        self.gb_toggle = True
        self.file_into_seas_str = '(INTO SEAS)'
        self.swell_dir_updated = False
        self.swell_dir_default = '999'
        self.swell_dir_message = True
        self.current_default = '0'

        # list of available test types; RX Noise is only available vs. speed, not heading at present
        # RX Noise Spectrum is not available yet; update accordingly
        self.bist_list = ["N/A or non-BIST", "TX Channels Z", "RX Channels Z", "RX Noise Level", "RX Noise Spectrum"]

        # set up layouts of main window
        self.set_left_layout()
        self.set_right_layout()
        self.set_main_layout()

        # enable initial tab/input states and custom speed list
        self.update_buttons()
        self.update_param_info()

        # set up file control actions
        self.add_file_btn.clicked.connect(lambda: self.add_files('Kongsberg BIST .txt(*.txt)'))
        self.get_indir_btn.clicked.connect(self.get_input_dir)
        self.get_outdir_btn.clicked.connect(self.get_output_dir)
        self.rmv_file_btn.clicked.connect(self.remove_bist_files)
        self.clr_file_btn.clicked.connect(lambda: self.remove_bist_files(clear_all=True))
        self.show_path_chk.stateChanged.connect(self.show_file_paths)

        # set up BIST selection and plotting actions
        self.select_type_btn.clicked.connect(self.select_bist)
        self.clear_type_btn.clicked.connect(self.clear_bist)
        # self.verify_bist_btn.clicked.connect(self.verify_system_info)
        self.plot_bist_btn.clicked.connect(self.plot_bist)
        # self.custom_info_chk.stateChanged(self.custom_info_gb.setEnabled(self.custom_info_chk.isChecked()))

        # set up user system info actions
        self.model_cbox.activated.connect(self.update_system_info)
        self.sn_tb.textChanged.connect(self.update_system_info)
        self.ship_tb.textChanged.connect(self.update_system_info)
        self.date_tb.textChanged.connect(self.update_system_info)
        self.warn_user_chk.stateChanged.connect(self.verify_system_info)

        self.type_cbox.activated.connect(self.update_buttons)
        self.noise_test_type_cbox.activated.connect(self.update_buttons)
        # self.prm_unit_cbox.activated.connect(self.update_buttons)
        self.prm_unit_cbox.activated.connect(self.update_noise_param_unit)
        self.prm_str_tb.textChanged.connect(self.update_noise_param_string)

        self.parse_test_params_gb.clicked.connect(self.update_groupboxes)
        self.custom_param_gb.clicked.connect(self.update_groupboxes)

        self.prm_min_tb.textChanged.connect(self.update_param_info)
        self.prm_max_tb.textChanged.connect(self.update_param_info)
        self.prm_int_tb.textChanged.connect(self.update_param_info)
        self.num_tests_tb.textChanged.connect(self.update_param_info)

    def set_right_layout(self):
        # set layout with file controls on right, sources on left, and progress log on bottom
        btnh = 20  # height of file control button
        btnw = 110  # width of file control button

        # set the custom info control buttons
        self.sys_info_lbl = QtWidgets.QLabel('Default: any info in BIST will be used;'
                                             '\nmissing fields require user input')

        self.warn_user_chk = CheckBox('Check selected files for missing\nor conflicting system info',
                                      True, 'warn_user_chk',
                                      'Turn off warnings only if you are certain the system info is consistent')

        self.sys_info_lbl.setStyleSheet('font: 8pt')
        model_tb_lbl = Label('Model:', 100, 20, 'model_tb_lbl', (Qt.AlignRight | Qt.AlignVCenter))
        self.model_cbox = ComboBox(['EM 2040', 'EM 302', 'EM 304', 'EM 710', 'EM 712', 'EM 122', 'EM 124'],
                                   100, 20, 'model', 'Select the EM model (required)')
        model_info_layout = BoxLayout([model_tb_lbl, self.model_cbox], 'h')

        sn_tb_lbl = Label('Serial No.:', 100, 20, 'sn_tb_lbl', (Qt.AlignRight | Qt.AlignVCenter))
        self.sn_tb = LineEdit('999', 100, 20, 'sn', 'Enter the serial number (required)')
        sn_info_layout = BoxLayout([sn_tb_lbl, self.sn_tb], 'h')

        ship_tb_lbl = Label('Ship Name:', 100, 20, 'ship_tb_lbl', (Qt.AlignRight | Qt.AlignVCenter))
        self.ship_tb = LineEdit('R/V Unsinkable II', 100, 20, 'ship', 'Enter the ship name (optional)')
        ship_info_layout = BoxLayout([ship_tb_lbl, self.ship_tb], 'h')

        cruise_tb_lbl = Label('Cruise Name:', 100, 20, 'cruise_tb_lbl', (Qt.AlignRight | Qt.AlignVCenter))
        self.cruise_tb = LineEdit('A 3-hour tour', 100, 20, 'cruise_name', 'Enter the cruise name (optional)')
        cruise_info_layout = BoxLayout([cruise_tb_lbl, self.cruise_tb], 'h')

        date_tb_lbl = Label('Date (yyyy/mm/dd):', 115, 20, 'date_tb_lbl', (Qt.AlignRight | Qt.AlignVCenter))
        self.date_tb = LineEdit('yyyy/mm/dd', 75, 20, 'date', 'Enter the date (required; BISTs over multiple days will '
                                                              'use dates in files, if available)')
        date_info_layout = BoxLayout([date_tb_lbl, self.date_tb], 'h')

        # set the custom info button layout
        custom_info_layout = BoxLayout([self.sys_info_lbl, model_info_layout, sn_info_layout, ship_info_layout,
                                        cruise_info_layout, date_info_layout, self.warn_user_chk], 'v')

        # set the custom info groupbox
        self.custom_info_gb = QtWidgets.QGroupBox('System Information')
        self.custom_info_gb.setLayout(custom_info_layout)
        self.custom_info_gb.setFixedWidth(200)

        # add file control buttons and file list
        self.add_file_btn = PushButton('Add Files', btnw, btnh, 'add_files', 'Add BIST .txt files')
        self.get_indir_btn = PushButton('Add Directory', btnw, btnh, 'add_dir',
                                        'Add a directory with BIST .txt files')
        self.include_subdir_chk = CheckBox('Include subdirectories', True, 'include_subdir_chk',
                                           'Include subdirectories when adding a directory')
        self.get_outdir_btn = PushButton('Select Output Dir.', btnw, btnh, 'get_outdir',
                                         'Select the output directory (see current output directory below)')
        self.rmv_file_btn = PushButton('Remove Selected', btnw, btnh, 'rmv_files', 'Remove selected files')
        self.clr_file_btn = PushButton('Remove All Files', btnw, btnh, 'clr_file_btn', 'Remove all files')
        self.show_path_chk = CheckBox('Show file paths', False, 'show_paths_chk', 'Show paths in file list')
        self.open_outdir_chk = CheckBox('Open folder after plotting', True, 'open_outdir_chk',
                                        'Open the output directory after plotting')

        # set the file control button layout
        file_btn_layout = BoxLayout([self.add_file_btn, self.get_indir_btn, self.get_outdir_btn,
                                     self.rmv_file_btn, self.clr_file_btn, self.include_subdir_chk,
                                     self.show_path_chk, self.open_outdir_chk], 'v')

        # set the BIST selection buttons
        lblw = 60
        lblh = 20
        type_cbox_lbl = Label('Select BIST:', lblw, lblh, 'type_cbox_lbl', (Qt.AlignRight | Qt.AlignVCenter))
        type_cbox_lbl.setFixedWidth(lblw)
        self.type_cbox = ComboBox(self.bist_list[1:-1], 100, btnh, 'bist_cbox',
                                  'Select a BIST type for file verification and plotting')
        bist_type_layout = BoxLayout([type_cbox_lbl, self.type_cbox], 'h', add_stretch=True)

        noise_test_type_lbl = Label('Plot noise:', lblw, lblh, 'noise_type_lbl', (Qt.AlignRight | Qt.AlignVCenter))
        noise_test_type_lbl.setFixedWidth(lblw)
        # noise_test_type_list = ['vs. Speed', 'vs. Azimuth', 'Standalone']
        noise_test_type_list = ['vs. Speed', 'vs. Azimuth']
        self.noise_test_type_cbox = ComboBox(noise_test_type_list, 85, btnh, 'noise_test_cbox',
                                             'Select a noise test type:'
                                             '\nNoise vs. speed (e.g., 0-10 kts; see Speed tab for options)'
                                             '\nNoise vs. azimuth (e.g., heading relative to prevailing swell)'
                                             '\n or Standalone (e.g., dockside or machinery testing)')
        self.noise_test_type_cbox.setEnabled(False)
        noise_type_layout = BoxLayout([noise_test_type_lbl, self.noise_test_type_cbox], 'h', add_stretch=True)

        cmap_lbl = Label('Colormap:', lblw, lblh, 'cmap_lbl', (Qt.AlignRight | Qt.AlignVCenter))
        cmap_lbl.setFixedWidth(lblw)
        self.cmap_cbox = ComboBox(['Inferno', 'Hot', 'Jet'], 70, btnh, 'cmap_cbox', 'Select desired colormap')
        cmap_layout = BoxLayout([cmap_lbl, self.cmap_cbox], 'h', add_stretch=True)

        self.select_type_btn = PushButton('Select BISTs', btnw, btnh, 'select_type',
                                          'Filter and select source files by the chosen BIST type')
        self.clear_type_btn = PushButton('Clear Selected', btnw, btnh, 'clear_type', 'Clear file selection')
        self.plot_bist_btn = PushButton('Plot Selected', btnw, btnh, 'plot_bist',
                                        'Plot selected, verified files (using current system information above, '
                                        'if not available in BIST)')

        # set the BIST options layout
        plot_btn_layout = BoxLayout([bist_type_layout, noise_type_layout, cmap_layout,
                                     self.select_type_btn, self.clear_type_btn, self.plot_bist_btn], 'v')

        # set RX noise test parameters
        prm_unit_lbl = Label('Test units:', 110, 20, 'prm_unit_lbl', (Qt.AlignRight | Qt.AlignVCenter))
        # self.prm_unit_cbox = ComboBox(['SOG (kts)', 'RPM', 'Handle (%)', 'Pitch (%)', 'Pitch (deg)', 'Azimuth (deg)'],
        #                               90, 20, 'prm_unit_cbox', 'Select the test units')
        self.prm_unit_cbox = ComboBox([prm for prm in self.noise_params.keys()],
                                      90, 20, 'prm_unit_cbox', 'Select the test units\n\n'
                                                               'SOG: Speed Over Ground\n'
                                                               'STW: Speed Through Water\n'
                                                               'RPM: Rotations Per Minute\n')
        prm_unit_layout = BoxLayout([prm_unit_lbl, self.prm_unit_cbox], 'h')
        # self.prm_unit_gb = GroupBox('Noise testing', prm_unit_layout, False, False, 'prm_unit_gb')

        # set parameter plot limits
        self.prm_plot_min_tb = LineEdit('0', 40, 20, 'prm_plot_min_tb', 'Enter the parameter plot Y-axis minimum')
        self.prm_plot_max_tb = LineEdit('10', 40, 20, 'prm_plot_max_tb', 'Enter the parameter plot Y-axis maximum')
        prm_plot_min_lbl = Label('Min:', 20, 20, 'prm_plot_min_lbl', (Qt.AlignLeft | Qt.AlignVCenter))
        prm_plot_max_lbl = Label('Max:', 20, 20, 'prm_plot_max_lbl', (Qt.AlignLeft | Qt.AlignVCenter))
        prm_plot_lim_layout = BoxLayout([prm_plot_min_lbl, self.prm_plot_min_tb,
                                         prm_plot_max_lbl, self.prm_plot_max_tb], 'h')

        self.prm_plot_lim_gb = GroupBox('Set test param plot limits', prm_plot_lim_layout,
                                        True, False, 'parse_test_params_gb')

        self.prm_plot_lim_gb.setToolTip('Set the minimum and maximum parameters for plotting\n\n'
                                        'This creates consistent axes for test params aross data sets with '
                                        'different min/max values (e.g., speeds going into seas vs. with seas')

        # set options for getting RX Noise vs speed string from filename, custom speed vector, and/or sorting
        # prm_str_tb_lbl = Label('Filename speed string:', 120, 20, 'prm_str_tb_lbl', (Qt.AlignRight | Qt.AlignVCenter))
        prm_str_tb_lbl = Label('Filename string:', 120, 20, 'prm_str_tb_lbl', (Qt.AlignRight | Qt.AlignVCenter))
        self.prm_str_tb = LineEdit(self.default_prm_str, 65, 20, 'prm_str_tb',
                                   'Enter an example string for the test parameter recorded in the filename (e.g., '
                                   '"_08_kts", "_045_deg", "_pitch_30_pct") for each BIST text file. This string is '
                                   'used only to search for the format of the test parameter in the filename.\n\n'
                                   'Note that heading/azimuth tests require specific formatting for the heading and '
                                   'swell direction (follow direction in log and/or pop-up message).'
                                   '\n\nThe user will be warned if the test parameter cannot be parsed for all files. '
                                   'Using a consistent filename format will help greatly.'
                                   '\n\nNotes for speed testing:'
                                   '\n\nSIS 4 RX Noise BISTs do not include speed, so the user must note the test speed '
                                   'in the text filename, e.g., default naming of "BIST_FILE_NAME_02_kt.txt" or '
                                   '"_120_RPM.txt", etc. '
                                   '\n\nSIS 5 BISTs include speed over ground, which is parsed and used by default, '
                                   'if available. The user may assign a custom speed list in any case if speed is not '
                                   'available in the filename or applicable for the desired plot.')
        prm_str_layout = BoxLayout([prm_str_tb_lbl, self.prm_str_tb], 'h')

        # set current text input for converting SOG to STW
        self.current_tb = LineEdit(self.current_default, 15, 20, 'current_tb',
                                     'Enter the apparent current magnitude (kt, along the ship heading) and '
                                     'select the direction (with or against the ship) during testing\n\n'
                                     'This will be used to convert speed over ground (SOG, parsed from file or file '
                                     'name) to speed through water (STW) for plotting\n\n'
                                     'NOTE: Tests collected with and against the current should be plotted separately')
        self.current_tb.setEnabled(False)
        current_lbl = Label('Current (kt):', 20, 20, 'current_lbl', (Qt.AlignRight | Qt.AlignVCenter))
        self.current_dir_cbox = ComboBox(['with ship', 'against ship'], 80, 20, 'current_dir_cbox',
                                         'Select the direction of the apparent current\n\n'
                                         '"With ship" means the ship is being aided by the current (SOG > STW)\n'
                                         '"Against ship" means the ship is fighting the current (SOG < STW)')
        self.current_dir_cbox.setEnabled(False)
        current_layout = BoxLayout([current_lbl, self.current_tb, self.current_dir_cbox], 'h')

        # set swell direction text input
        self.swell_dir_tb = LineEdit(self.swell_dir_default, 40, 20, 'swell_dir_tb',
                                     'Enter the swell direction (degrees, compass direction from which the prevailing seas are '
                                     'coming)\n\n'
                                     'For instance, swell coming from the northeast would be entered as 45 deg')
        self.swell_dir_tb.setEnabled(False)

        swell_dir_lbl = Label('Swell direction (deg):', 120, 20, 'swell_dir_lbl', (Qt.AlignRight | Qt.AlignVCenter))
        swell_dir_layout = BoxLayout([swell_dir_lbl, self.swell_dir_tb], 'h')

        sort_order_lbl = Label('Sort order:', 120, 20, 'sort_order_lbl', (Qt.AlignRight | Qt.AlignVCenter))
        # self.sort_cbox = ComboBox(['Ascending', 'Descending', 'Unsorted'], 80, 20, 'sort_cbox',
        #                           'Select the test parameter sort order for plotting ("Unsorted" will plot tests '
        #                           'in the order they were parsed)')
        self.sort_cbox = ComboBox(['Ascending', 'Descending', 'Unsorted', 'Reverse'], 80, 20, 'sort_cbox',
                                  'Select the test parameter sort order for plotting ("Unsorted" will plot tests '
                                  'in the order they were parsed)')
        sort_order_layout = BoxLayout([sort_order_lbl, self.sort_cbox], 'h')

        # default_test_params_layout = BoxLayout([prm_str_layout, prm_unit_layout], 'v')
        # default_test_params_layout = BoxLayout([prm_str_layout, swell_dir_layout], 'v')
        # default_test_params_layout = BoxLayout([prm_str_layout, swell_dir_layout, sort_order_layout], 'v')
        default_test_params_layout = BoxLayout([prm_str_layout, current_layout, swell_dir_layout, sort_order_layout], 'v')


        self.parse_test_params_gb = GroupBox('Parse test params from files', default_test_params_layout,
                                               True, True, 'parse_test_params_gb')
        self.parse_test_params_gb.setToolTip('The RX Noise test params (e.g., speed) will be parsed from the file, '
                                             'if available (e.g., speed in SIS 5 format).\n\n'
                                             'If not found in the file, the parser will search for speed or heading '
                                             'information in the file name using the provided test string format '
                                             '(e.g., "_08_kts.txt" or "-200-RPM.txt") and assign that value to all '
                                             'BIST data parsed from that file.  The test units selected will be '
                                             'applied to all plots.\n\n'
                                             'For noise vs. azimuth tests, it is strongly recommended to use clear '
                                             'notation of the headings in filenames, such as "_123T_090S.txt" for '
                                             'a file collected at 123 deg True and heading 090 relative to the '
                                             'the prevailing seas (e.g., swell on the port side, where 000S '
                                             'corresponds to swell on the bow).\n\n'
                                             'The custom test params option below is intended only for particular '
                                             'data sets where the user has a very clear understanding of the test '
                                             'parameters (and consistent number of tests) in each file.')

        prm_min_tb_lbl = Label('Minimum param:', 120, 20, 'prm_min_tb_lbl', (Qt.AlignRight | Qt.AlignVCenter))
        self.prm_min_tb = LineEdit('0', 40, 20, 'prm_min_tb', 'Enter the minimum speed')
        self.prm_min_tb.setValidator(QDoubleValidator(0, np.inf, 1))
        prm_min_layout = BoxLayout([prm_min_tb_lbl, self.prm_min_tb], 'h')

        prm_max_tb_lbl = Label('Maximum param:', 120, 20, 'prm_max_tb_lbl', (Qt.AlignRight | Qt.AlignVCenter))
        self.prm_max_tb = LineEdit('12', 40, 20, 'prm_max_tb', 'Enter the maximum speed')
        self.prm_max_tb.setValidator(QDoubleValidator(0, np.inf, 1))
        prm_max_layout = BoxLayout([prm_max_tb_lbl, self.prm_max_tb], 'h')

        prm_int_tb_lbl = Label('Param interval:', 120, 20, 'prm_int_tb_lbl', (Qt.AlignRight | Qt.AlignVCenter))
        self.prm_int_tb = LineEdit('2', 40, 20, 'prm_min_tb', 'Enter the speed interval')
        self.prm_int_tb.setValidator(QDoubleValidator(0, np.inf, 1))
        prm_int_layout = BoxLayout([prm_int_tb_lbl, self.prm_int_tb], 'h')

        num_tests_tb_lbl = Label('Num. tests/interval:', 120, 20, 'num_tests_tb_lbl',
                                 (Qt.AlignRight | Qt.AlignVCenter))
        self.num_tests_tb = LineEdit('10', 40, 20, 'num_tests_tb', 'Enter the number of tests at each speed')
        self.num_tests_tb.setValidator(QDoubleValidator(0, np.inf, 0))
        prm_num_layout = BoxLayout([num_tests_tb_lbl, self.num_tests_tb], 'h')

        # total_num_params_tb_lbl = Label('Total num. intervals:', 120, 20, 'total_num_params_tb_lbl',
        #                                 (Qt.AlignRight | Qt.AlignVCenter))
        # self.total_num_params_tb = LineEdit('7', 40, 20, 'total_num_params_tb',
        #                                     'Total number of speeds in custom info')
        # self.total_num_params_tb.setEnabled(False)
        # total_prm_num_layout = BoxLayout([total_num_params_tb_lbl, self.total_num_params_tb], 'h')

        total_num_tests_tb_lbl = Label('Total num. tests:', 120, 20, 'total_num_tests_tb_lbl',
                                       (Qt.AlignRight | Qt.AlignVCenter))
        self.total_num_tests_tb = LineEdit('70', 40, 20, 'total_num_tests_tb',
                                           'Total number of tests in custom info')
        self.total_num_tests_tb.setEnabled(False)
        total_test_num_layout = BoxLayout([total_num_tests_tb_lbl, self.total_num_tests_tb], 'h')

        self.final_params_hdr = 'Params list: '
        self.final_params_lbl = Label(self.final_params_hdr + ', '.join([p for p in self.param_list]), 200, 20,
                                      'final_params_lbl', (Qt.AlignLeft | Qt.AlignVCenter))
        self.final_params_lbl.setWordWrap(True)

        # custom_prm_layout = BoxLayout([prm_min_layout, prm_max_layout, prm_int_layout, prm_num_layout,
        #                                total_prm_num_layout, total_test_num_layout, self.final_params_lbl], 'v')

        custom_prm_layout = BoxLayout([prm_min_layout, prm_max_layout, prm_int_layout, prm_num_layout,
                                       total_test_num_layout, self.final_params_lbl], 'v')

        self.custom_param_gb = GroupBox('Use custom test params', custom_prm_layout, True, False, 'custom_params_gb')
        self.custom_param_gb.setToolTip('Enter custom test parameter information.  The total number of tests shown '
                                        'below must equal the total number of BISTs parsed from the selected files '
                                        '(total tests, not file count).\n\n'
                                        'The parameters will be associated with files in the order they are loaded '
                                        '(e.g., first BIST parsed will be associated with "minimium" parameter).')

        # param_layout = BoxLayout([prm_unit_layout, self.parse_test_params_gb, self.custom_param_gb], 'v')
        # param_layout = BoxLayout([prm_unit_layout, self.parse_test_params_gb, self.custom_param_gb], 'v')
        param_layout = BoxLayout([prm_unit_layout, self.prm_plot_lim_gb, self.parse_test_params_gb, self.custom_param_gb], 'v')


        self.noise_test_gb = GroupBox('RX Noise Testing', param_layout, False, False, 'noise_test_gb')

        # set up tabs
        self.tabs = QtWidgets.QTabWidget()

        # set up tab 1: plot options
        self.tab1 = QtWidgets.QWidget()
        self.tab1.layout = file_btn_layout
        self.tab1.layout.addStretch()
        self.tab1.setLayout(self.tab1.layout)

        # TEST set up tab 2: combined filtering and advanced noise test options
        self.tab2 = QtWidgets.QWidget()
        # self.tab2.layout = BoxLayout([plot_btn_layout, param_layout], 'v')
        self.tab2.layout = BoxLayout([plot_btn_layout, self.noise_test_gb], 'v')
        self.tab2.layout.addStretch()
        self.tab2.setLayout(self.tab2.layout)

        # set up tab 2: filtering options
        # self.tab2 = QtWidgets.QWidget()
        # self.tab2.layout = plot_btn_layout
        # self.tab2.layout.addStretch()
        # self.tab2.setLayout(self.tab2.layout)

        # set up tab 3: advanced options
        # self.tab3 = QtWidgets.QWidget()
        # self.tab3.layout = param_layout
        # self.tab3.layout.addStretch()
        # self.tab3.setLayout(self.tab3.layout)

        # add tabs to tab layout
        self.tabs.addTab(self.tab1, 'Files')
        self.tabs.addTab(self.tab2, 'Plot')
        # self.tabs.addTab(self.tab3, 'Noise Test')

        self.tabw = 215  # set fixed tab width
        self.tabs.setFixedWidth(self.tabw)

        # stack file_control_gb and plot_control_gb
        self.right_layout = QtWidgets.QVBoxLayout()
        self.right_layout.addWidget(self.custom_info_gb)
        self.right_layout.addWidget(self.tabs)

    def set_left_layout(self):
        # add table showing selected files
        self.file_list = QtWidgets.QListWidget()
        self.file_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.file_list.installEventFilter(self)

        # set layout of file list
        self.file_list_layout = QtWidgets.QVBoxLayout()
        self.file_list_layout.addWidget(self.file_list)

        # set file list group box
        self.file_list_gb = QtWidgets.QGroupBox('Sources')
        self.file_list_gb.setLayout(self.file_list_layout)
        self.file_list_gb.setMinimumWidth(550)
        self.file_list_gb.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding,
                                        QtWidgets.QSizePolicy.MinimumExpanding)

        # add activity log widget
        self.log = QtWidgets.QTextEdit()
        # self.log.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding,
        #                        QtWidgets.QSizePolicy.MinimumExpanding)
        self.log.setStyleSheet("background-color: lightgray")
        self.log.setReadOnly(True)
        self.update_log('*** New BIST plotting log ***')

        # add progress bar for total file list
        self.current_fnum_lbl = QtWidgets.QLabel('Current file count:')
        self.current_outdir_lbl = QtWidgets.QLabel('Current output directory: ' + self.output_dir)

        self.calc_pb_lbl = QtWidgets.QLabel('Total Progress:')
        self.calc_pb = QtWidgets.QProgressBar()
        self.calc_pb.setGeometry(0, 0, 200, 30)
        self.calc_pb.setMaximum(100)  # this will update with number of files
        self.calc_pb.setValue(0)

        # set progress bar layout
        self.calc_pb_layout = QtWidgets.QHBoxLayout()
        self.calc_pb_layout.addWidget(self.calc_pb_lbl)
        self.calc_pb_layout.addWidget(self.calc_pb)

        self.prog_layout = QtWidgets.QVBoxLayout()
        self.prog_layout.addWidget(self.current_fnum_lbl)
        self.prog_layout.addWidget(self.current_outdir_lbl)
        self.prog_layout.addLayout(self.calc_pb_layout)

        # set the log layout
        self.log_layout = QtWidgets.QVBoxLayout()
        self.log_layout.addWidget(self.log)
        self.log_layout.addLayout(self.prog_layout)

        # set the log group box widget with log layout
        self.log_gb = QtWidgets.QGroupBox('Activity Log')
        self.log_gb.setLayout(self.log_layout)
        self.log_gb.setMinimumWidth(550)

        # set the left panel layout with file controls on top and log on bottom
        self.left_layout = QtWidgets.QVBoxLayout()
        self.left_layout.addWidget(self.file_list_gb)
        self.left_layout.addWidget(self.log_gb)  # add log group box

    def set_main_layout(self):  # set the main layout with file controls on left and swath figure on right
        main_layout = QtWidgets.QHBoxLayout()
        main_layout.addLayout(self.left_layout)
        main_layout.addLayout(self.right_layout)
        self.mainWidget.setLayout(main_layout)

    def update_noise_param_string(self):  # update the dict of strings for parsing noise parameters from filenames
        self.noise_params[self.prm_unit_cbox.currentText()] = self.prm_str_tb.text()

    def update_noise_param_unit(self):  # update text box with custom string for noise test unit
        self.prm_str_tb.setText(self.noise_params[self.prm_unit_cbox.currentText()])

        # enable current adjustment input fields if speed through water is selected
        self.current_tb.setEnabled('stw' in self.prm_unit_cbox.currentText().lower())
        self.current_dir_cbox.setEnabled('stw' in self.prm_unit_cbox.currentText().lower())

    def update_buttons(self):  # update buttons/options from user actions
        if self.type_cbox.currentIndex() == 2:  # noise testing
            self.noise_test_gb.setEnabled(True)
            self.noise_test_type_cbox.setEnabled(True)

            if self.prm_unit_cbox.currentIndex() != self.prm_unit_cbox.count() - 1:  # store last non-azimuth param unit
                self.prm_unit_cbox_last_index = self.prm_unit_cbox.currentIndex()

            if 'azimuth' in self.noise_test_type_cbox.currentText().lower():  # disable custom param, enable swell tb
                self.prm_unit_cbox.setCurrentIndex(self.prm_unit_cbox.count()-1)
                self.prm_unit_cbox.setEnabled(False)
                self.prm_str_tb.setEnabled(False)
                # self.current_tb.setEnabled(False)
                # self.current_dir_cbox.setEn(False)
                self.swell_dir_tb.setEnabled(True)
                self.parse_test_params_gb.setChecked(True)
                self.custom_param_gb.setEnabled(False)
                self.update_swell_dir()

            else:  # noise vs speed / custom parameter; enable custom param, disable swell tb
                self.prm_unit_cbox.setCurrentIndex(self.prm_unit_cbox_last_index)
                self.prm_unit_cbox.setEnabled(True)
                self.prm_str_tb.setEnabled(True)
                self.swell_dir_tb.setEnabled(False)
                self.custom_param_gb.setEnabled(True)

                # if 'stw' in self.prm_unit_cbox.currentText().lower(): # enable current adjustments to SOG for STW calc
                #     self.current_tb.setEnabled(True)
                #     self.current_dir_cbox.setEn(True)

        else:
            self.noise_test_gb.setEnabled(False)
            self.noise_test_type_cbox.setEnabled(False)

        self.prm_str_tb.setText(self.noise_params[self.prm_unit_cbox.currentText()])

    def update_groupboxes(self):  # toggle groupbox checked state
        if 'azimuth' in self.noise_test_type_cbox.currentText().lower():
            return

        else:
            self.gb_toggle = not self.gb_toggle
            self.parse_test_params_gb.setChecked(self.gb_toggle)
            self.custom_param_gb.setChecked(not self.gb_toggle)

    def add_files(self, ftype_filter, input_dir='HOME', include_subdir=False):  # add all files of specified type in dir
        if input_dir == 'HOME':  # select files manually if input_dir not specified as optional argument
            fnames = QtWidgets.QFileDialog.getOpenFileNames(self, 'Open files...', os.getenv('HOME'), ftype_filter)
            fnames = fnames[0]  # keep only the filenames in first list item returned from getOpenFileNames

        else:  # get all files satisfying ftype_filter in input_dir
            fnames = []

            if include_subdir:  # walk through all subdirectories
                for dirpath, dirnames, filenames in os.walk(input_dir):
                    for filename in [f for f in filenames if f.endswith(ftype_filter)]:
                        fnames.append(os.path.join(dirpath, filename))

            else:  # step through all files in this directory only (original method)
                for f in os.listdir(input_dir):
                    if os.path.isfile(os.path.join(input_dir, f)):  # verify it's a file
                        if os.path.splitext(f)[1] == ftype_filter:  # verify ftype_filter extension
                            fnames.append(os.path.join(input_dir, f))  # add whole path, same as getOpenFileNames

        # get updated file list and add selected files only if not already listed
        self.get_current_file_list()
        fnames_new = [fn for fn in fnames if fn not in self.filenames]
        fnames_skip = [fs for fs in fnames if fs in self.filenames]

        if len(fnames_skip) > 0:  # skip any files already added, update log
            self.update_log('Skipping ' + str(len(fnames_skip)) + ' file(s) already added')

        for f in range(len(fnames_new)):  # add the new files only after verifying BIST type
            bist_type, sis_ver_found = multibeam_tools.libs.read_bist.verify_bist_type(fnames_new[f])
            print(bist_type, sis_ver_found)

            if 0 not in bist_type:  # add files only if plotters are available for tests in file (test types  > 0)
                # add item with full file path data, set text according to show/hide path button
                [path, fname] = fnames_new[f].rsplit('/', 1)
                # print('path=', path)
                # print('fname=', fname)
                # add file only if name exists prior to ext (may slip through splitext check if adding directory)
                if fname.rsplit('.', 1)[0]:
                    new_item = QtWidgets.QListWidgetItem()
                    new_item.setData(1, fnames_new[f].replace('\\','/'))  # set full file path as data, role 1
                    new_item.setText((path + '/') * int(self.show_path_chk.isChecked()) + fname)  # set text, show path
                    self.file_list.addItem(new_item)
                    # self.update_log('Added ' + fname)  # fnames_new[f].rsplit('/',1)[-1])
                    bist_types_found = [self.bist_list[idx_found] for idx_found in bist_type]
                    self.update_log('Added ' + fnames_new[f].split('/')[-1] +
                                    ' (SIS ' + str(sis_ver_found) + ': ' +
                                    ', '.join(bist_types_found) + ')')

                else:
                    self.update_log('Skipping empty filename ' + fname)

            else:  # skip non-verified BIST types
                self.update_log('Skipping ' + fnames_new[f].split('/')[-1] + ' (' + self.bist_list[0] + ')')

        self.get_current_file_list()  # update self.file_list and file count
        self.current_fnum_lbl.setText('Current file count: ' + str(len(self.filenames)))

    def show_file_paths(self):
        # show or hide path for all items in file_list according to show_paths_chk selection
        for i in range(self.file_list.count()):
            [path, fname] = self.file_list.item(i).data(1).rsplit('/', 1)  # split full file path from item data, role 1
            self.file_list.item(i).setText((path+'/')*int(self.show_path_chk.isChecked()) + fname)

    def get_input_dir(self):
        try:
            self.input_dir = QtWidgets.QFileDialog.getExistingDirectory(self, 'Add directory', os.getenv('HOME'))
            self.update_log('Added directory: ' + self.input_dir)

            # get a list of all .txt files in that directory, '/' avoids '\\' in os.path.join in add_files
            self.update_log('Adding files in directory: ' + self.input_dir)
            self.add_files(ftype_filter='.txt', input_dir=self.input_dir+'/',
                           include_subdir=self.include_subdir_chk.isChecked())

        except ValueError:
            self.update_log('No input directory selected.')
            self.input_dir = ''
            pass

    def get_output_dir(self):  # get output directory for saving plots
        try:
            new_output_dir = QtWidgets.QFileDialog.getExistingDirectory(self, 'Select output directory',
                                                                        os.getenv('HOME'))

            if new_output_dir is not '':  # update output directory if not cancelled
                self.output_dir = new_output_dir.replace('/','\\')
                self.update_log('Selected output directory: ' + self.output_dir)
                self.current_outdir_lbl.setText('Current output directory: ' + self.output_dir)

        except:
            self.update_log('No output directory selected.')
            pass

    # def remove_files(self, clear_all=False):  # remove selected files
    #     self.get_current_file_list()
    #     selected_files = self.file_list.selectedItems()
    #
    #     if clear_all:  # clear all
    #         self.file_list.clear()
    #         self.filenames = []
    #         self.update_log('All files have been removed.')
    #
    #     elif self.filenames and not selected_files:  # files exist but nothing is selected
    #         self.update_log('No files selected for removal.')
    #         return
    #
    #     else:  # remove only the files that have been selected
    #         for f in selected_files:
    #             fname = f.text().split('/')[-1]
    #             self.file_list.takeItem(self.file_list.row(f))
    #             self.update_log('Removed ' + fname)

    def remove_bist_files(self, clear_all=False):  # remove selected files
        # remove selected files or clear all files, update det and spec dicts accordingly
        removed_files = remove_files(self, clear_all)
        self.get_current_file_list()

        if self.filenames == []:  # all files have been removed
            self.update_log('Cleared all files')
            self.cruise_name_updated = False
            self.model_updated = False
            self.ship_name_updated = False
            self.sn_updated = False
            self.swell_dir_updated = False
            self.swell_dir_tb.setText(self.swell_dir_default)
            self.swell_dir_message = True

    def get_current_file_list(self):  # get current list of files in qlistwidget
        list_items = []
        for f in range(self.file_list.count()):
            list_items.append(self.file_list.item(f))

        # self.filenames = [f.text() for f in list_items]  # convert to text
        self.filenames = [f.data(1) for f in list_items]  # return list of full file paths stored in item data, role 1

        # self.filenames = [f.data(1) for f in list_items]  # return list of full file paths stored in item data, role 1
        self.current_fnum_lbl.setText('Current file count: ' + str(len(self.filenames)))

    def get_new_file_list(self, fext=[''], flist_old=[]):
        # determine list of new files with file extension fext that do not exist in flist_old
        # flist_old may contain paths as well as file names; compare only file names
        self.get_current_file_list()
        fnames_ext = [fn for fn in self.filenames if any(ext in fn for ext in fext)]  # fnames (w/ paths) matching ext
        fnames_old = [fn.split('/')[-1] for fn in flist_old]  # file names only (no paths) from flist_old
        fnames_new = [fn for fn in fnames_ext if fn.split('/')[-1] not in fnames_old]  # check if fname in fnames_old

        return fnames_new  # return the fnames_new (with paths)

    def select_bist(self):
        # verify BIST types in current file list and select those matching current BIST type in combo box
        self.clear_bist()  # update file list and clear all selections before re-selecting those of desired BIST type
        bist_count = 0  # count total selected files

        for f in range(len(self.filenames)):  # loop through file list and select if matches BIST type in combo box
            # bist_type, sis_ver_found = multibeam_tools.libs.read_bist.verify_bist_type(self.file_list.item(f).text())
            bist_type, sis_ver_found = multibeam_tools.libs.read_bist.verify_bist_type(self.file_list.item(f).data(1))

            # check whether selected test index from combo box  is available in this file
            if int(self.type_cbox.currentIndex()+1) in bist_type:  # currentIndex+1 because bist_list starts at 0 = N/A
                self.file_list.item(f).setSelected(True)
                bist_count = bist_count+1

        if bist_count == 0:  # update log with selection total
            self.update_log('No ' + self.type_cbox.currentText() + ' files available for selection')

        else:
            self.update_log('Selected ' + str(bist_count) + ' ' + self.type_cbox.currentText() + ' file(s)')

        if self.warn_user_chk.isChecked():  # if desired, check the system info in selected files
            self.verify_system_info()

    def clear_bist(self):
        self.get_current_file_list()
        for f in range(len(self.filenames)):
            self.file_list.item(f).setSelected(False)  # clear any pre-selected items before re-selecting verified ones

    def update_system_info(self):  # get updated/stripped model, serial number, ship, cruise, and date
        self.model_number = self.model_cbox.currentText().replace('EM', '').strip()  # get model from name list
        self.sn = self.sn_tb.text().strip()
        self.ship_name = self.ship_tb.text().strip()
        self.cruise_name = self.cruise_tb.text().strip()
        self.date_str = self.date_tb.text().strip()

        # reset the text color after clicking/activating/entering user info
        sender_button = self.sender()
        sender_button.setStyleSheet('color: black')

        # print('current list of missing fields is:', self.missing_fields)
        # remove the user-updated field from the list of missing fields
        if sender_button.objectName() in self.missing_fields:
            self.missing_fields.remove(sender_button.objectName())
            # self.plot_bist_btn.setEnabled(False)

    def verify_system_info(self):  # prompt user for missing fields or warn if different
        self.missing_fields = []
        self.conflicting_fields = []
        self.model_updated = False
        self.sn_updated = False
        self.date_updated = False

        fnames_sel = [self.file_list.item(f).data(1) for f in range(self.file_list.count())
                      if self.file_list.item(f).isSelected()]

        if self.file_list.count() > 0:
            if self.warn_user_chk.isChecked():
                if not fnames_sel:  # prompt user to select files if none selected
                    self.update_log('Please select BIST type and click Select BISTs to verify system info')
                else:
                    # elif self.warn_user_chk.isChecked():
                    self.update_log('Checking ' + str(len(fnames_sel)) + ' files for model, serial number, and date')

        for fname in fnames_sel:  # loop through files, verify BIST type, and plot if matches test type
            fname_str = fname[fname.rfind('/') + 1:].rstrip()
            # get SIS version for later use in parsers, store in BIST dict (BIST type verified at file selection)
            _, sis_ver_found = multibeam_tools.libs.read_bist.verify_bist_type(fname)  # get SIS ver for RX Noise parser

            # get available system info in this file
            sys_info = multibeam_tools.libs.read_bist.check_system_info(fname, sis_version=sis_ver_found)

            if not sys_info or any(not v for v in sys_info.values()):  # warn user if missing system info in file
                if sys_info:
                    missing_fields = ', '.join([k for k, v in sys_info.items() if not v])
                    self.update_log('***WARNINGS: Missing system info (' + missing_fields + ') in file ' + fname)
                else:
                    # self.update_log('***WARNING: Missing all system info in file ' + fname)
                    self.update_log('***WARNING: Missing all system info in file ' + fname_str)

                # continue

            # update user entry fields to any info available in BIST, store conflicting fields if different
            if sys_info['model']:
                print('BIST has model=', sys_info['model'])
                model = sys_info['model']
                # if sys_info['model'].find('2040') > -1:
                if sys_info['model'] in ['2040', '2045', '2040P']:  # EM2040C MKII shows 'Sounder Type: 2045'
                    model = '2040'  # store full 2040 model name in sys_info, but just use 2040 for model comparison

                if not self.model_updated:  # update model with first model found
                    # self.model_cbox.setCurrentIndex(self.model_cbox.findText('EM '+sys_info['model']))
                    self.model_cbox.setCurrentIndex(self.model_cbox.findText('EM '+model))
                    self.update_log('Updated model to ' + self.model_cbox.currentText() + ' (first model found)')
                    self.model_updated = True

                # elif 'EM '+sys_info['model'] != self.model_cbox.currentText():  # model was updated but new model found
                elif 'EM '+model != self.model_cbox.currentText():  # model was updated but new model found

                    # self.update_log('***WARNING: New model (EM ' + sys_info['model'] + ') detected in ' + fname_str)
                    self.update_log('***WARNING: New model (EM ' + model + ') detected in ' + fname_str)
                    self.conflicting_fields.append('model')

            if sys_info['sn']:
                if not self.sn_updated:  # update serial number with first SN found
                    self.sn_tb.setText(sys_info['sn'])
                    self.update_log('Updated serial number to ' + self.sn_tb.text() + ' (first S/N found)')

                    if self.sn_tb.text() in ['40', '60', '71']:  # warn user of PU IP address bug in SIS 5 BISTs
                        self.update_log('***WARNING: SIS 5 serial number parsed from the BIST header may be the last '
                                        'digits of the IP address (no specific PU serial number found in file); '
                                        'update system info as needed')
                        self.conflicting_fields.append('sn')

                    self.sn_updated = True

                elif sys_info['sn'] != self.sn_tb.text().strip():  # serial number was updated but new SN found
                    self.update_log('***WARNING: New serial number (' + sys_info['sn'] + ') detected in ' + fname_str)
                    self.conflicting_fields.append('sn')

            if sys_info['date']:
                if not self.date_updated:  # update date with first date found
                    self.date_tb.setText(sys_info['date'])
                    self.update_log('Updated date to ' + self.date_tb.text() + ' (first date found)')
                    self.date_updated = True

                elif sys_info['date'] != self.date_tb.text().strip():  # date was updated but new date found
                    self.update_log('***WARNING: New date (' + sys_info['date'] + ') detected in ' + fname_str)
                    self.conflicting_fields.append('date')

            # store missing fields, reduce to set after looping through files and disable/enable plot button
            self.missing_fields.extend([k for k in ['model', 'sn', 'date'] if not sys_info[k]])
            # print('self.missing fields =', self.missing_fields)
            # print('self.conflicting fields =', self.conflicting_fields)

        # after reading all files, reduce set of missing fields and disable/enable plot button accordingly
        self.missing_fields = [k for k in set(self.missing_fields)]
        self.conflicting_fields = [k for k in set(self.conflicting_fields)]

        # if self.missing_fields or self.conflicting_fields:
        self.update_sys_info_colors()
        if self.warn_user_chk.isChecked() and any(self.missing_fields or self.conflicting_fields):
            user_warning = QtWidgets.QMessageBox.question(self, 'System info check',
                'Red field(s) are either:\n\n' +
                '          1) not available from the selected BIST(s), or\n' +
                '          2) available but conflicting across selected BISTs\n\n' +
                'Please confirm these fields or update file selection before plotting.\n' +
                'System info shown will be used for any fields not found in a file, but will not replace fields parsed '
                'successfully (even if conflicting).',
                QtWidgets.QMessageBox.Ok)

    def update_sys_info_colors(self):  # update the user field colors to red/black based on missing/conflicting info
        for widget in [self.model_cbox, self.sn_tb, self.date_tb]:  # set text to red for all missing fields
            widget.setStyleSheet('color: black')  # reset field to black before checking missing/conflicting fields
            if widget.objectName() in self.missing_fields + self.conflicting_fields:
                widget.setStyleSheet('color: red')

    def plot_bist(self):
        # get list of selected files and send each to the appropriate plotter
        bist_test_type = self.type_cbox.currentText()
        self.update_log('Plotting selected ' + bist_test_type + ' BIST files')
        self.get_current_file_list()
        self.update_system_info()

        # housekeeping for updating each parsed BIST dict with system info (assume correct from user; add check later)
        freq = multibeam_tools.libs.read_bist.get_freq(self.model_number)  # get nominal freq to use if not parsed
        swell_str = '_into_swell'  # identify the RX Noise/Spectrum file heading into the swell by '_into_swell.txt'
        # rxn_test_type = 1  # vs speed only for now; add selection, parsers, and plotters for heading tests later
        rxn_test_type = self.noise_test_type_cbox.currentIndex()
        print('rxn_test_type =', rxn_test_type)

        bist_count = 0  # reset
        bist_fail_list = []

        # set up dicts for parsed data; currently setup to work with read_bist with minimal modification as first step
        bist_list_index = self.bist_list.index(bist_test_type)
        bist = multibeam_tools.libs.read_bist.init_bist_dict(bist_list_index)
        fnames_sel = [self.file_list.item(f).data(1) for f in range(self.file_list.count())
                      if self.file_list.item(f).isSelected()]

        if not fnames_sel:
            self.update_log('Please select at least one BIST to plot...')

        if self.type_cbox.currentIndex() == 2:  # check if RX Noise test
            if self.noise_test_type_cbox.currentIndex() == 0:  # check if speed test
                if self.custom_param_gb.isChecked():
                    self.update_log('RX Noise vs. Speed: Custom speeds entered by user will override any speeds parsed '
                                    'from files or filenames, and will be applied in order of files loaded')
                else:
                    self.update_log('RX Noise vs. Speed: Speeds will be parsed from filename (SIS 4) or file (SIS 5), '
                                    'if available')
            else:  # check if azimuth test
                self.update_log('RX Noise vs. Azimuth: Ship heading will be parsed from the filename in the '
                                'format _123T.txt'' or _123.txt, if available.\n\n'
                                'Please right-click and select the file heading into the swell or enter the swell '
                                'direction manually (note: compass direction from which the seas are arriving).\n\n'
                                'Alternatively, swell direction may be included in the filename after the heading, '
                                'in the format _090S.  This is suitable for cases where the swell direction is not '
                                'consistent across all files, or simply to ensure it is logged explicitly for each.\n\n'
                                'For example, a BIST file on a true heading of 180 with swell out of the east would '
                                'have a filename ending with _180T_090S.txt')

                hdg_parsed = True
                az_parsed = True

                for fname in fnames_sel:  # loop through filenames and make sure at least the headings can be parsed
                    fname_str = fname[fname.rfind('/') + 1:].rstrip()
                    self.update_log('Checking heading/azimuth info in ' + fname_str)
                    print('checking heading/azimuth info in file ', fname_str)
                    temp_hdg, temp_az = self.parse_fname_hdg_az(fname_str)
                    print('back in loop, got temp_hdg and temp_az from parser: ', temp_hdg, temp_az)

                    if temp_hdg == '999':
                        print('failed to get HEADING from ', fname_str)
                        hdg_parsed = False

                    if temp_az == '999':
                        print('failed to get AZIMUTH from ', fname_str)
                        az_parsed = False

                if not hdg_parsed:
                    # warn user and return if headings are not included in filenames
                    self.update_swell_dir(hdg_parse_fail=True)
                    return

                if not az_parsed or self.swell_dir_tb.text() == self.swell_dir_default:
                    # warn user and return if the azimuth cannot be determined from current inputs
                    self.update_swell_dir(swell_parse_fail=True)
                    return

        for fname in fnames_sel:  # loop through files, verify BIST type, and plot if matches test type

            fname_str = fname[fname.rfind('/') + 1:].rstrip()
            self.update_log('Parsing ' + fname_str)
            # fname_str = fname[fname.rfind('/') + 1:].rstrip()

            # get SIS version for later use in parsers, store in BIST dict (BIST type verified at file selection)
            _, sis_ver_found = multibeam_tools.libs.read_bist.verify_bist_type(fname)  # get SIS ver for RX Noise parser

            print('in BIST plotter, found SIS version:', sis_ver_found)

            # get available system info in this file
            sys_info = multibeam_tools.libs.read_bist.check_system_info(fname, sis_version=sis_ver_found)
            print('sys_info return =', sys_info)

            bist_temp = []

            try:  # try parsing the files according to BIST type
                if bist_test_type == self.bist_list[1]:  # TX Channels
                    bist_temp = multibeam_tools.libs.read_bist.parse_tx_z(fname, sis_version=sis_ver_found)
                    print('********* after parse_tx_z, got bist_temp =', bist_temp)

                    # like RX Channels, some TX BISTs logged in SIS 4 follow the SIS 5 format; the SIS ver check
                    # returns 4 (correct) but parser returns empty bist_temp; retry with SIS 5 format as a last resort
                    # example: Australian Antarctic Division EM712 data recorded in SIS 4 (2022)
                    if not bist_temp and sys_info['model']:
                        if sys_info['model'] in ['712', '304', '124'] and sis_ver_found == 4:
                            print('bist_temp returned empty --> retrying parse_rx_noise with SIS 5 format')
                            bist_temp = multibeam_tools.libs.read_bist.parse_tx_z(fname, sis_version=int(5))

                elif bist_test_type == self.bist_list[2]:  # RX Channels
                    # check model and skip EM2040 variants (model combobox is updated during verification step,
                    # so this can be checked even if model is not available in sys_info)
                    # print('sys info model is', sys_info['model'],' with type', type(sys_info['model']))

                    # skip 2040 (FUTURE: RX Channels for all freq)
                    # if sys_info['model']:
                    #     if sys_info['model'].find('2040') > -1:
                    #         self.update_log('***WARNING: RX Channels plot N/A for EM2040 variants: ' + fname_str)
                    #         bist_fail_list.append(fname)
                    #         continue

                    # if sys_info['model']:
                    #     if sys_info['model'].find('2040') > -1:
                    #         if sis_ver_found == 4:
                    #             self.update_log('***WARNING: RX Channels plot N/A for EM2040 (SIS 4): ' + fname_str)
                    #             bist_fail_list.append(fname)
                    #             continue

                    # elif self.model_cbox.currentText().find('2040') > -1:
                    #     self.update_log('***WARNING: Model not parsed from file and EM2040 selected; '
                    #                     'RX Channels plot not yet available for EM2040 variants: ' + fname_str)
                    #     bist_fail_list.append(fname)
                    #     continue

                    # elif self.model_cbox.currentText().find('2040') > -1:
                    #     if sis_ver_found == 4:
                    #         self.update_log('***WARNING: Model not parsed from file (EM2040 selected in system info); '
                    #                         'RX Channels plot not yet available for EM2040 (SIS 4) variants: ' + fname_str)
                    #         bist_fail_list.append(fname)
                    #         continue


                    print('*******calling parse_rx_z********** --> sis_ver_found =', sis_ver_found)
                    bist_temp = multibeam_tools.libs.read_bist.parse_rx_z(fname, sis_version=sis_ver_found)

                    # some EM2040 RX Channels BISTs recorded in SIS 4 are in the SIS 5 format; retry if failed w/ SIS 4
                    if not bist_temp and sys_info['model']:
                        if sys_info['model'] in ['2040', '2045', '2040P', '712'] and sis_ver_found == 4:

                            print('retrying parse_rx_z for EM2040 / 2045(2040C) / 2040P / 712 with SIS 5 format')
                            bist_temp = multibeam_tools.libs.read_bist.parse_rx_z(fname, sis_version=5, sis4_retry=True)


                elif bist_test_type == self.bist_list[3]:  # RX Noise
                    print('calling parse_rx_noise with sis_version =', sis_ver_found)
                    bist_temp = multibeam_tools.libs.read_bist.parse_rx_noise(fname, sis_version=sis_ver_found)

                    # like RX Channels, some RX Noise BISTs logged in SIS 4 follow the SIS 5 format; the SIS ver check
                    # returns 4 (correct) but parser returns empty bist_temp; retry with SIS 5 format as a last resort
                    # example: Australian Antarctic Division EM712 data recorded in SIS 4 (2022)
                    if not bist_temp['rxn'] and sys_info['model']:
                        if sys_info['model'] in ['2040', '2045', '2040P', '712', '304', '124'] and sis_ver_found == 4:
                            print('bist_temp[rxn] returned empty --> retrying parse_rx_noise with SIS 5 format')
                            bist_temp = multibeam_tools.libs.read_bist.parse_rx_noise(fname, sis_version=int(5))

                    # print('in main script, BIST_temp[test]=', bist_temp['test'])
                    # print('with type', type(bist_temp['test']))
                    # print('with size', np.size(bist_temp['test']))
                    # print('and len', len(bist_temp['test']))

                    # get speed or heading of test from filename
                    if rxn_test_type == 0:  # RX noise vs speed; get speed from fname "_6_kts.txt", "_9p5_kts.txt"

                        print('\n\n****got bist_temp[speed] =', bist_temp['speed'])

                        # if bist_temp['speed'] == []:  # try to get speed from filename if not parsed from BIST
                        # try to get speed from filename if SOG was not parsed (e.g., SIS 4) OR if test is not for SOG
                        # if bist_temp['speed'] == [] or self.prm_unit_cbox.currentText().lower().find('sog') == -1:
                        if bist_temp['speed'] == [] or \
                            self.prm_unit_cbox.currentText().split()[0].lower() not in ['sog', 'stw']:

                            print('getting bist_temp[speed_bist] from the filename for test units: ', self.prm_unit_cbox.currentText())

                            # self.update_log('Parsing speeds from SIS 4 filenames (e.g., "_6_kts.txt", "_9p5_kts.txt")')
                            try:
                                temp_speed = float(999.9)  # placeholder speed

                                if not self.custom_param_gb.isChecked():
                                    # continue trying to get speed from filename if custom speed is not checked
                                    temp = ["".join(x) for _, x in itertools.groupby(self.prm_str_tb.text(), key=str.isdigit)]
                                    print('********parsing speed based on example prm_str = ', self.prm_str_tb.text())
                                    print('temp =', temp)

                                    # take all characters between first and last elements in temp, if not digits
                                    print('temp[-1].isdigit() is', temp[-1].isdigit())
                                    if not temp[-1].isdigit():
                                        print('trying to split at non-digit char following speed')
                                        try:
                                            temp_speed = fname.rsplit(temp[-1], 1)[0]  # split at non-digit char following speed
                                            print('splitting fname at non-digit char following speed: temp_speed=', temp_speed)
                                        except:
                                            print('***failed to split at non-digit char following speed')
                                    else:
                                        print('trying to split at decimal')
                                        temp_speed = fname.rsplit(".", 1)[0]  # or split at start of file extension
                                        print('splitting fname temp speed at file ext: temp_speed=', temp_speed)

                                    print('after first step, temp_speed=', temp_speed)

                                    print('temp[0].isdigit() is', temp[0].isdigit())
                                    if not temp[0].isdigit():
                                        print('trying to split at non-digit char preceding speed')
                                        temp_speed = temp_speed.rsplit(temp[0], 1)[-1]  # split at non-digit char preceding spd
                                    else:
                                        print('splitting at last _ preceding speed')
                                        # temp_speed = temp_speed.rsplit("_", 1)[-1]  # or split at last _ or / preceding speed
                                        temp_speed = temp_speed.rsplit('_', 1)[-1].rsplit('/', 1)[-1]

                                    print('after second step, temp_speed=', temp_speed)
                                    temp_speed = float(temp_speed.replace(" ", "").replace("p", "."))  # replace
                                    print('parsed temp_speed = ', temp_speed)

                                bist_temp['speed'] = temp_speed  # store updated speed if

                                # testing to assign one speed per test rather than one speed per file
                                print('after parsing, bist_temp[test]=', bist_temp['test'])
                                bist_temp['speed_bist'] = [temp_speed for i in range(len(bist_temp['test']))]
                                print('bist_temp[speed_bist] =', bist_temp['speed_bist'])

                            except ValueError:
                                self.update_log('***WARNING: Error parsing speeds from filenames; '
                                                'check filename string example if parsing test parameter from filename,'
                                                'or use custom test parameters')
                                self.update_log('***SIS v4 RX Noise file names must include speed, '
                                                '.e.g., "_6_kts.txt" or "_9p5_kts.txt"')
                                bist_fail_list.append(fname)
                                continue

                    elif rxn_test_type == 1:  # RX noise vs azimuth rel to seas; get hdg, swell dir from fname or user
                        if bist_temp['hdg_true'] == [] and bist_temp['azimuth'] == []:
                            try:
                                self.update_log('Parsing headings (and azimuths, if available) from filenames')

                                temp_hdg, temp_az = self.parse_fname_hdg_az(fname_str)

                                bist_temp['hdg_true'] = float(temp_hdg)
                                bist_temp['azimuth'] = float(temp_az)
                                bist_temp['azimuth_bist'] = [float(temp_az) for i in range(len(bist_temp['test']))]

                                print('got hdgs ', bist_temp['hdg_true'], bist_temp['azimuth'], 'in ', fname_str)
                                print('bist_temp[azimuth_bist] =', bist_temp['azimuth_bist'])
                                # self.update_log('Assigning date (' + bist_temp['date'] + ') from filename')
                                # try:
                                    # if fname_str.find(swell_str) > -1:
                                    #     bist_temp['file_idx_into_swell'] = bist_count
                                    # get heading from fname "..._hdg_010.txt" or "...hdg_055_into_swell.txt"
                                    # bist_temp['hdg'] = float(fname.replace(swell_str, '').rsplit("_")[-1].rsplit(".")[0])


                            except ValueError:
                                self.update_log('***WARNING: Error parsing headings from filenames; default format to '
                                                'include is, e.g., "_045T_000S.txt" where T indicates the true heading '
                                                '(e.g., 000T = North) and S indicates the heading relative to seas on '
                                                'the bow (e.g., 000S = into the seas, 045S = seas on port bow, 090S = '
                                                'seas on port side, etc.)\n'
                                                'If headings relative to the seas are not known (or not relevant), '
                                                'the true heading for each file may be included using the same format '
                                                '(e.g., "_045T.txt") and heading relative to the seas may be excluded.')
                                bist_fail_list.append(fname)
                                continue

                # elif bist_test_type == self.bist_list[4]:  # RX Spectrum
                #     bist_temp = multibeam_tools.libs.read_bist.parseRXSpectrum(fname)  # SPECTRUM PARSER NOT WRITTEN

                else:
                    print("Unknown test type: ", bist_test_type)

                if bist_temp == []:
                    # self.update_log('***WARNING: No data parsed in ' + fname)
                    self.update_log('***WARNING: No data parsed in ' + fname_str)
                    bist_fail_list.append(fname)
                    continue  # do not try to append

            except ValueError:
                self.update_log('***WARNING: Error parsing ' + fname)
                bist_fail_list.append(fname)
                pass  # do not try to append

            else:  # try to append data if no exception during parsing
                # print('no exceptions during parsing, checking bist_temp for file', fname_str)
                try:
                    # add user fields if not parsed from BIST file (availability depends on model and SIS ver)
                    # this can be made more elegant once all modes are working
                    print('*********** ----> checking info, at start:')
                    print('bist_temp[frequency]=', bist_temp['frequency'])
                    print('bist_temp[model]=', bist_temp['model'])
                    print('bist_temp[sn]=', bist_temp['sn'])
                    print('bist_temp[date]=', bist_temp['date'])
                    print('bist_temp[time]=', bist_temp['time'])

                    if bist_temp['frequency'] == []:  # add freq if empty (e.g., most SIS 4 BISTs); np array if read
                        # bist_temp['frequency'] = [freq]  # add nominal freq for each file in case order changes
                        bist_temp['frequency'] = [[freq]]  # add freq as list to match format of parsed multi-freq


                    if not bist_temp['date']:  # add date if not parsed (incl. in SIS 5, but not all SIS 4 or TX chan)
                        self.update_log('***WARNING: no date parsed from file ' + fname_str)

                        if sys_info['date']:  # take date from sys_info if parsed
                            bist_temp['date'] = sys_info['date']

                        else:  # otherwise, try to get from filename or take from user input
                            try:
                                try:
                                    date_guess = re.search(r"\d{8}", fname_str).group()

                                except:
                                    date_guess = re.search(r"\d{4}[-_]\d{2}[-_]\d{2}", fname_str).group()

                                bist_temp['date'] = date_guess.replace("_", "").replace("-","")

                                self.update_log('Assigning date (' + bist_temp['date'] + ') from YYYYMMDD in filename')

                            except:
                                if self.date_str.replace('/', '').isdigit():  # user date if modified from yyyy/mm/dd
                                    date_str = self.date_str.split()
                                    bist_temp['date'] = self.date_str.replace('/','')
                                    self.update_log('Assigning date (' + bist_temp['date'] + ') from user input')

                        if bist_temp['date'] == []:
                            self.update_log('***WARNING: no date assigned to ' + fname_str + '\n' +
                                            '           This file may be skipped if date/time are required\n' +
                                            '           Update filenames to include YYYYMMDD (or enter date ' +
                                            'in user input field if all files are on the same day)')

                    if not bist_temp['time']:  # add time if not parsed (incl. in SIS 5, but not all SIS 4 or TX chan)
                        self.update_log('***WARNING: no time parsed from test information in file ' + fname_str)

                        if sys_info['time']:  # take date from sys_info if parsed
                            bist_temp['time'] = sys_info['time']
                            self.update_log('Assigning time (' + bist_temp['time'] + ') from system info')

                        else:  # otherwise, try to get from filename or take from user input
                            print('*** no sis_info[time]--> trying to get time from filename')
                            try:  # assume date and time in filename are YYYYMMDD and HHMMSS with _ or - in between
                                print('try start')
                                # print('fname_str =', fname_str)
                                # time_str = re.search(r"[_-]\d{6}", fname_str).group()
                                # time_str = re.search(r"_?-?\d{6}_?-?\d{6}", fname_str).group()
                                # print('got time_str =', time_str)
                                # bist_temp['time'] = time_str.replace('_', "").replace('-', "")
                                # bist_temp['time'] = time_str.replace('_', "").replace('-', "")[-6:]

                                # take last six digits in filename as the time
                                # this fails with other numbers (e.g., speed) in the file name
                                # time_str = ''.join([c for c in fname_str if c.isnumeric()])

                                # testing more flexible fname time parsing (exclude numbers without - or _, e.g., 12kt

                                if bist_temp['date']:  # split filename after date if available
                                    print('bist_temp[date] is available')
                                    fname_str_split = fname_str.split(bist_temp['date'])[1]
                                    print('got fname_str_split =', fname_str_split)

                                    try:  # try parsing 4 or 6 digit time separated by _- or space from rest of fname
                                        print('trying regex search for 4- or 6-digit time_str in filename')
                                        time_str_temp = re.search(r"[ _-](\d{4}|\d{6})[ _-]", fname_str_split).group()
                                        print('found time_str_temp: ', time_str_temp)

                                        # remove delimiters, pad with zeros as necessary, and add .000
                                        time_str_temp = time_str_temp[1:-1].ljust(6, '0') + '.000'
                                        print('got time_str_temp = ', time_str_temp)

                                    except:
                                        print('did not find 4- or 6-digit time_str after date_str in fname_str_split')
                                        time_str_temp = '000000.000'

                                    if time_str_temp > '240000.000':
                                        print('parsed time_str_temp greater than 240000.000; replacing with 000000.000')
                                        time_str_temp = '000000.000'

                                # date_str = re.search("\d{8}", fname_str).group()

                                # time_str = date_str + time_str_temp

                                print('storing bist_temp[time] = ', time_str_temp)
                                bist_temp['time'] = time_str_temp

                                print('final date and time are ', bist_temp['date'], bist_temp['time'])

                                time_str = bist_temp['date'] + bist_temp['time']
                                time_str = time_str.split('.')[0]

                                if len(time_str) == 14:
                                    self.update_log('Assigning time (' + bist_temp['time'] + ') from filename')

                                else:
                                    self.update_log('***WARNING: date and time not parsed (expected YYYYMMDD HHMM[SS] '
                                                    'format, separated by - or _ from the rest of the filename, e.g., '
                                                    'BIST_file_20210409_123000.txt); assigning time 000000.000 for '
                                                    'this file')
                                    bist_temp['time'] = '000000.000'  # placeholder time

                                self.update_log('Assigned date / time: ' + bist_temp['date'] + '/' + bist_temp['time'])

                                # else: # len(time_str) < 14:
                                #     self.update_log('***WARNING: date and time not parsed (expected YYYYMMDD HHMM[SS] '
                                #                     'format, separated by - or _ from the rest of the filename); as a '
                                #                     'last attempt, time will be parsed from the end of the '
                                #                     'filename, such as BIST_file_20210409_123000.txt)')
                                #
                                #
                                #
                                #     try:
                                #         bist_temp['time'] = ''.join([c for c in fname_str if c.isnumeric()])[-6:] + '.000'
                                #
                                #     except:
                                #         bist_temp['time'] = '000000.000'  # placeholder time
                                #
                                # else:
                                #     bist_temp['time'] = ''.join([c for c in fname_str if c.isnumeric()])[-6:] + '.000'

                                # self.update_log('Assigning time (' + bist_temp['time'] + ') from filename')

                            except:
                                self.update_log('***WARNING: no time assigned to ' + fname_str + '\n' +
                                                '           This file may be skipped if date/time are required\n' +
                                                '           Update filenames to include time, e.g., YYYYMMDD-HHMMSS')

                    if bist_temp['model'] == []:  # add model if not parsed
                        if sys_info['model']:
                            bist_temp['model'] = sys_info['model']
                        else:
                            bist_temp['model'] = self.model_number

                    if bist_temp['sn'] == []:  # add serial number if not parsed
                        if sys_info['sn'] and sis_ver_found != 5:
                            bist_temp['sn'] = sys_info['sn']  # add serial number if not parsed from system info
                        else:  # store user-entered serial number if not available or possible SIS 5 bug
                            bist_temp['sn'] = self.sn

                    print('************ after checking, bist_temp info is now:')
                    print('bist_temp[frequency]=', bist_temp['frequency'])
                    print('bist_temp[model]=', bist_temp['model'])
                    print('bist_temp[sn]=', bist_temp['sn'])
                    print('bist_temp[date]=', bist_temp['date'])

                    # store other fields
                    bist_temp['sis_version'] = sis_ver_found  # store SIS version
                    bist_temp['ship_name'] = self.ship_tb.text()  # store ship name
                    bist_temp['cruise_name'] = self.cruise_tb.text()  # store cruise name

                    # append dicts
                    bist = multibeam_tools.libs.read_bist.appendDict(bist, bist_temp)
                    bist_count += 1  # increment counter if no issues parsing or appending

                except ValueError:
                    # self.update_log('***WARNING: Error appending ' + fname)
                    self.update_log('***WARNING: Error appending ' + fname_str)
                    bist_fail_list.append(fname)

        if bist['filename']:  # try plotting only if at least one BIST was parsed successfully
            if len(bist_fail_list) > 0:
                self.update_log('The following BISTs will not be plotted:')
                for i in range(len(bist_fail_list)):
                    self.update_log('     ' + str(i + 1) + ". " + bist_fail_list[i])

            self.update_log('Plotting ' + str(bist_count) + ' ' + self.type_cbox.currentText() + ' BIST files...')

            if bist_test_type == self.bist_list[1]:  # TX Channels
                for ps in [1, 2]:  # loop through and plot both available styles of TX Z plots, then plot history
                    f_out = multibeam_tools.libs.read_bist.plot_tx_z(bist, plot_style=ps, output_dir=self.output_dir)
                self.update_log('Saved ' + str(len(f_out)) + ' ' + self.bist_list[1] + ' plot(s) in ' + self.output_dir)

                # plot TX Z history
                f_out = multibeam_tools.libs.read_bist.plot_tx_z_history(bist, output_dir=self.output_dir)
                if f_out:
                    self.update_log('Saved TX Z history plot ' + f_out + ' in ' + self.output_dir)
                else:
                    self.update_log('No TX Z history plot saved (check log for missing date/time warnings)')

            elif bist_test_type == self.bist_list[2]:  # RX Channels
                multibeam_tools.libs.read_bist.plot_rx_z(bist, save_figs=True, output_dir=self.output_dir)
                # multibeam_tools.libs.read_bist.plot_rx_z_annual(bist, save_figs=True, output_dir=self.output_dir)
                multibeam_tools.libs.read_bist.plot_rx_z_history(bist, save_figs=True, output_dir=self.output_dir)

            elif bist_test_type == self.bist_list[3]:  # RX Noise
                freq_list = bist['frequency'][0][0]  # freq list; assume identical across all files
                print('freq_list=', freq_list)
                print('bist=', bist)

                # if rxn_test_type == 0:
                test_type = ['speed', 'azimuth', 'standalone'][self.noise_test_type_cbox.currentIndex()]
                param_unit = self.prm_unit_cbox.currentText()
                param_adjust = 0.0

                # sort_by = test_type
                print('test_type = ', test_type)

                param_list = []
                param_lims = []

                if self.prm_plot_lim_gb.isChecked():
                    param_lims = [float(self.prm_plot_min_tb.text()), float(self.prm_plot_max_tb.text())]

                if self.custom_param_gb.isChecked():
                    # apply param list from custom entries; assumes BISTs are loaded and selected in order of
                    # increasing param corresponding to these custom params; there is no other way to check!
                    self.update_param_info()
                    param_list = np.repeat(self.param_list, int(self.num_tests_tb.text()))
                    param_count = np.size(self.param_list)
                    print('using custom param list=', param_list)

                elif test_type == 'speed':
                    # param_list = bist['speed_bist']
                    param_count = len(bist['speed'])

                    if 'stw' in self.prm_unit_cbox.currentText().lower():  # get current magnitude and relative scale
                        print('***getting current value for Speed Through Water adjustment****')
                        param_adjust = float(self.current_tb.text())
                        param_adjust *= float([-1 if 'with' in self.current_dir_cbox.currentText().lower() else 1][0])
                        print('***STW test ---> applying param adjust =', param_adjust)

                elif test_type == 'azimuth':
                #     param_list = bist['azimuth_bist']
                    param_count = len(bist['azimuth'])

                print('*****ahead of plotting, bist[speed]=', bist['speed'])
                print('*****ahead of plotting, bist[speed_bist]=', bist['speed_bist'])
                print('*****ahead of plotting, bist[azimuth]=', bist['azimuth'])
                print('*****ahead of plotting, bist[azimuth_bist]=', bist['azimuth_bist'])

                if len(set(freq_list)) == 1:
                # if len(set((bist['frequency'][0][0]))) == 1:  # single frequency detected, single plot
                    print('single frequency found in RX Noise test')
                    bist['frequency'] = [freq_list]  # simplify single frequency, assuming same across all tests
                    multibeam_tools.libs.read_bist.plot_rx_noise(bist, save_figs=True,
                                                                 output_dir=self.output_dir,
                                                                 test_type=test_type,
                                                                 param=param_list,
                                                                 param_unit=self.prm_unit_cbox.currentText(),
                                                                 param_adjust=param_adjust,
                                                                 param_lims=param_lims,
                                                                 cmap=self.cmap_cbox.currentText().lower().strip(),
                                                                 sort=self.sort_cbox.currentText().lower().strip())

                else:  # loop through each frequency, reduce RXN data for each freq and call plotter for that subset
                    print('multiple frequencies found in RX Noise test, setting up to plot each freq')
                    for f in range(len(freq_list)):
                        print('f=', f)
                        bist_freq = copy.deepcopy(bist)  # copy, pare down columns for each frequency
                        print('bist_freq=', bist_freq)
                        bist_freq['rxn'] = []

                        for p in range(param_count):
                            # print('before trying to grab freqs, size of bist[rxn][p] =', np.shape(bist['rxn'][p]))
                            # print('bist[test][p] =', bist['test'][p])
                            for t in bist['test'][p]:
                                print('working on f=', f, ' p =', p, ' and t = ', t)
                                rxn_array_z = [np.array(bist['rxn'][p][t][:, f])]
                                bist_freq['rxn'].append(rxn_array_z)  # store in frequency-specific BIST dict
                                bist_freq['frequency'] = [[freq_list[f]]]  # plotter expects list of freq

                        # print('\n\n*********for f = ', f, 'and bist_freq =', bist_freq)
                        # print('calling plot_rx_noise with param_list = ', param_list)
                        # print('bist_freq[speed_bist]=', bist_freq['speed_bist'])
                        # print('bist_freq[azimuth_bist]=', bist_freq['azimuth_bist'])
                        # print('bist-freq[rxn] has shape', np.shape(bist_freq['rxn']))

                        multibeam_tools.libs.read_bist.plot_rx_noise(bist_freq, save_figs=True,
                                                                     output_dir=self.output_dir,
                                                                     test_type=test_type,
                                                                     param=param_list,  # [] if unspecified
                                                                     param_unit=param_unit,
                                                                     param_adjust=param_adjust,
                                                                     param_lims=param_lims,
                                                                     cmap=self.cmap_cbox.currentText().lower().strip(),
                                                                     sort=self.sort_cbox.currentText().lower().strip())

            elif bist_test_type == self.bist_list[4]:  # RX Spectrum
                print('RX Spectrum parser and plotter are not available yet...')

            if self.open_outdir_chk.isChecked():
                print('trying to open the output directory: ', self.output_dir.replace('/','\\'))
                os.system('explorer.exe ' + self.output_dir.replace('/','\\'))

        else:
            self.update_log('No BISTs to plot')

    def update_log(self, entry):  # update the activity log
        self.log.append(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' ' + entry)
        QtWidgets.QApplication.processEvents()

    def update_prog(self, total_prog):
        self.calc_pb.setValue(total_prog)
        QtWidgets.QApplication.processEvents()

    def update_param_info(self):
        try:
            prm_min = float(self.prm_min_tb.text())
            prm_max = float(self.prm_max_tb.text())
            prm_int = float(self.prm_int_tb.text())
            prm_num = np.floor((prm_max-prm_min)/prm_int) + 1
            print('min, max, int, num=', prm_min, prm_max, prm_int, prm_num)
            self.param_list = np.arange(0, prm_num)*prm_int + prm_min
            self.param_list.round(decimals=1)
            print('param_list=', self.param_list)
            # self.total_num_params_tb.setText(str(np.size(self.param_list)))
            self.total_num_tests_tb.setText(str(int(prm_num*float(self.num_tests_tb.text()))))
            self.final_params_lbl.setText(self.final_params_hdr +
                                          np.array2string(self.param_list, precision=1, separator=', '))
            # self.final_params_lbl.setText(self.final_params_hdr + ', '.join([p for p in self.param_list]))

        except:
            pass

    def parse_fname_hdg_az(self, fname_str='fname_str_000T_000S.txt'):
        # parse ship heading and swell direction from a file name, if available
        # heading is required as 3-digit string w/ or w/o T (denoting 'true'), e.g., '_090T.txt'
        # swell dir is optional after hdg as 3-digit string w/ or w/o S (denoting 'swell'), e.g. '_090T_270S.txt'
        temp_hdg = '999'
        temp_az = '999'
        temp_swell = '999'

        try:  # try parsing file name
            try:  # try to parse ship heading and swell direction (e.g., '_045T_270S.txt' or '_045_270.txt)
                hdgs = re.search(r"[_]\d{1,3}[T]?[_]\d{1,3}[S]?(_|.txt)", fname_str).group().split('_')[1:]
                temp_hdg = ''.join([c for c in hdgs[0] if c.isdigit()])
                temp_swell = ''.join([c for c in hdgs[1] if c.isdigit()])
                print('found hdgs with format _045[T]_000[S], hdgs = ', hdgs)
                self.update_log('Parsed true heading and swell direction from ' + fname_str)
                self.swell_dir_tb.setText(temp_swell)
                self.update_log('Parsed swell direction ' + self.swell_dir_tb.text() + ' deg from filename')
                self.swell_dir_updated = True

            except:  # look for simple heading (e.g., _234T.txt), get swell direction from user
                hdgs = re.search(r"[_]\d{1,3}[T]?(_|.txt)", fname_str).group().split('_')[1:]
                temp_hdg = ''.join([c for c in hdgs[0] if c.isdigit()])
                print('found hdgs with format _123[T], hdgs = ', hdgs, ' getting swell from input')
                self.update_log('Parsed true heading (no swell direction) from ' + fname_str)
                temp_swell = self.swell_dir_tb.text()

            temp_az = str(np.mod(float(temp_hdg) - float(temp_swell), 360))  # get azimuth re swell dir on [0,360]
            print('got temp_hdg = ', temp_hdg, ' and temp_az =', temp_az)

        except:
            self.update_log('Failed to parse heading/swell direction from ' + fname_str)

        return temp_hdg, temp_az

    def update_swell_dir(self, swell_parse_fail=False, hdg_parse_fail=False):
        # get the swell direction for RX Noise vs Azimuth tests, if not found from filenames
        self.tabs.setCurrentIndex(2)  # show noise test params tab

        swell_dir_text = ('RX noise vs. azimuth processing requires user input to specify the ship heading and '
                          'direction of the prevailing seas.\n\n' \
                          'HEADING must be specified in each file name as a three-digit true heading in the format '
                          '_123T.txt or _123.txt.\n\n' \
                          'SWELL DIRECTION must be specified by one of the following options:\n\n' \
                          'Option 1: Right-click the file heading into the seas and select Set file INTO SEAS\n\n' \
                          'Option 2: Enter the swell direction manually under Noise Test --> Swell direction\n\n' \
                          'Option 3: Include the swell direction in the file name as a three-digit direction ' \
                          '(after ship heading) in the format _060S.txt or _060.txt.  For instance, the file name for '
                          'a BIST recorded on a heading of 270 with swell from the east would end in _270T_090S.txt\n\n'
                          'Options 1 and 2 are suitable for steady swell direction and option 3 is suitable if swell '
                          'direction changes throughout the files (e.g., BISTs recorded over several hours.\n\n' \
                          'Note that swell direction is the compass direction from which the swell is arriving; for ' \
                          'example, swell out of the northwest is 270 and swell out of the northeast is 045.')

        if swell_parse_fail:  # add a note if plot attempt failed to get swell direction
            self.swell_dir_updated = False
            swell_dir_text = 'WARNING: Swell direction was not found.\n\n' + swell_dir_text

        if hdg_parse_fail:  # add a note if plot attempt failed to get heading
            swell_dir_text = 'WARNING: Heading was not found.\n\n' + swell_dir_text

        if self.swell_dir_tb.text() == self.swell_dir_default or not self.swell_dir_updated:
            swell_dir_warning = QtWidgets.QMessageBox.question(self, 'RX Noise vs. Azimuth (relative to seas)',
                                                           swell_dir_text, QtWidgets.QMessageBox.Ok)
            self.swell_dir_message = False

        else:
            self.swell_dir_updated = True

    def eventFilter(self, source, event):
        # enable user to right-click and set a file "INTO SEAS" for the noise vs azimuth test
        if (event.type() == QEvent.ContextMenu and source is self.file_list) and \
                self.noise_test_type_cbox.currentText().lower().find('azimuth') > -1:

            menu = QtWidgets.QMenu()
            set_file_action = menu.addAction('Set file INTO SEAS')
            clear_file_action = menu.addAction('Clear setting')
            action = menu.exec_(event.globalPos())
            item = source.itemAt(event.pos())

            if action == set_file_action or action == clear_file_action:
                set_into_seas = action == set_file_action
                self.set_file_into_seas(item, set_into_seas)

            # if menu.exec_(event.globalPos()):
            #     item = source.itemAt(event.pos())
            #     self.set_file_into_seas(item, event)
                # print(item.text())
                # item.setTextColor("red")
                # item.setText(item.text() + ' (INTO SEAS)')

            return True
        return super(MainWindow, self).eventFilter(source, event)

    def set_file_into_seas(self, item, set_into_seas):
        # manage the file list to allow only one file selected as 'into seas'
        print('now trying to set into seas for file: ', item.text())
        self.get_current_file_list()

        for i in range(self.file_list.count()):  # reset all text in file list
            f = self.file_list.item(i)
            f.setText(f.text().split()[0])  # reset text to filename only

        if set_into_seas:  # set the selected (right-clicked) file as INTO SEAS
            fname_str = item.text()
            item.setText(fname_str + ' ' + self.file_into_seas_str)
            self.update_log('Set file INTO SEAS: ' + fname_str)

            # update the swell direction text box
            try:
                # hdgs = re.search(r"[_]\d{1,3}[T]?[_]\d{1,3}[S]?", fname_str).group().split('_')[1:]
                hdgs = re.search(r"[_]\d{1,3}[T]?(_|.txt)", fname_str).group().split('_')[1:]
                # temp_hdg = float(''.join([c for c in hdgs[0] if c.isdigit()]))
                temp_swell = ''.join([c for c in hdgs[0] if c.isdigit()])
                print('in set_file_into_seas, found hdgs with format _045[T]_000[S], hdgs = ', hdgs)
                self.swell_dir_tb.setText(temp_swell)
                self.update_log('Parsed swell direction ' + self.swell_dir_tb.text() + ' deg from filename')
                self.swell_dir_updated = True

            except:
                self.update_log('Failed to parse swell direction from filename.  Please check the filename formats to '
                                'ensure the true heading is included as, e.g., ''_124T.txt'' for each, then retry '
                                'selecting the file oriented into the swell or enter the swell direction manually')
                self.swell_dir_tb.setText(self.swell_dir_default)
                self.swell_dir_updated = False

        else:
            self.update_log('Cleared INTO SEAS file setting')
            self.swell_dir_tb.setText(self.swell_dir_default)
            self.swell_dir_updated = False


class NewPopup(QtWidgets.QWidget):  # new class for additional plots
    def __init__(self):
        QtWidgets.QWidget.__init__(self)


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)

    main = MainWindow()
    main.show()

    sys.exit(app.exec_())
