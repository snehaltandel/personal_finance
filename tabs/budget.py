import boto3
import json
import csv
from io import StringIO
import pandas as pd
import plotly.express as px
import streamlit as st

config = json.load(open("assets/config.json"))

s3 = boto3.client('s3')
bucket_name = config["S3_BUCKET_NAME"]
budget_file_key = config["budget_file_key"]
BUDGET_START_DATE = config["BUDGET_START_DATE"]

class BudgetVariance:
    def __init__(self, expenses, budget_amount):
        """
        Initialize the Budget class with expenses and budget amount.
        """
        self.budget_amount = budget_amount
        self.expenses = expenses
        self.expenses = self.expenses[(~self.expenses["Category"].isin([config["BUDGET_EXCLUDED_CATEGORIES"]]))]  # Filter out credit card payments and Investments
        self.expenses['Transaction_Date'] = pd.to_datetime(self.expenses['Transaction_Date'])
        self.expenses['Month'] = self.expenses['Transaction_Date'].dt.to_period('M')
    
    def calculate_variance(self):
        """
        Calculate the variance between actual expenses and the budgeted amount for each month.
        """
        if self.expenses.empty:
            return []
        
        expenses = self.expenses.groupby('Month')['Amount'].sum().abs()
        expenses = expenses.to_dict()
        results = []
        for month, expense in expenses.items():
            if expense > self.budget_amount:
                over_budget = expense - self.budget_amount
                under_budget = 0
            else:
                over_budget = 0
                under_budget = self.budget_amount - expense
            results.append({
                'Month': month,
                'Under Budget': under_budget,
                'Over Budget': over_budget
            })
        return results

    def get_budget_variance(self):
        """
        Calculate and return the budget variance as a DataFrame.
        """
        variance_data = self.calculate_variance()
        if not variance_data:
            return pd.DataFrame(columns=['Month', 'Under_Budget', 'Over_Budget']).set_index('Month')
        variance_df = pd.DataFrame(variance_data)
        variance_df.set_index('Month', inplace=True)
        variance_df.index = variance_df.index.astype(str)
        variance_df.index.name = 'Month'
        variance_df.columns = ['Under_Budget', 'Over_Budget']
        return variance_df
    
    def get_monthly_expense_summary(self):
        """
        Generate a summary of monthly expenses.
        """
        if self.expenses.empty:
            return pd.DataFrame(columns=['Month', 'Category', 'Amount'])
        monthly_expenses = self.expenses.groupby(['Month', 'Category'])['Amount'].sum().abs().reset_index()
        return monthly_expenses
    
    def get_monthly_expense_average(self):
        """
        Calculate the average monthly expenses per category.
        """
        if self.expenses.empty:
            return pd.DataFrame(columns=['Category', 'Amount'])
        # monthly_expenses = self.expenses.groupby(['Month', 'Category'])['Amount'].sum().abs().reset_index()
        num_months = self.expenses['Month'].nunique()
        average_expenses = self.expenses.groupby(['Category'])['Amount'].sum().abs().reset_index()
        average_expenses['Amount'] = (average_expenses['Amount'] / num_months).round()
        average_expenses = average_expenses.sort_values(by='Amount', ascending=False).reset_index(drop=True)
        print(average_expenses)
        return average_expenses
    
    def total_of_average_expenese(self):
        """

        Returns:
            float: The total amount of average expenses.
        """
        if self.expenses.empty:
            return 0
        monthly_expenses = self.expenses.groupby(['Month', 'Category'])['Amount'].sum().abs().reset_index()
        total_amount = monthly_expenses['Amount'].sum()
        return total_amount


class SetBudget:
    def __init__(self, df):
        """
        Initialize the SetBudget class with a budget amount and other necessary parameters.
        """
        self.df = df

    def main(self):
        """
        Display the budget setting interface using Streamlit.
        """
        st.subheader("Set Budget")
        
        # Get unique categories sorted in ascending order
        categories = sorted(self.df["Category"].unique())

        # Get the next 36 months
        start_date = pd.Timestamp(BUDGET_START_DATE)
        next_36_months = pd.date_range(start=start_date, periods=36, freq='M')

        # Try to read the budget file from S3
        try:
            obj = s3.get_object(Bucket=bucket_name, Key=budget_file_key)
            budget_df = pd.read_csv(obj['Body'])
            
            # Sort the dataframe by Month column in descending order
            budget_df = budget_df.sort_values(by=['Month', 'Category'], ascending=[True, True]).reset_index(drop=True)
            st.write("Loaded existing budget data.")
        except s3.exceptions.NoSuchKey:
            # If the file does not exist, create a new dataframe
            budget_df = pd.DataFrame(index=next_36_months, columns=categories)
            budget_df = budget_df.reset_index().melt(id_vars=['index'], var_name='Category', value_name='Budgeted Amount')
            budget_df.rename(columns={'index': 'Month'}, inplace=True)
            # Format the Month column to show only year and month
            budget_df['Month'] = budget_df['Month'].dt.strftime('%Y-%m')
            
            # Sort the dataframe by Month column in ascending order
            budget_df = budget_df.sort_values(by=['Month', 'Category'], ascending=[True, True]).reset_index(drop=True)
            st.write("No existing budget data found. Created a new budget dataframe.")

        # Display the editable dataframe using st.data_editor or st.experimental_data_editor based on Streamlit version
        try:
            edited_budget_df = st.data_editor(budget_df, num_rows="dynamic", use_container_width=True)
        except AttributeError:
            edited_budget_df = st.experimental_data_editor(budget_df, num_rows="dynamic", use_container_width=True)

        # Save button
        if st.button("Save Budget"):
            st.write("Budget amounts submitted successfully!")
            
            # Save the dataframe to a CSV file
            csv_buffer = StringIO()
            edited_budget_df.to_csv(csv_buffer, index=False)
            
            s3.put_object(Bucket=bucket_name, Key=budget_file_key, Body=csv_buffer.getvalue())
            
            st.write(f"Budget amounts saved to S3 bucket '{bucket_name}' with key '{budget_file_key}'")
        
        st.subheader("Monthly Budget Total")
        # Calculate and display the monthly budget total
        monthly_budget_total = edited_budget_df.groupby('Month')['Budgeted Amount'].sum().reset_index()
        st.dataframe(monthly_budget_total, use_container_width=True)

        st.subheader("Annual Budget Total")
        # Calculate and display the annual budget total
        annual_budget_total = edited_budget_df.groupby(edited_budget_df['Month'].str[:4])['Budgeted Amount'].sum().reset_index()
        annual_budget_total.rename(columns={'Month': 'Year'}, inplace=True)
        st.dataframe(annual_budget_total, use_container_width=True)