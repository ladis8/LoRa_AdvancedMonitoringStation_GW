import requests
import logging
from collections import OrderedDict

import radio_packet as rp


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



#TODO: rejoin if lora params differ

class Config:

    VOLTAGE = 3.3
    BATTERY_FULL = 254

    CFG_DEFAULT_BW = "BW7_8"
    CFG_DEFAULT_SF = "SF12"
    CFG_DEFAULT_CR = "CR4_5"
    CFG_DEFAULT_JOIN_INTERVAL = 10000


    def __init__(self):
        self.config_fetched = False

        #lora settings
        self.lora_bw = None
        self.lora_cr = None
        self.lora_sf = None
        self.lora_freq = None

        #statusinfo settings
        self.statusinfo_interval = None
        self.statusinfo_listen_interval = None
        self.join_interval = None

        #dsp settings
        self.dsp_rms_averaging_num = None
        self.dsp_rms_ac  = None
        self.dsp_kurtosis_trimmed_samples = None
        self.dsp_threshold_voltage = None

        #fft settings
        self.fft_samples_num = None
        self.fft_peaks_num = None
        self.fft_peaks_delta= None
        self.fft_adc_sampling_time = None
        self.fft_adc_divider = None
        self.adc_resolution = None

        #temperature_settings
        self.temperature_averaging_num = None
        self.temperature_calibration_const = None

    def __str__(self):
        return "Config of lora node:\n" +\
               "".join("   setting: {} - {}\n".format(x, self.__dict__[x]) for x in self.__dict__.keys())


    def set_from_json_packet(self, jp):
        for setting in jp.settings:
            key = setting['code'].split(".")[-1]
            if setting['datatype'] == "int": value = int(setting['value'])
            if setting['datatype'] == "float": value = float(setting['value'])
            if setting['datatype'] == "bool": value = bool(setting['value'])
            if setting['datatype'] == "pointer" or setting['datatype'] == "text": value = setting['value']
            if key in self.__dict__:
                self.__dict__[key] = value
            else:
                logging.warning("Setting %s with value %s is not in Config parameters!", key, value)

        self.config_fetched = True

    def get_fft_params(self):
        adc_divider = ADCDividers[self.fft_adc_divider]
        adc_sampling_time = ADCSamplingTimes[self.fft_adc_sampling_time]
        fs = HSI_FREQUENCY/adc_divider * 1.0/(ADC_CONV_CONST + adc_sampling_time)
        N = FFTSamplesNum[self.fft_samples_num]
        return (fs, N) #returns tuple (fs, N-samplenum)


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

        config.config_fetched = True

    @staticmethod
    def store_config_to_radio_packet(config, cr):

        if isinstance(cr, rp.ConfigReply):
            #General
            cr.statusinfo_interval = config.statusinfo_interval
            cr.statusinfo_listen_interval = config.statusinfo_listen_interval
            cr.temperature_averaging_num = config.temperature_averaging_num
            #FFT && ADC
            cr.fft_adc_divider = list(ADCDividers.keys()).index(config.fft_adc_divider)
            cr.fft_adc_sampling_time = list(ADCSamplingTimes.keys()).index(config.fft_adc_sampling_time)
            cr.fft_samples_num = list(FFTSamplesNum.keys()).index(config.fft_samples_num)
            cr.fft_peaks_num = config.fft_peaks_num
            cr.fft_peaks_delta = config.fft_peaks_delta
            #DSP
            cr.dsp_threshold_voltage = int(config.dsp_threshold_voltage * config.adc_resolution / Config.VOLTAGE)
            cr.dsp_kurtosis_trimmed_samples = config.dsp_kurtosis_trimmed_samples
            cr.dsp_rms_averaging_num = config.dsp_rms_averaging_num
            cr.dsp_rms_ac = int(config.dsp_rms_ac)

        elif isinstance(cr, rp.JoinReplyCommandMode):
            raise NotImplementedError()

        config.config_fetched = True





