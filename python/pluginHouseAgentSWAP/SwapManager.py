#########################################################################
#
# SwapManager
#
# Copyright (c) 2011 Daniel Berenguer <dberenguer@usapiens.com>
#
# This file is part of the panStamp project.
#
# panStamp  is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# panStamp is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with panLoader; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301
# USA
#
#########################################################################
__author__="Daniel Berenguer"
__date__  ="$Aug 21, 2011 4:30:47 PM$"
#########################################################################

from swap.SwapServer import SwapServer
from swap.SwapDefs import SwapState, SwapType

import datetime

class SwapManager:
    """ SWAP Management Tool """
    def newMoteDetected(self, mote):
        """ New mote detected by SWAP server """
        if self._printSWAP == True:
            print "New mote with address " + str(mote.address) + " : " + mote.definition.product + \
            " (by " + mote.definition.manufacturer + ")"


    def newEndpointDetected(self, endpoint):
        """ New endpoint detected by SWAP server """
        if self._printSWAP == True:
            print "New endpoint with Reg ID = " + str(endpoint.getRegId()) + " : " + endpoint.name


    def moteStateChanged(self, mote):
        """ Mote state changed """
        if self._printSWAP == True:
            print "Mote with address " + str(mote.address) + " switched to \"" + \
            SwapState.toString(mote.state) + "\""
        # SYNC mode entered?
        if mote.state == SwapState.SYNC:
            self._addrInSyncMode = mote.address


    def moteAddressChanged(self, mote):
        """ Mote address changed """
        if self._printSWAP == True:
            print "Mote changed address to " + str(mote.address)


    def registerValueChanged(self, register):
        """
        Register value changed
        """
        if self._printSWAP == True:
            print  "Register addr= " + str(register.getAddress()) + " id=" + str(register.id) + " changed to " + register.value.toAsciiHex()
        # Empty dictionary
        values = {}
        # For every endpoint contained in this register
        for endp in register.lstItems:
            strVal = endp.getValueInAscii() + " " + endp.unit.name

            if self._printSWAP == True:
                print endp.name + " in address " + str(endp.getRegAddress()) + " changed to " + strVal

            values[endp.name] = strVal
            
        if self._pluginapi is not None:
            self._pluginapi.value_update(register.getAddress(), values)


    def getAddressInSync(self):
        """ Return the address of the mote currently in SYNC mode """
        return self._addrInSyncMode


    def resetAddressInSync(self):
        """ Reset _addrInSyncMode variable """
        self._addrInSyncMode = None


    def getNbOfMotes(self):
        """ Return the amounf of motes available in the list"""
        return self.server.getNbOfMotes()


    def getNbOfEndpoints(self):
        """ Return the amount of endpoints available in the list"""
        return self.server.getNbOfEndpoints()


    def getMote(self, index=None, address=None):
        """ Return mote from list"""
        return self.server.getMote(index, address)


    def getEndpoint(self, index=None):
        """ Return endpoint from list"""
        return self.server.getEndpoint(index)


    def setMoteRegister(self, mote, regId, value):
        """ Set new register value on wireless mote
        Return True if the command is correctly ack'ed. Return False otherwise """
        return server.setMoteRegister(mote, regId, value)


    def queryMoteRegister(self, mote, regId):
        """ Query mote register, wait for response and return value
        Non re-entrant method!! """
        return server.queryMoteRegister(mote, regId)


    def stop(self):
        """ Stop SWAP server """
        self.server.stop()


    def on_custom(self, command, parameters):
        """
        Handles several custom actions used througout the plugin.
        """ 
        if command == 'get_networkinfo':
            motes = {}
            
            for index, mote in enumerate(self.server.lstMotes):
                moteInfo = {"address": mote.address,
                            "manufacturer": mote.definition.manufacturer,
                            "product": mote.definition.product,
                            "sleeping": mote.definition.pwrDownMode,
                            "lastupdate": datetime.datetime.fromtimestamp(mote.timeStamp).strftime("%d-%m-%Y %H:%M:%S")}
                
                motes[index] = moteInfo
           
            return motes
        elif command == "get_motevalues":
            values = {}
            
            devAddress = int(parameters["mote"])
            mote = self.server.getMote(address=devAddress)
            i = 0
            for reg in mote.lstRegRegs:
                for endp in reg.lstItems:                                 
                    valueinfo = {"type": endp.type + " " + SwapType.toString(endp.direction),
                                 "name": endp.name,
                                 "units": endp.unit.name,
                                 "value": endp.getValueInAscii() }                
                
                    values[i] = valueinfo
                    i += 1

            print "Values sent to coordinator:"
            print values
            return values      


    def __init__(self, pluginapi=None, verbose=False, monitor=False):
        """
        Class constructor
        """
        # HouseAgent PluginApi object
        self._pluginapi = pluginapi
        # Register ourselves to receive custom callbacks
        self._pluginapi.register_custom(self)
        # Print SWAP activity
        self._printSWAP = monitor
        # Mote address in SYNC mode
        self._addrInSyncMode = None
        # Start SWAP server
        print "SWAP server starting... "
        self.server = SwapServer(self, verbose)
        print "SWAP server is now running... "

        # Set to None any callback function not being used
        self.endpointValueChanged = None
        