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
@st.cache_data(ttl=3600) # Cache data for 1 hour
def load_and_process_data(_r_client): # Changed r_client to _r_client
    """
    Loads food entry data from Redis, processes it, and returns a DataFrame.
    """
    if not _r_client: # Changed r_client to _r_client
        return pd.DataFrame()

    all_food_entries = []
    try:
        # Scan for keys matching the pattern "food_entries:YYYY-MM-DD"
        # Ensure we are iterating over bytes for scan_iter and decoding
        for key_bytes in _r_client.scan_iter("food_entries:*"): # Changed r_client to _r_client
            key = key_bytes # scan_iter with decode_responses=True already returns strings
            date_str = key.split(':')[-1]
            try:
                # Convert key string to datetime object
                entry_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                st.warning(f"Skipping malformed date key: {key}")
                continue

            json_data = _r_client.get(key) # Changed r_client to _r_client
            if json_data:
                try:
                    entries_for_day = json.loads(json_data)
                    for entry in entries_for_day:
                        # Add the date to each entry for later filtering
                        entry['date'] = entry_date
                        all_food_entries.append(entry)
                except json.JSONDecodeError:
                    st.warning(f"Skipping malformed JSON for key: {key}")
            else:
                st.info(f"No data found for key: {key}")

    except Exception as e:
        st.error(f"Error fetching data from Redis: {e}")
        return pd.DataFrame()

    if not all_food_entries:
        # If no entries are found, return an empty DataFrame.
        # The UI will then gracefully handle the empty DataFrame.
        return pd.DataFrame()

    # Convert to DataFrame for easier manipulation
    df = pd.DataFrame(all_food_entries)

    # Convert numeric columns to float, coercing errors to NaN
    numeric_cols = ["calories", "carbohydrate", "fat", "protein", "sodium", "sugar", "number_of_units"]
    for col in numeric_cols:
        if col in df.columns:
            # Replace empty strings or non-numeric values with NaN, then convert to numeric
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0) # Fill NaN with 0 after conversion

    # Ensure date column is datetime object
    df['date'] = pd.to_datetime(df['date']).dt.date # Keep only the date part

    return df

food_df = load_and_process_data(redis_client)

# --- Streamlit UI ---
st.title("🍽️ Calorista Food Logging Infographics") # This was moved after set_page_config

# Only proceed with UI rendering if food_df is not empty
if not food_df.empty:
    # Sort dates to find the latest
    sorted_dates = sorted(food_df['date'].unique(), reverse=True)
    latest_date = sorted_dates[0] if sorted_dates else None # latest_date will be None if sorted_dates is empty

    if latest_date: # Only display if a latest_date exists
        st.write(f"Data available from **{min(food_df['date']).strftime('%Y-%m-%d')}** to **{max(food_df['date']).strftime('%Y-%m-%d')}**")

        # --- Latest Day Infographics ---
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

        # --- Weekly Overview Infographics ---
        st.header("🗓️ Weekly Overview")

        # User selection for number of weeks
        num_weeks = st.slider("Select number of weeks to display:", min_value=1, max_value=8, value=1)
        end_date = latest_date
        start_date = end_date - timedelta(weeks=num_weeks) + timedelta(days=1) # Start from the beginning of the selected week range

        st.write(f"Displaying data from **{start_date.strftime('%Y-%m-%d')}** to **{end_date.strftime('%Y-%m-%d')}**")

        weekly_df = food_df[(food_df['date'] >= start_date) & (food_df['date'] <= end_date)].copy() # Use .copy() to avoid SettingWithCopyWarning

        if not weekly_df.empty:
            # Group by date for daily totals within the selected period
            daily_totals_weekly = weekly_df.groupby('date').agg(
                total_calories=('calories', 'sum'),
                total_carbohydrate=('carbohydrate', 'sum'),
                total_fat=('fat', 'sum'),
                total_protein=('protein', 'sum')
            ).reset_index()

            # Ensure all dates in the range are present, fill missing with 0
            date_range = pd.date_range(start=start_date, end=end_date, freq='D').date
            daily_totals_weekly = daily_totals_weekly.set_index('date').reindex(date_range, fill_value=0).reset_index()
            daily_totals_weekly.rename(columns={'index': 'date'}, inplace=True)


            st.subheader(f"Daily Calorie Intake ({num_weeks} Week{'s' if num_weeks > 1 else ''} Trend)")
            st.line_chart(daily_totals_weekly.set_index('date')['total_calories'])

            st.subheader(f"Daily Macronutrient Intake ({num_weeks} Week{'s' if num_weeks > 1 else ''} Trend)")
            st.line_chart(daily_totals_weekly.set_index('date')[['total_carbohydrate', 'total_fat', 'total_protein']])

            st.subheader(f"Aggregated Macros for the Selected Period ({start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')})")
            total_period_calories = daily_totals_weekly['total_calories'].sum()
            total_period_carbs = daily_totals_weekly['total_carbohydrate'].sum()
            total_period_fat = daily_totals_weekly['total_fat'].sum()
            total_period_protein = weekly_df['protein'].sum() # Corrected to sum from the weekly_df

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
            st.info(f"No entries found for the selected weekly period from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}.")
    else:
        st.warning("No date entries found in your Redis database that match the 'food_entries:YYYY-MM-DD' key pattern.")

else:
    st.info("No data to display. Please ensure Redis has 'food_entries:YYYY-MM-DD' keys with valid JSON data, and your connection details in the .env file are correct.")
