import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_plotly_events import plotly_events
import boto3
import json
import os
from dotenv import load_dotenv
load_dotenv()

# Load configuration
config = json.load(open("assets/config.json"))

# Initialize S3 client
s3 = boto3.client(
    's3',
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"]
)
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

    def _load_needs_wants_savings_config(self):
        obj = s3.get_object(Bucket=bucket_name, Key=NEEDS_WANTS_SAVINGS_PATH)
        return pd.read_csv(obj["Body"])

    def _get_category_type_sets(self):
        needs_wants_savings_df = self._load_needs_wants_savings_config()
        needs = set(
            needs_wants_savings_df[needs_wants_savings_df["Type"] == "Need"]["Category"].dropna()
        )
        wants = set(
            needs_wants_savings_df[needs_wants_savings_df["Type"] == "Want"]["Category"].dropna()
        )
        savings = set(
            needs_wants_savings_df[needs_wants_savings_df["Type"] == "Saving"]["Category"].dropna()
        )
        return needs, wants, savings

    def _get_expense_breakdown_df(self):
        if self.filtered_df.empty:
            return pd.DataFrame(columns=self.filtered_df.columns)

        needs, wants, _ = self._get_category_type_sets()
        expense_categories = needs.union(wants)
        return self.filtered_df[self.filtered_df["Category"].isin(expense_categories)].copy()

    def _get_unmapped_expense_categories(self):
        if self.filtered_df.empty:
            return []

        needs, wants, savings = self._get_category_type_sets()
        mapped_categories = needs.union(wants).union(savings).union(self.income_categories)
        candidate_df = self.filtered_df[
            ~self.filtered_df["Category"].isin(self.excluded_categories)
        ]
        unmapped_categories = sorted(
            set(candidate_df["Category"].dropna()) - mapped_categories
        )
        return unmapped_categories

    def _calculate_bucket_totals(self):
        if self.filtered_df.empty:
            return {
                "needs_total": 0.0,
                "wants_total": 0.0,
                "savings_total": 0.0,
                "total_expenses": 0.0,
                "total_income": 0.0,
            }

        needs, wants, savings = self._get_category_type_sets()
        categorized_df = self.filtered_df.copy()

        needs_total = abs(categorized_df[categorized_df["Category"].isin(needs)]["Amount"].sum())
        wants_total = abs(categorized_df[categorized_df["Category"].isin(wants)]["Amount"].sum())
        savings_total = abs(categorized_df[categorized_df["Category"].isin(savings)]["Amount"].sum())
        total_income = abs(
            categorized_df[categorized_df["Category"].isin(self.income_categories)]["Amount"].sum()
        )

        return {
            "needs_total": needs_total,
            "wants_total": wants_total,
            "savings_total": savings_total,
            "total_expenses": needs_total + wants_total,
            "total_income": total_income,
        }

    def show_kpi_cards(self):
        """
        Displays KPI cards for Total Income and Total Expenses.
        """
        if not self.filtered_df.empty:
            totals = self._calculate_bucket_totals()
            total_expenses = totals["total_expenses"]
            total_income = totals["total_income"]

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
        if not self.filtered_df.empty:
            totals = self._calculate_bucket_totals()
            needs_total = totals["needs_total"]
            wants_total = totals["wants_total"]
            savings_total = totals["savings_total"]
            total_income = totals["total_income"]
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
            filtered_df = self._get_expense_breakdown_df()
            unmapped_categories = self._get_unmapped_expense_categories()

            st.info(
                "NOTE: This table includes only categories mapped to Needs or Wants so it matches Total Expenses. "
                f"Excluded categories are {self.excluded_categories}."
            )
            if unmapped_categories:
                st.warning(
                    "These categories are not currently mapped to Needs/Wants/Savings and are excluded from Total Expenses: "
                    + ", ".join(unmapped_categories)
                )

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
