import pandas as pd
import streamlit as st
from thefuzz import fuzz
import re
import spacy
from spacy.tokens import Span

# Load spaCy model for NER
nlp = spacy.load("en_core_web_sm")

# File path to the CSV from GitHub
file_path = 'https://raw.githubusercontent.com/aavadhan10/Conflict-Checks/main/combined_contact_and_matters.csv'

@st.cache_data
def load_data():
    # Load the CSV file from GitHub, fill NaN with empty strings to avoid errors
    return pd.read_csv(file_path).fillna("")

# Function to perform fuzzy conflict check and identify the matter numbers
def fuzzy_conflict_check(full_name, email, phone_number, threshold=80):
    matching_records = []
    for index, row in data.iterrows():
        client_name = str(row['Client Name'])
        name_match = fuzz.partial_ratio(client_name, full_name)
        if name_match >= threshold:
            matching_records.append(row)
    return pd.DataFrame(matching_records)

# Function to check for potential conflicts in matter descriptions
def check_matter_conflicts(matching_records, full_name):
    direct_conflicts = []
    positional_conflicts = []
    personal_conflicts = []
    involved_parties = []

    for index, row in matching_records.iterrows():
        matter_description = str(row['Matter Description']).lower()
        client_name = row['Client Name'].lower()

        # Direct Conflicts
        if full_name.lower() in matter_description:
            direct_conflicts.append(row)

        # Personal Conflicts
        if any(name in matter_description for name in [full_name.lower()]):
            personal_conflicts.append(row)
        
        # Example positional conflicts
        if re.search(r'\b(?:opposing|adverse)\b', matter_description):
            positional_conflicts.append(row)

        # Extract entities from matter description using spaCy
        doc = nlp(matter_description)
        for ent in doc.ents:
            if ent.label_ in ["PERSON", "ORG"]:  # Example: Adjust based on the types of entities you're interested in
                involved_parties.append({
                    'Matter Number': row['Matter Number'],
                    'Entity': ent.text,
                    'Label': ent.label_
                })

    return pd.DataFrame(direct_conflicts), pd.DataFrame(positional_conflicts), pd.DataFrame(personal_conflicts), pd.DataFrame(involved_parties)

# Streamlit app
st.title("Scale LLP Conflict Check System")

# Input fields for client information
full_name = st.text_input("Enter Client's Full Name")
email = st.text_input("Enter Client's Email")
phone_number = st.text_input("Enter Client's Phone Number")

# Load the CSV data
data = load_data()

# Buttons
col1, col2 = st.columns([2, 1])
with col1:
    conflict_check_clicked = st.button("Check for Conflict")

with col2:
    create_graph_clicked = st.button("Create Relationship Graph", disabled=not conflict_check_clicked)

if conflict_check_clicked:
    results = fuzzy_conflict_check(full_name, email, phone_number)
    
    if not results.empty:
        # Drop the unnecessary columns
        columns_to_drop = ['Attorney', 'Client', 'Practice Area', 'Matter Number', 'Matter Description']
        results_cleaned = results.drop(columns=[col for col in columns_to_drop if col in results.columns])
        
        # Conflict Analysis
        direct_conflicts, positional_conflicts, personal_conflicts, involved_parties = check_matter_conflicts(results, full_name)

        # Display conflict results
        st.success(f"Conflict found! Scale LLP has previously worked with the client.")
        st.dataframe(results_cleaned)

        if not direct_conflicts.empty:
            st.subheader("Direct Conflicts")
            st.dataframe(direct_conflicts)
        
        if not positional_conflicts.empty:
            st.subheader("Positional Conflicts")
            st.dataframe(positional_conflicts)

        if not personal_conflicts.empty:
            st.subheader("Personal Conflicts")
            st.dataframe(personal_conflicts)

        if not involved_parties.empty:
            st.subheader("Potential Involved or Opposing Parties")
            st.dataframe(involved_parties)
        
    else:
        st.info("No conflicts found. Scale LLP has not worked with this client.")

# Generate the relationship graph when the "Create Relationship Graph" button is clicked
if create_graph_clicked and not results.empty:
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
num_matters = len(data)
st.sidebar.markdown(f"<h2 style='color: #4CAF50;'>Number of Matters Worked with: {num_matters}</h2>", unsafe_allow_html=True)
st.sidebar.markdown(
    "<div style='background-color: #f0f0f5; padding: 10px; border-radius: 5px; border: 1px solid #ccc;'>"
    "<strong>Data Updated from Clio API</strong><br>Last Update: <strong>9/14/2024</strong>"
    "</div>", unsafe_allow_html=True
)

