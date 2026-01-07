# 车票回流监控脚本

## 项目简介
这是一个用于自动监控微信小程序特定城际公交线路余票情况的Python脚本。当您心仪的班次无票时，它可以持续监控，并在发现“回流票”（即票数从0变为有票）时，通过**QQ邮件**立即通知您，帮助您抓住他人退票的机会。

## ✨ 核心功能
- **全自动查询**：自动获取指定日期的所有班次信息（时间、余票、票价等）。
- **智能筛选**：清晰列出**有票**和**无票**班次，提供美观的彩色表格供选择。
- **回流票监控**：对选定的无票班次，进行定时、持续的余票监控。
- **邮件通知**：发现回流票时，自动发送**详细邮件通知**到指定QQ邮箱。

## 🛠️ 核心配置与参数获取
脚本运行依赖于从目标网站获取的动态参数。以下是关键的配置部分及其获取方法。

### 1. 配置位置总览
脚本中需要你关注和修改的配置主要有三处，均位于 `bus_monitor.py` 文件中：
1. **邮件配置 (`EMAIL_CONFIG`)**：在文件开头的 `import` 语句之后。
2. **请求头 (`headers`)**：在 `RefundTicketMonitor` 类的 `__init__` 方法中。
3. **请求参数 (`base_params`)**：在 `RefundTicketMonitor` 类的 `__init__` 方法中。

### 2. 请求参数详解：固定参数与动态更新
脚本的请求参数采用“固定基础参数 + 动态更新”的设计，这是保证查询准确性和代码可维护性的关键。

#### 基础固定参数 (`base_params`)
这些参数定义了要监控的**固定线路信息**，存储在 `base_params` 字典中。

**代码位置**：`RefundTicketMonitor` 类的 `__init__` 方法中。
```python
self.base_params = {
    "StartNodeGis": "经度,纬度",           # 【需替换】
    "ArrivalNodeGis": "经度,纬度",         # 【需替换】
    "StartCityCode": "城市区号",           # 【需替换】
    "ArrivalCityCode": "城市区号",         # 【需替换】
    "StartNodeName": "起点站名",           # 【需替换】
    "StartNodeDistrictName": "起点区县",    # 【需替换】
    "ArrivalNodeName": "终点站名",         # 【需替换】
    "ArrivalNodeDistrictName": "终点区县"  # 【需替换】
}
```

#### 动态参数更新 (`params.update`)
这是脚本的**核心机制**。通过 `update_params()` 方法，将动态参数（主要是日期）合并到基础参数中，形成每次查询的完整请求。

**工作流程**：
1.  **复制固定参数**：创建 `self.params` 字典作为 `self.base_params` 的副本，避免污染原数据。
2.  **合并动态参数**：使用 `update()` 方法将动态的日期、时间戳等参数添加进去。
3.  **生成完整参数**：形成包含所有必填项的最终查询参数。

**关键代码**（在 `update_params` 方法中）：
```python
def update_params(self):
    # 1. 复制基础固定参数
    self.params = self.base_params.copy()
    
    # 2. 更新动态参数
    self.params.update({
        # 动态日期参数（由用户输入的 self.target_date 决定）
        "BeginDate": f"{self.target_date} 00:00",
        "EndDate": f"{self.target_date} 23:59",
        # 动态生成的JSON文本，包含时间戳、定位信息等
        "_JsonText": json.dumps({
            "IsNewSearch": True,
            "HasLocation": True,
            "InTiimeStamp": int(time.time() * 1000), # 当前毫秒级时间戳
            "LocationGis": "经度,纬度",              # 【需替换】当前定位坐标
            "LocationDistrict": "区县名",           # 【需替换】当前定位区县
            # ... 根据实际API要求补充其他字段
        })
    })
```

**这种设计的优势**：
- **维护方便**：修改线路信息只需改 `base_params` 一处；修改日期逻辑只需看 `update_params` 方法。
- **避免错误**：防止在构造多次请求时遗漏或错写固定参数。
- **灵活复用**：同一套线路信息可轻松查询不同日期。

### 3. 请求头配置 (`headers`)
请求头用于API的身份验证和客户端标识。

**代码位置**：`RefundTicketMonitor` 类的 `__init__` 方法中，`self.base_params` 之后。
```python
self.headers = {
    # 【最关键】身份验证令牌，会过期，需定期手动更新
    "authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbG...（很长一串字符）",# 【需替换】
    
    # 以下字段通常可直接复用，模拟微信小程序环境
    "user-agent": "",# 【需替换】
    "content-type": "application/json",# 【需替换】
    "iswxapp": "1",# 【需替换】
    "agentappid": "xxx",      # 【需替换】应用ID
    "accept": "*/*",# 【需替换】
    "referer": "" # 【需替换】
}
```

### 4. 如何获取这些参数？（关键步骤）
`authorization` 令牌、`_JsonText` 结构以及所有 `【需替换】` 标记的值，都需要从目标网站手动获取一次。

**获取步骤**：
1.  **手动查询**：在电脑浏览器中访问目标车票查询网站或小程序网页版，进行一次完整的线路查询。
2.  **打开开发者工具**：按 `F12`，切换到 **“网络”(Network)** 标签。
3.  **捕获请求**：在请求列表中，寻找包含 `GisLineClassDayNewQuery` 或类似关键词的 `GET` 请求。
4.  **提取信息**：
    - **`authorization`**：在该请求的 **“请求头”(Headers)** 中找到并复制。
    - **所有参数**：在该请求的 **“载荷”(Payload)** 或 **“查询参数”(Query String Parameters)** 中，找到 `StartNodeGis`、`ArrivalNodeGis`、`_JsonText` 等所有字段及其对应的值。
5.  **替换到代码中**：将复制到的值，逐一替换到上述代码片段的对应位置。

### 5. QQ邮件通知配置 (`EMAIL_CONFIG`)
此配置位于脚本文件**开头的 import 语句之后**，用于设置邮件提醒。
```python
EMAIL_CONFIG = {
    'smtp_server': 'smtp.qq.com',       # 固定
    'smtp_port': 465,                    # 固定
    'sender_email': '你的QQ邮箱@qq.com',  # 【需替换】发件邮箱
    'sender_name': '车票监控助手',        # 可自定义
    'authorization_code': '你的16位授权码', # 【关键】在QQ邮箱设置中生成
    'receiver_email': '接收通知的邮箱地址'   # 【需替换】收件邮箱
}
```
**授权码获取**：登录QQ邮箱网页版 → 设置 → 账户 → 开启“IMAP/SMTP服务” → 生成16位授权码。

## ⚙️ 核心函数说明

### 1. 主监控函数：`monitor_refund_ticket(...)`
这是脚本的核心，负责持续检查余票变化。

**工作流程**：
1.  **初始化**：打印开始信息。
2.  **循环检查**：定时获取最新数据，对比票数变化。
3.  **判断与触发**：
    - **发现回流票**（票数从0变为≥阈值）时：控制台高亮提醒、调用邮件函数、播放提示音。
    - 票数其他变化时，仅在控制台输出信息。
4.  **状态管理**：可自动停止或手动中断。

**关键参数**：
- `target_class_info`：班次详情字典。
- `check_interval`：检查间隔（秒），**建议不小于30秒**。
- `alert_threshold`：触发提醒的票数阈值（默认1张）。

### 2. 邮件发送函数：`send_email_notification(subject, content)`
被主函数调用，独立发送邮件。

## 🚀 快速开始
1.  **环境**：安装 Python 3.7+，执行 `pip install requests urllib3`。
2.  **配置（最关键）**：按上述步骤获取并替换 `headers`、`base_params` 和 `EMAIL_CONFIG` 中的所有 `【需替换】` 内容。
3.  **运行**：执行 `python bus_monitor.py`，按提示操作。


### 4. 运行脚本
1.  在终端中运行脚本：
    ```bash
    python bus_monitor.py
    ```
2.  根据交互提示输入监控日期（如 `2025-12-01`）。
3.  脚本将列出所有班次，请从 **无票班次列表** 中选择序号，开始监控。

## 📧 邮件通知效果示例
收到邮件内容大致如下：
```
【回流票提醒】2025-12-01 08:30 班次

发现车票回流！
日期：2025-12-01
班次：08:30 -> 10:05
当前余票：2 张
票价：¥45
运行时间：95分钟
速去抢票！
```

## 🔍 常见问题 (FAQ)

**Q：运行后提示“登陆已过期”或“未找到任何班次信息”？**

A：`authorization`令牌已失效。请严格按照`如何获取这些参数？` 步骤重新获取并替换

**Q：收不到邮件通知？**

A：请按顺序检查：
1.  `EMAIL_CONFIG` 配置是否正确，特别是16位授权码。
2.  QQ邮箱SMTP服务是否已开启。
3.  服务器防火墙是否放行465端口。

**Q：如何监控另一条线路？**

A：需要更新`base_params`字典中的所有字段，并重新获取对应的`authorization`令牌和`_JsonText`参数。

## 📄 免责声明
本项目依据MIT开源协议公开，仅供学习和技术交流使用。请务必合理设置查询频率，尊重目标网站的服务压力。车票信息请以官方平台为准，开发者不对因使用此工具而导致的任何问题负责。

---
**配置是关键！** 请确保在运行前，已完成 **`获取并更新配置`** 的所有步骤。祝您购票顺利！转载脚本务必注明出处，喜欢该项目的话麻烦给个免费的star!~
