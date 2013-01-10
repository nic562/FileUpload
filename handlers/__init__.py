# coding=utf8

from FileUpload.handlers.img_uploader import ImageHandler
from FileUpload.handlers.file_system import LocalFileSystem, TFS
from FileUpload.configs import settings

def get_local_fs():
    return LocalFileSystem(settings.LOCAL_UPLOAD_FILE_PATH)

def get_tfs_0():
    return TFS(settings.TFS_SERVER_IP_0, settings.TFS_SERVER_PORT_0, settings.TFS_APP_ID_0, settings.TFS_APP_KEY_0)

handler_map = {'1': get_local_fs,
               '2': get_tfs_0
              } 

def get_app_handler(app_id, file_size, file_hash):
    hd = handler_map.get(str(app_id))
    if hd:
        return hd(file_size, file_hash)

