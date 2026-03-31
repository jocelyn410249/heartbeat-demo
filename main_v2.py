import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time
import json
import os
from datetime import datetime
from streamlit_folium import st_folium
import folium
from folium.plugins import Draw

# ==================== 页面配置 ====================
st.set_page_config(layout="wide", page_title="无人机地面站 (新)")
st.sidebar.title("导航")
page = st.sidebar.radio("功能页面", ["航线规划", "飞行监控"])

# ==================== 初始化 session_state ====================
if "point_a" not in st.session_state:
    # 南京科技职业学院附近坐标 (GCJ-02)
    st.session_state.point_a = (32.2322, 118.749)
    st.session_state.point_b = (32.2343, 118.749)
if "coord_system" not in st.session_state:
    st.session_state.coord_system = "GCJ-02 (高德/百度)"
if "heartbeat_data" not in st.session_state:
    st.session_state.heartbeat_data = []
if "last_received_time" not in st.session_state:
    st.session_state.last_received_time = time.time()

# 障碍物多边形数据（GeoJSON 格式）
OBSTACLE_FILE = "obstacle_config.json"  # 保存到程序同目录
if "obstacle_geojson" not in st.session_state:
    if os.path.exists(OBSTACLE_FILE):
        with open(OBSTACLE_FILE, "r", encoding="utf-8") as f:
            st.session_state.obstacle_geojson = json.load(f)
    else:
        st.session_state.obstacle_geojson = {"type": "FeatureCollection", "features": []}

# ==================== 障碍物持久化函数 ====================
def save_obstacles():
    with open(OBSTACLE_FILE, "w", encoding="utf-8") as f:
        json.dump(st.session_state.obstacle_geojson, f, indent=2)
    st.success(f"障碍物已保存到 {OBSTACLE_FILE}")

def load_obstacles():
    if os.path.exists(OBSTACLE_FILE):
        with open(OBSTACLE_FILE, "r", encoding="utf-8") as f:
            st.session_state.obstacle_geojson = json.load(f)
        st.success("障碍物加载成功")
    else:
        st.warning("没有找到保存的障碍物文件")

def clear_obstacles():
    st.session_state.obstacle_geojson = {"type": "FeatureCollection", "features": []}
    st.success("已清除所有障碍物")

# ==================== 卫星地图（含多边形圈选）====================
def draw_satellite_map():
    """显示高德卫星图，支持多边形绘制，并显示已保存的障碍物"""
    center_lat = (st.session_state.point_a[0] + st.session_state.point_b[0]) / 2
    center_lon = (st.session_state.point_a[1] + st.session_state.point_b[1]) / 2

    # 高德卫星图（GCJ-02 坐标系）
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=15,
        tiles='https://webst01.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}',
        attr='高德地图',
        name='卫星图'
    )

    # 添加 A、B 点标记
    folium.Marker(
        location=st.session_state.point_a,
        popup='起点 A',
        icon=folium.Icon(color='green', icon='info-sign')
    ).add_to(m)
    folium.Marker(
        location=st.session_state.point_b,
        popup='终点 B',
        icon=folium.Icon(color='red', icon='info-sign')
    ).add_to(m)

    # 绘制已保存的多边形障碍物
    for feature in st.session_state.obstacle_geojson.get("features", []):
        if feature["geometry"]["type"] == "Polygon":
            folium.GeoJson(
                feature,
                style_function=lambda x: {'color': 'orange', 'weight': 3, 'fillOpacity': 0.3},
                name='障碍物'
            ).add_to(m)

    # 添加绘图控件（仅允许多边形）
    Draw(
        export=True,
        filename='obstacle.geojson',
        position='topleft',
        draw_options={
            'polygon': True,
            'polyline': False,
            'rectangle': False,
            'circle': False,
            'marker': False,
            'circlemarker': False
        },
        edit_options={'edit': True, 'remove': True}
    ).add_to(m)

    # 获取绘制数据
    output = st_folium(m, width=800, height=500, returned_objects=['last_active_drawing'])

    # 处理新绘制的多边形
    if output and 'last_active_drawing' in output and output['last_active_drawing']:
        drawing = output['last_active_drawing']
        if drawing and drawing.get('geometry') and drawing['geometry']['type'] == 'Polygon':
            new_feature = {
                "type": "Feature",
                "geometry": drawing['geometry'],
                "properties": {"name": f"障碍物_{len(st.session_state.obstacle_geojson['features'])+1}"}
            }
            st.session_state.obstacle_geojson["features"].append(new_feature)
            st.rerun()

# ==================== 心跳监控（与原版相同）====================
def heartbeat_monitor():
    st.subheader("飞行监控")
    st.session_state.last_received_time = time.time()  # 重置计时起点

    data = st.session_state.heartbeat_data
    placeholder = st.empty()
    chart_placeholder = st.empty()

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

        if current_time - st.session_state.last_received_time > 3:
            st.error("连接超时！")
        else:
            st.session_state.last_received_time = current_time

        time.sleep(1)
    st.success("演示结束")

# ==================== 页面路由 ====================
if page == "航线规划":
    st.header("航线规划")
    st.markdown("### 坐标系统：GCJ-02 (高德/百度)")

    # 坐标输入（与原版一致）
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("起点 A")
        lat_a = st.number_input("纬度", value=st.session_state.point_a[0], step=0.0001, format="%.6f", key="lat_a")
        lon_a = st.number_input("经度", value=st.session_state.point_a[1], step=0.0001, format="%.6f", key="lon_a")
        if st.button("设置A点"):
            st.session_state.point_a = (lat_a, lon_a)
            st.success("A点已设置")
    with col2:
        st.subheader("终点 B")
        lat_b = st.number_input("纬度", value=st.session_state.point_b[0], step=0.0001, format="%.6f", key="lat_b")
        lon_b = st.number_input("经度", value=st.session_state.point_b[1], step=0.0001, format="%.6f", key="lon_b")
        if st.button("设置B点"):
            st.session_state.point_b = (lat_b, lon_b)
            st.success("B点已设置")

    st.slider("设定飞行高度 (m)", 0, 200, 50, key="flight_height")

    # 障碍物管理工具栏
    st.markdown("### 障碍物圈选")
    col_btn1, col_btn2, col_btn3 = st.columns(3)
    with col_btn1:
        if st.button("💾 保存障碍物"):
            save_obstacles()
    with col_btn2:
        if st.button("📂 从文件加载"):
            load_obstacles()
    with col_btn3:
        if st.button("🗑️ 清除全部"):
            clear_obstacles()

    # 显示卫星地图
    draw_satellite_map()
    st.caption("提示：点击左侧绘图工具绘制多边形（障碍物），绘制后自动保存到当前会话。点击「保存障碍物」可永久保存到文件。")

else:
    heartbeat_monitor()
