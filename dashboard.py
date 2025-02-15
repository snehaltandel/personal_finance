import streamlit as st
import pandas as pd
import plotly.express as px
from expenses import Expenses
from trends import FinanceTrends
from budget import BudgetVariance
import boto3
import json
import plotly.express as px

config = json.load(open("assets/config.json"))

# Set page configuration to wide layout
st.set_page_config(layout="wide")

s3 = boto3.client('s3')
bucket_name = config["S3_BUCKET_NAME"]
budget_file_key = config["budget_file_key"]
BUDGET_START_DATE = config["BUDGET_START_DATE"]
NEEDS = config["NEEDS"]
WANTS = config["WANTS"]
SAVINGS = config["SAVINGS"]
NEEDS_WANTS_SAVINGS_PATH = config["NEEDS_WANTS_SAVINGS_PATH"]

class Dashboard:
    def __init__(self, df):
        """
        Initialize the Dashboard class with a dataframe.
        
        Parameters:
        df (pd.DataFrame): The dataframe containing financial data.
        """
        self.df = df

    def filter_data(self):
        """
        Filter the dataframe based on user inputs from the sidebar.
        
        Returns:
        pd.DataFrame: The filtered dataframe.
        """
        # Filter by Transaction Date
        min_date = self.df["Transaction_Date"].min()
        max_date = self.df["Transaction_Date"].max()
        
        # Sidebar radio button to choose filter option
        filter_option = st.sidebar.radio(
            "Filter by", 
            options=["Custom Date Range", "Previous Month", "Last 3 Months", "Year To Date", "Last Year"], 
            key="filter_option"
        )
        
        if filter_option == "Custom Date Range":
            # Date range filter
            current_year = pd.Timestamp.now().year
            default_end_date = max_date
            default_start_date = pd.Timestamp(f"{default_end_date.year}-{default_end_date.month}-01")
            self.start_date, self.end_date = st.sidebar.date_input(
            "Select Date Range", 
            [default_start_date, default_end_date], 
            min_value=min_date, 
            max_value=max_date
            )
        elif filter_option == "Previous Month":
            # Previous month filter
            self.start_date = (pd.Timestamp.now() - pd.DateOffset(months=1)).replace(day=1).date()
            self.end_date = self.start_date + pd.offsets.MonthEnd(1)

        elif filter_option == "Year To Date":
            # Year to date filter
            self.start_date = pd.to_datetime(f"{pd.Timestamp.now().year}-01-01")
            self.end_date = pd.Timestamp.now().replace(day=1) + pd.offsets.MonthEnd(0)
        elif filter_option == "Last 3 Months":
            # Last 3 months filter
            self.start_date = (pd.Timestamp.now() - pd.DateOffset(months=3)).replace(day=1)
            self.end_date = pd.Timestamp.now().replace(day=1) + pd.offsets.MonthEnd(0)
        elif filter_option == "Last Year":
            # Last year filter
            self.start_date = (pd.Timestamp.now() - pd.DateOffset(years=1)).replace(day=1)
            self.end_date = pd.to_datetime(f"{pd.Timestamp.now().year - 1}-12-31")
     
        # Ensure Category column contains only strings
        self.df["Category"] = self.df["Category"].astype(str)

        # Filter by Category
        self.categories = st.sidebar.multiselect(
            "Select Category", 
            options=sorted(self.df["Category"].unique()), 
            default=sorted(self.df["Category"].unique()), 
            key="category_filter"
        )

        # Ensure Account_Type column contains only strings
        self.df["Account_Type"] = self.df["Account_Type"].astype(str)

        # Filter by Account Type
        self.account_types = st.sidebar.multiselect(
            "Select Account Type", 
            options=sorted(self.df["Account_Type"].unique()), 
            default=sorted(self.df["Account_Type"].unique()), 
            key="account_type_filter"
        )

        # Apply filters to the dataframe
        filtered_df = self.df[
            (self.df["Category"].isin(self.categories)) &
            (self.df["Account_Type"].isin(self.account_types)) &
            (self.df["Transaction_Date"] >= pd.to_datetime(self.start_date)) &
            (self.df["Transaction_Date"] <= pd.to_datetime(self.end_date))
        ]
        return filtered_df

    def main(self):
        """
        Main function to render the dashboard.
        """
        # Sidebar header for filters
        st.sidebar.header("Dashboard Filters")
        
        # Select breakdown type for expense analysis
        breakdown_type = st.sidebar.selectbox("Select Breakdown Type", ["Account Type", "Category"], index=1)

        st.sidebar.header("Filters")

        # Create sub-tabs within the Dashboard tab
        sub_tab1, sub_tab2, sub_tab3, sub_tab4, sub_tab5, sub_tab6 = st.tabs(["Expense Analysis", "Trends", "Budget", "Set Budget", "Summary", "Set Needs Wants Savings"])
        
        # Filter the dataframe based on user inputs
        filtered_df = self.filter_data()
        
        with sub_tab1:
            # Expense Analysis tab
            exp = Expenses(filtered_df)
            exp.main(breakdown_type)

        with sub_tab2:
            # Trends tab
            trend = FinanceTrends(filtered_df)
            trend.plot_trends()

        with sub_tab3:
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
            
                # Filter the dataframe to include only 2024 transactions
                df = self.df[self.df["Transaction_Date"].dt.year == 2024]
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

        with sub_tab4:
            # Set Budget Tab
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
                budget_df = budget_df.sort_values(by=['Month', 'Category'], ascending=[True,True]).reset_index(drop=True)
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
                csv_buffer = edited_budget_df.to_csv(index=False)
                
                s3.put_object(Bucket=bucket_name, Key=budget_file_key, Body=csv_buffer)
                
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

        with sub_tab5:
            # Summary Tab
            st.subheader("Summary")
            st.write("This tab will contain a summary of the financial data.")

            # Filter data to only include transactions from the year 2024
            # df = self.df[self.df['Transaction_Date'].dt.year == 2024]
            summary_df = self.df.copy(deep=False)

            # Re-categorize transactions into Needs, Wants, and Savings
            summary_df['Type'] = summary_df['Category'].apply(
                lambda x: 'Needs' if x in NEEDS else 'Wants' if x in WANTS else 'Savings' if x in SAVINGS else None
            )
            summary_df = summary_df.dropna(subset=['Type'])

            # Step 1: Income vs. Expenses (Pie Chart)
            summary = summary_df.groupby('Type')['Amount'].sum().abs()

            # Filter out negative values
            summary = summary[summary >= 0]

            # Create pie chart using Plotly
            fig = px.pie(summary, values=summary.values, names=summary.index, title='Income vs. Expenses Breakdown', hole=0.4)
            fig.update_traces(textinfo='label+percent', hovertemplate='Type: %{label}<br>Amount: %{value}<extra></extra>')
            st.plotly_chart(fig, use_container_width=True)

            # Step 2: Needs, Wants, and Savings Breakdown (Pie Charts)
            needs_summary = summary_df[summary_df['Type'] == 'Needs'].groupby('Category')['Amount'].sum().abs()
            wants_summary = summary_df[summary_df['Type'] == 'Wants'].groupby('Category')['Amount'].sum().abs()
            savings_summary = summary_df[summary_df['Type'] == 'Savings'].groupby('Category')['Amount'].sum().abs()

            # Create pie charts using Plotly
            fig_needs = px.pie(needs_summary, values=needs_summary.values, names=needs_summary.index, title='Needs Breakdown', hole=0.4)
            fig_wants = px.pie(wants_summary, values=wants_summary.values, names=wants_summary.index, title='Wants Breakdown', hole=0.4)
            fig_savings = px.pie(savings_summary, values=savings_summary.values, names=savings_summary.index, title='Savings Breakdown', hole=0.4)

            # Display the charts in the same row
            col1, col2, col3 = st.columns(3)
            with col1:
                st.plotly_chart(fig_needs, use_container_width=True)
            with col2:
                st.plotly_chart(fig_wants, use_container_width=True)
            with col3:
                st.plotly_chart(fig_savings, use_container_width=True)


        with sub_tab6:
            # Set Needs, Wants, and Savings Tab
            st.subheader("Set Needs, Wants, and Savings")
            
            # Get unique categories sorted in ascending order
            categories = sorted(self.df["Category"].unique())

            try:
                obj = s3.get_object(Bucket=bucket_name, Key=NEEDS_WANTS_SAVINGS_PATH)
                needs_wants_savings_df = pd.read_csv(obj['Body'])
                st.info("Loaded existing Needs, Wants, and Savings data.")
            except s3.exceptions.NoSuchKey:
                # If the file does not exist, create a new dataframe
                needs_wants_savings_df = pd.DataFrame({
                    'Category': categories,
                    'Type': [''] * len(categories)
                })
                st.warning("No existing Needs, Wants, and Savings data found. Created a new dataframe.")

            # Define the options for the dropdown
            type_options = ['Need', 'Want', 'Saving']

            # Display the editable dataframe with dropdown options for the 'Type' column
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

            # Save button
            if st.button("Save"):
                with st.spinner("Saving..."):
                    # Save the dataframe to a CSV file
                    csv_buffer = edited_needs_wants_savings_df.to_csv(index=False)
                    
                    s3.put_object(Bucket=bucket_name, Key=NEEDS_WANTS_SAVINGS_PATH, Body=csv_buffer)
                    
                st.success(f"Needs, Wants, and Savings saved to S3 bucket '{bucket_name}' with key {NEEDS_WANTS_SAVINGS_PATH}")