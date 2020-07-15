#!/usr/bin/python3

"""
isotemp_p-band_response.py

Track temperature response rate and overshoot in proportional mode.
v0.5 (c) JRW 2020 - jwinnikoff@mbari.org

GNU PUBLIC LICENSE DISCLAIMER:
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
"""

import sys
import traceback
import time
import configparser
import numpy as np
from math import isclose
import isotemp6200 as isotemp
import isco260D as isco

# wait time in s
delay = 1

def wait_for_setpt(func, setpt, tol, dur=0, rep=0):
    "Wait for return from func to stay within tolerance of setpoint for duration."
    print("waiting for stability...", file=sys.stderr)
    time_start = time.time()
    reps = 0
    while True:
    	val = func()
    	yield(val)
        if abs(val - setpt) < tol:
            if ((time.time() - time_start) >= dur) and (reps >= rep):
                print(file=sys.stderr)
                # once time and replicates are satisfied, bail out of the loop
                break
            print("n={} t={}: {}\r".format(reps, round(time.time() - time_start), val), end='', file=sys.stderr)
            reps += 1
        else: 
            # if out of tolerance, start over
            time_start = time.time()
            reps = 0

# read config data from stdin
config = configparser.RawConfigParser()
config.read_file(sys.stdin)

# generate parameter landscape
temps = np.arange(*[float(x) for x in (config["temps"]["min"], config["temps"]["max"], config["temps"]["step"])]).tolist()
press = np.arange(*[float(x) for x in (config["press"]["min"], config["press"]["max"], config["press"]["step"])]).tolist()
    
# open output data file
with open(config["files"]["data"], 'x') as file_data:
    
    # now we're opening serial connections, which need to be closed cleanly on exit
    try:
        # init water bath
        bath = isotemp.IsotempController(port=config["ports"]["bath"])
        
        # columns in the data table
        cols  = ("clock", "watch", "temp_set", "temp_act")
        # write header
        file_data.write('\t'.join(cols) + '\n')
        # start experiment timer (i.e. stopwatch)
        time_start = time.time()
        
        ## run experiment
        # start circulator
        while not bath.on():
            print("starting bath")
            bath.on(True)
        for temp in temps:
            # set temp persistently
            while not isclose(bath.temp_set(), temp):
                bath.temp_set(temp)
            print("temperature set to {}˚C".format(temp), file = sys.stderr)
            while True:
            	temp_act = bath.temp_get_ext()
            	line_data = '\t'.join([
            	    # date, clock time
            	    time.strftime("%Y%m%d %H%M%S"),
            	    # watch time
            	    str(time.time() - time_start),
            	    # setpoints
            	    str(temp),
            	    # actual conditions
            	    str(bath.temp_get_ext())
            	])
            	file_data.write(line_data + '\n')
    except:
        #bath.on(False)
        bath.disconnect()
        traceback.print_exc()