import streamlit as st
import pandas as pd
import os
from datetime import datetime
import re
import json
import boto3
from io import BytesIO

config = json.load(open("assets/config.json"))

s3_client = boto3.client('s3')
bucket_name = config["S3_BUCKET_NAME"]

class FileUploader:
    def __init__(self):
        self.uploaded_files = []
        self.account_types = config["ACCOUNT_TYPES"]
        self.df = pd.DataFrame(columns=["Account Type", "New File Name", "Min Transaction Date", "Max Transaction Date", "Number of Transactions", "File Upload Date"])
    
    def view_files(self):
        '''
        Display the list of uploaded files with details
        '''
        data = []
        for account_type in self.account_types:
            prefix = f"data/{account_type}/"
            response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
            if 'Contents' in response:
                for obj in response['Contents']:
                    file_key = obj['Key']
                    st.write(file_key)
                    if file_key.endswith('.csv'):
                        obj = s3_client.get_object(Bucket=bucket_name, Key=file_key)
                        try:
                            df = pd.read_csv(BytesIO(obj['Body'].read()))
                            if df.empty:
                                continue
                            min_date = pd.to_datetime(df['Transaction_Date']).dt.date.min()
                            max_date = pd.to_datetime(df['Transaction_Date']).dt.date.max()
                            num_transactions = len(df)
                            upload_date = obj['LastModified']
                            data.append({
                                'File': file_key,
                                'Min Date': min_date,
                                'Max Date': max_date,
                                'Transactions': num_transactions,
                                'File Upload Date': upload_date
                            })
                        except pd.errors.EmptyDataError:
                            st.write(f"Warning: {file_key} is empty and will be skipped.")
            else:
                st.write(f"No files found for account type: {account_type}")
        self.df = pd.DataFrame(data)
        if not self.df.empty:
            self.df = self.df.sort_values(by="File Upload Date", ascending=False)
        st.header("Uploaded Files")
        st.dataframe(self.df, use_container_width=True)       

    # Function to save uploaded file with updated headers
    def save_file(self, df, account_type):            
        headers = config["HEADERS"][account_type]
        st.write(f"Using headers: {headers}")
        df.columns = headers
        try:
            # Extract min and max transaction dates
            min_date = str(pd.to_datetime(df['Transaction_Date']).dt.date.min())
            max_date = str(pd.to_datetime(df['Transaction_Date']).dt.date.max())

            # Create new file name
            new_file_name = f"data/{account_type}/{min_date}_{max_date}.csv"

            # Save cleaned dataframe to new CSV file in memory
            csv_buffer = BytesIO()
            df.to_csv(csv_buffer, index=False)
            csv_buffer.seek(0)

            # Upload to S3
            s3_client.put_object(Bucket=bucket_name, Key=new_file_name, Body=csv_buffer.getvalue())
            st.success(f"File successfully saved as {new_file_name}")
        except Exception as e:
            st.error(f"Error saving file: {e}")

    def upload_file(self):
        account_type = st.selectbox("Select Account Type", self.account_types)
        uploaded_file = st.file_uploader("Upload CSV or Excel file", type=["csv", "xlsx"])
        if uploaded_file is not None:
            st.subheader("Preview File")
            df = pd.read_csv(uploaded_file)
            st.dataframe(df, use_container_width=True)

            if st.button("Save File"):
                self.save_file(df, account_type)