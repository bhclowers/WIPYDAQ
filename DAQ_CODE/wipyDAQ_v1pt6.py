
import machine
from machine import Timer, Pin, ADC
import os, time
import array

import uredis as r
import json
import gc

#ToDo
#DAQ Trigger
#   Set callback to none
#LED for transfer
#Pause/Stop Trigger 
#   Is it a simply a matter of detaching the IRQ
#Better Unique ID Generator
#Error Logger
#Integrate calculator for frequency
#how to update the uniqueID and -- feature to turn off autowrite?
# ISR Routines:https://docs.pycom.io/wipy/reference/isr_rules.html
#https://forum.micropython.org/viewtopic.php?f=11&t=1793&hilit=handler&start=10

DAQPARAMKEY = 'daqParams'
DATAKEY = 'activeData'
#You need to know the IP of the computer running the redis server
RDB = r.Redis('192.168.1.2')#expecting the redis database to be running on the same network on your wifi connected device
INDEXVAL = 100

DAQPARAMS = {}
DAQPARAMS['numPnts'] = 1000
DAQPARAMS['numAves'] = 100
DAQPARAMS['gpw'] = 200
DAQPARAMS['acqSpeed'] = 25
DAQPARAMS['acqType'] = 0
DAQPARAMS['freq'] = 40000
DAQPARAMS['multiplexParam'] = 0 # this is for future use 
    
def pullRedisJson(rdb, rKey):
    pullStr = rdb.get(rKey)
    pullObj = json.loads(pullStr)
    return pullObj

def RDBKeyExists(rdb, rKey):
    '''
    This is not used at this time as it could be slow.
    '''
    curKeys = rdb.keys()
    if len(curKeys)<1:
        print("Empty Redis DB")
        return False
    else:
        if rKey in curKeys:
            return True
        else:
            return False

def uniqid(prefix=''):#this is not unique enough--need to reevalute
    m = time.time()
    # uniqid = '%8x%05x' %(math.floor(m),(m-math.floor(m))*1000000)
    uniqid = '%8x%05x'%((m,1))
    uniqid = prefix + uniqid
    return uniqid


class Trigger_Monitor(object):
    '''
    Is there a way to change the callback?
    '''
    def __init__(self):
        #        OUTPUT/INPUT
        self.pins = ['GP16', 'GP13']
        self.outputPin = Pin(self.pins[0], mode=Pin.OUT, value=1)
        self.inputPin = Pin(self.pins[1], mode=Pin.IN, pull=Pin.PULL_UP)

        self.triggerCount = 0
        self._triggerType_ = Pin.IRQ_RISING
        self.inputIRQ = self.inputPin.irq(trigger=self._triggerType_, handler=self.pinHandler)
        self.irqState = True

    def toggleInput(self, time_ms = 5):
        self.outputPin.toggle()
        time.sleep_ms(time_ms)

    def pinHandler(self, pin_o):
        # global self.pin_irq_count_trigger
        # global self.pin_irq_count_total
        # self._triggerType_
        # if self._triggerType_ & self.inputIRQ.flags():
        #     self.pin_irq_count_trigger += 1
        self.triggerCount += 1 

    def getTriggerCount(self):
        print("Trigger Count: ", self.triggerCount)

    def resetTriggerCount(self):
        self.triggerCount = 0

    def disableIRQ(self):
        self.irqState = machine.disable_irq() # Start of critical section

    def reEnableIRQ(self):
        machine.enable_irq(True)
        self.irqState=True

class DAQ_Unit(object):
    def __init__(self):#, freqVal=10000, numpnts = 1000):
        if RDB.ping():
            self.daqDict = pullRedisJson(RDB, DAQPARAMKEY)
            gc.collect()
        else:
            self.daqDict = DAQPARAMS
        self.setDaqParams()
        self.curPos = 0
        self.setupADC()
        self.setupTimer()

    def updateDaqParams(self):
        if RDB.ping():
            self.daqDict = pullRedisJson(RDB, DAQPARAMKEY)
            gc.collect()
        else:
            print("Redis DAQ Param Pull Failed\n\tReverting to defaults...")
        self.setDaqParams()

    def setDaqParams(self):
        self.gpw = self.daqDict['gpw']
        self.numPnts = self.daqDict['numPnts']
        self.acqSpeed = self.daqDict['acqSpeed']
        self.freq = self.daqDict['freq']#40000#1//(self.acqSpeed*1000)#acqSpeed is in microseconds
        self.acqType = self.daqDict['acqType']
        self.numAves = self.daqDict['numAves']
        self.multiplexParam = self.daqDict['multiplexParam']
        self.dataArray = array.array('H', range(self.numPnts))#initialize data array
        self.dataID = uniqid()
        self.daqDict['dataCode'] = self.dataID
        self.filePath = self.dataID+'.txt'
        self.daqDict['filePath'] = self.filePath
        self.daqDict['data'] = self.dataArray
        gc.collect()

    def pushData(self, writeSD = False):
        t = time.time()
        RDB.rpush(self.dataID, self.dataID)
        RDB.rpush(self.dataID, self.numPnts)
        RDB.rpush(self.dataID, self.numAves)
        RDB.rpush(self.dataID, self.gpw)
        RDB.rpush(self.dataID, self.acqSpeed)
        RDB.rpush(self.dataID, self.freq)
        RDB.rpush(self.dataID, self.filePath)
        RDB.rpush(self.dataID, self.acqType)
        RDB.rpush(self.dataID, self.multiplexParam)
        print(time.time()-t)
        j = 0#Break and send data (Not optimum but better than one by one)
        for i in range(1+len(self.dataArray)//INDEXVAL):
            RDB.rpush(self.dataID, str(self.dataArray[j:j+INDEXVAL]))
            j+=INDEXVAL
        RDB.rpush('activeData', self.dataID)
        if writeSD:
            self.writeData()
        gc.collect()
        print("Push Time")
        t = time.time()-t
        print(t)

    def stopTimer(self):
        self.tim.deinit()

    def setupTimer(self):
        '''
        Need to look at the following:
        But how to average? (Do we need two buffers)
        http://docs.micropython.org/en/latest/pyboard/library/pyb.ADC.html
        '''
        #How to stop timer?
        self.tim = Timer(0, mode = Timer.PERIODIC, width = 32)#what is this width? Timer resolution?
        self.timChannel = self.tim.channel(Timer.A, freq = self.freq)
        #What is the function of the trigger, do we need to implement external vs internal?
        self.timChannel.irq(handler=self._addData_, trigger = Timer.TIMEOUT)

    def setupADC(self):
        self.adc = ADC()
        self.adcPin = self.adc.channel(pin = 'GP3')

    def _addData_(self, timer, saveData = False):
        self.dataArray[self.curPos] = self.adcPin()
        self.curPos+=1
        self.curPos%=self.numPnts#this value can ultimately help us with the number of aves.
        
    def writeData(self):
        t = time.time()
        curDir = os.getcwd()
        os.chdir("/sd")#change directory to SD card
        try:
            f = open(self.filePath, 'w')
            # json.dump(self.daqDict, f)#assumes the data has already been converted to a string-Redis doesn't like arrays
            f.write("%s\n"%self.dataID)
            f.write("%s\n"%str(self.numPnts))
            f.write("%s\n"%str(self.numAves))
            f.write("%s\n"%str(self.gpw))
            f.write("%s\n"%str(self.acqSpeed))
            f.write("%s\n"%str(self.freq))
            f.write("%s\n"%self.filePath)
            f.write("%s\n"%str(self.acqType))
            f.write("%s\n"%str(self.multiplexParam))
            for d in self.dataArray:
                f.write("%s,\n"%str(d))
            f.close()
            os.chdir(curDir)
        except:
            os.chdir(curDir)
            print("Saving to %s failed"%fileName)
        gc.collect()
        print("Write Time: %s"%(time.time()-t))

print(gc.mem_free())
daq = DAQ_Unit()
print("Go ADC!")
# daq.writeData()
# print("Done with ADC")