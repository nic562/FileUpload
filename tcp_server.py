# -*- coding: utf-8 -*-

import sys, traceback, logging

from gevent import server, monkey
from multiprocessing import Process, current_process

from FileUpload.handlers import get_app_handler
from FileUpload.utils import int2hex, hex2int
from FileUpload.const import (RESULT_INVALID_ARGS, FileSizeError, RESULT_FILE_TOO_LARGE, InvalidArgsError,
                              AuthenticateError, RESULT_AUTH_FAIL, FileTypeError, RESULT_WRONG_FILE_TYPE, FileExistError,
                              RESULT_FILE_EXIST, RESULT_ALLOW_UPLOAD, FileHashError, RESULT_HASH_ERROR, FilesystemError,
                              RESULT_FS_ERROR, RESULT_UPLOAD_SUCCESS)
from FileUpload.configs import settings

log = logging

monkey.patch_os()

def note(formatter, *args):
    sys.stderr.write('[%s]\t%s\n' % ( current_process().name, formatter%args))

def do_upload(socket, address):
    error_code = ''
    fileobj = socket.makefile()
    
    # 读取上传请求
    request_head = fileobj.read(26)
    # print 'request head', repr(request_head)
    try:
        packet_length = hex2int(request_head[:4]) # 第一次参数接受、解析出错，就不理会
    except:
        fileobj.write(int2hex(RESULT_INVALID_ARGS, int_len=2))
        fileobj.close()
        return
        
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
    try:
        server_.start_accepting()
        
        # server_._stop_event.wait() # gevent 1.x
        server_._stopped_event.wait() # gevent 0.13
    except KeyboardInterrupt:
        pass

print 'starting %s processes' % settings.NUM_PROCESS
for i in range(settings.NUM_PROCESS):
    Process(target=serve_forever, args=(s,)).start()

s.serve_forever()

