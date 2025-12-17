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
# Secrets from GitHub Environment
EMAIL_USER = os.environ.get('EMAIL_USER')
EMAIL_PASS = os.environ.get('EMAIL_PASS')
EMAIL_RECEIVER = os.environ.get('EMAIL_RECEIVER')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# Configure AI
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def get_latest_linkfest_url():
    """Finds the latest 'Linkfest' post from the homepage."""
    try:
        response = requests.get(SOURCE_URL)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all article links
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
        
        # The content is usually in a div class 'entry-content' or 'post-content'
        content_div = soup.find('div', class_='entry-content')
        
        if content_div:
            for p in content_div.find_all('p'):
                # Look for links inside paragraphs (ignoring share buttons, etc)
                a_tag = p.find('a')
                if a_tag and a_tag['href']:
                    href = a_tag['href']
                    # Filter out internal links or social share links
                    if "alphaideas.in" not in href and "facebook.com" not in href and "twitter.com" not in href:
                        links_to_summarize.append({
                            'title': p.get_text().strip(),
                            'url': href
                        })
    except Exception as e:
        print(f"Error extracting links: {e}")
    return links_to_summarize

def summarize_article(url):
    """Fetches article text and asks AI to summarize it."""
    try:
        # 1. Fetch Article Content
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract text (simple approach: grab all paragraphs)
        paragraphs = [p.get_text() for p in soup.find_all('p')]
        full_text = " ".join(paragraphs)[:10000] # Limit text to avoid token limits
        
        if len(full_text) < 200:
            return "Could not extract enough text to summarize."

        # 2. Ask AI to summarize
        prompt = f"""
        Read the following news article text and provide a 2-sentence executive summary.
        Focus on the key facts and numbers.
        
        Article Text:
        {full_text}
        """
        response = model.generate_content(prompt)
        return response.text.strip()
        
    except Exception as e:
        return f"Error reading article: {e}"

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

if __name__ == "__main__":
    print("Starting Daily Brief...")
    
    # 1. Find the post
    linkfest_url = get_latest_linkfest_url()
    if not linkfest_url:
        print("No Linkfest found today.")
        exit()
        
    print(f"Found Linkfest: {linkfest_url}")
    
    # 2. Get the links
    articles = extract_article_links(linkfest_url)
    print(f"Found {len(articles)} articles. Summarizing (this may take a moment)...")
    
    # 3. Generate Summaries
    email_content = f"<h2>Daily Brief: {datetime.date.today()}</h2>"
    email_content += f"<p>Source: <a href='{linkfest_url}'>Alpha Ideas Linkfest</a></p><hr>"
    
    for article in articles[:10]: # Limit to top 10 to save time/tokens
        print(f"Processing: {article['title']}")
        summary = summarize_article(article['url'])
        
        email_content += f"<h3>{article['title']}</h3>"
        email_content += f"<p><i>Summary:</i> {summary}</p>"
        email_content += f"<p><a href='{article['url']}'>Read Original Article</a></p><br>"
        
        # Sleep briefly to be polite to the API
        time.sleep(2)

    # 4. Send Email
    send_email(email_content)
