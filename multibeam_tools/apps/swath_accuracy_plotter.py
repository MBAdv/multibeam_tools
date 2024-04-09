# -*- coding: utf-8 -*-
"""
Created on Thu Apr 11 14:45:21 2019

@author: kjerram

Multibeam Echosounder Assessment Toolkit: Swath Accuracy Plotter

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

import sys
sys.path.append('C:\\Users\\kjerram\\Documents\\GitHub')  # add path to outer di rectory for pyinstaller

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from multibeam_tools.libs.gui_widgets import *
from multibeam_tools.libs.swath_accuracy_lib import *

__version__ = "20240217"  # testing Qimera ASCII import
__version__ = "0.1.2"  # new version with position time series duplicate filtering per IB Nuyina EM712 example



class MainWindow(QtWidgets.QMainWindow):

    media_path = os.path.join(os.path.dirname(__file__), "media")

    def __init__(self, parent=None):
        super(MainWindow, self).__init__()

        # set up main window
        self.mainWidget = QtWidgets.QWidget(self)
        self.setCentralWidget(self.mainWidget)
        self.setMinimumWidth(1000)
        self.setMinimumHeight(900)
        self.setWindowTitle('Swath Accuracy Plotter v.%s' % __version__)
        self.setWindowIcon(QtGui.QIcon(os.path.join(self.media_path, "icon.png")))

        if os.name == 'nt':  # necessary to explicitly set taskbar icon
            import ctypes
            current_app_id = 'MAC.AccuracyPlotter.' + __version__  # arbitrary string
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(current_app_id)

        setup(self)  # initialize variables and plotter params

        # set up three layouts of main window
        self.set_left_layout()
        self.set_center_layout()
        self.set_right_layout()
        self.set_main_layout()
        init_all_axes(self)
        # init_swath_ax(self)
        # init_surf_ax(self)
        # init_tide_ax(self)
        update_buttons(self)

        # set up button controls for specific action other than refresh_plot
        # self.add_file_btn.clicked.connect(lambda: self.add_files('Kongsberg(*.all *.kmall)'))
        # self.add_file_btn.clicked.connect(lambda: add_acc_files(self, 'Kongsberg (*.all *.kmall)'))
        self.add_file_btn.clicked.connect(lambda: add_acc_files(self, 'Kongsberg or Qimera ASCII (*.all *.kmall *ASCII.txt)'))

        self.get_indir_btn.clicked.connect(lambda: add_acc_files(self, ['.all', '.kmall'], input_dir=[],
                                                                 include_subdir=self.include_subdir_chk.isChecked()))
        self.get_outdir_btn.clicked.connect(lambda: get_output_dir(self))
        self.add_ref_surf_btn.clicked.connect(lambda: add_ref_file(self, 'Reference surface XYZ (*.xyz)'))
        self.add_dens_surf_btn.clicked.connect(lambda: add_dens_file(self, 'Density surface XYD (*.xyd)'))
        # self.add_tide_btn.clicked.connect(lambda: add_tide_file(self, 'Tide file (*.tid)'))
        self.add_tide_btn.clicked.connect(lambda: add_tide_file(self, 'Tide file (*.tid *.txt)'))
        self.rmv_file_btn.clicked.connect(lambda: remove_acc_files(self))
        # self.rmv_file_btn.clicked.connect(lambda: remove_files(self))
        self.clr_file_btn.clicked.connect(lambda: clear_files(self))
        self.show_path_chk.stateChanged.connect(lambda: show_file_paths(self))
        self.calc_accuracy_btn.clicked.connect(lambda: calc_accuracy(self))
        self.save_plot_btn.clicked.connect(lambda: save_plot(self))
        # self.ref_proj_cbox.activated.connect(lambda: parse_ref_depth(self))
        self.ref_proj_cbox.activated.connect(lambda: update_ref_utm_zone(self))
        self.slope_win_cbox.activated.connect(lambda: update_ref_slope(self))
        self.slope_win_cbox.activated.connect(lambda: calc_accuracy(self, recalc_dz_only=True))
        # self.tide_unit_cbox.activated.connect(lambda: parse_tide(self, force_refresh=True))
        self.tide_unit_cbox.activated.connect(lambda: process_tide(self, unit_set_by_user=True))
        self.depth_mode_cbox.activated.connect(lambda: calc_accuracy(self, recalc_dz_only=True))
        self.waterline_tb.returnPressed.connect(lambda: update_buttons(self, recalc_acc=True))

        # set up event actions that call refresh_plot with appropriate lists of which plots to refresh

        # testing maps with dicts of more options... seems to refresh only on last item
        # gb_map = {self.custom_info_gb: {'refresh': ['acc'], 'active_tab': 1},
        #           self.plot_lim_gb: {'refresh': ['acc'], 'active_tab': 1},
        #           self.angle_gb: {'refresh': ['acc'], 'active_tab': 1},
        #           self.depth_xline_gb: {'refresh': ['acc'], 'active_tab': 1},
        #           self.depth_ref_gb: {'refresh': ['ref'], 'active_tab': 2},
        #           self.bs_gb: {'refresh': ['acc'], 'active_tab': 1},
        #           self.slope_gb: {'refresh': ['ref'], 'active_tab': 2},
        #           self.density_gb: {'refresh': ['ref'], 'active_tab': 2}}
                  # self.depth_gb: {'refresh': ['ref'], 'active_tab': 2}}

        # gb_map = {0: {'widget': self.custom_info_gb, 'refresh': ['acc'], 'active_tab': 1},
        #           1: {'widget': self.plot_lim_gb, 'refresh': ['acc'], 'active_tab': 1},
        #           2: {'widget': self.angle_gb, 'refresh': ['acc'], 'active_tab': 1},
        #           3: {'widget': self.depth_xline_gb, 'refresh': ['acc'], 'active_tab': 1},
        #           4: {'widget': self.depth_ref_gb, 'refresh': ['ref'], 'active_tab': 2},
        #           5: {'widget': self.bs_gb, 'refresh': ['acc'], 'active_tab': 1},
        #           6: {'widget': self.slope_gb, 'refresh': ['ref'], 'active_tab': 2},
        #           7: {'widget': self.density_gb, 'refresh': ['ref'], 'active_tab': 2}}
        #           # self.depth_gb: {'refresh': ['ref'], 'active_tab': 2}}

        gb_acc_map = [self.custom_info_gb]
                      # self.plot_lim_gb,
                      # self.angle_xline_gb,
                      # self.depth_xline_gb,
                      # self.bs_xline_gb,
                      # self.dz_gb]

        gb_ref_map = [self.slope_gb,
                      self.density_gb,
                      self.depth_ref_gb,
                      self.uncertainty_gb]

        gb_all_map = [self.pt_count_gb,
                      self.plot_lim_gb]  # refresh acc and ref plot if depth_gb is activated

        cbox_map = [self.model_cbox,
                    self.pt_size_cbox,
                    self.pt_size_cov_cbox,
                    self.pt_alpha_cbox,
                    self.ref_cbox,
                    self.depth_mode_cbox]  # only one reference in cbox so far

        chk_acc_map = [self.show_acc_proc_text_chk,
                       # self.grid_lines_toggle_chk,
                       self.IHO_lines_toggle_chk,
                       self.set_zero_mean_chk]

        chk_ref_map = [self.update_ref_plots_chk,
                       self.show_xline_cov_chk,
                       self.show_ref_proc_text_chk]

        chk_all_map = [self.grid_lines_toggle_chk,
                       self.show_u_plot_chk,
                       self.show_model_chk,
                       self.show_ship_chk,
                       self.show_cruise_chk]

        tb_all_map = [self.ship_tb,
                      self.cruise_tb,
                      self.max_count_tb,
                      self.dec_fac_tb]
                      # self.waterline_tb]

        tb_acc_map = [self.max_beam_angle_tb,
                      self.angle_spacing_tb,
                      self.max_bias_tb,
                      self.max_std_tb]

        tb_ref_map = [self.min_depth_ref_tb,
                      self.max_depth_ref_tb,
                      self.max_slope_tb,
                      self.min_dens_tb,
                      self.max_u_tb,
                      self.axis_margin_tb]

        tb_recalc_bins_map = [self.min_depth_xline_tb,
                              self.max_depth_xline_tb,
                              self.min_angle_xline_tb,
                              self.max_angle_xline_tb,
                              self.max_bs_xline_tb,
                              self.min_bs_xline_tb,
                              self.max_dz_tb,
                              self.max_dz_wd_tb,
                              self.min_bin_count_tb,
                              self.mean_bias_angle_lim_tb]

        tb_recalc_dz_map = [self.min_depth_ref_tb,
                            self.max_depth_ref_tb,
                            self.max_slope_tb,
                            self.min_dens_tb,
                            self.max_u_tb]

        gb_recalc_bins_map = [self.depth_xline_gb,
                              self.angle_xline_gb,
                              self.bs_xline_gb,
                              self.dz_gb,
                              self.depth_mode_gb,
                              self.bin_count_gb,
                              self.flatten_mean_gb]

        gb_recalc_dz_map = [self.depth_ref_gb,
                            self.slope_gb,
                            self.uncertainty_gb,
                            self.density_gb]

        # for i, gb in gb_map.items():
        #     print('running through gb_map with gb=', gb)
        #     print('settings[refresh]=', gb['refresh'], 'and active_tab = ', gb['active_tab'])
        # # groupboxes tend to not have objectnames, so use generic sender string
        #     gb['widget'].clicked.connect(lambda: refresh_plot(self,
        #                                             refresh_list=gb['refresh'],
        #                                             sender=str(gb['widget'].objectName()).split('.')[-1],
        #                                             set_active_tab=gb['active_tab']))

        for gb in gb_acc_map:
            # groupboxes tend to not have objectnames, so use generic sender string
            gb.clicked.connect(lambda:
                               refresh_plot(self, refresh_list=['acc'], sender='GROUPBOX_CHK', set_active_tab=0))

        for gb in gb_ref_map:
            # groupboxes tend to not have objectnames, so use generic sender string
            gb.clicked.connect(lambda:
                               refresh_plot(self, refresh_list=['ref'], sender='GROUPBOX_CHK', set_active_tab=1))

            gb.clicked.connect(lambda: calc_accuracy(self, recalc_dz_only=True))  # recalculate xline dz after ref filt

        for gb in gb_all_map:
            # groupboxes tend to not have objectnames, so use generic sender string
            gb.clicked.connect(lambda:
                               refresh_plot(self, refresh_list=['acc', 'ref'], sender='GROUPBOX_CHK', set_active_tab=0))

        for gb in gb_recalc_bins_map:
            gb.clicked.connect(lambda: calc_accuracy(self, recalc_bins_only=True))

        for cbox in cbox_map:
            # lambda needs _ for cbox
            cbox.activated.connect(lambda _, sender=cbox.objectName():
                                   refresh_plot(self, sender=sender))  # refresh_list not specified, will update all

        # for cbox in cbox_recalc_map:
        #     lambda needs _ for cbox
            # cbox.activated.connect(lambda _, sender=cbox.objectName():
            #                        refresh_plot(self, sender=sender))  # refresh_list not specified, will update all

        for chk in chk_acc_map:
            # lambda needs _ for chk
            chk.stateChanged.connect(lambda _, sender=chk.objectName():
                                     refresh_plot(self, refresh_list=['acc'], sender=sender, set_active_tab=0))

        for chk in chk_ref_map:
            # lambda needs _ for chk
            chk.stateChanged.connect(lambda _, sender=chk.objectName():
                                     refresh_plot(self, refresh_list=['ref'], sender=sender, set_active_tab=1))

        for chk in chk_all_map:
            # lambda needs _ for chk
            chk.stateChanged.connect(lambda _, sender=chk.objectName():
                                     refresh_plot(self, sender=sender))  # refresh_list not specified, will update all

        for tb in tb_acc_map:
            # lambda seems to not need _ for tb
            tb.returnPressed.connect(lambda sender=tb.objectName():
                                     refresh_plot(self, refresh_list=['acc'], sender=sender, set_active_tab=0))

        for tb in tb_ref_map:
            # lambda seems to not need _ for tb
            tb.returnPressed.connect(lambda sender=tb.objectName():
                                     refresh_plot(self, refresh_list=['ref'], sender=sender, set_active_tab=1))


        for tb in tb_all_map:
            # lambda seems to not need _ for tb
            tb.returnPressed.connect(lambda sender=tb.objectName():
                                     refresh_plot(self, sender=sender))

        for tb in tb_recalc_bins_map:
            # lambda seems to not need _ for tb
            tb.returnPressed.connect(lambda sender=tb.objectName():
                                     calc_accuracy(self, recalc_bins_only=True))

        for tb in tb_recalc_dz_map:
            tb.returnPressed.connect(lambda sender=tb.objectName():
                                     calc_accuracy(self, recalc_dz_only=True))

    def set_left_layout(self):
        btnh = 20  # height of file control button
        btnw = 100  # width of file control button

        # add reference surface import options (processed elsewhere, XYZ in meters positive up, UTM 1-60N through 1-60S)
        self.add_ref_surf_btn = PushButton('Add Ref. Surface', btnw, btnh, 'add_ref_surf_btn',
                                           'Add a reference surface in UTM projection with northing, easting, and '
                                           'depth in meters, with depth positive up / negative down.')
        self.add_dens_surf_btn = PushButton('Add Dens. Surface', btnw, btnh, 'add_ref_surf_btn',
                                           'Add a sounding density surface corresponding to the reference surface, if '
                                           'needed (e.g., Qimera .xyz exports do not include sounding density. '
                                           'A density layer can be exported from the same surface as .xyz, changed to '
                                           '.xyd for clarity, and imported here to support filtering by sounding count')

        proj_list = [str(i) + 'N' for i in range(1, 61)]  # list of all UTM zones, 1-60N and 1-60S
        proj_list.extend([str(i) + 'S' for i in range(1, 61)])
        EPSG_list = [str(i) for i in range(32601, 32661)]  # list of EPSG codes for WGS84 UTM1-60N
        EPSG_list.extend([str(i) for i in range(32701, 32761)])  # add EPSG codes for WGS84 UTM1-60S
        self.proj_dict = dict(zip(proj_list, EPSG_list))  # save for lookup during xline UTM zone conversion with pyproj
        self.ref_proj_cbox = ComboBox(proj_list, 50, 20, 'ref_proj_cbox', 'Select the reference surface UTM projection')
        ref_cbox_layout = BoxLayout([Label('Proj.:', 50, 20, 'ref_proj_lbl', (Qt.AlignRight | Qt.AlignVCenter)),
                                     self.ref_proj_cbox], 'h')
        # ref_cbox_layout.addStretch()
        ref_btn_layout = BoxLayout([self.add_ref_surf_btn, self.add_dens_surf_btn, ref_cbox_layout], 'v')
        ref_utm_gb = GroupBox('Reference Surface', ref_btn_layout, False, False, 'ref_surf_gb')

        # add crossline file control buttons and file list
        self.add_file_btn = PushButton('Add Crosslines', btnw, btnh, 'add_xlines_btn', 'Add crossline files')
        self.get_indir_btn = PushButton('Add Directory', btnw, btnh, 'get_indir_btn', 'Add a directory')
        self.include_subdir_chk = CheckBox('Incl. subfolders', False, 'include_subdir_chk',
                                           'Include subdirectories when adding a directory')
        self.show_path_chk = CheckBox('Show file paths', False, 'show_paths_chk', 'Show file paths')
        self.get_outdir_btn = PushButton('Select Output Dir.', btnw, btnh, 'get_outdir_btn',
                                         'Select the output directory (see current directory below)')
        self.rmv_file_btn = PushButton('Remove Selected', btnw, btnh, 'rmv_file_btn', 'Remove selected files')
        self.clr_file_btn = PushButton('Remove All Files', btnw, btnh, 'clr_file_btn', 'Remove all files')
        source_btn_layout = BoxLayout([self.add_file_btn, self.get_indir_btn, self.get_outdir_btn, self.rmv_file_btn,
                                       self.clr_file_btn, self.include_subdir_chk, self.show_path_chk], 'v')
        source_btn_gb = GroupBox('Crosslines', source_btn_layout, False, False, 'source_btn_gb')

        # add tide file control buttons
        self.add_tide_btn = PushButton('Add Tide', btnw, btnh, 'add_tide_btn',
                                       'Add a tide (.tid) text file to apply to the accuracy crosslines.\n\n'
                                       'Each line of the tide file is space-delimited with'
                                       '[YYYY/MM/DD hh:mm:ss amplitude] in meters, positive up.\n\n'
                                       'The time zone is assumed to match that used in the accuracy crossline files '
                                       'and the vertical datum is assumed to match that used during processing of the '
                                       'reference surface.')

        tide_btn_gb = GroupBox('Tide', BoxLayout([self.add_tide_btn], 'v'), False, False, 'tide_btn_gb')

        self.calc_accuracy_btn = PushButton('Calc Accuracy', btnw, btnh, 'calc_accuracy_btn',
                                            'Calculate accuracy from loaded files')
        self.save_plot_btn = PushButton('Save Plot', btnw, btnh, 'save_plot_btn', 'Save current plot')
        plot_btn_gb = GroupBox('Plot Data', BoxLayout([self.calc_accuracy_btn, self.save_plot_btn], 'v'),
                               False, False, 'plot_btn_gb')
        # plot_btn_gb.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.MinimumExpanding)
        file_btn_layout = BoxLayout([ref_utm_gb, source_btn_gb, tide_btn_gb, plot_btn_gb], 'v', add_stretch=True)
        self.file_list = FileList()  # add file list with extended selection and icon size = (0,0) to avoid indent
        self.file_list.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.Minimum)
        # self.file_list.setMaximumWidth(500)
        # file_layout = BoxLayout([self.file_list, file_btn_layout], 'h')
        file_gb = GroupBox('Sources', BoxLayout([self.file_list, file_btn_layout], 'h'), False, False, 'file_gb')
        file_gb.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.MinimumExpanding)

        # add activity log widget
        self.log = TextEdit("background-color: lightgray", True, 'log')
        self.log.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.Minimum)
        # self.log.setMaximumWidth(500)

        # self.log.setMaximumSize(350,50)
        # self.log.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)

        update_log(self, '*** New swath accuracy processing log ***')
        log_gb = GroupBox('Activity Log', BoxLayout([self.log], 'v'), False, False, 'log_gb')

        # add progress bar for total file list and layout
        self.current_file_lbl = Label('Current File:')
        self.current_outdir_lbl = Label('Current output directory:\n' + self.output_dir)
        calc_pb_lbl = Label('Total Progress:')
        self.calc_pb = QtWidgets.QProgressBar()
        self.calc_pb.setGeometry(0, 0, 100, 30)
        self.calc_pb.setMaximum(100)  # this will update with number of files
        self.calc_pb.setValue(0)
        self.calc_pb.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.Minimum)
        # self.calc_pb.setMaximumSize(300,30)
        # self.calc_pb.setMaximumWidth(500)
        calc_pb_layout = BoxLayout([calc_pb_lbl, self.calc_pb], 'h')
        self.prog_layout = BoxLayout([self.current_file_lbl, self.current_outdir_lbl], 'v')
        self.prog_layout.addLayout(calc_pb_layout)

        # set the left panel layout with file controls on top and log on bottom
        self.left_layout = BoxLayout([file_gb, log_gb, self.prog_layout], 'v')

    def set_center_layout(self):  # set center layout with swath coverage plot
        # add figure instance and layout for swath accuracy plots
        self.swath_canvas_height = 10
        self.swath_canvas_width = 10
        self.swath_figure = Figure(figsize=(self.swath_canvas_width, self.swath_canvas_height))
        self.swath_canvas = FigureCanvas(self.swath_figure)  # canvas widget that displays the figure
        self.swath_canvas.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding,
                                        QtWidgets.QSizePolicy.MinimumExpanding)
        self.swath_toolbar = NavigationToolbar(self.swath_canvas, self) # swath plot toolbar
        self.x_max = 0.0
        self.y_max = 0.0
        self.swath_layout = BoxLayout([self.swath_toolbar, self.swath_canvas], 'v')

        # add figure instance and layout for reference surface plots
        self.surf_canvas_height = 10
        self.surf_canvas_width = 10
        self.surf_figure = Figure(figsize=(self.surf_canvas_width, self.surf_canvas_height))
        self.surf_canvas = FigureCanvas(self.surf_figure)
        self.surf_canvas.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding,
                                       QtWidgets.QSizePolicy.MinimumExpanding)
        self.surf_toolbar = NavigationToolbar(self.surf_canvas, self)
        self.x_max_surf = 0.0
        self.y_max_surf = 0.0
        self.surf_layout = BoxLayout([self.surf_toolbar, self.surf_canvas], 'v')

        # add figure instance and layout for large final masked reference surface
        # self.surf_canvas_height = 10
        # self.surf_canvas_width = 10
        self.surf_final_figure = Figure(figsize=(self.surf_canvas_width, self.surf_canvas_height))
        self.surf_final_canvas = FigureCanvas(self.surf_final_figure)
        self.surf_final_canvas.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding,
                                             QtWidgets.QSizePolicy.MinimumExpanding)
        self.surf_final_toolbar = NavigationToolbar(self.surf_final_canvas, self)
        # self.x_max_surf = 0.0
        # self.y_max_surf = 0.0
        self.surf_final_layout = BoxLayout([self.surf_final_toolbar, self.surf_final_canvas], 'v')

        # add figure instance and layout for tide plot
        self.tide_canvas_height = 10
        self.tide_canvas_width = 10
        self.tide_figure = Figure(figsize=(self.tide_canvas_width, self.tide_canvas_height))
        self.tide_canvas = FigureCanvas(self.tide_figure)
        self.tide_canvas.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding,
                                       QtWidgets.QSizePolicy.MinimumExpanding)
        self.tide_toolbar = NavigationToolbar(self.tide_canvas, self)
        self.x_max_tide = 0.0
        self.y_max_tide = 0.0
        self.tide_layout = BoxLayout([self.tide_toolbar, self.tide_canvas], 'v')

        # set up tabs
        self.plot_tabs = QtWidgets.QTabWidget()
        self.plot_tabs.setStyleSheet("background-color: none")
        self.plot_tabs.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Maximum)

        # set up tab 1: accuracy results
        self.plot_tab1 = QtWidgets.QWidget()
        self.plot_tab1.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Maximum)
        self.plot_tab1.layout = self.swath_layout
        self.plot_tab1.setLayout(self.plot_tab1.layout)

        # set up tab 2: reference surface
        self.plot_tab2 = QtWidgets.QWidget()
        self.plot_tab2.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Maximum)
        self.plot_tab2.layout = self.surf_layout
        self.plot_tab2.setLayout(self.plot_tab2.layout)

        # set up tab 3: final masked reference surface
        self.plot_tab3 = QtWidgets.QWidget()
        self.plot_tab3.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Maximum)
        self.plot_tab3.layout = self.surf_final_layout
        self.plot_tab3.setLayout(self.plot_tab3.layout)

        # set up tab 4: crossline tide
        self.plot_tab4 = QtWidgets.QWidget()
        self.plot_tab4.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Maximum)
        self.plot_tab4.layout = self.tide_layout
        self.plot_tab4.setLayout(self.plot_tab4.layout)

        # add tabs to tab layout
        self.plot_tabs.addTab(self.plot_tab1, 'Accuracy')
        self.plot_tabs.addTab(self.plot_tab2, 'Ref. Surf. Filter')
        self.plot_tabs.addTab(self.plot_tab3, 'Ref. Surf. Final')
        self.plot_tabs.addTab(self.plot_tab4, 'Tide')

        self.center_layout = BoxLayout([self.plot_tabs], 'v')
        # self.center_layout.addStretch()

    def set_right_layout(self):
        # set right layout with swath plot controls

        # TAB 1: PLOT OPTIONS
        # add text boxes for system, ship, cruise
        model_tb_lbl = Label('Model:', width=100, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.model_cbox = ComboBox(self.model_list, 100, 20, 'model_cbox', 'Select the model')
        self.show_model_chk = CheckBox('', True, 'show_model_chk', 'Show model in plot title')
        model_info_layout_left = BoxLayout([model_tb_lbl, self.model_cbox], 'h', alignment=(Qt.AlignRight | Qt.AlignVCenter))
        model_info_layout = BoxLayout([model_info_layout_left, self.show_model_chk], 'h', alignment=(Qt.AlignRight | Qt.AlignVCenter))

        ship_tb_lbl = Label('Ship Name:', width=100, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.ship_tb = LineEdit('R/V Unsinkable II', 100, 20, 'ship_tb', 'Enter the ship name')
        self.show_ship_chk = CheckBox('', True, 'show_ship_chk', 'Show ship name in plot title')
        ship_info_layout_left = BoxLayout([ship_tb_lbl, self.ship_tb], 'h', alignment=(Qt.AlignRight | Qt.AlignVCenter))
        ship_info_layout = BoxLayout([ship_info_layout_left, self.show_ship_chk], 'h', alignment=(Qt.AlignRight | Qt.AlignVCenter))

        cruise_tb_lbl = Label('Cruise Name:', width=100, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.cruise_tb = LineEdit('A 3-hour tour', 100, 20, 'cruise_tb', 'Enter the cruise name')
        self.show_cruise_chk = CheckBox('', True, 'show_cruise_chk', 'Show cruise in plot title')
        cruise_info_layout_left = BoxLayout([cruise_tb_lbl, self.cruise_tb], 'h', alignment=(Qt.AlignRight | Qt.AlignVCenter))
        cruise_info_layout = BoxLayout([cruise_info_layout_left, self.show_cruise_chk], 'h', alignment=(Qt.AlignRight | Qt.AlignVCenter))

        self.custom_info_gb = GroupBox('Use custom system information',
                                       BoxLayout([model_info_layout, ship_info_layout, cruise_info_layout], 'v'),
                                       True, False, 'custom_info_gb')
        self.custom_info_gb.setToolTip('Add system/cruise info; system info parsed from the file is used if available')

        # add depth reference options and groupbox
        self.ref_cbox = ComboBox(self.data_ref_list, 100, 20, 'ref_cbox',
                                 'Select the reference for plotting depth and acrosstrack distance\n\n'
                                 'As parsed, .all depths are referenced to the TX array and .kmall depths are '
                                 'referenced to the mapping system origin in SIS\n\n'
                                 'Waterline reference is appropriate for normal surface vessel data; '
                                 'other options are available for special cases (e.g., underwater vehicles or '
                                 'troubleshooting installation offset discrepancies)\n\n'
                                 'Overview of adjustments:\n\nWaterline: change reference to the waterline '
                                 '(.all: shift Y and Z ref from TX array to origin, then Z ref to waterline; '
                                 '.kmall: shift Z ref from origin to waterline)\n\n'
                                 'Origin: change reference to the mapping system origin '
                                 '(.all: shift Y and Z ref from TX array to origin; .kmall: no change)\n\n'
                                 'TX Array: change reference to the TX array reference point '
                                 '(.all: no change; .kmall: shift Y and Z ref from origin to TX array)\n\n'
                                 'Raw: use the native depths and acrosstrack distances parsed from the file '
                                 '(.all: referenced to TX array; .kmall: referenced to mapping system origin)')

        data_ref_lbl = Label('Reference data to:', 100, 20, 'data_ref_lbl', (Qt.AlignLeft | Qt.AlignVCenter))
        data_ref_layout = BoxLayout([data_ref_lbl, self.ref_cbox], 'h')

        # add tide units
        self.tide_unit_cbox = ComboBox([unit for unit in self.tide_unit_dict.keys()], 100, 20, 'tide_unit_cbox',
                                 'Select the tide amplitude units')
        tide_unit_lbl = Label('Tide file units:', 100, 20, 'tide_unit_lbl', (Qt.AlignLeft | Qt.AlignVCenter))
        tide_unit_layout = BoxLayout([tide_unit_lbl, self.tide_unit_cbox], 'h')


        # add waterline offset (SIS format, with WL in meters Z+ down from origin)
        waterline_lbl = Label('Adjust waterline (m, pos. down):', width=110, alignment=(Qt.AlignLeft | Qt.AlignVCenter))
        self.waterline_tb = LineEdit('0.00', 30, 20, 'waterline_tb',
                                     'Adjust the SIS waterline (WL) value applied.  WL is the Z offset from the system '
                                     'origin to waterline in meters, positive DOWN (Kongsberg convention).\n\n'
                                     'The value entered here will be added to the WL parsed from the crossline.  For '
                                     'instance, if a crossline is acquired with WL = -3.00 but WL is actually -3.50 m, '
                                     '(WL is 0.50 m higher above the origin, or more negative, than the configured '
                                     'WL), then a WL adjustment of -0.50 can be entered to effectively shift the '
                                     'crossline WL from -3.00 to -3.50 m for processing purposes.  This will cause the '
                                     'crossline data to appear deeper by 0.50 m compared to default as acquired.\n\n'
                                     'NOTE: Waterline adjustment applies to crosslines only.  No change is made to the '
                                     'reference surface.')
        self.waterline_tb.setValidator(QDoubleValidator(-1*np.inf, np.inf, 2))
        waterline_layout = BoxLayout([waterline_lbl, self.waterline_tb], 'h')

        # ref_unit_layout = BoxLayout([data_ref_layout, tide_unit_layout], 'v')
        ref_unit_layout = BoxLayout([data_ref_layout, tide_unit_layout, waterline_layout], 'v')

        # self.data_ref_gb = GroupBox('Data reference', data_ref_layout, False, False, 'data_ref_gb')
        self.data_ref_gb = GroupBox('Data reference and units', ref_unit_layout, False, False, 'data_ref_gb')

        # add point size and opacity comboboxes
        # pt_size_lbl = Label('Point size:', width=60, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        # self.pt_size_cbox = ComboBox([str(pt) for pt in range(11)], 45, 20, 'pt_size_cbox', 'Select point size')
        # self.pt_size_cbox.setCurrentIndex(5)
        # pt_size_layout = BoxLayout([pt_size_lbl, self.pt_size_cbox], 'h', add_stretch=True)

        pt_size_lbl = Label('Point size:', width=60, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.pt_size_cbox = ComboBox([str(pt) for pt in range(11)], 45, 20, 'pt_size_cbox',
                                     'Select point size for soundings in the accuracy plot')
        self.pt_size_cbox.setCurrentIndex(1)
        self.pt_size_cov_cbox = ComboBox([str(pt) for pt in range(11)], 45, 20, 'pt_size_cov_cbox',
                                         'Select point size for soundings in the coverage plot (if shown)')
        self.pt_size_cov_cbox.setCurrentIndex(5)
        pt_size_layout = BoxLayout([pt_size_lbl, self.pt_size_cbox, self.pt_size_cov_cbox], 'h')

        pt_size_blank = Label('                ', width=60, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        pt_size_acc_cov_lbl = Label('Accuracy  Coverage', width=150, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        pt_size_lbl_layout = BoxLayout([pt_size_blank, pt_size_acc_cov_lbl], 'h')

        # add point transparency/opacity slider (can help to visualize density of data)
        pt_alpha_lbl = Label('Opacity (%):', width=60, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.pt_alpha_cbox = ComboBox([str(10 * pt) for pt in range(11)], 45, 20, 'pt_alpha_cbox', 'Select opacity')
        self.pt_alpha_cbox.setCurrentIndex(self.pt_alpha_cbox.count() - 1)  # update opacity to greatest value
        pt_alpha_layout = BoxLayout([pt_alpha_lbl, self.pt_alpha_cbox], 'h', add_stretch=True)

        # set final point parameter layout
        # pt_param_layout = BoxLayout([pt_size_layout, pt_alpha_layout], 'v')
        pt_param_layout = BoxLayout([pt_size_lbl_layout, pt_size_layout, pt_alpha_layout], 'v')
        pt_param_gb = GroupBox('Point style', pt_param_layout, False, False, 'pt_param_gb')

        # add custom plot axis limits
        max_beam_angle_lbl = Label('Max beam angle (deg):', width=110, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.max_beam_angle_tb = LineEdit('', 50, 20, 'max_beam_angle_tb', 'Set the maximum plot angle (X axis)')
        self.max_beam_angle_tb.setValidator(QDoubleValidator(0, 90, 2))
        max_beam_angle_layout = BoxLayout([max_beam_angle_lbl, self.max_beam_angle_tb], 'h')

        angle_spacing_lbl = Label('Angle spacing (deg):', width=110, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.angle_spacing_tb = LineEdit('', 50, 20, 'angle_spacing_tb', 'Set the angle tick spacing')
        self.angle_spacing_tb.setValidator(QDoubleValidator(0, 90, 2))
        angle_spacing_layout = BoxLayout([angle_spacing_lbl, self.angle_spacing_tb], 'h')

        max_bias_lbl = Label('Max bias (' + self.unit_mode + '):', width=110,
                             alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.max_bias_tb = LineEdit('', 50, 20, 'max_bias_tb', 'Set the maximum plot bias (Y axis)')
        self.max_bias_tb.setValidator(QDoubleValidator(0, 100, 2))
        max_bias_layout = BoxLayout([max_bias_lbl, self.max_bias_tb], 'h')

        max_std_lbl = Label('Max st. dev. (' + self.unit_mode + '):', width=110,
                            alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.max_std_tb = LineEdit('', 50, 20, 'max_std_tb', 'Set the maximum plot standard deviation (Y axis)')
        self.max_std_tb.setValidator(QDoubleValidator(0, 100, 2))
        max_std_layout = BoxLayout([max_std_lbl, self.max_std_tb], 'h')

        axis_margin_lbl = Label('Ref. plot margins (%)', width=110, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.axis_margin_tb = LineEdit('', 50, 20, 'axis_margin_tb', 'Set the reference plot axis margins (%)')
        self.axis_margin_tb.setValidator(QDoubleValidator(0, 100, 2))
        axis_margin_layout = BoxLayout([axis_margin_lbl, self.axis_margin_tb], 'h')

        # autoscale_lbl = Label('Autoscale')

        # plot_lim_layout = BoxLayout([max_beam_angle_layout, angle_spacing_layout, max_bias_layout, max_std_layout], 'v')
        plot_lim_layout = BoxLayout([max_beam_angle_layout, angle_spacing_layout, max_bias_layout, max_std_layout,
                                     axis_margin_layout], 'v')

        self.plot_lim_gb = GroupBox('Use custom plot limits', plot_lim_layout, True, False, 'plot_lim_gb')

        # add check boxes with other options
        self.show_acc_proc_text_chk = CheckBox('Show crossline proc. params.', False, 'show_acc_proc_text_chk',
                                               'Show text box with crossline processing/filtering information')
        self.show_ref_proc_text_chk = CheckBox('Show reference proc. params.', False, 'show_ref_proc_text_chk',
                                               'Show text box with reference surface processing/filtering information')
        self.grid_lines_toggle_chk = CheckBox('Show grid lines', True, 'show_grid_lines_chk', 'Show grid lines')
        self.IHO_lines_toggle_chk = CheckBox('Show IHO lines', True, 'show_IHO_lines_chk', 'Show IHO lines')
        self.update_ref_plots_chk = CheckBox('Show filtered reference data', True, 'show_filtered_ref_chk',
                                             'Update reference surface subplots with depth, density, and slope filters'
                                             'applied (uncheck to show the reference surface data as parsed).\n\n'
                                             'This option affects plotting only; all reference surface filters are '
                                             'applied prior to crossline analysis.')
        self.show_xline_cov_chk = CheckBox('Show crossline coverage', True, 'show_xline_cov_chk',
                                           'Show crossline soundings (unfiltered) on reference grids')
        self.show_u_plot_chk = CheckBox('Show uncertainty plot if parsed', True, 'show_u_plot_chk',
                                        'Plot the reference surface uncertainty if parsed from .xyz file (zeros if not'
                                        'parsed.\nThis will replace the subplot for the "final" masked surface.')



        toggle_chk_layout = BoxLayout([self.show_acc_proc_text_chk,
                                       self.show_ref_proc_text_chk,
                                       self.grid_lines_toggle_chk,
                                       self.update_ref_plots_chk,
                                       self.show_xline_cov_chk,
                                       self.show_u_plot_chk], 'v')  # self.IHO_lines_toggle_chk], 'v')

        toggle_gb = QtWidgets.QGroupBox('Plot options')
        toggle_gb.setLayout(toggle_chk_layout)

        # options to flatten the mean bias curve to reduce impacts of refraction on the visualization of sounding dist.
        self.set_zero_mean_chk = CheckBox('Force zero mean (remove all biases)', False, 'zero_mean_plot_chk',
                                        'Force the mean to zero for each angle bin; this is to be used only for '
                                        'visualizing the distribution of soundings without other biases (e.g., '
                                        'refraction issues) and does not represent the observed swath performance.')

        mean_bias_angle_lim_lbl = Label('Angle limit for bias calc. (deg)',
                                        width=110, alignment=(Qt.AlignRight | Qt.AlignVCenter))

        self.mean_bias_angle_lim_tb = LineEdit('40', 45, 20, 'mean_bias_angle_lim_tb',
                                               'Set the angle limit (+/- deg to each side) for the desired portion of '
                                               'the swath to use for the mean bias calculations; this is useful for '
                                               'reducing the impacts of significant refraction (e.g., outer swath) on '
                                               'visualization of the sounding distribition, thereby highlighting other '
                                               'biases (e.g., waterline errors) that may have been masked in part by '
                                               'the refraction issues.')

        self.mean_bias_angle_lim_tb.setValidator(QDoubleValidator(1, np.inf, 2))
        mean_bias_angle_lim_layout = BoxLayout([mean_bias_angle_lim_lbl, self.mean_bias_angle_lim_tb], 'h')

        flatten_mean_chk_layout = BoxLayout([mean_bias_angle_lim_layout, self.set_zero_mean_chk], 'v')
        self.flatten_mean_gb = GroupBox('Flatten swath', flatten_mean_chk_layout, True, False, 'flatten_mean_gb')
        # flatten_mean_gb.setLayout(flatten_mean_chk_layout)


        # TAB 2: FILTER OPTIONS: REFERENCE SURFACE
        # add custom depth limits for ref surf
        min_depth_ref_lbl = Label('Min:', alignment=(Qt.AlignRight | Qt.AlignVCenter))
        max_depth_ref_lbl = Label('Max:', alignment=(Qt.AlignRight | Qt.AlignVCenter))

        self.min_depth_ref_tb = LineEdit('0', 40, 20, 'min_depth_ref_tb', 'Min depth of the reference surface data')
        self.max_depth_ref_tb = LineEdit('10000', 40, 20, 'max_depth_ref_tb', 'Max depth of the reference surface data')
        self.min_depth_ref_tb.setValidator(QDoubleValidator(0, float(self.max_depth_ref_tb.text()), 2))
        self.max_depth_ref_tb.setValidator(QDoubleValidator(float(self.min_depth_ref_tb.text()), np.inf, 2))
        depth_ref_layout = BoxLayout([min_depth_ref_lbl, self.min_depth_ref_tb,
                                      max_depth_ref_lbl, self.max_depth_ref_tb], 'h', add_stretch=True)
        self.depth_ref_gb = GroupBox('Depth (m, ref. surf.)', depth_ref_layout, True, False, 'depth_ref_gb')
        self.depth_ref_gb.setToolTip('Hide reference surface data by depth (m, positive down).\n\n'
                                     'Acceptable min/max fall within [0 inf].')

        # add slope calc and filtering options
        slope_win_lbl = Label('Window (cells):', width=50, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.slope_win_cbox = ComboBox(['1x1', '3x3', '5x5', '7x7', '9x9'], 60, 20, 'slope_window_cbox',
                                       'Select the ref. surface moving average window size for slope calculation')
        max_slope_lbl = Label('Max (deg):', width=50, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.max_slope_tb = LineEdit('5', 40, 20, 'max_slope_tb',
                                     'Set the maximum reference surface slope allowed for crossline analysis (maximum '
                                     'slope for each ref. surface node is estimated from maximum N-S and E-W gradients '
                                     'of the reference depth grid after any averaging using the window size selected)')
        self.max_slope_tb.setValidator(QDoubleValidator(0, np.inf, 2))

        slope_win_layout = BoxLayout([slope_win_lbl, self.slope_win_cbox], 'h', add_stretch=True)
        slope_max_layout = BoxLayout([max_slope_lbl, self.max_slope_tb], 'h', add_stretch=True)
        slope_layout = BoxLayout([slope_win_layout, slope_max_layout], 'v')
        self.slope_gb = GroupBox('Slope', slope_layout, True, False, 'slope_win_gb')

        # ref surf sounding density filtering
        min_dens_lbl = Label('Min:', width=50, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.min_dens_tb = LineEdit('10', 40, 20, 'min_dens_tb',
                                    'Set the min. reference surface sounding density allowed for crossline analysis)')
        self.min_dens_tb.setValidator(QDoubleValidator(0, np.inf, 2))

        density_layout = BoxLayout([min_dens_lbl, self.min_dens_tb], 'h', add_stretch=True)
        self.density_gb = GroupBox('Density (soundings/cell)', density_layout, True, False, 'density_gb')

        # ref surf uncertainty filtering
        max_u_lbl = Label('Max:', width=50, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.max_u_tb = LineEdit('10', 40, 20, 'max_u_tb',
                                 'Set the max. reference surface uncertainty allowed for crossline analysis)')
        self.max_u_tb.setValidator(QDoubleValidator(0, np.inf, 2))

        uncertainty_layout = BoxLayout([max_u_lbl, self.max_u_tb], 'h', add_stretch=True)
        self.uncertainty_gb = GroupBox('Uncertainty (m)', uncertainty_layout, True, False, 'uncertainty_gb')

        # set up layout and groupbox for tabs
        tab2_ref_filter_layout = BoxLayout([self.depth_ref_gb, self.uncertainty_gb,
                                            self.density_gb, self.slope_gb], 'v')
        tab2_ref_filter_gb = GroupBox('Reference surface', tab2_ref_filter_layout, False, False, 'tab2_ref_filter_gb')

        # TAB 2: FILTER OPTIONS: ACCURACY CROSSLINES
        # add custom depth limits for crosslines
        min_depth_xline_lbl = Label('Min:', alignment=(Qt.AlignRight | Qt.AlignVCenter))
        max_depth_xline_lbl = Label('Max:', alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.min_depth_xline_tb = LineEdit('0', 40, 20, 'min_depth_tb', 'Min depth of the crossline data')
        self.max_depth_xline_tb = LineEdit('10000', 40, 20, 'max_depth_tb', 'Max depth of the crossline data')
        self.min_depth_xline_tb.setValidator(QDoubleValidator(0, float(self.max_depth_xline_tb.text()), 2))
        self.max_depth_xline_tb.setValidator(QDoubleValidator(float(self.min_depth_xline_tb.text()), np.inf, 2))
        depth_xline_layout = BoxLayout([min_depth_xline_lbl, self.min_depth_xline_tb,
                                        max_depth_xline_lbl, self.max_depth_xline_tb], 'h')
        depth_xline_layout.addStretch()
        self.depth_xline_gb = GroupBox('Depth (m, crosslines)', depth_xline_layout, True, False, 'depth_xline_gb')
        self.depth_xline_gb.setToolTip('Hide crossline data by depth (m, positive down).\n\n'
                                       'Acceptable min/max fall within [0 inf].')

        # add custom swath angle limits (-port, +stbd on [-inf, inf]; not [0, inf] like swath coverage plotter)
        min_angle_xline_lbl = Label('Min:', width=50, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        max_angle_xline_lbl = Label('Max:', width=50, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.min_angle_xline_tb = LineEdit('-75', 40, 20, 'min_angle_xline_tb',
                                           'Set the minimum beam angle for accuracy calculations (port, <= max angle)')
        self.max_angle_xline_tb = LineEdit('75', 40, 20, 'max_angle_xline_tb',
                                           'Set the maximum beam angle for accuracy calulations (stbd, >= min angle)')
        self.min_angle_xline_tb.setValidator(QDoubleValidator(-1*np.inf, float(self.max_angle_xline_tb.text()), 2))
        self.max_angle_xline_tb.setValidator(QDoubleValidator(float(self.min_angle_xline_tb.text()), np.inf, 2))
        # angle_layout = BoxLayout([min_angle_lbl, self.min_angle_tb, max_angle_lbl, self.max_angle_tb], 'h')
        angle_xline_layout = BoxLayout([min_angle_xline_lbl, self.min_angle_xline_tb,
                                        max_angle_xline_lbl, self.max_angle_xline_tb],
                                       'h', add_stretch=True)

        self.angle_xline_gb = GroupBox('Angle (deg)', angle_xline_layout, True, False, 'angle_xline_gb')
        self.angle_xline_gb.setToolTip('Hide soundings based on nominal swath angles calculated from depths and '
                                 'acrosstrack distances; these swath angles may differ slightly from RX beam '
                                 'angles (w.r.t. RX array) due to installation, attitude, and refraction.\n\n'
                                 'Angles are treated as negative to port and positive to starboard.')

        # add custom reported backscatter limits
        min_bs_xline_lbl = Label('Min:', width=50, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.min_bs_xline_tb = LineEdit('-50', 40, 20, 'min_bs_xline_tb',
                                        'Set the minimum reported backscatter (e.g., -50 dB); '
                                        'while backscatter values in dB are inherently negative, the filter range may '
                                        'include positive values to accommodate anomalous reported backscatter data')
        max_bs_xline_lbl = Label('Max:', width=50, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.max_bs_xline_tb = LineEdit('0', 40, 20, 'max_bs_xline_tb',
                                  'Set the maximum reported backscatter of the data (e.g., 0 dB); '
                                  'while backscatter values in dB are inherently negative, the filter range may '
                                  'include positive values to accommodate anomalous reported backscatter data')
        self.min_bs_xline_tb.setValidator(QDoubleValidator(-1 * np.inf, float(self.max_bs_xline_tb.text()), 2))
        self.max_bs_xline_tb.setValidator(QDoubleValidator(float(self.min_bs_xline_tb.text()), np.inf, 2))
        bs_xline_layout = BoxLayout([min_bs_xline_lbl, self.min_bs_xline_tb,
                               max_bs_xline_lbl, self.max_bs_xline_tb], 'h', add_stretch=True)
        self.bs_xline_gb = GroupBox('Backscatter (dB)', bs_xline_layout, True, False, 'bs_xline_gb')
        self.bs_xline_gb.setToolTip('Hide data by reported backscatter amplitude (dB).\n\n'
                                    'Acceptable min/max fall within [-inf inf] to accommodate anomalous data >0.')

        # add custom limits for crossline differences from reference surface
        max_dz_lbl = Label('Meters:', alignment=(Qt.AlignRight | Qt.AlignVCenter))
        max_dz_wd_lbl = Label('%WD:', alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.max_dz_tb = LineEdit('10', 40, 20, 'max_dz_tb', 'Max depth difference from reference surface (m)')
        self.max_dz_wd_tb = LineEdit('10', 40, 20, 'max_dz_wd_tb', 'Max depth difference from reference surface (%WD)')
        self.max_dz_tb.setValidator(QDoubleValidator(0, np.inf, 2))
        self.max_dz_wd_tb.setValidator(QDoubleValidator(0, np.inf, 2))
        max_dz_layout = BoxLayout([max_dz_lbl, self.max_dz_tb, max_dz_wd_lbl, self.max_dz_wd_tb], 'h')
        max_dz_layout.addStretch()
        self.dz_gb = GroupBox('Depth difference (from ref.)', max_dz_layout, True, False, 'dz_gb')
        self.dz_gb.setToolTip('Hide crossline data exceeding an acceptable depth difference from the reference surface '
                              '(meters or percent of water depth, as estimated from the reference surface depth).')

        # self.max_dz_tb = LineEdit('10', 40, 20, 'max_dz_tb', 'Max depth difference from reference surface (m)')
        # self.max_dz_wd_tb = LineEdit('10', 40, 20, 'max_dz_wd_tb', 'Max depth difference from reference surface (%WD)')
        # self.max_dz_tb.setValidator(QDoubleValidator(0, np.inf, 2))
        # self.max_dz_wd_tb.setValidator(QDoubleValidator(0, np.inf, 2))
        # max_dz_layout = BoxLayout([max_dz_lbl, self.max_dz_tb, max_dz_wd_lbl, self.max_dz_wd_tb], 'h')
        # max_dz_layout.addStretch()
        # self.dz_gb = GroupBox('Depth difference (from ref.)', max_dz_layout, True, False, 'dz_gb')
        # self.dz_gb.setToolTip('Hide crossline data exceeding an acceptable depth difference from the reference surface '
        #                       '(meters or percent of water depth, as estimated from the reference surface depth).')

        # add depth mode filter for crossline
        # self.depth_mode_list = ['Very Shallow', 'Shallow', 'Medium', 'Deep', 'Deeper',
        #                         'Very Deep', 'Extra Deep', 'Extreme Deep']
        self.depth_mode_list = ['None']
        self.depth_mode_cbox = ComboBox(self.depth_mode_list, 80, 20, 'depth_mode_cbox',
                                        'Filter crosslines by depth mode(s) found in file(s)')
        depth_mode_layout = BoxLayout([Label('Available mode(s):', 50, 20,'depth_mode_lbl',
                                             (Qt.AlignRight | Qt.AlignVCenter)), self.depth_mode_cbox], 'h')
        self.depth_mode_gb = GroupBox('Depth mode', depth_mode_layout, True, False, 'depth_mode_gb')


        # add minimum sounding count for binning
        min_bin_count_lbl = Label('Min:', width=50, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.min_bin_count_tb = LineEdit('10', 40, 20, 'min_bin_count_tb',
                                         'Set the min. sounding count per angle bin for running accuracy calculations)')
        self.min_bin_count_tb.setValidator(QDoubleValidator(0, np.inf, 2))

        bin_count_layout = BoxLayout([min_bin_count_lbl, self.min_bin_count_tb], 'h', add_stretch=True)
        self.bin_count_gb = GroupBox('Bin count (soundings/bin)', bin_count_layout, True, True, 'bin_count_gb')

        # add plotted point max count and decimation factor control in checkable groupbox
        max_count_lbl = Label('Max. plotted points (0-inf):', width=140, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.max_count_tb = LineEdit(str(self.n_points_max_default), 50, 20, 'max_count_tb',
                                     'Set the maximum number of plotted points for each data set')
        self.max_count_tb.setValidator(QDoubleValidator(0, np.inf, 2))
        max_count_layout = BoxLayout([max_count_lbl, self.max_count_tb], 'h')
        dec_fac_lbl = Label('Decimation factor (1-inf):', width=140, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.dec_fac_tb = LineEdit(str(self.dec_fac_default), 50, 20, 'dec_fac_tb', 'Set the custom decimation factor')
        self.dec_fac_tb.setValidator(QDoubleValidator(1, np.inf, 2))
        dec_fac_layout = BoxLayout([dec_fac_lbl, self.dec_fac_tb], 'h')
        pt_count_layout = BoxLayout([max_count_layout, dec_fac_layout], 'v')
        self.pt_count_gb = GroupBox('Limit plotted point count (plot faster)', pt_count_layout, True, True, 'pt_ct_gb')
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

        # set up layout and groupbox for tabs
        tab2_xline_filter_layout = BoxLayout([self.angle_xline_gb, self.depth_xline_gb, self.dz_gb,
                                              self.bs_xline_gb, self.depth_mode_gb, self.bin_count_gb], 'v')
        tab2_xline_filter_gb = GroupBox('Crosslines', tab2_xline_filter_layout,
                                        False, True, 'tab2_xline_filter_gb')
        tab2_xline_filter_gb.setEnabled(True)

        # set up tabs
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setStyleSheet("background-color: none")

        # set up tab 1: plot options
        self.tab1 = QtWidgets.QWidget()
        self.tab1.layout = BoxLayout([self.custom_info_gb, self.data_ref_gb, pt_param_gb,
                                      self.plot_lim_gb, toggle_gb, self.flatten_mean_gb], 'v')
        self.tab1.layout.addStretch()
        self.tab1.setLayout(self.tab1.layout)

        # set up tab 2: filtering options
        self.tab2 = QtWidgets.QWidget()
        label_in_prog = Label('FILTERS IN PROGRESS\nNOT APPLIED TO DATA')
        label_in_prog.setStyleSheet("color: red")
        # self.tab2.layout = BoxLayout([label_in_prog, self.angle_gb, self.depth_ref_gb, self.depth_xline_gb,
        #                               self.bs_gb, self.slope_gb, self.density_gb], 'v')
        self.tab2.layout = BoxLayout([tab2_ref_filter_gb, tab2_xline_filter_gb, self.pt_count_gb], 'v')

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
        main_layout = QtWidgets.QHBoxLayout()
        main_layout.addLayout(self.left_layout)
        # main_layout.addLayout(self.swath_layout)
        main_layout.addLayout(self.center_layout)
        main_layout.addLayout(self.right_layout)
        
        self.mainWidget.setLayout(main_layout)


class NewPopup(QtWidgets.QWidget): # new class for additional plots
    def __init__(self):
        QtWidgets.QWidget.__init__(self)
        
        
if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)

    main = MainWindow()
    main.show()

    sys.exit(app.exec_())
