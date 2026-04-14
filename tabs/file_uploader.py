import streamlit as st
import pandas as pd
import os
from datetime import datetime
import re
import json
import boto3
from io import BytesIO
from dotenv import load_dotenv
from tabs.transaction_service import TransactionService
load_dotenv()

config = json.load(open("assets/config.json"))

s3_client = boto3.client(
    's3',
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"]
)
bucket_name = config["S3_BUCKET_NAME"]

class FileUploader:
    def __init__(self):
        self.uploaded_files = []
        self.account_types = config["ACCOUNT_TYPES"]
        self.df = pd.DataFrame(columns=["Account Type", "New File Name", "Min Transaction Date", "Max Transaction Date", "Number of Transactions", "File Upload Date"])
        self.transaction_service = TransactionService()

    def _normalize_column_name(self, column_name):
        normalized = re.sub(r"[^A-Z0-9]+", "_", str(column_name).strip().upper())
        return normalized.strip("_")

    def _prepare_wells_fargo_dataframe(self, df):
        expected_headers = config["HEADERS"]["WellsFargo_Checking"]
        normalized_columns = {
            self._normalize_column_name(column): column for column in df.columns
        }

        new_structure_mapping = {
            "DATE": "Transaction_Date",
            "DESCRIPTION": "Description",
            "AMOUNT": "Amount",
            "CHECK": "Comment1",
            "CHECK_NUMBER": "Comment1",
            "STATUS": "Comment2",
        }

        required_new_columns = {"DATE", "DESCRIPTION", "AMOUNT"}
        if required_new_columns.issubset(normalized_columns):
            prepared_df = df.rename(
                columns={
                    normalized_columns[source_column]: target_column
                    for source_column, target_column in new_structure_mapping.items()
                    if source_column in normalized_columns
                }
            ).copy()

            for header in expected_headers:
                if header not in prepared_df.columns:
                    prepared_df[header] = pd.NA

            return prepared_df[expected_headers]

        if len(df.columns) != len(expected_headers):
            raise ValueError(
                "Unsupported Wells Fargo file structure. Expected either the legacy format "
                "or the new DATE / DESCRIPTION / AMOUNT / CHECK # / STATUS format."
            )

        prepared_df = df.copy()
        prepared_df.columns = expected_headers
        return prepared_df

    def _prepare_uploaded_dataframe(self, df, account_type):
        if account_type == "WellsFargo_Checking":
            return self._prepare_wells_fargo_dataframe(df)

        headers = config["HEADERS"][account_type]
        if len(df.columns) != len(headers):
            raise ValueError(
                f"Unexpected number of columns for {account_type}. "
                f"Expected {len(headers)} columns but received {len(df.columns)}."
            )

        prepared_df = df.copy()
        prepared_df.columns = headers
        return prepared_df
    
    def view_files(self):
        '''
        Display the list of uploaded files with details
        '''
        data = []
        for account_type in self.account_types:
            prefix = f"data/{account_type}/"
            response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
            if "Contents" not in response:
                continue

            for obj in response["Contents"]:
                file_key = obj["Key"]
                if not file_key.endswith(".csv"):
                    continue

                s3_object = s3_client.get_object(Bucket=bucket_name, Key=file_key)
                try:
                    df = pd.read_csv(BytesIO(s3_object["Body"].read()))
                    if df.empty:
                        continue
                    min_date = pd.to_datetime(df["Transaction_Date"], errors="coerce").dt.date.min()
                    max_date = pd.to_datetime(df["Transaction_Date"], errors="coerce").dt.date.max()
                    num_transactions = len(df)
                    upload_date = s3_object["LastModified"]
                    data.append(
                        {
                            "File": file_key,
                            "Min Date": min_date,
                            "Max Date": max_date,
                            "Transactions": num_transactions,
                            "File Upload Date": upload_date,
                        }
                    )
                except pd.errors.EmptyDataError:
                    st.write(f"Warning: {file_key} is empty and will be skipped.")

        self.df = pd.DataFrame(data)
        if not self.df.empty:
            self.df = self.df.sort_values(by="File Upload Date", ascending=False)
        st.header("Uploaded Files")
        if self.df.empty:
            st.info("No uploaded files found.")
            return

        st.dataframe(self.df, use_container_width=True)

        selected_files = st.multiselect(
            "Select uploaded files to delete",
            options=self.df["File"].tolist(),
            placeholder="Choose one or more files",
        )
        confirm_delete = st.checkbox(
            "Also remove all transactions imported from the selected files",
            value=True,
        )
        if st.button("Delete Selected Files", type="primary", disabled=not selected_files):
            if not confirm_delete:
                st.warning("Confirm transaction removal before deleting the file.")
                return
            self.delete_files(selected_files)

    def delete_files(self, file_keys):
        try:
            for file_key in file_keys:
                self.transaction_service.delete_source_file(file_key)
            consolidated_df, edited_df = self.transaction_service.rebuild_all_datasets()
            st.success(
                f"Deleted {len(file_keys)} file(s). Rebuilt datasets with "
                f"{consolidated_df.shape[0]} consolidated transactions and "
                f"{edited_df.shape[0]} editable transactions."
            )
            rerun = getattr(st, "rerun", None) or getattr(st, "experimental_rerun", None)
            if rerun:
                rerun()
        except Exception as e:
            st.error(f"Error deleting file: {e}")

    # Function to save uploaded file with updated headers
    def save_file(self, df, account_type):            
        try:
            df = self._prepare_uploaded_dataframe(df, account_type)
            st.write(f"Mapped columns: {df.columns.tolist()}")

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
            return new_file_name
        except Exception as e:
            raise RuntimeError(f"Error saving file: {e}") from e

    def upload_file(self):
        account_type = st.selectbox("Select Account Type", self.account_types)
        uploaded_files = st.file_uploader(
            "Upload CSV or Excel files",
            type=["csv", "xlsx"],
            accept_multiple_files=True,
        )
        if uploaded_files:
            preview_frames = []
            parsed_files = []

            for uploaded_file in uploaded_files:
                if uploaded_file.name.endswith(".csv"):
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)

                preview_df = df.copy()
                preview_df.insert(0, "Uploaded_File", uploaded_file.name)
                preview_frames.append(preview_df)
                parsed_files.append((uploaded_file.name, df))

            st.subheader("Preview Files")
            for preview_df in preview_frames:
                st.dataframe(preview_df, use_container_width=True)

            if st.button("Save Files"):
                saved_files = 0
                failed_files = []

                for file_name, df in parsed_files:
                    try:
                        new_file_name = self.save_file(df.copy(), account_type)
                        saved_files += 1
                        st.success(f"{file_name} saved as {new_file_name}")
                    except Exception as exc:
                        failed_files.append(f"{file_name}: {exc}")

                if saved_files:
                    st.success(f"Saved {saved_files} file(s) for {account_type}.")

                for failure in failed_files:
                    st.error(failure)
