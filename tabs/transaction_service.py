import json
import os
from io import StringIO

import boto3
from botocore.exceptions import ClientError
import pandas as pd
from dotenv import load_dotenv

from tabs.amount_utils import normalize_amount_series

load_dotenv()

config = json.load(open("assets/config.json"))

s3 = boto3.client(
    "s3",
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
)

bucket_name = config["S3_BUCKET_NAME"]
account_types = config["ACCOUNT_TYPES"]
output_headers = config["OUTPUT_HEADERS"]
amount_negative_accounts = config["AMOUNT_NEGATIVE_ACCOUNTS"]
all_accounts_file_path = config["ALL_ACCOUNTS_FILE_PATH"]
all_accounts_edited_file_path = config["ALL_ACCOUNTS_EDITED_FILE_PATH"]

SOURCE_FILE_COLUMN = "Source_File"
TRANSACTION_MATCH_COLUMNS = [
    "Transaction_Date",
    "Account_Type",
    "Description",
    "Amount",
]
SOURCE_AWARE_MATCH_COLUMNS = [SOURCE_FILE_COLUMN] + TRANSACTION_MATCH_COLUMNS


class TransactionService:
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir

    def list_source_files(self):
        file_list = []
        response = s3.list_objects_v2(Bucket=bucket_name, Prefix=self.data_dir)
        for obj in response.get("Contents", []):
            if obj["Key"].endswith(".csv"):
                account_type = obj["Key"].split("/")[-2]
                if account_type in account_types:
                    file_list.append(obj["Key"])
        return sorted(file_list)

    def read_csv_from_s3(self, file_path, optional=False):
        try:
            obj = s3.get_object(Bucket=bucket_name, Key=file_path)
            return pd.read_csv(StringIO(obj["Body"].read().decode("utf-8")))
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")
            if optional and error_code in {"NoSuchKey", "404"}:
                return pd.DataFrame()
            raise

    def save_csv_to_s3(self, df, file_path):
        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False)
        s3.put_object(Bucket=bucket_name, Key=file_path, Body=csv_buffer.getvalue())

    def delete_source_file(self, file_path):
        s3.delete_object(Bucket=bucket_name, Key=file_path)

    def _empty_transactions_df(self):
        return pd.DataFrame(columns=output_headers + [SOURCE_FILE_COLUMN])

    def _prepare_dataframe(self, df, file_path):
        account_type = file_path.split("/")[-2]
        prepared_df = df.copy()
        prepared_df["Account_Type"] = account_type
        prepared_df[SOURCE_FILE_COLUMN] = file_path

        prepared_df["Amount"] = normalize_amount_series(prepared_df["Amount"])

        if account_type in amount_negative_accounts:
            prepared_df["Amount"] = prepared_df["Amount"] * -1

        prepared_df["Amount"] = prepared_df["Amount"].round(2)

        for header in output_headers + [SOURCE_FILE_COLUMN]:
            if header not in prepared_df.columns:
                prepared_df[header] = pd.NA

        prepared_df["Transaction_Date"] = pd.to_datetime(
            prepared_df["Transaction_Date"], errors="coerce"
        ).dt.date
        prepared_df["Post_Date"] = pd.to_datetime(
            prepared_df["Post_Date"], errors="coerce"
        ).dt.date

        ordered_columns = output_headers + [SOURCE_FILE_COLUMN]
        remaining_columns = [
            column for column in prepared_df.columns if column not in ordered_columns
        ]
        return prepared_df[ordered_columns + remaining_columns]

    def consolidate_transactions(self, selected_files):
        if not selected_files:
            return self._empty_transactions_df()

        all_data = pd.DataFrame()
        for file_path in selected_files:
            df = self.read_csv_from_s3(file_path)
            prepared_df = self._prepare_dataframe(df, file_path)
            all_data = pd.concat([all_data, prepared_df], ignore_index=True)

        if all_data.empty:
            return self._empty_transactions_df()

        return all_data.sort_values(
            by=["Transaction_Date", "Description", "Amount"],
            ascending=[False, True, True],
        ).reset_index(drop=True)

    def _normalize_match_columns(self, df):
        normalized_df = df.copy()
        if normalized_df.empty:
            return normalized_df

        if "Transaction_Date" in normalized_df.columns:
            normalized_df["Transaction_Date"] = pd.to_datetime(
                normalized_df["Transaction_Date"], errors="coerce"
            ).dt.date

        if "Amount" in normalized_df.columns:
            normalized_df["Amount"] = normalize_amount_series(
                normalized_df["Amount"]
            ).round(2)

        return normalized_df

    def _build_preserved_edits(self, edited_df):
        if edited_df.empty or "Category" not in edited_df.columns:
            return pd.DataFrame()

        normalized_edited_df = self._normalize_match_columns(edited_df)

        preferred_match_columns = (
            SOURCE_AWARE_MATCH_COLUMNS
            if SOURCE_FILE_COLUMN in normalized_edited_df.columns
            else TRANSACTION_MATCH_COLUMNS
        )
        available_match_columns = [
            column
            for column in preferred_match_columns
            if column in normalized_edited_df.columns
        ]

        if not available_match_columns:
            return pd.DataFrame()

        return normalized_edited_df[
            available_match_columns + ["Category"]
        ].drop_duplicates(subset=available_match_columns, keep="last")

    def reapply_edited_categories(self, consolidated_df, edited_df):
        if consolidated_df.empty:
            return self._empty_transactions_df()

        rebuilt_df = self._normalize_match_columns(consolidated_df)
        preserved_edits = self._build_preserved_edits(edited_df)

        if preserved_edits.empty:
            return rebuilt_df

        join_columns = [
            column
            for column in preserved_edits.columns
            if column != "Category" and column in rebuilt_df.columns
        ]
        if not join_columns:
            return rebuilt_df

        rebuilt_df = rebuilt_df.merge(
            preserved_edits,
            on=join_columns,
            how="left",
            suffixes=("", "_edited"),
        )
        rebuilt_df["Category"] = rebuilt_df["Category_edited"].combine_first(
            rebuilt_df.get("Category")
        )
        return rebuilt_df.drop(columns=["Category_edited"])

    def rebuild_all_datasets(self):
        source_files = self.list_source_files()
        consolidated_df = self.consolidate_transactions(source_files)
        existing_edited_df = self.read_csv_from_s3(
            all_accounts_edited_file_path, optional=True
        )
        edited_df = self.reapply_edited_categories(consolidated_df, existing_edited_df)

        self.save_csv_to_s3(consolidated_df, all_accounts_file_path)
        self.save_csv_to_s3(edited_df, all_accounts_edited_file_path)

        return consolidated_df, edited_df
