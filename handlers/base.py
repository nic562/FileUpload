# coding=utf8
'''
Created on 2013-1-9

@author: nic
'''

import hashlib

from FileUpload.utils import int2hex, hex2int
from FileUpload.const import (REQ_TAG_SESSION_ID, REQ_TAG_FILENAME, RETURN_TAG_FILENAME,
                              FileSizeError, InvalidArgsError, FileTypeError,
                              AuthenticateError, FileExistError, FileHashError)
from FileUpload.configs import settings
from FileUpload.handlers.file_system import BaseFileSystem

class BaseHandler(object):
    ALLOW_FILE_EXTENSION = [] # 空则代表允许所有
    FILE_MAX_SIZE = settings.DEFAULT_FILESIZE_LIMIT
   
    def __init__(self, file_system, file_size, file_hash):
        assert isinstance(file_system, BaseFileSystem)
        self._fs = file_system
        self.session_id = ''
        self.file_name = ''
        self.file_size = file_size
        self.file_hash = file_hash
        if self.file_size > self.FILE_MAX_SIZE:
            raise FileSizeError()

    def _parse_request_args(self, tlv):
        pos = 0
        while pos < len(tlv):
            tag = hex2int(tlv[pos:pos+2], int_len=2)
            # print 'tag', tag
            if not tag:
                break

            length = hex2int(tlv[pos+2:pos+4], int_len=2)
            value = tlv[pos+4:pos+4+length]
            if tag == REQ_TAG_SESSION_ID:
                self.session_id = value 
            if tag == REQ_TAG_FILENAME:
                self.file_name = value

            pos = pos + 4 + length
        
    def _check_file_exist(self):
        'check self.file_name and return exist_filename/False'
        if settings.DEBUG: print 'check file exist........'
        return self._fs.check_file_exist(self.file_name, self.file_hash, self.file_type)
    
    def _check_file_extension(self):
        if settings.DEBUG: print 'check file extension........'
        ext_index = self.file_name.rfind('.')
        if ext_index == -1:
            raise FileTypeError()
        ext = self.file_name[ext_index+1 :].upper()
        if (not self.ALLOW_FILE_EXTENSION) or (ext and ext in self.ALLOW_FILE_EXTENSION):
            self.file_type = ext
            return ext
        else:
            raise FileTypeError()

    def check_session(self):
        'check self.session_id and return True/False'
        raise Exception, NotImplemented

    def check_request(self, tlv):
        '请重载该方法，用于各个不同需求的tlv参数检测'
        raise Exception, NotImplemented
        
    def handle_request(self, tlv):
        # print 'handle request', tlv
        self._parse_request_args(tlv)
        # 解析请求参数

        if not self.session_id:
        # 检查请求参数是否存在错误
            raise InvalidArgsError()

        if not self.check_session():
        # 检查session
            raise AuthenticateError()
        
        self._check_file_extension()
        
        exist_file = self._check_file_exist()
        if exist_file:
            result = ''
            result += int2hex(10, int_len=2)
            result += int2hex(len(exist_file), int_len=2)
            result += exist_file
            raise FileExistError(result)
        
        self.check_request(tlv)
        
    def _save_file(self, content):
        '保存文件并返回保存后的文件名'
        return self._fs.put_file(self.file_name, self.file_type, content)
    
    def make_return_file_name(self, filename):
        raise Exception, NotImplemented

    def handle_upload(self, content):
        # print 'handle upload', content
        # 检查文件hash
        m = hashlib.md5()
        m.update(content)
        if m.digest() != self.file_hash:
            raise FileHashError()
        
        file_name = self.make_return_file_name(self._save_file(content))
        
        # 返回结果TLV
        result = ''
        result += int2hex(RETURN_TAG_FILENAME, int_len=2)
        result += int2hex(len(file_name), int_len=2)
        result += file_name
        return result 

