# 功能
* 这是一个腾讯云COS的同步工具（仅上传更新过的文件）。
* 可指定更新个别目录。
* 同步源 **以本地文件为准，镜像到COS，让COS上的文件和本地一致。**
* 会删除COS上多余的文件。 **不会改动本地文件**。
* 我是用来把本地生成的静态页面同步到COS的。

**【重要】使用前务必做好备份！做好备份！做好备份！**



# 安装环境
首先，安装官方的SDK。
```python
pip install cos-python-sdk-v5
```
[官方 Python SDK 文档](https://cloud.tencent.com/document/product/436/12270)



# 配置参数
看代码最下端
## 初始化客户端
在【密钥管理】找到appid和配套的key，填写下面3个值。
```python
appid = 88888888  # your appid
secret_id = 'your_id'
secret_key = 'your_key'
```

## 地区列表
可以看自己的bucket下的域名管理/静态地址/`cos.`后面那段。
```python
region_info = 'ap-shanghai'
```

## 填写同步目录
设定本地特定目录为root，对应bucket根目录。还可以指定仅更新某个目录。

**bucket** 前面appid对应项目下的bucket name。
```python
bucket_name = 'your_bucket_name'
```

**root** 本地根目录，对应bucket根目录。我两台电脑，所以适配了win和mac。
```python
if os.name == 'nt':
    root = 'D:/OneDrive/yourRoot'  # PC
else:
    root = '/Users/Erimus/OneDrive/yourRoot'  # MAC
```

**subFolder** 仅更新root下指定目录
```python
subFolder = '' #仅更新root下指定目录
subFolder = 'notebook' #无需指定的话直接注释本行
```

**maxAge** 可以设置浏览器缓存时间了
```python
    maxAge = 0  # header的缓存过期时间 0为不设置
```

## 忽略文件/文件夹
**ignoreFiles / ignoreFolders** 这两个函数可以自己去设定。  
目前默认排除了git相关文件，还有exe、py、psd等等。具体看一下代码就明白了。  
默认排除项目见顶部的两个 **DEFAULT_IGNORE** 。
```python
ignoreFiless = []  # 忽略的文件结尾字符(扩展名)
ignoreFolders = []  # 需要忽略的文件夹
```
上述两个列表，接受字符串，也可以直接传入自定义规则的 function。   
示例：
```python
def my_rule(fn):
    if os.path.getsize(fn) > 10000000:  # 忽略大文件
        return True
ignoreFiless = ['exe', 'py', my_rule]
```

**ignoreFiles**  
判断的对象是含完整路径的文件名，如 `C:/path/file.ext`。  
传入字符串时，默认识别结尾字符串(扩展名)，符合的忽略（不同步）。  
传入函数时，以文件名为参数。返回 `True` 时，忽略该文件（不同步）。  

**ignoreFolders**  
判断的对象是相对根目录的**完整路径**，如`/path`。  
传入字符串时，只要上述路径中的某一级等于该字符串，就忽略（不同步）。  
传入函数时，以上述路径为参数。返回 `True` 时，忽略该目录（不同步）。  



# 工作流程
* 扫描指定的本地目录，搜集基于root的相对地址及文件名，还有修改时间。并搜集空文件夹信息。
* 排除符合ignore规则的文件。(git、exe、py、psd、ai等)
* 读取整个bucket(中指定的目录)，搜集含相对地址的文件名和修改时间。并搜集空文件夹信息。
* 比较本地和COS上文件的修改时间，仅上传较新的文件。
* 删除本地不存在(或ignore)，但COS上存在的文件。
* 比较空文件夹，同步。逻辑同文件。(暂无效)  
    新版本SDK会自动删除空文件夹。所以本地空文件夹，不会在cos上出现。



# 使用示例
## 配置文件 
`my_bucket1.py` 用来统一配置 bucket 的链接密钥和本地对应目录等。  
因为每次初始化会连接，建议不同 bucket 分不同文件。
```python
from qCloud_COS_Sync import COS

my_cos_config = {
    'appid': 888888,
    'secret_id': '',
    'secret_key': '',
    'region_info': 'ap-shanghai',
    'bucket_name': '',
    'maxAge': 0
}

ignore = {'ignoreFiles': [],
          'ignoreFolders': ['python']}

root = _root + '/OneDrive/site'  # PC
# subFolder = 'notebook'  # 无需指定的话 直接注释本行
MY_BUCKET1 = COS(**my_cos_config, root=root, **ignore)  # 初始化
```

## 使用场景 
`my_func.py` 直接调用上述配置好的 bucket 连接。  
还可以中途修改过滤规则，目录，默认maxAge，等等。
```python
from cos.my_bucket1 import MY_BUCKET1

here = os.path.abspath(os.path.dirname(__file__))
sub_folder = 'test_folder'
file_full_path = os.path.join(here, sub_folder, 'test_file.html')
local_file = file_full_path[len(here):]

# 创建本地测试文件
if not os.path.exists(new:=os.path.join(here, sub_folder)):
    os.mkdir(new)
if not os.path.exists(file_full_path):
    with open(file_full_path, 'w', encoding='utf-8') as f:
        f.write('test file')


def title(x): print('\n' + x.center(30, '='))


title('修改配置')
MY_BUCKET1.config({'root': here})
[print(f'{k}: {v}') for k, v in MY_BUCKET1.cfg.items()]

title('上传')
MY_BUCKET1.upload(local_file)
cos_files = MY_BUCKET1.read(sub_folder)
[print(i) for i in cos_files]

title('删除')
MY_BUCKET1.delete(local_file)
cos_files = MY_BUCKET1.read(sub_folder)
[print(i) for i in cos_files]

title('同步')
MY_BUCKET1.sync(sub_folder)
cos_files = MY_BUCKET1.read(sub_folder)
[print(i) for i in cos_files]

title('删除')
MY_BUCKET1.delete(local_file)
cos_files = MY_BUCKET1.read(sub_folder)
[print(i) for i in cos_files]

```


`腾讯云 COS 同步 网站 静态 Python SDK`

---

# Update log

- 2020-03-08
    - 改为 Class 的形式。（原函数形式移入 archive）  
        这样配置文件比较容易分离调用，在有多个bucket或服务器时也会比较方便，且易于区分。

- 2019-11-19
    - 阻止 sdk 自带的 logging，它的 info 级信息过多。
    - 缩减打印信息。
    - 扩展忽略规则，接受自定义函数。
