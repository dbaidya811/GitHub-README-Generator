import os
import markdown2
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from github_analyzer import GitHubAnalyzer
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Add markdown filter to Jinja2 environment
@app.template_filter('markdown')
def markdown_to_html(markdown_text):
    if not markdown_text:
        return ""
    return markdown2.markdown(markdown_text)
app.secret_key = os.getenv('SECRET_KEY', 'dev-key-for-testing')

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        repo_url = request.form.get('repo_url')
        user_name = request.form.get('user_name')
        user_email = request.form.get('user_email')
        portfolio_url = request.form.get('portfolio_url', '')
        
        if not repo_url:
            flash('Please enter a GitHub repository URL', 'error')
            return redirect(url_for('index'))
        if not user_name:
            flash('Please enter your name', 'error')
            return redirect(url_for('index'))
        if not user_email:
            flash('Please enter your email', 'error')
            return redirect(url_for('index'))
        
        token = request.form.get('github_token') or os.getenv('GITHUB_TOKEN')
        
        # Store in session for result page
        return redirect(url_for('analyze', 
                             repo_url=repo_url, 
                             token=token or '',
                             user_name=user_name,
                             user_email=user_email,
                             portfolio_url=portfolio_url))
    
    return render_template('index.html')

@app.route('/analyze')
def analyze():
    repo_url = request.args.get('repo_url')
    token = request.args.get('token')
    user_name = request.args.get('user_name')
    user_email = request.args.get('user_email')
    portfolio_url = request.args.get('portfolio_url', '')
    
    if not repo_url:
        flash('No repository URL provided', 'error')
        return redirect(url_for('index'))
    
    # Prefer logged-in user's token if available
    if not token:
        token = session.get('gh_token')
    analyzer = GitHubAnalyzer(token=token or None)
    owner, repo_name = analyzer.get_repo_info(repo_url)
    
    if not owner or not repo_name:
        flash('Invalid GitHub repository URL', 'error')
        return redirect(url_for('index'))
    
    try:
        repo_data = analyzer.analyze_repository(owner, repo_name)
        if not repo_data:
            flash('Could not analyze repository', 'error')
            return redirect(url_for('index'))
        
        # Add user information to repo_data
        repo_data['user'] = {
            'name': user_name,
            'email': user_email,
            'portfolio_url': portfolio_url
        }
        
        # Generate the README content (Markdown)
        readme_markdown = analyzer.generate_readme(repo_data)
        
        # Convert markdown to HTML for preview
        readme_html = markdown2.markdown(readme_markdown)
        
        return render_template('result.html', 
                             repo_data=repo_data, 
                             readme_html=readme_html,
                             readme_markdown=readme_markdown,
                             repo_url=repo_url,
                             user_name=user_name,
                             user_email=user_email,
                             portfolio_url=portfolio_url)
    except Exception as e:
        app.logger.error(f"Error analyzing repository: {str(e)}")
        flash(f'Error analyzing repository: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/api/generate', methods=['POST'])
def api_generate():
    data = request.get_json()
    if not data or 'repo_url' not in data:
        return jsonify({'error': 'Missing repository URL'}), 400
    
    repo_url = data['repo_url']
    token = data.get('token') or os.getenv('GITHUB_TOKEN')
    
    analyzer = GitHubAnalyzer(token=token or None)
    owner, repo_name = analyzer.get_repo_info(repo_url)
    
    if not owner or not repo_name:
        return jsonify({'error': 'Invalid GitHub repository URL'}), 400
    
    try:
        repo_data = analyzer.analyze_repository(owner, repo_name)
        if not repo_data:
            return jsonify({'error': 'Could not analyze repository'}), 500
        
        readme_content = analyzer.generate_readme(repo_data)
        return jsonify({
            'success': True,
            'readme': readme_content,
            'repo_data': repo_data
        })
    except Exception as e:
        app.logger.error(f"API Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

# --- GitHub OAuth ---
GITHUB_CLIENT_ID = os.getenv('GITHUB_CLIENT_ID', '')
GITHUB_CLIENT_SECRET = os.getenv('GITHUB_CLIENT_SECRET', '')
GITHUB_OAUTH_CALLBACK = os.getenv('GITHUB_OAUTH_CALLBACK', '')  # e.g., http://localhost:5000/callback

@app.route('/login')
def login():
    if not GITHUB_CLIENT_ID:
        flash('GitHub OAuth not configured. Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET.', 'error')
        return redirect(url_for('index'))
    authorize_url = (
        'https://github.com/login/oauth/authorize'
        f'?client_id={GITHUB_CLIENT_ID}'
        '&scope=repo%20read:user%20user:email'
    )
    return redirect(authorize_url)

@app.route('/callback')
def oauth_callback():
    code = request.args.get('code')
    if not code:
        flash('Login failed: missing code.', 'error')
        return redirect(url_for('index'))
    try:
        # Exchange code for access token
        token_resp = requests.post(
            'https://github.com/login/oauth/access_token',
            headers={'Accept': 'application/json'},
            data={
                'client_id': GITHUB_CLIENT_ID,
                'client_secret': GITHUB_CLIENT_SECRET,
                'code': code,
                'redirect_uri': GITHUB_OAUTH_CALLBACK or None,
            },
            timeout=15
        )
        token_resp.raise_for_status()
        token_json = token_resp.json()
        access_token = token_json.get('access_token')
        if not access_token:
            raise RuntimeError('No access token returned from GitHub')

        # Fetch user
        user_resp = requests.get(
            'https://api.github.com/user',
            headers={'Authorization': f'Bearer {access_token}', 'Accept': 'application/vnd.github+json'},
            timeout=15
        )
        user_resp.raise_for_status()
        user = user_resp.json()

        # Save to session
        session['gh_token'] = access_token
        session['gh_user'] = {
            'login': user.get('login'),
            'name': user.get('name') or user.get('login'),
            'avatar_url': user.get('avatar_url'),
            'html_url': user.get('html_url'),
        }
        flash(f"Logged in as {session['gh_user']['login']}", 'info')
        return redirect(url_for('index'))
    except Exception as e:
        app.logger.error(f"OAuth error: {e}")
        flash(f'GitHub login failed: {e}', 'error')
        return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('gh_token', None)
    session.pop('gh_user', None)
    flash('Logged out of GitHub', 'info')
    return redirect(url_for('index'))

@app.route('/api/me')
def api_me():
    user = session.get('gh_user')
    return jsonify({'authenticated': bool(user), 'user': user})

@app.route('/api/repos')
def api_repos():
    token = session.get('gh_token')
    if not token:
        return jsonify({'error': 'Not authenticated'}), 401
    try:
        repos = []
        page = 1
        while page <= 3:  # fetch up to ~300 repos
            resp = requests.get(
                'https://api.github.com/user/repos',
                headers={'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json'},
                params={'per_page': 100, 'page': page, 'sort': 'updated', 'affiliation': 'owner,collaborator,organization_member'},
                timeout=20
            )
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            for r in batch:
                repos.append({
                    'full_name': r.get('full_name'),
                    'html_url': r.get('html_url'),
                    'name': r.get('name'),
                    'private': r.get('private'),
                    'description': r.get('description'),
                    'language': r.get('language'),
                    'updated_at': r.get('updated_at'),
                })
            page += 1
        return jsonify({'repos': repos})
    except Exception as e:
        app.logger.error(f"Repos API error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/publish', methods=['POST'])
def api_publish():
    token = session.get('gh_token')
    if not token:
        return jsonify({'error': 'Not authenticated with GitHub'}), 401
    data = request.get_json() or {}
    full_name = data.get('full_name')  # e.g., owner/repo
    content = data.get('content')  # markdown string
    message = data.get('message') or 'chore: update README via README Generator'
    path = data.get('path') or 'README.md'
    branch = data.get('branch')  # optional
    if not full_name or not content:
        return jsonify({'error': 'Missing required fields: full_name, content'}), 400
    try:
        # Get current SHA if file exists
        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github+json',
        }
        get_url = f'https://api.github.com/repos/{full_name}/contents/{path}'
        sha = None
        r = requests.get(get_url, headers=headers, timeout=20, params={'ref': branch} if branch else None)
        if r.status_code == 200:
            j = r.json()
            sha = j.get('sha')
            # Avoid no-op commit: compare existing content
            try:
                import base64
                existing = base64.b64decode(j.get('content', '').encode('utf-8')).decode('utf-8')
                if existing.strip() == content.strip():
                    return jsonify({'success': True, 'skipped': True, 'reason': 'No changes'}), 200
            except Exception:
                pass
        elif r.status_code not in (404,):
            r.raise_for_status()

        import base64
        b64_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
        put_body = {
            'message': message,
            'content': b64_content,
        }
        if branch:
            put_body['branch'] = branch
        if sha:
            put_body['sha'] = sha
        put_url = get_url
        pr = requests.put(put_url, headers=headers, json=put_body, timeout=30)
        if not pr.ok:
            try:
                err = pr.json()
                return jsonify({'error': err.get('message') or 'GitHub API error', 'details': err}), pr.status_code
            except Exception:
                pr.raise_for_status()
        resp = pr.json()
        return jsonify({'success': True, 'content': resp.get('content'), 'commit': resp.get('commit')})
    except Exception as e:
        app.logger.error(f"Publish API error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
