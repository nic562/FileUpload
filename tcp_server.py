# -*- coding: utf-8 -*-

import sys, traceback, logging, time, threading

from gevent import server, monkey
from multiprocessing import Process, current_process

from FileUpload.handlers import get_app_handler
from FileUpload.utils import int2hex, hex2int
from FileUpload.const import (RESULT_INVALID_ARGS, FileSizeError, RESULT_FILE_TOO_LARGE, InvalidArgsError,
                              AuthenticateError, RESULT_AUTH_FAIL, FileTypeError, RESULT_WRONG_FILE_TYPE, FileExistError,
                              RESULT_FILE_EXIST, RESULT_ALLOW_UPLOAD, FileHashError, RESULT_HASH_ERROR,
                              RESULT_FS_ERROR, RESULT_UPLOAD_SUCCESS)
from FileUpload.configs import settings

log = logging

monkey.patch_os()

def note(formatter, *args):
    sys.stderr.write('[%s]\t%s\n' % ( current_process().name, formatter%args))

SOCKET_STATUS_WAITING = 'waiting' # 等待状态
SOCKET_STATUS_WORKING = 'working' # 工作状态

living_socket_list = []

def _close_socket(sk):
    try:
        sk.shutdown(0) # 关闭读入流
        sk.shutdown(1) # 关闭写入流
        sk.close()
    except:
        pass # log.error(traceback.format_exc())
    finally:
        if sk in living_socket_list:
            living_socket_list.remove(sk)
        del(sk)

def kill_timeout_socket(base_timeout=5):
    '@param base_timeout: 基础超时时长，若一个链接一直处于等待状态，超过这个时间值则把它关闭，用于过滤占用资源却无任何数据输入的链接'
    for _lc in living_socket_list:
        now = time.time()
        # print 'now %s, start %s, pass %s , timeout %s' %(now, _lc._start_time, now - _lc._start_time, _lc.timeout)
        if _lc._status == SOCKET_STATUS_WAITING:
            if (now - _lc._start_time) >= base_timeout:
                if settings.DEBUG: note( 'shutdown empty connection %s id:%s' %(_lc, id(_lc)))
                _close_socket(_lc)
        else:
            if (now - _lc._start_time) >= _lc.timeout:
                if settings.DEBUG: note( 'shutdown working timeout connection %s id:%s' %(_lc, id(_lc)))
                _close_socket(_lc)

class SocketManager(threading.Thread):
    def run(self):
        note('start socketmanager')
        while 1:
            time.sleep(5)
            # note('checking socket list [size=%s]' %len(living_socket_list))
            kill_timeout_socket()
__s = SocketManager()
__s.setDaemon(True) # 设置为后台子线程，后台子线程随主线程的结束而结束
__s.start()

def _gc_socket(func):
    'socket 回收装饰器'
    def wrapper(socket, remote_address):
        if settings.DEBUG: note('new socket: %s' %id(socket))
        living_socket_list.append(socket) # 把链接存放到管理列表中
        func(socket, remote_address)
        if socket in living_socket_list:
            try:
                _close_socket(socket)
            except:
                pass
    return wrapper

class FileObjWrapper(object):
    '''
        由于链接管理器对链接实行了超时关闭管理
        所以在原进程中运行的链接文件对象在正常运行时可能已经被管理器关闭
        需要在对原对象进行操作前，必须判断该文件对象是否已经被关闭
    '''
    def __init__(self, fobj):
        self._fileobj = fobj
        
    @property
    def closed(self):
        return self._fileobj.closed
    
    def read(self, *args, **kv):
        if self.closed: pass
        try:
            return self._fileobj.read(*args, **kv)
        except:
            self.close()
        
    def write(self, *args, **kv):
        if self.closed: pass
        try:
            return self._fileobj.write(*args, **kv)
        except:
            self.close()
        
    def flush(self, *args, **kv):
        if self.closed: pass
        try:
            return self._fileobj.flush(*args, **kv)
        except:
            self.close()
        
    def close(self, *args, **kv):
        if self.closed: pass
        try:
            return self._fileobj.close(*args, **kv)
        except:
            pass
        

@_gc_socket
def do_upload(socket, remote_address):
    # print remote_address
    socket._start_time = time.time() # 赋值开始时间
    socket._status = SOCKET_STATUS_WAITING # 标记链接状态
    
    error_code = ''
    fileobj = FileObjWrapper(socket.makefile())
    # 读取上传请求
    try:
        request_head = fileobj.read(26)
        # print 'request head', repr(request_head)
        packet_length = hex2int(request_head[:4]) # 第一次参数接受、解析出错，就不理会
    except:
        try:
            fileobj.write(int2hex(RESULT_INVALID_ARGS, int_len=2))
            fileobj.close()
        except:
            pass
        return
    
    socket._status = SOCKET_STATUS_WORKING # 标记链接状态
    
    app_id = hex2int(request_head[4:6], int_len=2)
    file_size = hex2int(request_head[6:10])
    file_hash = request_head[10:26]
    
    try:
        handler = get_app_handler(app_id, file_size, file_hash)
    except FileSizeError:
        fileobj.write(int2hex(RESULT_FILE_TOO_LARGE, int_len=2))
        fileobj.close()
        return
    except Exception:
        log.error(traceback.format_exc())
        fileobj.write(int2hex(RESULT_FS_ERROR, int_len=2))
        fileobj.close()
        return
        
    if not handler: # 找不到授权应用
        fileobj.write(int2hex(RESULT_INVALID_ARGS, int_len=2))
        fileobj.close()
        return
    
    socket.timeout = handler.CONNECTION_TIMEOUT # 设置线程总超时时长，秒
    
    # 读取请求TLV参数
    tlv = fileobj.read(packet_length - 26)
    try:
        handler.handle_request(tlv)
    except InvalidArgsError:
        error_code = RESULT_INVALID_ARGS
    except AuthenticateError:
        error_code = RESULT_AUTH_FAIL
    except FileTypeError:
        error_code = RESULT_WRONG_FILE_TYPE
    except FileExistError, e:
        fileobj.write(int2hex(RESULT_FILE_EXIST, int_len=2))
        fileobj.write(int2hex(4 + len(e.message))) # 4个字节是这个长度值本身长度
        fileobj.write(e.message)
        fileobj.close()
        return
    except Exception:
        log.error(traceback.format_exc())
        error_code = RESULT_FS_ERROR
        
    if error_code:
        fileobj.write(int2hex(error_code, int_len=2))
        fileobj.close()
        return

    # 返回允许上传标志
    fileobj.write(int2hex(RESULT_ALLOW_UPLOAD, int_len=2))
    fileobj.flush()
    # print 'write request result', RESULT_ALLOW_UPLOAD

    # 读取文件内容
    content = fileobj.read(file_size)
    if len(content) > handler.FILE_MAX_SIZE:
        error_code = RESULT_FILE_TOO_LARGE
    try:
        # 执行文件处理程序
        result_tlv = handler.handle_upload(content)
    except FileHashError:
        error_code = RESULT_HASH_ERROR
    except Exception:
        log.error(traceback.format_exc())
        error_code = RESULT_FS_ERROR
    if error_code:
        fileobj.write(int2hex(error_code, int_len=2))
        fileobj.close()
        return
    result = ''
    result += int2hex(4 + 2 + len(result_tlv))
    result += int2hex(RESULT_UPLOAD_SUCCESS, int_len=2)
    result += result_tlv

    fileobj.write(result)
    fileobj.flush()
    fileobj.close()

s = server.StreamServer((settings.SERVER_IP, settings.SERVER_PORT), do_upload, backlog=settings.SERVER_BACKLOG)
# s.init_socket() # gevent 1.x
s.pre_start() # gevent 0.13

def serve_forever(server_):
    note('starting server')
    _smng = SocketManager()
    _smng.setDaemon(True)
    _smng.start()
    try:
        server_.start_accepting()
        
        # server_._stop_event.wait() # gevent 1.x
        server_._stopped_event.wait() # gevent 0.13
    except KeyboardInterrupt:
        server_.stop()

note('starting %s server processes' % settings.NUM_PROCESS)
for i in range(settings.NUM_PROCESS):
    Process(target=serve_forever, args=(s,)).start()

s.serve_forever()

    