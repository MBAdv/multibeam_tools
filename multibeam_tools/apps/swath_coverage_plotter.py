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

import sys
sys.path.append('C:\\Users\\kjerram\\Documents\\GitHub')  # add path to outer directory for pyinstaller

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from multibeam_tools.libs.gui_widgets import *
from multibeam_tools.libs.swath_coverage_lib import *
import matplotlib.pyplot as plt


__version__ = "0.2.1"


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
        init_all_axes(self)

        # add fname annotations from SO example (moved to setup)
        # self.annot = self.data_rate_ax1.annotate("", xy=(0, 0), xytext=(20, 20), textcoords="offset points",
        # 										 bbox=dict(boxstyle="round", fc="w"),
        # 										 arrowprops=dict(arrowstyle="->"))
        # self.annot.set_visible(False)

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
        self.scbtn.clicked.connect(lambda: update_solid_color(self, 'color'))
        self.scbtn_arc.clicked.connect(lambda: update_solid_color(self, 'color_arc'))
        self.export_gf_btn.clicked.connect(lambda: export_gap_filler_trend(self))
        self.param_search_btn.clicked.connect(lambda: update_param_search(self))
        self.save_param_log_btn.clicked.connect(lambda: save_param_log(self))

        # set up event actions that call refresh_plot
        gb_map = [self.custom_info_gb,
                  self.plot_lim_gb,
                  self.rtp_angle_gb,
                  self.rtp_cov_gb,
                  self.angle_gb,
                  self.depth_gb,
                  self.bs_gb,
                  self.angle_lines_gb,
                  self.n_wd_lines_gb,
                  self.pt_count_gb,
                  self.ping_int_gb]

        cbox_map = [self.model_cbox,
                    self.pt_size_cbox,
                    self.pt_alpha_cbox,
                    self.color_cbox,
                    self.color_cbox_arc,
                    self.clim_cbox,
                    self.top_data_cbox,
                    self.ref_cbox]

        chk_map = [self.show_data_chk,
                   self.show_data_chk_arc,
                   self.grid_lines_toggle_chk,
                   self.colorbar_chk,
                   self.clim_filter_chk,
                   self.spec_chk,
                   self.show_ref_fil_chk,
                   self.show_hist_chk,
                   self.match_data_cmodes_chk,
                   self.show_model_chk,
                   self.show_ship_chk,
                   self.show_cruise_chk,
                   self.show_coverage_trend_chk]

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
                  self.max_clim_tb,
                  self.min_ping_int_tb,
                  self.max_ping_int_tb,
                  self.max_dr_tb,
                  self.max_pi_tb]

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

        # set up annotations on hovering
        self.swath_canvas.mpl_connect('motion_notify_event', self.hover)
        self.data_canvas.mpl_connect('motion_notify_event', self.hover_data)
        # self.swath_canvas.mpl_connect('motion_notify_event', self.hover)
        # plt.show()


    # def update_annotation(self, ind, text):  # update annotations on plot (e.g., show fname on hover); adapted from SO example
    #     text_all = [self.fnames_sorted[n] for n in ind["ind"]]
    #     text_set = [t for t in set(text_all)]  # list of unique filenames (returns alphabetical order)
        #
        # text_set = list(dict.fromkeys(text_all).keys())  # list of unique filenames that preserves order
        #
        # print('text_all =', text_all)
        # print('text_set =', text_set)
        #
        # print('len(det) and len(text_all)= ', len(self.det['fname']), len(text_all))
        #
        # self.annot.set_text(text_set[0])  #
        # self.sounding_fname = text_set[0].replace('[\'','').replace('\']','')


    def hover_data(self, event):  # adapted from SO example
        # print('\n\nnew hover event!')
        if self.det:
            # print('det exists, making ax_dict')
            ax_dict = dict(zip([self.data_rate_ax1, self.data_rate_ax2],
                               [self.h_data_rate_smoothed, self.h_ping_interval]))

        else:
            # print('det does not exist, returning...')
            return

        for ax in ax_dict.keys():
            # print('working on ax = ', ax)
            # print('*event.inaxes = ', event.inaxes)

            if event.inaxes == ax:  # check if event is in this axis
                # print('***event is in a data rate ax')
                cont, ind = ax_dict[ax].contains(event)  # check if the scatter plot contains this event
                # print('cont, ind =', cont, ind)

                if cont:
                    # print('cont is true')
                    # self.update_annotation(ind)
                    # self.data_canvas.draw_idle()
                    text_all = [self.fnames_sorted[n] for n in ind["ind"]]  # fnames sorted per data plots
                    self.sounding_fname = text_all[0].replace('[\'','').replace('\']','')

                    self.sounding_file_lbl.setText('Cursor: ' + self.sounding_fname)
                    return  # leave after updating
                else:
                    # print('cont is NOT true')
                    self.sounding_file_lbl.setText('Cursor: ' + self.sounding_fname_default)


    def hover(self, event):  # adapted from SO example
        if not self.det:
            return

        # print('working on swath_ax=', self.swath_ax)
        # print('*event.inaxes = ', event.inaxes)
        # print('are these equal --> ', event.inaxes == self.swath_ax)

        if event.inaxes == self.swath_ax:
            # print('event.inaxes == self.swath_ax')
            cont, ind = self.h_swath.contains(event)
            # print('cont, ind =', cont, ind)
            if cont:
                # print('cont is true')
                text_all = [self.fnames_all[n] for n in ind["ind"]]  # fnames_all from plot_coverage step
                # print('got text_all =', text_all)
                self.sounding_fname = text_all[0].replace('[\'','').replace('\']','')
                # print('got sounding fname = ', self.sounding_fname)

                # self.update_annotation(ind)
                # swath plot has two soundings per fname, stbd then port
                self.sounding_file_lbl.setText('Cursor: ' + self.sounding_fname)
            else:
                # print('cont is NOT true')
                self.sounding_file_lbl.setText('Cursor: ' + self.sounding_fname_default)
    #

    # def hover(self, event):  # adapted from SO example
    #     vis = self.annot.get_visible()
    #     if event.inaxes == self.data_rate_ax1:
    #         print('event.inaxes == self.data_rate_ax1')
    #         cont, ind = self.h_data_rate_smoothed.contains(event)
    #         print('cont, ind =', cont, ind)
    #         if cont:
    #             print('cont is true')
    #             self.update_annot(ind)
    #             # self.annot.set_visible(True)
    #             self.data_canvas.draw_idle()
    #             self.sounding_file_lbl.setText('Cursor: ' + self.sounding_fname)
    #         else:
    #             print('cont is NOT true')
    #             self.sounding_file_lbl.setText('Cursor: (hover over point for file name)')
    #             if vis:
    #                 print('vis is true')
    #                 self.annot.set_visible(False)
    #                 self.data_canvas.draw_idle()

        # # set up annotations on hovering
        # self.data_canvas.mpl_connect('motion_notify_event', self.hover)
        # plt.show()


    def set_left_layout(self):
        # set left layout with file controls
        btnh = 20  # height of file control button
        btnw = 100  # width of file control button
        
        # add file control buttons
        self.add_file_btn = PushButton('Add Files', btnw, btnh, 'add_file_btn', 'Add files')
        self.get_indir_btn = PushButton('Add Directory', btnw, btnh, 'get_indir_btn', 'Add a directory')
        self.include_subdir_chk = CheckBox('Incl. subfolders', False, 'include_subdir_chk',
                                           'Include subdirectories when adding a directory')
        self.show_path_chk = CheckBox('Show file paths', False, 'show_paths_chk', 'Show file paths')
        self.get_outdir_btn = PushButton('Select Output Dir.', btnw, btnh, 'get_outdir_btn',
                                         'Select the output directory (see current directory below)')
        self.rmv_file_btn = PushButton('Remove Selected', btnw, btnh, 'rmv_file_btn', 'Remove selected files')
        self.clr_file_btn = PushButton('Remove All Files', btnw, btnh, 'clr_file_btn', 'Remove all files')
        self.archive_data_btn = PushButton('Archive Data', btnw, btnh, 'archive_data_btn',
                                           'Archive current data from new files to a .pkl file')
        self.load_archive_btn = PushButton('Load Archive', btnw, btnh, 'load_archive_btn',
                                           'Load archive data from a .pkl file')
        self.load_spec_btn = PushButton('Load Spec. Curve', btnw, btnh, 'load_spec_btn',
                                        'IN DEVELOPMENT: Load theoretical performance file')
        self.calc_coverage_btn = PushButton('Calc Coverage', btnw, btnh, 'calc_coverage_btn',
                                            'Calculate coverage from loaded files')
        self.save_plot_btn = PushButton('Save Plot', btnw, btnh, 'save_plot_btn', 'Save current plot')

        self.export_gf_btn = PushButton('Export Gap Filler', btnw, btnh, 'export_gf_btn',
                                             'Export text file of swath coverage trend for Gap Filler import')

        self.export_gf_cbox = ComboBox(['New', 'Archive'], 55, btnh, 'export_gf_cbox',
                                       'Select data source to use for trend export')

        export_gf_lbl = Label('Source:')
        export_gf_source = BoxLayout([export_gf_lbl, self.export_gf_cbox], 'h')

        # set file control button layout and groupbox
        source_btn_layout = BoxLayout([self.add_file_btn, self.get_indir_btn, self.get_outdir_btn, self.rmv_file_btn,
                                       self.clr_file_btn, self.include_subdir_chk, self.show_path_chk], 'v')
        source_btn_gb = GroupBox('Add Data', source_btn_layout, False, False, 'source_btn_gb')
        source_btn_arc_layout = BoxLayout([self.load_archive_btn, self.archive_data_btn], 'v')
        source_btn_arc_gb = GroupBox('Archive Data', source_btn_arc_layout, False, False, 'source_btn_arc_gb')
        spec_btn_gb = GroupBox('Spec. Data', BoxLayout([self.load_spec_btn], 'v'), False, False, 'spec_btn_gb')
        plot_btn_gb = GroupBox('Plot Data', BoxLayout([self.calc_coverage_btn, self.save_plot_btn], 'v'),
                               False, False, 'plot_btn_gb')
        export_btn_gb = GroupBox('Export Trend', BoxLayout([self.export_gf_btn, export_gf_source], 'v'),
                                 False, False, 'export_btn_gb')
        # file_btn_layout = BoxLayout([source_btn_gb, source_btn_arc_gb, spec_btn_gb, plot_btn_gb, export_btn_gb], 'v')
        file_btn_layout = BoxLayout([source_btn_gb, plot_btn_gb, source_btn_arc_gb, spec_btn_gb, export_btn_gb], 'v')

        file_btn_layout.addStretch()
        self.file_list = FileList()  # add file list with extended selection and icon size = (0,0) to avoid indent
        self.file_list.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.MinimumExpanding)
        file_gb = GroupBox('Sources', BoxLayout([self.file_list, file_btn_layout], 'h'), False, False, 'file_gb')
        
        # add activity log widget
        self.log = TextEdit("background-color: lightgray", True, 'log')
        self.log.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.Minimum)
        update_log(self, '*** New swath coverage processing log ***')
        log_gb = GroupBox('Activity Log', BoxLayout([self.log], 'v'), False, False, 'log_gb')

        # add progress bar for total file list and layout
        self.current_file_lbl = Label('Current file:')
        self.sounding_file_lbl = Label('Cursor: ' + self.sounding_fname_default)
        self.current_outdir_lbl = Label('Current output directory:\n' + self.output_dir)
        calc_pb_lbl = Label('Total Progress:')
        self.calc_pb = QtWidgets.QProgressBar()
        self.calc_pb.setGeometry(0, 0, 150, 30)
        self.calc_pb.setMaximum(100)  # this will update with number of files
        self.calc_pb.setValue(0)
        calc_pb_layout = BoxLayout([calc_pb_lbl, self.calc_pb], 'h')
        # self.prog_layout = BoxLayout([self.current_file_lbl, self.current_outdir_lbl], 'v')
        self.prog_layout = BoxLayout([self.current_file_lbl, self.sounding_file_lbl, self.current_outdir_lbl], 'v')
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

        # add figure instance and layout for data rate plot
        self.data_canvas_height = 10
        self.data_canvas_width = 10
        self.data_figure = Figure(figsize=(self.data_canvas_width, self.data_canvas_height))
        self.data_canvas = FigureCanvas(self.data_figure)
        self.data_canvas.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding,
                                       QtWidgets.QSizePolicy.MinimumExpanding)
        self.data_toolbar = NavigationToolbar(self.data_canvas, self)
        self.x_max_data = 0.0
        self.y_max_data = 0.0
        self.data_layout = BoxLayout([self.data_toolbar, self.data_canvas], 'v')

        # add figure instance and layout for data timing
        self.time_canvas_height = 10
        self.time_canvas_width = 10
        self.time_figure = Figure(figsize=(self.time_canvas_width, self.time_canvas_height))
        self.time_canvas = FigureCanvas(self.time_figure)
        self.time_canvas.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding,
                                       QtWidgets.QSizePolicy.MinimumExpanding)
        self.time_toolbar = NavigationToolbar(self.time_canvas, self)
        self.x_max_time = 0.0
        self.y_max_time = 0.0
        self.time_layout = BoxLayout([self.time_toolbar, self.time_canvas], 'v')

        # add figure instance and layout for runtime parameter plotting/tracking
        # self.param_canvas_height = 5
        # self.param_canvas_width = 10
        # self.param_figure = Figure(figsize=(self.param_canvas_width, self.param_canvas_height))
        # self.param_canvas = FigureCanvas(self.param_figure)
        # self.param_canvas.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding,
        #                                 QtWidgets.QSizePolicy.MinimumExpanding)
        # self.param_toolbar = NavigationToolbar(self.param_canvas, self)
        # self.x_max_param = 0.0
        # self.y_max_param = 0.0

        # add parameter log widget to lower half of Parameters tab
        self.param_log = TextEdit("background-color: lightgray", True, 'log')
        self.param_log.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.MinimumExpanding)
        update_param_log(self, '*** New acquisition parameter log ***')
        param_log_gb = GroupBox('Runtime Parameter Log', BoxLayout([self.param_log], 'v'), False, False, 'param_log_gb')
        # self.param_layout = BoxLayout([self.param_toolbar, self.param_canvas, param_log_gb], 'v')
        self.param_layout = BoxLayout([param_log_gb], 'v')

        # set up tabs
        self.plot_tabs = QtWidgets.QTabWidget()
        self.plot_tabs.setStyleSheet("background-color: none")
        self.plot_tabs.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Maximum)

        # set up tab 1: swath coverage
        self.plot_tab1 = QtWidgets.QWidget()
        self.plot_tab1.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Maximum)
        self.plot_tab1.layout = self.swath_layout
        self.plot_tab1.setLayout(self.plot_tab1.layout)

        # set up tab 2: data rate
        self.plot_tab2 = QtWidgets.QWidget()
        self.plot_tab2.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Maximum)
        self.plot_tab2.layout = self.data_layout
        self.plot_tab2.setLayout(self.plot_tab2.layout)

        # set up tab 3: timing
        self.plot_tab3 = QtWidgets.QWidget()
        self.plot_tab3.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Maximum)
        self.plot_tab3.layout = self.time_layout
        self.plot_tab3.setLayout(self.plot_tab3.layout)

        # set up tab 4: runtime parameters
        self.plot_tab4 = QtWidgets.QWidget()
        self.plot_tab4.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Maximum)
        self.plot_tab4.layout = self.param_layout
        self.plot_tab4.setLayout(self.plot_tab4.layout)

        # add tabs to tab layout
        self.plot_tabs.addTab(self.plot_tab1, 'Coverage')
        self.plot_tabs.addTab(self.plot_tab2, 'Data Rate')
        self.plot_tabs.addTab(self.plot_tab3, 'Timing')
        self.plot_tabs.addTab(self.plot_tab4, 'Parameters')

        self.center_layout = BoxLayout([self.plot_tabs], 'v')
        # self.center_layout.addStretch()

    
    def set_right_layout(self):
        # set right layout with swath plot controls
        # add text boxes for system, ship, cruise
        model_tb_lbl = Label('Model:', width=100, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.model_cbox = ComboBox(self.model_list, 100, 20, 'model_cbox', 'Select the model')
        self.show_model_chk = CheckBox('', True, 'show_model_chk', 'Show model in plot title')
        model_info_layout_left = BoxLayout([model_tb_lbl, self.model_cbox], 'h',
                                           alignment=(Qt.AlignRight | Qt.AlignVCenter))
        model_info_layout = BoxLayout([model_info_layout_left, self.show_model_chk], 'h',
                                      alignment=(Qt.AlignRight | Qt.AlignVCenter))

        ship_tb_lbl = Label('Ship Name:', width=100, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.ship_tb = LineEdit('R/V Unsinkable II', 100, 20, 'ship_tb', 'Enter the ship name')
        self.show_ship_chk = CheckBox('', True, 'show_ship_chk', 'Show ship name in plot title')
        ship_info_layout_left = BoxLayout([ship_tb_lbl, self.ship_tb], 'h',
                                          alignment=(Qt.AlignRight | Qt.AlignVCenter))
        ship_info_layout = BoxLayout([ship_info_layout_left, self.show_ship_chk], 'h',
                                     alignment=(Qt.AlignRight | Qt.AlignVCenter))

        cruise_tb_lbl = Label('Cruise Name:', width=100, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.cruise_tb = LineEdit('A 3-hour tour', 100, 20, 'cruise_tb', 'Enter the cruise name')
        self.show_cruise_chk = CheckBox('', True, 'show_cruise_chk', 'Show cruise in plot title')
        cruise_info_layout_left = BoxLayout([cruise_tb_lbl, self.cruise_tb], 'h',
                                            alignment=(Qt.AlignRight | Qt.AlignVCenter))
        cruise_info_layout = BoxLayout([cruise_info_layout_left, self.show_cruise_chk], 'h',
                                       alignment=(Qt.AlignRight | Qt.AlignVCenter))

        self.custom_info_gb = GroupBox('Use custom system information',
                                       BoxLayout([model_info_layout, ship_info_layout, cruise_info_layout], 'v'),
                                       True, False, 'custom_info_gb')
        self.custom_info_gb.setToolTip('Add system/cruise info; system info parsed from the file is used if available')




        # add text boxes for system, ship, cruise
        # model_tb_lbl = Label('Model:', alignment=(Qt.AlignRight | Qt.AlignVCenter))
        # self.model_cbox = ComboBox(self.model_list, 100, 20, 'mofdel_cbox', 'Select the model')
        # model_info_layout = BoxLayout([model_tb_lbl, self.model_cbox], 'h')

        # ship_tb_lbl = Label('Ship Name:', alignment=(Qt.AlignRight | Qt.AlignVCenter))
        # # self.ship_tb = LineEdit('R/V Unsinkable II', 100, 20, 'ship_tb', 'Enter the ship name')
        # self.ship_tb = LineEdit(self.ship_name, 100, 20, 'ship_tb', 'Enter the ship name')
        #
        # ship_info_layout = BoxLayout([ship_tb_lbl, self.ship_tb], 'h')

        # cruise_tb_lbl = Label('Cruise Name:', alignment=(Qt.AlignRight | Qt.AlignVCenter))
        # self.cruise_tb = LineEdit('A 3-hour tour', 100, 20, 'cruise_tb', 'Enter the cruise name')
        # cruise_info_layout = BoxLayout([cruise_tb_lbl, self.cruise_tb], 'h')

        # self.custom_info_gb = GroupBox('Use custom system information',
        #                                BoxLayout([model_info_layout, ship_info_layout, cruise_info_layout], 'v'),
        #                                True, False, 'custom_info_gb')
        #
        # self.custom_info_gb.setToolTip('Add system/cruise info; system info parsed from the file is used if available')

        # add depth reference options and groupbox
        self.ref_cbox = ComboBox(self.depth_ref_list, 100, 20, 'ref_cbox',
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

        depth_ref_lbl = Label('Reference data to:', 100, 20, 'depth_ref_lbl', (Qt.AlignLeft | Qt.AlignVCenter))
        depth_ref_layout = BoxLayout([depth_ref_lbl, self.ref_cbox], 'h')
        self.depth_ref_gb = GroupBox('Depth reference', depth_ref_layout, False, False, 'depth_ref_gb')

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
                                      'Select the loaded dataset to plot last (on top)\n\n'
                                      'NOTE: the colorbar or legend, if shown, will correspond to the "top" dataset; '
                                      'the colorbar or legend may not clearly represent all data shown if '
                                      'a) the option to apply color modes to data plots is checked, and '
                                      'b) the new and archive color modes do not match.')
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
        self.pt_size_cbox = ComboBox([str(pt) for pt in range(1,11)], 45, 20, 'pt_size_cbox', 'Select point size')
        self.pt_size_cbox.setCurrentIndex(4)

        # set point size layout
        pt_size_lbl = Label('Point size:', width=50, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        pt_size_layout = BoxLayout([pt_size_lbl, self.pt_size_cbox], 'h')
        pt_size_layout.addStretch()

        # add point transparency/opacity slider (can help to visualize density of data)
        pt_alpha_lbl = Label('Opacity (%):', width=50, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.pt_alpha_cbox = ComboBox([str(10 * pt) for pt in range(1,11)], 45, 20, 'pt_alpha_cbox', 'Select opacity')
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
        max_dr_lbl = Label('Data rate:', width=50, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        max_pi_lbl = Label('Ping int.:', width=50, alignment=(Qt.AlignRight | Qt.AlignVCenter))

        self.max_z_tb = LineEdit('', 40, 20, 'max_z_tb', 'Set the maximum depth of the plot')
        self.max_z_tb.setValidator(QDoubleValidator(0, 20000, 2))
        self.max_x_tb = LineEdit('', 40, 20, 'max_x_tb', 'Set the maximum width of the plot')
        self.max_x_tb.setValidator(QDoubleValidator(0, 20000, 2))
        self.max_dr_tb = LineEdit('', 40, 20, 'max_dr_tb', 'Set the maximum data rate of the plot')
        self.max_dr_tb.setValidator(QDoubleValidator(0, np.inf, 2))
        self.max_pi_tb = LineEdit('', 40, 20, 'max_pi_tb', 'Set the maximum ping interval of the plot')
        self.max_pi_tb.setValidator(QDoubleValidator(0, np.inf, 2))
        # plot_lim_layout = BoxLayout([max_z_lbl, self.max_z_tb, max_x_lbl, self.max_x_tb], 'h')
        plot_lim_layout_upper = BoxLayout([max_z_lbl, self.max_z_tb, max_x_lbl, self.max_x_tb], 'h')
        plot_lim_layout_lower = BoxLayout([max_dr_lbl, self.max_dr_tb, max_pi_lbl, self.max_pi_tb], 'h')
        plot_lim_layout = BoxLayout([plot_lim_layout_upper, plot_lim_layout_lower], 'v')
        self.plot_lim_gb = GroupBox('Use custom plot limits', plot_lim_layout, True, False, 'plot_lim_gb')
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
        self.max_angle_tb.setValidator(QDoubleValidator(float(self.min_angle_tb.text()), np.inf, 2))

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

        # add custom ping interval limits
        min_ping_int_lbl = Label('Min:', width=50, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.min_ping_int_tb = LineEdit('0.25', 40, 20, 'min_ping_int_tb',
                                        'Set the minimum ping interval (e.g., 0.25 sec)')
        max_ping_int_lbl = Label('Max:', width=50, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.max_ping_int_tb = LineEdit('20', 40, 20, 'max_ping_int_tb',
                                  'Set the maximum ping interval (e.g., 15 sec)')
        self.min_ping_int_tb.setValidator(QDoubleValidator(-1 * np.inf, float(self.max_ping_int_tb.text()), 2))
        self.max_ping_int_tb.setValidator(QDoubleValidator(float(self.min_ping_int_tb.text()), np.inf, 2))
        ping_int_layout = BoxLayout([min_ping_int_lbl, self.min_ping_int_tb, max_ping_int_lbl, self.max_ping_int_tb], 'h')
        self.ping_int_gb = GroupBox('Ping Interval (sec)', ping_int_layout, True, False, 'ping_int_gb')
        self.ping_int_gb.setToolTip('Hide data by detected ping interval (sec).\n\n'
                                    'Filtering is applied to the time interval between swaths and affects only the '
                                    'ping interval plot.  The minimum filter value should be a small non-zero value'
                                    'to exclude the very short intervals between swaths in dual-swath operation and '
                                    'more clearly show the time intervals between the major ping cycles.')

        # add custom threshold/buffer for comparing RX beam angles to runtime parameters
        rtp_angle_buffer_lbl = Label('Angle buffer (+/-10 deg):', width=40, alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.rtp_angle_buffer_tb = LineEdit(str(self.rtp_angle_buffer_default), 40, 20, 'rtp_angle_buffer_tb', '')
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
        rtp_cov_buffer_lbl = Label('Coverage buffer (-inf-0 m):', alignment=(Qt.AlignRight | Qt.AlignVCenter))
        self.rtp_cov_buffer_tb = LineEdit('-100', 40, 20, 'rtp_cov_buffer_tb', '')
        self.rtp_cov_buffer_tb.setValidator(QDoubleValidator(-1*np.inf, 0, 2))
        rtp_cov_layout = BoxLayout([rtp_cov_buffer_lbl, self.rtp_cov_buffer_tb], 'h')
        self.rtp_cov_gb = GroupBox('Hide coverage near runtime limits', rtp_cov_layout, True, False, 'rtp_cov_gb')
        self.rtp_cov_gb.setToolTip('Hide soundings that may have been limited by user-defined acrosstrack '
                                   'coverage constraints during data collection.\n\n'
                                   'Buffer must be negative.  Decrease the buffer (down to -inf m) for more aggressive'
                                   'masking of soundings approaching the runtime coverage.\n\n'
                                   'Soundings outside the runtime coverage limit (i.e., within a buffer > 0 m) should '
                                   'not available, as they are rejected during acquisition.\n\n'
                                   'Fine tuning may help to visualize (and remove) outer soundings that were '
                                   'clearly limited by runtime parameters during acquisition.')

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
        self.show_ref_fil_chk = CheckBox('Show reference/filter text', True, 'show_ref_fil_chk',
                                         'Show text box with sounding reference and filter information')
        self.grid_lines_toggle_chk = CheckBox('Show grid lines', True, 'show_grid_chk', 'Show grid lines')
        self.colorbar_chk = CheckBox('Show colorbar/legend', True, 'show_colorbar_chk',
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

        self.standard_fig_size_chk = CheckBox('Save standard figure size', True, 'standard_fig_size_chk',
                                              'Save figures in a standard size '
                                              '(H: ' + str(self.std_fig_height_inches) + '", '
                                              'W: ' + str(self.std_fig_width_inches) + '", 600 PPI).  Uncheck to '
                                              'allow the saved figure size to scale with the current plotter window.')

        self.show_hist_chk = CheckBox('Show histogram of soundings', False, 'show_hist_chk',
                                      'Show the distribution of soundings on the swath coverage plot.')
        self.match_data_cmodes_chk = CheckBox('Apply color modes to data plots', True, 'match_data_cmodes_chk',
                                              'Apply the chosen color modes for new / archive data to the data rate '
                                              'and ping interval plots.  Uncheck to use solid colors for data plots; '
                                              'the most recent solid colors will be used for new / archive data plots')

        self.show_coverage_trend_chk = CheckBox('Show coverage trend points', False, 'show_cov_trend_chk',
                                                'Show coverage trend points that will be used for export (e.g., to Gap '
                                                'Filler text file), if available')

        toggle_chk_layout = BoxLayout([self.show_ref_fil_chk, self.grid_lines_toggle_chk, self.colorbar_chk,
                                       self.spec_chk, self.standard_fig_size_chk, self.show_hist_chk,
                                       self.match_data_cmodes_chk, self.show_coverage_trend_chk], 'v')

        toggle_chk_gb = GroupBox('Other options', toggle_chk_layout, False, False, 'other_options_gb')


        # add runtime parameter search options
        param_cond_lbl = Label('Show when', 60, 20, 'param_cond_lbl', (Qt.AlignLeft | Qt.AlignVCenter))
        self.param_cond_cbox = ComboBox(['ANY parameter matches', 'ALL parameters match'], 140, 20, 'param_cond_cbox',
                                        'Search for parameter changes that match ANY or ALL of the selections.\n\n'
                                        '"ANY parameter matches" will return every time a parameter change satisfies'
                                        'any of the checked search options.\n\n'
                                        '"ALL parameters match" will return only times where every checked search '
                                        'option is satisfied')

        param_cond_layout = BoxLayout([param_cond_lbl, self.param_cond_cbox], 'h', False, (Qt.AlignLeft | Qt.AlignVCenter))
        # param5_tb_layout = BoxLayout([self.p5_cbox, self.p5_tb], 'h', False, (Qt.AlignRight | Qt.AlignVCenter))

        self.p1_chk = CheckBox('Depth Mode:', False, 'ping_mode', 'Search by Depth Mode', 100, 20)
        self.p1_cbox = ComboBox(['All', 'Very Shallow', 'Shallow', 'Medium', 'Deep', 'Deeper', 'Very Deep',
                                     'Extra Deep', 'Extreme Deep'], 100, 20, 'param1_cbox',
                                    'Depth Modes (not all modes apply for all models)')

        self.p2_chk = CheckBox('Swath Mode:', False, 'swath_mode', 'Search by Swath Mode', 100, 20)
        self.p2_cbox = ComboBox(['All', 'Single Swath', 'Dual Swath'], 100, 20, 'param2_cbox',
                                    'Swath Modes (Dual Swath includes "Dynamic" and "Fixed" spacing)')

        self.p3_chk = CheckBox('Pulse Form:', False, 'pulse_form', 'Search by Pulse Form', 100, 20)
        self.p3_cbox = ComboBox(['All', 'CW', 'FM', 'Mixed'], 100, 20, 'param3_cbox', 'Pulse Form')

        self.p4_chk = CheckBox('Swath Angle (deg):', False, 'swath_angle',
                                   'Search by Swath Angle Limits (Port/Stbd)', 140, 20)
        self.p4_cbox = ComboBox(['All', '<=', '>=', '=='], 40, 20, 'param4_cbox',
                                    'Select swath angle limit search criterion')
        self.p4_tb = LineEdit('', 38, 20, 'port_angle_tb', 'Search by port swath angle limit')
        param4_tb_layout = BoxLayout([self.p4_cbox, self.p4_tb], 'h', False, (Qt.AlignRight | Qt.AlignVCenter))

        self.p5_chk = CheckBox('Swath Cover. (m):', False, 'swath_cov', 'Search by Swath Coverage Limits', 140, 20)
        self.p5_cbox = ComboBox(['All', '<=', '>=', '=='], 40, 20, 'param5_cbox',
                                    'Select swath coverage limit search criterion')
        self.p5_tb = LineEdit('', 38, 20, 'port_cov_tb', 'Search by port swath coverage limit')
        param5_tb_layout = BoxLayout([self.p5_cbox, self.p5_tb], 'h', False, (Qt.AlignRight | Qt.AlignVCenter))

        # making separate vertical layouts of checkbox widgets and combobox widgets to set alignments separately
        self.param_chk_layout = BoxLayout([self.p1_chk, self.p2_chk, self.p3_chk, self.p4_chk,
                                           self.p5_chk], 'v', False)
        param_value_layout = BoxLayout([self.p1_cbox, self.p2_cbox, self.p3_cbox, param4_tb_layout,
                                        param5_tb_layout], 'v', False, (Qt.AlignRight | Qt.AlignVCenter))
        param_search_hlayout = BoxLayout([self.param_chk_layout, param_value_layout], 'h')

        param_search_vlayout = BoxLayout([param_cond_layout, param_search_hlayout], 'v', False)

        self.param_search_gb = GroupBox('Search Acquisition Parameters', param_search_vlayout, True, False, 'param_search_gb')

        # make zipped list of

        # add search / update button
        self.param_search_btn = PushButton('Update Search', 100, 20, 'param_search_btn',
                                           'Search acquisition parameters for settings specified above.\n\n'
                                           'Results reflect the first ping time(s) when settings match the selected '
                                           'search options (i.e., the first ping and after any changes that match).\n\n'
                                           'ALL changes will be shown by default if no settings are specified.\n\n'
                                           'If individual settings are selected, the results can be further filtered by'
                                           'matching ANY or ALL selections:\n\n'
                                           '  a) ANY selected parameter matches (e.g., any time Depth Mode is changed '
                                           '  to Deep *and* any time Swath Mode is changed to Dual Swath), or\n\n'
                                           '  b) ALL selected parameters match (e.g., only times when a change has'
                                           '  been made so the Depth Mode is Deep *and* Swath Mode is Dual Swath\n\n'
                                           'Results will be printed to the acquisition parameter log. ')

        self.save_param_log_btn = PushButton('Save Search Log', 100, 20, 'param_log_save_btn',
                                             'Save the current Acquisition Parameter Log to a text file')

        # with open('log.txt', 'w') as yourFile:
        #     yourFile.write(str(yourQTextEdit.toPlainText()))

        # Testing alternative layouts for text boxes
        # self.param6_chk = CheckBox('Swath Angle (deg):', False, 'param6_chk',
        #                            'Search by Swath Angle Limits (Port/Stbd)', 120, 20)
        # self.param6_tb1 = LineEdit('', 20, 20, 'port_angle_tb', 'Search by port swath angle limit')
        # self.param6_tb2 = LineEdit('', 20, 20, 'stbd_angle_tb', 'Search by stbd swath angle limit')
        # param6_tb_layout = BoxLayout([self.param6_tb1, self.param6_tb2], 'h', False, (Qt.AlignRight | Qt.AlignVCenter))
        # param6_chk_layout = BoxLayout([self.param6_chk], 'h', False)
        # param6_layout = BoxLayout([param6_chk_layout, param6_tb_layout], 'h', False)
        #
        # param_test_layout = BoxLayout([param_search_layout, param6_layout], 'v')
        # self.param_search_gb = GroupBox('Search Acquisition Parameters', param_test_layout,
        #                                 False, False, 'param_search_gb')
        # self.param4_tb2.setAlignment(Qt.AlignRight)

        # alignment = (Qt.AlignLeft | Qt.AlignVCenter)
        # self.param_search_gb = GroupBox('Search Acquisition Parameters', param1_layout, False, False, 'param_search_gb')


        # set up tabs
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setStyleSheet("background-color: none")

        # set up tab 1: plot options
        self.tab1 = QtWidgets.QWidget()
        self.tab1.layout = BoxLayout([self.custom_info_gb, self.depth_ref_gb, cmode_layout, pt_param_gb, self.plot_lim_gb,
                                      self.angle_lines_gb, self.n_wd_lines_gb, toggle_chk_gb], 'v')
        self.tab1.layout.addStretch()
        self.tab1.setLayout(self.tab1.layout)

        # set up tab 2: filtering options
        self.tab2 = QtWidgets.QWidget()
        self.tab2.layout = BoxLayout([self.angle_gb, self.depth_gb, self.bs_gb, self.ping_int_gb, self.rtp_angle_gb,
                                      self.rtp_cov_gb, self.pt_count_gb], 'v')
        self.tab2.layout.addStretch()
        self.tab2.setLayout(self.tab2.layout)

        # set up tab 3: parameter search options
        self.tab3 = QtWidgets.QWidget()
        self.tab3.layout = BoxLayout([self.param_search_gb, self.param_search_btn, self.save_param_log_btn], 'v')
        self.tab3.layout.addStretch()
        self.tab3.setLayout(self.tab3.layout)

        # add tabs to tab layout
        self.tabs.addTab(self.tab1, 'Plot')
        self.tabs.addTab(self.tab2, 'Filter')
        self.tabs.addTab(self.tab3, 'Search')

        self.tabw = 240  # set fixed tab width
        self.tabs.setFixedWidth(self.tabw)

        self.right_layout = BoxLayout([self.tabs], 'v')
        self.right_layout.addStretch()

    def set_main_layout(self):
        # set the main layout with file controls on left and swath figure on right
        # self.mainWidget.setLayout(BoxLayout([self.left_layout, self.swath_layout, self.right_layout], 'h'))
        self.mainWidget.setLayout(BoxLayout([self.left_layout, self.center_layout, self.right_layout], 'h'))


    # set up annotations on hovering
    # self.data_canvas.mpl_connect('motion_notify_event', self.hover)
    # plt.show()



class NewPopup(QtWidgets.QWidget): # new class for additional plots
    def __init__(self):
        QtWidgets.QWidget.__init__(self)


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)

    main = MainWindow()
    main.show()

    sys.exit(app.exec_())
