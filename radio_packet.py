"""
\file       radio_packet.py
\author     Ladislav Stefka
\brief      Definition of binary radio protocol between central unit and measuring units
            - defines radio packets used in application
\copyright
"""

import binascii
from struct import pack, unpack
import json

# TODO: Soleve nsamples

PAT_UINT64 = "Q"
PAT_UINT32 = "I"
PAT_UINT16 = "H"
PAT_UINT8 = "B"
PAT_FLOAT = "f"
PAT_STR8 = "8s"


# [0] CMD
# [1] ID
# [2] DATA_TYPE !OPTIONAL

class RadioPacket:
    """General radio packet class"""

    RES_RESULT_OK = 0,
    RES_ERROR = 1,
    RES_BUSY = 2,
    RES_INVALID_CMD = 3,
    RES_TIMEOUT = 4,

    def __init__(self, data=None):
        if data:
            self.command = data[0]
            self.rawdata = bytes(data)
            self.rsii = None
            self.snr = None
            for x in RadioPacket.__subclasses__():
                if x.CMD == self.command:
                    if self.command == SensorDataReply.CMD:
                        for sensor_dt in SensorDataReply.__subclasses__():
                            if self.rawdata[2] == sensor_dt.DATA_TYPE:
                                self.__class__ = sensor_dt
                                return
                        raise NameError("Sensor class not found for data_type", self.rawdata[2], "data len",
                                        len(self.rawdata))
                    else:
                        self.__class__ = x
                        return
            raise NameError("Packet class not found for command ", self.command)

        else:
            self.rawdata = bytearray(2)
            self.rawdata[0] = self.__class__.CMD

    @property
    def sessionid(self):
        return self.rawdata[1]

    @sessionid.setter
    def sessionid(self, value):
        self.rawdata[1] = value

    def __str__(self):
        return "Radio packet {} data: {}".format(self.getName(), str(self.__dict__))

    def __len__(self):
        return len(self.rawdata)

    def __iter__(self):
        return iter(self.rawdata)

    def __add__(self, other):
        print("Add called")
        if isinstance(other, list):
            return other + list(self.rawdata)
        if isinstance(other, bytes) or isinstance(other, bytearray):
            return other + self.rawdata

    def toHexString(self):
        return binascii.hexlify(self.rawdata).decode()

    def getName(self):
        return self.__class__.__name__


#region Join Process
class JoinRequest(RadioPacket):
    CMD = 0x10

    def __init__(self):
        super().__init__()
        self.rawdata.extend(bytearray(4 + 1))

    @property
    def unique_id(self):
        return "0x{0:08X}".format(unpack(PAT_UINT32, self.rawdata[2:6])[0])

    @property
    def time(self):
        return unpack(PAT_UINT32, self.rawdata[6:10])[0]

    @property
    def fwver(self):
        return self.rawdata[11]

#TODO: move application mode up
class JoinReply(RadioPacket):
    CMD = 0x01

    def __init__(self):
        super().__init__()
        self.rawdata.extend(bytearray(1 + 3 * 1 + 2 + 1))

    @property
    def result(self):
        return self.rawdata[2]

    @result.setter
    def result(self, value):
        self.rawdata[2] = value

    @property
    def bw(self):
        return self.rawdata[3]

    @bw.setter
    def bw(self, value):
        self.rawdata[3] = value

    @property
    def sf(self):
        return self.rawdata[4]

    @sf.setter
    def sf(self, value):
        self.rawdata[4] = value

    @property
    def cr(self):
        return self.rawdata[5]

    @cr.setter
    def cr(self, value):
        self.rawdata[5] = value

    @property
    def join_interval(self):
        return unpack(PAT_UINT16, self.rawdata[6:8])[0]

    @join_interval.setter
    def join_interval(self, value):
        self.rawdata[6:8] = pack(PAT_UINT16, value)

    @property
    def app_mode(self):
        return self.rawdata[8]

    @app_mode.setter
    def app_mode(self, value):
        self.rawdata[8] = value

#endregion


# class JoinReplyCommandMode(JoinReply):
#     pass

#region Config Process
class ConfigRequest(RadioPacket):
    CMD = 0x20

    def __init__(self):
        super().__init__()

class ConfigReply(RadioPacket):
    CMD = 0x02

    def __init__(self):
        super().__init__()
        self.rawdata.extend(bytearray(5 + 5 + 5))
        self.app_mode = 0

    #region General Settings
    @property
    def statusinfo_interval(self):
        return unpack(PAT_UINT16, self.rawdata[2:4])[0]

    @statusinfo_interval.setter
    def statusinfo_interval(self, value):
        self.rawdata[2:4] = pack(PAT_UINT16, value)

    @property
    def statusinfo_listen_interval(self):
        return unpack(PAT_UINT16, self.rawdata[4:6])[0]

    @statusinfo_listen_interval.setter
    def statusinfo_listen_interval(self, value):
        self.rawdata[4:6] = pack(PAT_UINT16, value)

    @property
    def temperature_averaging_num(self):
        return self.rawdata[6]

    @temperature_averaging_num.setter
    def temperature_averaging_num(self, value):
        assert value <= 10
        self.rawdata[6] = value
    #endregion

    #region ADC && FFT
    @property
    def fft_adc_sampling_time(self):
        return self.rawdata[7]

    @fft_adc_sampling_time.setter
    def fft_adc_sampling_time(self, value):
        self.rawdata[7] = value

    @property
    def fft_adc_divider(self):
        return self.rawdata[8]

    @fft_adc_divider.setter
    def fft_adc_divider(self, value):
        self.rawdata[8] = value

    @property
    def fft_samples_num(self):
        return self.rawdata[9]

    @fft_samples_num.setter
    def fft_samples_num(self, value):
        self.rawdata[9] = value

    @property
    def fft_peaks_num(self):
        return self.rawdata[10]

    @fft_peaks_num.setter
    def fft_peaks_num(self, value):
        assert value <= 10
        self.rawdata[10] = value

    @property
    def fft_peaks_delta(self):
        return self.rawdata[11]

    @fft_peaks_delta.setter
    def fft_peaks_delta(self, value):
        assert value <= 10
        self.rawdata[11] = value
    #endregion

    #region DSP
    @property
    def dsp_threshold_voltage(self):
        return unpack(PAT_UINT16, self.rawdata[12:14])[0]

    @dsp_threshold_voltage.setter
    def dsp_threshold_voltage(self, value):
        self.rawdata[12:14] = pack(PAT_UINT16, value)

    @property
    def dsp_kurtosis_trimmed_samples(self):
        return self.rawdata[14]

    @dsp_kurtosis_trimmed_samples.setter
    def dsp_kurtosis_trimmed_samples(self, value):
        assert value < 50
        self.rawdata[14] = value

    @property
    def dsp_rms_ac(self):
        return self.rawdata[15]

    @dsp_rms_ac.setter
    def dsp_rms_ac(self, value):
        assert value == 0 or value == 1
        self.rawdata[15] = value

    @property
    def dsp_rms_averaging_num(self):
        return self.rawdata[16]

    @dsp_rms_averaging_num.setter
    def dsp_rms_averaging_num(self, value):
        assert value <= 10
        self.rawdata[16] = value
#endregion


#region Statusinfo
class StatusInfo(RadioPacket):
    CMD = 0x30  # StatusInfo.CMD

    def __init__(self):
        super().__init__()
        self.rawdata.extend(bytearray(0))

    #region measurments
    @property
    def battery(self):
        return self.rawdata[2]

    @property
    def temperature(self):
        return unpack(PAT_UINT16, self.rawdata[3:5])[0]

    @property
    def rms(self):
        return unpack(PAT_UINT16, self.rawdata[5:7])[0]

    @property
    def vpp(self):
        return unpack(PAT_UINT16, self.rawdata[7:9])[0]

    @property
    def kurtosis_ratio(self):
        return unpack(PAT_FLOAT, self.rawdata[9:13])[0]

    @property
    def ringdown_counts(self):
        return self.rawdata[13]

    @property
    def rise_time(self):
        return unpack(PAT_UINT16, self.rawdata[14:16])[0]

    @property
    def threshold_duration(self):
        return unpack(PAT_UINT16, self.rawdata[16:18])[0]

    @property
    def fft_peaks_num(self):
        return self.rawdata[18]

    @property
    def fft_peaks_indexes(self):
        peaks = []
        lastindex = 19
        for i in range(self.fft_peaks_num):
            index = unpack(PAT_UINT16, self.rawdata[lastindex+i*2 : lastindex+(i+1)*2])[0]
            peaks.append(index)
        return peaks

    @property
    def fft_peaks_values(self):
        peaks = []
        lastindex = 19 + self.fft_peaks_num * 2
        for i in range(self.fft_peaks_num):
            value = unpack(PAT_FLOAT, self.rawdata[lastindex+i*4 : lastindex+(i+1)*4])[0]
            peaks.append(value)
        return peaks

    def get_fft_peaks(self):
        peaks = []
        fft_peaks_indexes = self.fft_peaks_indexes
        fft_peaks_values = self.fft_peaks_values
        for i in range(self.fft_peaks_num):
            peaks.append((fft_peaks_indexes[i], fft_peaks_values[i]))
        return sorted(peaks)
#endregion

class Restart(RadioPacket):
    CMD = 0x60  # StatusInfo.CMD

    def __init__(self):
        super().__init__()
        self.rawdata.extend(bytearray(1))
    @property
    def resetConfig(self):
        return self.rawdata[2]

    @resetConfig.setter
    def resetConfig(self, value):
        assert int(value) == 1 or int(value) == 0
        self.rawdata[2] = value




class SensorDataRequest(RadioPacket):
    CMD = 0x04
    DATA_TYPE = 0x00

    def __init__(self):
        super().__init__()
        self.rawdata.extend(bytearray(1 + 1))
        if self.DATA_TYPE:
            self.rawdata[2] = self.DATA_TYPE

    @property
    def data_type(self):
        return self.rawdata[2]

    @data_type.setter
    def data_type(self, value):
        self.rawdata[2] = value

    @property
    def nsamples(self):
        return self.rawdata[3]

    @nsamples.setter
    def nsamples(self, value):
        self.rawdata[3] = value


class TemperatureDataRequest(SensorDataRequest):
    DATA_TYPE = 0x01

    def __init__(self):
        super().__init__()


# data types max 256 seqn num
class SensorDataReply(RadioPacket):
    CMD = 0x40
    DATA_TYPE = 0x00

    def __init__(self):
        super().__init__()
        self.rawdata.extend(bytearray(3))  # data_type, seqnum, nsamples
        if self.DATA_TYPE:
            self.rawdata[2] = self.DATA_TYPE

    def getTypeName(self):
        raise NotImplementedError("Implemnt in sub-class")

    def getJson(self):
        raise NotImplementedError("Implemnt in sub-class")

    def getDataSize(self):
        raise NotImplementedError("Implemnt in sub-class")

    @property
    def data_type(self):
        return self.rawdata[2]

    @data_type.setter
    def data_type(self, value):
        self.rawdata[2] = value

    @property
    def seqnum(self):
        return self.rawdata[3]

    @seqnum.setter
    def seqnum(self, value):
        self.rawdata[3] = value

    @property
    def nsamples(self):
        return self.rawdata[4]

    @nsamples.setter
    def nsamples(self, value):
        self.rawdata[4] = value

    @property
    def data(self):
        return self.rawdata[5:5 + self.getDataSize()]

    @data.setter
    def data(self, value):
        self.rawdata[5:5 + self.getDataSize()] = value


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
        return 5 * self.nsamples

    @property
    def time(self):
        return unpack(PAT_UINT32, self.rawdata[5:9])[0]

    # @time.setter
    # def time(self, value):
    #     self.rawdata[4:8] = pack(PAT_UINT32, value)

    @property
    def temperature(self):
        return unpack(PAT_UINT16, self.rawdata[9:11])[0]

        # @temperature.setter
        # def temperature(self, value):
        #     self.rawdata[8:10] = pack(PAT_UINT16, value)


# region DATA CHUNKS

class FFTChunkRequest(RadioPacket):
    CMD = 0x05
    DATA_TYPE = 0x01

    def __init__(self):
        super().__init__()
        self.rawdata.extend(bytearray(1))

    @property
    def data_type(self):
        return self.rawdata[2]

    @data_type.setter
    def data_type(self, value):
        self.rawdata[2] = value


class FFTChunkData(RadioPacket):
    CMD = 0x50
    DATA_TYPE = 0x01

    def __init__(self):
        super().__init__()
        self.rawdata.extend(bytearray(3))  # data_type, seqnum, nsamples
        self.rawdata.extend(bytearray(128))  # chunksize
        if self.DATA_TYPE:
            self.rawdata[2] = self.DATA_TYPE

    @property
    def data_type(self):
        return self.rawdata[2]

    @property
    def seqnum(self):
        return self.rawdata[3]

    @property
    def nchunks(self):
        return self.rawdata[4]

    @property
    def time(self):
        return unpack(PAT_UINT32, self.rawdata[5:9])[0]

    @property
    def data(self):
        return self.rawdata[9:]

    def get_FFT_bins(self):
        fft_bins = []
        for i in range(128 // 4):
            fft_bins.append(unpack(PAT_FLOAT, self.rawdata[9 + i * 4: 9 + i * 4 + 4])[0])
        return fft_bins

    def getTypeName(self):
        return "FFT"
# endregion
