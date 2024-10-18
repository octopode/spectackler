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
from collections import deque
import threading
from math import isclose
import isotemp6200
import isco260D
import rf5301
from serial.serialutil import SerialException

def product_dict(**kwargs):
    "Generator function lifted from https://stackoverflow.com/questions/5228158/cartesian-product-of-a-dictionary-of-lists"
    keys = kwargs.keys()
    vals = kwargs.values()
    for instance in itertools.product(*vals):
        yield dict(zip(keys, instance))
        
# Hacky temp calibration functions!
def temp_ext2int(temp_ext):
    "Predict bath internal RTD setpoint to achieve passed external RTD temperature"
    # From calibration sweeps 20200716
    return (temp_ext * 1.312841332) - 6.295898744
    
def temp_ext2act(temp_ext):
    "Predict actual cuvette temperature from external RTD measurement"
    # From calibration sweeps 20200714
    return (temp_ext * 1.18052628) - 3.199902021
    
def temp_act2ext(temp_act):
    "Predict external RTD measurement for passed target cuvette temperature"
    # From calibration sweeps 20200714
    return (temp_act + 3.199902021) / 1.1805262
    
def poll(dev, free, meas):
    while True:
        try:
            "Poll the passed device all at once. Free is a threading.Event, meas a deque"
            free.wait()
            devclass = dev.__class__.__name__
            if devclass == "IsotempController":
                temp_ext = dev.temp_get_ext()
                vals_dict = {
                    "T_int" : dev.temp_get_int(),
                    "T_ext" : temp_ext,
                    "T_act" : temp_ext2act(temp_ext)
                }
            elif devclass == "ISCOController":
                vals_dict = {
                    "vol"   : dev.vol_get(),
                    "P_act" : dev.press_get(),
                    "air"   : dev.digital(0)
                }
            elif devclass == "RF5301":
                vals_dict = {
                    "intensity" : dev.fluor_get(),
                    "wl_ex"     : dev.ex_wl(),
                    "wl_em"     : dev.em_wl()
                }
            meas.append(vals_dict)
        except SerialException:
            print("{} has been disconnected".format(dev.__ser__))
            # do anything else?
        
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
    parser.add_argument('-e', "--eq_min", help="minimum equilibration time (s)", type=int, default=60)
    parser.add_argument('-t', "--eq_max", help="maximum equilibration time/state timeout (s)", type=int, default=600)
    parser.add_argument("--vars_eq", help="list of parameters (pass in quotes) that require equilibration", default="T_set, P_set")
    parser.add_argument("--tol_T", help="Temperature tolerance (˚C)", type=float, default=0.05)
    parser.add_argument("--tol_P", help="Pressure tolerance (˚bar)", type=float, default=1)
    parser.add_argument("--dewpoint", help="Chamber temperature at which windows will fog (˚C)", type=float, default=12)
    parser.add_argument("--air_saver", help="Save air during long transitions?", type=bool, default=True)
    parser.add_argument("--air_time", help="Time it takes the windows to defog (s)", type=int, default=20)
    parser.add_argument('-n', "--n_read", help="Number of fluor readings to take per state", type=int, default=5)
    parser.add_argument('-c', "--cyc_time", help="Read cycle time in ms", type=int, default=100)
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
        list_head = ["clock", "watch", "state"] + list(states.head()) + ["T_int", "T_ext", "T_act", "P_act", "intensity"]
        line_head = "\t".join(list_head)
        hand_log.write(line_head + '\n')
        hand_log.flush()
        
        # now we're opening serial connections, which need to be closed cleanly on exit
        try:
            # init instruments
            print("connecting...", file=stderr)
            bath = isotemp6200.IsotempController(port=args['port_bath'])
            print("temperature controller √", file=stderr)
            pump = isco260D.ISCOController(port=args['port_pump'])
            print("pressure controller    √", file=stderr)
            spec = rf5301.RF5301(port=args['port_spec'])
            print("fluorospectrometer     √", file=stderr)
            
            ## hardware init
            print("starting...", file=stderr)
            # start bath circulator
            print("bath", end=' ', file=stderr)
            # set precision
            prec_bath = 2 # number of decimal places
            while not bath.temp_prec(prec_bath):
                pass
            while not bath.on():
                bath.on(True)
            print('√', file=stderr)
                
            # clear and start pump
            print("pump", end=' ', file=stderr)
            while not pump.remote():
                pass
            while not pump.clear():
                pass
            while not pump.run():
                pass
            # get initial volume
            vol_start = False
            while not vol_start:
                vol_start = pump.vol_get()
            print("√ V0 = {} mL".format(vol_start), file=stderr)
                
            # open the shutter, unless in auto
            if not args["auto_shut"]:
                while not spec.shutter(True):
                    pass
            
            # declare async queues
            queue_bath = deque(maxlen=1)
            queue_pump = deque(maxlen=1)
            queue_spec = deque(maxlen=1)
            
            # start polling threads
            # all device instances have RLocks!
            bath_free = threading.Event()
            pump_free = threading.Event()
            spec_free = threading.Event()
            [event.set() for event in (bath_free, pump_free, spec_free)]
            threading.Thread(name="pollbath", target=poll, args=(bath, bath_free, queue_bath)).start()
            threading.Thread(name="pollpump", target=poll, args=(pump, pump_free, queue_pump)).start()
            threading.Thread(name="pollspec", target=poll, args=(spec, spec_free, queue_spec)).start()
            
            ## run experiment
            
            # start experiment timer (i.e. stopwatch)
            time_start = time.time()
            
            time_air_tot = 0
            save_air = True
        
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
                if state_num < states.shape[0]-1:
                    state_next = states.iloc[state_num+1].to_dict()
                else:
                    # if final state
                    state_next = {key: 0 for key in state_curr.keys()}
                    chg_next = {key: True for key in state_curr.keys()}
                
                # which params have changed since previous state?
                chg_prev = {key: (state_curr[key] != state_prev[key]) for key in state_curr.keys()}
                chg_next = {key: (state_curr[key] != state_next[key]) for key in state_curr.keys()}
                
                time_state = time.time() # mark time
                waited = False # did the state have to wait for stability?
                readings = 0 # reset n counter
                
                # status update
                print("state {}/{}:".format(state_num+1, states.shape[0]), file=stderr)
                print(state_curr, file=stderr)
                
                # set temp persistently
                # this is the actual setpoint passed to the waterbath
                temp_set = round(temp_ext2int(temp_act2ext(state_curr['T_set'])), prec_bath)
                temp_tol = round(args['tol_T'] / 1.18052628 * 1.312841332, prec_bath)
                bath_free.clear()
                while not isclose(bath.temp_set(), temp_set):
                    print("setting temperature to {}˚C".format(state_curr['T_set']), file=stderr, end=' ')
                    if bath.temp_set(temp_set): print('√', file=stderr)
                bath_free.set()
                
                # set pres persistently
                pump_free.clear()
                while not isclose(pump.press_set(), state_curr['P_set']):
                    print("setting pressure to {} bar".format(state_curr['P_set']), file=stderr, end=' ')
                    if pump.press_set(state_curr['P_set']): print('√', file=stderr)
                pump_free.set()
                    
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
                    spec_free.clear()
                    if (state_curr['wl_ex'] == 340) and (state_curr['wl_em'] == 440):
                        print("setting wavelengths to Laurdan blue", file=stderr, end=' ')
                        if spec.wl_set_laurdan_blu(): print('√', file=stderr)
                    elif (state_curr['wl_ex'] == 340) and (state_curr['wl_em'] == 490):
                        print("setting wavelengths to Laurdan red", file=stderr, end=' ')
                        if spec.wl_set_laurdan_red(): print('√', file=stderr)
                    spec_free.set()
                
                # init a log table for the state
                trails = pd.DataFrame(columns = list_head)
                
                # data logging loop
                data_dict = {}
                # init the data dict. Persistent the first time.
                for dq in (queue_bath, queue_pump, queue_spec):
                    while True:
                        # ensure that *something* gets popped out so the dict is complete
                        try:
                            data_dict.update(dq.popleft())
                            break
                        except:
                            pass
                                
                while True:
                
                    time_cycle = time.time()
                    
                    # DATA FIRST
                    for dq in (queue_bath, queue_pump, queue_spec):
                        try:
                            data_dict.update(dq.popleft())
                            break
                        except:
                            pass
                    # add internal data
                    data_dict.update(
                        {
                            "clock" : time.strftime("%Y%m%d %H%M%S"),
                            "watch" : time.time() - time_start,
                            "state" : state_num,
                            "T_set" : state_curr["T_set"],
                            "P_set" : state_curr["P_set"],
                            #"wl_ex" : state_curr["wl_ex"],
                            #"wl_em" : state_curr["wl_em"]
                        }
                    )
                    # round off the modeled T_act
                    data_dict["T_act"] = round(data_dict["T_act"], prec_bath)
                    
                    # SAFETY SECOND
                    # check for pressure system leak
                    if (data_dict["vol"] - vol_start) > args["vol_diff"]:
                        pump_free.clear()
                        pump.clear()
                        raise Exception("Pump has discharged > {} mL!".format(args["vol_diff"]))
                        
                    # AIR SAVER
                    # if transition's been running for >2x the stability time,
                    # but bath internal temperature still not in range,
                    # shut air off temporarily
                    if args["air_saver"] and \
                        ((time_cycle - time_state) >= 2 * args["eq_min"]) and \
                        (data_dict["T_int"] < temp_set - temp_tol) or \
                        (data_dict["T_int"] > temp_set + temp_tol):
                        if waited and not save_air: print(file=stderr)
                        if not save_air: print("air saver activated", end='', file=stderr)
                        save_air = True
                    else:
                        save_air = False
                        
                    # control the air system
                    #NTS 20200720: pin set executes twice, which is annoying but not fatal
                    if data_dict['T_act'] <= args["dewpoint"] and not save_air:
                        # if it's cold
                        if not data_dict['air']:
                            # and air is off
                            pump_free.clear()
                            if waited: print(file=stderr)
                            print("turning air ON", file=stderr, end=' ')
                            pump.digital(0, 1)
                            print("√", file=stderr)
                            pump_free.set()
                            data_dict['air'] = True
                            # start a timer for air being on
                            time_air = time.time()
                            print("total air time {} s".format(round(time_air_tot)), file=stderr)
                    else:
                        # if it's warm
                        if data_dict['air']:
                            # and air is on
                            pump_free.clear()
                            if waited: print(file=stderr)
                            print("\nturning air OFF", file=stderr, end=' ')
                            pump.digital(0, 0)
                            print("√", file=stderr)
                            pump_free.set()
                            data_dict['air'] = False
                            # add air time to the total
                            time_air_tot += (time.time() - time_air)
                            print("total air time {} s".format(round(time_air_tot)), file=stderr)
                    
                    # does the state change require equilibration?
                    if any([chg_prev[var] for var in args["vars_eq"]]):
                        # if any of the slow params have changed from last state
                        need2wait = True
                    else:
                        need2wait = False
                    
                    # put data in the temporary trailing DF
                    trails = trails.append(data_dict, ignore_index=True)
                    # cut the DF down to within the trailing time
                    trails = trails[trails['watch'] >= trails['watch'].iloc[-1] - args["eq_min"]]
                    
                    # if the fluor reading has changed
                    # this check takes about 0.1 ms
                    if (trails.shape[0] == 1) or (trails["intensity"].iloc[-1] !=  trails["intensity"].iloc[-2]):
                        # write data to file
                        hand_log.write('\t'.join([str(data_dict[col]) for col in list_head])+'\n')
                        hand_log.flush()
                        
                    #NTS 20200719: It would be nice to abstract pressure and temp stability!
                    try:
                        # note that this checks range of the internal temperature, and stability of the actual temperature
                        temp_in_range = ((max(trails["T_int"]) <= temp_set + temp_tol) and (min(trails["T_int"]) >= temp_set - temp_tol) and ((max(trails["T_act"]) - min(trails["T_act"]) <= 2 * args["tol_T"])))
                        pres_in_range = ((max(trails["P_act"]) <= state_curr["P_set"] + args["tol_P"]) and (min(trails["P_act"]) >= state_curr["P_set"] - args["tol_P"]))
                    except:
                        # in case the dataframe is Empty
                        temp_in_range = False
                        pres_in_range = False
                        pass
                    
                    # if we're equilibrated
                    # and in range
                    # or state has timed out
                    # and windows are defogged
                    if ((not need2wait or (time_cycle - time_state) >= args["eq_min"] and \
                       temp_in_range and pres_in_range and not save_air) or \
                       (time_cycle - time_state) >= args["eq_max"]) and \
                       (data_dict['T_act'] > args["dewpoint"] or (time_cycle - time_air) >= args["air_time"]) :
                       
                        if waited: print(file=stderr) # newline
                        waited = False
                        
                        # open the shutter
                        if (not readings) and args["auto_shut"] and any([chg_prev[var] for var in args["vars_eq"]]): 
                            spec_free.clear()
                            while not spec.shutter(True):
                                pass
                            spec_free.set()
                        # take some readings
                        if (trails.shape[0] == 1) or (trails["intensity"].iloc[-1] !=  trails["intensity"].iloc[-2]):
                            if readings: print("reading {}: {} AU\r".format(readings, trails['intensity'].iloc[-1]), end='', file=stderr)
                            readings += 1
                        # break out of loop to next state
                        if (readings > args["n_read"]):
                            if args["auto_shut"] and any([chg_next[var] for var in args["vars_eq"]]):
                                spec_free.clear()
                                while not spec.shutter(False):
                                    pass
                                spec_free.set()
                            print(file=stderr)
                            break
                            
                    else:
                        # what are we waiting for?
                        print("waiting {} s to get {} s of stability\r".format(round(time.time()-time_state), args["eq_min"]), end='', file=stderr)
                        waited = True
                        
                    # prescribed sleep
                    try:
                        time.sleep((args["cycle_time"] / 1000) - (time.time() - (time_cycle)))
                    except:
                        pass
                    
            # shut down when done
            pump_free.clear()
            pump.digital(0,0)
            pump.pause()
            pump.disconnect()
            bath_free.clear()
            bath.on(False)
            bath.disconnect()
            spec_free.clear()
            spec.shutter(False)
            spec.disconnect()
            sys.exit(0)
    
        except:
            pump_free.clear()
            pump.pause()
            pump.digital(0,0) # turn the air off!
            spec_free.clear()
            spec.ack()
            spec.shutter(False)
            traceback.print_exc()
            
if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    main(args, sys.stdin, sys.stdout, sys.stderr)