#!/usr/bin/python2.7
#-*- coding: utf-8 -*-
__author__ = 'Erimus'
import os,sys,time,re,json,urllib
from datetime import datetime,timedelta
from qcloud_cos import CosClient,UploadFileRequest,StatFileRequest,ListFolderRequest,DelFileRequest,DelFolderRequest,CreateFolderRequest

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
	width = (len(string)+len(string.decode('utf-8')))/2
	hr = '─'*(width+10)
	print '\n┌%s┐\n│ >>> %s <<< │\n└%s┘'%(hr,string,hr)
# Print format JSON
def formatJSON(obj,indent=4):
	return json.dumps(obj,encoding="UTF-8", ensure_ascii=False,indent=indent)





def readLocalFiles(root,subFolder=u''):
	start = datetime.now()
	drawTitle('Reading local files')

	#斜杠转换(windows) & 去头尾斜杠
	root=re.sub(r'\\',u'/',root).rstrip('\\/')
	subFolder=re.sub(r'\\',u'/',subFolder).lstrip('\\/').rstrip('\\/')

	localFilesDict,localEmptyFolders = {},[]
	for path, dirs, files in os.walk(root+'/'+subFolder):
		total = len(files)
		for i,fileName in enumerate(files[:]):
			localFile = (path+'/'+fileName)[len(root):]
			localFile = re.sub(r'\\',u'/',localFile) #斜杠转换
			localFile = re.sub(r'//',u'/',localFile) #根目录重复斜杠
			# print '%s'%localFile
			modifyTime = int(os.stat(path+'/'+fileName).st_mtime)
			localFilesDict[localFile] = modifyTime #输出结果 {'正斜杠相对地址文件名':'int文件修改时间'}
			# print '%s / %s'%(i+1,total)
		
		if not os.listdir(path):
			emptyFolder = path[len(root):]
			emptyFolder = re.sub(r'\\',u'/',emptyFolder) + '/' #斜杠转换
			# print emptyFolder
			localEmptyFolders.append(emptyFolder)

	print 'Local Files: %s\nLocal Empty Folders: %s'%(len(localFilesDict),len(localEmptyFolders))
	# print 'localFilesDict'+formatJSON(localFilesDict.keys()[:20])
	if localEmptyFolders:
		print '---\nlocalEmptyFolders'+formatJSON(localEmptyFolders)
	print '---\n%s: %s'%('Used',datetime.now()-start)
	return localFilesDict,localEmptyFolders



def ignoreFiles(localFilesDict):
	drawTitle('Ignore specific files')
	ignoreList = []
	for file in localFilesDict.keys():
		ignore = False
		if '/.git/' in file: #.git folder
			ignore = True

		fileName = re.findall(r'(?<=/)(?!.*/).*',file)[0]
		# print fileName
		if fileName[0]=='.': #file start with '.'
			ignore = True

		ignoreExts = ['exe','py'] #ignore extension list
		try:
			extension = re.findall(r'(?<=.)(?!.*\.).*',file)[0].lower()
		except:
			extension = ''
		# print extension
		for ext in ignoreExts:
			if extension==ext:
				ignore = True

		if ignore:
			localFilesDict.pop(file)
			ignoreList.append(file)

	print 'Ignore Files: %s\nLocal files need to be compared: %s'%(len(ignoreList),len(localFilesDict))
	# print 'ignoreList'+formatJSON(ignoreList[:10])
	return localFilesDict


def readCosFiles(cos_client,bucket,subFolder=''):
	start = datetime.now()
	drawTitle('Reading COS files')

	cosFilesDict,cosEmptyFolders = {},[]
	if subFolder:
		folderPool = ['/' + re.sub(r'\\',u'/',subFolder).lstrip('\\/').rstrip('\\/') + '/']
	else:
		folderPool = [u'/']
	while len(folderPool)>0:
		folder = folderPool.pop()

		cosFilesList,listover,context = [],False,'' #每次请求有199限制 神tm199为毛不是200
		while listover==False:
			succes = times = 0
			while succes==0 and times<10:
				times += 1
				request = ListFolderRequest(bucket, folder)
				if context:
					request.set_context(context) #文档里虽然给了参数 但怎么用你猜（文档不会告诉你用set的哦）
				try:
					list_folder_ret = cos_client.list_folder(request)
					# print formatJSON(list_folder_ret)
					if list_folder_ret['message']==u'SUCCESS':
						succes = 1
						cosFilesList += list_folder_ret['data']['infos']
						listover = list_folder_ret['data']['listover']
						context = list_folder_ret['data']['context']
				except:
					print 'ListFolderRequest Failed.\nFolder: %s\nContext:%s'%(folder,context)
			if times==10:
				print '===Error===: %s info load failed'%(folder)
				continue

		for item in cosFilesList:
			if item['mtime']==0: #folder with files
				folderPool.append(folder+item['name'])
				# print folder+item['name']

			if ('filesize' not in item) and (item['mtime']!=0): #empty folder
				cosEmptyFolders.append(folder+item['name'])

			if 'filesize' in item: #file
				cosFile = re.sub(r'^.*?qcloud.com','',item['source_url']) #取含路径的文件名
				cosFile = urllib.unquote(cosFile.encode('utf-8')).decode('utf-8') #url中文转码
				# print cosFile,type(cosFile)
				cosFilesDict[cosFile] = item['mtime']

	print 'COS files: %s\nCOS empty folders: %s'%(len(cosFilesDict),len(cosEmptyFolders))
	if cosEmptyFolders:
		print '---\ncosEmptyFolders'+formatJSON(cosEmptyFolders)
	print '---\n%s: %s'%('Used',datetime.now()-start)
	return cosFilesDict,cosEmptyFolders



# def getCosFileModifyTime(cos_client,cosFile): #StatFileRequest instead by readCosFiles
# 	# try 10 times, if fail then print error.
# 	succes = times = mtime = 0
# 	while succes==0 and times<10:
# 		times += 1
# 		try:
# 			request = StatFileRequest(bucket, cosFile)
# 			stat_file_ret = cos_client.stat_file(request)
# 			if stat_file_ret['message']==u'SUCCESS':
# 				mtime = stat_file_ret['data']['mtime']
# 				succes = 1
# 		except:
# 			print 'Error\n%-30s: %s'%(cosFile,stat_file_ret['message'])
# 	if times==10:
# 		print '===Error===: %s get state failed'%(cosFile)
# 	return mtime



def filterModifiedLocalFiles(localFilesDict,cosFilesDict):
	drawTitle('Filtering modified local files')

	modifiedLocalFiles=[]
	for i,file in enumerate(localFilesDict):
		# print 'read cos file state: %s / %s'%(i+1,len(localFilesDict))
		# cosFileModifyTime = getCosFileModifyTime(file) #old method
		try:
			cosFileModifyTime = cosFilesDict[file]
		except:
			cosFileModifyTime = 0
		if localFilesDict[file]>cosFileModifyTime:
			modifiedLocalFiles.append(file)
	
	if len(modifiedLocalFiles)==0:
		print 'All files on COS are the newest.\nNo files need to be uploaded.'
	else:
		print 'Modified Files: %s'%len(modifiedLocalFiles)
	
	return modifiedLocalFiles



def uploadToCos(cos_client,bucket,root,localFile):
	# try 10 times, if fail then print error.
	succes = times = 0
	request = UploadFileRequest(bucket, localFile, root+localFile)
	request.set_insert_only(0) # 0是允许覆盖 1是不允许
	while succes==0 and times<10:
		times += 1
		try:	
			upload_file_ret = cos_client.upload_file(request)
			if upload_file_ret['message']==u'SUCCESS':
				succes = 1
			print 'Upload | %s | %s'%(localFile,upload_file_ret['message'])
		except:
			pass
	if times==10:
		print '===Error===: %s upload failed'%(localFile)



def filterExtraCosFiles(localFilesDict,cosFilesDict):
	drawTitle('Filtering extra files on COS')

	extraCosFiles = []
	for file in cosFilesDict:
		if file not in localFilesDict:
			extraCosFiles.append(file)
	# print extraCosFiles
	if len(extraCosFiles)==0:
		print 'No files need to be deleted.'
	else:
		print 'Extra Files: %s'%len(extraCosFiles)

	return extraCosFiles 



def deleteCosFile(cos_client,bucket,cosFile):
	succes = times = 0
	while succes==0 and times<10:
		times += 1
		try:
			del_ret = cos_client.del_file(DelFileRequest(bucket, cosFile))
			# print cosFile+formatJSON(del_ret)
			if del_ret['message']==u'SUCCESS':
				succes = 1
			print 'Delete | %s | %s'%(cosFile,del_ret['message'])
		except:
			pass
	if times==10:
		print '===Error===: %s delete failed'%(cosFile)



def deleteCosFolder(cos_client,bucket,folder):
	try:
		request = DelFolderRequest(bucket, folder)
		delete_folder_ret = cos_client.del_folder(request)
		print 'Delete | %s | %s'%(folder,delete_folder_ret['message'])
	except:
		print 'Error: deleteCosFolder | %s'%folder



def createCosFolder(cos_client,bucket,folder):
	try:
		request = CreateFolderRequest(bucket, folder)
		create_folder_ret = cos_client.create_folder(request)
		print 'Create | %s | %s'%(folder,create_folder_ret['message'])
	except:
		print 'Error: createCosFolder | %s'%folder



def syncEmptyFolders(cos_client,bucket,localEmptyFolders,cosEmptyFolders):
	start = datetime.now()
	drawTitle('Sync empty folders')
	for folder in localEmptyFolders:
		if folder not in cosEmptyFolders:
			createCosFolder(cos_client,bucket,folder)
		else:
			cosEmptyFolders.remove(folder)
	for folder in cosEmptyFolders:
		deleteCosFolder(cos_client,bucket,folder)
	print '---\n%s: %s'%('Used',datetime.now()-start)



def syncLocalToCOS(appid,secret_id,secret_key,bucket,root,subFolder=''):
	cos_client = CosClient(appid, secret_id, secret_key)

	localFilesDict,localEmptyFolders = readLocalFiles(root,subFolder) #读取本地需要更新的目录
	localFilesDict = ignoreFiles(localFilesDict) #忽略部分文件 具体规则内详
	cosFilesDict,cosEmptyFolders = readCosFiles(cos_client,bucket,subFolder) #读取cos上需要更新的目录
	# # print 'localFilesDict'+formatJSON(localFilesDict)
	# # print 'cosFilesDict'+formatJSON(cosFilesDict)

	# 比较文件修改时间，筛选出需要更新的文件，并且上传。
	modifiedLocalFiles = filterModifiedLocalFiles(localFilesDict,cosFilesDict)
	if modifiedLocalFiles:
		start = datetime.now()
		drawTitle('Uploading files')
		for file in modifiedLocalFiles:
			uploadToCos(cos_client,bucket,root,file)
		print '---\n%s: %s'%('Used',datetime.now()-start)

	# 筛选出cos上有，但本地已经不存在的文件，删除COS上的文件。
	extraCosFiles = filterExtraCosFiles(localFilesDict,cosFilesDict)
	if extraCosFiles:
		start = datetime.now()
		drawTitle('Deleting COS files')
		for file in extraCosFiles:
			deleteCosFile(cos_client,bucket,file)
		print '---\n%s: %s'%('Used',datetime.now()-start)

	# 同步空文件夹
	syncEmptyFolders(cos_client,bucket,localEmptyFolders,cosEmptyFolders)





if __name__ == '__main__':
	# 初始化客户端。在【云key密钥/项目密钥】找到appid和配套的key，填写下面3个值。
	appid = 88888888
	secret_id = u'YOUR_ID'
	secret_key = u'YOUR_KEY'

	# 填写同步目录。COS端的bucket，本地的root，可以指定root下的单个目录(optional)。
	bucket = u'YOUR_BUCKET_NAME' #上述appid对应项目下的bucket name
	# 本地根目录 对应bucket根目录
	if os.name == 'nt':
		root = u'D:\\OneDrive\\erimus-koo.github.io' #PC
	else:
		root = u'/Users/Erimus/OneDrive/erimus-koo.github.io' #MAC
	subFolder=u'' #仅更新root下指定目录
	# subFolder=u'bilibili' #无需指定的话直接注释本行

	# Main Progress
	syncLocalToCOS(appid,secret_id,secret_key,bucket,root,subFolder)