import streamlit as st
import pandas as pd
import folium
import osmnx as ox
from geopy.distance import geodesic
from opencage.geocoder import OpenCageGeocode
import os
import heapq
from collections import defaultdict

# OpenCage API Key
OPENCAGE_API_KEY = "0d01f656fc7042dbb49dbbc548fd6d62"
geocoder = OpenCageGeocode(OPENCAGE_API_KEY)

st.set_page_config(page_title="Domino's Route Optimizer", layout="wide")
st.title("🍕 Domino's Nearest Branch Route Optimizer")

# Load branches CSV
@st.cache_data
def load_branches():
    return pd.read_csv("dataset_ddun.csv")

# Geocode destination address
def geocode_address(address):
    result = geocoder.geocode(f"{address}, Dehradun, India")
    if result:
        return result[0]['geometry']['lat'], result[0]['geometry']['lng']
    return None, None

# Find nearest branch to destination
def find_nearest_branch(dest_coords, df):
    df["Distance"] = df.apply(
        lambda row: geodesic((row["Latitude"], row["Longitude"]), dest_coords).meters,
        axis=1
    )
    return df.loc[df["Distance"].idxmin()]

# Load or create graph
def load_or_create_graph_dynamic(lat1, lng1, lat2, lng2):
    dist_meters = geodesic((lat1, lng1), (lat2, lng2)).meters
    buffer = 3000
    dist = max(dist_meters + buffer, 4000)

    graph_path = "dehradun_dynamic.graphml"
    if os.path.exists(graph_path):
        G = ox.load_graphml(graph_path)
        nodes_gdf = ox.graph_to_gdfs(G, edges=False)
        minx, miny, maxx, maxy = nodes_gdf.total_bounds
        if not (minx <= lng1 <= maxx and miny <= lat1 <= maxy and minx <= lng2 <= maxx and miny <= lat2 <= maxy):
            st.info("📢 Graph area too small, rebuilding...")
            G = ox.graph_from_point((lat1, lng1), dist=dist, network_type='drive')
            ox.save_graphml(G, graph_path)
    else:
        G = ox.graph_from_point((lat1, lng1), dist=dist, network_type='drive')
        ox.save_graphml(G, graph_path)
    return G

# Custom Dijkstra’s algorithm
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

# Build and save route map
def get_route_map(start_coords, end_coords, G):
    try:
        orig_node = ox.distance.nearest_nodes(G, start_coords[1], start_coords[0])
        dest_node = ox.distance.nearest_nodes(G, end_coords[1], end_coords[0])
        path = custom_dijkstra(G, orig_node, dest_node)

        if not path or len(path) < 2:
            st.error("❌ No valid route found.")
            return None

        route_coords = [(G.nodes[n]['y'], G.nodes[n]['x']) for n in path]

        mid_lat = (start_coords[0] + end_coords[0]) / 2
        mid_lng = (start_coords[1] + end_coords[1]) / 2
        m = folium.Map(location=[mid_lat, mid_lng], zoom_start=13)

        folium.Marker(start_coords, tooltip="Domino's Branch", icon=folium.Icon(color="green")).add_to(m)
        folium.Marker(end_coords, tooltip="Delivery Destination", icon=folium.Icon(color="red")).add_to(m)
        folium.PolyLine(route_coords, color="blue", weight=5).add_to(m)

        map_file = "route_map_dynamic.html"
        m.save(map_file)
        return map_file

    except Exception as e:
        st.error(f"Routing failed: {e}")
        return None

# Main UI
branches_df = load_branches()
destination = st.text_input("📍 Enter your delivery destination (in Dehradun):")

if st.button("🚗 Show Nearest Branch & Route") and destination:
    dest_coords = geocode_address(destination)

    if None in dest_coords:
        st.error("❌ Geocoding failed. Try a more specific location.")
    else:
        nearest = find_nearest_branch(dest_coords, branches_df)
        start_coords = (nearest["Latitude"], nearest["Longitude"])

        st.success(f"✅ Nearest Domino's Branch: {nearest['Branch']}")

        G = load_or_create_graph_dynamic(start_coords[0], start_coords[1], dest_coords[0], dest_coords[1])
        route_map = get_route_map(start_coords, dest_coords, G)

        if route_map:
            with open(route_map, 'r', encoding='utf-8') as f:
                st.components.v1.html(f.read(), height=600)
