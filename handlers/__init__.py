# coding=utf8

from FileUpload.handlers.img_uploader import ImageHandler
from FileUpload.handlers.file_system import LocalFileSystem, TFS
from FileUpload.configs import settings

def get_upload_img_to_local_fs_handler(file_size, file_hash):
    return ImageHandler(LocalFileSystem(settings.LOCAL_UPLOAD_FILE_PATH), file_size, file_hash)

def get_upload_img_to_tfs_0_handler(file_size, file_hash):
    return ImageHandler(TFS(settings.TFS_SERVER_IP_0, settings.TFS_SERVER_PORT_0, settings.TFS_APP_ID_0, settings.TFS_APP_KEY_0),
                        file_size, file_hash
                        )

handler_map = {'1': get_upload_img_to_local_fs_handler,
               # '2': get_upload_img_to_tfs_0_handler
              } 

def get_app_handler(app_id, file_size, file_hash):
    hd = handler_map.get(str(app_id))
    if hd:
        return hd(file_size, file_hash)

