import io
from pathlib import Path
from time import time, sleep
from typing import Optional, Union, BinaryIO

from synology_drive_api.base import SynologyOfficeFileConvertFailed
from synology_drive_api.utils import concat_drive_path
from synology_drive_api.utils import form_urlencoded


class FilesMixin:
    """
    file folder related function
    """

    def get_teamfolder_info(self):
        """
        get teamfolder sub_folder info
        :return: {sub_folder_name: folder_id, ...}
        """
        api_name = 'SYNO.SynologyDrive.TeamFolders'
        endpoint = 'entry.cgi'
        params = {'api': api_name, 'version': 1, 'method': 'list', 'filter': {}, 'sort_direction': 'asc',
                  'sort_by': 'owner', 'offset': 0, 'limit': 1000}
        resp = self.session.http_get(endpoint, params=params)

        if not resp['success']:
            raise Exception('Get teamfolder info failed.')

        if resp['data']['total'] == 0:
            return {}

        return {folder_info['name']: folder_info['file_id'] for folder_info in resp['data']['items']}

    def list_folder(self, dir_path: str) -> dict:
        """
        :param dir_path: '/team-folders/folder_name/folder_name1' or '430167496067125111'
        :return:
        """
        if dir_path.isdigit():
            dest_path = f"id:{dir_path}"
        else:
            # add start position /
            dest_path = f"/{dir_path}" if not dir_path.startswith('/') else dir_path

        api_name = 'SYNO.SynologyDrive.Files'
        endpoint = 'entry.cgi'
        params = {'api': api_name, 'version': 2, 'method': 'list', 'filter': {}, 'sort_direction': 'asc',
                  'sort_by': 'owner', 'offset': 0, 'limit': 1000, 'path': dest_path}
        return self.session.http_get(endpoint, params=params)

    def create_folder(self, folder_name: str, dest_folder_path: Optional[str] = None) -> dict:
        """
        Create folder in dest_folder, default location is 'mydrive'. If folder in path does not exist
        :param dest_folder_path: 'id:433415919843151874/folder1', '/mydrive/', 'mydrive/', 'team-folder/folder2/'
        :param folder_name: created folder name
        :return:
        """
        display_path = concat_drive_path(dest_folder_path, folder_name)
        api_name = 'SYNO.SynologyDrive.Files'
        endpoint = 'entry.cgi'
        params = {'path': display_path, 'version': 2, 'api': api_name,
                  'type': 'folder', 'conflict_action': 'autorename', 'method': 'create'}
        return self.session.http_put(endpoint, params=params)

    def get_file_or_folder_info(self, file_or_folder_path: str) -> dict:
        """
        :param file_or_folder_path: file_path or file_id "552146100935505098"
        :return:
        """
        if file_or_folder_path.isdigit():
            path_params = f"id:{file_or_folder_path}"
        else:
            # add start position /
            path_params = f"/{file_or_folder_path}" if not file_or_folder_path.startswith('/') else file_or_folder_path

        api_name = 'SYNO.SynologyDrive.Files'
        endpoint = 'entry.cgi'
        data = {'api': api_name, 'method': 'update', 'version': 2, 'path': path_params}
        urlencoded_data = form_urlencoded(data)
        return self.session.http_post(endpoint, data=urlencoded_data)

    def upload_file(self, file: Union[io.BytesIO, BinaryIO], dest_folder_path: Optional[str] = None) -> dict:
        """
        upload file to drive
        :param file: binary_file
        :param dest_folder_path: upload folder path
        :return:
        """
        file_name = file.name
        display_path = concat_drive_path(dest_folder_path, file_name)
        api_name = 'SYNO.SynologyDrive.Files'
        endpoint = 'entry.cgi'
        params = {'api': api_name, 'method': 'upload', 'version': 2, 'path': display_path,
                  'type': 'file', 'conflict_action': 'version'}
        files = {'file': file}
        upload_ret = self.session.http_post(endpoint, params=params, files=files)
        return upload_ret

    def download_file(self, file_path: str) -> io.BytesIO:
        """
        download file from drive
        :param file_path:
        :return:
        """
        ret = self.get_file_or_folder_info(file_path)
        file_name = ret['data']['name']
        if Path(file_name).suffix in ['.osheet', 'odoc']:
            bio_ret_with_name = self.download_synology_office_file(file_path)
        else:
            file_id = ret['data']['file_id']
            api_name = 'SYNO.SynologyDrive.Files'
            endpoint = f'entry.cgi/{file_name}'
            # \42: "
            params = {'api': api_name, 'method': 'download', 'version': 2, 'files': f"[\42id:{file_id}\42]",
                      'force_download': True, 'json_error': True, '_dc': str(time() * 1000)[:13]}
            bio_ret = self.session.http_get(endpoint, params=params, bio=True)
            bio_ret_with_name = io.BytesIO(bio_ret)
            bio_ret_with_name.name = file_name
        return bio_ret_with_name

    def convert_to_online_office(self, file_path: str, delete_original_file=True):
        """
        convert file to online synology office file
        :param file_path:
        :param delete_original_file: indicator delete original file or not
        :return:
        """
        if not file_path.isdigit() and '.' not in file_path:
            raise Exception('file_path should be id or path with file extension, extensions are xlsx, xls, docx etc.')
        ret = self.get_file_or_folder_info(file_path)
        file_name = ret['data']['name']
        file_extension = Path(file_name).suffix
        if file_extension not in ['.xlsx', '.xls', '.docx']:
            raise SynologyOfficeFileConvertFailed('file_path extension error.')
        file_id = ret['data']['file_id']
        api_name = 'SYNO.SynologyDrive.Files'
        endpoint = 'entry.cgi'
        data = {'api': api_name, 'method': 'convert_office', 'version': 2, 'conflict_action': 'autorename',
                'files': f"[\42id:{file_id}\42]"}
        urlencoded_data = form_urlencoded(data)
        ret = self.session.http_post(endpoint, data=urlencoded_data)
        # when finish converting, delete original file
        if delete_original_file:
            # wait for conversion success
            sleep(1)
            task_status = self.get_task_status(ret['data']['async_task_id'])
            if not task_status['data']['result'][0]['success']:
                sleep(1)
                second_counts = 0
                while True:
                    second_counts = second_counts + 1
                    task_status = self.get_task_status(ret['data']['async_task_id'])
                    if task_status['result'][0]['success'] or second_counts >= 15:
                        break
                if second_counts >= 15:
                    raise SynologyOfficeFileConvertFailed('convert progress timeout(>15s)')
            self.delete_path(file_id)
        return ret

    def upload_as_synology_office_file(self, file: Union[io.BytesIO, BinaryIO], dest_folder_path: Optional[str] = None):
        """
        upload file to drive, and converted to
        :param file: binary_file
        :param dest_folder_path: upload folder path
        :return:
        """
        upload_ret = self.upload_file(file, dest_folder_path)
        # if conversion is failed, delete uploaded file.
        try:
            convert_ret = self.convert_to_online_office(upload_ret['data']['file_id'])
        except SynologyOfficeFileConvertFailed as e:
            self.delete_path(upload_ret['data']['file_id'])
            raise e
        return convert_ret

    def download_synology_office_file(self, file_path: str) -> io.BytesIO:
        """
        download synology office file as excel or word
        :param file_path: file/folder or file/folder id "552146100935505098"
        :return:
        """
        if not file_path.isdigit() and '.' not in file_path:
            raise Exception('file_path should be id or path with file extension, extensions are osheet or odoc')

        ret = self.get_file_or_folder_info(file_path)
        file_name = ret['data']['name']
        export_end_point = file_name.replace('osheet', 'xlsx').replace('odoc', 'docx')
        file_id = ret['data']['file_id']

        api_name = 'SYNO.Office.Export'
        endpoint = f"entry.cgi/{export_end_point}"
        params = {'api': api_name, 'method': 'download', 'version': 1, 'path': f"id:{file_id}"}
        bio_ret = self.session.http_get(endpoint, params=params, bio=True)
        bio_ret_with_name = io.BytesIO(bio_ret)
        bio_ret_with_name.name = export_end_point
        return bio_ret_with_name

    def rename_path(self, new_name: str, dest_path: str) -> dict:
        """
        rename file or folder
        :param new_name:
        :param dest_path: file/folder or file/folder id "552146100935505098"
        :return:
        """
        if dest_path.isdigit():
            path_params = f"id:{dest_path}"
        else:
            path_params = dest_path

        api_name = 'SYNO.SynologyDrive.Files'
        endpoint = 'entry.cgi'
        data = {'api': api_name, 'method': 'update', 'version': 2, 'path': path_params, 'name': new_name}
        urlencoded_data = form_urlencoded(data)
        return self.session.http_post(endpoint, data=urlencoded_data)

    def move_path(self, ready_for_move_paths: str, dest_folder: str) -> dict:
        """
        # TODO ready_for_move_paths can be list，str.
        move file or folder to another folder
        :param ready_for_move_paths: file/folder name or file/folder id "552146100935505098"
        :param dest_folder: file/folder name or file/folder id "552146100935505098"
        :return:
        """
        if dest_folder.isdigit():
            dest_path = f"id:{dest_folder}"
        else:
            # add start position /
            dest_path = f"/{dest_folder}" if not dest_folder.startswith('/') else dest_folder

        if ready_for_move_paths.isdigit():
            ready_for_move_paths = [f"id:{ready_for_move_paths}"]
        else:
            ready_for_move_paths = f"/{ready_for_move_paths}" if not ready_for_move_paths.startswith(
                '/') else ready_for_move_paths
            ret = self.get_file_or_folder_info(ready_for_move_paths)
            ready_for_move_paths = [f"id:{ret['data']['file_id']}"]

        # ret = self.get_file_or_folder_info(dest_path)
        api_name = 'SYNO.SynologyDrive.Files'
        endpoint = 'entry.cgi'
        data = {'api': api_name,
                'method': 'move',
                'version': 2,
                'files': ready_for_move_paths,
                'to_parent_folder': dest_path,
                'conflict_action': 'autorename'}
        urlencoded_data = form_urlencoded(data)
        return self.session.http_post(endpoint, data=urlencoded_data)

    def delete_path(self, dest_path: str) -> dict:
        """
        delete file or folder, it's a async task.
        :param dest_path: file/folder or file/folder id "552146100935505098"
        :return:
        """
        ret = self.get_file_or_folder_info(dest_path)
        api_name = 'SYNO.SynologyDrive.Files'
        endpoint = 'entry.cgi'
        data = {'api': api_name, 'method': 'delete', 'version': 2, 'files': [f"id:{ret['data']['file_id']}"],
                'permanent': 'false', 'revisions': ret['data']['revisions']}
        urlencoded_data = form_urlencoded(data)
        return self.session.http_post(endpoint, data=urlencoded_data)
