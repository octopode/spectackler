#!/usr/bin/python3

"""
Real-time visual and numerical analyzer for temperature scans.
Read TSV file with setpoint and actual temperature traces, plot them all.
Also plot and calculate pairwise correlations between actual temps from right before
setpoint changes.
"""

import sys
import argparse
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import itertools
import pandas as pd
        
def animate(i, farg):
    "Called on loop from FuncAnimation; effectively the body routine"
    
    data = pd.read_csv(args.file_data, sep='\t')

    # Plot temp/time traces
    axs[0].clear()
    for col, color in zip(([args.T_set_col] + args.T_act_cols), (["black"] + args.colors)):
        axs[0].plot(data[args.t_col], data[col], c=color)
    
    # plot sensor correlations
    # filter temp traces to just equilibrated values before the setpoint change
    data_eqbr = data[data[args.T_set_col] != data[args.T_set_col].shift(periods=-1)][:-1]
    for ax in axs[1:]:
        # names of traces to be correlated are passed thru the global axes object
        ax.plot(data_eqbr[ax.get_xlabel()], data_eqbr[ax.get_ylabel()], linewidth=0, marker='o', color="black")
    
        
def parse_args(argv):
    "Parse command line arguments"
    
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    if not len(argv):
        argv.append("-h")
        
    parser.add_argument('-f', "--file_data", help="continuously read log of temp, P, I, D traces")
    parser.add_argument("--t_col", help="name of ordinal time column", default="watch")
    parser.add_argument("--T_set_col", help="name of temp setpoint", default="T_set")
    parser.add_argument("--T_act_cols", help="names of actual temp columns", nargs='+', default=["T_int", "T_ext"])
    parser.add_argument("--colors", help="trace colors", nargs='+', default=["red", "green"])
    parser.add_argument('-r', "--refresh", help="refresh period in ms", type=int, default=1000)
        
    return parser.parse_args(argv)

def main(args, stdin, stdout, stderr):

    # check that the file exists
    pd.read_csv(args.file_data, sep='\t')
    
    # Create figure for plotting
    fig = plt.figure()
    # gridspec with 2 columns and nC2 columns, where n=number of temp sensors
    correl_pairs = list(itertools.combinations(args.T_act_cols, r=2))
    gs = fig.add_gridspec(2, len(correl_pairs))
    
    # initialize axes
    global axs
    # first axes are the trace panel, which spans the entire top row
    axs = [fig.add_subplot(gs[0, :])]
    for correl in range(len(correl_pairs)):
        axs.append(fig.add_subplot(gs[1, correl]))
        axs[correl + 1]
    
    # axis labels
    axs[0].set(xlabel="time (s)", ylabel="temperature (˚C)")
    for ax, pair in zip(axs[1:], correl_pairs):
        ax.set(xlabel=pair[0], ylabel=pair[1])
        
    # initialize traces
        
    # Set up plot to call animate() function periodically
    ani = animation.FuncAnimation(fig, animate, fargs=[1], interval=args.refresh)
    plt.show()
            
if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    main(args, sys.stdin, sys.stdout, sys.stderr)