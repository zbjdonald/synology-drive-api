import functools
from http import cookiejar
from time import sleep
from urllib.parse import urlparse

import requests
import simplejson as json
import urllib3
from typing import Optional, Union

# Used for verify=False in requests
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class BlockAll(cookiejar.CookiePolicy):
    """
    drop cookies from session object
    """
    return_ok = set_ok = domain_return_ok = path_return_ok = lambda self, *args, **kwargs: False
    netscape = True
    rfc2965 = hide_cookie2 = False


class SynologyException(requests.RequestException):

    def __init__(self, code=-1, message=None, *args, **kwargs):
        super(SynologyException, self).__init__(*args, **kwargs)
        self.code = code
        self.message = message

    def __str__(self):
        return self.response.text

    __repr__ = __str__


class SynologyOfficeFileConvertFailed(Exception):
    pass


def concat_nas_address(ip_address: Optional[str] = None,
                       port: Union[None, str, int] = None,
                       drive_prefix: Optional[str] = None,
                       https: bool = True) -> str:
    """
    :param ip_address: such as 192.168.1.51
    :param port: port number
    :param drive_prefix: such as drive.xxxx.com, hehe.com/drive
    :param https:
    :return:
    """
    scheme = 'https://' if https else 'http://'
    if port is None:
        # https default port 5001, http default port 5000
        port = '5001' if https else '5000'
    else:
        # int => str
        port = str(port)

    if ip_address is None:
        assert isinstance(drive_prefix, str)
        nas_address = ':'.join(filter(None, [drive_prefix]))
    else:
        assert drive_prefix is None
        nas_address = ':'.join(filter(None, [ip_address, port]))

    return f"{scheme}{nas_address}"


def add_sid_token(reqs_data: dict, sid: str) -> dict:
    """
    add sid token in requests params
    :param reqs_data: requests kwargs
    :param sid: sid token
    :return:
    """
    if 'params' not in reqs_data:
        reqs_data['params'] = {}

    # api params may in forms sometimes
    if 'api' not in reqs_data['params'] and 'api=' not in reqs_data.get('data', ''):
        return reqs_data

    # login logout don't need sid
    if reqs_data['params'].get('api') != 'SYNO.API.Auth':
        reqs_data['params']['_sid'] = sid
    return reqs_data


def raise_synology_exception(resp, bio_exist: bool = False) -> None:
    """
    :param resp:
    :param bio_exist: indicate response contains binary object
    :return:
    """
    # handle 404, 400, ..., and synology server error code
    try:
        resp.raise_for_status()
    except requests.RequestException as reqe:
        code = -1
        message = None
        if reqe.response.text:
            try:
                err_info = json.loads(reqe.response.text)
                code = err_info['code']
                message = err_info['message']
            except (ValueError, KeyError):
                pass
        raise SynologyException(
            code=code,
            message=message,
            request=reqe.request,
            response=reqe.response
        )

    if resp.status_code == 200 and not bio_exist:
        result = resp.json() if resp.text else {}
        if not result['success']:
            raise SynologyException(
                code=result['error']['code'],
                # sometimes there is no 'errors' key
                message=result['error'].get('errors') if result['error'].get('errors') else result['error'],
                request=resp.request,
                response=resp
            )


class SynologySession:
    """
    Synology App base class
    """
    _username: str
    _password: str
    _otp_code: str
    # api base url
    _base_url: str
    # sid token
    _sid: Optional[str] = None
    req_session: requests.Session = requests.Session()
    _session_expire: bool = True
    # dsm version, used for login api version
    dsm_version: str = '6'
    max_retry: int = 2

    def __init__(self,
                 username: str,
                 password: str,
                 ip_address: Optional[str] = None,
                 port: Optional[int] = None,
                 nas_domain: Optional[str] = None,
                 https: Optional[bool] = True,
                 dsm_version: str = '6',
                 max_retry: int = 2,
                 otp_code: Optional[str] = None) -> None:
        assert dsm_version in ('6', '7'), "dsm_version should be either '6' or '7'."

        nas_address = concat_nas_address(ip_address, port, nas_domain, https)
        self._username = username
        self._password = password
        self._otp_code = otp_code
        self.dsm_version = dsm_version
        self._base_url = f"{nas_address}/webapi/"
        self.req_session.cookies.set_policy(BlockAll())
        self.max_retries = max_retry

    def _request(self, method: str, endpoint: str, **kwargs):
        """
        :param method: get, post, put, delete
        :param endpoint: api endpoint
        :param kwargs:
        :return:
        """
        if not endpoint.startswith(('http://', 'https://')):
            api_base_url = kwargs.pop('api_base_url', self._base_url)
            url = f"{api_base_url}{endpoint}"
        else:
            url = endpoint

        kwargs = add_sid_token(kwargs, self._sid)

        if isinstance(kwargs.get('data', ''), dict):
            body = json.dumps(
                kwargs['data'],
                ensure_ascii=False,
            )
            body = body.encode('utf-8')
            kwargs['data'] = body
        elif isinstance(kwargs.get('data'), str):
            kwargs['data'] = kwargs['data'].encode('utf-8')

        parsed_url = urlparse(url)
        # Allow url pattern: https://192.168.1.58:133/webapi
        if parsed_url.scheme == 'https' and parsed_url.netloc.count('.') >= 3:
            # if scheme is https:// and url contains ip,
            # return true indicate adding verify=False to requests.
            kwargs['verify'] = False
        bio_flag = kwargs.pop('bio') if 'bio' in kwargs else None
        if not self.max_retries:
            res = self.req_session.request(
                method=method,
                url=url,
                **kwargs
            )
            raise_synology_exception(res, bio_exist=bio_flag)
        else:
            for retry in range(self.max_retries):
                try:
                    res = self.req_session.request(
                        method=method,
                        url=url,
                        **kwargs
                    )
                    raise_synology_exception(res, bio_exist=bio_flag)
                    break
                except SynologyException as e:
                    # retry
                    # 105: permission denied by anonymous
                    # 1003 1002: get file information failed
                    if e.code in (105, 1003, 1002):
                        sleep(0.5 * (retry + 1))
                        if retry == self.max_retries - 1:
                            raise e
                        else:
                            continue
                    else:
                        raise e
        if bio_flag:
            return res.content
        result = res.json() if res.text else {}
        return result

    def http_get(self, endpoint: str, **kwargs):
        return self._request('get', endpoint, **kwargs)

    def http_post(self, endpoint: str, **kwargs):
        return self._request('post', endpoint, **kwargs)

    def http_put(self, endpoint: str, **kwargs):
        return self._request('put', endpoint, **kwargs)

    def http_delete(self, endpoint: str, **kwargs):
        return self._request('delete', endpoint, **kwargs)

    def login(self, application: str):
        endpoint = 'auth.cgi'
        login_api_version = '2' if self.dsm_version == '6' else '3'
        params = {'api': 'SYNO.API.Auth', 'version': login_api_version, 'method': 'login', 'account': self._username,
                  'passwd': self._password, 'session': application, 'format': 'cookie'}
        if self._otp_code is not None:
            params['otp_code'] = self._otp_code

        if not self._session_expire:
            if self._sid is not None:
                self._session_expire = False
                return 'User already logged'
        else:
            resp = self.http_get(
                endpoint,
                params=params
            )
            self._sid = resp['data']['sid']
            self._session_expire = False
            return 'User logging... New session started!'

    def logout(self, application: str):
        endpoint = 'auth.cgi'
        logout_api_version = '2' if self.dsm_version == '6' else '3'
        params = {'api': 'SYNO.API.Auth', 'version': logout_api_version, 'method': 'logout', 'session': application}
        resp = self.http_get(
            endpoint,
            params=params
        )
        if resp['success'] is True:
            self._session_expire = True
            self._sid = None
            return 'Logged out'
        else:
            self._session_expire = True
            self._sid = None
            return 'No valid session is open'

    @functools.lru_cache()
    def get_api_list(self, app=None):
        endpoint = 'query.cgi'
        params = {'api': 'SYNO.API.Info', 'version': '1', 'method': 'query', 'query': 'all'}
        resp = self.http_get(
            endpoint,
            params=params
        )
        if app is not None:
            for key in resp['data']:
                if app.lower() in key.lower():
                    return resp['data'][key]
        else:
            return resp['data']

    @property
    def sid(self):
        return self._sid
