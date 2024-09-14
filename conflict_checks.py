import streamlit as st
import requests
import logging
from datetime import datetime, timedelta

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
        st.session_state['access_token'] = token_data['access_token']
        st.session_state['token_expiry'] = datetime.now() + timedelta(seconds=token_data['expires_in'])
        return token_data['access_token']
    else:
        st.error(f"Failed to get new token: {response.status_code}, {response.text}")
        return None
        
def get_valid_token():
    """Function to get a valid token, refreshing if necessary"""
    token_expiry = st.session_state.get('token_expiry')
    access_token = st.session_state.get('access_token')

    if not access_token or not token_expiry:
        st.info("No valid token or token expiry found. Fetching a new token.")
        return get_new_token()
    elif token_expiry <= datetime.now():
        st.info("Token has expired. Fetching a new token.")
        return get_new_token()
    else:
        st.info("Using cached access token.")
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
            'dob': new_client_dob.strftime('%Y-%m-%d'),
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
    
    # Ensure 'token_expiry' is initialized properly
    if st.session_state['token_expiry'] and isinstance(st.session_state['token_expiry'], datetime):
        if st.session_state['token_expiry'] > datetime.now():
            st.sidebar.success("Token is valid")
        else:
            st.sidebar.warning("Token has expired (will be refreshed on next API call)")
    else:
        st.sidebar.warning("Token expiry is not properly set.")
else:
    st.sidebar.warning("No access token available.")
