# -*- coding: utf-8 -*-

REQ_TAG_SESSION_ID = 1
REQ_TAG_FILENAME = 2

RESULT_ALLOW_UPLOAD = 0
RESULT_BUSY = 1
RESULT_AUTH_FAIL = 2
RESULT_FILE_TOO_LARGE = 3
RESULT_INVALID_ARGS = 4
RESULT_WRONG_FILE_TYPE = 5
RESULT_FILE_EXIST = 6

RESULT_UPLOAD_SUCCESS = 10
RESULT_HASH_ERROR = 11
RESULT_FS_ERROR = 12

RETURN_TAG_FILENAME = 10

class FileHashError(Exception):
    pass

class InvalidArgsError(Exception):
    pass

class AuthenticateError(Exception):
    pass

class FilesystemError(Exception):
    pass

class FileTypeError(Exception):
    pass
class FileSizeError(Exception):
    pass
class FileExistError(Exception):
    pass