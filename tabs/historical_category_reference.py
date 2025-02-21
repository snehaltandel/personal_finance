import boto3
import pandas as pd
from io import StringIO
import botocore
import json
import os
from dotenv import load_dotenv
load_dotenv()

class HistoricalCategoryReference:
    def __init__(self):
        """
        Initializes the class by loading configuration, setting up S3 client, and reading necessary files.
        """
        config = json.load(open("assets/config.json"))
        self.s3_bucket = config["S3_BUCKET_NAME"]
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"]
        )
        self.category_reference_file = config["CATEGORY_REFERENCE_FILE_PATH"]
        self.all_accounts_file = config["ALL_ACCOUNTS_FILE_PATH"]
        self.all_accounts_edited_file = config["ALL_ACCOUNTS_EDITED_FILE_PATH"]
        self.REPLACEMENT_DICT = config["REPLACEMENT_DICT"]
        self.all_accounts_df = self.read_csv_from_s3(self.all_accounts_file)
        self.all_accounts_edited_df = self.read_csv_from_s3(self.all_accounts_edited_file)
        self.df = None
        categories_file_path = config["CATEGORIES_FILE_PATH"]
        categories_df = pd.read_excel(categories_file_path)
        self.predefined_categories = sorted(categories_df['Custom Categories'].unique().tolist())

    def read_csv_from_s3(self, s3_key):
        """
        Reads a CSV file from an S3 bucket and returns it as a pandas DataFrame.

        Parameters:
        s3_key (str): The key (path) of the CSV file in the S3 bucket.

        Returns:
        pd.DataFrame: A DataFrame containing the data from the CSV file.
                  If the specified key does not exist, returns an empty DataFrame.

        Raises:
        botocore.exceptions.ClientError: If there is an error accessing the S3 bucket or reading the object.
        """
        try:
            obj = self.s3_client.get_object(Bucket=self.s3_bucket, Key=s3_key)
            return pd.read_csv(StringIO(obj['Body'].read().decode('utf-8')))
        except self.s3_client.exceptions.NoSuchKey:
            print(f"Warning: The specified key {s3_key} does not exist.")
            return pd.DataFrame()

    def write_csv_to_s3(self, df, s3_key):
        """
        Write a DataFrame to a CSV file and upload it to an S3 bucket.

        Parameters:
        df (pandas.DataFrame): The DataFrame to be written to CSV.
        s3_key (str): The S3 key (path) where the CSV file will be stored.

        Returns:
        None
        """
        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False)
        self.s3_client.put_object(Bucket=self.s3_bucket, Key=s3_key, Body=csv_buffer.getvalue())

    def load_data(self):
        """
        Loads data from a CSV file stored in an S3 bucket and processes it.

        Attributes:
        -----------
        df : pandas.DataFrame
            A DataFrame containing the loaded and processed data.
        """
        self.df = self.read_csv_from_s3(self.category_reference_file)
        self.df = self.df[['Transaction_Date', 'Description', 'Amount', 'Account_Type', 'Category']]

    def replace_account_types(self):
        """
        Replaces account type values in the DataFrame with more readable names.

        Parameters:
        None

        Returns:
        None
        """
        
        self.df['Account_Type'] = self.df['Account_Type'].replace(self.REPLACEMENT_DICT)

    def adjust_amounts(self):
        """

        Returns:
            None
        """
        self.df['Amount'] = self.df['Amount'] * -1
        self.df['Amount'] = self.df['Amount'].round(2)

    def similar_descriptions(self):
        """
        This method finds and assigns the most similar category to descriptions in the `all_accounts_df` DataFrame 
        that have null or empty categories, or categories not in the predefined list.
        
        Returns:
            None: The method updates the `Category` column of `all_accounts_df` in place.
        """
        # Implement your logic for similar descriptions
        ref_df = self.df[~self.df["Category"].isnull()].drop_duplicates()
        ref_df = ref_df[["Description","Category"]].drop_duplicates(subset=["Description"])
        ref_df = ref_df.sort_values(by=["Description"], ascending=True).reset_index(drop=True)

        # Function to get similarlity score
        def get_similarity(text1, text2):
            # Split the texts into words
            words1 = set(text1.split())
            words2 = set(text2.split())
            
            # Calculate the intersection and union of the two sets of words
            intersection = words1.intersection(words2)
            union = words1.union(words2) # Calculate the union of the two sets of words
            
            # Calculate the Jaccard similarity score
            similarity_score = len(intersection) / len(union)
            
            return similarity_score

        # Function to find the best match for a description using similarity score
        def get_best_match(description, ref_df):
            ref_df['similarity'] = ref_df['Description'].apply(lambda x: get_similarity(description, x))
            best_match = ref_df.loc[ref_df['similarity'].idxmax()] # Get the row with the highest similarity score
            return best_match['Category']

        # Apply the best match function to the uncat_df
        self.all_accounts_df.loc[self.all_accounts_df['Category'].isnull() | (self.all_accounts_df['Category'] == '') | (~self.all_accounts_df['Category'].isin(self.predefined_categories)), 'Category'] = self.all_accounts_df['Description'].apply(lambda x: get_best_match(x, ref_df))

    def merge_data(self):
        """
        Merges and updates the account data with historical category references.
        Returns:
            None
        """

        # Apply Category from Reference data
        self.all_accounts_df = self.all_accounts_df.merge(
            self.df[['Transaction_Date', 'Account_Type', 'Description', 'Amount', 'Category']],
            on=['Transaction_Date', 'Account_Type', 'Description', 'Amount'],
            how='left',
            suffixes=('', '_df')
        )
        self.all_accounts_df['Category'] = self.all_accounts_df['Category_df'].combine_first(self.all_accounts_df['Category'])
        
        self.all_accounts_df = self.all_accounts_df.drop(columns=['Category_df'])

        # Apply Category from Edited data
        if not self.all_accounts_edited_df.empty:
            
            # Apply Description level category reference
            df_ref = self.all_accounts_edited_df[['Description', 'Category']].drop_duplicates(subset=['Description'])
            self.all_accounts_df = self.all_accounts_df.merge(
                df_ref,
                on=['Description'],
                how='left',
                suffixes=('', '_df')
            )
            self.all_accounts_df['Category'] = self.all_accounts_df['Category_df'].combine_first(self.all_accounts_df['Category'])
            
            self.all_accounts_df = self.all_accounts_df.drop(columns=['Category_df'])

            # Apply Transaction level category reference
            df_ref = self.all_accounts_edited_df[['Transaction_Date', 'Account_Type', 'Description', 'Amount','Category']].drop_duplicates(subset=['Transaction_Date', 'Account_Type', 'Description', 'Amount'])
            self.all_accounts_df = self.all_accounts_df.merge(
                df_ref,
                on=['Transaction_Date', 'Account_Type', 'Description', 'Amount'],
                how='left',
                suffixes=('', '_df')
            )
            self.all_accounts_df['Category'] = self.all_accounts_df['Category_df'].combine_first(self.all_accounts_df['Category'])
            
            self.all_accounts_df = self.all_accounts_df.drop(columns=['Category_df'])

        if (self.all_accounts_df['Category'].isna().any() | (~self.all_accounts_df['Category'].isin(self.predefined_categories)).any()):  # Check for NaN values in 'Category'

            df_ref = self.all_accounts_df[['Account_Type', 'Description', 'Category']].drop_duplicates(subset=['Account_Type', 'Description'])
            # Drop records where Category is null or empty
            df_ref = df_ref[df_ref['Category'].notna() & (df_ref['Category'] != '')]

            self.all_accounts_df = self.all_accounts_df.merge(
                df_ref,
                on=['Account_Type', 'Description'],
                how='left',
                suffixes=('', '_df')
            )
            # Update Category based on Category_Ref
            self.all_accounts_df['Category'] = self.all_accounts_df['Category_df'].combine_first(self.all_accounts_df['Category'])
            
            # Drop the Category_Ref column
            self.all_accounts_df = self.all_accounts_df.drop(columns=['Category_df'])

            # Get Similar Categories
            self.similar_descriptions()
   
            # Drop duplicates
            self.all_accounts_df = self.all_accounts_df.sort_values(by=['Transaction_Date', 'Account_Type', 'Description', 'Amount'], ascending=[False, True, True, True]).reset_index(drop=True)


    def main(self):
        """
        Main function to load and merge financial data.

        This function performs the following steps:
        1. Loads the data by calling `self.load_data()`.
        2. Merges the data by calling `self.merge_data()`.
        3. Returns the merged data as a DataFrame.

        Note: Some steps like replacing account types, adjusting amounts, and writing the CSV to S3 are currently commented out.

        Returns:
            DataFrame: The merged financial data.
        """
        self.load_data()
        self.merge_data()
        return self.all_accounts_df