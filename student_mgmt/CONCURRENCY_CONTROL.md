# 数据库并发控制机制说明

本文档说明系统中实现的数据库并发控制机制及其使用方法。

## 已实现的并发控制机制

### 1. 数据库连接池

**位置**: `server/models.py`

**功能**:
- 实现了自定义连接池，避免频繁创建/关闭数据库连接
- 支持最小连接数（2）和最大连接数（20）配置
- 自动检测和清理失效连接
- 支持连接超时和空闲超时

**配置参数**:
```python
POOL_MIN_SIZE = 2      # 最小连接数
POOL_MAX_SIZE = 20     # 最大连接数
POOL_IDLE_TIMEOUT = 300  # 空闲连接超时时间（秒）
POOL_TIMEOUT = 10      # 获取连接超时时间（秒）
```

**使用方式**:
```python
from server.models import get_conn

with get_conn() as conn:
    cur = conn.cursor()
    # 执行数据库操作
    cur.execute("SELECT * FROM scores")
```

### 2. 事务隔离级别

**功能**:
- 支持设置不同的事务隔离级别
- 默认使用 MySQL 的 REPEATABLE READ
- 关键操作使用 SERIALIZABLE 确保最高一致性

**使用方式**:
```python
# 使用 REPEATABLE READ（默认）
with get_conn() as conn:
    # 操作...

# 使用 SERIALIZABLE（批量操作）
with get_conn(isolation_level='SERIALIZABLE') as conn:
    # 批量操作...
```

**隔离级别说明**:
- `READ UNCOMMITTED`: 最低隔离级别，可能读到脏数据
- `READ COMMITTED`: 避免脏读，但可能出现不可重复读
- `REPEATABLE READ`: 默认级别，避免脏读和不可重复读
- `SERIALIZABLE`: 最高隔离级别，完全串行化，避免所有并发问题

### 3. 悲观锁（Pessimistic Locking）

**位置**: `server/app.py` - `update_score()` 函数

**功能**:
- 使用 `SELECT ... FOR UPDATE` 锁定要修改的行
- 防止其他事务同时修改同一行数据
- 适用于高冲突场景

**实现示例**:
```python
# 使用悲观锁查询并锁定行
cur.execute("""
    SELECT score_id, score, version
    FROM scores
    WHERE score_id = %s
    FOR UPDATE
""", (score_id,))
```

### 4. 乐观锁（Optimistic Locking）

**位置**: `server/app.py` - `update_score()` 函数

**功能**:
- 使用版本号字段（`version`）检测并发修改
- 更新时检查版本号是否匹配
- 如果版本不匹配，返回 409 Conflict 错误

**数据库迁移**:
运行以下命令为现有数据库添加版本字段：
```bash
python student_mgmt/server/migrate_add_version.py
```

**使用方式**:
```python
# 客户端请求时包含版本号
PUT /api/scores/123
{
    "score": 95,
    "version": 5  # 期望的版本号
}

# 如果版本不匹配，服务器返回：
{
    "status": "error",
    "msg": "数据已被其他用户修改，请刷新后重试",
    "current_version": 6
}
```

### 5. 表级锁（Table Locking）

**位置**: `server/app.py` - `batch_import_scores()` 和 `cleanup_abnormal_scores()` 函数

**功能**:
- 批量操作时使用表级锁（`LOCK TABLES`）
- 防止并发批量操作冲突
- 操作完成后自动释放锁

**实现示例**:
```python
with get_conn(isolation_level='SERIALIZABLE') as conn:
    cur = conn.cursor()
    cur.execute("LOCK TABLES scores WRITE")
    try:
        # 批量操作...
    finally:
        cur.execute("UNLOCK TABLES")
```

## 并发控制策略总结

### 单条记录更新（update_score）
- **悲观锁**: `SELECT ... FOR UPDATE` 锁定行
- **乐观锁**: 版本号检查
- **隔离级别**: `REPEATABLE READ`
- **双重保护**: 确保数据一致性

### 批量导入（batch_import_scores）
- **表级锁**: `LOCK TABLES scores WRITE`
- **隔离级别**: `SERIALIZABLE`
- **版本控制**: 更新时自动增加版本号

### 批量清理（cleanup_abnormal_scores）
- **表级锁**: `LOCK TABLES scores WRITE`
- **隔离级别**: `SERIALIZABLE`
- **悲观锁**: `SELECT ... FOR UPDATE` 锁定要删除的记录

### 查询操作（list_scores, get_teacher_scores）
- **无锁**: 只读操作，不需要锁
- **返回版本号**: 客户端可以用于乐观锁

## 客户端使用建议

### 1. 获取数据时保存版本号
```javascript
// 获取成绩列表
const response = await fetch('/api/scores');
const data = await response.json();
// data.data[0].version 包含版本号
```

### 2. 更新时传递版本号
```javascript
// 更新成绩
const response = await fetch('/api/scores/123', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        score: 95,
        version: currentVersion  // 使用保存的版本号
    })
});

if (response.status === 409) {
    // 版本冲突，提示用户刷新
    alert('数据已被其他用户修改，请刷新后重试');
}
```

### 3. 处理版本冲突
```javascript
if (response.status === 409) {
    const error = await response.json();
    // 显示错误信息
    // 重新获取最新数据
    await refreshData();
}
```

## 性能考虑

1. **连接池**: 减少连接创建开销，提高并发性能
2. **隔离级别**: 
   - 查询操作使用默认级别（REPEATABLE READ）
   - 批量操作使用 SERIALIZABLE（性能较低但一致性最高）
3. **锁粒度**:
   - 单条更新：行级锁（SELECT FOR UPDATE）
   - 批量操作：表级锁（LOCK TABLES）

## 注意事项

1. **版本字段迁移**: 首次使用前必须运行迁移脚本
2. **表级锁**: 批量操作会锁定整个表，避免在高并发时执行
3. **连接池**: 最大连接数限制为 20，高并发场景可能需要调整
4. **错误处理**: 客户端必须正确处理 409 Conflict 错误

## 测试建议

1. **并发更新测试**: 多个用户同时修改同一条成绩
2. **批量操作测试**: 并发执行批量导入和清理操作
3. **连接池测试**: 高并发场景下的连接池表现
4. **版本冲突测试**: 模拟版本冲突场景

## 未来改进方向

1. 分布式锁（Redis）用于多服务器场景
2. 读写分离提高查询性能
3. 更细粒度的锁策略
4. 连接池监控和自动调整

