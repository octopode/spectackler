#!/usr/bin/python3

"""
viscotheque.py

Collect fluorescence data at intervals across a temperature-pressure landscape.
The landscape is provided as a TSV via stdin, or from command-line args.
v0.9 (c) JRW 2020 - jwinnikoff@mbari.org

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
import argparse
from re import split
import traceback
import time
import itertools
import numpy as np
import pandas as pd
from math import isclose
import isotemp6200
import isco260D
import rf5301

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
    parser.add_argument('-b', "--port_bath", help="device address of isotemp waterbath", default="/dev/cu.usbserial-AL01M1X9")
    parser.add_argument('-p', "--port_pump", help="device address of ISCO syringe pump", default="/dev/cu.usbserial-FTV5C58R1")
    parser.add_argument('-s', "--port_spec", help="device address of RF5301 fluorospec", default="/dev/cu.usbserial-FTV5C58R0")
    parser.add_argument('-T', "--range_T", help="temperature min, max, step exclusive (pass in quotes)")
    parser.add_argument('-P', "--range_P", help="pressure min, max, step exclusive (pass in quotes)")
    parser.add_argument('-x', "--wl_ex", help="list of excitation wavelengths (pass in quotes)")
    parser.add_argument('-m', "--wl_em", help="list of emission wavelengths (pass in quotes)")
    parser.add_argument('-r', "--scan_rank", help="list of arguments (pass in quotes) defining sort rank; rightmost parameter changes fastest", default="T_set, P_set, wl_em, wl_ex")
    parser.add_argument('-a', "--scan_asc", help="list of booleans (pass in quotes) defining asc (True)/desc (False) sort order; parallels scan_rank", default=' '.join(["True"] * 7))
    parser.add_argument('-t', "--time_set", help="how long conditions must be stable for (s)", type=int, default=60)
    parser.add_argument("--vars_set", help="list of parameters (pass in quotes) that require equilibration", default="T_set, P_set")
    parser.add_argument("--tol_T", help="Temperature tolerance (˚C)", type=float, default=0.1)
    parser.add_argument("--tol_P", help="Pressure tolerance (˚bar)", type=float, default=1)
    parser.add_argument('-n', "--n_read", help="Number of fluor readings to take per state", type=int, default=3)
    parser.add_argument('-d', "--auto_shut", help="Auto-shutter/dark mode: only open the shutter for readings", type=bool, default=True)
    parser.add_argument('-V', "--vol_diff", help="Max allowed volume change for the pressure system (mL)", type=int, default=20)
    
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

def main(args, stdin, stdout, stderr):
    "Run a temperature/parameter scan and store output to a file."
    
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
            "T_set"     : np.arange(*args['range_T']).tolist(),
            "P_set"     : np.arange(*args['range_P']).tolist(),
            "wl_ex" : np.arange(*args['wl_ex']).tolist(),
            "wl_em" : np.arange(*args['wl_em']).tolist(),
        }
       
        # calculate cartesian product of these ranges
        states = pd.DataFrame(list(product_dict(**ranges)))
        # sort for efficient transitions
        # parameters on the right change faster
        states = states.sort_values(by=args['scan_rank'], ascending=args['scan_asc']).reset_index(drop=True)
        # print the generated table to stdout for records
        states.to_csv(stdout, sep='\t')
    
    ## run the experiment
    
    # open output file, do not overwrite!
    with open(args['file_log'], 'x') as hand_log:
    
        # compose and write header
        list_head = ["clock", "watch"] + list(states.head()) + ["T_int", "T_ext", "P_act", "intensity"]
        line_head = "\t".join(list_head)
        hand_log.write(line_head + '\n')
        hand_log.flush()
        
        # now we're opening serial connections, which need to be closed cleanly on exit
        try:
            # init instruments
            print("connecting...", file=stderr)
            bath = isotemp6200.IsotempController(port=args['port_bath'])
            print("√ temperature controller", file=stderr)
            pump = isco260D.ISCOController(port=args['port_pump'])
            print("√ pressure controller", file=stderr)
            spec = rf5301.RF5301(port=args['port_spec'])
            print("√ fluorospectrometer", file=stderr)
            
            # start bath circulator
            while not bath.on():
                bath.on(True)
            # set precision
            while not bath.temp_prec(2):
                pass
                
            # clear and start pump
            while not pump.remote():
                pass
            while not pump.clear():
                pass
            while not pump.run():
                pass
                
            # open the shutter, unless in auto
            if not args["auto_shut"]:
                while not spec.shutter(True):
                    pass
            
            ## run experiment
            
            # start experiment timer (i.e. stopwatch)
            time_start = time.time()
            
            # get initial volume
            vol_start = False
            while not vol_start:
                vol_start = pump.vol_get()
        
            list_data = [0]*10
            
            # iterate over test states
            for state_num in range(states.shape[0]):
            
                # make dicts for this state, the last, and the next
                # takes about 1 ms
                state_curr = states.iloc[state_num+0].to_dict()
                if state_num: 
                    state_prev = states.iloc[state_num-1].to_dict()
                else:
                    # if first state
                    state_prev = {key: 0 for key in state_curr.keys()}
                    chg_prev = {key: True for key in state_curr.keys()}
                if state_num < states.shape[0]:
                    state_next = states.iloc[state_num+1].to_dict()
                else:
                    # if final state
                    state_prev = {key: 0 for key in state_curr.keys()}
                    chg_next = {key: True for key in state_curr.keys()}
                
                # which params have changed since previous state?
                chg_prev = {key: (state_curr[key] != state_prev[key]) for key in state_curr.keys()}
                chg_next = {key: (state_curr[key] != state_next[key]) for key in state_curr.keys()}
                
                time_state = time.time() # mark time
                waited = False # did the state have to wait for stability?
                readings = 0 # reset n counter
                
                # status update
                print("state {}/{}:".format(state_num, states.shape[0]), file=stderr)
                print(state_curr, file=stderr)
                
                # set temp persistently
                while not isclose(bath.temp_set(), state_curr['T_set']):
                    print("setting temperature to {}˚C".format(state_curr['T_set']), file=stderr, end=' ')
                    if bath.temp_set(state_curr['T_set']): print('√', file=stderr)
                
                # set pres persistently
                while not isclose(pump.press_set(), state_curr['P_set']):
                    print("setting pressure to {} bar".format(state_curr['P_set']), file=stderr, end=' ')
                    if pump.press_set(state_curr['P_set']): print('√', file=stderr)
                    
                ## set the excitation wavelength
                #while not isclose(spec.ex_wl(), state_curr['wl_ex']):
                #    print("setting excitation WL to {} nm".format(state_curr['wl_ex']), file=stderr, end=' ')
                #    if spec.ex_wl(state_curr['wl_ex']): print('√', file=stderr)
                #    
                ## set the excitation wavelength
                #while not isclose(spec.em_wl(), state_curr['wl_em']):
                #    print("setting emission WL to {} nm".format(state_curr['wl_em']), file=stderr, end=' ')
                #    if spec.ex_wl(state_curr['wl_em']): print('√', file=stderr)
                
                # temporary WL setters
                # Persistence implemented over cycles to improve efficiency;
                # note that this checks the previous data row.
                #NTS 20200719 reimplement list_data as a dict!!!
                if not ((state_curr['wl_ex'] == list_data[4]) and (state_curr['wl_em'] == list_data[5])):
                    if (state_curr['wl_ex'] == 340) and (state_curr['wl_em'] == 440):
                        print("setting wavelengths to Laurdan blue", file=stderr, end=' ')
                        if spec.wl_set_laurdan_blu(): print('√', file=stderr)
                    elif (state_curr['wl_ex'] == 340) and (state_curr['wl_em'] == 490):
                        print("setting wavelengths to Laurdan red", file=stderr, end=' ')
                        if spec.wl_set_laurdan_red(): print('√', file=stderr)
                
                # init a log table for the state
                trails = pd.DataFrame(columns = list_head)
                
                # data logging loop
                while True:
                
                    time_cycle = time.time()
                
                    # SAFETY FIRST!
                    # check for pressure system leak
                    vol_now = pump.vol_get()
                    if vol_now:
                        if (vol_now - vol_start) > args["vol_diff"]:
                            raise Exception("Pump has discharged > {} mL!".format(args["vol_diff"]))
                            
                    print("leak check: {} s".format(round(time.time()-time_cycle, 3)))
                    time_cycle = time.time()
                
                    # DATA SECOND
                    # can I parallelize this somehow?
                    list_data = [
                        time.strftime("%Y%m%d %H%M%S"), # clock time
                        round(time.time() - time_start, 3), # watch time
                        state_curr['T_set'], # T_set
                        state_curr['P_set'], # P_set
                        spec.ex_wl(), # wl_ex
                        spec.em_wl(), # wl_em
                        bath.temp_get_int(), # T_int
                        bath.temp_get_ext(), # T_ext
                        pump.press_get(), # P_act
                        spec.fluor_get() # intensity
                    ]
                    
                    print("data poll: {} s".format(round(time.time()-time_cycle, 3)))
                    time_cycle = time.time()
                    
                    # write data to file
                    hand_log.write('\t'.join([str(x) for x in list_data])+'\n')
                    hand_log.flush()
                    
                    print("data write: {} s".format(round(time.time()-time_cycle, 3)))
                    time_cycle = time.time()
                    
                    # put data in the temporary trailing DF
                    trails = trails.append({key: val for key, val in zip(list_head, list_data)}, ignore_index=True)
                    # cut the DF down to within the trailing time
                    trails = trails[trails['watch'] >= trails['watch'].iloc[-1] - args["time_set"]]
                        
                    print("tracking: {} s".format(round(time.time()-time_cycle, 3)))
                    time_cycle = time.time()
                        
                    # control the air system
                    # conditionals minimize queries to pump
                    temp_condense = 24
                    if trails['T_ext'].iloc[-1] < temp_condense:
                        # if it's cold
                        if (trails.shape[0] < 2):
                            # and a new state
                            if not pump.digital(0):
                                print("turning air ON", end=' ', file=stderr)
                                if pump.digital(0, 1): print("√", file=stderr)
                        elif trails['T_ext'].iloc[-2] > temp_condense > trails['T_ext'].iloc[-1]:
                            # and it wasn't cold a second ago
                            print("turning air ON", end=' ', file=stderr)
                            if pump.digital(0, 1): print("√", file=stderr)
                    else:
                        # if it's warm
                        if (trails.shape[0] < 2):
                            # and a new state
                            if pump.digital(0):
                                print("turning air OFF", end=' ', file=stderr)
                                if pump.digital(0, 0): print("√", file=stderr)
                        elif trails['T_ext'].iloc[-2] < temp_condense < trails['T_ext'].iloc[-1]:
                            print("turning air OFF", end=' ', file=stderr)
                            if pump.digital(0, 0): print("√", file=stderr)
                            
                    print("air control: {} s".format(round(time.time()-time_cycle, 3)))
                    time_cycle = time.time()
                    
                    if any([chg_prev[var] for var in args["vars_set"]]):
                        # if any of the slow params have changed from last state
                        # with requisite stability in range,
                        
                        #NTS 20200719: It would be nice to abstract pressure and temp stability!
                        try:
                            temp_in_range = ((max(trails["T_int"]) <= state_curr["T_set"] + args["tol_T"]) and (min(trails["T_int"]) >= state_curr["T_set"] - args["tol_T"]))
                            pres_in_range = ((max(trails["P_act"]) <= state_curr["P_set"] + args["tol_P"]) and (min(trails["P_act"]) >= state_curr["P_set"] - args["tol_P"]))
                        except:
                            # in case the dataframe is Empty
                            temp_in_range = False
                            pres_in_range = False
                            pass
                    else:
                        temp_in_range = True
                        pres_in_range = True
                        
                    print("stability check: {} s".format(round(time.time()-time_cycle, 3)))
                    time_cycle = time.time()
                    
                    if temp_in_range and pres_in_range:
                        if waited: print(file=stderr) # newline
                        waited = False
                        
                        # open the shutter
                        if (not readings) and args["auto_shut"] and any([chg_prev[var] for var in args["vars_set"]]): 
                            while not spec.shutter(True):
                                pass
                        # take some readings
                        if readings: print("reading {}: {} AU\r".format(readings, trails['intensity'].iloc[-1]), end='', file=stderr)
                        readings += 1
                        # break out of loop to next state
                        if (readings > args["n_read"]):
                            if args["auto_shut"] and any([chg_next[var] for var in args["vars_set"]]):
                                while not spec.shutter(False):
                                    pass
                            print(file=stderr)
                            break
                            
                        print("n counter: {} s".format(round(time.time()-time_cycle, 3)))
                        time_cycle = time.time()
                    else:
                        # what are we waiting for?
                        print("waiting {} s to get {} s of stability\r".format(round(time.time()-time_state), args["time_set"]), end='', file=stderr)
                        waited = True
                    
            # shut down when done
            pump.clear()
            pump.disconnect()
            bath.on(False)
            bath.disconnect()
    
        except:
            pump.pause()
            spec.shutter(False)
            traceback.print_exc()
            
if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    main(args, sys.stdin, sys.stdout, sys.stderr)