import json
from typing import Optional

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st


config = json.load(open("assets/config.json"))


class SavingsForecast:
    """Render savings forecasts and life-event affordability insights."""

    def __init__(self, filtered_df: pd.DataFrame, full_df: pd.DataFrame):
        self.filtered_df = filtered_df.copy()
        self.full_df = full_df.copy()
        self.income_categories = set(config.get("INCOME_CATEGORIES", []))

    def main(self) -> None:
        monthly_summary = self._prepare_monthly_summary()

        if monthly_summary.empty:
            st.warning("Not enough transaction history to build a savings forecast.")
            return

        st.subheader("Monthly Savings Overview")
        self._render_monthly_summary(monthly_summary)
        st.divider()
        st.subheader("Major Life Event Affordability")
        avg_net_savings = monthly_summary["Net_Savings"].mean()
        self._render_mortgage_affordability(avg_net_savings)
        self._render_family_planning(avg_net_savings)
        self._render_second_car_affordability(avg_net_savings)

    def _prepare_monthly_summary(self) -> pd.DataFrame:
        """Aggregate income, expense, and net savings by month."""

        df = self.filtered_df if not self.filtered_df.empty else self.full_df
        if df.empty:
            return pd.DataFrame()

        df = df.copy()
        df["Transaction_Date"] = pd.to_datetime(df["Transaction_Date"])
        df["YearMonth"] = df["Transaction_Date"].dt.to_period("M")

        income_mask = df["Category"].isin(self.income_categories)
        monthly_income = df.loc[income_mask].groupby("YearMonth")["Amount"].sum()
        monthly_expenses = df.loc[~income_mask].groupby("YearMonth")["Amount"].sum()

        summary = (
            pd.concat([monthly_income, monthly_expenses], axis=1)
            .rename(columns={0: "Income", 1: "Expenses"})
            .fillna(0)
        )
        summary.index.name = "YearMonth"
        summary = summary.rename(columns={
            summary.columns[0]: "Income",
            summary.columns[1]: "Expenses",
        })

        summary["Net_Savings"] = summary["Income"] + summary["Expenses"]
        summary = summary.sort_index()
        summary["Month"] = summary.index.to_timestamp()
        summary["Expense_Absolute"] = summary["Expenses"].abs()
        summary["Rolling_Net_Savings"] = (
            summary["Net_Savings"].rolling(window=3, min_periods=1).mean()
        )
        return summary.reset_index(drop=True)

    def _render_monthly_summary(self, summary: pd.DataFrame) -> None:
        latest_row = summary.iloc[-1]
        last_three_avg = summary["Net_Savings"].tail(3).mean()

        col1, col2, col3 = st.columns(3)
        col1.metric(
            "Latest Net Savings",
            f"${latest_row['Net_Savings']:,.0f}",
            help="Net income after expenses for the most recent month.",
        )
        col2.metric(
            "Latest Income",
            f"${latest_row['Income']:,.0f}",
            help="Gross inflows recorded in the most recent month.",
        )
        col3.metric(
            "Latest Expenses",
            f"${latest_row['Expense_Absolute']:,.0f}",
            help="Total outflows recorded in the most recent month.",
        )

        display_df = summary[[
            "Month",
            "Income",
            "Expense_Absolute",
            "Net_Savings",
            "Rolling_Net_Savings",
        ]].rename(columns={
            "Month": "Month",
            "Income": "Income ($)",
            "Expense_Absolute": "Expenses ($)",
            "Net_Savings": "Net Savings ($)",
            "Rolling_Net_Savings": "3-Month Avg Net ($)",
        })
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Month": st.column_config.DateColumn("Month"),
                "Income ($)": st.column_config.Column("Income ($)", format="$%0.0f"),
                "Expenses ($)": st.column_config.Column("Expenses ($)", format="$%0.0f"),
                "Net Savings ($)": st.column_config.Column("Net Savings ($)", format="$%0.0f"),
                "3-Month Avg Net ($)": st.column_config.Column("3-Month Avg Net ($)", format="$%0.0f"),
            },
        )

        line_fig = px.line(
            summary,
            x="Month",
            y=["Income", "Expense_Absolute", "Net_Savings"],
            labels={"value": "Amount ($)", "variable": "Series"},
            title="Income vs. Expenses vs. Net Savings",
        )
        line_fig.update_traces(mode="lines+markers")
        line_fig.update_layout(legend_title_text="")
        st.plotly_chart(line_fig, use_container_width=True)

        area_fig = px.area(
            summary,
            x="Month",
            y="Net_Savings",
            title="Monthly Net Savings Trend",
        )
        area_fig.update_layout(yaxis_title="Net Savings ($)")
        st.plotly_chart(area_fig, use_container_width=True)

        if last_three_avg < 0:
            st.error(
                "Net savings have been negative over the last three months. Consider trimming discretionary spending," \
                " negotiating recurring bills, or setting aside a fixed transfer to savings right after payday."
            )
        elif last_three_avg < latest_row["Net_Savings"]:
            st.warning(
                "Savings are improving, but continue monitoring upcoming large expenses to keep momentum."
            )
        else:
            st.success(
                "Savings are stable. Keep automating transfers to savings and look for opportunities to invest excess cash."
            )

    def _render_mortgage_affordability(self, avg_net_savings: float) -> None:
        with st.expander("Mortgage Affordability"):
            home_price = st.number_input(
                "Target home price ($)", value=350000.0, min_value=0.0, step=5000.0
            )
            down_payment = st.number_input(
                "Available down payment ($)",
                value=70000.0,
                min_value=0.0,
                max_value=home_price if home_price else None,
                step=5000.0,
            )
            interest_rate = st.number_input(
                "Mortgage interest rate (%)", value=6.0, min_value=0.0, step=0.1
            )
            term_years = st.number_input(
                "Mortgage term (years)", value=30, min_value=1, step=1
            )

            loan_amount = max(home_price - down_payment, 0)
            monthly_payment = self._amortized_payment(
                principal=loan_amount,
                annual_rate=interest_rate,
                term_years=term_years,
            )

            affordability_ratio = self._affordability_ratio(monthly_payment, avg_net_savings)
            months_to_recover_down = self._break_even_months(down_payment, avg_net_savings)

            self._display_affordability_metrics(
                monthly_cost=monthly_payment,
                ratio=affordability_ratio,
                break_even_months=months_to_recover_down,
                avg_net_savings=avg_net_savings,
                context="mortgage",
            )

    def _render_family_planning(self, avg_net_savings: float) -> None:
        with st.expander("Starting or Expanding a Family"):
            childcare = st.number_input(
                "Monthly childcare or education costs ($)",
                value=1200.0,
                min_value=0.0,
                step=50.0,
            )
            healthcare = st.number_input(
                "Additional healthcare and insurance ($)",
                value=400.0,
                min_value=0.0,
                step=25.0,
            )
            lifestyle = st.number_input(
                "Higher living expenses (food, utilities, etc.) ($)",
                value=350.0,
                min_value=0.0,
                step=25.0,
            )
            family_total = childcare + healthcare + lifestyle

            affordability_ratio = self._affordability_ratio(family_total, avg_net_savings)
            cushion_months = self._break_even_months(family_total * 6, avg_net_savings)

            self._display_affordability_metrics(
                monthly_cost=family_total,
                ratio=affordability_ratio,
                break_even_months=cushion_months,
                avg_net_savings=avg_net_savings,
                context="family",
            )

    def _render_second_car_affordability(self, avg_net_savings: float) -> None:
        with st.expander("Buying a Second Car"):
            car_price = st.number_input(
                "Car purchase price ($)", value=38000.0, min_value=0.0, step=1000.0
            )
            car_down_payment = st.number_input(
                "Down payment ($)",
                value=5000.0,
                min_value=0.0,
                max_value=car_price if car_price else None,
                step=500.0,
            )
            car_rate = st.number_input(
                "Auto loan rate (%)", value=5.5, min_value=0.0, step=0.1
            )
            car_term_years = st.number_input(
                "Auto loan term (years)", value=5, min_value=1, step=1
            )
            insurance = st.number_input(
                "Additional monthly insurance ($)", value=180.0, min_value=0.0, step=10.0
            )
            maintenance = st.number_input(
                "Maintenance & fuel allowance ($)", value=150.0, min_value=0.0, step=10.0
            )

            loan_amount = max(car_price - car_down_payment, 0)
            loan_payment = self._amortized_payment(
                principal=loan_amount,
                annual_rate=car_rate,
                term_years=car_term_years,
            )
            total_monthly_cost = loan_payment + insurance + maintenance

            affordability_ratio = self._affordability_ratio(total_monthly_cost, avg_net_savings)
            months_to_rebuild_down = self._break_even_months(car_down_payment, avg_net_savings)

            self._display_affordability_metrics(
                monthly_cost=total_monthly_cost,
                ratio=affordability_ratio,
                break_even_months=months_to_rebuild_down,
                avg_net_savings=avg_net_savings,
                context="car",
            )

    @staticmethod
    def _amortized_payment(principal: float, annual_rate: float, term_years: float) -> float:
        if principal <= 0:
            return 0.0
        months = int(term_years * 12)
        months = max(months, 1)
        monthly_rate = annual_rate / 100 / 12
        if monthly_rate == 0:
            return principal / months
        factor = (1 + monthly_rate) ** months
        return principal * (monthly_rate * factor) / (factor - 1)

    @staticmethod
    def _affordability_ratio(monthly_cost: float, avg_net_savings: float) -> float:
        if avg_net_savings <= 0:
            return np.inf
        return monthly_cost / avg_net_savings if avg_net_savings else np.inf

    @staticmethod
    def _break_even_months(amount: float, avg_net_savings: float) -> Optional[float]:
        if amount <= 0 or avg_net_savings <= 0:
            return None
        return amount / avg_net_savings

    def _display_affordability_metrics(
        self,
        *,
        monthly_cost: float,
        ratio: float,
        break_even_months: Optional[float],
        avg_net_savings: float,
        context: str,
    ) -> None:
        monthly_label = {
            "mortgage": "Estimated monthly mortgage",
            "family": "New monthly family costs",
            "car": "Total second car cost",
        }[context]

        ratio_label = {
            "mortgage": "Mortgage vs. savings",
            "family": "Family costs vs. savings",
            "car": "Car costs vs. savings",
        }[context]

        with st.container():
            kpi1, kpi2 = st.columns(2)
            kpi1.metric(monthly_label, f"${monthly_cost:,.0f}")
            if np.isinf(ratio):
                kpi2.metric(ratio_label, "Not affordable")
            else:
                kpi2.metric(ratio_label, f"{ratio:.2f}x")

            if break_even_months is None:
                st.caption("Build positive monthly savings to fund this goal sustainably.")
            else:
                years = break_even_months / 12
                st.caption(
                    f"Rebuilding the upfront cost would take about {break_even_months:.1f} months (~{years:.1f} years) at the current average net savings of ${avg_net_savings:,.0f}."
                )

            guidance = self._affordability_guidance(ratio, context)
            if guidance:
                st.write(guidance)

    @staticmethod
    def _affordability_guidance(ratio: float, context: str) -> str:
        context_messages = {
            "mortgage": (
                "Aim to keep housing costs under 30%-35% of take-home savings. Consider a larger down payment or lower price range if the ratio exceeds 1.0x."
            ),
            "family": (
                "Layer new costs gradually and earmark sinking funds for childcare, healthcare, and parental leave to avoid dipping into emergency reserves."
            ),
            "car": (
                "Compare total car costs to net savings and explore certified pre-owned options or delaying the purchase until insurance and maintenance fit comfortably."
            ),
        }

        if np.isinf(ratio):
            return "Current net savings are negative or zero. Stabilize cash flow before committing to this goal."
        if ratio <= 0.4:
            return "This goal fits well within typical savings capacity. Continue automating transfers to stay disciplined."
        if ratio <= 0.75:
            return "The goal is manageable but monitor cash buffers and prepare a contingency fund for unexpected costs."
        if ratio <= 1.0:
            return "Affordability is tight—adjust lifestyle expenses, increase income, or extend the timeline before proceeding."
        return context_messages[context]
