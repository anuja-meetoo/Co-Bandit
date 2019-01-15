'''
@description:   Defines a class that models a wireless network
'''

''' _______________________________________________________________________ Network class definition ______________________________________________________________________ '''
class Network(object):
    ''' class to represent network objects '''
    numNetwork = 0  # keeps track of number of networks to automatically assign an ID to network upon creation

    def __init__(self, dataRate):
        Network.numNetwork = Network.numNetwork + 1 # increment number of network objects created
        self.networkID = Network.numNetwork         # ID of network
        self.dataRate = dataRate                    # date rate of network (in Mbps)
        # self.numDevice = 0                          # number of devices currently associated with the network;
                                                    # NO NEED FOR THIS SINCE WE HAVE THE SET OF DEVICES, BUT I ADDED THE SET AT A LATER STAGE DURING IMPLEMENTATION
        self.associatedDevice = set()               # set of associated devices
        # end __init__

    ''' ################################################################################################################################################################### '''
    def associateDevice(self, deviceID):
        '''
        description: increments the number of devices connected to the network
        arg:         self
        returns:     None
        '''
        # self.numDevice = self.numDevice + 1
        self.associatedDevice.add(deviceID)
        # end associateDevice

    ''' ################################################################################################################################################################### '''
    def disassociateDevice(self, deviceID):
        '''
        description: decrements the number of devices connected to the network
        arg:         self
        returns:     None
        '''
        # self.numDevice = self.numDevice - 1
        self.associatedDevice.remove(deviceID)
        # end disassociateDevice

    ''' ################################################################################################################################################################### '''
    def getPerDeviceBitRate(self):
        '''
        description: computes the bit rate observed by one device in Mbps, assuming network bandwidth is equally shared among its clients
        args:        self
        returns:     bit rate observed by a mobile device of the network (in Mbps)
        '''
        return self.dataRate / len(self.associatedDevice) #self.numDevice

    ''' ################################################################################################################################################################### '''
    def getPerDeviceDownload(self, timeSlotDuration, delay=0):
        '''
        description: computes the total download of a mobile device during a time slot in Mbits (when switching cost is considered)
        args:        self, delay (the delay incurred while diassociating from the previous network and associating with this one and resuming, e.g., download)
        returns:     total download of a device during one time slot (in Mbits), considering switching cost
        '''
        # return (self.dataRate / self.numDevice) * (timeSlotDuration - delay)
        return (self.dataRate / len(self.associatedDevice)) * (timeSlotDuration - delay)

    ''' ################################################################################################################################################################### '''
    def getNumAssociatedDevice(self):
        '''
        description: returns the number of devices associated to the network
        args:        self
        return:      count of associated device
        '''
        return len(self.associatedDevice)

    ''' ################################################################################################################################################################### '''
    def getAssociatedDevice(self):
        '''
        description: returns the set of devices associated to the network
        args:        self
        return:      set of associated device
        '''
        return self.associatedDevice
# end class Network