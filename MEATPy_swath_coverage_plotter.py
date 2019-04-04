# -*- coding: utf-8 -*-
"""
Created on Fri Feb 15 14:33:30 2019

@author: kjerram

Multibeam Echosounder Assessment Toolkit: Swath Coverage Plotter

"""
import os, sys, struct, datetime, math, py_compile, readEM, pickle
from PyQt5 import QtWidgets, QtGui
from PyQt5.QtCore import Qt, QSize
import numpy as np
import matplotlib, matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib import colors
from collections import defaultdict


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__()

        # set up main window
        self.mainWidget = QtWidgets.QWidget(self)
        self.setCentralWidget(self.mainWidget)
#        self.setMinimumSize(QSize(640,480))
        self.setMinimumWidth(1000)
        self.setMinimumHeight(600)
        self.setWindowTitle('MEATPy Swath Coverage Plotter')
        
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
        self.rmv_file_btn.clicked.connect(self.remove_files)
        self.clr_file_btn.clicked.connect(self.clear_files)
        self.calc_coverage_btn.clicked.connect(self.calc_coverage)        
#        self.swath_plot_btn.clicked.connect(self.refresh_plot) # plot only new, non-archive data
        self.save_plot_btn.clicked.connect(self.save_plot)
#        self.clear_plot_btn.clicked.connect(self.clear_plot)
        self.archive_data_btn.clicked.connect(self.archive_data)
        self.load_archive_btn.clicked.connect(self.load_archive)
    
        # set up swath plot control actions
        self.pt_size_slider.valueChanged.connect(self.refresh_plot)
        self.color_cbox.activated.connect(self.refresh_plot)
        self.scbtn.clicked.connect(self.update_solid_color)
#        self.archive_toggle_chk.stateChanged.connect(self.show_archive)
        self.archive_toggle_chk.stateChanged.connect(self.refresh_plot)
        self.WD_lines_toggle_chk.stateChanged.connect(self.refresh_plot)
        self.nominal_angle_lines_toggle_chk.stateChanged.connect(self.refresh_plot)
        self.grid_lines_toggle_chk.stateChanged.connect(self.refresh_plot)
        self.custom_info_chk.stateChanged.connect(self.refresh_plot)
#        self.model_tb.returnPressed.connect(self.refresh_plot)
        self.model_cbox.activated.connect(self.refresh_plot)
        self.ship_tb.returnPressed.connect(self.refresh_plot)
        self.cruise_tb.returnPressed.connect(self.refresh_plot)


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
        self.add_file_btn = QtWidgets.QPushButton('Add Files')
        self.rmv_file_btn = QtWidgets.QPushButton('Remove Selected')
        self.clr_file_btn = QtWidgets.QPushButton('Clear All Files')
        self.calc_coverage_btn = QtWidgets.QPushButton('Calc Coverage')
#        self.swath_plot_btn = QtWidgets.QPushButton('Plot Coverage')
        self.save_plot_btn = QtWidgets.QPushButton('Save Plot')
#        self.clear_plot_btn = QtWidgets.QPushButton('Clear Plot')
        self.archive_data_btn = QtWidgets.QPushButton('Archive Data')
        self.load_archive_btn = QtWidgets.QPushButton('Load Archive')
        
        # format file control buttons
        self.add_file_btn.setFixedSize(file_button_width,file_button_height)
        self.rmv_file_btn.setFixedSize(file_button_width,file_button_height)
        self.clr_file_btn.setFixedSize(file_button_width,file_button_height)
        self.calc_coverage_btn.setFixedSize(file_button_width, file_button_height)
#        self.swath_plot_btn.setFixedSize(file_button_width,file_button_height)
        self.save_plot_btn.setFixedSize(file_button_width, file_button_height)
#        self.clear_plot_btn.setFixedSize(file_button_width, file_button_height)
        self.archive_data_btn.setFixedSize(file_button_width, file_button_height)
        self.load_archive_btn.setFixedSize(file_button_width, file_button_height)
        
        # set the file control button layout
        file_btn_layout = QtWidgets.QVBoxLayout()
        file_btn_layout.addWidget(self.add_file_btn)
        file_btn_layout.addWidget(self.rmv_file_btn)
        file_btn_layout.addWidget(self.clr_file_btn)
        file_btn_layout.addWidget(self.calc_coverage_btn)
#        file_btn_layout.addWidget(self.swath_plot_btn)
        file_btn_layout.addWidget(self.archive_data_btn)
        file_btn_layout.addWidget(self.load_archive_btn)
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
        self.log.setReadOnly(True)
        self.update_log('*** New swath coverage processing log ***')
        
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
        self.color_cbox = QtWidgets.QComboBox() # combo box with color modes
        self.color_cbox.setFixedSize(80,20)
        self.color_cbox.addItems(['Depth', 'Backscatter', 'Ping Mode', 'Pulse Form', 'Swath Mode', 'Solid Color']) # color modes
        self.scbtn = QtWidgets.QPushButton('Select Color') # button to select solid color options
        self.scbtn.setFixedSize(80,20)
        
        # set color control layout
        cbox_layout = QtWidgets.QHBoxLayout()
        cbox_layout.addWidget(self.color_cbox)
        cbox_layout.addWidget(self.scbtn)
        pt_color_layout = QtWidgets.QVBoxLayout()
#        pt_color_layout.addWidget(self.color_cbox_lbl)
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
        
        toggle_chk_layout = QtWidgets.QVBoxLayout()
        toggle_chk_layout.addWidget(self.archive_toggle_chk)
        toggle_chk_layout.addWidget(self.grid_lines_toggle_chk)
        toggle_chk_layout.addWidget(self.WD_lines_toggle_chk)
        toggle_chk_layout.addWidget(self.nominal_angle_lines_toggle_chk)
        
        # add checkbox groupbox
        toggle_gb = QtWidgets.QGroupBox('Plot Options')
        toggle_gb.setLayout(toggle_chk_layout)
        
        # add text boxes for system, ship, cruise
        self.model_tb_lbl = QtWidgets.QLabel('Model:')
        self.model_tb_lbl.resize(100,20)
        self.model_cbox = QtWidgets.QComboBox() # combo box with color modes
        self.model_cbox.setFixedSize(100,20)
        self.model_cbox.addItems(['EM 2040', 'EM 302', 'EM 304', 'EM 710', 'EM 712', 'EM 122', 'EM 124']) # color modes
#        self.model_tb = QtWidgets.QLineEdit()
#        self.model_tb.setFixedSize(100,20)
        
        model_info_layout = QtWidgets.QHBoxLayout()
        model_info_layout.addWidget(self.model_tb_lbl)
#        model_tb_layout.addWidget(self.model_tb)
        model_info_layout.addWidget(self.model_cbox)
        
        self.ship_tb_lbl = QtWidgets.QLabel('Ship Name:')
        self.ship_tb_lbl.resize(100,20)
        self.ship_tb = QtWidgets.QLineEdit()
        self.ship_tb.setFixedSize(100,20)
        self.ship_tb.setText('R/V Unsinkable II')
        ship_info_layout = QtWidgets.QHBoxLayout()
        ship_info_layout.addWidget(self.ship_tb_lbl)
#        ship_tb_layout.addStretch()
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
        
        # set the plot control layout
        self.plot_control_layout = QtWidgets.QVBoxLayout()
        self.plot_control_layout.addWidget(system_info_gb)        
        self.plot_control_layout.addWidget(pt_size_gb)
        self.plot_control_layout.addWidget(pt_color_gb)
        self.plot_control_layout.addWidget(toggle_gb)

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
        fnames = QtWidgets.QFileDialog.getOpenFileNames(self, 'Open files...', os.getenv('HOME'), ftype_filter)
        self.get_current_file_list() # get updated file list and add selected files only if not already listed
        fnames_new = [fn for fn in fnames[0] if fn not in self.filenames]
        fnames_skip = [fs for fs in fnames[0] if fs in self.filenames]

        if len(fnames_skip) > 0: # skip any files already added, update log
            self.update_log('Skipping ' + str(len(fnames_skip)) + ' file(s) already added')
        
        for f in range(len(fnames_new)): # add the new files only
            self.file_list.addItem(fnames_new[f])
            self.update_log('Added ' + fnames_new[f].split('/')[-1])
        
        if len(fnames_new) > 0 and ftype_filter == 'Kongsberg .all(*.all)':
            self.calc_coverage_btn.setStyleSheet("background-color: red") # set calculate_coverage button red if new .all files loaded
        
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
                print('working on fname', fname)
                self.file_list.takeItem(self.file_list.row(f))
                self.update_log('Removed ' + fname)

                try: # try to remove detections associated with this file
                    if '.all' in fname:
                        print('trying to get indices of det matching .all file', f)
                        i = [j for j in range(len(self.det['fname'])) if self.det['fname'][j] == fname] # get indices of soundings in det dict with matching filenames
                    
                        for k in self.det.keys(): # loop through all keys and remove values at these indices
                            print(k)
                            self.det[k] = np.delete(self.det[k],i).tolist()
                    elif '.pkl' in fname:
                        print('trying to get keys of det_archive matching .pkl file', f)
                        print('len of det_archive before pop attempt is', len(self.det_archive))
                        self.det_archive.pop(fname, None)
                        print('len of det_archive after pop attempt is', len(self.det_archive))

                    
                except:  # will fail if detection dict has not been created yet (e.g., if calc_coverage has not been run)
                    self.update_log('Failed to remove ' + fname)
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
        

    def get_current_file_list(self, ftype = ''): # get current list of files in qlistwidget
        list_items = []
        for f in range(self.file_list.count()):
            list_items.append(self.file_list.item(f))
        
        self.filenames = [f.text() for f in list_items] # convert to text

    def get_new_file_list(self, fext = '', flist_old = []):
        # determine list of new files with file extension fext that do not exist in flist_old
        # flist_old may contain paths as well as file names; compare only file names
        self.get_current_file_list()
        print('in get_new_file_list, just got the new current file list:', self.filenames)
#        fnames_all = [f for f in self.filenames if '.all' in f]
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
            
        if len(fnames_new_all) > 0: # proceed if at least one .all file
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
    #        	data[f] = readEM.parseEMfile(fnames[f], parse_list = [80,88], print_updates = False) # parse XYZ88 and position datagrams
                data[f] = readEM.parseEMfile(fnames_new_all[f], parse_list = [88], print_updates = False, parse_outermost_only = True) # parse XYZ88, outermost only to save time
                self.update_log('Parsed file ' + fname_str)
                self.update_prog(f+1)
            
            self.data = readEM.interpretMode(data, print_updates = False) # interpret modes
            det_new = readEM.sortDetections(data, print_updates = False) # sort new detections (includes filename for each for later reference)
                        
            if len(self.det) is 0: # if length of detection dict is 0, store all new detections
                self.det = det_new
                
            else: # otherwise, append new detections to existing detection dict                
                for key, value in det_new.items(): # loop through the new data and append to existing self.det
                    self.det[key].extend(value)
            
            self.update_log('Finished calculating coverage from ' + str(len(fnames_new_all)) + ' new file(s)')
            self.current_file_lbl.setText('Current File [' + str(f+1) + '/' + str(len(fnames_new_all)) + ']: Finished calculating coverage')
    
            # convert position --> add position parsing / conversion / plotting as a separate option
    #        dt, lat, lon = readEM.convertEMpos(data) # convert and sort parsed EM position data
    #        # store ship track
    #        self.det['ship_track_lat'] = lat
    #        self.det['ship_track_lon'] = lon
    #        self.det['ship_track_time'] = dt
                        
            self.refresh_plot()             # refresh the plot
            
        else: # if no .all files are listed
            self.update_log('No new .all file(s) added.  Please add new .all file(s) and calculate coverage.')
#            error_msg = QtWidgets.QMessageBox()
#            error_msg.setText('No .all files loaded.  Please load .all files and calculate coverage.')

#        self.det['filenames'] = fnames  # store updated file list
        self.calc_coverage_btn.setStyleSheet("background-color: none") # reset the button color to default
    
    
    def update_log(self, entry): # update the activity log
        self.log.append(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' ' + entry)
        QtWidgets.QApplication.processEvents()
        
        
    def update_prog(self, total_prog):
        self.calc_pb.setValue(total_prog)
        QtWidgets.QApplication.processEvents()


    def refresh_plot(self): # update swath plot with new data and options
#        self.init_axes()
        self.clear_plot()
        self.update_color_mode() # initialize self.cmode if cmode not changed previously
        self.show_archive() # plot archive data with new plot control values
        
        try:
            self.plot_coverage(self.det, False) # plot new data if available
        except:
            pass
#            self.update_log('No .all coverage data available.  Please load files and calculate coverage.')

        self.add_grid_lines() # add grid lines
        self.add_WD_lines() # add water depth-multiple lines over coverage
        self.add_nominal_angle_lines() # add nominal swath angle lines over coverage
        self.update_axes() # update axes to fit all loaded data


    def init_swath_ax(self): # set initial swath parameters
        self.swath_ax = self.swath_figure.add_subplot(111)
        self.x_max = 1
        self.z_max = 1
        self.update_color_mode()
        self.cruise_name = ''
        self.N_WD_max = 8
        self.nominal_angle_line_interval = 15 # degrees between nominal angle lines
        self.nominal_angle_line_max = 75 # maximum desired nominal angle line
        self.swath_ax_margin = 1.1 # scale axes to multiple of max data in each direction
        self.add_grid_lines()
        self.update_axes()
        self.color = QtGui.QColor(0,0,0) # set default solid color to black for new data
        self.archive_color = QtGui.QColor('darkGray')
            
        
    def plot_coverage(self, det, is_archive): # plot the parsed detections
    
        # future optional arguments:
        #   cruise_name: default for survey ID recorded in first IP_start datagram, optional string input (e.g., '2016 Arctic')
        #   N_WD_max: number of water depth multiples to grid (default 8 for typical multibeam) 
        
        # consolidate data from port and stbd sides for plotting
        x_all = 	det['x_port'] + det['x_stbd']
        z_all = 	det['z_port'] + det['z_stbd']

        # update x and z max for axis resizing during each plot call
        self.x_max = max([self.x_max, np.max(np.abs(np.asarray(x_all)))])
        self.z_max = max([self.z_max, np.max(np.asarray(z_all))])
    
        # set color maps based on combobox selection
        if self.cmode == 'depth':
            c_all = z_all # set color range to depth range
            c_min = min(c_all)
            c_max = max(c_all)
        
        elif self.cmode == 'backscatter':
            bs_all = det['bs_port'] + det['bs_stbd']
            c_all = []
            c_all = [int(bs)/10 for bs in bs_all] # convert to int, divide by 10 (BS reported in 0.1 dB)
            c_min = -50
            c_max = -20 
            
        # sort through other color mode options (see readEM.interpretMode for strings used for each option)    
        elif np.isin(self.cmode, ['ping_mode', 'pulse_form', 'swath_mode']): # these modes are listed for each ping, rather than each detection
            c_list = det[self.cmode] + det[self.cmode] # modes are listed per ping; append ping-wise setting to corresponed with x_all, z_all
            
            if self.cmode == 'ping_mode':
                c_set = ['Very Shallow', 'Shallow', 'Medium', 'Deep', 'Very Deep', 'Extra Deep'] # set of all ping modes
                
            elif self.cmode == 'pulse_form':
                c_set = ['CW', 'Mixed', 'FM'] # set of all pulse forms
                
            elif self.cmode == 'swath_mode':
                c_set = ['Single Swath','Dual Swath (Fixed)','Dual Swath (Dynamic)'] # set of all swath modes
                
            c_all = [] # set up list comprehension to find integer corresponding to mode of each detection
            c_all = [c_set.index(c_list[i]) for i in range(len(c_list))]
            c_min = 0
            c_max = len(c_set)-1 # set max of colorscale to correspond with greatest possible index for selected mode
                      
        else:
            pass
           
        # plot it up
        if self.cmode == 'solid_color' or is_archive is True: # plot solid color if selected, or archive data
            if is_archive is True:
                c_all = colors.hex2color(self.archive_color.name()) # set archive color
            else:
                c_all = colors.hex2color(self.color.name()) # set desired color from color dialog
            
            self.swath_ax.scatter(x_all, z_all, s = self.pt_size_slider.value(), c = c_all, marker = 'o')

        else: # plot other color scheme, specify vmin and vmax from color range
            self.swath_ax.scatter(x_all, z_all, s = self.pt_size_slider.value(), c = c_all, marker = 'o', vmin=c_min, vmax=c_max, cmap='rainbow') # specify vmin and vmax
            
        self.swath_canvas.draw() # refresh swath canvas in main window
        

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
        self.update_system_info()
        # adjust x and y axes to fit max data
        self.swath_ax.set_ylim(0, self.swath_ax_margin*self.z_max) # set depth axis to 0 and 1.1 times max(z) 
        self.swath_ax.set_xlim(-1*self.swath_ax_margin*self.x_max, self.swath_ax_margin*self.x_max) # set x axis to +/-1.1 times max(abs(x))
            
        title_str = 'Swath Width vs. Depth\n' + self.model_name + ' - ' + self.ship_name + ' - ' + self.cruise_name
        self.swath_ax.set(xlabel='Swath Coverage (m)', ylabel='Depth (m)', title=title_str)
        self.swath_ax.invert_yaxis() # invert the y axis
        plt.show() # need show() after axis update!
        self.swath_canvas.draw()
        
    
    def update_color_mode(self):
        self.cmode = self.color_cbox.currentText() # get the currently selected color mode
        self.cmode = self.cmode.lower().replace(' ', '_') # format for comparison to list of modes below
        

    def update_solid_color(self):
        if self.cmode == 'solid_color': # get solid color if needed
            self.color = QtWidgets.QColorDialog.getColor()
            print(self.color)
            self.refresh_plot()
            
            
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
#                            y_mag = 2*x_mag/n # scale y location with limited x location
                            y_label_mag = x_label_mag/np.tan(n*self.nominal_angle_line_interval*np.pi/180)
                        
                        self.swath_ax.text(x_label_mag*ps, y_label_mag, str(n*self.nominal_angle_line_interval) + '\xb0',
                                verticalalignment = 'center', horizontalalignment = 'center',
                                bbox=dict(facecolor='white', edgecolor = 'none', alpha=1, pad = 0.0))    
                self.swath_canvas.draw()
            
            except:
                self.update_log('Failure plotting the swath angle lines...')
                

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
        self.swath_ax.clear()
        self.swath_canvas.draw()
        self.x_max = 1
        self.z_max = 1
        

    def archive_data(self):
       
        # save (pickle) the detection dictionary for future import to compare performance over time
        archive_name = QtWidgets.QFileDialog.getSaveFileName(self, 'Save data...', os.getenv('HOME'), '.PKL files (*.pkl)')
        
        if not archive_name: # abandon if no output location selected
            self.update_log('No archive output file selected.')
            return
        else: # archive data to selected file
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
        self.add_files('Saved swath coverage data(*.pkl)') # add .pkl files to qlistwidget
        
        try: # try to make list of unique archive filenames (used as keys) already in det_archive dict 
            fnames_arc = list(set(self.det_archive.keys()))
        except:
            fnames_arc = []      # self.det_archive has not been created yet
            self.det_archive = {}
        
        try:
            fnames_new_pkl = self.get_new_file_list('.pkl', fnames_arc) # list new .all files not included in det dict                    
        except:
            self.update_log('Error loading archive files')
            pass
       
        for f in range(len(fnames_new_pkl)):         # load archives, append to self.det_archive
            # try to load archive data and extend the det_archive 
#            det_archive_new = pickle.load(open(fnames_new_pkl[f], 'rb')) # loads det_archive dict
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