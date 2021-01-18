from typing import Optional, List, Union

from optionaldict import OptionalDict

from synology_drive_api.utils import form_urlencoded


def color_name_to_id(color_name: str) -> str:
    """
    map color_name to hex color
    :param color_name:
    :return:
    """
    color_id = {
        'gray': '#A0A5AA',
        'red': '#FA8282',
        'orange': '#FA9C3E',
        'yellow': '#F2CA00',
        'green': '#94BF13',
        'blue': '#499DF2',
        'purple': '#A18AE6',
    }
    try:
        return color_id[color_name.lower()]
    except KeyError:
        raise KeyError('Color name error! Use gray/red/orange/yellow/green/blue/purple')


class LabelsMixin:
    """
    Drive labels related function
    """
    # label dict cache
    _label_dict: dict = dict()

    def get_labels(self, name: Optional[str] = None) -> dict:
        """
        Get label name and label id. If name is None, return all labels.
        :param name: label name
        :return: {name: label_id, ...}
        """
        api_name = 'SYNO.SynologyDrive.Labels'
        endpoint = 'entry.cgi'
        params = {'api': api_name, 'version': 1, 'method': 'list'}
        req = self.session.http_get(endpoint, params=params)
        label_items = req['data']['items']

        if not label_items:
            return dict()

        label_dict = {item['name']: item['label_id'] for item in label_items}
        if name is None:
            return label_dict
        else:
            try:
                return {name: label_dict[name]}
            except KeyError:
                raise Exception(f'Label <{name}> does not exist.')

    def create_label(self, name: str, color: str = 'gray', pos: Union[None, str, int] = None) -> dict:
        """
        :param name: label name
        :param color: color name gray/red/orange/yellow/green/blue/purple
        :param pos: label position
        :return:
        """
        color = color_name_to_id(color_name=color)
        if name in self.label_dict:
            raise Exception('Label_name already exists, please use another one!')
        api_name = 'SYNO.SynologyDrive.Labels'
        endpoint = 'entry.cgi'
        params = OptionalDict(api=api_name, version=1, method='create', name=name, color=color, position=pos)
        ret_label = self.session.http_put(endpoint, params=params)
        self.set_label_dict(name, ret_label['data']['label_id'])
        return ret_label

    def delete_label(self, label_name: Optional[str] = None, label_id: Union[None, str, int] = None) -> dict:
        """
        delete label by name or label_id
        :param label_name: label name
        :param label_id: label id
        :return:
        """
        params_count = [label_name, label_id].count(None)
        if params_count != 1:
            raise Exception('Wrong params number. Enter label name or label_id')

        if label_id is None:
            try:
                label_id = self.label_dict[label_name]
            except KeyError:
                raise Exception(f'Label <{label_name}> does not exists!')

        api_name = 'SYNO.SynologyDrive.Labels'
        endpoint = 'entry.cgi'
        params = {'api': api_name, 'version': 1, 'method': 'delete', 'label_id': label_id}
        return self.session.http_delete(endpoint, params=params)

    def manage_path_label(self, action: str, path: Union[str, List[str]],
                          label: Union[str, List[str], List[dict]]) -> dict:
        """
        add label/labels to file/files or folder/folders
        :param action: 'add', 'delete'
        :param path: file/files, folder/folders
        1. '/team-folders/test_drive/SCU285/test.xls', '/mydrive/test_sheet_file.osheet'
        2. '505415003021516807'
        3. ['505415003021516807', '505415003021516817']
        4. ["id:505415003021516807", "id:525657984139799470", "id:525657984810888112"]
        5. ['/team-folders/test_drive/SCU285/test.xls', '/team-folders/test_drive/SCU283/test2.xls']
        :param label: label/lables
        1. label_name
        2. ['label_name_1', 'lable_name_2']
        3. [{"action": "add", "label_id": "15"}, {"action": "add", "label_id": "16"}]
        :return:
        """
        action = action.lower()
        if action not in ('add', 'delete'):
            raise Exception('Wrong action params. Use add or delete.')

        if isinstance(label, list):
            # label = ['label_name_1', 'label_name_2', 'label_name_3', ...]
            if isinstance(label[0], str):
                label = [{'action': action, 'label_id': self.label_dict.get(single_label)} for single_label in label]
            elif isinstance(label[0], dict):
                # [{"action": "add", "label_id": "15"}, {"action": "add", "label_id": "16"}]
                label = label
            else:
                raise Exception('Wrong label params.')
        elif isinstance(label, str):
            label = [{'action': action, 'label_id': self.label_dict.get(label)}]
        else:
            raise Exception('Wrong label params.')

        if isinstance(path, list):
            path = [f"id:{single_path}" if single_path.isdigit() else single_path for single_path in path]
        elif isinstance(path, str):
            if path.isdigit():
                path = [f"id:{path}"]
            else:
                path = [path]
        else:
            raise Exception('Wrong path params')

        api_name = 'SYNO.SynologyDrive.Files'
        endpoint = 'entry.cgi'
        data = {'files': path, 'labels': label, 'api': api_name, 'method': 'label', 'version': '2'}
        urlencoded_data = form_urlencoded(data)
        return self.session.http_post(endpoint, data=urlencoded_data)

    def list_labelled_files(self, label_name=None, label_id=None, limit=1500) -> dict:
        """
        list specific label files
        :param label_name: label name
        :param label_id:
        :param limit: return result count
        :return:
        """
        params_count = [label_name, label_id].count(None)
        if params_count != 1:
            raise Exception('Wrong params number. Enter label name or label_id')

        if label_id is None:
            try:
                label_id = self.label_dict[label_name]
            except KeyError:
                raise Exception(f'Label <{label_name}> does not exists!')

        api_name = 'SYNO.SynologyDrive.Files'
        endpoint = 'entry.cgi'
        data = {'api': api_name, 'version': 2, 'method': 'list_labelled', 'label_id': label_id, 'offset': 0,
                'limit': limit, 'sort_by': 'name', 'sort_direction': 'desc', 'filter': {}}
        urlencoded_data = form_urlencoded(data)
        return self.session.http_post(endpoint, data=urlencoded_data)

    def set_label_dict(self, label_name, label_id):
        self._label_dict[label_name] = label_id

    @property
    def label_dict(self):
        """
        label name id map
        :return:
        """
        # if cache is disabled, get labels from drive server.
        if not self.enable_label_cache:
            self._label_dict = self.get_labels()
            return self._label_dict

        # if cache is enabled and empty, fill up cache.
        if not self._label_dict:
            self._label_dict = self.get_labels()
        return self._label_dict
