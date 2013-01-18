# coding=utf8
'''
Created on 2013-1-9

@author: nic
'''
import os, hashlib

from FileUpload.utils.tfs import TFS as BaseTFS

class BaseFileSystem(object):
    '基础文件系统类，用于定义文件上传handler所使用的文件操作函数'
    def check_file_exist(self, filename, filehash, filetype):
        '''检查文件是否存在
        若存在，则返回该文件名，不存在则返回False
        @param filehash: 为一个16字节的字符串
        '''
        raise NotImplemented
    
    def put_file(self, filename, filetype, content):
        '保存文件并返回保存后的文件名'
        raise NotImplemented
        
    def delete_file(self, filename):
        '删除文件'
        raise NotImplemented
    
class LocalFileSystem(BaseFileSystem):
    '本地磁盘文件系统, 上传的文件均不保存原来文件名，必须使用文件内容hash作为存储文件名'
    def __init__(self, file_path):
        self.fpath = file_path
        if not os.path.isdir(self.fpath):
            raise Exception('[%s] is not dir' %self.fpath)
    
    def check_file_exist(self, filename, filehash, filetype):
        file_name = '%s.%s' %(filehash.encode('hex'), filetype)
        return os.path.isfile(os.path.join(self.fpath, file_name)) and file_name
    
    def put_file(self, filename, filetype, content):
        m = hashlib.md5(content)
        f_name = '%s.%s' %(m.hexdigest(), filetype)
        f = open(os.path.join(self.fpath, f_name), 'w')
        f.write(content)
        f.flush()
        f.close()
        return f_name
    
    def delete_file(self, filename):
        fp = os.path.join(self.fpath, filename)
        if os.path.isfile(fp):
            os.remove(fp)
    
class TFS(BaseFileSystem):
    '淘宝小文件系统'
    def __init__(self, server_ip, port, app_id, app_key):
        self.tfs = BaseTFS(server_ip, port, app_id, app_key)
        
    def check_file_exist(self, filename, filehash, filetype):
        return self.tfs.check_file(filename)
    
    def put_file(self, filename, filetype, content):
        return self.tfs.put(filename, content)
    
    def delete_file(self, filename):
        return self.tfs.delete_file(filename)
