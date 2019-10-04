#!/usr/bin/python3

"""
isco260D.py

driver module for controlling [Teledyne] ISCO 260D syringe pump(s)
v0.5 (c) JRW 2019 - jwinnikoff@mbari.org

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

def dasnet_checksum(cmd):
    "Calculate 2-digit hex checksum for a DASNET command."
    #print([ord(char) for char in list(cmd)])
    tot = sum([ord(char) for char in list(cmd)])
    return format(256 - tot%256, '02x').upper()

def str2dasnet(msg, source='', dest=''):
    "Convert serial command to DASNET frame."
    cmd = "{}R{}{}{}".format(dest, source, format(len(msg), '02x'), msg).upper()
    frame = "{}{}\r".format(cmd, dasnet_checksum(cmd))
    return frame.encode()

class ISCOController:
    def __init__(self, port, baud=9600, timeout=1, source=0, dest=1):
        """
        Open serial interface, set remote status and baudrate.
        The serial handle becomes a public instance object.
        """
        self.__ser__ = serial.Serial(port, baud, timeout)
        self.remote(source, dest)
            
    def disconnect():
        self.__ser__.close()