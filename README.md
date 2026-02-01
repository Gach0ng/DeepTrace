
# 🦅 DeepTrace | 情报线索分析系统

**DeepTrace** 是一个基于 **Streamlit** 构建的轻量级情报线索分析与可视化平台。系统集成了 **HanLP** 自然语言处理能力，能够自动从非结构化文本（如邮件、Excel 记录）中提取人名、地名、机构名及联系方式，并基于力导向图（Force-Directed Graph）构建动态关联网络，帮助分析人员快速发现线索背后的隐藏关系。

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-green.svg)
![Streamlit](https://img.shields.io/badge/streamlit-1.30+-ff4b4b.svg)

## ✨ 核心功能

* **📂 数据导入与管理**: 支持 Excel 文件批量导入线索数据，自动去重与入库。
* **🧠 智能实体提取**: 内置 NLP 管道（基于 Electra 预训练模型），自动提取人名、地名、机构名及手机号。
* **🕸️ 交互式知识图谱**: 基于 `vis.js` 引擎的动态图谱，支持节点拖拽、缩放、高亮关联及详细信息查看。
* **📊 多维统计看板**: 提供时序流量分析、实体词云分布、活跃人物排行等可视化报表。
* **🔍 全局检索**: 支持按机构、时间、关键词（全文检索）的多条件组合筛选。

## 🛠️ 技术栈

### 前端
* **[Streamlit](https://streamlit.io/)**: 核心 Web 框架。
* **[Streamlit-Agraph](https://github.com/ChrisDelClea/streamlit-agraph)**: 基于 React Graph Vis 的图谱渲染组件。
* **[Plotly Express](https://plotly.com/python/)**: 交互式统计图表绘制。

### 后端
* **[PostgreSQL](https://www.postgresql.org/)**: 关系型数据库，存储线索及实体关系。
* **[Psycopg2](https://pypi.org/project/psycopg2/)**: PostgreSQL 数据库适配器。
* **[HanLP](https://github.com/hankcs/HanLP)**: 工业级自然语言处理工具包（NER 命名实体识别）。
* **[Pandas](https://pandas.pydata.org/)**: 数据清洗与处理。

## 🚀 快速开始


### 1. 环境准备

确保您的本地环境已安装 Python 3.8+ 和 PostgreSQL 数据库。

### 2. 克隆项目
```

```bash
git clone [https://github.com/Gach0ng/DeepTrace.git](https://github.com/Gach0ng/DeepTrace.git)
cd DeepTrace

```


### 3. 安装依赖

```bash
pip install -r requirements.txt

```

> **注意**: 首次运行 HanLP 时会自动下载预训练模型（约几百 MB），请保持网络畅通。

### 4. 数据库初始化

1. 创建一个名为 `Test` (或其他名称) 的 PostgreSQL 数据库。
2. 运行项目提供的 SQL 脚本以创建表结构：

```bash
psql -U postgres -d Test -f schema.sql

```

### 5. 配置连接

打开主程序文件（如 `app.py`），找到 `DB_CONFIG` 配置项，修改为您本地的数据库信息：

```python
DB_CONFIG = {
    'dbname': 'Test',
    'user': 'postgres',
    'password': 'your_password',
    'host': 'localhost',
    'port': '5432'
}

```

### 6. 启动系统

```bash
streamlit run app.py

```

浏览器将自动打开 `http://localhost:8501`。

## 📖 使用指南

1. **数据入库**: 点击侧边栏（或顶部折叠面板）的“📂 数据管理中心”，上传符合模板的 Excel 文件。
2. **智能分析**: 导入数据后，系统会检测未处理的线索。点击“🚀 立即运行 AI 分析”，后台将进行实体抽取。
3. **图谱侦查**:
* 在顶部筛选栏选择“归属机构”或“时间节点”。
* 输入关键词进行搜索。
* 点击 **“🚀 开始侦查”** 生成图谱。
* **蓝色方块**: 邮件/线索节点；**彩色圆点**: 实体节点（人名、地名等）。


 **查看详情**: 点击图谱中的任意节点，右侧面板将显示详细的元数据和正文摘要。

## 📁 目录结构

```text
DeepTrace/
├── app.py               # 主应用程序入口
├── schema.sql           # 数据库初始化脚本
├── requirements.txt     # 项目依赖列表
├── README.md            # 项目文档
└── .gitignore           # Git 忽略文件

```

## 📝 依赖

```text
streamlit>=1.30.0
pandas>=2.0.0
psycopg2-binary>=2.9.0
hanlp>=2.1.0b50
streamlit-agraph>=0.0.45
plotly>=5.18.0
openpyxl>=3.1.0

```

## 📄 License

[MIT](https://www.google.com/search?q=LICENSE) © 2024 Gach0ng


**注意事项：**

1. **HanLP 模型下载**：HanLP 在第一次运行时会自动下载 `COARSE_ELECTRA_SMALL_ZH` 等模型文件到本地缓存目录。
2. **数据库安全**：代码中数据库密码是硬编码的 (`'password': 'root'`)。建议将密码改为环境变量读取或占位符，以免泄露敏感信息。
* *修改建议*： `os.getenv('DB_PASSWORD', 'default_pass')`
3. **Excel 模板**：
数据库字段,推荐 Excel 表头,兼容的其他表头 (代码支持),说明
org,机构,(无),重要：用于左侧筛选栏的机构筛选
source_email,发件人,"来源邮箱, 邮箱",显示在统计看板和节点信息中
subject,邮件主题,"邮件名, 标题, 主题",核心：作为图谱中的方形节点显示
content,邮件内容,正文,核心：NLP 将分析此列以提取实体关系
send_time,收发日期,时间,建议格式 YYYY-MM-DD HH:MM:ss
batch_no,批次,(无),用于标记数据批次
recorder,记录人,(无),数据录入人员
remarks,备注,(无),额外说明
original_file,原件名,(无),原始文件名
