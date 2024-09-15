import pandas as pd
import spacy
from thefuzz import fuzz
import streamlit as st

# Load spaCy model for named entity recognition and similarity matching
nlp = spacy.load('en_core_web_md')

# File path to the CSV from GitHub
file_path = 'https://raw.githubusercontent.com/aavadhan10/Conflict-Checks/main/combined_contact_and_matters.csv'

@st.cache_data  # Use st.cache_data for caching data
def load_data():
    # Load the CSV file from GitHub
    return pd.read_csv(file_path).fillna("")

# Function to use spaCy for name matching
def nlp_name_matching(full_name, client_name):
    # Use spaCy NLP to find similarity between full name input and the client name in the data
    doc1 = nlp(full_name)
    doc2 = nlp(client_name)
    return doc1.similarity(doc2)

# Function to perform fuzzy conflict check with NLP enhancements
def nlp_conflict_check(full_name, email, phone_number, threshold=0.8):
    matching_records = []

    for index, row in data.iterrows():
        client_name = str(row['Client Name'])

        # Use spaCy similarity matching instead of simple fuzzy matching
        name_similarity = nlp_name_matching(full_name, client_name)

        # Add matching records if the similarity score exceeds the threshold
        if name_similarity >= threshold:
            matching_records.append(row)

    # Convert list of matching rows to DataFrame
    return pd.DataFrame(matching_records)

# Streamlit app for conflict check
st.title("Scale LLP Conflict Check System")

# Input fields for client information
full_name = st.text_input("Enter Client's Full Name")
email = st.text_input("Enter Client's Email")
phone_number = st.text_input("Enter Client's Phone Number")

# Load the CSV data
data = load_data()

# Perform the conflict check if the user has input all fields
if st.button("Check for Conflict"):
    results = nlp_conflict_check(full_name, email, phone_number)

    if not results.empty:
        st.success(f"Conflict found! Scale LLP has previously worked with the client.")
        
        # Drop unnecessary columns and show only relevant details
        columns_to_drop = ['Attorney', 'Client', 'Practice Area', 'Matter Number', 'Matter Description']
        results_cleaned = results.drop(columns=[col for col in columns_to_drop if col in results.columns])
        st.dataframe(results_cleaned)
    else:
        st.info("No conflicts found. Scale LLP has not worked with this client.")

# Sidebar for data overview
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

