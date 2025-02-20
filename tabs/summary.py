# Summary Tab
import streamlit as st
import json
import plotly.express as px

config = json.load(open("assets/config.json"))

NEEDS = config["NEEDS"]
WANTS = config["WANTS"]
SAVINGS = config["SAVINGS"]

class Summary:
    def __init__(self, df):
        self.df = df

    def main(self):
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