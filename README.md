# calorista

ETL pipeline for authenticated FatSecret users that extracts real-time food log data, transforms raw entries with detailed nutritional metadata.

## 🔑 API Access

To use this project, you must [register your application with FatSecret](https://platform.fatsecret.com/api/Default.aspx?screen=rapiintro) and obtain your own **API Key** and **API Secret**. This is required to authenticate users and access their food log data via the FatSecret Platform API.

Store your credentials in a `.env` file or environment variables:

```env
FATSECRET_CONSUMER_KEY=your_api_key_here  
FATSECRET_CONSUMER_SECRET=your_api_secret_here
