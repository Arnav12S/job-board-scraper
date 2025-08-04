import os
import subprocess
from dotenv import load_dotenv

# Change to the directory containing this script
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

# For local development only - load environment variables from .env file in parent directory
# In production/CI, environment variables should be set via GitHub secrets
if os.path.exists(os.path.join(script_dir, '..', '.env')):
    load_dotenv(os.path.join(script_dir, '..', '.env'))
    print("Loaded environment variables from .env file for local development")
else:
    print("No .env file found - using system environment variables (production mode)")

# Print environment variables for debugging (masked for security)
print(f"PG_HOST: {os.getenv('PG_HOST')}")
print(f"PG_USER: {os.getenv('PG_USER')}")
print(f"PG_DATABASE: {os.getenv('PG_DATABASE')}")
print(f"PG_PORT: {os.getenv('PG_PORT', '6543')}")

# Verify required environment variables are set
required_vars = ['PG_HOST', 'PG_USER', 'PG_PASSWORD', 'PG_DATABASE']
missing_vars = [var for var in required_vars if not os.getenv(var)]
if missing_vars:
    print(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
    print("For local development, ensure .env file exists in parent directory.")
    print("For production, ensure GitHub secrets are properly configured.")
    exit(1)

# Run dbt build with real-time output
print("Running dbt build...")
process = subprocess.Popen(['dbt', 'build'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

# Print output in real-time
for line in iter(process.stdout.readline, ''):
    print(line, end='')

# Wait for the process to complete
return_code = process.wait()
print(f"Return code: {return_code}")