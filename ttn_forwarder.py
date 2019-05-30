import socket

import uuid
from struct import pack
from json import dumps

# addressing information of target

IP = "52.169.76.203"
PORT = 1700
PKT_PUSH_DATA = 0x00
PROTOCOL_VERSION = 2


#Bytes | Function
#:------: | ---------------------------------------------------------------------
#0 | protocol version = 2
#1 - 2 | random token
#3 | PUSH_DATA identifier 0x00
#4 - 11 | Gateway unique identifier(MAC address)
#12 - end | JSON object, starting with {, ending with}, see section 4

class TTNForwarder:

    def __init__(self):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
        self.s.connect((IP, PORT))

    def create_stat_object(self):
        stat = {}
        stat['time'] = "2014-01-12 08:59:28 GMT"
        stat['rxnb'] = 2
        stat['rxok'] = 2
        stat['rxfw'] = 2
        stat['ackr'] = 100.0
        stat['dwnb'] = 2
        stat['txnb'] = 2
        stat['lati'] = 46.24000
        stat['long'] = 3.25230
        stat['alti'] = 145
        return {'stat': stat}



    def send_udp(self, packet_data):
        packet_data = bytearray(1 + 2 + 1 + 8)
        packet_data[0] = PROTOCOL_VERSION
        packet_data[1] = 2
        packet_data[2] = 3
        packet_data[3] = PKT_PUSH_DATA
        mac = pack(">Q", uuid.getnode())[2:]
        packet_data[4:7] = mac[:3]
        packet_data[7] = 0xFF
        packet_data[8] = 0xFF
        #packet_data[9:12] = [0x69, 0x67, 0xf8]
        packet_data[9:12] = mac[3:]
        print("".join("\\x{:02x}".format(x) for x in packet_data))
        print(dumps(self.create_stat_object()))
        packet_data.extend(dumps(self.create_stat_object()).encode('utf-8'))
        print(packet_data)
        self.s.send(packet_data)


# enter the data content of the UDP packet as hex
# initialize a socket, think of it as a cable
# send the command
