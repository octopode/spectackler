#!/env/python

"""
socatrans.py
Read socat hex output from stdin (-x) and make it (almost) plain English.
A must-have for cheap n00b protocol reverse engineers.

ex:
socat -x -dd /dev/cu.usbserial-FT4IVKAO0,raw,echo=0,crnl /dev/cu.usbserial-FT4IVKAO1,raw,echo=0,crnl 2>&1 | \
    tee hex.log | socatrans.py | asc.log
    
NOTE: tee *is* required to save the log
"""

import sys

def hex2asc(hex):
    "Convert hex to 7-bit ASCII and eat the parity bit."
    ch = chr(int('0x'+hex, 16)%128)
    if ch is ' ':
        return '\\x'+hex
    else:
        return ch
        
iodict = {'>': "TX", '<': "RX"}
hexout = ascout = True

ln = 0
while True:
    line = sys.stdin.readline()
    try: line[0]
    except: break
    if line[0] in iodict.keys():
        leader = str(ln)+'\t'+iodict[line[0]]+'\t'
    else:
        hexvec = line.split(' ')
        if hexout:
            print(leader, end='')
            print([hex.strip() for hex in hexvec if hex is not ''])
        if ascout:
            print(leader, end='')
            print([let for let in [hex2asc(ch.strip()) if ch is not '' else ' ' for ch in hexvec] if let != ' '])
        ln+=1