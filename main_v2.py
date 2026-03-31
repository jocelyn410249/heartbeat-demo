import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time
import json
import os
import math
from datetime import datetime
from streamlit_folium import st_folium
import folium
from folium.plugins import Draw

# ==================== 页面配置 ====================
st.set_page_config(layout="wide", page_title="无人机地面站")
st.sidebar.title("导航")
page = st.sidebar.radio("功能页面", ["航线规划", "飞行监控"])

# ==================== 坐标转换函数 ====================
# GCJ-02 转 WGS-84（简化算法，精度足够）
def gcj02_to_wgs84(lat, lng):
    """GCJ-02 坐标转 WGS-84 坐标"""
    a = 6378245.0
    ee = 0.00669342162296594323
    def transform_lat(x, y):
        ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
        ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
        ret += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
        ret += (160.0 * math.sin(y / 12.0 * math.pi) + 320 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
        return ret
    def transform_lng(x, y):
        ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
        ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
        ret += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
        ret += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
        return ret
    dlat = transform_lat(lng - 105.0, lat - 35.0)
    dlng = transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * math.pi
    magic = math.sin(radlat)
    magic = 1 - ee * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * math.pi)
    dlng = (dlng * 180.0) / (a / sqrtmagic * math.cos(radlat) * math.pi)
    wgs_lat = lat - dlat
    wgs_lng = lng - dlng
    return wgs_lat, wgs_lng

def wgs84_to_gcj02(lat, lng):
    """WGS-84 坐标转 GCJ-02 坐标"""
    a = 6378245.0
    ee = 0.00669342162296594323
    def transform_lat(x, y):
        ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
        ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
        ret += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
        ret += (160.0 * math.sin(y / 12.0 * math.pi) + 320 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
        return ret
    def transform_lng(x, y):
        ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
        ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
        ret += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
        ret += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
        return ret
    dlat = transform_lat(lng - 105.0, lat - 35.0)
    dlng = transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * math.pi
    magic = math.sin(radlat)
    magic = 1 - ee * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * math.pi)
    dlng = (dlng * 180.0) / (a / sqrtmagic * math.cos(radlat) * math.pi)
    gcj_lat = lat + dlat
    gcj_lng = lng + dlng
    return gcj_lat, gcj_lng

# ==================== 初始化 session_state ====================
if "point_a_gcj" not in st.session_state:
    # 南京科技职业学院附近坐标 (GCJ-02)
    st.session_state.point_a_gcj = (32.2322, 118.749)   # (lat, lng)
    st.session_state.point_b_gcj = (32.2343, 118.749)
if "coord_system" not in st.session_state:
    st.session_state.coord_system = "GCJ-02 (高德/百度)"
if "heartbeat_data" not in st.session_state:
    st.session_state.heartbeat_data = []
if "last_received_time" not in st.session_state:
    st.session_state.last_received_time = time.time()

# 障碍物配置文件路径（与程序同目录）
OBSTACLE_FILE = "obstacle_config.json"
if "obstacle_geojson" not in st.session_state:
    if os.path.exists(OBSTACLE_FILE):
        with open(OBSTACLE_FILE, "r", encoding="utf-8") as f:
            st.session_state.obstacle_geojson = json.load(f)
    else:
        st.session_state.obstacle_geojson = {"type": "FeatureCollection", "features": []}

# ==================== 障碍物持久化函数 ====================
def save_obstacles():
    """将当前多边形（GCJ-02 格式）保存到 JSON 文件"""
    with open(OBSTACLE_FILE, "w", encoding="utf-8") as f:
        json.dump(st.session_state.obstacle_geojson, f, indent=2)
    st.success(f"障碍物已保存到 {OBSTACLE_FILE}")

def load_obstacles():
    """从 JSON 文件加载多边形（GCJ-02）"""
    if os.path.exists(OBSTACLE_FILE):
        with open(OBSTACLE_FILE, "r", encoding="utf-8") as f:
            st.session_state.obstacle_geojson = json.load(f)
        st.success("障碍物加载成功")
    else:
        st.warning("没有找到保存的障碍物文件")

def clear_obstacles():
    """清除所有多边形"""
    st.session_state.obstacle_geojson = {"type": "FeatureCollection", "features": []}
    st.success("已清除所有障碍物")

# ==================== 转换 GeoJSON 多边形从 GCJ-02 到 WGS-84 ====================
def convert_geojson_gcj_to_wgs(geojson):
    """深拷贝并转换 GeoJSON 中所有坐标从 GCJ-02 到 WGS-84"""
    import copy
    new_geojson = copy.deepcopy(geojson)
    for feature in new_geojson.get("features", []):
        geom = feature["geometry"]
        if geom["type"] == "Polygon":
            # 转换外环和所有内环
            for ring in geom["coordinates"]:
                for point in ring:
                    lat, lng = point[1], point[0]   # GeoJSON 存储 [lng, lat]
                    wgs_lat, wgs_lng = gcj02_to_wgs84(lat, lng)
                    point[0] = wgs_lng
                    point[1] = wgs_lat
    return new_geojson

# ==================== 卫星地图（含多边形圈选）====================
def draw_osm_map():
    """显示 OpenStreetMap 底图（WGS-84），支持多边形绘制，坐标已转换"""
    # 将 A、B 点从 GCJ-02 转换为 WGS-84 用于显示
    a_wgs = gcj02_to_wgs84(st.session_state.point_a_gcj[0], st.session_state.point_a_gcj[1])
    b_wgs = gcj02_to_wgs84(st.session_state.point_b_gcj[0], st.session_state.point_b_gcj[1])

    center_lat = (a_wgs[0] + b_wgs[0]) / 2
    center_lon = (a_wgs[1] + b_wgs[1]) / 2

    # 创建 OSM 地图
    m = folium.Map(location=[center_lat, center_lon], zoom_start=15, tiles='OpenStreetMap')

    # 添加 A、B 点标记（已转换坐标）
    folium.Marker(
        location=[a_wgs[0], a_wgs[1]],
        popup='起点 A (WGS-84)',
        icon=folium.Icon(color='green', icon='info-sign')
    ).add_to(m)
    folium.Marker(
        location=[b_wgs[0], b_wgs[1]],
        popup='终点 B (WGS-84)',
        icon=folium.Icon(color='red', icon='info-sign')
    ).add_to(m)

    # 将存储的障碍物（GCJ-02）转换为 WGS-84 并显示
    wgs_obstacles = convert_geojson_gcj_to_wgs(st.session_state.obstacle_geojson)
    for feature in wgs_obstacles.get("features", []):
        if feature["geometry"]["type"] == "Polygon":
            folium.GeoJson(
                feature,
                style_function=lambda x: {'color': 'orange', 'weight': 3, 'fillOpacity': 0.3},
                name='障碍物'
            ).add_to(m)

    # 添加绘图控件（允许绘制多边形，返回的坐标是 WGS-84）
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

    # 处理新绘制的多边形（WGS-84 坐标），需转换回 GCJ-02 存储
    if output and 'last_active_drawing' in output and output['last_active_drawing']:
        drawing = output['last_active_drawing']
        if drawing and drawing.get('geometry') and drawing['geometry']['type'] == 'Polygon':
            # 深拷贝并转换坐标 WGS-84 -> GCJ-02
            import copy
            new_feature = copy.deepcopy(drawing)
            # 转换多边形顶点
            for ring in new_feature["geometry"]["coordinates"]:
                for point in ring:
                    lng, lat = point[0], point[1]   # GeoJSON 存储 [lng, lat]
                    gcj_lat, gcj_lng = wgs84_to_gcj02(lat, lng)
                    point[0] = gcj_lng
                    point[1] = gcj_lat
            new_feature["properties"] = {"name": f"障碍物_{len(st.session_state.obstacle_geojson['features'])+1}"}
            st.session_state.obstacle_geojson["features"].append(new_feature)
            st.rerun()

# ==================== 心跳监控（与原版相同）====================
def heartbeat_monitor():
    st.subheader("飞行监控")
    st.session_state.last_received_time = time.time()

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
    st.markdown("### 坐标系统：GCJ-02 (高德/百度) - 地图自动转换至 WGS-84")

    # 坐标输入（GCJ-02 数值）
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("起点 A")
        lat_a = st.number_input("纬度 (GCJ-02)", value=st.session_state.point_a_gcj[0], step=0.0001, format="%.6f", key="lat_a")
        lon_a = st.number_input("经度 (GCJ-02)", value=st.session_state.point_a_gcj[1], step=0.0001, format="%.6f", key="lon_a")
        if st.button("设置A点"):
            st.session_state.point_a_gcj = (lat_a, lon_a)
            st.success("A点已设置")
    with col2:
        st.subheader("终点 B")
        lat_b = st.number_input("纬度 (GCJ-02)", value=st.session_state.point_b_gcj[0], step=0.0001, format="%.6f", key="lat_b")
        lon_b = st.number_input("经度 (GCJ-02)", value=st.session_state.point_b_gcj[1], step=0.0001, format="%.6f", key="lon_b")
        if st.button("设置B点"):
            st.session_state.point_b_gcj = (lat_b, lon_b)
            st.success("B点已设置")

    st.slider("设定飞行高度 (m)", 0, 200, 50, key="flight_height")

    # 障碍物管理工具栏
    st.markdown("### 障碍物配置持久化")
    st.caption(f"配置文件: {os.path.abspath(OBSTACLE_FILE)} | 版本: v12.2 障碍物持久化版")
    col_btn1, col_btn2, col_btn3, col_btn4 = st.columns(4)
    with col_btn1:
        if st.button("💾 保存到文件"):
            save_obstacles()
    with col_btn2:
        if st.button("📂 从文件加载"):
            load_obstacles()
    with col_btn3:
        if st.button("🗑️ 清除全部"):
            clear_obstacles()
    with col_btn4:
        if st.button("🚀 一键部署"):
            save_obstacles()
            st.info("已保存当前配置，应用已就绪。")

    # 下载配置文件按钮
    if os.path.exists(OBSTACLE_FILE):
        with open(OBSTACLE_FILE, "r", encoding="utf-8") as f:
            config_data = f.read()
        st.download_button(
            label="📥 下载配置文件到本地",
            data=config_data,
            file_name="obstacle_config.json",
            mime="application/json"
        )
    else:
        st.info("尚未保存任何配置，请先绘制多边形并点击「保存到文件」。")

    # 显示地图（自动处理坐标转换）
    draw_osm_map()
    st.caption("提示：地图基于 OpenStreetMap（WGS-84），输入的 GCJ-02 坐标已自动转换显示。点击左侧绘图工具绘制多边形（障碍物），绘制后自动保存到当前会话。点击「保存到文件」可永久保存。")

else:
    heartbeat_monitor()
