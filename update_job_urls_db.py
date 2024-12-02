import pandas as pd
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from urllib.parse import urlparse
from sqlalchemy.engine import URL
import logging
import re

# Enable logging
logging.basicConfig(level=logging.DEBUG)

# Load environment variables from a specific path
dotenv_path = '/Users/arnav/Downloads/GitHub/job-board-scraper-arnav/.env'  # Replace with the actual path
load_dotenv(dotenv_path, verbose=True)

# Database connection parameters
DB_USER = os.getenv('PG_USER')
DB_PASSWORD = os.getenv('PG_PASSWORD')
DB_HOST = os.getenv('PG_HOST')
DB_NAME = os.getenv('PG_DATABASE')

# Print only necessary environment variables
print(f"DB_USER: {DB_USER} (type: {type(DB_USER)})")
print(f"DB_HOST: {DB_HOST} (type: {type(DB_HOST)})")
print(f"DB_NAME: {DB_NAME} (type: {type(DB_NAME)})")

# Check for missing environment variables
required_env_vars = ['PG_USER', 'PG_PASSWORD', 'PG_HOST', 'PG_DATABASE']
missing_vars = [var for var in required_env_vars if os.getenv(var) is None]

if missing_vars:
    raise EnvironmentError(f"Missing environment variables: {', '.join(missing_vars)}")

# Ensure DB_PASSWORD is a string
if not isinstance(DB_PASSWORD, str):
    DB_PASSWORD = str(DB_PASSWORD)

# Create database connection URL
db_url = URL.create(
    drivername="postgresql",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    database=DB_NAME
)
print("Database URL created.")

engine = create_engine(db_url)
print("Database engine created.")

# Read CSV file
df = pd.read_csv('/Users/arnav/Downloads/GitHub/Linkedin-Jobs/company_ats_data.csv')
print("CSV file read successfully.")

# Convert all column names to lowercase
df.columns = df.columns.str.lower()

# Define allowed ATS types including 'unknown'
allowed_ats = [
    'greenhouse', 'lever', 'ashbyhq', 'workable', 
    'recruitee', 'jobvite', 'smartrecruiters', 'teamtailor', 'unknown'
]
df = df[df['ats'].str.lower().isin(allowed_ats)]

# Define lists for unwanted subdomains and paths
UNWANTED_SUBDOMAINS = [
    'faq', 'faqs', 'marketing', 'dev', 'api', 'app', 
    'track', 'support', 'help', 'docs', 'reference', 
    'hire', 'auth'
]

# Define patterns for language and country codes
LANGUAGE_CODES = r'(?:/[a-z]{2}(?:-[A-Z]{2})?)'
COUNTRY_CODES = r'^[a-z]{2}\.|'  # e.g., fr., es., de.

# Define unwanted path segments
UNWANTED_PATHS = [
    'robots.txt', 'reference', 'settings', 
    'hiring-excellence-framework', 'embed',
    'data-privacy', 'privacy-policy', 'cookie-policy', 'cookie_policy',
    'connect', 'people', 'locations', 'pages', 'request_removal', 'data_request',
    'auth', 'faq', 'faqs', 'marketing', 'dev', 'api', 'app', 'track'
]

# Function to categorize unknown ATS based on URL
def categorize_unknown_ats(row):
    url = row['company url']
    parsed_url = urlparse(url)
    netloc = parsed_url.netloc.lower()
    path = parsed_url.path.lower()
    
    # Remove port if present
    netloc = netloc.split(':')[0]
    
    # Remove language or country codes in subdomain
    netloc_parts = netloc.split('.')
    filtered_netloc_parts = [
        part for part in netloc_parts 
        if part not in UNWANTED_SUBDOMAINS and not re.fullmatch(r'[a-z]{2}', part)
    ]
    filtered_netloc = '.'.join(filtered_netloc_parts)
    
    # Define patterns for known ATS
    ats_patterns = {
        'greenhouse': r'(\.eu)?\.greenhouse\.io$',
        'lever': r'\.lever\.co$',
        'ashbyhq': r'\.ashbyhq\.com$',
        'workable': r'\.workable\.com$',
        'recruitee': r'\.recruitee\.com$',
        'jobvite': r'\.jobvite\.com$',
        'smartrecruiters': r'\.smartrecruiters\.com$',
        'teamtailor': r'\.teamtailor\.com$'
    }
    
    for ats, pattern in ats_patterns.items():
        if re.search(pattern, filtered_netloc):
            return ats
    return 'unknown'  # If no pattern matches

# Categorize unknown ATS
df.loc[df['ats'].str.lower() == 'unknown', 'ats'] = df[df['ats'].str.lower() == 'unknown'].apply(categorize_unknown_ats, axis=1)

# Updated clean_url function
def clean_url(url, ats):
    parsed_url = urlparse(url)
    
    # Normalize netloc by removing port and lowercasing
    netloc = parsed_url.netloc.lower().split(':')[0]
    path = parsed_url.path.lower()
    
    # Remove language and country codes from path
    path = re.sub(LANGUAGE_CODES, '', path)
    
    # Check for unwanted subdomains
    netloc_parts = netloc.split('.')
    if netloc_parts[0] in UNWANTED_SUBDOMAINS:
        logging.debug(f"URL '{url}' excluded due to unwanted subdomain '{netloc_parts[0]}'.")
        return None
    
    # Check for unwanted paths
    path_segments = path.strip('/').split('/')
    for segment in path_segments:
        if segment in UNWANTED_PATHS:
            logging.debug(f"URL '{url}' excluded due to unwanted path segment '{segment}'.")
            return None
    
    # ATS-Specific Normalization
    if ats == 'ashbyhq':
        if netloc.startswith('jobs.ashbyhq.com'):
            company = path.strip('/')
            if company:
                return f"https://jobs.ashbyhq.com/{company}"
        return None
    
    elif ats == 'greenhouse':
        company = path.strip('/').split('/')[0]
        if company:
            return f"https://job-boards.greenhouse.io/{company}"
        return None
    
    elif ats == 'lever':
        if netloc.startswith('jobs.lever.co'):
            company = path.strip('/').split('/')[0]
            if company:
                return f"https://jobs.lever.co/{company}"
        return None
    
    elif ats == 'workable':
        if netloc.startswith('apply.workable.com'):
            company = path.strip('/').split('/')[0]
            if company:
                return f"https://apply.workable.com/{company}/"
        return None
    
    elif ats == 'recruitee':
        if netloc.endswith('.recruitee.com'):
            company = netloc.split('.')[0]
            if company:
                return f"https://{company}.recruitee.com/"
        return None
    
    elif ats == 'jobvite':
        if netloc.startswith('jobs.jobvite.com'):
            company = path.strip('/').split('/')[0]
            if company:
                # Remove query parameters
                return f"https://jobs.jobvite.com/{company}"
        return None
    
    elif ats == 'smartrecruiters':
        company = path.strip('/').split('/')[0]
        if company:
            # Remove query parameters and tracking links
            return f"https://careers.smartrecruiters.com/{company}"
        return None
    
    elif ats == 'teamtailor':
        company = netloc.split('.')[0]
        if path.startswith('/jobs'):
            return f"https://{company}.teamtailor.com/jobs"
        elif path == '' or path == '/':
            return f"https://{company}.teamtailor.com/jobs"
        elif '/jobs' in path:
            return f"https://{company}.teamtailor.com/jobs"
        else:
            # If no specific path, default to /jobs
            return f"https://{company}.teamtailor.com/jobs"
    
    elif ats == 'unknown':
        # Attempt to categorize based on existing ATS patterns
        # If still unknown, skip the URL
        return None
    
    # Return cleaned URL without query parameters for other ATS or unknown
    return f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"

# Apply the clean_url function and filter out None values
df['company_url'] = df.apply(lambda row: clean_url(row['company url'], row['ats'].lower()), axis=1)
df = df.dropna(subset=['company_url'])

# Drop duplicates based on 'company_url'
df = df.drop_duplicates(subset='company_url')

# Define ATS types that are enabled
enabled_ats = ['greenhouse', 'lever', 'ashbyhq']

# Set is_enabled to True for enabled ATS and False otherwise
df['is_enabled'] = df['ats'].str.lower().isin(enabled_ats)

# Set is_prospect to True for non-enabled ATS and False otherwise
df['is_prospect'] = ~df['is_enabled']

# Select and reorder columns - include is_prospect
final_df = df[['company_url', 'ats', 'is_enabled', 'is_prospect']]

# Create table and upload data
try:
    # Create table if it doesn't exist
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS job_board_urls (
        id SERIAL PRIMARY KEY,
        company_url TEXT NOT NULL UNIQUE,
        ats TEXT NOT NULL,
        is_enabled BOOLEAN DEFAULT TRUE,
        is_prospect BOOLEAN DEFAULT FALSE
    );
    """
    
    # Prepare upsert SQL with correct parameter binding
    upsert_sql = """
    INSERT INTO job_board_urls (company_url, ats, is_enabled, is_prospect)
    VALUES (:company_url, :ats, :is_enabled, :is_prospect)
    ON CONFLICT (company_url) 
    DO UPDATE SET 
        ats = EXCLUDED.ats,
        is_enabled = EXCLUDED.is_enabled,
        is_prospect = EXCLUDED.is_prospect;
    """
    
    with engine.connect() as conn:
        conn.execute(text(create_table_sql))
        
        records = final_df.to_dict('records')
        for record in records:
            conn.execute(text(upsert_sql), record)
        
        conn.commit()
        print(f"Successfully upserted {len(records)} records to database!")

except Exception as e:
    logging.error("An error occurred during the database operation", exc_info=True)
    print(f"An error occurred: {e}")