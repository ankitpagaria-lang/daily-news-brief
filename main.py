import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import datetime
import google.generativeai as genai
import time

# --- CONFIGURATION ---
SOURCE_URL = "https://alphaideas.in/"
EMAIL_USER = os.environ.get('EMAIL_USER')
EMAIL_PASS = os.environ.get('EMAIL_PASS')
EMAIL_RECEIVER = os.environ.get('EMAIL_RECEIVER')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# Configure AI
genai.configure(api_key=GEMINI_API_KEY)

# --- ROBUST AI FUNCTIONS ---

def get_working_summary(full_text):
    """
    Tries multiple models in order of preference until one works.
    """
    # 1. List of preferred models to try (Fastest -> Strongest -> Legacy)
    priority_models = [
        'gemini-1.5-flash',
        'gemini-1.5-pro',
        'gemini-pro',
        'gemini-1.0-pro'
    ]

    prompt = f"""
    Read the following news article text and provide a 2-sentence executive summary.
    Focus on the key facts and numbers.
    
    Article Text:
    {full_text}
    """

    # 2. Try the priority list
    for model_name in priority_models:
        try:
            # print(f"Trying model: {model_name}...") # Uncomment for debugging
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            # print(f"Model {model_name} failed: {e}")
            continue # Try the next one in the list

    # 3. If all specific names fail, ask the API what is available
    try:
        print("Standard models failed. Checking available API models...")
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                try:
                    model = genai.GenerativeModel(m.name)
                    response = model.generate_content(prompt)
                    return response.text.strip()
                except:
                    continue
    except Exception as e:
        print(f"Dynamic model search failed: {e}")

    return "Summary unavailable (All AI models failed to respond)."


# --- WEBSCRAPING FUNCTIONS ---

def get_latest_linkfest_url():
    """Finds the latest 'Linkfest' post from the homepage."""
    try:
        response = requests.get(SOURCE_URL)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        for link in soup.find_all('a'):
            text = link.get_text()
            if "Linkfest" in text and "Continue reading" not in text:
                return link['href']
    except Exception as e:
        print(f"Error finding Linkfest: {e}")
    return None

def extract_article_links(post_url):
    """Extracts external news links from the specific Linkfest post."""
    links_to_summarize = []
    try:
        response = requests.get(post_url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        content_div = soup.find('div', class_='entry-content')
        
        if content_div:
            for p in content_div.find_all('p'):
                a_tag = p.find('a')
                if a_tag and a_tag['href']:
                    href = a_tag['href']
                    # Filter out internal/social links
                    if "alphaideas.in" not in href and "facebook.com" not in href and "twitter.com" not in href:
                        links_to_summarize.append({
                            'title': p.get_text().strip(),
                            'url': href
                        })
    except Exception as e:
        print(f"Error extracting links: {e}")
    return links_to_summarize

def fetch_article_text(url):
    """Fetches text from a URL."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        paragraphs = [p.get_text() for p in soup.find_all('p')]
        text = " ".join(paragraphs)[:10000] # Limit size
        return text
    except:
        return ""

def send_email(summary_html):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_USER
    msg['To'] = EMAIL_RECEIVER
    msg['Subject'] = f"Alpha Ideas Daily Brief - {datetime.date.today()}"
    msg.attach(MIMEText(summary_html, 'html'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, EMAIL_RECEIVER, msg.as_string())
        server.quit()
        print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    print("Starting Daily Brief...")
    
    linkfest_url = get_latest_linkfest_url()
    if not linkfest_url:
        print("No Linkfest found today.")
        exit()
        
    print(f"Found Linkfest: {linkfest_url}")
    articles = extract_article_links(linkfest_url)
    print(f"Found {len(articles)} articles.")
    
    email_content = f"<h2>Daily Brief: {datetime.date.today()}</h2>"
    email_content += f"<p>Source: <a href='{linkfest_url}'>Alpha Ideas Linkfest</a></p><hr>"
    
    # Process up to 10 articles
    for article in articles[:10]:
        print(f"Processing: {article['title']}")
        
        # 1. Get Text
        full_text = fetch_article_text(article['url'])
        
        if len(full_text) < 200:
            summary = "Could not extract text (Site might block bots or be empty)."
        else:
            # 2. Get Summary (Using Robust Fail-Proof Logic)
            summary = get_working_summary(full_text)
        
        email_content += f"<h3>{article['title']}</h3>"
        email_content += f"<p><i>Summary:</i> {summary}</p>"
        email_content += f"<p><a href='{article['url']}'>Read Original Article</a></p><br>"
        
        time.sleep(1) # Polite delay

    send_email(email_content)
