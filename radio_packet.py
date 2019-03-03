import binascii
from struct import pack, unpack
import json


PAT_UINT64 = "Q"
PAT_UINT32 = "I"
PAT_UINT16 = "H"
PAT_UINT8 = "B"
PAT_FLOAT = "f"
PAT_STR8 = "8s"

class RadioPacket():
    RES_RESULT_OK = 0,
    RES_ERROR = 1,
    RES_BUSY = 2,
    RES_INVALID_CMD = 3,
    RES_TIMEOUT = 4,

    def __init__(self, data=None):
        if data:
            self.rawdata = data
            for x in RadioPacket.__subclasses__():
                if x.CMD == self.command:
                    self.__class__ = x
                    return
            raise NameError("Packet class not found for command ", self.rawdata[0])
        else:
            self.rawdata = bytearray()
            self.rawdata.append(self.CMD)

    def toHexString(self):
        return binascii.hexlify(self.rawdata).decode()



class Hello(RadioPacket):
    CMD = 0x01

    def __init__(self):
        super().__init__()
        self.rawdata.extend(bytearray(1 + 2 + 4))



class JoinRequest(RadioPacket):
    CMD = 0x01
    def __init__(self):
        super().__init__()
        self.rawdata.extend(bytearray(2 + 4 + 1))

    @property
    def sid(self):
        return unpack(PAT_UINT16, self.rawdata[2:4])[0]

    @sid.setter
    def sid(self, value):
        self.rawdata[2:4] = pack(PAT_UINT16, value)

    @property
    def time(self):
        return unpack(PAT_UINT32, self.rawdata[4:8])[0]

    @time.setter
    def time(self, value):
        self.rawdata[4:8] = pack(PAT_UINT32, value)

    @property
    def fwver(self):
        return unpack(PAT_UINT8, self.rawdata[8])[0]

    @fwver.setter
    def fwver(self, value):
        self.rawdata[8] = pack(PAT_UINT8, value)[0]

class JoinReply(RadioPacket):
    CMD = 0x10

    def __init__(self):
        super().__init__()
        self.rawdata.extend(bytearray(1 + 3*1 + 2*2))

    @property
    def result(self):
        return self.rawdata[1]

    @result.setter
    def result(self, value):
        self.rawdata[1] = value

    @property
    def bw(self):
        return unpack(PAT_UINT8, self.rawdata[2])[0]

    @bw.setter
    def bw(self, value):
        self.rawdata[2] = pack(PAT_UINT8, value)[0]

    @property
    def sf(self):
        return unpack(PAT_UINT8, self.rawdata[3])[0]

    @sf.setter
    def sf(self, value):
        self.rawdata[3] = pack(PAT_UINT8, value)[0]

    @property
    def cr(self):
        return unpack(PAT_UINT8, self.rawdata[4])[0]

    @cr.setter
    def cr(self, value):
        self.rawdata[4] = pack(PAT_UINT8, value)[0]

    @property
    def join_interval(self):
        return unpack(PAT_UINT16, self.rawdata[5:7])[0]

    @join_interval.setter
    def join_interval(self, value):
        self.rawdata[5:7] = pack(PAT_UINT16, value)

    @property
    def status_interval(self):
        return unpack(PAT_UINT16, self.rawdata[7:9])[0]

    @status_interval.setter
    def status_interval(self, value):
        self.rawdata[7:9] = pack(PAT_UINT16, value)


class SpectrumRequest(RadioPacket):
    CMD = 0x02
    def __init__(self):
        super().__init__()


# data types max 256 seqn num
class SensorDataReply(RadioPacket):
    CMD = 0x20
    DATA_TYPE = 0x00

    def __init__(self):
        super().__init__()
        self.rawdata.extend(bytearray(3))  # data_type, seqnum, nsamples
        if self.DATA_TYPE: self.rawdata[1] = self.DATA_TYPE

    def getTypeName(self):
        raise NotImplementedError("Implemnt in sub-class")

    def getJson(self):
        raise NotImplementedError("Implemnt in sub-class")

    def getDataSize(self):
        raise NotImplementedError("Implemnt in sub-class")

    @property
    def data_type(self):
        return self.rawdata[1]

    @data_type.setter
    def data_type(self, value):
        self.rawdata[1] = value

    @property
    def seqnum(self):
        return self.rawdata[2]

    @seqnum.setter
    def seqnum(self, value):
        self.rawdata[2] = value

    @property
    def nsamples(self):
        return self.rawdata[3]

    @nsamples.setter
    def nsamples(self, value):
        self.rawdata[3] = value

    @property
    def rdata(self):
        return self.rawdata[4:4 + self.getDataSize()]

    @rdata.setter
    def rdata(self, value):
        self.rawdata[4:4 + self.getDataSize()] = value


class TemperatureData(SensorDataReply):
    DATA_TYPE = 0x01

    def __init__(self):
        super().__init__()
        self.rawdata.extend(bytearray(4))  # time
        self.rawdata.extend(bytearray(2))  # temperature

    def getJson(self):
        return json.dumps({"time": self.time, "temperature": self.temperature})

    def getTypeName(self):
        return "TEMP"

    def getDataSize(self):
        return 6 * self.nsamples

    @property
    def time(self):
        return unpack(PAT_UINT32, self.rawdata[4:8])[0]

    # @time.setter
    # def time(self, value):
    #     self.rawdata[4:8] = pack(PAT_UINT32, value)

    @property
    def temperature(self):
        return unpack(PAT_UINT16, self.rawdata[8:10])[0]

    # @temperature.setter
    # def temperature(self, value):
    #     self.rawdata[8:10] = pack(PAT_UINT16, value)


class SpectrumData(SensorDataReply):
    DATA_TYPE = 0x02

    def __init__(self):
        super().__init__()
        self.rawdata.extend(bytearray(4))   #time
        self.rawdata.extend(bytearray(128)) #fft_part

    def getTypeName(self):
        return "FFT"

    def getDataSize(self):
        return 128

    @property
    def time(self):
        return unpack(PAT_UINT32, self.rawdata[4:8])[0]

    # @time.setter
    # def time(self, value):
    #     self.rawdata[4:8] = pack(PAT_UINT32, value)

    @property
    def fft_chunk(self):
        fft_bins= []
        for i in range(128//4):
            fft_bins.append(unpack(PAT_FLOAT, self.rawdata[8 + i*4: 8+i*4+4])[0])
        return fft_bins


