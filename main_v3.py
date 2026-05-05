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

# ==================== 几何工具 ====================
def haversine_distance(lat1, lng1, lat2, lng2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def point_in_polygon(px, py, polygon):
    """polygon: [[lng, lat], ...]"""
    inside = False
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i][0], polygon[i][1]
        x2, y2 = polygon[(i+1)%n][0], polygon[(i+1)%n][1]
        if ((y1 > py) != (y2 > py)) and (px < (x2-x1)*(py-y1)/(y2-y1)+x1):
            inside = not inside
    return inside

def segments_intersect(p1, p2, p3, p4):
    def ccw(ax, ay, bx, by, cx, cy):
        return (cy-ay)*(bx-ax) > (by-ay)*(cx-ax)
    return (ccw(p1[0],p1[1],p3[0],p3[1],p4[0],p4[1]) != ccw(p2[0],p2[1],p3[0],p3[1],p4[0],p4[1])) and \
           (ccw(p1[0],p1[1],p2[0],p2[1],p3[0],p3[1]) != ccw(p1[0],p1[1],p2[0],p2[1],p4[0],p4[1]))

def line_intersects_polygon(p1, p2, polygon):
    """p1/p2: [lng, lat]"""
    if point_in_polygon(p1[0], p1[1], polygon) or point_in_polygon(p2[0], p2[1], polygon):
        return True
    for i in range(len(polygon)):
        if segments_intersect(p1, p2, polygon[i], polygon[(i+1)%len(polygon)]):
            return True
    return False

def expand_polygon(polygon, margin_deg):
    """向外膨胀多边形，polygon: [[lng,lat],...]"""
    n = len(polygon)
    cx = sum(p[0] for p in polygon) / n
    cy = sum(p[1] for p in polygon) / n
    result = []
    for p in polygon:
        dx, dy = p[0]-cx, p[1]-cy
        dist = math.sqrt(dx*dx + dy*dy)
        if dist == 0:
            result.append([p[0], p[1]])
        else:
            scale = (dist + margin_deg) / dist
            result.append([cx + dx*scale, cy + dy*scale])
    return result

def polygon_signed_area(polygon):
    """计算有向面积（正=逆时针，负=顺时针）"""
    s = 0.0
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i][0], polygon[i][1]
        x2, y2 = polygon[(i+1)%n][0], polygon[(i+1)%n][1]
        s += (x1*y2 - x2*y1)
    return s / 2.0

def get_bypass_waypoints(start_lng, start_lat, end_lng, end_lat,
                          polygon, safe_deg, strategy):
    """
    基于膨胀多边形顶点的绕行算法。
    思路：
      1. 膨胀多边形
      2. 找出所有膨胀后顶点，根据叉积判断每个顶点在飞行线的左侧还是右侧
      3. 选择对应侧的顶点，按沿飞行方向的投影从小到大排列
      4. 验证路径，返回绕行点列表 [[lat,lng],...]
    """
    exp = expand_polygon(polygon, safe_deg)

    # 保证逆时针
    if polygon_signed_area(exp) < 0:
        exp = exp[::-1]

    n = len(exp)
    flight_dx = end_lng - start_lng
    flight_dy = end_lat - start_lat
    flight_len = math.sqrt(flight_dx**2 + flight_dy**2)
    if flight_len == 0:
        return []

    # 单位飞行方向向量
    ux, uy = flight_dx/flight_len, flight_dy/flight_len
    # 左法向量（逆时针旋转90度）
    lx, ly = -uy, ux

    verts_info = []
    for i, p in enumerate(exp):
        # 沿飞行方向的投影
        proj = (p[0]-start_lng)*ux + (p[1]-start_lat)*uy
        # 垂直于飞行方向的投影（正=左侧，负=右侧）
        side = (p[0]-start_lng)*lx + (p[1]-start_lat)*ly
        verts_info.append({"i": i, "proj": proj, "side": side, "p": p})

    # 按飞行方向投影排序
    verts_info.sort(key=lambda x: x["proj"])

    left_verts  = [v for v in verts_info if v["side"] >= 0]
    right_verts = [v for v in verts_info if v["side"] < 0]

    def route_len(verts):
        if not verts:
            return float("inf")
        pts = [v["p"] for v in verts]
        d = haversine_distance(start_lat, start_lng, pts[0][1], pts[0][0])
        for k in range(len(pts)-1):
            d += haversine_distance(pts[k][1], pts[k][0], pts[k+1][1], pts[k+1][0])
        d += haversine_distance(pts[-1][1], pts[-1][0], end_lat, end_lng)
        return d

    if strategy == "向左绕行":
        chosen = left_verts if left_verts else right_verts
    elif strategy == "向右绕行":
        chosen = right_verts if right_verts else left_verts
    else:
        chosen = left_verts if route_len(left_verts) <= route_len(right_verts) else right_verts

    if not chosen:
        chosen = verts_info

    bypass_lnglat = [v["p"] for v in chosen]  # [[lng, lat], ...]

    # 验证：逐段检查是否仍穿越膨胀多边形
    full_path_ll = [[start_lng, start_lat]] + bypass_lnglat + [[end_lng, end_lat]]
    ok = True
    for k in range(len(full_path_ll)-1):
        if line_intersects_polygon(full_path_ll[k], full_path_ll[k+1], exp):
            ok = False
            break

    if not ok:
        # 保底：使用全部顶点
        bypass_lnglat = [v["p"] for v in verts_info]

    return [[p[1], p[0]] for p in bypass_lnglat]  # [[lat, lng], ...]

# ==================== 页面配置 ====================
st.set_page_config(layout="wide", page_title="无人机智能地面站")
st.sidebar.title("导航")
page = st.sidebar.radio("功能页面", ["航线规划", "飞行监控"])

# ==================== Session State ====================
defaults = {
    "point_a_gcj": (32.2322, 118.749),
    "point_b_gcj": (32.2343, 118.749),
    "flight_height": 50,
    "safe_radius": 5.0,
    "flight_speed": 8.5,
    "bypass_strategy": "最佳航线",
    "obstacles_list": [],
    "waypoints": [],
    "is_flying": False,
    "current_wp_index": 0,
    "flight_start_time": None,
    "total_flight_distance": 0,
    "battery": 100,
    "monitor_messages": [],
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# 启动时从文件加载障碍物
if not st.session_state.obstacles_list:
    if os.path.exists("obstacles_full.json"):
        try:
            with open("obstacles_full.json", "r") as f:
                st.session_state.obstacles_list = json.load(f)
        except:
            pass

# ==================== 工具函数 ====================
def save_all_obstacles():
    with open("obstacles_full.json", "w") as f:
        json.dump(st.session_state.obstacles_list, f, indent=2)
    st.success("已保存所有障碍物")

def load_all_obstacles():
    if os.path.exists("obstacles_full.json"):
        with open("obstacles_full.json", "r") as f:
            st.session_state.obstacles_list = json.load(f)
        st.success("障碍物加载成功")

def clear_all_obstacles():
    st.session_state.obstacles_list = []
    st.session_state.waypoints = []
    st.success("已清除所有障碍物")

def calculate_total_distance(wps):
    total = 0
    for i in range(len(wps)-1):
        total += haversine_distance(wps[i][0], wps[i][1], wps[i+1][0], wps[i+1][1])
    return total

# ==================== 航线规划 ====================
def plan_route(strategy):
    a_lat, a_lng = gcj02_to_wgs84(st.session_state.point_a_gcj[0],
                                   st.session_state.point_a_gcj[1])
    b_lat, b_lng = gcj02_to_wgs84(st.session_state.point_b_gcj[0],
                                   st.session_state.point_b_gcj[1])

    flight_height = st.session_state.flight_height
    safe_deg = st.session_state.safe_radius / 111000

    messages = []

    # 预处理障碍物
    obs_data = []
    for obs in st.session_state.obstacles_list:
        try:
            coords_gcj = obs["geojson"]["geometry"]["coordinates"][0]
            poly = []
            for coord in coords_gcj:
                wlat, wlng = gcj02_to_wgs84(coord[1], coord[0])
                poly.append([wlng, wlat])
            obs_height = float(obs.get("height_m", 0))
            need_bypass = (flight_height <= obs_height)
            obs_data.append({
                "name": obs.get("name", "障碍物"),
                "height": obs_height,
                "polygon": poly,
                "need_bypass": need_bypass,
                "bypassed": False,
            })
        except Exception as e:
            messages.append("解析 {} 出错: {}".format(obs.get("name","?"), str(e)[:40]))

    waypoints = [[a_lat, a_lng]]
    MAX_ITER = 100
    iteration = 0

    while iteration < MAX_ITER:
        iteration += 1
        cur = waypoints[-1]
        cur_lng, cur_lat = cur[1], cur[0]
        p1 = [cur_lng, cur_lat]
        p2 = [b_lng, b_lat]

        # 找最近的未绕过且需要绕行的障碍物
        hit = None
        hit_dist = float("inf")
        for obs in obs_data:
            if not obs["need_bypass"]:
                continue
            if line_intersects_polygon(p1, p2, obs["polygon"]):
                cx = sum(v[0] for v in obs["polygon"]) / len(obs["polygon"])
                cy = sum(v[1] for v in obs["polygon"]) / len(obs["polygon"])
                d = haversine_distance(cur_lat, cur_lng, cy, cx)
                if d < hit_dist:
                    hit_dist = d
                    hit = obs

        if hit is None:
            break  # 路径畅通，结束

        bypass = get_bypass_waypoints(
            cur_lng, cur_lat, b_lng, b_lat,
            hit["polygon"], safe_deg, strategy
        )

        if not bypass:
            messages.append("警告: {} 无法生成绕行点".format(hit["name"]))
            hit["need_bypass"] = False
            continue

        added = 0
        for wp in bypass:
            last = waypoints[-1]
            if haversine_distance(last[0], last[1], wp[0], wp[1]) > 2:
                waypoints.append(wp)
                added += 1

        if added == 0:
            hit["need_bypass"] = False
            continue

        side_str = {"向左绕行": "左", "向右绕行": "右"}.get(strategy, "最佳")
        messages.append("{} ({}m, 飞高{}m): 水平绕行[{}侧] +{}航点".format(
            hit["name"], hit["height"], flight_height, side_str, added))

    waypoints.append([b_lat, b_lng])

    # 去重
    unique = [waypoints[0]]
    for wp in waypoints[1:]:
        if haversine_distance(unique[-1][0], unique[-1][1], wp[0], wp[1]) > 2:
            unique.append(wp)

    for obs in obs_data:
        if flight_height > obs["height"]:
            messages.append("{} ({}m): 飞行高度{}m，直接飞越".format(
                obs["name"], obs["height"], flight_height))

    messages.append("规划完成，共 {} 个航点".format(len(unique)))
    return unique, messages

# ==================== 地图 ====================
def draw_full_map():
    a_lat, a_lng = gcj02_to_wgs84(st.session_state.point_a_gcj[0],
                                   st.session_state.point_a_gcj[1])
    b_lat, b_lng = gcj02_to_wgs84(st.session_state.point_b_gcj[0],
                                   st.session_state.point_b_gcj[1])
    center = [(a_lat+b_lat)/2, (a_lng+b_lng)/2]
    m = folium.Map(location=center, zoom_start=16, tiles="OpenStreetMap")
    folium.Marker([a_lat, a_lng], popup="起点 A",
                  icon=folium.Icon(color="green", icon="play")).add_to(m)
    folium.Marker([b_lat, b_lng], popup="终点 B",
                  icon=folium.Icon(color="red", icon="flag")).add_to(m)

    fh = st.session_state.flight_height
    for obs in st.session_state.obstacles_list:
        try:
            coords_gcj = obs["geojson"]["geometry"]["coordinates"][0]
            coords_wgs = []
            for coord in coords_gcj:
                wlat, wlng = gcj02_to_wgs84(coord[1], coord[0])
                coords_wgs.append([wlat, wlng])
            oh = float(obs.get("height_m", 0))
            can = fh > oh
            color = "green" if can else "red"
            folium.Polygon(
                locations=coords_wgs, color=color, weight=3, fillOpacity=0.35,
                popup="{}<br>障碍: {}m / 飞高: {}m<br>{}".format(
                    obs["name"], oh, fh, "可飞越" if can else "需绕行")
            ).add_to(m)
            clat = sum(p[0] for p in coords_wgs)/len(coords_wgs)
            clng = sum(p[1] for p in coords_wgs)/len(coords_wgs)
            folium.Marker(
                [clat, clng],
                icon=folium.DivIcon(
                    html='<div style="font-size:11px;font-weight:bold;color:{};'
                         'background:rgba(255,255,255,0.85);padding:2px 4px;'
                         'border-radius:3px;">{}m</div>'.format(
                             "red" if not can else "darkgreen", oh),
                    icon_size=(55, 22), icon_anchor=(27, 11)
                )
            ).add_to(m)
        except:
            continue

    if st.session_state.waypoints and len(st.session_state.waypoints) >= 2:
        folium.PolyLine(
            st.session_state.waypoints,
            color="blue", weight=5, opacity=0.9, popup="规划航线"
        ).add_to(m)
        for i, wp in enumerate(st.session_state.waypoints[1:-1]):
            folium.CircleMarker(
                wp, radius=5, color="blue", fill=True, fill_color="white",
                popup="绕行点 {}".format(i+1)
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
                glat, glng = wgs84_to_gcj02(coord[1], coord[0])
                coords_gcj.append([glng, glat])
            st.session_state.obstacles_list.append({
                "id": len(st.session_state.obstacles_list),
                "name": "障碍物_{}".format(len(st.session_state.obstacles_list)+1),
                "height_m": 10.0,
                "geojson": {"type": "Feature",
                            "geometry": {"type": "Polygon", "coordinates": [coords_gcj]}}
            })
            st.session_state.waypoints = []
            st.rerun()
    return m

# ==================== 飞行监控 ====================
def start_flight():
    if len(st.session_state.waypoints) < 2:
        st.error("请先生成航线"); return
    st.session_state.is_flying = True
    st.session_state.current_wp_index = 0
    st.session_state.flight_start_time = time.time()
    st.session_state.total_flight_distance = calculate_total_distance(st.session_state.waypoints)
    st.session_state.battery = 100
    st.session_state.monitor_messages = ["飞行任务开始"]

def pause_flight():
    st.session_state.is_flying = False
    st.session_state.monitor_messages.append("飞行暂停")

def resume_flight():
    st.session_state.is_flying = True
    st.session_state.monitor_messages.append("飞行恢复")

def stop_flight():
    st.session_state.is_flying = False
    st.session_state.current_wp_index = 0
    st.session_state.flight_start_time = None
    st.session_state.monitor_messages.append("飞行任务结束")

def update_flight():
    if not st.session_state.is_flying or not st.session_state.flight_start_time:
        return
    elapsed = time.time() - st.session_state.flight_start_time
    traveled = st.session_state.flight_speed * elapsed
    total = st.session_state.total_flight_distance
    st.session_state.battery = max(0, 100 - (elapsed/(total/st.session_state.flight_speed+5))*100)
    accumulated = 0
    for i in range(len(st.session_state.waypoints)-1):
        seg = haversine_distance(
            st.session_state.waypoints[i][0], st.session_state.waypoints[i][1],
            st.session_state.waypoints[i+1][0], st.session_state.waypoints[i+1][1])
        if traveled <= accumulated + seg:
            st.session_state.current_wp_index = i; break
        accumulated += seg
    if traveled >= total:
        st.session_state.is_flying = False
        st.session_state.current_wp_index = len(st.session_state.waypoints)-1
        st.session_state.monitor_messages.append("飞行任务完成")

def run_flight_monitor():
    st.subheader("飞行实时监控")
    update_flight()
    c1,c2,c3,c4,c5,c6 = st.columns(6)
    with c1: st.metric("当前航点", "{}/{}".format(
        st.session_state.current_wp_index+1, len(st.session_state.waypoints)))
    with c2: st.metric("飞行速度", "{} m/s".format(st.session_state.flight_speed))
    elapsed = (time.time()-st.session_state.flight_start_time) if st.session_state.flight_start_time else 0
    with c3: st.metric("已用时间", "{:02d}:{:02d}".format(int(elapsed//60), int(elapsed%60)))
    traveled = st.session_state.flight_speed * elapsed
    remaining = max(0, st.session_state.total_flight_distance - traveled)
    with c4: st.metric("剩余距离", "{} m".format(int(remaining)))
    rt = remaining/st.session_state.flight_speed if st.session_state.flight_speed > 0 else 0
    with c5: st.metric("预计到达", "{:02d}:{:02d}".format(int(rt//60), int(rt%60)))
    with c6: st.metric("电量", "{}%".format(int(st.session_state.battery)))
    prog = traveled/st.session_state.total_flight_distance if st.session_state.total_flight_distance > 0 else 0
    st.progress(min(1.0, prog))
    st.markdown("### 通信链路")
    l1,l2,l3 = st.columns(3)
    with l1: st.success("GCS 在线")
    with l2: st.success("OBC 在线")
    with l3: st.success("FCU 在线")
    st.text_area("飞行日志", "\n".join(st.session_state.monitor_messages[-10:]),
                 height=150, disabled=True)
    b1,b2,b3,b4 = st.columns(4)
    with b1:
        if st.button("开始飞行", disabled=st.session_state.is_flying):
            start_flight(); st.rerun()
    with b2:
        if st.button("暂停", disabled=not st.session_state.is_flying):
            pause_flight(); st.rerun()
    with b3:
        if st.button("继续", disabled=st.session_state.is_flying):
            resume_flight(); st.rerun()
    with b4:
        if st.button("结束任务"):
            stop_flight(); st.rerun()
    if st.session_state.is_flying:
        time.sleep(0.5); st.rerun()

# ==================== 页面路由 ====================
if page == "航线规划":
    st.header("智能航线规划")

    c1,c2,c3,c4 = st.columns(4)
    with c1:
        nh = st.number_input("飞行高度 (m)", min_value=5, max_value=200,
                              value=st.session_state.flight_height, step=5)
        if nh != st.session_state.flight_height:
            st.session_state.flight_height = nh; st.session_state.waypoints = []
    with c2:
        nr = st.number_input("安全半径 (m)", min_value=1.0, max_value=50.0,
                              value=st.session_state.safe_radius, step=1.0)
        if nr != st.session_state.safe_radius:
            st.session_state.safe_radius = nr; st.session_state.waypoints = []
    with c3:
        ns = st.number_input("飞行速度 (m/s)", min_value=1.0, max_value=30.0,
                              value=st.session_state.flight_speed, step=0.5)
        if ns != st.session_state.flight_speed:
            st.session_state.flight_speed = ns
    with c4:
        strat = st.selectbox("绕行策略", ["向左绕行", "向右绕行", "最佳航线"],
                              index=["向左绕行","向右绕行","最佳航线"].index(
                                  st.session_state.bypass_strategy))
        if strat != st.session_state.bypass_strategy:
            st.session_state.bypass_strategy = strat; st.session_state.waypoints = []

    if st.session_state.obstacles_list:
        max_h = max(float(o.get("height_m",0)) for o in st.session_state.obstacles_list)
        fh = st.session_state.flight_height
        if fh > max_h:
            st.success("飞行高度 {}m 高于所有障碍物（最高 {}m），全程可直飞".format(fh, max_h))
        else:
            nb = [o["name"] for o in st.session_state.obstacles_list
                  if float(o.get("height_m",0)) >= fh]
            st.warning("以下障碍物高于飞行高度，将水平绕行：{}".format(", ".join(nb)))

    cA, cB = st.columns(2)
    with cA:
        la  = st.number_input("起点A 纬度(GCJ-02)", value=st.session_state.point_a_gcj[0], format="%.6f")
        loa = st.number_input("起点A 经度(GCJ-02)", value=st.session_state.point_a_gcj[1], format="%.6f")
        if st.button("设置 A 点"):
            st.session_state.point_a_gcj = (la, loa); st.session_state.waypoints = []; st.rerun()
    with cB:
        lb  = st.number_input("终点B 纬度(GCJ-02)", value=st.session_state.point_b_gcj[0], format="%.6f")
        lob = st.number_input("终点B 经度(GCJ-02)", value=st.session_state.point_b_gcj[1], format="%.6f")
        if st.button("设置 B 点"):
            st.session_state.point_b_gcj = (lb, lob); st.session_state.waypoints = []; st.rerun()

    st.divider()
    st.subheader("障碍物圈选与高度配置")

    if st.session_state.obstacles_list:
        for idx, obs in enumerate(st.session_state.obstacles_list):
            h1,h2,h3 = st.columns([3,2,1])
            with h1:
                oh = float(obs.get("height_m",0))
                can = st.session_state.flight_height > oh
                st.write("**{} {}** — {}m {}".format(
                    "v" if can else "!", obs["name"], oh,
                    "(可飞越)" if can else "(需绕行)"))
            with h2:
                new_oh = st.number_input("高度(m)", value=float(obs["height_m"]),
                                          key="h_{}".format(idx), step=1.0)
                if new_oh != st.session_state.obstacles_list[idx]["height_m"]:
                    st.session_state.obstacles_list[idx]["height_m"] = new_oh
                    st.session_state.waypoints = []
            with h3:
                if st.button("删除", key="del_{}".format(idx)):
                    st.session_state.obstacles_list.pop(idx)
                    st.session_state.waypoints = []; st.rerun()
    else:
        st.info("暂无障碍物，请在地图上绘制多边形进行圈选。")

    cs1,cs2,cs3 = st.columns(3)
    with cs1:
        if st.button("保存所有障碍物"): save_all_obstacles()
    with cs2:
        if st.button("加载障碍物"):
            load_all_obstacles(); st.session_state.waypoints = []; st.rerun()
    with cs3:
        if st.button("清除全部障碍物"):
            clear_all_obstacles(); st.rerun()

    draw_full_map()
    st.divider()

    cgen, cinfo = st.columns([1,2])
    with cgen:
        if st.button("生成航线", use_container_width=True):
            if st.session_state.obstacles_list:
                wps, msgs = plan_route(st.session_state.bypass_strategy)
                if len(wps) >= 2:
                    st.session_state.waypoints = wps
                    for msg in msgs:
                        if "绕行" in msg: st.warning(msg)
                        else: st.info(msg)
                    total = calculate_total_distance(wps)
                    st.success("航线已生成！共 {} 个航点，总距离 {} 米".format(len(wps), int(total)))
                    st.rerun()
                else:
                    st.warning("航线生成失败")
            else:
                a_lat, a_lng = gcj02_to_wgs84(st.session_state.point_a_gcj[0],
                                               st.session_state.point_a_gcj[1])
                b_lat, b_lng = gcj02_to_wgs84(st.session_state.point_b_gcj[0],
                                               st.session_state.point_b_gcj[1])
                st.session_state.waypoints = [[a_lat, a_lng], [b_lat, b_lng]]
                total = haversine_distance(a_lat, a_lng, b_lat, b_lng)
                st.success("无障碍物，航线已生成！总距离 {} 米".format(int(total)))
                st.rerun()
    with cinfo:
        if st.session_state.waypoints:
            st.info("当前航线：{} 个航点，安全半径 {}m，策略：{}".format(
                len(st.session_state.waypoints),
                st.session_state.safe_radius,
                st.session_state.bypass_strategy))
        else:
            st.info("点击「生成航线」规划飞行路径")

else:
    run_flight_monitor()
