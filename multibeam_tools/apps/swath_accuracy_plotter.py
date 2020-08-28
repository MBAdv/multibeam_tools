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

from multibeam_tools.libs.swath_accuracy_lib import *
from multibeam_tools.libs.swath_fun import *
from multibeam_tools.libs.file_fun import *
from multibeam_tools.libs.gui_widgets import *


__version__ = "0.0.5"


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
        init_swath_ax(self)
        init_surf_ax(self)
        update_buttons(self)

        # set up button controls for specific action other than refresh_plot
        # self.add_file_btn.clicked.connect(lambda: self.add_files('Kongsberg(*.all *.kmall)'))
        self.add_file_btn.clicked.connect(lambda: add_acc_files(self, 'Kongsberg (*.all *.kmall)'))
        self.get_indir_btn.clicked.connect(lambda: add_acc_files(self, ['.all', '.kmall'], input_dir=[],
                                                                 include_subdir=self.include_subdir_chk.isChecked()))
        self.get_outdir_btn.clicked.connect(lambda: get_output_dir(self))
        self.add_ref_surf_btn.clicked.connect(lambda: add_ref_file(self, 'Reference surface XYZ(*.xyz)'))
        self.add_dens_surf_btn.clicked.connect(lambda: add_dens_file(self, 'Density surface XYD(*.xyd)'))
        self.rmv_file_btn.clicked.connect(lambda: remove_acc_files(self))
        self.clr_file_btn.clicked.connect(lambda: clear_files(self))
        self.show_path_chk.stateChanged.connect(lambda: show_file_paths(self))
        self.calc_accuracy_btn.clicked.connect(lambda: calc_accuracy(self))
        self.save_plot_btn.clicked.connect(lambda: save_plot(self))
        self.ref_proj_cbox.activated.connect(lambda: parse_ref_depth(self))
        self.slope_win_cbox.activated.connect(lambda: update_ref_slope(self))

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

        gb_acc_map = [self.custom_info_gb,
                      self.plot_lim_gb,
                      self.angle_gb,
                      self.depth_xline_gb,
                      self.bs_gb]

        gb_ref_map = [self.slope_gb,
                      self.density_gb,
                      self.depth_ref_gb]  # refresh acc and ref plot if depth_gb is activated

        cbox_map = [self.model_cbox,
                    self.pt_size_cbox,
                    self.pt_alpha_cbox,
                    self.ref_cbox]  # only one reference in cbox so far

        chk_acc_map = [self.show_acc_proc_text_chk,
                       self.grid_lines_toggle_chk,
                       self.IHO_lines_toggle_chk]

        chk_ref_map = [self.update_ref_plots_chk,
                       self.show_xline_cov_chk,
                       self.show_ref_proc_text_chk]

        tb_acc_map = [self.ship_tb,
                      self.cruise_tb,
                      self.max_beam_angle_tb,
                      self.angle_spacing_tb,
                      self.max_bias_tb,
                      self.max_std_tb,
                      self.min_angle_tb,
                      self.max_angle_tb,
                      self.min_depth_xline_tb,
                      self.max_depth_xline_tb,
                      self.min_bs_tb,
                      self.max_bs_tb]

        tb_ref_map = [self.min_depth_ref_tb,
                      self.max_depth_ref_tb,
                      self.max_slope_tb,
                      self.min_dens_tb]

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

        for cbox in cbox_map:
            # lambda needs _ for cbox
            cbox.activated.connect(lambda _, sender=cbox.objectName():
                                   refresh_plot(self, refresh_list=['acc'], sender=sender, set_active_tab=0))

        for chk in chk_acc_map:
            # lambda needs _ for chk
            chk.stateChanged.connect(lambda _, sender=chk.objectName():
                                     refresh_plot(self, refresh_list=['acc'], sender=sender, set_active_tab=0))

        for chk in chk_ref_map:
            # lambda needs _ for chk
            chk.stateChanged.connect(lambda _, sender=chk.objectName():
                                     refresh_plot(self, refresh_list=['ref'], sender=sender, set_active_tab=1))

        for tb in tb_acc_map:
            # lambda seems to not need _ for tb
            tb.returnPressed.connect(lambda sender=tb.objectName():
                                     refresh_plot(self, refresh_list=['acc'], sender=sender, set_active_tab=0))

        for tb in tb_ref_map:
            # lambda seems to not need _ for tb
            tb.returnPressed.connect(lambda sender=tb.objectName():
                                     refresh_plot(self, refresh_list=['ref'], sender=sender, set_active_tab=1))

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

        # add file control buttons and file list
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

        self.calc_accuracy_btn = PushButton('Calc Accuracy', btnw, btnh, 'calc_accuracy_btn',
                                            'Calculate accuracy from loaded files')
        self.save_plot_btn = PushButton('Save Plot', btnw, btnh, 'save_plot_btn', 'Save current plot')
        plot_btn_gb = GroupBox('Plot Data', BoxLayout([self.calc_accuracy_btn, self.save_plot_btn], 'v'),
                               False, False, 'plot_btn_gb')
        # plot_btn_gb.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.MinimumExpanding)
        file_btn_layout = BoxLayout([ref_utm_gb, source_btn_gb, plot_btn_gb], 'v')
        file_btn_layout.addStretch()
        self.file_list = FileList()  # add file list with extended selection and icon size = (0,0) to avoid indent
        self.file_list.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.Minimum)
        # self.file_list.setMaximumWidth(500)
        # file_layout = BoxLayout([self.file_list, file_btn_layout], 'h')
        file_gb = GroupBox('Sources', BoxLayout([self.file_list, file_btn_layout], 'h'), False, False, 'file_gb')
        file_gb.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.MinimumExpanding)

        # add activity log widget
        self.log = TextEdit("background-color: lightgray", True, 'log')
        self.log.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
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

        # add tabs to tab layout
        self.plot_tabs.addTab(self.plot_tab1, 'Accuracy')
        self.plot_tabs.addTab(self.plot_tab2, 'Reference Surface')

        self.center_layout = BoxLayout([self.plot_tabs], 'v')
        # self.center_layout.addStretch()

    def set_right_layout(self):
        # set right layout with swath plot controls

        # TAB 1: PLOT OPTIONS
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
        self.data_ref_gb = GroupBox('Data reference', data_ref_layout, False, False, 'data_ref_gb')

        # add point size and opacity comboboxes
        pt_size_lbl = Label('Point size:', width=50, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.pt_size_cbox = ComboBox([str(pt) for pt in range(11)], 45, 20, 'pt_size_cbox', 'Select point size')
        self.pt_size_cbox.setCurrentIndex(5)
        pt_size_layout = BoxLayout([pt_size_lbl, self.pt_size_cbox], 'h')
        pt_size_layout.addStretch()

        # add point transparency/opacity slider (can help to visualize density of data)
        pt_alpha_lbl = Label('Opacity (%):', width=50, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.pt_alpha_cbox = ComboBox([str(10 * pt) for pt in range(11)], 45, 20, 'pt_alpha_cbox', 'Select opacity')
        self.pt_alpha_cbox.setCurrentIndex(self.pt_alpha_cbox.count() - 1)  # update opacity to greatest value
        pt_alpha_layout = BoxLayout([pt_alpha_lbl, self.pt_alpha_cbox], 'h')
        pt_alpha_layout.addStretch()

        # set final point parameter layout
        pt_param_layout = BoxLayout([pt_size_layout, pt_alpha_layout], 'v')
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

        plot_lim_layout = BoxLayout([max_beam_angle_layout, angle_spacing_layout, max_bias_layout, max_std_layout], 'v')
        self.plot_lim_gb = GroupBox('Use custom plot limits', plot_lim_layout, True, False, 'plot_lim_gb')

        # add check boxes with other options
        self.show_acc_proc_text_chk = CheckBox('Show crossline processing parameters', False, 'show_acc_proc_text_chk',
                                               'Show text box with crossline processing/filtering information')
        self.show_ref_proc_text_chk = CheckBox('Show reference processing parameters', False, 'show_ref_proc_text_chk',
                                               'Show text box with reference surface processing/filtering information')
        self.grid_lines_toggle_chk = CheckBox('Show grid lines', True, 'show_grid_lines_chk', 'Show grid lines')
        self.IHO_lines_toggle_chk = CheckBox('Show IHO lines', True, 'show_IHO_lines_chk', 'Show IHO lines')
        self.update_ref_plots_chk = CheckBox('Show filtered reference data', True, 'show_filtered_ref_chk',
                                             'Update reference surface subplots with depth, density, and slope filters'
                                             'applied (uncheck to show the reference surface data as parsed).\n\n'
                                             'This option affects plotting only; all reference surface filters are '
                                             'applied prior to crossline analysis.')
        self.show_xline_cov_chk = CheckBox('Show crossline coverage', False, 'show_xline_cov_chk',
                                           'Show crossline soundings (unfiltered) on reference grids')

        toggle_chk_layout = BoxLayout([self.show_acc_proc_text_chk,
                                       self.show_ref_proc_text_chk,
                                       self.grid_lines_toggle_chk,
                                       self.update_ref_plots_chk,
                                       self.show_xline_cov_chk], 'v')  # self.IHO_lines_toggle_chk], 'v')
        toggle_gb = QtWidgets.QGroupBox('Plot Options')
        toggle_gb.setLayout(toggle_chk_layout)



        # TAB 2: FILTER OPTIONS: REFERENCE SURFACE
        # add custom depth limits for ref surf
        min_depth_ref_lbl = Label('Min (m):', alignment=(Qt.AlignRight | Qt.AlignVCenter))
        max_depth_ref_lbl = Label('Max (m):', alignment=(Qt.AlignRight | Qt.AlignVCenter))

        self.min_depth_ref_tb = LineEdit('0', 40, 20, 'min_depth_arc_tb', 'Min depth of the reference surface data')
        self.max_depth_ref_tb = LineEdit('10000', 40, 20, 'max_depth_arc_tb', 'Max depth of the reference surface data')
        self.min_depth_ref_tb.setValidator(QDoubleValidator(0, float(self.max_depth_ref_tb.text()), 2))
        self.max_depth_ref_tb.setValidator(QDoubleValidator(float(self.min_depth_ref_tb.text()), np.inf, 2))
        depth_ref_layout = BoxLayout([min_depth_ref_lbl, self.min_depth_ref_tb,
                                      max_depth_ref_lbl, self.max_depth_ref_tb], 'h')
        self.depth_ref_gb = GroupBox('Depth (reference surface)', depth_ref_layout, True, False, 'depth_ref_gb')
        self.depth_ref_gb.setToolTip('Hide reference surface data by depth (m, positive down).\n\n'
                                     'Acceptable min/max fall within [0 inf].')

        # add slope calc and filtering options
        slope_win_lbl = Label('Window (cells):', width=100, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.slope_win_cbox = ComboBox(['1x1', '3x3', '5x5', '7x7', '9x9'], 60, 20, 'slope_window_cbox',
                                       'Select the ref. surface moving average window size for slope calculation')
        max_slope_lbl = Label('Max (deg):', width=50, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.max_slope_tb = LineEdit('5', 40, 20, 'max_slope_tb',
                                     'Set the maximum reference surface slope allowed for crossline analysis (maximum '
                                     'slope for each ref. surface node is estimated from maximum N-S and E-W gradients '
                                     'of the reference depth grid after any averaging using the window size selected)')
        self.max_slope_tb.setValidator(QDoubleValidator(0, np.inf, 2))

        slope_win_layout = BoxLayout([slope_win_lbl, self.slope_win_cbox], 'h')
        slope_max_layout = BoxLayout([max_slope_lbl, self.max_slope_tb], 'h')
        slope_layout = BoxLayout([slope_win_layout, slope_max_layout], 'v')
        self.slope_gb = GroupBox('Slope', slope_layout, True, False, 'slope_win_gb')

        # ref surf sounding density filtering
        min_dens_lbl = Label('Min (soundings/cell):', width=50, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.min_dens_tb = LineEdit('10', 40, 20, 'min_dens_tb',
                                    'Set the minimum reference surface sounding density allowed for crossline '
                                    'analysis)')
        self.min_dens_tb.setValidator(QDoubleValidator(0, np.inf, 2))

        density_layout = BoxLayout([min_dens_lbl, self.min_dens_tb], 'h')
        self.density_gb = GroupBox('Sounding Density', density_layout, True, False, 'density_gb')

        # set up layout and groupbox for tabs
        tab2_ref_filter_layout = BoxLayout([self.depth_ref_gb, self.density_gb, self.slope_gb], 'v')
        tab2_ref_filter_gb = GroupBox('Reference surface', tab2_ref_filter_layout, False, False, 'tab2_ref_filter_gb')


        # TAB 2: FILTER OPTIONS: ACCURACY CROSSLINES
        # add custom depth limits for crosslines
        min_depth_xline_lbl = Label('Min (m):', alignment=(Qt.AlignRight | Qt.AlignVCenter))
        max_depth_xline_lbl = Label('Max (m):', alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.min_depth_xline_tb = LineEdit('0', 40, 20, 'min_depth_tb', 'Min depth of the crossline data')
        self.max_depth_xline_tb = LineEdit('10000', 40, 20, 'max_depth_tb', 'Max depth of the crossline data')
        self.min_depth_xline_tb.setValidator(QDoubleValidator(0, float(self.max_depth_xline_tb.text()), 2))
        self.max_depth_xline_tb.setValidator(QDoubleValidator(float(self.min_depth_xline_tb.text()), np.inf, 2))
        depth_xline_layout = BoxLayout([min_depth_xline_lbl, self.min_depth_xline_tb,
                                        max_depth_xline_lbl, self.max_depth_xline_tb], 'h')
        self.depth_xline_gb = GroupBox('Depth (crosslines)', depth_xline_layout, True, False, 'depth_xline_gb')
        self.depth_xline_gb.setToolTip('Hide crossline data by depth (m, positive down).\n\n'
                                       'Acceptable min/max fall within [0 inf].')

        # add custom swath angle limits
        min_angle_lbl = Label('Min:', width=50, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        max_angle_lbl = Label('Max:', width=50, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.min_angle_tb = LineEdit('0', 40, 20, 'min_angle_tb', 'Set the minimum angle to plot (<= max angle)')
        self.max_angle_tb = LineEdit('75', 40, 20, 'max_angle_tb', 'Set the maximum angle to plot (>= min angle)')
        self.min_angle_tb.setValidator(QDoubleValidator(0, float(self.max_angle_tb.text()), 2))
        self.max_angle_tb.setValidator(QDoubleValidator(float(self.min_angle_tb.text()), np.inf, 2))
        angle_layout = BoxLayout([min_angle_lbl, self.min_angle_tb, max_angle_lbl, self.max_angle_tb], 'h')
        self.angle_gb = GroupBox('Angle (deg)', angle_layout, True, False, 'angle_gb')
        self.angle_gb.setToolTip('Hide soundings based on nominal swath angles calculated from depths and '
                                 'acrosstrack distances; these swath angles may differ slightly from RX beam '
                                 'angles (w.r.t. RX array) due to installation, attitude, and refraction.')

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
        self.min_bs_tb.setValidator(QDoubleValidator(-1 * np.inf, float(self.max_bs_tb.text()), 2))
        self.max_bs_tb.setValidator(QDoubleValidator(float(self.min_bs_tb.text()), np.inf, 2))
        bs_layout = BoxLayout([min_bs_lbl, self.min_bs_tb, max_bs_lbl, self.max_bs_tb], 'h')
        self.bs_gb = GroupBox('Backscatter (dB)', bs_layout, True, False, 'bs_gb')
        self.bs_gb.setToolTip('Hide data by reported backscatter amplitude (dB).\n\n'
                              'Acceptable min/max fall within [-inf inf] to accommodate anomalous data >0.')

        # set up layout and groupbox for tabs
        tab2_xline_filter_layout = BoxLayout([self.angle_gb, self.depth_xline_gb, self.bs_gb], 'v')
        tab2_xline_filter_gb = GroupBox('Crosslines', tab2_xline_filter_layout, False, False, 'tab2_xline_filter_gb')

        # # # add custom depth limits in combined layout
        # min_depth_lbl = Label('Min depth (m):', alignment=(Qt.AlignRight | Qt.AlignVCenter))
        # max_depth_lbl = Label('Max depth (m):', alignment=(Qt.AlignRight | Qt.AlignVCenter))
        # self.min_depth_xline_tb = LineEdit('0', 40, 20, 'min_depth_tb', 'Min depth of the crossline data')
        # self.min_depth_ref_tb = LineEdit('0', 40, 20, 'min_depth_arc_tb', 'Min depth of the reference surface data')
        # self.max_depth_xline_tb = LineEdit('10000', 40, 20, 'max_depth_tb', 'Max depth of the crossline data')
        # self.max_depth_ref_tb = LineEdit('10000', 40, 20, 'max_depth_arc_tb', 'Max depth of the reference surface data')
        # self.min_depth_xline_tb.setValidator(QDoubleValidator(0, float(self.max_depth_xline_tb.text()), 2))
        # self.max_depth_xline_tb.setValidator(QDoubleValidator(float(self.min_depth_xline_tb.text()), np.inf, 2))
        # self.min_depth_ref_tb.setValidator(QDoubleValidator(0, float(self.max_depth_ref_tb.text()), 2))
        # self.max_depth_ref_tb.setValidator(QDoubleValidator(float(self.min_depth_ref_tb.text()), np.inf, 2))
        # depth_layout_left = BoxLayout([QtWidgets.QLabel(''), min_depth_lbl, max_depth_lbl], 'v')
        # depth_layout_center = BoxLayout([QtWidgets.QLabel('Crossline'), self.min_depth_xline_tb, self.max_depth_xline_tb], 'v')
        # depth_layout_right = BoxLayout([QtWidgets.QLabel('Ref. Surf.'), self.min_depth_ref_tb, self.max_depth_ref_tb], 'v')
        # depth_layout = BoxLayout([depth_layout_left, depth_layout_center, depth_layout_right], 'h')
        # self.depth_gb = GroupBox('Depth (crossline / reference)', depth_layout, True, False, 'depth_gb')
        # self.depth_gb.setToolTip('Hide data by depth (m, positive down).\n\nAcceptable min/max fall within [0 inf].')


        # set up tabs
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setStyleSheet("background-color: none")

        # set up tab 1: plot options
        self.tab1 = QtWidgets.QWidget()
        self.tab1.layout = BoxLayout([self.custom_info_gb, self.data_ref_gb, pt_param_gb,
                                      self.plot_lim_gb, toggle_gb], 'v')
        self.tab1.layout.addStretch()
        self.tab1.setLayout(self.tab1.layout)

        # set up tab 2: filtering options
        self.tab2 = QtWidgets.QWidget()
        label_in_prog = Label('FILTERS IN PROGRESS\nNOT APPLIED TO DATA')
        label_in_prog.setStyleSheet("color: red")
        # self.tab2.layout = BoxLayout([label_in_prog, self.angle_gb, self.depth_ref_gb, self.depth_xline_gb,
        #                               self.bs_gb, self.slope_gb, self.density_gb], 'v')
        self.tab2.layout = BoxLayout([tab2_ref_filter_gb, tab2_xline_filter_gb], 'v')

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
