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
        try:
            with open(OBSTACLE_FILE, "r") as f:
                st.session_state.obstacles_list = json.load(f)
        except:
            st.session_state.obstacles_list = []
    else:
        st.session_state.obstacles_list = []

if "generated_waypoints" not in st.session_state:
    st.session_state.generated_waypoints = None

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
    st.session_state.generated_waypoints = None
    st.success("🗑️ 已清除所有障碍物")

# ==================== 检测直线是否与多边形相交 ====================
def point_in_polygon(px, py, polygon):
    """射线法判断点是否在多边形内"""
    inside = False
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i+1) % n]
        if ((y1 > py) != (y2 > py)) and (px < (x2 - x1) * (py - y1) / (y2 - y1) + x1):
            inside = not inside
    return inside

def segments_intersect(p1, p2, p3, p4):
    """检测两条线段是否相交"""
    def ccw(ax, ay, bx, by, cx, cy):
        return (cy - ay) * (bx - ax) > (by - ay) * (cx - ax)
    return (ccw(p1[0], p1[1], p3[0], p3[1], p4[0], p4[1]) != ccw(p2[0], p2[1], p3[0], p3[1], p4[0], p4[1])) and \
           (ccw(p1[0], p1[1], p2[0], p2[1], p3[0], p3[1]) != ccw(p1[0], p1[1], p2[0], p2[1], p4[0], p4[1]))

def line_intersects_polygon(line_start, line_end, polygon):
    """检测线段是否与多边形相交"""
    if point_in_polygon(line_start[0], line_start[1], polygon) or \
       point_in_polygon(line_end[0], line_end[1], polygon):
        return True
    for i in range(len(polygon)):
        p3 = polygon[i]
        p4 = polygon[(i+1) % len(polygon)]
        if segments_intersect(line_start, line_end, p3, p4):
            return True
    return False

# ==================== 航线规划 ====================
def plan_route(flight_height, safe_radius, strategy):
    """航线规划"""
    # 转换起点终点到 WGS-84
    a_lat, a_lng = gcj02_to_wgs84(st.session_state.point_a_gcj[0], st.session_state.point_a_gcj[1])
    b_lat, b_lng = gcj02_to_wgs84(st.session_state.point_b_gcj[0], st.session_state.point_b_gcj[1])
    
    # 基础航线：起点 -> 终点
    waypoints = [[a_lat, a_lng]]
    messages = []
    
    for idx, obs in enumerate(st.session_state.obstacles_list):
        try:
            # 获取障碍物多边形顶点（转换为 WGS-84）
            coords_gcj = obs["geojson"]["geometry"]["coordinates"][0]
            polygon = []
            for coord in coords_gcj:
                lng, lat = coord[0], coord[1]
                wgs_lat, wgs_lng = gcj02_to_wgs84(lat, lng)
                polygon.append([wgs_lng, wgs_lat])  # [lng, lat]
            
            # 检查是否与航线相交
            line_start = [a_lng, a_lat]
            line_end = [b_lng, b_lat]
            
            if line_intersects_polygon(line_start, line_end, polygon):
                obs_height = obs.get("height_m", 10)
                
                if flight_height > obs_height + safe_radius:
                    # 飞跃
                    mid_lat = (a_lat + b_lat) / 2
                    mid_lng = (a_lng + b_lng) / 2
                    waypoints.append([mid_lat, mid_lng])
                    messages.append(f"✈️ {obs['name']}：飞跃（高度{flight_height}m > {obs_height}m）")
                else:
                    # 计算障碍物中心点
                    center_lng = sum(p[0] for p in polygon) / len(polygon)
                    center_lat = sum(p[1] for p in polygon) / len(polygon)
                    
                    # 计算AB方向
                    dx = b_lng - a_lng
                    dy = b_lat - a_lat
                    length = math.sqrt(dx*dx + dy*dy)
                    if length > 0:
                        dx /= length
                        dy /= length
                    
                    # 垂直向量
                    perp_x = -dy
                    perp_y = dx
                    
                    # 绕行距离 = 安全半径 * 2
                    offset = safe_radius * 0.0003  # 转换为经纬度偏移量
                    
                    left_lng = center_lng - perp_x * offset
                    left_lat = center_lat - perp_y * offset
                    right_lng = center_lng + perp_x * offset
                    right_lat = center_lat + perp_y * offset
                    
                    if strategy == "向左绕行":
                        waypoints.append([left_lat, left_lng])
                        messages.append(f"🔄 {obs['name']}：向左绕行")
                    elif strategy == "向右绕行":
                        waypoints.append([right_lat, right_lng])
                        messages.append(f"🔄 {obs['name']}：向右绕行")
                    else:
                        # 最佳航线：计算到起点终点的距离总和
                        def calc_dist(lat, lng):
                            d1 = math.sqrt((lat - a_lat)**2 + (lng - a_lng)**2)
                            d2 = math.sqrt((lat - b_lat)**2 + (lng - b_lng)**2)
                            return d1 + d2
                        
                        left_dist = calc_dist(left_lat, left_lng)
                        right_dist = calc_dist(right_lat, right_lng)
                        
                        if left_dist <= right_dist:
                            waypoints.append([left_lat, left_lng])
                            messages.append(f"⭐ {obs['name']}：最佳航线（向左）")
                        else:
                            waypoints.append([right_lat, right_lng])
                            messages.append(f"⭐ {obs['name']}：最佳航线（向右）")
        except Exception as e:
            messages.append(f"⚠️ 处理障碍物时出错: {str(e)[:50]}")
            continue
    
    waypoints.append([b_lat, b_lng])
    return waypoints, messages

# ==================== 地图绘制 ====================
def draw_full_map():
    """绘制完整地图"""
    a_lat, a_lng = gcj02_to_wgs84(st.session_state.point_a_gcj[0], st.session_state.point_a_gcj[1])
    b_lat, b_lng = gcj02_to_wgs84(st.session_state.point_b_gcj[0], st.session_state.point_b_gcj[1])
    center = [(a_lat + b_lat) / 2, (a_lng + b_lng) / 2]
    
    m = folium.Map(location=center, zoom_start=16, tiles="OpenStreetMap")
    
    # 起点终点
    folium.Marker([a_lat, a_lng], popup="起点 A", icon=folium.Icon(color="green", icon="play")).add_to(m)
    folium.Marker([b_lat, b_lng], popup="终点 B", icon=folium.Icon(color="red", icon="flag")).add_to(m)
    
    # 障碍物
    for obs in st.session_state.obstacles_list:
        try:
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
                popup=f"{obs['name']}<br>高度: {obs['height_m']}m"
            ).add_to(m)
        except:
            continue
    
    # 航线
    if st.session_state.generated_waypoints and len(st.session_state.generated_waypoints) >= 2:
        folium.PolyLine(
            st.session_state.generated_waypoints,
            color="blue",
            weight=5,
            opacity=0.8,
            popup="规划航线"
        ).add_to(m)
        
        # 中间航点标记
        for i, wp in enumerate(st.session_state.generated_waypoints[1:-1]):
            folium.CircleMarker(
                wp,
                radius=6,
                color="blue",
                fill=True,
                fill_color="white",
                popup=f"绕行点 {i+1}"
            ).add_to(m)
    
    # 绘图控件
    Draw(export=True, draw_options={"polygon": True, "polyline": False, "rectangle": False,
                                   "circle": False, "marker": False, "circlemarker": False},
         edit_options={"edit": True, "remove": True}).add_to(m)
    
    output = st_folium(m, width=800, height=500, returned_objects=["last_active_drawing"])
    
    # 处理新多边形
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
                    "geometry": {"type": "Polygon", "coordinates": [coords_gcj]}
                }
            }
            st.session_state.obstacles_list.append(new_obstacle)
            st.session_state.generated_waypoints = None
            st.rerun()

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
        new_height = st.number_input("🚁 飞行高度 (米)", min_value=5, max_value=200, value=st.session_state.flight_height, step=5)
        if new_height != st.session_state.flight_height:
            st.session_state.flight_height = new_height
            st.session_state.generated_waypoints = None
    with col2:
        new_radius = st.number_input("🛡️ 安全半径 (米)", min_value=1.0, max_value=50.0, value=st.session_state.safe_radius, step=1.0)
        if new_radius != st.session_state.safe_radius:
            st.session_state.safe_radius = new_radius
            st.session_state.generated_waypoints = None
    with col3:
        strategy = st.selectbox("🔄 绕行策略", ["向左绕行", "向右绕行", "最佳航线"])
    
    colA, colB = st.columns(2)
    with colA:
        lat_a = st.number_input("起点 A 纬度 (GCJ-02)", value=st.session_state.point_a_gcj[0], format="%.6f")
        lon_a = st.number_input("起点 A 经度 (GCJ-02)", value=st.session_state.point_a_gcj[1], format="%.6f")
        if st.button("📍 设置 A 点"):
            st.session_state.point_a_gcj = (lat_a, lon_a)
            st.session_state.generated_waypoints = None
            st.rerun()
    with colB:
        lat_b = st.number_input("终点 B 纬度 (GCJ-02)", value=st.session_state.point_b_gcj[0], format="%.6f")
        lon_b = st.number_input("终点 B 经度 (GCJ-02)", value=st.session_state.point_b_gcj[1], format="%.6f")
        if st.button("📍 设置 B 点"):
            st.session_state.point_b_gcj = (lat_b, lon_b)
            st.session_state.generated_waypoints = None
            st.rerun()
    
    st.divider()
    st.subheader("🗺️ 障碍物圈选与高度配置")
    
    if st.session_state.obstacles_list:
        for idx, obs in enumerate(st.session_state.obstacles_list):
            col_h1, col_h2, col_h3 = st.columns([3, 2, 1])
            with col_h1:
                st.write(f"**{obs['name']}**")
            with col_h2:
                new_h = st.number_input(f"高度 (m)", value=float(obs["height_m"]), key=f"h_{idx}", step=1.0)
                if new_h != st.session_state.obstacles_list[idx]["height_m"]:
                    st.session_state.obstacles_list[idx]["height_m"] = new_h
                    st.session_state.generated_waypoints = None
            with col_h3:
                if st.button("❌ 删除", key=f"del_{idx}"):
                    st.session_state.obstacles_list.pop(idx)
                    st.session_state.generated_waypoints = None
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
            st.session_state.generated_waypoints = None
            st.rerun()
    with col_s3:
        if st.button("🗑️ 清除全部障碍物"):
            clear_all_obstacles()
            st.rerun()
    
    draw_full_map()
    
    st.divider()
    st.subheader("✈️ 航线生成与展示")
    
    if st.button("🚀 生成航线"):
        if len(st.session_state.obstacles_list) > 0:
            waypoints, messages = plan_route(st.session_state.flight_height, st.session_state.safe_radius, strategy)
            if len(waypoints) >= 2:
                st.session_state.generated_waypoints = waypoints
                for msg in messages:
                    st.info(msg)
                st.success(f"✅ 航线已生成（共 {len(waypoints)} 个航点）")
                st.rerun()
            else:
                st.warning("⚠️ 航线生成失败")
        else:
            st.warning("⚠️ 请先添加障碍物")

else:
    heartbeat_monitor()
