'''
@description:   Defines utility methods used by other programs (python files)
'''
import csv
from sys import argv
import os
from itertools import permutations, product
# import matplotlib.pyplot as plt
import numpy as np
from os import mkdir, chmod, umask


''' _______________________________________________________________________ test for Nash equilibrium _____________________________________________________________________ '''
def isNashEquilibrium(state, numNetwork, bandwidthPerNetwork):
    for i in range(numNetwork):
        for j in range(numNetwork):
            if i != j and state[i] != 0 and bandwidthPerNetwork[i]/state[i] < bandwidthPerNetwork[j]/(state[j] + 1): return False
    return True

# def isNashEquilibrium(networkList, mobileDeviceList):
#     '''
#     description: checks if Nash equilibrium has been reached
#     arg:         None
#     returns:     Boolean value denoting whether the current state is a Nash equilibrium or not
#     '''
#     for i in range(len(mobileDeviceList)):
#         selectedNetwork = mobileDeviceList[i].currentNetwork
#         selectedNetworkIndex = mobileDeviceList[i].getListIndex(selectedNetwork)
#         for j in range(len(networkList)):
#             if ((networkList[j].networkID != selectedNetwork) and
#                     ((networkList[j].dataRate / (networkList[j].numDevice + 1)) > (networkList[selectedNetworkIndex].dataRate / networkList[selectedNetworkIndex].numDevice))):
#                 return False
#     return True
#     # end NashEquilibrium
#
# ''' _____________________________________________________________________ test for epsilon equilibrium ____________________________________________________________________ '''
# def isEpsilonEquilibrium(networkList, mobileDeviceList):
#     '''
#     description: checks if Nash equilibrium has been reached
#     arg:         None
#     returns:     Boolean value denoting whether the current state is an epsilon equilibrium or not
#     '''
#     global EPSILON
#
#     for i in range(len(mobileDeviceList)):
#         selectedNetwork = mobileDeviceList[i].currentNetwork
#         selectedNetworkIndex = selectedNetwork - 1
#         for j in range(len(networkList)):
#             if ((networkList[j].networkID != selectedNetwork) and
#                         ((networkList[j].dataRate / (networkList[j].numDevice + 1)) - (networkList[selectedNetworkIndex].dataRate / networkList[selectedNetworkIndex].numDevice))
#                         > ((networkList[selectedNetworkIndex].dataRate / networkList[selectedNetworkIndex].numDevice) * EPSILON / 100)):
#                 return False
#     return True
#     # end isEpsilonEquilibrium

''' ___________________________________________________________________ compute moving average of a list _________________________________________________________________ '''
def computeMovingAverage(values, window):
    ''' source: https://gordoncluster.wordpress.com/2014/02/13/python-numpy-how-to-generate-moving-averages-efficiently-part-2/ '''
    weights = np.repeat(1.0, window) / window
    sma = np.convolve(values, weights, 'valid')
    return sma
    # end computeMovingAverage

''' ___________________________________________________________________ get the index of object in list __________________________________________________________________ '''
def getListIndex(networkList, searchID):
    '''
    description: returns the index in a list (e.g. networkList or self.weight) at which details of the network with ID searchID is stored
    args:        self, ID of the network whose details is being sought
    returns:     index of array at which details of the network is stored
    assumption:  the list contains a network object with the given network ID searchID
    '''
    index = 0
    while index < len(networkList) and networkList[index].networkID != searchID:
        index += 1
    return index
    # end getListIndex

''' ________________________________________________________ compute percentage element in list greater than a value _____________________________________________________ '''
def percentageElemGreaterOrEqual(alist, val):
    '''
    description: computes the percentage of elements in a list that are greater than a particular value
    args:        a list of elements alist, a value val
    returns:     percentage of elements in alist that are greater than val
    '''
    count = 0
    for num in alist:
        if num > val: count += 1
    return count * 100 / len(alist)
    # end percentageElemGreaterOrEqual

''' ____________________________________________________________ check if an observation was already received ____________________________________________________________ '''
def duplicateObservation(observationList, observation):
    # message format: [timeslot, deviceID, networkselected, bitrate, numAssociatedDevice, probabilityDistribution, ttl]
    # get the time slot, deviceID and networkselected from the observation; together they can be used to identify uniqueness of a message/feedback
    observation = observation.split(",")
    observation = ','.join(str(element) for element in observation[:3])
    # print("observation:",observation)

    observationList = observationList.split(";")
    for someObservation in observationList:
        someObservation = someObservation.split(",")
        someObservation = ','.join(str(element) for element in someObservation[:3])
        if observation == someObservation: return True
    return False
    # end duplicateObservation

''' _________________________________________________________________ combine 2 strings of observation(s) ________________________________________________________________ '''
def combineObservation(original, update):
    '''
    decsription: combines observations formatted as strings, dropping duplicate ones
    args:        original string of observations, new observations received to be appended to the original string of observations
    return:      combined string of unique observations
    '''
    if update == "": return original

    updateList = update.split(";")
    for update in updateList:
        if duplicateObservation(original, update) == False:
            if original == "": original = update
            else: original += ";" + update
    return original
    # end combineObservation

''' ____________________________________________________________ decrements the ttl value of each observation ____________________________________________________________ '''
def decrementTTL(observationStr):
    '''
    description: decrements the ttl value of every observation in observationStr and drop stale ones
     args:       string of observation
    return:      string of relevant (in time) observation(s) with the right ttl value
    '''
    # message format: [timeslot, deviceID, networkselected, bitrate, numAssociatedDevice, probabilityDistribution, ttl]
    updatedObservationStr = ""

    if observationStr != "":
        observationList = observationStr.split(";")
        # print("updatedObservationStr:", updatedObservationStr,", observationList:", observationList)
        for i in range(len(observationList)):
            observation = observationList[i].split(",")
            if int(observation[-1]) == 1: continue # skip the rest of the loop; drop the observation/feedback as it's no longer relevant (stale)
            observation[-1] = int(observation[-1]) - 1
            if updatedObservationStr == "": updatedObservationStr = ','.join(str(element) for element in observation)
            else: updatedObservationStr += ";" + ','.join(str(element) for element in observation)
    return updatedObservationStr
    # end decrementTTL

''' _________________________________________________________ computes distance to Nash equilibrium per time slot ________________________________________________________ '''
def computeDistanceToNashEquilibrium(numNetwork, networkCSVfile, networkBandwidth, originalNElist, setting, numTimeSlot):
    '''
    description: computes the distance to NE per time slot and returns it as a list
    args:
    return:      list of distance to NE per time slot
    '''
    distanceToNE = []  # to store distance to NE per time steps (for individual runs)

    # networkCSVfile = dir + "run_" + str(j + 1) + "/network.csv"
    with open(networkCSVfile, newline='') as networkCSVfile:
        networkReader = csv.reader(networkCSVfile)
        count = 0

        for rowNetwork in networkReader:  # compute total gain of user and that of each expert
            if count != 0:
                runNum = int(rowNetwork[0])
                iterationNum = int(rowNetwork[1])

                NElist = getNElist(originalNElist, iterationNum, setting, numTimeSlot)

                numUserPerNet = []
                for i in range(numNetwork): numUserPerNet.append(int(rowNetwork[3 + i]))  # construct list with number of users per network

                # compute the distance from the current state to NE
                if numUserPerNet in NElist:  # current state is one of the NE state
                    distance = 0
                else:  # current state is not any of the NE state
                    distance = 0

                    ### compute sum of all additional bandwidth obtainable by the users by moving to NE state
                    # select the NE state to be considered based on the number of users to move from/to each network to reach each of the NE states
                    countNumUsersToMove = []  # number of users to move to reach each NE state
                    for NEstate in NElist:
                        numUserDiff = list(numUserAtNE - numUserAtPresent for numUserAtNE, numUserAtPresent in zip(NEstate, numUserPerNet))
                        countNumUsersToMove.append(sum(x for x in numUserDiff if x > 0))

                    minNumUsersToMove = min(countNumUsersToMove)
                    NEindex = countNumUsersToMove.index(minNumUsersToMove)
                    NE = NElist[NEindex]

                    numUserDiff = list(numUserAtNE - numUserAtPresent for numUserAtNE, numUserAtPresent in zip(NE, numUserPerNet))

                    index = 0
                    while index < len(numUserDiff):
                        if numUserDiff[index] < 0:  # user need to move from the network
                            for n in range(len(numUserDiff)):
                                if numUserDiff[n] > 0:
                                    numUsersToBeMoved = min(numUserDiff[n], abs(
                                        numUserDiff[index]))  # no of users that can be moved to this network
                                    currentGain = networkBandwidth[index] / numUserPerNet[index]; #print("currentGain:", currentGain)
                                    tmpDistance = (((networkBandwidth[n] / NE[n]) - currentGain)) * 100 / currentGain; #print("tmpDistance:", tmpDistance)
                                    if tmpDistance > distance: distance = tmpDistance
                                    numUserDiff[index] += numUsersToBeMoved
                                    numUserDiff[n] -= numUsersToBeMoved
                                if numUserDiff[index] == 0:
                                    if NE[index] != 0:
                                        currentGain = networkBandwidth[index] / numUserPerNet[index]
                                        tmpDistance = ((networkBandwidth[index] / NE[
                                            index] - currentGain)) * 100 / currentGain
                                        if tmpDistance > distance: distance = tmpDistance
                                    break
                        index += 1
                distanceToNE.append([distance])
            count += 1
    networkCSVfile.close()
    return distanceToNE
    # end computeDistanceToNashEquilibrium

def getNElist(originalNElist, iterationNum, setting, numTimeSlot):
    if setting == 1: return originalNElist
    elif setting == 2:
        # setting 2 - 16 devices leave the service area at the end of t = 600; all devices have access to the same set of networks
        if iterationNum <= numTimeSlot//2: return [originalNElist[0]]
        else: return [originalNElist[1]]
    elif setting == 3:
        # setting 3 - 10 devices join the service area at the beginning of t = 401 and leave the service area at the end of t = 800;
        if iterationNum <= numTimeSlot//3 or iterationNum > 2*numTimeSlot//3: return [originalNElist[0]]
        else: return [originalNElist[1]]
    elif setting == 4:
        return originalNElist
    # end getNElist

''' ___________________________________________________ computes number of devices per network at Nash equilibrium statenits of time __________________________________________________ '''
def isNashEquilibrium(combination, numNetwork, bandwidthPerNetwork):
    for i in range(numNetwork):
        for j in range(numNetwork):
            if i != j and combination[i] != 0 and bandwidthPerNetwork[i]/combination[i] < bandwidthPerNetwork[j]/(combination[j] + 1): return False
    return True

def isEpsilonEquilibrium(combination, numNetwork, bandwidthPerNetwork):
    for i in range(numNetwork):
        for j in range(numNetwork):
            if i != j and combination[i] != 0 and\
             (bandwidthPerNetwork[j]/(combination[j] + 1) - bandwidthPerNetwork[i]/combination[i]) > (EPSILON * (bandwidthPerNetwork[i]/combination[i])/100):
                return False
    return True

def computeNashEquilibriumState(numDevice, numNetwork, bandwidthPerNetwork):
    NashEquilibriumElist = []
    # epsilonEquilibriumList = []

    for item in product(range(numDevice + 1), repeat = numNetwork):
        if sum(item) == numDevice:
            if isNashEquilibrium(item, numNetwork, bandwidthPerNetwork):

                NashEquilibriumElist.append(list(item))#; print(item)
            # elif isEpsilonEquilibrium(item, numNetwork, bandwidthPerNetwork): epsilonEquilibriumList.append(item); print(item)

    return NashEquilibriumElist

''' ___________________________________________________ computes and returns the time taken in the proper units of time __________________________________________________ '''
def getTimeTaken(startTime, endTime):
    timeTaken = endTime - startTime; unit = "seconds"
    if timeTaken > (60 ** 2): timeTaken /= (60 ** 2); unit = "hours"
    elif timeTaken > 60: timeTaken /= 60; unit = "minutes"
    return timeTaken, unit

''' __________________________________________ create CSV files with the right headers to store details of networks and devices __________________________________________ '''
def createCSVfile(numDevice, numNetwork, dir, setting, save_minimal, algorithmName):
    '''
    decsription: creates a csv file to store details of the networks per time slot, and a csv file for each device; each file will have a header
    args:        number of devices, number of wireless networks, directory to store the files, whether to save minimal (or all) details in files, setting being considered
    return:      None
    '''
    NUM_PHASE = 3 if setting == 4 else 1

    for i in range(NUM_PHASE):
        phaseDir = dir + "PHASE_" + str(i + 1) if NUM_PHASE > 1 else dir
        if not os.path.exists(phaseDir): os.makedirs(phaseDir)  # create output directory if it doesn't exist
        # create network csv file(s)
        networkfilename = phaseDir + "/" + "network.csv"
        createNetworkCSVfile(numNetwork, networkfilename)
        # create device csv files
        for device in range(1, numDevice + 1):
            devicefilename = phaseDir + "/" + "device" + str(device) + ".csv"
            createDeviceCSVfile(numNetwork, device, devicefilename, setting, i + 1, save_minimal, algorithmName)
    # for i in range(numDevice): createDeviceCSVfile(numNetwork, dir + "device" + str(i + 1) + ".csv", setting, save_minimal, algorithmName)
    # end createCSVfile

def createNetworkCSVfile(numNetwork, filename):
    data = ["Run no.", "Time slot", "Device ID"]
    for i in range(numNetwork): data.append("#devices in network " + str(i + 1))
    for i in range(numNetwork): data.append("devices in network " + str(i + 1))
    myfile = open(filename, "a")
    out = csv.writer(myfile, delimiter=',', quoting=csv.QUOTE_ALL)
    out.writerow(data)
    myfile.close()
    # end createNetworkCSVfile

def createDeviceCSVfile(numNetwork, deviceID, devicefilename, setting, phase, save_minimal, algorithmName):
    # print("creating csv file, device", deviceID, "file", devicefilename, "setting:", setting)
    if setting == 4:
        networkPerPhase = [[1, 2, 3], [1, 3, 4, 5], [1, 4, 5]]
        if deviceID in list(range(1, 9)): availableNetworkList = networkPerPhase[phase - 1] # devices 1 - 8 --- mobile devices
        if deviceID in list(range(9, 11)): availableNetworkList = networkPerPhase[0]        # devices 9 - 10
        if deviceID in list(range(11, 16)): availableNetworkList = networkPerPhase[1]       # devices 11 - 15
        if deviceID in list(range(16, 21)): availableNetworkList = networkPerPhase[2]       # devices 16 - 20
    else: availableNetworkList = list(range(1, numNetwork + 1))
    data = ["Run no.", "Time slot"]
    for networkID in availableNetworkList: data.append("Weight (net " + str(networkID) + ")")
    for networkID in availableNetworkList: data.append("Probability (net " + str(networkID) + ")")
    data = data + ["Current network", "Delay", "# Megabytes recv", "self.gain(Mbps)"]
    for networkID in availableNetworkList: data.append("Bandwidth in network " + str(networkID) + "(MB)")
    if algorithmName == "CollaborativeEWA" or algorithmName == "CollaborativeEXP3":
        data += ["Network detail history", "Action", "D", "Gain history", "Loss history", "Probability history", "Estimated loss"]
    data += ["max gain (for scaling)"]
    myfile = open(devicefilename, "a")
    out = csv.writer(myfile, delimiter=',', quoting=csv.QUOTE_ALL)
    out.writerow(data)
    myfile.close()
    # end createDeviceCSVfile

def saveToCSV(outputCSVfile, header, data):
    myfile = open(outputCSVfile, "w")
    out = csv.writer(myfile, delimiter=',', quoting=csv.QUOTE_ALL)
    if header != []: out.writerow(header)
    for row in data: out.writerow(row)
    myfile.close()

def saveToTxt(outputTxtFile, data):
    myfile =  open(outputTxtFile, "w")
    myfile.write(data)
    myfile.close()

''' ________________________________________________________________ plot the distance to Nash equilibrium _______________________________________________________________ '''

def plot(filename, numTimeSlot):
    # return
    plt.style.use('classic')

    # print("numTimeslot:", numTimeSlot, ", filename: ", filename)
    LINE_WIDTH = 2.0
    plt.xlim(xmin=1, xmax=numTimeSlot)
    plt.xlabel("Time slot")
    plt.ylabel("Distance to Nash equilibrium")

    # compute rolling average over 15 time slots
    window = 10

    # distance = np.genfromtxt(filename, skip_header=1) #, delimiter=' ', dtype=float)
    # print("distance1:", distance, len(distance))
    # distance.astype(float)
    distance = []
    with open(filename, newline='') as filename:
        fileReader = csv.reader(filename)
        count = 0
        for row in fileReader:  # compute total gain of user and that of each expert
            if count != 0: distance.append(float(row[0])); #print(row)
            count+=1
    filename.close()
    distance = computeMovingAverage(distance, window)
    # print("distance2:",distance)
    plt.plot(distance, color='#0000FF', linestyle='-', marker='None', linewidth=LINE_WIDTH)
    grd = plt.grid(True)
    plt.show()
''' _____________________________________________________________________________ end of file ____________________________________________________________________________ '''