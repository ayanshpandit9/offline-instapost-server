from flask import Flask, request, render_template_string, redirect, url_for, session
from instagrapi import Client
import random
import requests
import time
import os
import json
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

# HTML templates
MAIN_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Instagram Auto Comment Bot</title>
    <style>
        body { font-family: Arial, sans-serif; background-color: #f0f0f0; text-align: center; padding: 50px; }
        .container { max-width: 400px; margin: auto; background: white; padding: 20px; border-radius: 10px; }
        input, button { margin: 10px; padding: 10px; width: 80%; }
        button { background-color: #4CAF50; color: white; border: none; cursor: pointer; }
        button:hover { background-color: #45a049; }
        .success { color: green; }
        .error { color: red; }
    </style>
</head>
<body>
    <div class="container">
        <h2>Instagram Auto Comment Bot</h2>
        <p>Developer: Your Name | Version: 1.0 | Date: {{ date }}</p>
        <form method="post" action="/comment" enctype="multipart/form-data">
            <input type="file" name="cookies_file" accept=".json" required placeholder="Upload cookies.json"><br>
            <input type="text" name="post_url" placeholder="Instagram Post URL (e.g., https://www.instagram.com/p/POST_CODE/)" required><br>
            <input type="number" name="delay" placeholder="Delay between comments (seconds)" min="1" required><br>
            <input type="text" name="prefix" placeholder="Prefix for comments (e.g., Hello Akash)" required><br>
            <input type="file" name="comment_file" accept=".txt" required placeholder="Upload comments.txt"><br>
            <button type="submit">Start Commenting</button>
        </form>
        {% if message %}
        <p class="{{ message_type }}">{{ message }}</p>
        {% endif %}
    </div>
</body>
</html>
"""

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

# Convert Instagram post URL to media ID
def get_media_id(post_url, client):
    try:
        shortcode = post_url.split('/p/')[1].split('/')[0]
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

    # Save and read cookies file
    if cookies_file:
        cookies_file.save('cookies.json')
        try:
            with open('cookies.json', 'r') as f:
                cookies = json.load(f)
        except Exception as e:
            return render_template_string(MAIN_PAGE, message=f"Invalid cookies file: {str(e)}", message_type="error", date=datetime.now().strftime('%d-%m-%Y'))
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
        cl.load_settings_dict({"cookies": cookies})
        cl.login_by_sessionid(cookies.get('sessionid', ''))
    except Exception as e:
        return render_template_string(MAIN_PAGE, message=f"Login failed: {str(e)}", message_type="error", date=datetime.now().strftime('%d-%m-%Y'))

    # Get media ID from URL
    media_id = get_media_id(post_url, cl)
    if not media_id:
        return render_template_string(MAIN_PAGE, message="Invalid post URL or unable to fetch media ID", message_type="error", date=datetime.now().strftime('%d-%m-%Y'))

    # Post comments with delay
    with ThreadPool(max_workers=5) as pool:
        for comment in comments:
            pool.submit(post_comment, media_id, comment, cl, prefix)
            time.sleep(delay)

    message = f"Finished! Total Successful Comments: {len(successfull)}"
    return render_template_string(MAIN_PAGE, message=message, message_type="success", date=datetime.now().strftime('%d-%m-%Y'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=True)
