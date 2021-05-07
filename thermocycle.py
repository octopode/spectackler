#!/usr/bin/env python

#import __future__

"""
thermocycle.py

script to run waterbath through a temperature program (TSV from stdin)
while logging internal and external temperature to a file
v0.5 (c) JRW 2021 - jwinnikoff@mbari.org

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

from __future__ import print_function # supposed to be 2/3 compatible
input = raw_input
import os
import sys
import argparse
import serial # pip install pyserial
import time
import pandas as pd
import neslabrte as rte

from random import uniform

class FakeBath:
    "Test class for waterbath"
    def __init__(self, wayout=sys.stderr):
        self.wayout = wayout
        
    def temp_set(self, temp): 
        #print("setpoint to {}".format(temp), file=self.wayout)
        return True
        
    def temp_get_int(self):
        return round(uniform(2, 30), 1)
        
    # just an alias
    temp_get_ext = temp_get_int

def parse_args(argv):
    "Parse command line arguments. This script will also take a pre-generated TSV from stdin."
    
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    if not len(argv):
        argv.append("-h")
        
    parser.add_argument('-f', "--file_log", help="continuously written log of temp traces")
    parser.add_argument('-b', "--port_bath", help="device address of waterbath", default="COM13")
    parser.add_argument('-m', "--baud_bath", help="device address of waterbath", default=19200)
    parser.add_argument('-r', "--rate_poll", help="temp poll rate in s", default=1)
    parser.add_argument('-d', "--dummy",     help="use random gen in place of bath hardware", action="store_true")
    
    return parser.parse_args(argv)
    
def main(args, stdin, stdout, stderr):
    "Run temp scan and store output to file."
    
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
        print("ERR: you need to pass the state table on stdin!", file=stderr)
        exit(1)
        
    # open serial connection
    
    print("connecting...", file=stderr)
    print("temperature controller ", end='', file=stderr)
    if not args["dummy"]: bath = rte.NeslabController(port = args["port_bath"], baud = args["baud_bath"])
    else: bath = FakeBath() #TEST
    print("OK ", file=stderr)
    
    # open output file, do not overwrite!
    if os.path.exists(args['file_log']):
        print("ERR: logfile already exists!", file=stderr)
        exit(1)
    with open(args['file_log'], 'w') as hand_log:
    
        # variables tracking the expt schedule
        vars_sched = ["clock", "watch"]
        # externally measured and derived variables
        vars_measd = ["T_int", "T_ext"]
        # compose and write header - states.head() are the setpoint variables
        list_head = vars_sched + list(states.head()) + vars_measd
        line_head = "\t".join(list_head)
        hand_log.write(line_head + '\n')
        hand_log.flush()
        
        # start experiment
        sys.stdin = open('/dev/tty')
        input("ready - press ENTER to start")
        
        # start experiment timer (i.e. stopwatch)
        time_start = time.time()
        
        # iterate over test states
        for state_num in range(states.shape[0]):
        
            # make dict for this state
            this_state = states.iloc[state_num].to_dict()
            # init output dict
            data_dict = this_state
            
             # status update
            print("state {}/{}:".format(state_num+1, states.shape[0]), file=stderr)
            print(this_state, file=stderr)
            	
            # set the target temperature persistently
            while not bath.temp_set(this_state["T_set"]): pass
            
            # start counting down!
            time_step = time.time()
            while time_step + this_state["time"] - time.time() >= 0:
                time_cyc = time.time()
                # gather info
                data_dict.update(
                    {
                        "clock" : time.strftime("%Y%m%d %H%M%S"),
                        "watch" : time.time() - time_start,
                        "state" : state_num,
                        "T_int" : bath.temp_get_int(),
                        "T_ext" : bath.temp_get_ext(),
                    }
                )
                print(
                    "T_int: {}C\tT_ext: {}C\t{} s remaining        ".format(
                        data_dict["T_int"],
                        data_dict["T_ext"],
                        round(time_step + this_state["time"] - time.time())
                    ),
                    end='\r', file=stderr
                )
                # write to log
                hand_log.write('\t'.join([str(data_dict.get(col)) for col in list_head if data_dict.get(col) is not None])+'\n')
                while time.time() - time_cyc < args["rate_poll"] : pass
            # one last time
            print(
                    "T_int: {}C\tT_ext: {}C\t{} s remaining        ".format(
                        data_dict["T_int"],
                        data_dict["T_ext"],
                        0
                    ),
                    end='\r', file=stderr
                )
            print('', file=stderr)
    

if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    main(args, sys.stdin, sys.stdout, sys.stderr)
    