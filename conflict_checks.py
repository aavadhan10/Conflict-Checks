import streamlit as st
import requests
import logging
from datetime import datetime, timedelta
import sqlite3
import json
from urllib.parse import urlencode, urlparse, parse_qs

# ------------------------------
# 1. Configuration and Initialization
# ------------------------------

# Set up logging
logging.basicConfig(level=logging.INFO)

# Clio API URLs
CLIO_API_BASE_URL = "https://app.clio.com/api/v4"
AUTH_URL = "https://app.clio.com/oauth/authorize"
TOKEN_URL = "https://app.clio.com/oauth/token"

# Retrieve credentials from Streamlit secrets
CLIENT_ID = st.secrets["CLIO_CLIENT_ID"]
CLIENT_SECRET = st.secrets["CLIO_CLIENT_SECRET"]
REDIRECT_URI = st.secrets["REDIRECT_URI"]  # Must match the redirect URI set in Clio

# Initialize SQLite database
DB_NAME = 'clio_app.db'

# ------------------------------
# 2. Database Management Functions
# ------------------------------

def init_db():
    """
    Initialize the SQLite database with required tables.
    Adds missing columns if necessary.
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Create tokens table if it doesn't exist
    c.execute('''
        CREATE TABLE IF NOT EXISTS tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            access_token TEXT NOT NULL,
            refresh_token TEXT,
            token_expiry TEXT NOT NULL
        )
    ''')
    
    # Check if 'refresh_token' column exists
    c.execute("PRAGMA table_info(tokens)")
    columns = [info[1] for info in c.fetchall()]
    
    if 'refresh_token' not in columns:
        try:
            c.execute('ALTER TABLE tokens ADD COLUMN refresh_token TEXT')
            st.info("Added 'refresh_token' column to 'tokens' table.")
        except sqlite3.OperationalError as e:
            st.error(f"Error altering tokens table: {e}")
    
    # Ensure contacts table exists
    c.execute('''
        CREATE TABLE IF NOT EXISTS contacts (
            id TEXT PRIMARY KEY,
            data TEXT NOT NULL
        )
    ''')
    
    # Ensure matters table exists
    c.execute('''
        CREATE TABLE IF NOT EXISTS matters (
            id TEXT PRIMARY KEY,
            data TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()

def get_token_from_db():
    """
    Retrieve the latest access token, refresh token, and expiry from the database.
    Returns:
        access_token (str or None)
        refresh_token (str or None)
        token_expiry (datetime or None)
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT access_token, refresh_token, token_expiry FROM tokens ORDER BY id DESC LIMIT 1')
    row = c.fetchone()
    conn.close()
    if row:
        access_token, refresh_token, token_expiry_str = row
        try:
            token_expiry = datetime.strptime(token_expiry_str, '%Y-%m-%d %H:%M:%S.%f')
            return access_token, refresh_token, token_expiry
        except ValueError:
            st.error("Invalid token expiry format in database.")
            return None, None, None
    return None, None, None

def save_token_to_db(access_token, refresh_token, token_expiry):
    """
    Save a new access token and refresh token to the database.
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('INSERT INTO tokens (access_token, refresh_token, token_expiry) VALUES (?, ?, ?)', 
              (access_token, refresh_token, token_expiry.strftime('%Y-%m-%d %H:%M:%S.%f')))
    conn.commit()
    conn.close()

def get_refresh_token():
    """
    Retrieve the latest refresh token from the database.
    Returns:
        refresh_token (str or None)
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT refresh_token FROM tokens ORDER BY id DESC LIMIT 1')
    row = c.fetchone()
    conn.close()
    if row:
        return row[0]
    return None

def get_contacts_from_db():
    """
    Retrieve all contacts from the database.
    Returns:
        contacts (list): List of contact dictionaries.
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT data FROM contacts')
    rows = c.fetchall()
    conn.close()
    contacts = [json.loads(row[0]) for row in rows]
    return contacts

def save_contacts_to_db(contacts):
    """
    Save contacts to the database.
    Args:
        contacts (list): List of contact dictionaries.
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    for contact in contacts:
        c.execute('INSERT OR REPLACE INTO contacts (id, data) VALUES (?, ?)', 
                  (contact['id'], json.dumps(contact)))
    conn.commit()
    conn.close()

def get_matters_from_db():
    """
    Retrieve all matters from the database.
    Returns:
        matters (list): List of matter dictionaries.
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT data FROM matters')
    rows = c.fetchall()
    conn.close()
    matters = [json.loads(row[0]) for row in rows]
    return matters

def save_matters_to_db(matters):
    """
    Save matters to the database.
    Args:
        matters (list): List of matter dictionaries.
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    for matter in matters:
        c.execute('INSERT OR REPLACE INTO matters (id, data) VALUES (?, ?)', 
                  (matter['id'], json.dumps(matter)))
    conn.commit()
    conn.close()

# ------------------------------
# 3. Token Management Functions
# ------------------------------

def refresh_access_token(refresh_token):
    """
    Refresh the access token using the provided refresh token.
    Returns:
        new_access_token (str or None)
    """
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    response = requests.post(TOKEN_URL, data=data)
    if response.status_code == 200:
        token_data = response.json()
        access_token = token_data['access_token']
        new_refresh_token = token_data.get('refresh_token', refresh_token)  # Some APIs may return a new refresh token
        token_expiry = datetime.now() + timedelta(seconds=token_data['expires_in'])
        save_token_to_db(access_token, new_refresh_token, token_expiry)
        st.success("Access token refreshed successfully.")
        return access_token
    else:
        st.error(f"Failed to refresh token: {response.status_code}, {response.text}")
        return None

def get_valid_token():
    """
    Retrieve a valid access token, refreshing it if necessary.
    Returns:
        access_token (str or None)
    """
    access_token, refresh_token, token_expiry = get_token_from_db()
    if not access_token or not token_expiry:
        return None
    elif token_expiry <= datetime.now():
        if refresh_token:
            return refresh_access_token(refresh_token)
        else:
            return None
    else:
        return access_token

# ------------------------------
# 4. OAuth Authentication Function
# ------------------------------

def authenticate():
    """
    Handles the OAuth 2.0 Authorization Code Grant flow.
    """
    # Check if the user is returning from the authorization server
    query_params = st.experimental_get_query_params()
    if 'code' in query_params:
        code = query_params['code'][0]
        # Exchange the authorization code for an access token
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        }
        response = requests.post(TOKEN_URL, data=data)
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data['access_token']
            refresh_token = token_data.get('refresh_token')
            token_expiry = datetime.now() + timedelta(seconds=token_data['expires_in'])
            save_token_to_db(access_token, refresh_token, token_expiry)
            st.success("Authentication successful!")
            # Remove the authorization code from the URL to clean up
            st.experimental_set_query_params()
        else:
            st.error(f"Failed to obtain token: {response.status_code}, {response.text}")
    
    # Check if a valid token exists
    access_token, refresh_token, token_expiry = get_token_from_db()
    if not access_token or not token_expiry or token_expiry <= datetime.now():
        auth_params = {
            "response_type": "code",
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "scope": "read",  # Adjust scopes as necessary
            "state": "streamlit_app",  # Optional: can be used to prevent CSRF
        }
        auth_url = f"{AUTH_URL}?{urlencode(auth_params)}"
        st.markdown(f"### Please [authorize the application]({auth_url}) to continue.")
        st.stop()

# ------------------------------
# 5. API Request Function
# ------------------------------

def clio_api_request(endpoint, params=None):
    """
    Make an authenticated GET request to the Clio API.
    Args:
        endpoint (str): API endpoint (e.g., 'contacts', 'matters').
        params (dict, optional): Query parameters.
    Returns:
        response.json() if successful, else None
    """
    token = get_valid_token()
    if not token:
        st.warning("No valid access token available. Please authenticate.")
        return None
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{CLIO_API_BASE_URL}/{endpoint}", headers=headers, params=params)
    if response.status_code == 200:
        return response.json()
    elif response.status_code == 401:
        # Token might have just expired, try refreshing once
        refresh_token = get_refresh_token()
        if refresh_token:
            new_token = refresh_access_token(refresh_token)
            if new_token:
                headers = {"Authorization": f"Bearer {new_token}"}
                response = requests.get(f"{CLIO_API_BASE_URL}/{endpoint}", headers=headers, params=params)
                if response.status_code == 200:
                    return response.json()
        st.error(f"Failed to fetch data from Clio: {response.status_code}, {response.text}")
    else:
        st.error(f"Failed to fetch data from Clio: {response.status_code}, {response.text}")
    return None

# ------------------------------
# 6. Data Fetching Function with Pagination Limit
# ------------------------------

def fetch_all_pages(endpoint, save_to_db_func, max_pages=10):
    """
    Fetch all pages of data from a Clio API endpoint up to a maximum number of pages.
    
    Args:
        endpoint (str): API endpoint to fetch data from (e.g., 'contacts', 'matters').
        save_to_db_func (function): Function to save fetched data to the database.
        max_pages (int): Maximum number of pages to fetch. Defaults to 10.
        
    Returns:
        list: Accumulated data from all fetched pages.
    """
    all_data = []
    params = {"limit": 100, "page": 1}
    pages_fetched = 0  # Counter for the number of pages fetched

    while True:
        if pages_fetched >= max_pages:
            st.warning(f"Reached the maximum page limit of {max_pages}. Stopping data fetch.")
            break

        data = clio_api_request(endpoint, params)
        
        if data and 'data' in data:
            fetched_records = len(data['data'])
            all_data.extend(data['data'])
            pages_fetched += 1
            st.write(f"Fetched {fetched_records} items from {endpoint}, page {params['page']} (Page {pages_fetched}/{max_pages})")
            
            # Log pagination details for debugging
            paging = data.get('meta', {}).get('paging', {})
            current_page = paging.get('current_page')
            next_page = paging.get('next_page')
            total_pages = paging.get('total_pages')
            total_records = paging.get('total_records')
            
            st.write(f"Current Page: {current_page}, Next Page: {next_page}, Total Pages: {total_pages}, Total Records: {total_records}")
            
            if next_page:
                params['page'] = next_page
            else:
                st.write("No more pages to fetch.")
                break
        else:
            st.write("No data found or end of data reached.")
            break

    # Save fetched data to the database
    save_to_db_func(all_data)
    
    return all_data

# ------------------------------
# 7. Custom Field Retrieval Function
# ------------------------------

def get_custom_field_value(contact, field_name):
    """
    Retrieve the value of a custom field from a contact.
    Args:
        contact (dict): Contact data.
        field_name (str): Name of the custom field.
    Returns:
        value (str or None)
    """
    for field in contact.get('custom_field_values', []):
        if field['field_name'].lower() == field_name.lower():
            return field['value']
    return None

# ------------------------------
# 8. Conflict Checking Function
# ------------------------------

def perform_advanced_conflict_check(new_client_info, contacts, matters):
    """
    Perform an advanced conflict check against existing contacts and matters.
    Args:
        new_client_info (dict): Information about the new client.
        contacts (list): List of existing contacts.
        matters (list): List of existing matters.
    Returns:
        conflicts (list): List of detected conflicts.
    """
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
                    conflicts.append(f"Nickname match: {contact['name']} (Nickname: {nickname.strip()})")
        
        # Check date of birth
        dob = get_custom_field_value(contact, 'Date of Birth')
        if dob and dob == new_client_info['dob']:
            conflicts.append(f"Date of birth match: {contact['name']} (DOB: {dob})")
        
        # Check address
        contact_address = contact.get('address', {}).get('street', '').lower()
        new_address = new_client_info['address'].lower()
        if contact_address and new_address and contact_address == new_address:
            conflicts.append(f"Address match: {contact['name']}")
        
        # Check phone number
        for phone in contact.get('phone_numbers', []):
            if phone['number'] == new_client_info['phone']:
                conflicts.append(f"Phone number match: {contact['name']}")
        
        # Business-specific checks
        if contact.get('type', '').lower() == 'company':
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
        client = matter.get('client', {})
        client_name = client.get('name', '').lower()
        if new_client_info['name'].lower() in client_name:
            conflicts.append(f"Opposing party match in matter: {matter.get('display_number', 'N/A')} - {matter.get('description', 'N/A')}")
    
    return conflicts

# ------------------------------
# 9. Data Loading Function
# ------------------------------

def load_data():
    """
    Load contacts and matters from the database or fetch from Clio API if not present.
    Returns:
        contacts (list): List of contact dictionaries.
        matters (list): List of matter dictionaries.
    """
    contacts = get_contacts_from_db()
    matters = get_matters_from_db()
    
    if not contacts or not matters:
        with st.spinner("Fetching data from Clio..."):
            if not contacts:
                # Limit to 10 pages for contacts
                contacts = fetch_all_pages('contacts', save_contacts_to_db, max_pages=10)
            if not matters:
                # Limit to 10 pages for matters
                matters = fetch_all_pages('matters', save_matters_to_db, max_pages=10)
        if contacts and matters:
            st.success(f"Loaded {len(contacts)} contacts and {len(matters)} matters from Clio and saved to the database.")
        else:
            st.error("Failed to fetch data. Please check your Clio API credentials and authentication.")
    else:
        st.success(f"Loaded {len(contacts)} contacts and {len(matters)} matters from the database.")
    
    return contacts, matters

# ------------------------------
# 10. Streamlit Application Layout
# ------------------------------

# Initialize the database
init_db()

# Authenticate the user
authenticate()

# Load contacts and matters with a limit of 10 pages each
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

# Display data statistics in the sidebar
st.sidebar.title("Data Statistics")
st.sidebar.write(f"Number of contacts: {len(contacts)}")
st.sidebar.write(f"Number of matters: {len(matters)}")

# Optional: Add a refresh data button in the sidebar
if st.sidebar.button("Refresh Clio Data"):
    with st.spinner("Refreshing data from Clio..."):
        # Clear the database tables
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('DELETE FROM contacts')
        c.execute('DELETE FROM matters')
        conn.commit()
        conn.close()
    st.success("Clio data refreshed successfully.")
    st.experimental_rerun()

# Display token information in the sidebar
access_token, refresh_token, token_expiry = get_token_from_db()
if access_token and token_expiry:
    st.sidebar.title("Token Information")
    st.sidebar.write(f"Token expires at: {token_expiry.strftime('%Y-%m-%d %H:%M:%S')}")
    if token_expiry > datetime.now():
        st.sidebar.success("Token is valid")
    else:
        st.sidebar.warning("Token has expired (will be refreshed on next API call)")
