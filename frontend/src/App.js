import React, { useState, useEffect } from 'react';
import './App.css';
import { FiSun, FiMoon } from 'react-icons/fi';
import ReactMarkdown from 'react-markdown';

function App() {
  const [repoUrl, setRepoUrl] = useState('');
  const [readme, setReadme] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [isCopied, setIsCopied] = useState(false);
  const [isDownloaded, setIsDownloaded] = useState(false);

  // Optional fields
  const [buyMeCoffeeUser, setBuyMeCoffeeUser] = useState('');
  const [twitterUser, setTwitterUser] = useState('');
  const [linkedinUser, setLinkedinUser] = useState('');

  const [theme, setTheme] = useState('light');
  const [showPreview, setShowPreview] = useState(false);

  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') || 'light';
    setTheme(savedTheme);
    document.body.className = savedTheme + '-mode';
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setReadme('');
    try {
      const payload = {
        repo_url: repoUrl,
        buy_me_a_coffee_user: buyMeCoffeeUser,
        twitter_user: twitterUser,
        linkedin_user: linkedinUser,
        generation_method: 'template',
      };
      const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
      // Add timeout logic
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 seconds
      let response;
      try {
        response = await fetch(`${apiUrl}/generate-readme/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
          signal: controller.signal
        });
      } catch (err) {
        if (err.name === 'AbortError') {
          setError('Request timed out or server not responding.');
        } else {
          setError('Network error: ' + err.message);
        }
        setLoading(false);
        clearTimeout(timeoutId);
        return;
      }
      clearTimeout(timeoutId);
      if (!response.ok) {
        setError('Failed to generate README. Check the repo URL and backend server.');
        setLoading(false);
        return;
      }
      const data = await response.json();
      if (data.readme && data.readme.startsWith('Error:')) {
        setError(data.readme);
      } else if (data.readme) {
        setReadme(data.readme);
      } else {
        setError('Unexpected server response.');
      }
    } catch (err) {
      setError('Unexpected error: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(readme).then(() => {
      setIsCopied(true);
      setTimeout(() => {
        setIsCopied(false);
      }, 2000); // Reset after 2 seconds
    });
  };

  // const handleDownload = () => {
  //   const blob = new Blob([readme], { type: 'text/markdown' });
  //   const url = URL.createObjectURL(blob);
  //   const a = document.createElement('a');
  //   a.href = url;
  //   a.download = 'README.md';
  //   document.body.appendChild(a);
  //   a.click();
  //   document.body.removeChild(a);
  //   URL.revokeObjectURL(url);
  //   setIsDownloaded(true);
  //   setTimeout(() => setIsDownloaded(false), 2000);
  // };

  const toggleTheme = () => {
    const newTheme = theme === 'light' ? 'dark' : 'light';
    setTheme(newTheme);
    localStorage.setItem('theme', newTheme);
    document.body.className = newTheme + '-mode';
  };

  return (
    <div className="App">
      <button onClick={toggleTheme} className="theme-toggle-button" aria-label="Toggle theme">
        {theme === 'light' ? <FiMoon /> : <FiSun />}
      </button>
      
      <h2>Auto README Generator</h2>

      <form onSubmit={handleSubmit}>
        <div className="repo-form">
          <input
            type="text"
            className="repo-input"
            placeholder="Enter GitHub repo URL"
            value={repoUrl}
            onChange={e => setRepoUrl(e.target.value)}
            required
          />
          <button type="submit" className="generate-button" disabled={loading} aria-label="Generate README">
            {loading ? 'Generating...' : 'Generate'}
          </button>
        </div>
        
        <div className="optional-section">
            <h3>Optional: Add Your Info</h3>
            <div className="optional-inputs">
                <div className="optional-input-group">
                  <label htmlFor="buyMeCoffee">Buy Me a Coffee Username</label>
                  <input
                    type="text"
                    id="buyMeCoffee"
                    className="optional-input"
                    placeholder="e.g., yourname"
                    value={buyMeCoffeeUser}
                    onChange={e => setBuyMeCoffeeUser(e.target.value)}
                  />
                </div>
                <div className="optional-input-group">
                  <label htmlFor="twitter">Twitter Username</label>
                  <input
                    type="text"
                    id="twitter"
                    className="optional-input"
                    placeholder="e.g., yourhandle"
                    value={twitterUser}
                    onChange={e => setTwitterUser(e.target.value)}
                  />
                </div>
                <div className="optional-input-group">
                  <label htmlFor="linkedin">LinkedIn Username</label>
                  <input
                    type="text"
                    id="linkedin"
                    className="optional-input"
                    placeholder="e.g., your-profile-id"
                    value={linkedinUser}
                    onChange={e => setLinkedinUser(e.target.value)}
                  />
                </div>
            </div>
        </div>
      </form>
      
      {error && <div className="error-message">{error}</div>}
      {readme && (
        <div className="readme-container">
          <div className="readme-header">
            <h3>Generated README.md</h3>
            <button
              className={`copy-button ${isCopied ? 'copied' : ''}`}
              onClick={handleCopy}
              disabled={isCopied}
              aria-label="Copy README"
            >
              {isCopied ? 'Copied!' : 'Copy'}
            </button>
            <button
              className="preview-button"
              onClick={() => setShowPreview(true)}
              aria-label="Preview README"
            >
              Preview
            </button>
          </div>
          <textarea
            className="readme-textarea"
            value={readme}
            readOnly
            rows={20}
          />
        </div>
      )}
      {showPreview && (
        <div className="modal-overlay" onClick={() => setShowPreview(false)}>
          <div className={`modal-content markdown-body ${theme}-mode`} style={{ maxWidth: '900px', maxHeight: '85vh', overflowY: 'auto', background: theme === 'dark' ? '#222' : '#fff' }} onClick={e => e.stopPropagation()}>
            <h3>README Preview</h3>
            <div style={{ padding: '1em', borderRadius: '8px', minHeight: '200px' }}>
              <ReactMarkdown>{readme}</ReactMarkdown>
            </div>
            <button className="generate-button" style={{ marginTop: '15px' }} onClick={() => setShowPreview(false)} aria-label="Close Preview">
              Close Preview
            </button>
          </div>
        </div>
      )}
      
      <a 
        href="https://www.buymeacoffee.com/dbaidya811e" 
          target="_blank"
          rel="noopener noreferrer"
        className="buy-me-coffee-link"
        >
        <img 
          src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" 
          alt="Buy Me A Coffee" 
        />
        </a>
      {isDownloaded && <div className="success-message">README.md downloaded!</div>}
    </div>
  );
}

export default App;
