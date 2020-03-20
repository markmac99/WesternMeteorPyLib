""" Preprocess the simulations before feeding them into the neural network. """

from __future__ import print_function, division, absolute_import, unicode_literals


import os
import random

import numpy as np

from wmpl.MetSim.ML.GenerateSimulations import MetParam, ErosionSimContainer, ErosionSimParametersCAMO, \
    extractSimData
from wmpl.Utils.Pickling import loadPickle


def preprocessSims(data_path, min_frames_visible=10):
    """ Preprocess simulations generated by the ablation model to prepare them for training. 
    
    From all simulations, make fake observations by taking only data above the limiting magnitude and
    add noise to simulated data.

    Arguments:
        dir_path:
        output_dir:

    """

    # A list of trajectories that satisfy the visibility criteria
    good_list = []

    # Go through all simulations
    for file_name in os.listdir(data_path):

        file_path = os.path.join(data_path, file_name)

        # Check if the given file is a pickle file
        if os.path.isfile(file_path) and file_name.endswith(".pickle"):

            # Load the pickle file
            sim = loadPickle(data_path, file_name)

            # Extract simulation data
            res = extractSimData(sim, min_frames_visible=min_frames_visible)

            # If the simulation didn't satisfy the filters, skip it
            if res is None:
                continue

            # If all conditions are satisfied, add the trajectory to the processing list
            good_list.append(file_name)

            print("Good:", file_name)


    # Randomize the list
    random.shuffle(good_list)


    # Compute the average minimum time the meteor needs to be visible
    min_time_visible = min_frames_visible/sim.params.fps \
        + (sim.params.len_delay_min + sim.params.len_delay_max)/2

    # Save the list of good files to disk
    good_list_file_name = "lm{:+04.1f}_mintime{:.3f}s_good_files.txt".format( \
        (sim.params.lim_mag_faintest + sim.params.lim_mag_brightest)/2, min_time_visible)

    with open(os.path.join(data_path, good_list_file_name), 'w') as f:
        for file_name in good_list:
            f.write("{:s}\n".format(file_name))

    print("{:d} entries saved to {:s}".format(len(good_list), good_list_file_name))





if __name__ == "__main__":

    import argparse


    ### COMMAND LINE ARGUMENTS

    # Init the command line arguments parser
    arg_parser = argparse.ArgumentParser(description="Check that the simulations in the given directory satisfy the given conditions and create a file with the list of simulation to use for training.")

    arg_parser.add_argument('dir_path', metavar='DIR_PATH', type=str, \
        help="Path to the directory with simulation pickle files.")

    # Parse the command line arguments
    cml_args = arg_parser.parse_args()

    #########################

    # Preprocess simulations
    preprocessSims(cml_args.dir_path)