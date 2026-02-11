#!/usr/bin/env python3
"""Wrapper script to start Streamlit with proper port handling"""
import os
import subprocess
import sys

# Get port from environment, handle empty/None values
port = os.environ.get('PORT', '').strip()

# If PORT is empty, None, or invalid, use default
if not port or not port.isdigit():
    port = '8501'
    print(f"PORT not set or invalid, using default: {port}")
else:
    print(f"Using PORT from environment: {port}")

# Build streamlit command
cmd = [
    'streamlit', 'run',
    'dashboard/app.py',
    f'--server.port={port}',
    '--server.address=0.0.0.0',
    '--server.headless=true',
    '--server.enableCORS=false',
    '--server.enableXsrfProtection=false'
]

print(f"Starting Streamlit on port {port}...")
print(f"Command: {' '.join(cmd)}")

# Run streamlit
try:
    subprocess.run(cmd, check=True)
except KeyboardInterrupt:
    print("\nShutting down Streamlit...")
    sys.exit(0)
except Exception as e:
    print(f"Error starting Streamlit: {e}")
    sys.exit(1)
