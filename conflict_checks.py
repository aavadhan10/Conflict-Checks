import pandas as pd
import streamlit as st
from thefuzz import fuzz, process

# GitHub CSV file URL
github_url = 'https://raw.githubusercontent.com/aavadhan10/Conflict-Checks/main/combined_contact_and_matters.csv'

@st.cache
def load_data():
    # Load the CSV file from GitHub
    return pd.read_csv(github_url)

# Streamlit app for conflict check
st.title("Law Firm Conflict Check System")

# Input fields for client information
first_name = st.text_input("Enter Client's First Name")
last_name = st.text_input("Enter Client's Last Name")
email = st.text_input("Enter Client's Email")
phone_number = st.text_input("Enter Client's Phone Number")

# Load the CSV data
data = load_data()

# Function to perform fuzzy conflict check
def fuzzy_conflict_check(first_name, last_name, email, phone_number, threshold=80):
    # Results DataFrame to store matching records
    matching_records = pd.DataFrame()

    # Apply fuzzy matching to first name, last name, email, and phone number
    for index, row in data.iterrows():
        name_match = fuzz.partial_ratio(f"{row['First Name']} {row['Last Name']}", f"{first_name} {last_name}")
        email_match = fuzz.partial_ratio(row['Email'], email)
        phone_match = fuzz.partial_ratio(row['Phone'], phone_number)

        # If any of these match the threshold, consider it a match
        if name_match >= threshold or email_match >= threshold or phone_match >= threshold:
            matching_records = matching_records.append(row)

    return matching_records

# Perform the conflict check if the user has input all fields
if st.button("Check for Conflict"):
    results = fuzzy_conflict_check(first_name, last_name, email, phone_number)
    
    if not results.empty:
        st.success(f"Conflict found! The firm has previously worked with the client.")
        st.dataframe(results)
    else:
        st.info("No conflicts found. The firm has not worked with this client.")

# Display data statistics in the sidebar
st.sidebar.title("Data Statistics")
st.sidebar.write(f"Number of contacts: {len(data)}")

