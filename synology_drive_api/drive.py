from typing import Optional, Union

from synology_drive_api.base import SynologySession
from synology_drive_api.files import FilesMixin
from synology_drive_api.labels import LabelsMixin
from synology_drive_api.tasks import TasksMixin


class SynologyDrive(LabelsMixin, FilesMixin, TasksMixin):
    # synology login session
    session: SynologySession
    # if you need multiple login session and label functions, disable label cache. Default behavior is enabling cache.
    enable_label_cache: bool

    def __init__(self,
                 username: str,
                 password: str,
                 ip_address: Optional[str] = None,
                 port: Union[None, str, int] = None,
                 nas_domain: Optional[str] = None,
                 https: bool = True,
                 enable_label_cache: bool = True,
                 dsm_version: str = '6',
                 max_retry: int = 2,
                 otp_code: Optional[str] = None) -> None:
        self.session = SynologySession(username, password, ip_address, port, nas_domain, https, dsm_version, max_retry,
                                       otp_code)
        self.enable_label_cache = enable_label_cache

    def __enter__(self):
        self.login()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logout()

    def login(self):
        return self.session.login('SynologyDrive')

    def logout(self):
        return self.session.logout('SynologyDrive')

    def get_info(self):
        api_name = 'SYNO.SynologyDrive.Info'
        info = self.session.get_api_list(api_name)
        endpoint = info['path']
        params = {'api': api_name, 'version': info['maxVersion'], 'method': 'get', '_sid': self.session.sid}
        return self.session.http_get(endpoint, params=params)
