from flask import Flask, request, render_template_string
from instagrapi import Client
import random
import requests
import time
import os
from concurrent.futures import ThreadPoolExecutor as ThreadPool
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key')  # Use environment variable for security

# Color codes (for terminal output during testing)
G = '\x1b[1;92m'  # Green
W = '\x1b[0;97m'  # White
Y = '\x1b[1;93m'  # Yellow
B = '\x1b[1;90m'   # Black
x = f'{G}➤{W}➤'
xy1 = f'{G}•{W}•'
xy = f'{G}━{W}➤'

# Modern HTML template for single form
MAIN_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Instagram Auto Comment Bot</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Segoe UI', Arial, sans-serif;
        }
        body {
            background: linear-gradient(135deg, #833ab4, #fd1d1d, #fcb045);
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            background: white;
            max-width: 500px;
            width: 100%;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 8px 16px rgba(0, 0, 0, 0.2);
        }
        h2 {
            color: #333;
            text-align: center;
            margin-bottom: 10px;
        }
        .info {
            color: #555;
            text-align: center;
            margin-bottom: 20px;
            font-size: 0.9em;
        }
        form {
            display: flex;
            flex-direction: column;
            gap: 15px;
        }
        input[type="file"], input[type="text"], input[type="number"] {
            padding: 12px;
            border: 1px solid #ddd;
            border-radius: 8px;
            font-size: 1em;
            transition: border-color 0.3s;
        }
        input[type="file"]:focus, input[type="text"]:focus, input[type="number"]:focus {
            border-color: #4CAF50;
            outline: none;
        }
        button {
            padding: 12px;
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 1.1em;
            cursor: pointer;
            transition: background-color 0.3s;
        }
        button:hover {
            background-color: #45a049;
        }
        .success {
            color: #4CAF50;
            text-align: center;
            margin-top: 15px;
            font-weight: bold;
        }
        .error {
            color: #e74c3c;
            text-align: center;
            margin-top: 15px;
            font-weight: bold;
        }
        @media (max-width: 600px) {
            .container {
                padding: 20px;
            }
            input, button {
                font-size: 0.9em;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h2>Instagram Auto Comment Bot</h2>
        <p class="info">Developer: Your Name | Version: 1.0 | Date: {{ date }}</p>
        <form method="post" action="/comment" enctype="multipart/form-data">
            <input type="file" name="cookies_file" accept=".txt" required placeholder="Upload cookies.txt (e.g., sessionid=abc)">
            <input type="text" name="post_url" placeholder="Instagram Post/Reel URL (e.g., https://www.instagram.com/reel/POST_CODE/)" required>
            <input type="number" name="delay" placeholder="Delay between comments (seconds)" min="1" required>
            <input type="text" name="prefix" placeholder="Prefix for comments (e.g., Hello Akash)" required>
            <input type="file" name="comment_file" accept=".txt" required placeholder="Upload comments.txt">
            <button type="submit">Start Commenting</button>
        </form>
        {% if message %}
        <p class="{{ message_type }}">{{ message }}</p>
        {% endif %}
    </div>
</body>
</html>
"""

# Parse raw cookies from text file
def parse_cookies(cookies_text):
    cookies = {}
    try:
        # Split cookies by semicolon
        for cookie in cookies_text.split(';'):
            if '=' in cookie:
                name, value = cookie.strip().split('=', 1)
                cookies[name] = value
        return cookies
    except Exception as e:
        print(f"{Y}Error parsing cookies: {e}")
        return None

# Fetch proxies
def fetch_proxies():
    try:
        prox = requests.get('https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all').text
        with open('proxies.txt', 'w') as f:
            f.write(prox)
        return prox.splitlines()
    except:
        try:
            with open('proxies.txt', 'r') as f:
                return f.read().splitlines()
        except:
            print(f"{Y}Failed to fetch or read proxies")
            return []

# Generate random user agent
def generate_user_agent():
    devices = [
        'Instagram 194.0.0.36.172 Android (29/10; 480dpi; 1080x2340; Samsung; SM-G975F; beyond2; exynos9820; en_US)',
        'Instagram 202.0.0.37.123 Android (30/11; 320dpi; 720x1440; Xiaomi; MI 8; dipper; qcom; en_US)',
        'Mozilla/5.0 (Linux; Android 10; SM-A205U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36'
    ]
    return random.choice(devices)

# Convert Instagram post/reel URL to media ID
def get_media_id(post_url, client):
    try:
        # Handle both /p/ and /reel/ URLs
        if '/reel/' in post_url:
            shortcode = post_url.split('/reel/')[1].split('/')[0].split('?')[0]
        else:
            shortcode = post_url.split('/p/')[1].split('/')[0].split('?')[0]
        media_id = client.media_id(client.media_pk_from_url(post_url))
        return media_id
    except Exception as e:
        print(f"{Y}Error fetching media ID: {e}")
        return None

# Post comment on Instagram
successfull = []
def post_comment(media_id, comment_text, client, prefix):
    try:
        # Add prefix to comment
        final_comment = f"{prefix}, {comment_text}" if prefix else comment_text
        client.media_comment(media_id, final_comment)
        result = f"[COMMENT-OK] Media ID: {media_id} | Comment: {final_comment}"
        print(f"{xy1}{G} {result}")
        with open('comments_ok.txt', 'a') as f:
            f.write(f"{result}\n")
        successfull.append(result)
        return result
    except Exception as e:
        print(f"{xy1}{Y} Error with Media ID {media_id}: {e}")
        return None

# Routes
@app.route('/')
def index():
    return render_template_string(MAIN_PAGE, date=datetime.now().strftime('%d-%m-%Y'))

@app.route('/comment', methods=['POST'])
def comment():
    cookies_file = request.files.get('cookies_file')
    post_url = request.form.get('post_url')
    delay = int(request.form.get('delay', 1))
    prefix = request.form.get('prefix')
    comment_file = request.files.get('comment_file')

    # Save and parse cookies file
    if cookies_file:
        cookies_file.save('cookies.txt')
        try:
            with open('cookies.txt', 'r') as f:
                cookies_text = f.read().strip()
            cookies = parse_cookies(cookies_text)
            if not cookies or 'sessionid' not in cookies:
                return render_template_string(MAIN_PAGE, message="Invalid cookies file or missing sessionid", message_type="error", date=datetime.now().strftime('%d-%m-%Y'))
        except Exception as e:
            return render_template_string(MAIN_PAGE, message=f"Error reading cookies file: {str(e)}", message_type="error", date=datetime.now().strftime('%d-%m-%Y'))
    else:
        return render_template_string(MAIN_PAGE, message="No cookies file uploaded", message_type="error", date=datetime.now().strftime('%d-%m-%Y'))

    # Save and read comment file
    if comment_file:
        comment_file.save('comments.txt')
        with open('comments.txt', 'r') as f:
            comments = [line.strip() for line in f if line.strip()]
    else:
        return render_template_string(MAIN_PAGE, message="No comment file uploaded", message_type="error", date=datetime.now().strftime('%d-%m-%Y'))

    # Initialize instagrapi client with cookies
    try:
        cl = Client()
        cl.set_user_agent(generate_user_agent())
        proxies = random.choice(fetch_proxies()) if fetch_proxies() else None
        if proxies:
            cl.set_proxy(f"http://{proxies}")
        # Use login_by_session for cookies-based login
        cl.login_by_session(cookies.get('sessionid', ''))
        # Verify login by fetching user info
        cl.get_timeline_feed()  # This will raise an exception if login fails
    except Exception as e:
        return render_template_string(MAIN_PAGE, message=f"Login failed: {str(e)}", message_type="error", date=datetime.now().strftime('%d-%m-%Y'))

    # Get media ID from URL
    media_id = get_media_id(post_url, cl)
    if not media_id:
        return render_template_string(MAIN_PAGE, message="Invalid post/reel URL or unable to fetch media ID", message_type="error", date=datetime.now().strftime('%d-%m-%Y'))

    # Post comments with delay
    with ThreadPool(max_workers=5) as pool:
        for comment in comments:
            pool.submit(post_comment, media_id, comment, cl, prefix)
            time.sleep(delay)

    message = f"Finished! Total Successful Comments: {len(successfull)}"
    return render_template_string(MAIN_PAGE, message=message, message_type="success", date=datetime.now().strftime('%d-%m-%Y'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=True)
