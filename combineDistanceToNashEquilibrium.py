'''
combines the distance to Nash equilibrium per time slot for all the runs
'''

import csv
import argparse
from numpy import median
from utility_method import saveToCSV, saveToTxt, computeMovingAverage

parser = argparse.ArgumentParser(description='Combines the distance to Nash equilibrium per time slot for all the runs.')
parser.add_argument('-d', dest="root_dir", required=True, help='root directory where data of all runs are stored')
parser.add_argument('-r', dest="num_run", required=True, help='number of simulation runs')
parser.add_argument('-t', dest="num_time_slot", required=True, help='number of time slots in each simulation run')
parser.add_argument('-w', dest="rolling_avg_window", required=True, help='window for rolling average')
args = parser.parse_args()
rootDir = args.root_dir
numRun = int(args.num_run)
numTimeSlot = int(args.num_time_slot)
window = int(args.rolling_avg_window)

def combineDistanceToNashEquilibrium(rootDir, numRun, numTimeSlot):
    distanceToNashEquilibriumPerTimeSlot = [0] * numTimeSlot
    numTimeSlotAtNashEquilibriumPerRun = []
    for runIndex in range(1, numRun + 1):
        numTimeSlotAtNashEquilibrium = 0
        filename = rootDir + "run" + str(runIndex) + "/distanceToNashEquilibrium.csv"
        with open(filename, newline='') as filename:
            fileReader = csv.reader(filename)
            count = 0
            for row in fileReader:  # compute total gain of user and that of each expert
                if count != 0:
                    distance = float(row[0])
                    distanceToNashEquilibriumPerTimeSlot[count - 1] += distance
                    if distance == 0: numTimeSlotAtNashEquilibrium += 1
                count += 1
        filename.close()
        numTimeSlotAtNashEquilibriumPerRun.append(numTimeSlotAtNashEquilibrium)
    for i in range(len(distanceToNashEquilibriumPerTimeSlot)):
        distanceToNashEquilibriumPerTimeSlot[i] = distanceToNashEquilibriumPerTimeSlot[i]/numRun
    return distanceToNashEquilibriumPerTimeSlot, numTimeSlotAtNashEquilibriumPerRun

def main():
    global rootDir, numRun, numTimeSlot, window
    avgDistanceToNashEquilibriumPerTimeSlot, numTimeSlotAtNashEquilibriumPerRun = combineDistanceToNashEquilibrium(rootDir, numRun, numTimeSlot)
    avgDistanceToNashEquilibriumPerTimeSlot = computeMovingAverage(avgDistanceToNashEquilibriumPerTimeSlot, window)
    print("avgDistanceToNashEquilibriumPerTimeSlot:", avgDistanceToNashEquilibriumPerTimeSlot)
    avgDistanceToNashEquilibriumPerTimeSlot = [[x] for x in avgDistanceToNashEquilibriumPerTimeSlot]

    saveToCSV(rootDir + "distanceToNashEquilibrium.csv", ["average_distance"], avgDistanceToNashEquilibriumPerTimeSlot)
    print("numTimeSlotAtNashEquilibriumPerRun:", numTimeSlotAtNashEquilibriumPerRun)
    saveToTxt(rootDir + "timeSpendAtNashEquilibrium.txt", str(numTimeSlotAtNashEquilibriumPerRun) + "\n" + "Time spent at Nash equilibrium per run:-\n"
              + "\tAverage: " + str(sum(numTimeSlotAtNashEquilibriumPerRun)/len(numTimeSlotAtNashEquilibriumPerRun))
              + "\t(" + str((sum(numTimeSlotAtNashEquilibriumPerRun)/len(numTimeSlotAtNashEquilibriumPerRun))*100/numTimeSlot) + "%)" + "\n"
              + "\tMedian: " + str(median(numTimeSlotAtNashEquilibriumPerRun))
              + "\t(" + str(median(numTimeSlotAtNashEquilibriumPerRun)*100/numTimeSlot) + "%)" + "\n"
              + "\tMinimum: " + str(min(numTimeSlotAtNashEquilibriumPerRun)) + "\n"
              + "\t(" + str(min(numTimeSlotAtNashEquilibriumPerRun) * 100 / numTimeSlot) + "%)" + "\n"
              + "\tMaximum: " + str(max(numTimeSlotAtNashEquilibriumPerRun))
              + "\t(" + str(max(numTimeSlotAtNashEquilibriumPerRun) * 100 / numTimeSlot) + "%)")

if __name__ == "__main__": main()