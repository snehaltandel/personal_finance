import streamlit as st
import pandas as pd


class Filter:
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
            default_end_date = max_date
            default_start_date = pd.Timestamp(f"{default_end_date.year}-{default_end_date.month}-01")

            self.start_date, self.end_date = st.sidebar.date_input(
                "Select Date Range", 
                [default_start_date, default_end_date], 
                min_value=min_date, 
                max_value=max_date,
                key='date_input'
            )
            
        elif filter_option == "Previous Month":
            # Previous month filter
            self.start_date = (pd.Timestamp.now() - pd.DateOffset(months=1)).replace(day=1).date()
            self.end_date = (self.start_date + pd.offsets.MonthEnd(1)).date()

        elif filter_option == "Year To Date":
            # Year to date filter
            self.start_date = (pd.to_datetime(f"{pd.Timestamp.now().year}-01-01")).date()
            self.end_date = (pd.Timestamp.now().replace(day=1) + pd.offsets.MonthEnd(0)).date()

        elif filter_option == "Last 3 Months":
            # Last 3 months filter
            self.start_date = ((pd.Timestamp.now() - pd.DateOffset(months=3)).replace(day=1)).date()
            self.end_date = (pd.Timestamp.now().replace(day=1) + pd.offsets.MonthEnd(0)).date()
            
        elif filter_option == "Last Year":
            # Last year filter
            self.start_date = (pd.to_datetime(f"{pd.Timestamp.now().year - 1}-01-01")).date()
            self.end_date = (pd.to_datetime(f"{pd.Timestamp.now().year - 1}-12-31")).date()
    
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
            (self.df["Transaction_Date"] >= pd.Timestamp(self.start_date).date()) &
            (self.df["Transaction_Date"] <= pd.Timestamp(self.end_date).date())
        ]
        return filtered_df, self.df