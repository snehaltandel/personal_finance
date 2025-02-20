import os
import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
from datetime import datetime
import boto3
from io import BytesIO
import json
from components.sidebar import Filter

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
    def __init__(self, filtered_df, df):
        """
        Initializes the TransactionEditor class.
        Raises:
            s3.exceptions.NoSuchKey: If neither the edited nor the consolidated file exists in S3.
        """
        self.filtered_df = filtered_df
        self.df = df
        
        # self.consolidated_file_key = CONSOLIDATED_FILE_KEY
        # self.edited_file_key = ALL_ACCOUNTS_EDITED_FILE_PATH
        # self.backup_dir_key = BACKUP_DIR_KEY

        # try:
        #     edited_obj = s3.get_object(Bucket=bucket_name, Key=self.edited_file_key)
        #     self.df = pd.read_csv(BytesIO(edited_obj['Body'].read()))
        #     self.df["Transaction_Date"] = pd.to_datetime(self.df["Transaction_Date"], format='mixed').dt.date

        #     self.filtered_df, self.df = Filter(self.df).filter_data()

        # except s3.exceptions.NoSuchKey:
        #     try:
        #         consolidated_obj = s3.get_object(Bucket=bucket_name, Key=self.consolidated_file_key)
        #         self.df = pd.read_csv(BytesIO(consolidated_obj['Body'].read()))
        #         self.df['Last_Updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        #         self.save_to_s3(self.df, self.edited_file_key)
        #     except s3.exceptions.NoSuchKey:
        #         self.df = pd.DataFrame()

    def main(self):
        """
        Displays a form for editing transactions and provides options to save changes, refresh, or backup the data.
        """

        # Define the order of columns to display
        column_order = ["Transaction_Date", "Description", "Category", "Amount", "Account_Type", "Last_Updated"]

        Header, Sorting = st.columns(2)
        with Header:
            st.write("Edit Transactions:")
        with Sorting:
            # Sort options in a compact layout
            sort_column, sort_order = st.columns(2)
            with sort_column:
                sort_column = st.selectbox(
                    "Sort by",
                    options=column_order,
                    index=0,
                    key="sort_column"
                )
            with sort_order:
                sort_order = st.radio(
                    "Order",
                    options=["Ascending", "Descending"],
                    index=1,  # Set default to Descending
                    key="sort_order"
                )
            ascending = sort_order == "Ascending"
            self.df = self.df.sort_values(by=sort_column, ascending=ascending)
        

        # Ensure the DataFrame has the required columns
        for col in column_order:
            if col not in self.df.columns:
                self.df[col] = None

        filter_data = self.filtered_df
        # Display the DataFrame with the specified column order
        edited_df = st.data_editor(
            filter_data[column_order],
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
            hide_index=False)

        # Merge edited_df back into self.df
        self.df = self.df.set_index(['Transaction_Date', 'Description', 'Amount', 'Account_Type'])
        edited_df = edited_df.set_index(['Transaction_Date', 'Description', 'Amount', 'Account_Type'])
        combined_df = self.df.join(edited_df['Category'], rsuffix='_edited', how='left')
        combined_df['Category'] = combined_df['Category_edited'].combine_first(combined_df['Category'])
        combined_df.drop(columns=['Category_edited'], inplace=True)
        self.df = combined_df.reset_index()
        # st.dataframe(self.df)

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("Save Changes"):
                self.save_to_s3(self.df, self.edited_file_key)

        # with col2:
        #     if st.button("Refresh"):
        #         self.refresh_transactions()

        with col3:
            if st.button("Backup"):
                self.backup_file()

    def refresh_transactions(self):
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
                self.df[['Transaction_Date', 'Amount', 'Account_Type', 'Description']].apply(tuple, 1))]
            if not new_transactions.empty:
                
                new_transactions['Last_Updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.info("New Transactions:")
                st.dataframe(new_transactions)
                updated_df = pd.concat([self.df, new_transactions]).reset_index(drop=True)
                self.save_to_s3(updated_df, self.edited_file_key)
                st.write("Transactions refreshed successfully!")
            else:
                st.write("No new transactions to add.")
        except s3.exceptions.NoSuchKey:
            st.write("Edited file does not exist.")

    def backup_file(self):
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
            self.save_to_s3(self.df, backup_filename_key)
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