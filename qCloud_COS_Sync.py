#!/usr/bin/env python3
# -*- coding: utf-8 -*-
__author__ = 'Erimus'
import os
import json
import time
import logging
from datetime import datetime
from qcloud_cos import *
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
logging.getLogger(__name__)  # 阻止SDK打印的log
# ====================
DEFAULT_IGNORE_FOLDERS = ['.git', '.svn', '__pycache__']
DEFAULT_IGNORE_FILES = ['exe', 'py', 'pyc', 'psd', 'ai', 'xlsx']
# ====================


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


# ====================


def readLocalFiles(root, subFolder='', ignoreFiles=[], ignoreFolders=[]):
    start = datetime.now()
    drawTitle('Read local files')

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


def isIgnoreFolder(path, ignoreFolders=[]):  # 忽略文件夹
    path = formatPath(path)
    for k in DEFAULT_IGNORE_FOLDERS + ignoreFolders:
        if isinstance(k, str) and k in path.split('/'):
            return True
        if callable(k):
            return k(path)


def isIgnoreFile(fileName, ignoreFiles=[]):  # 忽略文件
    # file start with '.' 隐藏文件
    if fileName[0] == '.':
        return True

    for ext in DEFAULT_IGNORE_FILES + ignoreFiles:
        if isinstance(ext, str) and fileName.lower().endswith(ext):
            return True
        if callable(ext):  # function
            return ext(fileName)


# ====================


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
    return cosFilesDict, cosEmptyFolders


# ====================


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


def uploadToCos(cos_client, bucket, root, localFile, maxAge=0):
    times = 0
    while times < 10:
        times += 1
        try:
            cos_client.put_object_from_local_file(
                Bucket=bucket,
                LocalFilePath=os.path.join(root, localFile),
                Key=localFile,
                CacheControl=f'max-age={maxAge}' if maxAge else ''
            )
            print(f'Upload | {localFile}')
            break
        except CosServiceError as e:
            print(repr(e))
            pass
        if times == 10:
            print(f'Error: Upload failed! | {localFile}')


# ====================


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


def deleteCosFiles(cos_client, bucket, cosFiles):
    while cosFiles:
        once, cosFiles = cosFiles[:500], cosFiles[500:]  # 号称最高1000
        delObjects = {'Object': [{'Key': i} for i in once], 'Quiet': 'false'}
        times = 0
        while times < 10:
            times += 1
            try:
                res = cos_client.delete_objects(Bucket=bucket, Delete=delObjects)
                if 'Error' in res:
                    print(res['Error'])
                    raise
                print(f'Delete | {len(once)} files')
                print(formatJSON(once))
                break
            except Exception:
                pass
            if times == 10:
                print(f'Error: delete failed!\n{formatJSON(once)}')
                return


# ====================


def deleteCosFolder(cos_client, bucket, folder):
    try:
        cos_client.delete_object(Bucket=bucket, Key=folder)
        print(f'Delete | {folder}')
    except Exception:
        print(f'Error: deleteCosFolder | {folder}')


def createCosFolder(cos_client, bucket, folder):  # 新版本中好像无法建空文件夹
    if folder[-1] != '/':
        folder += '/'
    try:
        request = CreateFolderRequest(bucket, folder)
        create_folder_ret = cos_client.create_folder(request)
        print(f'Create | {create_folder_ret["message"]} | {folder}')
    except Exception:
        print(f'Error: createCosFolder | {folder}')


def syncEmptyFolders(cos_client, bucket,
                     localEmptyFolders, cosEmptyFolders):
    start = datetime.now()

    if localEmptyFolders + cosEmptyFolders:
        drawTitle('Sync empty folders')
    else:
        return

    createFolderNum = 0
    for folder in localEmptyFolders:
        if folder not in cosEmptyFolders:
            createCosFolder(cos_client, bucket, folder)
            createFolderNum += 1
        else:
            cosEmptyFolders.remove(folder)
    if createFolderNum:
        print('Create folder(s): %s' % (createFolderNum))

    for folder in cosEmptyFolders:
        deleteCosFolder(cos_client, bucket, folder)
    if cosEmptyFolders:
        print('Delete folder(s): %s' % len(cosEmptyFolders))

    print(f'Used: {datetime.now() - start}')


# ====================


def syncLocalToCOS(appid, secret_id, secret_key, bucket_name, region_info,
                   root, subFolder, ignoreFiles, ignoreFolders, maxAge):
    _start = datetime.now()
    print(f'Sync [{subFolder if subFolder else os.path.dirname(root)}] to COS')

    subFolder = subFolder.strip('/')
    bucket = f'{bucket_name}-{appid}'

    # check cos_client & bucket
    while True:  # 偶尔会失联 隔一段时间自动重试
        cos_config = CosConfig(SecretId=secret_id,
                               SecretKey=secret_key,
                               Region=region_info)
        cos_client = CosS3Client(cos_config)
        try:
            cos_client.head_bucket(Bucket=bucket)
            break
        except Exception as e:
            print(repr(e))
            print('Check your appid / secret_id / secret_key / bucket_name\n'
                  'Retry after 30 seconds.')
            time.sleep(30)

    # 读取本地需要更新的目录
    localFilesDict, localEmptyFolders = readLocalFiles(root, subFolder,
                                                       ignoreFiles,
                                                       ignoreFolders)

    # 读取cos上需要更新的目录
    cosFilesDict, cosEmptyFolders = readCosFiles(cos_client, bucket, subFolder)

    # 比较文件修改时间，筛选出需要更新的文件，并且上传。
    modifiedLocalFiles = filterModifiedLocalFiles(localFilesDict, cosFilesDict)
    if modifiedLocalFiles:
        start = datetime.now()
        drawTitle('Uploading files')
        for file in modifiedLocalFiles:
            uploadToCos(cos_client, bucket, root, file, maxAge=maxAge)
        print(f'Used: {datetime.now() - start}')

    # 筛选出cos上有，但本地已经不存在的文件，删除COS上的文件。
    extraCosFiles = filterExtraCosFiles(localFilesDict, cosFilesDict)
    if extraCosFiles:
        start = datetime.now()
        drawTitle('Deleting COS files')
        deleteCosFiles(cos_client, bucket, extraCosFiles)
        print(f'Used: {datetime.now() - start}')

    # 同步空文件夹（这个功能暂停）
    # 这个版本的SDK在删除文件后，会自动删除空文件夹，所以COS上不会存在空文件夹。
    # syncEmptyFolders(cos_client, bucket, localEmptyFolders, cosEmptyFolders)

    print('-' * 20 + f'\nTotal used: {datetime.now() - _start}')


# ====================


if __name__ == '__main__':
    # 初始化客户端。在【密钥管理】找到appid和配套的key，填写下面3个值。
    appid = 88888888  # your appid
    secret_id = 'your_id'
    secret_key = 'your_key'

    # 地区列表，可以看自己的bucket下的域名管理/静态地址/'cos.'后面那段。
    region_info = 'ap-shanghai'

    # 填写同步目录。
    # COS端的bucket，对应本地的root。
    bucket_name = 'your_bucket_name'  # 上述appid对应项目下的bucket name

    # 本机root根目录
    if os.name == 'nt':
        root = 'D:\\OneDrive\\yourRoot'  # PC
    else:
        root = '/Users/Erimus/OneDrive/yourRoot'  # MAC

    subFolder = ''  # 仅更新root下指定目录（可选）
    # subFolder = 'bilibili' # 无需指定的话 直接注释本行

    # 忽略以下内容，不进行上传。(请参考顶部两组 default ignore)
    ignoreFiless = []  # 忽略的文件结尾字符(扩展名)
    ignoreFolders = []  # 需要忽略的文件夹
    '''
    上述两个列表，接受字符串，也可以直接传入自定义规则的 function。
    ignoreFiles。默认识别结尾字符串(扩展名)，或以含路径文件名作为参数的函数。
    ignoreFolders。识别完整匹配文件夹名的字符，或以一个文件夹名为参数的函数。
    示例：
    def my_rule(fn):
        if os.path.getsize(fn) > 10000000:  # 忽略大文件
            return True
    ignoreFiless = ['exe', 'py', my_rule]
    '''

    maxAge = 0  # header的缓存过期时间 0为不设置

    # Main Progress
    syncLocalToCOS(appid, secret_id, secret_key, bucket_name, region_info,
                   root, subFolder, ignoreFiles, ignoreFolders, maxAge)
