import pandas as pd
import streamlit as st
from thefuzz import fuzz

# GitHub CSV file URL
github_url = 'https://raw.githubusercontent.com/aavadhan10/Conflict-Checks/main/combined_contact_and_matters.csv'

@st.cache_data  # Use st.cache_data for caching data
def load_data():
    # Load the CSV file from GitHub, fill NaN with empty strings to avoid errors
    return pd.read_csv(github_url).fillna("")

# Streamlit app for conflict check
st.title("Scale LLP Conflict Check System")

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
        # Assume there is a column called 'Matter Number'
        matter_numbers = results['Matter Number'].unique()  # Change to the actual column name
        matter_list = ', '.join(map(str, matter_numbers))

        st.success(f"Conflict found! Scale LLP has previously worked with the client. Matter Number(s): {matter_list}")

        # Drop the unnecessary columns (Attorney, Client, Matter Description)
        columns_to_drop = ['Attorney Name', 'Client Name', 'Matter Description']
        results_cleaned = results.drop(columns=[col for col in columns_to_drop if col in results.columns])

        st.dataframe(results_cleaned)
    else:
        st.info("No conflicts found. Scale LLP has not worked with this client.")

# Enhanced sidebar
st.sidebar.title("📊 Scale LLP Matters Overview")

# Display number of matters worked with in a "prettier" way
num_matters = len(data)
st.sidebar.markdown(f"<h2 style='color: #4CAF50;'>Number of Matters Till Date: {num_matters}</h2>", unsafe_allow_html=True)

# Add a banner or button for data update info
st.sidebar.markdown(
    "<div style='background-color: #f0f0f5; padding: 10px; border-radius: 5px; border: 1px solid #ccc;'>"
    "<strong>Data Updated from Clio API</strong><br>Last Update: <strong>9/14/2024</strong>"
    "</div>", unsafe_allow_html=True
)
