import boto3
import json
import csv
from io import StringIO
import pandas as pd
import plotly.express as px

class BudgetVariance:
    def __init__(self, expenses, budget_amount):
        """
        Initialize the Budget class with expenses and budget amount.
        """
        config = json.load(open("assets/config.json"))
        self.budget_amount = budget_amount
        self.expenses = expenses
        self.expenses = self.expenses[(self.expenses["Amount"] < 0) & (~self.expenses["Category"].isin([config["BUDGET_EXCLUDED_CATEGORIES"]]))]  # Filter out credit card payments and Investments
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
        monthly_expenses = self.expenses.groupby(['Month', 'Category'])['Amount'].sum().abs().reset_index()
        num_months = self.expenses['Month'].nunique()
        monthly_expenses = monthly_expenses.groupby(['Category'])['Amount'].sum().abs().reset_index()
        monthly_expenses['Amount'] = (monthly_expenses['Amount'] / num_months).round()
        monthly_expenses = monthly_expenses.sort_values(by='Amount', ascending=False).reset_index(drop=True)
        return monthly_expenses
    
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
