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
    def __init__(self, port, pos_em=None, pos_ex=None, baud=9600, timeout=3):
        """
        Open serial interface, store filter arrangements, init wheels.
        """
        self.__ser__ = serial.Serial(port=port, baudrate=baud, timeout=timeout)
        self.lock = threading.RLock()
        self.pos_ex = pos_ex
        self.pos_em = pos_em
        
        self.lamp(False)
        
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
            self.__ser__.write("X{}\n".format(filt).encode())
            self.pos_ex = self.__ser__.read(4).rstrip().decode()[1]
        return self.pos_ex
        
    def em(self, filt=None):
        "Command or query the emission filter wheel"
        if filt is not None:
            # flush I/O
            self.__ser__.flush()
            self.__ser__.write("M{}\n".format(filt).encode())
            self.pos_em = self.__ser__.read(4).rstrip().decode()[1]
        return self.pos_em
        
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