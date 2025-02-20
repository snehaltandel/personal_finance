import os
import pandas as pd
import streamlit as st
from eda.file_uploader import FileUploader
from tabs.historical_category_reference import HistoricalCategoryReference
import json
import boto3
from io import StringIO

config = json.load(open("assets/config.json"))

account_types = config["ACCOUNT_TYPES"]
output_headers = config["OUTPUT_HEADERS"]

s3 = boto3.client('s3')
bucket_name = config["S3_BUCKET_NAME"]
AMOUNT_NEGATIVE_ACCOUNTS = config["AMOUNT_NEGATIVE_ACCOUNTS"]
ALL_ACCOUNTS_FILE_PATH = config["ALL_ACCOUNTS_FILE_PATH"]
ALL_ACCOUNTS_EDITED_FILE_PATH = config["ALL_ACCOUNTS_EDITED_FILE_PATH"]

class TransactionCleaner:
    def __init__(self, data_dir="data"):
        """
        Initializes the TransactionCleaner with the specified data directory.

        Args:
            data_dir (str): The directory where the data files are stored. Defaults to "data".
        """
        self.data_dir = data_dir

    def list_files(self):
        """
        List all CSV files from an S3 bucket within a specified directory.

        Returns:
            list: A list of file paths (keys) for CSV files that match the specified account types.
        """
        file_list = []
        response = s3.list_objects_v2(Bucket=bucket_name, Prefix=self.data_dir)
        for obj in response.get('Contents', []):
            if obj['Key'].endswith('.csv'):
                account_type = obj['Key'].split("/")[-2]
                if account_type in account_types:
                    file_list.append(obj['Key'])
        return file_list

    def read_s3_file(self, file_path):
        """
        Reads a CSV file from an S3 bucket and returns it as a pandas DataFrame.

        Parameters:
        file_path (str): The path to the file in the S3 bucket.

        Returns:
        pd.DataFrame: The contents of the CSV file as a pandas DataFrame.
        """
        obj = s3.get_object(Bucket=bucket_name, Key=file_path)
        return pd.read_csv(StringIO(obj['Body'].read().decode('utf-8')))

    def save_s3_file(self, df, file_path):
        """
        Save a DataFrame to an S3 bucket as a CSV file.

        Parameters:
        df (pandas.DataFrame): The DataFrame to be saved.
        file_path (str): The S3 file path where the CSV will be saved.

        Returns:
        None
        """
        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False)
        s3.put_object(Bucket=bucket_name, Key=file_path, Body=csv_buffer.getvalue())

    def consolidate_transactions(self, selected_files):
        """
        Consolidates transactions from multiple files into a single DataFrame.
        Args:
            selected_files (list): List of file paths to be consolidated.
        Returns:
            None
        """
        all_data = pd.DataFrame()
        for file_path in selected_files:
            df = self.read_s3_file(file_path)
            account_type = file_path.split("/")[-2]
            df['Account_Type'] = account_type

            # Multiply Amount by -1 
            if account_type in AMOUNT_NEGATIVE_ACCOUNTS:
                df['Amount'] = df['Amount'] * -1

            # Make Amount to be 2 decimal places
            df['Amount'] = df['Amount'].round(2)

            # Update code to add new columns if missing
            for header in output_headers:
                if header not in df.columns:
                    df[header] = pd.NaT
            
            # Update Transaction_Date and Post_Date column to datetime format
            df['Transaction_Date'] = pd.to_datetime(df['Transaction_Date'], errors='coerce').dt.date
            df['Post_Date'] = pd.to_datetime(df['Post_Date'], errors='coerce').dt.date

            all_data = pd.concat([all_data, df], ignore_index=True)
            # Sort data by all columns

            all_data = all_data.sort_values(by=['Transaction_Date', 'Description', 'Amount'], ascending=[False, True, True]).reset_index(drop=True)

        st.write("Consolidated Data:")
        st.dataframe(all_data)

        self.save_s3_file(all_data, ALL_ACCOUNTS_FILE_PATH)
        st.success(f"{all_data.shape[0]} Transactions consolidated successfully & saved as {ALL_ACCOUNTS_FILE_PATH}!")
        
    # Streamlit app
    def main(self):
        """
        Main function to handle the transaction cleaning process.
        """
        file_list = self.list_files()

        if file_list:
            # Update multiselect to display check boxes and an option to select all files from the drop down
            selected_files = st.multiselect(
                "Select files to consolidate:",
                options=file_list,
                default=file_list if st.checkbox("Select All") else []
            )

            if st.button("Consolidate Transactions"):
                with st.spinner("Consolidating transactions..."):
                    self.consolidate_transactions(selected_files)
            
            if st.button("Apply Historical Categories"):
                with st.spinner("Applying Historical Categories..."):

                    # Apply historical categories
                    historical_ref = HistoricalCategoryReference()
                    consolidated_data = historical_ref.main()
                    consolidated_data = consolidated_data.sort_values(by=['Transaction_Date', 'Account_Type', 'Description', 'Amount'], ascending=[False, True, True, True]).reset_index(drop=True)

                    st.write("Data with Applied Categories:")
                    st.dataframe(consolidated_data, use_container_width=True)
                    st.write("Number of transactions:", consolidated_data.shape[0])

                    self.save_s3_file(consolidated_data, ALL_ACCOUNTS_EDITED_FILE_PATH)
                    st.success("Categories applied successfully!")
                    st.write(f"Data with categories saved as {ALL_ACCOUNTS_EDITED_FILE_PATH}")
        else:
            st.write("No CSV files found in the specified directory.")