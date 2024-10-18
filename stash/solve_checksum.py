#!/usr/bin/python3

import sys
import os
import pandas as pd
import matplotlib.pyplot as plt
import string

def extract_packets(hex_stream):
    reading = False
    packet = []
    packets = []
    for byte in hex_stream:
        # comparison seems to work only in decimal!?!
        if byte == 2:
            reading = True
        if reading == True:
            packet.append(hex(byte))
        if byte == 134:
            reading = False
            packets.append(packet)
            packet = []
            
    return packets
    
def hex2ascii(hex):
    hex_string = hex[2:] # trim "0x"
    if len(hex_string) == 1:
        hex_string = "0" + hex_string
    bytes_object = bytes.fromhex(hex_string)
    try:
        ascii_string = bytes_object.decode("ASCII")
    except:
        ascii_string = "."
        pass
    
    return ascii_string
    
def hex2dec(hex):
    hex = "0x" + hex
    return -(int(hex, 16) & 0x800000) | (int(hex, 16) & 0x7fffff)
    
def calcLRC(input):
    lrc = ord(input[0])
    for i in range(1,len(input)):
        lrc ^= ord(input[i])     
    return lrc
    
def all_odd(input):
    return [term+1 if term%2 == 0 else term for term in input]
    
def all_even(input):
    return [term if term%2 == 0 else term+1 for term in input]

# same as above, takes list of numbers
def calcLRC_dec(input):
    lrc = input[0]
    for i in range(1,len(input)):
        lrc ^= input[i]
    return lrc
"""   
def calcLRC_dec2(input):
    lrc = input[0]
    for i in range(1,len(input)):
        lrc = (lrc + input[i]) & 0xFF
    return (((lrc ^ 0xFF) + 1) & 0xFF)
"""
    
#EVEN BYTE COUNT

[176,87,88,176,196,52,56,131] # 68; should be 196

[76,176,176,49,185,179,67,151] # 163; should be 35

#ODD
[87,193,176,196,52,56,49,49,179,176,131] # LRC 110! Correct!

[87, 88, 176, 69, 52, 50, 131] # 127! YES!

[206,50,131] # 127, good!


# where to look for capture files
dir_captures = "/Users/jwinnikoff/Documents/MBARI/spectackler/RF5301_packets"
# filename pattern
suffix = ".txt"

# load files
files_all = os.listdir(dir_captures)
files_suffix = [filename for filename in files_all if suffix in filename]

tables_capture = {}
hex_capture = []
for file in files_suffix:
    print(file)
    try:
        table = pd.read_csv(os.path.join(dir_captures, file), skiprows = 61, delim_whitespace=True).iloc[1:-1,:]
        if "7-bit_ASCII" in table.columns:
            tables_capture[file] = table
        hex_capture.append([eval('0x'+string) for string in list(table.loc[:,"Hex"])])
    except:
        print("PARSE ERR")
        pass

tables_packets = {}
for file, table in tables_capture.items():
    # filter the table to rows containing only one byte each (there are some glitches)
    tables_capture[file] = table.loc[table['7-bit_ASCII'].isin(list(string.printable))]
    # now, split it into packets
    packets = []
    packet = []
    reading = False
    for i, row in tables_capture[file].iterrows():
        byte = int(row["Dec"])
        if byte == 2:
            reading = True
        if reading == True:
            packet.append(row)
        if byte == 134:
            reading = False
            try:
                #print(pd.concat(packet))
                packets.append(pd.concat(packet, axis=1).transpose())
            except:
                #print("empty packet!")
                pass
            packet = []
    tables_packets[file] = packets
    
for file, stream in tables_packets.items():
    for i, packet in enumerate(stream):
        packet.to_csv(os.path.join(dir_captures, "packets", file.replace(".txt", "")+"_"+str(i)+".tsv"), sep='\t')
#print(tables_packets)
    
    #tables_capture[file].to_csv(sys.stdout, sep='\t')
    #tables_capture[file].to_csv(os.path.join(dir_captures, file.replace(".txt", ".tsv")), sep='\t')
    #ascii_streams[file] = ''.join(str(byte) for byte in list(table.loc[:,"7-bit_ASCII"]) if len(str(byte)) == 1)
    


#print("parsed "+str(len(packets_all))+" packets")
"""
# summary of the valid modulos
mod_dist = {val: mod_ok.count(val) for val in sorted(set(mod_ok))}
print(mod_dist)
plt.bar(mod_dist.keys(), mod_dist.values())
#plt.text(mod_dist.keys(), mod_dist.values(), [str(val) for val in mod_dist.values()], color='blue', va='center', fontweight='bold')
plt.show()
"""