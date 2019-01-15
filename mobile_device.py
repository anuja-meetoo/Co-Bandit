'''
@description:   Defines a class that models a mobile device
'''

''' ______________________________________________________________________ import external libraries ______________________________________________________________________ '''
import simpy
from random import randint, choice, uniform
from math import exp, sqrt, log, ceil, e
import numpy as np
import pandas
from scipy.stats import t, johnsonsu
from copy import deepcopy
import csv                          # to save output to file
from sys import argv, float_info    # to read command line argument; float_info to get the smallest float value
from time import time, sleep
from statistics import median
from network import Network
from utility_method import computeMovingAverage, getListIndex, percentageElemGreaterOrEqual, combineObservation, decrementTTL
import global_setting
from multiprocessing import Lock
from termcolor import colored

''' _____________________________________________________________________________ for logging _____________________________________________________________________________ '''
import logging
from colorlog import ColoredFormatter   # install using sudo pip3 install colorlog

LOG_LEVEL = logging.INFO
logging.root.setLevel(LOG_LEVEL)
formatter = ColoredFormatter(
    "  %(log_color)s%(levelname)-8s%(reset)s %(log_color)s%(message)s%(reset)s",
	datefmt=None,
	reset=True,
	log_colors={
		'DEBUG':    'cyan',
		'INFO':     'green',
		'WARNING':  'yellow',
		'ERROR':    'red',
		'CRITICAL': 'white,bg_red',
	},
	secondary_log_colors={},
	style='%'
)
stream = logging.StreamHandler()
stream.setLevel(LOG_LEVEL)
stream.setFormatter(formatter)
logging = logging.getLogger('pythonConfig')
logging.setLevel(LOG_LEVEL)
logging.addHandler(stream)

''' ______________________________________________________________________________ constants ______________________________________________________________________________ '''
BETA = global_setting.constants['beta']                             # beta is used in block length update rule
TIME_SLOT_DURATION = global_setting.constants['time_slot_duration'] # duration of a time step in seconds
EPSILON = global_setting.constants['epsilon']
CONVERGED_PROBABILITY = global_setting.constants['converged_probability']
MAX_TIME_SLOT_CONSIDERED_PREV_BLOCK = global_setting.constants['max_time_slot_considered_prev_block']
MIN_BLOCK_LENGTH_PERIODIC_RESET = global_setting.constants['min_block_length_periodic_reset']
NUM_CONSECUTIVE_SLOT_FOR_RESET = global_setting.constants['num_consecutive_slot_for_reset']
PERCENTAGE_DECLINE_FOR_RESET = global_setting.constants['percentage_decline_for_reset']
GAIN_ROLLING_AVERAGE_WINDOW_SIZE = global_setting.constants['gain_rolling_average_window_size']

# for collaborative version
MIN_GAMMA = global_setting.constants['min_gamma']; MAX_GAMMA = global_setting.constants['max_gamma']
ETA = global_setting.constants['eta']
GAMMA = global_setting.constants['gamma']
TRANSMIT_PROBABILITY = global_setting.constants['p_t']
LISTEN_PROBABILITY = global_setting.constants['p_l']
# WINDOW_SIZE = global_setting.constants['window_size'] # virtual window for algorithm; expect to hear about all networks within that window...

NUM_MOBILE_DEVICE = global_setting.constants['num_mobile_device']
NUM_NETWORK = global_setting.constants['num_network']
NETWORK_BANDWIDTH = global_setting.constants['network_bandwidth'] # in Mbps
NUM_TIME_SLOT = global_setting.constants['num_time_slot']
NUM_SUB_TIME_SLOT = global_setting.constants['num_sub_time_slot']
DELAY = global_setting.constants['delay']
RUN_NUM = global_setting.constants['run_num']
ALGORITHM = global_setting.constants['algorithm_name']
ORIGINAL_OUTPUT_DIR = OUTPUT_DIR = global_setting.constants['output_dir']
SETTING = global_setting.constants['setting']
SAVE_MINIMAL_DETAIL = global_setting.constants['save_minimal_detail']
networkList = global_setting.constants['network_list']
MAX_TIME_UNHEARD_ACCEPTABLE = global_setting.constants['max_time_unheard_acceptable']

lock = Lock()
''' ____________________________________________________________________ MobileDevice class definition ____________________________________________________________________ '''
class MobileDevice(object):
    numMobileDevice = 0                                     # keeps track of number of mobile devices to automatically assign an ID to device upon creation
    sharedObservation = {}                                  # observations about networks shared among devices; there may be more than one service area
    resetTimeSlotPerDevice = {}

    def __init__(self, networks):
        MobileDevice.numMobileDevice = MobileDevice.numMobileDevice + 1
        self.deviceID = MobileDevice.numMobileDevice              # ID of device
        self.availableNetwork = [networks[i].networkID for i in range(len(networks))]  # networkIDs of set of available networks
        self.weight = [1.0] * len(self.availableNetwork)    # weight assigned to each network based on gains observed from it
        self.probability = [0] * len(self.availableNetwork) # probability distribution over available networks
        self.currentNetwork = -1                            # network to which the device is currently associated
        self.gain = 0                                       # bit rate observed
        self.download = 0                                   # amount of data downloaded in Mbits (takes into account switching cost)
        self.maxGain = max([NETWORK_BANDWIDTH[i - 1] for i in self.availableNetwork])
        self.delay = 0                                      # delay incurred while switching network in seconds
        self.exploration = 0                                # whether the algorithm has unexplored network(s)

        # for collaboration
        self.networkDetailHistory = []                      # observation made/received for the past DELAY time slots; used for weight update
        self.timeLastHeard = [-1] * len(self.availableNetwork)          # time slot each network was last heard
        self.recentGainHistoryPerNetwork = {}               # gain that was (or could be) observed from each network over the past few time slots
        self.numDevicePerNetwork = [-1] * len(self.availableNetwork)    # last value I know of
        self.serviceArea = 1
        self.numDevicePerServiceArea = {1:NUM_MOBILE_DEVICE}

        # attribute for log
        self.log = []                                         # something to log to csv file, e.g. whether it's NE, why a type of strategy is chosen, ...

        # to log stabilization; for scalability test
        self.stabilizedNetwork = -1
        self.stabilizationTime = -1
        # end __init__

    ''' ################################################################################################################################################################### '''
    def collaborativeEWA(self, env):
        '''
        description: repeatedly performs a wireless network selection, following a collaborative version of Exponentially Weighted Average algorithm
        args:        self, env
        returns:     None
        '''
        global NUM_TIME_SLOT, NUM_SUB_TIME_SLOT, DELAY, SETTING, ETA, GAMMA, TRANSMIT_PROBABILITY, LISTEN_PROBABILITY, MAX_TIME_UNHEARD_ACCEPTABLE

        # initialization
        subTimeSlot = t = 1                                 # current time slot and sub-time slot (keeps increasing across time slots)
        message = ""                                        # message to be shared during current time slot; includes feedback being forwarded
        feedbackReceived = ""                               # feedback received during current time slot
        prevWeight = []                                     # a copy of the previous weight of all available networks - for logging purpose
        resetTimeSlot = []

        while subTimeSlot <= NUM_TIME_SLOT * NUM_SUB_TIME_SLOT:
            if MobileDevice.updateSetting(self, t):
                MobileDevice.sharedObservation = {}            # reset the shared observation
                yield env.timeout(10)

                if subTimeSlot % NUM_SUB_TIME_SLOT == 1 or NUM_SUB_TIME_SLOT == 1:        # first sub-time slot of current time slot
                    if self.deviceID == 1: logging.debug("t = " + str(t));
                    feedbackReceived = ""                       # clear feedback; it stores feedback received during one time slot
                    self.log = []; actionList = []              # both are for logging
                    prevWeight = deepcopy(self.weight)          # make a copy of the weights since it will be required to save in cvs file later in the current iteration

                    # update probability
                    self.probability = list((1 - GAMMA) * (weight / sum(self.weight)) + (GAMMA / len(self.availableNetwork)) for weight in self.weight)
                    if 0 in self.probability: print("device", self.deviceID, ", zero prob detected! weight:", self.weight, ", prob:", self.probability)

                    # to log stabilization - for scalability test
                    if max(self.probability) >= CONVERGED_PROBABILITY and t <= NUM_TIME_SLOT - 10:
                        networkWithHighestProb = self.availableNetwork[self.probability.index(max(self.probability))]
                        if self.stabilizedNetwork != networkWithHighestProb: self.stabilizedNetwork = networkWithHighestProb; self.stabilizationTime = t
                    elif max(self.probability) < CONVERGED_PROBABILITY and self.stabilizedNetwork != -1: self.stabilizedNetwork = -1; self.stabilizationTime = -1

                    # select a network
                    prevNetworkSelected = self.currentNetwork
                    explore, unheardNetworkList, unheardNetworkProbability, exploreProbability = MobileDevice.mustExploreNetworkUnheardOf(self, t)
                    if explore == True:
                        self.currentNetwork = np.random.choice(unheardNetworkList, p=unheardNetworkProbability)
                        print(colored("@t= " + str(t) + ", device " + str(self.deviceID) + " explores unheard network " + str(self.currentNetwork) + " with prob " + str(exploreProbability), "yellow"))
                    else: self.currentNetwork = np.random.choice(self.availableNetwork, p=self.probability)
                    # self.currentNetwork = np.random.choice(self.availableNetwork, p=self.probability)
                    if self.deviceID == 1: logging.debug("device:" + str(self.deviceID) + ", network:" + str(self.currentNetwork) + ", explore: " + str(explore))

                    # associate with the network selected
                    if prevNetworkSelected != self.currentNetwork:
                        if prevNetworkSelected != -1: MobileDevice.leaveNetwork(self, prevNetworkSelected)
                        MobileDevice.joinNetwork(self, self.currentNetwork); self.delay = MobileDevice.computeDelay(self)
                    else: self.delay = 0

                    yield env.timeout(10)

                    # observe a gain (here it's the same across all sub-time slots of a time slot, hence 'measured' only in the first sub-time slot)
                    MobileDevice.observeGain(self)            # bit rate scaled to the range [0, 1]
                else: yield env.timeout(10)

                # determine whether to transmit or not
                if explore == True: transmit = True; currentProbability = MobileDevice.updateExploreNetworkUnheardOfProbability(self, unheardNetworkList, unheardNetworkProbability, exploreProbability)
                else:
                    transmit = MobileDevice.mustTransmit(self)
                    currentProbability = deepcopy(self.probability)     # to be used in the feedback message

                # build message for transmission; combination of my current observation and all observations made and feedback received
                # message format: [timeslot, deviceID, networkselected, bitrate, numAssociatedDevice, availableNetwork,  probabilityDistribution, ttl]
                myObservation = str(t) + "," + str(self.deviceID) + "," + str(self.currentNetwork) + "," + str(self.gain) + "," \
                                + str(networkList[getListIndex(networkList, self.currentNetwork)].getNumAssociatedDevice()) + "," \
                                + '_'.join(str(network) for network in self.availableNetwork) + "," \
                                + '_'.join(str(prob) for prob in currentProbability) + "," + str(DELAY + 1)
                # combine my observation with all previous valid observation and feedback received; 'message' will be broadcasted
                message = combineObservation(message, myObservation)

                # broadcast feedback and received messages being transmitted
                if transmit == True:
                    MobileDevice.transmit(self, message); actionList.append("TRANSMIT");
                    yield env.timeout(10)                           # transmit
                else: yield env.timeout(10)

                if transmit != True and MobileDevice.mustListen(self):
                    # if MobileDevice.mustListen(self):
                    feedbackReceived = combineObservation(feedbackReceived, MobileDevice.listen(self)); yield env.timeout(10); actionList.append("LISTEN") # listen
                else: yield env.timeout(10);

                if self.deviceID == 1:
                    # logging.debug("global msg:" + MobileDevice.sharedObservation)
                    if self.deviceID == 1: logging.debug("feedback received:" + str(feedbackReceived) + "; message:" + str(message) + "; bit rate:" + str(self.gain))
                if subTimeSlot % NUM_SUB_TIME_SLOT == 0 or NUM_SUB_TIME_SLOT == 1:         # last sub-time slot of current time slot
                    self.log.append(actionList)
                    newObservation = combineObservation(feedbackReceived, myObservation)
                    MobileDevice.updateNetworkDetailHistory(self, t, newObservation)
                    yield env.timeout(10)
                    if self.deviceID == 1: logging.debug("networkDetailHistory: " + str(self.networkDetailHistory) + "----- LENGTH:" + str(len(self.networkDetailHistory)))

                    estimatedLoss = MobileDevice.estimateLoss(self, t)

                    if self.deviceID == 1: logging.debug("time last heard:" + str(self.timeLastHeard) + ", #device per net:" + str(self.numDevicePerNetwork) + ", recent gain:" + str(self.recentGainHistoryPerNetwork))

                    if explore == True: self.log.append("EXPLORE unheard network")
                    else: self.log.append("")

                    # update weight; reset the weight of a network that might be better to 1; and rescale the weights to [0, 1]
                    # reset, networkToReset = MobileDevice.mustReset_collaborativeEWA(self, explore, t) # networkToReset is the index of the network whose weight must be reset
                    # if reset == True:
                    #     MobileDevice.reset_CollaborativeEWA(self, networkToReset); resetTimeSlot.append(t)
                    #     logging.debug("device " + str(self.deviceID) + ", resets its weight (b4 update) " + str(self.weight))
                    self.weight = list(w * exp(-1 * ETA * loss) for w, loss in zip(self.weight, estimatedLoss))
                    maxWeight = max(self.weight); self.weight = [(w / maxWeight) if w / max(self.weight) > 0 else (float_info.min * float_info.epsilon) for w in self.weight]
                    if self.deviceID == 1: logging.debug("weight:" + str(self.weight))

                    message = combineObservation(message, feedbackReceived) # combine the new feedback received to my message to be forwarded in the next time slot
                    message = decrementTTL(message)  # decrement the ttl value of each observation before forwarding them
                    MobileDevice.saveDeviceDetail(self, t, prevWeight, GAMMA, estimatedLoss)  # save device details to csv file
                    if self.deviceID == 1: MobileDevice.saveNetworkDetail(self, t)  # save network details to csv file
                    t += 1
                else: yield env.timeout(10)
                yield env.timeout(10)
                subTimeSlot += 1
                if LOG_LEVEL == 10 and self.deviceID == 1: input()  # if DEBUG level
            else:
                subTimeSlot += 1;
                if subTimeSlot % NUM_SUB_TIME_SLOT == 0 or NUM_SUB_TIME_SLOT == 1: t += 1
                yield env.timeout(60)
            # print("device ", self.deviceID, "done t = ", t)
        logging.info("device" + str(self.deviceID) + " done")
        # logging.info("device " + str(self.deviceID)  + ", reset time slots: " + str(resetTimeSlot))
        MobileDevice.resetTimeSlotPerDevice.update({self.deviceID:resetTimeSlot})
        # end collaborativeEWA

    ''' ################################################################################################################################################################### '''
    def reset_CollaborativeEWA(self, networkToReset):
        '''
        description: resets the weights, and networkDetail
        args:        self
        return:      None
        '''
        for networkIndex in networkToReset: self.weight[networkIndex] = 1
        for j in range(len(self.networkDetailHistory)):
            newElement = {}
            for networkID in self.availableNetwork:
                newElement.update({networkID: {}})
                newElement[networkID].update({'aggregate_bit_rate': 0})
                newElement[networkID].update({'associated_device_list': set()})
                newElement[networkID].update({'probability_list': []})
                newElement[networkID].update({'num_associated_device': 0})
            self.networkDetailHistory[j] = newElement
        # end reset_CollaborativeEWA

    ''' ################################################################################################################################################################### '''
    def mustTransmit(self):
        '''
        description: determines whether there is a need to transmit
        args:        self
        return:      True of False depending on whether need to transmit or not
        '''
        global TRANSMIT_PROBABILITY

        possibleAction = [0, 1]  # transmit or not
        actionProbability = [1 - TRANSMIT_PROBABILITY, TRANSMIT_PROBABILITY]
        transmit = np.random.choice(possibleAction, p=actionProbability)  # select and return an action
        return transmit
        # end mustTransmit

    ''' ################################################################################################################################################################### '''
    def mustListen(self):
        '''
        description: determines whether there is a need to listen to broadcast
        args:        self
        return:      True of False depending on whether need to listen or not
        '''
        global LISTEN_PROBABILITY

        possibleAction = [False, True]  # transmit or not
        actionProbability = [1 - LISTEN_PROBABILITY, LISTEN_PROBABILITY]
        listen = np.random.choice(possibleAction, p=actionProbability)  # select and return an action
        return listen
        # end mustTransmit

    ''' ################################################################################################################################################################### '''
    def updateExploreNetworkUnheardOfProbability(self, unheardNetworkList, unheardNetworkProbability, exploreProbability):
        '''
        description: updates the probability distribution when a device explores a network unheard of; the distribution is used only for the current feedback message
        args:        self, the list of network(s) un heard of, the probability of selecting each of the networks unheard of (we assume a uniform distribution), the
                     probability with which a device considers exploring a network unheard of
        return:      the updated probability distribution
        '''
        currentProbability = deepcopy(self.probability)

        # find aggregate probability of all networks heard (not in unheardNetworkList
        aggregateProb = 0
        # print("unheard:", unheardNetworkList, ", heard:", [x for x in self.availableNetwork if x not in unheardNetworkList])
        # for networkID in [x for x in self.availableNetwork if x not in unheardNetworkList]: aggregateProb += currentProbability[getListIndex(networkList, networkID)]
        for networkID in [x for x in self.availableNetwork if x not in unheardNetworkList]: aggregateProb += currentProbability[self.availableNetwork.index(networkID)]

        for networkID in self.availableNetwork:
            networkIndex = self.availableNetwork.index(networkID)#getListIndex(networkList, networkID)
            if networkID in unheardNetworkList: currentProbability[networkIndex] = exploreProbability * unheardNetworkProbability[-1] # we explore any unheard of network with equal probability
            else: currentProbability[networkIndex] *= (1 - exploreProbability)/aggregateProb
        return currentProbability
        # end updateExploreNetworkUnheardOfProbability

    ''' ################################################################################################################################################################### '''
    def mustExploreNetworkUnheardOf(self, t):
        '''
        description: determines whether there is a need to explore a network not heard since a while
        args:        self, current time slot
        return:      whether to explore an unheard of network (True/False), list of networks unheard of, probability with which to select each of the unheard of networks,
                     the probability with which the device considers to explore some network unheard of
        '''
        global MAX_TIME_UNHEARD_ACCEPTABLE

        explore = False; unheardOfNetworkList = []; unheardOfNetworkProbability = []; exploreProbability = 0

        if (min(self.timeLastHeard) == -1 and t > MAX_TIME_UNHEARD_ACCEPTABLE) or (min(self.timeLastHeard) != -1 and (t - min(self.timeLastHeard)) > MAX_TIME_UNHEARD_ACCEPTABLE):
            # build a list of network(s) unheard of for more than MAX_TIME_UNHEARD_ACCEPTABLE time slots
            for networkID in self.availableNetwork:
                # if t - self.timeLastHeard[getListIndex(networkList, networkID)] > MAX_TIME_UNHEARD_ACCEPTABLE: unheardOfNetworkList.append(networkID)
                if t - self.timeLastHeard[self.availableNetwork.index(networkID)] > MAX_TIME_UNHEARD_ACCEPTABLE: unheardOfNetworkList.append(networkID)
            # any one of the unheard of network will be selected with equal probability
            unheardOfNetworkProbability = [1 / len(unheardOfNetworkList)] * len(unheardOfNetworkList)
            possibleAction = [False, True]  # transmit or not
            # exploreProbability = len(unheardOfNetworkList)/NUM_MOBILE_DEVICE
            exploreProbability = len(unheardOfNetworkList)/self.numDevicePerServiceArea[self.serviceArea]
            actionSelectionProbability = [1 - exploreProbability, exploreProbability]
            # exploreProbability = actionSelectionProbability[-1] * (1/len(unheardOfNetworkList))
            explore = np.random.choice(possibleAction, p=actionSelectionProbability)

        if self.deviceID == 1: logging.debug("explore? " + str(explore) + ", unheardNetworkList: " + str(unheardOfNetworkList) + ", unheardNetworkSelectionProbability:" +
                                     str(unheardOfNetworkProbability) + ", exploreProbability:" + str(exploreProbability))

        return explore, unheardOfNetworkList, unheardOfNetworkProbability, exploreProbability
        # end mustExploreNetworkUnheardOf

    ''' ################################################################################################################################################################### '''
    def mustReset_collaborativeEWA(self, explore, currentTimeSlot):
        '''
        description: determines whether the collaborative EWA algorithm must reset; this is true when (1) the device observes higher gain from a network being explored as
                     no one shared details about it (assuming in this case that no one was associated to that network and the device will be better off there), and (2) the
                     device has converged (favors a network with sufficiently high probability) but constantly hears that more bandwidth is available from another network
        args:        self
        return:      True or False depending on whether the algorithm must reset or not
        '''
        global CONVERGED_PROBABILITY, MAX_TIME_UNHEARD_ACCEPTABLE

        # preferredNetworkIndex = self.probability.index(max(self.probability)); preferredNetworkID = networkList[preferredNetworkIndex].networkID
        preferredNetworkIndex = self.probability.index(max(self.probability)); preferredNetworkID = self.availableNetwork[preferredNetworkIndex]
        if self.deviceID == 1: logging.debug("prob:" + str(self.probability) + ", pref net ID:" + str(preferredNetworkID) + ", pref net index:" + str(preferredNetworkIndex))

        if self.probability[preferredNetworkIndex] >= CONVERGED_PROBABILITY:
            # reset as the device observes higher gain from a network being explored while it has converged to another one
            if explore == True:
                gainList = self.recentGainHistoryPerNetwork[preferredNetworkID]; gainList = [x for x in gainList if x >= 0]
                if self.deviceID == 1: logging.debug("current gain: " + str(self.gain) + ", recentGainHistory:" + str(self.recentGainHistoryPerNetwork[preferredNetworkID])
                                                     + ", excl unknown: " + str(gainList) + ", median:" + str(median(gainList)))
                if self.gain > median(gainList):
                    # coinFlip = np.random.choice([True, False], p=[0.5, 0.5])
                    # if coinFlip == True:
                    print(colored("@t = " + str(currentTimeSlot) + ", device " + str(self.deviceID) + " resets when exploring unheard network " + str(self.currentNetwork), "magenta"));
                    self.log.append("RESET WHEN EXPLORATION UNHEARD NETWORK")
                    # return True, [getListIndex(networkList, self.currentNetwork)]
                    return True, [self.availableNetwork.index(self.currentNetwork)]

            # reset as I learn from neighbors that I can observe higher bit rate from another network other than the one I have converged to;
            # I reset with prob 1/(#device in my network) - all need not reset; also if all reset, it may cause major disruption to the setting?
            elif len(self.recentGainHistoryPerNetwork[1]) == MAX_TIME_UNHEARD_ACCEPTABLE and currentTimeSlot % (MAX_TIME_UNHEARD_ACCEPTABLE//2) == 0:
                # find median gain of all networks
                medianGainPerNetwork = []
                for networkID in self.availableNetwork:
                    gainList = self.recentGainHistoryPerNetwork[networkID]; gainList = [x for x in gainList if x >= 0];
                    if gainList != []: medianGainPerNetwork.append(median(gainList))
                    else: medianGainPerNetwork.append(-1)
                maxMedianGain = max(medianGainPerNetwork)
                if medianGainPerNetwork[preferredNetworkIndex] != maxMedianGain \
                        and ((maxMedianGain - medianGainPerNetwork[preferredNetworkIndex])*100/medianGainPerNetwork[preferredNetworkIndex]) > 0:
                    # > 5 to ignore errors in estimating the gain observable from other networks...
                    possibleAction = [False, True]  # reset or not
                    actionSelectionProbability = [1 - (1 / self.numDevicePerNetwork[preferredNetworkIndex]),1 / self.numDevicePerNetwork[preferredNetworkIndex]]
                    reset = np.random.choice(possibleAction, p=actionSelectionProbability)

                    if reset == True:
                        # build list of network(s) with higher median gain; save their indices
                        maxMedianGainNetworkList = []
                        for networkIndex in range(len(self.availableNetwork)):
                            if medianGainPerNetwork[networkIndex] == maxMedianGain: maxMedianGainNetworkList.append(networkIndex)
                        print(colored("@t = " + str(currentTimeSlot) + ", device " + str(self.deviceID) + " resets as a better network is available", "blue"))
                        # print(colored("@t = " + str(currentTimeSlot) + ", device " + str(self.deviceID) + " resets as a better network is available (prob "
                        #               + str(actionSelectionProbability[-1]) + ") - preferred network:" + str(preferredNetworkID) + ", #device in pref net:"
                        #               + str(self.numDevicePerNetwork[preferredNetworkIndex]) + ", better network(s):" + str([x+1 for x in maxMedianGainNetworkList])
                        #               + " with median gain " + str(medianGainPerNetwork) + ", gain history: " + str(self.recentGainHistoryPerNetwork), "red"));
                        self.log.append("RESET THERE IS A BETTER NETWORK")
                        return reset, maxMedianGainNetworkList
        return False, []

    ''' ################################################################################################################################################################### '''
    def updateRecentHistory(self, currentTimeSlot, networkID, gain, count):
        '''
        description: updates the list of recent gain observed and number of devices per network (stored to known when to explore/reset)
        args:        self, current time slot, ID of a network whose details is being updated, gain I (could) observe from the network at the specific time slot, average
                     bit rate observed by devices associated to the network in that time slot, number of devices associated to that device during that time slot, count -
                     i.e. whether it's the first element of self.networkDetailHistory - it's used to identify the index at which the data is to be stored in the list
                     being updated
        return:      None
        '''
        global DELAY

        if networkID not in self.recentGainHistoryPerNetwork: self.recentGainHistoryPerNetwork.update({networkID: [gain]})
        else:
            if count == 1: self.recentGainHistoryPerNetwork[networkID].append(-1);
            index = count - 1 if currentTimeSlot <= DELAY + 1 else len(self.recentGainHistoryPerNetwork[networkID]) - len(self.networkDetailHistory) + count - 1
            self.recentGainHistoryPerNetwork[networkID][index] = gain
            if len(self.recentGainHistoryPerNetwork[networkID]) > MAX_TIME_UNHEARD_ACCEPTABLE:
                self.recentGainHistoryPerNetwork[networkID] = self.recentGainHistoryPerNetwork[networkID][1:]
        # end updateRecentHistory

    ''' ################################################################################################################################################################### '''
    def estimateLoss(self, currentTimeSlot):
        '''
        decsription: estimates the loss of each network based on that has been learnt about them; also build a list of recent gain (could be) observed from each network
        args:        self, current time slot
        returns:     estimated loss of each network
        '''
        global DELAY, MAX_TIME_UNHEARD_ACCEPTABLE

        gainHistory = []; lossHistory = []; probabilityHistory = []; estimatedLoss = []; D = [];

        # compute the gain of each network and probability of hearing about each of them over the past DELAY time slots, based on one's own knowledge and feedback received
        gainListOverDelay = []
        count = 1
        for networkDetail in self.networkDetailHistory: # networkDetail refers to details of all networks in one particular time slot
            gainList = []
            gainHistory.append({}); lossHistory.append({}); probabilityHistory.append({}); D.append({})
            for networkID in self.availableNetwork:
                singleNetworkDetail = networkDetail[networkID]
                if singleNetworkDetail['associated_device_list'] == set(): gain = -1
                elif self.deviceID in singleNetworkDetail['associated_device_list']: gain = singleNetworkDetail['aggregate_bit_rate']
                else:
                    avgPerUserBitRate = singleNetworkDetail['aggregate_bit_rate']/len(singleNetworkDetail['associated_device_list'])
                    gain = (avgPerUserBitRate * singleNetworkDetail['num_associated_device'])/(singleNetworkDetail['num_associated_device'] + 1)
                gainList.append(gain)

                MobileDevice.updateRecentHistory(self, currentTimeSlot, networkID, gain, count)

                # compute probability
                if len(singleNetworkDetail['probability_list']) == 1: prob = singleNetworkDetail['probability_list'][0]
                else: prob = 1 - np.prod([(1 - x) for x in singleNetworkDetail['probability_list']])
                probabilityHistory[-1].update({networkID:prob})
            if self.maxGain < max(gainList): self.maxGain = max(gainList)
            count += 1
            gainListOverDelay.append(gainList)

        # compute the scaled gain, loss of each network and build list D
        countKnownGain = [0] * len(self.availableNetwork)
        for i in range(len(gainListOverDelay)):
            gainList = gainListOverDelay[i]
            for networkIndex in range(len(self.availableNetwork)):
                if gainList[networkIndex] > 0: gainList[networkIndex] /= self.maxGain
                gainHistory[i].update({self.availableNetwork[networkIndex]: gainList[networkIndex]})
            # compute loss of each network
            for networkIndex in range(len(self.availableNetwork)):
                if gainList[networkIndex] == -1: loss = 0
                else: loss = max(gainList) - gainList[networkIndex]
                lossHistory[i].update({self.availableNetwork[networkIndex]: loss})
            # when gain/loss is present or can be used, indicate it with a one in list D
            for networkIndex in range(len(self.availableNetwork)):
                if gainList[networkIndex] == -1 or gainList.count(-1) == len(self.availableNetwork) - 1: D[i].update({self.availableNetwork[networkIndex]: 0})
                else: D[i].update({self.availableNetwork[networkIndex]: 1}); countKnownGain[networkIndex] += 1

        # value = [0] * len(self.availableNetwork)
        for i in range(len(D)):
            for networkID in self.availableNetwork:
                # method 1: D[i] = 0 if gain/loss is unknown
                # if D[i][networkID] != 0: D[i].update({networkID:1/countKnownGain[networkID - 1]})
                # method 2: D[i] = 1/len(D)
                if D[i][networkID] != 0: D[i].update({networkID:1/len(D)})
                # method 3: D[i] = (i + 1)/sum[1..len(D)]; build from method 1
                # if D[i][networkID] != 0: value[getListIndex(networkList, networkID)] += 1; D[i].update({networkID: value[getListIndex(networkList, networkID)] / sum(range(1,countKnownGain[networkID - 1] + 1))})
                # method 4: D[i] = (i + 1)/sum[1..len(D)]; build from method 2
                # if D[i][networkID] != 0: D[i].update({networkID: (i + 1) / sum(range(1,len(D)+1))})
        self.log.append(str(D))
        self.log.append(str(gainHistory)); self.log.append(str(lossHistory)); self.log.append(str(probabilityHistory));
        # if self.deviceID == 1: logging.debug("gainHistory:" + str(gainHistory) + "; lossHistory:" + str(lossHistory) + ", probabilityHistory: " + str(probabilityHistory))

        # estimate the loss of each network
        for i in range(len(self.availableNetwork)): # for each network
            loss = 0
            networkID = self.availableNetwork[i]
            for j in range(len(lossHistory)):
                # if self.deviceID == 1: logging.debug("lossHistory[j][networkID]:" + str(lossHistory[j][networkID]))
                if D[j][networkID] > 0:
                    if probabilityHistory[j][networkID] == 0: print(colored("ERROR!!!!! Zero probability!" + ", networkID " + str(networkID) + ", net details " + str(self.networkDetailHistory), "red")); input()
                    loss += D[j][networkID] * lossHistory[j][networkID] / probabilityHistory[j][networkID]
            estimatedLoss.append(loss)
        self.log.append(str(estimatedLoss)); self.log.append(str(self.maxGain))
        # if self.deviceID == 1: logging.debug("estimatedLoss:" + str(estimatedLoss))

        return estimatedLoss
        # end estimateLoss

    ''' ################################################################################################################################################################### '''
    def mustCollaborate(self, transmitProb, listenProb):
        '''
        description: determines whether the device must share its observations and data received from neighbors in the previous time slot, or listen for data from neighbors,
                     or do nothing
        args:        self
        returns:     an integer value denoting the action to take (0 - do nothing, 1 - transmit, 2 - listen)
        '''
        actionList = [0, 1, 2]                                     # 0 - do nothing, 1 - transmit, 2 - listen
        probability = [1 - (transmitProb + listenProb), transmitProb, listenProb]
        return np.random.choice(actionList, p=probability)         # select and return an action
        # end mustCollaborate

    ''' ################################################################################################################################################################### '''
    def transmit(self, message):
        '''
        description: simulates braodcasting of observations made and received from neighbors; appends them to a shared string, while dropping duplicates
        args:        self, observation(s) to be shared (as a string of values separated by ";")
        returns:     None
        '''
        global lock

        # OLD message format: timeslot, deviceID, networkselected, bitrate, probabilitydistribution, ttl
        # message format: [timeslot, deviceID, networkselected, bitrate, numAssociatedDevice, probabilityDistribution, ttl]
        with lock:
            if self.serviceArea not in MobileDevice.sharedObservation: MobileDevice.sharedObservation.update({self.serviceArea: ""})
            MobileDevice.sharedObservation.update({self.serviceArea:combineObservation(MobileDevice.sharedObservation[self.serviceArea], message)})
            # MobileDevice.sharedObservation = combineObservation(MobileDevice.sharedObservation, message)
        # end transmit

    ''' ################################################################################################################################################################### '''
    def listen(self):
        '''
        description: simulates listening for feedback from neighbors; retrieves the value from a shared string
        args:        self
        returns:     observations shared during the current sub-time slot (as a string seperated by ";")
        '''

        if self.serviceArea in MobileDevice.sharedObservation:
            return MobileDevice.sharedObservation[self.serviceArea]
        else: return ""
        # end listen

    ''' ################################################################################################################################################################### '''
    def updateNetworkDetailHistory(self, currentTimeSlot, observationStr):
        '''
        description: updates the network detail history based on what has been learnt during the current time slot through observation and feedback
        args:        self, the current time slot and the observations made and received during the current time slot
        returns:     None
        '''
        # message format: timeslot, deviceID, networkselected, bitrate, probabilitydistribution, ttl, numAssociatedDevices
        global DELAY

        # discard stale data (back in time)
        if DELAY == 0: self.networkDetailHistory = []
        elif len(self.networkDetailHistory) == (DELAY + 1): self.networkDetailHistory = self.networkDetailHistory[1:]   # discard stale history

        # if self.deviceID == 1: logging.debug("networkDetailHistory after discarding stale information..." + str(self.networkDetailHistory))

        # create an entry for the current time slot
        self.networkDetailHistory.append({})

        for networkID in self.availableNetwork:
            self.networkDetailHistory[-1].update({networkID: {}})
            self.networkDetailHistory[-1][networkID].update({'aggregate_bit_rate': 0})
            self.networkDetailHistory[-1][networkID].update({'associated_device_list': set()})
            self.networkDetailHistory[-1][networkID].update({'probability_list': []})
            self.networkDetailHistory[-1][networkID].update({'num_associated_device': 0})
        # print("@t=", currentTimeSlot, ", appending ne welement for device:", self.deviceID)
        # if self.deviceID == 1: print("observationStr:", observationStr)
        # update details based on observation made or feedback received (depending on which of the 2 is passed as argument to the function) during the current time slot
        if observationStr != "":
            observationList = observationStr.split(";")
            for observation in observationList:
                observation = observation.split(",")
                # message format: [timeslot, deviceID, networkselected, bitrate, numAssociatedDevice, availableNetwork,  probabilityDistribution, ttl]
                deviceID = int(observation[1]); networkSelected = int(observation[2]); bitRate = float(observation[3]); networkList = observation[5];
                probabilityDistribution = observation[6]; numAssociatedDevice = int(observation[4]); timeSlot = int(observation[0])

                if networkSelected in self.availableNetwork:    # if someone from another area comes and is forwarding details about its previous networks...
                    if self.timeLastHeard[self.availableNetwork.index(networkSelected)] < timeSlot:
                        self.timeLastHeard[self.availableNetwork.index(networkSelected)] = timeSlot
                        self.numDevicePerNetwork[self.availableNetwork.index(networkSelected)] = numAssociatedDevice

                    if currentTimeSlot <= DELAY: networkDetailHistoryIndex = len(self.networkDetailHistory) - 1 - (currentTimeSlot - timeSlot)
                    else: networkDetailHistoryIndex = DELAY - (currentTimeSlot - timeSlot)
                    try:
                        deviceAssociated = self.networkDetailHistory[networkDetailHistoryIndex][networkSelected]['associated_device_list']
                    except:
                        print("ERROR! device:", self.deviceID, ", accessing index ", networkDetailHistoryIndex, ", in ", self.networkDetailHistory); input()
                    if deviceID not in deviceAssociated:    # I don't already have this device's observation for that network
                        tmpDeviceAssociated = list(deviceAssociated)
                        if deviceID == self.deviceID:
                            self.networkDetailHistory[networkDetailHistoryIndex][networkSelected].update({'aggregate_bit_rate': bitRate})
                        elif self.deviceID not in deviceAssociated:
                            # if I selected the network, I know for sure the quality of the network and do not have to estimate based on what others are saying
                            aggregateBitRate = self.networkDetailHistory[networkDetailHistoryIndex][networkSelected]['aggregate_bit_rate']
                            aggregateBitRate += bitRate
                            self.networkDetailHistory[networkDetailHistoryIndex][networkSelected].update({'aggregate_bit_rate': aggregateBitRate})
                        deviceAssociated.add(deviceID)
                        self.networkDetailHistory[networkDetailHistoryIndex][networkSelected].update({'associated_device_list': deviceAssociated})
                        probabilityDistribution = probabilityDistribution.split("_"); probabilityDistribution = [float(prob) for prob in probabilityDistribution]
                        networkList = networkList.split("_"); networkList = [int(net) for net in networkList]
                        for networkID in self.availableNetwork:
                            try:
                                if networkID in networkList:
                                    self.networkDetailHistory[networkDetailHistoryIndex][networkID]['probability_list'].append(probabilityDistribution[networkList.index(networkID)])
                            except:
                                print("exception caught: device:", self.deviceID, ", networkDetailHistory:", self.networkDetailHistory, ", networkDetailHistoryIndex:",
                                      networkDetailHistoryIndex, ", networkID:", networkID, ", probabilityDistribution: ", probabilityDistribution,
                                        ", self.availableNetwork.index(networkID):", self.availableNetwork.index(networkID))
                                input()
                        self.networkDetailHistory[networkDetailHistoryIndex][networkSelected].update({'num_associated_device': numAssociatedDevice})
        # end updateNetworkDetailHistory

    ''' ################################################################################################################################################################### '''
    def fullInformation(self, env):
        '''
        description: performs all the steps involved in a wireless network selection using exponential weighted average in full information setting; implementation based on
                     algorithm 2 (Exponentially weighted average decision) in the paper "Adaptive routing using expert advice", Andras Gyorgy and Gyorgy Ottucsak, 2005;
                     value of eta based on?????
        args:        self, env
        return:      None
        '''
        global NUM_TIME_SLOT, SETTING, ETA, networkList

        # initialization
        variant = "exponential"                                     # standard "exponential" or "linear" variant of the algorithm
        t = 1                                                       # current time slot
        # eta = 20 #sqrt(8 * log(len(self.availableNetwork)) / t)     # value of eta without the need to know the horizon; log to base e (ln)

        while t <= NUM_TIME_SLOT:  # True:
            if MobileDevice.updateSetting(self, t):
                yield env.timeout(10)

                # initialization of variables
                self.log = []                                       # solely for the purpose of saving the data in the csv file
                prevWeight = deepcopy(self.weight)                  # make a copy of the weights since it will be required to save in cvs file later in the current iteration

                # update probability distribution and select a wireless network
                totalWeight = sum(self.weight); self.probability = list((weight / totalWeight) for weight in self.weight)          # update probability
                prevNetworkSelected = self.currentNetwork
                self.currentNetwork = np.random.choice(self.availableNetwork, p=self.probability)       # select a wireless network

                # update number of devices in networks; as devices leave a network and join another
                if prevNetworkSelected != self.currentNetwork:
                    if prevNetworkSelected != -1: MobileDevice.leaveNetwork(self, prevNetworkSelected)
                    MobileDevice.joinNetwork(self, self.currentNetwork)
                    self.delay = MobileDevice.computeDelay(self)
                else: self.delay = 0

                yield env.timeout(10)

                MobileDevice.observeGain(self)                                               # bit rate scaled to the range [0, 1]
                scaledGain = self.gain/self.maxGain

                # store bandwidth obtained/obtainable in each network
                scaledGainPerNetwork = [0] * len(self.availableNetwork)
                scaledGainPerNetwork[self.availableNetwork.index(self.currentNetwork)] = scaledGain
                for i in range(len(self.availableNetwork)):
                    networkIndex = getListIndex(networkList, self.availableNetwork[i])
                    if (self.currentNetwork != networkList[networkIndex].networkID):                               # already set for current network
                        scaledGainPerNetwork[i] = (networkList[networkIndex].dataRate / (networkList[networkIndex].getNumAssociatedDevice() + 1)) / self.maxGain

                # compute loss
                scaledLossPerNetwork = list((max(scaledGainPerNetwork) - bandwidth) for bandwidth in scaledGainPerNetwork)
                # scaledLossPerNetwork = list((1 - bandwidth) for bandwidth in scaledGainPerNetwork)    # compute the loss using 1 as the maximum scaled gain, instead of the max gain obtained from the networks
                # if variant == "linear": scaledLossPerNetwork = [x + 0.01 for x in scaledLossPerNetwork] # FOR LINEAR VARIANT; so that it's not zero
                # if variant == "linear": scaledLossPerNetwork = [x + 0.01 for x in scaledGainPerNetwork] # MISTAKE - scaledGainPerNetwork instead of scaledLossPerNetwork - BUT THEN LINEAR VARIANT CONVERGES FAST

                yield env.timeout(10)

                self.log.append("scaledGainPerNetwork: " + str(scaledGainPerNetwork) + "; ")
                self.log.append("scaledLossPerNetwork: " + str(scaledLossPerNetwork) + "; ")

                # if isNashEquilibrium(): self.log.append("Nash equilibrium")
                MobileDevice.saveDeviceDetail(self, t, prevWeight, ETA, scaledGain)                         # save device details to csv file
                if self.deviceID == 1: MobileDevice.saveNetworkDetail(self, t)                              # save network details to csv file

                # eta = 20 #sqrt(8 * log(len(self.availableNetwork)) / t) # update value of eta

                # update weight
                # if variant == "exponential":                        # for standard exponential variant
                self.weight = list((w * exp(-1 * ETA * scaledLoss)) for w, scaledLoss in zip(self.weight, scaledLossPerNetwork))  # standard exponential version
                # elif variant == "linear":                           # FOR LINEAR VARIANT
                #     epsilon = 0.1; self.weight = list((w * (1 - epsilon * ETA * scaledLoss)) for w, scaledLoss in zip(self.weight, scaledLossPerNetwork)) #epsilon = (1 - e ** (-5))
                #     # epsilon = 0.1; self.weight = list((w * (1 - epsilon) * (ETA * scaledLoss)) for w, scaledLoss in zip(self.weight, scaledLossPerNetwork)) # USED WHEN MISTAKE WAS MADE YIELDING CONVERGENCE OF LINEAR VARIANT

                maxWeight = max(self.weight); self.weight = [w/maxWeight for w in self.weight]          # normalize weights

                if self.deviceID == 1: logging.debug("@t = " + str(t-1) + ", device " + str(self.deviceID) + ", loss: " + str(scaledLossPerNetwork) + ", weight: " + str(self.weight) +
                                                   ", probability: " + str(self.probability)); #input()
                # if SETTING == 2 or SETTING == 3  and t == 601: self.weight = [1] * len(self.availableNetwork)
            else: yield env.timeout(30)
            # print("device ", self.deviceID, "done t = ", t)
            t += 1  # increment number of iterations

        # end fullInformation

    ''' ################################################################################################################################################################### '''
    def computeDelay(self):
        '''
        description: generates a delay for switching between WiFi networks, which is modeled using Johnson’s SU distribution (identified as a best fit to 500 delay values).
        args:        self
        returns:     a delay value
        '''
        wifiDelay = [3.0659475327, 14.6918344498]  # min and max delay observed for wifi in some real experiments; used as caps for the delay generated
        delay = min(max(johnsonsu.rvs(0.29822254217554717, 0.71688524931466857, loc=6.6093350624107909, scale=0.5595970482712973), wifiDelay[0]), wifiDelay[1])
        # if self.deviceID == 1: logging.debug("Delay: " + str(delay))
        return delay
        # end computeDelay

    ''' ################################################################################################################################################################### '''
    def observeGain(self):
        '''
        description: determines the bit rate observed by the device from the wireless network selected and scale the gain to the range [0, 1]
        args:        self
        returns:     amount of bandwidth observed by the device
        '''
        global networkList, TIME_SLOT_DURATION

        networkIndex = getListIndex(networkList, self.currentNetwork)  # get the index in lists where details of the specific network is saved
        self.gain = networkList[networkIndex].getPerDeviceBitRate()  # in Mbps
        if self.maxGain < self.gain: self.maxGain = self.gain; #print("device:", self.deviceID, ", own observation max:", self.maxGain)
        # scaledGain = self.gain / self.maxGain  # scale gain in range [0, 1]
        self.download = networkList[networkIndex].getPerDeviceDownload(TIME_SLOT_DURATION, self.delay)  # Mbits
        # return scaledGain
        # end observeGain
        ''' scale gain in range [0, 1]; scaling in range [0, GAIN_SCALE] is performed after calling exp in updateWeight to avoid overflow from exp... '''

    ''' ################################################################################################################################################################### '''
    def joinNetwork(self, networkSelected):
        '''
        description: adds a particular device to a specified network, by incrementing the number of devices in that network by 1
        arg:         self, ID of network to join
        returns:     None
        '''
        global networkList

        networkIndex = getListIndex(networkList, networkSelected)
        networkList[networkIndex].associateDevice(self.deviceID)
        # end joinNetwork

    ''' ################################################################################################################################################################### '''
    def leaveNetwork(self, prevNetworkSelected):
        '''
        description: removes a particular device from a specified network, by decrementing the number of devices in that network by 1
        arg:         self, ID of network to leave
        returns:   None
        '''
        global networkList

        networkIndex = getListIndex(networkList, prevNetworkSelected)
        networkList[networkIndex].disassociateDevice(self.deviceID)
        # end leaveNetwork

    ''' ################################################################################################################################################################### '''
    def updateSetting(self, t):
        '''
        description: identifies whether a device is still in the service area and performing a network selection, based on current setting considered; the settings considered
                     are: (1) setting 1 - all devices are always in the service area; all devices have access to the same set of networks, (2) setting 2 - 9 devices leave the
                     service area at the end of t = 600; all devices have access to the same set of networks, (3) setting 3 - 16 devices leave the service area at the end of
                     t = 600; all devices have access to the same set of networks, (4) setting 4 - 9 devices join the service area at the beginning of t = 401 and leave the
                     service area at the end of t = 800; all devices have access to the same set of networks
        args:        self, current time slot t
        returns:     True or False denoting whether the device is still in the service area
        '''
        global SETTING, NUM_TIME_SLOT, DELAY, CONVERGED_PROBABILITY, OUTPUT_DIR

        if SETTING == 2 and t == (NUM_TIME_SLOT // 2) + 1: self.numDevicePerServiceArea.update({1:NUM_MOBILE_DEVICE/2})
        elif SETTING == 3:
            if t == 1: self.numDevicePerServiceArea.update({1:NUM_MOBILE_DEVICE//2})
            elif t == (NUM_TIME_SLOT // 3) + 1: self.numDevicePerServiceArea.update({1:NUM_MOBILE_DEVICE})
            elif t == (2 * NUM_TIME_SLOT // 3) + 1: self.numDevicePerServiceArea.update({1:NUM_MOBILE_DEVICE//2})
        elif SETTING == 4:
            if t == 1: self.numDevicePerServiceArea.update({1:10}); self.numDevicePerServiceArea.update({2:5}); self.numDevicePerServiceArea.update({3:5})
            elif t == (NUM_TIME_SLOT // 3) + 1:
                self.numDevicePerServiceArea.update({1:2}); self.numDevicePerServiceArea.update({2:13}); self.numDevicePerServiceArea.update({3:5})
            elif t == (2 * NUM_TIME_SLOT // 3) + 1:
                self.numDevicePerServiceArea.update({1: 2}); self.numDevicePerServiceArea.update({2: 5}); self.numDevicePerServiceArea.update({3:13})
        # print(colored("@t=" + str(t) + ", #devices per service area:" + str(self.numDevicePerServiceArea), "green"))

        if SETTING == 2 and self.deviceID >= 11 and t > NUM_TIME_SLOT // 2:
            # setting 2 - 10 devices leave the service area at the end of t = 600; all devices have access to the same set of networks
            if t == ((NUM_TIME_SLOT // 2) + 1):
                prevNetwork, self.currentNetwork = self.currentNetwork, -1
                MobileDevice.leaveNetwork(self, prevNetwork); print("@t = ", t, "device", self.deviceID, "leaves the service area")
            return False
        elif SETTING == 3 and self.deviceID >= 11 and (t <= (NUM_TIME_SLOT // 3) or t > (2 * (NUM_TIME_SLOT // 3))):
            # setting 3 - 10 devices join the service area at the beginning of t = 401 and leave the service area at the end of t = 800;
            # all devices have access to the same set of networks
            if t == ((2 * (NUM_TIME_SLOT // 3)) + 1):
                prevNetwork, self.currentNetwork = self.currentNetwork, -1
                MobileDevice.leaveNetwork(self, prevNetwork); print("@t = ", t, "device", self.deviceID, "leaves the service area")
            return False
        elif SETTING == 3 and self.deviceID >= 11 and t == ((NUM_TIME_SLOT // 3) + 1):
            print("@t = ", t, "device", self.deviceID, "joins the service area")
            for i in range(DELAY):
                newElement = {}
                for i in range(len(self.availableNetwork)):
                    newElement.update({i + 1: {}})
                    newElement[i + 1].update({'aggregate_bit_rate': 0})
                    newElement[i + 1].update({'associated_device_list': set()})
                    newElement[i + 1].update({'probability_list': []})
                    newElement[i + 1].update({'num_associated_device': 0})
                self.networkDetailHistory.append(newElement)
            for i in range(len(self.availableNetwork)):
                self.recentGainHistoryPerNetwork.update({i+1: []})
                for j in range(DELAY): self.recentGainHistoryPerNetwork[i+1].append(-1)
                self.timeLastHeard[i] = t - 1

            # print("@t = ", t, ", device", self.deviceID, "joins the service area, with detail history", self.networkDetailHistory); input()
        elif SETTING == 4 and t == 1:
            # first phase
            OUTPUT_DIR = ORIGINAL_OUTPUT_DIR + "PHASE_1/"
            if self.deviceID >= 1 and self.deviceID <= 8: self.serviceArea = 1; self.transmitProbability = 1/10
            elif self.deviceID >= 9 and self.deviceID <= 10: self.serviceArea = 1; self.transmitProbability = 1/10
            elif self.deviceID >= 11 and self.deviceID <= 15: self.serviceArea = 2; self.transmitProbability = 1/5
            elif self.deviceID >= 16 and self.deviceID <= 20: self.serviceArea = 3; self.transmitProbability = 1/5
            print("@t = ", t, ", device ", self.deviceID, ", service area ", self.serviceArea, ", p_t ", self.transmitProbability)

        elif SETTING == 4 and t == (NUM_TIME_SLOT // 3) + 1:
            # second phase
            OUTPUT_DIR = ORIGINAL_OUTPUT_DIR + "PHASE_2/"
            if self.deviceID >= 1 and self.deviceID <= 8:
                prevAvailableNetwork = deepcopy(self.availableNetwork)
                networks = [networkList[0]] + networkList[2:]
                self.availableNetwork = [networks[i].networkID for i in range(len(networks))]
                self.maxGain = max([NETWORK_BANDWIDTH[i - 1] for i in self.availableNetwork])
                self.serviceArea = 2; self.transmitProbability = 1/13

                MobileDevice.updateChangeServiceArea(self, prevAvailableNetwork, t)

            elif self.deviceID >= 9 and self.deviceID <= 10: self.serviceArea = 1; self.transmitProbability = 1/2
            elif self.deviceID >= 11 and self.deviceID <= 15: self.serviceArea = 2; self.transmitProbability = 1/13
            elif self.deviceID >= 16 and self.deviceID <= 20: self.serviceArea = 3; self.transmitProbability = 1/5
            print("@t = ", t, ", device ", self.deviceID, ", service area ", self.serviceArea, ", p_t ", self.transmitProbability)

        elif SETTING == 4 and t == (2*NUM_TIME_SLOT // 3) + 1:
            # third phase
            OUTPUT_DIR = ORIGINAL_OUTPUT_DIR + "PHASE_3/"
            if self.deviceID >= 1 and self.deviceID <= 8:
                prevAvailableNetwork = deepcopy(self.availableNetwork); prevWeight = deepcopy(self.weight)
                networks = [networkList[0]] + networkList[3:]
                self.availableNetwork = [networks[i].networkID for i in range(len(networks))]
                self.maxGain = max([NETWORK_BANDWIDTH[i - 1] for i in self.availableNetwork])
                self.serviceArea = 3; self.transmitProbability = 1/13

                MobileDevice.updateChangeServiceArea(self, prevAvailableNetwork, t)

            elif self.deviceID >= 9 and self.deviceID <= 10: self.serviceArea = 1; self.transmitProbability = 1/2
            elif self.deviceID >= 11 and self.deviceID <= 15: self.serviceArea = 2; self.transmitProbability = 1/5
            elif self.deviceID >= 16 and self.deviceID <= 20: self.serviceArea = 3; self.transmitProbability = 1/13
            print("@t = ", t, ", device ", self.deviceID, ", service area ", self.serviceArea, ", p_t ", self.transmitProbability)
        return True  # for setting 1 and all other settings where the above conditions evaluate to False
        # end updateSetting
    ''' ################################################################################################################################################################### '''
    def updateChangeServiceArea(self, prevAvailableNetwork, t):
        prevWeight = deepcopy(self.weight); self.weight = [1] * len(self.availableNetwork)
        prevNetworkDetailHistory = deepcopy(self.networkDetailHistory); prevTimeLastHeard = deepcopy(self.timeLastHeard);
        prevRecentGainHistoryPerNetwork = deepcopy(self.recentGainHistoryPerNetwork); prevNumDevicePerNetwork = deepcopy(self.numDevicePerNetwork)

        # print("@t = ", t, ", device ", self.deviceID, " called updateChangeServiceArea...")
        self.networkDetailHistory = [{}] * (len(prevNetworkDetailHistory)); self.timeLastHeard = [t-1] * len(self.availableNetwork); self.numDevicePerNetwork = [-1] * len(self.availableNetwork)
        self.recentGainHistoryPerNetwork = {}
        for i in range(len(self.availableNetwork)):
            networkID = self.availableNetwork[i]
            if networkID in prevAvailableNetwork:                       # network was also available earlier
                networkIndex = prevAvailableNetwork.index(networkID)    # get its index in the previous list of networks

                if max(self.probability) >= CONVERGED_PROBABILITY and prevAvailableNetwork[self.probability.index(max(self.probability))] in self.availableNetwork:
                    self.weight[i] = prevWeight[networkIndex]
                else: print(colored("t = " + str(t) + ", device " + str(self.deviceID) + ", resets its weight " + str(self.weight), "cyan"))
                if ALGORITHM == "CollaborativeEWA":
                    self.timeLastHeard[i] = prevTimeLastHeard[networkIndex]
                    self.recentGainHistoryPerNetwork.update({networkID:prevRecentGainHistoryPerNetwork[networkID]})
                    self.numDevicePerNetwork[i] = prevNumDevicePerNetwork[networkIndex]
            else:
                if ALGORITHM == "CollaborativeEWA":
                    # network newly discovered
                    self.recentGainHistoryPerNetwork.update({networkID: []})
                    for j in range(DELAY): self.recentGainHistoryPerNetwork[networkID].append(-1)

        # networkDetailHistory; if self.availableNetwork[i] in prevAvailableNetwork:  # if network was previously available, save its data else default...
        if ALGORITHM == "CollaborativeEWA":
            for i in range(len(prevNetworkDetailHistory)):
                singleNetworkDetailHistory = prevNetworkDetailHistory[i]
                # print("singleNetworkDetailHistory:", singleNetworkDetailHistory)
                for j in range(len(self.availableNetwork)):
                    if self.availableNetwork[j] in prevAvailableNetwork:
                        self.networkDetailHistory[i].update({self.availableNetwork[j]: singleNetworkDetailHistory[self.availableNetwork[j]]})
                    else:
                        self.networkDetailHistory[i].update({self.availableNetwork[j]:{}})
                        self.networkDetailHistory[i][self.availableNetwork[j]].update({'aggregate_bit_rate': 0})
                        self.networkDetailHistory[i][self.availableNetwork[j]].update({'associated_device_list': set()})
                        self.networkDetailHistory[i][self.availableNetwork[j]].update({'probability_list': []})
                        self.networkDetailHistory[i][self.availableNetwork[j]].update({'num_associated_device': 0})

        # print("@t=",t, ", device", self.deviceID, ", prev prob:", self.probability, ", weight", self.weight, ", time last heard:", self.timeLastHeard,
        #       ", recent gain history:", self.recentGainHistoryPerNetwork, ", #device per net:", self.numDevicePerNetwork, ", network detail history:", self.networkDetailHistory)
        # print("@t=",t, ", device", self.deviceID, ", time last heard:", self.timeLastHeard, ", recent gain history:", self.recentGainHistoryPerNetwork, ", #device per net:", self.numDevicePerNetwork)

        self.probability = [0] * len(self.availableNetwork)
       # end updateChangeServiceArea

    ''' ################################################################################################################################################################### '''
    def saveDeviceDetail(self, t, prevWeight, learningRate, estimatedGain = -1):
        # , sharedData = [], shareObservation=0, receiveObservation=0, shareProb=0, receiveProb=0, uniformProb=0):
        '''
        description: save details for each device in its own cvs file
        args:        self, iteration t, weight used in the previous iteration to compute the probability, learning rate, scaled gain and estimated for the current time slot,
                     data that has been shared and is still valid, whether one's observation has been shared or data has been received in this time slot, the probability with
                     which the device shares and receives data, the value of the variable that controls the uniform part of the probability distribution
        returns:     None
        '''
        global networkList, ALGORITHM

        filename = OUTPUT_DIR + "device" + str(self.deviceID) + ".csv"
        # currentNetworkIndex = getListIndex(networkList, self.currentNetwork)
        currentNetworkIndex = self.availableNetwork.index(self.currentNetwork)

        # build list of data values to be saved to csv file
        if SAVE_MINIMAL_DETAIL == True:
            data = [RUN_NUM, t]
            for index in range(len(prevWeight)): data.append(prevWeight[index])  # weight used in this time slot to calculate the probability distribution
            for index in range(len(self.probability)): data.append(self.probability[index])
            data += [self.currentNetwork, self.delay, self.download / 8, self.gain]  # save download in MB; gain is bit rate - Mbps
            for netID in self.availableNetwork:    # append achievable download if connected to each of the other networks; each expert's gain
                networkIndex = getListIndex(networkList, netID)
                if netID == self.currentNetwork:
                    possibleDownload = (networkList[networkIndex].dataRate / networkList[networkIndex].getNumAssociatedDevice()) * TIME_SLOT_DURATION
                else: possibleDownload = (networkList[networkIndex].dataRate / (networkList[networkIndex].getNumAssociatedDevice() + 1)) * TIME_SLOT_DURATION
                data.append(possibleDownload / 8)       # in MB
            if ALGORITHM == "SmartEXP3":
                data.append(self.coinFlip)
                data.append(self.chooseGreedily)
                data.append(self.switchBack)
                data.append(self.blockLengthPerNetwork[currentNetworkIndex])
                data.append(self.resetBlockLength)
            elif ALGORITHM == "CollaborativeEWA" or ALGORITHM == "CollaborativeEXP3":
                data.append(self.networkDetailHistory)
            data += self.log
                # data.append(self.log)
        else:
            data = [RUN_NUM, t, self.deviceID, learningRate]
            for index in range(len(prevWeight)): data.append(prevWeight[index])  # weight used in this time slot to calculate the probability distribution
            for index in range(len(self.probability)): data.append(self.probability[index])
            data += [self.currentNetwork, networkList[currentNetworkIndex].getNumAssociatedDevice(), self.delay, self.download / 8, self.gain, self.gain/self.maxGain, estimatedGain]
            for netID in self.availableNetwork:  # append achievable download if connected to each of the other networks; each expert's gain
                networkIndex = getListIndex(networkList, netID)
                if netID == self.currentNetwork:
                    possibleDownload = (networkList[networkIndex].dataRate / networkList[networkIndex].getNumAssociatedDevice()) * TIME_SLOT_DURATION
                else: possibleDownload = (networkList[networkIndex].dataRate / (networkList[networkIndex].getNumAssociatedDevice() + 1)) * TIME_SLOT_DURATION
                data.append(possibleDownload / 8)       # in MB
            data.append(self.coinFlip)
            data.append(self.chooseGreedily)
            data.append(self.switchBack)
            data.append(self.log)
            data.append(self.blockLengthPerNetwork[currentNetworkIndex])
            data.append(self.networkSelectedPrevBlock)
            data.append(self.gainPerTimeSlotCurrentBlock)
            data.append(self.gainPerTimeSlotPrevBlock)
            data.append(self.resetBlockLength)
            data.append(self.totalNumResetPeriodic + self.totalNumResetDrop)
            data.append(str(self.totalBitRatePerNetwork))
            data.append(str(self.numTimeSlotNetworkSelected))

        # open the csv file, write the data to it and close it
        myfile = open(filename, "a")
        out = csv.writer(myfile, delimiter=',', quoting=csv.QUOTE_ALL)
        out.writerow(data)
        myfile.close()
        # end saveDeviceDetail

    ''' ################################################################################################################################################################### '''
    def saveNetworkDetail(self, t):
        '''
        description: save details pertaining to each wireless network
        args:        self, iteration t
        returns:     None
        '''
        filename = OUTPUT_DIR + "network.csv"

        # build list of data values to be saved to csv file
        data = [RUN_NUM, t, self.deviceID]
        for i in range(NUM_NETWORK): data.append(networkList[i].getNumAssociatedDevice())
        for i in range(NUM_NETWORK): data.append(networkList[i].getAssociatedDevice())
        # open the csv file, write the data to it and close it
        myfile = open(filename, "a")
        out = csv.writer(myfile, delimiter=',', quoting=csv.QUOTE_ALL)
        out.writerow(data)
        myfile.close()
        # end saveNetworkDetail
# end MobileDevice class