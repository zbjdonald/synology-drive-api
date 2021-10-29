from synology_drive_api.utils import form_urlencoded


class TasksMixin:
    """
    tasks related function
    """

    def get_task_status(self, task_id: str):
        """
        :param task_id:
        get task status
        :return:
        """
        api_name = 'SYNO.Entry.Request'
        endpoint = 'entry.cgi'
        data = {
            'stop_when_error': False,
            'mode': 'parallel',
            'api': api_name,
            'compound': [{"api": "SYNO.SynologyDrive.Tasks", "method": "get", "version": 1, "task_id": task_id}],
            'method': 'request',
            'version': 1
        }
        urlencoded_data = form_urlencoded(data)
        resp = self.session.http_post(endpoint, data=urlencoded_data)
        return resp
