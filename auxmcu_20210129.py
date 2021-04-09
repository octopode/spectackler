#!/usr/bin/env python3

import sys
import serial
import threading
from re import sub

"""
auxmcu.py

driver module for an Arduino that handles some aux functions
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

import serial
import time
import io

def str2float(bytestring):
    if bytestring: return float(sub("[^0123456789\.]", "", bytestring.decode()))
    
def str2bool(bytestring):
    "Convert b'0'/b'1' to Boolean. b'' also returns False."
    return bool(int('0'+bytestring.decode().strip()))

class AuxMCU:
    def __init__(self, port, filt_em=None, filt_ex=None, baud=9600, timeout=3, init=True):
        """
        Open serial interface, store filter arrangements, init wheels.
        """
        self.__ser__ = serial.Serial(port=port, baudrate=baud, timeout=timeout)
        self.lock = threading.RLock()
        self.filt_ex = filt_ex
        self.filt_em = filt_em
        
        self.lamp(False)
        # wheels_init() can be called later if desired for interface reasons
        # but it must still be called before ex() or em()!
        if init: self.wheels_init()
        
    def wheels_init(self):
        "Have user verify that filter wheels are properly indexed"
        # make sure stdin is the command line
        sys.stdin = open('/dev/tty')
        for whl in ('X', 'M'):
            self.__ser__.flush()
            while True:
                resp = input("set e{} 0 position (f/b/y) ".format(whl.lower()))
                if resp.rstrip() == 'y': 
                    # center
                    self.__ser__.write("E{}F\r\n".format(whl).encode())
                    self.__ser__.read(3)
                    self.__ser__.write("E{}R\r\n".format(whl).encode())
                    self.__ser__.read(3)
                    self.__ser__.write("ZR{}\r\n".format(whl).encode())
                    self.__ser__.read(3)
                    if whl == 'X': self.pos_ex = 0
                    if whl == 'M': self.pos_em = 0
                    break
                elif resp.rstrip() == 'f':
                    self.__ser__.write("E{}F\r\n".format(whl).encode())
                    self.__ser__.read(3)
                elif resp.rstrip() == 'b':
                    self.__ser__.write("E{}R\r\n".format(whl).encode())
                    self.__ser__.read(3)
        
    def disconnect(self):
        "Close serial interface."
        self.__ser__.reset_input_buffer()
        self.__ser__.reset_output_buffer()
        self.__ser__.close()
        
    # setter/getters
    
    def ex(self, filt=None):
        "Command or query the excitation filter wheel"
        if filt is not None:
            # flush I/O
            self.__ser__.flush()
            self.__ser__.write("EX{}\n".format(self.filt_ex.index(filt)).encode())
            self.pos_ex = int(self.__ser__.read(3).rstrip().decode())
        return self.filt_ex[self.pos_ex]
        
    def em(self, filt=None):
        "Command or query the emission filter wheel"
        if filt is not None:
            # flush I/O
            self.__ser__.flush()
            self.__ser__.write("EM{}\n".format(self.filt_em.index(filt)).encode())
            self.pos_em = int(self.__ser__.read(3).rstrip().decode())
        return self.filt_em[self.pos_em]
        
    def lamp(self, status=None):
        "Command or query the spec lamp interlock"
        # flush I/O
        self.__ser__.flush()
        if status is not None:
            if status: 
                self.__ser__.write("LON\n".encode())
                self.lamp_status = str2bool(self.__ser__.read(3).rstrip())
            else: 
                self.__ser__.write("LOF\n".encode())
                self.lamp_status = str2bool(self.__ser__.read(3).rstrip())
        return self.lamp_status
        
    def temp_get(self):
        "Request ambient temp in sample chamber"
        # flush input
        self.__ser__.write("TEM\n".encode())
        self.__ser__.flush()
        return str2float(self.__ser__.read(7).rstrip())
        
    def hum_get(self):
        "Request relative humidity in sample chamber"
        # flush input
        self.__ser__.write("HUM\n".encode())
        self.__ser__.flush()
        return str2float(self.__ser__.read(7).rstrip())