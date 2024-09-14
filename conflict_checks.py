import streamlit as st
import requests
import logging
import sqlite3
from urllib.parse import urlencode
from datetime import datetime, timedelta

# Set up logging
logging.basicConfig(level=logging.INFO)

# Clio API URLs (Adjust these as needed)
CLIO_API_BASE_URL = "https://app.clio.com/api/v4"
AUTH_URL = "https://app.clio.com/oauth/authorize"
TOKEN_URL = "https://app.clio.com/oauth/token"

# Retrieve credentials from secrets
CLIENT_ID = st.secrets["CLIO_CLIENT_ID"]
CLIENT_SECRET = st.secrets["CLIO_CLIENT_SECRET"]
REDIRECT_URI = st.secrets["REDIRECT_URI"]

# SQLite Database Initialization
def init_db():
    conn = sqlite3.connect('clio_data.db')
    c = conn.cursor()
    
    # Create tables for contacts and matters if they don't exist
    c.execute('''CREATE TABLE IF NOT EXISTS contacts (
        id INTEGER PRIMARY KEY,
        name TEXT,
        email TEXT,
        address TEXT,
        phone TEXT,
        custom_fields TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS matters (
        id INTEGER PRIMARY KEY,
        client_name TEXT,
        display_number TEXT,
        description TEXT
    )''')
    
    conn.commit()
    conn.close()

# Store data in the SQLite database
def store_data_in_db(contacts, matters):
    conn = sqlite3.connect('clio_data.db')
    c = conn.cursor()
    
    # Insert contacts data
    contact_data = [(contact['id'], contact['name'], contact.get('email', ''), 
                     contact.get('address', ''), contact.get('phone', ''), str(contact.get('custom_fields', '')))
                    for contact in contacts]
    
    c.executemany('''INSERT OR REPLACE INTO contacts VALUES (?, ?, ?, ?, ?, ?)''', contact_data)
    
    # Insert matters data
    matter_data = [(matter['id'], matter.get('client', {}).get('name', ''), 
                    matter['display_number'], matter.get('description', ''))
                   for matter in matters]
    
    c.executemany('''INSERT OR REPLACE INTO matters VALUES (?, ?, ?, ?)''', matter_data)
    
    conn.commit()
    conn.close()

# OAuth and Token Management Functions (from your provided code)
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
    
    if response.status_code == 200:
        token_data = response.json()
        st.session_state['access_token'] = token_data['access_token']
        st.session_state['refresh_token'] = token_data['refresh_token']
        st.session_state['token_expiry'] = datetime.now() + timedelta(seconds=token_data['expires_in'])
        return token_data['access_token']
    else:
        st.error(f"Failed to fetch token: {response.status_code}, {response.text}")
        return None

def refresh_access_token():
    """Refresh the access token using the refresh token"""
    refresh_token = st.session_state.get('refresh_token')
    if not refresh_token:
        st.error("No refresh token available. Please reauthorize.")
        return None

    data = {
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": refresh_token,
        "redirect_uri": REDIRECT_URI
    }
    response = requests.post(TOKEN_URL, data=data)
    
    if response.status_code == 200:
        token_data = response.json()
        st.session_state['access_token'] = token_data['access_token']
        st.session_state['refresh_token'] = token_data.get('refresh_token', refresh_token)
        st.session_state['token_expiry'] = datetime.now() + timedelta(seconds=token_data['expires_in'])
        return token_data['access_token']
    else:
        st.error(f"Failed to refresh token: {response.status_code}, {response.text}")
        st.session_state.pop('access_token', None)
        st.session_state.pop('refresh_token', None)
        st.session_state.pop('token_expiry', None)
        return None

def get_valid_token():
    """Check for a valid token, refresh if expired, or trigger authorization if needed"""
    token_expiry = st.session_state.get('token_expiry')
    access_token = st.session_state.get('access_token')
    
    if access_token and token_expiry:
        if token_expiry > datetime.now():
            return access_token
        else:
            return refresh_access_token()
    else:
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
        st.session_state.pop('access_token', None)
        st.session_state.pop('refresh_token', None)
        st.session_state.pop('token_expiry', None)
    else:
        st.error(f"Failed to fetch data from Clio: {response.status_code}, {response.text}")
    return None

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_all_pages_cached(endpoint):
    all_data = []
    params = {"limit": 100, "page": 1}
    
    while True:
        data = clio_api_request(endpoint, params)
        if data and 'data' in data:
            all_data.extend(data['data'])
            
            if data.get('meta', {}).get('paging', {}).get('next'):
                params['page'] += 1
            else:
                break
        else:
            break
    
    return all_data

# Perform conflict checks
def perform_advanced_conflict_check_from_db(new_client_info):
    conn = sqlite3.connect('clio_data.db')
    c = conn.cursor()
    
    conflicts = []
    
    # Conflict check for contacts
    c.execute('SELECT * FROM contacts WHERE LOWER(name) LIKE ?', (f"%{new_client_info['name'].lower()}%",))
    contact_matches = c.fetchall()
    for match in contact_matches:
        conflicts.append(f"Name match: {match[1]} (ID: {match[0]})")
    
    # Conflict check for matters (e.g., opposing parties)
    c.execute('SELECT * FROM matters WHERE LOWER(client_name) LIKE ?', (f"%{new_client_info['name'].lower()}%",))
    matter_matches = c.fetchall()
    for match in matter_matches:
        conflicts.append(f"Opposing party match in matter: {match[2]} - {match[3]}")
    
    conn.close()
    
    return conflicts

# Streamlit App UI
st.title("Advanced Clio Conflict Check Tool")

# Capture the authorization code from URL parameters
query_params = st.experimental_get_query_params()
authorization_code = query_params.get('code', [None])[0]

if authorization_code and 'access_token' not in st.session_state:
    fetch_token(authorization_code)
    st.experimental_rerun()

# Fetch data if not already cached and authorized
if 'access_token' in st.session_state:
    with st.spinner("Fetching data from Clio..."):
        contacts = fetch_all_pages_cached('contacts')
        matters = fetch_all_pages_cached('matters')
    if contacts and matters:
        store_data
