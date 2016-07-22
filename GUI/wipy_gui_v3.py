# -*- coding: utf-8 -*-

"""Simple application based on guiqwt and guidata by Pierre Raybaut"""

SHOW = True # Show test in GUI-based test launcher

from guidata.qt.QtGui import QAction, QIcon, QMainWindow, QDockWidget, QTabWidget, QTextEdit, QTextCursor, QMessageBox, QSplitter, QListWidget, QPushButton
from guidata.qt.QtCore import (QSize, QT_VERSION_STR, PYQT_VERSION_STR, Qt)#, SIGNAL)
from PyQt4.QtCore import SIGNAL
from guidata.qt.compat import getopenfilename

import os, sys, platform
import os.path as osp
import numpy as np

from guidata.dataset.datatypes import DataSet, GetAttrProp
from guidata.dataset.dataitems import (IntItem, FloatItem, FloatArrayItem, StringItem, ChoiceItem)
from guidata.dataset.qtwidgets import DataSetEditGroupBox
from guidata.configtools import get_icon
from guidata.qthelpers import create_action, add_actions, get_std_icon
from guidata.utils import update_dataset
from guidata.py3compat import to_text_string
from guidata.qtwidgets import DockableWidget, DockableWidgetMixin

from guiqwt.config import _
from guiqwt.plot import ImageWidget, CurveWidget
from guiqwt.builder import make
# from guiqwt.signals import SIG_LUT_CHANGED
# from guiqwt.baseplot import SIG_LUT_CHANGED
from guiqwt import io
import guiqwt.pyplot as P

import redis as r
import wipyRedis as WR
import json

import peakdetect as pd

APP_NAME = _("WIPY DAQ")
VERSION = '0.8.0'



'''
TODO:

Create DAQ parameters

Make DAQ Parameters for existing data set visible

Load dataset and add to redis queue.

Add threaded monitor for plotting.
    How to turn off automatic plotting?

Add time of Acq to the Redis data entry

Implement Peak Picking
    How to push to redis queue
    Push list with each element being a JSON element...

'''

class SignalParam(DataSet):
    title = StringItem(_("Title"), default=_("Untitled"))
    xydata = FloatArrayItem(_("Data"), transpose=True, minmax="rows")
    
    def copy_data_from(self, other, dtype=None):
        self.xydata = np.array(other.xydata, copy=True, dtype=dtype)
    
    def change_data_type(self, dtype):
        self.xydata = np.array(self.xydata, dtype=dtype)
    
    def get_data(self):
        if self.xydata is not None:
            return self.xydata[1]
    
    def set_data(self, data):
        self.xydata[1] = data
    
    data = property(get_data, set_data)

class SignalParamNew(DataSet):
    title = StringItem(_("Title"), default=_("Untitled"))
    xmin = FloatItem("Xmin", default=-10.)
    xmax = FloatItem("Xmax", default=10.)
    size = IntItem(_("Size"), help=_("Signal size (total number of points)"),
                   min=1, default=500)
    type = ChoiceItem(_("Type"),
                      (("rand", _("random")), ("zeros", _("zeros")),
                       ("gauss", _("gaussian"))))

class LineParam(DataSet):
    '''
    Need to update to be specific for the lines
    '''
    _hide_data = False
    _hide_size = True
    title = StringItem(_("Title"), default=_("Untitled"))
    xydata = FloatArrayItem(_("Data")).set_prop("display",
                                              hide=GetAttrProp("_hide_data"))
    width = IntItem(_("Width"), help=_("Image width (pixels)"), min=1,
                    default=100).set_prop("display",
                                          hide=GetAttrProp("_hide_size"))
    height = IntItem(_("Height"), help=_("Image height (pixels)"), min=1,
                     default=100).set_prop("display",
                                           hide=GetAttrProp("_hide_size"))

class DAQParam(DataSet):
    # title = StringItem(_("Title"), default=_("Untitled"))
    # xmin = FloatItem("Gate Pulse Width", default=-10.)
    # xmax = FloatItem("Xmax", default=10.)
    numPnts = IntItem(_("Number of Points"), help=_("Signal size (total number of points)"),
                   min=200, default=1000)

    numAves = IntItem(_("Number of Averages"), help=_("Number of averages during acquisition"),
                   min=2, default=256)

    gpw = IntItem(_("Gate Pulse Width"), help=_("Signal size (total number of points)"),
                   min=20, default=200)
    daqSpeed = IntItem(_("DAQ Speed"), help=_("DAQ Speed in microseconds)"),
                   min=5, default=10)
    freq = IntItem(_("Frequency"), help=_("DAQ Frequency (Hz)"),
                   min=1000, default=40000)     
    fp = StringItem(_("WIPY Data Path"), default=_("/sd"))
    acqType = ChoiceItem(_("DAQ Type"),
                      (("0", _("Signal Averaged")), ("1", _("Hadamard")),
                       ("2", _("Fourier"))))
    multiplexParam = IntItem(_("Multiplex Param"), min=0, default = 0)
    
    def getParamDict(self):
        daqDict = {}
    
        daqDict['numPnts'] = self.numPnts
        daqDict['gpw'] = self.gpw 
        daqDict['acqSpeed'] = self.acqSpeed 
        daqDict['acqType'] = self.acqType
        daqDict['numAves'] = self.numAves
        daqDict['freq'] = self.freq
        daqDict['acqType'] = self.acqType
        daqDict['multiplexParam'] = self.multiplexParam

        return daqDict

    '''
    0-dataCode -- the unique identifier for the file
    1-numPnts -- number of points across the spectrum
    2-numAves -- the number of times the data acquisition loop is repeated.  Keep in mind that the actual averaging needs to occur following the load.  The Wipy only does integer mathematics.
    3-gpw -- value of the gate pulse width in microseconds
    4-acqSpeed -- the time between each data point in microseconds
    5-freq -- the frequency of data acquisition
    6-filePath -- string to the path on the SD card for the future retrieval
    7-acqType -- 0 - Signal Averaged, 1 - Hadamard, 2 - Fourier, 3 or more is for future use
    8-multiplexParam -- if the acqType is above 0 then a special code to define the mechanisms will be in this field (TBD).
    9-data --- All of the data for the experiment
    '''


class DAQParamsProperties(QSplitter):
    def __init__(self, parent):
        QSplitter.__init__(self, parent)
        # self.lineList = QListWidget(self)
        # self.addWidget(self.lineList)
        self.properties = DataSetEditGroupBox(_("Properties"), DAQParam)
        self.properties.setEnabled(True)
        self.addWidget(self.properties)

class LineListWithProperties(QSplitter):
    def __init__(self, parent):
        QSplitter.__init__(self, parent)
        self.lineList = QListWidget(self)
        self.addWidget(self.lineList)
        self.properties = DataSetEditGroupBox(_("Properties"), SignalParam)
        self.properties.setEnabled(False)
        self.addWidget(self.properties)


# Import spyderlib shell, if available
try:

    from spyderlib.widgets.internalshell import InternalShell
    from guidata.qt.QtGui import QFont
    class DockableConsole(InternalShell):
        LOCATION = Qt.BottomDockWidgetArea
        def __init__(self, parent, namespace, message, commands=[]):
            InternalShell.__init__(self, parent=parent, namespace=namespace,
                                   message=message, commands=commands,
                                   multithreaded=False)
            self.setup()

        def setup(self):
            font = QFont("Courier new")
            font.setPointSize(10)
            self.set_font(font)
            self.set_codecompletion_auto(True)
            self.set_calltips(True)
            self.setup_calltips(size=600, font=font)
            self.setup_completion(size=(300, 180), font=font)

except ImportError:
    print "Spyderlib is missing, no console"
    DockableConsole = None

class CentralWidget(QSplitter):
    def __init__(self, parent, toolbar):
        QSplitter.__init__(self, parent)
        # QTabWidget.__init__(self, parent)
        self.setContentsMargins(10, 10, 10, 10)
        self.setOrientation(Qt.Vertical)

        linelistwithproperties = LineListWithProperties(self)
        # self.addWidget(linelistwithproperties)
        self.lineList = linelistwithproperties.lineList
        self.connect(self.lineList, SIGNAL("currentRowChanged(int)"),
                     self.current_item_changed)
        self.connect(self.lineList, SIGNAL("itemSelectionChanged()"),
                     self.selection_changed)
        self.curveProperties = linelistwithproperties.properties
        self.connect(self.curveProperties, SIGNAL("apply_button_clicked()"),
                     self.curve_properties_changed)
        
        self.curvewidget = CurveWidget(self)
        self.curvewidget.register_all_curve_tools()
        self.curve_item = make.curve([], [], color='b')
        self.peak_item = make.curve([],[], markerfacecolor = 'r', marker = 'o', curvestyle="NoCurve")#, alpha = 0.75)
        self.curvewidget.plot.add_item(self.curve_item)
        self.curvewidget.plot.add_item(self.peak_item)
        self.curvewidget.plot.set_antialiasing(True)
        self.addWidget(self.curvewidget)
        
        self.lines = [] # List of ImageParam instances
        self.peaks = []

        
        vSplitter = QSplitter()
        vSplitter.setOrientation(Qt.Vertical)
        daqParamProperties = DAQParamsProperties(self)
        self.daqProperties = daqParamProperties.properties
        self.connect(self.daqProperties, SIGNAL("apply_button_clicked()"), self.daq_properties_changed)
        # daqButton = QPushButton("Upload DAQ Params")
        vSplitter.addWidget(daqParamProperties)
        # vSplitter.addWidget(daqButton)
        tabWidget = QTabWidget()
        tab1 = tabWidget.addTab(linelistwithproperties, "Curve Params")
        tab2 = tabWidget.addTab(vSplitter, "DAQ Params")
        
        self.addWidget(tabWidget)

        self.setStretchFactor(0, 0)
        self.setStretchFactor(1, 1)
        self.setHandleWidth(10)
        self.setSizes([1, 2])

    def refresh_list(self):
        self.lineList.clear()
        for line in self.lines:
            self.lineList.addItem(line.title)
        
    def selection_changed(self):
        """Image list: selection changed"""
        row = self.lineList.currentRow()
        self.curveProperties.setDisabled(row == -1)
        
    def current_item_changed(self, row):
        """Line list: current line changed"""
        line = self.lines[row]
        peaks = self.peaks[row]
        self.show_peaks(peaks)
        self.show_data(line)
        update_dataset(self.curveProperties.dataset, line)
        self.curveProperties.get()
        # print "Current Item Changed."
        
    def show_data(self, line):
        plot = self.curvewidget.plot
        # plot.add_item(self.curve_item)
        self.curve_item.setData(line.xydata[0], line.xydata[1])
        self.autoScale()

    def show_peaks(self, curPeak):
        print "Set Peaks"
        self.peak_item.setData(curPeak[0], curPeak[1])
    
    def autoScale(self):
        # print "AutoScale"
        plot = self.curvewidget.plot
        for ax in plot.get_active_axes():
            plot.setAxisAutoScale(ax)
        plot.replot()

    def curve_properties_changed(self):
        """The properties 'Apply' button was clicked: updating line plot"""
        row = self.lineList.currentRow()
        line = self.lines[row]
        update_dataset(line, self.curveProperties.dataset)
        self.refresh_list()
        self.show_data(line)

    def daq_properties_changed(self):
        """The properties 'Apply' button was clicked: updating DAQ Properties"""
        print self.daqProperties.dataset

    def add_curve(self, lineName, x, y, pickPeaks = True):
        line = SignalParam()
        line.title = lineName
        line.xydata = np.vstack((x,y))#array([x,y]))
        self.lines.append(line)
        self.refresh_list()
        # print line.xydata[0:10], lineName, np.array([x,y])[0:10]

        if pickPeaks:
            self.addPeaks(line)
        self.show_data(line)
        # self.curve_item.setData(x, y)
        # self.curvewidget.plot.do_autoscale()
        # for ax in self.curvewidget.plot.get_active_axes():
        #             self.curvewidget.plot.setAxisAutoScale(ax)
        # self.curvewidget.plot.replot()

    def addPeaks(self, line):
        '''
        Need to create the points
        Consider: https://pythonhosted.org/guiqwt/examples.html
        '''
        x = line.xydata[0]
        y = line.xydata[1]
        _max, _min = pd.peakdetect(y, x, 5)
        xm = [p[0] for p in _max]
        ym = [p[1] for p in _max]
        xn = [p[0] for p in _min]
        yn = [p[1] for p in _min]

        curPeak = np.vstack((xm,ym))
        self.peaks.append(curPeak)
        self.show_peaks(curPeak)
    
    def add_image_from_file(self, filename):
        image = SignalParam()
        image.title = to_text_string(filename)
        image.data = io.imread(filename, to_grayscale=True)
        image.height, image.width = image.data.shape
        self.add_image(image)

class MainWindow(QMainWindow):
    def __init__(self, parent = None):
        QMainWindow.__init__(self, parent)
        self.console = None
        self.setup()
    
    def closeEvent(self, event):
        if self.console is not None:
            self.console.exit_interpreter()
        event.accept()

    def setup(self):
        """Setup window parameters"""
        self.setWindowIcon(get_icon('python.png'))
        self.setWindowTitle(APP_NAME)
        self.resize(QSize(600, 800))
        
        # Welcome message in statusbar:
        status = self.statusBar()
        status.showMessage(_("Welcome to guiqwt application example!"), 5000)
        self.setupMainWidget()

        # File menu
        file_menu = self.menuBar().addMenu(_("File"))

        new_action = create_action(self, _("New..."),
                                   shortcut="Ctrl+N",
                                   icon=get_icon('filenew.png'),
                                   tip=_("Create a new image"),
                                   triggered=self.new_image)
        open_action = create_action(self, _("Open..."),
                                    shortcut="Ctrl+O",
                                    icon=get_icon('fileopen.png'),
                                    tip=_("Open an image"),
                                    triggered=self.open_image)
        quit_action = create_action(self, _("Quit"),
                                    shortcut="Ctrl+Q",
                                    icon=get_std_icon("DialogCloseButton"),
                                    tip=_("Quit application"),
                                    triggered=self.close)
        add_actions(file_menu, (new_action, open_action, None, quit_action))
        
        processing_menu = self.menuBar().addMenu(_("Processing"))
        autoscale_action = create_action(self, _("Autoscale"),
                                    shortcut="Ctrl+W",
                                    tip=_("Autoscale Graph"),
                                    triggered=self.plotWidget.autoScale)
        add_actions(processing_menu, (autoscale_action,))
        # Help menu
        help_menu = self.menuBar().addMenu("?")
        about_action = create_action(self, _("About..."),
                                     icon=get_std_icon('MessageBoxInformation'),
                                     triggered=self.about)
        add_actions(help_menu, (about_action,))
        
        main_toolbar = self.addToolBar("Main")
        add_actions(main_toolbar, (new_action, open_action, ))
        
        self.curFIFOVal = 0
        self.rdb = r.Redis('localhost')

        # self.setShortcuts()

        # self.setCentralWidget(self.plotWidget)
        self.setCentralWidget(self.main_dock)  

    
    def setShortcuts(self):
        self.autoScaleAction = QAction(QIcon(), '&Autoscale', self)
        self.autoScaleAction.setShortcut("Ctrl+W")
        self.autoScaleAction.triggered.connect(self.plotWidget.autoScale)
        # print "initiating shortcuts"
    #------

    def setupMainWidget(self) :
        self.main_dock = QDockWidget(_(''))
        self.addDockWidget(Qt.BottomDockWidgetArea, self.main_dock)
        self.dockTab = QTabWidget()
        dockSplitter = QSplitter()
        dockSplitter.setOrientation(Qt.Vertical)
        #-----
        toolbar = self.addToolBar("Curve")
        self.plotWidget = CentralWidget(self, toolbar)        # Set central widget:
        self.dockTab.addTab(self.plotWidget, "Plot")
        #-----
        self.statusEdit = QTextEdit()
        self.statusEdit.setText("Status updates to go here.")
        self.statusEdit.setEnabled(False)
        self.statusEdit.moveCursor(QTextCursor.End)
        #-----
        self.testButton = QPushButton("Test Button")
        self.testButton.clicked.connect(self.__testClick__)
        dockSplitter.addWidget(self.testButton)
        dockSplitter.addWidget(self.statusEdit)
        self.dockTab.addTab(dockSplitter, "Status Info")

        if DockableConsole is None:
            self.console = None
        else:
            import time, scipy.signal as sps, scipy.ndimage as spi
            import sys, os
            import numpy as np
            ns = {'np': np, 'sps': sps, 'spi': spi,
                  'os': os, 'sys': sys, 'time': time}
            msg = "Example: np.arange(20)\n"\
                  "Modules imported at startup: "\
                  "os, sys, os.path as osp, time, "\
                  "numpy as np, scipy.signal as sps, scipy.ndimage as spi"
            self.console = DockableConsole(self, namespace=ns, message=msg)
            # console_dock = QDockWidget(_('Console'))
            # self.addDockWidget(Qt.BottomDockWidgetArea, console_dock)
            # console_dock.setWidget(self.console)
            self.dockTab.addTab(self.console, "Console")
            # dockSplitter.addWidget(self.console)


        # main_dock.setWidget(dockSplitter)
        self.main_dock.setWidget(self.dockTab)

    #------
    def __testClick__(self):
        # self.statusEdit.append("Clicked")
        self.dataList = self.rdb.lrange('activeData', 0, -1)
        if self.curFIFOVal>20:
            self.curFIFOVal = 0

        dataID = self.dataList[self.curFIFOVal]
        # metaDict, raw = WR.processDataJson(self.rdb, dataID)
        # metaDict, raw = WR.processData(self.rdb, dataID)
        metaDict, raw = WR.processDataSegmented(self.rdb, dataID)
        xVals = np.arange(len(raw))
        self.curFIFOVal+=1
        self.statusEdit.append(str(raw[0:5]))
        self.plotWidget.add_curve(dataID, xVals, raw)

    #------?
    def about(self):
        QMessageBox.about( self, _("About ")+APP_NAME,
              """<b>%s</b> v%s<p>%s Brian H. Clowers
              <br>
              <br>Copyright &copy; 2016
              <p>Python %s, Qt %s, PyQt %s %s %s""" % \
              (APP_NAME, VERSION, _("Developped by"), platform.python_version(),
               QT_VERSION_STR, PYQT_VERSION_STR, _("on"), platform.system()) )
        
    #------I/O
    def new_image(self):
        """Create a new image"""
        imagenew = ImageParamNew(title=_("Create a new image"))
        if not imagenew.edit(self):
            return
        image = ImageParam()
        image.title = imagenew.title
        if imagenew.type == 'zeros':
            image.data = np.zeros((imagenew.width, imagenew.height))
        elif imagenew.type == 'rand':
            image.data = np.random.randn(imagenew.width, imagenew.height)
        self.mainwidget.add_image(image)
    
    def open_image(self):
        """Open image file"""
        saved_in, saved_out, saved_err = sys.stdin, sys.stdout, sys.stderr
        sys.stdout = None
        filename, _filter = getopenfilename(self, _("Open"), "",
                                            io.iohandler.get_filters('load'))
        sys.stdin, sys.stdout, sys.stderr = saved_in, saved_out, saved_err
        if filename:
            self.mainwidget.add_image_from_file(filename)
        
if __name__ == '__main__':
    from guidata import qapplication
    app = qapplication()
    window = MainWindow()
    window.show()
    app.exec_()
