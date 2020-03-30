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
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import colors
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
import multibeam_tools.libs.readEM
import multibeam_tools.libs.parseEMswathwidth

__version__ = "0.1.2"

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

        # initialize other necessities
        self.filenames = ['']
        self.input_dir = ''
        self.output_dir = os.getcwd()

        # set up three layouts of main window
        self.set_left_layout()
        self.set_center_layout()
        self.set_right_layout()
        self.set_main_layout()
        self.init_swath_ax()

        # set up file control actions
        self.add_file_btn.clicked.connect(lambda: self.add_files('Kongsberg .all(*.all)'))
        self.get_indir_btn.clicked.connect(self.get_input_dir)
        self.get_outdir_btn.clicked.connect(self.get_output_dir)
        self.rmv_file_btn.clicked.connect(self.remove_files)
        self.clr_file_btn.clicked.connect(self.clear_files)
        self.calc_coverage_btn.clicked.connect(self.calc_coverage)        
        self.save_plot_btn.clicked.connect(self.save_plot)
        self.archive_data_btn.clicked.connect(self.archive_data)
        self.load_archive_btn.clicked.connect(self.load_archive)
    
        # set up swath plot control actions
        self.pt_size_slider.valueChanged.connect(self.refresh_plot)
        self.color_cbox.activated.connect(self.refresh_plot)
        self.scbtn.clicked.connect(lambda: self.update_solid_color('color'))
        self.color_cbox_arc.activated.connect(self.refresh_plot)
        self.scbtn_arc.clicked.connect(lambda: self.update_solid_color('color_arc'))
        self.archive_toggle_chk.stateChanged.connect(self.refresh_plot)
        self.WD_lines_toggle_chk.stateChanged.connect(self.refresh_plot)
        self.nominal_angle_lines_toggle_chk.stateChanged.connect(self.refresh_plot)
        self.grid_lines_toggle_chk.stateChanged.connect(self.refresh_plot)
        self.colorbar_chk.stateChanged.connect(self.refresh_plot)
        self.custom_info_chk.stateChanged.connect(self.refresh_plot)
        self.model_cbox.activated.connect(self.refresh_plot)
        self.ship_tb.returnPressed.connect(self.refresh_plot)
        self.cruise_tb.returnPressed.connect(self.refresh_plot)

        self.custom_max_chk.stateChanged.connect(self.refresh_plot)
        self.custom_angle_chk.stateChanged.connect(self.refresh_plot)
        self.custom_depth_chk.stateChanged.connect(self.refresh_plot)
        self.dec_fac_chk.stateChanged.connect(self.refresh_plot)
        self.max_x_tb.returnPressed.connect(self.refresh_plot)
        self.max_z_tb.returnPressed.connect(self.refresh_plot)
        self.max_angle_tb.returnPressed.connect(self.refresh_plot)
        self.min_angle_tb.returnPressed.connect(self.refresh_plot)
        self.max_depth_tb.returnPressed.connect(self.refresh_plot)
        self.min_depth_tb.returnPressed.connect(self.refresh_plot)
        self.max_depth_arc_tb.returnPressed.connect(self.refresh_plot)
        self.min_depth_arc_tb.returnPressed.connect(self.refresh_plot)
        self.dec_fac_tb.returnPressed.connect(self.refresh_plot)

    def set_left_layout(self):
        # set left layout with file controls
        file_button_height = 20 # height of file control button
        file_button_width = 100 # width of file control button
        
        # add file control buttons and file list
        self.add_file_btn = QtWidgets.QPushButton('Add Files')
        self.add_file_btn.setToolTip('Add files for coverage plotting')
        self.get_indir_btn = QtWidgets.QPushButton('Add Directory')
        self.get_indir_btn.setToolTip('Add a directory')

        self.get_outdir_btn = QtWidgets.QPushButton('Select Output Dir.')
        self.get_outdir_btn.setToolTip('Set the output directory (see current output directory below)')
        self.rmv_file_btn = QtWidgets.QPushButton('Remove Selected')
        self.rmv_file_btn.setToolTip('Remove selected files')
        self.clr_file_btn = QtWidgets.QPushButton('Remove All Files')
        self.clr_file_btn.setToolTip('Remove all files')
        self.calc_coverage_btn = QtWidgets.QPushButton('Calc Coverage')
        self.calc_coverage_btn.setToolTip('Calculate coverage from loaded files')
        self.save_plot_btn = QtWidgets.QPushButton('Save Plot')
        self.save_plot_btn.setToolTip('Save current plot')
        self.archive_data_btn = QtWidgets.QPushButton('Archive Data')
        self.archive_data_btn.setToolTip('Archive current data from new files to a .pkl file')
        self.load_archive_btn = QtWidgets.QPushButton('Load Archive')
        self.load_archive_btn.setToolTip('Load archive data from a .pkl file')

        
        # format file control buttons
        self.add_file_btn.setFixedSize(file_button_width,file_button_height)
        self.get_indir_btn.setFixedSize(file_button_width, file_button_height)
        self.get_outdir_btn.setFixedSize(file_button_width, file_button_height)
        self.rmv_file_btn.setFixedSize(file_button_width,file_button_height)
        self.clr_file_btn.setFixedSize(file_button_width,file_button_height)
        self.calc_coverage_btn.setFixedSize(file_button_width, file_button_height)
        self.save_plot_btn.setFixedSize(file_button_width, file_button_height)
        self.archive_data_btn.setFixedSize(file_button_width, file_button_height)
        self.load_archive_btn.setFixedSize(file_button_width, file_button_height)
        
        # set the file control button layout
        source_btn_layout = QtWidgets.QVBoxLayout()
        source_btn_layout.addWidget(self.add_file_btn)
        source_btn_layout.addWidget(self.get_indir_btn)
        source_btn_layout.addWidget(self.get_outdir_btn)
        source_btn_layout.addWidget(self.rmv_file_btn)
        source_btn_layout.addWidget(self.clr_file_btn)
        source_btn_gb = QtWidgets.QGroupBox('Add Data')
        source_btn_gb.setLayout(source_btn_layout)

        # set the archive control button layout
        source_btn_arc_layout = QtWidgets.QVBoxLayout()
        source_btn_arc_layout.addWidget(self.load_archive_btn)
        source_btn_arc_layout.addWidget(self.archive_data_btn)
        source_btn_arc_gb = QtWidgets.QGroupBox('Archive Data')
        source_btn_arc_gb.setLayout(source_btn_arc_layout)

        # set the plot button layout
        plot_btn_layout = QtWidgets.QVBoxLayout()
        plot_btn_layout.addWidget(self.calc_coverage_btn)
        plot_btn_layout.addWidget(self.save_plot_btn)
        plot_btn_gb = QtWidgets.QGroupBox('Plot Data')
        plot_btn_gb.setLayout(plot_btn_layout)

        # new layout
        file_btn_layout = QtWidgets.QVBoxLayout()
        file_btn_layout.addWidget(source_btn_gb)
        file_btn_layout.addWidget(source_btn_arc_gb)
        file_btn_layout.addWidget(plot_btn_gb)
        file_btn_layout.addStretch()

        # old layout
        # file_btn_layout = QtWidgets.QVBoxLayout()
        # file_btn_layout.addWidget(self.add_file_btn)
        # file_btn_layout.addWidget(self.get_indir_btn)
        # file_btn_layout.addWidget(self.get_outdir_btn)
        # file_btn_layout.addWidget(self.rmv_file_btn)
        # file_btn_layout.addWidget(self.clr_file_btn)
        # file_btn_layout.addWidget(self.calc_coverage_btn)
        # file_btn_layout.addWidget(self.archive_data_btn)
        # file_btn_layout.addWidget(self.load_archive_btn)
        # file_btn_layout.addWidget(self.save_plot_btn)
        # file_btn_layout.addStretch()
        # file_btn_layout.setSizeConstraint()

        # add table showing selected files
        self.file_list = QtWidgets.QListWidget()
        # self.file_list.setSizePolicy(QtWidgets.QSizePolicy.Minimum,
        #                              QtWidgets.QSizePolicy.Minimum)
        # self.file_list.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding,
        #                              QtWidgets.QSizePolicy.MinimumExpanding)
        self.file_list.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding,
                                     QtWidgets.QSizePolicy.Minimum)

        # set layout of file list and controls
        self.file_layout = QtWidgets.QHBoxLayout()
        self.file_layout.addWidget(self.file_list)
        self.file_layout.addLayout(file_btn_layout)

        # set file list group box
        self.file_gb = QtWidgets.QGroupBox('Sources')
        self.file_gb.setLayout(self.file_layout)
        
        # add activity log widget
        self.log = QtWidgets.QTextEdit()
        self.log.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding,
                               QtWidgets.QSizePolicy.Minimum)
        self.log.setStyleSheet("background-color: lightgray")
        self.log.setReadOnly(True)
        self.update_log('*** New swath coverage processing log ***')
        
        # add progress bar for total file list
        self.current_file_lbl = QtWidgets.QLabel('Current File:')
        # self.current_fnum_lbl = QtWidgets.QLabel('Current file count:')
        self.current_outdir_lbl = QtWidgets.QLabel('Current output directory:\n' + self.output_dir)
        self.calc_pb_lbl = QtWidgets.QLabel('Total Progress:')
        self.calc_pb = QtWidgets.QProgressBar()
        self.calc_pb.setGeometry(0,0,150,30)
        self.calc_pb.setMaximum(100) # this will update with number of files
        self.calc_pb.setValue(0)
        
        # set progress bar layout
        self.calc_pb_layout = QtWidgets.QHBoxLayout()
        self.calc_pb_layout.addWidget(self.calc_pb_lbl)
        self.calc_pb_layout.addWidget(self.calc_pb)
        
        self.prog_layout = QtWidgets.QVBoxLayout()
        # add progress bar for total file list
        # self.prog_layout.addWidget(self.current_fnum_lbl)
        self.prog_layout.addWidget(self.current_file_lbl)
        self.prog_layout.addWidget(self.current_outdir_lbl)
        self.prog_layout.addLayout(self.calc_pb_layout)
 
        # set the log layout
        self.log_layout = QtWidgets.QVBoxLayout()
        self.log_layout.addWidget(self.log)
        self.log_layout.addLayout(self.prog_layout)
        
        # set the log group box widget with log layout
        self.log_gb = QtWidgets.QGroupBox('Activity Log')
        self.log_gb.setLayout(self.log_layout)
        self.log_gb.setFixedWidth(450)

        # set the left panel layout with file controls on top and log on bottom
        self.left_layout = QtWidgets.QVBoxLayout()
        self.left_layout.addWidget(self.file_gb)  # add file list group box
        self.left_layout.addWidget(self.log_gb)  # add log group box

    def set_center_layout(self):
        self.swath_canvas_height = 10
        self.swath_canvas_width = 10
        # set center layout with swath coverage plot
        # add figure instance to plot swath coverage versus depth
        self.swath_figure = Figure(figsize=(self.swath_canvas_width,self.swath_canvas_height))
        self.swath_canvas = FigureCanvas(self.swath_figure)  # canvas widget that displays the figure
        self.swath_canvas.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding,
                                        QtWidgets.QSizePolicy.MinimumExpanding)
        self.swath_toolbar = NavigationToolbar(self.swath_canvas, self)  # swath plot toolbar

        # initialize max x, z limits
        self.x_max = 0.0
        self.z_max = 0.0

        # set the swath layout
        self.swath_layout = QtWidgets.QVBoxLayout()
        self.swath_layout.addWidget(self.swath_toolbar)
        self.swath_layout.addWidget(self.swath_canvas)
    
    def set_right_layout(self):
        # set right layout with swath plot controls
        # add point size slider
        self.pt_size_slider = QtWidgets.QSlider(Qt.Horizontal)  # slider w/ small # of steps; scale pt_size during plot
        self.pt_size_slider.setMinimum(1)
        self.pt_size_slider.setMaximum(11)
        self.pt_size_slider.setValue(6)
        self.pt_size_slider.setTickInterval(1)
        self.pt_size_slider.setTickPosition(QtWidgets.QSlider.TicksBelow)  # set tick marks on bottom of slider
        self.pt_size_slider.setFixedHeight(30)
        self.pt_size_slider.setFixedWidth(185)
        
        # set the point size slider layout
        pt_size_layout = QtWidgets.QVBoxLayout()
        pt_size_layout.addWidget(self.pt_size_slider)
        
        # set point size group box
        pt_size_gb = QtWidgets.QGroupBox('Point Size:')
        pt_size_gb.setLayout(pt_size_layout)
                
        # add point color options for new data
        self.color_lbl = QtWidgets.QLabel('New Data')
        self.color_cbox = QtWidgets.QComboBox()  # combo box with color modes
        self.color_cbox.setFixedSize(80,20)
        self.color_cbox.addItems(['Depth', 'Backscatter', 'Ping Mode', 'Pulse Form', 'Swath Mode', 'Solid Color']) # color modes
        self.scbtn = QtWidgets.QPushButton('Select Color') # button to select solid color options
        self.scbtn.setEnabled(False) # disable color selection until 'Solid Color' is chosen from color_cbox
        self.scbtn.setFixedSize(80,20)

        # set new data color control layout
        cbox_layout_new = QtWidgets.QVBoxLayout()
        cbox_layout_new.addWidget(self.color_lbl)
        cbox_layout_new.addWidget(self.color_cbox)
        cbox_layout_new.addWidget(self.scbtn)

        # add point color options for archive data
        self.color_lbl_arc = QtWidgets.QLabel('Archive Data')
        self.color_cbox_arc = QtWidgets.QComboBox()  # combo box with color modes
        self.color_cbox_arc.setFixedSize(80,20)
        self.color_cbox_arc.addItems(['Depth', 'Backscatter', 'Ping Mode', 'Pulse Form', 'Swath Mode', 'Solid Color']) # color modes
        self.scbtn_arc = QtWidgets.QPushButton('Select Color') # button to select solid color options
        self.scbtn_arc.setEnabled(False) # disable color selection until 'Solid Color' is chosen from color_cbox
        self.scbtn_arc.setFixedSize(80,20)

        # set archive data color control layout
        cbox_layout_arc = QtWidgets.QVBoxLayout()
        cbox_layout_arc.addWidget(self.color_lbl_arc)
        cbox_layout_arc.addWidget(self.color_cbox_arc)
        cbox_layout_arc.addWidget(self.scbtn_arc)

        # set total color control layout
        cbox_layout = QtWidgets.QHBoxLayout()
        cbox_layout.addLayout(cbox_layout_new)
        cbox_layout.addLayout(cbox_layout_arc)

        pt_color_layout = QtWidgets.QVBoxLayout()
        pt_color_layout.addLayout(cbox_layout)
        
        # add color control group box
        pt_color_gb = QtWidgets.QGroupBox('Point Color:')
        pt_color_gb.setLayout(pt_color_layout)
        
        # add check boxes to show archive data, grid lines, WD-multiple lines
        self.archive_toggle_chk = QtWidgets.QCheckBox('Show archive data')
        self.grid_lines_toggle_chk = QtWidgets.QCheckBox('Show grid lines')
        self.grid_lines_toggle_chk.setChecked(True)        
        self.WD_lines_toggle_chk = QtWidgets.QCheckBox('Show N*WD lines')
        self.nominal_angle_lines_toggle_chk = QtWidgets.QCheckBox('Show nominal angle lines')
        self.colorbar_chk = QtWidgets.QCheckBox('Show colorbar/legend')
        
        toggle_chk_layout = QtWidgets.QVBoxLayout()
        toggle_chk_layout.addWidget(self.archive_toggle_chk)
        toggle_chk_layout.addWidget(self.grid_lines_toggle_chk)
        toggle_chk_layout.addWidget(self.WD_lines_toggle_chk)
        toggle_chk_layout.addWidget(self.nominal_angle_lines_toggle_chk)
        toggle_chk_layout.addWidget(self.colorbar_chk)
        
        # add checkbox groupbox
        toggle_gb = QtWidgets.QGroupBox('Plot Options')
        toggle_gb.setLayout(toggle_chk_layout)
        
        # add text boxes for system, ship, cruise
        self.model_tb_lbl = QtWidgets.QLabel('Model:')
        self.model_tb_lbl.resize(100,20)
        self.model_cbox = QtWidgets.QComboBox() # combo box with color modes
        self.model_cbox.setFixedSize(100,20)
        self.model_cbox.addItems(['EM 2040', 'EM 302', 'EM 304', 'EM 710', 'EM 712', 'EM 122', 'EM 124']) # color modes
        
        model_info_layout = QtWidgets.QHBoxLayout()
        model_info_layout.addWidget(self.model_tb_lbl)
        model_info_layout.addWidget(self.model_cbox)
        
        self.ship_tb_lbl = QtWidgets.QLabel('Ship Name:')
        self.ship_tb_lbl.resize(100,20)
        self.ship_tb = QtWidgets.QLineEdit()
        self.ship_tb.setFixedSize(100,20)
        self.ship_tb.setText('R/V Unsinkable II')
        ship_info_layout = QtWidgets.QHBoxLayout()
        ship_info_layout.addWidget(self.ship_tb_lbl)
        ship_info_layout.addWidget(self.ship_tb)

        self.cruise_tb_lbl = QtWidgets.QLabel('Cruise Name:')
        self.cruise_tb_lbl.resize(100,20)
        self.cruise_tb = QtWidgets.QLineEdit()
        self.cruise_tb.setFixedSize(100,20)
        self.cruise_tb.setText('A 3-hour tour')
        cruise_info_layout = QtWidgets.QHBoxLayout()
        cruise_info_layout.addWidget(self.cruise_tb_lbl)
        cruise_info_layout.addWidget(self.cruise_tb)
        
        custom_info_layout = QtWidgets.QVBoxLayout()
        custom_info_layout.addLayout(model_info_layout)
        custom_info_layout.addLayout(ship_info_layout)
        custom_info_layout.addLayout(cruise_info_layout)
        
        self.custom_info_gb = QtWidgets.QGroupBox()
        self.custom_info_gb.setLayout(custom_info_layout)
        
        # add checkbox and set layout
        self.custom_info_chk = QtWidgets.QCheckBox('Use custom system information\n(default: parsed if available)')
        system_info_layout = QtWidgets.QVBoxLayout()
        system_info_layout.addWidget(self.custom_info_chk)
        system_info_layout.addWidget(self.custom_info_gb)
        
        system_info_gb = QtWidgets.QGroupBox('System Information')
        system_info_gb.setLayout(system_info_layout)

        # add custom plot axis limits
        self.max_z_lbl = QtWidgets.QLabel('Max depth (m):')
        self.max_z_lbl.resize(80, 20)
        self.max_z_tb = QtWidgets.QLineEdit()
        self.max_z_tb.setFixedSize(80, 20)
        self.max_z_tb.setText('')
        self.max_z_tb.setValidator(QDoubleValidator(0, 20000, 2))

        self.max_x_lbl = QtWidgets.QLabel('Max width (m):')
        self.max_x_lbl.resize(80, 20)
        self.max_x_tb = QtWidgets.QLineEdit()
        self.max_x_tb.setFixedSize(80, 20)
        self.max_x_tb.setText('')
        self.max_x_tb.setValidator(QDoubleValidator(0, 20000, 2))

        max_z_layout = QtWidgets.QHBoxLayout()
        max_z_layout.addWidget(self.max_z_lbl)
        max_z_layout.addWidget(self.max_z_tb)

        max_x_layout = QtWidgets.QHBoxLayout()
        max_x_layout.addWidget(self.max_x_lbl)
        max_x_layout.addWidget(self.max_x_tb)

        max_layout = QtWidgets.QVBoxLayout()
        max_layout.addLayout(max_z_layout)
        max_layout.addLayout(max_x_layout)

        self.max_gb = QtWidgets.QGroupBox()
        self.max_gb.setLayout(max_layout)
        self.max_gb.setEnabled(False)

        # add checkbox and set layout
        self.custom_max_chk = QtWidgets.QCheckBox('Use custom plot limits')
        custom_max_layout = QtWidgets.QVBoxLayout()
        custom_max_layout.addWidget(self.custom_max_chk)
        custom_max_layout.addWidget(self.max_gb)

        plot_lim_gb = QtWidgets.QGroupBox('Plot Limits')
        plot_lim_gb.setLayout(custom_max_layout)

        # add custom swath angle limits
        self.max_angle_lbl = QtWidgets.QLabel('Max angle (0-80 deg):')
        self.max_angle_lbl.resize(140, 20)
        self.max_angle_tb = QtWidgets.QLineEdit()
        self.max_angle_tb.setFixedSize(50, 20)
        self.max_angle_tb.setText('75')
        self.max_angle_tb.setValidator(QDoubleValidator(0, 80, 2))

        self.min_angle_lbl = QtWidgets.QLabel('Min angle (0-80 deg):')
        self.min_angle_lbl.resize(140, 20)
        self.min_angle_tb = QtWidgets.QLineEdit()
        self.min_angle_tb.setFixedSize(50, 20)
        self.min_angle_tb.setText('0')
        self.min_angle_tb.setValidator(QDoubleValidator(0, 80, 2))

        max_angle_layout = QtWidgets.QHBoxLayout()
        max_angle_layout.addWidget(self.max_angle_lbl)
        max_angle_layout.addWidget(self.max_angle_tb)

        min_angle_layout = QtWidgets.QHBoxLayout()
        min_angle_layout.addWidget(self.min_angle_lbl)
        min_angle_layout.addWidget(self.min_angle_tb)

        angle_layout = QtWidgets.QVBoxLayout()
        angle_layout.addLayout(min_angle_layout)
        angle_layout.addLayout(max_angle_layout)

        self.angle_gb = QtWidgets.QGroupBox()
        self.angle_gb.setLayout(angle_layout)
        self.angle_gb.setEnabled(False)

        # add checkbox and set layout
        self.custom_angle_chk = QtWidgets.QCheckBox('Hide data by angle (per side)')
        custom_angle_layout = QtWidgets.QVBoxLayout()
        custom_angle_layout.addWidget(self.custom_angle_chk)
        custom_angle_layout.addWidget(self.angle_gb)

        swath_lim_gb = QtWidgets.QGroupBox('Swath Angle Limits')
        swath_lim_gb.setLayout(custom_angle_layout)

        # add custom depth limits
        self.max_depth_lbl = QtWidgets.QLabel('Max depth (m):')
        self.max_depth_lbl.resize(100, 20)
        self.max_depth_tb = QtWidgets.QLineEdit()
        self.max_depth_tb.setFixedSize(40, 20)
        self.max_depth_tb.setText('10000')
        self.max_depth_tb.setValidator(QDoubleValidator(0, np.inf, 2))
        self.max_depth_arc_tb = QtWidgets.QLineEdit()
        self.max_depth_arc_tb.setFixedSize(40, 20)
        self.max_depth_arc_tb.setText('10000')
        self.max_depth_arc_tb.setValidator(QDoubleValidator(0, np.inf, 2))

        self.min_depth_lbl = QtWidgets.QLabel('Min depth (m):')
        self.min_depth_lbl.resize(100, 20)
        self.min_depth_tb = QtWidgets.QLineEdit()
        self.min_depth_tb.setFixedSize(40, 20)
        self.min_depth_tb.setText('0')
        self.min_depth_tb.setValidator(QDoubleValidator(0, np.inf, 2))
        self.min_depth_arc_tb = QtWidgets.QLineEdit()
        self.min_depth_arc_tb.setFixedSize(40, 20)
        self.min_depth_arc_tb.setText('0')
        self.min_depth_arc_tb.setValidator(QDoubleValidator(0, np.inf, 2))

        # original depth limits layout
        # max_depth_layout = QtWidgets.QHBoxLayout()
        # max_depth_layout.addWidget(self.max_depth_lbl)
        # max_depth_layout.addWidget(self.max_depth_tb)
        # max_depth_layout.addWidget(self.max_depth_arc_tb)
        #
        # min_depth_layout = QtWidgets.QHBoxLayout()
        # min_depth_layout.addWidget(self.min_depth_lbl)
        # min_depth_layout.addWidget(self.min_depth_tb)
        # min_depth_layout.addWidget(self.min_depth_arc_tb)
        #
        # depth_layout = QtWidgets.QVBoxLayout()
        # depth_layout.addWidget(self.custom_depth_lbl)
        # depth_layout.addLayout(min_depth_layout)
        # depth_layout.addLayout(max_depth_layout)

        # new depth limits layout
        self.custom_depth_arc_lbl = QtWidgets.QLabel('Archive')
        self.custom_depth_new_lbl = QtWidgets.QLabel('New')

        depth_layout_left = QtWidgets.QVBoxLayout()
        depth_layout_left.addWidget(QtWidgets.QLabel(''))  # empty space above min and max depth labels
        depth_layout_left.addWidget(self.min_depth_lbl)
        depth_layout_left.addWidget(self.max_depth_lbl)

        depth_layout_center = QtWidgets.QVBoxLayout()
        depth_layout_center.addWidget(self.custom_depth_new_lbl)
        depth_layout_center.addWidget(self.min_depth_tb)
        depth_layout_center.addWidget(self.max_depth_tb)

        depth_layout_right = QtWidgets.QVBoxLayout()
        depth_layout_right.addWidget(self.custom_depth_arc_lbl)
        depth_layout_right.addWidget(self.min_depth_arc_tb)
        depth_layout_right.addWidget(self.max_depth_arc_tb)

        depth_layout = QtWidgets.QHBoxLayout()
        depth_layout.addLayout(depth_layout_left)
        depth_layout.addLayout(depth_layout_center)
        depth_layout.addLayout(depth_layout_right)

        self.depth_gb = QtWidgets.QGroupBox()
        self.depth_gb.setLayout(depth_layout)
        self.depth_gb.setEnabled(False)

        # add checkbox and set layout
        self.custom_depth_chk = QtWidgets.QCheckBox('Hide data by depth (new/archive)')
        custom_depth_layout = QtWidgets.QVBoxLayout()
        custom_depth_layout.addWidget(self.custom_depth_chk)
        custom_depth_layout.addWidget(self.depth_gb)

        depth_lim_gb = QtWidgets.QGroupBox('Swath Depth Limits')
        depth_lim_gb.setLayout(custom_depth_layout)

        # add data decimation
        self.dec_fac_lbl = QtWidgets.QLabel('Dec. factor (0-inf):')
        self.dec_fac_lbl.resize(140, 20)
        self.dec_fac_tb = QtWidgets.QLineEdit()
        self.dec_fac_tb.setFixedSize(50, 20)
        self.dec_fac_tb.setText('0')
        self.dec_fac_tb.setValidator(QDoubleValidator(0, np.inf, 2))

        dec_fac_layout = QtWidgets.QHBoxLayout()
        dec_fac_layout.addWidget(self.dec_fac_lbl)
        dec_fac_layout.addWidget(self.dec_fac_tb)

        self.dec_fac_gb = QtWidgets.QGroupBox()
        self.dec_fac_gb.setLayout(dec_fac_layout)
        self.dec_fac_gb.setEnabled(False)

        # add checkbox and set layout
        self.dec_fac_chk = QtWidgets.QCheckBox('Decimate data (plot faster)')
        custom_dec_layout = QtWidgets.QVBoxLayout()
        custom_dec_layout.addWidget(self.dec_fac_chk)
        custom_dec_layout.addWidget(self.dec_fac_gb)

        dec_gb = QtWidgets.QGroupBox('Data Decimation')
        dec_gb.setLayout(custom_dec_layout)

        # set the plot control layout
        self.plot_control_layout = QtWidgets.QVBoxLayout()
        self.plot_control_layout.addWidget(system_info_gb)        
        self.plot_control_layout.addWidget(pt_size_gb)
        self.plot_control_layout.addWidget(pt_color_gb)
        self.plot_control_layout.addWidget(toggle_gb)
        self.plot_control_layout.addWidget(plot_lim_gb)
        self.plot_control_layout.addWidget(swath_lim_gb)
        self.plot_control_layout.addWidget(depth_lim_gb)
        self.plot_control_layout.addWidget(dec_gb)

        # set plot control group box
        self.plot_control_gb = QtWidgets.QGroupBox('Plot Control')
        self.plot_control_gb.setLayout(self.plot_control_layout)
        self.plot_control_gb.setFixedWidth(225)

        # set the right panel layout
        self.right_layout = QtWidgets.QVBoxLayout()
        self.right_layout.addWidget(self.plot_control_gb)
        self.right_layout.addStretch()

    def set_main_layout(self):
        # set the main layout with file controls on left and swath figure on right
        main_layout = QtWidgets.QHBoxLayout()
        main_layout.addLayout(self.left_layout)
        main_layout.addLayout(self.swath_layout)
        main_layout.addLayout(self.right_layout)
        
        self.mainWidget.setLayout(main_layout)

    def add_files(self, ftype_filter, input_dir='HOME'): # select files with desired type, add to list box
        # fnames = QtWidgets.QFileDialog.getOpenFileNames(self, 'Open files...', os.getenv('HOME'), ftype_filter)

        if input_dir == 'HOME':  # select files manually if input_dir not specified as optional argument
            fnames = QtWidgets.QFileDialog.getOpenFileNames(self, 'Open files...', os.getenv('HOME'), ftype_filter)
            # fnames = fnames[0]  # keep only the filenames in first list item returned from getOpenFileNames

        else:  # get all files satisfying ftype_filter in input_dir
            fnames = []
            for f in os.listdir(input_dir):  # step through all files in this directory
                if os.path.isfile(os.path.join(input_dir, f)):  # verify it's a file
                    if os.path.splitext(f)[1] == ftype_filter:  # verify ftype_filter extension
                        fnames.append(os.path.join(input_dir, f))  # add whole path, same convention as getOpenFileNames

        self.get_current_file_list()  # get updated file list and add selected files only if not already listed
        fnames_new = [fn for fn in fnames[0] if fn not in self.filenames]
        fnames_skip = [fs for fs in fnames[0] if fs in self.filenames]

        if len(fnames_skip) > 0:  # skip any files already added, update log
            self.update_log('Skipping ' + str(len(fnames_skip)) + ' file(s) already added')
        
        for f in range(len(fnames_new)): # add the new files only
            self.file_list.addItem(fnames_new[f])
            self.update_log('Added ' + fnames_new[f].split('/')[-1])

        # set calculate_coverage button red if new .all files loaded
        if len(fnames_new) > 0 and ftype_filter == 'Kongsberg .all(*.all)':
            self.calc_coverage_btn.setStyleSheet("background-color: yellow")

    def get_input_dir(self):
        try:
            self.input_dir = QtWidgets.QFileDialog.getExistingDirectory(self, 'Add directory',
                                                                        os.getenv('HOME'))
            self.update_log('Added directory: ' + self.input_dir)

            # get a list of all .txt files in that directory, '/' avoids '\\' in os.path.join in add_files
            self.update_log('Adding files in directory: ' + self.input_dir)
            self.add_files('Kongsberg .all(*.all)')
            # self.add_files(ftype_filter='.txt', input_dir=self.input_dir + '/')

        except ValueError:
            self.update_log('No input directory selected.')
            self.input_dir = ''
            pass

    def get_output_dir(self):  # get output directory for saving plots
        try:
            new_output_dir = QtWidgets.QFileDialog.getExistingDirectory(self, 'Select output directory',
                                                                        os.getenv('HOME'))

            if new_output_dir is not '':  # update output directory if not cancelled
                self.output_dir = new_output_dir
                self.update_log('Selected output directory: ' + self.output_dir)
                self.current_outdir_lbl.setText('Current output directory: ' + self.output_dir)

        except:
            self.update_log('No output directory selected.')
            pass

    def remove_files(self): # remove selected files
        self.get_current_file_list()
        selected_files = self.file_list.selectedItems()
        fnames_all = [f for f in self.filenames if '.all' in f]
        fnames_pkl = [f for f in self.filenames if '.pkl' in f]
        
        if len(fnames_all) + len(fnames_pkl) == 0: # all .all and .pkl files have been removed, reset det and det_archive dicts
            self.det = {}
            self.det_archive = {}
            
        elif not selected_files: # files exist but nothing is selected
            self.update_log('No files selected for removal.')
            return

        else: # remove only the files that have been selected
            for f in selected_files:
                fname = f.text().split('/')[-1]
                self.file_list.takeItem(self.file_list.row(f))
                self.update_log('Removed ' + fname)

                try: # try to remove detections associated with this file
                    if '.all' in fname:
                        i = [j for j in range(len(self.det['fname'])) if self.det['fname'][j] == fname] # get indices of soundings in det dict with matching filenames
                    
                        for k in self.det.keys(): # loop through all keys and remove values at these indices
                            self.det[k] = np.delete(self.det[k],i).tolist()

                    elif '.pkl' in fname:
                        self.det_archive.pop(fname, None)
                    
                except:  # will fail if detection dict has not been created yet (e.g., if calc_coverage has not been run)
                    self.update_log('Failed to remove soundings from ' + fname)
                    pass
                            
        self.refresh_plot() # refresh with updated (reduced or cleared) detection data
        
    def clear_files(self):
        self.file_list.clear() # clear the file list display
        self.filenames = [] # clear the list of (paths + files) passed to calc_coverage
        self.det = {} # clear current non-archive detections
        self.det_archive = {} # clear dictionary of archive detection dictionaries
        self.update_log('Cleared all files')
        self.current_file_lbl.setText('Current File [0/0]:')
        self.calc_pb.setValue(0)
        self.remove_files()

    def get_current_file_list(self): # get current list of files in qlistwidget
        list_items = []
        for f in range(self.file_list.count()):
            list_items.append(self.file_list.item(f))
        
        self.filenames = [f.text() for f in list_items] # convert to text

    def get_new_file_list(self, fext = '', flist_old = []):
        # determine list of new files with file extension fext that do not exist in flist_old
        # flist_old may contain paths as well as file names; compare only file names
        self.get_current_file_list()
        fnames_ext = [f for f in self.filenames if fext in f] # file names (with paths) that match the extension
        fnames_old = [f.split('/')[-1] for f in flist_old] # file names only (no paths) from flist_old 
        fnames_new = [fn for fn in fnames_ext if fn.split('/')[-1] not in fnames_old] # check if file name (without path) exists in fnames_old
        return(fnames_new) # return the fnames_new (with paths)

    def calc_coverage(self):
        # calculate swath coverage from new .all files and update the detection dictionary
        try:
            fnames_det = list(set(self.det['fname'])) # make list of unique filenames already in det dict
        except:
            fnames_det = [] # self.det has not been created yet
            self.det = {}

        fnames_new_all = self.get_new_file_list('.all', fnames_det) # list new .all files not included in det dict
#        self.update_log('Found ' + str(len(fnames_new_all)) + ' new .all files')
            
        if len(fnames_new_all) > 0: # proceed if at least one new .all file
            self.update_log('Calculating coverage from ' + str(len(fnames_new_all)) + ' new file(s)')
            QtWidgets.QApplication.processEvents() # try processing and redrawing the GUI to make progress bar update
            data = {}
            
            # update progress bar and log
            self.calc_pb.setValue(0) # reset progress bar to 0 and max to number of files
            self.calc_pb.setMaximum(len(fnames_new_all))
            
            for f in range(len(fnames_new_all)):         # read previously unparsed files
                fname_str = fnames_new_all[f].rsplit('/')[-1]
                self.current_file_lbl.setText('Parsing new file [' + str(f+1) + '/' + str(len(fnames_new_all)) + ']: ' + fname_str)
                QtWidgets.QApplication.processEvents()
                data[f] = multibeam_tools.libs.parseEMswathwidth.parseEMswathwidth(fnames_new_all[f], print_updates = True)
                self.update_log('Parsed file ' + fname_str)
                self.update_prog(f+1)
            
            self.data = multibeam_tools.libs.readEM.interpretMode(data, print_updates = False) # interpret modes
            det_new = multibeam_tools.libs.readEM.sortDetections(data, print_updates = False) # sort new detections (includes filename for each for later reference)
                        
            if len(self.det) is 0: # if length of detection dict is 0, store all new detections
                self.det = det_new
                
            else: # otherwise, append new detections to existing detection dict                
                for key, value in det_new.items(): # loop through the new data and append to existing self.det
                    self.det[key].extend(value)
            
            self.update_log('Finished calculating coverage from ' + str(len(fnames_new_all)) + ' new file(s)')
            self.current_file_lbl.setText('Current File [' + str(f+1) + '/' + str(len(fnames_new_all)) + ']: Finished calculating coverage')
            self.refresh_plot()             # refresh the plot
            
        else: # if no .all files are listed
            self.update_log('No new .all file(s) added.  Please add new .all file(s) and calculate coverage.')

        self.calc_coverage_btn.setStyleSheet("background-color: none") # reset the button color to default

    def update_log(self, entry): # update the activity log
        self.log.append(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' ' + entry)
        QtWidgets.QApplication.processEvents()

    def update_prog(self, total_prog):
        self.calc_pb.setValue(total_prog)
        QtWidgets.QApplication.processEvents()

    def refresh_plot(self): # update swath plot with new data and options
#        self.init_axes()
        print('refreshing plot')
        self.clear_plot()
        self.update_color_modes()  # initialize self.cmode if cmode not changed previously
        self.angle_gb.setEnabled(self.custom_angle_chk.isChecked())
        self.depth_gb.setEnabled(self.custom_depth_chk.isChecked())
        self.dec_fac_gb.setEnabled(self.dec_fac_chk.isChecked())
        self.show_archive()  # plot archive data with new plot control values
        
        try:
            self.plot_coverage(self.det, False)  # plot new data if available
        except:
            pass
            self.update_log('No .all coverage data available.  Please load files and calculate coverage.')

        self.update_axes()  # update axes to fit all loaded data
        # add WD and angle lines after axes are updated with custom limits
        self.add_grid_lines()  # add grid lines
        self.add_WD_lines()  # add water depth-multiple lines over coverage
        self.add_nominal_angle_lines()  # add nominal swath angle lines over coverage
        self.add_legend()  # add legend or colorbar
        self.swath_canvas.draw()  # final update for the swath canvas

    def init_swath_ax(self): # set initial swath parameters
        self.swath_ax = self.swath_figure.add_subplot(111)
        self.x_max = 1
        self.z_max = 1
        self.x_max_custom = self.x_max # store future custom entries
        self.z_max_custom = self.z_max
        self.max_x_tb.setText(str(self.x_max))
        self.max_z_tb.setText(str(self.z_max))
        self.update_color_modes()
        # self.clim = []
        # self.clim_arc = []
        self.cruise_name = ''
        self.N_WD_max = 8
        self.nominal_angle_line_interval = 15  # degrees between nominal angle lines
        self.nominal_angle_line_max = 75  # maximum desired nominal angle line
        self.swath_ax_margin = 1.1  # scale axes to multiple of max data in each direction
        self.add_grid_lines()
        self.update_axes()
        self.color = QtGui.QColor(0,0,0)  # set default solid color to black for new data
        self.color_arc = QtGui.QColor('darkGray')
        self.color_cbox_arc.setCurrentText('Solid Color')

    def plot_coverage(self, det, is_archive): # plot the parsed detections from new or archive data
        # consolidate data from port and stbd sides for plotting
        x_all = det['x_port'] + det['x_stbd']
        z_all = det['z_port'] + det['z_stbd']
        c_all = []

        print('entering plot_coverage with x_all and z_all lengths', len(x_all), len(z_all))

        cmode = self.cmode  # get color mode for local use depending on new / archive data
        if is_archive:
            cmode = self.cmode_arc

        # update x and z max for axis resizing during each plot call
        self.x_max = max([self.x_max, np.max(np.abs(np.asarray(x_all)))])
        self.z_max = max([self.z_max, np.max(np.asarray(z_all))])

        # apply the angle filter to the local detections, but do this after determining x_max and z_max
        angle_all = np.rad2deg(np.abs(np.arctan2(x_all,z_all)))

        # set point size; slider is on [1-11] for small # of discrete steps; square slider value for real pt size
        pt_size = np.square(self.pt_size_slider.value())

        if self.custom_angle_chk.isChecked():
            # find indices for angles within user thresholds
            angle_idx = np.logical_and(np.asarray(angle_all) >= float(self.min_angle_tb.text()),
                                       np.asarray(angle_all) <= float(self.max_angle_tb.text()))

            # apply indices to generate reduced x_all and z_all for plotting
            x_all = np.asarray(x_all)[angle_idx].tolist()
            z_all = np.asarray(z_all)[angle_idx].tolist()

        if self.custom_depth_chk.isChecked():
            lims = [float(self.min_depth_tb.text()), float(self.max_depth_tb.text())]

            if is_archive:
                lims = [float(self.min_depth_arc_tb.text()), float(self.max_depth_arc_tb.text())]

            # find indices for depths within user thresholds
            depth_idx = np.logical_and(np.asarray(z_all) >= lims[0],
                                       np.asarray(z_all) <= lims[1])

            # apply indices to generate reduced x_all and z_all for plotting
            x_all = np.asarray(x_all)[depth_idx].tolist()
            z_all = np.asarray(z_all)[depth_idx].tolist()

        # set the color map, initialize color limits and set for legend/colorbars (will apply to last det data plotted)
        self.cmap = 'rainbow'
        self.clim = []
        # self.clim_arc = []
        self.cset = []
        self.legend_label = ''

        # set color maps based on combobox selection
        if cmode == 'depth':
            c_all = z_all # set color range to depth range
            # c_min = min(c_all)
            # c_max = max(c_all)
            self.clim = [min(c_all), max(c_all)]
            self.cmap = self.cmap + '_r'  # reverse the color map so shallow is red, deep is blue
            self.legend_label = 'Depth (m)'
        
        elif cmode == 'backscatter':
            bs_all = det['bs_port'] + det['bs_stbd']
            # c_all = []
            c_all = [int(bs)/10 for bs in bs_all] # convert to int, divide by 10 (BS reported in 0.1 dB)
            # c_min = -50
            # c_max = -20
            self.clim = [-50, -20]
            self.legend_label = 'Reported Backscatter (dB)'

        # sort through other color mode options (see readEM.interpretMode for strings used for each option)
        # modes are listed for each ping, rather than each detection
        # elif np.isin(cmode, ['ping_mode', 'pulse_form', 'swath_mode']):

        elif np.isin(cmode, ['ping_mode', 'pulse_form', 'swath_mode']):
            # modes are listed per ping; append ping-wise setting to corresponed with x_all, z_all
            c_list = det[cmode] + det[cmode]

            if cmode == 'ping_mode':
                c_set = ['Very Shallow', 'Shallow', 'Medium', 'Deep', 'Very Deep', 'Extra Deep']  # set of ping modes
                self.legend_label = 'Ping Mode'
                
            elif cmode == 'pulse_form':
                c_set = ['CW', 'Mixed', 'FM']  # set of pulse forms
                self.legend_label = 'Pulse Form'
                
            elif cmode == 'swath_mode':
                c_set = ['Single Swath', 'Dual Swath (Fixed)', 'Dual Swath (Dynamic)']  # set of all swath modes
                self.legend_label = 'Swath Mode'
                
            # c_all = []
            # set up list comprehension to find integer corresponding to mode of each detection
            c_all = [c_set.index(c_list[i]) for i in range(len(c_list))]
            # c_min = 0
            # c_max = len(c_set)-1  # set max of colorscale to correspond with greatest possible index for selected mode
            self.clim = [0, len(c_set)-1]
            self.cset = c_set

        else:
            print('else --> cmode must be solid_color...')

        # if selected, decimate the data for plotting by selected mode
        self.decimation_factor = max(self.dec_fac_chk.isChecked()*int(self.dec_fac_tb.text()), 1)
        # decimate by 1000 for testing
        if self.dec_fac_chk.isChecked():
            self.update_log('Trying to decimate data by ' + str(self.decimation_factor))

#####################################################################################################
        # try decimating by N_max allowed in N_bins
        # get max sounding count allowed by decimation factor
        # N_bins = 10
        # N_max_bin = np.floor(len(x_all)/self.decimation_factor/N_bins)
        # print('N_max_bin:', N_max_bin)
        #
        # dz_bin = (max(z_all)-min(z_all))/N_bins
        # print('dz_bin is', dz_bin)
        # z_bins = [z for z in range(min(z_all), max(z_all), (max(z_all)-min(z_all))/N_bins)]
        #
        #
        # for z in z_bins:
        #     z_idx = np.logical_and(np.asarray(z_all) >= float(z),
        #                            np.asarray(z_all) <= float()
        #                            )
        #
        #
        #     angle_idx = np.logical_and(np.asarray(angle_all) >= float(self.min_angle_tb.text()),
        #                                np.asarray(angle_all) <= float(self.max_angle_tb.text()))
        #
        #     # apply indices to generate reduced x_all and z_all for plotting
        #     x_all = np.asarray(x_all)[angle_idx].tolist()
        #     z_all = np.asarray(z_all)[angle_idx].tolist()
######################################################################################################

        # simple decimation
        x_all = x_all[0::self.decimation_factor]
        z_all = z_all[0::self.decimation_factor]
        c_all = c_all[0::self.decimation_factor]

        # print(cmode, self.color_arc.name(), self.color.name())

        # plot x_all vs z_all using colormap c_all
        if cmode == 'solid_color':   # or is_archive is True: # plot solid color if selected, or archive data
            # print('made it to cmode == solid_color')

            if is_archive is True:
                c_all = colors.hex2color(self.color_arc.name())  # set archive color
            else:
                c_all = colors.hex2color(self.color.name())  # set desired color from color dialog

            # convert c_all for solid colors to array to avoid warning ("c looks like single numeric RGB sequence...")
            c_all = np.tile(np.asarray(c_all), (len(x_all),1))

            # print('cmode is solid color, lengths are', len(x_all), len(z_all), len(c_all))
            self.mappable = self.swath_ax.scatter(x_all, z_all, s=pt_size, c=c_all, marker='o')

            # self.swath_ax.scatter(x_all, z_all, s = self.pt_size_slider.value(), c = c_all, marker = 'o')

        else:  # plot other color scheme, specify vmin and vmax from color range
            self.mappable = self.swath_ax.scatter(x_all, z_all, s=pt_size, c=c_all, marker='o',
                                                  vmin=self.clim[0], vmax=self.clim[1], cmap=self.cmap)
            # self.swath_ax.scatter(x_all, z_all, s = self.pt_size_slider.value(), c = c_all, marker = 'o',
            #                       vmin=c_min, vmax=c_max, cmap=self.cmap)  # specify vmin and vmax

        self.swath_canvas.draw()  # refresh swath canvas in main window

        # # store color limits for legend use
        # if is_archive:
        #     self.clim_arc = [c_min, c_max]
        # else:
        #     self.clim = [c_min, c_max]

#################### add legend testing from ZRX plotter
        # ax1.plot(ZRX_module, ZRX_last.flatten(), color='k', linewidth=2)
        # line, = ax2.plot(ZRX_module, ZRX_array_last.flatten(), color='k', linewidth=2)
        #
        # legend_artists.append(line)  # add line artist to legend list
        # legend_labels.append('Last')
        #
        # print('just added last black lines')
        # print(legend_artists)
        # print(legend_labels)
        #
        # # set legend
        # ax1.legend(legend_artists, legend_labels, loc='upper right', fontsize=axfsize)
        # ax2.legend(legend_artists, legend_labels, loc='upper right', fontsize=axfsize)
#####################################

    def update_system_info(self):
        # update model, serial number, ship, cruise based on availability in parsed data and/or custom fields
        if self.custom_info_chk.isChecked(): # use custom info if checked
            self.custom_info_gb.setEnabled(True) # enable the custom info group box
            self.ship_name = self.ship_tb.text()
            self.cruise_name = self.cruise_tb.text()
            self.model_name = self.model_cbox.currentText()
        else: # get info from detections if available
            self.custom_info_gb.setEnabled(False) # disable the custom info group box

            try: # try to grab ship name from filenames (conventional file naming)
                self.ship_name = self.det['fname'][0] # try getting ship name from first detection filename
                self.ship_name = self.ship_name[self.ship_name.rfind('_')+1:-4] # assumes filename ends in _SHIPNAME.all
            except:
                self.ship_name = 'SHIP NAME N/A' # if ship name not available in filename
                
            try: # try to grab cruise name from Survey ID field in 
                self.cruise_name = self.data[0]['IP_start'][0]['SID'].upper() # update cruise ID with Survey ID
            except:
                self.cruise_name = 'CRUISE N/A'
    
            try:
                self.model_name = 'EM ' + str(self.data[0]['IP_start'][0]['MODEL'])
            except:
                self.model_name = 'MODEL N/A' 

    def update_axes(self):
        self.update_system_info()
        self.update_plot_limits()
        # adjust x and y axes to fit max data
        self.swath_ax.set_ylim(0, self.swath_ax_margin*self.z_max) # set depth axis to 0 and 1.1 times max(z) 
        self.swath_ax.set_xlim(-1*self.swath_ax_margin*self.x_max,
                               self.swath_ax_margin*self.x_max) # set x axis to +/-1.1 times max(abs(x))
            
        title_str = 'Swath Width vs. Depth\n' + self.model_name + ' - ' + self.ship_name + ' - ' + self.cruise_name
        self.swath_ax.set(xlabel='Swath Coverage (m)', ylabel='Depth (m)', title=title_str)
        self.swath_ax.invert_yaxis() # invert the y axis
        plt.show() # need show() after axis update!
        # self.swath_canvas.draw()

    def update_plot_limits(self):
        # expand custom limits to accommodate new data
        self.x_max_custom = max([self.x_max, self.x_max_custom])
        self.z_max_custom = max([self.z_max, self.z_max_custom])

        if self.x_max > self.x_max_custom or self.z_max > self.z_max_custom:
            self.custom_max_chk.setChecked(False) # force automatic limit updates with new data
            self.x_max_custom = max([self.x_max, self.x_max_custom])
            self.z_max_custom = max([self.z_max, self.z_max_custom])

        if self.custom_max_chk.isChecked():  # use custom plot limits if checked
            self.max_gb.setEnabled(True)
            self.x_max_custom = int(self.max_x_tb.text())
            self.z_max_custom = int(self.max_z_tb.text())
            self.x_max = self.x_max_custom/self.swath_ax_margin # divide custom limit by axis margin (multiplied later)
            self.z_max = self.z_max_custom/self.swath_ax_margin

        else: # revert to automatic limits from the data if unchecked, but keep the custom numbers in text boxes
            self.max_gb.setEnabled(False)
            # set text boxes to latest relevent custom value
            self.max_x_tb.setText(str(int(self.x_max_custom)))
            self.max_z_tb.setText(str(int(self.z_max_custom)))

    def update_color_modes(self):
        # update color modes for the new data and archive data
        self.cmode = self.color_cbox.currentText()  # get the currently selected color mode
        self.cmode = self.cmode.lower().replace(' ', '_')  # format for comparison to list of modes below
        self.scbtn.setEnabled(self.cmode == 'solid_color')

        # enable archive color options if 'show archive' is checked
        self.color_cbox_arc.setEnabled(self.archive_toggle_chk.isChecked())
        self.cmode_arc = self.color_cbox_arc.currentText()  # get the currently selected color mode
        self.cmode_arc = self.cmode_arc.lower().replace(' ', '_')  # format for comparison to list of modes below
        self.scbtn_arc.setEnabled(self.archive_toggle_chk.isChecked() and self.cmode_arc == 'solid_color')

    def update_solid_color(self, field):  # launch solid color dialog and assign to designated color attribute
        print('start update_solid_color with field', field)

        temp_color = QtWidgets.QColorDialog.getColor()
        print(temp_color)
        setattr(self,field,temp_color)  # field is either 'color' (new data) or 'color_arc' (archive data)
        self.refresh_plot()
        print('end update_solid_color')

    def add_grid_lines(self):
        if self.grid_lines_toggle_chk.isChecked(): # turn on grid lines
            self.swath_ax.grid()
            self.swath_ax.minorticks_on()
            self.swath_ax.grid(which = 'both', linestyle = '-', linewidth = '0.5', color = 'black')
        else:
            self.swath_ax.grid(False) # turn off the grid lines
            self.swath_ax.minorticks_off()
            
        self.swath_canvas.draw() # redraw swath canvas with grid lines
        
    def add_WD_lines(self):
        # add water-depth-multiple lines
        if self.WD_lines_toggle_chk.isChecked(): # plot WD lines if checked
            try:
                # loop through multiples of WD (-port,+stbd) and plot grid lines with text 
                for n in range(1,self.N_WD_max+1):   # add 1 for indexing, do not include 0X WD
                    for ps in [-1,1]:           # port/stbd multiplier
                        self.swath_ax.plot([0, ps*n*self.swath_ax_margin*self.z_max/2],\
                                           [0,self.swath_ax_margin*self.z_max], 'k', linewidth = 1)
                        x_mag = 0.9*n*self.z_max/2 # set magnitude of text locations to 90% of line end
                        y_mag = 0.9*self.z_max
                        
                        # keep text locations on the plot
                        if x_mag > 0.9*self.x_max:
                            x_mag = 0.9*self.x_max
                            y_mag = 2*x_mag/n # scale y location with limited x location
                            
                        self.swath_ax.text(x_mag*ps, y_mag, str(n) + 'X',
                                verticalalignment = 'center', horizontalalignment = 'center',
                                bbox=dict(facecolor='white', edgecolor = 'none', alpha=1, pad = 0.0))    
                self.swath_canvas.draw()
            
            except:
                error_msg = QtWidgets.QMessageBox()
                error_msg.setText('Failure plotting the WD lines...')

    def add_nominal_angle_lines(self):
        # add lines approximately corresponding to nominal swath angles; these are based on plot
        # geometry only and are not RX angles (e.g., due to attitude and refraction)
        if self.nominal_angle_lines_toggle_chk.isChecked(): # plot nominal lines if checked
            try:
                # loop through beam lines (-port,+stbd) and plot grid lines with text
                for n in range(1,int(np.floor(self.nominal_angle_line_max/self.nominal_angle_line_interval)+1)):   # repeat for desired number of beam angle lines, skip 0
                    for ps in [-1,1]:           # port/stbd multiplier
                        x_line_mag = self.swath_ax_margin*self.z_max*np.tan(n*self.nominal_angle_line_interval*np.pi/180)
                        y_line_mag = self.swath_ax_margin*self.z_max
                        self.swath_ax.plot([0, ps*x_line_mag],\
                                           [0, y_line_mag], 'k', linewidth = 1)
                        x_label_mag = 0.9*x_line_mag # set magnitude of text locations to 90% of line end
                        y_label_mag = 0.9*y_line_mag
                        
                        # keep text locations on the plot
                        if x_label_mag > 0.9*self.x_max:
                            x_label_mag = 0.9*self.x_max
                            y_label_mag = x_label_mag/np.tan(n*self.nominal_angle_line_interval*np.pi/180)
                        
                        self.swath_ax.text(x_label_mag*ps, y_label_mag, str(n*self.nominal_angle_line_interval) + '\xb0',
                                verticalalignment ='center', horizontalalignment='center',
                                bbox=dict(facecolor='white', edgecolor='none', alpha=1, pad=0.0))
                self.swath_canvas.draw()
            
            except:
                self.update_log('Failure plotting the swath angle lines...')

    def add_legend(self):
        print('adding legend')
        # make legend or colorbar corresponding to clim and cset

        try:
            self.cbarbase.remove()
        except:
            print('failed to remove cbar')

        # local_colors = plt.get_cmap(self.cmap)
        # print('in add_legend')

        print('self.clim is', self.clim)
        print('self.cset is', self.cset)

        if self.colorbar_chk.isChecked() and self.clim:
        # if self.clim:  # clim is not empty --> make legend/colorbar for non-solid-color option
            print('making a colorbar or legend for non-solid-color option')

            if self.cset:  # clim and cset not empty --> make legend with discrete colors for ping, pulse, or swath mode
                print('making a legend for ping, pulse, or swath mode')
                # colors(np.linspace(0, 1, NUMBER OF ENTRIES)  # set up line colors over number of years

            else:  # cset is empty --> make colorbar for depth or backscatter
                print('making a colorbar for depth or backscatter')
                cbaxes = inset_axes(self.swath_ax, width="2%", height="30%", loc=1)
                # self.cbar = self.swath_figure.colorbar(self.mappable, cax=cbaxes, ticks=self.clim, orientation='vertical')
                tickvalues = np.linspace(self.clim[0], self.clim[1], 10)
                ticklabels = [str(round(float(tick))) for tick in tickvalues]
                # print('tickvalues will be', tickvalues)
                # print('ticklabels will be', ticklabels)
                self.cbarbase = matplotlib.colorbar.ColorbarBase(cbaxes, cmap=self.cmap, orientation='vertical',
                                                                 norm=colors.Normalize(self.clim[0], self.clim[1]),
                                                                 ticks=tickvalues,
                                                                 ticklocation='left',
                                                                 label=self.legend_label)

                if self.cmode == 'depth':
                    self.cbarbase.ax.invert_yaxis()  # invert for depth using rainbow_r colormap; BS is rainbow

                self.cbarbase.set_ticklabels(ticklabels)
                # self.cbarbase.set_label(self.cmode)

                # set label from
                # self.cbar = self.swath_figure.colorbar(self.mappable)

        else:
            # clim not defined --> make legend for solid color
            # FUTURE: add custom text option in legend for datasets using solid color, useful for comparison plots
            print('this is just a solid color')




        # from matplotlib.lines import Line2D
        # custom_lines = [Line2D([0], [0], color=cmap(0.), lw=4),
        #                 Line2D([0], [0], color=cmap(.5), lw=4),
        #                 Line2D([0], [0], color=cmap(1.), lw=4)]
        #
        # fig, ax = plt.subplots()
        # lines = ax.plot(data)
        # ax.legend(custom_lines, ['Cold', 'Medium', 'Hot'])

        # import matplotlib.patches as mpatches
        # import matplotlib.pyplot as plt
        # import numpy as np
        #
        # data = np.random.randint(8, size=(100, 100))
        # cmap = plt.cm.get_cmap('PiYG', 8)
        # plt.pcolormesh(data, cmap=cmap, alpha=0.75)
        # # Set borders in the interval [0, 1]
        # bound = np.linspace(0, 1, 9)
        # # Preparing borders for the legend
        # bound_prep = np.round(bound * 7, 2)
        # # Creating 8 Patch instances
        # plt.legend([mpatches.Patch(color=cmap(b)) for b in bound[:-1]],
        #            ['{} - {}'.format(bound_prep[i], bound_prep[i + 1] - 0.01) for i in range(8)])


    def save_plot(self):
        # save a .PNG of the swath plot
        plot_path = QtWidgets.QFileDialog.getSaveFileName(self,'Save plot as...', os.getenv('HOME'),
                                                          ".PNG file (*.PNG);; .JPG file (*.JPG);; .TIF file (*.TIF)")
        fname_out = plot_path[0]

        self.swath_figure.savefig(fname_out,
                                  dpi=600, facecolor='w', edgecolor='k',
                                  orientation='portrait', papertype=None, format=None,
                                  transparent=False, bbox_inches=None, pad_inches=0.1,
                                  frameon=None, metadata=None)
        
        self.update_log('Saved figure ' + fname_out.rsplit('/')[-1])
        
    def clear_plot(self):
        self.swath_ax.clear()
        self.swath_canvas.draw()
        self.x_max = 1
        self.z_max = 1

    def archive_data(self):
        # save (pickle) the detection dictionary for future import to compare performance over time
        archive_name = QtWidgets.QFileDialog.getSaveFileName(self, 'Save data...', os.getenv('HOME'), '.PKL files (*.pkl)')

        if not archive_name[0]:  # abandon if no output location selected
            self.update_log('No archive output file selected.')
            return
        else:  # archive data to selected file
            fname_out = archive_name[0]
            det_archive = self.det # store new dictionary that can be reloaded / expanded in future sessions
            det_archive['model_name'] = self.model_name
            det_archive['ship_name'] = self.ship_name
            det_archive['cruise_name'] = self.cruise_name
            output = open(fname_out, 'wb')
            pickle.dump(det_archive, output)
            output.close()
            self.update_log('Archived data to ' + fname_out.rsplit('/')[-1])

    def load_archive(self):
        # load previously-pickled swath coverage data files and add to plot
        self.add_files('Saved swath coverage data(*.pkl)')  # add .pkl files to qlistwidget
        
        try: # try to make list of unique archive filenames (used as keys) already in det_archive dict 
            fnames_arc = list(set(self.det_archive.keys()))
        except:
            fnames_arc = []      # self.det_archive has not been created yet
            self.det_archive = {}
        
        try:
            fnames_new_pkl = self.get_new_file_list('.pkl', fnames_arc)  # list new .all files not included in det dict
        except:
            self.update_log('Error loading archive files')
            pass
       
        for f in range(len(fnames_new_pkl)):  # load archives, append to self.det_archive
            # try to load archive data and extend the det_archive 
            fname_str = fnames_new_pkl[f].split('/')[-1] # strip just the file string for key in det_archive dict
            det_archive_new = pickle.load(open(fnames_new_pkl[f], 'rb'))
            self.det_archive[fname_str] = det_archive_new
            self.update_log('Loaded archive ' + fname_str)
                
        self.archive_toggle_chk.setChecked(True)
        self.refresh_plot()

    def show_archive(self):
        # plot archive data underneath 'current' swath coverage data 
        if self.archive_toggle_chk.isChecked(): # plot archive data if checked
            try: # need to loop through det_archive dict (possible multiple archives loaded; each key is filename, each value is dict of detections)
                for k in self.det_archive.keys(): 
                    self.plot_coverage(self.det_archive[k], True) # plot det_archive
                    self.swath_canvas.draw()                
            except:
                error_msg = QtWidgets.QMessageBox()
                error_msg.setText('No archive data loaded.  Please load archive data.')
        else:
            self.swath_ax.clear() # clear axes if unchecked, then plot non-archive det data
            
        self.swath_canvas.draw()

#def update_file_progress(self, parse_prog):
#    self.file_pb.setValue(parse_prog) # 0-100 in steps of 10 sent from progress checker in parseEM.parseEMfile

class NewPopup(QtWidgets.QWidget): # new class for additional plots
    def __init__(self):
        QtWidgets.QWidget.__init__(self)

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)

    main = MainWindow()
    main.show()

    sys.exit(app.exec_())