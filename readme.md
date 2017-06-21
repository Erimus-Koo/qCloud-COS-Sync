# 功能
* 这是一个腾讯云COS的同步工具（仅上传更新过的文件）。
* 可指定更新个别目录。
* 同步源以本地文件为准，镜像到COS，会删除COS上多余的文件。
* 我是用来把本地生成的静态页面同步到COS的。

**【重要】使用前务必做好备份！做好备份！做好备份！  
这是一个美工写的工具，请谨慎使用。**

# 安装环境
首先，安装官方的SDK。
```
pip install qcloud_cos_v4
```
[官方 Pyethon SDK 文档](https://www.qcloud.com/document/product/436/6275)
>*这个文档倒是一直有在更新，但因为升级了 Python3.6 想更新下，结果发现这玩意儿只支持到 Python2.7。无奈。*

# 配置参数
看代码最下端
## 初始化客户端
在【云key密钥/项目密钥】找到appid和配套的key，填写下面3个值。
```
appid = 88888888
secret_id = u'YOUR_ID'
secret_key = u'YOUR_KEY'
```
## 填写同步目录
设定本地特定目录为root，对应bucket根目录。还可以指定仅更新某个目录。

**bucket** 前面appid对应项目下的bucket name。
```
bucket = u'YOUR_BUCKET_NAME'
```

**root** 本地根目录，对应bucket根目录。我两台电脑，所以适配了win和mac。
```
if os.name == 'nt':
    root = u'D:\\OneDrive\\erimus-koo.github.io' #PC
else:
    root = u'/Users/Erimus/OneDrive/erimus-koo.github.io' #MAC
```

**subFolder** 仅更新root下指定目录
```
subFolder = u'' #仅更新root下指定目录
subFolder = u'bilibili' #无需指定的话直接注释本行
```

**ignoreFiles** 目前是排除了git相关文件，还有exe、py等。具体可以自行调节。

# 工作流程
* 扫描指定的本地目录，搜集基于root的相对地址及文件名，还有修改时间。并搜集空文件夹信息。
* 排除符合ignore规则的文件。(git、exe、py、psd、ai等)
* 读取整个bucket(中指定的目录)，搜集含相对地址的文件名和修改时间。并搜集空文件夹信息。
* 比较本地和COS上文件的修改时间，仅上传较新的文件。
* 删除本地不存在(或ignore)，但COS上存在的文件。
* 比较空文件夹，同步。逻辑同文件。

# 吐槽
竟然连一个官方工具都没有！文档写得糊涂得一逼！引导做得也超烂！跟工单磨了整整一天(— A —)凸  
阿里云虽然也只有一个上传工具，但至少不用我自己写啊！不用看这稀里糊涂的SDK文档啊！  
也不要吐槽我的代码，我是美工。不过欢迎指正。  
git还用不大来，纯分享。

`腾讯云 COS 同步 网站 静态 Python SDK`