#!/usr/bin/python3

"""
viscotheque.py

Collect fluorescence data at intervals across a temperature-pressure landscape.
The landscape is provided as a TSV via stdin, or from command-line args.
v1.1 (c) JRW 2021 - jwinnikoff@mbari.org

CHANGELOG:
This version (20220103) is designed to be robust (read: dumb).
The following simplifications improve ease of use and reliability:
(1) Equilibration times are user-determined constants passed in the input table.
(2) Temperature process control uses the waterbath's internal RTD. Therefore:
  (a) The factory PID parameters can be used (saves a lot of work).
  (b) No need for the functional-but-cumbersome "topside" PID implementation.
  (c) BUT a highly accurate calibration curve relating the bath's internal temp to the
  sample temp at equilibrium is required to calculate setpoints. temp_cal_sweep.py 
  collects these data with a traceable QTI temp probe (or cheap Arduino mimic.)
  (c) The stepwise calibration sweep should also be used to determine equilibration times.
(3) The output file header is written after poll() has been executed once.
This obviates the need to manually match the columns with the data streams.
The header is now written in alpha order.

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

from __future__ import print_function

import sys
import argparse
from re import split
import traceback
import time
import itertools
import numpy as np
import pandas as pd
from collections import deque
#from simple_pid import PID
import threading
from math import isclose # not avail for py2
import neslabrte
import isco260D
import rf5301
import auxmcu
from serial.serialutil import SerialException

def dewpt(rh, temp):
    "Approximate dewpoint per http;//dx.doi.org/10.1175/BAMS-86-2-225"
    try: return (temp - ((100 - rh)/5))
    # an invalid input will turn air on automatically
    except: return 0
    
def poll(dev, free, meas, pid=None):
    while True:
        try:
            "Poll the passed devices all at once. Free is a threading.Event, meas a deque"
            free.wait()
            devclass = dev.__class__.__name__
            if devclass == "NeslabController":
                # save serial bandwidth
                temp_int = dev.temp_get_int()
                # this line used to continuously update the setpoint
                #dev.temp_set(dev.cal_ext.act2ref(temp_act + pid(temp_act)))
                vals_dict = {
                    "T_int" : dev.temp_get_int(),
                    "T_ext" : dev.temp_get_ext(),
                    "T_act" : round(dev.cal_int.ref2act(temp_int), 2)
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
                    "wl_ex"     : dev.wl_ex(),
                    "wl_em"     : dev.wl_em(),
                    "slit_ex"   : dev.slit_ex(),
                    "slit_em"   : dev.slit_em(),
                    "shutter"   : dev.shutter()
                }
            elif devclass == "AuxMCU":
                # In the past I have had to make these requests persistent,
                # but maybe this is unnecessary
                # save bandwidth
                hum_dht = dev.hum_get()
                temp_dht = dev.temp_get()
                vals_dict = {
                    # humidity/dewpoint params
                    "dht_H" : hum_dht,
                    "dht_T" : temp_dht,
                    "dewpt" : round(dewpt(hum_dht, temp_dht), 2),
                    # IR non-contact thermometer
                    "mlx_inf": dev.inf_get(),
                    "mlx_amb": dev.amb_get()
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
        
    parser.add_argument('-f', "--file_log", help="continuously written datafile")
    parser.add_argument('-b', "--port_bath", help="device address of Isotemp waterbath", default="/dev/cu.usbserial-FT4IVKAO1")
    parser.add_argument('-p', "--port_pump", help="device address of ISCO syringe pump", default="/dev/cu.usbserial-FT4IVKAO0")
    parser.add_argument('-s', "--port_spec", help="device address of RF5301 fluorospec", default="/dev/cu.usbserial-FTV5C58R0")
    parser.add_argument('-a', "--port_amcu", help="device address of auxiliary Arduino", default="/dev/cu.usbmodem1411401")
    #parser.add_argument('-e', "--eqls", help="dict of tuples of (min, max) equilibration times for each variable", type=eval, default='{"T_set":(300,1500), "P_set":(150,300)}') # reset to 60,1500
    #parser.add_argument('-e', "--eqls", help="dict of tuples of (min, max) equilibration times for each variable", type=eval, default='{"T_set":(10, 10), "P_set":(10, 10)}') # reset to 60,1500
    #parser.add_argument('-t', "--tols", help="dict of max change over equilibration time for each variable", type=eval, default='{"T_act":0.2, "P_act":0.2}')
    #parser.add_argument('-n', "--n_read", help="Number of fluor readings to take per state", type=int, default=10)
    #parser.add_argument('-c', "--cyc_time", help="Read cycle time in ms", type=int, default=100)
    parser.add_argument('-d', "--auto_shut", help="Auto-shutter/dark mode: only open the shutter for readings", type=eval, default="True")
    #parser.add_argument("--shut_sit", help="Seconds to let dye relax after temp shift", type=float, default=0) # Laurdan is already chill :)
    parser.add_argument('-v', "--vol_diff", help="Max allowed volume change for the pressure system (mL)", type=int, default=20)
    parser.add_argument('-w', "--dew_tol", help="How close can T_act get to ambient dewpoint before air turns on?", type=float, default=2.5)
    parser.add_argument('-r', "--rtd_cal", help="Internal RTD cal slope and intercept (waterbath to sample temp at equilibrium)", type=eval, default='(0.9634942, 0.4696366)')
    
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
        print("reading states from stdin", file=stderr, flush=True)
        states = pd.read_csv(stdin, sep='\t')
    else:
        print("ERR: you need to pass the state table on stdin!", file=stderr, flush=True)
        exit(1)
                  
    ## run the experiment
    
    # open output file, do not overwrite!
    #with open(args['file_log'], 'x') as hand_log:
    with open(args['file_log'], 'w') as hand_log:
    
        ## variables tracking the expt schedule
        #vars_sched = ["clock", "watch", "state"]
        ## externally measured and derived variables
        #vars_measd = ["T_int", "T_ext", "T_act", "P", "I", "D", "P_act", "vol", "intensity", "T_amb", "H_amb", "dewpt", "air"]
        ## compose and write header - states.head() are the setpoint variables
        #list_head = vars_sched + list(states.head()) + vars_measd
        #line_head = "\t".join(list_head)
        #hand_log.write(line_head + '\n')
        #hand_log.flush()
        
        # now we're opening serial connections, which need to be closed cleanly on exit
        try:
            # init instruments
            print("connecting...", file=stderr, flush=True)
            print("fluorospectrometer     ", end='', file=stderr, flush=True)
            spec = rf5301.RF5301(port=args['port_spec'])
            print("√", file=stderr, flush=True)
            print("aux microcontroller    ", end='', file=stderr, flush=True)
            amcu = auxmcu.AuxMCU(port=args['port_amcu'])
            print("√", file=stderr, flush=True)
            print("temperature controller ", end='', file=stderr, flush=True)
            bath = neslabrte.NeslabController(port=args['port_bath'])
            print("√", file=stderr, flush=True)
            print("pressure controller    ", end='', file=stderr, flush=True)
            pump = isco260D.ISCOController(port=args['port_pump'])
            print("√", file=stderr, flush=True)
            
            ## hardware init
            print("initializing...", file=stderr, flush=True)
            
            # set spec slits and gain
            print("spec        ", end='', file=stderr, flush=True)
            # autozero with emission slit closed
            while not spec.slit_em(0): pass
            while not spec.zero(): pass
            # open the shutter, unless in auto
            if not args["auto_shut"]:
                while not spec.shutter(True): pass
                print('.', end='', file=stderr, flush=True)
            print(' √', file=stderr, flush=True)
            
            # initialize the AMCU
            print("auxiliary    ", end='', file=stderr, flush=True)
            amcu.lamp(True)
            print(' √', file=stderr, flush=True)
                
            # start bath circulator
            print("bath        ", end='', file=stderr, flush=True)
            # enter topside cal coefficients
            bath.cal_int.reset(*args["rtd_cal"])
            # start the bath
            #while not bath.on():
            #    bath.on(True)
            bath.on(True) # 20220105 hack
            print(' √', file=stderr, flush=True)
                
            # clear and start pump
            print("pump", end='', file=stderr, flush=True)
            while not pump.remote(): pass
            print('.', end='', file=stderr, flush=True)
            while not pump.clear(): pass
            print('.', end='', file=stderr, flush=True)
            while not pump.run(): pass
            print('.', end='', file=stderr, flush=True)
            # get initial volume
            vol_start = None
            while not vol_start: vol_start = pump.vol_get()
            print("         √ V0 = {} mL".format(vol_start), file=stderr, flush=True)
            
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
            threading.Thread(name="pollbath", target=poll, args=(bath, bath_free, queue_bath)).start()
            threading.Thread(name="pollpump", target=poll, args=(pump, pump_free, queue_pump)).start()
            threading.Thread(name="pollspec", target=poll, args=(spec, spec_free, queue_spec)).start()
            threading.Thread(name="pollamcu", target=poll, args=(amcu, amcu_free, queue_amcu)).start()
            
            ## run experiment
            
            # start experiment timer (i.e. stopwatch)
            time_start = time.time()
            
            print("waiting for data streams...", file=stderr, flush=True)
            # init the data dict. Persistent at start of program.
            data_dict = {
                "clock" : time.strftime("%Y%m%d %H%M%S"),
                "watch" : time.time() - time_start,
            }
            for dq in (queue_bath, queue_pump, queue_spec, queue_amcu):
                while True:
                    #print(data_dict) #TEST
                    # ensure that *something* gets popped out so the dict is complete
                    try:
                        data_dict.update(dq.popleft())
                        break
                    except:
                        pass
            
            # iterate over test states
            for state_num in range(states.shape[0]):
            
                # make dict for this state
                state_curr = states.iloc[state_num+0].to_dict()
                try: state_next = states.iloc[state_num+1].to_dict()
                except: pass
                
                # status update
                print("state {}/{}:".format(state_num+1, states.shape[0]), file=stderr, flush=True)
                print(state_curr, file=stderr, flush=True)
                            
                # before entering the first state, write the data file header
                if not state_num:
                    hand_log.write('\t'.join(sorted(set(list(state_curr.keys()) + list(data_dict.keys())))) + '\n')
                
                ## SETTING COMMANDS
                ## once these have executed, state_curr and data_dict can be merged
                ## without loss of information
                
                # set temp
                bath_free.clear()
                time.sleep(1)
                while not isclose(bath.temp_set(), round(bath.cal_int.act2ref(state_curr['T_set']), 2)):
                    print("setting temperature to {}°C".format(state_curr['T_set']), file=stderr, flush=True, end=' ')
                    bath.temp_set(bath.cal_int.act2ref(state_curr['T_set']))
                    print('√', file=stderr, flush=True)
                bath_free.set()
                
                # set pressure persistently
                pump_free.clear()
                while not isclose(pump.press_set(), state_curr['P_set']):
                    print("setting pressure to {} bar".format(state_curr['P_set']), file=stderr, flush=True, end=' ')
                    if pump.press_set(state_curr['P_set']): print('√', file=stderr, flush=True)
                pump_free.set()
                
                # mark time for start of state
                # doing this before wavelengths saves a few seconds
                time_state = time.time()
                waited = False
                # init n counter
                readings = 0
                    
                # set wavelengths
                
                ## set the excitation wavelength
                #while not isclose(spec.wl_ex(), state_curr['wl_ex']):
                #    print("setting excitation WL to {} nm".format(state_curr['wl_ex']), file=stderr, flush=True, end=' ')
                #    if spec.wl_ex(state_curr['wl_ex']): print('√', file=stderr, flush=True)
                #    
                ## set the emission wavelength
                #while not isclose(spec.wl_em(), state_curr['wl_em']):
                #    print("setting emission WL to {} nm".format(state_curr['wl_em']), file=stderr, flush=True, end=' ')
                #    if spec.wl_ex(state_curr['wl_em']): print('√', file=stderr, flush=True)
                
                # temporary WL setters
                # Persistence implemented over cycles to improve efficiency;
                # note that this checks the previous data row.
                if not (
                    # do any requests need to be sent to the spec?
                    state_curr['wl_ex'] == data_dict['wl_ex'] and 
                    state_curr['wl_em'] == data_dict['wl_em'] and
                    state_curr['slit_ex'] == data_dict['slit_ex'] and 
                    state_curr['slit_em'] == data_dict['slit_em']):
                    #spec_free.clear() # seems like maybe these flags should be removed bc they slow things down?
                    if (state_curr['wl_ex'] == 350) and (state_curr['wl_em'] == 428):
                        print("setting wavelengths for DPH", file=stderr, flush=True, end=' ')
                        if spec.wl_set_dph(): print('√', file=stderr, flush=True)
                    elif (state_curr['wl_ex'] == 340) and (state_curr['wl_em'] == 440):
                        print("setting wavelengths to 340/440", file=stderr, flush=True, end=' ')
                        if spec.wl_set_340_440(): print('√', file=stderr, flush=True)
                    elif (state_curr['wl_ex'] == 340) and (state_curr['wl_em'] == 490):
                        print("setting wavelengths to 340/490", file=stderr, flush=True, end=' ')
                        if spec.wl_set_340_490(): print('√', file=stderr, flush=True)
                    elif (state_curr['wl_ex'] == 410) and (state_curr['wl_em'] == 440):
                        print("setting wavelengths to 410/440", file=stderr, flush=True, end=' ')
                        if spec.wl_set_410_440(): print('√', file=stderr, flush=True)
                    elif (state_curr['wl_ex'] == 410) and (state_curr['wl_em'] == 490):
                        print("setting wavelengths to 410/490", file=stderr, flush=True, end=' ')
                        if spec.wl_set_410_490(): print('√', file=stderr, flush=True)
                        
                    # slits
                    if state_curr['slit_ex'] != data_dict['slit_ex']:
                        print("setting ex slit to {} nm".format(state_curr['slit_ex']), file=stderr, flush=True, end=' ')
                        if spec.slit_ex(state_curr['slit_ex']): print('√', file=stderr, flush=True)
                    if state_curr['slit_em'] != data_dict['slit_em']:
                        print("setting em slit to {} nm".format(state_curr['slit_em']), file=stderr, flush=True, end=' ')
                        if spec.slit_em(state_curr['slit_em']): print('√', file=stderr, flush=True)
                    #spec_free.set()
                
                # add input data to output buffer
                data_dict.update(state_curr)
                
                # init buffer for previous data line
                data_prev = {key:None for key in data_dict.keys()}
                
                # data logging loop                
                while True:
                
                    time_cycle = time.time()
                    
                    # DATA FIRST
                    for dq in (queue_bath, queue_pump, queue_spec, queue_amcu):
                        try:
                            data_dict.update(dq.popleft())
                            break
                        except:
                            pass
                    # add timing data
                    data_dict.update({
                        "clock" : time.strftime("%Y%m%d %H%M%S"),
                        "watch" : time.time() - time_start,
                    })
                    
                    ## Cyclewise instrument control
                    ## for stuff that needs to be monitored in real time
                    
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
                        if waited: print(file=stderr, flush=True)
                        print("turning air ON", file=stderr, flush=True, end=' ')
                        while not pump.digital(0, 1): pass
                        print("√", file=stderr, flush=True, end='\r')
                        pump_free.set()
                        data_dict['air'] = True
                    # if it's warm and the air is on
                    elif (data_dict['T_act'] > (data_dict["dewpt"] + args["dew_tol"])) and data_dict['air']:
                        # and air is on
                        pump_free.clear()
                        if waited: print(file=stderr, flush=True)
                        print("turning air OFF", file=stderr, flush=True, end=' ')
                        while not pump.digital(0, 0): pass
                        print("√", file=stderr, flush=True, end='\r')
                        pump_free.set()
                        data_dict['air'] = False
                        
                    #print("P "+str(data_prev["intensity"]))
                    #print("C "+str(data_dict["intensity"]))
                    
                    # if state wait time has not elapsed
                    waiting = (time.time() - time_state) < data_dict["time"]
                    if waiting:
                        print("waiting {}/{} s    ".format(round(time.time()-time_state), data_dict["time"]), file=sys.stderr, end='\r', flush=True)
                        waited = True
                    else:
                        if waited: print(file=stderr, flush=True) # newline
                        
                        # open the shutter
                        if (not readings) and args["auto_shut"] and waited: 
                            spec_free.clear() # good or bad?
                            while not spec.shutter(True): pass
                            spec_free.set()
                            time_open = time.time()
                            
                        # reset
                        waited = False
                    
                    # fluor intensity is the fastest-changing variable
                    # so only save data when it changes
                    # this is the output block
                    if data_dict["intensity"] != data_prev["intensity"]:
                    
                        # write data to file whether it counts as a reading or not
                        hand_log.write('\t'.join([str(data_dict[key]) for key in sorted(data_dict.keys())]) + '\n')
                        hand_log.flush()
                        # and buffer the data
                        data_prev.update(data_dict)
                    
                        if not waiting:
                            # increment the reading count
                            readings += 1
                            print("reading {}/{} s: {} AU  ".format(readings, data_dict["n_read"], data_dict["intensity"]), file=sys.stderr, end='\r', flush=True)
                            # once sufficient readings have been taken
                            if readings >= data_dict["n_read"]:
                                print(file=stderr, flush=True) # newline
                                # if there is a wait between states, close shutter
                                if state_next["time"]:
                                    spec_free.clear() # good or bad?
                                    while not spec.shutter(False): pass
                                    spec_free.set()
                                    time_shut = time.time()
                                # escape to next state
                                break
                    
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
            sys.exit(0)
    
        except:
            # on failure:
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
            traceback.print_exc()
            
if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    main(args, sys.stdin, sys.stdout, sys.stderr)