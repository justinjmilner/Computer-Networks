import socket
import select
import datetime
import time
import re
import sys

# Create a UDP socket
class udpSocket:
    def __init__(self, destination):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(destination)


class log:
    def __init__(self):
        localTime = time.localtime()
        self.tzAbbr = time.tzname[localTime.tm_isdst]

    def print_log(self, sendOrReceive, flag, byteNum, length=None, window=None):
        # Print the log

        # syn, fin, dat log
        if window == None:
            print(datetime.datetime.now().strftime(f"%a %b %d %H:%M:%S {self.tzAbbr} %Y: {sendOrReceive}; {flag}; Sequence: {byteNum}; Length: {length}"))
        
        # ACK log
        if length == None:
            print(datetime.datetime.now().strftime(f"%a %b %d %H:%M:%S {self.tzAbbr} %Y: {sendOrReceive}; {flag}; Acknowledgment: {byteNum}; Window {window}")); 

class timer:
    def __init__(self):
        self.packetsTime = {}
        self.rttNum = 0
        self.srtt = 0
        self.rttVar = 0
        self.rto = 1


    def updateTimeout(self, rtt):
        alpha = 0.125
        beta = 0.25
        g = 0.01

        if self.rttNum == 0:
            self.srtt = rtt
            self.rttVar = rtt/2
            self.rto = self.srtt + max(g, 4 * self.rttVar)
        elif self.rttNum > 0:
            self.rttVar = (1 - beta) * self.rttVar + beta * abs(self.srtt - rtt)
            self.srtt = (1 - alpha) * self.srtt + alpha * rtt
            self.rto = self.srtt + max(g, 4 * self.rttVar)

        self.rttNum += 1
    
    def checkTimeout(self):
        nums = []
        for num in self.packetsTime.keys():
            if self.packetsTime[num] != 0 and time.time() - self.packetsTime[num] > self.rto:
                nums.append(num)
        if nums:
            return (True, nums)
        return (False, nums)
        
    def startTimer(self, seqNum):
        self.packetsTime[seqNum] = time.time()

    def stopTimer(self, seqNum):
        self.packetsTime[seqNum] = 0

    def returnTimers(self):
        return self.packetsTime
          

class rdpReceiverBuffer:
    def __init__(self):
        self.buffer = {}

    def receive(self, seqNum, length, data):
        self.buffer[seqNum] = (length, data)

    def getBuffer(self):
        return self.buffer
    
  

class regexProcessor:
    def __init__(self):
        pass

    def parseCommand(self, header):
        regexList = [r'SYN', r'ACK', r'FIN', r'DAT', r'RST']
        # Split the data using the compiled pattern
        for command in regexList:
            if re.search(command, header):
                return command
        return None
    
    def findWindowSize(self, header):
        windowRe = r'Window: (\d+)'
        windowReg = re.search(windowRe, header)
        return int(windowReg.group(1))

    def findAckNum(self, header):
        ackRe = r'Acknowledgment: (\d+)'
        ackReg = re.search(ackRe, header)
        return int(ackReg.group(1))
    
    def findSeqNum(self, header):
        seqRe = r'Sequence: (\d+)'
        seqReg = re.search(seqRe, header)
        return int(seqReg.group(1))
    
    def findLength(self, header):
        lengthRe = r'Length: (\d+)'
        lengthReg = re.search(lengthRe, header)
        return int(lengthReg.group(1))
    
    def findData(self, binary_packet):
        try:
            split_pattern = re.compile(b'\r?\n\r?\n')
            # Split the data using the compiled pattern
            split_results = split_pattern.split(binary_packet, 1)[1:]
            return b''.join(split_results)
        except IndexError:
            return None
    
    def parseHeader(self, binary_packet):
        split_pattern = re.compile(b'\r?\n\r?\n')
        # Split the data using the compiled pattern
        return split_pattern.split(binary_packet, 1)[0].decode()
    
    def findCatPac(self, data):
        ackRe = b'Acknowledgment: (\d+)'
        ackReg = re.search(ackRe, data)
        seqRe = b'Sequence: (\d+)'
        seqReg = re.search(seqRe, data)
        if ackReg or seqReg:
            return True
        return False

        
    

class rdpReceiver:
    def __init__(self, fileWrite):
        # File write destination
        self.fileWriter = open(fileWrite, 'wb')

        # Receiver variables
        self.state = 'closed'
        self.windowSize = 2048 # 2KB buffer
        self.reset = 0

        # Helper objects
        self.log = log()
        self.buffer = rdpReceiverBuffer()
        self.regex = regexProcessor()

        # Packet variables
        self.currentAckNum = 1
        self.packets = []
    
    def getState(self):
        return self.state
    
    def setState(self, state):
        self.state = state
    
    def setAckNum(self, ackNum):
        self.ackNum = ackNum

    def processPacket(self, command, header, binary_data):
        # initial connection
        if self.state == 'closed' and command == 'SYN':
            self.setState('open') 
            self.sendAck()  
            
        elif self.state == 'open' and command == 'SYN':
            # resend initial ack
            self.sendAck()
            
        # process data
        elif self.state == 'open' and command == 'DAT':
            seqNum = regex.findSeqNum(header) 
            
            # Resend currentAckNum if the packet number has already been ackd
            if seqNum < self.currentAckNum:
                self.sendAck()
                
            
            # buffer the data
            length = regex.findLength(header) 
            # check packet length fits in buffer
            if length <= self.windowSize:
                self.buffer.receive(seqNum, length, binary_data)  # buffer the data
                if self.currentAckNum == seqNum: # if next expected packet
                    self.currentAckNum += length 
                    # Check if the buffer already has future packets to get next ack number
                    tempSeqNum = self.currentAckNum
                    while tempSeqNum in self.buffer.getBuffer().keys():
                        self.currentAckNum += self.buffer.getBuffer()[self.currentAckNum][0]
                        tempSeqNum = self.currentAckNum
                    self.sendAck()
                else:
                    # resend the ack
                    self.packets.append(f'ACK\nAcknowledgment: {self.currentAckNum}\nWindow: {self.windowSize}\n\n'.encode())
            else:
                self.reset = 1
            
        elif (self.state == 'open' or self.state == 'closed') and command == 'FIN':
            # write data to output file
            finalPacket = None
            for key in sorted(self.buffer.getBuffer().keys()):
                finalPacket = self.buffer.getBuffer()[key][1]
                self.fileWriter.write(self.buffer.getBuffer()[key][1])
            #self.currentAckNum += 1
            try:
                finalPacket.decode()
                self.fileWriter.write('\n'.encode())
            except:
                pass
            self.packets = []
            self.setState('closed')
            self.sendAck()      
    
    def sendAck(self):
        self.packets.append(f'ACK\nAcknowledgment: {self.currentAckNum}\nWindow: {self.windowSize}\n\n'.encode())



class rdpSender: 
    def __init__(self, fileRead):
        # File variables
        self.fileReader = open(fileRead, 'rb')
        self.totalFileLength = 0
        self.readFileSize()

        # Receiver variables
        self.windowSize = 0

        # Sender variables
        self.state = 'closed'
        self.numDup = 0 # Error control
        self.RTTsent = 0
        self.RTTreceived = 0
        
        # Helper objects
        self.timer = timer()
        self.log = log()
        self.regex = regexProcessor()

        # Packet variables
        self.seqNumTemp = 0
        self.seqNumAckd = 0
        self.packets = []
        self.packetsNotAckd = {}
        self.length = 0

        # Start connection
        self.sendSyn(self.seqNumTemp)
        
    
    def getState(self):
        return self.state
    
    def setState(self, state):
        self.state = state
    
    def setTime(self, seqNum):
        self.timer.startTimer(seqNum)

    def checkTimeout(self):
        boolean, seqNums = self.timer.checkTimeout()
        if boolean: 
            # retransmit the packet
            for seqNum in seqNums:
                try:
                    self.packets.append(self.packetsNotAckd[seqNum]) 
                except KeyError:
                    pass # packet already ack'd

    def sendSyn(self, seqNum):
        # send a SYN packet
        self.packets.append(f'SYN\nSequence: {seqNum}\nLength: 0\n\n'.encode())
        self.packetsNotAckd[seqNum] = f'SYN\nSequence: {seqNum}\nLength: 0\n\n'.encode()
        self.setState('open')
    
    def processPacket(self, command, header):
        # process connection ack 
        if self.state == 'synSent' and command == 'ACK':
            self.RTTreceived = time.time()
            self.setState('open')
            self.windowSize = regex.findWindowSize(header) # get initial window size
            self.seqNumAckd = regex.findAckNum(header) # get initial ack number
            self.updateAckdPackets() # delete ack'd packets
            self.sendData()
        # process data ack
        if self.state == 'open' and command == 'ACK':
            self.RTTreceived = time.time()
            self.setState('open')
            self.windowSize = regex.findWindowSize(header)
            tempAckNum = max(self.seqNumAckd, regex.findAckNum(header))
            if tempAckNum == self.seqNumAckd: # check for duplicate acks
                self.numDup += 1
            else:
                self.numDup = 0
            self.seqNumAckd = tempAckNum
            self.updateAckdPackets()
            self.sendData() 
        # process close ack
        elif self.state == 'closeSent' and command == 'ACK':
            self.setState('closed')
    
    def sendData(self):
        # send a data packet
        final_packet = 0
        self.seqNumTemp = self.seqNumAckd
        if self.seqNumAckd == self.totalFileLength or self.seqNumAckd > self.totalFileLength:
            self.packets = []
            self.sendClose()
            return
        while self.windowSize > 0: # send packets until window is full
            self.length = min(self.windowSize, 1024)
            if self.seqNumTemp + self.length > self.totalFileLength:
                self.length = self.totalFileLength - self.seqNumTemp
                final_packet = 1
            if self.seqNumTemp not in self.packetsNotAckd.keys():
                data = self.fileReader.read(self.length)
                self.packetsNotAckd[self.seqNumTemp] = f'DAT\nSequence: {self.seqNumTemp}\nLength: {self.length}\n\n'.encode() + data
            self.packets.append(self.packetsNotAckd[self.seqNumTemp])
            self.setTime(self.seqNumTemp)
            if final_packet: 
                break
            self.seqNumTemp += self.length
            self.windowSize -= self.length
        self.RTTsent = time.time()
            
    def readFileSize(self):
        self.fileReader.seek(0, 2)  # Move the cursor to the end of the file
        self.totalFileLength = self.fileReader.tell()  # Get the file size in bytes
        self.fileReader.seek(0)
        
    def sendClose(self):
        self.packets = []
        self.packets.append(f'FIN\nSequence: {self.seqNumAckd}\nLength: 0\n'.encode())
        self.setTime(self.seqNumAckd)
        self.setState('closeSent')

    def updateAckdPackets(self):
        for seqNum in list(self.packetsNotAckd.keys()):
            if seqNum < self.seqNumAckd:
                del self.packetsNotAckd[seqNum]

    def updateTimers(self):
        for seqNum in self.timer.returnTimers().keys():
            if seqNum < self.seqNumAckd:
                self.timer.stopTimer(seqNum)

        


# main variables
destination = ('10.10.1.100', 8888)
sock = udpSocket((sys.argv[1], int(sys.argv[2])))
sock.sock.setblocking(0)
regex = regexProcessor()
lg = log()

def clearSocketBuffer(): # clear the socket buffer
    try:
        while True:
            data, addr = sock.sock.recvfrom(1024)    
    except BlockingIOError:
        pass

def restartConnection(): # restart the connection
    global rdpReceiver1, rdpSender1
    rdpReceiver1 = rdpReceiver(sys.argv[4])
    rdpSender1 = rdpSender(sys.argv[3])

restartConnection() # start connection

timer1 = time.time()
timer2 = time.time()

while (rdpSender1.getState() != 'closed') or (rdpReceiver1.getState() != 'closed'):
#     if rdpSender1.numDup == 3:
#         for key in sorted(rdpReceiver1.buffer.getBuffer().keys()):
#             rdpReceiver1.fileWriter.write(rdpReceiver1.buffer.getBuffer()[key][1])
#         lg.print_log('Send', 'RST', rdpSender1.seqNumAckd, length=0)
#         sys.exit()
        # clearSocketBuffer()
        # restartConnection() # option to restart the connection but not needed in p2

    if rdpReceiver1.reset == 1:
        for key in sorted(rdpReceiver1.buffer.getBuffer().keys()):
            rdpReceiver1.fileWriter.write(rdpReceiver1.buffer.getBuffer()[key][1])
        lg.print_log('Send', 'RST', rdpReceiver1.currentA01ckNum, window=rdpReceiver1.windowSize)
        sys.exit()

    readable, writable, exceptional = select.select([sock.sock], [sock.sock], [sock.sock], 0.1)
    if sock.sock in readable:
        # receive data and append it into receiver buffer
        binary_packet, addr = sock.sock.recvfrom(2048)
        header = regex.parseHeader(binary_packet) # decoded header
        command = regex.parseCommand(header)  
        data = regex.findData(binary_packet)
        try:
            cat_pack = regex.findCatPac(data)
            if cat_pack:
                command = None
        except:
            pass
        if command == 'ACK':
            lg.print_log('Receive', command, regex.findAckNum(header), window=regex.findWindowSize(header))
            rdpSender1.processPacket(command, header)

        elif command in ['SYN', 'FIN', 'DAT']:
            lg.print_log('Receive', command, regex.findSeqNum(header), length=regex.findLength(header))
            rdpReceiver1.processPacket(command, header, regex.findData(binary_packet))

    elif sock.sock in writable:
        # send the data
        if rdpSender1.packets:
            unique_list1 = []
            for item in rdpSender1.packets:
                if item not in unique_list1:
                    unique_list1.append(item)
            for packet in unique_list1:
                header = regex.parseHeader(packet)
                command = regex.parseCommand(header)
                seqNum = regex.findSeqNum(header)
                rdpSender1.setTime(seqNum)
                lg.print_log('Send', command, seqNum, length=regex.findLength(header))
                sock.sock.sendto(packet, destination)
                if command == 'FIN':
                    break
            rdpSender1.packets = []

        elif rdpReceiver1.packets:
            unique_list2 = []
            for item in rdpReceiver1.packets:
                if item not in unique_list2:
                    unique_list2.append(item)
            for packet in unique_list2:
                header = regex.parseHeader(packet)
                command = regex.parseCommand(header)
                ackNum = regex.findAckNum(header)
                rdpSender1.setTime(ackNum)
                lg.print_log('Send', command, ackNum, window=regex.findWindowSize(header))
                sock.sock.sendto(packet, destination)
                timer1 = time.time()
            rdpReceiver1.packets = []
    
    # check for any timeouts
    if abs(timer2 - time.time()) > 0.01:
        rtt = abs(rdpSender1.RTTreceived - rdpSender1.RTTsent)
        rdpSender1.timer.updateTimeout(rtt)
        rdpSender1.updateTimers()
        rdpSender1.checkTimeout()
    if abs(timer1 - time.time()) > 2:
        timer1 = time.time()
        if rdpSender1.seqNumAckd == rdpSender1.totalFileLength:
            rdpSender1.sendClose()