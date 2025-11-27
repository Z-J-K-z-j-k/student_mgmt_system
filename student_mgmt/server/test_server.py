#!/usr/bin/env python3
"""
服务器端测试脚本
用于获取服务器IP地址，方便客户端配置
"""
import socket

def get_local_ip():
    """获取本机IP地址"""
    try:
        # 创建一个UDP socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # 连接到一个远程地址（不需要实际连接，只是用来获取本地IP）
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        # 如果上述方法失败，尝试获取主机名对应的IP
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            return ip
        except Exception:
            return '127.0.0.1'

def get_all_ips():
    """获取所有网络接口的IP地址"""
    import socket
    ips = []
    hostname = socket.gethostname()
    ips.append(('主机名', hostname))
    
    # 获取所有IP地址
    try:
        for addr_info in socket.getaddrinfo(hostname, None):
            ip = addr_info[4][0]
            if ip not in [item[1] for item in ips]:
                ips.append(('IP地址', ip))
    except Exception:
        pass
    
    # 获取本地IP（用于外部访问）
    local_ip = get_local_ip()
    if local_ip not in [item[1] for item in ips]:
        ips.append(('推荐IP（外部访问）', local_ip))
    
    return ips

if __name__ == "__main__":
    print("=" * 50)
    print("服务器网络信息")
    print("=" * 50)
    
    all_ips = get_all_ips()
    for label, ip in all_ips:
        print(f"{label}: {ip}")
    
    print("\n" + "=" * 50)
    recommended_ip = get_local_ip()
    print(f"推荐客户端配置: http://{recommended_ip}:5000")
    print("=" * 50)
    print("\n提示：")
    print("1. 确保服务器已启动（python student_mgmt/server/app.py）")
    print("2. 确保防火墙允许5000端口的入站连接")
    print("3. 在客户端配置文件中设置 SERVER_URL = \"http://" + recommended_ip + ":5000\"")

