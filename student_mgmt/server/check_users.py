"""
诊断和修复用户密码脚本
用于检查数据库中的用户密码格式，并修复为正确的哈希格式
"""
import sys
from pathlib import Path

# 兼容直接运行脚本
if __package__ in (None, ""):
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.append(str(project_root))
    from server.models import get_conn
    from werkzeug.security import generate_password_hash, check_password_hash
else:
    from .models import get_conn
    from werkzeug.security import generate_password_hash, check_password_hash

def check_users():
    """检查所有用户的密码格式"""
    print("=" * 60)
    print("检查用户密码格式")
    print("=" * 60)
    
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT user_id, username, password, role FROM users")
        users = cur.fetchall()
        
        if not users:
            print("❌ 数据库中没有用户")
            return
        
        print(f"\n找到 {len(users)} 个用户：\n")
        
        issues = []
        for user in users:
            username = user['username']
            password_hash = user['password']
            role = user['role']
            
            # 检查密码格式
            # Werkzeug 的哈希值通常以 pbkdf2:sha256: 开头
            is_hashed = password_hash.startswith('pbkdf2:sha256:')
            
            print(f"用户: {username} ({role})")
            print(f"  密码格式: {'✅ 已哈希' if is_hashed else '❌ 明文密码'}")
            print(f"  密码值: {password_hash[:50]}...")
            
            if not is_hashed:
                issues.append(user)
            print()
        
        if issues:
            print("=" * 60)
            print(f"发现 {len(issues)} 个用户的密码需要修复")
            print("=" * 60)
            print("\n需要修复的用户：")
            for user in issues:
                print(f"  - {user['username']} ({user['role']})")
            
            print("\n是否要修复这些用户的密码？")
            print("请输入新密码（所有用户将使用相同密码，或按 Ctrl+C 取消）")
            try:
                new_password = input("新密码: ").strip()
                if not new_password:
                    print("❌ 密码不能为空，取消操作")
                    return
                
                confirm = input(f"确认将所有 {len(issues)} 个用户的密码设置为 '{new_password}'? (y/n): ").strip().lower()
                if confirm != 'y':
                    print("❌ 取消操作")
                    return
                
                # 修复密码
                password_hash = generate_password_hash(new_password)
                for user in issues:
                    cur.execute(
                        "UPDATE users SET password=%s WHERE user_id=%s",
                        (password_hash, user['user_id'])
                    )
                    print(f"✅ 已修复用户 {user['username']} 的密码")
                
                conn.commit()
                print(f"\n🎉 成功修复 {len(issues)} 个用户的密码")
                print(f"现在可以使用密码 '{new_password}' 登录这些用户")
            except KeyboardInterrupt:
                print("\n❌ 操作已取消")
        else:
            print("✅ 所有用户的密码格式正确！")
            print("\n如果仍然无法登录，请检查：")
            print("1. 用户名和角色是否匹配")
            print("2. 密码是否正确")
            print("3. 服务器是否正常运行")

def test_login(username, password, role):
    """测试登录"""
    print(f"\n测试登录: {username} / {role}")
    
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=%s AND role=%s", (username, role))
        row = cur.fetchone()
        
        if row is None:
            print(f"❌ 用户不存在或角色不匹配")
            return False
        
        password_hash = row['password']
        is_valid = check_password_hash(password_hash, password)
        
        if is_valid:
            print(f"✅ 密码验证成功！")
            print(f"   user_id: {row['user_id']}")
            print(f"   role: {row['role']}")
            return True
        else:
            print(f"❌ 密码验证失败")
            print(f"   存储的密码哈希: {password_hash[:50]}...")
            return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='检查并修复用户密码')
    parser.add_argument('--test', nargs=3, metavar=('USERNAME', 'PASSWORD', 'ROLE'),
                       help='测试登录（例如: --test student01 123456 student）')
    args = parser.parse_args()
    
    if args.test:
        username, password, role = args.test
        test_login(username, password, role)
    else:
        check_users()

