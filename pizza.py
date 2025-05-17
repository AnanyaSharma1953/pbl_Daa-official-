import streamlit as st
import folium
import osmnx as ox
import pandas as pd
from opencage.geocoder import OpenCageGeocode
import os
from math import radians, cos, sin, asin, sqrt

# Streamlit Config
st.set_page_config(page_title="Dehradun Pizza Route Optimizer")
st.title("🍕 Domino's Dehradun Route Optimizer")

# OpenCage API Setup
OPENCAGE_API_KEY = "0d01f656fc7042dbb49dbbc548fd6d62"
geocoder = OpenCageGeocode(OPENCAGE_API_KEY)

# Haversine Distance (in km)
def haversine(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    km = 6371 * c
    return km

# Load Branch Locations
@st.cache_data
def load_branch_data():
    df = pd.read_csv("dataset_ddun.csv")
    return {row['Branch']: (row['Latitude'], row['Longitude']) for idx, row in df.iterrows()}

# Geocode and cache results
@st.cache_data
def get_coordinates_cached(address):
    query = f"{address}, Dehradun, India"
    result = geocoder.geocode(query)
    if result and len(result):
        return result[0]['geometry']['lat'], result[0]['geometry']['lng']
    return None, None

# Routing logic using built-in shortest path
def compute_path(G, orig_node, dest_node):
    return ox.shortest_path(G, orig_node, dest_node, weight='length')

# Load or generate road graph
def load_or_create_graph(lat, lng, dest_lat, dest_lng, dist=4000):
    graph_path = "dehradun_graph.graphml"
    distance_km = haversine(lat, lng, dest_lat, dest_lng)
    simplify_level = distance_km > 10  # simplify=True for long distance, False for detailed nearby routes

    st.write(f"📏 Distance between points: {distance_km:.2f} km | Simplify Graph: {simplify_level}")

    if os.path.exists(graph_path):
        G = ox.graph_from_point((lat, lng), dist=6000, network_type='drive', simplify=simplify_level)
    return G

# Build and plot route map
def plot_route_map(start_coords, end_address):
    start_lat, start_lng = start_coords
    end_lat, end_lng = get_coordinates_cached(end_address)

    st.write("📍 Start Coordinates:", start_lat, start_lng)
    st.write("📍 End Coordinates:", end_lat, end_lng)

    if None in (start_lat, start_lng, end_lat, end_lng):
        st.error("❌ Geocoding failed: Delivery address could not be located.")
        return None

    try:
        G = load_or_create_graph(start_lat, start_lng, end_lat, end_lng, dist=4000)
    except ValueError as ve:
        st.error("❌ Failed to create or load graph: " + str(ve))
        return None

    try:
        orig_node = ox.distance.nearest_nodes(G, start_lng, start_lat)
        dest_node = ox.distance.nearest_nodes(G, end_lng, end_lat)
        path = compute_path(G, orig_node, dest_node)
        if not path or len(path) < 2:
            st.error("❌ Route could not be calculated.")
            return None
    except Exception as e:
        st.error(f"❌ Routing failed: {e}")
        return None

    route_coords = [(G.nodes[n]['y'], G.nodes[n]['x']) for n in path]

    m = folium.Map(location=[start_lat, start_lng], zoom_start=13)
    folium.Marker([start_lat, start_lng], popup="Start (Branch)", icon=folium.Icon(color='green')).add_to(m)
    folium.Marker([end_lat, end_lng], popup="Delivery Destination", icon=folium.Icon(color='red')).add_to(m)
    folium.PolyLine(route_coords, color="blue", weight=5, opacity=0.9).add_to(m)

    map_file = "optimized_dijkstra_map.html"
    m.save(map_file)
    return map_file

# Streamlit Input & UI
branch_coords = load_branch_data()
branches = list(branch_coords.keys())

selected_branch = st.selectbox("📍 Select Domino's Branch", branches)
destination = st.text_input("🏠 Enter Delivery Destination", placeholder="e.g. ONGC chowk, Dehradun")

if st.button("🚗 Get Route"):
    if selected_branch and destination:
        start_coords = branch_coords[selected_branch]
        map_file = plot_route_map(start_coords, destination)
        if map_file:
            st.success("✅ Route generated!")
            with open(map_file, 'r', encoding='utf-8') as f:
                st.components.v1.html(f.read(), height=600)
    else:
        st.warning("⚠️ Please select a branch and enter a delivery address.")
