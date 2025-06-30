import React, { useState, useEffect } from 'react';
import './App.css';
import { FiSettings, FiSun, FiMoon } from 'react-icons/fi';

function App() {
  const [repoUrl, setRepoUrl] = useState('');
  const [readme, setReadme] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [isCopied, setIsCopied] = useState(false);

  // Optional fields
  const [buyMeCoffeeUser, setBuyMeCoffeeUser] = useState('');
  const [twitterUser, setTwitterUser] = useState('');
  const [linkedinUser, setLinkedinUser] = useState('');

  // AI Feature State
  const [showSettings, setShowSettings] = useState(false);
  const [apiKey, setApiKey] = useState('');
  const [tempApiKey, setTempApiKey] = useState('');
  const [generationMethod, setGenerationMethod] = useState('template'); // 'template' or 'ai'

  const [theme, setTheme] = useState('light');

  useEffect(() => {
    const storedApiKey = localStorage.getItem('openai_api_key');
    if (storedApiKey) {
      setApiKey(storedApiKey);
      setTempApiKey(storedApiKey);
    }
    const savedTheme = localStorage.getItem('theme') || 'light';
    setTheme(savedTheme);
    document.body.className = savedTheme + '-mode';
  }, []);

  const handleSaveSettings = () => {
    setApiKey(tempApiKey);
    localStorage.setItem('openai_api_key', tempApiKey);
    setShowSettings(false);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (generationMethod === 'ai' && !apiKey) {
      setError('Please set your OpenAI API key in the settings.');
      setShowSettings(true);
      return;
    }
    setLoading(true);
    setError('');
    setReadme('');
    try {
      const payload = {
        repo_url: repoUrl,
        buy_me_a_coffee_user: buyMeCoffeeUser,
        twitter_user: twitterUser,
        linkedin_user: linkedinUser,
        generation_method: generationMethod,
        api_key: apiKey,
      };
      const response = await fetch('http://localhost:8000/generate-readme/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!response.ok) throw new Error('Failed to generate README. Check the repo URL and backend server.');
      const data = await response.json();
      if (data.readme.startsWith('Error:')) {
        setError(data.readme);
      } else {
        setReadme(data.readme);
      }
    } catch (err) {
      setError(err.message);
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

  const toggleTheme = () => {
    const newTheme = theme === 'light' ? 'dark' : 'light';
    setTheme(newTheme);
    localStorage.setItem('theme', newTheme);
    document.body.className = newTheme + '-mode';
  };

  return (
    <div className="App">
      <button onClick={toggleTheme} className="theme-toggle-button">
        {theme === 'light' ? <FiMoon /> : <FiSun />}
      </button>
      <FiSettings className="settings-icon" onClick={() => setShowSettings(true)} />
      
      {showSettings && (
        <div className="modal-overlay" onClick={() => setShowSettings(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <h3>Settings</h3>
            <div className="optional-input-group">
              <label htmlFor="apiKey">OpenAI API Key</label>
              <input
                type="password"
                id="apiKey"
                className="optional-input"
                placeholder="sk-..."
                value={tempApiKey}
                onChange={e => setTempApiKey(e.target.value)}
              />
            </div>
            <button className="generate-button" onClick={handleSaveSettings} style={{marginTop: '15px'}}>
              Save
            </button>
          </div>
        </div>
      )}

      <h2>Auto README Generator</h2>

      <div className="generation-toggle">
        <button
          type="button"
          className={`method-button ${generationMethod === 'template' ? 'active' : ''}`}
          onClick={() => setGenerationMethod('template')}
        >
          Template
        </button>
        <button
          type="button"
          className={`method-button ${generationMethod === 'ai' ? 'active' : ''}`}
          onClick={() => setGenerationMethod('ai')}
        >
          AI (GPT)
        </button>
      </div>

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
          <button type="submit" className="generate-button" disabled={loading}>
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
            >
              {isCopied ? 'Copied!' : 'Copy'}
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
    </div>
  );
}

export default App;
