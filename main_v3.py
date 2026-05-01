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

# ==================== 简易几何类（完全替代 shapely）====================
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y
    
    def distance(self, other):
        return math.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)

def point_in_polygon(point, polygon):
    """射线法判断点是否在多边形内"""
    x, y = point.x, point.y
    inside = False
    for i in range(len(polygon)):
        x1, y1 = polygon[i].x, polygon[i].y
        x2, y2 = polygon[(i+1) % len(polygon)].x, polygon[(i+1) % len(polygon)].y
        if ((y1 > y) != (y2 > y)) and (x < (x2 - x1) * (y - y1) / (y2 - y1) + x1):
            inside = not inside
    return inside

def segments_intersect(p1, p2, p3, p4):
    """检测两条线段是否相交"""
    def ccw(A, B, C):
        return (C.y - A.y) * (B.x - A.x) > (B.y - A.y) * (C.x - A.x)
    return (ccw(p1, p3, p4) != ccw(p2, p3, p4)) and (ccw(p1, p2, p3) != ccw(p1, p2, p4))

def line_intersects_polygon(line_start, line_end, polygon):
    """检测线段是否与多边形相交"""
    # 检查线段端点是否在多边形内
    if point_in_polygon(line_start, polygon) or point_in_polygon(line_end, polygon):
        return True
    # 检查线段是否与多边形的任一边相交
    for i in range(len(polygon)):
        p3 = polygon[i]
        p4 = polygon[(i+1) % len(polygon)]
        if segments_intersect(line_start, line_end, p3, p4):
            return True
    return False

# ==================== 坐标转换函数 ====================
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

# ==================== 页面配置 ====================
st.set_page_config(layout="wide", page_title="无人机智能地面站")
st.sidebar.title("导航")
page = st.sidebar.radio("功能页面", ["航线规划", "飞行监控"])

# ==================== 初始化 Session State ====================
if "point_a_gcj" not in st.session_state:
    st.session_state.point_a_gcj = (32.2322, 118.749)
    st.session_state.point_b_gcj = (32.2343, 118.749)

if "flight_height" not in st.session_state:
    st.session_state.flight_height = 50
if "safe_radius" not in st.session_state:
    st.session_state.safe_radius = 5.0

if "obstacles_list" not in st.session_state:
    OBSTACLE_FILE = "obstacles_full.json"
    if os.path.exists(OBSTACLE_FILE):
        with open(OBSTACLE_FILE, "r") as f:
            st.session_state.obstacles_list = json.load(f)
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
    st.success("✅ 所有障碍物已保存")

def load_all_obstacles():
    if os.path.exists("obstacles_full.json"):
        with open("obstacles_full.json", "r") as f:
            st.session_state.obstacles_list = json.load(f)
        st.success("✅ 障碍物加载成功")

def clear_all_obstacles():
    st.session_state.obstacles_list = []
    st.success("🗑️ 已清除所有障碍物")

# ==================== 航线规划核心算法 ====================
def plan_route(flight_height, safe_radius, strategy):
    """航线规划：飞跃/绕行"""
    a_wgs = Point(*gcj02_to_wgs84(st.session_state.point_a_gcj[0], st.session_state.point_a_gcj[1])[::-1])
    b_wgs = Point(*gcj02_to_wgs84(st.session_state.point_b_gcj[0], st.session_state.point_b_gcj[1])[::-1])
    
    waypoints = [a_wgs]
    
    for obs in st.session_state.obstacles_list:
        # 获取障碍物多边形顶点（WGS-84）
        coords_gcj = obs["geojson"]["geometry"]["coordinates"][0]
        polygon_wgs = []
        for coord in coords_gcj:
            lng, lat = coord[0], coord[1]
            wgs_lat, wgs_lng = gcj02_to_wgs84(lat, lng)
            polygon_wgs.append(Point(wgs_lng, wgs_lat))
        
        # 检查是否需要处理该障碍物
        if line_intersects_polygon(a_wgs, b_wgs, polygon_wgs):
            if flight_height > obs["height_m"] + safe_radius:
                # 飞跃
                waypoints.append(Point((a_wgs.x + b_wgs.x)/2, (a_wgs.y + b_wgs.y)/2))
                st.info(f"✈️ {obs['name']}：飞行高度{flight_height}m > 障碍物高度{obs['height_m']}m，选择飞跃")
            else:
                # 绕行
                center_x = sum(p.x for p in polygon_wgs) / len(polygon_wgs)
                center_y = sum(p.y for p in polygon_wgs) / len(polygon_wgs)
                vec_x = b_wgs.x - a_wgs.x
                vec_y = b_wgs.y - a_wgs.y
                norm = math.sqrt(vec_x**2 + vec_y**2)
                if norm > 0:
                    vec_x /= norm
                    vec_y /= norm
                
                perp_x = -vec_y
                perp_y = vec_x
                
                left_point = Point(center_x - perp_x * safe_radius * 2, center_y - perp_y * safe_radius * 2)
                right_point = Point(center_x + perp_x * safe_radius * 2, center_y + perp_y * safe_radius * 2)
                
                if strategy == "向左绕行":
                    waypoints.append(left_point)
                    st.info(f"🔄 {obs['name']}：选择向左绕行")
                elif strategy == "向右绕行":
                    waypoints.append(right_point)
                    st.info(f"🔄 {obs['name']}：选择向右绕行")
                else:
                    dist_left = left_point.distance(a_wgs) + left_point.distance(b_wgs)
                    dist_right = right_point.distance(a_wgs) + right_point.distance(b_wgs)
                    waypoints.append(left_point if dist_left < dist_right else right_point)
                    st.info(f"⭐ {obs['name']}：选择最佳航线")
    
    waypoints.append(b_wgs)
    return waypoints

# ==================== 地图绘制函数 ====================
def draw_obstacle_map():
    """显示地图并处理多边形绘制"""
    a_wgs = gcj02_to_wgs84(st.session_state.point_a_gcj[0], st.session_state.point_a_gcj[1])
    b_wgs = gcj02_to_wgs84(st.session_state.point_b_gcj[0], st.session_state.point_b_gcj[1])
    center = [(a_wgs[0]+b_wgs[0])/2, (a_wgs[1]+b_wgs[1])/2]

    m = folium.Map(location=center, zoom_start=16, tiles="OpenStreetMap")
    folium.Marker(location=a_wgs, popup="起点 A", icon=folium.Icon(color="green")).add_to(m)
    folium.Marker(location=b_wgs, popup="终点 B", icon=folium.Icon(color="red")).add_to(m)

    # 显示现有障碍物
    for obs in st.session_state.obstacles_list:
        coords_gcj = obs["geojson"]["geometry"]["coordinates"][0]
        coords_wgs = []
        for coord in coords_gcj:
            lng, lat = coord[0], coord[1]
            wgs_lat, wgs_lng = gcj02_to_wgs84(lat, lng)
            coords_wgs.append([wgs_lng, wgs_lat])
        
        folium.Polygon(
            locations=[[lat, lng] for lng, lat in coords_wgs],
            color="orange",
            weight=3,
            fillOpacity=0.3,
            popup=f"{obs['name']}<br>高度: {obs['height_m']} m"
        ).add_to(m)

    Draw(export=True, draw_options={"polygon": True}, edit_options={"edit": True, "remove": True}).add_to(m)
    
    output = st_folium(m, width=800, height=500, returned_objects=["last_active_drawing"])
    
    # 处理新绘制的多边形
    if output and output.get("last_active_drawing"):
        drawing = output["last_active_drawing"]
        if drawing and drawing["geometry"]["type"] == "Polygon":
            coords_wgs = drawing["geometry"]["coordinates"][0]
            coords_gcj = []
            for coord in coords_wgs:
                lng, lat = coord[0], coord[1]
                gcj_lat, gcj_lng = wgs84_to_gcj02(lat, lng)
                coords_gcj.append([gcj_lng, gcj_lat])
            
            new_obstacle = {
                "id": len(st.session_state.obstacles_list),
                "name": f"障碍物_{len(st.session_state.obstacles_list)+1}",
                "height_m": 10.0,
                "geojson": {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [coords_gcj]
                    }
                }
            }
            st.session_state.obstacles_list.append(new_obstacle)
            st.rerun()

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

    # 显示障碍物
    for obs in st.session_state.obstacles_list:
        coords_gcj = obs["geojson"]["geometry"]["coordinates"][0]
        coords_wgs = []
        for coord in coords_gcj:
            lng, lat = coord[0], coord[1]
            wgs_lat, wgs_lng = gcj02_to_wgs84(lat, lng)
            coords_wgs.append([wgs_lng, wgs_lat])
        
        folium.Polygon(
            locations=[[lat, lng] for lng, lat in coords_wgs],
            color="orange",
            weight=2,
            fillOpacity=0.2
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

    col1, col2, col3 = st.columns(3)
    with col1:
        st.session_state.flight_height = st.number_input("🚁 飞行高度 (米)", min_value=5, max_value=200, value=50, step=5)
    with col2:
        st.session_state.safe_radius = st.number_input("🛡️ 安全半径 (米)", min_value=1.0, max_value=50.0, value=5.0, step=1.0)
    with col3:
        strategy = st.selectbox("🔄 绕行策略", ["向左绕行", "向右绕行", "最佳航线"])

    colA, colB = st.columns(2)
    with colA:
        lat_a = st.number_input("起点 A 纬度 (GCJ-02)", value=st.session_state.point_a_gcj[0], format="%.6f")
        lon_a = st.number_input("起点 A 经度 (GCJ-02)", value=st.session_state.point_a_gcj[1], format="%.6f")
        if st.button("📍 设置 A 点"):
            st.session_state.point_a_gcj = (lat_a, lon_a)
            st.rerun()
    with colB:
        lat_b = st.number_input("终点 B 纬度 (GCJ-02)", value=st.session_state.point_b_gcj[0], format="%.6f")
        lon_b = st.number_input("终点 B 经度 (GCJ-02)", value=st.session_state.point_b_gcj[1], format="%.6f")
        if st.button("📍 设置 B 点"):
            st.session_state.point_b_gcj = (lat_b, lon_b)
            st.rerun()

    st.divider()
    st.subheader("🗺️ 障碍物圈选与高度配置")

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
