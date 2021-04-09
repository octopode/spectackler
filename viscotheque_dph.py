#!/usr/bin/python3

"""
viscotheque.py

Collect fluorescence anisotropy data at intervals across a temperature-pressure landscape.
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
from simple_pid import PID
import threading
from math import isclose
import isotemp6200
import isco260D
import rf5301
import auxmcu
from serial.serialutil import SerialException

def dewpt(rh, temp):
    "Approximate dewpoint per http;//dx.doi.org/10.1175/BAMS-86-2-225"
    return (temp - ((100 - rh)/5))
    
def poll(dev, free, meas, pid=None):
    while True:
        try:
            "Poll the passed devices all at once. Free is a threading.Event, meas a deque"
            free.wait()
            devclass = dev.__class__.__name__
            if devclass == "IsotempController":
                # get reference and actual temps with just one query
                temp_ext = dev.temp_get_ext()
                temp_act = dev.cal_ext.ref2act(temp_ext)
                # update topside PID (setpoint change should not persist)
                dev.temp_set(dev.cal_ext.act2ref(temp_act + pid(temp_act)))
                vals_dict = {
                    "T_int" : dev.temp_get_int(),
                    "T_ext" : temp_ext,
                    "T_act" : round(temp_act, 2),
                    "P"     : round(pid.components[0], 2),
                    "I"     : round(pid.components[1], 2),
                    "D"     : round(pid.components[2], 2)
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
            elif devclass == "AuxMCU":
                # be persistent!
                while True:
                    temp_amb = dev.temp_get()
                    if temp_amb: break
                while True:
                    hum_amb = dev.hum_get()
                    if hum_amb: break
                vals_dict = {
                    "pol_ex": dev.ex(),
                    "pol_em": dev.em(),
                    "H_amb" : hum_amb,
                    "T_amb" : temp_amb,
                    "dewpt" : round(dewpt(hum_amb, temp_amb), 2)
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
    parser.add_argument('-b', "--port_bath", help="device address of Isotemp waterbath", default="/dev/cu.usbserial-AL01M1X9")
    parser.add_argument('-p', "--port_pump", help="device address of ISCO syringe pump", default="/dev/cu.usbserial-FTV5C58R1")
    parser.add_argument('-s', "--port_spec", help="device address of RF5301 fluorospec", default="/dev/cu.usbserial-FTV5C58R0")
    parser.add_argument('-a', "--port_amcu", help="device address of auxiliary Arduino", default="/dev/cu.usbmodem142201")
    parser.add_argument('-e', "--eqls", help="dict of tuples of (min, max) equilibration times for each variable", type=eval, default='{"T_set":(300,1500), "P_set":(60,300)}') # reset to 60,1500
    parser.add_argument('-t', "--tols", help="dict of max change over equilibration time for each variable", type=eval, default='{"T_act":0.2, "P_act":0.2}')
    parser.add_argument('-n', "--n_read", help="Number of fluor readings to take per state", type=int, default=15)
    parser.add_argument('-c', "--cyc_time", help="Read cycle time in ms", type=int, default=100)
    parser.add_argument('-d', "--auto_shut", help="Auto-shutter/dark mode: only open the shutter for readings", type=eval, default="True")
    parser.add_argument("--shut_sit", help="Seconds to let dye relax after temp shift", type=float, default=0)
    parser.add_argument('-x', "--filt_ex", help="polarizers in the excitation filter wheel, clockwise order", type=eval, default='["0", "V", "H"]')
    parser.add_argument('-m', "--filt_em", help="polarizers in the emission filter wheel, clockwise order", type=eval, default='["0", "V", "H"]')
    parser.add_argument('-v', "--vol_diff", help="Max allowed volume change for the pressure system (mL)", type=int, default=20)
    parser.add_argument('-w', "--dew_tol", help="How close can T_act get to ambient dewpoint before air turns on?", type=float, default=2.5)
    parser.add_argument('-r', "--rtd_cal", help="External RTD cal slope and intercept (reference to actual)", type=eval, default='(1.341635, -5.255324)')
    
    return parser.parse_args(argv)

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
        print("ERR: you need to pass the state table on stdin!", file=stderr)
        exit(1)
                  
    ## run the experiment
    
    # open output file, do not overwrite!
    with open(args['file_log'], 'x') as hand_log:
    
        # variables tracking the expt schedule
        vars_sched = ["clock", "watch", "state"]
        # externally measured and derived variables
        vars_measd = ["T_int", "T_ext", "T_act", "P", "I", "D", "P_act", "vol", "intensity", "T_amb", "H_amb", "dewpt", "air"]
        # compose and write header - states.head() are the setpoint variables
        list_head = vars_sched + list(states.head()) + vars_measd
        line_head = "\t".join(list_head)
        hand_log.write(line_head + '\n')
        hand_log.flush()
        
        # now we're opening serial connections, which need to be closed cleanly on exit
        try:
            # init instruments
            print("connecting...", file=stderr)
            print("fluorospectrometer     √", file=stderr)
            amcu = auxmcu.AuxMCU(port=args['port_amcu'])
            print("aux microcontroller    √", file=stderr)
            bath = isotemp6200.IsotempController(port=args['port_bath'])
            print("temperature controller √", file=stderr)
            pump = isco260D.ISCOController(port=args['port_pump'])
            print("pressure controller    √", file=stderr)
            spec = rf5301.RF5301(port=args['port_spec'])
            
            ## hardware init
            print("initializing...", file=stderr)
            
            # set spec slits and gain
            print("spec", end='', file=stderr)
            # open the shutter, unless in auto
            if not args["auto_shut"]:
                while not spec.shutter(True):
                    pass
                print('.', end='', file=stderr)
            print(' √', file=stderr)
            
            # initialize the filter wheels
            print("auxiliary", file=stderr)
            amcu.lamp(True)
            #amcu.wheels_init()
                
            # start bath circulator
            print("bath", end='', file=stderr)
            
            # init topside PID
            pid = PID(1, 0, 85, setpoint=states.loc[states.index[0], "T_set"])
            # windup preventer
            pid.output_limits = (-20, 20)
            # enter topside cal coefficients
            bath.cal_ext.reset(*args["rtd_cal"])
            
            # set controller gains
            while not all(bath.pid('H', 0.8, 0, 0)):
                pass
            print('.', end='', file=stderr)
            while not all(bath.pid('C', 1, 0, 0)):
                pass
            print('.', end='', file=stderr)
            # set precision (number of decimal places)
            while not bath.temp_prec(2):
                pass
            print('.', end='', file=stderr)
            # set controller to listen to external RTD
            while not bath.probe_ext(True):
                pass
            print('.', end='', file=stderr)
            # finally, start the bath
            while not bath.on():
                bath.on(True)
            print(' √', file=stderr)
                
            # clear and start pump
            print("pump", end='', file=stderr)
            while not pump.remote(): pass
            print('.', end='', file=stderr)
            while not pump.clear(): pass
            print('.', end='', file=stderr)
            while not pump.run(): pass
            print('.', end='', file=stderr)
            # get initial volume
            vol_start = None
            while not vol_start: vol_start = pump.vol_get()
            print(" √ V0 = {} mL".format(vol_start), file=stderr)
            
            # declare async queues
            queue_bath = deque(maxlen=1)
            queue_pump = deque(maxlen=1)
            queue_spec = deque(maxlen=1)
            queue_amcu = deque(maxlen=1)
            
            # start polling threads
            # all device instances have RLocks!
            bath_free = threading.Event()
            pump_free = threading.Event()
            spec_free = threading.Event()
            amcu_free = threading.Event()
            [event.set() for event in (bath_free, pump_free, spec_free, amcu_free)]
            threading.Thread(name="pollbath", target=poll, args=(bath, bath_free, queue_bath, pid)).start()
            threading.Thread(name="pollpump", target=poll, args=(pump, pump_free, queue_pump)).start()
            threading.Thread(name="pollspec", target=poll, args=(spec, spec_free, queue_spec)).start()
            threading.Thread(name="pollamcu", target=poll, args=(amcu, amcu_free, queue_amcu)).start()
            
            ## run experiment
            
            # dict links setp vars to meas vars
            #NTS 20210113 there's gotta be a better place for these mappings
            setp2meas = {"T_set": "T_act", "P_set": "P_act"}
            
            # start experiment timer (i.e. stopwatch)
            time_start = time.time()
            
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
                
                time_state = time.time() # mark time when state starts
                waited = False # did the state have to wait for stability?
                sat = False # did the dye have to relax?
                readings = 0 # reset n counter
                
                # status update
                print("state {}/{}:".format(state_num+1, states.shape[0]), file=stderr)
                print(state_curr, file=stderr)
                
                # data logging loop
                data_dict = {}
                # init the data dict. Persistent the first time.
                for dq in (queue_bath, queue_pump, queue_spec, queue_amcu):
                    while True:
                        # ensure that *something* gets popped out so the dict is complete
                        try:
                            data_dict.update(dq.popleft())
                            break
                        except:
                            pass
                
                # set temp via topside PID
                while not isclose(pid.setpoint, state_curr['T_set']):
                    print("setting temperature to {}˚C".format(state_curr['T_set']), file=stderr, end=' ')
                    # pid object is picked up by poll()
                    pid.setpoint = state_curr['T_set']
                    print('√', file=stderr)
                
                # set pressure persistently
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
                ## set the emission wavelength
                #while not isclose(spec.em_wl(), state_curr['wl_em']):
                #    print("setting emission WL to {} nm".format(state_curr['wl_em']), file=stderr, end=' ')
                #    if spec.ex_wl(state_curr['wl_em']): print('√', file=stderr)
                
                # temporary WL setters
                # Persistence implemented over cycles to improve efficiency;
                # note that this checks the previous data row.
                if not ((state_curr['wl_ex'] == data_dict['wl_ex']) and (state_curr['wl_em'] == data_dict['wl_em'])):
                #if not (isclose(spec.ex_wl(), state_curr['wl_ex']) and isclose(spec.em_wl(), state_curr['wl_em'])):
                    if (state_curr['wl_ex'] == 350) and (state_curr['wl_em'] == 428):
                        print("setting wavelengths for DPH", file=stderr, end=' ')
                        spec_free.clear()
                        spec.wl_set_dph()
                        spec_free.set()
                        print('√', file=stderr)
                    
                # set polarizers
                if not ((state_curr['pol_ex'] == data_dict['pol_ex']) and (state_curr['pol_em'] == data_dict['pol_em'])):
                    amcu_free.clear()
                    # take the line from other thread!
                    amcu.__ser__.send_break(duration=amcu.__ser__.timeout+0.1)
                    time.sleep(amcu.__ser__.timeout+0.1)
                    # excitation
                    if state_curr['pol_ex'] != data_dict['pol_ex']:
                        print("setting ex polarization to {}". format(state_curr['pol_ex']), file=stderr, end=' ')
                        while not state_curr['pol_ex'] == amcu.ex(state_curr['pol_ex']): pass
                        print('√', file=stderr)
                    # emission
                    if state_curr['pol_em'] != data_dict['pol_em']:
                        print("setting em polarization to {}". format(state_curr['pol_em']), file=stderr, end=' ')
                        while not state_curr['pol_em'] == amcu.em(state_curr['pol_em']): pass
                        print('√', file=stderr)
                    amcu_free.set()
                    # wait until wheel is solidly in position before writing any data
                    time.sleep(amcu.__ser__.timeout)
                
                # init a log table for the state
                trails = pd.DataFrame(columns = list_head)
                                
                while True:
                
                    time_cycle = time.time()
                    
                    # DATA FIRST
                    for dq in (queue_bath, queue_pump, queue_spec, queue_amcu):
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
                            "msg"   : state_curr["msg"]
                        }
                    )
                    
                    # SAFETY SECOND
                    # check for pressure system leak
                    if (data_dict["vol"] - vol_start) > args["vol_diff"]:
                        pump_free.clear()
                        pump.clear()
                        raise Exception("Pump has discharged > {} mL!".format(args["vol_diff"]))
                        
                    # control the air system
                    # if it's cold and air is off
                    if (data_dict['T_act'] <= data_dict["dewpt"] + args["dew_tol"]) and not data_dict['air']:
                        pump_free.clear()
                        if waited: print(file=stderr)
                        print("\nturning air ON", file=stderr, end=' ')
                        while not pump.digital(0, 1): pass
                        print("√", file=stderr)
                        pump_free.set()
                        data_dict['air'] = True
                    # if it's warm and the air is on
                    elif (data_dict['T_act'] > (dewpt(data_dict['H_amb'], data_dict['T_amb']) + args["dew_tol"])) and data_dict['air']:
                        # and air is on
                        pump_free.clear()
                        if waited: print(file=stderr)
                        print("\nturning air OFF", file=stderr, end=' ')
                        while not pump.digital(0, 0): pass
                        print("√", file=stderr)
                        pump_free.set()
                        data_dict['air'] = False
                    
                    # does the state change require equilibration?
                    vars_wait = [var for var in args["eqls"] if chg_prev[var]] 
                    # if this in an empty dict, all(in_range.values()) will be true
                    in_range = {var: False for var in vars_wait}
                    
                    # put new data into a trailing buffer
                    trails = trails.append(data_dict, ignore_index=True)
                    # cut the buffer down to the min equil time of the slowest variable
                    if vars_wait:
                        trails = trails[trails['watch'] >= (trails['watch'].iloc[-1] - max([min(args["eqls"][var]) for var in vars_wait]))]
                    
                    # if the fluor reading has changed, write line to logfile
                    # this check takes about 0.1 ms
                    if (trails.shape[0] == 1) or (trails["intensity"].iloc[-1] !=  trails["intensity"].iloc[-2]):
                        # write data to file
                        hand_log.write('\t'.join([str(data_dict[col]) for col in list_head])+'\n')
                        hand_log.flush()
                        
                    for var in vars_wait:
                        # if variable's timeout is past
                        if (time_cycle - time_state) >= max(args["eqls"][var]):
                            in_range[var] = True
                        # else, if min equilibration has elapsed
                        elif (time_cycle - time_state) >= min(args["eqls"][var]):
                            #print("{}: {}\r".format(var, data_dict[var]), end='')
                            # see if the trace of the variable is in range
                            trace = trails[trails['watch'] >= (trails['watch'].iloc[-1] - min(args["eqls"][var]))][setp2meas[var]].tolist()
                            #print(trace)
                            # and green- or redlight the variable as appropriate
                            in_range[var] = ((max(trace) < (state_curr[var] + args["tols"][setp2meas[var]])) and (min(trace) > (state_curr[var] - args["tols"][setp2meas[var]])))
                    
                    # if all equilibrations have cleared
                    if all(in_range.values()):
                       
                        if waited: print(file=stderr) # newline
                        waited = False
                        
                        # open the shutter
                        if (not readings) and args["auto_shut"] and len(vars_wait) and not sat: 
                            spec_free.clear()
                            while not spec.shutter(True):
                                pass
                            spec_free.set()
                            time_open = time.time()
                            
                        # let the dye relax after a long dark period (temp xsition)
                        if ("T_set" not in vars_wait) or ((time.time() - args["shut_sit"]) >= time_open):
                            # take some readings
                            if (trails.shape[0] == 1) or (trails["intensity"].iloc[-1] !=  trails["intensity"].iloc[-2]):
                                if readings: print("reading {}: {} AU \r".format(readings, trails['intensity'].iloc[-1]), end='', file=stderr)
                                readings += 1
                            # break out of loop to next state
                            if (readings > args["n_read"]):
                                if args["auto_shut"] and any([chg_next[var] for var in args["eqls"].keys()]):
                                    spec_free.clear()
                                    while not spec.shutter(False):
                                        pass
                                    spec_free.set()
                                print(file=stderr)
                                break
                        else:
                            print("dye relaxed for {}/{} s\r".format(round(time.time()-time_open), args["shut_sit"]), end='', file=stderr)
                            sat = True
                            # gotta get a newline in here somewhere!
                    else:
                        # what are we waiting for?
                        print("waiting {} s to get {} s of stability\r".format(round(time.time()-time_state), max([min(args["eqls"][var]) for var in vars_wait])), end='', file=stderr)
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
            spec.shutter(True)
            spec.disconnect()
            amcu_free.clear()
            amcu.__ser__.send_break(duration=amcu.__ser__.timeout+0.1)
            time.sleep(amcu.__ser__.timeout+0.1)
            amcu.lamp(False)
            amcu.ex('0')
            amcu.em('0')
            sys.exit(0)
    
        except:
            pump_free.clear()
            pump.pause()
            pump.digital(0,0) # turn the air off!
            spec_free.clear()
            spec.ack()
            spec.shutter(False)
            amcu_free.clear()
            amcu.__ser__.send_break(duration=amcu.__ser__.timeout+0.1)
            time.sleep(amcu.__ser__.timeout+0.1)
            amcu.lamp(False)
            amcu.ex('0')
            amcu.em('0')
            traceback.print_exc()
            
if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    main(args, sys.stdin, sys.stdout, sys.stderr)