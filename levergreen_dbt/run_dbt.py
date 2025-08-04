import os
import subprocess
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Print environment variables for debugging
print(f"PG_HOST: {os.getenv('PG_HOST')}")
print(f"PG_USER: {os.getenv('PG_USER')}")
print(f"PG_DATABASE: {os.getenv('PG_DATABASE')}")

# Run dbt build with real-time output
print("Running dbt build...")
process = subprocess.Popen(['dbt', 'build'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

# Print output in real-time
for line in iter(process.stdout.readline, ''):
    print(line, end='')

# Wait for the process to complete
return_code = process.wait()
print(f"Return code: {return_code}")