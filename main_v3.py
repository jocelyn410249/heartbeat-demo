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

# ==================== 几何计算函数 ====================
def point_in_polygon(px, py, polygon):
    inside = False
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i+1) % n]
        if ((y1 > py) != (y2 > py)) and (px < (x2 - x1) * (py - y1) / (y2 - y1) + x1):
            inside = not inside
    return inside

def segments_intersect(p1, p2, p3, p4):
    def ccw(ax, ay, bx, by, cx, cy):
        return (cy - ay) * (bx - ax) > (by - ay) * (cx - ax)
    return (ccw(p1[0], p1[1], p3[0], p3[1], p4[0], p4[1]) != ccw(p2[0], p2[1], p3[0], p3[1], p4[0], p4[1])) and \
           (ccw(p1[0], p1[1], p2[0], p2[1], p3[0], p3[1]) != ccw(p1[0], p1[1], p2[0], p2[1], p4[0], p4[1]))

def line_intersects_polygon(line_start, line_end, polygon):
    if point_in_polygon(line_start[0], line_start[1], polygon) or \
       point_in_polygon(line_end[0], line_end[1], polygon):
        return True
    for i in range(len(polygon)):
        p3 = polygon[i]
        p4 = polygon[(i+1) % len(polygon)]
        if segments_intersect(line_start, line_end, p3, p4):
            return True
    return False

def haversine_distance(lat1, lng1, lat2, lng2):
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

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
if "flight_speed" not in st.session_state:
    st.session_state.flight_speed = 8.5
if "bypass_strategy" not in st.session_state:
    st.session_state.bypass_strategy = "最佳航线"

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

if "waypoints" not in st.session_state:
    st.session_state.waypoints = []

if "is_flying" not in st.session_state:
    st.session_state.is_flying = False
if "current_wp_index" not in st.session_state:
    st.session_state.current_wp_index = 0
if "flight_start_time" not in st.session_state:
    st.session_state.flight_start_time = None
if "total_flight_distance" not in st.session_state:
    st.session_state.total_flight_distance = 0
if "battery" not in st.session_state:
    st.session_state.battery = 100
if "monitor_messages" not in st.session_state:
    st.session_state.monitor_messages = []

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
    st.session_state.waypoints = []
    st.success("🗑️ 已清除所有障碍物")

# ==================== 航线规划（绕过所有障碍物）====================
def plan_route(strategy):
    """航线规划：绕过所有与AB连线相交的障碍物"""
    a_lat, a_lng = gcj02_to_wgs84(st.session_state.point_a_gcj[0], st.session_state.point_a_gcj[1])
    b_lat, b_lng = gcj02_to_wgs84(st.session_state.point_b_gcj[0], st.session_state.point_b_gcj[1])
    
    waypoints = [[a_lat, a_lng]]
    messages = []
    # 安全半径转经纬度（米转度，约 1度=111000米）
    safe_radius_deg = st.session_state.safe_radius / 111000
    
    for idx, obs in enumerate(st.session_state.obstacles_list):
        try:
            coords_gcj = obs["geojson"]["geometry"]["coordinates"][0]
            polygon = []
            for coord in coords_gcj:
                lng, lat = coord[0], coord[1]
                wgs_lat, wgs_lng = gcj02_to_wgs84(lat, lng)
                polygon.append([wgs_lng, wgs_lat])
            
            # 检查当前规划的路径是否与障碍物相交
            current_start = waypoints[-1]
            current_end = [b_lat, b_lng]
            line_start = [current_start[1], current_start[0]]  # [lng, lat]
            line_end = [current_end[1], current_end[0]]
            
            if line_intersects_polygon(line_start, line_end, polygon):
                obs_height = obs.get("height_m", 10)
                
                # 计算障碍物中心点
                center_lng = sum(p[0] for p in polygon) / len(polygon)
                center_lat = sum(p[1] for p in polygon) / len(polygon)
                
                # 计算从当前点到B点的方向
                dx = b_lng - current_start[1]
                dy = b_lat - current_start[0]
                length = math.sqrt(dx*dx + dy*dy)
                if length > 0:
                    dx /= length
                    dy /= length
                
                # 垂直向量（左右方向）
                perp_x = -dy
                perp_y = dx
                
                # 绕行距离 = 安全半径 * 5
                offset = safe_radius_deg * 5
                
                left_lng = center_lng - perp_x * offset
                left_lat = center_lat - perp_y * offset
                right_lng = center_lng + perp_x * offset
                right_lat = center_lat + perp_y * offset
                
                def calc_total_dist(lat, lng):
                    d1 = haversine_distance(current_start[0], current_start[1], lat, lng)
                    d2 = haversine_distance(b_lat, b_lng, lat, lng)
                    return d1 + d2
                
                left_dist = calc_total_dist(left_lat, left_lng)
                right_dist = calc_total_dist(right_lat, right_lng)
                
                # 根据策略选择绕行方向
                if strategy == "向左绕行":
                    waypoints.append([left_lat, left_lng])
                    messages.append(f"🔄 {obs['name']}：向左绕行（安全半径 {st.session_state.safe_radius}m）")
                elif strategy == "向右绕行":
                    waypoints.append([right_lat, right_lng])
                    messages.append(f"🔄 {obs['name']}：向右绕行（安全半径 {st.session_state.safe_radius}m）")
                else:  # 最佳航线
                    if left_dist <= right_dist:
                        waypoints.append([left_lat, left_lng])
                        messages.append(f"⭐ {obs['name']}：最佳航线-向左绕行")
                    else:
                        waypoints.append([right_lat, right_lng])
                        messages.append(f"⭐ {obs['name']}：最佳航线-向右绕行")
        except Exception as e:
            messages.append(f"⚠️ 处理障碍物出错: {str(e)[:50]}")
            continue
    
    waypoints.append([b_lat, b_lng])
    
    # 去重（移除距离太近的连续点）
    unique_wp = []
    for wp in waypoints:
        if not unique_wp:
            unique_wp.append(wp)
        else:
            dist = haversine_distance(unique_wp[-1][0], unique_wp[-1][1], wp[0], wp[1])
            if dist > 5:  # 距离大于5米才添加
                unique_wp.append(wp)
    
    return unique_wp, messages

def calculate_total_distance(waypoints):
    total = 0
    for i in range(len(waypoints)-1):
        total += haversine_distance(waypoints[i][0], waypoints[i][1], waypoints[i+1][0], waypoints[i+1][1])
    return total

# ==================== 地图绘制 ====================
def draw_full_map():
    """绘制完整地图（障碍物 + 航线）"""
    a_lat, a_lng = gcj02_to_wgs84(st.session_state.point_a_gcj[0], st.session_state.point_a_gcj[1])
    b_lat, b_lng = gcj02_to_wgs84(st.session_state.point_b_gcj[0], st.session_state.point_b_gcj[1])
    center = [(a_lat + b_lat) / 2, (a_lng + b_lng) / 2]
    
    m = folium.Map(location=center, zoom_start=16, tiles="OpenStreetMap")
    
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
    if st.session_state.waypoints and len(st.session_state.waypoints) >= 2:
        folium.PolyLine(
            st.session_state.waypoints,
            color="blue",
            weight=5,
            opacity=0.8,
            popup="规划航线"
        ).add_to(m)
        
        for i, wp in enumerate(st.session_state.waypoints[1:-1]):
            folium.CircleMarker(
                wp,
                radius=5,
                color="blue",
                fill=True,
                fill_color="white",
                popup=f"航点 {i+1}"
            ).add_to(m)
    
    Draw(
        export=True,
        draw_options={"polygon": True, "polyline": False, "rectangle": False,
                      "circle": False, "marker": False, "circlemarker": False},
        edit_options={"edit": True, "remove": True}
    ).add_to(m)
    
    output = st_folium(m, width=800, height=500, returned_objects=["last_active_drawing"])
    
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
                "geojson": {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [coords_gcj]}}
            }
            st.session_state.obstacles_list.append(new_obstacle)
            st.session_state.waypoints = []
            st.rerun()
    
    return m

# ==================== 飞行监控 ====================
def start_flight():
    if len(st.session_state.waypoints) < 2:
        st.error("请先生成航线")
        return
    st.session_state.is_flying = True
    st.session_state.current_wp_index = 0
    st.session_state.flight_start_time = time.time()
    st.session_state.total_flight_distance = calculate_total_distance(st.session_state.waypoints)
    st.session_state.battery = 100
    st.session_state.monitor_messages = []
    st.session_state.monitor_messages.append("🚁 飞行任务开始")

def pause_flight():
    st.session_state.is_flying = False
    st.session_state.monitor_messages.append("⏸️ 飞行暂停")

def resume_flight():
    st.session_state.is_flying = True
    st.session_state.monitor_messages.append("▶️ 飞行恢复")

def stop_flight():
    st.session_state.is_flying = False
    st.session_state.current_wp_index = 0
    st.session_state.flight_start_time = None
    st.session_state.monitor_messages.append("🛬 飞行任务结束")

def update_flight():
    if not st.session_state.is_flying or st.session_state.flight_start_time is None:
        return
    
    elapsed = time.time() - st.session_state.flight_start_time
    traveled_distance = st.session_state.flight_speed * elapsed
    total_distance = st.session_state.total_flight_distance
    
    st.session_state.battery = max(0, 100 - (elapsed / (total_distance / st.session_state.flight_speed + 5)) * 100)
    
    accumulated = 0
    for i in range(len(st.session_state.waypoints) - 1):
        segment_dist = haversine_distance(
            st.session_state.waypoints[i][0], st.session_state.waypoints[i][1],
            st.session_state.waypoints[i+1][0], st.session_state.waypoints[i+1][1]
        )
        if traveled_distance <= accumulated + segment_dist:
            st.session_state.current_wp_index = i
            break
        accumulated += segment_dist
    
    if traveled_distance >= total_distance:
        st.session_state.is_flying = False
        st.session_state.current_wp_index = len(st.session_state.waypoints) - 1
        st.session_state.monitor_messages.append("✅ 飞行任务完成")

def run_flight_monitor():
    st.subheader("📡 飞行实时画面 - 任务执行监控")
    
    update_flight()
    
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    current_waypoint = f"{st.session_state.current_wp_index + 1}/{len(st.session_state.waypoints)}"
    with col1:
        st.metric("当前航点", current_waypoint)
    with col2:
        st.metric("飞行速度", f"{st.session_state.flight_speed} m/s")
    
    elapsed_time = 0
    if st.session_state.flight_start_time:
        elapsed_time = time.time() - st.session_state.flight_start_time
    with col3:
        st.metric("已用时间", f"{int(elapsed_time // 60):02d}:{int(elapsed_time % 60):02d}")
    
    traveled = st.session_state.flight_speed * elapsed_time
    remaining_dist = max(0, st.session_state.total_flight_distance - traveled)
    with col4:
        st.metric("剩余距离", f"{int(remaining_dist)} m")
    
    remaining_time = remaining_dist / st.session_state.flight_speed if st.session_state.flight_speed > 0 else 0
    with col5:
        st.metric("预计到达", f"{int(remaining_time // 60):02d}:{int(remaining_time % 60):02d}")
    
    with col6:
        st.metric("电量模拟", f"{int(st.session_state.battery)}%")
    
    progress = (traveled / st.session_state.total_flight_distance) if st.session_state.total_flight_distance > 0 else 0
    st.progress(min(1.0, progress))
    
    st.markdown("### 通信链路拓扑与数据流")
    link_col1, link_col2, link_col3 = st.columns(3)
    with link_col1:
        st.success("✅ GCS在线")
    with link_col2:
        st.success("✅ OBC在线")
    with link_col3:
        st.success("✅ FCU在线")
    
    st.markdown("### 飞行日志")
    st.text_area("消息", "\n".join(st.session_state.monitor_messages[-10:]), height=150, disabled=True)
    
    col_btn1, col_btn2, col_btn3, col_btn4 = st.columns(4)
    with col_btn1:
        if st.button("🚀 开始飞行", disabled=st.session_state.is_flying):
            start_flight()
            st.rerun()
    with col_btn2:
        if st.button("⏸️ 暂停", disabled=not st.session_state.is_flying):
            pause_flight()
            st.rerun()
    with col_btn3:
        if st.button("▶️ 继续", disabled=st.session_state.is_flying):
            resume_flight()
            st.rerun()
    with col_btn4:
        if st.button("🛬 结束任务"):
            stop_flight()
            st.rerun()
    
    if st.session_state.is_flying:
        time.sleep(0.5)
        st.rerun()

# ==================== 页面路由 ====================
if page == "航线规划":
    st.header("✈️ 智能航线规划")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        new_height = st.number_input("🚁 飞行高度 (米)", min_value=5, max_value=200, value=st.session_state.flight_height, step=5)
        if new_height != st.session_state.flight_height:
            st.session_state.flight_height = new_height
            st.session_state.waypoints = []
    with col2:
        new_radius = st.number_input("🛡️ 安全半径 (米)", min_value=1.0, max_value=50.0, value=st.session_state.safe_radius, step=1.0)
        if new_radius != st.session_state.safe_radius:
            st.session_state.safe_radius = new_radius
            st.session_state.waypoints = []
    with col3:
        new_speed = st.number_input("⚡ 飞行速度 (m/s)", min_value=1.0, max_value=30.0, value=st.session_state.flight_speed, step=0.5)
        if new_speed != st.session_state.flight_speed:
            st.session_state.flight_speed = new_speed
    with col4:
        strategy = st.selectbox("🔄 绕行策略", ["向左绕行", "向右绕行", "最佳航线"], 
                                index=["向左绕行", "向右绕行", "最佳航线"].index(st.session_state.bypass_strategy))
        if strategy != st.session_state.bypass_strategy:
            st.session_state.bypass_strategy = strategy
            st.session_state.waypoints = []
    
    colA, colB = st.columns(2)
    with colA:
        lat_a = st.number_input("起点 A 纬度 (GCJ-02)", value=st.session_state.point_a_gcj[0], format="%.6f")
        lon_a = st.number_input("起点 A 经度 (GCJ-02)", value=st.session_state.point_a_gcj[1], format="%.6f")
        if st.button("📍 设置 A 点"):
            st.session_state.point_a_gcj = (lat_a, lon_a)
            st.session_state.waypoints = []
            st.rerun()
    with colB:
        lat_b = st.number_input("终点 B 纬度 (GCJ-02)", value=st.session_state.point_b_gcj[0], format="%.6f")
        lon_b = st.number_input("终点 B 经度 (GCJ-02)", value=st.session_state.point_b_gcj[1], format="%.6f")
        if st.button("📍 设置 B 点"):
            st.session_state.point_b_gcj = (lat_b, lon_b)
            st.session_state.waypoints = []
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
                    st.session_state.waypoints = []
            with col_h3:
                if st.button("❌ 删除", key=f"del_{idx}"):
                    st.session_state.obstacles_list.pop(idx)
                    st.session_state.waypoints = []
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
            st.session_state.waypoints = []
            st.rerun()
    with col_s3:
        if st.button("🗑️ 清除全部障碍物"):
            clear_all_obstacles()
            st.rerun()
    
    draw_full_map()
    
    st.divider()
    
    col_gen, col_info = st.columns([1, 2])
    with col_gen:
        if st.button("🚀 生成航线", use_container_width=True):
            if len(st.session_state.obstacles_list) > 0:
                waypoints, messages = plan_route(st.session_state.bypass_strategy)
                if len(waypoints) >= 2:
                    st.session_state.waypoints = waypoints
                    for msg in messages:
                        st.info(msg)
                    total_dist = calculate_total_distance(waypoints)
                    st.success(f"✅ 航线已生成！共 {len(waypoints)} 个航点，总距离 {int(total_dist)} 米")
                    st.rerun()
                else:
                    st.warning("⚠️ 航线生成失败")
            else:
                a_lat, a_lng = gcj02_to_wgs84(st.session_state.point_a_gcj[0], st.session_state.point_a_gcj[1])
                b_lat, b_lng = gcj02_to_wgs84(st.session_state.point_b_gcj[0], st.session_state.point_b_gcj[1])
                st.session_state.waypoints = [[a_lat, a_lng], [b_lat, b_lng]]
                total_dist = haversine_distance(a_lat, a_lng, b_lat, b_lng)
                st.success(f"✅ 无障碍物，航线已生成！总距离 {int(total_dist)} 米")
                st.rerun()
    
    with col_info:
        if st.session_state.waypoints:
            st.info(f"📊 当前航线：{len(st.session_state.waypoints)} 个航点，安全半径 {st.session_state.safe_radius} 米，绕行策略：{st.session_state.bypass_strategy}")
        else:
            st.info("📌 点击「生成航线」规划飞行路径")

else:
    run_flight_monitor()
