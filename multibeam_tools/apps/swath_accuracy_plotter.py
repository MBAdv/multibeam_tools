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
# import multibeam_tools.libs.parseEMswathwidth
from scipy.interpolate import griddata
from multibeam_tools.libs.gui_widgets import *
from multibeam_tools.libs.file_fun import *
from multibeam_tools.libs.swath_accuracy_lib import *
from multibeam_tools.libs.swath_fun import *



__version__ = "0.0.4"

# just testing branch switching in Git... again


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

        # initialize other necessities
        # self.filenames = ['']
        self.unit_mode = '%WD'  # default plot as % Water Depth; option to toggle alternative meters

        # set up three layouts of main window
        self.set_left_layout()
        self.set_center_layout()
        self.set_right_layout()
        self.set_main_layout()
        self.init_swath_ax()

        # set up file control actions
        # self.add_file_btn.clicked.connect(lambda: self.add_files('Kongsberg(*.all *.kmall)'))
        self.add_file_btn.clicked.connect(lambda: add_acc_files(self, 'Kongsberg (*.all *.kmall)'))
        self.get_indir_btn.clicked.connect(lambda: add_acc_files(self, ['.all', '.kmall'], input_dir=[],
                                                                 include_subdir=self.include_subdir_chk.isChecked()))
        self.get_outdir_btn.clicked.connect(lambda: get_output_dir(self))

        # self.add_ref_surf_btn.clicked.connect(lambda: self.add_files('Reference surface XYZ(*.xyz)'))
        self.add_ref_surf_btn.clicked.connect(lambda: add_ref_file(self, 'Reference surface XYZ(*.xyz)'))

        self.rmv_file_btn.clicked.connect(self.remove_files)
        self.clr_file_btn.clicked.connect(self.clear_files)
        self.show_path_chk.stateChanged.connect(lambda: show_file_paths(self))

        self.calc_accuracy_btn.clicked.connect(self.calc_accuracy)        
        self.save_plot_btn.clicked.connect(self.save_plot)

        # set up plot control actions
        # self.custom_info_chk.stateChanged.connect(self.refresh_plot)
        self.custom_info_gb.clicked.connect(self.refresh_plot)
        # self.model_cbox.activated.connect(self.refresh_plot)
        self.ship_tb.returnPressed.connect(self.refresh_plot)
        self.cruise_tb.returnPressed.connect(self.refresh_plot)
        self.grid_lines_toggle_chk.stateChanged.connect(self.refresh_plot)
        self.IHO_lines_toggle_chk.stateChanged.connect(self.refresh_plot)
        # self.custom_max_chk.stateChanged.connect(self.refresh_plot)
        self.plot_lim_gb.clicked.connect(self.refresh_plot)
        self.max_beam_angle_tb.returnPressed.connect(self.refresh_plot)
        self.angle_spacing_tb.returnPressed.connect(self.refresh_plot)
        self.max_bias_tb.returnPressed.connect(self.refresh_plot)
        self.max_std_tb.returnPressed.connect(self.refresh_plot)

        # add max angle limits
        # self.custom_angle_chk.stateChanged.connect(self.refresh_plot)
        # self.max_angle_tb.returnPressed.connect(self.refresh_plot)
        # self.min_angle_tb.returnPressed.connect(self.refresh_plot)

        cbox_map = [self.model_cbox,
                    self.pt_size_cbox,
                    self.pt_alpha_cbox,
                    self.ref_cbox]
                    # self.color_cbox,
                    # self.color_cbox_arc,
                    # self.clim_cbox,
                    # self.top_data_cbox,
                    # self.ref_cbox]

        for cbox in cbox_map:
            # lambda needs _ for cbox
            cbox.activated.connect(lambda _, sender=cbox.objectName(): self.refresh_plot(sender=sender))

    def set_left_layout(self):
        btnh = 20  # height of file control button
        btnw = 100  # width of file control button

        # add reference surface import options (processed elsewhere, XYZ in meters positive up, UTM 1-60N through 1-60S)
        self.add_ref_surf_btn = PushButton('Add Ref. Surface', btnw, btnh, 'add_ref_surf_btn', 'Add a ref. surface')
        proj_list = [str(i) + 'N' for i in range(1, 61)]  # list of all UTM zones, 1-60N and 1-60S
        proj_list.extend([str(i) + 'S' for i in range(1, 61)])
        EPSG_list = [str(i) for i in range(32601, 32661)]  # list of EPSG codes for WGS84 UTM1-60N
        EPSG_list.extend([str(i) for i in range(32701, 32761)])  # add EPSG codes for WGS84 UTM1-60S
        self.proj_dict = dict(zip(proj_list, EPSG_list))  # save for lookup during xline UTM zone conversion with pyproj
        self.ref_proj_cbox = ComboBox(proj_list, 50, 20, 'ref_proj_cbox', 'Select the reference surface UTM projection')
        ref_cbox_layout = BoxLayout([Label('Proj.:', 50, 20, 'ref_proj_lbl', (Qt.AlignRight | Qt.AlignVCenter)),
                                     self.ref_proj_cbox], 'h')
        ref_cbox_layout.addStretch()
        ref_btn_layout = BoxLayout([self.add_ref_surf_btn, ref_cbox_layout], 'v')
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
        file_btn_layout = BoxLayout([ref_utm_gb, source_btn_gb, plot_btn_gb], 'v')
        file_btn_layout.addStretch()
        self.file_list = FileList()  # add file list with extended selection and icon size = (0,0) to avoid indent
        file_gb = GroupBox('Sources', BoxLayout([self.file_list, file_btn_layout], 'h'), False, False, 'file_gb')

        # add activity log widget
        self.log = TextEdit("background-color: lightgray", True, 'log')
        self.log.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.Minimum)
        update_log(self, '*** New swath accuracy processing log ***')
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

    def set_center_layout(self):  # set center layout with swath coverage plot
        # add figure instance
        self.swath_canvas_height = 10
        self.swath_canvas_width = 10
        self.swath_figure = Figure(figsize=(self.swath_canvas_width, self.swath_canvas_height))
        self.swath_canvas = FigureCanvas(self.swath_figure)  # canvas widget that displays the figure
        self.swath_canvas.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding,
                                        QtWidgets.QSizePolicy.MinimumExpanding)
        self.swath_toolbar = NavigationToolbar(self.swath_canvas, self) # swath plot toolbar

        # initialize max x, z limits
        self.x_max = 0.0
        self.y_max = 0.0

        # set the swath layout
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


        # # add checkbox and set layout
        # self.custom_info_chk = QtWidgets.QCheckBox('Use custom system information\n(default: parsed if available)')
        # system_info_layout = QtWidgets.QVBoxLayout()
        # system_info_layout.addWidget(self.custom_info_chk)
        # system_info_layout.addWidget(self.custom_info_gb)
        #
        # system_info_gb = QtWidgets.QGroupBox('System Information')
        # system_info_gb.setLayout(system_info_layout)

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
        self.grid_lines_toggle_chk = CheckBox('Show grid lines', True, 'show_grid_lines_chk', 'Show grid lines')
        self.IHO_lines_toggle_chk = CheckBox('Show IHO lines', True, 'show_IHO_lines_chk', 'Show IHO lines')
        toggle_chk_layout = BoxLayout([self.grid_lines_toggle_chk], 'v')  # do not add IHO lines yet
        toggle_gb = QtWidgets.QGroupBox('Plot Options')
        toggle_gb.setLayout(toggle_chk_layout)



        # set up tabs
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setStyleSheet("background-color: none")

        # set up tab 1: plot options
        self.tab1 = QtWidgets.QWidget()
        self.tab1.layout = BoxLayout([self.custom_info_gb, self.depth_ref_gb, pt_param_gb,
                                      self.plot_lim_gb, toggle_gb], 'v')
        self.tab1.layout.addStretch()
        self.tab1.setLayout(self.tab1.layout)

        # set up tab 2: filtering options
        self.tab2 = QtWidgets.QWidget()
        self.tab2.layout = BoxLayout([Label('FUTURE FILTERS')], 'v')
        self.tab2.layout.addStretch()
        self.tab2.setLayout(self.tab2.layout)

        # add tabs to tab layout
        self.tabs.addTab(self.tab1, 'Plot')
        self.tabs.addTab(self.tab2, 'Filter')

        self.tabw = 240  # set fixed tab width
        self.tabs.setFixedWidth(self.tabw)

        self.right_layout = BoxLayout([self.tabs], 'v')
        self.right_layout.addStretch()

        # # set plot control group box
        # self.plot_control_gb = QtWidgets.QGroupBox('Plot Control')
        # self.plot_control_gb.setLayout(self.plot_control_layout)
        # self.plot_control_gb.setFixedWidth(225)
        #
        # # set the right panel layout
        # self.right_layout = QtWidgets.QVBoxLayout()
        # self.right_layout.addWidget(self.plot_control_gb)
        # self.right_layout.addStretch()
        
    def set_main_layout(self):
        # set the main layout with file controls on left and swath figure on right
        main_layout = QtWidgets.QHBoxLayout()
        main_layout.addLayout(self.left_layout)
        main_layout.addLayout(self.swath_layout)
        main_layout.addLayout(self.right_layout)
        
        self.mainWidget.setLayout(main_layout)

    # def add_files(self, ftype_filter): # select files with desired type, add to list box
    #     if '.xyz' in ftype_filter: # pick only one file for reference surface
    #         fname_ref = QtWidgets.QFileDialog.getOpenFileName(self, 'Open reference surface file...', os.getenv('HOME'), ftype_filter)
    #         fnames = ([fname_ref[0]],) + (ftype_filter,) # make a tuple similar to return from getOpenFileNames
    #
    #     else:
    #         fnames = QtWidgets.QFileDialog.getOpenFileNames(self, 'Open crossline file(s)...', os.getenv('HOME'), ftype_filter)
    #
    #     self.get_current_file_list() # get updated file list and add selected files only if not already listed
    #
    #     fnames_new = [fn for fn in fnames[0] if fn not in self.filenames]
    #     fnames_skip = [fs for fs in fnames[0] if fs in self.filenames]
    #
    #     if len(fnames_skip) > 0: # skip any files already added, update log
    #         self.update_log('Skipping ' + str(len(fnames_skip)) + ' file(s) already added')
    #
    #     for f in range(len(fnames_new)): # add the new files only
    #         self.file_list.addItem(fnames_new[f])
    #         self.update_log('Added ' + fnames_new[f].split('/')[-1])
    #
    #     self.update_buttons()

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
        self.file_list.clear()  # clear the file list display
        self.filenames = []  # clear the list of (paths + files) passed to calc_coverage
        self.xline = {}  # clear current non-archive detections
        self.ref_surf = {}  # clear ref surf data
        self.bin_beamwise()  # call bin_beamwise with empty self.xline to reset all other binned results
        # self.beam_bin_dz_mean = []
        # self.beam_bin_dz_N
        self.remove_files()  # remove files and refresh plot
        self.update_log('Cleared all files')
        self.current_file_lbl.setText('Current File [0/0]:')
        self.calc_pb.setValue(0)
        self.add_ref_surf_btn.setEnabled(True)

    def get_current_file_list(self, ftype = ''):  # get current list of files in qlistwidget
        list_items = []
        for f in range(self.file_list.count()):
            list_items.append(self.file_list.item(f))
        
        self.filenames = [f.text() for f in list_items] # convert to text

#     def get_new_file_list(self, fext = '', flist_old = []):
#         # determine list of new files with file extension fext that do not exist in flist_old
#         # flist_old may contain paths as well as file names; compare only file names
#         self.get_current_file_list()
# #        print('in get_new_file_list, just got the new current file list:', self.filenames)
# #        fnames_all = [f for f in self.filenames if '.all' in f]
#         fnames_ext = [f for f in self.filenames if fext in f] # file names (with paths) that match the extension
#         fnames_old = [f.split('/')[-1] for f in flist_old] # file names only (no paths) from flist_old
#         fnames_new = [fn for fn in fnames_ext if fn.split('/')[-1] not in fnames_old] # check if file name (without path) exists in fnames_old
#         return(fnames_new) # return the fnames_new (with paths)

    def calc_accuracy(self):
        # calculate accuracy of soundings from at least one crossline over exactly one reference surface
        self.update_log('Starting accuracy calculations')
        self.parse_ref_surf()  # parse the ref surf

        print('survived parse_ref_surf')
        # self.apply_masks() # FUTURE: flag outlier soundings and mask nodes for density, slope
        self.parse_crosslines()  # parse the crossline(s)

        _, _, dz_ping = adjust_depth_ref(self.xline, depth_ref=self.ref_cbox.currentText().lower())
        print('dz_ping has len', len(dz_ping))
        print('first 20 of xline[z]=', self.xline['z'][0:20])
        print('first 20 of dz_ping =', dz_ping[0:20])

        z_final = [z + dz for z, dz in zip(self.xline['z'], dz_ping)]  # add dz
        self.xline['z_final'] = (-1*np.asarray(z_final)).tolist()  # flip sign to neg down and store 'final' soundings

        self.convert_crossline_utm()   # convert crossline X,Y to UTM zone of reference surface
        self.calc_dz_from_ref_interp()  # interpolate ref surf onto sounding positions, take difference
        # self.find_nearest_node() # find nearest ref node for each sounding -- SUPERCEDED BY calc_dz_from_ref_interp
        # self.calc_dz() # calculate differences from ref surf -- SUPERCEDED BY calc_dz_from_ref_interp
        self.bin_beamwise()  # bin the results by beam angle
        self.update_log('Finished calculating accuracy')
        self.update_log('Plotting accuracy results')
        self.refresh_plot()             # refresh the plot

    def parse_ref_surf(self):
        # parse the loaded reference surface .xyz file
        # ref grid is assumed UTM projection with meters east, north, depth (+Z up), e.g., export from processing
        self.ref_surf = {}
        # self.get_current_file_list()
        fnames_xyz = get_new_file_list(self, ['.xyz'], [])  # list .xyz files
        num_ref_files = len(fnames_xyz)
        print('fnames_xyz is', fnames_xyz)
        # fnames_xyz = [f for f in self.filenames if '.xyz' in f]  # get all .xyz file names
        # fnames_xyz = [f for f in fnames_new if '.xyz' in f]  # get all .xyz file names

        if len(fnames_xyz) != 1:  # warn user to add exactly one ref grid
            self.update_log('Please add one reference grid .xyz file in a UTM projection')
            pass
        else:
            fname_ref = fnames_xyz[0]
            print(fname_ref)
            fid_ref = open(fname_ref, 'r')
            e_ref, n_ref, z_ref = [], [], []
            for line in fid_ref:
                temp = line.replace('\n', '').split(",")
                e_ref.append(temp[0])  # easting
                n_ref.append(temp[1])  # northing
                z_ref.append(temp[2])  # up
            
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
            fnames_xline = list(set(self.xline['fname']))  # make list of unique filenames already in detection dict
        except:
            fnames_xline = []  # self.xline has not been created yet; initialize this and self.xline detection dict
            self.xline = {}

        # fnames_new_all = self.get_new_file_list('.all', fnames_xline)  # list new .all files not included in det dict
        fnames_new = get_new_file_list(self, ['.all', '.kmall'], fnames_xline)  # list all files not in xline dict
        num_new_files = len(fnames_new)
        self.update_log('Found ' + str(len(fnames_new)) + ' new crossline .all files')

        if num_new_files == 0:
            update_log(self, 'No new .all or .kmall crosslines added.  Please add new file(s) and calculate accuracy')

        else:
            # if len(fnames_new_all) > 0:  # proceed if there is at least one .all file that does not exist in det dict
            update_log(self, 'Calculating accuracy from ' + str(num_new_files) + ' new file(s)')
            # self.update_log('Calculating accuracy from ' + str(len(fnames_new_all)) + ' new file(s)')
            QtWidgets.QApplication.processEvents()  # try processing and redrawing the GUI to make progress bar update
            data_new = {}
            
            # update progress bar and log
            self.calc_pb.setValue(0)  # reset progress bar to 0 and max to number of files
            self.calc_pb.setMaximum(len(fnames_new))

            for f in range(len(fnames_new)):
            # for f in range(len(fnames_new_all)):         # read previously unparsed files
                fname_str = fnames_new[f].rsplit('/')[-1]
                self.current_file_lbl.setText('Parsing new file [' + str(f+1) + '/' + str(num_new_files) + ']:' + fname_str)
                QtWidgets.QApplication.processEvents()
                ftype = fname_str.rsplit('.', 1)[-1]

                if ftype == 'all':
                    # parse IPSTART73, RRA78, POS80, RTP82, XYZ88
                    # data_new[f] = multibeam_tools.libs.readEM.parseEMfile(fnames_new[f],
                    #                                                       parse_list=[73, 78, 80, 82, 88],
                    #                                                       print_updates=False)
                    data_new[f] = readALLswath(self, fnames_new[f],
                                               print_updates=True,
                                               parse_outermost_only=False)

                elif ftype == 'kmall':

                    km = kmall.kmall(fnames_new[f])
                    km.verbose = 0
                    km.index_file()
                    km.report_packet_types()
                    km.extract_dg('MRZ')
                    km.extract_dg('IOP')
                    km.extract_dg('IIP')
                    # print('km is', km)
                    km.closeFile()
                    data_new[f] = {'fname': fnames_new[f], 'XYZ': km.mrz['soundings'],
                                   'HDR': km.mrz['header'], 'RTP': km.mrz['pinginfo'],
                                   'IOP': km.iop, 'IP': km.iip}

                    print('data_new[IP]=', data_new[f]['IP'])
                    print('IP text =', data_new[f]['IP']['install_txt'])

                else:
                    update_log(self, 'Warning: Skipping unrecognized file type for ' + fname_str)

                update_log(self, 'Parsed file ' + fname_str)
                self.update_prog(f+1)


            # regardless of data source, convert XYZ to lat and lon; maintain depth as reported in file
            self.data_new = multibeam_tools.libs.readEM.convertXYZ(data_new, print_updates=True)  # convert XYZ datagrams to lat, lon, depth


            # self.data = multibeam_tools.libs.readEM.interpretMode(data, print_updates=False) # interpret modes
            self.data_new = interpretMode(self, data_new, print_updates=False)  # interpret modes using updated fun (for .all, .kmall)
            files_OK, EM_params = multibeam_tools.libs.readEM.verifyMode(self.data_new)  # verify consistent installation and runtime parameters

            if not files_OK: # warn user if inconsistencies detected (perhaps add logic later for sorting into user-selectable lists for archiving and plotting)
                update_log(self, 'WARNING! CROSSLINES HAVE INCONSISTENT MODEL, S/N, or RUNTIME PARAMETERS')
            
            # det_new = multibeam_tools.libs.readEM.sortAccuracyDetections(data_new, print_updates=False)  # sort new accuracy soundings
            det_new = sortAccDetections(self, self.data_new, print_updates=False)  # sort new accuracy soundings

            # print('just got back from sortAccDetections, need to make sure det_new soundings are in list form!, det_new=', det_new)

            # # z is returned as positive down; flip sign for later use
            # z_pos_up = -1*np.asarray(det_new['z'])
            # z_re_wl_pos_up = -1*np.asarray(det_new['z_re_wl'])
            # det_new['z'] = z_pos_up.tolist()
            # det_new['z_re_wl'] = z_re_wl_pos_up.tolist()

            # det_new['z'] = (-1*np.asarray(det_new['z'])).tolist()
            # det_new['z_re_wl'] = (-1*np.asarray(det_new['z_re_wl'])).tolist()

            if len(self.xline) is 0:  # if detection dict is empty, store all new detections
                self.xline = det_new
                
            else: # otherwise, append new detections to existing detection dict                
                for key, value in det_new.items():  # loop through the new data and append to existing self.xline
                    self.xline[key].extend(value)
                    
            update_log(self, 'Finished parsing ' + str(num_new_files) + ' new file(s)')
            self.current_file_lbl.setText('Current File [' + str(f+1) + '/' + str(num_new_files) +
                                          ']: Finished parsing crosslines')
                                    
        # else:  # if no .all files are listed
        #     update_log(self, 'No new crossline .all file(s) added')

#        self.xline['filenames'] = fnames  # store updated file list
        self.calc_accuracy_btn.setStyleSheet("background-color: none")  # reset the button color to default

        # # get set of modes in these crosslines
        # if self.xline['ping_mode']:
        #     modes = [' / '.join([self.xline['ping_mode'][i],
        #                        self.xline['swath_mode'][i],
        #                        self.xline['pulse_form'][i]]) for i in range(len(self.xline['ping_mode']))]
        #     print('first ten mode strings found:', modes[0:10])
        #     print('set of modes is ', ' + '.join(list(set(modes))))


    def convert_crossline_utm(self):
        # if necessary, convert crossline X,Y to UTM zone of reference surface
        update_log(self, 'Checking UTM zones of ref grid and crossline(s)')
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
            update_log(self, 'Found crossline soundings in different UTM zone')

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

                update_log(self, 'Transformed ' + str(len(idx)) + ' soundings (out of '
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
        update_log(self, 'Calculating ref grid depths at crossline sounding positions')
        print('N ref_surf nodes e =', len(self.ref_surf['e']), 'with first ten =', self.ref_surf['e'][0:10])
        print('N ref_surf nodes n =', len(self.ref_surf['n']), 'with first ten =', self.ref_surf['n'][0:10])
        print('N ref_surf nodes z =', len(self.ref_surf['z']), 'with first ten =', self.ref_surf['z'][0:10])

        print('N xline soundings e =', len(self.xline['e']), 'with first ten =', self.xline['e'][0:10])
        print('N xline soundings n =', len(self.xline['n']), 'with first ten =', self.xline['n'][0:10])
        print('N xline soundings z =', len(self.xline['z']), 'with first ten =', self.xline['z'][0:10])
        print('N xline soundings z_final =', len(self.xline['z_final']), 'with first ten =', self.xline['z_final'][0:10])

        # interpolate the reference grid (linearly) onto the sounding positions
        # note: griddata will interpolate only within the convex hull of the input grid coordinates
        # xline sounding positions outside the convex hull (i.e., off the grid) will return NaN
        self.xline['z_ref_interp'] = griddata((self.ref_surf['e'], self.ref_surf['n']),
                                              self.ref_surf['z'],
                                              (self.xline['e'], self.xline['n']),
                                              method='linear')

        print('z_ref_interp looks like', self.xline['z_ref_interp'][0:30])
        print('xline z_final after flip looks like', self.xline['z_final'][0:30])

        N_ref_surf_interp = np.sum(~np.isnan(self.xline['z_ref_interp']))  # count non-Nan interpolated value
        update_log(self, 'Found ' + str(N_ref_surf_interp) + ' crossline soundings on ref grid')

        # calculate dz for xline soundings with non-NaN interpolated reference grid depths
        # note that xline['z'] is positive down as returned from parser; flip sign for differencing from ref surf
        update_log(self, 'Calculating crossline differences from ref grid')
        # self.xline['dz_ref'] = np.subtract(self.xline['z'], self.xline['z_ref_interp'])
        self.xline['dz_ref'] = np.subtract(self.xline['z_final'], self.xline['z_ref_interp'])

        print('xline dz_ref looks like', self.xline['dz_ref'][0:100])

        # store dz as percentage of water depth, with positive dz_ref_wd meaning shallower crossline soundings
        # to retain intuitive plotting appearance, with shallower soundings above deeper soundings
        # e.g., if xline z = -98 and z_ref_interp = -100, then dz_ref = +2; dz_ref_wd should be positive; division of
        # positive bias (up) by reference depth (always negative) yields negative, so must be flipped in sign for plot
        dz_ref_wd = np.array(-1*100*np.divide(np.asarray(self.xline['dz_ref']), np.asarray(self.xline['z_ref_interp'])))
        self.xline['dz_ref_wd'] = dz_ref_wd.tolist()

        print('xline dz_ref_wd looks like', self.xline['dz_ref_wd'][0:100])

        self.ref_surf['z_mean'] = np.nanmean(self.xline['z_ref_interp'])  # mean of ref grid interp values used

    def bin_beamwise(self):
        update_log(self, 'Binning soundings by angle')
        # bin by angle, calc mean and std of sounding differences in that angular bin
        self.beam_bin_size = 1  # beam angle bin size (deg)
        self.beam_bin_lim = 75  # max angle (deg)

        self.beam_bin_dz_mean = []  # declare dz mean, std, and sample count
        self.beam_bin_dz_std = []
        self.beam_bin_dz_N = []
        self.beam_bin_dz_wd_mean = []
        self.beam_bin_dz_wd_std = []
        self.beam_range = range(-1*self.beam_bin_lim, self.beam_bin_lim, self.beam_bin_size)

        # calculate simplified beam angle from acrosstrack distance and depth
        # # depth is used here as negative down re WL, consistent w/ %WD results
        # Kongsberg angle convention is right-hand-rule about +X axis (fwd), so port angles are + and stbd are -
        # however, for plotting purposes, this will use negative beam angles to port and positive to stbd, per plotting
        # conventions used elsewhere (e.g., Qimera)
        # print('trying to calc beam angles with len(xline(y))=', len(self.xline['y']), ' and len(z_re_wl)=', len(self.xline['z_re_wl']))
        self.xline['beam_angle'] = np.rad2deg(np.arctan2(self.xline['y'],
                                                         (-1*np.asarray(self.xline['z_final'])).tolist())).tolist()
        # self.xline['beam_angle'] = (-1*np.rad2deg(np.arctan2(self.xline['y'], self.xline['z_re_wl']))).tolist()

        print('size of beam_angle is now', len(self.xline['beam_angle']))
        print('first 30 beam angles are', self.xline['beam_angle'][0:30])

        # self.xline['beam_angle'] = (-1*np.rad2deg(np.arctan2(self.xline['y'], self.xline['z_re_wl']))).tolist()

        # if crossline data AND reference surface are available, convert soundings with meaningful reference surface
        # nodes to array for binning; otherwise, continue to refresh plot with empty results
        if 'beam_angle' in self.xline and 'z' in self.ref_surf:
            print('found beam_angle in self.xline and z in self.ref_surf')
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

        else:
            print('missing something in bin_beamwise!!!!!')

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
        # set point size; slider is on [1-11] for small # of discrete steps; square slider value for real pt size
        pt_size = float(self.pt_size_cbox.currentText())/10
        pt_alpha = np.divide(float(self.pt_alpha_cbox.currentText()), 100)

        beam_bin_centers = np.asarray([b+self.beam_bin_size/2 for b in self.beam_range])  # generate bin centers for plotting
        beam_bin_dz_wd_std = np.asarray(self.beam_bin_dz_wd_std)

        # plot standard deviation as %WD versus beam angle
        self.ax1.plot(beam_bin_centers, beam_bin_dz_wd_std, '-', linewidth=self.lwidth, color='b')  # beamwise bin mean + st. dev.
        self.ax1.grid(True)

        # plot the raw differences, mean, and +/- 1 sigma as %wd versus beam angle
        self.ax2.scatter(self.xline['beam_angle'], self.xline['dz_ref_wd'],
                         marker='o', color='0.75', s=pt_size, alpha=pt_alpha)
        # raw differences from reference grid, small gray points
        self.ax2.plot(beam_bin_centers, self.beam_bin_dz_wd_mean, '-',
                      linewidth=self.lwidth, color='r')  # beamwise bin mean difference
        self.ax2.plot(beam_bin_centers, np.add(self.beam_bin_dz_wd_mean, self.beam_bin_dz_wd_std), '-',
                      linewidth=self.lwidth, color='b')  # beamwise bin mean + st. dev.
        self.ax2.plot(beam_bin_centers, np.subtract(self.beam_bin_dz_wd_mean, self.beam_bin_dz_wd_std), '-',
                      linewidth=self.lwidth, color='b')  # beamwise bin mean - st. dev.
        self.ax2.grid(True)

    def update_log(self, entry):  # update the activity log
        self.log.append(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' ' + entry)
        QtWidgets.QApplication.processEvents()

    def update_prog(self, total_prog):  # update progress bar
        self.calc_pb.setValue(total_prog)
        QtWidgets.QApplication.processEvents()

    def refresh_plot(self, sender=None): # update swath plot with new data and options
        self.clear_plot()
        self.update_plot_limits()

        try:
            self.plot_accuracy(self.xline, False)  # plot new data if available
        except:
            update_log(self, 'No .all coverage data available.  Please load files and calculate coverage.')
            pass

        self.add_grid_lines()  # add grid lines
        self.update_axes()  # update axes to fit all loaded data
        self.swath_canvas.draw()

    def update_system_info(self):
        # update model, serial number, ship, cruise based on availability in parsed data and/or custom fields
        if self.custom_info_gb.isChecked(): # use custom info if checked
            # self.custom_info_gb.setEnabled(True) # enable the custom info group box
            self.ship_name = self.ship_tb.text()
            self.cruise_name = self.cruise_tb.text()
            self.model_name = self.model_cbox.currentText()
        else: # get info from detections if available
            # self.custom_info_gb.setEnabled(False) # disable the custom info group box

            try:  # try to grab ship name from filenames (conventional file naming)
                self.ship_name = self.det['fname'][0]  # try getting ship name from first detection filename
#                self.ship_name = self.det['filenames'][0] # try getting ship name from detection dict filenames
                self.ship_name = self.ship_name[self.ship_name.rfind('_')+1:-4] # assumes filename ends in _SHIPNAME.all  
            except:
                self.ship_name = 'SHIP NAME N/A' # if ship name not available in filename
                
            try:  # try to grab cruise name from Survey ID field in
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
        title_str = 'Swath Accuracy vs. Beam Angle\n' + ' - '.join([self.model_name, self.ship_name, self.cruise_name])

        # # mode_str = 'multiple modes'
        # if self.xline['ping_mode']:
        #     modes = ['/'.join([self.xline['ping_mode'][i], self.xline['swath_mode'][i], self.xline['pulse_form'][i]]) for
        #              i in range(len(self.xline['ping_mode']))]
        #     print('first ten mode strings found:', modes[0:10])
        # [str(param) for param in set(self.xline['ping_mode'])]
        # if all([len(set(self.xline[param])) == 1 for param in ['ping_mode', 'swath_mode', 'pulse_form']]):
        #     mode_str = '/'.join([str(param) for param in set(self.xline['ping_mode'])])
        # get set of modes in these crosslines
        if self.xline:
            modes = [' / '.join([self.xline['ping_mode'][i],
                                 self.xline['swath_mode'][i],
                                 self.xline['pulse_form'][i]]) for i in range(len(self.xline['ping_mode']))]
            print('first ten mode strings found:', modes[0:10])
            print('set of modes is ', ' + '.join(list(set(modes))))
            title_str += ' - ' + ' + '.join(list(set(modes)))

        else:
            title_str += ' - Unknown modes'


        'ping_mode', 'pulse_form', 'swath_mode',
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

        if self.plot_lim_gb.isChecked():  # use custom plot limits if checked, store custom values in text boxes
            # self.max_gb.setEnabled(True)
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
            # self.max_gb.setEnabled(False)
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
        
        update_log(self, 'Saved figure ' + fname_out.rsplit('/')[-1])
        
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





