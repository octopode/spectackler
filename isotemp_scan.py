#!/usr/bin/python3

"""
Multipurpose script for calibrating or tuning an Isotemp-based temperature control system.
Steps through an ordered set of temperature setpoints and PID parameters.
Can interface with a reference thermometer whose temp_get() method is passed in.
"""

import sys
import argparse
from re import split
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
        
def parse_args(argv):
    "Parse command line arguments. This script will also take a pre-generated TSV from stdin."
    
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    if not len(argv):
        argv.append("-h")
        
    parser.add_argument('-f', "--file_log", help="continuously written log of temp, P, I, D traces")
    parser.add_argument('-p', "--port_isotemp", help="device address of isotemp waterbath", default="/dev/cu.usbserial-AL01M1X9")
    parser.add_argument('-T', "--range_T_set", help="temp min, max, step exclusive (pass in quotes)")
    parser.add_argument("--range_Cp", help="chiller proportional min, max, step exclusive (pass in quotes)", default = "1.0 1.1")
    parser.add_argument("--range_Ci", help="chiller integral min, max, step exclusive (pass in quotes)", default = "0.6 0.7")
    parser.add_argument("--range_Cd", help="chiller derivative min, max, step exclusive (pass in quotes)", default = "0.0, 0.1")
    parser.add_argument("--range_Hp", help="heater proportional min, max, step exclusive (pass in quotes)", default = "1.0 1.1")
    parser.add_argument("--range_Hi", help="heater integral min, max, step exclusive (pass in quotes)", default = "0.6 0.7")
    parser.add_argument("--range_Hd", help="heater derivative min, max, step exclusive (pass in quotes)", default = "0.0, 0.1")
    parser.add_argument('-r', "--scan_rank", help="list of arguments (pass in quotes) defining sort rank; rightmost parameter changes fastest", default="T_set Cp Ci Cd Hp Hi Hd")
    parser.add_argument('-a', "--scan_asc", help="list of booleans (pass in quotes) defining asc (True)/desc (False) sort order; parallels scan_rank", default=' '.join(["True"] * 7))
    parser.add_argument('-t', "--timeout", help="state args['timeout'] in seconds", type=int)
    parser.add_argument('-o', "--oscillations", help="if tuning PID, move on after n oscillations", type=int, default=50)
    
    # parse list args, i.e. strings containing spaces or commas
    args_dict = {}
    for key, val in vars(parser.parse_args(argv)).items():
        try:
            if (' ' in val) or (',' in val):
                args_dict[key] = [x for x in split("\s|,", val) if x != '']
                try:
                    args_dict[key] = [float(x) for x in args_dict[key]]
                except:
                    pass
            else:
                args_dict[key] = val
        except TypeError:
            # if arg not an iterable
            args_dict[key] = val
            pass
        
    return argparse.Namespace(**args_dict)
    
def main(args, stdin, stdout, stderr, aux=None):
    "Run a temperature/parameter scan and store output to a file. Aux is query method for an auxiliary sensor."
    
    # if args are passed as namespace, convert it to dict
    try:
        args = vars(args)
    except:
        pass
    
    if not stdin.isatty():
        # if a state table is passed on stdin, read it
        print("reading states from stdin", file=stderr)
        states = pd.read_csv(stdin, sep='\t')
    else:
        # generate state table from args
        ranges = {
            "T_set"  : np.arange(*args['range_T_set']).tolist(),
            "Cp" : np.arange(*args['range_Cp']).tolist(),
            "Ci" : np.arange(*args['range_Ci']).tolist(),
            "Cd" : np.arange(*args['range_Cd']).tolist(),
            "Hp" : np.arange(*args['range_Hp']).tolist(),
            "Hi" : np.arange(*args['range_Hi']).tolist(),
            "Hd" : np.arange(*args['range_Hd']).tolist()
        }
       
        # calculate cartesian product of these ranges
        states = pd.DataFrame(list(product_dict(**ranges)))
        # sort for efficient transitions
        # parameters on the right change faster
        #NTS 20200714 .iloc[::-1] reversal is #temporary, idk why ascending= doesn't work!
        states = states.sort_values(by=args['scan_rank'], ascending=args['scan_asc']).reset_index(drop=True).iloc[::-1]
        # print the generated table to stdout for records
        states.to_csv(stdout, sep='\t')
    
    ## run the experiment
    
    # open output file, do not overwrite!
    with open(args['file_log'], 'x') as hand_log:
    
        # compose and write header
        list_head = ["clock", "watch", "T_int", "T_ext"] + list(ranges.keys())
        # insert T_aux column if aux provided
        if aux:
            list_head.insert(4, "T_aux")
        line_head = "\t".join(list_head)
        hand_log.write(line_head + '\n')
        hand_log.flush()
        
        # now we're opening serial connections, which need to be closed cleanly on exit
        try:
            # init water bath
            bath = isotemp.IsotempController(args['port_isotemp'])
            
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
                
                print("state {}/{}:".format(state[0], states.shape[0]), file=stderr)
                print(state[1:], file=stderr)
                
                # set temp persistently
                while not isclose(bath.temp_set(), state._asdict()['T_set']):
                    print("setpoint to {}".format(state._asdict()['T_set']), file=stderr)
                    bath.temp_set(state._asdict()['T_set'])
                    
                for drive in ('C', 'H'):
                    print("{} to PID {}".format(drive, [state._asdict()[drive + 'p'], state._asdict()[drive + 'i'], state._asdict()[drive + 'd']]), file=stderr)
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
                    # insert T_aux column if aux provided
                    if aux:
                        list_head.insert(4, aux())
                    line_data = '\t'.join([str(x) for x in list_data])
                    hand_log.write(line_data+'\n')
                    hand_log.flush()
                    
                    # if temp has changed by 0.1˚C, update trend
                    if abs(temp_ext - trace[-1]) > 0.1:
                        trace = trace[1:] + [temp_ext]
                    
                    # oscillation counter
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
                    if oscs >= args['oscillations']:
                        print("{} oscillations completed".format(oscs), file=stderr)
                        break
                    # time bailout
                    elif (time.time() - state_start) > args['timeout']:
                        print("args['timeout'] {} s reached after {} oscillations".format(args['timeout'], oscs), file=stderr)
                        break
                    
            # shut down when done
            bath.on(False)
            bath.disconnect()
    
        except:
            bath.disconnect()
            traceback.print_exc()
            
if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    main(args, sys.stdin, sys.stdout, sys.stderr)