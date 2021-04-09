#!/usr/bin/python3

import os
import sys
import pandas as pd
import random
import subprocess

def calcLRC_dec(input):
    lrc = input[0]
    for i in range(1,len(input)):
        lrc ^= input[i]
    return lrc

# where to look for capture files
dir_packets = "/Users/jwinnikoff/Documents/MBARI/spectackler/RF5301_packets/packets"
# filename pattern
suffix = ".tsv"

# load files
files_all = os.listdir(dir_packets)
files_suffix = [filename for filename in files_all if suffix in filename]

messages = [''.join(str(i) for i in list(pd.read_csv(os.path.join(dir_packets, file), sep='\t').iloc[1:-1,:].loc[:,"Hex"])) for file in files_suffix]

print(set(messages))

while True:
	# pull four messages randomly and run reveng
	samp_messages = random.sample(set(messages), 4)
	cmd_reveng = "reveng -w 16 -q 0 -F -s " + ' '.join(samp_messages)
	try:
		result = subprocess.check_output(cmd_reveng, shell=True, stderr=subprocess.DEVNULL)
	except subprocess.CalledProcessError:
		result = False
		pass
	if result and (result.decode() != "reveng: no models found"):
		print(cmd_reveng)
		print(result.decode())

#first_checkbyte = []
#for file in files_suffix:
#	table = pd.read_csv(os.path.join(dir_packets, file), sep='\t').iloc[1:-1,:]
#	hex = list(table.loc[:,"Hex"])
#	dec = list(table.loc[:,"Dec"])
#	#lrc_predict = -sum(dec[:-2])%256
#	#lrc_predict = calcLRC_dec(dec[:-2])
#	#lrc_actual = dec[-2:]
#	# even length data only
#	#if len(dec[:-2])%2 == 0:
#	#   print("{} {} {}".format(dec, lrc_actual, lrc_predict))
#	#print("{} {}".format(' '.join(str(i) for i in hex[:-2]), hex[-2:]))
#	first_checkbyte.append(dec[-2])
#	# prints whole message, checksum and all
#	#print(''.join(str(i) for i in hex))
#	
#print(set(first_checkbyte))