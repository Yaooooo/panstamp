#########################################################################
#
# SwapServer
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
__date__ ="$Aug 20, 2011 10:36:00 AM$"
#########################################################################

from modem.SerialModem import SerialModem
from swap.SwapRegister import SwapRegister
from swap.SwapDefs import SwapFunction, SwapRegId
from swap.SwapPacket import SwapPacket
from swap.SwapQueryPacket import SwapQueryPacket
from swap.SwapMote import SwapMote
from swapexception.SwapException import SwapException
from xmltools.XmlSettings import XmlSettings
from xmltools.XmlSerial import XmlSerial
from xmltools.XmlNetwork import XmlNetwork

import time

class SwapServer:
    """
    SWAP server class
    """
    # Maximum waiting time (in ms) for ACK's
    _MAX_WAITTIME_ACK = 500
    # Max tries for any SWAP command
    _MAX_SWAP_COMMAND_TRIES = 3

   
    def start(self):
        """
        Start SWAP server
        """
        # Serial configuration settings
        self._xmlSerial = XmlSerial(self._xmlSettings.serialFile)
        # Network configuration settings
        self._xmlNetwork = XmlNetwork(self._xmlSettings.networkFile)

        # Serial configuration settings
        self._xmlSerial = XmlSerial(self._xmlSettings.serialFile)
        
        try:
            # Create and start serial modem object
            self.modem = SerialModem(self._xmlSerial.port, self._xmlSerial.speed, self.verbose)
            if self.modem is None:
                raise SwapException("Unable to start serial modem on port " + self._xmlSerial.port)
            # Declare receiving callback function
            self.modem.setRxCallback(self._ccPacketReceived)
    
            # Set modem configuration from _xmlNetwork
            paramChanged = False
            # Device address
            if self._xmlNetwork.devAddress is not None:
                if self.modem.deviceAddr != self._xmlNetwork.devAddress:
                    if self.modem.setDevAddress(self._xmlNetwork.devAddress) == False:
                        raise SwapException("Unable to set modem's device address to " + self._xmlNetwork.devAddress)
                    else:
                        paramChanged = True
            # Device address
            if self._xmlNetwork.NetworkId is not None:
                if self.modem.syncWord != self._xmlNetwork.NetworkId:
                    if self.modem.setSyncWord(self._xmlNetwork.NetworkId) == False:
                        raise SwapException("Unable to set modem's network ID to " + self._xmlNetwork.NetworkId)
                    else:
                        paramChanged = True
            # Frequency channel
            if self._xmlNetwork.freqChannel is not None:
                if self.modem.freqChannel != self._xmlNetwork.freqChannel:
                    if self.modem.setFreqChannel(self._xmlNetwork.freqChannel) == False:
                        raise SwapException("Unable to set modem's frequency channel to " + self._xmlNetwork.freqChannel)
                    else:
                        paramChanged = True
    
            # Return to data mode if necessary
            if paramChanged == True:
                self.modem.goToDataMode()
    
            # Discover motes in the current SWAP network
            self._discoverMotes()
        except SwapException:
            raise
        
        
    def stop(self):
        """
        Stop SWAP server
        """
        self.modem.stop()
        pass


    def resetNetwork(self):
        """
        Clear SWAP network
        """
        # Clear lists of motes
        self.lstMotes = []

        
    def _ccPacketReceived(self, ccPacket):
        """
        CcPacket received
        
        @param ccPacket: CcPacket received        
        """
        try:
            # Convert CcPacket into SwapPacket
            swPacket = SwapPacket(ccPacket)
        except SwapException:
            raise
        
        # Check function code
        if swPacket.function == SwapFunction.INFO:
            # Expected response?
            self._checkInfo(swPacket)
            # Check type of data received
            # Product code received
            if swPacket.regId == SwapRegId.ID_PRODUCT_CODE:
                try:
                    mote = SwapMote(self, swPacket.value.toList(), swPacket.srcAddress)
                    mote.nonce = swPacket.nonce
                    self._checkMote(mote)
                except IOError as ex:
                    raise SwapException("Unable to create mote: {0}".format(ex))
            # Device address received
            elif swPacket.regId == SwapRegId.ID_DEVICE_ADDR:
                # Check address in list of motes
                self._updateMoteAddress(swPacket.srcAddress, swPacket.value.toInteger())
            # System state received
            elif swPacket.regId == SwapRegId.ID_SYSTEM_STATE:
                self._updateMoteState(swPacket)
            # For any other register id
            else:
                # Update register in the list of motes
                self._updateRegisterValue(swPacket)


    def _checkMote(self, mote):
        """
        Check SWAP mote from against the current list
        
        @param mote: to be searched in the list
        """
        # Search mote in list
        exists = False
        for item in self.lstMotes:
            if item.address == mote.address:
                exists = True
                break

        # Is this a new mote?
        if exists == False:
            # Append mote to the list
            self.lstMotes.append(mote)
            # Notify event handler about the discovery of a new mote
            if self._eventHandler.newMoteDetected is not None:
                self._eventHandler.newMoteDetected(mote)
            # Notify the event handler about the discovery of new endpoints
            for reg in mote.lstRegRegs:
                for endp in reg.lstItems:
                    if  self._eventHandler.newEndpointDetected is not None:
                        self._eventHandler.newEndpointDetected(endp)


    def _updateMoteAddress(self, oldAddr, newAddr):
        """
        Update new mote address in list
        
        @param oldAddr: Old address
        @param newAddr: New address
        """
        # Has the address really changed?
        if oldAddr == newAddr:
            return
        # Search mote in list
        for i, item in enumerate(self.lstMotes):
            if item.address == oldAddr:
                self.lstMotes[i].address = newAddr
                # Notify address change to event handler
                if self._eventHandler.moteAddressChanged is not None:
                    self._eventHandler.moteAddressChanged(self.lstMotes[i])
                break


    def _updateMoteState(self, packet):
        """
        Update mote state in list

        @param packet: SWAP packet to extract the information from
        """
        # New system state
        state = packet.value.toInteger()

        # Search mote in list
        for mote in self.lstMotes:
            if mote.address == packet.srcAddress:
                # Has the state really changed?
                if mote.state == state:
                    return

                # Update system state in the list
                mote.state = state

                # Notify state change to event handler
                if self._eventHandler.moteStateChanged is not None:
                    self._eventHandler.moteStateChanged(mote)
                break


    def _updateRegisterValue(self, packet):
        """
        Update register value in the list of motes

        @param packet: SWAP packet to extract the information from
        """
        # Search in the list of motes
        for mote in self.lstMotes:
            # Same register address?
            if mote.address == packet.regAddress:
                # Search within its list of regular registers
                if mote.lstRegRegs is not None:
                    for reg in mote.lstRegRegs:
                        # Same register ID?
                        if reg.id == packet.regId:
                            # Did register's value change?
                            if not reg.value.isEqual(packet.value):
                                # Save new register value
                                reg.setValue(packet.value)
                                # Notify register'svalue change to event handler
                                if self._eventHandler.registerValueChanged is not None:
                                    self._eventHandler.registerValueChanged(reg)
                                # Notify endpoint's value change to event handler
                                if self._eventHandler.endpointValueChanged is not None:
                                    # Has any of the endpoints changed?
                                    for endp in reg.lstItems:
                                        if endp.valueChanged == True:
                                            self._eventHandler.endpointValueChanged(endp)
                                return
                # Search within its list of config registers
                if mote.lstCfgRegs is not None:
                    for reg in mote.lstCfgRegs:
                        # Same register ID?
                        if reg.id == packet.regId:
                            # Did register's value change?
                            if not reg.value.isEqual(packet.value):
                                # Save new register value
                                reg.setValue(packet.value)
                                # Notify register'svalue change to event handler
                                if self._eventHandler.registerValueChanged is not None:
                                    self._eventHandler.registerValueChanged(reg)
                                # Notify parameter's value change to event handler
                                if self._eventHandler.paramValueChanged is not None:
                                    # Has any of the endpoints changed?
                                    for param in reg.lstItems:
                                        if param.valueChanged == True:
                                            self._eventHandler.paramValueChanged(param)
                                return
                return


    def _checkInfo(self, info):
        """
        Compare expected SWAP info against info packet received

        @param info: SWAP packet to extract the information from
        """
        # Check possible command ACK
        self._packetAcked = False
        if (self._expectedAck is not None) and (info.function == SwapFunction.INFO):
            if info.regAddress == self._expectedAck.regAddress:
                if info.regId == self._expectedAck.regId:
                    self._packetAcked = self._expectedAck.value.isEqual(info.value)

        # Check possible response to a precedent query
        self._valueReceived = None
        if (self._expectedRegister is not None) and (info.function == SwapFunction.INFO):
            if info.regAddress == self._expectedRegister.getAddress():
                if info.regId == self._expectedRegister.id:
                    self._valueReceived = info.value

        # Update nonce in list
        mote = self.getMote(address=info.srcAddress)
        if mote is not None:
            mote.nonce = info.nonce
            

    def _discoverMotes(self):
        """
        Send broadcasted query to all available (awaken) motes asking them
        to identify themselves
        """
        query = SwapQueryPacket(SwapRegId.ID_PRODUCT_CODE)
        query.send(self.modem)


    def getNbOfMotes(self):
        """
        Return the amounf of motes available in the list
        
        @return Amount of motes available in lstMotes
        """
        return len(self.lstMotes)


    def getMote(self, index=None, address=None):
        """
        Return mote from list given its index or address

        @param index: Index of hte mote within lstMotes
        @param address: Address of the mote
        
        @return mote
        """
        if index is not None and index >= 0:
            return self.lstMotes[index]
        elif (address is not None) and (address > 0) and (address <= 255):
            for item in self.lstMotes:
                if item.address == address:
                    return item
        return None


    def setMoteRegister(self, mote, regId, value):
        """
        Set new register value on wireless mote
        Non re-entrant method!!

        @param mote: Mote containing the register
        @param regId: Register ID
        @param value: New register value

        @return True if the command is correctly ack'ed. Return False otherwise
        """
        # Send command multiple times if necessary
        for i in range(SwapServer._MAX_SWAP_COMMAND_TRIES):
            # Send command
            ack = mote.cmdRegister(regId, value);
            # Wait for aknowledgement from mote
            if self._waitForAck(ack, SwapServer._MAX_WAITTIME_ACK):
                return True;    # ACK received
        return False            # Got no ACK from mote


    def queryMoteRegister(self, mote, regId):
        """
        Query mote register, wait for response and return value
        Non re-entrant method!!
        
        @param mote: Mote containing the register
        @param regId: Register ID
        
        @return register value
        """
        # Queried register
        register = SwapRegister(mote, regId)
        # Send query multiple times if necessary
        for i in range(SwapServer._MAX_SWAP_COMMAND_TRIES):
            # Send query
            register.sendSwapQuery()
            # Wait for aknowledgement from mote
            regVal = self._waitForReg(register, SwapServer._MAX_WAITTIME_ACK)
            if regVal is not None:
                break   # Got response from mote
        return regVal


    def _waitForAck(self, ackPacket, waitTime):
        """
        Wait for ACK (SWAP info packet)
        Non re-entrant method!!

        @param ackPacket: SWAP info packet to expect as a valid ACK
        @param waitTime: Max waiting time in milliseconds
        
        @return True if the ACK is received. False otherwise
        """
        # Expected ACK packet (SWAP info)
        self._expectedAck = ackPacket
        
        loops = waitTime / 10
        while not self._packetAcked:
            time.sleep(0.01)
            loops -= 1
            if loops == 0:
                break
 
        res = self._packetAcked
        self._expectedAck = None
        self._packetAcked = False
        return res


    def _waitForReg(self, register, waitTime):
        """
        Wait for ACK (SWAP info packet)
        Non re-entrant method!!
        
        @param register: Expected register to be informed about
        @param waitTime: Max waiting time in milliseconds
        
        @return True if the ACK is received. False otherwise
        """
        # Expected ACK packet (SWAP info)
        self._expectedRegister = register

        loops = waitTime / 10
        while self._valueReceived is None:
            time.sleep(0.01)
            loops -= 1
            if loops == 0:
                break

        res = self._valueReceived
        self._expectedRegister = None
        self._valueReceived = None
        return res


    def __init__(self, eventHandler, verbose=False):
        """
        Class constructor

        @param eventHandler: Parent event handler object
        @param verbose: Verbose SWAP traffic
        """
        ## Verbose SWAP frames
        self.verbose = verbose
        ## Serial wireless gateway
        self.modem = None
        # Server's Security nonce
        self._nonce = 0
        # True if last packet was ack'ed
        self._packetAcked = False
        # Expected ACK packet (SWAP info packet containing a given endpoint data)
        self._expectedAck = None
        # Value received about register being queried
        self._valueReceived = None
        # Register being queried
        self._expectedRegister = None
        ## List of SWAP motes available in the network
        self.lstMotes = []

        # Event handling object. Its class must define the following methods
        # in order to dispatch incoming SWAP events:
        # - newMoteDetected(mote)
        # - newEndpointDetected(endpoint)
        # - newParameterDetected(parameter)
        # - moteStateChanged(mote)
        # - moteAddressChanged(mote)
        # - registerValueChanged(register)
        # - endpointValueChanged(endpoint)
        # - parameterValueChanged(parameter)
        self._eventHandler = eventHandler

        # General settings
        self._xmlSettings = XmlSettings()
 
        # Start SWAP server
        self.start()