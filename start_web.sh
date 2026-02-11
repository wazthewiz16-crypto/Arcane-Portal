#!/bin/bash
# Start Streamlit dashboard
echo "Starting Streamlit dashboard..."
streamlit run dashboard/app.py --server.port=${PORT:-8501} --server.address=0.0.0.0 --server.headless=true --server.enableCORS=false --server.enableXsrfProtection=false
