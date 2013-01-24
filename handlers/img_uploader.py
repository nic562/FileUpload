# coding=utf8
'''
Created on 2012-9-28

@author: nic
'''

from FileUpload.handlers.base import BaseHandler

class ImageHandler(BaseHandler):
    CONNECTION_TIMEOUT = 10 # 上传过程总超时时间, 秒
    ALLOW_FILE_EXTENSION = ['JPG', 'JPEG', 'PNG', 'GIF']
        
    def check_request(self, tlv):
        if self.file_type == 'JPG':
            self.file_type = 'JPEG'
            
    def make_return_file_name(self, filename):
        return filename
    
    def check_session(self):
        return True
    
    
        
        