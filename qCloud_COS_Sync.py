#!/usr/bin/env python3
# -*- coding: utf-8 -*-
__author__ = 'Erimus'
"""
这是一个腾讯云COS的同步工具（仅上传更新部分）。可指定更新个别目录。
同步源以本地文件为准，镜像到COS，会删除COS上多余的文件。我是用来把本地生成的静态页面同步到COS的。

【重要】使用前务必做好备份！做好备份！做好备份！这是一个美工写的工具，请谨慎使用。

准备工作，安装以下SDK。
pip install -U cos-python-sdk-v5

设定本地特定目录为root，对应bucket根目录。还可以指定仅更新某个目录。
会比较本地和COS上文件的修改时间，仅上传较新的文件。
如果某个文件，本地没有，但COS对应路径下有，会自动删COS上的文件。
会忽略部分文件，具体搜ignoreFiles部分。
"""

import os
import json
import time
import logging
from datetime import datetime
from qcloud_cos import *

logging.getLogger(__name__)  # 阻止SDK打印的log

# ==================== 默认不同步的文件/文件夹


DEFAULT_IGNORE_FILES = ['exe', 'py', 'pyc', 'psd', 'psb', 'ai', 'xlsx',
                        lambda x:x.split('/')[-1][0] == '.',  # 隐藏文件
                        ]
DEFAULT_IGNORE_FOLDERS = ['.git', '.svn', '__pycache__']


# ==================== 工具


# Draw title with Frame
def drawTitle(string):
    print('-' * 20 + f'\n>>> {string} >>>')


# Print format JSON
def formatJSON(obj, indent=4):
    return json.dumps(obj, ensure_ascii=False, indent=indent)


def formatPath(path):
    return path.replace('\\', '/').strip('/')


def ts2uft(ts):
    return datetime.utcfromtimestamp(ts).strftime('%Y-%m-%dT%H:%M:%S.000Z')


# ==================== 读取本地文件


def readLocalFiles(root, subFolder='', ignoreFiles=None, ignoreFolders=None):
    start = datetime.now()
    drawTitle('Read local files')

    ignoreFiles = [] if ignoreFiles is None else ignoreFiles
    ignoreFolders = [] if ignoreFolders is None else ignoreFolders

    localFilesDict, localEmptyFolders = {}, []
    ignoreFoldersNum = ignoreFilesNum = 0  # ignore计数
    for path, dirs, files in os.walk(os.path.join(root, subFolder)):
        # 忽略部分目录 不上传
        if isIgnoreFolder(path[len(root):], ignoreFolders):
            ignoreFoldersNum += 1
            continue

        # 忽略部分文件 不上传
        for i, fileName in enumerate(files[:]):
            if isIgnoreFile(os.path.join(path, fileName), ignoreFiles):
                ignoreFilesNum += 1
                continue

            localFile = formatPath(os.path.join(path, fileName)[len(root):])
            # print('local: %s'%localFile)
            modifyTime = int(os.stat(os.path.join(path, fileName)).st_mtime)
            modifyTime = ts2uft(modifyTime)
            # 输出结果 {'/相对地址文件名':'文件修改时间int'}
            localFilesDict[localFile] = modifyTime

        if not os.listdir(path):  # 标注空文件夹
            emptyFolder = formatPath(path[len(root):])
            # print(emptyFolder)
            localEmptyFolders.append(emptyFolder)

    # 打印详情
    print(f'Local Files: {len(localFilesDict)} / '
          f'Empty Folders: {len(localEmptyFolders)}')
    # if localEmptyFolders:
    #     print('localEmptyFolders: ' + formatJSON(localEmptyFolders))
    print(f'Ignored folders: {ignoreFoldersNum} / '
          f'Files: {ignoreFilesNum}')
    # print(f'localFilesDict: \n{formatJSON(list(localFilesDict.items())[:20])}')

    print(f'Used: {datetime.now() - start}')
    return localFilesDict, localEmptyFolders


def isIgnoreFile(file, ignoreFiles):  # 忽略文件
    file = formatPath(file)
    for ext in DEFAULT_IGNORE_FILES + ignoreFiles:
        if isinstance(ext, str) and file.lower().endswith(ext):
            return True
        if callable(ext) and ext(file):  # 传入为函数 且结果为真
            return True


def isIgnoreFolder(path, ignoreFolders):  # 忽略文件夹
    path = formatPath(path)
    for k in DEFAULT_IGNORE_FOLDERS + ignoreFolders:
        if isinstance(k, str) and k in path.split('/'):
            return True
        if callable(k) and k(path):  # 传入为函数 且结果为真
            return True


# ==================== 文件比较


def filterModifiedLocalFiles(localFilesDict, cosFilesDict):
    drawTitle('Filter modified local files')

    modifiedLocalFiles = []
    for i, file in enumerate(localFilesDict):
        cosFileModifyTime = cosFilesDict.get(file, '')  # cos上没有的文件
        if localFilesDict[file] > cosFileModifyTime:
            # print(f'{file}\n'
            #       f'LOC Modify Time: {localFilesDict[file]}\n'
            #       f'COS Modify Time: {cosFileModifyTime}')
            modifiedLocalFiles.append(file)

    if modifiedLocalFiles:
        print(f'Modified Files: {len(modifiedLocalFiles)}')
    else:
        print('All files on COS are the latest version.')

    # print(f'modifiedLocalFiles: \n{formatJSON(modifiedLocalFiles[:20])}')
    return modifiedLocalFiles


def filterExtraCosFiles(localFilesDict, cosFilesDict):
    drawTitle('Filter extra files on COS')

    extraCosFiles = []
    for file in cosFilesDict:
        if file not in localFilesDict:
            extraCosFiles.append(file)
    # print(extraCosFiles)
    if extraCosFiles:
        print(f'Extra Files: {len(extraCosFiles)}')
    else:
        print('No files need to be deleted.')

    return extraCosFiles


# ==================== COS读取操作


def readCosFiles(cos_client, bucket, subFolder=''):
    start = datetime.now()
    drawTitle('Read COS files')
    cosFilesDict, cosEmptyFolders = {}, []
    end, marker = 0, ''
    while not end:
        times = 0
        while times < 100:
            times += 1
            try:
                # 每次请求有1000限制
                res = cos_client.list_objects(
                    Bucket=bucket,
                    Prefix=subFolder,
                    Marker=marker,    # 设置请求头(下一页)
                    # Delimiter="/",  # 目录分隔符 不设置可自动获取全部文件
                    # MaxKeys=100,    # 默认单次返回1000条
                )
                break  # 访问成功则退出
            except Exception:
                print(f'ListFolderRequest Failed. [{times}]\nMarder: {marker}')
                time.sleep(3)
            if times == 100:
                print(f'===Error===: {folder} info load failed')
                res = {}

        if 'NextMarker' in res:
            marker = res['NextMarker']
        else:
            end = 1

        # print(formatJSON(res))

        # 获取文件
        for k in res.get('Contents', []):
            fn = k['Key']
            if fn.endswith('/'):  # 空文件夹
                cosEmptyFolders.append(fn)
            else:  # 文件
                mt = k['LastModified']
                if '.000Z' not in mt:
                    print('Time format changed!!!', mt)
                    raise
                cosFilesDict[fn] = mt

    print(f'COS files: {len(cosFilesDict)} / '
          f'Empty folders: {len(cosEmptyFolders)}')
    if cosEmptyFolders:
        print('---\ncosEmptyFolders: ' + formatJSON(cosEmptyFolders))
    # print(f'cosFilesDict: \n{formatJSON(list(cosFilesDict.items())[:20])}')

    print(f'Used: {datetime.now() - start}')
    # return cosFilesDict, cosEmptyFolders  # 这个版本不含空文件夹
    return cosFilesDict


# ==================== 主程序


class COS():
    def __init__(self, *,
                 appid, secret_id, secret_key, bucket_name, region_info,
                 retry_limit=10,  # 重试次数 偶尔会连接不上
                 root, ignoreFiles=None, ignoreFolders=None, maxAge=0
                 ):
        # 初始化 cos_client
        self.bucket = f'{bucket_name}-{appid}'
        while True:  # 偶尔会失联 隔一段时间自动重试
            cos_config = CosConfig(SecretId=secret_id,
                                   SecretKey=secret_key,
                                   Region=region_info)
            self.cos_client = CosS3Client(cos_config)
            try:
                self.cos_client.head_bucket(Bucket=self.bucket)
                break
            except Exception as e:
                print(repr(e),
                      '\nCheck your appid / secret_id / secret_key / bucket_name'
                      '\nRetry after 30 seconds.')
                time.sleep(30)
        # 初始化常量
        self.cfg = {
            'retry_limit': retry_limit,
            'root': root,
            'ignoreFiles': ignoreFiles,
            'ignoreFolders': ignoreFolders,
            'maxAge': maxAge,
        }

    def config(self, dicts):  # 传入字典修改配置。例{'root':'C:/test'}
        assert isinstance(dicts, dict)
        for k, v in dicts.items():
            if k in self.cfg:
                self.cfg[k] = v
            else:
                raise KeyError(f'[{k}] not in cfg:{self.cfg.keys()}')

    def upload(self, localFile, maxAge=None):
        # localFile 是相对根目录的完整路径。
        localFile = formatPath(localFile)
        maxAge = self.cfg['maxAge'] if maxAge is None else maxAge

        times = 0
        while times < self.cfg['retry_limit']:
            times += 1
            try:
                self.cos_client.put_object_from_local_file(
                    Bucket=self.bucket,
                    LocalFilePath=os.path.join(self.cfg['root'], localFile),
                    Key=localFile,
                    CacheControl=f'max-age={maxAge}' if maxAge else ''
                )
                print(f'Upload | {localFile}')
                break
            except CosServiceError as e:
                print(repr(e))
                pass
        else:
            print(f'Error: Upload failed! | {localFile}')

    def delete(self, cosFiles):
        # cosFiles应该是文件的相对于根目录的路径。
        # 如果传入单个文件，自动转化为list。
        if isinstance(cosFiles, str):
            cosFiles = [cosFiles]
        assert isinstance(cosFiles, list)
        cosFiles = [formatPath(i) for i in cosFiles]

        while cosFiles:  # 单次删除的数量有限，需要分批处理。
            once, cosFiles = cosFiles[:500], cosFiles[500:]  # 号称最高1000
            delObjects = {'Object': [{'Key': i} for i in once], 'Quiet': 'false'}
            times = 0
            while times < self.cfg['retry_limit']:
                times += 1
                try:
                    res = self.cos_client.delete_objects(Bucket=self.bucket,
                                                         Delete=delObjects)
                    if 'Error' in res:
                        print(res['Error'])
                        raise
                    print(f'Delete | {len(once)} files')
                    print(formatJSON(once))
                    break
                except Exception:
                    pass
            else:
                print(f'Error: delete failed!\n{formatJSON(once)}')

    def read(self, subFolder):
        return readCosFiles(self.cos_client, self.bucket, subFolder)

    def sync(self, subFolder='', *, maxAge=None):
        maxAge = self.cfg['maxAge'] if maxAge is None else maxAge
        _start = datetime.now()
        _folder = subFolder or self.cfg['root'].strip('/').split('/')[-1]
        print(f'\n{"="*20}\nSYNC [{_folder}] TO COS')

        subFolder = subFolder.strip('/')

        # 读取本地需要更新的目录
        localFilesDict, localEmptyFolders = readLocalFiles(
            self.cfg['root'], subFolder,
            self.cfg['ignoreFiles'], self.cfg['ignoreFolders'])

        # 读取cos上需要更新的目录
        cosFilesDict = self.read(subFolder)

        # 比较文件修改时间，筛选出需要更新的文件，并且上传。
        modifiedLocalFiles = filterModifiedLocalFiles(localFilesDict, cosFilesDict)
        if modifiedLocalFiles:
            start = datetime.now()
            drawTitle('Uploading files')
            for file in modifiedLocalFiles:
                self.upload(file, maxAge=maxAge)
            print(f'Used: {datetime.now() - start}')

        # 筛选出cos上有，但本地已经不存在的文件，删除COS上的文件。
        extraCosFiles = filterExtraCosFiles(localFilesDict, cosFilesDict)
        if extraCosFiles:
            start = datetime.now()
            drawTitle('Deleting COS files')
            self.delete(extraCosFiles)
            print(f'Used: {datetime.now() - start}')

        # 同步空文件夹（这个功能暂停）
        # 这个版本的SDK在删除文件后，会自动删除空文件夹，所以COS上不会存在空文件夹。

        print('-' * 20 + f'\nTotal used: {datetime.now() - _start}')


# ====================


if __name__ == '__main__':

    # ========== 服务器端初始化参数 ==========
    # appid/secret_id/secret_key 详见COS/密钥管理。
    # region_info 地区列表，在bucket下的域名管理/静态地址/'cos.'后面那段。
    # bucket_name 是COS端的bucket，对应本地的root。
    my_cos_config = {
        'appid': 88888888,
        'secret_id': 'your_id',
        'secret_key': 'your_key',
        'region_info': 'ap-shanghai',
        'bucket_name': 'your_bucket_name'
    }

    # ========== 本机需要同步的参数 ==========
    # root 本机根目录
    if os.name == 'nt':
        root = 'D:/OneDrive/yourRoot'  # PC
    else:
        root = '/Users/Erimus/OneDrive/yourRoot'  # MAC

    # ========== 可选的参数 ==========
    subFolder = ''  # 仅更新root下指定目录（可选）
    # subFolder = 'notebook' # 示例

    # 不需要进行上传的内容，通过以下规则忽略。(最下有详细说明)
    ignore = {
        'ignoreFiles': [],  # 忽略的文件结尾字符(扩展名)
        'ignoreFolders': []  # 需要忽略的文件夹
    }

    maxAge = 0  # header 可设置文件缓存的过期时间。upload和sync可用该参数。

    # ========== 使用示例 ==========
    my_bucket = COS(**my_cos_config, root=root, **ignore)  # 初始化
    my_bucket.sync(subFolder)  # 同步

    # 其它用法
    # my_bucket.upload(root, localFile='notebook/index.html', maxAge)  # 上传
    # my_bucket.delete(localFile='notebook/index.html')  # 删除

    # ========== 忽略规则说明 ==========
    '''
    上述两个列表，接受字符串，也可以直接传入自定义规则的 function。

    ignoreFiles 判断的对象是含完整路径的文件名，如'C:/path/file.ext'。
    传入字符串时，默认识别结尾字符串(扩展名)，符合的忽略（不同步）。
    传入函数时，以文件名为参数。返回True时，忽略该文件（不同步）。

    ignoreFolders 判断的对象是相对根目录的完整路径，如'/path'。
    传入字符串时，只要上述路径中的某一级等于该字符串，就忽略（不同步）。
    传入函数时，以上述路径为参数。返回True时，忽略该目录（不同步）。

    示例：
    def my_rule(fn):
        if os.path.getsize(fn) > 10000000:  # 忽略大文件
            return True
    ignoreFiles = ['exe', 'py', my_rule]

    另请参考顶部两组 default ignore
    '''
