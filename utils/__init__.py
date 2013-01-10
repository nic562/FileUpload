# coding=utf8

import struct

def int2hex(value, int_len=4):
    unsigned_len_map = {4: 'I', 2: 'H', 1:'B'}
    return struct.pack('!%s'%unsigned_len_map[int_len], value)

def hex2int(value, int_len=4):
    unsigned_len_map = {4: 'I', 2: 'H', 1:'B'}
    return struct.unpack('!%s'%unsigned_len_map[int_len], value)[0]