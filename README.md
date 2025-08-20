# GitHub Repository Analyzer and README Generator

This Python tool analyzes GitHub repositories and generates well-structured README.md files automatically.

## Features

- Analyzes GitHub repositories using the GitHub API
- Extracts important repository information (description, languages, contributors, etc.)
- Generates professional README.md files with:
  - Badges (license, language)
  - Table of contents
  - Installation instructions
  - Usage examples
  - Features section
  - Contributing guidelines
  - License information

## Prerequisites

- Python 3.6+
- GitHub Personal Access Token (optional but recommended to avoid rate limits)

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/github-readme-generator.git
   cd github-readme-generator
   ```

2. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Basic usage:
```bash
python github_analyzer.py https://github.com/username/repository
```

With custom output file:
```bash
python github_analyzer.py https://github.com/username/repository -o CUSTOM_README.md
```

Using a GitHub Personal Access Token (recommended):
```bash
python github_analyzer.py https://github.com/username/repository -t your_github_token
```

### Getting a GitHub Personal Access Token

1. Go to GitHub > Settings > Developer Settings > Personal Access Tokens > Tokens (classic)
2. Generate a new token with the `public_repo` scope
3. Copy the token and use it with the `-t` or `--token` flag

## Example

```bash
python github_analyzer.py https://github.com/octocat/Hello-World -o MY_README.md
```

This will analyze the repository and generate a `MY_README.md` file in the current directory.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
