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

"/dev/cu.usbserial-FTV5C58R0"
    
def bitstring_to_bytes(s):
    return int(s, 2).to_bytes(len(s) // 8, byteorder='big')

# convert Shimadzu's funky 24-bit hex to a decimal intensity value (-100 - 1000)
# https://stackoverflow.com/questions/24563786/conversion-from-hex-to-signed-dec-in-python/32276534
def hex2dec(hex):
    hex = "0x" + hex
    return -(int(hex, 16) & 0x800000) | (int(hex, 16) & 0x7fffff)

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
        return hex2ascii(bytestr[:-1]).decode().strip()[1:-1]
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
        self.__ser__.flush()
        
        ## initialization routine
        #init = []
        #for query in [[0x23], [0x45], [0xd6], [0x45], [0x43, 0x52]]:
        #    init.append(self.query(query))
        #print(init)
    
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
                "ser_num" : self.ser_num(),
                "xen_hrs" : self.xen_hrs()
            }
            #post_dict.append(self.opt_chk())
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
        "Optical bench check: ex/em slits, monochromators, BL stability"
        
        
    def xen_hrs(self):
        "Get hours on the Xe lamp. RETURNS 1 if optics not yet checked"
        msg = [0x45]
        return hex2dec(remove_prefix(self.query(msg), '0'+hex2ascii(msg).decode()))
        
    # SOFTWARE HANDSHAKING METHODS
    def query(self, msg):
        "Enframe query (presently bytelist), send to instrument, return reply"
        self.__ser__.flush()
        # two handshakes?
        for i in range(2):
            self.etx(True)
            self.enq(True)
            self.ack(False)
        # now send the command
        self.__ser__.write(str2shim(msg))
        # wait for ack
        self.ack(False)
        # send ETX
        self.etx(True)
        # wait for ACK
        self.enq(False)
        # send ACK
        self.ack(True)
        # init block list
        blocks = []
        # read first data byte
        byte = self.__ser__.read(1)
        # read bytes
        while byte != b'\x85':
            # init block
            block = b''
            while byte != b'\x97':
                # concat prev byte to block
                block += byte
                byte = self.__ser__.read(1)
                if byte == b'\x85':
                    # if there aren't any blocks
                    break
            # ACK receipt of block
            blocks.append(block)
            self.ack(True)
        ## get reply to the final ENQ
        #reply = self.__ser__.read_until('\x85')
        ## ACK receipt
        #self.ack(True)
        # wait for ETX to clear the line
        self.etx(False)
        # return
        #return shim2str(reply)
        return [shim2str(block) for block in blocks]
    
    # senders/receivers
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
            
    def etx(self, send=True):
        "Send or recieve ETX"
        self.signal(send, b'\x04')
        
    def etb(self, send=True):
        "Send or recieve ETB"
        self.signal(send, b'\x97')
    
    ## Shimadzu MODBUS protocol methods
    def meas(self, status):
        # start or stop returning fluorescence data
        if status:
            # send ENQ
            self.__ser__.write(serial.to_bytes([0x85]))
            # wait for ACK
            while self.__ser__.read(1) != 0x86:
                pass
            # wait for ENQ
            while self.__ser__.read(1) != 0x85:
                pass
            # turn on
            self.__ser__.write(str2shim([0x57, 0xcd]))
    
    # wait the specified num of character times
    def wait_bytes(self, num_bytes):
        sleep(num_bytes / (self.__ser__.baudrate / 8))
    
    # clear the buffer and start transmission
    def start_xmit(self):
        if self.__ser__.read() == b'x85': #DCE ENQ
            self.__ser__.write(serial.to_bytes([0x86])) #DTE ACK
        self.__ser__.write(serial.to_bytes([0x02])) #DTE STX
        #self.wait_bytes(3.5)
        
    # send EOT and clear the buffer
    def end_xmit(self, timeout = 4):
        for i in list(range(timeout)):
            byte = self.__ser__.read()
            if byte == b'x85': #DCE ENQ
                self.__ser__.write(serial.to_bytes([0x86])) #DTE ACK
            elif byte == b'x86': #DCE ACK
                self.__ser__.write(serial.to_bytes([0x04])) #DTE EOT
            #else: return True
    
        
    # do the little dance and get a packet back
    def call_response(self):
        while True:
            byte = self.__ser__.read()
            if byte == b'x85': #DCE ENQ
                self.__ser__.write(serial.to_bytes([0x86])) #DTE ACK
            elif byte == b'x86': #DCE ACK
                self.__ser__.write(serial.to_bytes([0x04])) #DTE EOT
                return self.__ser__.readline()
            else: return self.__ser__.readline()
    
    # send ENQ (0x85), return true if ACK (0x86)
    def enq_ack(self):
        self.__ser__.write(serial.to_bytes([0x85])) #DTE ENQ
        return (self.__ser__.read() == b'\x86') #DCE ACK
        
    # clear read buffer,
    # make sure the spec is happy and not sending ENQs
    def clear_com_status(self):
        rbuff = self.__ser__.readline()
        if (b'x85' in rbuff) and (b'x04' not in rbuff):
            self.__ser__.write(serial.to_bytes([0x86])) #DTE ACK
        return self.enq_ack()
        
    def shutter_close(self):
        while (not self.clear_com_status()):
            pass
        # STX + shutter close message
        self.__ser__.write(serial.to_bytes([0x02, 0xce, 0x32, 0x83, 0x7f]))
        print(self.__ser__.readline()) #TEST
        # hardwired for now
        self.__ser__.write(serial.to_bytes([0x04])) #DTE EOT
        self.__ser__.write(serial.to_bytes([0x86])) #DTE ACK
        print(self.__ser__.readline()) #TEST
        self.__ser__.write(serial.to_bytes([0x86])) #DTE ACK
    
    def shutter_open(self):
        while (not self.clear_com_status()):
            pass
        # STX + shutter open message
        self.__ser__.write(serial.to_bytes([0x02, 0xce, 0x31, 0x83, 0x7c]))
        print(self.__ser__.readline()) #TEST
        self.__ser__.write(serial.to_bytes([0x04])) #DTE EOT
        self.__ser__.write(serial.to_bytes([0x86])) #DTE ACK
        print(self.__ser__.readline()) #TEST
        self.__ser__.write(serial.to_bytes([0x86])) #DTE ACK
                
    def get_wl_ex(self):
        pack = ascii2hex("WX")
        pack += ("\\x83" + "\\x8c")
        print(serial.to_bytes([0x57, 0x58, 0x83, 0x8c]))
        #self.__ser__.write(pack.encode())
        self.__ser__.write(serial.to_bytes([0x57, 0x58, 0x83, 0x8c]))
        # gives b'WX\x83\x8c', which is probably correct
        return self.__ser__.readline()
        
    def get_wl_em(self):
        pack = ascii2hex("WM")
        pack += ("\\x83" + "\\x19")
        print(pack.encode())
        self.__ser__.write(pack.encode())
        return self.__ser__.readline()
    
    def goto_wl(self, ex, em):
        wl_hex = [str(hex(wl*10)).upper()[2:].zfill(4) for wl in (ex, em)]
        pack = "WA{}{}".format(*wl_hex).encode()
        # test checkbyte
        pack += ("0x83".encode() + "0x1c".encode())
        self.__ser__.write(pack)
        print(pack)

#spec = RF5301(port="/dev/cu.usbserial-FTV5C58R0")
    
"""# load captured packets from stdin
data_serial = pd.read_table(stdin, skiprows=61, header=None, sep=r"[ ]{1,}")
# chomp first two rows and drop null columns
data_serial = data_serial[2:].dropna(axis = "columns", how = "all")

# set headers
#data_serial.columns = data_serial[0:1].values.tolist()
data_serial.columns = [
    "Date",
    "Time",
    "AM/PM",
    "Delta",
    "Byte Number",
    "Frame Number",
    "Type",
    "Hex",
    "Dec",
    "Oct",
    "Bin",
    "Side",
    "ASCII",
    "RTS",
    "CTS",
    "DSR",
    "DTR",
    "CD",
    "RI",
    "UART Overrun",
    "Parity Error",
    "Framing Error"
    ]
    
# drop rows containing illegal binary
data_serial = data_serial[~data_serial.Bin.str.contains("<")]

#print(data_serial.to_string())

ascii = data_serial["ASCII"].values.tolist()
words = list(filter(None, "".join(ascii).split(".")))
# take last 6 chars of words at least 6 chars long
raw_hex = [word[-6:] for word in words if len(word) >= 6]

# convert hex to decimal, chuck invalid hex digits
# assuming these are some kind of control signal
print(raw_hex)
#raw_dec = [hex2dec(y) for y in raw_hex]
raw_dec = []
for hex in raw_hex:
    try:
        raw_dec.append(hex2dec(hex))
    except:
        pass
        
# scale decimal
fin_dec = [float(y)/1000 for y in raw_dec if ((y >= -1E5) and (y < 1E6))]
print(fin_dec)

plt.plot(fin_dec)
plt.show()"""