import json
import os
import urllib.parse
from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import redis
import streamlit as st
from dotenv import load_dotenv

# --- Constants and Configuration ---
class Config:
    """Application configuration constants"""
    PAGE_TITLE = "Calorista Infographics"
    PAGE_LAYOUT = "wide"
    REDIS_KEY_PATTERN = "food_entries:*"
    DATE_FORMAT = "%Y-%m-%d"
    CACHE_TTL = 3600
    NUMERIC_COLS = [
        "calories", "carbohydrate", "fat", "protein", 
        "sodium", "sugar", "number_of_units"
    ]
    DISPLAY_COLS = [
        "food_entry_name", "meal", "calories", "carbohydrate", 
        "fat", "protein", "food_entry_description"
    ]
    MACRO_NUTRIENTS = ["Carbohydrate", "Fat", "Protein"]
    COLOR_MAP = {
        "Carbohydrate": "#636EFA",
        "Fat": "#EF553B",
        "Protein": "#00CC96"
    }


# --- Streamlit UI Configuration ---
st.set_page_config(layout=Config.PAGE_LAYOUT, page_title=Config.PAGE_TITLE)

# Load environment variables
load_dotenv()


# --- Redis Connection Handler ---
class RedisConnection:
    """Handles Redis connection and operations"""
    
    @staticmethod
    @st.cache_resource
    def get_connection():
        """Establishes and caches the Redis connection"""
        redis_url = os.getenv("REDIS_URL")
        
        if not redis_url:
            st.error("REDIS_URL is not set in your .env file. Please provide it.")
            st.stop()
            return None

        try:
            url = urllib.parse.urlparse(redis_url)
            redis_client = redis.Redis(
                host=url.hostname,
                port=url.port,
                password=url.password,
                decode_responses=True,
                ssl=True,
                ssl_cert_reqs=None,
            )
            redis_client.ping()
            st.success("Successfully connected to Redis!")
            return redis_client
        except redis.exceptions.ConnectionError as e:
            st.error(f"Could not connect to Redis. Please check your .env file and Redis server. Error: {e}")
            st.stop()
        except Exception as e:
            st.error(f"An unexpected error occurred while connecting to Redis: {e}")
            st.stop()
        
        return None


# --- Data Processing Utilities ---
class DataProcessor:
    """Handles data processing and transformation"""
    
    @staticmethod
    def parse_date_from_key(key):
        """Extracts date from Redis key"""
        try:
            date_str = key.split(":")[-1] if isinstance(key, str) else key.decode().split(":")[-1]
            return datetime.strptime(date_str, Config.DATE_FORMAT).date()
        except (ValueError, IndexError):
            return None
    
    @staticmethod
    def create_entry_identifier(entry, date_str):
        """Creates a unique identifier for an entry to prevent duplicates"""
        return (
            f"{date_str}-"
            f"{entry.get('id', '')}-"
            f"{entry.get('food_entry_name', '')}-"
            f"{entry.get('timestamp', '')}-"
            f"{entry.get('meal', '')}"
        )
    
    @staticmethod
    def process_numeric_columns(df):
        """Converts specified columns to numeric values"""
        for col in Config.NUMERIC_COLS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        return df


# --- Data Retrieval ---
@st.cache_data(ttl=Config.CACHE_TTL)
def load_and_process_data(_redis_client):
    """
    Loads and processes data from Redis, preventing duplicates
    Note: The leading underscore tells Streamlit not to hash the redis_client parameter
    """
    if not _redis_client:
        return pd.DataFrame()

    all_food_entries = []
    seen_entries = set()

    try:
        for key in _redis_client.scan_iter(Config.REDIS_KEY_PATTERN):
            entry_date = DataProcessor.parse_date_from_key(key)
            if not entry_date:
                st.warning(f"Skipping malformed date key: {key}")
                continue

            json_data = _redis_client.get(key)
            if not json_data:
                st.info(f"No data found for key: {key}")
                continue

            try:
                entries_for_day = json.loads(json_data)
                for entry in entries_for_day:
                    entry_id = DataProcessor.create_entry_identifier(entry, str(entry_date))
                    
                    if entry_id not in seen_entries:
                        entry["date"] = entry_date
                        all_food_entries.append(entry)
                        seen_entries.add(entry_id)
            except json.JSONDecodeError:
                st.warning(f"Skipping malformed JSON for key: {key}")
                
    except Exception as e:
        st.error(f"Error fetching data from Redis: {e}")
        return pd.DataFrame()

    if not all_food_entries:
        return pd.DataFrame()

    # Convert to DataFrame and process
    df = pd.DataFrame(all_food_entries)
    df = DataProcessor.process_numeric_columns(df)
    df["date"] = pd.to_datetime(df["date"]).dt.date

    return df


# --- Visualization Components ---
class VisualizationComponents:
    """Contains reusable visualization components"""
    
    @staticmethod
    def display_metrics_row(calories, carbs, fat, protein):
        """Displays a row of nutritional metrics"""
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Calories", f"{calories:.0f} kcal")
        with col2:
            st.metric("Carbohydrates", f"{carbs:.1f} g")
        with col3:
            st.metric("Fat", f"{fat:.1f} g")
        with col4:
            st.metric("Protein", f"{protein:.1f} g")
    
    @staticmethod
    def create_macro_bar_chart(data, x_col, y_col, color_col, title):
        """Creates a bar chart for macronutrients"""
        fig = px.bar(
            data,
            x=x_col,
            y=y_col,
            color=color_col,
            barmode="group",
            labels={x_col: "Week", y_col: "Amount (g)"},
            color_discrete_map=Config.COLOR_MAP,
            title=title
        )
        fig.update_layout(xaxis_tickangle=-45)
        return fig
    
    @staticmethod
    def create_line_chart(data, x_col, y_col, title, color=None):
        """Creates a line chart with customizable parameters"""
        fig = px.line(
            data,
            x=x_col,
            y=y_col,
            markers=True,
            labels={y_col: title, x_col: "Time"},
            line_shape="spline",
            color=color,
            title=title
        )
        
        if color is None:
            fig.update_traces(line=dict(width=3))
            
        fig.update_layout(xaxis_tickangle=-45)
        return fig


# --- Application Sections ---
class AppSections:
    """Contains the different sections of the application"""
    
    def __init__(self, food_df):
        self.food_df = food_df
    
    def render_latest_day_section(self):
        """Renders the latest day overview section"""
        st.header("📊 Latest Day Overview")
        
        if self.food_df.empty:
            st.info("No data available for the latest day.")
            return
            
        # Get the latest date
        sorted_dates = sorted(self.food_df["date"].unique(), reverse=True)
        latest_date = sorted_dates[0] if sorted_dates else None
        
        if not latest_date:
            st.warning("No date entries found in your Redis database.")
            return
            
        st.subheader(f"{latest_date.strftime('%Y-%m-%d')}")
        
        # Filter data for the latest day
        latest_day_df = self.food_df[self.food_df["date"] == latest_date]
        
        if latest_day_df.empty:
            st.info(f"No entries for the latest day: {latest_date.strftime('%Y-%m-%d')}.")
            return
            
        # Calculate totals
        total_calories = latest_day_df["calories"].sum()
        total_carbs = latest_day_df["carbohydrate"].sum()
        total_fat = latest_day_df["fat"].sum()
        total_protein = latest_day_df["protein"].sum()
        
        # Display metrics
        VisualizationComponents.display_metrics_row(total_calories, total_carbs, total_fat, total_protein)
        
        # Macronutrient distribution
        st.subheader("Macronutrient Distribution (Latest Day)")
        macros_data = pd.DataFrame({
            "Nutrient": Config.MACRO_NUTRIENTS,
            "Amount (g)": [total_carbs, total_fat, total_protein],
        })
        st.bar_chart(macros_data.set_index("Nutrient"))
        
        # Detailed entries
        st.subheader("Detailed Food Entries (Latest Day)")
        st.dataframe(
            latest_day_df[Config.DISPLAY_COLS].sort_values(by="meal")
        )
    
    def render_date_range_section(self):
        """Renders the custom date range section"""
        st.header("🗓️ Custom Date Range Overview")
        
        if self.food_df.empty:
            st.info("No data available for date range selection.")
            return
            
        # Get date bounds
        min_date = min(self.food_df["date"])
        max_date = max(self.food_df["date"])
        
        st.write(f"Data available from **{min_date.strftime('%Y-%m-%d')}** to **{max_date.strftime('%Y-%m-%d')}**")
        
        # Date selection
        default_start = max(min_date, max_date - timedelta(days=6))
        
        col_start, col_end = st.columns(2)
        with col_start:
            start_date = st.date_input(
                "Select Start Date:",
                value=default_start,
                min_value=min_date,
                max_value=max_date,
                key="start_date_picker",
            )
        with col_end:
            end_date = st.date_input(
                "Select End Date:",
                value=max_date,
                min_value=min_date,
                max_value=max_date,
                key="end_date_picker",
            )
        
        # Validate date range
        if start_date > end_date:
            st.error("Error: Start date cannot be after end date. Please adjust your selection.")
            return
            
        st.write(f"Displaying data from **{start_date.strftime('%Y-%m-%d')}** to **{end_date.strftime('%Y-%m-%d')}**")
        
        # Filter data
        filtered_df = self.food_df[
            (self.food_df["date"] >= start_date) & 
            (self.food_df["date"] <= end_date)
        ].copy()
        
        if filtered_df.empty:
            st.info(f"No entries found for the selected date range.")
            return
            
        # Calculate daily totals
        daily_totals = (
            filtered_df.groupby("date")
            .agg(
                total_calories=("calories", "sum"),
                total_carbohydrate=("carbohydrate", "sum"),
                total_fat=("fat", "sum"),
                total_protein=("protein", "sum"),
            )
            .reset_index()
        )
        
        # Ensure all dates in range are represented
        date_range = pd.date_range(start=start_date, end=end_date, freq="D").date
        daily_totals = (
            daily_totals.set_index("date")
            .reindex(date_range, fill_value=0)
            .reset_index()
            .rename(columns={"index": "date"})
        )
        
        # Display charts
        st.subheader("Daily Calorie Intake Trend")
        st.line_chart(daily_totals.set_index("date")["total_calories"])
        
        st.subheader("Daily Macronutrient Intake Trend")
        st.line_chart(
            daily_totals.set_index("date")[
                ["total_carbohydrate", "total_fat", "total_protein"]
            ]
        )
        
        # Period totals
        st.subheader("Aggregated Macros for the Selected Period")
        total_calories = daily_totals["total_calories"].sum()
        total_carbs = daily_totals["total_carbohydrate"].sum()
        total_fat = daily_totals["total_fat"].sum()
        total_protein = daily_totals["total_protein"].sum()
        
        VisualizationComponents.display_metrics_row(total_calories, total_carbs, total_fat, total_protein)
    
    def render_weekly_trends_section(self):
        """Renders the weekly trends section"""
        st.header("📈 Weekly Aggregated Trends (All Historical Data)")
        
        if self.food_df.empty:
            st.info("No data available to calculate weekly trends.")
            return
            
        # Prepare weekly data
        self.food_df["year"] = self.food_df["date"].apply(lambda x: x.isocalendar()[0])
        self.food_df["week"] = self.food_df["date"].apply(lambda x: x.isocalendar()[1])
        
        weekly_totals = (
            self.food_df.groupby(["year", "week"])
            .agg(
                total_calories=("calories", "sum"),
                total_carbohydrate=("carbohydrate", "sum"),
                total_fat=("fat", "sum"),
                total_protein=("protein", "sum"),
                week_start=("date", "min"),
                days_logged=("date", "nunique"),
            )
            .reset_index()
            .sort_values(["year", "week"])
        )
        
        if weekly_totals.empty:
            st.info("No weekly data to display.")
            return
            
        # Create week labels
        weekly_totals["week_label"] = weekly_totals.apply(
            lambda x: f"Week {x['week']} ({x['week_start'].strftime('%b %d')})", axis=1
        )
        
        # Calculate daily averages
        numeric_cols = ["total_calories", "total_carbohydrate", "total_fat", "total_protein"]
        weekly_totals[numeric_cols] = weekly_totals[numeric_cols].apply(pd.to_numeric, errors="coerce")
        
        weekly_totals["avg_daily_calories"] = weekly_totals["total_calories"] / weekly_totals["days_logged"]
        weekly_totals["avg_daily_carbs"] = weekly_totals["total_carbohydrate"] / weekly_totals["days_logged"]
        weekly_totals["avg_daily_fat"] = weekly_totals["total_fat"] / weekly_totals["days_logged"]
        weekly_totals["avg_daily_protein"] = weekly_totals["total_protein"] / weekly_totals["days_logged"]
        
        # Weekly Calorie Intake
        st.subheader("Weekly Calorie Intake")
        col1, col2 = st.columns(2)
        
        with col1:
            fig = px.bar(
                weekly_totals,
                x="week_label",
                y="total_calories",
                labels={"total_calories": "Total Calories", "week_label": "Week"},
                color="total_calories",
                color_continuous_scale="Bluered",
                title="Total Calories by Week"
            )
            fig.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            fig = VisualizationComponents.create_line_chart(
                weekly_totals,
                "week_label",
                "avg_daily_calories",
                "Average Daily Calories by Week"
            )
            fig.update_traces(line=dict(color="royalblue", width=3))
            st.plotly_chart(fig, use_container_width=True)
        
        # Weekly Macros
        st.subheader("Weekly Macronutrient Distribution")
        
        weekly_macros = weekly_totals.melt(
            id_vars=["week_label"],
            value_vars=["total_carbohydrate", "total_fat", "total_protein"],
            var_name="Macronutrient",
            value_name="Amount (g)",
        )
        weekly_macros["Macronutrient"] = weekly_macros["Macronutrient"].str.replace("total_", "").str.capitalize()
        
        fig = VisualizationComponents.create_macro_bar_chart(
            weekly_macros, "week_label", "Amount (g)", "Macronutrient", "Weekly Macronutrient Distribution"
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Weekly Macro Ratios
        st.subheader("Weekly Macronutrient Ratios")
        weekly_totals["total_macros"] = (
            weekly_totals["total_carbohydrate"] + 
            weekly_totals["total_fat"] + 
            weekly_totals["total_protein"]
        )
        
        for nutrient in ["carbohydrate", "fat", "protein"]:
            weekly_totals[f"{nutrient}_ratio"] = (
                weekly_totals[f"total_{nutrient}"] / weekly_totals["total_macros"] * 100
            )
        
        ratio_df = weekly_totals.melt(
            id_vars=["week_label"],
            value_vars=["carbohydrate_ratio", "fat_ratio", "protein_ratio"],
            var_name="Macro",
            value_name="Percentage",
        )
        ratio_df["Macro"] = ratio_df["Macro"].str.replace("_ratio", "").str.capitalize()
        
        fig = px.area(
            ratio_df,
            x="week_label",
            y="Percentage",
            color="Macro",
            labels={"week_label": "Week", "Percentage": "Percentage (%)"},
            color_discrete_map=Config.COLOR_MAP,
            title="Weekly Macronutrient Ratios"
        )
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)
        
        # Data table
        st.subheader("Weekly Summary Data")
        display_cols = [
            "week_label", "total_calories", "avg_daily_calories",
            "total_carbohydrate", "total_fat", "total_protein", "days_logged"
        ]
        
        renamed_cols = {
            "week_label": "Week",
            "total_calories": "Total Calories",
            "avg_daily_calories": "Avg Daily Calories",
            "total_carbohydrate": "Carbs (g)",
            "total_fat": "Fat (g)",
            "total_protein": "Protein (g)",
            "days_logged": "Days Logged",
        }
        
        st.dataframe(
            weekly_totals[display_cols].rename(columns=renamed_cols),
            hide_index=True,
        )
    
    def render_monthly_trends_section(self):
        """Renders the monthly trends section"""
        st.header("🗓️ Monthly Aggregated Trends (All Historical Data)")
        
        if self.food_df.empty:
            st.info("No data available to calculate monthly trends.")
            return
            
        # Prepare monthly data
        self.food_df["date"] = pd.to_datetime(self.food_df["date"])
        self.food_df["month_start"] = self.food_df["date"].dt.to_period("M").dt.to_timestamp()
        self.food_df["month_label"] = self.food_df["month_start"].dt.strftime("%b %Y")
        
        monthly_totals = (
            self.food_df.groupby(["month_start", "month_label"])
            .agg(
                total_calories=("calories", "sum"),
                total_carbohydrate=("carbohydrate", "sum"),
                total_fat=("fat", "sum"),
                total_protein=("protein", "sum"),
                days_logged=("date", "nunique"),
            )
            .reset_index()
            .sort_values("month_start")
        )
        
        if monthly_totals.empty:
            st.info("No monthly data to display.")
            return
            
        # Calculate daily averages
        monthly_totals["avg_daily_calories"] = monthly_totals["total_calories"] / monthly_totals["days_logged"]
        monthly_totals["avg_daily_carbs"] = monthly_totals["total_carbohydrate"] / monthly_totals["days_logged"]
        monthly_totals["avg_daily_fat"] = monthly_totals["total_fat"] / monthly_totals["days_logged"]
        monthly_totals["avg_daily_protein"] = monthly_totals["total_protein"] / monthly_totals["days_logged"]
        
        # Monthly Calorie Intake
        st.subheader("Monthly Calorie Intake")
        col1, col2 = st.columns(2)
        
        with col1:
            fig = px.bar(
                monthly_totals,
                x="month_label",
                y="total_calories",
                labels={"total_calories": "Total Calories", "month_label": "Month"},
                color="total_calories",
                color_continuous_scale="thermal",
                title="Total Calories by Month"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            fig = VisualizationComponents.create_line_chart(
                monthly_totals,
                "month_label",
                "avg_daily_calories",
                "Average Daily Calories by Month"
            )
            fig.update_traces(line=dict(color="firebrick", width=3))
            st.plotly_chart(fig, use_container_width=True)
        
        # Monthly Macros
        st.subheader("Monthly Macronutrient Distribution")
        
        monthly_macros = monthly_totals.melt(
            id_vars=["month_label"],
            value_vars=["total_carbohydrate", "total_fat", "total_protein"],
            var_name="Macronutrient",
            value_name="Amount (g)",
        )
        monthly_macros["Macronutrient"] = monthly_macros["Macronutrient"].str.replace("total_", "").str.capitalize()
        
        fig = VisualizationComponents.create_macro_bar_chart(
            monthly_macros, "month_label", "Amount (g)", "Macronutrient", "Monthly Macronutrient Distribution"
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Data table
        st.subheader("Monthly Summary Data")
        display_cols = [
            "month_label", "total_calories", "avg_daily_calories",
            "total_carbohydrate", "total_fat", "total_protein", "days_logged"
        ]
        
        renamed_cols = {
            "month_label": "Month",
            "total_calories": "Total Calories",
            "avg_daily_calories": "Avg Daily Calories",
            "total_carbohydrate": "Carbs (g)",
            "total_fat": "Fat (g)",
            "total_protein": "Protein (g)",
            "days_logged": "Days Logged",
        }
        
        st.dataframe(
            monthly_totals[display_cols].rename(columns=renamed_cols),
            hide_index=True,
        )


# --- Main Application ---
def main():
    """Main application function"""
    st.title("🍽️ Calorista Food Logging Infographics")
    
    # Initialize Redis connection
    redis_client = RedisConnection.get_connection()
    
    # Load and process data
    food_df = load_and_process_data(redis_client)
    
    # Initialize app sections
    app_sections = AppSections(food_df)
    
    # Render application sections
    app_sections.render_latest_day_section()
    app_sections.render_date_range_section()
    app_sections.render_weekly_trends_section()
    app_sections.render_monthly_trends_section()


if __name__ == "__main__":
    main()