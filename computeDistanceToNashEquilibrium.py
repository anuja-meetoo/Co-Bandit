'''
@description: to compute distance to Nash equilibrium for simulations done earlier (at the time of Smart EXP3)...
'''

from utility_method import computeDistanceToNashEquilibrium, saveToCSV

NUM_NETWORK = 3
DIR = "/media/anuja/myDrive/FullInformation_eta_20/"
NETWORK_BANDWIDTH = [4,7,22]
nashEquilibriumStateList = [[2,4,14]]
NUM_TIME_SLOT = 1200
numRun = 500

for i in range(1, numRun + 1):
    runDir = DIR + "run" + str(i) + "/"
    distanceToNE = computeDistanceToNashEquilibrium(NUM_NETWORK, runDir + "network.csv", NETWORK_BANDWIDTH, nashEquilibriumStateList)
    outputfile = runDir + "distanceToNashEquilibrium.csv"
    saveToCSV(outputfile, ["Distance_to_Nash_equilibrium"], distanceToNE)
    print(distanceToNE.count([0])*100/NUM_TIME_SLOT, "% time spent at NE")
