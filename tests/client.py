# coding=utf8
'''
Created on 2013-1-18

@author: nic
'''
import sys, socket, hashlib, traceback

from FileUpload.configs import settings
from FileUpload.const import (RESULT_ALLOW_UPLOAD, RESULT_UPLOAD_SUCCESS, RESULT_BUSY, RESULT_AUTH_FAIL,
                              RESULT_FILE_TOO_LARGE, RESULT_INVALID_ARGS, RESULT_WRONG_FILE_TYPE, RESULT_FILE_EXIST,
                              RESULT_FS_ERROR)
from FileUpload.utils import int2hex, hex2int

def open_conn(host, port):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(100)
        s.connect((host, port))
    except:
        traceback.print_exc()
        s.close()
    return s

def push_file(app_id, filename, session_id, server_ip, server_port):
    print 'put file to : %s:%s' %(server_ip, server_port)
    f = open(filename, 'r')
    content = f.read()
    f.close()
    
    m = hashlib.md5()
    m.update(content)
    file_hash = m.digest()
    file_size = len(content)
    file_name = f.name
    
    request = ''
    request += int2hex(26 + 4 * 2 + len(session_id) + len(file_name))
    request += int2hex(app_id, int_len=2)
    request += int2hex(file_size)
    request += file_hash
    request += int2hex(1, int_len=2)
    request += int2hex(len(session_id), int_len=2)
    request += session_id
    request += int2hex(2, int_len=2)
    request += int2hex(len(file_name), int_len=2)
    request += file_name
    
    s = open_conn(server_ip, server_port)
    s.sendall(request)
    response = s.recv(2) # 请求结果2个字节
    result = hex2int(response, int_len=2)
    if result == RESULT_ALLOW_UPLOAD:
        p = int(file_size / 10)
        sum_ = 0
        for _k in range(1, 10):
            c_ = content[p*(_k-1): p*_k]
            sum_ += len(c_)
            print '  %d%% [%d/%d] ...' %(_k * 10, sum_, file_size)
            s.sendall(c_)
        print ' %d%% [%d/%d] ...' %((_k + 1) * 10, sum_ + len(content[p*_k: ]), file_size)
        s.sendall(content[p*_k: ])
        try:
            upload_response = s.recv(6) # 这6个字节分别为：4个字节的包长度，2个字节的上传结果
            # 正常上传结果
            packet_len = hex2int(upload_response[:4])
            result = hex2int(upload_response[4:6], int_len=2)
        except:
            result = hex2int(upload_response[:2], int_len=2) # 上传过程中发生异常，则只有2字节
        if result == RESULT_UPLOAD_SUCCESS:
            tlv = s.recv(packet_len - 6)
            pos = 0
            f_url = None
            while pos < len(tlv):
                tag = hex2int(tlv[pos:pos+2], int_len=2)
                if not tag:
                    break
                length = hex2int(tlv[pos+2:pos+4], int_len=2)
                value = tlv[pos+4:pos+4+length]
                pos += 4 + length
                if tag == 10: # 文件路径tag
                    f_url = value
                else:
                    print 'unknow tag:::::::::', tag
                    break
            print 'f_url::::::::::::', f_url
            
        else:
            print 'upload error::::', result
    else:
        if result == RESULT_FILE_EXIST: # 文件已经存在
            print 'file exist!!'
            pak_len = hex2int(s.recv(4)) - 4
            pak = s.recv(pak_len)
            p = 0
            f_url = None
            while p < pak_len:
                t = hex2int(pak[p:p+2], int_len=2)
                # print "tag::", t
                if not t:
                    break
                
                length = hex2int(pak[p+2:p+4], int_len=2)
                # print 'len::', length
                value = pak[p+4:p+4+length]
                # print 'value::', value
                p += 4 + length
                if t == 10: # 文件路径tag
                    f_url = value
                else:
                    print 'unknow tag:::::::::', t
                    break
            print 'f_url::::::::::::', f_url
        else:
            print 'upload error::::',
            if result == RESULT_WRONG_FILE_TYPE:
                print u'不允许的文件类型'
            elif result == RESULT_INVALID_ARGS:
                print u'参数无效'
            elif result == RESULT_FILE_TOO_LARGE:
                print u'文件太大'
            elif result == RESULT_AUTH_FAIL:
                print u'认证错误'
            elif result == RESULT_BUSY:
                print u'系统繁忙'
            elif result == RESULT_FS_ERROR:
                print u'文件系统异常'
            else:
                print u'未知错误[%s]' %result
    s.close()
        
if __name__ == '__main__':
    l = len(sys.argv)
    if l < 3:
        print 'args: filename session_id [server_ip, server_port]'
        sys.exit(0)
    f = sys.argv[1]
    sid = sys.argv[2]
    sip = sys.argv[3] if l > 3 else settings.SERVER_IP
    port = int(sys.argv[4]) if l > 4 else settings.SERVER_PORT
    push_file(1, f, sid, sip, port)