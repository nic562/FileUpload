# coding=utf8
'''
Created on 2012-9-28

@author: nic
'''

import os, hashlib, Image, StringIO

from FileUpload.utils import int2hex
from FileUpload.const import InvalidArgsError, AuthenticateError, FileTypeError, FilesystemError, FileHashError, FileExistError
from FileUpload.handlers.base import BaseHandler
from FileUpload.configs import settings

class ImageHandler(BaseHandler):
    ALLOW_FILE_EXTENSION = ['JPG', 'JPEG', 'PNG', 'GIF']
        
    def handle_request(self, tlv):
        # print 'handle request', tlv
        # 解析请求参数
        self._parse_request_args(tlv)

        # 检查请求参数是否存在错误
        if not self.session_id:
            raise InvalidArgsError()

        # 检查session
        if not self._check_session():
            raise AuthenticateError()
        
        file_ext = self._check_file_extension()
        if file_ext == 'JPG':
            self.file_type = 'JPEG'
            
    
        
        