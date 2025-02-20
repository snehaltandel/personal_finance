import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_plotly_events import plotly_events
import boto3
import json

# Load configuration
config = json.load(open("assets/config.json"))

# Initialize S3 client
s3 = boto3.client('s3')
bucket_name = config["S3_BUCKET_NAME"]
budget_file_key = config["budget_file_key"]
NEEDS_WANTS_SAVINGS_PATH = config["NEEDS_WANTS_SAVINGS_PATH"]
EXCLUDED_CATEGORIES = config["EXCLUDED_CATEGORIES"]
INCOME_CATEGORIES = config["INCOME_CATEGORIES"]

class Expenses:
    def __init__(self, filter_data):
        self.filtered_df = filter_data
        self.excluded_categories = EXCLUDED_CATEGORIES
        self.income_categories = INCOME_CATEGORIES

    def show_kpi_cards(self):
        """
        Displays KPI cards for Total Income and Total Expenses.
        """
        if not self.filtered_df.empty:
            total_expenses = abs(self.filtered_df[~self.filtered_df["Category"].isin(self.excluded_categories)]["Amount"].sum())
            total_income = abs(self.filtered_df[self.filtered_df["Category"].isin(self.income_categories)]["Amount"].sum())

            st.markdown(
                """
                <style>
                .kpi-card {
                    background-color: #f0f2f6;
                    padding: 20px;
                    border-radius: 10px;
                    text-align: center;
                    margin-bottom: 20px;
                }
                .kpi-card h3 {
                    margin: 0;
                    font-size: 24px;
                }
                .kpi-card p {
                    margin: 0;
                    font-size: 18px;
                }
                </style>
                """, unsafe_allow_html=True
            )

            col1, col2 = st.columns(2)
            with col1:
                st.markdown(
                    f"""
                    <div class="kpi-card">
                    <h3>Total Expenses</h3>
                    <p>${total_expenses:,.2f}</p>
                    </div>
                    """, unsafe_allow_html=True
                )
            with col2:
                st.markdown(
                    f"""
                    <div class="kpi-card">
                    <h3>Total Income</h3>
                    <p>${total_income:,.2f}</p>
                    </div>
                    """, unsafe_allow_html=True
                )
        else:
            st.warning("No data available for the selected filters.")

    def need_want_saving(self):
        """
        Categorizes and displays the total amounts for needs, wants, and savings from the filtered DataFrame.
        """
        # Fetch the CSV file from S3
        obj = s3.get_object(Bucket=bucket_name, Key=NEEDS_WANTS_SAVINGS_PATH)
        needs_wants_savings_df = pd.read_csv(obj['Body'])

        # Extract categories
        needs = needs_wants_savings_df[needs_wants_savings_df['Type'] == 'Need']['Category'].tolist()
        wants = needs_wants_savings_df[needs_wants_savings_df['Type'] == 'Want']['Category'].tolist()
        savings = needs_wants_savings_df[needs_wants_savings_df['Type'] == 'Saving']['Category'].tolist()

        if not self.filtered_df.empty:
            needs_total = abs(self.filtered_df[self.filtered_df["Category"].isin(needs)]["Amount"].sum())
            wants_total = abs(self.filtered_df[self.filtered_df["Category"].isin(wants)]["Amount"].sum())
            savings_total = abs(self.filtered_df[self.filtered_df["Category"].isin(savings)]["Amount"].sum())

            total_income = abs(self.filtered_df[self.filtered_df["Category"].isin(self.income_categories)]["Amount"].sum())
            needs_percentage = (needs_total / total_income) * 100 if total_income > 0 else 0
            wants_percentage = (wants_total / total_income) * 100 if total_income > 0 else 0
            savings_percentage = (savings_total / total_income) * 100 if total_income > 0 else 0

            st.markdown(
            """
            <style>
            .kpi-card {
                background-color: #f0f2f6;
                padding: 20px;
                border-radius: 10px;
                text-align: center;
                margin-bottom: 20px;
            }
            .kpi-card h3 {
                margin: 0;
                font-size: 24px;
            }
            .kpi-card p {
                margin: 0;
                font-size: 18px;
            }
            </style>
            """, unsafe_allow_html=True
            )

            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown(
                    f"""
                    <div class="kpi-card">
                    <h3>Needs</h3>
                    <p>${needs_total:,.2f} ({needs_percentage:.2f}%)</p>
                    </div>
                    """, unsafe_allow_html=True
                )
            with col2:
                st.markdown(
                    f"""
                    <div class="kpi-card">
                    <h3>Wants</h3>
                    <p>${wants_total:,.2f} ({wants_percentage:.2f}%)</p>
                    </div>
                    """, unsafe_allow_html=True
                )
            with col3:
                st.markdown(
                    f"""
                    <div class="kpi-card">
                    <h3>Savings</h3>
                    <p>${savings_total:,.2f} ({savings_percentage:.2f}%)</p>
                    </div>
                    """, unsafe_allow_html=True
                )
        else:
            st.warning("No data available for the selected filters.")

    def show_dashboard(self):
        """
        Displays a dashboard with a breakdown of amounts based on the specified breakdown type.
        """

        if not self.filtered_df.empty:
            st.subheader("Total Amount by Category")
            st.info(f"NOTE: Categories excluded are {self.excluded_categories}")
            
            filtered_df = self.filtered_df[~self.filtered_df["Category"].isin(self.excluded_categories)]

            summary = filtered_df.groupby("Category")["Amount"].sum().abs().reset_index()
            summary = summary.sort_values(by="Amount", ascending=False)
            fig = px.bar(summary, x="Amount", y="Category", orientation='h', 
                        title="Total Amount by Category", text_auto='.2s')

            fig.update_layout(xaxis_tickformat='$,.2f', font=dict(size=24))
            
            # Create a toggle to switch between tree plot, bar chart, bubble chart, and table view
            view_option = st.radio("Select View", ("Tree Plot", "Bar Chart", "Bubble Chart", "Table View"), index=0, horizontal=True)

            if view_option == "Tree Plot":
                # Display the tree plot
                tree_fig = px.treemap(summary, path=["Category"], values='Amount', title="Tree Plot of Amounts")
                tree_fig.update_traces(textinfo="label+value")
                st.plotly_chart(tree_fig, use_container_width=True)
            elif view_option == "Bar Chart":
                # Display the bar chart
                st.plotly_chart(fig, use_container_width=True)
            elif view_option == "Bubble Chart":
                # Display a simple bubble chart
                bubble_fig = px.scatter(summary, x="Amount", y="Category", size="Amount", color="Category", title="Bubble Chart of Amounts")
                st.plotly_chart(bubble_fig, use_container_width=True)
            elif view_option == "Table View":
                # Display the table view
                st.dataframe(summary.reset_index(drop=True), use_container_width=True)

            # Calculate total amount
            total_summary = pd.DataFrame({
                "Total": ["Total"],
                "Amount": [abs(filtered_df["Amount"].sum())]
            })

            st.dataframe(total_summary, use_container_width=True)

        else:
            st.warning("No data available for the selected filters.")
            

    def show_full_tabular_view(self):
        """
        Displays a full tabular view of the filtered DataFrame.
        """

        self.filtered_df = self.filtered_df.sort_values(by=["Transaction_Date", "Account_Type", "Description", "Amount"], ascending=[True, True, True, True]).reset_index(drop=True)

        if not self.filtered_df.empty:
            st.subheader("Full Tabular View of Filtered Data")
            st.dataframe(self.filtered_df, use_container_width=True)
        else:
            st.warning("No data available for the selected filters.")

    def main(self):
        """
        Main method to display the dashboard.
        This method displays the dashboard with various options including KPI cards,
        breakdown by category or account type, and tabular views.
        Returns:
            None
        """
        self.show_kpi_cards()

        self.need_want_saving()

        self.show_dashboard()

        self.show_full_tabular_view()