# calorista

Extracts food logs from the FatSecret API for authenticated users, cleans and deduplicates entries, transforms them into structured nutritional records, and loads them into Redis for fast, low-latency access. The data is then visualized in a Streamlit dashboard, providing real-time insights, macro tracking, and historical trends.

Demo:

https://calorista.streamlit.app/

![Calorista Icon](./icon.jpg)

ETL pipeline for authenticated fatsecret users that extracts real-time food log data, transforms raw entries with detailed nutritional metadata.

## 🔑 API Access

To use this project, you must [register your application with FatSecret](https://platform.fatsecret.com/api/Default.aspx?screen=rapiintro) and obtain your own **API Key** and **API Secret**. This is required to authenticate users and access their food log data via the fatsecret Platform API.

Please remember that you need to also whitelist your IP inside your personal account settings.

things to improve - if food entry was deleted/adjusted catch the change and display correct entries on the redis side.
now it's just stacked appending any entries added.

## Environment Setup

Create a .env file in the project root:

[fatsecret API Configuration (Get these from https://platform.fatsecret.com)](https://platform.fatsecret.com)

```
CONSUMER_KEY=your_fatsecret_consumer_key
CONSUMER_SECRET=your_fatsecret_consumer_secret
CALLBACK_URL="https://oauth.pstmn.io/v1/callback"
OAUTH_SIGNATURE_METHOD="HMAC-SHA1"
OAUTH_VERSION="1.0"

REDIS_URL=your_redis_url
```
For a deeper dive, familiarize yourself with [fatsecret API docs](https://platform.fatsecret.com/docs/guides/authentication/oauth1/three-legged)

## 🔄 How It Works

### Main Script (`main.py`)
- **Authentication** → Handles OAuth flow with FatSecret API  
- **Data Sync** → Fetches historical food entries from a specified start date  
- **Duplicate Detection** → Uses entry fingerprints to avoid duplicates  
- **Redis Storage** → Stores data with date-based keys (`food_entries:YYYY-MM-DD`)  
- **Incremental Updates** → Only updates changed or new entries

### Streamlit Dashboard (`streamlit_app.py`)
- **Real-time Analytics** → Displays current nutritional data  
- **Weight Tracking** → Shows user weight progression  
- **Interactive Interface** → Date-based filtering and visualization  
- **Macro Breakdown** → Detailed nutritional information display

## 🔧 Planned Improvements

### Orchestration System
- Automated scheduled syncs (e.g., every 30 minutes)  
- Retry mechanisms for failed API calls  
- Health monitoring and alerts

### Enhanced Features
- Real-time webhook integration  
- Advanced analytics and trends  
- Export functionality for data (CSV, JSON, PDF)  
- Mobile-responsive design

## 📊 Data Flow
1. **Extract** → OAuth authentication → FatSecret API calls  
2. **Transform** → Deduplication → Date formatting → Nutritional enrichment  
3. **Load** → Redis storage with optimized key structure  
4. **Visualize** → Streamlit dashboard with interactive charts
