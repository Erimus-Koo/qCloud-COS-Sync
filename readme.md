### 更新sdk v5

---

# 功能
* 这是一个腾讯云COS的同步工具（仅上传更新过的文件）。
* 可指定更新个别目录。
* 同步源以本地文件为准，镜像到COS，让COS上的文件和本地一致。
* 会删除COS上多余的文件。不会改动本地文件。
* 我是用来把本地生成的静态页面同步到COS的。

**【重要】使用前务必做好备份！做好备份！做好备份！  
这是一个美工写的工具，请谨慎使用。**

# 安装环境
首先，安装官方的SDK。
```
pip install cos-python-sdk-v5
```
[官方 Python SDK 文档](https://cloud.tencent.com/document/product/436/12270)

# 配置参数
看代码最下端
## 初始化客户端
在【密钥管理】找到appid和配套的key，填写下面3个值。
```
appid = 88888888  # your appid
secret_id = 'your_id'
secret_key = 'your_key'
```

## 地区列表
可以看自己的bucket下的域名管理/静态地址/`cos.`后面那段。
```
region_info = 'ap-shanghai'
```

## 填写同步目录
设定本地特定目录为root，对应bucket根目录。还可以指定仅更新某个目录。

**bucket** 前面appid对应项目下的bucket name。
```
bucket_name = 'your_bucket_name'
```

**root** 本地根目录，对应bucket根目录。我两台电脑，所以适配了win和mac。
```
if os.name == 'nt':
    root = 'D:\\OneDrive\\yourRoot'  # PC
else:
    root = '/Users/Erimus/OneDrive/yourRoot'  # MAC
```

**subFolder** 仅更新root下指定目录
```
subFolder = u'' #仅更新root下指定目录
subFolder = u'bilibili' #无需指定的话直接注释本行
```

**maxAge** 可以设置浏览器缓存时间了
```
    maxAge = 0  # header的缓存过期时间 0为不设置
```

## 打印信息
**debug** 开启打印较详细信息，关闭打印较精简信息。

## 忽略文件/文件夹
**ignoreFiles / ignoreFolders** 这两个函数可以自己去设定。  
目前是排除了git相关文件，还有exe、py、psd等等。具体看一下代码就明白了。  
默认排除项目见顶部的两个 DEFAULT_IGNORE 。

**ignoreFiles** 默认识别结尾字符串(扩展名)，或以含路径文件名作为参数的函数。  
**ignoreFolders** 识别完整匹配文件夹名的字符，或以一个文件夹名为参数的函数。 
只要整个路径含有该数组中的字符，就会被忽略。
```
ignoreFiless = []  # 忽略的文件结尾字符(扩展名)
ignoreFolders = []  # 需要忽略的文件夹
```
上述两个列表，接受字符串，也可以直接传入自定义规则的 function。   
示例：
```
def my_rule(fn):
    if os.path.getsize(fn) > 10000000:  # 忽略大文件
        return True
ignoreFiless = ['exe', 'py', my_rule]
```

# 工作流程
* 扫描指定的本地目录，搜集基于root的相对地址及文件名，还有修改时间。并搜集空文件夹信息。
* 排除符合ignore规则的文件。(git、exe、py、psd、ai等)
* 读取整个bucket(中指定的目录)，搜集含相对地址的文件名和修改时间。并搜集空文件夹信息。
* 比较本地和COS上文件的修改时间，仅上传较新的文件。
* 删除本地不存在(或ignore)，但COS上存在的文件。
* 比较空文件夹，同步。逻辑同文件。(暂无效)  
    新版本SDK会自动删除空文件夹。所以本地空文件夹，不会在cos上创建。

`腾讯云 COS 同步 网站 静态 Python SDK`

---

# Update log

- 2019-11-19
    - 阻止 sdk 自带的 logging，它的 info 级信息过多。
    - 缩减打印信息。
    - 扩展忽略规则，接受自定义函数。
