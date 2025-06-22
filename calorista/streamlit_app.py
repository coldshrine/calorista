import streamlit as st
import redis
import json
import pandas as pd
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import urllib.parse # Import urllib.parse to parse the Redis URL

# --- Streamlit UI Configuration (MUST be the first Streamlit command) ---
st.set_page_config(layout="wide", page_title="Calorista Infographics")

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
# Use REDIS_URL directly from the .env file
REDIS_URL = os.getenv("REDIS_URL")

# --- Redis Connection ---
@st.cache_resource
def get_redis_connection():
    """Establishes and caches the Redis connection by parsing REDIS_URL."""
    if not REDIS_URL:
        st.error("REDIS_URL is not set in your .env file. Please provide it.")
        st.stop()
        return None

    try:
        url = urllib.parse.urlparse(REDIS_URL)
        redis_host = url.hostname
        redis_port = url.port
        redis_password = url.password
        
        # Add ssl=True for secure connections, common with cloud Redis providers like Upstash
        r = redis.Redis(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            decode_responses=True, # Decode Redis responses to string
            ssl=True, # Explicitly enable SSL
            ssl_cert_reqs=None # Or provide certs if specific validation is needed
        )
        r.ping() # Test connection
        st.success("Successfully connected to Redis!")
        return r
    except redis.exceptions.ConnectionError as e:
        st.error(f"Could not connect to Redis. Please check your .env file and Redis server. Error: {e}")
        st.stop() # Stop the app if connection fails
    except Exception as e:
        st.error(f"An unexpected error occurred while connecting to Redis: {e}")
        st.stop()
    return None

redis_client = get_redis_connection()

# --- Data Retrieval and Processing ---
# --- Data Retrieval and Processing ---
@st.cache_data(ttl=3600)
def load_and_process_data(_r_client):
    """
    Enhanced version that prevents duplicates while keeping all functionality
    """
    if not _r_client:
        return pd.DataFrame()

    all_food_entries = []
    seen_entries = set()  # Track unique entries to prevent duplicates
    
    try:
        for key in _r_client.scan_iter("food_entries:*"):
            date_str = key.split(':')[-1] if isinstance(key, str) else key.decode().split(':')[-1]
            
            try:
                entry_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                st.warning(f"Skipping malformed date key: {key}")
                continue

            json_data = _r_client.get(key)
            if json_data:
                try:
                    entries_for_day = json.loads(json_data)
                    for entry in entries_for_day:
                        # Create a unique identifier for each entry
                        entry_id = (
                            f"{date_str}-"
                            f"{entry.get('id', '')}-"
                            f"{entry.get('food_entry_name', '')}-"
                            f"{entry.get('timestamp', '')}-"
                            f"{entry.get('meal', '')}"
                        )
                        
                        if entry_id not in seen_entries:
                            entry['date'] = entry_date
                            all_food_entries.append(entry)
                            seen_entries.add(entry_id)
                except json.JSONDecodeError:
                    st.warning(f"Skipping malformed JSON for key: {key}")
            else:
                st.info(f"No data found for key: {key}")

    except Exception as e:
        st.error(f"Error fetching data from Redis: {e}")
        return pd.DataFrame()

    if not all_food_entries:
        return pd.DataFrame()

    # Convert to DataFrame (keeping all your existing processing)
    df = pd.DataFrame(all_food_entries)

    # Your existing numeric conversions
    numeric_cols = ["calories", "carbohydrate", "fat", "protein", "sodium", "sugar", "number_of_units"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

    # Your existing date handling
    df['date'] = pd.to_datetime(df['date']).dt.date

    return df

food_df = load_and_process_data(redis_client)

# --- Streamlit UI ---
st.title("🍽️ Calorista Food Logging Infographics")

# Only proceed with UI rendering if food_df is not empty
if not food_df.empty:
    # Get min and max dates from the loaded data
    min_available_date = min(food_df['date'])
    max_available_date = max(food_df['date'])

    st.write(f"Data available from **{min_available_date.strftime('%Y-%m-%d')}** to **{max_available_date.strftime('%Y-%m-%d')}**")

    # --- Latest Day Infographics ---
    # Sort dates to find the latest
    sorted_dates = sorted(food_df['date'].unique(), reverse=True)
    latest_date = sorted_dates[0] if sorted_dates else None

    if latest_date: # Only display if a latest_date exists
        st.header(f"📊 Latest Day Overview: {latest_date.strftime('%Y-%m-%d')}")

        latest_day_df = food_df[food_df['date'] == latest_date]
        if not latest_day_df.empty:
            total_calories_latest = latest_day_df['calories'].sum()
            total_carbs_latest = latest_day_df['carbohydrate'].sum()
            total_fat_latest = latest_day_df['fat'].sum()
            total_protein_latest = latest_day_df['protein'].sum()

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Calories", f"{total_calories_latest:.0f} kcal")
            with col2:
                st.metric("Carbohydrates", f"{total_carbs_latest:.1f} g")
            with col3:
                st.metric("Fat", f"{total_fat_latest:.1f} g")
            with col4:
                st.metric("Protein", f"{total_protein_latest:.1f} g")

            st.subheader("Macronutrient Distribution (Latest Day)")
            macros_latest = pd.DataFrame({
                'Nutrient': ['Carbohydrates', 'Fat', 'Protein'],
                'Amount (g)': [total_carbs_latest, total_fat_latest, total_protein_latest]
            })
            st.bar_chart(macros_latest.set_index('Nutrient'))

            st.subheader("Detailed Food Entries (Latest Day)")
            st.dataframe(latest_day_df[['food_entry_name', 'meal', 'calories', 'carbohydrate', 'fat', 'protein', 'food_entry_description']].sort_values(by='meal'))

        else:
            st.info(f"No entries for the latest day: {latest_date.strftime('%Y-%m-%d')}.")
    else:
        st.warning("No date entries found in your Redis database that match the 'food_entries:YYYY-MM-DD' key pattern for the latest day.")


    # --- Flexible Date Range Overview ---
    st.header("🗓️ Custom Date Range Overview")

    # Calculate default start date for the date picker (e.g., last 7 days from max_available_date)
    default_start_date_picker = max(min_available_date, max_available_date - timedelta(days=6))

    col_start, col_end = st.columns(2)
    with col_start:
        selected_start_date = st.date_input(
            "Select Start Date:",
            value=default_start_date_picker,
            min_value=min_available_date,
            max_value=max_available_date,
            key="start_date_picker"
        )
    with col_end:
        selected_end_date = st.date_input(
            "Select End Date:",
            value=max_available_date,
            min_value=min_available_date,
            max_value=max_available_date,
            key="end_date_picker"
        )

    # Ensure start date is not after end date
    if selected_start_date > selected_end_date:
        st.error("Error: Start date cannot be after end date. Please adjust your selection.")
    else:
        st.write(f"Displaying data from **{selected_start_date.strftime('%Y-%m-%d')}** to **{selected_end_date.strftime('%Y-%m-%d')}**")

        filtered_df = food_df[(food_df['date'] >= selected_start_date) & (food_df['date'] <= selected_end_date)].copy()

        if not filtered_df.empty:
            # Group by date for daily totals within the selected period
            daily_totals_filtered = filtered_df.groupby('date').agg(
                total_calories=('calories', 'sum'),
                total_carbohydrate=('carbohydrate', 'sum'),
                total_fat=('fat', 'sum'),
                total_protein=('protein', 'sum')
            ).reset_index()

            # Ensure all dates in the range are present, fill missing with 0
            date_range = pd.date_range(start=selected_start_date, end=selected_end_date, freq='D').date
            daily_totals_filtered = daily_totals_filtered.set_index('date').reindex(date_range, fill_value=0).reset_index()
            daily_totals_filtered.rename(columns={'index': 'date'}, inplace=True)


            st.subheader(f"Daily Calorie Intake Trend")
            st.line_chart(daily_totals_filtered.set_index('date')['total_calories'])

            st.subheader(f"Daily Macronutrient Intake Trend")
            st.line_chart(daily_totals_filtered.set_index('date')[['total_carbohydrate', 'total_fat', 'total_protein']])

            st.subheader(f"Aggregated Macros for the Selected Period")
            total_period_calories = daily_totals_filtered['total_calories'].sum()
            total_period_carbs = daily_totals_filtered['total_carbohydrate'].sum()
            total_period_fat = daily_totals_filtered['total_fat'].sum()
            total_period_protein = filtered_df['protein'].sum()

            col5, col6, col7, col8 = st.columns(4)
            with col5:
                st.metric("Total Period Calories", f"{total_period_calories:.0f} kcal")
            with col6:
                st.metric("Total Period Carbs", f"{total_period_carbs:.1f} g")
            with col7:
                st.metric("Total Period Fat", f"{total_period_fat:.1f} g")
            with col8:
                st.metric("Total Period Protein", f"{total_period_protein:.1f} g")

        else:
            st.info(f"No entries found for the selected date range from {selected_start_date.strftime('%Y-%m-%d')} to {selected_end_date.strftime('%Y-%m-%d')}.")


    # --- Weekly Aggregated Trends ---
    st.header("📈 Weekly Aggregated Trends (All Historical Data)")
    if not food_df.empty:
        # Create a 'week_start' column
        # Using week of year (W) for grouping, ensuring it's tied to the year
        # Get Monday of the week for consistent grouping
        food_df['week_start'] = food_df['date'].apply(lambda x: x - timedelta(days=x.weekday()))
        
        weekly_totals = food_df.groupby('week_start').agg(
            total_calories=('calories', 'sum'),
            total_carbohydrate=('carbohydrate', 'sum'),
            total_fat=('fat', 'sum'),
            total_protein=('protein', 'sum')
        ).reset_index().sort_values('week_start')

        if not weekly_totals.empty:
            st.subheader("Weekly Calorie Intake Trend")
            st.line_chart(weekly_totals.set_index('week_start')['total_calories'])

            st.subheader("Weekly Macronutrient Intake Trend")
            st.line_chart(weekly_totals.set_index('week_start')[['total_carbohydrate', 'total_fat', 'total_protein']])
        else:
            st.info("No weekly data to display.")
    else:
        st.info("No data available to calculate weekly trends.")


    # --- Monthly Aggregated Trends ---
    st.header("🗓️ Monthly Aggregated Trends (All Historical Data)")
    if not food_df.empty:
        # Create a 'month_start' column
        food_df['month_start'] = food_df['date'].apply(lambda x: x.replace(day=1))

        monthly_totals = food_df.groupby('month_start').agg(
            total_calories=('calories', 'sum'),
            total_carbohydrate=('carbohydrate', 'sum'),
            total_fat=('fat', 'sum'),
            total_protein=('protein', 'sum')
        ).reset_index().sort_values('month_start')

        if not monthly_totals.empty:
            st.subheader("Monthly Calorie Intake Trend")
            st.line_chart(monthly_totals.set_index('month_start')['total_calories'])

            st.subheader("Monthly Macronutrient Intake Trend")
            st.line_chart(monthly_totals.set_index('month_start')[['total_carbohydrate', 'total_fat', 'total_protein']])
        else:
            st.info("No monthly data to display.")
    else:
        st.info("No data available to calculate monthly trends.")

else:
    st.info("No data to display. Please ensure Redis has 'food_entries:YYYY-MM-DD' keys with valid JSON data, and your connection details in the .env file are correct.")
