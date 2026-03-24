import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import pydeck as pdk
import time
from datetime import datetime

# 页面配置
st.set_page_config(layout="wide", page_title="无人机地面站")
st.sidebar.title("导航")
page = st.sidebar.radio("功能页面", ["航线规划", "飞行监控"])

# 初始化 session_state
if "point_a" not in st.session_state:
    # 南京科技职业学院附近坐标 (GCJ-02)
    st.session_state.point_a = (32.2322, 118.749)   # (纬度, 经度)
    st.session_state.point_b = (32.2343, 118.749)
    # 预设多个障碍物（纬度, 经度, 高度/米），高度调高让3D效果更明显
    st.session_state.obstacles = [
        (32.2325, 118.7487, 35),
        (32.2329, 118.7485, 45),
        (32.2333, 118.7488, 30),
        (32.2337, 118.7490, 50),
        (32.2339, 118.7493, 40),
    ]
if "running" not in st.session_state:
    st.session_state.running = False
if "heartbeat_data" not in st.session_state:
    st.session_state.heartbeat_data = []
if "last_received_time" not in st.session_state:
    st.session_state.last_received_time = time.time()

def draw_3d_map(point_a, point_b, obstacles):
    """绘制具有显著3D效果的地图（倾斜视角+高柱状障碍物）"""
    # 起点A（绿色球体）
    a_layer = pdk.Layer(
        "ScatterplotLayer",
        data=[{"lat": point_a[0], "lon": point_a[1]}],
        get_position="[lon, lat]",
        get_color="[0, 255, 0, 200]",
        get_radius=100,
        pickable=True,
    )
    # 终点B（红色球体）
    b_layer = pdk.Layer(
        "ScatterplotLayer",
        data=[{"lat": point_b[0], "lon": point_b[1]}],
        get_position="[lon, lat]",
        get_color="[255, 0, 0, 200]",
        get_radius=100,
        pickable=True,
    )
    # 障碍物（橙色高柱，增强3D效果）
    obs_data = [{"lat": o[0], "lon": o[1], "height": o[2]} for o in obstacles]
    obstacle_layer = pdk.Layer(
        "ColumnLayer",
        data=obs_data,
        get_position="[lon, lat]",
        get_elevation="height",
        elevation_scale=80,      # 让柱子更高
        radius=25,               # 让柱子更粗
        get_fill_color="[255, 165, 0, 200]",
        pickable=True,
    )
    # 视图居中，倾斜视角（pitch=60）增强3D感
    center_lat = (point_a[0] + point_b[0]) / 2
    center_lon = (point_a[1] + point_b[1]) / 2
    view_state = pdk.ViewState(
        latitude=center_lat,
        longitude=center_lon,
        zoom=14,          # 适当缩小视野，突出柱子
        pitch=60,         # 大倾斜角，让柱子立体
        bearing=0,
    )
    r = pdk.Deck(
        layers=[a_layer, b_layer, obstacle_layer],
        initial_view_state=view_state,
        tooltip={"text": "高度: {height} m" if "height" in obs_data[0] else "{position}"},
    )
    st.pydeck_chart(r)

def heartbeat_monitor():
    """飞行监控页面：心跳模拟与可视化"""
    st.subheader("飞行监控")
    data = st.session_state.heartbeat_data
    placeholder = st.empty()
    chart_placeholder = st.empty()
    # 模拟10次心跳，可自行调整
    for i in range(1, 11):
        current_time = time.time()
        data.append({
            "序号": len(data) + 1,
            "时间": datetime.now().strftime("%H:%M:%S"),
            "接收": 1
        })
        df = pd.DataFrame(data)
        placeholder.dataframe(df.tail(10))
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=list(range(1, len(data)+1)),
            y=[1]*len(data),
            mode='lines+markers',
            name='心跳状态'
        ))
        fig.update_layout(
            title="心跳序号随时间变化",
            xaxis_title="序号",
            yaxis_title="是否接收"
        )
        chart_placeholder.plotly_chart(fig, use_container_width=True)
        # 掉线检测（模拟3秒未收到则报警）
        if current_time - st.session_state.last_received_time > 3:
            st.error("连接超时！")
        st.session_state.last_received_time = current_time
        time.sleep(1)
    st.success("演示结束")

# 页面跳转
if page == "航线规划":
    st.header("航线规划")
    st.markdown("### 坐标系统：GCJ-02 (高德/百度)")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("起点 A")
        lat_a = st.number_input(
            "纬度", value=st.session_state.point_a[0], step=0.0001, format="%.6f",
            key="lat_a"
        )
        lon_a = st.number_input(
            "经度", value=st.session_state.point_a[1], step=0.0001, format="%.6f",
            key="lon_a"
        )
        if st.button("设置A点"):
            st.session_state.point_a = (lat_a, lon_a)
            st.success("A点已设置")
    with col2:
        st.subheader("终点 B")
        lat_b = st.number_input(
            "纬度", value=st.session_state.point_b[0], step=0.0001, format="%.6f",
            key="lat_b"
        )
        lon_b = st.number_input(
            "经度", value=st.session_state.point_b[1], step=0.0001, format="%.6f",
            key="lon_b"
        )
        if st.button("设置B点"):
            st.session_state.point_b = (lat_b, lon_b)
            st.success("B点已设置")
    st.slider("设定飞行高度 (m)", 0, 200, 50, key="flight_height")
    draw_3d_map(
        st.session_state.point_a,
        st.session_state.point_b,
        st.session_state.obstacles
    )
    st.caption("提示：绿色为起点A，红色为终点B，橙色柱体为障碍物。鼠标拖拽可旋转视角，右键平移，滚轮缩放。")
else:
    heartbeat_monitor()
