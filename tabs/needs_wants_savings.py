import streamlit as st
import pandas as pd
import boto3
import json
import os
from dotenv import load_dotenv
load_dotenv()

config = json.load(open("assets/config.json"))

s3 = boto3.client(
    's3',
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"]
)
bucket_name = config["S3_BUCKET_NAME"]
budget_file_key = config["budget_file_key"]
NEEDS_WANTS_SAVINGS_PATH = config["NEEDS_WANTS_SAVINGS_PATH"]


class NeedsWantsSavings:
    def __init__(self, df):
        self.df = df
        self.bucket_name = bucket_name
        self.needs_wants_savings_path = NEEDS_WANTS_SAVINGS_PATH
        self.s3 = s3

    def load_data(self):
        try:
            obj = self.s3.get_object(Bucket=self.bucket_name, Key=self.needs_wants_savings_path)
            needs_wants_savings_df = pd.read_csv(obj['Body'])
            st.info("Loaded existing Needs, Wants, and Savings data.")
        except self.s3.exceptions.NoSuchKey:
            categories = sorted(self.df["Category"].unique())
            needs_wants_savings_df = pd.DataFrame({
                'Category': categories,
                'Type': [''] * len(categories)
            })
            st.warning("No existing Needs, Wants, and Savings data found. Created a new dataframe.")
        return needs_wants_savings_df

    def display_editor(self, needs_wants_savings_df):
        type_options = ['Need', 'Want', 'Saving']
        edited_needs_wants_savings_df = st.data_editor(
            needs_wants_savings_df,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                'Type': st.column_config.SelectboxColumn(
                    "Type",
                    help="Select a type",
                    options=type_options,
                    required=True
                )
            }
        )
        return edited_needs_wants_savings_df

    def save_data(self, edited_needs_wants_savings_df):
        if st.button("Save"):
            with st.spinner("Saving..."):
                csv_buffer = edited_needs_wants_savings_df.to_csv(index=False)
                self.s3.put_object(Bucket=self.bucket_name, Key=self.needs_wants_savings_path, Body=csv_buffer)
            st.success(f"Needs, Wants, and Savings saved to S3 bucket '{self.bucket_name}' with key {self.needs_wants_savings_path}")

    def main(self):
        st.subheader("Set Needs, Wants, and Savings")
        needs_wants_savings_df = self.load_data()
        edited_needs_wants_savings_df = self.display_editor(needs_wants_savings_df)
        self.save_data(edited_needs_wants_savings_df)