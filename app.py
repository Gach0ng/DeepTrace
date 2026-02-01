import streamlit as st
import pandas as pd
import psycopg2
import hanlp
import re
import time
from datetime import datetime
from streamlit_agraph import agraph, Node, Edge, Config
import plotly.express as px

# ==========================================
# 1. 系统配置
# ==========================================
st.set_page_config(
    page_title="DeepTrace | 情报线索分析系统",
    layout="wide",
    page_icon="🦅",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
        header, footer, #MainMenu {visibility: hidden;}
        .block-container {
            padding-top: 2rem !important;
            padding-left: 2rem !important;
            padding-right: 2rem !important;
            max-width: 100% !important;
        }
        .filter-container {
            background-color: #ffffff;
            border-bottom: 2px solid #f0f2f6;
            padding: 15px 10px 10px 10px;
            margin-bottom: 20px;
            position: sticky;
            top: 0;
            z-index: 999;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        }
        div[data-testid="stMetric"] {
            background-color: #f8fafc;
            border: 1px solid #e2e8f0;
            padding: 15px;
            border-radius: 8px;
        }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 数据库配置
# ==========================================
DB_CONFIG = {
    'dbname': 'Test',
    'user': 'postgres',
    'password': 'root',
    'host': 'localhost',
    'port': '5432'
}


def get_db_conn():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception:
        return None


# ==========================================
# 3. 核心逻辑 (NLP & DB Init)
# ==========================================
@st.cache_resource
def load_nlp_model():
    try:
        with st.spinner('正在加载 NLP 神经元网络...'):
            tok = hanlp.load(hanlp.pretrained.tok.COARSE_ELECTRA_SMALL_ZH)
            ner = hanlp.load(hanlp.pretrained.ner.MSRA_NER_ELECTRA_SMALL_ZH)
        return tok, ner
    except:
        return None, None


def init_db_structure():
    conn = get_db_conn()
    if not conn: return
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS t_clues (
                id SERIAL PRIMARY KEY, source_email VARCHAR(150), batch_no VARCHAR(100),
                send_time TIMESTAMP, content TEXT, subject VARCHAR(255), recorder VARCHAR(100),
                remarks TEXT, original_file VARCHAR(255), process_status SMALLINT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, org VARCHAR(200)
            );
        """)
        cur.execute("ALTER TABLE t_clues ADD COLUMN IF NOT EXISTS org VARCHAR(200);")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS t_entities (
                id SERIAL PRIMARY KEY, name VARCHAR(200) NOT NULL, type VARCHAR(50) NOT NULL,
                UNIQUE(name, type)
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS t_relations (
                clue_id INT REFERENCES t_clues(id), entity_id INT REFERENCES t_entities(id),
                PRIMARY KEY (clue_id, entity_id)
            );
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"DB Init Error: {e}")


tok, ner = load_nlp_model()
init_db_structure()


# ==========================================
# 4. 数据管道
# ==========================================
def save_excel_to_db(uploaded_file):
    conn = get_db_conn()
    if not conn: return 0
    try:
        df = pd.read_excel(uploaded_file)
        col_map = {
            '来源邮箱': 'source_email', '发件人': 'source_email', '邮箱': 'source_email',
            '批次': 'batch_no', '收发日期': 'send_time', '时间': 'send_time',
            '邮件内容': 'content', '正文': 'content', '邮件名': 'subject', '标题': 'subject', '主题': 'subject',
            '记录人': 'recorder', '备注': 'remarks', '原件名': 'original_file', '机构': 'org'
        }
        df.rename(columns=col_map, inplace=True)
        cur = conn.cursor()
        count = 0
        for _, row in df.iterrows():
            send_time = row.get('send_time') if pd.notna(row.get('send_time')) else datetime.now()
            cur.execute("""
                INSERT INTO t_clues (source_email, batch_no, send_time, content, subject, recorder, remarks, original_file, process_status, org)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0, %s)
            """, (
                row.get('source_email'), row.get('batch_no'), send_time,
                row.get('content'), row.get('subject'), row.get('recorder'),
                row.get('remarks'), row.get('original_file'), row.get('org')
            ))
            count += 1
        conn.commit()
        conn.close()
        get_org_options.clear()
        get_time_options_by_org.clear()
        get_analytics_data.clear()
        return count
    except Exception:
        return 0


def run_analysis_pipeline():
    if not tok or not ner: return 0
    conn = get_db_conn()
    if not conn: return 0
    cur = conn.cursor()
    cur.execute("SELECT id, content, subject, source_email FROM t_clues WHERE process_status = 0")
    rows = cur.fetchall()
    if not rows:
        conn.close()
        return 0

    processed_count = 0
    bar = st.progress(0)
    for i, row in enumerate(rows):
        cid, content, subject, email = row
        text = f"{subject or ''} {content or ''} {email or ''}"
        entities = set()
        try:
            for term, label in ner(tok(text), tasks='ner*'):
                if len(term) > 1 and label in ['PERSON', 'PER', 'ORG', 'ORGANIZATION', 'LOC', 'LOCATION']:
                    std_label = '人名' if label in ['PERSON', 'PER'] else '机构' if label in ['ORG',
                                                                                              'ORGANIZATION'] else '地名'
                    entities.add((term, std_label))
            phones = re.findall(r'(?<!\d)1[3-9]\d{9}(?!\d)', text)
            for p in phones: entities.add((p, '手机号'))

            for name, etype in entities:
                cur.execute(
                    "INSERT INTO t_entities (name, type) VALUES (%s, %s) ON CONFLICT (name, type) DO UPDATE SET name=EXCLUDED.name RETURNING id",
                    (name, etype))
                eid = cur.fetchone()[0]
                cur.execute("INSERT INTO t_relations (clue_id, entity_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                            (cid, eid))
            cur.execute("UPDATE t_clues SET process_status = 1 WHERE id = %s", (cid,))
        except:
            cur.execute("UPDATE t_clues SET process_status = -1 WHERE id = %s", (cid,))
        processed_count += 1
        bar.progress((i + 1) / len(rows))
    conn.commit()
    conn.close()
    get_analytics_data.clear()
    return processed_count


# ==========================================
# 5. 数据查询 (Cache)
# ==========================================
@st.cache_data(ttl=600)
def get_org_options():
    conn = get_db_conn()
    if not conn: return ["全部机构"]
    try:
        df = pd.read_sql("SELECT DISTINCT org FROM t_clues WHERE org IS NOT NULL AND org != '' ORDER BY org", conn)
        conn.close()
        return ["全部机构"] + df['org'].tolist()
    except:
        return ["全部机构"]


# 恢复：根据机构筛选时间字符串列表
@st.cache_data(ttl=600)
def get_time_options_by_org(selected_org):
    conn = get_db_conn()
    if not conn: return ["全部时间"]
    try:
        sql = "SELECT DISTINCT TO_CHAR(send_time, 'YYYY-MM-DD') as d FROM t_clues WHERE send_time IS NOT NULL"
        params = []
        if selected_org != "全部机构":
            sql += " AND org = %s"
            params.append(selected_org)
        sql += " ORDER BY d DESC"
        df = pd.read_sql(sql, conn, params=params)
        conn.close()
        return ["全部时间"] + df['d'].tolist()
    except:
        return ["全部时间"]


@st.cache_data(ttl=300)
def get_analytics_data(keyword, org, date_val):
    conn = get_db_conn()
    if not conn: return None

    conditions = ["1=1"]
    params = []

    if org != "全部机构":
        conditions.append("c.org = %s")
        params.append(org)

    # 恢复：精确匹配某一天 或 全部时间
    if date_val != "全部时间":
        conditions.append("TO_CHAR(c.send_time, 'YYYY-MM-DD') = %s")
        params.append(date_val)

    if keyword:
        conditions.append("(c.content LIKE %s OR c.subject LIKE %s OR e.name LIKE %s)")
        wildcard = f'%{keyword}%'
        params.extend([wildcard, wildcard, wildcard])

    where_clause = " AND ".join(conditions)
    data = {}

    try:
        sql_clues = f"""
            SELECT DISTINCT c.id, c.subject, c.send_time, c.org, c.source_email, c.content
            FROM t_clues c
            LEFT JOIN t_relations r ON c.id = r.clue_id
            LEFT JOIN t_entities e ON r.entity_id = e.id
            WHERE {where_clause}
            ORDER BY c.send_time DESC LIMIT 300
        """
        data['clues'] = pd.read_sql(sql_clues, conn, params=params)

        if not data['clues'].empty:
            ids = tuple(data['clues']['id'].tolist())
            if len(ids) == 1: ids = (ids[0], ids[0])

            sql_ent = f"""
                SELECT e.name, e.type, COUNT(*) as weight
                FROM t_entities e
                JOIN t_relations r ON e.id = r.entity_id
                WHERE r.clue_id IN {ids}
                GROUP BY e.name, e.type
                ORDER BY weight DESC LIMIT 100
            """
            data['entities'] = pd.read_sql(sql_ent, conn)

            top_ids = tuple(data['clues']['id'].head(50).tolist())
            if len(top_ids) == 1: top_ids = (top_ids[0], top_ids[0])
            sql_rel = f"""
                SELECT r.clue_id, e.id as eid, e.name, e.type 
                FROM t_relations r JOIN t_entities e ON r.entity_id = e.id 
                WHERE r.clue_id IN {top_ids} LIMIT 500
            """
            data['relations'] = pd.read_sql(sql_rel, conn)
        else:
            data['entities'] = pd.DataFrame()
            data['relations'] = pd.DataFrame()

        conn.close()
        return data
    except Exception:
        conn.close()
        return None


def get_node_detail(node_id):
    conn = get_db_conn()
    if not conn or not node_id: return None
    cur = conn.cursor()
    info = {}
    try:
        if node_id.startswith("MAIL_"):
            cid = node_id.split("_")[1]
            cur.execute("SELECT subject, send_time, source_email, org, content FROM t_clues WHERE id=%s", (cid,))
            row = cur.fetchone()
            if row:
                info = {
                    "type": "mail", "title": row[0],
                    "meta": [("📅 时间", str(row[1])[:19]), ("🏢 机构", row[3]), ("📧 发件人", row[2])],
                    "body": row[4]
                }
        elif node_id.startswith("ENT_"):
            eid = node_id.split("_")[1]
            cur.execute("SELECT name, type FROM t_entities WHERE id=%s", (eid,))
            row = cur.fetchone()
            if row:
                info = {"type": "entity", "title": row[0], "meta": [("🏷️ 类型", row[1])], "body": None}
    except:
        pass
    conn.close()
    return info


# ==========================================
# 6. 前端 UI 构建
# ==========================================
st.title("🦅 DeepTrace | 情报线索分析系统")

# --- A. 数据管理区 ---
with st.expander("📂 数据管理中心 (展开/收起)", expanded=True):
    col_admin1, col_admin2 = st.columns([1, 1])
    with col_admin1:
        st.markdown("#### 📥 线索入库")
        up_file = st.file_uploader("上传 Excel 文件", type="xlsx", label_visibility="collapsed")
        if up_file and st.button("确认导入", type="primary"):
            n = save_excel_to_db(up_file)
            if n:
                st.success(f"成功入库 {n} 条！")
                time.sleep(1)
                st.rerun()

    with col_admin2:
        st.markdown("#### 🧠 智能分析状态")
        pending_count = 0
        conn_check = get_db_conn()
        if conn_check:
            try:
                curr = conn_check.cursor()
                curr.execute("SELECT COUNT(*) FROM t_clues WHERE process_status = 0")
                pending_count = curr.fetchone()[0]
            except:
                pass
            finally:
                conn_check.close()

        if pending_count > 0:
            st.warning(f"⚠️ {pending_count} 条线索待分析")
            if st.button(f"🚀 立即运行 AI 分析 ({pending_count})", type="primary", use_container_width=True):
                with st.spinner("正在提取实体关系..."):
                    n = run_analysis_pipeline()
                st.success(f"完成！新增 {n} 组关系")
                time.sleep(1)
                st.rerun()
        else:
            st.success("✅ 系统就绪")
            if st.button("🔄 强制重扫"):
                run_analysis_pipeline()
                st.rerun()

# --- B. 悬浮筛选条 (恢复 SelectBox) ---
st.markdown('<div class="filter-container">', unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns([1.5, 1.5, 3, 1])

with c1:
    org_list = get_org_options()
    sel_org = st.selectbox("🏢 归属机构", org_list)

with c2:
    # 恢复：下拉选择时间
    time_list = get_time_options_by_org(sel_org)
    sel_time = st.selectbox("📅 时间节点", time_list)

with c3:
    search_keyword = st.text_input("🔍 全局侦查", placeholder="输入线索内容 / 人名 / 邮箱...")

with c4:
    st.write("")
    st.write("")
    start_search = st.button("🚀 开始侦查", use_container_width=True, type="primary")

st.markdown('</div>', unsafe_allow_html=True)

# --- C. 数据加载 ---
if 'selected_node_id' not in st.session_state:
    st.session_state.selected_node_id = None
if 'analytics_data' not in st.session_state:
    st.session_state.analytics_data = None

if start_search or st.session_state.analytics_data is None:
    with st.spinner("正在构建情报网络..."):
        st.session_state.analytics_data = get_analytics_data(search_keyword, sel_org, sel_time)
        st.session_state.selected_node_id = None

data_bundle = st.session_state.analytics_data
df_clues = data_bundle['clues'] if data_bundle else pd.DataFrame()
df_ents = data_bundle['entities'] if data_bundle else pd.DataFrame()
df_rels = data_bundle.get('relations', pd.DataFrame()) if data_bundle else pd.DataFrame()

if df_clues.empty:
    st.info("👋 暂无数据，请检查筛选条件。")
    st.stop()

# 核心指标
m1, m2, m3, m4 = st.columns(4)
m1.metric("命中线索", f"{len(df_clues)}")
m2.metric("涉及实体", f"{len(df_ents)}")
if not df_clues.empty:
    times = pd.to_datetime(df_clues['send_time'])
    m3.metric("时间范围", f"{times.min():%m-%d} ~ {times.max():%m-%d}")
    top_u = df_clues['source_email'].mode()[0] if not df_clues['source_email'].empty else "N/A"
    m4.metric("核心人物", str(top_u)[:15] + ".." if len(str(top_u)) > 15 else str(top_u))

st.markdown("---")

tab_dash, tab_graph, tab_time, tab_ent = st.tabs(["📊 统计看板", "🕸️ 关联侦查", "📅 时序分析", "👥 实体明细"])

with tab_dash:
    c1, c2 = st.columns(2)
    with c1:
        st.caption("发件人活跃度 TOP10")
        if not df_clues.empty:
            df_top = df_clues['source_email'].value_counts().reset_index().head(10)
            df_top.columns = ['email', 'count']
            st.plotly_chart(px.bar(df_top, x='count', y='email', orientation='h'), use_container_width=True)
    with c2:
        st.caption("实体关键词分布")
        if not df_ents.empty:
            st.plotly_chart(px.treemap(df_ents, path=['type', 'name'], values='weight'), use_container_width=True)

# === 核心修改部分：增强图谱配置，确保居中显示 ===
with tab_graph:
    cg1, cg2 = st.columns([3, 1])
    with cg1:
        st.markdown("#### 交互式图谱")
        nodes, edges = [], []
        exist_ids = set()

        if not df_clues.empty:
            # 优先展示前 30 条线索，保证性能
            for _, row in df_clues.head(30).iterrows():
                nid = f"MAIL_{row['id']}"
                if nid not in exist_ids:
                    label = row['subject'][:6] + ".." if row['subject'] and len(row['subject']) > 6 else "无题"
                    nodes.append(
                        Node(id=nid, label=label, size=25, color="#3B82F6", shape="square", title=row['subject']))
                    exist_ids.add(nid)

            if not df_rels.empty:
                for _, r in df_rels.iterrows():
                    mnid = f"MAIL_{r['clue_id']}"
                    enid = f"ENT_{r['eid']}"
                    # 仅添加与现有线索关联的实体
                    if mnid in exist_ids:
                        if enid not in exist_ids:
                            color = "#F59E0B" if r['type'] == '人名' else "#10B981" if r[
                                                                                           'type'] == '地名' else "#8B5CF6"
                            nodes.append(Node(id=enid, label=r['name'], size=15, color=color, shape="dot"))
                            exist_ids.add(enid)
                        edges.append(Edge(source=mnid, target=enid, color="#E5E7EB"))

        # 核心修改：使用详细的物理引擎配置来确保图谱稳定和居中
        config = Config(
            width="100%",  # 宽度自适应容器
            height=700,    # 固定高度 (整数)，防止塌陷
            directed=True,
            nodeHighlightBehavior=True,
            highlightColor="#FCA5A5",
            collapsible=False,
            # 关键配置：启用适应视图和物理稳定化
            fit=True,
            physics={
                "enabled": True,
                "stabilization": {
                    "enabled": True,
                    "iterations": 1000, # 预计算1000次布局
                    "fit": True,        # 稳定后强制适应视图
                    "updateInterval": 50,
                    "onlyDynamicEdges": False,
                },
                # 调整斥力参数，让节点散开，避免重叠
                "barnesHut": {
                    "gravitationalConstant": -3000,
                    "centralGravity": 0.3,
                    "springLength": 95,
                    "springConstant": 0.04,
                    "damping": 0.09,
                    "avoidOverlap": 0.1
                },
                "minVelocity": 0.75
            }
        )

        # 修复：移除 key 参数
        if nodes:
            selected_id = agraph(nodes=nodes, edges=edges, config=config)
            if selected_id:
                st.session_state.selected_node_id = selected_id
        else:
            st.warning("当前筛选条件下无关联节点")

    with cg2:
        st.markdown("#### 详情面板")
        with st.container(border=True):
            curr_id = st.session_state.selected_node_id
            if curr_id:
                details = get_node_detail(curr_id)
                if details:
                    st.caption(details['type'].upper())
                    st.markdown(f"**{details['title']}**")
                    st.divider()
                    for k, v in details['meta']:
                        st.write(f"**{k}:** {v}")
                    if details['body']:
                        st.markdown("---")
                        st.text_area("内容摘要", details['body'], height=300)
            else:
                st.info("👈 点击左侧节点查看")

# === 保持：折线图 (Line Chart) ===
with tab_time:
    st.markdown("#### 📅 邮件流量趋势")
    if not df_clues.empty:
        df_chart = df_clues.copy()
        df_chart['day'] = pd.to_datetime(df_chart['send_time']).dt.date
        df_grouped = df_chart.groupby(['day', 'org']).size().reset_index(name='count')

        fig_line = px.line(
            df_grouped,
            x='day',
            y='count',
            color='org',
            markers=True,
            labels={'day': '日期', 'count': '邮件数量', 'org': '机构'},
            title="每日线索数量变化趋势"
        )
        fig_line.update_layout(hovermode="x unified")
        st.plotly_chart(fig_line, use_container_width=True)

        st.markdown("#### 数据明细")
        st.dataframe(df_clues[['send_time', 'org', 'source_email', 'subject']], use_container_width=True)

with tab_ent:

    st.dataframe(df_ents, use_container_width=True)
