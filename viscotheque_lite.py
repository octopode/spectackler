#!/usr/bin/python3

from __future__ import print_function

"""
Follow a supplied temperature/pressure program,
logging process and reference temps all the way
"""
## ATTENTION: this script is set up for Windows

# the serial port to which the NESLAB waterbath is connected
bathport = "COM5"
pumpport = "COM6"

from os import getcwd
import sys
import traceback
import time
import numpy as np
import pandas as pd
import neslabrte111 as neslab
import isco260D as isco

#delay = 0.1 # approximate (overestimate) of sampling period in seconds
delay = 0.9 

# start a timestamped datalog file
file_log = getcwd() + r"\tplog_" + time.strftime("%Y%m%dT%H%M") + ".tsv"
        
if not sys.stdin.isatty():
    # if a state table is passed on sys.stdin, read it
    print("reading states from sys.stdin", file=sys.stderr)
    states = pd.read_csv(sys.stdin, sep='\t')
else:
    print("ERR: you need to pass the state table on sys.stdin!", file=sys.stderr)
    exit(1)

# open output file
with open(file_log, 'a+', buffering=1) as hand_log:

    # write header
    header = sorted(["clock", "watch", "temp_int", "temp_ext", "press_act"] + list(states.head()))
    hand_log.write('\t'.join(header) + '\n')
    
    # init water bath
    bath = neslab.NeslabController(port=bathport)

    # init ISCO pump
    pump = isco.ISCOController(port=pumpport,source=0,dest=1)
    pump.run()

    ## run experiment
    
    # start experiment timer (i.e. stopwatch)
    time_start = time.time()
    
    # iterate over test states
    for state_num in range(states.shape[0]):
    
        # make dicts for this state, the last, and the next
        state_curr = states.iloc[state_num+0].to_dict()
        print(state_curr) #TEST
        
        time_state = time.time()
        
        # set bath temperature persistently
        print("setting temp...", end="\r", file=sys.stderr)
        while not bath.temp_set(state_curr["temp_set"]): pass
        print("temp set to {} deg C".format(state_curr["temp_set"]), file=sys.stderr)

        # set pressure persistently
        print("setting press...", end="\r", file=sys.stderr)
        while not pump.press_set(state_curr["press_set"]): pass
        print("press set to {} bar".format(state_curr["press_set"]), file=sys.stderr)
        
        # log data for the prescribed period
        while time.time() - time_state < state_curr["time"]:
            while True: # persistent polling
                try:
                    data = {
                        "clock": time.strftime("%Y%m%d %H%M%S"), 
                        "watch": time.time() - time_start, 
                        "temp_int": bath.temp_get_int(),
                        "temp_ext": bath.temp_get_ext(),
                        "press_act": pump.press_get(),
                    }
                    break
                #except: pass
                except: print(traceback.format_exc())
            time.sleep(delay)
            data.update(state_curr) # add the command vars to the log
            hand_log.write('\t'.join([str(data[key]) for key in sorted(data.keys())]) + '\n')
            print("waiting {}/{} s".format(round(time.time()-time_state), data["time"]), file=sys.stderr, end='\r')
        
        print('', file=sys.stderr)
        
    # shut down hardware
    pump.stop()