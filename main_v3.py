import streamlit as st
import pandas as pd
import numpy as np
import time
import json
import os
from datetime import datetime
import plotly.graph_objects as go
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium

# --- 坐标系转换工具 (WGS-84 与 GCJ-02) ---
def wgs84_to_gcj02(lng, lat):
    """将 GPS 坐标转换为高德/腾讯地图坐标"""
    a, ee = 6378245.0, 0.00669342162296594323
    import math
    def _transformlat(x, y):
        ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
        ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
        ret += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
        ret += (160.0 * math.sin(y / 12.0 * math.pi) + 320 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
        return ret
    def _transformlng(x, y):
        ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
        ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
        ret += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
        ret += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x * math.pi / 30.0)) * 2.0 / 3.0
        return ret
    dlat = _transformlat(lng - 105.0, lat - 35.0)
    dlng = _transformlng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * math.pi
    magic = math.sin(radlat); magic = 1 - ee * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * math.pi)
    dlng = (dlng * 180.0) / (a / sqrtmagic * math.cos(radlat) * math.pi)
    return lng + dlng, lat + dlat

# --- 障碍物持久化存储 ---
SAVE_FILE = "uav_data.json"
def load_data():
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, "r") as f: return json.load(f)
    return {"obstacles": [], "point_a": [32.2325, 118.7845], "point_b": [32.2345, 118.7865]}

def save_data(data):
    with open(SAVE_FILE, "w") as f: json.dump(data, f)

# --- 初始化状态 ---
if 'history' not in st.session_state: st.session_state.history = []
if 'uav_online' not in st.session_state: st.session_state.uav_online = False
if 'db' not in st.session_state: st.session_state.db = load_data()

# --- 页面配置 ---
st.set_page_config(page_title="南京科技职业技术学院 - 无人机平台", layout="wide")
st.sidebar.image("https://www.streamlit.io/images/brand/streamlit-logo-secondary-colormark-darktext.png", width=150)
nav = st.sidebar.radio("导航菜单", ["航线规划", "飞行监控"])

# --- 页面 1: 航线规划 (3D地图与障碍物) ---
if nav == "航线规划":
    st.header("🗺️ 校园航线规划 (南京科技职业技术学院)")
    
    col_map, col_ctrl = st.columns([3, 1])
    
    with col_ctrl:
        st.subheader("坐标设置 (GCJ-02)")
        a_lat = st.number_input("起点 A 纬度", value=st.session_state.db["point_a"][0], format="%.6f")
        a_lng = st.number_input("起点 A 经度", value=st.session_state.db["point_a"][1], format="%.6f")
        b_lat = st.number_input("终点 B 纬度", value=st.session_state.db["point_b"][0], format="%.6f")
        b_lng = st.number_input("终点 B 经度", value=st.session_state.db["point_b"][1], format="%.6f")
        
        if st.button("更新并保存坐标"):
            st.session_state.db["point_a"] = [a_lat, a_lng]
            st.session_state.db["point_b"] = [b_lat, b_lng]
            save_data(st.session_state.db)
            st.success("坐标已更新")

        st.divider()
        st.info("操作提示：\n1. 使用地图左侧工具圈选障碍物。\n2. 点击下方按钮保存到云端。")
        
        if st.button("🗑️ 清空所有障碍物"):
            st.session_state.db["obstacles"] = []
            save_data(st.session_state.db)
            st.rerun()

    with col_map:
        # 创建地图，使用 Esri 卫星图层实现“3D/实况”感
        m = folium.Map(location=[(a_lat+b_lat)/2, (a_lng+b_lng)/2], zoom_start=17,
                       tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                       attr='Esri Satellite')

        # 绘制已保存的障碍物
        for obs in st.session_state.db["obstacles"]:
            folium.Polygon(locations=obs, color="red", fill=True, fill_opacity=0.5, popup="障碍区").add_to(m)

        # 绘制 A, B 点
        folium.Marker([a_lat, a_lng], tooltip="起点 A", icon=folium.Icon(color='green', icon='play')).add_to(m)
        folium.Marker([b_lat, b_lng], tooltip="终点 B", icon=folium.Icon(color='blue', icon='flag')).add_to(m)
        folium.PolyLine([[a_lat, a_lng], [b_lat, b_lng]], color="yellow", weight=2, dash_array='5').add_to(m)

        # 启用绘制工具
        draw = Draw(export=False, draw_options={'polyline':False, 'circle':False, 'marker':False, 'circlemarker':False, 'rectangle':True, 'polygon':True})
        draw.add_to(m)

        # 渲染地图
        map_output = st_folium(m, width=900, height=600, key="campus_map")

        # 捕获新绘制的障碍物
        if map_output and map_output['all_drawings']:
            if st.button("💾 确认并保存新圈选的障碍物"):
                new_obs = []
                for feat in map_output['all_drawings']:
                    coords = feat['geometry']['coordinates'][0]
                    new_obs.append([[c[1], c[0]] for c in coords])
                st.session_state.db["obstacles"] = new_obs
                save_data(st.session_state.db)
                st.rerun()

# --- 页面 2: 飞行监控 (心跳包与报警) ---
elif nav == "飞行监控":
    st.header("🛰️ 无人机飞行监控系统")
    
    col_stat, col_chart = st.columns([1, 2])
    
    with col_stat:
        st.subheader("链路状态")
        online = st.toggle("开启地面站接收机", value=st.session_state.uav_online)
        st.session_state.uav_online = online
        status_placeholder = st.empty()
        st.metric("已接收数据包", len(st.session_state.history))

    with col_chart:
        chart_placeholder = st.empty()
        table_placeholder = st.empty()

    if st.session_state.uav_online:
        while st.session_state.uav_online:
            now_time = datetime.now().strftime("%H:%M:%S")
            # 模拟随机心跳（含10%丢包）
            is_received = np.random.choice([True, False], p=[0.9, 0.1])
            st.session_state.history.append({
                "序号": len(st.session_state.history) + 1,
                "时间": now_time,
                "状态": 1 if is_received else 0
            })
            
            # 数据切片（仅看最近30秒）
            df = pd.DataFrame(st.session_state.history[-30:])
            
            # 逻辑：连续3秒未收到心跳则报警
            if len(df) >= 3 and df['状态'].tail(3).sum() == 0:
                status_placeholder.error(f"🚨 连接超时！连续3秒未收到心跳包\n最后更新: {now_time}")
            else:
                status_placeholder.success(f"📡 信号强 - 序号: {len(st.session_state.history)}")

            # 绘制 Plotly 折线图
            fig = go.Figure(go.Scatter(x=df['时间'], y=df['状态'], mode='lines+markers', line_color='#1f77b4'))
            fig.update_layout(height=300, margin=dict(l=0,r=0,t=0,b=0), yaxis=dict(tickvals=[0,1], ticktext=["丢失","正常"]))
            chart_placeholder.plotly_chart(fig, use_container_width=True)
            
            # 简易表格显示
            table_placeholder.table(df.tail(5))
            
            time.sleep(1)
            if not st.session_state.uav_online: break

