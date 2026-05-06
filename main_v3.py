import streamlit as st
import time
import json
import os
import math
from streamlit_folium import st_folium
import folium
from folium.plugins import Draw

# ==================== 坐标转换 ====================
def gcj02_to_wgs84(lat, lng):
    a = 6378245.0
    ee = 0.00669342162296594323
    def transform_lat(x, y):
        ret = -100.0 + 2.0*x + 3.0*y + 0.2*y*y + 0.1*x*y + 0.2*math.sqrt(abs(x))
        ret += (20.0*math.sin(6.0*x*math.pi) + 20.0*math.sin(2.0*x*math.pi)) * 2.0/3.0
        ret += (20.0*math.sin(y*math.pi) + 40.0*math.sin(y/3.0*math.pi)) * 2.0/3.0
        ret += (160.0*math.sin(y/12.0*math.pi) + 320*math.sin(y*math.pi/30.0)) * 2.0/3.0
        return ret
    def transform_lng(x, y):
        ret = 300.0 + x + 2.0*y + 0.1*x*x + 0.1*x*y + 0.1*math.sqrt(abs(x))
        ret += (20.0*math.sin(6.0*x*math.pi) + 20.0*math.sin(2.0*x*math.pi)) * 2.0/3.0
        ret += (20.0*math.sin(x*math.pi) + 40.0*math.sin(x/3.0*math.pi)) * 2.0/3.0
        ret += (150.0*math.sin(x/12.0*math.pi) + 300.0*math.sin(x/30.0*math.pi)) * 2.0/3.0
        return ret
    dlat = transform_lat(lng - 105.0, lat - 35.0)
    dlng = transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * math.pi
    magic = math.sin(radlat)
    magic = 1 - ee * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a*(1-ee)) / (magic*sqrtmagic) * math.pi)
    dlng = (dlng * 180.0) / (a / sqrtmagic * math.cos(radlat) * math.pi)
    return lat - dlat, lng - dlng

def wgs84_to_gcj02(lat, lng):
    a = 6378245.0
    ee = 0.00669342162296594323
    def transform_lat(x, y):
        ret = -100.0 + 2.0*x + 3.0*y + 0.2*y*y + 0.1*x*y + 0.2*math.sqrt(abs(x))
        ret += (20.0*math.sin(6.0*x*math.pi) + 20.0*math.sin(2.0*x*math.pi)) * 2.0/3.0
        ret += (20.0*math.sin(y*math.pi) + 40.0*math.sin(y/3.0*math.pi)) * 2.0/3.0
        ret += (160.0*math.sin(y/12.0*math.pi) + 320*math.sin(y*math.pi/30.0)) * 2.0/3.0
        return ret
    def transform_lng(x, y):
        ret = 300.0 + x + 2.0*y + 0.1*x*x + 0.1*x*y + 0.1*math.sqrt(abs(x))
        ret += (20.0*math.sin(6.0*x*math.pi) + 20.0*math.sin(2.0*x*math.pi)) * 2.0/3.0
        ret += (20.0*math.sin(x*math.pi) + 40.0*math.sin(x/3.0*math.pi)) * 2.0/3.0
        ret += (150.0*math.sin(x/12.0*math.pi) + 300.0*math.sin(x/30.0*math.pi)) * 2.0/3.0
        return ret
    dlat = transform_lat(lng - 105.0, lat - 35.0)
    dlng = transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * math.pi
    magic = math.sin(radlat)
    magic = 1 - ee * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a*(1-ee)) / (magic*sqrtmagic) * math.pi)
    dlng = (dlng * 180.0) / (a / sqrtmagic * math.cos(radlat) * math.pi)
    return lat + dlat, lng + dlng

def haversine_distance(lat1, lng1, lat2, lng2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

# ==================== 页面配置 ====================
st.set_page_config(layout="wide", page_title="无人机地面站")
st.sidebar.title("导航")
page = st.sidebar.radio("功能页面", ["航线规划", "飞行监控"])

# ==================== Session State ====================
if "point_a_gcj" not in st.session_state:
    st.session_state.point_a_gcj = (32.2322, 118.749)
    st.session_state.point_b_gcj = (32.2343, 118.749)
if "flight_height" not in st.session_state:
    st.session_state.flight_height = 50.0
if "safe_radius" not in st.session_state:
    st.session_state.safe_radius = 30.0
if "flight_speed" not in st.session_state:
    st.session_state.flight_speed = 8.5
if "bypass_strategy" not in st.session_state:
    st.session_state.bypass_strategy = "最佳航线"
if "obstacles_list" not in st.session_state:
    if os.path.exists("obstacles_full.json"):
        try:
            with open("obstacles_full.json", "r") as f:
                st.session_state.obstacles_list = json.load(f)
        except:
            st.session_state.obstacles_list = []
    else:
        st.session_state.obstacles_list = []
if "waypoints" not in st.session_state:
    st.session_state.waypoints = []
if "is_flying" not in st.session_state:
    st.session_state.is_flying = False
if "flight_start_time" not in st.session_state:
    st.session_state.flight_start_time = None
if "monitor_messages" not in st.session_state:
    st.session_state.monitor_messages = []

def save_obstacles():
    with open("obstacles_full.json", "w") as f:
        json.dump(st.session_state.obstacles_list, f, indent=2)
    st.success("已保存")

def load_obstacles():
    if os.path.exists("obstacles_full.json"):
        with open("obstacles_full.json", "r") as f:
            st.session_state.obstacles_list = json.load(f)
        st.session_state.waypoints = []
        st.success("加载成功")

def clear_obstacles():
    st.session_state.obstacles_list = []
    st.session_state.waypoints = []
    st.success("已清除")

# ==================== 核心绕行算法（强制绕过） ====================
def plan_route():
    a_lat, a_lng = gcj02_to_wgs84(st.session_state.point_a_gcj[0], st.session_state.point_a_gcj[1])
    b_lat, b_lng = gcj02_to_wgs84(st.session_state.point_b_gcj[0], st.session_state.point_b_gcj[1])
    
    # 绕行距离（米 -> 经纬度）
    offset_deg = st.session_state.safe_radius / 111000
    
    # 1. 找起点到终点的直线方向
    dx = b_lng - a_lng
    dy = b_lat - a_lat
    length = math.sqrt(dx*dx + dy*dy)
    if length > 0:
        dx /= length
        dy /= length
    
    # 垂直方向
    perp_x = -dy
    perp_y = dx
    
    # 2. 计算左右两个绕行点（在 AB 直线中点的旁边）
    center_lng = (a_lng + b_lng) / 2
    center_lat = (a_lat + b_lat) / 2
    
    left_point = [center_lat + perp_y * offset_deg, center_lng - perp_x * offset_deg]
    right_point = [center_lat - perp_y * offset_deg, center_lng + perp_x * offset_deg]
    
    # 3. 根据策略选择
    if st.session_state.bypass_strategy == "向左绕行":
        bypass = left_point
        msg = "向左绕行"
    elif st.session_state.bypass_strategy == "向右绕行":
        bypass = right_point
        msg = "向右绕行"
    else:  # 最佳航线
        # 计算到起点和终点的总距离
        left_dist = haversine_distance(a_lat, a_lng, left_point[0], left_point[1]) + \
                    haversine_distance(left_point[0], left_point[1], b_lat, b_lng)
        right_dist = haversine_distance(a_lat, a_lng, right_point[0], right_point[1]) + \
                     haversine_distance(right_point[0], right_point[1], b_lat, b_lng)
        if left_dist <= right_dist:
            bypass = left_point
            msg = "最佳航线（左）"
        else:
            bypass = right_point
            msg = "最佳航线（右）"
    
    waypoints = [[a_lat, a_lng], bypass, [b_lat, b_lng]]
    return waypoints, [msg]

def total_distance(waypoints):
    total = 0
    for i in range(len(waypoints)-1):
        total += haversine_distance(waypoints[i][0], waypoints[i][1], waypoints[i+1][0], waypoints[i+1][1])
    return total

# ==================== 地图 ====================
def draw_map():
    a_lat, a_lng = gcj02_to_wgs84(st.session_state.point_a_gcj[0], st.session_state.point_a_gcj[1])
    b_lat, b_lng = gcj02_to_wgs84(st.session_state.point_b_gcj[0], st.session_state.point_b_gcj[1])
    center = [(a_lat+b_lat)/2, (a_lng+b_lng)/2]
    m = folium.Map(location=center, zoom_start=16)
    
    folium.Marker([a_lat, a_lng], popup="起点 A", icon=folium.Icon(color="green")).add_to(m)
    folium.Marker([b_lat, b_lng], popup="终点 B", icon=folium.Icon(color="red")).add_to(m)
    
    fh = st.session_state.flight_height
    for obs in st.session_state.obstacles_list:
        try:
            coords = obs["geojson"]["geometry"]["coordinates"][0]
            wgs = []
            for c in coords:
                wlat, wlng = gcj02_to_wgs84(c[1], c[0])
                wgs.append([wlat, wlng])
            oh = float(obs.get("height_m", 0))
            color = "green" if fh > oh else "red"
            folium.Polygon(
                locations=wgs,
                color=color, weight=2, fillOpacity=0.3,
                popup=f"{obs['name']}<br>{oh}m"
            ).add_to(m)
        except:
            pass
    
    if st.session_state.waypoints and len(st.session_state.waypoints) >= 2:
        folium.PolyLine(st.session_state.waypoints, color="blue", weight=5, opacity=0.9).add_to(m)
        for wp in st.session_state.waypoints[1:-1]:
            folium.CircleMarker(wp, radius=6, color="blue", fill=True, fill_color="white", popup="绕行点").add_to(m)
    
    Draw(draw_options={"polygon": True}).add_to(m)
    output = st_folium(m, width=800, height=500, returned_objects=["last_active_drawing"])
    
    if output and output.get("last_active_drawing"):
        drawing = output["last_active_drawing"]
        if drawing and drawing["geometry"]["type"] == "Polygon":
            coords_wgs = drawing["geometry"]["coordinates"][0]
            coords_gcj = []
            for c in coords_wgs:
                glat, glng = wgs84_to_gcj02(c[1], c[0])
                coords_gcj.append([glng, glat])
            st.session_state.obstacles_list.append({
                "id": len(st.session_state.obstacles_list),
                "name": f"障碍物_{len(st.session_state.obstacles_list)+1}",
                "height_m": 30.0,
                "geojson": {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [coords_gcj]}}
            })
            st.session_state.waypoints = []
            st.rerun()
    return m

# ==================== 飞行监控 ====================
def flight_monitor():
    st.subheader("飞行监控")
    if st.session_state.is_flying and st.session_state.flight_start_time:
        elapsed = time.time() - st.session_state.flight_start_time
        traveled = st.session_state.flight_speed * elapsed
        total = total_distance(st.session_state.waypoints)
        progress = traveled / total if total > 0 else 0
        battery = max(0.0, 100.0 - elapsed * 2)
        
        c1,c2,c3,c4,c5,c6 = st.columns(6)
        with c1: st.metric("当前航点", f"{min(int(len(st.session_state.waypoints)*progress)+1, len(st.session_state.waypoints))}/{len(st.session_state.waypoints)}")
        with c2: st.metric("速度", f"{st.session_state.flight_speed} m/s")
        with c3: st.metric("已用时间", f"{int(elapsed//60)}:{int(elapsed%60):02d}")
        with c4: st.metric("剩余距离", f"{int(total - traveled)} m")
        with c5: st.metric("预计到达", f"{int((total-traveled)/st.session_state.flight_speed)}秒")
        with c6: st.metric("电量", f"{int(battery)}%")
        st.progress(min(1.0, progress))
        if traveled >= total:
            st.session_state.is_flying = False
            st.success("飞行完成！")
    else:
        st.info("点击「开始飞行」启动模拟")
    
    col1,col2,col3,col4 = st.columns(4)
    with col1:
        if st.button("开始飞行", disabled=st.session_state.is_flying):
            if len(st.session_state.waypoints) >= 2:
                st.session_state.is_flying = True
                st.session_state.flight_start_time = time.time()
                st.rerun()
            else:
                st.error("请先生成航线")
    with col2:
        if st.button("暂停", disabled=not st.session_state.is_flying):
            st.session_state.is_flying = False
            st.rerun()
    with col3:
        if st.button("继续", disabled=st.session_state.is_flying):
            st.session_state.is_flying = True
            st.rerun()
    with col4:
        if st.button("结束"):
            st.session_state.is_flying = False
            st.session_state.flight_start_time = None
            st.rerun()

# ==================== 主页 ====================
if page == "航线规划":
    st.header("航线规划")
    
    col1,col2,col3,col4 = st.columns(4)
    with col1:
        fh = st.number_input("飞行高度(m)", min_value=10.0, max_value=200.0, value=st.session_state.flight_height, step=5.0)
        if fh != st.session_state.flight_height:
            st.session_state.flight_height = fh
    with col2:
        sr = st.number_input("安全半径(m)", min_value=5.0, max_value=50.0, value=st.session_state.safe_radius, step=5.0)
        if sr != st.session_state.safe_radius:
            st.session_state.safe_radius = sr
    with col3:
        sp = st.number_input("速度(m/s)", min_value=1.0, max_value=30.0, value=st.session_state.flight_speed, step=1.0)
        st.session_state.flight_speed = sp
    with col4:
        strat = st.selectbox("绕行策略", ["向左绕行", "向右绕行", "最佳航线"], 
                            index=["向左绕行","向右绕行","最佳航线"].index(st.session_state.bypass_strategy))
        if strat != st.session_state.bypass_strategy:
            st.session_state.bypass_strategy = strat
    
    colA, colB = st.columns(2)
    with colA:
        la = st.number_input("起点A纬度", min_value=32.0, max_value=33.0, value=st.session_state.point_a_gcj[0], format="%.6f")
        loa = st.number_input("起点A经度", min_value=118.0, max_value=119.0, value=st.session_state.point_a_gcj[1], format="%.6f")
        if st.button("设置A"):
            st.session_state.point_a_gcj = (la, loa)
            st.rerun()
    with colB:
        lb = st.number_input("终点B纬度", min_value=32.0, max_value=33.0, value=st.session_state.point_b_gcj[0], format="%.6f")
        lob = st.number_input("终点B经度", min_value=118.0, max_value=119.0, value=st.session_state.point_b_gcj[1], format="%.6f")
        if st.button("设置B"):
            st.session_state.point_b_gcj = (lb, lob)
            st.rerun()
    
    if st.session_state.obstacles_list:
        st.subheader("障碍物列表")
        for i, obs in enumerate(st.session_state.obstacles_list):
            oh = float(obs.get("height_m", 0))
            col_h1, col_h2, col_h3 = st.columns([2,2,1])
            with col_h1:
                st.write(f"{obs['name']}")
            with col_h2:
                new_h = st.number_input("高度", min_value=5.0, max_value=200.0, value=oh, key=f"h_{i}", step=5.0)
                if new_h != oh:
                    st.session_state.obstacles_list[i]["height_m"] = new_h
            with col_h3:
                if st.button("删除", key=f"del_{i}"):
                    st.session_state.obstacles_list.pop(i)
                    st.rerun()
    else:
        st.info("在地图上画多边形添加障碍物")
    
    btn1,btn2,btn3 = st.columns(3)
    with btn1:
        if st.button("保存障碍物"):
            save_obstacles()
    with btn2:
        if st.button("加载障碍物"):
            load_obstacles()
            st.rerun()
    with btn3:
        if st.button("清除全部"):
            clear_obstacles()
            st.rerun()
    
    draw_map()
    
    if st.button("生成航线", use_container_width=True):
        wps, msgs = plan_route()
        st.session_state.waypoints = wps
        for msg in msgs:
            st.warning(msg)
        st.success(f"航线已生成！共 {len(wps)} 个航点，总距离 {int(total_distance(wps))} 米")
        st.rerun()

else:
    flight_monitor()
