import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import os
import json
from datetime import datetime

# ==========================================
# ⚙️ 0. 系统配置
# ==========================================
st.set_page_config(page_title="策 · 结构化战略看板", page_icon="🛡️", layout="wide")

# 数据文件路径（支持本地和云端）
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
US_DATA_FILE = os.path.join(DATA_DIR, "us_data.csv")
CN_DATA_FILE = os.path.join(DATA_DIR, "cn_data.csv")
EMAIL_CONFIG_FILE = os.path.join(DATA_DIR, "email_config.json")

# 确保数据目录存在
os.makedirs(DATA_DIR, exist_ok=True)

# 邮件配置
EMAIL_RECIPIENT = "xuxingtong1688@gmail.com"

# ==========================================
# 💾 数据保存和加载函数
# ==========================================
def save_data(df, filepath):
    """保存数据到CSV文件"""
    try:
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        return True
    except Exception as e:
        st.error(f"保存数据失败: {e}")
        return False

def load_data(filepath, default_data):
    """从CSV文件加载数据，如果文件不存在则返回默认数据"""
    try:
        # 先将默认数据转换为 DataFrame（如果还不是的话）
        default_df = pd.DataFrame(default_data) if not isinstance(default_data, pd.DataFrame) else default_data.copy()
        
        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            df = pd.read_csv(filepath, encoding='utf-8-sig')
            # 确保列名匹配且数据不为空
            if not df.empty and list(df.columns) == list(default_df.columns):
                # 确保数据类型正确
                for col in df.columns:
                    if col in default_df.columns:
                        df[col] = df[col].astype(default_df[col].dtype, errors='ignore')
                return df
        return default_df
    except Exception as e:
        # 只在首次加载时显示警告，避免重复提示
        if 'data_load_warning_shown' not in st.session_state:
            st.warning(f"加载数据失败，使用默认数据: {e}")
            st.session_state['data_load_warning_shown'] = True
        return pd.DataFrame(default_data) if not isinstance(default_data, pd.DataFrame) else default_data

def check_and_save(edited_df, session_key, filepath, data_name):
    """检查数据是否变化并自动保存"""
    try:
        # 初始化保存状态
        if f'{session_key}_saved_hash' not in st.session_state:
            st.session_state[f'{session_key}_saved_hash'] = None
        
        # 确保 edited_df 是有效的 DataFrame
        if edited_df.empty or not isinstance(edited_df, pd.DataFrame):
            return False
        
        # 计算当前数据的哈希值（使用字符串表示）
        current_hash = str(edited_df.values.tolist())
        
        # 如果数据发生变化，保存
        if current_hash != st.session_state[f'{session_key}_saved_hash']:
            if save_data(edited_df, filepath):
                st.session_state[f'{session_key}_saved_hash'] = current_hash
                st.toast(f"✅ {data_name}数据已自动保存", icon="💾")
                return True
        return False
    except Exception:
        # 静默失败，避免影响用户体验
        return False

# ==========================================
# 🔔 浏览器通知提醒功能（无需配置）
# ==========================================
def show_browser_notification(alert_data, market_type="美股"):
    """显示浏览器通知（无需配置）"""
    try:
        # 检查是否已发送过相同的提醒（避免重复发送）
        alert_key = f"alert_shown_{market_type}_{alert_data.get('资产一级分类', '')}_{datetime.now().strftime('%Y%m%d')}"
        if alert_key in st.session_state:
            return False
        
        status = alert_data.get('状态', '')
        if '🔴' not in status and '🟠' not in status:
            return False  # 正常状态不发送通知
        
        # 判断是买入还是卖出信号
        if '🔴' in status:
            action = "🔴 买入信号"
            urgency = "紧急"
        else:
            action = "🟠 卖出信号"
            urgency = "重要"
        
        # 构建通知内容
        title = f"⚠️ {market_type}警戒提醒"
        body = f"{alert_data.get('资产一级分类', '未知')} - {action}\n当前比例: {alert_data.get('当前比例', 0):.2f}%"
        
        # 使用 Streamlit 的 JavaScript 显示浏览器通知
        notification_js = f"""
        <script>
        if ("Notification" in window) {{
            if (Notification.permission === "granted") {{
                new Notification("{title}", {{
                    body: "{body}",
                    icon: "🛡️",
                    tag: "{alert_key}",
                    requireInteraction: true
                }});
            }} else if (Notification.permission !== "denied") {{
                Notification.requestPermission().then(function (permission) {{
                    if (permission === "granted") {{
                        new Notification("{title}", {{
                            body: "{body}",
                            icon: "🛡️",
                            tag: "{alert_key}",
                            requireInteraction: true
                        }});
                    }}
                }});
            }}
        }}
        </script>
        """
        
        st.components.v1.html(notification_js, height=0)
        
        # 标记已发送，避免重复
        st.session_state[alert_key] = True
        return True
        
    except Exception:
        return False

def check_and_show_alerts(alerts_df, market_type="美股"):
    """检查警戒线并显示浏览器通知"""
    try:
        for _, row in alerts_df.iterrows():
            status = str(row.get('状态', ''))
            # 只对异常状态显示通知
            if '🔴' in status or '🟠' in status:
                alert_data = row.to_dict()
                show_browser_notification(alert_data, market_type)
    except Exception:
        pass

# 样式：给预警表上色
def highlight_alert(val, min_val, max_val):
    if val < min_val:
        return 'color: #D32F2F; font-weight: bold;' # 深红 (买入)
    elif val > max_val:
        return 'color: #F57C00; font-weight: bold;' # 橙色 (卖出)
    else:
        return 'color: #2E7D32; font-weight: bold;' # 绿色 (正常)

# 获取价格
@st.cache_data(ttl=900)
def fetch_price(ticker):
    """获取股票/ETF价格，失败返回0.0"""
    try:
        if "CASH" in ticker: 
            return 1.0
        ticker_obj = yf.Ticker(ticker)
        data = ticker_obj.history(period="1d")
        if data.empty or len(data) == 0:
            return 0.0
        price = data['Close'].iloc[-1]
        # 确保返回的是有效的数值
        if pd.notna(price) and price > 0:
            return float(price)
        return 0.0
    except Exception:
        # 静默失败，返回0.0
        return 0.0

# 汇率
@st.cache_data(ttl=3600)
def get_exchange_rate():
    """获取美元对人民币汇率"""
    try:
        ticker = yf.Ticker("CNY=X")
        # 尝试获取最近1天的数据
        data = ticker.history(period="1d")
        if not data.empty and len(data) > 0:
            rate = data['Close'].iloc[-1]
            if pd.notna(rate) and rate > 0:
                return float(rate)
        
        # 如果1天数据失败，尝试获取5天数据
        data = ticker.history(period="5d")
        if not data.empty and len(data) > 0:
            rate = data['Close'].iloc[-1]
            if pd.notna(rate) and rate > 0:
                return float(rate)
        
        # 如果还是失败，尝试使用 info 方法
        info = ticker.info
        if 'regularMarketPrice' in info and info['regularMarketPrice']:
            return float(info['regularMarketPrice'])
    except Exception as e:
        # 静默失败，不显示警告（避免每次刷新都显示）
        pass
    
    # 默认汇率（如果所有方法都失败）
    return 7.25

usd_cny = get_exchange_rate()

# ==========================================
# 🇺🇸 1. 美股数据 (分级结构)
# ==========================================
# 示例数据（首次使用时，用户需要输入自己的真实持仓）
US_INIT_DATA = [
    # --- 权益类 (Stock) ---
    {"大类": "Stock (权益)", "名称": "标普500", "代码": "SPY", "持有数量": 0, "手动价格": None},
    {"大类": "Stock (权益)", "名称": "全美市场", "代码": "VTI", "持有数量": 0, "手动价格": None},
    # --- 长债类 (Bond) ---
    {"大类": "Bond (长债)", "名称": "20年美债", "代码": "TLT", "持有数量": 0, "手动价格": None},
    {"大类": "Bond (长债)", "名称": "抗通胀债", "代码": "TIP", "持有数量": 0, "手动价格": None},
    # --- 现金类 (Cash) ---
    {"大类": "Cash (现金)", "名称": "短债(SHV)", "代码": "SHV", "持有数量": 0, "手动价格": None},
    {"大类": "Cash (现金)", "名称": "美元余额", "代码": "CASH_USD", "持有数量": 1, "手动价格": 0.0},
    # --- 黄金类 (Gold) ---
    {"大类": "Gold (黄金)", "名称": "黄金GLD", "代码": "GLD", "持有数量": 0, "手动价格": None},
    # --- 卫星类 (Satellite) ---
    {"大类": "Satellite (卫星)", "名称": "谷歌GOOG", "代码": "GOOG", "持有数量": 0, "手动价格": None},
]

# ==========================================
# 🇨🇳 2. A股数据 (分级结构 - 重点修正)
# ==========================================
# 示例数据（首次使用时，用户需要输入自己的真实持仓）
CN_INIT_DATA = [
    # --- 权益类 (Stock) ---
    {"大类": "Stock (权益)", "名称": "易方达300(场外)", "代码": "110020", "持有数量": 0, "手动价格": None},
    {"大类": "Stock (权益)", "名称": "300ETF(场内)", "代码": "510300.SS", "持有数量": 0, "手动价格": None},
    
    # --- 长债类 (Bond) - 三债合一 ---
    {"大类": "Bond (长债)", "名称": "10年长债", "代码": "511260.SS", "持有数量": 0, "手动价格": None},
    {"大类": "Bond (长债)", "名称": "政金债", "代码": "511520.SS", "持有数量": 0, "手动价格": None},
    {"大类": "Bond (长债)", "名称": "30年长债", "代码": "511090.SS", "持有数量": 0, "手动价格": None},
    
    # --- 现金类 (Cash) - 货基+现金合一 ---
    {"大类": "Cash (现金)", "名称": "银华日利(货基)", "代码": "511880.SS", "持有数量": 0, "手动价格": None},
    {"大类": "Cash (现金)", "名称": "人民币余额", "代码": "CASH_CNY", "持有数量": 1, "手动价格": 0.0},
    
    # --- 黄金类 (Gold) ---
    {"大类": "Gold (黄金)", "名称": "华安黄金(场外)", "代码": "000216", "持有数量": 0, "手动价格": None},
    {"大类": "Gold (黄金)", "名称": "黄金ETF(场内)", "代码": "518880.SS", "持有数量": 0, "手动价格": None},
    
    # --- 卫星类 (Satellite) ---
    {"大类": "Satellite (卫星)", "名称": "恒瑞医药", "代码": "600276.SS", "持有数量": 0, "手动价格": None},
    {"大类": "Satellite (卫星)", "名称": "迈瑞医疗", "代码": "300760.SZ", "持有数量": 0, "手动价格": None},
]

# ==========================================
# 🧮 核心算法：分级聚合 (Tiered Aggregation)
# ==========================================
def process_tiered_data(df_input, currency_symbol):
    total_val = 0
    
    # 1. 存储结构： Category -> {Total: 0, Items: []}
    grouped_data = {}
    
    # 初始化5大类
    categories = ["Stock (权益)", "Bond (长债)", "Gold (黄金)", "Cash (现金)", "Satellite (卫星)"]
    for cat in categories:
        grouped_data[cat] = {"Total": 0, "Items": []}

    # 2. 遍历计算详细数据
    for index, row in df_input.iterrows():
        try:
            cat = row['大类']
            code = str(row['代码']) if pd.notna(row['代码']) else ""
            shares = float(row['持有数量']) if pd.notna(row['持有数量']) else 0.0
            manual = float(row['手动价格']) if pd.notna(row['手动价格']) else None
            
            # 价格获取逻辑
            if manual is not None and manual > 0:
                price = manual
            elif "CASH" in code: # 纯现金行，若没填手动价，默认1
                price = 1.0 
            else:
                price = fetch_price(code)
            
            # 确保价格和数量都是有效数值
            if not isinstance(price, (int, float)) or price < 0:
                price = 0.0
            if not isinstance(shares, (int, float)) or shares < 0:
                shares = 0.0
                
            # 市值计算
            if "CASH" in code:
                # 现金行的"持有数量"通常是1，"手动价格"是总金额
                # 或者"持有数量"是金额，"手动价格"是1
                # 兼容逻辑：如果价格是1，市值=数量；如果价格很大，市值=价格*数量
                # 为了简单，假设用户在"手动价格"填总金额，数量为1
                if manual is not None and manual > 10: 
                    market_val = manual 
                    price = 1.0 # 归一化展示
                else:
                    market_val = shares * price
            else:
                market_val = shares * price
        except Exception:
            # 如果某一行数据有问题，跳过这一行
            continue

        total_val += market_val
        
        # 归类
        if cat in grouped_data:
            grouped_data[cat]["Total"] += market_val
            grouped_data[cat]["Items"].append(f"{row['名称']}: {currency_symbol}{market_val:,.0f}")
    
    if total_val == 0: total_val = 1
    
    # 3. 生成预警表 (Alert Table)
    alert_rows = []
    
    # 阈值设定
    CORE_TARGET = 21.25 # 85% / 4
    CORE_MIN, CORE_MAX = 16.25, 26.25
    
    SAT_TARGET = 15.0
    SAT_MIN, SAT_MAX = 13.0, 17.0
    
    for cat in categories:
        data = grouped_data[cat]
        val = data["Total"]
        pct = (val / total_val) * 100
        
        # 确定目标区间
        if cat == "Satellite (卫星)":
            target, min_v, max_v = SAT_TARGET, SAT_MIN, SAT_MAX
        else:
            target, min_v, max_v = CORE_TARGET, CORE_MIN, CORE_MAX
            
        # 状态判断
        status = "✅ 正常"
        if pct < min_v: status = "🔴 过低 (买入)"
        elif pct > max_v: status = "🟠 过高 (卖出)"
        
        # 生成详细构成字符串
        composition_str = " | ".join(data["Items"])
        
        alert_rows.append({
            "资产一级分类": cat,
            "二级构成 (明细)": composition_str, # 这里展示分级内容
            "总市值": val,
            "当前比例": pct,
            "目标": target,
            "下限": min_v,
            "上限": max_v,
            "状态": status
        })
        
    return pd.DataFrame(alert_rows), total_val

# ==========================================
# 🖥️ 界面渲染
# ==========================================

# 移动端优化 - 添加到主屏幕支持
st.markdown("""
<style>
@media (max-width: 768px) {
    .main .block-container {
        padding: 1rem;
    }
    h1 {
        font-size: 1.5rem;
    }
    h2 {
        font-size: 1.3rem;
    }
    h3 {
        font-size: 1.1rem;
    }
}
</style>
""", unsafe_allow_html=True)

st.title("🛡️ 策 (Ce) · 结构化战略驾驶舱")
st.markdown(f"**当前汇率:** 1 USD = {usd_cny:.2f} CNY")

# 浏览器通知设置侧边栏
with st.sidebar:
    st.header("🔔 提醒设置")
    
    # 请求浏览器通知权限
    if 'notification_permission_requested' not in st.session_state:
        st.session_state['notification_permission_requested'] = False
    
    notification_enabled = st.checkbox("启用浏览器通知", value=True, 
                                       help="当资产比例超出警戒线时，会在浏览器中显示通知")
    
    if notification_enabled:
        st.info("💡 首次使用需要授权浏览器通知权限")
        
        # 请求通知权限的JavaScript
        if st.button("🔔 授权通知权限"):
            st.session_state['notification_permission_requested'] = True
            st.success("✅ 请在浏览器弹出的对话框中点击'允许'")
        
        st.markdown("---")
        st.markdown("""
        **使用说明：**
        - ✅ 无需配置邮箱，简单方便
        - 🔔 当资产比例超出警戒线时自动弹出通知
        - 📱 即使不在当前标签页也能收到提醒
        - 🔕 可在浏览器设置中关闭通知
        """)
        
        # 自动请求通知权限的脚本
        if notification_enabled:
            request_permission_js = """
            <script>
            if ("Notification" in window && Notification.permission === "default") {
                Notification.requestPermission();
            }
            </script>
            """
            st.components.v1.html(request_permission_js, height=0)

st.markdown("---")

# ------------------------------------------
# 🇺🇸 美股模块
# ------------------------------------------
st.header("🇺🇸 美股体系 (US Market)")

# 加载美股数据（首次加载或从文件加载）
if 'us_data_v2' not in st.session_state:
    st.session_state.us_data_v2 = load_data(US_DATA_FILE, US_INIT_DATA)
    # 初始化保存哈希值
    st.session_state['us_data_saved_hash'] = str(st.session_state.us_data_v2.values.tolist())

with st.expander("📝 展开/编辑美股持仓", expanded=False):
    edited_us = st.data_editor(
        st.session_state.us_data_v2,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "手动价格": st.column_config.NumberColumn(format="$%.2f", help="现金请直接在此填总金额"),
            "大类": st.column_config.SelectboxColumn(options=["Stock (权益)", "Bond (长债)", "Gold (黄金)", "Cash (现金)", "Satellite (卫星)"])
        },
        key="us_editor"
    )
    
    # 检测数据变化并自动保存
    if not edited_us.equals(st.session_state.us_data_v2):
        st.session_state.us_data_v2 = edited_us.copy()
        check_and_save(edited_us, 'us_data', US_DATA_FILE, '美股')

us_alerts, us_total = process_tiered_data(edited_us, "$")

# 检查并显示浏览器通知
check_and_show_alerts(us_alerts, "美股")

# 美股展示
c1, c2 = st.columns([1, 3])
c1.metric("美股总资产", f"${us_total:,.0f}")

st.subheader("🚦 战略平衡表 (分级监控)")
st.dataframe(
    us_alerts.style.format({
        "总市值": "${:,.0f}", "当前比例": "{:.2f}%", "目标": "{:.2f}%", "下限": "{:.2f}%", "上限": "{:.2f}%"
    }).apply(lambda x: [f"background-color: {'#ffcccc' if '🔴' in x['状态'] or '🟠' in x['状态'] else '#e8f5e9'}" for i in x], axis=1),
    column_config={
        "二级构成 (明细)": st.column_config.TextColumn(width="medium", help="该分类下的具体资产")
    },
    use_container_width=True
)

st.markdown("---")

# ------------------------------------------
# 🇨🇳 A股模块 (核心关注点)
# ------------------------------------------
st.header("🇨🇳 A股体系 (CN Market)")

# 加载A股数据（首次加载或从文件加载）
if 'cn_data_v2' not in st.session_state:
    loaded_data = load_data(CN_DATA_FILE, CN_INIT_DATA)
    st.session_state.cn_data_v2 = loaded_data
    # 初始化保存哈希值
    st.session_state['cn_data_saved_hash'] = str(st.session_state.cn_data_v2.values.tolist())
    
    # 如果是首次使用（数据文件不存在），显示提示
    if not os.path.exists(CN_DATA_FILE):
        st.info("💡 **首次使用提示**：请在下方编辑区域输入你的真实持仓数据，数据会自动保存。")

with st.expander("📝 展开/编辑A股持仓", expanded=False):
    edited_cn = st.data_editor(
        st.session_state.cn_data_v2,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "手动价格": st.column_config.NumberColumn(format="¥%.2f", help="现金或场外基金请直接在此填金额/净值"),
            "大类": st.column_config.SelectboxColumn(options=["Stock (权益)", "Bond (长债)", "Gold (黄金)", "Cash (现金)", "Satellite (卫星)"])
        },
        key="cn_editor"
    )
    
    # 检测数据变化并自动保存
    if not edited_cn.equals(st.session_state.cn_data_v2):
        st.session_state.cn_data_v2 = edited_cn.copy()
        check_and_save(edited_cn, 'cn_data', CN_DATA_FILE, 'A股')

cn_alerts, cn_total = process_tiered_data(edited_cn, "¥")

# 检查并显示浏览器通知
check_and_show_alerts(cn_alerts, "A股")

# A股展示
k1, k2 = st.columns([1, 3])
k1.metric("A股总资产", f"¥{cn_total:,.0f}")

st.subheader("🚦 战略平衡表 (分级监控)")
st.info("💡 **分级说明**：长债类已自动合并(10年+政金+30年)；现金类已自动合并(货币基金+余额)。")

st.dataframe(
    cn_alerts.style.format({
        "总市值": "¥{:,.0f}", "当前比例": "{:.2f}%", "目标": "{:.2f}%", "下限": "{:.2f}%", "上限": "{:.2f}%"
    }).apply(lambda x: [f"background-color: {'#ffcccc' if '🔴' in x['状态'] or '🟠' in x['状态'] else '#e8f5e9'}" for i in x], axis=1),
    column_config={
        "二级构成 (明细)": st.column_config.TextColumn(width="large", help="此处展示归并前的详细资产")
    },
    use_container_width=True
)

# ------------------------------------------
# ⚔️ 战术看板 (恒瑞/迈瑞)
# ------------------------------------------
st.subheader("⚔️ 卫星战术执行 (Tactical Action)")

# 重新获取价格用于战术板
def get_price_for_tactical(df, code_key):
    row = df[df['代码'] == code_key]
    if row.empty: return 0
    # 优先取手动，没有则自动
    manual = row.iloc[0]['手动价格']
    if pd.notna(manual) and manual > 0: return manual
    return fetch_price(code_key)

hr_price = get_price_for_tactical(edited_cn, "600276.SS")
mr_price = get_price_for_tactical(edited_cn, "300760.SZ")

col_a, col_b = st.columns(2)
with col_a:
    st.markdown("#### 💊 恒瑞医药 (600276)")
    st.metric("当前价格", f"¥{hr_price:.2f}")
    if hr_price > 0:
        if hr_price <= 54.9: st.error("💀 **止损触发 (54.9)**")
        elif hr_price <= 57.8: st.error("⚡ **买入信号 (57.8)**")
        else: st.success("✅ 观察区")

with col_b:
    st.markdown("#### 🏥 迈瑞医疗 (300760)")
    st.metric("当前价格", f"¥{mr_price:.2f}")
    if mr_price > 0:
        if mr_price <= 180: st.error("💀 **止损触发 (180)**")
        else: st.success("✅ 持有区")

# ==========================================
# 💰 全球汇总
# ==========================================
st.markdown("---")
grand_total = (us_total * usd_cny) + cn_total
st.metric("🌍 全球总资产 (折合RMB)", f"¥{grand_total:,.0f}")