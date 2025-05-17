import streamlit as st
import pandas as pd
import folium
import osmnx as ox
from geopy.distance import geodesic
from opencage.geocoder import OpenCageGeocode

# -- OpenCage API Key --
OPENCAGE_API_KEY = "0d01f656fc7042dbb49dbbc548fd6d62"
geocoder = OpenCageGeocode(OPENCAGE_API_KEY)

st.set_page_config(page_title="Domino's Route Optimizer", layout="wide")
st.title("🍕 Domino's Nearest Branch Route Optimizer")

# -- Load branches --
@st.cache_data
def load_branches():
    return pd.read_csv("dataset_ddun.csv")

# -- Geocode destination address --
@st.cache_data
def geocode_address(address):
    result = geocoder.geocode(f"{address}, Dehradun, India")
    if result:
        return result[0]['geometry']['lat'], result[0]['geometry']['lng']
    return None, None

# -- Find nearest branch --
def find_nearest_branch(dest_coords, df):
    df["Distance"] = df.apply(
        lambda row: geodesic((row["Latitude"], row["Longitude"]), dest_coords).meters,
        axis=1
    )
    return df.loc[df["Distance"].idxmin()]

# -- Build graph and route --
def get_route_map(start_coords, end_coords):
    mid_lat = (start_coords[0] + end_coords[0]) / 2
    mid_lng = (start_coords[1] + end_coords[1]) / 2

    try:
        G = ox.graph_from_point((mid_lat, mid_lng), dist=8000, network_type='drive')
        orig_node = ox.distance.nearest_nodes(G, start_coords[1], start_coords[0])
        dest_node = ox.distance.nearest_nodes(G, end_coords[1], end_coords[0])
        path = ox.shortest_path(G, orig_node, dest_node, weight="length")
        route_coords = [(G.nodes[n]['y'], G.nodes[n]['x']) for n in path]

        m = folium.Map(location=[mid_lat, mid_lng], zoom_start=13)
        folium.Marker(start_coords, tooltip="Domino's Branch", icon=folium.Icon(color="green")).add_to(m)
        folium.Marker(end_coords, tooltip="Delivery Destination", icon=folium.Icon(color="red")).add_to(m)
        folium.PolyLine(route_coords, color="blue", weight=5).add_to(m)

        map_file = "route_map.html"
        m.save(map_file)
        return map_file

    except Exception as e:
        st.error(f"Routing failed: {e}")
        return None

# -- Main UI --
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
        st.write("📍 **Start Coordinates**:", start_coords)
        st.write("📍 **End Coordinates**:", dest_coords)

        route_map = get_route_map(start_coords, dest_coords)
        if route_map:
            with open(route_map, 'r', encoding='utf-8') as f:
                st.components.v1.html(f.read(), height=600)
