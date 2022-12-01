# Synology Drive API
[![Downloads](https://static.pepy.tech/personalized-badge/synology-drive-api?period=total&units=international_system&left_color=grey&right_color=red&left_text=Downloads)](https://pepy.tech/project/synology-drive-api)
![Python](https://img.shields.io/badge/python-v3.7+-blue.svg)
[![License](https://img.shields.io/badge/license-MIT-gree.svg)](https://opensource.org/licenses/MIT)
![Contributions welcome](https://img.shields.io/badge/contributions-welcome-orange.svg)

`synology-drive-api` is inspired by  [synology-api](https://github.com/N4S4/synology-api). 
This repo is aimed at providing **Synology drive** api wrapper and related helper functions. It helps you manage your files/folders/labels in synology drive.  By means of Synology Office, you can edit spreadsheet on Drive and use this api wrapper read spreadsheet. It supports Python 3.7+.

## Installation
```bash
pip install synology-drive-api
```

## Get login session

You can access drive by IP, drive domain or nas domain + drive path. 

> Synology Drive allows same user with multiple login session. if you need multiple login session and label functions, disable label cache.

```python
from synology_drive_api.drive import SynologyDrive

# default http port is 5000, https is 5001. 
with SynologyDrive(NAS_USER, NAS_PASS, NAS_IP) as synd:
    pass 
# Use specified port
with SynologyDrive(NAS_USER, NAS_PASS, NAS_IP, NAS_PORT) as synd:
    pass
# use http instead of https. https: default is True.
with SynologyDrive(NAS_USER, NAS_PASS, NAS_IP, https=False) as synd:
    pass
# Enable 2fa.
with SynologyDrive(NAS_USER, NAS_PASS, otp_code='XXXXXX') as synd:
    pass
# use domain name or name + path access drive
# Enabled in Application Portal | Application | Drive | General | Enable customized alias
drive_path_demo = 'your_nas_domain/drive'
# Enabled in Application Portal | Application | Drive | General | Enable customized domain
drive_path_demo2 = 'your_drive_domain'
with SynologyDrive(NAS_USER, NAS_PASS, drive_path_demo) as synd:
    pass
# disable label cache
with SynologyDrive(NAS_USER, NAS_PASS, drive_path_demo, enable_label_cache=False) as synd:
    pass
```
If you use dsm 7, default dsm_version is '6'.  
```python
from synology_drive_api.drive import SynologyDrive

# default http port is 5000, https is 5001. 
with SynologyDrive(NAS_USER, NAS_PASS, NAS_IP, dsm_version='7') as synd:
   pass
```
## Manage labels

Synology drive thinks labels need to belong to single user. **If you want share labels between users, you should have access to these user accounts.** Another solution is creating a *tool user*.

Synology drive search function provide label union search rather than intersection search. **If you need label intersection search, combine them into one label.**

### Get label info

```python
# get single label info
synd.get_labels('your_label_name')
# get all labels info
synd.get_labels()
```

### Create/delete label

Label name is unique in drive.

```python
# create a label, color name: gray/red/orange/yellow/green/blue/purple.
# default color is gray, default position is end of labels. 0 is first position.
ret = synd.create_label('your_label_name', color='orange', pos=0)
# delete label by name/id.
ret = synd.delete_label('your_label_name')
ret = synd.delete_label(label_id=419)
```

### Add/delete path label

```python
# acition：add, delete
synd.manage_path_label(action, path, label)
```

path examples:

```python
1. '/team-folders/test_drive/SCU285/test.xls', '/mydrive/test_sheet_file.osheet'
2. '505415003021516807'
3. ['505415003021516807', '505415003021516817']
4. ["id:505415003021516807", "id:525657984139799470", "id:525657984810888112"]
5. ['/team-folders/test_drive/SCU285/test.xls', '/team-folders/test_drive/SCU283/test2.xls']
```

label examples:

```python
1. 'label_name'
2. ['label_name_1', 'lable_name_2']
3. [{"action": "add", "label_id": "15"}, {"action": "add", "label_id": "16"}]
```

### List labelled files

Filter files or folders by single label. If you want to use label union search, use search functions (todo).

```python
synd.list_labelled_file(label_name='your_label_name')
```

## Manage File/Folder

>Team folder start with `/team-folders/`, Private folder start with `/mydrive/`

### List TeamFolder

Teamfolder  is virtual parent folder of shared folders in Synology drive. When you login in Drive, you can see your authorized shared folder.

```python
synd.get_teamfolder_info()
# {sub_folder_name: folder_id, ...}
```

### List Folder

List Folder or files info of a folder

```python
synd.list_folder('/mydrive')
```

### Get specific folder or file info

Get folder or file info such as created time.

```python
# file_path or file_id "552146100935505098"
synd.get_file_or_folder_info(path_or_path_id)
```

### Create Folder

```python
# create folder in your private folder
synd.create_folder(folder_name)
# create folder in dest folder
synd.create_folder('test', 'team-folder/folder2/')
```

### Upload file

You don't need create folder subfolder before uploading your file.

```python
# prepare your file
file = io.BytesIO(mail_attachment['file'])
# add a file name to file
file.name = strip_file_name(mail_attachment['name'])
ret_upload = nas_client.upload_file(file, dest_folder_path=dest_folder_path)
# upload to your private folder
ret_upload = nas_client.upload_file(file)
```

You can upload xlsx or docx as synology office file.
``` python
with open('test.xlsx', 'rb') as file:
    nas_client.upload_as_synology_office_file(file, '/mydrive/')
```

### Download file
New: Support osheet and odoc extensions.
```python
file_name = 'test.osheet'
bio = synd.download_file(f'/mydrive/{file_name}')
with open(file_name, 'wb') as f:
    f.write(bio)
```

### Download Synology office file

```python
import pandas as pd

# download osheet as xlsx and read into pandas dataframe.
bio = synd.download_synology_office_file('/mydrive/test.osheet')
pd.read_excel(bio, sheet_name=None)

# dowloand odoc as docx
bio = synd.download_synology_office_file('/mydrive/test.odoc')
with open('test.docx', 'wb') as f:
    f.write(bio)
```

### Delete file or folder

Delete file or folder is  an async task.

```python
synd.delete_path('/mydrive/abc_folder')
synd.delete_path('598184594644187768')
```

### Rename file or folder

```python
# Rename file '/mydrive/H3_AP201812091265503218_1.pdf' to '/mydrive/new.pdf'
synd.rename_path('new.pdf', '/mydrive/H3_AP201812091265503218_1.pdf')
# Rename folder '/mydrive/test_folder' to '/mydrive/abc_folder'
synd.rename_path('abc_folder', '/mydrive/test_folder')
```
