import streamlit as st
import redis
import json
import pandas as pd
from datetime import datetime, timedelta
import os
import plotly.express as px
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
    # Improved week grouping using isocalendar
    food_df['year'] = food_df['date'].apply(lambda x: x.isocalendar()[0])
    food_df['week'] = food_df['date'].apply(lambda x: x.isocalendar()[1])
    
    # Group by year and week to avoid year-over-week issues
    weekly_totals = food_df.groupby(['year', 'week']).agg(
        total_calories=('calories', 'sum'),
        total_carbohydrate=('carbohydrate', 'sum'),
        total_fat=('fat', 'sum'),
        total_protein=('protein', 'sum'),
        week_start=('date', 'min'),  # Get the first date of each week
        days_logged=('date', 'nunique')  # Count unique days with entries
    ).reset_index().sort_values(['year', 'week'])

    # Create a readable week label
    weekly_totals['week_label'] = weekly_totals.apply(
        lambda x: f"Week {x['week']} ({x['week_start'].strftime('%b %d')})", 
        axis=1
    )
    
    if not weekly_totals.empty:
        # Convert to numeric just to be safe
        numeric_cols = ['total_calories', 'total_carbohydrate', 'total_fat', 'total_protein']
        weekly_totals[numeric_cols] = weekly_totals[numeric_cols].apply(pd.to_numeric, errors='coerce')
        
        # Calculate daily averages
        weekly_totals['avg_daily_calories'] = weekly_totals['total_calories'] / weekly_totals['days_logged']
        weekly_totals['avg_daily_carbs'] = weekly_totals['total_carbohydrate'] / weekly_totals['days_logged']
        weekly_totals['avg_daily_fat'] = weekly_totals['total_fat'] / weekly_totals['days_logged']
        weekly_totals['avg_daily_protein'] = weekly_totals['total_protein'] / weekly_totals['days_logged']
        
        # Weekly Calorie Intake
        st.subheader("Weekly Calorie Intake")
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Total Calories by Week**")
            fig = px.bar(
                weekly_totals,
                x='week_label',
                y='total_calories',
                labels={'total_calories': 'Total Calories', 'week_label': 'Week'},
                color='total_calories',
                color_continuous_scale='Bluered'
            )
            fig.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.write("**Average Daily Calories by Week**")
            fig = px.line(
                weekly_totals,
                x='week_label',
                y='avg_daily_calories',
                markers=True,
                labels={'avg_daily_calories': 'Avg Daily Calories', 'week_label': 'Week'},
                line_shape='spline'
            )
            fig.update_traces(line=dict(color='royalblue', width=3))
            fig.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
        
        # Weekly Macros
        st.subheader("Weekly Macronutrient Distribution")
        
        # Melt the dataframe for better plotting
        weekly_macros = weekly_totals.melt(
            id_vars=['week_label'], 
            value_vars=['total_carbohydrate', 'total_fat', 'total_protein'],
            var_name='Macronutrient', 
            value_name='Amount (g)'
        )
        weekly_macros['Macronutrient'] = weekly_macros['Macronutrient'].str.replace('total_', '').str.capitalize()
        
        fig = px.bar(
            weekly_macros,
            x='week_label',
            y='Amount (g)',
            color='Macronutrient',
            barmode='group',
            labels={'week_label': 'Week'},
            color_discrete_map={
                'Carbohydrate': '#636EFA',
                'Fat': '#EF553B',
                'Protein': '#00CC96'
            }
        )
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)
        
        # Weekly Macro Ratios
        st.subheader("Weekly Macronutrient Ratios")
        weekly_totals['total_macros'] = weekly_totals['total_carbohydrate'] + weekly_totals['total_fat'] + weekly_totals['total_protein']
        weekly_totals['carb_ratio'] = weekly_totals['total_carbohydrate'] / weekly_totals['total_macros'] * 100
        weekly_totals['fat_ratio'] = weekly_totals['total_fat'] / weekly_totals['total_macros'] * 100
        weekly_totals['protein_ratio'] = weekly_totals['total_protein'] / weekly_totals['total_macros'] * 100
        
        ratio_df = weekly_totals.melt(
            id_vars=['week_label'], 
            value_vars=['carb_ratio', 'fat_ratio', 'protein_ratio'],
            var_name='Macro', 
            value_name='Percentage'
        )
        ratio_df['Macro'] = ratio_df['Macro'].str.replace('_ratio', '').str.capitalize()
        
        fig = px.area(
            ratio_df,
            x='week_label',
            y='Percentage',
            color='Macro',
            labels={'week_label': 'Week', 'Percentage': 'Percentage (%)'},
            color_discrete_map={
                'Carb': '#636EFA',
                'Fat': '#EF553B',
                'Protein': '#00CC96'
            }
        )
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)
        
        # Show data table
        st.subheader("Weekly Summary Data")
        display_cols = [
            'week_label', 'total_calories', 'avg_daily_calories',
            'total_carbohydrate', 'total_fat', 'total_protein',
            'days_logged'
        ]
        st.dataframe(
            weekly_totals[display_cols].rename(columns={
                'week_label': 'Week',
                'total_calories': 'Total Calories',
                'avg_daily_calories': 'Avg Daily Calories',
                'total_carbohydrate': 'Carbs (g)',
                'total_fat': 'Fat (g)',
                'total_protein': 'Protein (g)',
                'days_logged': 'Days Logged'
            }),
            hide_index=True
        )
    else:
        st.info("No weekly data to display.")
else:
    st.info("No data available to calculate weekly trends.")

# --- Monthly Aggregated Trends ---
st.header("🗓️ Monthly Aggregated Trends (All Historical Data)")
if not food_df.empty:
    # Ensure 'date' is datetime and create 'month_start' as datetime
    food_df['date'] = pd.to_datetime(food_df['date'])
    food_df['month_start'] = food_df['date'].dt.to_period('M').dt.to_timestamp()
    
    # Create a readable month label
    food_df['month_label'] = food_df['month_start'].dt.strftime('%b %Y')

    monthly_totals = food_df.groupby(['month_start', 'month_label']).agg(
        total_calories=('calories', 'sum'),
        total_carbohydrate=('carbohydrate', 'sum'),
        total_fat=('fat', 'sum'),
        total_protein=('protein', 'sum'),
        days_logged=('date', 'nunique')  # Count unique days with entries
    ).reset_index().sort_values('month_start')

    if not monthly_totals.empty:
        # Calculate daily averages
        monthly_totals['avg_daily_calories'] = monthly_totals['total_calories'] / monthly_totals['days_logged']
        monthly_totals['avg_daily_carbs'] = monthly_totals['total_carbohydrate'] / monthly_totals['days_logged']
        monthly_totals['avg_daily_fat'] = monthly_totals['total_fat'] / monthly_totals['days_logged']
        monthly_totals['avg_daily_protein'] = monthly_totals['total_protein'] / monthly_totals['days_logged']
        
        # Monthly Calorie Intake
        st.subheader("Monthly Calorie Intake")
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Total Calories by Month**")
            fig = px.bar(
                monthly_totals,
                x='month_label',
                y='total_calories',
                labels={'total_calories': 'Total Calories', 'month_label': 'Month'},
                color='total_calories',
                color_continuous_scale='thermal'
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.write("**Average Daily Calories by Month**")
            fig = px.line(
                monthly_totals,
                x='month_label',
                y='avg_daily_calories',
                markers=True,
                labels={'avg_daily_calories': 'Avg Daily Calories', 'month_label': 'Month'},
                line_shape='spline'
            )
            fig.update_traces(line=dict(color='firebrick', width=3))
            st.plotly_chart(fig, use_container_width=True)
        
        # Monthly Macros
        st.subheader("Monthly Macronutrient Distribution")
        monthly_macros = monthly_totals.melt(
            id_vars=['month_label'], 
            value_vars=['total_carbohydrate', 'total_fat', 'total_protein'],
            var_name='Macronutrient', 
            value_name='Amount (g)'
        )
        monthly_macros['Macronutrient'] = monthly_macros['Macronutrient'].str.replace('total_', '').str.capitalize()
        
        fig = px.bar(
            monthly_macros,
            x='month_label',
            y='Amount (g)',
            color='Macronutrient',
            barmode='group',
            labels={'month_label': 'Month'},
            color_discrete_map={
                'Carbohydrate': '#636EFA',
                'Fat': '#EF553B',
                'Protein': '#00CC96'
            }
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Show data table
        st.subheader("Monthly Summary Data")
        display_cols = [
            'month_label', 'total_calories', 'avg_daily_calories',
            'total_carbohydrate', 'total_fat', 'total_protein',
            'days_logged'
        ]
        st.dataframe(
            monthly_totals[display_cols].rename(columns={
                'month_label': 'Month',
                'total_calories': 'Total Calories',
                'avg_daily_calories': 'Avg Daily Calories',
                'total_carbohydrate': 'Carbs (g)',
                'total_fat': 'Fat (g)',
                'total_protein': 'Protein (g)',
                'days_logged': 'Days Logged'
            }),
            hide_index=True
        )
    else:
        st.info("No monthly data to display.")
else:
    st.info("No data available to calculate monthly trends.")