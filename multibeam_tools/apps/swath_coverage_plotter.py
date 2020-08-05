# -*- coding: utf-8 -*-
"""
Created on Fri Feb 15 14:33:30 2019

@author: kjerram

Multibeam Echosounder Assessment Toolkit: Swath Coverage Plotter

"""

try:
    from PySide2 import QtWidgets, QtGui
    from PySide2.QtGui import QDoubleValidator
    from PySide2.QtCore import Qt, QSize
except ImportError as e:
    print(e)
    from PyQt5 import QtWidgets, QtGui
    from PyQt5.QtGui import QDoubleValidator
    from PyQt5.QtCore import Qt, QSize
import datetime
import os
import pickle
import sys
import numpy as np

# add path to external module common_data_readers for pyinstaller
sys.path.append('C:\\Users\\kjerram\\Documents\\GitHub')

from matplotlib import colors
from matplotlib import colorbar
from matplotlib import patches
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
from multibeam_tools.libs import parseEMswathwidth
from multibeam_tools.libs.gui_widgets import *
from multibeam_tools.libs.file_fun import *
from multibeam_tools.libs.swath_coverage_lib import *
from common_data_readers.python.kongsberg.kmall import kmall
from time import process_time
from scipy.interpolate import interp1d
from copy import deepcopy


__version__ = "0.1.4"


class MainWindow(QtWidgets.QMainWindow):

    media_path = os.path.join(os.path.dirname(__file__), "media")

    def __init__(self, parent=None):
        super(MainWindow, self).__init__()

        # set up main window
        self.mainWidget = QtWidgets.QWidget(self)
        self.setCentralWidget(self.mainWidget)
        self.setMinimumWidth(1000)
        self.setMinimumHeight(900)
        self.setWindowTitle('Swath Coverage Plotter v.%s' % __version__)
        self.setWindowIcon(QtGui.QIcon(os.path.join(self.media_path, "icon.png")))

        if os.name == 'nt':  # necessary to explicitly set taskbar icon
            import ctypes
            current_app_id = 'MAC.CoveragePlotter.' + __version__  # arbitrary string
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(current_app_id)

        setup(self)  # initialize variables and plotter params

        # set up three layouts of main window
        self.set_left_layout()
        self.set_center_layout()
        self.set_right_layout()
        self.set_main_layout()
        init_swath_ax(self)

        # set up button controls for specific actions other than refresh_plot
        self.add_file_btn.clicked.connect(lambda: add_cov_files(self, 'Kongsberg (*.all *.kmall)'))
        self.get_indir_btn.clicked.connect(lambda: add_cov_files(self, ['.all', '.kmall'], input_dir=[],
                                                                 include_subdir=self.include_subdir_chk.isChecked()))
        self.get_outdir_btn.clicked.connect(lambda: get_output_dir(self))
        self.rmv_file_btn.clicked.connect(lambda: remove_cov_files(self))
        self.clr_file_btn.clicked.connect(lambda: remove_cov_files(self, clear_all=True))
        self.show_path_chk.stateChanged.connect(lambda: show_file_paths(self))
        self.archive_data_btn.clicked.connect(lambda: archive_data(self))
        self.load_archive_btn.clicked.connect(lambda: load_archive(self))
        self.load_spec_btn.clicked.connect(lambda: load_spec(self))
        self.calc_coverage_btn.clicked.connect(lambda: calc_coverage(self))
        self.save_plot_btn.clicked.connect(lambda: save_plot(self))
        self.scbtn.clicked.connect(lambda: self.update_solid_color('color'))
        self.scbtn_arc.clicked.connect(lambda: self.update_solid_color('color_arc'))

        # set up event actions that call refresh_plot
        gb_map = [self.custom_info_gb,
                  self.plot_lim_gb,
                  self.rtp_angle_gb,
                  self.rtp_cov_gb,
                  self.angle_gb,
                  self.depth_gb,
                  self.bs_gb,
                  self.angle_lines_gb,
                  self.n_wd_lines_gb]

        cbox_map = [self.model_cbox,
                    self.pt_size_cbox,
                    self.pt_alpha_cbox,
                    self.color_cbox,
                    self.color_cbox_arc,
                    self.clim_cbox,
                    self.top_data_cbox]

        chk_map = [self.show_data_chk,
                   self.show_data_chk_arc,
                   self.grid_lines_toggle_chk,
                   self.colorbar_chk,
                   self.clim_filter_chk,
                   self.spec_chk]

        tb_map = [self.ship_tb,
                  self.cruise_tb,
                  self.max_x_tb, self.max_z_tb,
                  self.min_angle_tb, self.max_angle_tb,
                  self.min_depth_arc_tb, self.max_depth_arc_tb,
                  self.min_depth_tb, self.max_depth_tb,
                  self.min_bs_tb, self.max_bs_tb,
                  self.rtp_angle_buffer_tb,
                  self.rtp_cov_buffer_tb,
                  self.max_count_tb,
                  self.dec_fac_tb,
                  self.angle_lines_tb_max,
                  self.angle_lines_tb_int,
                  self.n_wd_lines_tb_max,
                  self.n_wd_lines_tb_int,
                  self.min_clim_tb,
                  self.max_clim_tb]

        # if self.det or self.det_archive:  # execute only if data are loaded, not on startup
        for gb in gb_map:
            #groupboxes tend to not have objectnames, so use generic sender string
            gb.clicked.connect(lambda: refresh_plot(self, sender='GROUPBOX_CHK'))

        for cbox in cbox_map:
            # lambda needs _ for cbox
            cbox.activated.connect(lambda _, sender=cbox.objectName(): refresh_plot(self, sender=sender))

        for chk in chk_map:
            # lambda needs _ for chk
            chk.stateChanged.connect(lambda _, sender=chk.objectName(): refresh_plot(self, sender=sender))

        for tb in tb_map:
            # lambda seems to not need _ for tb
            tb.returnPressed.connect(lambda sender=tb.objectName(): refresh_plot(self, sender=sender))

    def set_left_layout(self):
        # set left layout with file controls
        btnh = 20  # height of file control button
        btnw = 100  # width of file control button
        
        # add file control buttons
        self.add_file_btn = PushButton('Add Files', btnw, btnh, 'add_file_btn', 'Add files')
        self.get_indir_btn = PushButton('Add Directory', btnw, btnh, 'get_indir_btn', 'Add a directory')
        self.get_outdir_btn = PushButton('Select Output Dir.', btnw, btnh, 'get_outdir_btn',
                                         'Select the output directory (see current directory below)')
        self.rmv_file_btn = PushButton('Remove Selected', btnw, btnh, 'rmv_file_btn', 'Remove selected files')
        self.clr_file_btn = PushButton('Remove All Files', btnw, btnh, 'clr_file_btn', 'Remove all files')
        self.include_subdir_chk = CheckBox('Include subdirectories', False, 'include_subdir_chk',
                                           'Include subdirectories when adding a directory')
        self.show_path_chk = CheckBox('Show file paths', False, 'show_paths_chk', 'Show file paths')
        self.archive_data_btn = PushButton('Archive Data', btnw, btnh, 'archive_data_btn',
                                           'Archive current data from new files to a .pkl file')
        self.load_archive_btn = PushButton('Load Archive', btnw, btnh, 'load_archive_btn',
                                           'Load archive data from a .pkl file')
        self.load_spec_btn = PushButton('Load Spec. Curve', btnw, btnh, 'load_spec_btn',
                                        'IN DEVELOPMENT: Load theoretical performance file')
        self.calc_coverage_btn = PushButton('Calc Coverage', btnw, btnh, 'calc_coverage_btn',
                                            'Calculate coverage from loaded files')
        self.save_plot_btn = PushButton('Save Plot', btnw, btnh, 'save_plot_btn', 'Save current plot')

        # set file control button layout and groupbox
        source_btn_layout = BoxLayout([self.add_file_btn, self.get_indir_btn, self.get_outdir_btn, self.rmv_file_btn,
                                       self.clr_file_btn, self.include_subdir_chk, self.show_path_chk], 'v')
        source_btn_gb = GroupBox('Add Data', source_btn_layout, False, False, 'source_btn_gb')
        source_btn_arc_layout = BoxLayout([self.load_archive_btn, self.archive_data_btn], 'v')
        source_btn_arc_gb = GroupBox('Archive Data', source_btn_arc_layout, False, False, 'source_btn_arc_gb')
        spec_btn_gb = GroupBox('Spec. Data', BoxLayout([self.load_spec_btn], 'v'), False, False, 'spec_btn_gb')
        plot_btn_gb = GroupBox('Plot Data', BoxLayout([self.calc_coverage_btn, self.save_plot_btn], 'v'),
                               False, False, 'plot_btn_gb')
        file_btn_layout = BoxLayout([source_btn_gb, source_btn_arc_gb, spec_btn_gb, plot_btn_gb], 'v')
        file_btn_layout.addStretch()
        self.file_list = FileList()  # add file list with selection and icon size = (0,0) to avoid indent
        file_gb = GroupBox('Sources', BoxLayout([self.file_list, file_btn_layout], 'h'), False, False, 'file_gb')
        
        # add activity log widget
        self.log = TextEdit("background-color: lightgray", True, 'log')
        self.log.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.Minimum)
        update_log(self, '*** New swath coverage processing log ***')
        log_gb = GroupBox('Activity Log', BoxLayout([self.log], 'v'), False, False, 'log_gb')

        # add progress bar for total file list and layout
        self.current_file_lbl = Label('Current File:')
        self.current_outdir_lbl = Label('Current output directory:\n' + self.output_dir)
        calc_pb_lbl = Label('Total Progress:')
        self.calc_pb = QtWidgets.QProgressBar()
        self.calc_pb.setGeometry(0, 0, 150, 30)
        self.calc_pb.setMaximum(100)  # this will update with number of files
        self.calc_pb.setValue(0)
        calc_pb_layout = BoxLayout([calc_pb_lbl, self.calc_pb], 'h')
        self.prog_layout = BoxLayout([self.current_file_lbl, self.current_outdir_lbl], 'v')
        self.prog_layout.addLayout(calc_pb_layout)

        # set the left panel layout with file controls on top and log on bottom
        self.left_layout = BoxLayout([file_gb, log_gb, self.prog_layout], 'v')

    def set_center_layout(self):
        # set center layout with swath coverage plot
        self.swath_canvas_height = 10
        self.swath_canvas_width = 10
        self.swath_figure = Figure(figsize=(self.swath_canvas_width, self.swath_canvas_height))  # figure instance
        self.swath_canvas = FigureCanvas(self.swath_figure)  # canvas widget that displays the figure
        self.swath_canvas.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding,
                                        QtWidgets.QSizePolicy.MinimumExpanding)
        self.swath_toolbar = NavigationToolbar(self.swath_canvas, self)  # swath plot toolbar
        self.swath_layout = BoxLayout([self.swath_toolbar, self.swath_canvas], 'v')
    
    def set_right_layout(self):
        # set right layout with swath plot controls
        # add text boxes for system, ship, cruise
        model_tb_lbl = Label('Model:', alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.model_cbox = ComboBox(self.model_list, 100, 20, 'model_cbox', 'Select the model')
        model_info_layout = BoxLayout([model_tb_lbl, self.model_cbox], 'h')

        ship_tb_lbl = Label('Ship Name:', alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.ship_tb = LineEdit('R/V Unsinkable II', 100, 20, 'ship_tb', 'Enter the ship name')
        ship_info_layout = BoxLayout([ship_tb_lbl, self.ship_tb], 'h')

        cruise_tb_lbl = Label('Cruise Name:', alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.cruise_tb = LineEdit('A 3-hour tour', 100, 20, 'cruise_tb', 'Enter the cruise name')
        cruise_info_layout = BoxLayout([cruise_tb_lbl, self.cruise_tb], 'h')

        self.custom_info_gb = GroupBox('Use custom system information',
                                       BoxLayout([model_info_layout, ship_info_layout, cruise_info_layout], 'v'),
                                       True, False, 'custom_info_gb')
        self.custom_info_gb.setToolTip('Add system/cruise info; system info parsed from the file is used if available')

        # add point color options for new data
        self.show_data_chk = CheckBox('New data', False, 'show_data_chk', 'Show new data')
        self.color_cbox = ComboBox(self.cmode_list, 80, 20, 'color_cbox', 'Select the color mode for new data')
        self.scbtn = PushButton('Select Color', 80, 20, 'scbtn', 'Select solid color for new data')
        self.scbtn.setEnabled(False)  # disable color selection until 'Solid Color' is chosen from cbox
        cbox_layout_new = BoxLayout([self.show_data_chk, self.color_cbox, self.scbtn], 'v')

        # add point color options for archive data
        self.show_data_chk_arc = CheckBox('Archive data', False, 'show_data_chk_arc', 'Show archive data')
        self.color_cbox_arc = ComboBox(self.cmode_list, 80, 20, 'color_cbox_arc', 'Select the color mode for archive data')
        self.scbtn_arc = PushButton('Select Color', 80, 20, 'scbtn_arc', 'Select solid color for archive data')
        self.scbtn_arc.setEnabled(False)  # disable color selection until 'Solid Color' is chosen from cbox
        cbox_layout_arc = BoxLayout([self.show_data_chk_arc, self.color_cbox_arc, self.scbtn_arc], 'v')
        cmode_layout = BoxLayout([cbox_layout_new, cbox_layout_arc], 'h')

        # add selection for data to plot last (on top)
        top_data_lbl = Label('Plot data on top:', width=90, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.top_data_cbox = ComboBox(self.top_data_list, 90, 20, 'top_data_cbox',
                                      'Select the loaded dataset to plot last (on top)')
        top_data_layout = BoxLayout([top_data_lbl, self.top_data_cbox], 'h')

        # add color limit options
        clim_cbox_lbl = Label('Scale colormap to:', width=90, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.clim_cbox = ComboBox(self.clim_list, 90, 20, 'clim_cbox',
                                  'Scale the colormap limits to fit all unfiltered data, user-filtered '
                                  'data (e.g., masked for depth or backscatter), or fixed values.\n\n'
                                  'If the same color mode is used for new and archive data, then the colormap '
                                  'and its limits are scaled to all plotted data according to the selected '
                                  'colormap limit scheme.\n\n'
                                  'If different color modes are used, the colormap and its limits are scaled '
                                  'to the dataset plotted last (on top) according to the selected colormap '
                                  'limit scheme.\n\n'
                                  'Note: The order of plotting can be reversed by the user (e.g., to plot '
                                  'archive data on top of new data), using the appropriate plot options.')
        clim_options_layout = BoxLayout([clim_cbox_lbl, self.clim_cbox], 'h')
        pt_param_layout_top = BoxLayout([top_data_layout, clim_options_layout], 'v')
        pt_param_layout_top.addStretch()

        # add fixed color limit options
        min_clim_lbl = Label('Min:', width=40, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.min_clim_tb = LineEdit(str(self.clim_last_user['depth'][0]), 40, 20, 'min_clim_tb',
                                    'Set the minimum color limit')
        self.min_clim_tb.setEnabled(False)
        min_clim_layout = BoxLayout([min_clim_lbl, self.min_clim_tb], 'h')
        max_clim_lbl = Label('Max:', width=40, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.max_clim_tb = LineEdit(str(self.clim_last_user['depth'][1]), 40, 20, 'max_clim_tb',
                                    'Set the maximum color limit')
        self.max_clim_tb.setEnabled(False)
        max_clim_layout = BoxLayout([max_clim_lbl, self.max_clim_tb], 'h')
        self.min_clim_tb.setValidator(QDoubleValidator(-1*np.inf, np.inf, 2))
        self.max_clim_tb.setValidator(QDoubleValidator(-1*np.inf, np.inf, 2))

        pt_param_layout_right = BoxLayout([min_clim_layout, max_clim_layout], 'v')

        # add point size and opacity comboboxes
        self.pt_size_cbox = ComboBox([str(pt) for pt in range(11)], 45, 20, 'pt_size_cbox', 'Select point size')
        self.pt_size_cbox.setCurrentIndex(5)

        # add point size slider
        pt_size_lbl = Label('Point size:', width=50, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        pt_size_layout = BoxLayout([pt_size_lbl, self.pt_size_cbox], 'h')
        pt_size_layout.addStretch()

        # add point transparency/opacity slider (can help to visualize density of data)
        pt_alpha_lbl = Label('Opacity (%):', width=50, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.pt_alpha_cbox = ComboBox([str(10 * pt) for pt in range(11)], 45, 20, 'pt_alpha_cbox', 'Select opacity')
        self.pt_alpha_cbox.setCurrentIndex(self.pt_alpha_cbox.count() - 1)  # update opacity to greatest value
        pt_alpha_layout = BoxLayout([pt_alpha_lbl, self.pt_alpha_cbox], 'h')
        pt_alpha_layout.addStretch()

        # set final point parameter layout with color modes, colorscale limit options, point size, and opacity
        pt_param_layout_left = BoxLayout([pt_size_lbl, pt_alpha_lbl], 'v')
        pt_param_layout_center = BoxLayout([self.pt_size_cbox, self.pt_alpha_cbox], 'v')
        pt_param_layout_bottom = BoxLayout([pt_param_layout_left, pt_param_layout_center, pt_param_layout_right], 'h')
        pt_param_layout = BoxLayout([cmode_layout, pt_param_layout_top, pt_param_layout_bottom], 'v')
        pt_param_gb = GroupBox('Point style', pt_param_layout, False, False, 'pt_param_gb')

        # add custom plot axis limits
        max_z_lbl = Label('Depth:', width=50, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        max_x_lbl = Label('Width:', width=50, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.max_z_tb = LineEdit('', 40, 20, 'max_z_tb', 'Set the maximum depth of the plot')
        self.max_z_tb.setValidator(QDoubleValidator(0, 20000, 2))
        self.max_x_tb = LineEdit('', 40, 20, 'max_x_tb', 'Set the maximum width of the plot')
        self.max_x_tb.setValidator(QDoubleValidator(0, 20000, 2))
        plot_lim_layout = BoxLayout([max_z_lbl, self.max_z_tb, max_x_lbl, self.max_x_tb], 'h')
        self.plot_lim_gb = GroupBox('Use custom plot limits (m)', plot_lim_layout, True, False, 'max_gb')
        self.plot_lim_gb.setToolTip('Set maximum depth and width (0-20000 m) to override automatic plot scaling.')

        # add custom swath angle limits
        min_angle_lbl = Label('Min:', width=50, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        max_angle_lbl = Label('Max:', width=50, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.min_angle_tb = LineEdit('0', 40, 20, 'min_angle_tb', 'Set the minimum angle to plot (<= max angle)')
        self.max_angle_tb = LineEdit('75', 40, 20, 'max_angle_tb', 'Set the maximum angle to plot (>= min angle)')
        angle_layout = BoxLayout([min_angle_lbl, self.min_angle_tb, max_angle_lbl, self.max_angle_tb], 'h')
        self.angle_gb = GroupBox('Angle (deg)', angle_layout, True, False, 'angle_gb')
        self.angle_gb.setToolTip('Hide soundings based on nominal swath angles calculated from depths and '
                                 'acrosstrack distances; these swath angles may differ slightly from RX beam '
                                 'angles (w.r.t. RX array) due to installation, attitude, and refraction.')
        self.min_angle_tb.setValidator(QDoubleValidator(0, float(self.max_angle_tb.text()), 2))
        self.max_angle_tb.setValidator(QDoubleValidator(float(self.min_angle_tb.text()), 90, 2))

        # add custom depth limits
        min_depth_lbl = Label('Min depth (m):', alignment=(Qt.AlignRight | Qt.AlignVCenter))
        max_depth_lbl = Label('Max depth (m):', alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.min_depth_tb = LineEdit('0', 40, 20, 'min_depth_tb', 'Min depth of the new data')
        self.min_depth_arc_tb = LineEdit('0', 40, 20, 'min_depth_arc_tb', 'Min depth of the archive data')
        self.max_depth_tb = LineEdit('10000', 40, 20, 'max_depth_tb', 'Max depth of the new data')
        self.max_depth_arc_tb = LineEdit('10000', 40, 20, 'max_depth_arc_tb', 'Max depth of the archive data')
        self.min_depth_tb.setValidator(QDoubleValidator(0, float(self.max_depth_tb.text()), 2))
        self.max_depth_tb.setValidator(QDoubleValidator(float(self.min_depth_tb.text()), np.inf, 2))
        self.min_depth_arc_tb.setValidator(QDoubleValidator(0, float(self.max_depth_arc_tb.text()), 2))
        self.max_depth_arc_tb.setValidator(QDoubleValidator(float(self.min_depth_arc_tb.text()), np.inf, 2))
        depth_layout_left = BoxLayout([QtWidgets.QLabel(''), min_depth_lbl, max_depth_lbl], 'v')
        depth_layout_center = BoxLayout([QtWidgets.QLabel('New'), self.min_depth_tb, self.max_depth_tb], 'v')
        depth_layout_right = BoxLayout([QtWidgets.QLabel('Archive'), self.min_depth_arc_tb, self.max_depth_arc_tb], 'v')
        depth_layout = BoxLayout([depth_layout_left, depth_layout_center, depth_layout_right], 'h')
        self.depth_gb = GroupBox('Depth (new/archive)', depth_layout, True, False, 'depth_gb')
        self.depth_gb.setToolTip('Hide data by depth (m, positive down).\n\nAcceptable min/max fall within [0 inf].')

        # add custom reported backscatter limits
        min_bs_lbl = Label('Min:', width=50, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.min_bs_tb = LineEdit('-50', 40, 20, 'min_bs_tb',
                                  'Set the minimum reported backscatter (e.g., -50 dB); '
                                  'while backscatter values in dB are inherently negative, the filter range may '
                                  'include positive values to accommodate anomalous reported backscatter data')
        max_bs_lbl = Label('Max:', width=50, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.max_bs_tb = LineEdit('0', 40, 20, 'max_bs_tb',
                                  'Set the maximum reported backscatter of the data (e.g., 0 dB); '
                                  'while backscatter values in dB are inherently negative, the filter range may '
                                  'include positive values to accommodate anomalous reported backscatter data')
        self.min_bs_tb.setValidator(QDoubleValidator(-1*np.inf, float(self.max_bs_tb.text()), 2))
        self.max_bs_tb.setValidator(QDoubleValidator(float(self.min_bs_tb.text()), np.inf, 2))
        bs_layout = BoxLayout([min_bs_lbl, self.min_bs_tb, max_bs_lbl, self.max_bs_tb], 'h')
        self.bs_gb = GroupBox('Backscatter (dB)', bs_layout, True, False, 'bs_gb')
        self.bs_gb.setToolTip('Hide data by reported backscatter amplitude (dB).\n\n'
                              'Acceptable min/max fall within [-inf inf] to accommodate anomalous data >0.')

        # add custom threshold/buffer for comparing RX beam angles to runtime parameters
        rtp_angle_buffer_lbl = Label('Angle buffer (+/-10 deg):', width=40, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.rtp_angle_buffer_tb = LineEdit('2', 40, 20, 'rtp_angle_buffer_tb', '')
        self.rtp_angle_buffer_tb.setValidator(QDoubleValidator(-10, 10, 2))
        rtp_angle_layout = BoxLayout([rtp_angle_buffer_lbl, self.rtp_angle_buffer_tb], 'h')
        self.rtp_angle_gb = GroupBox('Hide angles near runtime limits', rtp_angle_layout, True, False, 'rtp_angle_gb')
        self.rtp_angle_gb.setToolTip('Hide soundings that may have been limited by user-defined RX angle '
                                     'constraints during collection.\n\n'
                                     'Note that soundings limited by the echosounder mode are preserved '
                                     '(e.g., soundings at 52 deg in Very Deep mode are shown) as long as they do not '
                                     'fall within the angle buffer of the swath angle limit set during acquisition.'
                                     '\n\nNote also RX beam angles (w.r.t. RX array) differ slightly from achieved '
                                     'swath angles (calculated from depth and acrosstrack distance) due to'
                                     'installation, attitude, and refraction.')
        self.rtp_angle_buffer_tb.setToolTip('RX angle buffer may be set between -10 and +10 deg to accommodate RX beam '
                                            'angle variability near the user-defined runtime limits, e.g., due to beam-'
                                            'steering for vessel attitude and refraction correction.\n\n'
                                            'A zero buffer value will mask soundings only if the associated RX beam '
                                            'angles (or nominal swath angles, if RX beam angles are not available) '
                                            'exceeds the user-defined runtime parameter; there is no accomodation of '
                                            'variability around this threshold.\n\n'
                                            'Decrease the buffer (down to -10 deg) for more aggressive masking '
                                            'of soundings approaching the runtime limits (e.g., narrower swath) and '
                                            'increase the buffer (positive up to +10 deg) for a wider allowance of '
                                            'soundings near the runtime limits.\n\n'
                                            'Fine tuning may help to visualize (and remove) outer soundings that were '
                                            'clearly limited by runtime parameters during acquisition.')

        # add custom threshold/buffer for comparing RX beam angles to runtime parameters
        rtp_cov_buffer_lbl = Label('Coverage buffer (0-inf m):', alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.rtp_cov_buffer_tb = LineEdit('100', 40, 20, 'rtp_cov_buffer_tb', '')
        self.rtp_cov_buffer_tb.setValidator(QDoubleValidator(0, np.inf, 2))
        rtp_cov_layout = BoxLayout([rtp_cov_buffer_lbl, self.rtp_cov_buffer_tb], 'h')
        self.rtp_cov_gb = GroupBox('Hide coverage near runtime limits', rtp_cov_layout, True, False, 'rtp_cov_gb')
        self.rtp_cov_gb.setToolTip('Hide soundings that may have been limited by user-defined acrosstrack '
                                   'coverage constraints during data collection.\n\n'
                                   'Increase the buffer (0-inf m) for more aggressive masking of soundings '
                                   'approaching the runtime coverage.  Soundings outside the runtime coverage '
                                   'limit should not available, as they are rejected during acquisition.\n\n'
                                   'Fine tuning may help to visualize (and remove) outer soundings that were '
                                   'clearly limited by runtime parameters during acquisition.')

        # add plotted point max count and decimation factor control in checkable groupbox
        max_count_lbl = Label('Max. plotted points (0-inf):', width=140, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.max_count_tb = LineEdit(str(self.n_points_max_default), 50, 20, 'max_count_tb',
                                     'Set the maximum number of plotted points for each data set')
        self.max_count_tb.setValidator(QDoubleValidator(0, np.inf, 2))
        max_count_layout = BoxLayout([max_count_lbl, self.max_count_tb], 'h')
        dec_fac_lbl = Label('Decimation factor (1-inf):', width=140, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.dec_fac_tb = LineEdit('1', 50, 20, 'dec_fac_tb', 'Set the custom decimation factor')
        self.dec_fac_tb.setValidator(QDoubleValidator(1, np.inf, 2))
        dec_fac_layout = BoxLayout([dec_fac_lbl, self.dec_fac_tb], 'h')
        pt_count_layout = BoxLayout([max_count_layout, dec_fac_layout], 'v')
        self.pt_count_gb = GroupBox('Limit plotted point count (plot faster)', pt_count_layout, True, False, 'pt_ct_gb')
        self.pt_count_gb.setToolTip('To maintain reasonable plot and refresh speeds, the display will be limited '
                                   'by default to a total of ' + str(self.n_points_max_default) + ' soundings.  '
                                   'The limit is applied to new and archive datasets separately.  If needed, the user '
                                   'may specify a custom maximum point count.\n\n'
                                   'Reduction of each dataset is accomplished by simple decimation as a final step '
                                   'after all user-defined filtering (depth, angle, backscatter, etc.).  Non-integer '
                                   'decimation factors are handled using nearest-neighbor interpolation; soundings '
                                   'are not altered, just downsampled to display the maximum count allowed by the '
                                   'user parameters.'
                                   '\n\nAlternatively, the user may also specify a custom decimation factor.  '
                                   'Each dataset will be downsampled according to the more aggressive of the two '
                                   'inputs (max. count or dec. fac.) to achieve the greatest reduction in total '
                                   'displayed sounding count.  Unchecking these options will revert to the default.  '
                                   'In any case, large sounding counts may significantly slow the plotting process.')

        # add swath angle line controls in chackable groupbox
        angle_lines_lbl_max = Label('Max:', width=50, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.angle_lines_tb_max = LineEdit('75', 40, 20, 'angle_lines_tb_max', 'Set the angle line maximum (0-90 deg)')
        self.angle_lines_tb_max.setValidator(QDoubleValidator(0, 90, 2))
        angle_lines_lbl_int = Label('Interval:', width=50, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.angle_lines_tb_int = LineEdit('15', 40, 20, 'angle_lines_tb_int', 'Set the angle line interval (5-30 deg)')
        self.angle_lines_tb_int.setValidator(QDoubleValidator(5, 30, 2))
        angle_lines_layout = BoxLayout([angle_lines_lbl_max, self.angle_lines_tb_max,
                                        angle_lines_lbl_int, self.angle_lines_tb_int], 'h')
        self.angle_lines_gb = GroupBox('Show swath angle lines', angle_lines_layout, True, False, 'angle_lines_gb')
        self.angle_lines_gb.setToolTip('Plot swath angle lines.\n\n'
                                       'Specify a custom maximum (0-90 deg) and interval (5-30 deg).\n\n'
                                       'These lines represent the achieved swath angles (calculated simply from depth '
                                       'and acrosstrack distance) and may differ from RX beam angles.')

        # add water depth multiple (N*WD) line controls in checkable groupbox
        n_wd_lines_lbl_max = Label('Max:', width=50, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.n_wd_lines_tb_max = LineEdit('6', 40, 20, 'n_wd_lines_tb_max', 'Set the N*WD lines maximum (0-10 WD)')
        self.n_wd_lines_tb_max.setValidator(QDoubleValidator(0, 20, 2))
        n_wd_lines_lbl_int = Label('Interval:', width=50, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.n_wd_lines_tb_int = LineEdit('1', 40, 20, 'n_wd_lines_tb_int', 'Set the N*WD lines interval (0.5-5 WD)')
        self.n_wd_lines_tb_int.setValidator(QDoubleValidator(0.5, 5, 2))
        n_wd_lines_layout = BoxLayout([n_wd_lines_lbl_max, self.n_wd_lines_tb_max,
                                       n_wd_lines_lbl_int, self.n_wd_lines_tb_int], 'h')
        self.n_wd_lines_gb = GroupBox('Show water depth multiple lines', n_wd_lines_layout, True, False, 'wd_lines_gb')
        self.n_wd_lines_gb.setToolTip('Plot water depth multiple (N*WD) lines.\n\n'
                                      'Specify a custom maximum (0-10 WD) and interval (0.5-5 WD).')

        # add check boxes to show archive data, grid lines, WD-multiple lines
        self.grid_lines_toggle_chk = CheckBox('Show grid lines', True, 'show_grid_chk', 'Show grid lines')
        self.colorbar_chk = CheckBox('Show colorbar/legend', False, 'show_colorbar_chk',
                                     'Enable colorbar or legend to follow the selected color mode.\n\n'
                                     'By default, the colorbar/legend follows the color mode of the last '
                                     'dataset added to the plot.  Typically, new data are plotted last (on '
                                     'top of any archive) and the new data color mode sets the colorbar.'
                                     '\n\nThe colorbar can be set to follow the archive data, if loaded, by '
                                     'checking the option to reverse the plot order.')

        self.clim_filter_chk = CheckBox('Set color scale from data filters', False, 'clim_from_filter_chk',
                                        'Scale the colorbar to limits used for hiding data by depth or '
                                        'backscatter.\n\nIf the same color mode is used for new and archive '
                                        'data, then the color scale applies to both datasets and the min/max '
                                        'are taken from the limits that are actively applied to the data.\n\n'
                                        'If different color modes are used, the color scale follows the '
                                        'dataset plotted last (on top) and the min/max are taken from the '
                                        'limits entered by the user for that dataset.\n\n'
                                        'Note the order of plotting can be reversed by the user, e.g., to '
                                        'plot archive data on top.')

        self.spec_chk = CheckBox('Show specification lines', False, 'show_spec_chk',
                                 'IN DEVELOPMENT: Load a text file with theoretical swath coverage performance')

        toggle_chk_layout = BoxLayout([self.grid_lines_toggle_chk, self.colorbar_chk, self.spec_chk], 'v')
        toggle_chk_gb = GroupBox('Other options', toggle_chk_layout, False, False, 'other_options_gb')

        # set up tabs
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setStyleSheet("background-color: none")

        # set up tab 1: plot options
        self.tab1 = QtWidgets.QWidget()
        self.tab1.layout = BoxLayout([self.custom_info_gb, cmode_layout, pt_param_gb, self.plot_lim_gb,
                                      self.angle_lines_gb, self.n_wd_lines_gb, toggle_chk_gb], 'v')
        self.tab1.layout.addStretch()
        self.tab1.setLayout(self.tab1.layout)

        # set up tab 2: filtering options
        self.tab2 = QtWidgets.QWidget()
        self.tab2.layout = BoxLayout([self.angle_gb, self.depth_gb, self.bs_gb, self.rtp_angle_gb,
                                      self.rtp_cov_gb, self.pt_count_gb], 'v')
        self.tab2.layout.addStretch()
        self.tab2.setLayout(self.tab2.layout)

        # add tabs to tab layout
        self.tabs.addTab(self.tab1, 'Plot')
        self.tabs.addTab(self.tab2, 'Filter')

        self.tabw = 240  # set fixed tab width
        self.tabs.setFixedWidth(self.tabw)

        self.right_layout = BoxLayout([self.tabs], 'v')
        self.right_layout.addStretch()

    def set_main_layout(self):
        # set the main layout with file controls on left and swath figure on right
        self.mainWidget.setLayout(BoxLayout([self.left_layout, self.swath_layout, self.right_layout], 'h'))


class NewPopup(QtWidgets.QWidget): # new class for additional plots
    def __init__(self):
        QtWidgets.QWidget.__init__(self)


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)

    main = MainWindow()
    main.show()

    sys.exit(app.exec_())