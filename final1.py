import streamlit as st
import folium
import osmnx as ox
import pandas as pd
from opencage.geocoder import OpenCageGeocode
import os
import heapq
from collections import defaultdict
from geopy.distance import geodesic

st.set_page_config(page_title="🍕 Dehradun Domino's Route Optimizer", layout="wide")
st.markdown("""
    <style>
        html, body, [class*="css"]  {
            font-size: 18px;
        }
        h1 {
            font-size: 40px !important;
        }
        h2 {
            font-size: 30px !important;
        }
        h3 {
            font-size: 24px !important;
        }
        .stTabs [role="tab"] {
            font-size: 18px;
        }
    </style>
""", unsafe_allow_html=True)

st.title("🍕 Domino's Dehradun Route Optimizer")

OPENCAGE_API_KEY = "0d01f656fc7042dbb49dbbc548fd6d62"
geocoder = OpenCageGeocode(OPENCAGE_API_KEY)

# --- Load Branch Data ---
@st.cache_data
def load_branch_data():
    df = pd.read_csv("dataset_ddun.csv", quotechar='"')
    return df, {row['Branch']: (row['Latitude'], row['Longitude']) for idx, row in df.iterrows()}

# --- Geocode Address ---
@st.cache_data
def get_coordinates_cached(address):
    query = f"{address}, Dehradun, India"
    result = geocoder.geocode(query)
    if result and len(result):
        # Extract important quality fields
        confidence = result[0].get("confidence", 0)
        components = result[0].get("components", {})
        match_type = result[0].get("components", {}).get("_type", "")

        # Accept only high-confidence full address or road-level match
        if confidence >= 6 and match_type in ["road", "house", "building", "residential"]:
            lat = result[0]['geometry']['lat']
            lng = result[0]['geometry']['lng']
            return lat, lng

    return None, None


# --- Load or Create Graph ---
def load_or_create_graph(lat, lng, dist=8000):
    graph_path = f"dehradun_graph_{lat}_{lng}_{dist}.graphml"
    if os.path.exists(graph_path):
        G = ox.load_graphml(graph_path)
    else:
        G = ox.graph_from_point((lat, lng), dist=dist, network_type='drive')
        ox.save_graphml(G, graph_path)
    return G

# --- Dijkstra ---
def custom_dijkstra(G, source, target):
    adj = defaultdict(list)
    for u, v, data in G.edges(data=True):
        weight = data.get('length', 1)
        adj[u].append((v, weight))
        if not data.get('oneway', False):
            adj[v].append((u, weight))

    heap = [(0, source, [])]
    visited = set()

    while heap:
        (cost, node, path) = heapq.heappop(heap)
        if node in visited:
            continue
        visited.add(node)
        path = path + [node]
        if node == target:
            return path
        for neighbor, weight in adj[node]:
            if neighbor not in visited:
                heapq.heappush(heap, (cost + weight, neighbor, path))
    return []

# --- Route Map ---
def plot_route_map(start_coords, end_coords):
    start_lat, start_lng = start_coords
    end_lat, end_lng = end_coords

    try:
        mid_lat = (start_lat + end_lat) / 2
        mid_lng = (start_lng + end_lng) / 2
        dist_m = int(geodesic((start_lat, start_lng), (end_lat, end_lng)).meters)
        graph_radius = max(dist_m // 2 + 2000, 3000)

        G = load_or_create_graph(mid_lat, mid_lng, dist=graph_radius)
        orig_node = ox.distance.nearest_nodes(G, start_lng, start_lat)
        dest_node = ox.distance.nearest_nodes(G, end_lng, end_lat)

        path = custom_dijkstra(G, orig_node, dest_node)
        if not path or len(path) < 2:
            st.error("❌ Route could not be calculated.")
            return None

        route_coords = [(G.nodes[n]['y'], G.nodes[n]['x']) for n in path]
        center_lat = (min([c[0] for c in route_coords]) + max([c[0] for c in route_coords])) / 2
        center_lng = (min([c[1] for c in route_coords]) + max([c[1] for c in route_coords])) / 2

        m = folium.Map(location=[center_lat, center_lng], zoom_start=14)
        folium.Marker([start_lat, start_lng], popup="Start (Branch)", icon=folium.Icon(color='green')).add_to(m)
        folium.Marker([end_lat, end_lng], popup="Delivery Destination", icon=folium.Icon(color='red')).add_to(m)
        folium.PolyLine(route_coords, color="blue", weight=5, opacity=0.8).add_to(m)

        map_file = "route_map.html"
        m.save(map_file)
        return map_file

    except Exception as e:
        st.error(f"❌ Routing failed: {e}")
        return None

# --- Find Nearest Branch ---
def find_nearest_branch(dest_coords, df):
    df["Distance"] = df.apply(
        lambda row: geodesic((row["Latitude"], row["Longitude"]), dest_coords).meters,
        axis=1
    )
    nearest_row = df.loc[df["Distance"].idxmin()]
    return nearest_row["Branch"], (nearest_row["Latitude"], nearest_row["Longitude"])

# --- Load Data ---
branch_df, branch_coords_dict = load_branch_data()

# --- Tabs ---
tab1, tab2 = st.tabs(["🚀 Automatic Mode", "🛠️ Manual Mode"])

with tab1:
    st.subheader("🚀 Automatic Mode – Nearest Branch Selected")
    destination = st.text_input("🏠 Enter Delivery Destination", key="auto_input", placeholder="e.g. ONGC Chowk, Dehradun")
    show_info_auto = st.checkbox("Show Info Panel", value=True, key="auto_info")

    if st.button("🔍 Find Route Automatically"):
        dest_coords = get_coordinates_cached(destination)
        if None in dest_coords:
            st.error("❌ Geocoding failed.")
        else:
            selected_branch, start_coords = find_nearest_branch(dest_coords, branch_df)
            if show_info_auto:
                st.markdown("### ℹ️ Route Details")
                st.markdown(f"**Delivery Address:** {destination}")
                st.markdown(f"**Nearest Branch:** {selected_branch}")
            map_file = plot_route_map(start_coords, dest_coords)
            if map_file:
                st.success("✅ Route generated successfully!")
                with open(map_file, 'r', encoding='utf-8') as f:
                    st.components.v1.html(f.read(), height=600)

with tab2:
    st.subheader("🛠️ Manual Mode – Select Branch")
    destination = st.text_input("🏠 Enter Delivery Destination", key="manual_input", placeholder="e.g. GMS Road, Dehradun")
    selected_branch = st.selectbox("📍 Select Branch", list(branch_coords_dict.keys()))
    show_info_manual = st.checkbox("Show Info Panel", value=True, key="manual_info")

    if st.button("📍 Show Route Manually"):
        dest_coords = get_coordinates_cached(destination)
        if None in dest_coords:
            st.error("❌ Geocoding failed.")
        else:
            start_coords = branch_coords_dict[selected_branch]
            if show_info_manual:
                st.markdown("### ℹ️ Route Details")
                st.markdown(f"**Delivery Address:** {destination}")
                st.markdown(f"**Selected Branch:** {selected_branch}")
            map_file = plot_route_map(start_coords, dest_coords)
            if map_file:
                st.success("✅ Route generated successfully!")
                with open(map_file, 'r', encoding='utf-8') as f:
                    st.components.v1.html(f.read(), height=600)
