# Builds a single-folder EXE for distribution.
# Note that an "unbundled" distribution launches much more quickly, but
# requires an installer program to distribute.
#
# To compile, execute the following within the source directory:
#
# pyinstaller --clean -y swath_coverage_plotter.spec
#
# The resulting .exe file is placed in the dist/swath_coverage_plotter folder.
#
# It may require to manually copy DLL libraries.
#

from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT, TOC
from PyInstaller.compat import is_darwin

import os
import sys

from multibeam_tools.apps.file_trimmer import __version__ as ft_version

sys.modules['FixTk'] = None


def collect_pkg_data(package, include_py_files=False, subdir=None):
    import os
    from PyInstaller.utils.hooks import get_package_paths, remove_prefix, PY_IGNORE_EXTENSIONS

    # Accept only strings as packages.
    if type(package) is not str:
        raise ValueError

    pkg_base, pkg_dir = get_package_paths(package)
    if subdir:
        pkg_dir = os.path.join(pkg_dir, subdir)
    # Walk through all file in the given package, looking for data files.
    data_toc = TOC()
    for dir_path, dir_names, files in os.walk(pkg_dir):
        for f in files:
            extension = os.path.splitext(f)[1]
            if include_py_files or (extension not in PY_IGNORE_EXTENSIONS):
                source_file = os.path.join(dir_path, f)
                dest_folder = remove_prefix(dir_path, os.path.dirname(pkg_base) + os.sep)
                dest_file = os.path.join(dest_folder, f)
                data_toc.append((dest_file, source_file, 'DATA'))

    return data_toc


scp_data = collect_pkg_data('multibeam_tools')
pyside2_data = collect_pkg_data('PySide2')

icon_file = os.path.abspath(os.path.join('freeze', 'file_trimmer.ico'))
if is_darwin:
    icon_file = os.path.join('freeze', 'file_trimmer.icns')

a = Analysis(['file_trimmer.py'],
             pathex=[],
             hiddenimports=["PIL", "scipy._lib.messagestream", "typing"],
             excludes=["IPython", "PyQt5", "pandas", "sphinx", "sphinx_rtd_theme", "OpenGL_accelerate",
                       "FixTk", "tcl", "tk", "_tkinter", "tkinter", "Tkinter",
                       "wx"],
             hookspath=None,
             runtime_hooks=None)

pyz = PYZ(a.pure)
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name='file_trimmer.%s' % ft_version,
          debug=False,
          strip=None,
          upx=True,
          console=True,
          icon=icon_file)
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               scp_data,
               pyside2_data,
               strip=None,
               upx=True,
               name='file_trimmer.%s' % ft_version)
