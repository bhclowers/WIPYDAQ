import redis as r
import numpy as N
import threading
import time, math
from PyQt4 import QtCore, QtGui
import redisdl #Dump code for redis db
import os, sys
import zlib
import json

'''
Do we want to push and pull the data as dicts through json?
'''

#Be sure these default parameters are translated to the code to run on the WIPY
DAQPARAMS = {}
DAQPARAMS['numPnts'] = 1000
DAQPARAMS['numAves'] = 100
DAQPARAMS['gpw'] = 200
DAQPARAMS['acqSpeed'] = 25
DAQPARAMS['freq'] = 40000
DAQPARAMS['acqType'] = 0
DAQPARAMS['multiplexParam'] = 0 # this is for future use 


class WIPYConnection(object):
    '''
    WIPY Connection

    The local redis database has the following data organization.
    Each of the following keys has an example attached 

    activeData -- this list contains the active data that has most recently been acquired
    self.rdb.lpush('activeData', 'uniqueID')
    activeData = [uniqueID1, uniqueID2, uniqueID3, uniqueID3]
    Once the FIFO limit (default = 25 items) has been reached the last items start getting popped out.

    The database also will/does contain all of the info loaded for the defaul values
    as specified in the Yaml file found in the resources folder

    There is also a thread that when used in the GUI is based upon the QThread
    The other thread is retained in case someone else wants to use that approach.
    Regardless, the thread subscribes to new additions to the activeData item
    and processess it/displays it appropriately.  

    All other data are stored as their unique IDs and have the following format
    expData = [dataCode, numPnts, numAves, gpw, acqSpeed, filePath, acqType, multiplexParam, finished, data]
    
    0-dataCode -- the unique identifier for the file
    1-numPnts -- number of points across the spectrum
    2-numAves -- the number of times the data acquisition loop is repeated.  Keep in mind that the actual averaging needs to occur following the load.  The Wipy only does integer mathematics.
    3-gpw -- value of the gate pulse width in microseconds
    4-acqSpeed -- the time between each data point in microseconds
    5-freq
    6-filePath -- string to the path on the SD card for the future retrieval
    7-acqType -- 0 - Signal Averaged, 1 - Hadamard, 2 - Fourier, 3 or more is for future use
    8-multiplexParam -- if the acqType is above 0 then a special code to define the mechanisms will be in this field (TBD).
    9-data --- All of the data for the experiment

    One thing to consider then is how to consider peak picking once that is completed

    import uuid#This would be ideal but uuid is not implemented in python
    dataCode = uuid.uuid4()


    dataCode = uniqid()


    '''
    def __init__(self):
        '''
        More to be added later
        '''
        self.setupRedis(True)

    def setupRedis(self, getInfo = False):
        self.rdb = r.Redis('localhost')
        self.rdbOK = self.rdb.ping()

        print "Connection Status: ", self.rdbOK
        if self.rdbOK:
            print "DB Size: %s"%self.rdb.info()['used_memory_human']
        
            if getInfo:
                print "Connection Info: ", self.rdb.info()

    def cullDataEntires(self, targetMem=100000000.0):#limiting to 100MB 
        '''
        Currently only culls the memory for the keys that are store in the 
        activeData keys
        '''
        curMemory = self.rdb.info()['used_memory']#This is NOT the human memory and is in bytes.
        dataKeys = self.rdb.keys()#Need to have this return the list of daq arrays#might be able to kill
        while curMemory>=targetMem:
            lastKey = self.rdb.getkey()[-1]#This needs to be a list of keys for daq arrays
            poppedElement = self.rdb.rpop(lastKey)
            curMemory = self.rdb.info()['used_memory_human']

    def manageDaqFIFO(self, fifoLimit = 25, listKey = 'activeData'):
        activeDaqLen = self.rdb.llen(listKey)#daq fifo list length
        if activeDaqLen > fifoLimit:
            numIters = fifoLimit-activeDaqLimit#not sure if this will is off by one.
            for i in range(numIters):
                self.rdb.rpop(listKey)
        return self.rdb.lrange(listKey,0,-1)#return the full array which is 25

    def queryStatus(self):
        self.rdbOK = False
        self.rdbOK = self.rdb.ping()
        return self.rdbOK

    def dumpDB(self, fileName):
        try:
            jsonStr = redisdl.dumps(host='localhost', port=6379, encoding='utf-8', pretty=True)
            f = open(fileName, 'wb')
            f.write(zlib.compress(jsonStr, 9))
            f.close()
            '''
            http://stackoverflow.com/questions/1316357/zlib-decompression-in-python
            # imports and other superstructure left as a exercise
            str_object1 = open('my_log_file', 'rb').read()
            str_object2 = zlib.compress(str_object1, 9)
            f = open('compressed_file', 'wb')
            f.write(str_object2)
            f.close()
            To decompress a file:

            str_object1 = open('compressed_file', 'rb').read()
            str_object2 = zlib.decompress(str_object1)
            f = open('my_recovered_log_file', 'wb')
            f.write(str_object2)
            f.close()

            '''
        except OSError:
            print "DumpDB Error!!!!"
            print "%s not a valid path"%fileName# handle error here

    def getKeys(self):
        if self.rdbOK:
            existingKeys = self.rdb.keys()
            print "Existing Keys: "
            for k in existingKeys:
                print "\t%s"%k

    def clearDB(self):
        '''
        This will clear the database entirely--use with caution.
        '''
        if self.rdbOK:
            self.rdb.flushdb()
    
    def _testArray_(self):
        if self.rdbOK:
            arrayKey = 'dataArray'
            tempArray = N.arange(2000)
            for val in tempArray:
                    self.rdb.lpush(arrayKey, val)

            listStr = self.rdb.lrange(arrayKey,0,-1)
            dataArray = N.array(listStr, dtype = N.float)
            dataArray = dataArray[::-1]#reverse array
            print dataArray



class WIPY_DAQ(WIPYConnection):
    '''
    Not sure this is needed 
    # PARAMLIST = [dataCode, numPnts, numAves, gpw, acqSpeed, filePath, acqType, multiplexParam]
    
    dataCode -- the unique identifier for the file
    numPnts -- number of points across the spectrum
    numAves -- the number of times the data acquisition loop is repeated.  Keep in mind that the actual averaging needs to occur following the load.  The Wipy only does integer mathematics.
    gpw -- value of the gate pulse width in microseconds
    acqSpeed -- the time between each data point in microseconds
    freq -- acquisition frequency (Hz)
    filePath -- string to the path on the SD card for the future retrieval
    acqType -- 0 - Signal Averaged, 1 - Hadamard, 2 - Fourier, 3 or more is for future use
    multiplexParam -- if the acqType is above 0 then a special code to define the mechanisms will be in this field (TBD).
    finished -- -1 is no and 0 is yes
    data
    '''
    def __init__(self):
        super(WIPY_DAQ, self).__init__()
        print "Go Joe"

    def getData(self):
        print "Go Joe"

    def queryState(self):
        '''
        Ask if there is any data and if so return True
        Assumes there is 
        '''
        if self.rdbOK:
            print "Everything OK"

class Listener(threading.Thread):
    '''
    Thread class that does not rely upon PyQt4
    '''
    def __init__(self, r, channels):
        threading.Thread.__init__(self)
        self.redis = r
        self.pubsub = self.redis.pubsub()
        self.pubsub.subscribe(channels)
    
    def work(self, item):
        print item['channel'], ":", item['data']
    
    def run(self):
        for item in self.pubsub.listen():
            if item['data'] == "KILL":
                self.pubsub.unsubscribe()
                print self, "unsubscribed and finished"
                break
            else:
                self.work(item)

class RedisWindow(QtGui.QWidget):
    '''
    Basic example of how to link and subscribe via a thread to a redis queue
    '''
    def __init__(self, parent = None):
    
        QtGui.QWidget.__init__(self, parent)
        
        self.tabs = QtGui.QTabWidget(self)
        self.dataTab = QtGui.QWidget(self.tabs)
        self.redisTab = QtGui.QWidget(self.tabs)

        sendButton = QtGui.QPushButton(self.tr("Send line"))
        self.sendEdit = QtGui.QLineEdit(self)
        self.resultLabel = QtGui.QLabel(self.tr("..."))
        
        # New style: uses the connect method of a pyqtSignal object.
        self.connect(sendButton, QtCore.SIGNAL("clicked()"), self.handleClick)
        
        # Old style: uses the SIGNAL function to describe the signal.
        self.connect(self, QtCore.SIGNAL("sendValue(PyQt_PyObject)"), self.handleValue)
        
        self.rdb = r.Redis('localhost')
        self.client = ListenerQT(self.rdb, ['test'])
        self.connect(self.client, QtCore.SIGNAL('sendValue(PyQt_PyObject)'), self.postResult)

        layout = QtGui.QVBoxLayout(self)
        layout.addWidget(sendButton)
        layout.addWidget(self.sendEdit)
        layout.addWidget(self.resultLabel)

        self.tb = QtGui.QTextEdit(self)
        self.tb.setWindowTitle("Redis result")
        self.tb.setText("")
        layout.addWidget(self.tb)

        self.__startThread__()


    def __setupWIPY__(self):
        self.wipyCon = WIPY_DAQ()

    def postResult(self, postText):
        print type(postText)
        self.tb.clear()
        # self.tb.setText(str(postText))
        self.tb.append(str(postText))

    def __startThread__(self):
        # self.rdb.publish('test', 'this will reach the listener')
        # self.rdb.publish('fail', 'this will not')
        # self.rdb.publish('test', 'KILL')
        self.client.start()

    def handleClick(self):
    
        # Old style: emits the signal using the SIGNAL function.
        self.emit(QtCore.SIGNAL("sendValue(PyQt_PyObject)"), {"abc": 123})
    
    def handleValue(self, value):
        curText = str(self.sendEdit.text())
        self.rdb.publish('test', curText)
        self.sendEdit.clear()
        self.resultLabel.setText(curText)

    def closeEvent(self, event):
        self.rdb.publish('data', "KILL")#This will kill the thread safely.

class ListenerQT(QtCore.QThread):
    def __init__(self, rdb, channels, parent = None):
        QtCore.QThread.__init__(self)
        self.redis = rdb
        self.parent = parent
        self.pubsub = self.redis.pubsub()
        self.pubsub.subscribe(channels)
    
    def work(self, item):
        tempItem = item['data']
        print item['channel'], ":", item['data']
        self.emit(QtCore.SIGNAL('sendValue(PyQt_PyObject)'), tempItem)
    
    def run(self):
        for item in self.pubsub.listen():
            if item['data'] == "KILL":
                self.pubsub.unsubscribe()
                print self, "unsubscribed and finished"
                break
            else:
                self.work(item)

 
def uniqid(prefix=''):
    m = time.time()
    uniqid = '%8x%05x' %(math.floor(m),(m-math.floor(m))*1000000)
    uniqid = prefix + uniqid
    return uniqid

def processDataSegmented(rdb, dataID):
    '''
    rdb -- Redis database
    dataID -- unique key in redisDB that holds the raw data object
    It would be possible to push and pull values for this object as JSON dictionaries but not sure what the benefit might be...
    '''
    if not RDBKeyExists(rdb, dataID):
        print "The following data key was not found: %s"%dataID
        return False, False
    dataList = rdb.lrange(dataID, 0, -1)
    # dataList = dataList[::-1]#reverse array as it was pushed in rather than stacked
    #first elements are DAQ parameters
    tempData = dataList[9::]
    specData = []#ultimate array to store data
    for seg in tempData:
        seg = seg.strip("]")
        seg = seg.strip("[")
        seg = seg.split("\n")            
        for m in seg:
            m = m.split(' ')#get rid of spaces
            for n in m:
                if len(n)>1:#number string
                    specData.append(n)
    specData = N.array(specData, dtype = N.float)
    metaData = dataList[0:9]
    metaList = ['dataCode', 'numPnts', 'numAves', 'gpw', 'acqSpeed', 'freq', 'filePath', 'acqType', 'multiplexParam']
    metadtypes = [str, int, int, int, int, int, str, int, int]#not used but for clarity
    metaDict = {}
    for i,k in enumerate(metaList):
        if type(metaData) == int:

            metaDict[k] = int(metaData[i])
        else:
            metaDict[k] = metaData[i]

    return metaDict, specData


def processData(rdb, dataID):
    '''
    rdb -- Redis database
    dataID -- unique key in redisDB that holds the raw data object
    It would be possible to push and pull values for this object as JSON dictionaries but not sure what the benefit might be...
    '''
    if not RDBKeyExists(rdb, dataID):
        print "The following data key was not found: %s"%dataID
        return False, False
    dataList = rdb.lrange(dataID, 0, -1)
    # dataList = dataList[::-1]#reverse array as it was pushed in rather than stacked
    #first elements are DAQ parameters
    specData = N.array(dataList[9:-1], dtype = N.float)
    metaData = dataList[0:9]
    metaList = ['dataCode', 'numPnts', 'numAves', 'gpw', 'acqSpeed', 'freq', 'filePath', 'acqType', 'multiplexParam']
    metadtypes = [str, int, int, int, int, int, str, int, int]#not used but for clarity
    metaDict = {}
    for i,k in enumerate(metaList):
        if type(metaData) == int:

            metaDict[k] = int(metaData[i])
        else:
            metaDict[k] = metaData[i]

    return metaDict, specData

def pushDAQParams(rdb, rKey = 'daqParams', daqParams = DAQPARAMS, initialPush = False):
    '''
    daqParams is a dictionary with the following structure:
    daqParams = {}
    daqParams['numPnts'] = 1000
    daqParams['numAves'] = 100
    daqParams['gpw'] = 200
    daqParams['acqSpeed'] = 25
    daqParams['freq'] = 40000
    daqParams['acqType'] = 0
    daqParams['multiplexParam'] = 0 # this is for future use 

    Unless specified otherwise everything is an integer
    '''
    if initialPush:
        pushStr = json.dumps(daqParams)
        rdb.set(rKey, pushStr)

    if RDBKeyExists(rdb, rKey):
        pushStr = json.dumps(daqParams)
        rdb.set(rKey, pushStr)
        return True
    else:
        return False

def pullRedisJson(rdb, rKey):
    if RDBKeyExists(rdb, rKey):
        pullStr = rdb.get(rKey)
        pullObj = json.loads(pullStr)
    else:
        pullObj = None

    return pullObj

def RDBKeyExists(rdb, rKey):
    curKeys = rdb.keys()
    if len(curKeys)<1:
        print "Empty Redis DB"
        return False
    else:
        if rKey in curKeys:
            return True
        else:
            return False

def processDataJson(rdb, dataID):
    '''
    rdb -- Redis database
    dataID -- unique key in redisDB that holds the raw data object
    It would be possible to push and pull values for this object as JSON dictionaries but not sure what the benefit might be...
    '''
    if not RDBKeyExists(rdb, dataID):
        print "The following data key was not found: %s"%dataID
        return False
    dataDict = pullRedisJson(rdb, dataID)
    specData = dataDict['data'].split(",")#split and convert to list
    specData = N.array(specData, dtype = N.float)
    dataDict['data']=specData
    metaList = ['dataCode', 'numPnts', 'numAves', 'gpw', 'acqSpeed', 'freq', 'filePath', 'acqType', 'multiplexParam']
    metadtypes = [str, int, int, int, int, int, str, int, int]#not used but for clarity
    # metaDict = {}
    # for i,k in enumerate(metaList):
    #     if type(metaData) == int:

    #         metaDict[k] = int(metaData[i])
    #     else:
    #         metaDict[k] = metaData[i]

    return dataDict, specData

def generateDummyJsonData(rdb, numPnts=1000, numAves=10, gpw=200, acqSpeed=25, filePath='DUMMY', acqType=0, multiplexParam=-1, data = []):
    
    daqDict = DAQPARAMS
    dataID = uniqid()#generate unique ID for each run -- add feature to turn off autowrite?
    daqDict['dataCode'] = dataID
    filePath = dataID+'.json'
    daqDict['filePath'] = filePath
    
    data = N.loadtxt('Test_Data.txt')
    numPnts = len(data)
    daqDict['numPnts'] = numPnts
    tempRandom = N.random.randn(numPnts)
    tempRandom += 5#make most of them positive
    data *=tempRandom
    #This is ugly but makes things smoother later
    data = str(data.tolist())#convert to list then a string (Redis takes strings!)
    # print type(data)
    data = data.strip('[')#get rid of brackets
    data = data.strip(']')
    daqDict['data'] = data

    rdb.set(dataID, json.dumps(daqDict))

    rdb.lpush('activeData', dataID)
    #need to test the following line out. 

def generateDummyDataSegmented(redisDB, numPnts=1000, numAves=10, gpw=200, acqSpeed=25, freq = 40000, filePath='DUMMY', acqType=0, multiplexParam=-1, data = []):

    data = N.loadtxt('Test_Data.txt')
    numPnts = len(data)
    tempRandom = N.random.randn(numPnts)
    tempRandom += 5#make most of them positive
    data *=tempRandom
    dataID = uniqid()
    dataList = [dataID, numPnts, numAves, gpw, acqSpeed, freq, filePath, acqType, multiplexParam]
    for val in dataList:
        redisDB.rpush(dataID, val)

    j = 0#Break and send data (Not optimum but better than one by one)
    # print dataID
    for i in range(1+len(data)/100):
        tempData = data[j:j+100]
        # print "len tempData", len(tempData)
        redisDB.rpush(dataID, str(tempData))
        j+=100

    # for d in data:
    #     redisDB.rpush(dataID, d)

    redisDB.rpush('activeData', dataID)

    print "Complete with the following unique identifier: %s"%dataID
    return dataID


def generateDummyData(redisDB, numPnts=1000, numAves=10, gpw=200, acqSpeed=25, freq = 40000, filePath='DUMMY', acqType=0, multiplexParam=-1, data = []):

    data = N.loadtxt('Test_Data.txt')
    numPnts = len(data)
    tempRandom = N.random.randn(numPnts)
    tempRandom += 5#make most of them positive
    data *=tempRandom
    dataID = uniqid()
    dataList = [dataID, numPnts, numAves, gpw, acqSpeed, freq, filePath, acqType, multiplexParam]
    for val in dataList:
        redisDB.lpush(dataID, val)

    for d in data:
        redisDB.lpush(dataID, d)

    redisDB.lpush('activeData', dataID)

    print "Complete with the following unique identifier: %s"%dataID
    return dataID


if __name__ == "__main__": 

    #Test 1
    # curDB = WIPYConnection()
    # curDB._testArray_()
    
    #Test 2
    # wipyDAQ = WIPY_DAQ()
    # wipyDAQ._testArray_()


    #Test 3
    # rdb = r.Redis('localhost')
    # client = ListenerQT(rdb, ['test'])
    # client.start()
    # rdb.publish('test', 'this will reach the listener')
    # rdb.publish('fail', 'this will not')
    # rdb.publish('test', 'KILL')

    # Test #4 Generate Dummy Data
    rdb = r.Redis('localhost')
    rdb.flushdb()
    for i in xrange(5):
        time.sleep(0.100)
        # generateDummyJsonData(rdb)
        # generateDummyData(rdb)
        generateDummyDataSegmented(rdb)


    ## Plot Test
    # from matplotlib import pyplot as P
    # rdb = r.Redis('localhost')
    # dataList = rdb.lrange('activeData', 0, -1)
    # # for d in dataList:
    # d = dataList[0]
    # # metaDict, raw = processDataJson(rdb, d)
    # metaDict, raw = processDataSegmented(rdb, d)
    # print metaDict
    # print len(raw)
    # P.plot(raw)
    # P.show()
    
    ##Daq Param Testing
    # rdb = r.Redis('localhost')
    # # rdb.flushdb()
    # pushDAQParams(rdb, initialPush = True)
    # daqParams = pullRedisJson(rdb, 'daqParams')
    # print rdb.keys()
    # print daqParams 

    #Test #5
    # app = QtGui.QApplication(sys.argv)
    # window = RedisWindow()
    # window.show()
    # sys.exit(app.exec_())



    #Time #6
    # timer = QTimer()  # set up your QTimer
    # timer.timeout.connect(self.updateButtonCount)  # connect it to your update function
    # timer.start(5000)  # set it to timeout in 5000 ms


# def dumpSDCard 

# def setTrigger(self):
# '''
# How to set trigger to continue. 
# '''
# setIRQ to call the data acquisition loop

