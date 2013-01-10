#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
tfs proxy client module

check, upload and delete file

"""

import hashlib
import socket
import struct

# protocol define

PROXY_MAGIC = 0xA1B2

CMD_FILE_CHECK_REQ  = 0x0010
CMD_FILE_UPLOAD_REQ = 0x0011
CMD_FILE_DEL_REQ    = 0x0012

TAG_APPID    = 1
TAG_FILENAME = 2
TAG_CONTENT  = 3
TAG_CHKSUM   = 4

MAX_CMD_SEQ = (1 << 16) - 1
MAX_FILE_LENGTH = (1 << 32) - 1

TLV_HEADER_FMT = '!HI'
TLV_HEADER_SIZE = struct.calcsize(TLV_HEADER_FMT)

MSG_HEADER_FMT = '!HIHHH'
MSG_HEADER_SIZE = struct.calcsize(MSG_HEADER_FMT)

CHKSUM_SIZE =  TLV_HEADER_SIZE + hashlib.md5().digestsize  # tlv_header + 16 bytes md5


def _cmd_seq():
    """ for cmd seq """
    for i in xrange(MAX_CMD_SEQ):
        yield i

class error(Exception):
    pass

class TFS(object):
    """ tfs proxy client module """

    def __init__(self, host, port, app_id, app_key, timeout=45):
        self.host = host
        self.port = port

        self.app_id = app_id
        self.app_key = app_key

        self.cmd_seq = _cmd_seq()

        self.conn = socket.socket()
        self.conn.settimeout(timeout)
        self.conn.connect((self.host, self.port))

        self.rfile = self.conn.makefile('r')
        self.wfile = self.conn.makefile('w')

        self.md5 = hashlib.md5(self.app_key)


    def _reset_chksum(self):
        self.md5 = hashlib.md5(self.app_key)


    def _write_chksum(self):
        self._write(struct.pack(TLV_HEADER_FMT, TAG_CHKSUM, self.md5.digestsize))
        self._write(self.md5.digest())


    def _write_tlv_header(self, tag, length):
        self._write(struct.pack(TLV_HEADER_FMT, tag, length), chksum=True)


    def _read_tlv_header(self):
        tag, length = struct.unpack(TLV_HEADER_FMT, self._read(TLV_HEADER_SIZE))
        return tag, length


    def _write_req_header(self, cmd_id, body_length):
        buf = struct.pack(MSG_HEADER_FMT, PROXY_MAGIC, body_length, cmd_id, self.cmd_seq.next(), self.app_id)
        self._write(buf)

        self._reset_chksum()


    def _read_rsp_header(self):
        _, body_len, cmd_id, cmd_seq, rsp_code, = struct.unpack(MSG_HEADER_FMT, self._read(MSG_HEADER_SIZE))
        return cmd_id, rsp_code, body_len


    def _write(self, buf, chksum = False):
        if chksum and self.md5:
            self.md5.update(buf)
        self.conn.sendall(buf)

    def _read(self, length):
        try:
            buf = self.rfile.read(length)

            if len(buf) != length:
                raise error("unexpected length", len(buf), length)
            return buf
        except socket.error, e:
            raise error(*e.args)



    def check_file(self, file_name):
        """ check file exists """

        body_length = TLV_HEADER_SIZE + len(file_name) + CHKSUM_SIZE
        self._write_req_header(CMD_FILE_CHECK_REQ, body_length)

        self._write_tlv_header(TAG_FILENAME, len(file_name))
        self.write_chunk(file_name)

        self._write_chksum()

        cmd_id, rsp_code, body_length = self._read_rsp_header()

        if cmd_id != CMD_FILE_CHECK_REQ:
            raise error("unexpected command", cmd_id, CMD_FILE_CHECK_REQ)

        if rsp_code not in (0, 1):
            raise error("unexpected response", rsp_code)

        return True if rsp_code == 1 else False


    def start_upload(self, origin_name, file_length):
        """
            request to start a file upload progress
            you need call write_chunk to write the real data
            and call finish_upload to finish upload

        """

        if file_length > MAX_FILE_LENGTH:
            raise error('max file length', file_length, MAX_FILE_LENGTH)

        body_length = TLV_HEADER_SIZE * 2 + len(origin_name) + file_length + CHKSUM_SIZE
        self._write_req_header(CMD_FILE_UPLOAD_REQ, body_length)

        self._write_tlv_header(TAG_FILENAME, len(origin_name))
        self.write_chunk(origin_name)

        self._write_tlv_header(TAG_CONTENT, file_length)


    def write_chunk(self, chunk):
        """ write chunk to network """
        self._write(chunk, chksum=True)


    def finish_upload(self):
        """ finish upload progress to get rsp code and file name """

        self._write_chksum()

        cmd_id, rsp_code, body_length = self._read_rsp_header()

        if cmd_id != CMD_FILE_UPLOAD_REQ:
            raise error("unexpected command", cmd_id, CMD_FILE_UPLOAD_REQ)

        if rsp_code:
            raise error("unexpected response", rsp_code)


        tag, length = self._read_tlv_header()

        if tag != TAG_FILENAME:
            raise error("unexpected tag", tag, TAG_FILENAME)

        return self.rfile.read(length)

    def put(self, origin_name, origin_content):
        self.start_upload(origin_name, len(origin_content))

        for i in xrange(0, len(origin_content), 8192):
            self.write_chunk(origin_content[i:i+8192])

        tfs_name = self.finish_upload()
        return tfs_name


    def delete_file(self, file_name):
        """ delete from tfs """

        body_length = TLV_HEADER_SIZE + len(file_name) + CHKSUM_SIZE
        self._write_req_header(CMD_FILE_DEL_REQ, body_length)

        self._write_tlv_header(TAG_FILENAME, len(file_name))
        self.write_chunk(file_name)

        self._write_chksum()

        cmd_id, rsp_code, body_length = self._read_rsp_header()

        if cmd_id != CMD_FILE_DEL_REQ:
            raise error("unexpected command", cmd_id, CMD_FILE_DEL_REQ)

        if rsp_code:
            raise error("unexpected response", rsp_code)


    def get_file_path(self, file_name):
        return '/tfs/%s?appid=%d' % (file_name, self.app_id)

