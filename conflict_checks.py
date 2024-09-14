import streamlit as st
import requests
import pandas as pd
import logging
from datetime import datetime, timedelta
from authlib.integrations.requests_client import OAuth2Session

# Set up logging
logging.basicConfig(level=logging.INFO)

# Retrieve credentials from st.secrets
CLIENT_ID = st.secrets["clio"]["client_id"]
CLIENT_SECRET = st.secrets["clio"]["client_secret"]
REDIRECT_URI = st.secrets["clio"]["redirect_uri"]

# Clio API URLs
CLIO_API_BASE_URL = "https://app.clio.com/api/v4"
AUTH_URL = "https://app.clio.com/oauth/authorize"
TOKEN_URL = "https://app.clio.com/oauth/token"

def get_oauth_session(state=None, token=None):
    """Create an OAuth2Session with Authlib."""
    return OAuth2Session(
        CLIENT_ID,
        CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        state=state,
        token=token,
    )

# Streamlit app
st.title("Advanced Clio Conflict Check Tool")

# Initialize session_state variables
if 'oauth_state' not in st.session_state:
    st.session_state['oauth_state'] = None
if 'access_token' not in st.session_state:
    st.session_state['access_token'] = None
if 'refresh_token' not in st.session_state:
    st.session_state['refresh_token'] = None
if 'token_expiry' not in st.session_state:
    st.session_state['token_expiry'] = None

# Check if we have an access token
if not st.session_state['access_token']:
    # Create an OAuth2Session
    oauth = get_oauth_session()

    # Retrieve query parameters
    query_params = st.experimental_get_query_params()

    # Check if we have an authorization code in the URL parameters
    if 'code' in query_params:
        code = query_params['code'][0]
        # Fetch the token using the authorization code
        token = oauth.fetch_token(
            TOKEN_URL,
            code=code,
            include_client_id=True,
            client_secret=CLIENT_SECRET,
        )
        # Store tokens and expiry in session_state
        st.session_state['access_token'] = token['access_token']
        st.session_state['refresh_token'] = token.get('refresh_token')
        st.session_state['token_expiry'] = datetime.now() + timedelta(seconds=token.get('expires_in', 3600))
        st.success("Authentication successful!")
        # Remove 'code' from query parameters to clean up the URL
        st.experimental_set_query_params()
    else:
        # Redirect the user to the Clio authorization page
        authorization_url, state = oauth.create_authorization_url(AUTH_URL)
        st.session_state['oauth_state'] = state
        st.write("Please authorize the application to access Clio data.")
        st.markdown(f"[Click here to authorize]({authorization_url})")
        st.stop()
else:
    # We have an access token, proceed with the app

    def get_valid_token():
        """Refresh the token if it's expired."""
        if st.session_state['token_expiry'] <= datetime.now():
            oauth = get_oauth_session(token={
                'access_token': st.session_state['access_token'],
                'refresh_token': st.session_state['refresh_token'],
                'token_type': 'Bearer',
                'expires_in': 3600,
            })
            token = oauth.refresh_token(
                TOKEN_URL,
                refresh_token=st.session_state['refresh_token'],
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
            )
            st.session_state['access_token'] = token['access_token']
            st.session_state['refresh_token'] = token.get('refresh_token')
            st.session_state['token_expiry'] = datetime.now() + timedelta(seconds=token.get('expires_in', 3600))
        return st.session_state['access_token']

    def clio_api_request(endpoint, params=None):
        token = get_valid_token()
        if not token:
            st.error("Unable to obtain a valid token.")
            return None

        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{CLIO_API_BASE_URL}/{endpoint}", headers=headers, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Failed to fetch data from Clio: {response.status_code}, {response.text}")
            return None

    def fetch_all_pages(endpoint):
        all_data = []
        params = {"limit": 100, "page": 1}

        while True:
            data = clio_api_request(endpoint, params)
            if data and 'data' in data:
                all_data.extend(data['data'])
                st.write(f"Fetched {len(data['data'])} items from {endpoint}, page {params['page']}")

                if data.get('meta', {}).get('paging', {}).get('next'):
                    params['page'] += 1
                else:
                    break
            else:
                break

        return all_data

    def get_custom_field_value(contact, field_name):
        for field in contact.get('custom_field_values', []):
            if field['field_name'] == field_name:
                return field['value']
        return None

    def perform_advanced_conflict_check(new_client_info, contacts, matters):
        conflicts = []

        for contact in contacts:
            # Check full legal name
            if new_client_info['name'].lower() in contact['name'].lower():
                conflicts.append(f"Name match: {contact['name']}")

            # Additional checks...

        # Additional code...

        return conflicts

    # Fetch data if not already in session state
    if 'contacts' not in st.session_state or 'matters' not in st.session_state:
        with st.spinner("Fetching data from Clio..."):
            st.session_state['contacts'] = fetch_all_pages('contacts')
            st.session_state['matters'] = fetch_all_pages('matters')
        if st.session_state['contacts'] and st.session_state['matters']:
            st.success(f"Fetched {len(st.session_state['contacts'])} contacts and {len(st.session_state['matters'])} matters")
        else:
            st.error("Failed to fetch data. Please check your Clio API credentials.")

    # Input for new client details
    st.header("New Client Details")
    new_client_name = st.text_input("Full Legal Name")
    new_client_dob = st.date_input("Date of Birth")
    new_client_address = st.text_input("Address")
    new_client_phone = st.text_input("Phone Number")

    if st.button("Run Advanced Conflict Check"):
        if new_client_name:
            new_client_info = {
                'name': new_client_name,
                'dob': new_client_dob.strftime('%Y-%m-%d') if new_client_dob else '',
                'address': new_client_address,
                'phone': new_client_phone
            }
            conflicts = perform_advanced_conflict_check(new_client_info, st.session_state['contacts'], st.session_state['matters'])

            if conflicts:
                st.warning("Potential conflicts detected:")
                for conflict in conflicts:
                    st.write(conflict)
            else:
                st.success("No conflicts detected.")
        else:
            st.error("Please enter at least the client's full legal name.")

    # Display data statistics
    st.sidebar.title("Data Statistics")
    st.sidebar.write(f"Number of contacts: {len(st.session_state.get('contacts', []))}")
    st.sidebar.write(f"Number of matters: {len(st.session_state.get('matters', []))}")

    # Optional: Add a refresh data button
    if st.sidebar.button("Refresh Clio Data"):
        st.session_state.pop('contacts', None)
        st.session_state.pop('matters', None)
        st.experimental_rerun()

    # Display token information in sidebar
    if 'access_token' in st.session_state and 'token_expiry' in st.session_state:
        st.sidebar.title("Token Information")
        st.sidebar.write(f"Token expires at: {st.session_state['token_expiry']}")
        if st.session_state['token_expiry'] > datetime.now():
            st.sidebar.success("Token is valid")
        else:
            st.sidebar.warning("Token has expired (will be refreshed on next API call)")
