import os
import markdown2
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from github_analyzer import GitHubAnalyzer
from dotenv import load_dotenv

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
        
        # Generate the README content
        readme_content = analyzer.generate_readme(repo_data)
        
        # Convert markdown to HTML
        readme_html = markdown2.markdown(readme_content)
        
        return render_template('result.html', 
                             repo_data=repo_data, 
                             readme_content=readme_html,
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

if __name__ == '__main__':
    app.run(debug=True)
