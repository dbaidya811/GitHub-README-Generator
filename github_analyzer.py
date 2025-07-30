import os
import sys
import requests
from github import Github, GithubException
from datetime import datetime
import markdown2
import re
from urllib.parse import urlparse, unquote
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class GitHubAnalyzer:
    def __init__(self, token=None):
        """Initialize GitHub client with token if provided"""
        self.token = token or os.getenv('GITHUB_TOKEN')
        if not self.token:
            print("Warning: No GitHub token provided. You may hit rate limits.")
        self.g = Github(self.token) if self.token else Github()
    
    def get_repo_info(self, repo_url):
        """Extract repository information from URL"""
        try:
            # Handle different GitHub URL formats
            parsed = urlparse(repo_url)
            if parsed.netloc != 'github.com':
                raise ValueError("Only GitHub repository URLs are supported")
                
            # Extract path and clean it up
            path = parsed.path.strip('/')
            path = re.sub(r'\.git$', '', path)  # Remove .git if present
            
            # Split into parts
            parts = path.split('/')
            if len(parts) < 2:
                raise ValueError("Invalid GitHub repository URL format")
                
            owner = parts[0]
            repo_name = parts[1]
            
            # Clean up the repository name (remove any query parameters or fragments)
            repo_name = repo_name.split('?')[0].split('#')[0]
            
            return owner, repo_name
            
        except Exception as e:
            print(f"Error parsing repository URL: {e}")
            return None, None
    
    def analyze_repository(self, owner, repo_name):
        """Analyze GitHub repository and return metadata"""
        try:
            repo = self.g.get_repo(f"{owner}/{repo_name}")
            
            # Get basic repository information
            repo_data = {
                'name': repo.name,
                'full_name': repo.full_name,
                'description': repo.description or 'No description provided',
                'url': repo.html_url,
                'created_at': repo.created_at,
                'updated_at': repo.updated_at,
                'language': repo.language,
                'forks_count': repo.forks_count,
                'stargazers_count': repo.stargazers_count,
                'open_issues_count': repo.open_issues_count,
                'license': None,
                'topics': [],
                'readme': None,
                'contributors': [],
                'languages': {},
                'releases': []
            }
            
            # Get license information safely
            try:
                if repo.license:
                    repo_data['license'] = repo.get_license().license.name
            except:
                pass
                
            # Get topics safely
            try:
                repo_data['topics'] = repo.get_topics()
            except:
                pass
            
            # Get README content safely
            try:
                readme = repo.get_readme()
                repo_data['readme'] = markdown2.markdown(readme.decoded_content.decode('utf-8', errors='replace'))
            except Exception as e:
                print(f"Could not fetch README: {e}")
                repo_data['readme'] = "No README found"
            
            # Get contributors (first 5) safely
            try:
                contributors = list(repo.get_contributors())[:5]  # Limit to first 5 contributors
                repo_data['contributors'] = [{
                    'login': c.login,
                    'url': c.html_url,
                    'contributions': c.contributions
                } for c in contributors]
            except Exception as e:
                print(f"Could not fetch contributors: {e}")
            
            # Get languages safely
            try:
                repo_data['languages'] = repo.get_languages()
            except Exception as e:
                print(f"Could not fetch languages: {e}")
            
            # Get releases (first 3) safely
            try:
                releases = list(repo.get_releases())[:3]  # Get latest 3 releases
                repo_data['releases'] = [{
                    'tag_name': r.tag_name,
                    'name': r.name or r.tag_name,
                    'published_at': r.published_at or r.created_at,
                    'body': (r.body[:200] + '...') if r.body else ''
                } for r in releases if hasattr(r, 'tag_name')]
            except Exception as e:
                print(f"Could not fetch releases: {e}")
                
            return repo_data
            
        except Exception as e:
            print(f"Error analyzing repository: {e}")
            return None
    
    def generate_readme(self, repo_data):
        """Generate a comprehensive README.md file based on repository data"""
        if not repo_data:
            return "# Error: Could not generate README - No repository data provided"
        
        # Get user information or use defaults
        user_data = repo_data.get('user', {})
        user_name = user_data.get('name', 'Your Name')
        user_email = user_data.get('email', 'your.email@example.com')
        portfolio_url = user_data.get('portfolio_url', '')
        
        # Initialize README with project title
        project_name = repo_data.get('name', 'My Project')
        readme = f"# {project_name}\n\n"
        
        # Add badges
        badges = []
        if repo_data.get('license'):
            license_badge = repo_data['license'].replace(' ', '%20')
            badges.append(f"![License](https://img.shields.io/badge/license-{license_badge}-blue)")
        if repo_data.get('language'):
            badges.append(f"![Language](https://img.shields.io/badge/language-{repo_data['language']}-blueviolet)")
        if 'stargazers_count' in repo_data:
            badges.append(f"![Stars](https://img.shields.io/github/stars/{repo_data['full_name']}?style=social)")
        if 'forks_count' in repo_data:
            badges.append(f"![Forks](https://img.shields.io/github/forks/{repo_data['full_name']}?style=social)")
        
        # Add badges (stars, license, etc.) if available
        if badges:
            readme += ' '.join(badges) + '\n\n'
        
        # Table of Contents
        readme += "## 📋 Table of Contents\n"
        sections = [
            ("Features", "#-features"),
            ("Getting Started", "#-getting-started"),
            ("Prerequisites", "#prerequisites"),
            ("Installation", "#installation"),
            ("Usage", "#-usage"),
            ("Tech Stack", "#-tech-stack"),
            ("Contributing", "#-contributing"),
            ("License", "#-license"),
            ("Contact", "#-contact")
        ]
        
        for section, link in sections:
            readme += f"- [{section}]({link})\n"
        readme += "\n"
        
        # Features
        readme += "## ✨ Key Features\n\n"
        if repo_data.get('topics') and len(repo_data['topics']) > 0:
            # Use repository topics as features
            features = []
            for topic in repo_data['topics'][:5]:  # Limit to first 5 topics
                # Convert topic to readable format (e.g., "machine-learning" -> "Machine Learning")
                feature_name = ' '.join(word.capitalize() for word in topic.split('-'))
                features.append(feature_name)
        else:
            # Default features if no topics available
            features = [
                "Modern UI: Clean and intuitive user interface",
                "Responsive Design: Works on all devices and screen sizes",
                "Easy Setup: Simple installation and configuration process"
            ]
        
        for feature in features:
            if ":" in feature:
                # If feature is already in "Label: Description" format
                label, desc = feature.split(":", 1)
                readme += f"- ✅ **{label.strip()}**:{desc.strip()}\n"
            else:
                # If just a topic name, format it as a feature
                readme += f"- ✅ **{feature}**: Core functionality for {feature.lower()}.\n"
        readme += "\n"
        
        # Demo / Screenshots (after features)
        readme += "## 🎥 Demo / Screenshots\n\n"
        readme += "```markdown\n"
        readme += "<!-- Add your screenshots here -->\n"
        readme += "![Screenshot 1](screenshots/screenshot1.png)\n"
        readme += "*Figure 1: Brief description of the screenshot*\n"
        readme += "```\n\n"
        
        # Getting Started
        readme += "## 🚀 Getting Started\n\n"
        readme += "### Prerequisites\n\n"
        
        # Add prerequisites based on the project type
        if repo_data.get('language') == 'Python':
            readme += "- Python 3.8 or higher\n"
            readme += "- pip (Python package manager)\n"
            readme += "- Git\n\n"
        elif repo_data.get('language') == 'JavaScript':
            readme += "- Node.js (v14 or higher)\n"
            readme += "- npm (Node package manager)\n"
            readme += "- Git\n\n"
        else:
            readme += "- Git\n"
            readme += "- [Specify other requirements]\n\n"
        
        readme += "### Installation\n\n"
        readme += "1. **Clone the repository**\n\n"
        readme += "```bash\n"
        readme += f"git clone {repo_data['url']}.git\n"
        readme += f"cd {repo_data['name']}\n"
        readme += "```\n\n"
        
        # Add language-specific installation
        if repo_data.get('language') == 'Python':
            readme += "2. **Set up a virtual environment** (recommended)\n\n"
            readme += "```bash\n"
            readme += "# Create a virtual environment\n"
            readme += "python -m venv venv\n"
            readme += "# Activate the virtual environment\n"
            readme += "# On Windows:\n"
            readme += "venv\\Scripts\\activate\n"
            readme += "# On macOS/Linux:\n"
            readme += "source venv/bin/activate\n"
            readme += "```\n\n"
            readme += "3. **Install dependencies**\n\n"
            readme += "```bash\n"
            readme += "pip install -r requirements.txt\n"
            readme += "```\n\n"
        elif repo_data.get('language') == 'JavaScript':
            readme += "2. **Install dependencies**\n\n"
            readme += "```bash\n"
            readme += "npm install\n"
            readme += "```\n\n"
        
        # Usage
        readme += "## 💻 Usage\n\n"
        
        if repo_data.get('language') == 'Python':
            readme += "To run the application:\n\n"
            readme += "```bash\n"
            readme += "python main.py\n"
            readme += "```\n\n"
        elif repo_data.get('language') == 'JavaScript':
            readme += "To run the application:\n\n"
            readme += "```bash\n"
            readme += "npm start\n"
            readme += "```\n\n"
        else:
            readme += "To run the application:\n\n"
            readme += "```bash\n"
            readme += "python app.py  # for Python applications\n"
            readme += "# or\n"
            readme += "npm start     # for Node.js applications\n"
            readme += "```\n\n"
            
        # Configuration
        readme += "## 🔧 Configuration\n\n"
        readme += "Create a `.env` file in the root directory for environment-specific settings.\n\n"
        
        # Tech Stack
        readme += "## 🛠️ Tech Stack\n\n"
        
        tech_stack = {
            "Frontend": ["HTML", "CSS", "JavaScript"],
            "Backend": ["Python"],
            "Database": ["SQLite"],
            "DevOps": ["Docker", "GitHub Actions"]
        }
        
        for category, techs in tech_stack.items():
            readme += f"**{category}**\\n"
            for tech in techs:
                readme += f"- {tech}\\n"
            readme += "\n"
        
        # Contributing
        readme += "## 🤝 Contributing\n\n"
        readme += "Contributions are what make the open-source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.\n\n"
        readme += "1. Fork the Project\n"
        readme += "2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)\n"
        readme += "3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)\n"
        readme += "4. Push to the Branch (`git push origin feature/AmazingFeature`)\n"
        readme += "5. Open a Pull Request\n\n"
        
        # License
        readme += f"## 📄 License\n\n"
        if repo_data.get('license'):
            readme += f"Distributed under the {repo_data['license']} License. See `LICENSE` for more information.\n\n"
        else:
            readme += "Distributed under the MIT License. See `LICENSE` for more information.\n\n"
        
        # Contact
        readme += "## 📫 Contact\n\n"
        readme += f"**{user_name}**\n"
        
        if user_email:
            readme += f"📧 {user_email}\n"
            
        if portfolio_url:
            readme += f"🌐 [{portfolio_url}]({portfolio_url})\n"
            
        readme += f"🔗 Project Link: [{repo_data['url']}]({repo_data['url']})\n\n"
        
        # Contributors
        if repo_data.get('contributors'):
            readme += "## 👥 Contributors\n\n"
            readme += "Thanks to these wonderful people who have contributed to this project!\n\n"
            
            for contributor in repo_data['contributors']:
                readme += f"<a href=\"{contributor['url']}\"><img src=\"{contributor['url']}.png?size=50\" width=\"50\" height=\"50\" alt=\"{contributor['login']}\" style=\"border-radius: 50%;\"></a>\n"
            
            readme += "\n"
        
        # Acknowledgments
        readme += "## 🙏 Acknowledgments\n\n"
        readme += "- [Choose an Open Source License](https://choosealicense.com)\\n"
        readme += "- [GitHub Emoji Cheat Sheet](https://www.webpagefx.com/tools/emoji-cheat-sheet)\\n"
        readme += "- [Img Shields](https://shields.io)\\n"
        readme += "- [GitHub Pages](https://pages.github.com)\\n\n"
        
        return readme

def main():
    parser = argparse.ArgumentParser(description='Generate a README for a GitHub repository')
    parser.add_argument('repo_url', type=str, help='GitHub repository URL')
    parser.add_argument('--output', '-o', type=str, default='README.md', help='Output file path (default: README.md)')
    parser.add_argument('--token', '-t', type=str, help='GitHub Personal Access Token')
    
    args = parser.parse_args()
    
    analyzer = GitHubAnalyzer(token=args.token)
    
    # Get repository info from URL
    owner, repo_name = analyzer.get_repo_info(args.repo_url)
    if not owner or not repo_name:
        print("Error: Invalid GitHub repository URL")
        sys.exit(1)
    
    print(f"Analyzing repository: {owner}/{repo_name}")
    
    try:
        # Analyze repository
        repo_data = analyzer.analyze_repository(owner, repo_name)
        if not repo_data:
            print("Error: Could not analyze repository")
            sys.exit(1)
        
        # Generate README
        readme_content = analyzer.generate_readme(repo_data)
        
        # Save to file
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(readme_content)
        
        print(f"✅ README generated successfully at {args.output}")
        
    except GithubException as e:
        if e.status == 404:
            print("Error: Repository not found or access denied")
        elif e.status == 403 and 'rate limit' in str(e).lower():
            print("Error: GitHub API rate limit exceeded. Please provide a GitHub token.")
        else:
            print(f"GitHub API Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
