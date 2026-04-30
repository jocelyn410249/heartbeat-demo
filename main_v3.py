import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time
import json
import os
import math
import copy
from datetime import datetime
from streamlit_folium import st_folium
import folium
from folium.plugins import Draw
from shapely.geometry import Point, Polygon, LineString
import numpy as np

# ==================== 页面配置 ====================
st.set_page_config(layout="wide", page_title="无人机智能地面站")
st.sidebar.title("导航")
page = st.sidebar.radio("功能页面", ["航线规划", "飞行监控"])

# ==================== 坐标转换函数 (GCJ-02 <-> WGS-84) ====================
def gcj02_to_wgs84(lat, lng):
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

# ==================== 初始化 Session State ====================
if "point_a_gcj" not in st.session_state:
    st.session_state.point_a_gcj = (32.2322, 118.749)
    st.session_state.point_b_gcj = (32.2343, 118.749)

if "flight_height" not in st.session_state:
    st.session_state.flight_height = 50   # 飞行高度 (米)
if "safe_radius" not in st.session_state:
    st.session_state.safe_radius = 5.0    # 安全半径 (米)

# 障碍物存储结构: [ {"id": 0, "name": "障碍物1", "height_m": 20, "geojson": {...}, "polygon_wgs": Polygon, ... } ]
if "obstacles_list" not in st.session_state:
    OBSTACLE_FILE = "obstacles_full.json"
    if os.path.exists(OBSTACLE_FILE):
        with open(OBSTACLE_FILE, "r") as f:
            loaded = json.load(f)
            st.session_state.obstacles_list = loaded
    else:
        st.session_state.obstacles_list = []

if "heartbeat_data" not in st.session_state:
    st.session_state.heartbeat_data = []
if "last_received_time" not in st.session_state:
    st.session_state.last_received_time = time.time()

# ==================== 障碍物持久化 ====================
def save_all_obstacles():
    with open("obstacles_full.json", "w") as f:
        json.dump(st.session_state.obstacles_list, f, indent=2)
    st.success("✅ 所有障碍物（含高度）已保存为 obstacles_full.json")

def load_all_obstacles():
    if os.path.exists("obstacles_full.json"):
        with open("obstacles_full.json", "r") as f:
            st.session_state.obstacles_list = json.load(f)
        st.success("✅ 障碍物列表加载成功")
    else:
        st.warning("未找到已保存的障碍物文件")

def clear_all_obstacles():
    st.session_state.obstacles_list = []
    st.success("🗑️ 已清除所有障碍物")

# ==================== 地图与多边形圈选处理 ====================
def process_new_drawing(drawing):
    """处理新绘制的 WGS-84 多边形，转换为 GCJ-02 并存入列表"""
    if not drawing or drawing["geometry"]["type"] != "Polygon":
        return
    # 提取 WGS-84 坐标
    coords_wgs = drawing["geometry"]["coordinates"][0]  # 外环
    # 转换为 GCJ-02
    coords_gcj = []
    for coord in coords_wgs:
        lng, lat = coord[0], coord[1]
        gcj_lat, gcj_lng = wgs84_to_gcj02(lat, lng)
        coords_gcj.append([gcj_lng, gcj_lat])
    # 构造 GeoJSON
    new_feature = {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [coords_gcj]
        },
        "properties": {"name": f"新障碍物_{len(st.session_state.obstacles_list)+1}", "height_m": 10.0}
    }
    # 添加到列表
    new_obstacle = {
        "id": len(st.session_state.obstacles_list),
        "name": new_feature["properties"]["name"],
        "height_m": 10.0,
        "geojson": new_feature
    }
    st.session_state.obstacles_list.append(new_obstacle)
    st.rerun()

def draw_obstacle_map():
    """显示 OSM 地图，支持绘制多边形，并显示现有障碍物"""
    a_wgs = gcj02_to_wgs84(st.session_state.point_a_gcj[0], st.session_state.point_a_gcj[1])
    b_wgs = gcj02_to_wgs84(st.session_state.point_b_gcj[0], st.session_state.point_b_gcj[1])
    center = [(a_wgs[0]+b_wgs[0])/2, (a_wgs[1]+b_wgs[1])/2]

    m = folium.Map(location=center, zoom_start=16, tiles="OpenStreetMap")
    folium.Marker(location=a_wgs, popup="起点 A", icon=folium.Icon(color="green")).add_to(m)
    folium.Marker(location=b_wgs, popup="终点 B", icon=folium.Icon(color="red")).add_to(m)

    # 显示所有障碍物（需转换坐标至 WGS-84）
    for obs in st.session_state.obstacles_list:
        geojson_gcj = obs["geojson"]
        # 转换坐标展示
        coords_gcj = geojson_gcj["geometry"]["coordinates"][0]
        coords_wgs = []
        for coord in coords_gcj:
            lng, lat = coord[0], coord[1]
            wgs_lat, wgs_lng = gcj02_to_wgs84(lat, lng)
            coords_wgs.append([wgs_lng, wgs_lat])
        display_geojson = {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [coords_wgs]},
            "properties": {"name": obs["name"], "height": obs["height_m"]}
        }
        folium.GeoJson(
            display_geojson,
            style_function=lambda x, h=obs["height_m"]: {
                "color": "orange", "weight": 3, "fillOpacity": 0.3,
                "popup": f"高度: {h} m"
            },
            popup=folium.Popup(f"障碍物: {obs['name']}<br>高度: {obs['height_m']} m", max_width=200)
        ).add_to(m)

    Draw(export=True, draw_options={"polygon": True, "polyline": False, "rectangle": False,
                                   "circle": False, "marker": False, "circlemarker": False},
         edit_options={"edit": True, "remove": True}).add_to(m)

    output = st_folium(m, width=800, height=500, returned_objects=["last_active_drawing"])
    if output and output.get("last_active_drawing"):
        process_new_drawing(output["last_active_drawing"])
    return m

# ==================== 航线规划核心算法 ====================
def plan_route(flight_height, safe_radius, strategy):
    """基于 A/B 点、障碍物列表计算航线（飞跃/绕行）"""
    a_wgs = Point(gcj02_to_wgs84(st.session_state.point_a_gcj[0], st.session_state.point_a_gcj[1])[::-1])
    b_wgs = Point(gcj02_to_wgs84(st.session_state.point_b_gcj[0], st.session_state.point_b_gcj[1])[::-1])
    direct_line = LineString([a_wgs, b_wgs])
    waypoints = [a_wgs]

    for obs in st.session_state.obstacles_list:
        # 获取障碍物 WGS-84 多边形
        coords_gcj = obs["geojson"]["geometry"]["coordinates"][0]
        coords_wgs = [Point(gcj02_to_wgs84(lat, lng)[::-1]) for lng, lat in coords_gcj]
        poly_wgs = Polygon(coords_wgs)
        obs_height = obs["height_m"]

        # 检查航线是否需要处理该障碍物
        if direct_line.intersects(poly_wgs):
            if flight_height > obs_height + safe_radius:  # 飞跃
                waypoints.append(Point((a_wgs.x + b_wgs.x)/2, (a_wgs.y + b_wgs.y)/2))  # 简化飞跃路径
            else:  # 绕行
                # 计算绕过点的候选方向
                centroid = poly_wgs.centroid
                vec = np.array([b_wgs.x - a_wgs.x, b_wgs.y - a_wgs.y])
                norm = np.linalg.norm(vec)
                if norm == 0:
                    continue
                vec = vec / norm
                perp = np.array([-vec[1], vec[0]])  # 垂直向量

                # 左右绕行点
                left_point = Point(centroid.x - perp[0]*safe_radius*2, centroid.y - perp[1]*safe_radius*2)
                right_point = Point(centroid.x + perp[0]*safe_radius*2, centroid.y + perp[1]*safe_radius*2)

                # 根据策略选择
                if strategy == "向左绕行":
                    waypoints.append(left_point)
                elif strategy == "向右绕行":
                    waypoints.append(right_point)
                else:  # 最佳航线
                    dist_left = left_point.distance(a_wgs) + left_point.distance(b_wgs)
                    dist_right = right_point.distance(a_wgs) + right_point.distance(b_wgs)
                    waypoints.append(left_point if dist_left < dist_right else right_point)

    waypoints.append(b_wgs)
    return waypoints

def plot_route_on_map(waypoints):
    """在地图上绘制规划好的航线"""
    if not waypoints:
        return
    a_wgs = gcj02_to_wgs84(st.session_state.point_a_gcj[0], st.session_state.point_a_gcj[1])
    b_wgs = gcj02_to_wgs84(st.session_state.point_b_gcj[0], st.session_state.point_b_gcj[1])
    center = [(a_wgs[0]+b_wgs[0])/2, (a_wgs[1]+b_wgs[1])/2]

    m = folium.Map(location=center, zoom_start=16, tiles="OpenStreetMap")
    folium.Marker(location=a_wgs, popup="起点 A", icon=folium.Icon(color="green")).add_to(m)
    folium.Marker(location=b_wgs, popup="终点 B", icon=folium.Icon(color="red")).add_to(m)

    # 绘制航线
    points = [[wp.y, wp.x] for wp in waypoints]
    folium.PolyLine(points, color="blue", weight=4, opacity=0.8, popup="规划航线").add_to(m)

    # 绘制障碍物（同前）
    for obs in st.session_state.obstacles_list:
        coords_gcj = obs["geojson"]["geometry"]["coordinates"][0]
        coords_wgs = []
        for coord in coords_gcj:
            lng, lat = coord[0], coord[1]
            wgs_lat, wgs_lng = gcj02_to_wgs84(lat, lng)
            coords_wgs.append([wgs_lng, wgs_lat])
        folium.GeoJson(
            {"type": "Polygon", "coordinates": [coords_wgs]},
            style_function=lambda x: {"color": "orange", "weight": 2, "fillOpacity": 0.2}
        ).add_to(m)

    st_folium(m, width=800, height=500)

# ==================== 心跳监控 ====================
def heartbeat_monitor():
    st.subheader("📡 飞行监控")
    st.session_state.last_received_time = time.time()
    data = st.session_state.heartbeat_data
    placeholder = st.empty()
    chart_placeholder = st.empty()

    for i in range(1, 11):
        current_time = time.time()
        data.append({"序号": len(data)+1, "时间": datetime.now().strftime("%H:%M:%S"), "接收": 1})
        placeholder.dataframe(pd.DataFrame(data).tail(10))

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=list(range(1, len(data)+1)), y=[1]*len(data), mode='lines+markers'))
        fig.update_layout(title="心跳状态", xaxis_title="序号", yaxis_title="是否接收")
        chart_placeholder.plotly_chart(fig, use_container_width=True)

        if current_time - st.session_state.last_received_time > 3:
            st.error("❌ 连接超时！")
        else:
            st.session_state.last_received_time = current_time
        time.sleep(1)
    st.success("✅ 演示结束")

# ==================== 页面路由 ====================
if page == "航线规划":
    st.header("✈️ 智能航线规划")

    # 参数设置
    col1, col2, col3 = st.columns(3)
    with col1:
        st.session_state.flight_height = st.number_input("🚁 飞行高度 (米)", min_value=5, max_value=200, value=50, step=5)
    with col2:
        st.session_state.safe_radius = st.number_input("🛡️ 安全半径 (米)", min_value=1.0, max_value=50.0, value=5.0, step=1.0)
    with col3:
        strategy = st.selectbox("🔄 绕行策略", ["向左绕行", "向右绕行", "最佳航线"])

    # 坐标输入
    colA, colB = st.columns(2)
    with colA:
        lat_a = st.number_input("起点 A 纬度 (GCJ-02)", value=st.session_state.point_a_gcj[0], format="%.6f")
        lon_a = st.number_input("起点 A 经度 (GCJ-02)", value=st.session_state.point_a_gcj[1], format="%.6f")
        if st.button("📍 设置 A 点"):
            st.session_state.point_a_gcj = (lat_a, lon_a)
    with colB:
        lat_b = st.number_input("终点 B 纬度 (GCJ-02)", value=st.session_state.point_b_gcj[0], format="%.6f")
        lon_b = st.number_input("终点 B 经度 (GCJ-02)", value=st.session_state.point_b_gcj[1], format="%.6f")
        if st.button("📍 设置 B 点"):
            st.session_state.point_b_gcj = (lat_b, lon_b)

    st.divider()
    st.subheader("🗺️ 障碍物圈选与高度配置")

    # 障碍物列表管理
    if st.session_state.obstacles_list:
        st.write("📋 当前障碍物列表")
        for idx, obs in enumerate(st.session_state.obstacles_list):
            col_h1, col_h2, col_h3 = st.columns([3, 2, 1])
            with col_h1:
                st.write(f"**{obs['name']}**")
            with col_h2:
                new_h = st.number_input(f"高度 (m)", value=float(obs["height_m"]), key=f"h_{idx}", step=1.0)
                st.session_state.obstacles_list[idx]["height_m"] = new_h
            with col_h3:
                if st.button("❌ 删除", key=f"del_{idx}"):
                    st.session_state.obstacles_list.pop(idx)
                    st.rerun()
    else:
        st.info("暂无障碍物，请在地图上绘制多边形进行圈选。")

    # 持久化按钮
    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1:
        if st.button("💾 一键保存所有障碍物"):
            save_all_obstacles()
    with col_s2:
        if st.button("📂 加载障碍物"):
            load_all_obstacles()
    with col_s3:
        if st.button("🗑️ 清除全部障碍物"):
            clear_all_obstacles()

    # 绘制地图
    draw_obstacle_map()

    st.divider()
    st.subheader("✈️ 航线生成与展示")
    if st.button("🚀 生成航线"):
        if st.session_state.obstacles_list:
            waypoints = plan_route(st.session_state.flight_height, st.session_state.safe_radius, strategy)
            plot_route_on_map(waypoints)
            st.success("✅ 航线已生成（蓝色线条为规划路径）")
        else:
            st.warning("⚠️ 请先添加障碍物后再生成航线")

else:
    heartbeat_monitor()
