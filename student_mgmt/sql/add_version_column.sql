-- 为 scores 表添加版本字段（用于乐观锁）
-- 如果版本字段已存在，此脚本会安全跳过

USE student_mgmt;

-- 检查并添加版本字段
SET @dbname = DATABASE();
SET @tablename = "scores";
SET @columnname = "version";
SET @preparedStatement = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE
      (TABLE_SCHEMA = @dbname)
      AND (TABLE_NAME = @tablename)
      AND (COLUMN_NAME = @columnname)
  ) > 0,
  "SELECT 'Column version already exists.'",
  CONCAT("ALTER TABLE ", @tablename, " ADD COLUMN ", @columnname, " INT DEFAULT 1 NOT NULL AFTER exam_date")
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

-- 为现有记录设置初始版本号
UPDATE scores SET version = 1 WHERE version IS NULL OR version = 0;

