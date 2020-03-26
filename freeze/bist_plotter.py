try:
    import PySide2
    from PySide2 import QtWidgets, QtGui
    from PySide2.QtCore import Qt, QSize
except ImportError as e:
    print(e)
    import PyQt5
    from PyQt5 import QtWidgets, QtGui
    from PyQt5.QtCore import Qt, QSize

import matplotlib
matplotlib.use('Qt5Agg')

import sys
from multibeam_tools.apps.bist_plotter import MainWindow

app = QtWidgets.QApplication(sys.argv)

main = MainWindow()
main.show()

sys.exit(app.exec_())
