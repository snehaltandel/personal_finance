import streamlit as st
import pandas as pd
import plotly.express as px
from tabs.expenses import Expenses
from tabs.trends import FinanceTrends
from tabs.budget import BudgetVariance
import boto3
import json
import plotly.express as px
from tabs.summary import Summary
from tabs.budget import SetBudget
from tabs.needs_wants_savings import NeedsWantsSavings
import os
from dotenv import load_dotenv
load_dotenv()

config = json.load(open("assets/config.json"))

# Set page configuration to wide layout
st.set_page_config(layout="wide")

s3 = boto3.client(
    's3',
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"]
)
bucket_name = config["S3_BUCKET_NAME"]
budget_file_key = config["budget_file_key"]
BUDGET_START_DATE = config["BUDGET_START_DATE"]
NEEDS = config["NEEDS"]
WANTS = config["WANTS"]
SAVINGS = config["SAVINGS"]
NEEDS_WANTS_SAVINGS_PATH = config["NEEDS_WANTS_SAVINGS_PATH"]

class Dashboard:
    def __init__(self, filtered_df, df):
        """
        Initialize the Dashboard class with a dataframe.
        
        Parameters:
        df (pd.DataFrame): The dataframe containing financial data.
        """
        self.df = df
        self.filtered_df = filtered_df


    def main(self):
        """
        Main function to render the dashboard.
        """
        # Filter the dataframe based on user inputs
        filtered_df = self.filtered_df

        # Create sub-tabs within the Dashboard tab
        Expense_Tab, Budget_Tab, SetBudget_Tab, Summary_Tab, Trends_Tab, NWS_Tab = st.tabs(["Expense Analysis", "Budget", "Set Budget", "Summary", "Trends", "Set Needs Wants Savings"])
        
        with Expense_Tab:
            # Expense Analysis tab
            exp = Expenses(filtered_df)
            exp.main()

        with Budget_Tab:
            # Budget tab
            st.subheader("Budget Variance")
            
            # Input for budget amount
            budget_amount = st.number_input("Enter your budget amount", min_value=0.0, step=50.0, value=5500.0)
            budget = BudgetVariance(filtered_df, budget_amount)  # Initialize the BudgetVariance class
            
            # Display budget variance
            if not filtered_df.empty:
                variance_df = budget.get_budget_variance()
                st.dataframe(variance_df, use_container_width=True)
            else:
                st.warning("No data available for the selected filters.")
            
            st.subheader("Monthly Expense Summary")
            # Display monthly expense summary
            if not filtered_df.empty:
                get_monthly_expense_summary = budget.get_monthly_expense_summary()
                print(get_monthly_expense_summary)
            
                # Filter the dataframe to include only 2024 transactions
                df = self.df.copy(deep=False)
                df["Transaction_Date"] = pd.to_datetime(df["Transaction_Date"])
                df = df[df["Transaction_Date"].dt.year == 2024]
                if not df.empty:
                    category_budget = BudgetVariance(df, budget_amount)
                    monthly_average = category_budget.get_monthly_expense_average()
                    
                    # Merge the average expenses into the monthly expense summary
                    merged_df = get_monthly_expense_summary.merge(
                    monthly_average, 
                    on='Category', 
                    how='left', 
                    suffixes=('', '_Average')
                    )
                    
                    # Rename the columns for clarity
                    merged_df.rename(columns={'Amount_Average': 'Average_Amount'}, inplace=True)

                    # Calculate the variance between actual amount and average amount
                    merged_df['Variance'] = merged_df['Amount'] - merged_df['Average_Amount']

                    obj = s3.get_object(Bucket=bucket_name, Key=budget_file_key)
                    budget_df = pd.read_csv(obj['Body'])

                    # Filter the budget dataframe to include only the relevant categories and months
                    budget_df["Month"] = pd.to_datetime(budget_df["Month"])

                    # Group by category and sum the budgeted amounts
                    budget_summary = budget_df.groupby("Category")["Budgeted Amount"].sum().reset_index()

                    # Merge the budgeted amounts into the merged dataframe
                    merged_df = merged_df.merge(
                    budget_summary, 
                    on="Category", 
                    how="left", 
                    suffixes=("", "_Budgeted")
                    )

                    # Rename the columns for clarity
                    merged_df.rename(columns={"Budgeted Amount": "Budgeted_Amount"}, inplace=True)

                    # Calculate the variance between actual amount and budgeted amount
                    merged_df["Budget_Variance"] = merged_df["Amount"] - merged_df["Budgeted_Amount"]
                    
                    st.dataframe(merged_df, use_container_width=True)

                    st.subheader("Tree Map of Average Expenses By Category")

                    # Information text about the chart
                    st.info("NOTE: Credit Card Payment and Investments are excluded from the calculation.")

                    # Create a tree map for average expenses by category with labels
                    fig = px.treemap(
                    monthly_average, 
                    path=['Category'], 
                    values='Amount', 
                    labels={'Amount': 'Average Expense'}
                    )
                    fig.update_traces(textinfo='label+value', valuessrc='$,.2f')
                    st.plotly_chart(fig, use_container_width=True)

                    st.subheader("Total of Average Expenses")
                    # Display total of average expenses
                    total_average_expenses = budget.total_of_average_expenese()
                    st.write(f"Total of Average Expenses: ${total_average_expenses:.2f}")

                    st.subheader("Monthly Expense Trend by Category")
                    # Plot monthly expense trend by category
                    get_monthly_expense_summary["Month"] = get_monthly_expense_summary["Month"].dt.to_timestamp()

                    # Plotly line plot for monthly expenses by category
                    fig = px.line(
                    get_monthly_expense_summary, 
                    x='Month', 
                    y='Amount', 
                    color='Category', 
                    title='Monthly Expense Trend by Category'
                    )

                    # Display the chart
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("No data available for the year 2024.")
            else:
                st.warning("No data available for the selected filters.")

        with SetBudget_Tab:
            SetBudget(self.df).main()

        with Summary_Tab:
            Summary(self.df).main()

        with Trends_Tab:
            # Trends tab
            trend = FinanceTrends(filtered_df)
            trend.plot_trends()

        with NWS_Tab:
            NeedsWantsSavings(self.df).main()