#!/usr/bin/env python3
"""
客户端连接测试脚本
用于测试客户端是否能连接到服务器
"""
import requests
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 从配置文件读取服务器地址
try:
    from client.config import SERVER_URL
except ImportError:
    try:
        # 尝试从utils/api_client导入
        from client.utils.api_client import SERVER_URL
    except ImportError:
        SERVER_URL = "http://127.0.0.1:5000"
        print("⚠️  警告：未找到配置文件，使用默认地址: http://127.0.0.1:5000")

def test_connection():
    """测试与服务器的连接"""
    print("=" * 50)
    print("客户端连接测试")
    print("=" * 50)
    print(f"服务器地址: {SERVER_URL}")
    print("正在测试连接...")
    print()
    
    try:
        # 测试基本连接
        response = requests.get(f"{SERVER_URL}/api/login", timeout=5)
        print(f"✅ 连接成功！")
        print(f"   状态码: {response.status_code}")
        print(f"   响应内容: {response.text[:100]}...")
        return True
    except requests.exceptions.ConnectionError:
        print(f"❌ 连接失败：无法连接到服务器 {SERVER_URL}")
        print()
        print("请检查：")
        print("1. 服务器是否正在运行？")
        print("   - 运行: python student_mgmt/server/app.py")
        print("2. 服务器IP地址是否正确？")
        print("   - 检查 client/config.py 中的 SERVER_URL")
        print("3. 防火墙是否允许5000端口？")
        print("   - Windows: 检查防火墙规则")
        print("   - Linux: 检查 ufw 或 firewall-cmd")
        print("4. 两台机器是否在同一网络？")
        print("   - 尝试 ping 服务器IP地址")
        return False
    except requests.exceptions.Timeout:
        print(f"❌ 连接超时：服务器 {SERVER_URL} 响应时间过长")
        print("   可能原因：网络延迟、防火墙阻止、服务器未启动")
        return False
    except Exception as e:
        print(f"❌ 连接失败：{type(e).__name__}: {e}")
        return False

def test_ping(host):
    """测试网络连通性（ping）"""
    import platform
    import subprocess
    
    print(f"\n测试网络连通性 (ping {host})...")
    
    # 从URL中提取主机名
    if "://" in host:
        host = host.split("://")[1].split(":")[0]
    
    try:
        # 根据操作系统选择ping命令
        param = '-n' if platform.system().lower() == 'windows' else '-c'
        result = subprocess.run(
            ['ping', param, '3', host],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            print("✅ 网络连通性测试通过")
            return True
        else:
            print("❌ 网络连通性测试失败")
            print(result.stdout)
            return False
    except Exception as e:
        print(f"⚠️  无法执行ping测试: {e}")
        return None

if __name__ == "__main__":
    success = test_connection()
    
    # 如果连接失败，尝试ping测试
    if not success and "://" in SERVER_URL:
        host = SERVER_URL.split("://")[1].split(":")[0]
        if host not in ["127.0.0.1", "localhost"]:
            test_ping(host)
    
    print("\n" + "=" * 50)
    if success:
        print("✅ 测试通过！可以启动客户端程序了")
        sys.exit(0)
    else:
        print("❌ 测试失败！请检查上述问题后重试")
        sys.exit(1)

