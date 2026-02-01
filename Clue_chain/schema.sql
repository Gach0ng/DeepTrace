-- DeepTrace Database Schema
-- Database: PostgreSQL

-- 1. 清理旧表 (如果存在，注意顺序，先删关联表)
DROP TABLE IF EXISTS t_relations;
DROP TABLE IF EXISTS t_entities;
DROP TABLE IF EXISTS t_clues;

-- 2. 创建线索主表 (t_clues)
-- 用于存储原始邮件/线索数据
CREATE TABLE t_clues (
    id SERIAL PRIMARY KEY,                          -- 自增主键
    source_email VARCHAR(150),                      -- 来源邮箱/发件人
    batch_no VARCHAR(100),                          -- 批次号
    send_time TIMESTAMP,                            -- 收发时间
    content TEXT,                                   -- 邮件正文/线索内容
    subject VARCHAR(255),                           -- 邮件标题/主题
    recorder VARCHAR(100),                          -- 记录人
    remarks TEXT,                                   -- 备注信息
    original_file VARCHAR(255),                     -- 原始文件名
    process_status SMALLINT DEFAULT 0,              -- 处理状态: 0-待处理, 1-已分析, -1-失败
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- 入库时间
    org VARCHAR(200)                                -- 归属机构
);

-- 创建 t_clues 的索引以加速查询
CREATE INDEX idx_clues_org ON t_clues(org);
CREATE INDEX idx_clues_send_time ON t_clues(send_time);
CREATE INDEX idx_clues_source_email ON t_clues(source_email);


-- 3. 创建实体表 (t_entities)
-- 用于存储通过 NLP 提取的人名、地名、机构名、手机号等
CREATE TABLE t_entities (
    id SERIAL PRIMARY KEY,          -- 自增主键
    name VARCHAR(200) NOT NULL,     -- 实体名称
    type VARCHAR(50) NOT NULL,      -- 实体类型 (人名, 地名, 机构, 手机号)
    CONSTRAINT t_entities_name_type_key UNIQUE (name, type) -- 联合唯一约束，防止重复存储
);

-- 创建 t_entities 的索引
CREATE INDEX idx_entities_name ON t_entities(name);
CREATE INDEX idx_entities_type ON t_entities(type);


-- 4. 创建关系表 (t_relations)
-- 关联表：连接线索与实体，形成知识图谱边
CREATE TABLE t_relations (
    clue_id INTEGER NOT NULL,
    entity_id INTEGER NOT NULL,
    PRIMARY KEY (clue_id, entity_id), -- 联合主键
    CONSTRAINT t_relations_clue_id_fkey FOREIGN KEY (clue_id) REFERENCES t_clues(id) ON DELETE CASCADE,
    CONSTRAINT t_relations_entity_id_fkey FOREIGN KEY (entity_id) REFERENCES t_entities(id) ON DELETE CASCADE
);

-- 创建 t_relations 的索引
CREATE INDEX idx_relations_clue_id ON t_relations(clue_id);
CREATE INDEX idx_relations_entity_id ON t_relations(entity_id);

-- 注释
COMMENT ON TABLE t_clues IS '线索原始数据表';
COMMENT ON TABLE t_entities IS 'NLP提取实体表';
COMMENT ON TABLE t_relations IS '线索与实体关联关系表';