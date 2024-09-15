import pandas as pd
import requests
import json
import streamlit as st

# Load the data
def load_data(file_url):
    data = pd.read_csv(file_url)
    return data

# Call Claude Sonnet API
def call_claude_sonnet(prompt, api_key):
    url = "https://api.anthropic.com/v1/complete"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    data = {
        "model": "claude-3.5",
        "prompt": prompt,
        "max_tokens": 500,
        "temperature": 0.7
    }
    response = requests.post(url, headers=headers, data=json.dumps(data))
    response_json = response.json()
    return response_json['completion']

# Streamlit app
st.title("Conflict Check with Claude Sonnet 3.5")

# Load and display the data
data_url = "https://github.com/aavadhan10/Conflict-Checks/blob/main/combined_contact_and_matters.csv"
data = load_data(data_url)

st.write("### Data Preview")
st.write(data.head())

# User input
user_name = st.text_input("Enter the client's full name:")
user_email = st.text_input("Enter the client's email:")
user_phone = st.text_input("Enter the client's phone number:")

# Check for conflicts
if st.button("Check for Conflicts"):
    if user_name or user_email or user_phone:
        # Construct the prompt for Claude
        prompt = f"""
        Analyze the following data for any conflicts involving a client:
        Name: {user_name}
        Email: {user_email}
        Phone: {user_phone}

        Data:
        {data.to_string(index=False)}

        Please provide a detailed conflict check report.
        """

        api_key = st.secrets["CLAUDE_API_KEY"]
        if not api_key:
            st.error("Claude API key not found. Please check your Streamlit secrets configuration.")
            st.stop()

        # Call Claude and get the result
        result = call_claude_sonnet(prompt, api_key)
        st.write("### Conflict Check Report")
        st.write(result)
    else:
        st.error("Please provide at least one piece of client information.")

