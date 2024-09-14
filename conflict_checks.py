import streamlit as st
import requests
import urllib.parse
import pandas as pd

# Clio API details (retrieved from Streamlit secrets)
CLIENT_ID = st.secrets["CLIO_CLIENT_ID"]
CLIENT_SECRET = st.secrets["CLIO_CLIENT_SECRET"]
REDIRECT_URI = st.secrets["REDIRECT_URI"]  # Should be "https://conflictchecks.streamlit.app"

# Clio API URLs
CLIO_API_BASE_URL = "https://app.clio.com/api/v4"
AUTH_URL = "https://app.clio.com/oauth/authorize"
TOKEN_URL = "https://app.clio.com/oauth/token"

# Function to get authorization URL
def get_authorization_url():
    params = {
        'response_type': 'code',
        'client_id': CLIENT_ID,
        'redirect_uri': REDIRECT_URI,
        'state': 'xyz',  # You might want to generate a random state
        'redirect_on_decline': 'true'
    }
    return f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

# Function to exchange authorization code for access token
def get_access_token(auth_code):
    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': auth_code,
        'redirect_uri': REDIRECT_URI
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    response = requests.post(TOKEN_URL, data=data, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        st.error(f"Error fetching access token: {response.status_code}, {response.text}")
        return None

# Function to make a request to the Clio API
def clio_api_request(endpoint, access_token):
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(f"{CLIO_API_BASE_URL}/{endpoint}", headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        st.error(f"Failed to fetch data from Clio: {response.status_code}, {response.text}")
        return None

# App title
st.title("Clio Conflict Check Tool")

# Check for 'code' parameter in URL
query_params = st.experimental_get_query_params()
if 'code' in query_params:
    auth_code = query_params['code'][0]
    st.success("Authorization code received!")
    
    # Use the auth_code to get the access token
    token_data = get_access_token(auth_code)
    if token_data and 'access_token' in token_data:
        access_token = token_data['access_token']
        st.success("Access token retrieved successfully!")
        
        # Store the access token in session state
        st.session_state['access_token'] = access_token
        
        # Clear the URL parameters
        st.experimental_set_query_params()
        st.experimental_rerun()
    else:
        st.error("Failed to retrieve access token.")
elif 'access_token' in st.session_state:
    st.success("You are authorized!")
    if st.button("Fetch User Data"):
        user_data = clio_api_request('users/who_am_i', st.session_state['access_token'])
        if user_data:
            st.write("User Data:", user_data)
        else:
            st.error("Failed to fetch user data.")
else:
    st.write("Follow these steps to authorize and use the Clio Conflict Check Tool:")
    
    # Step 1: Display the Authorization URL
    st.header("Step 1: Authorize the App")
    st.markdown("**Important:** Please log out of Clio in your browser before proceeding.")
    auth_url = get_authorization_url()
    st.markdown(f"Click this link to authorize the app with Clio: [Authorize with Clio]({auth_url})")
    st.markdown("After authorizing, you will be redirected back to this app automatically.")

# Display some app info
st.sidebar.title("App Info")
st.sidebar.info(f"Using Client ID: {CLIENT_ID[:5]}...{CLIENT_ID[-5:]}")
st.sidebar.info(f"Redirect URI: {REDIRECT_URI}")
