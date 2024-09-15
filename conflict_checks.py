import pandas as pd
import streamlit as st
from thefuzz import fuzz

# GitHub CSV file URL
github_url = 'https://raw.githubusercontent.com/aavadhan10/Conflict-Checks/main/combined_contact_and_matters.csv'

@st.cache
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
    matching_records = pd.DataFrame()

    for index, row in data.iterrows():
        # Ensure the 'Client Name' field is a string before performing the fuzzy match
        client_name = str(row['Client Name'])

        # Fuzzy match for the client name
        name_match = fuzz.partial_ratio(client_name, full_name)

        # Add matching records if the name similarity exceeds the threshold
        if name_match >= threshold:
            matching_records = matching_records.append(row)

    return matching_records

# Perform the conflict check if the user has input all fields
if st.button("Check for Conflict"):
    results = fuzzy_conflict_check(full_name, email, phone_number)
    
    if not results.empty:
        # Assume there is a column called 'Matter Number'
        matter_numbers = results['Matter Number'].unique()  # Change to the actual column name
        matter_list = ', '.join(map(str, matter_numbers))

        st.success(f"Conflict found! Scale LLP has previously worked with the client. Matter Number(s): {matter_list}")
        st.dataframe(results)
    else:
        st.info("No conflicts found. Scale LLP has not worked with this client.")

# Display data statistics in the sidebar
st.sidebar.title("Data Statistics")
st.sidebar.write(f"Number of contacts: {len(data)}")
