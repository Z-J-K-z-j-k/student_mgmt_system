#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库迁移脚本：为 scores 表添加 version 字段（乐观锁）
运行此脚本为现有数据库添加版本字段
"""
import sys
from pathlib import Path

# 兼容直接运行脚本
if __package__ in (None, ""):
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.append(str(project_root))
    from server.models import get_conn
else:
    from .models import get_conn

def migrate_add_version():
    """为 scores 表添加 version 字段"""
    print("开始迁移：为 scores 表添加 version 字段...")
    
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            
            # 检查 version 字段是否已存在
            cur.execute("""
                SELECT COUNT(*) as cnt
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'scores'
                  AND COLUMN_NAME = 'version'
            """)
            result = cur.fetchone()
            
            if result and result.get('cnt', 0) > 0:
                print("✅ version 字段已存在，跳过迁移")
                return
            
            # 添加 version 字段
            print("正在添加 version 字段...")
            cur.execute("""
                ALTER TABLE scores
                ADD COLUMN version INT DEFAULT 1 NOT NULL
                AFTER exam_date
            """)
            
            # 为现有记录设置初始版本号
            print("正在为现有记录设置初始版本号...")
            cur.execute("UPDATE scores SET version = 1 WHERE version IS NULL OR version = 0")
            affected_rows = cur.rowcount
            
            conn.commit()
            print(f"✅ 迁移完成！已为 {affected_rows} 条记录设置版本号")
            
    except Exception as e:
        print(f"❌ 迁移失败：{e}")
        raise

if __name__ == "__main__":
    migrate_add_version()

