import streamlit as st
import requests
import logging
from urllib.parse import urlencode
from datetime import datetime, timedelta
import json
import os

# Set up logging
logging.basicConfig(level=logging.INFO)

# Clio API URLs
CLIO_API_BASE_URL = "https://app.clio.com/api/v4"
AUTH_URL = "https://app.clio.com/oauth/authorize"
TOKEN_URL = "https://app.clio.com/oauth/token"

# Retrieve credentials from secrets
CLIENT_ID = st.secrets["CLIO_CLIENT_ID"]
CLIENT_SECRET = st.secrets["CLIO_CLIENT_SECRET"]
REDIRECT_URI = st.secrets["REDIRECT_URI"]  # Should match your app's URL

# For saving data on your desktop (Works for Mac/Linux/Windows)
DESKTOP_PATH = os.path.join(os.path.expanduser("~"), "Desktop")
DATA_FILE = os.path.join(DESKTOP_PATH, "clio_data.json")
TOKEN_FILE = os.path.join(DESKTOP_PATH, "clio_tokens.json")  # File to store tokens

# Function to save tokens in a file
def save_tokens(access_token, refresh_token, token_expiry):
    tokens = {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'token_expiry': token_expiry.strftime('%Y-%m-%d %H:%M:%S')
    }
    with open(TOKEN_FILE, 'w') as token_file:
        json.dump(tokens, token_file)

# Function to load tokens from the file
def load_tokens():
    try:
        with open(TOKEN_FILE, 'r') as token_file:
            tokens = json.load(token_file)
            # Convert expiry time back to a datetime object
            tokens['token_expiry'] = datetime.strptime(tokens['token_expiry'], '%Y-%m-%d %H:%M:%S')
            return tokens
    except FileNotFoundError:
        return None

# Save contacts and matters data to a file on the desktop
def save_data(contacts, matters):
    data = {
        'contacts': contacts,
        'matters': matters,
        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    with open(DATA_FILE, 'w') as data_file:
        json.dump(data, data_file)

# Load contacts and matters data from the desktop
def load_data():
    try:
        with open(DATA_FILE, 'r') as data_file:
            return json.load(data_file)
    except FileNotFoundError:
        return None

def get_authorization_url():
    """Generate the authorization URL to get user consent"""
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": "contacts.read matters.read offline_access"
    }
    return f"{AUTH_URL}?{urlencode(params)}"

def fetch_token(authorization_code):
    """Exchange authorization code for access and refresh tokens"""
    data = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": authorization_code,
        "redirect_uri": REDIRECT_URI
    }
    response = requests.post(TOKEN_URL, data=data)
    
    # Log the API response for debugging
    logging.info(f"Response status code: {response.status_code}")
    logging.info(f"Response text: {response.text}")
    
    if response.status_code == 200:
        token_data = response.json()
        # Save tokens to file
        save_tokens(token_data['access_token'], token_data['refresh_token'], 
                    datetime.now() + timedelta(seconds=token_data['expires_in']))
        return token_data['access_token']
    else:
        st.error(f"Failed to fetch token: {response.status_code}, {response.text}")
        return None

def refresh_access_token():
    """Refresh the access token using the refresh token"""
    tokens = load_tokens()
    if not tokens or not tokens.get('refresh_token'):
        st.error("No refresh token available. Please reauthorize.")
        return None

    data = {
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": tokens['refresh_token'],
        "redirect_uri": REDIRECT_URI
    }
    response = requests.post(TOKEN_URL, data=data)
    
    if response.status_code == 200:
        token_data = response.json()
        # Update tokens in the file
        save_tokens(token_data['access_token'], token_data.get('refresh_token', tokens['refresh_token']), 
                    datetime.now() + timedelta(seconds=token_data['expires_in']))
        return token_data['access_token']
    else:
        st.error(f"Failed to refresh token: {response.status_code}, {response.text}")
        return None

def get_valid_token():
    """Check for a valid token, refresh if expired, or trigger authorization if needed"""
    tokens = load_tokens()
    if tokens:
        access_token = tokens['access_token']
        token_expiry = tokens['token_expiry']
        
        if token_expiry > datetime.now():
            return access_token  # Token is still valid
        else:
            return refresh_access_token()  # Token expired, refresh it
    else:
        # No valid token, prompt for authorization
        auth_url = get_authorization_url()
        st.markdown(f"Please [authorize the app]({auth_url}) to continue.")
        return None

def clio_api_request(endpoint, params=None):
    token = get_valid_token()
    if not token:
        return None
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{CLIO_API_BASE_URL}/{endpoint}", headers=headers, params=params)
    if response.status_code == 200:
        return response.json()
    elif response.status_code == 401:
        st.error("Token expired or invalid.")
        # Clear the token to force re-authentication
        save_tokens(None, None, None)
    else:
        st.error(f"Failed to fetch data from Clio: {response.status_code}, {response.text}")
    return None

# Fetch all contacts and matters and save them to cache
def fetch_all_data():
    contacts = clio_api_request('contacts')
    matters = clio_api_request('matters')
    if contacts and matters:
        save_data(contacts, matters)
    return contacts, matters

# Helper function to check for conflicts in Clio data
def perform_conflict_check(new_client_info, contacts, matters):
    conflicts = []
    
    for contact in contacts['data']:
        # Check full legal name
        if new_client_info['name'].lower() in contact['name'].lower():
            conflicts.append(f"Name match: {contact['name']}")
        
        # Check date of birth
        dob = contact.get('dob', None)
        if dob and dob == new_client_info['dob']:
            conflicts.append(f"Date of birth match: {contact['name']} (DOB: {dob})")
        
        # Check address
        if 'address' in contact and 'address' in new_client_info:
            if contact['address'].get('street', '').lower() == new_client_info['address'].lower():
                conflicts.append(f"Address match: {contact['name']}")
        
        # Check phone number
        for phone in contact.get('phone_numbers', []):
            if phone['number'] == new_client_info['phone']:
                conflicts.append(f"Phone number match: {contact['name']}")
    
    # Check matters for opposing parties
    for matter in matters['data']:
        if 'client' in matter and 'name' in matter['client']:
            if new_client_info['name'].lower() in matter['client']['name'].lower():
                conflicts.append(f"Opposing party match in matter: {matter.get('display_number', 'N/A')} - {matter.get('description', 'N/A')}")
    
    return conflicts

# Streamlit app
st.title("Clio Conflict Check Tool")

# Capture the authorization code from URL parameters
query_params = st.experimental_get_query_params()
authorization_code = query_params.get('code', [None])[0]

# Fetch token if authorization code is provided
if authorization_code and not load_tokens():
    fetch_token(authorization_code)
    st.experimental_rerun()

# Fetch data if a valid token is available
if load_tokens():
    cached_data = load_data()
    
    if cached_data:
        contacts = cached_data['contacts']
        matters = cached_data['matters']
        last_updated = cached_data['last_updated']
        st.success(f"Loaded {len(contacts['data'])} contacts and {len(matters['data'])} matters from cache (last updated on {last_updated}).")
    else:
        with st.spinner("Fetching data from Clio..."):
            contacts, matters = fetch_all_data()
            if contacts and matters:
                st.success(f"Fetched {len(contacts['data'])} contacts and {len(matters['data'])} matters from Clio.")
            else:
                st.error("Failed to fetch data. Please check your Clio API credentials.")
else:
    get_valid_token()  # This will display the authorization link if needed

# Input for new client details for conflict check
st.header("New Client Details")
new_client_name = st.text_input("Full Legal Name")
new_client_dob = st.date_input("Date of Birth")
new_client_address = st.text_input("Address")
new_client_phone = st.text_input("Phone Number")

if st.button("Run Conflict Check"):
    if new_client_name:
        new_client_info = {
            'name': new_client_name,
            'dob': new_client_dob.strftime('%Y-%m-%d') if new_client_dob else '',
            'address': new_client_address,
            'phone': new_client_phone
        }
        conflicts = perform_conflict_check(new_client_info, contacts, matters)
        
        if conflicts:
            st.warning("Potential conflicts detected:")
            for conflict in conflicts:
                st.write(conflict)
        else:
            st.success("No conflicts detected.")
    else:
        st.error("Please enter the client's full legal name.")

# Sidebar to manually refresh data
if st.sidebar.button("Refresh Clio Data"):
    fetch_all_data()  # Fetch and re-cache data
