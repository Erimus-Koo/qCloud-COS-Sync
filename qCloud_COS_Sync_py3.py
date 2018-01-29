#!/usr/bin/env python3
# -*- coding: utf-8 -*-
__author__ = 'Erimus'
import os
import re
import json
import urllib
from datetime import datetime
from qcloud_cos import *

"""
这是一个腾讯云COS的同步工具（仅上传更新部分）。可指定更新个别目录。
同步源以本地文件为准，镜像到COS，会删除COS上多余的文件。我是用来把本地生成的静态页面同步到COS的。

【重要】使用前务必做好备份！做好备份！做好备份！这是一个美工写的工具，请谨慎使用。

准备工作，安装SDK。
pip install qcloud_cos_v4

设定本地特定目录为root，对应bucket根目录。还可以指定仅更新某个目录。
会比较本地和COS上文件的修改时间，仅上传较新的文件。
如果某个文件，本地没有，但COS对应路径下有，会自动删COS上的文件。
会忽略部分文件，具体搜ignoreFiles部分。
"""

# Draw title with Frame


def drawTitle(string):
    width = (len(string) + len(string.encode('utf-8'))) // 2
    hr = '=' * (width + 8)
    print('\n%s\n>>> %s <<<\n%s' % (hr, string, hr))

# Print format JSON


def formatJSON(obj, indent=4):
    return json.dumps(obj, ensure_ascii=False, indent=indent)


def formatPath(path):
    path = path.replace('\\', '/')
    while '//' in path:
        path = path.replace('//', '/')
    return path.rstrip('/')


# ====================


def readLocalFiles(root, subFolder='', debug=1):
    start = datetime.now()
    if debug:
        drawTitle('Reading local files')

    localFilesDict, localEmptyFolders = {}, []
    ignoreFoldersNum = ignoreFilesNum = 0  # ignore计数
    for path, dirs, files in os.walk(root + '/' + subFolder):
        if isIgnoreFolder(path[len(root):]):  # 忽略目录
            ignoreFoldersNum += 1
            continue

        # total = len(files)
        for i, fileName in enumerate(files[:]):
            if isIgnoreFile(fileName):  # 忽略文件
                ignoreFilesNum += 1
                continue

            localFile = formatPath(path + '/' + fileName)[len(root):]
            # print('local: %s'%localFile)
            modifyTime = int(os.stat(path + '/' + fileName).st_mtime)
            # 输出结果 {'正斜杠相对地址文件名':'int文件修改时间'}
            localFilesDict[localFile] = modifyTime
            # print('%s / %s'%(i+1,total))

        if not os.listdir(path):  # 标注空文件夹
            emptyFolder = formatPath(path)[len(root):]
            # print(emptyFolder)
            localEmptyFolders.append(emptyFolder)

    if debug:  # 打印详情
        print('Local Files: %s\nLocal Empty Folders: %s'
              % (len(localFilesDict), len(localEmptyFolders)))
        print('\n-Ignored folders (& inner files): %s\n-Ignored files: %s'
              % (ignoreFoldersNum, ignoreFilesNum))
        # print('localFilesDict'+formatJSON(localFilesDict.keys()[:20]))

        if localEmptyFolders:
            print('\n---\nlocalEmptyFolders: ' + formatJSON(localEmptyFolders))
        print('\n---\n%s: %s\n' % ('Used', datetime.now() - start))

    return localFilesDict, localEmptyFolders


def isIgnoreFolder(path):  # 忽略文件夹
    # path = formatPath(path)
    if '.git' in path:
        return True


def isIgnoreFile(fileName):  # 忽略文件
    # file start with '.' 隐藏文件
    if fileName[0] == '.':
        return True

    ignoreExts = ['exe', 'py', 'psd', 'ai', 'xlsx']  # ignore extension list
    extension = fileName.split('.')[-1].lower()  # 获取扩展名
    if extension in ignoreExts:
        return True

    # 个人网页专用忽略项
    if extension in ['less']:
        return True
    if '.html' in fileName:
        if fileName == 'index.html':
            return
        if '.min.html' in fileName:
            return
        return True  # 过滤非首页且没有Minify过的网页源文件


# ====================


def readCosFiles(cos_client, bucket, subFolder='', debug=1):
    start = datetime.now()
    if debug:
        drawTitle('Reading COS files')

    cosFilesDict, cosEmptyFolders = {}, []
    folderPool = ['/' + subFolder + '/'] if subFolder else ['/']
    while len(folderPool) > 0:
        folder = folderPool.pop()

        cosFilesList, listover, context = [], False, ''
        while not listover:
            succes = times = 0
            while not succes and times < 10:
                times += 1
                request = ListFolderRequest(bucket, folder)
                # 设置请求头(下一页)
                if context:
                    request.set_context(context)
                try:
                    # 每次请求有199限制
                    list_folder_ret = cos_client.list_folder(request)
                    # print(formatJSON(list_folder_ret))
                    if list_folder_ret['message'] == 'SUCCESS':
                        succes = 1
                        cosFilesList += list_folder_ret['data']['infos']
                        listover = list_folder_ret['data']['listover']
                        context = list_folder_ret['data']['context']
                except Exception:
                    print('ListFolderRequest Failed.\nFolder: %s\nContext:%s'
                          % (folder, context))
            if times == 10:
                print('===Error===: %s info load failed' % (folder))
                continue

        for item in cosFilesList:
            if item['mtime'] == 0:  # folder with files
                folderPool.append(folder + item['name'])
                # print(folder+item['name'])

            if ('filesize' not in item) and (item['mtime'] != 0):  # empty folder
                cosEmptyFolders.append(folder + item['name'])

            if 'filesize' in item:  # file
                # 取含路径的文件名
                cosFile = re.sub(r'^.*?qcloud.com', '', item['source_url'])
                cosFile = urllib.parse.unquote(cosFile)  # url编码中文解码
                # print(cosFile,type(cosFile))
                cosFilesDict[cosFile] = item['mtime']

    if debug:
        print('COS files: %s\nCOS empty folders: %s'
              % (len(cosFilesDict), len(cosEmptyFolders)))
        if cosEmptyFolders:
            print('---\ncosEmptyFolders' + formatJSON(cosEmptyFolders))
        print('---\n%s: %s' % ('Used', datetime.now() - start))

    return cosFilesDict, cosEmptyFolders


# ====================


def filterModifiedLocalFiles(localFilesDict, cosFilesDict, debug=1):
    if debug:
        drawTitle('Filtering modified local files')

    modifiedLocalFiles = []
    for i, file in enumerate(localFilesDict):
        cosFileModifyTime = cosFilesDict.get(file, 0)  # cos上没有的文件
        if localFilesDict[file] > cosFileModifyTime:
            modifiedLocalFiles.append(file)

    if modifiedLocalFiles:
        print('Modified Files: %s' % len(modifiedLocalFiles))
    else:
        print('All files on COS are the newest.\nNo files need to be uploaded.')

    return modifiedLocalFiles


def uploadToCos(cos_client, bucket, root, localFile):
    # try 10 times, if fail then print(error.)
    succes = times = 0
    request = UploadFileRequest(bucket, localFile, root + localFile)
    request.set_insert_only(0)  # 0是允许覆盖 1是不允许
    while not succes and times < 10:
        times += 1
        try:
            upload_file_ret = cos_client.upload_file(request)
            if upload_file_ret['message'] == 'SUCCESS':
                succes = 1
            print('Upload | %-10s | %s'
                  % (upload_file_ret['message'], localFile))
        except Exception:
            pass
    if times == 10:
        print('===Error===: %s upload failed' % (localFile))


# ====================


def filterExtraCosFiles(localFilesDict, cosFilesDict, debug=1):
    if debug:
        drawTitle('Filtering extra files on COS')

    extraCosFiles = []
    for file in cosFilesDict:
        if file not in localFilesDict:
            extraCosFiles.append(file)
    # print(extraCosFiles)
    if extraCosFiles:
        print('Extra Files: %s' % len(extraCosFiles))
    else:
        print('No files need to be deleted.')

    return extraCosFiles


def deleteCosFile(cos_client, bucket, cosFile):
    succes = times = 0
    while succes == 0 and times < 10:
        times += 1
        try:
            del_ret = cos_client.del_file(DelFileRequest(bucket, cosFile))
            # print(cosFile+formatJSON(del_ret))
            if del_ret['message'] == 'SUCCESS':
                succes = 1
            print('Delete | %-10s | %s' % (del_ret['message'], cosFile))
        except Exception:
            pass
    if times == 10:
        print('===Error===: %s delete failed' % (cosFile))


# ====================


def deleteCosFolder(cos_client, bucket, folder):
    try:
        request = DelFolderRequest(bucket, folder)
        delete_folder_ret = cos_client.del_folder(request)
        print('Delete | %-10s | %s' % (delete_folder_ret['message'], folder))
    except Exception:
        print('Error: deleteCosFolder | %s' % folder)


def createCosFolder(cos_client, bucket, folder):
    if folder[-1] != '/':
        folder += '/'
    try:
        request = CreateFolderRequest(bucket, folder)
        create_folder_ret = cos_client.create_folder(request)
        print('Create | %-10s | %s' % (create_folder_ret['message'], folder))
    except Exception:
        print('Error: createCosFolder | %s' % folder)


def syncEmptyFolders(cos_client, bucket,
                     localEmptyFolders, cosEmptyFolders, debug=1):
    start = datetime.now()
    if debug:
        drawTitle('Sync empty folders')

        if not localEmptyFolders + cosEmptyFolders:
            print('No empty folder.')

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

    print('---\n%s: %s' % ('Used', datetime.now() - start))


# ====================


def syncLocalToCOS(appid, secret_id, secret_key, bucket, region_info,
                   root, subFolder='', debug=1):
    root = formatPath(root)
    subFolder = formatPath(subFolder)
    cos_client = CosClient(appid, secret_id, secret_key, region=region_info)

    # check cos_client & bucket
    list_folder_ret = cos_client.list_folder(ListFolderRequest(bucket, '/'))
    if list_folder_ret['message'] != 'SUCCESS':
        raise Exception('>>> Check your appid / secret_id / '
                        'secret_key / bucket_name <<<')

    # 读取本地需要更新的目录
    localFilesDict, localEmptyFolders = readLocalFiles(root, subFolder,
                                                       debug=debug)

    # 读取cos上需要更新的目录
    cosFilesDict, cosEmptyFolders = readCosFiles(cos_client, bucket, subFolder,
                                                 debug=debug)

    # 比较文件修改时间，筛选出需要更新的文件，并且上传。
    modifiedLocalFiles = filterModifiedLocalFiles(localFilesDict, cosFilesDict,
                                                  debug=debug)
    if modifiedLocalFiles:
        start = datetime.now()
        if debug:
            drawTitle('Uploading files')
        for file in modifiedLocalFiles:
            uploadToCos(cos_client, bucket, root, file)
        if debug:
            print('---\n%s: %s' % ('Used', datetime.now() - start))

    # 筛选出cos上有，但本地已经不存在的文件，删除COS上的文件。
    extraCosFiles = filterExtraCosFiles(localFilesDict, cosFilesDict,
                                        debug=debug)
    if extraCosFiles:
        start = datetime.now()
        if debug:
            drawTitle('Deleting COS files')
        for file in extraCosFiles:
            deleteCosFile(cos_client, bucket, file)
        if debug:
            print('---\n%s: %s' % ('Used', datetime.now() - start))

    # 同步空文件夹
    syncEmptyFolders(cos_client, bucket, localEmptyFolders, cosEmptyFolders,
                     debug=debug)


# ====================


if __name__ == '__main__':
    # 初始化客户端。在【云key密钥/项目密钥】找到appid和配套的key，填写下面4个值。
    appid = 88888888
    secret_id = 'YOUR_ID'
    secret_key = 'YOUR_KEY'
    region_info = 'sh'  # 'sh'=华东,'gz'=华南,'tj'=华北 ,('sgp'~=新加坡)

    # 填写同步目录。COS端的bucket，本地的root，可以指定root下的单个目录(可选)。
    bucket = 'YOUR_BUCKET_NAME'  # 上述appid对应项目下的bucket name
    # 本机根目录 对应bucket根目录
    if os.name == 'nt':
        root = 'D:\\OneDrive\\erimus-koo.github.io'  # PC
    else:
        root = '/Users/Erimus/OneDrive/erimus-koo.github.io'  # MAC
    subFolder = ''  # 仅更新root下指定目录
    # subFolder = 'bilibili' #无需指定的话直接注释本行

    # Main Progress
    syncLocalToCOS(appid, secret_id, secret_key, bucket,
                   region_info, root, subFolder)
