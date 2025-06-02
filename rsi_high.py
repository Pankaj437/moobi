import requests
import csv
import io
import smtplib
import os
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get environment variables
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASS = os.getenv('EMAIL_PASS')
EMAIL_TO = os.getenv('EMAIL_TO', 'reeeportnews@gmail.com')

# Validate environment variables
if not EMAIL_USER or not EMAIL_PASS:
    logger.error("EMAIL_USER or EMAIL_PASS is not set in environment variables.")
    exit(1)

def scan_stocks():
    """Perform HTTP request to scan stocks using TradingView API."""
    url = "https://scanner.tradingview.com/india/scan?label-product=screener-stock"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Referer": "https://www.tradingview.com/",
        "Content-Type": "text/plain;charset=UTF-8",
        "Origin": "https://www.tradingview.com",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "Priority": "u=0"
    }
    payload = {
        "columns": ["name", "description", "logoid", "update_mode", "type", "typespecs", "close", "pricescale", "minmov", "fractional", "minmove2", "currency", "change", "volume", "relative_volume_10d_calc", "market_cap_basic", "fundamental_currency_code", "price_earnings_ttm", "earnings_per_share_diluted_ttm", "earnings_per_share_diluted_yoy_growth_ttm", "dividends_yield_current", "sector.tr", "market", "sector", "recommendation_mark", "exchange"],
        "filter": [{"left": "is_blacklisted", "operation": "equal", "right": False}, {"left": "RSI", "operation": "greater", "right": 82}],
        "ignore_unknown_fields": False,
        "options": {"lang": "en"},
        "range": [0, 100],
        "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"},
        "symbols": {"symbolset": ["SYML:NSE;CNX500"]},
        "markets": ["india"],
        "filter2": {
            "operator": "and",
            "operands": [
                {"operation": {"operator": "or", "operands": [
                    {"operation": {"operator": "and", "operands": [{"expression": {"left": "type", "operation": "equal", "right": "stock"}}, {"expression": {"left": "typespecs", "operation": "has", "right": ["common"]}}]}},
                    {"operation": {"operator": "and", "operands": [{"expression": {"left": "type", "operation": "equal", "right": "stock"}}, {"expression": {"left": "typespecs", "operation": "has", "right": ["preferred"]}}]}},
                    {"operation": {"operator": "and", "operands": [{"expression": {"left": "type", "operation": "equal", "right": "dr"}}]}},
                    {"operation": {"operator": "and", "operands": [{"expression": {"left": "type", "operation": "equal", "right": "fund"}}, {"expression": {"left": "typespecs", "operation": "has_none_of", "right": ["etf"]}}]}}
                ]}}
            ]
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"HTTP Error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"Error in scan_stocks: {e}")
        return None

def stocks_to_csv(stocks_data):
    """Convert stock data to CSV string."""
    fieldnames = ["Symbol", "Company Name", "Close", "RSI", "Sector", "Market Cap", "Currency", "P/E Ratio"]
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(fieldnames)
    
    for stock in stocks_data:
        row = [
            stock.get("s", ""),  # Symbol
            stock.get("d", [])[1] if len(stock.get("d", [])) > 1 else "",  # Company Name
            stock.get("d", [])[6] if len(stock.get("d", [])) > 6 else "",  # Close
            "higher 80",  # RSI placeholder
            stock.get("d", [])[21] if len(stock.get("d", [])) > 21 else "",  # Sector
            stock.get("d", [])[15] if len(stock.get("d", [])) > 15 else "",  # Market Cap
            stock.get("d", [])[11] if len(stock.get("d", [])) > 11 else "",  # Currency
            stock.get("d", [])[17] if len(stock.get("d", [])) > 17 else ""   # P/E Ratio
        ]
        writer.writerow(row)
    
    csv_content = output.getvalue()
    output.close()
    return csv_content

def send_email(csv_content, stock_count, error_message=None):
    """Send email with CSV attachment or error message."""
    msg = MIMEMultipart()
    msg['From'] = EMAIL_USER
    msg['To'] = EMAIL_TO
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    if error_message:
        msg['Subject'] = f"high RSI Stocks Report - Error - {date_str}"
        body = f"""Dear Recipient,

Failed to scan stocks for RSI < 30 on {date_str}.
Error: {error_message}

Please check the logs for details.

Best regards,
Automated Data Service
"""
        msg.attach(MIMEText(body, 'plain'))
    else:
        msg['Subject'] = f"high RSI Stocks Report - {date_str}"
        body = f"""Dear Recipient,

Attached is the CSV file containing {stock_count} stocks with RSI < 30 for {date_str}.
Please review the attachment for details.

Best regards,
Automated Data Service
"""
        msg.attach(MIMEText(body, 'plain'))
        if stock_count > 0:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(csv_content.encode('utf-8'))
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', 'attachment; filename="low_rsi_stocks.csv"')
            msg.attach(part)
            logger.info("CSV attachment prepared")

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_USER, EMAIL_TO, msg.as_string())
        logger.info(f"Email sent successfully to {EMAIL_TO}" + (f" with {stock_count} stocks" if stock_count > 0 else " without attachment"))
    except Exception as e:
        logger.error(f"Email sending failed: {e}")

def main():
    """Main function to scan stocks and send email."""
    response_json = scan_stocks()
    if response_json and "data" in response_json:
        stocks = response_json.get("data", [])
        if stocks:
            logger.info(f"Found {len(stocks)} stocks with RSI < 30: {[stock['s'] for stock in stocks]}")
            csv_content = stocks_to_csv(stocks)
            send_email(csv_content, len(stocks))
        else:
            logger.info("No stocks found with RSI < 30")
            send_email(None, 0, "No stocks with RSI < 82 found")
    else:
        error_message = "Scan failed or returned no data"
        logger.error(error_message)
        if response_json:
            logger.error(f"Response: {response_json}")
        send_email(None, 0, error_message)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        send_email(None, 0, f"Fatal error: {e}")
        exit(1)
