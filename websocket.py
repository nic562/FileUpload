# coding=utf8
'''
Created on 2013-1-23

@author: nic
'''
import time, traceback, logging

from twisted.internet import reactor
# from twisted.python import log

from autobahn.websocket import WebSocketServerFactory, \
                               WebSocketServerProtocol, \
                               listenWS
# the autobahn resource is getting from git://github.com/tavendo/AutobahnPython.git

from FileUpload.configs import settings
from FileUpload.const import (RESULT_INVALID_ARGS, FileSizeError, RESULT_FILE_TOO_LARGE, InvalidArgsError,
                              AuthenticateError, RESULT_AUTH_FAIL, FileTypeError, RESULT_WRONG_FILE_TYPE, FileExistError,
                              RESULT_FILE_EXIST, RESULT_ALLOW_UPLOAD, FileHashError, RESULT_HASH_ERROR,
                              RESULT_FS_ERROR, RESULT_UPLOAD_SUCCESS)

from FileUpload.handlers import get_app_handler
from FileUpload.utils import int2hex, hex2int

log = logging

class EchoServerProtocol(WebSocketServerProtocol):
    '测试用协议'
    
    def onConnect(self, connectionRequest):
        print 'on connect...%s %s' %(connectionRequest.host, connectionRequest.path)
        WebSocketServerProtocol.onConnect(self, connectionRequest)
    
    def onFrameBegin(self):
        print 'on frame begin...'
        WebSocketServerProtocol.onFrameBegin(self)
    
    def onFrameData(self, payload):
        print 'on frame data %s...' %payload
        WebSocketServerProtocol.onFrameData(self, payload)
    
    def onFrameEnd(self):
        print 'on frame end ...'
        WebSocketServerProtocol.onFrameEnd(self)
    
    def onOpen(self):
        print 'onOpen....'
        WebSocketServerProtocol.onOpen(self)
        
    def onServerConnectionDropTimeout(self):
        print 'ServerConnectionDropTimeout...'
        WebSocketServerProtocol.onServerConnectionDropTimeout(self)
        
    def onMessageFrameBegin(self, length, reserved):
        print 'on message frame begin...%s, %s' %(length, reserved)
        WebSocketServerProtocol.onMessageFrameBegin(self, length, reserved)
        
    def onMessageBegin(self, opcode):
        print 'on message begin'
        WebSocketServerProtocol.onMessageBegin(self, opcode)
        
    def onMessage(self, msg, binary):
        print "sending echo(%s):" %binary, msg
        self.sendMessage(msg, binary)
        
    def onMessageEnd(self):
        print 'on message end'
        WebSocketServerProtocol.onMessageEnd(self)
        
    def onClose(self, wasClean, code, reason):
        print 'close ....'
        WebSocketServerProtocol.onClose(self, wasClean, code, reason)
        
    def onCloseFrame(self, code, reasonRaw):
        print 'close frame...'
        WebSocketServerProtocol.onCloseFrame(self, code, reasonRaw)
        
    def onCloseHandshakeTimeout(self):
        print 'close HandshakeTimeout......'
        WebSocketServerProtocol.onCloseHandshakeTimeout(self)

SOCKET_STATUS_WAITING = 'waiting' # 等待状态
SOCKET_STATUS_WORKING = 'working' # 工作状态

class UploadFileProtocal(WebSocketServerProtocol):
    '上传文件协议'
    UPLOAD_PACK_HEAD_MAXSIZE = 4 + 32 + 11 + 300
    # 4位应用ID，不足4位，前面补0
    # 32位 文件md5
    # 11位文件大小，不足11位，前面补0
    # 300：tlv值最大长度，可根据业务修改
    #    当前tlv值内容：a. 2位tag值，不足2位，前面补0
    #                 b. 11位内容长度，不足11位，前面补0
    #                 c. 具体值内容
    
    def format_tlv(self, tlv):
        '适应后端上传处理器而作tlv参数格式化'
        def _f(t):
            if len(t) > 0:
                tar = int(t[:2])
                length = int(t[2: 13])
                value = t[13:13 + length]
                if settings.DEBUG: print 'tlv:', tar, length, value
                return ''.join([int2hex(tar, int_len=2), int2hex(length, int_len=2), value, _f(t[13+length :])])
            return ''
        return _f(tlv)
    
    def unformat_tlv(self, tlv):
        '把后端处理器返回的tlv转换成当前适用的格式'
        def _f(t):
            if len(t) > 0:
                tar = hex2int(t[:2], int_len=2)
                length = hex2int(t[2:4], int_len=2)
                value = t[4:4+length]
                if settings.DEBUG: print 'tlv:', tar, length, value
                return ''.join(['%02.f' %tar, '%011.f' %length, value, _f(t[4+length:])])
            return ''
        return _f(tlv)
    
    def onConnect(self, connectionRequest):
        self.start_time = time.time() # 链接开始时间
        self._on_msg_to_do_func = self._handler_head # 接收到消息后的回调函数
        self._my_status = SOCKET_STATUS_WAITING # 等待状态
        self.maxFramePayloadSize = self.UPLOAD_PACK_HEAD_MAXSIZE # 初始请求设置请求包头大小
        WebSocketServerProtocol.onConnect(self, connectionRequest)
    
    def onMessageBegin(self, opcode):
        self._my_status = SOCKET_STATUS_WORKING # 工作状态
        WebSocketServerProtocol.onMessageBegin(self, opcode)
        
    def sendMessage(self, payload, binary=False, payload_frag_size=None, sync=False):
        self._my_status = SOCKET_STATUS_WAITING # 等待状态
        WebSocketServerProtocol.sendMessage(self, payload, binary, payload_frag_size, sync)
    
    def onMessage(self, msg, binary):
        assert self._on_msg_to_do_func is not None
        self._on_msg_to_do_func(msg)
        
    def closeConnection(self, msg, binary=False):
        self.sendMessage(msg, binary=binary)
        self.dropConnection()
        
    def _handler_head(self, msg):
        if len(msg) > self.UPLOAD_PACK_HEAD_MAXSIZE:
            self.failConnection()
            return
        try:
            app_id = int(msg[:4])
            file_hash = msg[4:36]
            file_size = int(msg[36:47])
            tlv = msg[47:]
        except:
            self.closeConnection('%02.f' %RESULT_INVALID_ARGS)
            return
        if settings.DEBUG: print '''\npack head:
                                            app_id: %s
                                            file_hash: %s
                                            file_size: %s
                                            tlv: %s
                                 ''' %(app_id, file_hash, file_size, tlv)
        
        file_hash = file_hash.decode('hex') # 适应后端 转换成16位字符
        
        try:
            handler = get_app_handler(app_id, file_size, file_hash)
        except FileSizeError:
            self.closeConnection('%02.f' %RESULT_FILE_TOO_LARGE)
            return
        except Exception:
            log.error(traceback.format_exc())
            self.closeConnection('%02.f' %RESULT_FS_ERROR)
            return
        if not handler:
            self.closeConnection('%02.f' %RESULT_INVALID_ARGS)
            return
        
        try:
            tlv = self.format_tlv(tlv)
        except:
            self.closeConnection('%02.f' %RESULT_INVALID_ARGS)
            return
        
        error_code = ''
        # 读取请求TLV参数
        try:
            handler.handle_request(tlv)
            if settings.DEBUG:
                print 'file name:', handler.file_name
                print 'file type:', handler.file_type
        except InvalidArgsError:
            error_code = RESULT_INVALID_ARGS
        except AuthenticateError:
            error_code = RESULT_AUTH_FAIL
        except FileTypeError:
            error_code = RESULT_WRONG_FILE_TYPE
        except FileExistError, e:
            self.closeConnection('%02.f' %RESULT_FILE_EXIST + self.unformat_tlv(e.message))
            return
        except Exception:
            log.error(traceback.format_exc())
            error_code = RESULT_FS_ERROR
            
        if error_code:
            self.closeConnection('%02.f' %error_code)
            return
    
        # 返回允许上传标志
        self.sendMessage('%02.f' %RESULT_ALLOW_UPLOAD)
        self.maxFramePayloadSize = file_size # 设置下次接收内容的最大长度值
        self._on_msg_to_do_func = self._handler_file # 设置下次处理接收内容的函数
        self._handler = handler
        self._file_content = '' # 预置文件内容变量
    
    def _handler_file(self, msg):
        if not msg:
            return
        # print 'this msg length:', len(msg)
        self._file_content += msg
        length = len(self._file_content)
        # print 'get file size:', length
        if length > self.maxFramePayloadSize:
            self.closeConnection('%02.f' %RESULT_FILE_TOO_LARGE)
            return
        elif length == self.maxFramePayloadSize:
            error_code = None
            try:
                result_tlv = self._handler.handle_upload(self._file_content)
            except FileHashError:
                error_code = RESULT_HASH_ERROR
            except Exception:
                log.error(traceback.format_exc())
                error_code = RESULT_FS_ERROR
            if error_code:
                self.closeConnection('%02.f' %error_code)
                return
            result = '%02.f' %RESULT_UPLOAD_SUCCESS
            result += self.unformat_tlv(result_tlv)
            self.closeConnection(result)

if __name__ == '__main__':
    # log.startLogging(sys.stdout)
    '''
    factory_echo = WebSocketServerFactory("ws://localhost:9000", debug=settings.DEBUG)
    factory_echo.protocol = EchoServerProtocol # UploadFileProtocal
    listenWS(factory_echo)'''
    factory_upload = WebSocketServerFactory("ws://localhost:9001", debug=settings.DEBUG)
    factory_upload.protocol = UploadFileProtocal
    listenWS(factory_upload)
    reactor.run()
    