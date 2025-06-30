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
    for file in os.listdir(repo_path):
        if file.lower().startswith('license'):
            return f"This project is licensed under the terms of the `{file}` file."
    return "No license file found."

def create_social_section(twitter, linkedin):
    if not twitter and not linkedin:
        return ""
    
    links = []
    if twitter:
        links.append(f"[Twitter](https://twitter.com/{twitter})")
    if linkedin:
        links.append(f"[LinkedIn](https://www.linkedin.com/in/{linkedin})")
    
    return f"""
## 🔗 Connect with me

{' | '.join(links)}
"""

def create_support_section(coffee_user):
    if not coffee_user:
        return ""
    return f"""
## 🙏 Support

If you like this project, please consider supporting me.

<a href="https://www.buymeacoffee.com/{coffee_user}" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>
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

@app.post("/generate-readme/")
async def generate_readme(request: RepoRequest):
    repo_url = request.repo_url
    temp_dir = tempfile.mkdtemp()
    try:
        Repo.clone_from(repo_url, temp_dir)
        
        repo_name = repo_url.split('/')[-1].replace('.git', '')
        lang = detect_main_language(temp_dir)
        files = list_main_files(temp_dir)
        instructions = get_setup_and_run_instructions(temp_dir)
        license_info = check_license(temp_dir)

        if request.generation_method == 'ai':
            if not request.api_key:
                raise HTTPException(status_code=400, detail="API Key is required for AI generation.")
            
            context = {
                "repo_name": repo_name,
                "lang": lang,
                "files": files,
                "instructions": instructions,
                "license_info": license_info,
                "social": {"twitter": request.twitter_user, "linkedin": request.linkedin_user},
                "support": {"coffee": request.buy_me_a_coffee_user},
            }
            ai_readme = generate_readme_with_ai(request.api_key, context)
            return {"readme": ai_readme}

        # Template-based generation (existing logic)
        social_section = create_social_section(request.twitter_user, request.linkedin_user)
        support_section = create_support_section(request.buy_me_a_coffee_user)

        readme_content = f"""
# {repo_name.replace('-', ' ').title()}

![Language Badge](https://img.shields.io/badge/language-{lang.replace(' ', '%20')}-blue.svg)

A brief one-sentence description of your project goes here. Explain what it does and who it's for.

{social_section}

## ✨ Features

- **Feature 1:** Describe a key feature of your project.
- **Feature 2:** Add another cool feature.
- **Feature 3:** And one more.

## 🛠️ Tech Stack

- **Main Language:** {lang}
- *You can add other technologies used, like frameworks or databases.*

## ⚙️ Setup and Installation

Follow these steps to get your development environment set up:

1.  **Clone the repository:**
    ```bash
    git clone {repo_url}
    cd {repo_name}
    ```

2.  **Install dependencies:**
    ```bash
    {instructions['setup']}
    ```

## 🚀 How to Run

Use the following command to run the project:

```bash
{instructions['run']}
```

## 📂 Project Structure

A brief overview of the key files and directories:
```
{repo_name}/
├── {"\n├── ".join(files)}
└── ...
```

## 📜 License

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