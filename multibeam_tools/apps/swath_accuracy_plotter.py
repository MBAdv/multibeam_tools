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
import datetime
import os
import sys
import pyproj
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import colors
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import multibeam_tools.libs.readEM
import multibeam_tools.libs.parseEMswathwidth
from scipy.interpolate import griddata
from multibeam_tools.libs.gui_fun import *


__version__ = "0.0.3"


# just testing branch switching in Git


class MainWindow(QtWidgets.QMainWindow):

    media_path = os.path.join(os.path.dirname(__file__), "media")

    def __init__(self, parent=None):
        super(MainWindow, self).__init__()

        # set up main window
        self.mainWidget = QtWidgets.QWidget(self)
        self.setCentralWidget(self.mainWidget)
#        self.setMinimumSize(QSize(640,480))
        self.setMinimumWidth(1000)
        self.setMinimumHeight(600)
        self.setWindowTitle('Swath Accuracy Plotter v.%s' % __version__)
        self.setWindowIcon(QtGui.QIcon(os.path.join(self.media_path, "icon.png")))

        if os.name == 'nt':  # necessary to explicitly set taskbar icon
            import ctypes
            current_app_id = 'MAC.AccuracyPlotter.' + __version__  # arbitrary string
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(current_app_id)

        # initialize other necessities
        self.filenames = ['']
        self.unit_mode = '%WD'  # default plot as % Water Depth; option to toggle alternative meters

        # set up three layouts of main window
        self.set_left_layout()
        self.set_center_layout()
        self.set_right_layout()
        self.set_main_layout()
        self.init_swath_ax()

        # set up file control actions
        self.add_file_btn.clicked.connect(lambda: self.add_files('Kongsberg(*.all *.kmall)'))
        self.add_ref_surf_btn.clicked.connect(lambda: self.add_files('Reference surface XYZ(*.xyz)'))
        self.rmv_file_btn.clicked.connect(self.remove_files)
        self.clr_file_btn.clicked.connect(self.clear_files)
        self.calc_accuracy_btn.clicked.connect(self.calc_accuracy)        
        self.save_plot_btn.clicked.connect(self.save_plot)

        # set up plot control actions
        self.custom_info_chk.stateChanged.connect(self.refresh_plot)
        self.model_cbox.activated.connect(self.refresh_plot)
        self.ship_tb.returnPressed.connect(self.refresh_plot)
        self.cruise_tb.returnPressed.connect(self.refresh_plot)
        self.grid_lines_toggle_chk.stateChanged.connect(self.refresh_plot)
        self.IHO_lines_toggle_chk.stateChanged.connect(self.refresh_plot)
        self.custom_max_chk.stateChanged.connect(self.refresh_plot)
        self.max_beam_angle_tb.returnPressed.connect(self.refresh_plot)
        self.angle_spacing_tb.returnPressed.connect(self.refresh_plot)
        self.max_bias_tb.returnPressed.connect(self.refresh_plot)
        self.max_std_tb.returnPressed.connect(self.refresh_plot)

        # add max angle limits
        # self.custom_angle_chk.stateChanged.connect(self.refresh_plot)
        # self.max_angle_tb.returnPressed.connect(self.refresh_plot)
        # self.min_angle_tb.returnPressed.connect(self.refresh_plot)

        # add

    def set_left_layout(self):
        btnh = 20  # height of file control button
        btnw = 100  # width of file control button

        # add file control buttons and file list
        self.add_file_btn = QtWidgets.QPushButton('Add Crosslines')
        self.add_ref_surf_btn= QtWidgets.QPushButton('Add Ref. Surface')

        # add combobox for reference surface UTM zone
        # self.ref_proj_lbl.resize(80, 20)
        # self.ref_proj_cbox = QtWidgets.QComboBox() # combo box with color modes
        # self.ref_proj_cbox.setFixedSize(70, 20)
        proj_list = [str(i) + 'N' for i in range(1,61)]
        proj_list.extend([str(i) + 'S' for i in range(1,61)])
        EPSG_list = [str(i) for i in range(32601, 32661)] # list of EPSG codes for WGS84 UTM1-60N
        EPSG_list.extend([str(i) for i in range(32701, 32761)]) # add EPSG codes for WGS84 UTM1-60S
        self.proj_dict = dict(zip(proj_list, EPSG_list)) # save for lookup during xline UTM zone conversion with pyproj
        # ref_proj_lbl = Label('Proj.:', 80, 20, 'ref_proj_lbl', self)
        # self.ref_proj_cbox.addItems(proj_list) # color modes
        self.ref_proj_cbox = ComboBox(proj_list, 70, 20, 'ref_proj_cbox', 'Select the ref. surf. projection', self)
        ref_utm_layout = BoxLayout([Label('Proj.:', 80, 20, 'ref_proj_lbl', (Qt.AlignRight | Qt.AlignVCenter), self),
                                    self.ref_proj_cbox], 'h', self)
        # ref_utm_layout = QtWidgets.QHBoxLayout()
        # ref_utm_layout.addWidget(self.ref_proj_lbl)
        # ref_utm_layout.addWidget(self.ref_proj_cbox)
        

        # self.rmv_file_btn = QtWidgets.QPushButton('Remove Selected')
        self.rmv_file_btn = PushButton('Remove Selected', btnw, btnh, 'rmv_file_btn', 'Remove selected files', self)
        # self.clr_file_btn = QtWidgets.QPushButton('Clear All Files')
        self.clr_file_btn = PushButton('Remove All Files', btnw, btnh, 'clr_file_btn', 'Remove all files', self)
        # self.calc_accuracy_btn = QtWidgets.QPushButton('Calc Accuracy')
        # self.save_plot_btn = QtWidgets.QPushButton('Save Plot')
        self.calc_accuracy_btn = PushButton('Calc Accuracy', btnw, btnh, 'calc_accuracy_btn',
                                            'Calculate accuracy from loaded files', self)
        self.save_plot_btn = PushButton('Save Plot', btnw, btnh, 'save_plot_btn', 'Save current plot', self)
        
        # format file control buttons
        # self.add_file_btn.setFixedSize(btnw,btnh)
        # self.add_ref_surf_btn.setFixedSize(btnw, btnh)
        # self.rmv_file_btn.setFixedSize(btnw,btnh)
        # self.clr_file_btn.setFixedSize(btnw,btnh)
        # self.calc_accuracy_btn.setFixedSize(btnw, btnh)
        # self.save_plot_btn.setFixedSize(btnw, btnh)
        
        # set the file control button layout
        # file_btn_layout = QtWidgets.QVBoxLayout()
        # file_btn_layout.addWidget(self.add_ref_surf_btn)
        # file_btn_layout.addLayout(ref_utm_layout)
        # file_btn_layout.addWidget(self.add_file_btn)
        # file_btn_layout.addWidget(self.rmv_file_btn)
        # file_btn_layout.addWidget(self.clr_file_btn)
        # file_btn_layout.addWidget(self.calc_accuracy_btn)
        # file_btn_layout.addWidget(self.save_plot_btn)
        file_btn_layout = BoxLayout([self.add_ref_surf_btn, ref_utm_layout, self.add_file_btn, self.rmv_file_btn,
                                     self.clr_file_btn, self.calc_accuracy_btn, self.save_plot_btn], 'v', self)
        file_btn_layout.addStretch()

        # add table showing selected files
        self.file_list = QtWidgets.QListWidget()
        self.file_list.setSizePolicy(QtWidgets.QSizePolicy.Minimum,
                                     QtWidgets.QSizePolicy.Minimum)

        # set layout of file list and controls
        # self.file_layout = QtWidgets.QHBoxLayout()
        # self.file_layout.addWidget(self.file_list)
        # self.file_layout.addLayout(file_btn_layout)
        self.file_layout = BoxLayout([self.file_list, file_btn_layout], 'h', self)
        
        # set file list group box
        self.file_gb = QtWidgets.QGroupBox('Sources')
        self.file_gb.setLayout(self.file_layout)
        
        # # add activity log widget
        # self.log = QtWidgets.QTextEdit()
        # self.log.setSizePolicy(QtWidgets.QSizePolicy.Minimum,
        #                        QtWidgets.QSizePolicy.Minimum)
        # self.log.setStyleSheet("background-color: lightgray")
        # self.log.setReadOnly(True)
        self.log = TextEdit()
        self.update_log('*** New swath accuracy processing log ***')
        
        # add progress bar for total file list
        self.current_file_lbl = QtWidgets.QLabel('Current File:')
        self.calc_pb_lbl = QtWidgets.QLabel('Total Progress:')
        self.calc_pb = QtWidgets.QProgressBar()
        self.calc_pb.setGeometry(0,0,200,30)
        self.calc_pb.setMaximum(100) # this will update with number of files
        self.calc_pb.setValue(0)
        
        # set progress bar layout
        self.calc_pb_layout = QtWidgets.QHBoxLayout()
        self.calc_pb_layout.addWidget(self.calc_pb_lbl)
        self.calc_pb_layout.addWidget(self.calc_pb)
        
        self.prog_layout = QtWidgets.QVBoxLayout()
        self.prog_layout.addWidget(self.current_file_lbl)
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
        self.left_layout.addWidget(self.file_gb) # add file list group box
        self.left_layout.addWidget(self.log_gb) # add log group box

    def set_center_layout(self):  # set center layout with swath coverage plot
        # add figure instance
        self.swath_canvas_height = 10
        self.swath_canvas_width = 10
        self.swath_figure = Figure(figsize = (self.swath_canvas_width, self.swath_canvas_height)) # figure instance for swath plot
        self.swath_canvas = FigureCanvas(self.swath_figure) # canvas widget that displays the figure
        self.swath_canvas.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding,
                                        QtWidgets.QSizePolicy.MinimumExpanding)
        self.swath_toolbar = NavigationToolbar(self.swath_canvas, self) # swath plot toolbar

        # initialize max x, z limits
        self.x_max = 0.0
        self.y_max = 0.0

        # set the swath layout
        self.swath_layout = QtWidgets.QVBoxLayout()
        self.swath_layout.addWidget(self.swath_toolbar)
        self.swath_layout.addWidget(self.swath_canvas)
    
    def set_right_layout(self):  # set right layout with swath plot controls
        # add check boxes to show archive data, grid lines, WD-multiple lines
        self.grid_lines_toggle_chk = QtWidgets.QCheckBox('Show grid lines')
        self.grid_lines_toggle_chk.setChecked(True)        
        self.IHO_lines_toggle_chk = QtWidgets.QCheckBox('Show IHO lines')

        toggle_chk_layout = QtWidgets.QVBoxLayout()
        toggle_chk_layout.addWidget(self.grid_lines_toggle_chk)
        # toggle_chk_layout.addWidget(self.IHO_lines_toggle_chk)

        # add checkbox groupbox
        toggle_gb = QtWidgets.QGroupBox('Plot Options')
        toggle_gb.setLayout(toggle_chk_layout)

        # add text boxes for system, ship, cruise
        self.model_tb_lbl = QtWidgets.QLabel('Model:')
        self.model_tb_lbl.resize(100, 20)
        self.model_cbox = QtWidgets.QComboBox() # combo box with color modes
        self.model_cbox.setFixedSize(100, 20)
        self.model_cbox.addItems(['EM 2040', 'EM 302', 'EM 304', 'EM 710', 'EM 712', 'EM 122', 'EM 124']) # color modes
#        self.model_tb = QtWidgets.QLineEdit()
#        self.model_tb.setFixedSize(100,20)
        
        model_info_layout = QtWidgets.QHBoxLayout()
        model_info_layout.addWidget(self.model_tb_lbl)
#        model_tb_layout.addWidget(self.model_tb)
        model_info_layout.addWidget(self.model_cbox)
        
        self.ship_tb_lbl = QtWidgets.QLabel('Ship Name:')
        self.ship_tb_lbl.resize(100, 20)
        self.ship_tb = QtWidgets.QLineEdit()
        self.ship_tb.setFixedSize(100, 20)
        self.ship_tb.setText('R/V Unsinkable II')
        ship_info_layout = QtWidgets.QHBoxLayout()
        ship_info_layout.addWidget(self.ship_tb_lbl)
#        ship_tb_layout.addStretch()
        ship_info_layout.addWidget(self.ship_tb)

        self.cruise_tb_lbl = QtWidgets.QLabel('Cruise Name:')
        self.cruise_tb_lbl.resize(100, 20)
        self.cruise_tb = QtWidgets.QLineEdit()
        self.cruise_tb.setFixedSize(100, 20)
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
        self.max_beam_angle_lbl = QtWidgets.QLabel('Max beam angle (deg):')
        self.max_beam_angle_lbl.resize(110, 20)
        self.max_beam_angle_tb = QtWidgets.QLineEdit()
        self.max_beam_angle_tb.setFixedSize(50, 20)
        self.max_beam_angle_tb.setText('')
        self.max_beam_angle_tb.setValidator(QDoubleValidator(0, 90, 2))

        self.angle_spacing_lbl = QtWidgets.QLabel('Angle spacing (deg):')
        self.angle_spacing_lbl.resize(110, 20)
        self.angle_spacing_tb = QtWidgets.QLineEdit()
        self.angle_spacing_tb.setFixedSize(50, 20)
        self.angle_spacing_tb.setText('')
        self.angle_spacing_tb.setValidator(QDoubleValidator(0, 90, 2))

        self.max_bias_lbl = QtWidgets.QLabel('Max bias (' + self.unit_mode + '):')
        self.max_bias_lbl.resize(110, 20)
        self.max_bias_tb = QtWidgets.QLineEdit()
        self.max_bias_tb.setFixedSize(50, 20)
        self.max_bias_tb.setText('')
        self.max_bias_tb.setValidator(QDoubleValidator(0, 100, 2))

        self.max_std_lbl = QtWidgets.QLabel('Max st. dev. (' + self.unit_mode + '):')
        self.max_std_lbl.resize(110, 20)
        self.max_std_tb = QtWidgets.QLineEdit()
        self.max_std_tb.setFixedSize(50, 20)
        self.max_std_tb.setText('')
        self.max_std_tb.setValidator(QDoubleValidator(0, 100, 2))

        max_beam_angle_layout = QtWidgets.QHBoxLayout()
        max_beam_angle_layout.addWidget(self.max_beam_angle_lbl)
        max_beam_angle_layout.addWidget(self.max_beam_angle_tb)

        angle_spacing_layout = QtWidgets.QHBoxLayout()
        angle_spacing_layout.addWidget(self.angle_spacing_lbl)
        angle_spacing_layout.addWidget(self.angle_spacing_tb)
        
        max_bias_layout = QtWidgets.QHBoxLayout()
        max_bias_layout.addWidget(self.max_bias_lbl)
        max_bias_layout.addWidget(self.max_bias_tb)

        max_std_layout = QtWidgets.QHBoxLayout()
        max_std_layout.addWidget(self.max_std_lbl)
        max_std_layout.addWidget(self.max_std_tb)
        
        max_layout = QtWidgets.QVBoxLayout()
        max_layout.addLayout(max_beam_angle_layout)
        max_layout.addLayout(angle_spacing_layout)
        max_layout.addLayout(max_std_layout)
        max_layout.addLayout(max_bias_layout)

        self.max_gb = QtWidgets.QGroupBox()
        self.max_gb.setLayout(max_layout)
        self.max_gb.setEnabled(False)
        
        # add checkbox and set layout
        self.custom_max_chk = QtWidgets.QCheckBox('Use custom plot limits')
        custom_max_layout = QtWidgets.QVBoxLayout()
        custom_max_layout.addWidget(self.custom_max_chk)
        custom_max_layout.addWidget(self.max_gb)
#        max_layout.addLayout(max_z_layout)
#        max_layout.addLayout(max_x_layout)
        
        plot_lim_gb = QtWidgets.QGroupBox('Plot Limits')
        plot_lim_gb.setLayout(custom_max_layout)
                
        # set the plot control layout
        self.plot_control_layout = QtWidgets.QVBoxLayout()
        self.plot_control_layout.addWidget(system_info_gb)        
        # self.plot_control_layout.addWidget(pt_size_gb)
#        self.plot_control_layout.addWidget(pt_color_gb)
        self.plot_control_layout.addWidget(toggle_gb)
        self.plot_control_layout.addWidget(plot_lim_gb)

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

    def add_files(self, ftype_filter): # select files with desired type, add to list box
        if '.xyz' in ftype_filter: # pick only one file for reference surface
            fname_ref = QtWidgets.QFileDialog.getOpenFileName(self, 'Open reference surface file...', os.getenv('HOME'), ftype_filter)
            fnames = ([fname_ref[0]],) + (ftype_filter,) # make a tuple similar to return from getOpenFileNames

        else:
            fnames = QtWidgets.QFileDialog.getOpenFileNames(self, 'Open crossline file(s)...', os.getenv('HOME'), ftype_filter)

        self.get_current_file_list() # get updated file list and add selected files only if not already listed
        
        fnames_new = [fn for fn in fnames[0] if fn not in self.filenames]
        fnames_skip = [fs for fs in fnames[0] if fs in self.filenames]

        if len(fnames_skip) > 0: # skip any files already added, update log
            self.update_log('Skipping ' + str(len(fnames_skip)) + ' file(s) already added')
        
        for f in range(len(fnames_new)): # add the new files only
            self.file_list.addItem(fnames_new[f])
            self.update_log('Added ' + fnames_new[f].split('/')[-1])
         
        self.update_buttons()

    def update_buttons(self):
        # enable or disable file selection and calc_accuracy buttons depending on loaded files
        self.get_current_file_list()
        fnames_ref = [fr for fr in self.filenames if '.xyz' in fr]
        fnames_xline = [fx for fx in self.filenames if '.all' in fx]
        
        # print('existing reference file names are', fnames_ref)
        # print('existing crossline file names are', fnames_xline)
            
        self.add_ref_surf_btn.setEnabled(len(fnames_ref) == 0)        # enable ref surf selection only if none loaded 
        
        # enable calc_accuracy button only if one ref surf and at least one crossline are loaded
        if len(fnames_ref) == 1 and len(fnames_xline) > 0:
            self.calc_accuracy_btn.setEnabled(True)
            self.calc_accuracy_btn.setStyleSheet("background-color: yellow")
        else:
            self.calc_accuracy_btn.setEnabled(False)
            self.calc_accuracy_btn.setStyleSheet("background-color: none")

    def remove_files(self):  # remove selected files only
        self.get_current_file_list()
        selected_files = self.file_list.selectedItems()
        fnames_ref = [fr for fr in self.filenames if '.xyz' in fr]
        fnames_xline = [f for f in self.filenames if '.all' in f]

        print('in remove_files, fnames_xline is', fnames_xline)
        
        if len(fnames_xline) + len(fnames_ref) == 0: # all .all and .xyz files have been removed, reset det dicts
        # if len(fnames_xline) == 0:  # if all .all files have been removed, reset det dicts
            self.xline = {}
            # self.bin_beamwise()  # call bin_beamwise with empty xline results to clear plots
#            self.xline_archive = {}
            
        elif not selected_files: # files exist but nothing is selected
            self.update_log('No files selected for removal.')
            return

        else:  # remove only the files that have been selected
            for f in selected_files:
                fname = f.text().split('/')[-1]
#                print('working on fname', fname)
                self.file_list.takeItem(self.file_list.row(f))
                self.update_log('Removed ' + fname)

                try: # try to remove detections associated with this file
                    if '.all' in fname:
                        # print('trying to get indices of det matching .all file', f)
                        # get indices of soundings in det dict with matching filenames
                        i = [j for j in range(len(self.xline['fname'])) if self.xline['fname'][j] == fname]
                    
                        for k in self.xline.keys(): # loop through all keys and remove values at these indices
                            print(k)
                            self.xline[k] = np.delete(self.xline[k],i).tolist()
                            
                    elif '.xyz' in fname:
#                        print('trying to get keys of det_archive matching .pkl file', f)
#                        print('len of det_archive before pop attempt is', len(self.xline_archive))
                        print('CLEARING REF SURF BECAUSE THERE WILL ONLY BE ONE LOADED')
                        self.ref_surf = {}
                        self.add_ref_surf_btn.setEnabled(True)  # enable button to add replacement reference surface
#                        self.xline_archive.pop(fname, None)
#                        print('len of det_archive after pop attempt is', len(self.xline_archive))

                except:  # will fail if detection dict has not been created yet (e.g., if calc_coverage has not been run)
#                    self.update_log('Failed to remove soundings stored from ' + fname)
                    pass

        # call bin_beamwise() to update results if the single .xyz ref surface or any of the .all files are removed
        self.bin_beamwise()
        # self.update_buttons()  # test skipping update_buttons if results are whittled down and replotted automatically
        self.refresh_plot()  # refresh with updated (reduced or cleared) detection data

    def clear_files(self):
        self.file_list.clear() # clear the file list display
        self.filenames = [] # clear the list of (paths + files) passed to calc_coverage
        self.xline = {} # clear current non-archive detections
        self.ref_surf = {} # clear ref surf data
        self.bin_beamwise()  # call bin_beamwise with empty self.xline to reset all other binned results
        # self.beam_bin_dz_mean = []
        # self.beam_bin_dz_N
        self.remove_files()  # remove files and refresh plot
        self.update_log('Cleared all files')
        self.current_file_lbl.setText('Current File [0/0]:')
        self.calc_pb.setValue(0)
        self.add_ref_surf_btn.setEnabled(True)

    def get_current_file_list(self, ftype = ''): # get current list of files in qlistwidget
        list_items = []
        for f in range(self.file_list.count()):
            list_items.append(self.file_list.item(f))
        
        self.filenames = [f.text() for f in list_items] # convert to text

    def get_new_file_list(self, fext = '', flist_old = []):
        # determine list of new files with file extension fext that do not exist in flist_old
        # flist_old may contain paths as well as file names; compare only file names
        self.get_current_file_list()
#        print('in get_new_file_list, just got the new current file list:', self.filenames)
#        fnames_all = [f for f in self.filenames if '.all' in f]
        fnames_ext = [f for f in self.filenames if fext in f] # file names (with paths) that match the extension
        fnames_old = [f.split('/')[-1] for f in flist_old] # file names only (no paths) from flist_old 
        fnames_new = [fn for fn in fnames_ext if fn.split('/')[-1] not in fnames_old] # check if file name (without path) exists in fnames_old
        return(fnames_new) # return the fnames_new (with paths)

    def calc_accuracy(self):
        # calculate accuracy of soundings from at least one crossline over exactly one reference surface
        self.update_log('Starting accuracy calculations')
        self.parse_ref_surf() # parse the ref surf
        # self.apply_masks() # FUTURE: flag outlier soundings and mask nodes for density, slope
        self.parse_crosslines() # parse the crossline(s)
        self.convert_crossline_utm() # convert crossline X,Y to UTM zone of reference surface
        self.calc_dz_from_ref_interp() # interpolate ref surf onto sounding positions, take difference
        # self.find_nearest_node() # find nearest ref node for each sounding -- SUPERCEDED BY calc_dz_from_ref_interp
        # self.calc_dz() # calculate differences from ref surf -- SUPERCEDED BY calc_dz_from_ref_interp
        self.bin_beamwise() # bin the results by beam angle
        self.update_log('Finished calculating accuracy')
        self.update_log('Plotting accuracy results')
        self.refresh_plot()             # refresh the plot

    def parse_ref_surf(self):
        # parse the loaded reference surface .xyz file
        # ref grid is assumed UTM projection with meters east, north, depth (+Z up), e.g., export from processing
        self.ref_surf = {}
        self.get_current_file_list()
        fnames_xyz = [f for f in self.filenames if '.xyz' in f]  # get all .xyz file names

        if len(fnames_xyz) != 1:  # warn user to add exactly one ref grid
            self.update_log('Please add one reference grid .xyz file in a UTM projection')
            pass
        else:
            fname_ref = fnames_xyz[0]
            fid_ref = open(fname_ref, 'r')
            e_ref, n_ref, z_ref = [], [], []
            for line in fid_ref:
                temp = line.replace('\n', '').split(",")
                e_ref.append(temp[0]) # easting
                n_ref.append(temp[1]) # northing
                z_ref.append(temp[2]) # up
            
        # convert to arrays with Z positive up; vertical datum for ref grid and crosslines is assumed same for now
        self.ref_surf['e'] = np.array(e_ref, dtype=np.float32)
        self.ref_surf['n'] = np.array(n_ref, dtype=np.float32)
        self.ref_surf['z'] = -1*np.abs(np.array(z_ref, dtype=np.float32)) # ensure grid is +Z UP (neg. depths)
        self.ref_surf['utm_zone'] = self.ref_proj_cbox.currentText()
        self.update_log('Imported ref grid: ' + fname_ref.split('/')[-1] + ' with ' + str(len(self.ref_surf['z'])) + ' nodes')
        self.update_log('Ref grid is assigned UTM zone ' + self.ref_surf['utm_zone'])

        # determine grid size and confirm for user
        ref_dE = np.mean(np.diff(np.sort(np.unique(self.ref_surf['e']))))
        ref_dN = np.mean(np.diff(np.sort(np.unique(self.ref_surf['n']))))
        
        if ref_dE == ref_dN:
            self.ref_cell_size = ref_dE
            self.update_log('Imported ref grid has uniform cell size: ' + str(self.ref_cell_size) + ' m')
        else:
            self.ref_cell_size = np.min([ref_dE, ref_dN])
            self.update_log('WARNING: Uneven grid cell spacing (easting: ' + str(ref_dE) + ', northing: ' + str(ref_dN) + ')')

    def parse_crosslines(self):
        # parse crosslines
        self.update_log('Parsing accuracy crosslines')
        try:
            fnames_xline = list(set(self.xline['fname'])) # make list of unique filenames already in detection dict
        except:
            fnames_xline = [] # self.xline has not been created yet; initialize this and self.xline detection dict
            self.xline = {}

        fnames_new_all = self.get_new_file_list('.all', fnames_xline) # list new .all files not included in det dict
        self.update_log('Found ' + str(len(fnames_new_all)) + ' new crossline .all files')
            
        if len(fnames_new_all) > 0: # proceed if there is at least one .all file that does not exist in det dict
            self.update_log('Calculating accuracy from ' + str(len(fnames_new_all)) + ' new file(s)')
            QtWidgets.QApplication.processEvents() # try processing and redrawing the GUI to make progress bar update
            data = {}
            
            # update progress bar and log
            self.calc_pb.setValue(0) # reset progress bar to 0 and max to number of files
            self.calc_pb.setMaximum(len(fnames_new_all))
            
            for f in range(len(fnames_new_all)):         # read previously unparsed files
                fname_str = fnames_new_all[f].rsplit('/')[-1]
                self.current_file_lbl.setText('Parsing new file [' + str(f+1) + '/' + str(len(fnames_new_all)) + ']: ' + fname_str)
                QtWidgets.QApplication.processEvents()
                data[f] = multibeam_tools.libs.readEM.parseEMfile(fnames_new_all[f], parse_list = [78, 80, 82, 88], print_updates = False) # parse RRA78, POS80, RTP82, XYZ88
                self.update_log('Parsed file ' + fname_str)
                self.update_prog(f+1)
            
            self.data = multibeam_tools.libs.readEM.interpretMode(data, print_updates = False) # interpret modes
            self.data = multibeam_tools.libs.readEM.convertXYZ(data, print_updates = False) # convert XYZ datagrams to lat, lon, depth
            
            files_OK, EM_params = multibeam_tools.libs.readEM.verifyMode(self.data) # verify consistent installation and runtime parameters

            if not files_OK: # warn user if inconsistencies detected (perhaps add logic later for sorting into user-selectable lists for archiving and plotting)
                self.update_log('WARNING! CROSSLINES HAVE INCONSISTENT MODEL, S/N, or RUNTIME PARAMETERS')
            
            det_new = multibeam_tools.libs.readEM.sortAccuracyDetections(data, print_updates = False)  # sort new accuracy soundings
            z_pos_up = -1*np.asarray(det_new['z'])  # z is returned as positive down; flip sign for later use
            det_new['z'] = z_pos_up.tolist()

            if len(self.xline) is 0: # if detection dict is empty, store all new detections
                self.xline = det_new
                
            else: # otherwise, append new detections to existing detection dict                
                for key, value in det_new.items(): # loop through the new data and append to existing self.xline
                    self.xline[key].extend(value)
                    
            self.update_log('Finished parsing ' + str(len(fnames_new_all)) + ' new file(s)')
            self.current_file_lbl.setText('Current File [' + str(f+1) + '/' + str(len(fnames_new_all)) + ']: Finished parsing crosslines')
                                    
        else: # if no .all files are listed
            self.update_log('No new crossline .all file(s) added')

#        self.xline['filenames'] = fnames  # store updated file list
        self.calc_accuracy_btn.setStyleSheet("background-color: none") # reset the button color to default

    def convert_crossline_utm(self):
        # if necessary, convert crossline X,Y to UTM zone of reference surface
        self.update_log('Checking UTM zones of ref grid and crossline(s)')
        ref_utm = self.ref_surf['utm_zone']

        # format xline UTM zone for comparison with ref_utm and use with pyproj; replace zone letter with S if southern
        # hemisphere (UTM zone letter C-M) or N if northern hemisphere (else)
        xline_utm = [utm_str.replace(" ", "") for utm_str in self.xline['utm_zone']]
        xline_utm = [utm_str[:-1] + 'S' if utm_str[-1] <= 'M' else utm_str[:-1] + 'N' for utm_str in xline_utm]
        self.xline['utm_zone'] = xline_utm  # replace with new format

        print(ref_utm)
        print(xline_utm[0:10])
        print('detected xline utm zones:', set(xline_utm))
        # get list of xline utm zones that do not match ref surf utm zone
        xline_utm_list = [u for u in set(xline_utm) if u != ref_utm]

        print('non-matching utm zones:', xline_utm_list)

        if len(xline_utm_list) > 0:  # transform soundings from non-matching xline utm zone(s) into ref utm zone
            self.update_log('Found crossline soundings in different UTM zone')

            # define projection of reference surface and numpy array for easier indexing
            p2 = pyproj.Proj(proj='utm', zone=ref_utm, ellps='WGS84')
            xline_e = np.asarray(self.xline['e'])
            xline_n = np.asarray(self.xline['n'])
            N_soundings = len(self.xline['utm_zone'])
            print('N_soundings is originally', N_soundings)

            for u in xline_utm_list:  # for each non-matching xline utm zone, convert those soundings to ref utm
                print('working on non-matching utm zone', u)
                p1 = pyproj.Proj(proj = 'utm', zone = u, ellps='WGS84')  # define proj of xline soundings

                print('first ten xline_utm are:', xline_utm[0:10])

                idx = [s for s in range(N_soundings) if xline_utm[s] == u]  # get indices of soundings with this zone
                print('length of idx is', str(len(idx)))

                print('first ten xline_utm for idx matches are:', [xline_utm[i] for i in idx[0:10]])

                (xline_e_new, xline_n_new) = pyproj.transform(p1, p2, xline_e[idx], xline_n[idx])  # transform
                xline_e[idx] = xline_e_new
                xline_n[idx] = xline_n_new

                self.update_log('Transformed ' + str(len(idx)) + ' soundings (out of '
                                + str(N_soundings) + ') from ' + u + ' to ' + ref_utm)

                print('fixed the eastings to:', xline_e_new)

            # reassign the final coordinates
            self.xline['e'] = xline_e.tolist()
            self.xline['n'] = xline_n.tolist()
            self.xline['utm_zone'] = [ref_utm]*N_soundings

            print('new xline_easting is', self.xline['e'][0:30])
            print('new xline_northing is', self.xline['n'][0:30])
            print('new utm_zone is', self.xline['utm_zone'][0:30])

########################################################################################################################
    ### FUTURE: ADD SLOPE AND SOUNDING DENSITY MASKING FOR REFERENCE SURFACE
########################################################################################################################

    def calc_dz_from_ref_interp(self):
        # calculate the difference of each sounding from the reference grid (interpolated onto sounding X, Y position)
        self.update_log('Calculating ref grid depths at crossline sounding positions')
        print('N ref_surf nodes =', len(self.ref_surf['e']))
        print('N xline soundings =', len(self.xline['e']))

        # interpolate the reference grid (linearly) onto the sounding positions
        # note: griddata will interpolate only within the convex hull of the input grid coordinates
        # xline sounding positions outside the convex hull (i.e., off the grid) will return NaN
        self.xline['z_ref_interp'] = griddata((self.ref_surf['e'], self.ref_surf['n']),
                                              self.ref_surf['z'],
                                              (self.xline['e'], self.xline['n']),
                                              method='linear')

        print('z_ref_interp looks like', self.xline['z_ref_interp'][0:30])
        print('xline z after flip looks like', self.xline['z'][0:30])

        N_ref_surf_interp = np.sum(~np.isnan(self.xline['z_ref_interp']))  # count non-Nan interpolated value
        self.update_log('Found ' + str(N_ref_surf_interp) + ' crossline soundings on ref grid')

        # calculate dz for xline soundings with non-NaN interpolated reference grid depths
        # note that xline['z'] is positive down as returned from parser; flip sign for differencing from ref surf
        self.update_log('Calculating crossline differences from ref grid')
        self.xline['dz_ref'] = np.subtract(self.xline['z'], self.xline['z_ref_interp'])

        print('xline dz_ref looks like', self.xline['dz_ref'][0:30])

        # store dz as percentage of water depth, with positive dz_ref_wd meaning shallower crossline soundings
        # to retain intuitive plotting appearance, with shallower soundings above deeper soundings
        # e.g., if xline z = -98 and z_ref_interp = -100, then dz_ref = +2; dz_ref_wd should be positive; division of
        # positive bias (up) by reference depth (always negative) yields negative, so must be flipped in sign for plot
        dz_ref_wd = np.array(-1*100*np.divide(np.asarray(self.xline['dz_ref']), np.asarray(self.xline['z_ref_interp'])))
        self.xline['dz_ref_wd'] = dz_ref_wd.tolist()

        print('xline dz_ref_wd looks like', self.xline['dz_ref_wd'][0:30])

        self.ref_surf['z_mean'] = np.nanmean(self.xline['z_ref_interp'])  # mean of ref grid interp values used

    def bin_beamwise(self):
        self.update_log('Binning soundings by angle')
        # bin by angle, calc mean and std of sounding differences in that angular bin
        self.beam_bin_size = 1  # beam angle bin size (deg)
        self.beam_bin_lim = 75  # max angle (deg)

        self.beam_bin_dz_mean = [] # declare dz mean, std, and sample count
        self.beam_bin_dz_std = []
        self.beam_bin_dz_N = []
        self.beam_bin_dz_wd_mean = []
        self.beam_bin_dz_wd_std = []
        self.beam_range = range(-1*self.beam_bin_lim, self.beam_bin_lim, self.beam_bin_size)

        # if crossline data AND reference surface are available, convert soundings with meaningful reference surface
        # nodes to array for binning; otherwise, continue to refresh plot with empty results
        if 'beam_angle' in self.xline and 'z' in self.ref_surf:
            beam_array = np.asarray(self.xline['beam_angle'])
            dz_array = np.asarray(self.xline['dz_ref'])
            dz_wd_array = np.asarray(self.xline['dz_ref_wd'])

            for b in self.beam_range: # loop through all beam bins, calc mean and std for dz results within each bin
                idx = (beam_array >= b) & (beam_array < b + self.beam_bin_size) # find indices of angles in this bin
                print('Found', str(np.sum(idx)), 'soundings between', str(b), 'and', str(b+self.beam_bin_size), 'deg')
                self.beam_bin_dz_N.append(np.sum(idx))

                if np.sum(idx) > 0:  # calc only if at least one sounding on ref surf within this bin
                    self.beam_bin_dz_mean.append(np.nanmean(dz_array[idx]))
                    self.beam_bin_dz_std.append(np.nanstd(dz_array[idx]))
                    self.beam_bin_dz_wd_mean.append(np.nanmean(dz_wd_array[idx]))  # simple mean of WD percentages
                    self.beam_bin_dz_wd_std.append(np.nanstd(dz_wd_array[idx]))
                else: # store NaN if no dz results are available for this bin
                    self.beam_bin_dz_mean.append(np.nan)
                    self.beam_bin_dz_std.append(np.nan)
                    self.beam_bin_dz_wd_mean.append(np.nan)  # this is the simple mean of WD percentages
                    self.beam_bin_dz_wd_std.append(np.nan)

    def init_swath_ax(self):  # set initial swath parameters
        self.ax1 = self.swath_figure.add_subplot(211)
        self.ax2 = self.swath_figure.add_subplot(212)

        self.x_max_default = 75
        self.x_spacing_default = 15
        self.y_max_std_default = 0.5  # max y range of depth st. dev. plot (top subplot)
        self.y_max_bias_default = 1  # max +/- y range of depth bias (raw, mean, +/- 1 sigma, bottom subplot)

        self.x_max_custom = self.x_max_default # store future custom entries
        self.x_spacing_custom = self.x_spacing_default
        self.y_max_bias_custom = self.y_max_bias_default
        self.y_max_std_custom = self.y_max_std_default

        self.max_beam_angle_tb.setText(str(self.x_max_default))
        self.angle_spacing_tb.setText(str(self.x_spacing_default))
        self.max_bias_tb.setText(str(self.y_max_bias_default))
        self.max_std_tb.setText(str(self.y_max_std_default))

        self.cruise_name = ''
        self.swath_ax_margin = 1.1  # scale axes to multiple of max data in each direction
        self.fsize_title = 12
        self.fsize_label = 10
        self.lwidth = 1  # line width
        self.add_grid_lines()
        self.update_axes()
        self.color = QtGui.QColor(0, 0, 0)  # set default solid color to black for new data
        self.archive_color = QtGui.QColor('darkGray')

        # self.swath_ax = self.swath_figure.add_subplot(111) # FROM COVERAGE PLOTTER
        # plt.setp((self.ax1, self.ax2), xticks = np.arange(-1*self.beam_max, self.beam_max + self.angle_spacing, self.angle_spacing),\
        #          xlim = (-1*(self.beam_max + self.angle_spacing), self.beam_max + self.angle_spacing))

    def plot_accuracy(self, det, is_archive):  # plot the accuracy results
        beam_bin_centers = np.asarray([b+self.beam_bin_size/2 for b in self.beam_range])  # generate bin centers for plotting
        beam_bin_dz_wd_std = np.asarray(self.beam_bin_dz_wd_std)

        # plot standard deviation as %WD versus beam angle
        self.ax1.plot(beam_bin_centers, beam_bin_dz_wd_std, '-', linewidth=self.lwidth, color='b')  # beamwise bin mean + st. dev.
        self.ax1.grid(True)

        # plot the raw differences, mean, and +/- 1 sigma as %wd versus beam angle
        self.ax2.scatter(self.xline['beam_angle'], self.xline['dz_ref_wd'], marker='o', color='0.75', s=0.5)  # raw differences from reference grid, small gray points
        self.ax2.plot(beam_bin_centers, self.beam_bin_dz_wd_mean, '-', linewidth=self.lwidth, color='r')  # beamwise bin mean difference
        self.ax2.plot(beam_bin_centers, np.add(self.beam_bin_dz_wd_mean, self.beam_bin_dz_wd_std), '-', linewidth=self.lwidth, color='b')  # beamwise bin mean + st. dev.
        self.ax2.plot(beam_bin_centers, np.subtract(self.beam_bin_dz_wd_mean, self.beam_bin_dz_wd_std), '-', linewidth=self.lwidth, color='b')  # beamwise bin mean - st. dev.
        self.ax2.grid(True)

    def update_log(self, entry):  # update the activity log
        self.log.append(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' ' + entry)
        QtWidgets.QApplication.processEvents()

    def update_prog(self, total_prog):  # update progress bar
        self.calc_pb.setValue(total_prog)
        QtWidgets.QApplication.processEvents()

    def refresh_plot(self): # update swath plot with new data and options
        self.clear_plot()
        self.update_plot_limits()

        try:
            self.plot_accuracy(self.xline, False)  # plot new data if available
        except:
            self.update_log('No .all coverage data available.  Please load files and calculate coverage.')
            pass

        self.add_grid_lines()  # add grid lines
        self.update_axes()  # update axes to fit all loaded data
        self.swath_canvas.draw()

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
#                self.ship_name = self.det['filenames'][0] # try getting ship name from detection dict filenames
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
        # update top subplot axes (std. dev. as %WD)
        self.update_system_info()
        self.update_plot_limits()
        print('survived update_plot_limits')
        # adjust x and y axes to fit max data
        # plt.sca(self.ax1)

        # set x axis limits and ticks for both plots
        plt.setp((self.ax1, self.ax2), xticks=np.arange(-1*self.x_max, self.x_max + self.x_spacing, self.x_spacing),\
                 xlim=(-1*self.x_max, self.x_max))

        # set y axis limits for both plots
        self.ax1.set_ylim(0, self.y_max_std)  # set y axis for std (0 to max, top plot)
        self.ax2.set_ylim(-1*self.y_max_bias, self.y_max_bias)  # set y axis for total bias+std (bottom plot)

        print('updating the title and axes in update_axes')
        title_str = 'Swath Accuracy vs. Beam Angle\n' + self.model_name + ' - ' + self.ship_name + ' - ' + self.cruise_name
        self.ax1.set(xlabel='Beam Angle (deg)', ylabel='Depth Bias Std. Dev (% Water Depth)', title=title_str)
        self.ax2.set(xlabel='Beam Angle (deg)', ylabel='Depth Bias (% Water Depth)')
        self.swath_canvas.draw()  # try update the axes labels and title before failing
        print('trying plt.show()')
        try:
            plt.show()  # need show() after update; failed until matplotlib.use('qt5agg') added at start
        except:
            print('in update_axes, failed plt.show()')
        # plt.sca(self.ax1)
        # plt.ylabel('Depth Bias Mean (% Water Depth)', fontsize=self.fsize_label)
        # plt.show() # need show() after axis update!
        # self.swath_canvas.draw()
        print('survived update_axes')
        print('*******')
    
    def update_plot_limits(self):  # update plot limits if custom limits are selected

        if self.custom_max_chk.isChecked():  # use custom plot limits if checked, store custom values in text boxes
            self.max_gb.setEnabled(True)
            self.x_max_custom = float(self.max_beam_angle_tb.text())
            self.x_spacing_custom = float(self.angle_spacing_tb.text())
            self.y_max_std_custom = float(self.max_std_tb.text())
            self.y_max_bias_custom = float(self.max_bias_tb.text())

            # assign to current plot limits
            self.x_max = self.x_max_custom
            self.x_spacing = self.x_spacing_custom
            self.y_max_std = self.y_max_std_custom
            self.y_max_bias = self.y_max_bias_custom

        else:  # revert to default limits from the data if unchecked, but keep the custom numbers in text boxes
            self.max_gb.setEnabled(False)
            self.x_max = self.x_max_default
            self.x_spacing = self.x_spacing_default
            self.y_max_std = self.y_max_std_default
            self.y_max_bias = self.y_max_bias_default

            # set text boxes to latest custom values for easier toggling between custom/default limits
            self.max_beam_angle_tb.setText(str(float(self.x_max_custom)))
            self.angle_spacing_tb.setText(str(float(self.x_spacing_custom)))
            self.max_bias_tb.setText(str(float(self.y_max_bias_custom)))
            self.max_std_tb.setText(str(float(self.y_max_std_custom)))
        
    def add_grid_lines(self):
        if self.grid_lines_toggle_chk.isChecked():  # turn on grid lines
            self.ax1.grid()
            self.ax1.minorticks_on()
            self.ax1.grid(which='both', linestyle='-', linewidth='0.5', color='black')
            self.ax2.grid()
            self.ax2.minorticks_on()
            self.ax2.grid(which='both', linestyle='-', linewidth='0.5', color='black')

        else:  # turn off the grid lines
            self.ax1.grid(False)
            self.ax1.minorticks_off()
            self.ax2.grid(False)
            self.ax2.minorticks_off()

        self.swath_canvas.draw()  # redraw swath canvas with grid lines
            
    def save_plot(self):
        # option 1: try to save a .PNG of the swath plot
        plot_path = QtWidgets.QFileDialog.getSaveFileName(self, 'Save plot as...', os.getenv('HOME'), ".PNG file (*.PNG);; .JPG file (*.JPG);; .TIF file (*.TIF)")
        fname_out = plot_path[0]

        self.swath_figure.savefig(fname_out,
                                  dpi=600, facecolor='w', edgecolor='k',
                                  orientation='portrait', papertype=None, format=None,
                                  transparent=False, bbox_inches=None, pad_inches=0.1,
                                  frameon=None, metadata=None)
        
        self.update_log('Saved figure ' + fname_out.rsplit('/')[-1])
        
    def clear_plot(self):
#        print('clear_plot')
        self.ax1.clear()
        self.ax2.clear()
        self.swath_canvas.draw()
        # self.x_max = 1
        # self.y_max = 1

class NewPopup(QtWidgets.QWidget): # new class for additional plots
    def __init__(self):
        QtWidgets.QWidget.__init__(self)
        
        
if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)

    main = MainWindow()
    main.show()

    sys.exit(app.exec_())
        
            
#    def add_IHO_lines(self):
#        # add lines indicating IHO orders
#        if self.wd_lines_toggle_chk.isChecked(): # plot wd lines if checked
#            try:
#                # loop through multiples of wd (-port,+stbd) and plot grid lines with text
#                for n in range(1,self.N_max_wd+1):   # add 1 for indexing, do not include 0X wd
#                    for ps in [-1,1]:           # port/stbd multiplier
#                        self.swath_ax.plot([0, ps*n*self.swath_ax_margin*self.y_max/2],\
#                                           [0,self.swath_ax_margin*self.y_max], 'k', linewidth = 1)
#                        x_mag = 0.9*n*self.y_max/2 # set magnitude of text locations to 90% of line end
#                        y_mag = 0.9*self.y_max
#                        
#                        # keep text locations on the plot
#                        if x_mag > 0.9*self.x_max:
#                            x_mag = 0.9*self.x_max
#                            y_mag = 2*x_mag/n # scale y location with limited x location
#                            
#                        self.swath_ax.text(x_mag*ps, y_mag, str(n) + 'X',
#                                verticalalignment = 'center', horizontalalignment = 'center',
#                                bbox=dict(facecolor='white', edgecolor = 'none', alpha=1, pad = 0.0))    
#                self.swath_canvas.draw()
#            
#            except:
#                error_msg = QtWidgets.QMessageBox()
#                error_msg.setText('Failure plotting the WD lines...')
                


## import and parse .all files for accuracy crosslines
## import XYZ of reference surface (exported from processing software in WGS84 --> lon, lat, meters +down, sounding count)
## mask reference surface cells for slope and sounding density
## for each sounding, find nearest reference surface node and calculate difference in m and as %WD
## for each ref surf node, calculate mean, st dev of associated xline soundings
## flag xline soundings beyond threshold (e.g., beyond 3 st dev from node)
## group unflagged soundings into RX beamwidth angle bins and calculate mean and st. dev of differences (m and %WD) from ref. surf. within each bin
## plot bin-wise mean and st. dev. of (unflagged) differences from ref. surf. across the swath (m and %WD) 





