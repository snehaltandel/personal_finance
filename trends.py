import pandas as pd
import plotly.express as px
import streamlit as st

class FinanceTrends:
    def __init__(self, data):
        """
        Initialize with a DataFrame containing 'Date', 'Income', and 'Expenses' columns.
        """
        self.data = data
        self.data['Transaction_Date'] = pd.to_datetime(self.data['Transaction_Date'])
        self.data['YearMonth'] = self.data['Transaction_Date'].dt.to_period('M')
        self.data['Income'] = self.data['Amount'].apply(lambda x: x if x > 0 else 0)
        self.data['Expenses'] = self.data['Amount'].apply(lambda x: x if x < 0 else 0)
        self.data = self.data.groupby('YearMonth').agg({'Income': 'sum', 'Expenses': 'sum'}).reset_index()
        self.data = self.data.sort_values('YearMonth')
        self.data['Date'] = self.data['YearMonth'].dt.to_timestamp()

    def plot_trends(self):
        """
            This method checks if the data is available. If the data is empty, it displays a warning message.
            Otherwise, it creates a line chart with 'Date' on the x-axis and 'Income' and 'Expenses' on the y-axis.
            The chart includes labels for the axes and a title. The chart is then displayed using Streamlit.

            Parameters:
            None

            Returns:
            None
        """
        
        if self.data.empty:
            st.warning("No data available for the selected filters.")
        else:
            fig = px.line(self.data, x='Date', y=['Income', 'Expenses'], 
                          labels={'value': 'Amount', 'variable': 'Category'},
                          title='Income and Expenses Over Time')
            fig.update_layout(xaxis_title='Date', yaxis_title='Amount')
            st.plotly_chart(fig, use_container_width=True)

