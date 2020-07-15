#!/usr/bin/python3

"""
Bounce back and forth between min and max temperature setpoints,
logging process and reference temps all the way
"""

temp_lo = 5
temp_hi = 30
time_dwell = 1200

file_log = "/Applications/spectackler/20200713_t-cal.tsv"

import sys
import traceback
import time
import configparser
import numpy as np
from math import isclose
import isotemp6200 as isotemp

class QTIProbe:
    "Class for QTI 6001 USB temperature probe"
    def __init__(self, port, baud=9600, timeout=1):
        """
        Open serial interface, return fault status.
        The serial handle becomes a public instance object.
        """
        import serial
        self.__ser__ = serial.Serial(port=port, baudrate=baud, timeout=timeout)
        self.__ser__.flush()
        # initialize
        self.__ser__.write(b'0')
        self.__ser__.flush()
        
    def temp_get(self):
        "Return current temperature."
        self.__ser__.write(b'2')
        self.__ser__.flush()
        return float(self.__ser__.readline().decode().strip())

# open output file
with open(file_log, 'w') as hand_log:

    # write header
    hand_log.write("\t".join(["clock", "watch", "T_int", "T_ext", "T_ref"])+'\n')
    hand_log.flush()
    
    # now we're opening serial connections, which need to be closed cleanly on exit
    try:
        # init water bath
        bath = isotemp.IsotempController(port="/dev/cu.usbserial-AL01M1X9")
        nist = QTIProbe(port="/dev/cu.usbmodem606318311")
        
        ## run experiment
        
        # start experiment timer (i.e. stopwatch)
        time_start = time.time()
        
        # start circulator
        while not bath.on():
            bath.on(True)
            
        # set precision
        while not bath.temp_prec(2):
            pass
           
        # set slow action 
        for drive in ('H', 'C'):
            while not all(bath.pid(drive, 0.1, 0, 0)):
                pass
        
        # loop 'til stopped
        while True:
                
            # set lo temp persistently
            while not isclose(bath.temp_set(), temp_lo):
                bath.temp_set(temp_lo)
             
            dwell = False
            while True:
                temp_int = bath.temp_get_int()
                temp_ext = bath.temp_get_ext()
                temp_ref = nist.temp_get()
                line_data = '\t'.join([
                        # date, clock time
                        time.strftime("%Y%m%d %H%M%S"),
                        # watch time
                        str(round(time.time() - time_start, 3)),
                        # temperatures
                        str(temp_int),
                        str(temp_ext),
                        str(temp_ref)
                    ])
                hand_log.write(line_data+'\n')
                hand_log.flush()
                if (temp_ref <= temp_lo) and not dwell:
                    # start dwell
                    time_reach = time.time()
                    dwell = True
                if dwell and (time.time() - time_reach >= time_dwell):
                    break
                    
            # set hi temp persistently
            while not isclose(bath.temp_set(), temp_hi):
                bath.temp_set(temp_hi)
             
            dwell = False
            while True:
                temp_int = bath.temp_get_int()
                temp_ext = bath.temp_get_ext()
                temp_ref = nist.temp_get()
                line_data = '\t'.join([
                        # date, clock time
                        time.strftime("%Y%m%d %H%M%S"),
                        # watch time
                        str(round(time.time() - time_start, 3)),
                        # temperatures
                        str(temp_int),
                        str(temp_ext),
                        str(temp_ref)
                    ])
                hand_log.write(line_data+'\n')
                hand_log.flush()
                if (temp_ref >= temp_hi) and not dwell:
                    # start dwell
                    time_reach = time.time()
                    dwell = True
                if dwell and (time.time() - time_reach >= time_dwell):
                    break

    except:
        bath.disconnect()
        traceback.print_exc()