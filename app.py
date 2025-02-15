# Import necessary libraries
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from file_uploader import FileUploader
from transaction_cleaner import TransactionCleaner
from transaction_editor import TransactionEditor
from dashboard import Dashboard
import boto3
from io import StringIO
import json

# Load configuration
config = json.load(open("assets/config.json"))

# Function to read uploaded file
def read_file(uploaded_file):
    if uploaded_file.name.endswith('.csv'):
        return pd.read_csv(uploaded_file)
    elif uploaded_file.name.endswith('.xlsx'):
        return pd.read_excel(uploaded_file)
    else:
        st.error("Unsupported file format")
        return None

# Streamlit app
st.title("Personal Finance Manager")

# Create tabs
tab1, tab2, tab3, tab4 = st.tabs(["Import Transactions", "Transaction Cleaner", "Transaction Editor", "Dashboard"])

# Tab 1: Import Transactions
with tab1:
    st.header("Import Transactions")
    uploader = FileUploader()
    uploader.upload_file()
    uploader.view_files()

# Tab 2: Transaction Cleaner
with tab2:
    st.header("Transaction Cleaner")
    TransactionCleaner().main()

# Tab 3: Trends
with tab3:
    st.header("Transaction Editor")
    editor = TransactionEditor()
    editor.main()

# Tab 4: Dashboard
with tab4:
    # st.header("Dashboard")
    # Load data
    # Initialize S3 client
    s3 = boto3.client('s3')

    # Define bucket and file name
    bucket_name = config["S3_BUCKET_NAME"]
    file_key = config["ALL_ACCOUNTS_EDITED_FILE_PATH"]

    # Read the file from S3
    obj = s3.get_object(Bucket=bucket_name, Key=file_key)
    df = pd.read_csv(StringIO(obj['Body'].read().decode('utf-8')))
    df["Transaction_Date"] = pd.to_datetime(df["Transaction_Date"])

    # Create an instance of the dashboard
    dashboard = Dashboard(df)
    dashboard.main()
    