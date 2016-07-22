# WIPYDAQ
WIPY DAQ Control and GUI

This repository is aimed at collecting the code necessary to acquire and process data from the WIPY module (www.pycom.io).  The underlying WIPY code is aimed at setting a repeating timer executing an ADC function at a given frequency and filling a circular buffer.  Once the buffer is filled the callback to fill the buffer is set to "None" while the array and the DAQ parameters used are stored in a redis server running on the computer wirelessly connected to the WIPY unit.  If the redis server is not running the DAQ will still work, however, there will be no way to directly view the data (though it will be stored on the SD card).

A few things to note:

-The WIPY does not execute floating point notation. 
-A standard redis server must be running
-Redis setup can be achieved on most OS systems but those for Windows can be found in a separate distribution (http://redis.io/download).
-The ADC can only take a maximum of 1.8 V. You will need a voltage divider to scale the output from most standard amplifiers. IGNORE THIS AT YOUR PERIL!

TODO:
 
 -Currently the whole uredis distribution is loaded and consumes a fair bit of WIPY memory.  
