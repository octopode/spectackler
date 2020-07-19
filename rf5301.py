#!/usr/bin/python3

"""
rf5301.py

driver module for controlling Shimadzu RF-5301PC spectrofluorophotometer
v0.5 (c) JRW 2020 - jwinnikoff@mbari.org

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
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sys import stdin
from time import sleep
import binascii
    
def bitstring_to_bytes(s):
    return int(s, 2).to_bytes(len(s) // 8, byteorder='big')

def hex2dec(hex):
    "Convert Shimadzu's funky 24-bit hex to a decimal intensity value (-100 - 1000)"
    # https://stackoverflow.com/questions/24563786/conversion-from-hex-to-signed-dec-in-python/32276534
    hex = "0x" + hex
    return -(int(hex, 16) & 0x800000) | (int(hex, 16) & 0x7fffff)
    
def dec2hex(dec):
    "Reverse of the above"
    # lop off the 0x
    return hex(dec).upper()[2:]
    
def pad_bytestring(byte_str, to_width, pad=b'\xb0', left=True):
    "Pad a bytestring to width with specified byte"
    if left:
        return b''.join([pad]*(to_width-len(byte_str))) + byte_str
    else:
        return byte_str + b''.join([pad]*(to_width-len(byte_str)))

# turn ASCII string into backslash-delimited hex values
def ascii2hex(mystr):
    return ''.join([("\\x" + hex(ord(ch))[2:]) for ch in list(mystr)])
    
#def hex2ascii(hex):
#    hex_string = hex[2:]
#    bytes_object = bytes.fromhex(hex_string)
#    ascii_string = bytes_object.decode("ASCII")
#
#    return ascii_string
    
def hex2ascii(bytelist):
    "Decode byte list to UTF-8, performing modulo"
    return serial.to_bytes([byte%128 for byte in bytelist])
    
def str2shim(msg):
    "Enframe a message for the spec (bytelist), return a bytelist."
    cmd = [0x02] + msg + [0x83]
    return cmd + [shim_checksum(cmd)]
    
def shim2str(bytestr):
    "Take bytestring from the spec, checksum and strip it."
    #NTS 20200719: True is temporary here!
    if True or bytestr[-1] == shim_checksum(bytestr[:-1]):
        # lop off first and last bytes (0x02, 0x83)
        return hex2ascii(bytestr[:-1])[1:-1].decode(errors="ignore").strip()
    else:
        # if checksum fails
        return None
    
def shim_checksum(msg):
    dict_stopgap = {
        b'\x02W\xcd\x83'    : 0x19,
        b'\x02#\x83'        : 0x20,
        b'\x02E\x83'        : 0x46,
        b'\x02\xd6\x83'     : 0xd5,
        b'\x02CR\x83'       : 0x92,
        b'\x02C\x83'        : 0x40,
        b'\x02I\x83'        : 0x4a,
        b'\x02\xce1\x83'    : 0x7c,
        b'\x02\xce2\x83'    : 0x7f,
        # data request
        b'\x02R\x83'        : 0x51,
        # WL check
        b'\x02WX\x83'       : 0x8c,
        b'\x02WM\x83'       : 0x19,
        # WL set
        b'\x02W\xc1\xb0\xc44811\xb62\x83'       : 0xe9,
        b'\x02W\xc1\xb0\xc4\xc1C1\xb0\xb68\x83' : 0xec,
        b'\x02W\xc1\xb0\xc44811\xb3\xb0\x83'    : 0x6e,
        b'\x02W\xc1\xb0\xc4481\xb324\x83'       : 0xe9
    }
    return dict_stopgap[serial.to_bytes(msg)]
    
def remove_prefix(text, prefix):
    return text[text.startswith(prefix) and len(prefix):]
    
class RF5301:
    def __init__(self, port, baud=9600, timeout=1):
        """
        Open serial interface, set remote status and baudrate.
        The serial handle becomes a public instance object.
        """
        self.__ser__ = serial.Serial(port=port, baudrate=baud, timeout=timeout)
        
        # clear the line
        while(self.__ser__.read(1) == b'\x85'):
        	self.ack(True)
        
        # has POST been run?
        if not self.post():
            # if not, run it
            results = self.post(True)
            fails = {key: val for key, val in results.items() if not val}
            if len(fails):
                raise Exception("{} failed self-test!".format(list(fails.keys())))
                exit(1)
    
    def post(self, status=False):
        "Perform full Power On Self-Test. False checks whether POST already run, True runs it."
        if not status:
            msg = [0x23]
            # reply of 1 means the spec was just turned on
            # return of True means POST already performed
            return not int(remove_prefix(self.query(msg), '0'+hex2ascii(msg).decode()))
        else:
            post_dict = {
                "mem_chk" : self.mem_chk(),
                "ser_num" : self.ser_num()
            }
            post_dict.update(self.opt_chk())
            post_dict["xen_hrs"] = self.xen_hrs()
            return post_dict
        
    def ser_num(self):
        "Get instrument SN"
        msg = [0xd6]
        # strip 0 and the query from beginning of a successful reply
        return remove_prefix(self.query(msg), '0'+hex2ascii(msg).decode())
        
    def rom_ver(self):
        "Get instrument ROM version"
        msg = [0x43, 0x52]
        # strip 0 and the query from beginning of a successful reply
        return float(remove_prefix(self.query(msg), '0'+hex2ascii(msg).decode()))
        
    def mem_chk(self):
        "self-check ROM, RAM, EEPROM"
        msg = [0x43]
        if remove_prefix(self.query(msg), '0'+hex2ascii(msg).decode()) == "R1":
            return True
        else:
            return False
            
    def opt_chk(self):
        "Optical bench check: ex/em slits, monochromators, (BL stability?)"
        msg = [0x49]
        # first element is successful receipt
        status = [remove_prefix(x, hex2ascii(msg).decode()) for x in self.query(msg)[1:]]
        prefixes = [x[0] for x in status]
        vals = [x[-1] for x in status]
        # dict defines codes in the reply, to my best inference
        chkpts = {
            'O' : "ex_slit_min",
            'A' : "ex_slit_max",
            'E' : "em_slit_min",
            'S' : "em_slit_max",
            'L' : "ex_mono_min",
            'X' : "ex_mono_max",
            'M' : "em_mono_min",
            'B' : "em_mono_max"
        }
        return {chkpts[prefix] : (not int(val)) for prefix, val in zip(prefixes, vals)}
        
    def xen_hrs(self):
        "Get hours on the Xe lamp. RETURNS 1 if optics not yet checked"
        msg = [0x45]
        return hex2dec(remove_prefix(self.query(msg), '0'+hex2ascii(msg).decode()))
        
    def shutter(self, status):
        "Open (True) or close (False) the shutter"
        msg = [0xce]
        if status:
            msg.append(0x31)
        else:
            msg.append(0x32)
        return not int(self.query(msg))
        
    def ex_wl(self, wl=None):
        "Get/set excitation wavelength"
        if wl is None:
            # get wavelength
            msg = [0x57, 0x58]
            hex_str = remove_prefix(self.query(msg), '0'+hex2ascii(msg).decode())
            return hex2dec(hex_str)/10
        else:
            #NTS 20200718 not done yet!
            # set wavelength
            # they have to be set simultaneously, so read em_wl
            em_wl = self.em_wl()
            msg = [0x57] + [0xc1] + list(pad_bytestring(dec2hex(int(wl*10)).encode(), to_width=4)) + list(pad_bytestring(dec2hex(int(em_wl*10)).encode(), to_width=4))
            print(str2shim(msg))
            #return self.query(msg)
            
    def em_wl(self, wl=None):
        "Get/set emission wavelength"
        if wl is None:
            # get wavelength
            msg = [0x57, 0xcd]
            hex_str = remove_prefix(self.query(msg), '0'+hex2ascii(msg).decode())
            return hex2dec(hex_str)/10
            
    ## Stopgap methods to establish common ex/em pairs
    def wl_set_nadh(self):
        "ex/em 340/445"
        msg = [0x57, 0xc1, 0xb0, 0xc4, 0x34, 0x38, 0x31, 0x31, 0xb6, 0x32]
        return not int(self.query(msg))
        
    def wl_set_dph(self):
        "ex/em 350/420"
        msg = [0x57, 0xc1, 0xb0, 0xc4, 0xc1, 0x43, 0x31, 0xb0, 0xb6, 0x38]
        return not int(self.query(msg))
        
    def wl_set_laurdan_blu(self):
        "ex/em 340/440"
        msg = [0x57, 0xc1, 0xb0, 0xc4, 0x34, 0x38, 0x31, 0x31, 0xb3, 0xb0]
        return not int(self.query(msg))
        
    def wl_set_laurdan_red(self):
        "ex/em 340/490"
        msg = [0x57, 0xc1, 0xb0, 0xc4, 0x34, 0x38, 0x31, 0xb3, 0x32, 0x34]
        return not int(self.query(msg))
        
    def fluor_get(self):
        "Request fluorescence reading"
        msg = [0x52]
        # there's a NUL between prefix and data!! Why is beyond me at present.
        # it's a pad. Should I replace it with 0 (0x30)?
        #print(self.query(msg))
        #hex_str = remove_prefix(self.query(msg), '0'+hex2ascii(msg).decode()+'\x00')
        # remove message and padding
        return hex2dec(self.query(msg)[-6:])/1000
        
    # SOFTWARE HANDSHAKING METHODS
    def query(self, msg):
        "Enframe query (presently bytelist), send to instrument, return reply"
        self.__ser__.flush()
        # hello?
        self.enq(True)
        self.ack(False)
        # now send the command
        self.__ser__.write(str2shim(msg))
        # wait for ack
        self.ack(False)
        # send EOT
        self.eot(True)
        # wait for ENQ (=CTR)
        self.enq(False)
        # send ACK
        self.ack(True)
        # read blocks to EOT
        blocks = []
        while True:
            blocks.append(self.read_block())
            if blocks[-1][-2] == ord(b'\x83'):
                break
        # wait for EOT to clear the line
        self.eot(False)
        #return shim2str(reply)
        if len(blocks) > 1:
            return [shim2str(block) for block in blocks]
        else:
            return shim2str(blocks[0])
            
    def read_block(self):
        "Read block terminated with ETB or ETX, return bytestring"
        block = b''
        while True:
            # WAIT for that first byte!
            while not block: block += self.__ser__.read(1)
            # after that, just try once 
            if block: block += self.__ser__.read(1)
            if block[-1] in [ord(sig) for sig in [b'\x97', b'\x83']]:
                # get the checkbyte
                block += self.__ser__.read(1)
                # ACK receipt
                self.ack(True)
                return block
    
    # signal senders/receivers
    # passing True sends the signal, False waits to receive it
    def signal(self, send, sig):
        if send:
            self.__ser__.write(sig)
        else:
            self.wait_for(sig)
    
    def wait_for(self, sig):
        while self.__ser__.read(1) != sig:
            pass
    
    def ack(self, send=True):
        "Send or recieve ACK"
        self.signal(send, b'\x86')
                        
    def enq(self, send=True):
        "Send or recieve ENQ"
        self.signal(send, b'\x85')
        
    def etb(self, send=True):
        "Send or recieve ETB"
        self.signal(send, b'\x97')
            
    def etx(self, send=True):
        "Send or recieve ETX"
        self.signal(send, b'\x83')
        
    def eot(self, send=True):
        "Send or recieve EOT"
        self.signal(send, b'\x04')