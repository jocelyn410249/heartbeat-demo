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

def line_intersects_polygon(p1, p2, polygon):
    if point_in_polygon(p1[0], p1[1], polygon) or point_in_polygon(p2[0], p2[1], polygon):
        return True
    for i in range(len(polygon)):
        p3 = polygon[i]
        p4 = polygon[(i+1) % len(polygon)]
        if segments_intersect(p1, p2, p3, p4):
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

def get_polygon_bbox(polygon):
    """获取多边形的外包矩形"""
    lngs = [p[0] for p in polygon]
    lats = [p[1] for p in polygon]
    return min(lngs), max(lngs), min(lats), max(lats)

def get_bypass_waypoints(current_start, b_pos, polygon, safe_radius_deg, strategy):
    """
    计算绕行航点：生成进入绕行点和离开绕行点，确保完整绕过障碍物多边形。
    返回 [bypass_enter, bypass_exit] 或 [bypass_single] 列表。
    """
    # 障碍物中心
    center_lng = sum(p[0] for p in polygon) / len(polygon)
    center_lat = sum(p[1] for p in polygon) / len(polygon)

    # 从当前点到B点的方向向量
    dx = b_pos[1] - current_start[1]  # lng方向
    dy = b_pos[0] - current_start[0]  # lat方向
    length = math.sqrt(dx*dx + dy*dy)
    if length == 0:
        return []
    dx /= length
    dy /= length

    # 垂直向量（左右）
    perp_x = -dy
    perp_y = dx

    # 计算障碍物在垂直方向上的最大投影半径（用外包矩形估算）
    min_lng, max_lng, min_lat, max_lat = get_polygon_bbox(polygon)
    obs_half_w = ((max_lng - min_lng) / 2 + (max_lat - min_lat) / 2) / 2
    # 绕行偏移 = 障碍物半径 + 安全距离，至少 safe_radius_deg * 3
    bypass_offset = max(obs_half_w + safe_radius_deg * 2, safe_radius_deg * 3)

    # 沿飞行方向，确定障碍物的"前后范围"，计算进入点和出口点
    # 障碍物中心在飞行方向上的投影
    start_vec_x = center_lng - current_start[1]
    start_vec_y = center_lat - current_start[0]
    proj_along = start_vec_x * dx + start_vec_y * dy  # 沿飞行方向距离

    # 进入点和退出点：在障碍物中心前后各偏移 obs_half_w + safe_radius_deg
    along_offset = obs_half_w + safe_radius_deg * 2

    enter_lng = current_start[1] + dx * max(0, proj_along - along_offset)
    enter_lat = current_start[0] + dy * max(0, proj_along - along_offset)
    exit_lng  = current_start[1] + dx * (proj_along + along_offset)
    exit_lat  = current_start[0] + dy * (proj_along + along_offset)

    # 左右两侧绕行点
    left_enter_lng  = enter_lng - perp_x * bypass_offset
    left_enter_lat  = enter_lat - perp_y * bypass_offset
    left_exit_lng   = exit_lng  - perp_x * bypass_offset
    left_exit_lat   = exit_lat  - perp_y * bypass_offset

    right_enter_lng = enter_lng + perp_x * bypass_offset
    right_enter_lat = enter_lat + perp_y * bypass_offset
    right_exit_lng  = exit_lng  + perp_x * bypass_offset
    right_exit_lat  = exit_lat  + perp_y * bypass_offset

    def route_dist_two(e_lat, e_lng, x_lat, x_lng):
        d1 = haversine_distance(current_start[0], current_start[1], e_lat, e_lng)
        d2 = haversine_distance(e_lat, e_lng, x_lat, x_lng)
        d3 = haversine_distance(x_lat, x_lng, b_pos[0], b_pos[1])
        return d1 + d2 + d3

    left_dist  = route_dist_two(left_enter_lat,  left_enter_lng,  left_exit_lat,  left_exit_lng)
    right_dist = route_dist_two(right_enter_lat, right_enter_lng, right_exit_lat, right_exit_lng)

    if strategy == "向左绕行":
        return [[left_enter_lat, left_enter_lng], [left_exit_lat, left_exit_lng]]
    elif strategy == "向右绕行":
        return [[right_enter_lat, right_enter_lng], [right_exit_lat, right_exit_lng]]
    else:  # 最佳航线
        if left_dist <= right_dist:
            return [[left_enter_lat, left_enter_lng], [left_exit_lat, left_exit_lng]]
        else:
            return [[right_enter_lat, right_enter_lng], [right_exit_lat, right_exit_lng]]

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

# ==================== 航线规划（高度感知绕行）====================
def plan_route(strategy):
    """
    航线规划：
    - 飞行高度 > 障碍物高度：直线飞越，无需绕行
    - 飞行高度 <= 障碍物高度：水平绕行（生成进入点 + 退出点，确保完整绕过）
    """
    a_lat, a_lng = gcj02_to_wgs84(st.session_state.point_a_gcj[0], st.session_state.point_a_gcj[1])
    b_lat, b_lng = gcj02_to_wgs84(st.session_state.point_b_gcj[0], st.session_state.point_b_gcj[1])

    flight_height = st.session_state.flight_height
    safe_radius_deg = st.session_state.safe_radius / 111000

    waypoints = [[a_lat, a_lng]]
    messages = []

    # 按障碍物在路径上的顺序排序（离起点由近及远）
    obs_with_poly = []
    for idx, obs in enumerate(st.session_state.obstacles_list):
        try:
            coords_gcj = obs["geojson"]["geometry"]["coordinates"][0]
            polygon = []
            for coord in coords_gcj:
                lng, lat = coord[0], coord[1]
                wgs_lat, wgs_lng = gcj02_to_wgs84(lat, lng)
                polygon.append([wgs_lng, wgs_lat])  # [lng, lat]
            center_lng = sum(p[0] for p in polygon) / len(polygon)
            center_lat = sum(p[1] for p in polygon) / len(polygon)
            dist_from_a = haversine_distance(a_lat, a_lng, center_lat, center_lng)
            obs_with_poly.append((dist_from_a, obs, polygon))
        except Exception as e:
            messages.append(f"⚠️ 解析 {obs.get('name', '障碍物')} 出错: {str(e)[:50]}")

    obs_with_poly.sort(key=lambda x: x[0])

    for dist_from_a, obs, polygon in obs_with_poly:
        obs_height = float(obs.get("height_m", 0))
        obs_name   = obs.get("name", "障碍物")

        # ---- 高度判断：飞行高度高于障碍物 → 直接飞越 ----
        if flight_height > obs_height:
            messages.append(f"✈️ {obs_name}（高度 {obs_height}m）：飞行高度 {flight_height}m 可飞越，无需绕行")
            continue

        # ---- 飞行高度不足：检查水平方向是否需要绕行 ----
        current_start = waypoints[-1]
        p1 = [current_start[1], current_start[0]]  # [lng, lat]
        p2 = [b_lng, b_lat]

        if not line_intersects_polygon(p1, p2, polygon):
            messages.append(f"✅ {obs_name}（高度 {obs_height}m）：不在航线上，无需绕行")
            continue

        # ---- 需要水平绕行 ----
        bypass_wps = get_bypass_waypoints(
            current_start,       # [lat, lng]
            [b_lat, b_lng],      # [lat, lng]
            polygon,             # [[lng, lat], ...]
            safe_radius_deg,
            strategy
        )

        side = "左" if strategy == "向左绕行" else ("右" if strategy == "向右绕行" else "")
        for bp in bypass_wps:
            waypoints.append(bp)

        # 验证绕行点是否真正避开了障碍物（否则加大偏移重试）
        valid = True
        for i in range(len(waypoints) - len(bypass_wps) - 1, len(waypoints) - 1):
            seg_p1 = [waypoints[i][1], waypoints[i][0]]
            seg_p2 = [waypoints[i+1][1], waypoints[i+1][0]]
            if line_intersects_polygon(seg_p1, seg_p2, polygon):
                valid = False
                break

        if not valid:
            # 加大偏移重试（×2）
            for _ in range(len(bypass_wps)):
                waypoints.pop()
            bypass_wps2 = get_bypass_waypoints(
                current_start, [b_lat, b_lng], polygon,
                safe_radius_deg * 2, strategy
            )
            for bp in bypass_wps2:
                waypoints.append(bp)
            messages.append(f"🔄 {obs_name}（高度 {obs_height}m）：飞行高度 {flight_height}m 不足，加大偏移绕行{'（' + side + '侧）' if side else ''}")
        else:
            messages.append(f"🔄 {obs_name}（高度 {obs_height}m）：飞行高度 {flight_height}m 不足，水平绕行{'（' + side + '侧）' if side else ''}")

    waypoints.append([b_lat, b_lng])

    # 去重（距离 < 3m 的相邻点合并）
    unique_wp = []
    for wp in waypoints:
        if not unique_wp:
            unique_wp.append(wp)
        else:
            dist = haversine_distance(unique_wp[-1][0], unique_wp[-1][1], wp[0], wp[1])
            if dist > 3:
                unique_wp.append(wp)

    if len(unique_wp) > 2:
        messages.append(f"📊 航线已规划，共 {len(unique_wp)} 个航点")

    return unique_wp, messages

def calculate_total_distance(waypoints):
    total = 0
    for i in range(len(waypoints)-1):
        total += haversine_distance(waypoints[i][0], waypoints[i][1], waypoints[i+1][0], waypoints[i+1][1])
    return total

# ==================== 地图绘制 ====================
def draw_full_map():
    """绘制完整地图（障碍物 + 航线），障碍物颜色根据可飞越性区分"""
    a_lat, a_lng = gcj02_to_wgs84(st.session_state.point_a_gcj[0], st.session_state.point_a_gcj[1])
    b_lat, b_lng = gcj02_to_wgs84(st.session_state.point_b_gcj[0], st.session_state.point_b_gcj[1])
    center = [(a_lat + b_lat) / 2, (a_lng + b_lng) / 2]

    m = folium.Map(location=center, zoom_start=16, tiles="OpenStreetMap")

    folium.Marker([a_lat, a_lng], popup="起点 A", icon=folium.Icon(color="green", icon="play")).add_to(m)
    folium.Marker([b_lat, b_lng], popup="终点 B", icon=folium.Icon(color="red", icon="flag")).add_to(m)

    flight_height = st.session_state.flight_height

    # 障碍物（颜色：红=需绕行，绿=可飞越）
    for obs in st.session_state.obstacles_list:
        try:
            coords_gcj = obs["geojson"]["geometry"]["coordinates"][0]
            coords_wgs = []
            for coord in coords_gcj:
                lng, lat = coord[0], coord[1]
                wgs_lat, wgs_lng = gcj02_to_wgs84(lat, lng)
                coords_wgs.append([wgs_lng, wgs_lat])

            obs_height = float(obs.get("height_m", 0))
            # 红色=飞行高度不足需绕行，绿色=可飞越
            color = "red" if flight_height <= obs_height else "green"
            label = f"{obs['name']}<br>障碍高度: {obs_height}m<br>飞行高度: {flight_height}m<br>{'⚠️ 需绕行' if color == 'red' else '✅ 可飞越'}"

            folium.Polygon(
                locations=[[lat, lng] for lng, lat in coords_wgs],
                color=color,
                weight=3,
                fillOpacity=0.35,
                popup=label
            ).add_to(m)

            # 在障碍物中心显示高度标注
            center_lat = sum(p[1] for p in coords_wgs) / len(coords_wgs)
            center_lng = sum(p[0] for p in coords_wgs) / len(coords_wgs)
            folium.Marker(
                [center_lat, center_lng],
                icon=folium.DivIcon(
                    html=f'<div style="font-size:11px;font-weight:bold;color:{"red" if color=="red" else "darkgreen"};'
                         f'background:rgba(255,255,255,0.8);padding:2px 4px;border-radius:3px;">'
                         f'{obs_height}m</div>',
                    icon_size=(50, 20),
                    icon_anchor=(25, 10)
                )
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
                popup=f"绕行点 {i+1}"
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

    # 高度提示
    if st.session_state.obstacles_list:
        max_obs_h = max(float(o.get("height_m", 0)) for o in st.session_state.obstacles_list)
        if st.session_state.flight_height > max_obs_h:
            st.success(f"✅ 当前飞行高度 {st.session_state.flight_height}m 高于所有障碍物（最高 {max_obs_h}m），全程可直飞")
        else:
            need_bypass = [o["name"] for o in st.session_state.obstacles_list if float(o.get("height_m", 0)) >= st.session_state.flight_height]
            st.warning(f"⚠️ 以下障碍物高于飞行高度，将水平绕行：{', '.join(need_bypass)}")

    colA, colB = st.columns(2)
    with colA:
        lat_a = st.number_input("起点 A 纬度 (GCJ-02)", value=st.session_state.point_a_gcj[0], format="%.6f")
        lon_a = st.number_input("起点 A 经度 (GCJ-02)", value=st.session_state.point_a_gcj[1], format="%.6f")
        if st.button("📍 设置 A 点"):
            st.session_state.point_a_gcj = (lat_a, lon_a)
            st.session_state.waypoints = []
            st.rerun()
    with colB:
        lat_b = st.number_input("起点 B 纬度 (GCJ-02)", value=st.session_state.point_b_gcj[0], format="%.6f")
        lon_b = st.number_input("起点 B 经度 (GCJ-02)", value=st.session_state.point_b_gcj[1], format="%.6f")
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
                obs_h = float(obs.get("height_m", 0))
                can_fly = st.session_state.flight_height > obs_h
                icon = "✅" if can_fly else "⚠️"
                st.write(f"**{icon} {obs['name']}** — {obs_h}m {'（可飞越）' if can_fly else '（需绕行）'}")
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
                        if "无需绕行" in msg or "可飞越" in msg:
                            st.info(msg)
                        elif "绕行" in msg:
                            st.warning(msg)
                        else:
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
