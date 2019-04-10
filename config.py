import requests
import radio_packet as rp
from collections import OrderedDict


#TODO: Create enums insted dict

#Configurable parameters - sending index insted of value
FFTSamplesNum = OrderedDict([
    ('N_64', 64),
    ('N_128', 128),
    ('N_512', 512),
    ('N_1024', 1024),
    ('N_2048', 2048)
])

ADCSamplingTimes = OrderedDict([
    ("1CYCLE5", 1.5),
    ("3CYCLE5", 3.5),
    ("7CYCLE5", 7.5),
    ("12CYCLE5", 12.5),
    ("19CYCLE5", 19.5),
    ("39CYCLE5", 39.5),
    ("79CYCLE5", 79.5),
    ("160CYCLE5", 160.5)
])
ADCDividers = OrderedDict([
    ("ASYNC_DIV1", 1),
    ("ASYNC_DIV2", 2),
    ("ASYNC_DIV4", 4),
    ("ASYNC_DIV8", 8),
    ("ASYNC_DIV16", 16),
    ("ASYNC_DIV32", 32),
    ("ASYNC_DIV64", 64),
    ("ASYNC_DIV128", 128),
    ("ASYNC_DIV256", 256)
])

Bandwidth = {
    "BW7_8"  : 0,
    "BW15_6" : 1,
    "BW20_8" : 3,
}

SpreadingFactor = {
    "SF7": 0,
    "SF8": 1,
    "SF9": 2,
    "SF10": 3,
    "SF11": 4,
    "SF12": 5
}

CodingRate = {
   "CR4_5": 0
}

HSI_FREQUENCY = 16000000
ADC_CONV_CONST = 12.5


URL_CONFIG = "http://127.0.0.1:1880/lora_nodered/config"





class Config:
    def __init__(self ):
        #lora settings
        self.bw = None
        self.cr = None
        self.sf = None
        self.f = None

        #statusinfo settings
        self.statusinfo_interval = None
        self.temperature_averaging_num = None
        self.rms_averaging_num = None

        #fft settings
        self.fft_samples_num = None
        self.fft_peaks_num = None
        self.fft_adc_sampling_time = None
        self.fft_adc_divider = None

    def __str__(self):
        return ("Config of lora node: {}".format(self.__dict__))

    @staticmethod
    def HTTP_get_config_fromDB(config, idloranode):

        params = {'idloranode': idloranode}
        req = requests.get(url=URL_CONFIG, params=params)
        out = req.json()

        if not len(out):
            raise Exception("No DB config for loranode with id {}".format(idloranode))

        for row in out:
            key = row['code'].split(".")[-1]
            if row['datatype'] == "int": value = int(row['value'])
            if row['datatype'] == "float": value = float(row['value'])
            if row['datatype'] == "pointer" or row['datatype'] == "text": value = row['value']
            config.__dict__[key] = value

    @staticmethod
    def store_config_to_radio_packet(config, jr):

        jr.bw = Bandwidth[config.bw]
        jr.sf = SpreadingFactor[config.sf]
        jr.cr = CodingRate[config.cr]

        if isinstance(jr, rp.JoinReplyStatusMode):
            jr.statusinfo_interval = config.statusinfo_interval
            jr.rms_averaging_num = config.rms_averaging_num
            jr.temperature_averaging_num = config.temperature_averaging_num
            jr.fft_samples_num = list(FFTSamplesNum.keys()).index(config.fft_samples_num)
            jr.fft_adc_divider = list(ADCDividers.keys()).index(config.fft_adc_divider)
            jr.fft_adc_sampling_time = list(ADCSamplingTimes.keys()).index(config.fft_adc_sampling_time)
            jr.fft_peaks_num = config.fft_peaks_num

        if isinstance(jr, rp.JoinReplyCommandMode):
            raise NotImplementedError()

    #returns tuple (fs, N-samplenum)
    def get_fft_params(self):
        adc_divider = ADCDividers[self.fft_adc_divider]
        adc_sampling_time = ADCSamplingTimes[self.fft_adc_sampling_time]
        fs = HSI_FREQUENCY/adc_divider * 1.0/(ADC_CONV_CONST + adc_sampling_time)
        N = FFTSamplesNum[self.fft_samples_num]
        return (fs, N)




