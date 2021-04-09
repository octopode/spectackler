#!/usr/bin/python3

"PID tuning script, scans param at steady state."

temp_setp = 20.0
time_step = 3000 # 50 min/step

# start value and increment
#beg = 4
#n = 5
#inc = 0.5
#top = 5.0

file_log = "/Applications/spectackler/20210109_t-log_derivative=5_lowP.tsv"

import sys
import traceback
import time
import configparser
import numpy as np
from math import isclose
import isotemp6200 as isotemp

#parvals = [round(beg + (inc * x), 2) for x in range(int(top/inc))]
parvals = [0.1]
print("parameter values: " + str(parvals))

# open unbuffered output file
with open(file_log, 'a') as hand_log:

    # write header
    hand_log.write("\t".join(["t", "T_int", "T_ext", "p", "i", "d"])+'\n')
    hand_log.flush()
    
    # now we're opening serial connections, which need to be closed cleanly on exit
    try:
        # init water bath
        bath = isotemp.IsotempController(port="/dev/cu.usbserial-AL01M1X9")
        
        ## run experiment
        
        # start experiment timer (i.e. stopwatch)
        time_start = time.time()
        # initialize
        time_act = time_start
        
        # start circulator
        while not bath.on():
            bath.on(True)
            
        # enable external RTD
        while not bath.probe_ext():
            bath.probe_ext(True)
            
        # set temp
        while not bath.temp_set(temp_setp):
            bath.temp_set(temp_setp)
            
        for step, par in enumerate(parvals):
        
            # set parameters
            p = par
            i = 0
            d = 5
            for drive in ('H', 'C'):
                while not all(bath.pid(drive, p, i, d)):
                    pass
                    
            print(time.strftime("%H%M")+" - step "+str(step)+": PID = "+str((p,i,d)))
            
            # collect data
            while time_act < time_start + ((step+1) * time_step):
                
                # read values
                time_act = time.time()
                temp_int = bath.temp_get_int()
                temp_ext = bath.temp_get_ext()
                
                # log the data
                hand_log.write("\t".join([str(x) for x in [round(time_act, 3), temp_int, temp_ext, p, i, d]])+'\n')
                hand_log.flush()

        # shut down when done
        bath.on(False)
        bath.disconnect()

    except:
        bath.disconnect()
        traceback.print_exc()