import os
import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
from datetime import datetime
import boto3
from io import BytesIO
import json

# Initialize S3 client
s3 = boto3.client('s3')
config = json.load(open("assets/config.json"))
# Define S3 bucket and file paths
bucket_name = config["S3_BUCKET_NAME"]
categories_file_path = config["CATEGORIES_FILE_PATH"]
CONSOLIDATED_FILE_KEY = config["CONSOLIDATED_FILE_KEY"]
ALL_ACCOUNTS_EDITED_FILE_PATH = config["ALL_ACCOUNTS_EDITED_FILE_PATH"]
BACKUP_DIR_KEY = config["BACKUP_DIR_KEY"]

# Get predefined categories from S3
categories_df = pd.read_excel(categories_file_path)
predefined_categories = sorted(categories_df['Custom Categories'].unique().tolist())

class TransactionEditor:
    def __init__(self):
        """
        Initializes the TransactionEditor class.
        Raises:
            s3.exceptions.NoSuchKey: If neither the edited nor the consolidated file exists in S3.
        """
        
        self.consolidated_file_key = CONSOLIDATED_FILE_KEY
        self.edited_file_key = ALL_ACCOUNTS_EDITED_FILE_PATH
        self.backup_dir_key = BACKUP_DIR_KEY

        try:
            edited_obj = s3.get_object(Bucket=bucket_name, Key=self.edited_file_key)
            self.df = pd.read_csv(BytesIO(edited_obj['Body'].read()))
        except s3.exceptions.NoSuchKey:
            try:
                consolidated_obj = s3.get_object(Bucket=bucket_name, Key=self.consolidated_file_key)
                self.df = pd.read_csv(BytesIO(consolidated_obj['Body'].read()))
                self.df['Last_Updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.save_to_s3(self.df, self.edited_file_key)
            except s3.exceptions.NoSuchKey:
                self.df = pd.DataFrame()

    def main(self):
        """
        Displays a form for editing transactions and provides options to save changes, refresh, or backup the data.
        """
        st.write("Edit Transactions:")
        edited_df = st.data_editor(
            self.df.sort_values(by="Transaction_Date", ascending=False),
            num_rows="dynamic", 
            use_container_width=True,
            column_config={
                    "Category": st.column_config.SelectboxColumn(
                        "Category",
                        help="Select a category",
                        options=predefined_categories,
                        required=True
                    )
                },
                hide_index=True
            )

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("Save Changes"):
                self.save_to_s3(edited_df, self.edited_file_key)

        with col2:
            if st.button("Refresh"):
                self.refresh_transactions(edited_df)

        with col3:
            if st.button("Backup"):
                self.backup_file(edited_df)

    def refresh_transactions(self, edited_df):
        """
        Refreshes the transactions by comparing the edited DataFrame with the consolidated data from S3.

        Parameters:
        edited_df (pd.DataFrame): The DataFrame containing the edited transactions.

        Raises:
        s3.exceptions.NoSuchKey: If the edited file does not exist in the S3 bucket.
        """
        try:
            consolidated_obj = s3.get_object(Bucket=bucket_name, Key=self.consolidated_file_key)
            consolidated_df = pd.read_csv(BytesIO(consolidated_obj['Body'].read()))
            new_transactions = consolidated_df[~consolidated_df[['Transaction_Date', 'Amount', 'Account_Type', 'Description']].apply(tuple, 1).isin(
                edited_df[['Transaction_Date', 'Amount', 'Account_Type', 'Description']].apply(tuple, 1))]
            if not new_transactions.empty:
                
                new_transactions['Last_Updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.info("New Transactions:")
                st.dataframe(new_transactions)
                updated_df = pd.concat([edited_df, new_transactions]).reset_index(drop=True)
                self.save_to_s3(updated_df, self.edited_file_key)
                st.write("Transactions refreshed successfully!")
            else:
                st.write("No new transactions to add.")
        except s3.exceptions.NoSuchKey:
            st.write("Edited file does not exist.")

    def backup_file(self, edited_df):
        """
        Creates a backup of the edited DataFrame by saving it to an S3 bucket with a timestamped filename.

        Args:
            edited_df (pd.DataFrame): The DataFrame containing the edited transaction data.

        Raises:
            s3.exceptions.NoSuchKey: If the specified S3 key does not exist.

        Side Effects:
            Writes a message to the Streamlit app indicating the success or failure of the backup operation.
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename_key = os.path.join(self.backup_dir_key, f"all_accounts_edited_backup_{timestamp}.csv")
            self.save_to_s3(edited_df, backup_filename_key)
            st.write(f"Backup created successfully: {backup_filename_key}")
        except s3.exceptions.NoSuchKey:
            st.write("Edited file does not exist.")

    def save_to_s3(self, df, key):
        """
        Save a DataFrame to an S3 bucket as a CSV file.

        Parameters:
        df (pandas.DataFrame): The DataFrame to be saved.
        key (str): The S3 object key (i.e., the path in the bucket).

        Returns:
        None
        """
        csv_buffer = BytesIO()
        df.to_csv(csv_buffer, index=False)
        s3.put_object(Bucket=bucket_name, Key=key, Body=csv_buffer.getvalue())
        st.write("Changes saved successfully!")