import pandas as pd
import streamlit as st
import networkx as nx
from pyvis.network import Network
import streamlit.components.v1 as components
from thefuzz import fuzz

# File path to the CSV from GitHub
file_path = 'https://raw.githubusercontent.com/aavadhan10/Conflict-Checks/main/combined_contact_and_matters.csv'

@st.cache_data
def load_data():
    # Load the CSV file from GitHub, fill NaN with empty strings to avoid errors
    return pd.read_csv(file_path).fillna("")

# Function to create a relationship graph using NetworkX and Pyvis
def create_relationship_graph(data):
    G = nx.Graph()

    # Add nodes and edges based on relationships between clients, matters, and attorneys
    for index, row in data.iterrows():
        client = row['Client Name']
        matter = row['Matter']
        attorney = row['Attorney']

        # Add nodes for client, matter, and attorney
        G.add_node(client, label="Client")
        G.add_node(matter, label="Matter")
        if pd.notna(attorney):
            G.add_node(attorney, label="Attorney")

        # Add edges representing relationships
        G.add_edge(client, matter)
        if pd.notna(attorney):
            G.add_edge(attorney, matter)

    return G

# Function to visualize the graph using Pyvis
def visualize_graph(G):
    net = Network(height="750px", width="100%", notebook=False)
    net.from_nx(G)
    return net

# Streamlit app for conflict check and relationship graph
st.title("Scale LLP Conflict Check System with Relationship Graph")

# Input fields for client information
full_name = st.text_input("Enter Client's Full Name")
email = st.text_input("Enter Client's Email")
phone_number = st.text_input("Enter Client's Phone Number")

# Load the CSV data
data = load_data()

# Function to perform fuzzy conflict check and identify the matter numbers
def fuzzy_conflict_check(full_name, email, phone_number, threshold=80):
    matching_records = []

    for index, row in data.iterrows():
        # Ensure the 'Client Name' field is a string before performing the fuzzy match
        client_name = str(row['Client Name'])

        # Fuzzy match for the client name
        name_match = fuzz.partial_ratio(client_name, full_name)

        # Add matching records if the name similarity exceeds the threshold
        if name_match >= threshold:
            matching_records.append(row)

    # Convert list of matching rows to DataFrame
    return pd.DataFrame(matching_records)

# Perform the conflict check if the user has input all fields
if st.button("Check for Conflict"):
    results = fuzzy_conflict_check(full_name, email, phone_number)

    if not results.empty:
        # Drop the unnecessary columns (Attorney, Client, Practice Area, Matter Number, Matter Description)
        columns_to_drop = ['Attorney', 'Client', 'Practice Area', 'Matter Number', 'Matter Description']
        results_cleaned = results.drop(columns=[col for col in columns_to_drop if col in results.columns])

        st.success(f"Conflict found! Scale LLP has previously worked with the client.")
        st.dataframe(results_cleaned)
    else:
        st.info("No conflicts found. Scale LLP has not worked with this client.")

# Create a graph for relationships
G = create_relationship_graph(data)

# Visualize the graph using Pyvis
net = visualize_graph(G)

# Show the graph in Streamlit
net.save_graph('relationship_graph.html')
HtmlFile = open('relationship_graph.html', 'r', encoding='utf-8')
source_code = HtmlFile.read()
components.html(source_code, height=800)

# Sidebar
st.sidebar.title("📊 Data Overview")

# Display number of matters worked with
num_matters = len(data)
st.sidebar.markdown(f"<h2 style='color: #4CAF50;'>Number of Matters Worked with: {num_matters}</h2>", unsafe_allow_html=True)

# Add a banner or button for data update info
st.sidebar.markdown(
    "<div style='background-color: #f0f0f5; padding: 10px; border-radius: 5px; border: 1px solid #ccc;'>"
    "<strong>Data Updated from Clio API</strong><br>Last Update: <strong>9/14/2024</strong>"
    "</div>", unsafe_allow_html=True
)

