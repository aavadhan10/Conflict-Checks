import streamlit as st
import requests
import urllib.parse
import pandas as pd

#Clio API details (retrieved from Streamlit secrets)
CLIENT_ID = st.secrets["CLIO_CLIENT_ID"]
CLIENT_SECRET = st.secrets["CLIO_CLIENT_SECRET"]
REDIRECT_URI = st.secrets["REDIRECT_URI"]

# Clio API URLs
CLIO_API_BASE_URL = "https://app.clio.com/api/v4"
AUTH_URL = "https://app.clio.com/oauth/authorize"
TOKEN_URL = "https://app.clio.com/oauth/token"

# Streamlit App Layout
st.title("Clio Conflict Check Tool")

# Display Client ID for verification
st.write(f"Using Client ID: {CLIENT_ID[:5]}...{CLIENT_ID[-5:]}")

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

st.write("Follow these steps to authorize and use the Clio Conflict Check Tool:")

# Step 1: Display the Authorization URL
st.header("Step 1: Authorize the App")
st.markdown("**Important:** Please log out of Clio in your browser before proceeding.")
auth_url = get_authorization_url()
st.markdown(f"1. Click this link to authorize the app with Clio: [Authorize with Clio]({auth_url})")
st.markdown("2. Log in to your Clio account if prompted.")
st.markdown("3. Grant the requested permissions.")
st.markdown("4. You will be redirected to a page with a URL containing a 'code' parameter.")
st.markdown("5. Copy the entire URL of that page.")

# Step 2: Input the redirect URL
st.header("Step 2: Enter the Redirect URL")
st.markdown("Paste the entire URL you were redirected to:")
redirect_url = st.text_input("Redirect URL")

if redirect_url:
    # Extract the authorization code from the redirect URL
    parsed_url = urllib.parse.urlparse(redirect_url)
    query_params = urllib.parse.parse_qs(parsed_url.query)
    auth_code = query_params.get('code', [None])[0]
    
    if auth_code:
        # Step 3: Get access token using the authorization code
        token_data = get_access_token(auth_code)
        if token_data and 'access_token' in token_data:
            access_token = token_data['access_token']
            st.success("Access token retrieved successfully!")
            
            # Step 4: Use the access token to fetch client data or matters
            st.header("Step 3: Fetch and Display Data")
            if st.button("Fetch User Data"):
                user_data = clio_api_request('users/who_am_i', access_token)
                if user_data:
                    st.write("User Data:", user_data)
                else:
                    st.error("Failed to fetch user data. Please check your authorization and try again.")
        else:
            st.error("Failed to retrieve access token. Please check your authorization code and try again.")
    else:
        st.error("No authorization code found in the redirect URL. Please ensure you copied the entire URL.")
