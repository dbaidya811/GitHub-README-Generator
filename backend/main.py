from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import tempfile
import shutil
import os
import json
import re
from git import Repo
from typing import Optional
import openai

app = FastAPI()

# Allow CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RepoRequest(BaseModel):
    repo_url: str
    generation_method: str = 'template'
    api_key: Optional[str] = None
    buy_me_a_coffee_user: Optional[str] = None
    twitter_user: Optional[str] = None
    linkedin_user: Optional[str] = None
    github_user: Optional[str] = None
    instagram_user: Optional[str] = None
    youtube_channel: Optional[str] = None
    website_url: Optional[str] = None

def detect_main_language(repo_path):
    # Count file extensions
    ext_count = {}
    for root, dirs, files in os.walk(repo_path):
        # Ignore dot-folders like .git, .vscode etc.
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext:
                ext_count[ext] = ext_count.get(ext, 0) + 1
    if not ext_count:
        return "Unknown"
    # Map common extensions to language
    ext_lang = {
        ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript", ".java": "Java",
        ".cpp": "C++", ".c": "C", ".rb": "Ruby", ".go": "Go", ".php": "PHP",
        ".cs": "C#", ".rs": "Rust", ".swift": "Swift", ".kt": "Kotlin", ".dart": "Dart",
        ".html": "HTML", ".css": "CSS"
    }
    # Sort by count and find the most common language
    sorted_ext = sorted(ext_count.items(), key=lambda item: item[1], reverse=True)
    for ext, count in sorted_ext:
        if ext in ext_lang:
            return ext_lang[ext]
    return "Unknown"

def list_main_files(repo_path):
    files = []
    # Limit scan depth to avoid going too deep into directories
    for root, dirs, fs in os.walk(repo_path):
        # Ignore dot-folders like .git, .vscode etc.
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        rel_root = os.path.relpath(root, repo_path)
        if rel_root.count(os.sep) > 2:
            continue
        for f in fs:
            if not f.startswith('.'):
                 files.append(os.path.join(rel_root, f) if rel_root != '.' else f)
    return files[:15] # Show up to 15 main files

def get_setup_and_run_instructions(repo_path):
    instructions = {
        "setup": "# No standard setup file found. Please add manually.",
        "run": "# No standard run command found. Please add manually."
    }
    # Python
    if os.path.exists(os.path.join(repo_path, 'requirements.txt')):
        instructions["setup"] = "pip install -r requirements.txt"
        if os.path.exists(os.path.join(repo_path, 'main.py')):
            instructions["run"] = "python main.py"
        elif os.path.exists(os.path.join(repo_path, 'app.py')):
            instructions["run"] = "python app.py"
    # Node.js
    elif os.path.exists(os.path.join(repo_path, 'package.json')):
        instructions["setup"] = "npm install"
        try:
            with open(os.path.join(repo_path, 'package.json'), 'r', encoding='utf-8') as f:
                pkg = json.load(f)
                if 'scripts' in pkg and 'start' in pkg['scripts']:
                    instructions["run"] = "npm start"
        except Exception:
            pass # Keep default if package.json is malformed
    return instructions

def check_license(repo_path):
    license_names = [
        'LICENSE', 'LICENSE.txt', 'LICENSE.md',
        'LICENCE', 'LICENCE.txt', 'LICENCE.md'
    ]
    files = os.listdir(repo_path)
    for name in license_names:
        for file in files:
            if file.lower() == name.lower():
                license_path = os.path.join(repo_path, file)
                try:
                    with open(license_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = [line.strip() for line in f.readlines() if line.strip()]
                        preview = '\n'.join(lines[:3])
                        return (
                            f"This project is licensed under the terms of the `{file}` file.\n\n"
                            f"**License Preview:**\n"
                            f"```\n{preview}\n```"
                        )
                except Exception:
                    return f"This project is licensed under the terms of the `{file}` file."
    return "No license file found."

def create_social_section(twitter, linkedin, github, instagram, youtube, website):
    social_links = []
    if twitter:
        social_links.append(f"[![Twitter](https://img.shields.io/badge/Twitter-%231DA1F2?style=for-the-badge&logo=Twitter&logoColor=white)](https://twitter.com/{twitter})")
    if linkedin:
        social_links.append(f"[![LinkedIn](https://img.shields.io/badge/LinkedIn-%230077B5?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/{linkedin})")
    if github:
        social_links.append(f"[![GitHub](https://img.shields.io/badge/GitHub-%23100000?style=for-the-badge&logo=github&logoColor=white)](https://github.com/{github})")
    if instagram:
        social_links.append(f"[![Instagram](https://img.shields.io/badge/Instagram-%23E4405F?style=for-the-badge&logo=Instagram&logoColor=white)](https://instagram.com/{instagram})")
    if youtube:
        social_links.append(f"[![YouTube](https://img.shields.io/badge/YouTube-%23FF0000?style=for-the-badge&logo=YouTube&logoColor=white)](https://youtube.com/{youtube})")
    if website:
        social_links.append(f"[![Website](https://img.shields.io/badge/Website-%23000000?style=for-the-badge&logo=About.me&logoColor=white)]({website})")
    if not social_links:
        return ""
    return f"""
## 🔗 Connect with me

{' '.join(social_links)}
"""

def create_support_section(coffee_user):
    if not coffee_user:
        return ""
    return f"""
## 🙏 Support

If you like this project, please consider supporting me.

[![Buy Me A Coffee](https://img.shields.io/badge/Buy_Me_A_Coffee-%23FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://www.buymeacoffee.com/{coffee_user})
"""

def generate_readme_with_ai(api_key, context):
    try:
        client = openai.OpenAI(api_key=api_key)
        prompt = f"""
        Based on the following repository context, generate a professional and well-structured README.md file in Markdown format.

        **Repository Context:**
        - **Project Name:** {context['repo_name']}
        - **Main Language:** {context['lang']}
        - **File Structure:**
        ```
        {context['repo_name']}/
        ├── {"\n├── ".join(context['files'])}
        └── ...
        ```
        - **Installation Command:** `{context['instructions']['setup']}`
        - **Run Command:** `{context['instructions']['run']}`

        **README Structure Requirements:**
        1.  **Project Title:** Use the project name.
        2.  **Badges:** Include a language badge for the main language.
        3.  **Description:** Write a concise, one-paragraph description of what the project likely does based on its name and file structure.
        4.  **Features:** Create a bulleted list of 2-3 potential key features.
        5.  **Tech Stack:** List the main language and any other obvious technologies.
        6.  **Setup and Installation:** Provide the steps to clone, and install dependencies using the provided commands.
        7.  **How to Run:** Show the command to run the project.
        8.  **License:** Mention the license info provided: `{context['license_info']}`.

        **Social/Support Links (if provided):**
        - Twitter: {context['social']['twitter']}
        - LinkedIn: {context['social']['linkedin']}
        - GitHub: {context['social']['github']}
        - Instagram: {context['social']['instagram']}
        - YouTube: {context['social']['youtube']}
        - Website: {context['social']['website']}
        - Buy Me a Coffee: {context['support']['coffee']}
        
        If social or support links are provided, add "Connect with me" and/or "Support" sections.

        Generate only the raw Markdown content for the README.md file. Do not include any explanatory text before or after the markdown content.
        """
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an expert in writing high-quality README.md files for software projects."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content

    except openai.AuthenticationError:
        raise HTTPException(status_code=401, detail="Invalid OpenAI API Key.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")

def generate_smart_overview(repo_name, files, lang):
    """
    Generate a highly accurate overview using advanced project analysis
    """
    # Convert repo name to readable format
    project_name = repo_name.replace('-', ' ').replace('_', ' ').title()
    
    # Deep analysis of project structure and content
    analysis = analyze_project_deeply(files, repo_name)
    
    # Generate context-aware overview
    overview = generate_context_aware_overview(project_name, analysis, lang)
    
    return overview

def analyze_project_deeply(files, repo_name):
    """
    Perform deep analysis of project structure and content
    """
    analysis = {
        'project_type': 'unknown',
        'primary_purpose': 'unknown',
        'tech_stack': [],
        'has_frontend': False,
        'has_backend': False,
        'has_database': False,
        'has_api': False,
        'has_cli': False,
        'has_web': False,
        'has_mobile': False,
        'has_docker': False,
        'has_tests': False,
        'has_docs': False,
        'is_fullstack': False,
        'is_microservice': False,
        'is_library': False,
        'is_tool': False,
        'is_bot': False,
        'is_api': False,
        'is_webapp': False,
        'key_files': [],
        'framework_detected': None,
        'database_detected': None
    }
    
    # Analyze file extensions and patterns
    for file in files:
        file_lower = file.lower()
        
        # Frontend detection
        if file_lower.endswith(('.html', '.css', '.js', '.jsx', '.tsx', '.vue', '.svelte')):
            analysis['has_frontend'] = True
            if 'react' in file_lower or 'package.json' in file_lower:
                analysis['framework_detected'] = 'React'
            elif 'vue' in file_lower:
                analysis['framework_detected'] = 'Vue'
            elif 'angular' in file_lower:
                analysis['framework_detected'] = 'Angular'
        
        # Backend detection
        if file_lower.endswith(('.py', '.js', '.java', '.php', '.go', '.rb', '.cs')):
            analysis['has_backend'] = True
            if 'fastapi' in file_lower or 'flask' in file_lower:
                analysis['framework_detected'] = 'FastAPI' if 'fastapi' in file_lower else 'Flask'
            elif 'express' in file_lower or 'node' in file_lower:
                analysis['framework_detected'] = 'Express.js'
            elif 'spring' in file_lower:
                analysis['framework_detected'] = 'Spring'
        
        # Database detection
        if file_lower.endswith(('.sql', '.db', '.sqlite', '.postgresql', '.mysql')):
            analysis['has_database'] = True
            if 'postgres' in file_lower:
                analysis['database_detected'] = 'PostgreSQL'
            elif 'mysql' in file_lower:
                analysis['database_detected'] = 'MySQL'
            elif 'sqlite' in file_lower:
                analysis['database_detected'] = 'SQLite'
        
        # API detection
        if any(keyword in file_lower for keyword in ['api', 'route', 'endpoint', 'controller']):
            analysis['has_api'] = True
        
        # CLI detection
        if any(keyword in file_lower for keyword in ['cli', 'command', 'console', 'terminal']):
            analysis['has_cli'] = True
        
        # Web detection
        if any(keyword in file_lower for keyword in ['web', 'www', 'public', 'static']):
            analysis['has_web'] = True
        
        # Mobile detection
        if any(keyword in file_lower for keyword in ['mobile', 'android', 'ios', 'react-native']):
            analysis['has_mobile'] = True
        
        # Docker detection
        if 'dockerfile' in file_lower or file_lower.endswith('.dockerfile'):
            analysis['has_docker'] = True
        
        # Test detection
        if any(keyword in file_lower for keyword in ['test', 'spec', 'specs', 'unit', 'integration']):
            analysis['has_tests'] = True
        
        # Documentation detection
        if any(keyword in file_lower for keyword in ['readme', 'doc', 'docs', 'documentation']):
            analysis['has_docs'] = True
        
        # Key files for analysis
        if any(keyword in file_lower for keyword in ['main', 'app', 'index', 'server', 'config']):
            analysis['key_files'].append(file)
    
    # Determine project type based on analysis
    if analysis['has_frontend'] and analysis['has_backend']:
        analysis['is_fullstack'] = True
        analysis['project_type'] = 'fullstack_webapp'
    elif analysis['has_api'] and not analysis['has_frontend']:
        analysis['is_api'] = True
        analysis['project_type'] = 'api_service'
    elif analysis['has_cli']:
        analysis['is_tool'] = True
        analysis['project_type'] = 'cli_tool'
    elif analysis['has_frontend'] and not analysis['has_backend']:
        analysis['is_webapp'] = True
        analysis['project_type'] = 'frontend_app'
    elif 'bot' in repo_name.lower():
        analysis['is_bot'] = True
        analysis['project_type'] = 'bot'
    elif 'lib' in repo_name.lower() or 'package' in repo_name.lower():
        analysis['is_library'] = True
        analysis['project_type'] = 'library'
    
    # Determine primary purpose
    if analysis['is_api']:
        analysis['primary_purpose'] = 'provide API services'
    elif analysis['is_fullstack']:
        analysis['primary_purpose'] = 'provide complete web application'
    elif analysis['is_tool']:
        analysis['primary_purpose'] = 'provide command-line tools'
    elif analysis['is_bot']:
        analysis['primary_purpose'] = 'provide automated bot services'
    elif analysis['is_library']:
        analysis['primary_purpose'] = 'provide reusable code library'
    else:
        analysis['primary_purpose'] = 'provide software solution'
    
    return analysis

def generate_context_aware_overview(project_name, analysis, lang):
    """
    Generate highly accurate overview based on deep analysis
    """
    overview_parts = []
    
    # Start with project name and type
    if analysis['project_type'] == 'api_service':
        overview_parts.append(f"{project_name} is a robust and scalable API service")
    elif analysis['project_type'] == 'fullstack_webapp':
        overview_parts.append(f"{project_name} is a comprehensive full-stack web application")
    elif analysis['project_type'] == 'cli_tool':
        overview_parts.append(f"{project_name} is a powerful command-line interface tool")
    elif analysis['project_type'] == 'bot':
        overview_parts.append(f"{project_name} is an intelligent automated bot")
    elif analysis['project_type'] == 'library':
        overview_parts.append(f"{project_name} is a reusable software library")
    elif analysis['project_type'] == 'frontend_app':
        overview_parts.append(f"{project_name} is a modern frontend web application")
    else:
        overview_parts.append(f"{project_name} is a sophisticated software solution")
    
    # Add technology stack information
    tech_stack_parts = []
    if analysis['framework_detected']:
        tech_stack_parts.append(f"built with {analysis['framework_detected']}")
    if analysis['database_detected']:
        tech_stack_parts.append(f"using {analysis['database_detected']} database")
    if analysis['has_docker']:
        tech_stack_parts.append("containerized with Docker")
    
    if tech_stack_parts:
        overview_parts.append(f"developed using {lang} and {', '.join(tech_stack_parts)}.")
    else:
        overview_parts.append(f"developed with {lang}.")
    
    # Add specific capabilities
    capabilities = []
    if analysis['has_api']:
        capabilities.append("RESTful API endpoints")
    if analysis['has_database']:
        capabilities.append("database integration")
    if analysis['has_frontend']:
        capabilities.append("responsive user interface")
    if analysis['has_tests']:
        capabilities.append("comprehensive testing")
    if analysis['has_docs']:
        capabilities.append("detailed documentation")
    if analysis['has_docker']:
        capabilities.append("containerized deployment")
    
    if capabilities:
        overview_parts.append(f"It features {', '.join(capabilities)}.")
    
    # Add purpose and benefits
    if analysis['project_type'] == 'api_service':
        overview_parts.append("Perfect for developers and applications requiring reliable data access and processing capabilities.")
    elif analysis['project_type'] == 'fullstack_webapp':
        overview_parts.append("Ideal for businesses and users seeking a complete digital solution with both frontend and backend components.")
    elif analysis['project_type'] == 'cli_tool':
        overview_parts.append("Designed to streamline developer workflows and automate repetitive tasks efficiently.")
    elif analysis['project_type'] == 'bot':
        overview_parts.append("Optimized for automated interactions and intelligent response handling across multiple platforms.")
    elif analysis['project_type'] == 'library':
        overview_parts.append("Built for developers to easily integrate and extend functionality in their own projects.")
    else:
        overview_parts.append("This project demonstrates modern software development practices and best-in-class architecture.")
    
    return " ".join(overview_parts)

def generate_smart_features(repo_name, files, lang):
    """
    Generate highly accurate features based on deep project analysis
    """
    # Use the same deep analysis as overview
    analysis = analyze_project_deeply(files, repo_name)
    
    features = []
    
    # Generate features based on project type and analysis
    if analysis['project_type'] == 'api_service':
        features.extend([
            "**RESTful API Design:** Clean and intuitive API endpoints following REST principles with comprehensive documentation",
            "**Scalable Architecture:** Built with scalability in mind, supporting high-traffic applications and microservices",
            "**Comprehensive Testing:** Extensive test coverage including unit tests, integration tests, and API endpoint testing",
            "**Security Features:** Built-in authentication, authorization, and data validation for secure API access",
            "**Performance Optimization:** Efficient data processing, caching mechanisms, and optimized database queries"
        ])
    elif analysis['project_type'] == 'fullstack_webapp':
        features.extend([
            "**Modern UI/UX:** Responsive design with intuitive user interface and smooth user experience",
            "**Full-stack Integration:** Seamless communication between frontend and backend components",
            "**Real-time Updates:** Dynamic content updates and real-time data synchronization",
            "**Cross-platform Compatibility:** Works seamlessly across different devices, browsers, and screen sizes",
            "**Advanced State Management:** Efficient state handling and data flow management"
        ])
    elif analysis['project_type'] == 'cli_tool':
        features.extend([
            "**Command-line Interface:** Intuitive CLI with comprehensive command options and help system",
            "**Automation Capabilities:** Streamlined workflow automation and batch processing features",
            "**Cross-platform Support:** Works consistently across Windows, macOS, and Linux systems",
            "**Configuration Management:** Flexible configuration options with environment variable support",
            "**Extensible Design:** Plugin architecture for easy customization and feature extensions"
        ])
    elif analysis['project_type'] == 'bot':
        features.extend([
            "**Intelligent Automation:** Smart responses and automated task handling with natural language processing",
            "**Multi-platform Support:** Works across various messaging platforms and social media channels",
            "**Advanced NLP:** Natural language understanding and context-aware conversation handling",
            "**Scalable Architecture:** Handles multiple concurrent conversations and high user loads",
            "**Customizable Responses:** Configurable response patterns and personalized user interactions"
        ])
    elif analysis['project_type'] == 'library':
        features.extend([
            "**Easy Integration:** Simple setup and configuration process with comprehensive documentation",
            "**Extensible Design:** Modular architecture for easy customization and feature extensions",
            "**Type Safety:** Strong typing support for better development experience and error prevention",
            "**Comprehensive Testing:** Extensive test coverage ensuring reliability and stability",
            "**Performance Optimized:** Efficient algorithms and optimized code for high-performance applications"
        ])
    elif analysis['project_type'] == 'frontend_app':
        features.extend([
            "**Modern UI/UX:** Responsive design with intuitive user interface and smooth animations",
            "**Cross-platform Compatibility:** Works seamlessly across different devices and browsers",
            "**Performance Optimized:** Fast loading times and efficient resource utilization",
            "**Accessibility Features:** Built-in accessibility support for inclusive user experience",
            "**Progressive Enhancement:** Graceful degradation and progressive enhancement for better user experience"
        ])
    else:
        # Generic features based on detected capabilities
        if analysis['has_frontend'] and analysis['has_backend']:
            features.extend([
                "**Full-stack Architecture:** Complete solution with frontend and backend components",
                "**Modern Tech Stack:** Built with the latest technologies and best practices",
                "**Scalable Design:** Architecture designed for growth and performance",
                "**Comprehensive Testing:** Extensive test coverage for reliability and stability"
            ])
        elif analysis['has_docker']:
            features.extend([
                "**Containerized Deployment:** Easy deployment with Docker containerization",
                "**Environment Consistency:** Consistent behavior across different environments",
                "**DevOps Ready:** Streamlined development and deployment workflow",
                "**Scalable Infrastructure:** Container orchestration support for scaling"
            ])
        else:
            features.extend([
                f"**{lang} Powered:** Built with {lang} for optimal performance and reliability",
                "**Clean Code:** Well-structured and maintainable codebase following best practices",
                "**Extensible Design:** Easy to extend and customize for specific needs",
                "**Comprehensive Documentation:** Detailed guides and API references"
            ])
    
    # Add technology-specific features
    if analysis['framework_detected']:
        if analysis['framework_detected'] == 'React':
            features.append("**React Ecosystem:** Leverages React's component-based architecture and virtual DOM")
        elif analysis['framework_detected'] == 'FastAPI':
            features.append("**FastAPI Features:** Automatic API documentation, data validation, and async support")
        elif analysis['framework_detected'] == 'Express.js':
            features.append("**Express.js Framework:** Middleware support and flexible routing system")
    
    if analysis['database_detected']:
        features.append(f"**Database Integration:** Robust {analysis['database_detected']} integration with optimized queries")
    
    if analysis['has_tests']:
        features.append("**Comprehensive Testing:** Extensive test coverage including unit, integration, and end-to-end tests")
    
    if analysis['has_docs']:
        features.append("**Detailed Documentation:** Complete guides, API references, and usage examples")
    
    if analysis['has_docker']:
        features.append("**Containerization:** Docker support for consistent deployment across environments")
    
    return features

def analyze_project_content_and_generate_features(repo_path, files, analysis):
    """
    Analyze actual project content to generate more specific features
    """
    specific_features = []
    
    # Analyze key files for specific functionality
    for file in files:
        file_lower = file.lower()
        
        # Authentication features
        if any(keyword in file_lower for keyword in ['auth', 'login', 'register', 'jwt', 'oauth']):
            specific_features.append("**User Authentication:** Secure login, registration, and session management")
        
        # Database features
        if any(keyword in file_lower for keyword in ['model', 'schema', 'migration', 'database']):
            specific_features.append("**Data Modeling:** Structured data models with database migrations")
        
        # API features
        if any(keyword in file_lower for keyword in ['api', 'endpoint', 'route', 'controller']):
            specific_features.append("**API Endpoints:** RESTful API with comprehensive endpoint coverage")
        
        # UI/UX features
        if any(keyword in file_lower for keyword in ['component', 'ui', 'interface', 'layout']):
            specific_features.append("**Component Architecture:** Modular UI components for reusability")
        
        # Real-time features
        if any(keyword in file_lower for keyword in ['websocket', 'socket', 'real-time', 'live']):
            specific_features.append("**Real-time Communication:** WebSocket support for live updates")
        
        # File handling
        if any(keyword in file_lower for keyword in ['upload', 'file', 'media', 'image']):
            specific_features.append("**File Management:** File upload, processing, and storage capabilities")
        
        # Search functionality
        if any(keyword in file_lower for keyword in ['search', 'filter', 'query']):
            specific_features.append("**Advanced Search:** Powerful search and filtering capabilities")
        
        # Notification system
        if any(keyword in file_lower for keyword in ['notification', 'alert', 'email', 'sms']):
            specific_features.append("**Notification System:** Email, SMS, and in-app notifications")
        
        # Payment integration
        if any(keyword in file_lower for keyword in ['payment', 'stripe', 'paypal', 'billing']):
            specific_features.append("**Payment Integration:** Secure payment processing and billing")
        
        # Analytics
        if any(keyword in file_lower for keyword in ['analytics', 'tracking', 'metrics', 'dashboard']):
            specific_features.append("**Analytics Dashboard:** Comprehensive data analytics and reporting")
        
        # Security features
        if any(keyword in file_lower for keyword in ['security', 'encryption', 'hash', 'bcrypt']):
            specific_features.append("**Security Features:** Data encryption, secure hashing, and protection")
        
        # Caching
        if any(keyword in file_lower for keyword in ['cache', 'redis', 'memcached']):
            specific_features.append("**Caching System:** Performance optimization with intelligent caching")
        
        # Testing
        if any(keyword in file_lower for keyword in ['test', 'spec', 'mock', 'fixture']):
            specific_features.append("**Comprehensive Testing:** Unit, integration, and end-to-end testing")
        
        # Documentation
        if any(keyword in file_lower for keyword in ['doc', 'readme', 'api-doc', 'swagger']):
            specific_features.append("**Auto Documentation:** Automatic API documentation and guides")
    
    # Remove duplicates
    specific_features = list(set(specific_features))
    
    return specific_features

def generate_detailed_tech_stack(repo_path, lang, files):
    """
    Generate detailed and accurate tech stack information
    """
    tech_stack_parts = []
    
    # Analyze project structure for technology detection
    analysis = analyze_project_deeply(files, "temp_repo")
    
    # Main language with version info if possible
    tech_stack_parts.append(f"- **Primary Language:** {lang}")
    
    # Framework detection
    if analysis['framework_detected']:
        tech_stack_parts.append(f"- **Framework:** {analysis['framework_detected']}")
    
    # Frontend technologies
    frontend_techs = []
    if any(f.endswith('.html') for f in files):
        frontend_techs.append("HTML5")
    if any(f.endswith('.css') for f in files):
        frontend_techs.append("CSS3")
    if any(f.endswith('.js') for f in files):
        frontend_techs.append("JavaScript")
    if any(f.endswith('.jsx') for f in files):
        frontend_techs.append("React JSX")
    if any(f.endswith('.tsx') for f in files):
        frontend_techs.append("TypeScript")
    if any(f.endswith('.vue') for f in files):
        frontend_techs.append("Vue.js")
    if any(f.endswith('.svelte') for f in files):
        frontend_techs.append("Svelte")
    
    if frontend_techs:
        tech_stack_parts.append(f"- **Frontend:** {', '.join(frontend_techs)}")
    
    # Backend technologies
    backend_techs = []
    if analysis['framework_detected']:
        if analysis['framework_detected'] == 'FastAPI':
            backend_techs.extend(["FastAPI", "Pydantic", "Uvicorn"])
        elif analysis['framework_detected'] == 'Flask':
            backend_techs.extend(["Flask", "Werkzeug"])
        elif analysis['framework_detected'] == 'Express.js':
            backend_techs.extend(["Express.js", "Node.js"])
        elif analysis['framework_detected'] == 'Spring':
            backend_techs.extend(["Spring Boot", "Java"])
    
    if backend_techs:
        tech_stack_parts.append(f"- **Backend:** {', '.join(backend_techs)}")
    
    # Database technologies
    if analysis['database_detected']:
        tech_stack_parts.append(f"- **Database:** {analysis['database_detected']}")
    elif any(f.endswith(('.sql', '.db', '.sqlite')) for f in files):
        tech_stack_parts.append("- **Database:** SQLite")
    
    # Additional technologies
    additional_techs = []
    
    # Package managers
    if os.path.exists(os.path.join(repo_path, 'package.json')):
        additional_techs.append("npm")
    if os.path.exists(os.path.join(repo_path, 'requirements.txt')):
        additional_techs.append("pip")
    if os.path.exists(os.path.join(repo_path, 'pom.xml')):
        additional_techs.append("Maven")
    if os.path.exists(os.path.join(repo_path, 'go.mod')):
        additional_techs.append("Go Modules")
    
    # Build tools
    if any(f.endswith('.webpack.js') or 'webpack' in f.lower() for f in files):
        additional_techs.append("Webpack")
    if any(f.endswith('.babelrc') or 'babel' in f.lower() for f in files):
        additional_techs.append("Babel")
    if any(f.endswith('.eslintrc') or 'eslint' in f.lower() for f in files):
        additional_techs.append("ESLint")
    if any(f.endswith('.prettierrc') or 'prettier' in f.lower() for f in files):
        additional_techs.append("Prettier")
    
    # Testing frameworks
    if any('jest' in f.lower() for f in files):
        additional_techs.append("Jest")
    if any('pytest' in f.lower() for f in files):
        additional_techs.append("pytest")
    if any('mocha' in f.lower() for f in files):
        additional_techs.append("Mocha")
    if any('junit' in f.lower() for f in files):
        additional_techs.append("JUnit")
    
    # Containerization
    if analysis['has_docker']:
        additional_techs.append("Docker")
    
    # Version control
    if os.path.exists(os.path.join(repo_path, '.git')):
        additional_techs.append("Git")
    
    if additional_techs:
        tech_stack_parts.append(f"- **Tools & Libraries:** {', '.join(additional_techs)}")
    
    # Add deployment info
    deployment_techs = []
    if analysis['has_docker']:
        deployment_techs.append("Docker Containerization")
    if any('heroku' in f.lower() for f in files):
        deployment_techs.append("Heroku")
    if any('vercel' in f.lower() for f in files):
        deployment_techs.append("Vercel")
    if any('netlify' in f.lower() for f in files):
        deployment_techs.append("Netlify")
    if any('aws' in f.lower() for f in files):
        deployment_techs.append("AWS")
    
    if deployment_techs:
        tech_stack_parts.append(f"- **Deployment:** {', '.join(deployment_techs)}")
    
    # Add development tools
    dev_tools = []
    if any('vscode' in f.lower() or '.vscode' in f.lower() for f in files):
        dev_tools.append("VS Code")
    if any('webstorm' in f.lower() for f in files):
        dev_tools.append("WebStorm")
    if any('intellij' in f.lower() for f in files):
        dev_tools.append("IntelliJ IDEA")
    
    if dev_tools:
        tech_stack_parts.append(f"- **Development:** {', '.join(dev_tools)}")
    
    return "\n".join(tech_stack_parts)

def detect_languages_with_percentage(repo_path):
    """
    Detect all languages used in the project with their percentages
    """
    language_stats = {}
    total_files = 0
    
    # Language file extensions mapping
    lang_extensions = {
        '.py': 'Python',
        '.js': 'JavaScript',
        '.ts': 'TypeScript',
        '.jsx': 'React',
        '.tsx': 'React',
        '.html': 'HTML',
        '.css': 'CSS',
        '.scss': 'SCSS',
        '.sass': 'Sass',
        '.java': 'Java',
        '.cpp': 'C++',
        '.c': 'C',
        '.cs': 'C#',
        '.php': 'PHP',
        '.rb': 'Ruby',
        '.go': 'Go',
        '.rs': 'Rust',
        '.swift': 'Swift',
        '.kt': 'Kotlin',
        '.dart': 'Dart',
        '.vue': 'Vue',
        '.svelte': 'Svelte',
        '.sql': 'SQL',
        '.sh': 'Shell',
        '.ps1': 'PowerShell',
        '.bat': 'Batch',
        '.yml': 'YAML',
        '.yaml': 'YAML',
        '.json': 'JSON',
        '.xml': 'XML',
        '.md': 'Markdown',
        '.txt': 'Text',
        '.r': 'R',
        '.m': 'MATLAB',
        '.scala': 'Scala',
        '.clj': 'Clojure',
        '.hs': 'Haskell',
        '.ml': 'OCaml',
        '.f90': 'Fortran',
        '.pl': 'Perl',
        '.lua': 'Lua',
        '.groovy': 'Groovy',
        '.gradle': 'Gradle',
        '.dockerfile': 'Docker',
        '.docker': 'Docker'
    }
    
    for root, dirs, files in os.walk(repo_path):
        # Ignore common directories
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', 'venv', '__pycache__', 'build', 'dist']]
        
        for file in files:
            if not file.startswith('.'):
                ext = os.path.splitext(file)[1].lower()
                if ext in lang_extensions:
                    lang = lang_extensions[ext]
                    language_stats[lang] = language_stats.get(lang, 0) + 1
                    total_files += 1
    
    # Calculate percentages
    if total_files > 0:
        percentages = {}
        for lang, count in language_stats.items():
            percentage = (count / total_files) * 100
            percentages[lang] = round(percentage, 1)
        
        # Sort by percentage (descending)
        sorted_langs = sorted(percentages.items(), key=lambda x: x[1], reverse=True)
        return sorted_langs
    
    return []

def generate_technology_badges(files, analysis):
    """
    Generate technology badges with logos
    """
    badges = []
    
    # Framework badges
    if analysis['framework_detected']:
        if analysis['framework_detected'] == 'React':
            badges.append("![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)")
        elif analysis['framework_detected'] == 'Vue':
            badges.append("![Vue.js](https://img.shields.io/badge/Vue.js-35495E?style=for-the-badge&logo=vuedotjs&logoColor=4FC08D)")
        elif analysis['framework_detected'] == 'Angular':
            badges.append("![Angular](https://img.shields.io/badge/Angular-DD0031?style=for-the-badge&logo=angular&logoColor=white)")
        elif analysis['framework_detected'] == 'FastAPI':
            badges.append("![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)")
        elif analysis['framework_detected'] == 'Flask':
            badges.append("![Flask](https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white)")
        elif analysis['framework_detected'] == 'Express.js':
            badges.append("![Express.js](https://img.shields.io/badge/Express.js-000000?style=for-the-badge&logo=express&logoColor=white)")
        elif analysis['framework_detected'] == 'Spring':
            badges.append("![Spring](https://img.shields.io/badge/Spring-6DB33F?style=for-the-badge&logo=spring&logoColor=white)")
    
    # Database badges
    if analysis['database_detected']:
        if analysis['database_detected'] == 'PostgreSQL':
            badges.append("![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)")
        elif analysis['database_detected'] == 'MySQL':
            badges.append("![MySQL](https://img.shields.io/badge/MySQL-00000F?style=for-the-badge&logo=mysql&logoColor=white)")
        elif analysis['database_detected'] == 'SQLite':
            badges.append("![SQLite](https://img.shields.io/badge/SQLite-07405E?style=for-the-badge&logo=sqlite&logoColor=white)")
    
    # Language badges
    for file in files:
        file_lower = file.lower()
        if file_lower.endswith('.py'):
            badges.append("![Python](https://img.shields.io/badge/Python-FFD43B?style=for-the-badge&logo=python&logoColor=blue)")
            break
        elif file_lower.endswith('.js'):
            badges.append("![JavaScript](https://img.shields.io/badge/JavaScript-323330?style=for-the-badge&logo=javascript&logoColor=F7DF1E)")
            break
        elif file_lower.endswith('.ts'):
            badges.append("![TypeScript](https://img.shields.io/badge/TypeScript-007ACC?style=for-the-badge&logo=typescript&logoColor=white)")
            break
        elif file_lower.endswith('.java'):
            badges.append("![Java](https://img.shields.io/badge/Java-ED8B00?style=for-the-badge&logo=openjdk&logoColor=white)")
            break
        elif file_lower.endswith('.cpp'):
            badges.append("![C++](https://img.shields.io/badge/C%2B%2B-00599C?style=for-the-badge&logo=c%2B%2B&logoColor=white)")
            break
        elif file_lower.endswith('.cs'):
            badges.append("![C#](https://img.shields.io/badge/C%23-239120?style=for-the-badge&logo=c-sharp&logoColor=white)")
            break
        elif file_lower.endswith('.php'):
            badges.append("![PHP](https://img.shields.io/badge/PHP-777BB4?style=for-the-badge&logo=php&logoColor=white)")
            break
        elif file_lower.endswith('.go'):
            badges.append("![Go](https://img.shields.io/badge/Go-00ADD8?style=for-the-badge&logo=go&logoColor=white)")
            break
        elif file_lower.endswith('.rs'):
            badges.append("![Rust](https://img.shields.io/badge/Rust-000000?style=for-the-badge&logo=rust&logoColor=white)")
            break
    
    # Additional technology badges
    if any('docker' in f.lower() for f in files):
        badges.append("![Docker](https://img.shields.io/badge/Docker-2CA5E0?style=for-the-badge&logo=docker&logoColor=white)")
    
    if any('git' in f.lower() for f in files):
        badges.append("![Git](https://img.shields.io/badge/GIT-E44C30?style=for-the-badge&logo=git&logoColor=white)")
    
    if any('npm' in f.lower() or 'package.json' in f.lower() for f in files):
        badges.append("![NPM](https://img.shields.io/badge/npm-CB3837?style=for-the-badge&logo=npm&logoColor=white)")
    
    if any('pip' in f.lower() or 'requirements.txt' in f.lower() for f in files):
        badges.append("![PyPI](https://img.shields.io/badge/pypi-3775A9?style=for-the-badge&logo=pypi&logoColor=white)")
    
    if any('html' in f.lower() for f in files):
        badges.append("![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white)")
    
    if any('css' in f.lower() for f in files):
        badges.append("![CSS3](https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white)")
    
    # Remove duplicates while preserving order
    seen = set()
    unique_badges = []
    for badge in badges:
        if badge not in seen:
            seen.add(badge)
            unique_badges.append(badge)
    
    return unique_badges

def get_dynamic_badge(tech):
    """
    Generate a dynamic Shields.io badge URL for a given technology or language name.
    """
    logo_map = {
        'python': ('python', 'FFD43B'),
        'javascript': ('javascript', 'F7DF1E'),
        'html': ('html5', 'E34F26'),
        'css': ('css3', '1572B6'),
        'json': ('json', '000000'),
        'markdown': ('markdown', '000000'),
        'text': ('text', '808080'),
        'typescript': ('typescript', '007ACC'),
        'react': ('react', '61DAFB'),
        'java': ('openjdk', 'ED8B00'),
        'c++': ('c%2B%2B', '00599C'),
        'c': ('c', '00599C'),
        'c#': ('c-sharp', '239120'),
        'php': ('php', '777BB4'),
        'go': ('go', '00ADD8'),
        'ruby': ('ruby', 'CC342D'),
        'rust': ('rust', '000000'),
        'sql': ('mysql', '4479A1'),
        'yaml': ('yaml', '000000'),
        'shell': ('gnu-bash', '121011'),
        'docker': ('docker', '2CA5E0'),
        'vue': ('vuedotjs', '4FC08D'),
        'svelte': ('svelte', 'FF3E00'),
        'scss': ('sass', 'CC6699'),
        'dart': ('dart', '0175C2'),
        'kotlin': ('kotlin', '0095D5'),
        'swift': ('swift', 'FA7343'),
        'powershell': ('powershell', '5391FE'),
        'batch': ('windows', '4B4B4B'),
        'matlab': ('mathworks', '0076A8'),
        'scala': ('scala', 'DC322F'),
        'clojure': ('clojure', '5881D8'),
        'haskell': ('haskell', '5D4F85'),
        'ocaml': ('ocaml', 'EC6813'),
        'fortran': ('fortran', '734F96'),
        'perl': ('perl', '39457E'),
        'lua': ('lua', '2C2D72'),
        'groovy': ('apache-groovy', '4298B8'),
        'gradle': ('gradle', '02303A'),
        'xml': ('xml', '000000'),
        'r': ('r', '276DC3'),
        'fastapi': ('fastapi', '005571'),
        'flask': ('flask', '000000'),
        'express.js': ('express', '000000'),
        'spring': ('spring', '6DB33F'),
        'postgresql': ('postgresql', '316192'),
        'mysql': ('mysql', '00000F'),
        'sqlite': ('sqlite', '07405E'),
        'npm': ('npm', 'CB3837'),
        'pip': ('pypi', '3775A9'),
        'jest': ('jest', 'C21325'),
        'webpack': ('webpack', '8DD6F9'),
        'babel': ('babel', 'F9DC3E'),
        'eslint': ('eslint', '4B32C3'),
        'prettier': ('prettier', 'F7B93E'),
        'vs code': ('visual-studio-code', '007ACC'),
        'heroku': ('heroku', '430098'),
        'aws': ('amazon-aws', '232F3E'),
        'vercel': ('vercel', '000000'),
        'netlify': ('netlify', '00C7B7'),
        # Add more as needed
    }
    key = tech.lower().replace('.', '').replace(' ', '')
    logo, color = logo_map.get(key, (key, '808080'))
    return f"https://img.shields.io/badge/{tech.replace(' ', '%20')}-{color}?style=for-the-badge&logo={logo}&logoColor=white"

@app.post("/generate-readme/")
async def generate_readme(request: RepoRequest):
    repo_url = request.repo_url
    temp_dir = tempfile.mkdtemp()
    try:
        # Use shallow clone for speed
        Repo.clone_from(repo_url, temp_dir, depth=1)
        
        repo_name = repo_url.split('/')[-1].replace('.git', '')
        lang = detect_main_language(temp_dir)
        files = list_main_files(temp_dir)
        instructions = get_setup_and_run_instructions(temp_dir)
        license_info = check_license(temp_dir)
        
        # Get language statistics and technology badges
        language_stats = detect_languages_with_percentage(temp_dir)
        analysis_for_badges = analyze_project_deeply(files, repo_name)
        tech_badges = generate_technology_badges(files, analysis_for_badges)

        if request.generation_method == 'ai':
            if not request.api_key:
                raise HTTPException(status_code=400, detail="API Key is required for AI generation.")
            
            context = {
                "repo_name": repo_name,
                "lang": lang,
                "files": files,
                "instructions": instructions,
                "license_info": license_info,
                "social": {
                    "twitter": request.twitter_user, 
                    "linkedin": request.linkedin_user,
                    "github": request.github_user,
                    "instagram": request.instagram_user,
                    "youtube": request.youtube_channel,
                    "website": request.website_url
                },
                "support": {"coffee": request.buy_me_a_coffee_user},
            }
            ai_readme = generate_readme_with_ai(request.api_key, context)
            return {"readme": ai_readme}

        # --- Enhanced Table of Contents ---
        toc = """
## Table of Contents
- [Overview](#-overview)
- [Features](#-features)
- [Tech Stack](#-tech-stack)
- [Installation](#-installation)
- [Usage](#-usage)
- [Project Structure](#-project-structure)
- [License](#-license)
"""

        # --- Auto-detect tech stack (enhanced) ---
        tech_stack = generate_detailed_tech_stack(temp_dir, lang, files)
        # Add badge rendering for tech stack
        import re
        tech_stack_lines = []
        for line in tech_stack.split('\n'):
            # Extract all tech names from the line (after ** and before : or -)
            matches = re.findall(r'\*\*(.*?)\*\*', line)
            for tech in matches:
                badge_url = get_dynamic_badge(tech.strip())
                tech_stack_lines.append(f'![]({badge_url})')
        tech_stack_badges = ' '.join(tech_stack_lines)

        # --- Features (using enhanced smart features generation) ---
        smart_features = generate_smart_features(repo_name, files, lang)
        # Get analysis for specific features
        analysis_for_features = analyze_project_deeply(files, repo_name)
        specific_features = analyze_project_content_and_generate_features(temp_dir, files, analysis_for_features)
        
        # Combine smart features with specific features
        all_features = smart_features + specific_features
        # Remove duplicates while preserving order
        seen = set()
        unique_features = []
        for feature in all_features:
            if feature not in seen:
                seen.add(feature)
                unique_features.append(feature)
        
        features = "\n".join([f"- {feature}" for feature in unique_features])

        # --- Overview (using smart overview generation) ---
        overview = generate_smart_overview(repo_name, files, lang)

        # --- If OpenAI API key is provided, enhance the smart overview with AI ---
        if request.api_key:
            try:
                client = openai.OpenAI(api_key=request.api_key)
                # Use the smart overview as base and enhance it
                base_overview = overview
                ai_prompt = f"""
                Enhance this project overview with more specific details:
                
                Base Overview: {base_overview}
                
                Project: {repo_name}
                Language: {lang}
                Files: {files[:10]}  # Show first 10 files
                
                Generate an improved, more detailed overview (2-3 sentences) that:
                1. Maintains the professional tone
                2. Adds specific technical details
                3. Mentions key features or capabilities
                4. Is more engaging and informative
                
                Return only the enhanced overview text.
                """
                ai_response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are an expert in writing high-quality README.md files for software projects."},
                        {"role": "user", "content": ai_prompt}
                    ]
                )
                enhanced_overview = ai_response.choices[0].message.content.strip()
                if enhanced_overview and len(enhanced_overview) > 50:  # Only use if AI generated something substantial
                    overview = enhanced_overview
                
                # Also enhance features with AI if possible
                try:
                    ai_features_prompt = f"""
                    Based on this project, suggest 2-3 additional specific features:
                    
                    Project: {repo_name}
                    Language: {lang}
                    Current Features: {smart_features[:3]}  # Show first 3 features
                    
                    Generate 2-3 additional specific, technical features that would be relevant.
                    Return only the features as bullet points starting with "- ".
                    """
                    ai_features_response = client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": "You are an expert in software project features and capabilities."},
                            {"role": "user", "content": ai_features_prompt}
                        ]
                    )
                    ai_features = ai_features_response.choices[0].message.content.strip()
                    if ai_features and ai_features.startswith('-'):
                        # Add AI-generated features to existing ones
                        additional_features = [f"- {feature.strip()}" for feature in ai_features.split('\n') if feature.strip().startswith('-')]
                        features = features + "\n" + "\n".join(additional_features)
                except Exception:
                    pass  # Keep original features if AI enhancement fails
            except Exception:
                pass  # fallback to smart overview

        # --- Social and Support Section ---
        social_section = create_social_section(request.twitter_user, request.linkedin_user, request.github_user, request.instagram_user, request.youtube_channel, request.website_url)
        support_section = create_support_section(request.buy_me_a_coffee_user)

        # --- Markdown Template (gitdocify style, no icon, left-aligned) ---
        readme_content = f"""
# {repo_name.replace('-', ' ').title()}

{' '.join(tech_badges)}

{toc}

---

## ✨ Overview

{overview}

---

{social_section}

## 🚀 Features

{features}

---

## 🛠️ Tech Stack

{tech_stack}

## 📊 Languages Used

"""
        # --- Languages Used section (project-based, not GitHub stats) ---
        if language_stats:
            for lang, percent in language_stats:
                # Use shields.io badge for each language
                badge_url = f"https://img.shields.io/badge/{lang.replace(' ', '%20')}-{percent}%25-blue?style=for-the-badge"
                readme_content += f"![{lang}]({badge_url}) "
            readme_content += "\n"
        else:
            readme_content += "No significant languages detected.\n"

        readme_content += f"""

## ⚙️ Installation

```bash
# Clone the repository
# git clone {repo_url}
# Change directory
# cd {repo_name}
# Backend setup (if applicable)
{instructions['setup']}
```

---

## 🏃 Usage

Use the following command to run the project:

```bash
# Run the project
{instructions['run']}
```

---

## 📂 Project Structure

A brief overview of the key files and directories:
```
{repo_name}/
├── {'\n├── '.join(files)}
└── ...
```

---

## 📄 License

{license_info}

{support_section}
---

*This README was automatically generated. Feel free to edit and improve!*
"""
        final_readme = re.sub(r'^  +', '', readme_content, flags=re.MULTILINE).strip()
        final_readme = final_readme.replace("...\n##", "##")
        return {"readme": final_readme}

    except HTTPException as e:
        return {"readme": f"Error: {e.detail}"}
    except Exception as e:
        error_message = str(e)
        if "Repository not found" in error_message:
             return {"readme": "Error: Repository not found. Please check the URL."}
        elif "Authentication failed" in error_message:
             return {"readme": "Error: This is a private repository. Authentication is required."}
        return {"readme": f"An unexpected error occurred: {error_message}"}
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True) 