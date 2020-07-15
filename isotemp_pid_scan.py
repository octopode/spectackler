#!/usr/bin/python3

"""
Script for semi-automated PID tuning
"""

import sys
import traceback
import time
import itertools
import numpy as np
import pandas as pd
from math import isclose
import isotemp6200 as isotemp

def product_dict(**kwargs):
    "Generator function lifted from https://stackoverflow.com/questions/5228158/cartesian-product-of-a-dictionary-of-lists"
    keys = kwargs.keys()
    vals = kwargs.values()
    for instance in itertools.product(*vals):
        yield dict(zip(keys, instance))

# all the parameters that will be combined to make test states
ranges = {
    "T_set"  : np.arange(5, 30.1, 5).tolist(),
    "Cp" : [1],
    "Ci" : np.arange(0, 1.1, 0.25).tolist(),
    "Cd" : np.arange(0, 1.1, 0.25).tolist(),
    "Hp" : [0.5],
    "Hi" : np.arange(0, 1.1, 0.25).tolist(),
    "Hd" : np.arange(0, 1.1, 0.25).tolist()
}

# calculate cartesian product of these ranges
states = pd.DataFrame(list(product_dict(**ranges)))
# sort for efficient transitions
states = states.sort_values(by=["T_set", "Cd", "Hd", "Ci", "Hi"], ascending=[False, True, True, True, True]).reset_index(drop=True)

print(states)

# number of oscillations to go through in each test state
num_osc = 3
# move on to next test state regardless of oscillation count
timeout = 1800

file_log = "/Applications/spectackler/20200714_t-log.tsv"

# open output file
with open(file_log, 'w') as hand_log:

    # write header
    hand_log.write("\t".join(["clock", "watch", "T_int", "T_ext"] + list(ranges.keys()))+'\n')
    hand_log.flush()
    
    # now we're opening serial connections, which need to be closed cleanly on exit
    try:
        # init water bath
        bath = isotemp.IsotempController(port="/dev/cu.usbserial-AL01M1X9")
        
        ## run experiment
        
        # start experiment timer (i.e. stopwatch)
        time_start = time.time()
        
        # start circulator
        while not bath.on():
            bath.on(True)
            
        # set precision
        while not bath.temp_prec(2):
            pass
        
        # iterate over test states
        for state in states.itertuples():
        
            oscs = 0
            state_start = time.time()
            
            print("state {}/{}:".format(state[0], states.shape[0]), file=sys.stderr)
            print(state[1:], file=sys.stderr)
            
            # set temp persistently
            while not isclose(bath.temp_set(), state._asdict()['T_set']):
                print("setpoint to {}".format(state._asdict()['T_set']), file=sys.stderr)
                bath.temp_set(temp_set)
                
            for drive in ('C', 'H'):
                print("{} to PID {}".format(drive, [state._asdict()[drive + 'p'], state._asdict()[drive + 'i'], state._asdict()[drive + 'd']]), file=sys.stderr)
                while not all(bath.pid(drive, state._asdict()[drive + 'p'], state._asdict()[drive + 'i'], state._asdict()[drive + 'd'])):
                    pass
            
            # data logging loop
            trace = [bath.temp_get_ext()] * 3
            peaks = []
            valleys = []
            while True:
                temp_int = bath.temp_get_int()
                temp_ext = bath.temp_get_ext()
                
                list_data = [
                    # date, clock time
                    time.strftime("%Y%m%d %H%M%S"),
                    # watch time
                    str(round(time.time() - time_start, 3)),
                    # temps
                    temp_int,
                    temp_ext
                ] + list(state[1:])
                line_data = '\t'.join([str(x) for x in list_data])
                hand_log.write(line_data+'\n')
                hand_log.flush()
                
                # if temp has changed, update trend
                if abs(temp_ext - trace[-1]) > 0.1:
                    trace = trace[1:] + [temp_ext]
                    
                if trace[0] < trace[1] > trace[2]:
                    peaks.append(trace[1])
                    # update trace
                    trace[2] = trace[1]
                elif trace[0] > trace[1] < trace[2]:
                    valleys.append(trace[1])
                    # update trace
                    trace[2] = trace[1]
                    
                oscs = min(len(peaks), len(valleys))
                
                # oscillation count bailout
                if oscs >= num_osc:
                    print("{} oscillations completed".format(oscs), file=sys.stderr)
                    break
                # time bailout
                elif (time.time() - state_start) > timeout:
                    print("timeout {} s reached after {} oscillations".format(timeout, oscs), file=sys.stderr)
                    break
                
        # shut down when done
        bath.on(False)
        bath.disconnect()

    except:
        bath.disconnect()
        traceback.print_exc()