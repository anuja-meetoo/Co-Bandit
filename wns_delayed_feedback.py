#!/usr/bin/python3
'''
@description:   Simulate a collaborative version of Exponential Weighted Average for wireless network selection which allows devices to share their observations with their
                neighbors, with the aim of improving the rate of convergence to Nash equilibrium.
@assumptions:   (1) all devices are in the service area throughout the simulation, (2) all devices see the same wireless networks, (3) mobile devices are time-synchronized,
                (4) mobile devices have enough battery to collaborate with neighbors (broadcasting data using BLE and scanning for data), (5) all devices who broadcast data
                at a time slot are able to get their data to all devices who are listening at that time.
@author:        Anuja
@date:          18 January 2018; @update: 8 May 2018, 1-2 October 2018
'''

import simpy
from network import Network
import global_setting
import argparse
import os
from utility_method import createCSVfile, computeDistanceToNashEquilibrium, saveToCSV, getTimeTaken, computeNashEquilibriumState, plot, isNashEquilibrium
import time
import csv

''' ______________________________________________________________________________ constants ______________________________________________________________________________ '''
global_setting.constants.update({'beta':0.1})
global_setting.constants.update({'time_slot_duration':15})
global_setting.constants.update({'epsilon':7.5})
global_setting.constants.update({'converged_probability':0.75})
global_setting.constants.update({'max_time_slot_considered_prev_block':8})
global_setting.constants.update({'min_block_length_periodic_reset':40})
global_setting.constants.update({'num_consecutive_slot_for_reset':4})
global_setting.constants.update({'percentage_decline_for_reset':15})
global_setting.constants.update({'gain_rolling_average_window_size':12})

# for collaborative version
global_setting.constants.update({'min_gamma':0.001}); global_setting.constants.update({'max_gamma':0.1}) # min and max values of gamma
# global_setting.constants.update({'eta':20})
# transmitProb = 1 #1/NUM_SUB_TIME_SLOT
# listenProb = 1    #2/NUM_SUB_TIME_SLOT #1 - transmitProb
# gamma = 0#0.001
# global_setting.constants.update({'window_size':3})#8}) # virtual window for algorithm; expect to hear about all networks within that window...

# set from values passed as arguments when the program is executed
parser = argparse.ArgumentParser(description='Simulates the wireless network selection by a number of wireless devices in the service area.')
parser.add_argument('-n', dest="num_device", required=True, help='number of active devices in the service area')
parser.add_argument('-k', dest="num_network", required=True, help='number of wireless networks in the service area')
parser.add_argument('-b', dest="network_bandwidth", required=True, help='total bandwidth of each network as a string separated with "_".')
parser.add_argument('-t', dest="num_time_slot", required=True, help='number of time slots in the simulation run')
parser.add_argument('-r', dest="run_index", required=True, help='current run index')
parser.add_argument('-a', dest="algorithm_name", required=True, help='name of selection algorithm used by the devices')
parser.add_argument('-dir', dest="directory", required=True, help='root directory containing the simulation files')
parser.add_argument('-s', dest="setting", required=True, help='setting being simulated')
parser.add_argument('-m', dest="save_minimal", required=True, help='whether to save minimal details in network and device csv files')
parser.add_argument('-st', dest="num_sub_time_slot", required=True, help='number of sub-time slots in one time slot')
parser.add_argument('-d', dest="delay", required=True, help='maximum delayed feedback considered')
parser.add_argument('-e', dest="eta", required=True, help='learning rate')
parser.add_argument('-g', dest="gamma", required=True, help='gamma that controls tje explicit exploration term')
parser.add_argument('-pt', dest="transmit_probability", required=True, help='probability with which to transmit')
parser.add_argument('-pl', dest="listen_probability", required=True, help='probability with which to listen')
parser.add_argument('-ne', dest="nash_equilibrium_state_list", required=True, help='list of Nash equilibrium states')
parser.add_argument('-max', dest="max_time_unheard_acceptable", required=True, help='maximum time a network can be unheard of')
args = parser.parse_args()
NUM_MOBILE_DEVICE = int(args.num_device); global_setting.constants.update({'num_mobile_device':NUM_MOBILE_DEVICE})
NUM_NETWORK = int(args.num_network); global_setting.constants.update({'num_network':NUM_NETWORK})
NETWORK_BANDWIDTH = args.network_bandwidth.split("_"); NETWORK_BANDWIDTH = [int(x) for x in NETWORK_BANDWIDTH]; global_setting.constants.update({'network_bandwidth':NETWORK_BANDWIDTH})  # in Mbps
NUM_TIME_SLOT = int(args.num_time_slot); global_setting.constants.update({'num_time_slot':NUM_TIME_SLOT})
global_setting.constants.update({'num_sub_time_slot':int(args.num_sub_time_slot)})  # per time slot
global_setting.constants.update({'delay':int(args.delay)})
global_setting.constants.update({'run_num':int(args.run_index)})
ALGORITHM_NAME = args.algorithm_name; global_setting.constants.update({'algorithm_name':ALGORITHM_NAME})
DIR = args.directory; global_setting.constants.update({'output_dir':DIR})
SETTING = int(args.setting); global_setting.constants.update({'setting':SETTING})
SAVE_MINIMAL = int(args.save_minimal); global_setting.constants.update({'save_minimal_detail':SAVE_MINIMAL})
global_setting.constants.update({'eta':float(args.eta)})
global_setting.constants.update({'gamma':float(args.gamma)})
global_setting.constants.update({'p_t':float(args.transmit_probability)})
global_setting.constants.update({'p_l':float(args.listen_probability)})
nashEquilibriumStates = args.nash_equilibrium_state_list.split(";");
global_setting.constants.update({'max_time_unheard_acceptable':int(args.max_time_unheard_acceptable)})
nashEquilibriumStateList = []
for state in nashEquilibriumStates: state = state.split("_"); state = [int(x) for x in state]; nashEquilibriumStateList.append(state)

''' ____________________________________________________________________ setup and start the simulation ___________________________________________________________________ '''
startTime = time.time()

env = simpy.Environment()

# print("p_t = ", global_setting.constants['p_t'])
if not os.path.exists(DIR): os.makedirs(DIR)                                     # create output directory if it doesn't exist

networkList = [Network(NETWORK_BANDWIDTH[i]) for i in range(NUM_NETWORK)]        # create network objects and store in networkList
global_setting.constants.update({'network_list':networkList})
from mobile_device import MobileDevice

# create mobile device objects and store in mobileDeviceList
if SETTING == 4:    # mobility scenario
    mobileDeviceList = []
    for i in range(10): mobileDeviceList.append(MobileDevice(networkList[:3]))
    for i in range(5): mobileDeviceList.append(MobileDevice([networkList[0]] + networkList[2:]))
    for i in range(5): mobileDeviceList.append(MobileDevice([networkList[0]] + networkList[3:]))
else: mobileDeviceList = [MobileDevice(networkList) for i in range(NUM_MOBILE_DEVICE)]
# mobileDeviceList = [MobileDevice(networkList) for i in range(NUM_MOBILE_DEVICE)]

# create the network and device csv files
createCSVfile(NUM_MOBILE_DEVICE, NUM_NETWORK, DIR, SETTING, SAVE_MINIMAL, ALGORITHM_NAME)

# print("nashEquilibriumStateList:", nashEquilibriumStateList); input()
for i in range(NUM_MOBILE_DEVICE):
    if ALGORITHM_NAME == "EXP3":  # each mobile device object calls the method Smart EXP3
        proc = env.process(mobileDeviceList[i].EXP3(env))                       # each mobile device object calls the method EXP3
    elif ALGORITHM_NAME == "SmartEXP3":                                         # each mobile device object calls the method Smart EXP3
        proc = env.process(mobileDeviceList[i].smartEXP3(env))
    elif ALGORITHM_NAME == "CollaborativeEWA":                            # each mobile device object calls the method for collaborative weighted average for full information
        proc = env.process(mobileDeviceList[i].collaborativeEWA(env))
    elif ALGORITHM_NAME == "CollaborativeEXP3":                                 # each mobile device object calls the method for collaborative EXP3
        proc = env.process(mobileDeviceList[i].collaborativeEXP3(env))
    elif ALGORITHM_NAME == "FullInformation":                                   # each mobile device object calls the method for weighted average for full information
        proc = env.process(mobileDeviceList[i].fullInformation(env))

env.run(until=proc)  # SIM_TIME)

endTime = time.time()
timeTaken, unit = getTimeTaken(startTime, endTime)

print("----- simulation completed in %s %s -----" % (timeTaken, unit))

# print("reset", MobileDevice.resetTimeSlotPerDevice)
if ALGORITHM_NAME == "CollaborativeEWA":
    header = ["deviceID", "#reset", "timeslot"]; data = []
    for networkID in range(1, NUM_MOBILE_DEVICE + 1): data.append([networkID, len(MobileDevice.resetTimeSlotPerDevice[networkID]), MobileDevice.resetTimeSlotPerDevice[networkID]])
    saveToCSV(DIR + "reset.csv", header, data)

# nashEquilibriumStateList = computeNashEquilibriumState(NUM_MOBILE_DEVICE, NUM_NETWORK, NETWORK_BANDWIDTH)
# print("nashEquilibriumStates:", nashEquilibriumStates)
# print("nashEquilibriumStateList:", nashEquilibriumStateList)
# print(percentageNashEquilibrium(DIR + "network.csv", NUM_NETWORK, nashEquilibriumStateList), "% time spent at NE")
if SETTING != 4:
    distanceToNE = computeDistanceToNashEquilibrium(NUM_NETWORK, DIR + "network.csv", NETWORK_BANDWIDTH, nashEquilibriumStateList, SETTING, NUM_TIME_SLOT)
    outputfile = DIR + "distanceToNashEquilibrium.csv"
    # saveToCSV(outputfile, ["Time_slot", "Distance_to_Nash_equilibrium"], distanceToNE)
    saveToCSV(outputfile, ["Distance_to_Nash_equilibrium"], distanceToNE)
    # print(distanceToNE.count([0])*100/NUM_TIME_SLOT, "% time spent at NE")
    # print("distance:", distanceToNE)
    # plot(outputfile, len(distanceToNE))
''' _____________________________________________________________________________ end of file _____________________________________________________________________________ '''