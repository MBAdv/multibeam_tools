# -*- coding: utf-8 -*-
"""
Created on Thu Apr 11 14:45:21 2019

@author: kjerram

Multibeam Echosounder Assessment Toolkit: Swath Accuracy Plotter

"""

# try:
#     from PySide2 import QtWidgets, QtGui
#     from PySide2.QtGui import QDoubleValidator
#     from PySide2.QtCore import Qt, QSize
# except ImportError as e:
#     print(e)
#     from PyQt5 import QtWidgets, QtGui
#     from PyQt5.QtGui import QDoubleValidator
#     from PyQt5.QtCore import Qt, QSize
# import os, sys, datetime, py_compile, readEM, pickle, time
# import numpy as np
# import matplotlib.pyplot as plt
# from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
# from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
# from matplotlib.figure import Figure
# from matplotlib import colors
# from collections import defaultdict
#

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
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import colors
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import multibeam_tools.libs.readEM
import multibeam_tools.libs.parseEMswathwidth

__version__ = "0.0.0"

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__()

        # set up main window
        self.mainWidget = QtWidgets.QWidget(self)
        self.setCentralWidget(self.mainWidget)
#        self.setMinimumSize(QSize(640,480))
        self.setMinimumWidth(1000)
        self.setMinimumHeight(600)
        self.setWindowTitle('MEATPy Swath Accuracy Plotter')
        
        # set up three layouts of main window
        self.set_left_layout()
        self.set_center_layout()
        self.set_right_layout()
        self.set_main_layout()

        # initialize other necessities
        self.filenames = ['']
        self.init_swath_ax()
        
        # set up file control actions
        self.add_file_btn.clicked.connect(lambda: self.add_files('Kongsberg .all(*.all)'))
        self.add_ref_surf_btn.clicked.connect(lambda: self.add_files('Reference surface XYZ(*.xyz)'))
        
        self.rmv_file_btn.clicked.connect(self.remove_files)
        self.clr_file_btn.clicked.connect(self.clear_files)
        self.calc_accuracy_btn.clicked.connect(self.calc_accuracy)        
#        self.swath_plot_btn.clicked.connect(self.refresh_plot) # plot only new, non-archive data
        self.save_plot_btn.clicked.connect(self.save_plot)
#                self.add_file_btn.clicked.connect(lambda: self.add_files('Kongsberg .all(*.all)'))



    def set_left_layout(self):
#        track_canvas_height = 6 # height of track canvas in...unit?
#        track_canvas_width = 6 # width of track canvas in... unit?
        file_button_height = 20 # height of file control button
        file_button_width = 100 # width of file control button
               
        # set left layout with file controls and ship track overview plot
        # add figure instance to plot ship track overview
#        track_figure = Figure(figsize = (track_canvas_width, track_canvas_height))
#        track_canvas = FigureCanvas(track_figure)
#        track_canvas.setSizePolicy(QtWidgets.QSizePolicy.Minimum,
#                                   QtWidgets.QSizePolicy.Minimum)
#        track_toolbar = NavigationToolbar(track_canvas, self)
        
        # set the track plot layout
#        track_layout = QtWidgets.QVBoxLayout()
#        track_layout.addWidget(track_toolbar)
#        track_layout.addWidget(track_canvas)
        
        # add file control buttons and file list
        self.add_file_btn = QtWidgets.QPushButton('Add Crosslines')
        self.add_ref_surf_btn= QtWidgets.QPushButton('Add Ref. Surface')
#        self.load_ref_surf_btn = QtWidgets.QPushButton('Add Ref. Surface')

        self.rmv_file_btn = QtWidgets.QPushButton('Remove Selected')
        self.clr_file_btn = QtWidgets.QPushButton('Clear All Files')
        self.calc_accuracy_btn = QtWidgets.QPushButton('Calc Accuracy')
#        self.swath_plot_btn = QtWidgets.QPushButton('Plot Coverage')
        self.save_plot_btn = QtWidgets.QPushButton('Save Plot')
#        self.clear_plot_btn = QtWidgets.QPushButton('Clear Plot')
#        self.archive_data_btn = QtWidgets.QPushButton('Archive Data')
        
        # format file control buttons
        self.add_file_btn.setFixedSize(file_button_width,file_button_height)
        self.add_ref_surf_btn.setFixedSize(file_button_width, file_button_height)
        self.rmv_file_btn.setFixedSize(file_button_width,file_button_height)
        self.clr_file_btn.setFixedSize(file_button_width,file_button_height)
        self.calc_accuracy_btn.setFixedSize(file_button_width, file_button_height)
#        self.swath_plot_btn.setFixedSize(file_button_width,file_button_height)
        self.save_plot_btn.setFixedSize(file_button_width, file_button_height)
#        self.clear_plot_btn.setFixedSize(file_button_width, file_button_height)
#        self.archive_data_btn.setFixedSize(file_button_width, file_button_height)
        
        # set the file control button layout
        file_btn_layout = QtWidgets.QVBoxLayout()
        file_btn_layout.addWidget(self.add_ref_surf_btn)
        file_btn_layout.addWidget(self.add_file_btn)
        file_btn_layout.addWidget(self.rmv_file_btn)
        file_btn_layout.addWidget(self.clr_file_btn)
        file_btn_layout.addWidget(self.calc_accuracy_btn)
#        file_btn_layout.addWidget(self.swath_plot_btn)
#        file_btn_layout.addWidget(self.archive_data_btn)
#        file_btn_layout.addWidget(self.load_ref_surf_btn)
        file_btn_layout.addWidget(self.save_plot_btn)
#        file_btn_layout.addWidget(self.clear_plot_btn)

        file_btn_layout.addStretch()

        # add table showing selected files
        self.file_list = QtWidgets.QListWidget()
        self.file_list.setSizePolicy(QtWidgets.QSizePolicy.Minimum,
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
        self.log.setSizePolicy(QtWidgets.QSizePolicy.Minimum,
                               QtWidgets.QSizePolicy.Minimum)
        self.log.setStyleSheet("background-color: lightgray")
        self.log.setReadOnly(True)
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
#        self.left_layout.addLayout(track_layout) # remove position parsing for now, track will be separate module
        self.left_layout.addWidget(self.file_gb) # add file list group box
        self.left_layout.addWidget(self.log_gb) # add log group box


    def set_center_layout(self):
        self.swath_canvas_height = 10
        self.swath_canvas_width = 10
        # set center layout with swath coverage plot
        # add figure instance to plot swath coverage versus depth
        self.swath_figure = Figure(figsize = (self.swath_canvas_width, self.swath_canvas_height)) # figure instance for swath plot
        self.swath_canvas = FigureCanvas(self.swath_figure) # canvas widget that displays the figure
        self.swath_canvas.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding,
                                        QtWidgets.QSizePolicy.MinimumExpanding)
        self.swath_toolbar = NavigationToolbar(self.swath_canvas, self) # swath plot toolbar

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
#        self.pt_size_slider_lbl = QtWidgets.QLabel('Point Size')
#        self.pt_size_slider_lbl.setFixedHeight(30)
#        self.pt_size_slider_lbl.setFixedWidth(200)
        self.pt_size_slider = QtWidgets.QSlider(Qt.Horizontal) # set up a slider
        self.pt_size_slider.setMinimum(1)
        self.pt_size_slider.setMaximum(100)
        self.pt_size_slider.setValue(50)
        self.pt_size_slider.setTickInterval(1)
        self.pt_size_slider.setTickPosition(QtWidgets.QSlider.TicksBelow) # set tick marks on bottom of slider
        self.pt_size_slider.setFixedHeight(30)
        self.pt_size_slider.setFixedWidth(200)
        
        # set the point size slider layout
        pt_size_layout = QtWidgets.QVBoxLayout()
#        pt_size_layout.addWidget(self.pt_size_slider_lbl)
        pt_size_layout.addWidget(self.pt_size_slider)
        
        # set point size group box
        pt_size_gb = QtWidgets.QGroupBox('Point Size:')
        pt_size_gb.setLayout(pt_size_layout)
                
        # add point color options (intensity, depth, system, mode, solid color)
#        self.color_cbox_lbl = QtWidgets.QLabel('Color By:')
#        self.color_cbox = QtWidgets.QComboBox() # combo box with color modes
#        self.color_cbox.setFixedSize(80,20)
#        self.color_cbox.addItems(['Depth', 'Backscatter', 'Ping Mode', 'Pulse Form', 'Swath Mode', 'Solid Color']) # color modes
#        self.scbtn = QtWidgets.QPushButton('Select Color') # button to select solid color options
#        self.scbtn.setEnabled(False) # disable color selection until 'Solid Color' is chosen from color_cbox
#        self.scbtn.setFixedSize(80,20)
        
        # set color control layout
#        cbox_layout = QtWidgets.QHBoxLayout()
#        cbox_layout.addWidget(self.color_cbox)
#        cbox_layout.addWidget(self.scbtn)
#        pt_color_layout = QtWidgets.QVBoxLayout()
#        pt_color_layout.addWidget(self.color_cbox_lbl)
#        pt_color_layout.addLayout(cbox_layout)
        
        # add color control group box
#        pt_color_gb = QtWidgets.QGroupBox('Point Color:')
#        pt_color_gb.setLayout(pt_color_layout)
        
        # add check boxes to show archive data, grid lines, WD-multiple lines
#        self.archive_toggle_chk = QtWidgets.QCheckBox('Show archive data')
        self.grid_lines_toggle_chk = QtWidgets.QCheckBox('Show grid lines')
        self.grid_lines_toggle_chk.setChecked(True)        
        self.IHO_lines_toggle_chk = QtWidgets.QCheckBox('Show IHO lines')
#        self.nominal_angle_lines_toggle_chk = QtWidgets.QCheckBox('Show nominal angle lines')
        
        toggle_chk_layout = QtWidgets.QVBoxLayout()
#        toggle_chk_layout.addWidget(self.archive_toggle_chk)
        toggle_chk_layout.addWidget(self.grid_lines_toggle_chk)
        toggle_chk_layout.addWidget(self.IHO_lines_toggle_chk)
#        toggle_chk_layout.addWidget(self.nominal_angle_lines_toggle_chk)
        
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
#        max_layout.addLayout(max_z_layout)
#        max_layout.addLayout(max_x_layout)
        
        plot_lim_gb = QtWidgets.QGroupBox('Plot Limits')
        plot_lim_gb.setLayout(custom_max_layout)
                
        # set the plot control layout
        self.plot_control_layout = QtWidgets.QVBoxLayout()
        self.plot_control_layout.addWidget(system_info_gb)        
        self.plot_control_layout.addWidget(pt_size_gb)
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
            print(fname_ref)
            fnames = ([fname_ref[0]],) + (ftype_filter,) # make a tuple similar to return from getOpenFileNames 

        else:
            fnames = QtWidgets.QFileDialog.getOpenFileNames(self, 'Open crossline file(s)...', os.getenv('HOME'), ftype_filter)
            print(fnames)
            
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

    def remove_files(self): # remove selected files
        self.get_current_file_list()
        selected_files = self.file_list.selectedItems()
        fnames_ref = [fr for fr in self.filenames if '.xyz' in fr]
        fnames_xline = [f for f in self.filenames if '.all' in f]
        
        if len(fnames_xline) + len(fnames_ref) == 0: # all .all and .xyz files have been removed, reset det dicts
            self.xline = {}
#            self.xline_archive = {}
            
        elif not selected_files: # files exist but nothing is selected
            self.update_log('No files selected for removal.')
            return

        else: # remove only the files that have been selected
            for f in selected_files:
                fname = f.text().split('/')[-1]
#                print('working on fname', fname)
                self.file_list.takeItem(self.file_list.row(f))
                self.update_log('Removed ' + fname)

                try: # try to remove detections associated with this file
                    if '.all' in fname:
#                        print('trying to get indices of det matching .all file', f)
                        i = [j for j in range(len(self.xline['fname'])) if self.xline['fname'][j] == fname] # get indices of soundings in det dict with matching filenames
                    
                        for k in self.xline.keys(): # loop through all keys and remove values at these indices
                            print(k)
                            self.xline[k] = np.delete(self.xline[k],i).tolist()
                            
                    elif '.xyz' in fname:
#                        print('trying to get keys of det_archive matching .pkl file', f)
#                        print('len of det_archive before pop attempt is', len(self.xline_archive))
                        print('CLEARING REF SURF BECAUSE THERE WILL ONLY BE ONE LOADED')
                        self.ref_surf = {}
#                        self.xline_archive.pop(fname, None)
#                        print('len of det_archive after pop attempt is', len(self.xline_archive))

                    
                except:  # will fail if detection dict has not been created yet (e.g., if calc_coverage has not been run)
#                    self.update_log('Failed to remove soundings stored from ' + fname)
                    pass
    
        self.update_buttons()
        self.refresh_plot() # refresh with updated (reduced or cleared) detection data
                        
    
    def clear_files(self):
        self.file_list.clear() # clear the file list display
        self.filenames = [] # clear the list of (paths + files) passed to calc_coverage
        self.xline = {} # clear current non-archive detections
        self.ref_surf = {} # clear ref surf data
        self.update_log('Cleared all files')
        self.current_file_lbl.setText('Current File [0/0]:')
        self.calc_pb.setValue(0)
        self.remove_files()
        

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
        self.update_log('Start calculating accuracy!')
        self.parse_ref_surf() # parse the ref surf
        self.parse_crosslines() # parse the crossline(s)
        self.find_nearest_node() # find ref surf node associated with each sounding
        self.calc_dz() # calculate differences from ref surf
        # self.apply_masks() # flag outlier soundings and mask nodes for density, slope
        self.bin_beamwise() # bin the results by beam angle
        self.update_log('Finished calculating accuracy')
        self.update_log('Plotting accuracy results')
        self.refresh_plot()             # refresh the plot

    def parse_ref_surf(self):
        # parse the loaded reference surface .xyz file
        self.ref_surf = {}
        self.get_current_file_list()
        
        fnames_xyz = [f for f in self.filenames if '.xyz' in f]

        if len(fnames_xyz) != 1:
            self.update_log('Please load one reference surface .xyz file')
            pass
        else:
            self.update_log('Parsing reference surface')
            fname_ref = fnames_xyz[0]
            fid_ref = open(fname_ref, 'r')
            e_ref, n_ref, z_ref = [], [], []
            for line in fid_ref:
                temp = line.replace('\n', '').split(",")
                e_ref.append(temp[0]) # easting
                n_ref.append(temp[1]) # northing
                z_ref.append(temp[2]) # up
            
        # convert to arrays with Z positive up
        self.ref_surf['e'] = np.array(e_ref, dtype=np.float32)
        self.ref_surf['n'] = np.array(n_ref, dtype=np.float32)
        self.ref_surf['z'] = np.array(z_ref, dtype=np.float32)
        self.update_log('Imported reference grid:' + fname_ref.split('/')[-1] + ' with ' + str(len(self.ref_surf['z'])) + ' nodes')

        # determine grid size and confirm for user
        ref_dE = np.mean(np.diff(np.sort(np.unique(self.ref_surf['e']))))
        ref_dN = np.mean(np.diff(np.sort(np.unique(self.ref_surf['n']))))
        
        if ref_dE == ref_dN:
            self.ref_cell_size = ref_dE
            self.update_log('Imported reference grid has uniform cell size: ' + str(self.ref_cell_size) + ' m')
        else:
            self.ref_cell_size = np.min([ref_dE, ref_dN])
            self.update_log('WARNING: Uneven grid cell spacing (easting: ' + str(ref_dE) + ', northing: ' + str(ref_dN) + ')')
            self.update_log('Using the minimum spacing detected to identify nearest node for each sounding')

    def parse_crosslines(self):
        # parse crosslines
        try:
            fnames_xline = list(set(self.xline['fname'])) # make list of unique filenames already in det dict
        except:
            fnames_xline = [] # self.xline has not been created yet
            self.xline = {}

        fnames_new_all = self.get_new_file_list('.all', fnames_xline) # list new .all files not included in det dict
        self.update_log('Found ' + str(len(fnames_new_all)) + ' new .all files')
            
        if len(fnames_new_all) > 0: # proceed if at least one .all file that does not exist in det dict
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
                data[f] = readEM.parseEMfile(fnames_new_all[f], parse_list = [78, 80, 82, 88], print_updates = False) # parse RRA78, POS80, RTP82, XYZ88
                self.update_log('Parsed file ' + fname_str)
                self.update_prog(f+1)
            
            self.data = readEM.interpretMode(data, print_updates = False) # interpret modes
            self.data = readEM.convertXYZ(data, print_updates = False) # convert XYZ datagrams to lat, lon, depth
            
            files_OK, EM_params = readEM.verifyMode(self.data) # verify consistent installation and runtime parameters

            if not files_OK: # warn user if inconsistencies detected (perhaps add logic later for sorting into user-selectable lists for archiving and plotting)
                self.update_log('WARNING! CROSSLINES HAVE INCONSISTENT MODEL, S/N, or RUNTIME PARAMETERS')
            
            det_new = readEM.sortAccuracyDetections(data, print_updates = False) # sort new accuracy soundings
            
            if len(self.xline) is 0: # if length of detection dict is 0, store all new detections
                self.xline = det_new
                
            else: # otherwise, append new detections to existing detection dict                
                for key, value in det_new.items(): # loop through the new data and append to existing self.xline
                    self.xline[key].extend(value)
                    
            self.update_log('Finished parsing ' + str(len(fnames_new_all)) + ' new file(s)')
            self.current_file_lbl.setText('Current File [' + str(f+1) + '/' + str(len(fnames_new_all)) + ']: Finished calculating coverage')
                                    
        else: # if no .all files are listed
            self.update_log('No new .all file(s) added.  Please add new .all file(s) and calculate accuracy.')

#        self.xline['filenames'] = fnames  # store updated file list
        self.calc_accuracy_btn.setStyleSheet("background-color: none") # reset the button color to default

    def find_nearest_node(self):
        # find the nearest ref surf node for each sounding
        parse_prog_old = -1

        print('starting nearest node finder')
        start = time.time()

        self.xline['dr_ref'] = []
        self.xline['ref_idx'] = []

        N_soundings = len(self.xline['z'])
        self.update_log('Finding nearest ref. surf. nodes for ' + str(N_soundings) + ' soundings')

        for s in range(N_soundings):
            parse_prog = round(10 * s / N_soundings)
            if parse_prog > parse_prog_old:
                print("%s%%" % (parse_prog * 10), end=" ", flush=True)
                parse_prog_old = parse_prog

            # find index of closest grid cell; implicitly assumes that crossline and ref surf are in same UTM zone
            # alternatively, could be calculated with lat and lon
            dE = np.subtract(self.ref_surf['e'], self.xline['e'][s])  # difference in easting
            dN = np.subtract(self.ref_surf['n'], self.xline['n'][s])  # difference in northing
            dR = np.sqrt(np.add(dE ** 2, dN ** 2))  # radius of sounding from all grid nodes

            if min(dR) <= self.ref_cell_size / 2:  # nearest node must be within half grid cell spacing
                temp_idx = np.argmin(dR)  # find index of closest grid node
                self.xline['dr_ref'].append(dR[temp_idx])  # store horizontal distance to nearest node
                self.xline['ref_idx'].append(temp_idx) # store idx of nearest ref surf node
            else: # otherwise, the sounding is not 'on' the reference surface
                #                print('WARNING: sounding farther than grid cell size from nearest node (', min(dR), ') and will be ignored (NaN for each entry)')
                self.xline['dr_ref'].append(np.nan)
                self.xline['ref_idx'].append(np.nan)

        N_soundings_matched = np.sum(~np.isnan(self.xline['ref_idx']))
        self.update_log('Found ref. surf. nodes for ' + str(N_soundings_matched) + ' of ' + str(N_soundings) + ' soundings')
        end = time.time()
        print('time to get nearest nodes for all soundings by full dR method:', end-start)

    def calc_dz(self):
        # calculate sounding difference from ref surf node (regardless of masking or flagging, handled later)
        self.update_log('Calculating differences from reference surface')

        if np.mean(self.xline['z'])/np.mean(self.ref_surf['z']) < 0: # flip Z sign convention to match ref surf if necessary
            # self.update_log('Changing sign convention to +Z UP to match ref. surf.')
            self.xline['z'] = [-1*s for s in self.xline['z']]
        
        self.xline['dz_ref'] = []
        self.xline['z_ref'] = []
        
        N_soundings = len(self.xline['z'])

        parse_prog_old = -1
        start = time.time()

        for s in range(N_soundings):
            parse_prog = round(10*s/N_soundings)
            if parse_prog > parse_prog_old:
                print("%s%%" % (parse_prog*10), end=" ", flush = True)
                parse_prog_old = parse_prog

            if not np.isnan(self.xline['ref_idx'][s]):  # calculate dz if a nearest node was found
                # calculate Z diff from ref node (Z is +UP, so +dz means the sounding is shallower than the ref surf)
                self.xline['dz_ref'].append(self.xline['z'][s] - self.ref_surf['z'][self.xline['ref_idx'][s]])
                self.xline['z_ref'].append(self.ref_surf['z'][self.xline['ref_idx'][s]]) # store ref surf z

            else:  # no nearest node was found; store NaNs
#                print('WARNING: sounding farther than grid cell size from nearest node (', min(dR), ') and will be ignored (NaN for each entry)')
                self.xline['dz_ref'].append(np.nan)
                self.xline['z_ref'].append(np.nan)

        end = time.time()
        print('time to calculate dz for all soundings:', end-start)
        # calculate dz as percentage of water depth
        # (z_ref is always negative, so *-100 to put in percent with dz and dz_wd sharing same sign,
        # i.e., shallower soundings yield positive dz and dz_wd)
        dz_ref_WD = np.array(-100*np.divide(np.asarray(self.xline['dz_ref']),np.asarray(self.xline['z_ref'])))
        self.xline['dz_ref_WD'] = dz_ref_WD.tolist()
        print('mean horizontal distance from node for meaningful comparisons is',
              np.nanmean(self.xline['dr_ref']))
        print('mean vertical difference from node for meaningful comparisons is',
              np.nanmean(self.xline['dz_ref']))

#        ## METHOD 2: list comprehension ######################################################################################################################################
#        print('starting array / list comprehension method')
#        start = time.time()
#        
#        # calculate differences from each sounding to all nodes --> list of arrays of dE or dN from ref nodes for each sounding
#        dE = [np.subtract(self.ref_surf['e'], self.xline['e'][s]) for s in range(len(self.xline['e']))]
#        dN = [np.subtract(self.ref_surf['n'], self.xline['n'][s]) for s in range(len(self.xline['n']))]
#                
#        # determine nodes that fall within half of the grid cell size of the sounding
#        # there should be 1 node that satisfies this for a sounding that is 'on' the reference surface, 0 otherwise
#        log_within_cell = [np.logical_and(np.abs(dE[s]) < self.ref_cell_size/2, np.abs(dN[s]) < self.ref_cell_size/2) for s in range(len(dE))] # list (N_soundings long) of logical arrays
#        
#        end = time.time()
#        print(end-start, 'seconds so far after log_within_cell')
#        print('finished log within cell, len of log_within_cell is', len(log_within_cell))
#        
#        # for each sounding, determine index of node that satisfies half-grid-cell criteria (empty if none, i.e., sounding is not on ref surface)
#        temp_idx_list = [[i for i,t in enumerate(log_within_cell[s]) if t] for s in range(len(log_within_cell))] # list of (lists of) indices of nearest nodes (empty if not within cell_size/2)
#        end = time.time()
#        print(end-start, 'seconds so far after temp_idx_list')
#        
#        # make temporary list of reference surface node depths corresponding to each sounding (NaN if sounding does not have a node dmatch)
##        temp_dz = [np.nan]*len(log_within_cell)
##        temp_zref = [np.nan]*len(log_within_cell)        
#        self.xline['z_ref'] = [self.ref_surf['z'][temp_idx_list[s][0]] if temp_idx_list[s] else np.nan for s in range(len(temp_idx_list))]
#        end = time.time()
#        print(end-start, 'seconds so far after z_ref assignment')
#        print('len of z_ref including NaNs for non-matches is', len(self.xline['z_ref']))
#        
#        # calculate difference between soundings and corresponding node depths (NaN if sounding does not have a node match)
#        self.xline['dz_ref'] = np.subtract(self.xline['z'], self.xline['z_ref']).tolist()
#        
#        # add NaN radii just for consistency for now...
#        self.xline['dr_ref'] = [np.nan]*len(log_within_cell)
#        
#        end = time.time()
#            
#        print('time to get node for all soundings by list comprehension method:', end-start)
        
#         # METHOD 3: loop assuming single node match if sounding is on ref surf####################################################################################

#        print('starting nearest node finder with alternative dR method')
#        start = time.time()
#
#        for s in range(N_soundings):
##            parse_prog = round(10*s/N_soundings)
##            if parse_prog > parse_prog_old:
##                print("%s%%" % (parse_prog*10), end=" ", flush = True)
##                parse_prog_old = parse_prog
#            
#            dE = np.subtract(self.ref_surf['e'], self.xline['e'][s]) # difference in easting
#            dN = np.subtract(self.ref_surf['n'], self.xline['n'][s]) # difference in northing
#            idx_within_cell = np.logical_and(np.abs(dE) < self.ref_cell_size/2, np.abs(dN) < self.ref_cell_size/2).tolist()
#
#            # in a perfect world, there is only one node that satisfies this constraint if the sounding is 'on' the reference surface
#            # ASSUMES CORRECT CALCULATION OF GRID CELL SIZE!
##            print('found', np.sum(idx_within_cell), 'nodes within half grid cell size in dN and dE directions')
#            
#            if any(idx_within_cell): # if there are any nodes within half the grid cell size in both directions, calculate nearest within that 
#                temp_idx = [i for i,t in enumerate(idx_within_cell) if t]
##                if len(temp_idx) > 1:
##                    print('dude, more than one node satisfied the shizzle! temp_idx is', temp_idx, ', using just the first one!')
##                    temp_idx = temp_idx[0]
#                                
#                self.xline['dz_ref'].append(self.xline['z'][s] - self.ref_surf['z'][temp_idx]) # calculate Z diff from ref node (Z is +UP, so +dz means the sounding is shallower than the reference surface)
#                self.xline['z_ref'].append(self.ref_surf['z'][temp_idx]) # store reference surface depth for this sounding
#                self.xline['dr_ref'].append(np.nan) # store horizontal distance to selected node
#
#            else:
##                print('WARNING: sounding farther than grid cell size from nearest node (', min(dR), ') and will be ignored (NaN for each entry)')
#                self.xline['dz_ref'].append(np.nan)
#                self.xline['z_ref'].append(np.nan)
#                self.xline['dr_ref'].append(np.nan)
#                
#        end = time.time()
#            
#        print('time to get node for all soundings by single node alternative dR method:', end-start)
#
#        print('coming out of dz calcs with a total of', len(self.xline['dz_ref']), 'entries in type', type(self.xline['dz_ref']))

    def bin_beamwise(self):
        # bin by angle, calc mean and std of sounding differences in that angular bin
        self.beam_bin_size = 1 # beam angle bin size (deg)
        self.beam_bin_lim = 75 # max angle (deg)
        
        # convert soundings with meaningful reference surface nodes to array for binning
        self.beam_range = range(-1*self.beam_bin_lim, self.beam_bin_lim, self.beam_bin_size)
        beam_array =    np.asarray(self.xline['beam_angle'])
        dz_array =      np.asarray(self.xline['dz_ref'])
        dz_WD_array =   np.asarray(self.xline['dz_ref_WD'])
        
        self.beam_bin_dz_mean = [] # declare dz mean, std, and sample count 
        self.beam_bin_dz_std = []
        self.beam_bin_dz_N = []
        self.beam_bin_dz_WD_mean = []
        self.beam_bin_dz_WD_std = []
        
        for b in self.beam_range: # loop through all beam bins, calc mean and std dev for dz results within each bin
            idx = (beam_array >= b) & (beam_array < b + self.beam_bin_size) # find indices of beam angles in this bin
            print('Found', str(np.sum(idx)), 'soundings between', str(b), 'and', str(b+self.beam_bin_size), 'deg')
            self.beam_bin_dz_N.append(np.sum(idx))

            if np.sum(idx) > 0: # calc only if at least one sounding on ref surf within this bin
                self.beam_bin_dz_mean.append(np.nanmean(dz_array[idx]))
                self.beam_bin_dz_std.append(np.nanstd(dz_array[idx]))
                self.beam_bin_dz_WD_mean.append(np.nanmean(dz_WD_array[idx])) # this is the simple mean of WD percentages
                self.beam_bin_dz_WD_std.append(np.nanstd(dz_WD_array[idx]))
            else: # store NaN if no dz results are available for this bin
                self.beam_bin_dz_mean.append(np.nan)
                self.beam_bin_dz_std.append(np.nan)
                self.beam_bin_dz_WD_mean.append(np.nan) # this is the simple mean of WD percentages
                self.beam_bin_dz_WD_std.append(np.nan)

    def init_swath_ax(self):  # set initial swath parameters
        # self.swath_ax = self.swath_figure.add_subplot(111) # FROM COVERAGE PLOTTER
        # plt.setp((self.ax1, self.ax2), xticks = np.arange(-1*beam_max, beam_max+beam_spacing, beam_spacing),\
        #          xlim = (-1*(beam_max+beam_spacing), beam_max+beam_spacing))

        self.ax1 = self.swath_figure.add_subplot(211)
        self.ax2 = self.swath_figure.add_subplot(212)
        # self.ax2 = self.swath_figure.add_subplot(212)
        self.x_max = 70
        self.z_max = 3
        self.max_x_tb.setText(str(self.x_max))
        self.max_z_tb.setText(str(self.z_max))
        #        self.update_color_mode()
        self.cruise_name = ''
        # self.N_WD_max = 8
        # self.nominal_angle_line_interval = 15  # degrees between nominal angle lines
        # self.nominal_angle_line_max = 75  # maximum desired nominal angle line
        self.swath_ax_margin = 1.1  # scale axes to multiple of max data in each direction

        self.fsize_label = 10

        self.add_grid_lines()
        self.update_axes()
        self.color = QtGui.QColor(0, 0, 0)  # set default solid color to black for new data
        self.archive_color = QtGui.QColor('darkGray')

        # set formatting params
        self.beam_max = 70
        self.beam_spacing = 10
        self.WD_std_max = 1 # max y range of depth st. dev. plot (top subplot)
        self.WD_std_spacing = 0.1 # y spacing of depth st. dev. plot (top subplot)
        self.WD_max = 3 # max +/- y range of depth bias (raw, mean, +/- 1 sigma, bottom subplot)
        self.WD_spacing = 0.5 # y spacing of depth bias (bottom subplot)
        self.fsize_title = 12
        self.lwidth = 1 # line width


    def plot_accuracy(self, det, is_archive): # plot the parsed detections
        beam_bin_centers = np.asarray([b+self.beam_bin_size/2 for b in self.beam_range]) # generate bin centers for plotting
        beam_bin_dz_WD_std = np.asarray(self.beam_bin_dz_WD_std)


        print('setting up the plt.setp')
        # print('beam_bin_centers is len', len(beam_bin_centers),' with type', type(beam_bin_centers), 'and looks like', beam_bin_centers)
        print('beam_bin_dz_WD_std is len', len(beam_bin_dz_WD_std),' with type', type(beam_bin_dz_WD_std), 'and looks like', beam_bin_dz_WD_std)
        #
        print('self.beam_bin_dz_WD_std are', self.beam_bin_dz_WD_std)
        # make figure and set xticks and xlim for both axes
        # fig, (self.ax1, self.ax2) = plt.subplots(nrows = 2)
        print('trying to plot ax1')
        # plot standard deviation as %WD versus beam angle
        self.ax1.plot(beam_bin_centers, beam_bin_dz_WD_std, '-', linewidth = self.lwidth, color = 'b') # beamwise bin mean + st. dev.
        print('made it past plot command')
        print('1')
        self.ax1.grid(True)
        print('2')
        plt.sca(self.ax1)
        print('3')
        plt.yticks(np.arange(0, self.WD_std_max+self.WD_std_spacing, self.WD_std_spacing))

        # plt.ylim(0, self.WD_std_max)
        # plt.xlabel('RX Beam Angle (deg)', fontsize = self.fsize_label)
        # plt.ylabel('Depth Bias Std. Dev. (% Water Depth)', fontsize = self.fsize_label)
        # plt.show()
        #
        # print('trying to plot ax2')
        # plot the raw differences, mean, and +/- 1 sigma as %WD versus beam angle        
        # self.ax2.scatter(self.xline['beam_angle'], self.xline['dz_ref_WD'], marker = 'o', color = '0.80', s = 1) # raw differences from reference grid, small gray points
        # self.ax2.plot(beam_bin_centers, self.beam_bin_dz_WD_mean, '-', linewidth = lwidth, color = 'r') # beamwise bin mean difference
        # self.ax2.plot(beam_bin_centers, np.add(self.beam_bin_dz_WD_mean, self.beam_bin_dz_WD_std), '-', linewidth = lwidth, color = 'b') # beamwise bin mean + st. dev.
        # self.ax2.plot(beam_bin_centers, np.subtract(self.beam_bin_dz_WD_mean, self.beam_bin_dz_WD_std), '-', linewidth = lwidth, color = 'b') # beamwise bin mean - st. dev.
        # self.ax2.grid(True)
        # plt.sca(self.ax2)
        # plt.yticks(np.arange(-1*WD_max, WD_max+WD_spacing, WD_spacing))
        # plt.ylim(-1*(WD_max+WD_spacing), WD_max+WD_spacing)
        # plt.xlabel('RX Beam Angle (deg)', fontsize = self.fsize_label)
        # plt.ylabel('Depth Bias Mean (% Water Depth)', fontsize = self.fsize_label)
        # plt.ylabel('Difference from Reference Grid (%WD)', fontsize = self.fsize_label)
        # plt.show()


           ############## FROM PLOTEMACCURACY.PY #######################
        # make figure and set xticks and xlim for both axes
        # fig, (ax1, ax2) = plt.subplots(nrows=2)
        # plt.setp((ax1, ax2), xticks=np.arange(-1 * beam_max, beam_max + beam_spacing, beam_spacing), \
        #          xlim=(-1 * (beam_max + beam_spacing), beam_max + beam_spacing))

        # plot standard deviation as %WD versus beam angle
        # ax1.plot(beam_bin_centers, beam_bin_dZ_WD_std, '-', linewidth=lwidth, color='b')  # beamwise bin mean + st. dev.
        # ax1.grid(True)
        # plt.sca(ax1)
        # plt.yticks(np.arange(0, WD_std_max + WD_std_spacing, WD_std_spacing))
        # plt.ylim(0, WD_std_max)
        # plt.xlabel('RX Beam Angle (deg)', fontsize=self.fsize_label)
        # plt.ylabel('Depth Bias Std. Dev. (% Water Depth)', fontsize=self.fsize_label)
        #
        # # plot the raw differences, mean, and +/- 1 sigma as %WD versus beam angle
        # ax2.scatter(beam_angle, beam_dZ_WD, marker='o', color='0.80',
        #             s=1)  # raw differences from reference grid, small gray points
        # ax2.plot(beam_bin_centers, beam_bin_dZ_WD_mean, '-', linewidth=lwidth,
        #          color='r')  # beamwise bin mean difference
        # ax2.plot(beam_bin_centers, np.add(beam_bin_dZ_WD_mean, beam_bin_dZ_WD_std), '-', linewidth=lwidth,
        #          color='b')  # beamwise bin mean + st. dev.
        # ax2.plot(beam_bin_centers, np.subtract(beam_bin_dZ_WD_mean, beam_bin_dZ_WD_std), '-', linewidth=lwidth,
        #          color='b')  # beamwise bin mean - st. dev.
        # ax2.grid(True)
        # plt.sca(ax2)
        # plt.yticks(np.arange(-1 * WD_max, WD_max + WD_spacing, WD_spacing))
        # plt.ylim(-1 * (WD_max + WD_spacing), WD_max + WD_spacing)
        # plt.xlabel('RX Beam Angle (deg)', fontsize=self.fsize_label)
        # plt.ylabel('Depth Bias Mean (% Water Depth)', fontsize=self.fsize_label)
        # # plt.ylabel('Difference from Reference Grid (%WD)', fontsize = self.fsize_label)
        # plt.show()

        ##############################################################################################


        print('trying swath_canvas.draw')
        self.swath_canvas.draw() # refresh swath canvas in main window
        print('survived swath_canvas.draw')
        


    def update_log(self, entry): # update the activity log
        self.log.append(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' ' + entry)
        QtWidgets.QApplication.processEvents()
        
        
    def update_prog(self, total_prog):
        self.calc_pb.setValue(total_prog)
        QtWidgets.QApplication.processEvents()


    def refresh_plot(self): # update swath plot with new data and options
#        self.init_axes()
        self.clear_plot()
        # self.update_color_mode() # initialize self.cmode if cmode not changed previously
        self.update_plot_limits()
#        self.show_archive() # plot archive data with new plot control values
        
        try:
            self.plot_accuracy(self.xline, False) # plot new data if available
        except:
            pass
#            self.update_log('No .all coverage data available.  Please load files and calculate coverage.')

        print('made it back to refresh plot after plot_accuracy)')
        self.add_grid_lines() # add grid lines
        print('back in refresh plot, survived add_grid_lines')

#        self.add_IHO_lines() # add water depth-multiple lines over coverage
#        self.add_nominal_angle_lines() # add nominal swath angle lines over coverage
        print('in refresh plot, calling update_axes')
        self.update_axes() # update axes to fit all loaded data
        print('survived update_axes')

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
        print('in update axes, starting update_system info')
        self.update_system_info()
        print('in update axes, starting update_plot_limits')
        self.update_plot_limits()
        print('survived update_plot_limits')
        # adjust x and y axes to fit max data
        # plt.sca(self.ax1)
        print('trying to set ylim with self.z_max at', self.z_max)
        self.ax1.set_ylim(-1*self.z_max, self.z_max) # set y axis
        print('trying to set xlim with self.x_max at', self.x_max)
        self.ax1.set_xlim(-1*self.x_max, self.x_max) # set x axis

        # self.ax2.set_ylim(-1*self.z_max, self.z_max) # set depth axis to 0 and 1.1 times max(z)
        # self.ax2.set_xlim(-1*self.x_max, self.x_max) # set x axis to +/-1.1 times max(abs(x))

        print('updating the title in update_axes')
        title_str = 'Swath Accuracy vs. Beam Angle\n' + self.model_name + ' - ' + self.ship_name + ' - ' + self.cruise_name
        self.ax1.set(xlabel='Beam Angle (deg)', ylabel='Depth Bias Std. Dev (% Water Depth)', title=title_str)

        # print('now inverting the yaxis')
        # self.ax1.invert_yaxis() # invert the y axis
        print('trying plt.show()')
        plt.show() # need show() after axis update!
        # plt.sca(self.ax1)
        # plt.ylabel('Depth Bias Mean (% Water Depth)', fontsize = self.fsize_label)

        # self.ax2.set(xlabel='Beam Angle (\deg)', ylabel='Depth (m)', title=title_str)
        # self.ax2.invert_yaxis() # invert the y axis


        # plt.show() # need show() after axis update!
        print('trying swath_canvas.draw in update_axes')
        self.swath_canvas.draw()
    
    def update_plot_limits(self):
        if self.custom_max_chk.isChecked(): # use custom plot limits if checked
            self.max_gb.setEnabled(True)
            print('in update_plot_limits the tb entry type is', type(self.max_x_tb.text()), 'with value', self.max_x_tb.text())
            self.x_max = int(self.max_x_tb.text())
            self.z_max = int(self.max_z_tb.text())
        else:
            self.max_gb.setEnabled(False)
    
        
    def add_grid_lines(self):
        if self.grid_lines_toggle_chk.isChecked():  # turn on grid lines
            self.ax1.grid()
            self.ax1.minorticks_on()
            self.ax1.grid(which = 'both', linestyle = '-', linewidth = '0.5', color = 'black')
            # self.ax2.grid()
            # self.ax2.minorticks_on()
            # self.ax2.grid(which = 'both', linestyle = '-', linewidth = '0.5', color = 'black')

        else:  # turn off the grid lines
            self.ax1.grid(False)
            self.ax1.minorticks_off()
            # self.ax2.grid(False)
            # self.ax2.minorticks_off()
        #
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
        # self.ax2.clear()
        self.swath_canvas.draw()
        # self.x_max = 1
        # self.z_max = 1
        
        
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
#        if self.WD_lines_toggle_chk.isChecked(): # plot WD lines if checked
#            try:
#                # loop through multiples of WD (-port,+stbd) and plot grid lines with text 
#                for n in range(1,self.N_WD_max+1):   # add 1 for indexing, do not include 0X WD
#                    for ps in [-1,1]:           # port/stbd multiplier
#                        self.swath_ax.plot([0, ps*n*self.swath_ax_margin*self.z_max/2],\
#                                           [0,self.swath_ax_margin*self.z_max], 'k', linewidth = 1)
#                        x_mag = 0.9*n*self.z_max/2 # set magnitude of text locations to 90% of line end
#                        y_mag = 0.9*self.z_max
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





