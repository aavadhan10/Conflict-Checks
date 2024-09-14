import streamlit as st
import pandas as pd
import requests

# Clio API details (retrieved from Streamlit secrets)
CLIO_API_BASE_URL = "https://app.clio.com/api/v4"
CLIENT_ID = st.secrets["CLIO_CLIENT_ID"]  # Client ID from Streamlit secrets
CLIENT_SECRET = st.secrets["CLIO_CLIENT_SECRET"]  # Client Secret from Streamlit secrets
REDIRECT_URI = st.secrets["REDIRECT_URI"]  # Redirect URI from Streamlit secrets
AUTH_URL = "https://app.clio.com/oauth/authorize"
TOKEN_URL = "https://app.clio.com/oauth/token"

# Function to get authorization URL
def get_authorization_url():
    auth_params = {
        'client_id': CLIENT_ID,
        'redirect_uri': REDIRECT_URI,
        'response_type': 'code',
        'scope': 'contacts.read matters.read',  # Adjust scopes if needed
    }
    url = f"{AUTH_URL}?client_id={auth_params['client_id']}&redirect_uri={auth_params['redirect_uri']}&response_type={auth_params['response_type']}&scope={auth_params['scope']}"
    return url

# Function to exchange authorization code for access token
def get_access_token(auth_code):
    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': auth_code,
        'redirect_uri': REDIRECT_URI
    }
    st.write(f"Access Token Request Data: {data}")  # Log request data for debugging
    response = requests.post(TOKEN_URL, data=data)
    st.write(f"Access Token Response: {response.status_code}, {response.text}")  # Log response for debugging
    if response.status_code == 200:
        return response.json().get('access_token')
    else:
        st.error(f"Error fetching access token: {response.status_code}, {response.text}")
        return None

# Function to make a request to the Clio API
def clio_api_request(endpoint, access_token):
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(f"{CLIO_API_BASE_URL}/{endpoint}", headers=headers)
    st.write(f"API Request to {endpoint}: Status {response.status_code}")  # Log API request status
    if response.status_code == 200:
        return response.json()
    else:
        st.error(f"Failed to fetch data from Clio: {response.status_code}, {response.text}")
        return None

# Streamlit App Layout
st.title("Clio Conflict Check Tool")

# Step 1: Display the Authorization URL
auth_url = get_authorization_url()
st.markdown(f"[Click here to authorize the app with Clio]({auth_url})")
st.write(f"Generated Authorization URL: {auth_url}")  # Log authorization URL for debugging

# Step 2: Input the authorization code (this will be copied from the redirect URL)
auth_code = st.text_input("Enter the authorization code from Clio:")

if auth_code:
    # Step 3: Get access token using the authorization code
    access_token = get_access_token(auth_code)

    if access_token:
        # Step 4: Use the access token to fetch client data or matters
        st.success("Access token retrieved successfully!")
        clients_data = clio_api_request('contacts', access_token)
        if clients_data:
            st.write("Clients Data:", clients_data)
