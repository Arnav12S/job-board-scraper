import pandas as pd
import os
from urllib.parse import urlparse
import logging
import re
from supabase import create_client, Client
import time

# Enable logging

# Supabase setup
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

# Check for required Supabase environment variables
required_env_vars = ['SUPABASE_URL', 'SUPABASE_KEY']
missing_vars = [var for var in required_env_vars if os.getenv(var) is None]

if missing_vars:
    raise EnvironmentError(f"Missing environment variables: {', '.join(missing_vars)}")

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
print("Supabase client initialized.")

# Read CSV file
csv_path = '/Users/arnav/Downloads/GitHub/Linkedin-Jobs/company_ats_data.csv'
df = pd.read_csv(csv_path)
print("CSV file read successfully.")

# Convert all column names to lowercase
df.columns = df.columns.str.lower()

# Define allowed ATS types including 'unknown'
allowed_ats = [
    'greenhouse', 'lever', 'ashbyhq', 'workable', 
    'recruitee', 'jobvite', 'smartrecruiters', 'teamtailor', 'personio', 'unknown'
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

# Configure logging to be less verbose
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Disable verbose HTTP debug logging
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('hpack').setLevel(logging.WARNING)

# After reading CSV, log initial count
initial_count = len(df)
logging.info(f"Initial records from CSV: {initial_count}")
logging.info("Initial ATS distribution:")
for ats, count in df['ats'].str.lower().value_counts().items():
    logging.info(f"- {ats}: {count} records")

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
        'teamtailor': r'\.teamtailor\.com$',
        'personio': r'\.personio\.com$'
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
            # Extract the company name from the path
            company = path.strip('/').split('/')[0]
            if company:
                # Correctly format the URL for Ashby
                return f"https://jobs.ashbyhq.com/{company}/jobs"
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
                # Add /jobs at the end of all Jobvite URLs
                return f"https://jobs.jobvite.com/{company}/search"
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
    
    elif ats == 'personio':
        if netloc.endswith('.personio.com'):
            company = netloc.split('.')[0]
            if company:
                return f"https://{company}.jobs.personio.com"
        return None
    
    elif ats == 'unknown':
        # Attempt to categorize based on existing ATS patterns
        # If still unknown, skip the URL
        return None
    
    # Return cleaned URL without query parameters for other ATS or unknown
    return f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"

# Apply the clean_url function and filter out None values
df['company_url'] = df.apply(lambda row: clean_url(row['company url'], row['ats'].lower()), axis=1)
cleaned_count = len(df)
removed_count = initial_count - cleaned_count
logging.info(f"Records removed during URL cleaning: {removed_count}")

# Drop duplicates based on 'company_url'
df = df.dropna(subset=['company_url'])
df = df.drop_duplicates(subset='company_url')
deduped_count = len(df)
dupes_removed = cleaned_count - deduped_count
logging.info(f"Duplicate records removed: {dupes_removed}")

# Log final preprocessing stats
logging.info("\nFinal preprocessing statistics:")
logging.info(f"Initial records: {initial_count}")
logging.info(f"Records after cleaning: {cleaned_count}")
logging.info(f"Records after deduplication: {deduped_count}")
logging.info(f"Total records removed: {initial_count - deduped_count}")

logging.info("\nFinal ATS distribution:")
for ats, count in df['ats'].str.lower().value_counts().items():
    logging.info(f"- {ats}: {count} records")

# Define ATS types that are enabled
enabled_ats = ['greenhouse', 'lever', 'ashbyhq', 'workable', 'jobvite', 'smartrecruiters', 'recruitee', 'teamtailor']

# Set is_enabled to True for enabled ATS and False otherwise
df['is_enabled'] = df['ats'].str.lower().isin(enabled_ats)

# Set is_prospect to True for non-enabled ATS and False otherwise
df['is_prospect'] = ~df['is_enabled']

# Select and reorder columns - include is_prospect
df = df[['company_url', 'ats', 'is_enabled', 'is_prospect']]

# Add required columns
df['is_web_scraped'] = True

# Extract company name based on ATS patterns
def extract_company_name(row):
    url = row['company_url']
    ats = row['ats']
    
    try:
        # Remove protocol and www if present
        clean_url = url.replace('https://', '').replace('http://', '').replace('www.', '')
        
        if ats in ['recruitee', 'teamtailor']:
            # Extract company name from subdomain
            return clean_url.split('.')[0]
        elif ats == 'personio':
            # Extract company name from subdomain for personio
            return clean_url.split('.')[0]
        else:
            # Extract company name from the first part of the URL path
            path_parts = clean_url.split('/')
            return path_parts[1] if len(path_parts) > 1 else None
    except Exception:
        return None

df['company'] = df.apply(extract_company_name, axis=1)

# Replace the database insertion code with this:
def batch_upsert(records, batch_size=100):
    total_records = len(records)
    successful_upserts = 0
    failed_upserts = 0
    
    for i in range(0, total_records, batch_size):
        batch = records[i:i + batch_size]
        try:
            response = supabase.table('job_board_urls').upsert(
                batch,
                on_conflict='company_url'
            ).execute()
            
            successful_upserts += len(batch)
            # Log every 1000 records or at the end
            if successful_upserts % 1000 == 0 or successful_upserts == total_records:
                logging.info(f"Progress: {successful_upserts}/{total_records} records processed ({(successful_upserts/total_records)*100:.1f}%)")
            
            time.sleep(0.5)
            
        except Exception as e:
            failed_upserts += len(batch)
            logging.error(f"Error processing batch {i//batch_size + 1}: {str(e)}")
            continue

    return successful_upserts, failed_upserts

# Convert DataFrame to records and process
records = df.to_dict('records')
successful_upserts, failed_upserts = batch_upsert(records)
print(f"Successfully upserted {successful_upserts} records to Supabase!")