# 远程登录访问测试指南

本文档说明如何测试"远程登录访问（网络）：网络对端测试使用不同的两台实体机器进行"功能。

## 📋 测试方案概览

### 方案一：使用两台实际物理机器（推荐用于最终演示）
- **机器A（服务器）**：运行Flask服务器
- **机器B（客户端）**：运行PyQt客户端程序

### 方案二：使用虚拟机（推荐用于开发测试）
- **主机**：运行Flask服务器
- **虚拟机**：运行PyQt客户端程序（或反之）

### 方案三：使用局域网内的两台设备
- 可以是两台电脑、一台电脑+一台笔记本等

---

## 🚀 方案一：两台实际物理机器测试

### 步骤1：准备服务器端（机器A）

#### 1.1 检查服务器配置
确保 `student_mgmt/server/app.py` 中的服务器配置如下：
```python
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)  # host="0.0.0.0" 允许外部访问
```

#### 1.2 配置防火墙
**Windows系统：**
1. 打开"Windows Defender 防火墙"
2. 点击"高级设置"
3. 选择"入站规则" → "新建规则"
4. 选择"端口" → 下一步
5. 选择"TCP"，输入端口号 `5000`
6. 选择"允许连接"
7. 应用到所有配置文件
8. 命名规则（如"Flask Server 5000"）

**Linux系统：**
```bash
# Ubuntu/Debian
sudo ufw allow 5000/tcp

# CentOS/RHEL
sudo firewall-cmd --permanent --add-port=5000/tcp
sudo firewall-cmd --reload
```

#### 1.3 获取服务器IP地址
**Windows：**
```cmd
ipconfig
```
查找"IPv4 地址"，例如：`192.168.1.100`

**Linux/Mac：**
```bash
ifconfig
# 或
ip addr show
```

#### 1.4 启动服务器
```bash
cd student_mgmt/server
python app.py
```

应该看到类似输出：
```
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:5000
 * Running on http://192.168.1.100:5000
```

#### 1.5 测试服务器是否可访问
在服务器机器上测试：
```bash
curl http://127.0.0.1:5000/api/login
```

### 步骤2：配置客户端（机器B）

#### 2.1 修改客户端配置
编辑 `student_mgmt/client/config.py`：
```python
SERVER_URL = "http://192.168.1.100:5000"  # 替换为机器A的实际IP地址
```

#### 2.2 测试网络连接
在客户端机器上测试是否能访问服务器：
```bash
# Windows
ping 192.168.1.100

# 测试HTTP连接（需要安装curl或使用浏览器）
curl http://192.168.1.100:5000/api/login
```

#### 2.3 启动客户端
```bash
cd student_mgmt/client
python main.py
```

#### 2.4 测试登录
1. 在客户端输入用户名、密码和角色
2. 点击登录
3. 如果成功，说明远程访问配置正确

---

## 🖥️ 方案二：使用虚拟机测试

### 步骤1：设置虚拟机网络

#### 1.1 网络模式选择
- **桥接模式（Bridged）**：虚拟机获得独立IP，与主机在同一局域网
- **NAT模式**：需要配置端口转发

**推荐使用桥接模式**，这样虚拟机就像局域网中的另一台机器。

#### 1.2 配置桥接网络（VMware）
1. 虚拟机设置 → 网络适配器
2. 选择"桥接模式"
3. 选择主机的物理网卡

#### 1.3 配置桥接网络（VirtualBox）
1. 虚拟机设置 → 网络
2. 适配器1 → 启用网络连接
3. 连接方式选择"桥接网卡"
4. 选择主机的物理网卡

### 步骤2：分配角色

**选项A：主机作为服务器，虚拟机作为客户端**
- 主机：运行 `python student_mgmt/server/app.py`
- 虚拟机：运行 `python student_mgmt/client/main.py`
- 客户端配置：使用主机的IP地址

**选项B：虚拟机作为服务器，主机作为客户端**
- 虚拟机：运行 `python student_mgmt/server/app.py`
- 主机：运行 `python student_mgmt/client/main.py`
- 客户端配置：使用虚拟机的IP地址

### 步骤3：获取IP地址并测试
按照方案一的步骤获取IP地址并测试连接。

---

## 🌐 方案三：局域网内测试

如果有多台设备在同一局域网（WiFi或以太网），可以：

1. **设备A**：运行服务器，获取IP地址（如 `192.168.1.100`）
2. **设备B**：运行客户端，配置服务器地址为设备A的IP
3. 按照方案一的步骤进行测试

---

## 🔍 故障排查

### 问题1：客户端无法连接服务器

**检查清单：**
1. ✅ 服务器是否正在运行？
2. ✅ 服务器IP地址是否正确？
3. ✅ 防火墙是否允许5000端口？
4. ✅ 两台机器是否在同一网络？
5. ✅ 能否ping通服务器IP？

**测试命令：**
```bash
# 在客户端机器上
ping <服务器IP>
telnet <服务器IP> 5000  # 测试端口是否开放
```

### 问题2：连接超时

**可能原因：**
- 防火墙阻止连接
- 网络不通
- 服务器未监听 `0.0.0.0`

**解决方法：**
1. 检查服务器是否使用 `host="0.0.0.0"`
2. 检查防火墙规则
3. 尝试在服务器上临时关闭防火墙测试

### 问题3：数据库连接问题

如果服务器端报数据库连接错误，检查：
1. MySQL是否在服务器机器上运行？
2. `student_mgmt/server/config.py` 中的数据库配置是否正确？
3. 数据库是否允许远程连接（如果需要）？

---

## 📝 测试记录模板

### 测试环境
- **服务器机器**：
  - 操作系统：___________
  - IP地址：___________
  - Python版本：___________
  
- **客户端机器**：
  - 操作系统：___________
  - IP地址：___________
  - Python版本：___________

### 测试步骤
1. [ ] 服务器启动成功
2. [ ] 客户端配置服务器IP
3. [ ] 网络连通性测试（ping）
4. [ ] 端口连通性测试（telnet/curl）
5. [ ] 客户端登录测试
6. [ ] 功能测试（增删改查等）

### 测试结果
- 登录功能：✅ / ❌
- 数据查询：✅ / ❌
- 数据修改：✅ / ❌
- 其他功能：✅ / ❌

---

## 🎯 快速测试脚本

### 服务器端测试脚本
创建 `student_mgmt/server/test_server.py`：
```python
import socket

def get_local_ip():
    """获取本机IP地址"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

if __name__ == "__main__":
    print(f"服务器IP地址: {get_local_ip()}")
    print(f"请在客户端配置: http://{get_local_ip()}:5000")
```

### 客户端连接测试脚本
创建 `student_mgmt/client/test_connection.py`：
```python
import requests
import sys

# 从配置文件读取服务器地址
try:
    from config import SERVER_URL
except ImportError:
    SERVER_URL = "http://127.0.0.1:5000"

def test_connection():
    """测试与服务器的连接"""
    try:
        print(f"正在测试连接到: {SERVER_URL}")
        response = requests.get(f"{SERVER_URL}/api/login", timeout=5)
        print(f"✅ 连接成功！状态码: {response.status_code}")
        return True
    except requests.exceptions.ConnectionError:
        print(f"❌ 连接失败：无法连接到服务器 {SERVER_URL}")
        print("请检查：")
        print("1. 服务器是否正在运行？")
        print("2. 服务器IP地址是否正确？")
        print("3. 防火墙是否允许5000端口？")
        return False
    except Exception as e:
        print(f"❌ 连接失败：{e}")
        return False

if __name__ == "__main__":
    if test_connection():
        sys.exit(0)
    else:
        sys.exit(1)
```

---

## 📸 演示截图建议

为了证明远程访问功能，建议截图：

1. **服务器端**：
   - 服务器启动日志（显示监听 `0.0.0.0:5000`）
   - 服务器机器的IP地址（`ipconfig` 或 `ifconfig`）

2. **客户端**：
   - 客户端配置文件（显示远程服务器IP）
   - 客户端成功登录界面
   - 客户端执行操作（查询、修改数据等）

3. **网络验证**：
   - 两台机器的IP地址对比
   - ping测试结果
   - 端口连通性测试

---

## 💡 提示

1. **开发阶段**：可以使用虚拟机快速测试
2. **演示阶段**：使用两台实际机器更有说服力
3. **如果只有一台机器**：可以使用手机热点，让两台设备连接同一热点进行测试
4. **云服务器**：如果有云服务器，也可以使用云服务器作为服务器端进行测试

