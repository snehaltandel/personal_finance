import os
import pandas as pd
import streamlit as st
from tabs.file_uploader import FileUploader
from tabs.historical_category_reference import HistoricalCategoryReference
import json
import boto3
from io import StringIO
from dotenv import load_dotenv
from tabs.amount_utils import normalize_amount_series
from tabs.transaction_service import TransactionService
load_dotenv()

config = json.load(open("assets/config.json"))

account_types = config["ACCOUNT_TYPES"]
output_headers = config["OUTPUT_HEADERS"]

s3 = boto3.client(
    's3',
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"]
)
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
        self.transaction_service = TransactionService(data_dir=data_dir)

    def list_files(self):
        """
        List all CSV files from an S3 bucket within a specified directory.

        Returns:
            list: A list of file paths (keys) for CSV files that match the specified account types.
        """
        return self.transaction_service.list_source_files()

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
        all_data = self.transaction_service.consolidate_transactions(selected_files)

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
