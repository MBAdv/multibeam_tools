try:
    from PySide2 import QtWidgets, QtGui
    from PySide2.QtCore import Qt, QSize
except ImportError as e:
    print(e)
    from PyQt5 import QtWidgets, QtGui
    from PyQt5.QtCore import Qt, QSize

import sys
from multibeam_tools.apps.swath_coverage_plotter import MainWindow

app = QtWidgets.QApplication(sys.argv)

main = MainWindow()
main.show()

sys.exit(app.exec_())
