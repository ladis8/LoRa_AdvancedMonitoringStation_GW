"""
\file       lora_module.py
\author     Ladislav Stefka
\brief      Module with additional tools 
\copyright
"""

from array import array

def to_uint8t(b):
    return b & 0xFF

def set_bit(reg, index, val):
    mask = 0x1 << index
    return reg | mask if val else reg & ~mask

def write_data_to_file(data, file, dtype):
    f = open(file, "wb")
    float_array = array(dtype, data)
    float_array.tofile(f)
    f.close()
