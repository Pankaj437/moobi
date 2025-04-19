import json
import time
import random
import requests
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

# === 🔐 Your 5 Google API Keys ===
pankaj = [
    "AIzaSyB5eimsAwDtfcl6ai6uLV16-UvX0W381ec",
    "AIzaSyBjQ-NSJGjZXulsyKk5IyAeniTYBaPucA8",
    "AIzaSyCr2yy_egb6vhPEj1IHeeE7XsaIsSvCQDM",
    "AIzaSyCeg73BEreaO-Qkccf0DsBpRQAGfeHuDLQ",
    "AIzaSyAFS-nok1taW4lC8Sy5EDSNggEFTzQWzcs",
]

# === 📁 Load News Links from JSON ===
NEWS_FILE = "news.json"

# === ✍️ Prompt to Use ===
PROMPT = """Given the following list of article titles from news.json, identify the 5 positve and 5 negative titles based on their relevance to the Financial Services Industry (FSI). For each title, provide the title, its associated link, and a brief explanation of why it was selected as best or worst. The best titles should focus on FSI topics like company acquisitions, IPOs, regulatory approvals, stock performance, or financial innovations. The worst titles should be least relevant to FSI, such as non-financial topics or vague content. Format the response as:
**5 Best Titles:**
1. Title: [Title]
   Link: [Link]
   Reason: [Explanation]
...
**5 Worst Titles:**
1. Title: [Title]
   Link: [Link]
   Reason: [Explanation]
...
Here are the titles:
{title_list}"""

# === 📂 Output PDF File ===
OUTPUT_PDF = "all_summaries.pdf"

# === 🧠 Headers for API Requests ===
def get_random_headers():
    # Static Firefox User-Agents
    firefox_user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:128.0) Gecko/20100101 Firefox/128.0",
        "Mozilla/5.0 (X11; Linux x86_64; rv:127.0) Gecko/20100101 Firefox/127.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0",
    ]

    user_agent = random.choice(firefox_user_agents)
    return {
        'User-Agent': user_agent,
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }

# === 🚀 Send to Gemini ===
def send_to_gemini(title_list, api_key):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    headers = get_random_headers()
    formatted_titles = "\n".join([f"- Title: {news['title']}\n  Link: {news['link']}" for news in title_list])
    data = {
        "contents": [{
            "parts": [{"text": PROMPT.format(title_list=formatted_titles)}]
        }]
    }

    try:
        res = requests.post(url, headers=headers, json=data, timeout=30)
        res.raise_for_status()
        content = res.json()
        return content['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        print("❌ Gemini API Error:", e)
        return None

# === 📄 Save to PDF ===
def save_to_pdf(summary):
    # Define PDF path in the current directory
    pdf_path = Path(OUTPUT_PDF)

    # Create PDF
    doc = SimpleDocTemplate(str(pdf_path), pagesize=letter)
    styles = getSampleStyleSheet()
    flowables = []

    # Add main title
    flowables.append(Paragraph("FSI Article Title Rankings", styles['Title']))
    flowables.append(Spacer(1, 0.2 * inch))

    # Add summary
    flowables.append(Paragraph("analyse top 2 positive and top 2 negative article from these", styles['Heading2']))
    flowables.append(Spacer(1, 0.1 * inch))
    formatted_summary = summary.replace('\n', '<br/>')
    flowables.append(Paragraph(formatted_summary, styles['BodyText']))
    flowables.append(Spacer(1, 0.2 * inch))

    # Build PDF
    doc.build(flowables)
    print(f"✅ Saved rankings to PDF: {pdf_path}")

# === 📊 Main Flow ===
def main():
    if not Path(NEWS_FILE).exists():
        print(f"❌ File not found: {NEWS_FILE}")
        return

    with open(NEWS_FILE, 'r', encoding='utf-8') as f:
        news_list = json.load(f)

    total_articles = len(news_list)
    if total_articles < 10:
        print(f"❌ Not enough titles ({total_articles}), need at least 10.")
        return

    print(f"📦 Total Articles: {total_articles}")
    
    all_summaries = ""
    batch_size = 50
    num_batches = (total_articles + batch_size - 1) // batch_size

    for i in range(num_batches):
        start = i * batch_size
        end = min((i + 1) * batch_size, total_articles)
        title_batch = news_list[start:end]

        if len(title_batch) < 10:
            print(f"⏩ Skipping batch {i+1}, not enough titles ({len(title_batch)})")
            continue

        api_key = pankaj[i % len(pankaj)]
        print(f"\n📤 Sending batch {i+1}/{num_batches} (Articles {start+1}-{end}) using API Key #{(i % len(GEMINI_API_KEYS)) + 1}")
        
        summary = send_to_gemini(title_batch, api_key)
        if summary:
            all_summaries += f"\n\n=== Batch {i+1} Summary ===\n\n" + summary
        else:
            all_summaries += f"\n\n=== Batch {i+1} Summary ===\n\n❌ Failed to get summary."

        # Optional: Wait between requests to avoid rate limits
        time.sleep(1.5)

    if all_summaries.strip():
        save_to_pdf(all_summaries)
    else:
        print("❌ No summaries generated.")
if __name__ == "__main__":
    main()
