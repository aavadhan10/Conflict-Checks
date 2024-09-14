import streamlit as st
import requests
import logging
from datetime import datetime, timedelta
import sqlite3
import json

# Set up logging
logging.basicConfig(level=logging.INFO)

# Clio API URLs
CLIO_API_BASE_URL = "https://app.clio.com/api/v4"
AUTH_URL = "https://app.clio.com/oauth/authorize"
TOKEN_URL = "https://app.clio.com/oauth/token"

# Retrieve credentials from secrets
CLIENT_ID = st.secrets["CLIO_CLIENT_ID"]
CLIENT_SECRET = st.secrets["CLIO_CLIENT_SECRET"]
REDIRECT_URI = st.secrets["REDIRECT_URI"]

# Initialize SQLite database
DB_NAME = 'clio_app.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Create tokens table
    c.execute('''
        CREATE TABLE IF NOT EXISTS tokens (
            id INTEGER PRIMARY KEY,
            access_token TEXT NOT NULL,
            token_expiry TEXT NOT NULL
        )
    ''')
    # Create contacts table
    c.execute('''
        CREATE TABLE IF NOT EXISTS contacts (
            id TEXT PRIMARY KEY,
            data TEXT NOT NULL
        )
    ''')
    # Create matters table
    c.execute('''
        CREATE TABLE IF NOT EXISTS matters (
            id TEXT PRIMARY KEY,
            data TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# Initialize the database
init_db()

def get_token_from_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT access_token, token_expiry FROM tokens ORDER BY id DESC LIMIT 1')
    row = c.fetchone()
    conn.close()
    if row:
        access_token, token_expiry_str = row
        token_expiry = datetime.strptime(token_expiry_str, '%Y-%m-%d %H:%M:%S.%f')
        return access_token, token_expiry
    return None, None

def save_token_to_db(access_token, token_expiry):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('INSERT INTO tokens (access_token, token_expiry) VALUES (?, ?)', 
              (access_token, token_expiry))
    conn.commit()
    conn.close()

def get_contacts_from_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT data FROM contacts')
    rows = c.fetchall()
    conn.close()
    contacts = [json.loads(row[0]) for row in rows]
    return contacts

def save_contacts_to_db(contacts):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    for contact in contacts:
        c.execute('INSERT OR REPLACE INTO contacts (id, data) VALUES (?, ?)', 
                  (contact['id'], json.dumps(contact)))
    conn.commit()
    conn.close()

def get_matters_from_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT data FROM matters')
    rows = c.fetchall()
    conn.close()
    matters = [json.loads(row[0]) for row in rows]
    return matters

def save_matters_to_db(matters):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    for matter in matters:
        c.execute('INSERT OR REPLACE INTO matters (id, data) VALUES (?, ?)', 
                  (matter['id'], json.dumps(matter)))
    conn.commit()
    conn.close()

def get_new_token():
    """Function to get a new access token using client credentials flow"""
    data = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }
    response = requests.post(TOKEN_URL, data=data)
    if response.status_code == 200:
        token_data = response.json()
        access_token = token_data['access_token']
        token_expiry = datetime.now() + timedelta(seconds=token_data['expires_in'])
        save_token_to_db(access_token, token_expiry)
        return access_token
    else:
        st.error(f"Failed to get new token: {response.status_code}, {response.text}")
        return None

def get_valid_token():
    """Function to get a valid token, refreshing if necessary"""
    access_token, token_expiry = get_token_from_db()
    if not access_token or not token_expiry:
        return get_new_token()
    elif token_expiry <= datetime.now():
        return get_new_token()
    else:
        return access_token

def clio_api_request(endpoint, params=None):
    token = get_valid_token()
    if not token:
        st.error("Unable to obtain a valid token.")
        return None
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{CLIO_API_BASE_URL}/{endpoint}", headers=headers, params=params)
    if response.status_code == 200:
        return response.json()
    elif response.status_code == 401:
        # Token might have just expired, try refreshing once
        token = get_new_token()
        if token:
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(f"{CLIO_API_BASE_URL}/{endpoint}", headers=headers, params=params)
            if response.status_code == 200:
                return response.json()
    
    st.error(f"Failed to fetch data from Clio: {response.status_code}, {response.text}")
    return None

def fetch_all_pages(endpoint, save_to_db_func):
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
    
    # Save fetched data to the database
    save_to_db_func(all_data)
    
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
        
        # Check maiden/married names
        maiden_name = get_custom_field_value(contact, 'Maiden Name')
        if maiden_name and new_client_info['name'].lower() in maiden_name.lower():
            conflicts.append(f"Maiden name match: {contact['name']} (Maiden: {maiden_name})")
        
        # Check nicknames
        nicknames = get_custom_field_value(contact, 'Nicknames')
        if nicknames:
            for nickname in nicknames.split(','):
                if nickname.strip().lower() in new_client_info['name'].lower():
                    conflicts.append(f"Nickname match: {contact['name']} (Nickname: {nickname})")
        
        # Check date of birth
        dob = get_custom_field_value(contact, 'Date of Birth')
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
        
        # Business-specific checks
        if contact['type'] == 'Company':
            # Check officers and directors
            officers = get_custom_field_value(contact, 'Officers and Directors')
            if officers and new_client_info['name'].lower() in officers.lower():
                conflicts.append(f"Officer/Director match: {contact['name']}")
            
            # Check partners
            partners = get_custom_field_value(contact, 'Partners')
            if partners and new_client_info['name'].lower() in partners.lower():
                conflicts.append(f"Partner match: {contact['name']}")
            
            # Check trade names
            trade_names = get_custom_field_value(contact, 'Trade Names')
            if trade_names and new_client_info['name'].lower() in trade_names.lower():
                conflicts.append(f"Trade name match: {contact['name']}")
    
    # Check matters for opposing parties
    for matter in matters:
        if 'client' in matter and 'name' in matter['client']:
            if new_client_info['name'].lower() in matter['client']['name'].lower():
                conflicts.append(f"Opposing party match in matter: {matter.get('display_number', 'N/A')} - {matter.get('description', 'N/A')}")
    
    return conflicts

# Streamlit app
st.title("Advanced Clio Conflict Check Tool")

# Function to load data from the database or fetch from API
def load_data():
    contacts = get_contacts_from_db()
    matters = get_matters_from_db()
    
    if not contacts or not matters:
        with st.spinner("Fetching data from Clio..."):
            if not contacts:
                contacts = fetch_all_pages('contacts', save_contacts_to_db)
            if not matters:
                matters = fetch_all_pages('matters', save_matters_to_db)
        if contacts and matters:
            st.success(f"Loaded {len(contacts)} contacts and {len(matters)} matters from the database.")
        else:
            st.error("Failed to fetch data. Please check your Clio API credentials.")
    else:
        st.success(f"Loaded {len(contacts)} contacts and {len(matters)} matters from the database.")
    
    return contacts, matters

# Load contacts and matters
contacts, matters = load_data()

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
            'dob': new_client_dob.strftime('%Y-%m-%d'),
            'address': new_client_address,
            'phone': new_client_phone
        }
        conflicts = perform_advanced_conflict_check(new_client_info, contacts, matters)
        
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
st.sidebar.write(f"Number of contacts: {len(contacts)}")
st.sidebar.write(f"Number of matters: {len(matters)}")

# Optional: Add a refresh data button
if st.sidebar.button("Refresh Clio Data"):
    # Clear the database tables
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('DELETE FROM contacts')
    c.execute('DELETE FROM matters')
    conn.commit()
    conn.close()
    st.experimental_rerun()

# Display token information in sidebar
access_token, token_expiry = get_token_from_db()
if access_token and token_expiry:
    st.sidebar.title("Token Information")
    st.sidebar.write(f"Token expires at: {token_expiry}")
    if token_expiry > datetime.now():
        st.sidebar.success("Token is valid")
    else:
        st.sidebar.warning("Token has expired (will be refreshed on next API call)")
