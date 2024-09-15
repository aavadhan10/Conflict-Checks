import pandas as pd
import streamlit as st
from thefuzz import fuzz

# GitHub CSV file URL
github_url = 'https://raw.githubusercontent.com/aavadhan10/Conflict-Checks/main/combined_contact_and_matters.csv'

@st.cache
def load_data():
    # Load the CSV file from GitHub
    return pd.read_csv(github_url)

# Streamlit app for conflict check
st.title("Law Firm Conflict Check System")

# Input fields for client information
full_name = st.text_input("Enter Client's Full Name")
email = st.text_input("Enter Client's Email")
phone_number = st.text_input("Enter Client's Phone Number")

# Load the CSV data
data = load_data()

# Function to perform fuzzy conflict check
def fuzzy_conflict_check(full_name, email, phone_number, threshold=80):
    matching_records = pd.DataFrame()

    for index, row in data.iterrows():
        # Fuzzy match for the client name
        name_match = fuzz.partial_ratio(row['Client Name'], full_name)

        # We don't have email or phone fields, so we check only names
        if name_match >= threshold:
            matching_records = matching_records.append(row)

    return matching_records

# Perform the conflict check if the user has input all fields
if st.button("Check for Conflict"):
    results = fuzzy_conflict_check(full_name, email, phone_number)
    
    if not results.empty:
        st.success(f"Conflict found! The firm has previously worked with the client.")
        st.dataframe(results)
    else:
        st.info("No conflicts found. The firm has not worked with this client.")

# Display data statistics in the sidebar
st.sidebar.title("Data Statistics")
st.sidebar.write(f"Number of contacts: {len(data)}")
