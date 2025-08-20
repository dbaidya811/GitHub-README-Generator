// Main client-side logic for GitHub README Generator
(function () {
  const overlay = document.getElementById('loadingOverlay');
  const pickBtn = document.getElementById('pickFromGithubBtn');

  function showLoading(text) {
    if (!overlay) return;
    const label = overlay.querySelector('.text-muted');
    if (label && text) label.textContent = text;
    overlay.classList.remove('d-none');
  }

  function hideLoading() {
    if (!overlay) return;
    overlay.classList.add('d-none');
  }

  // Show overlay on form submit
  const forms = document.querySelectorAll('form[action*="index"]');
  forms.forEach(f => {
    f.addEventListener('submit', () => {
      showLoading('Generating README...');
    });
  });

  // Specific handling for Generate form: show spinner and disable button
  const genForm = document.getElementById('generateForm');
  if (genForm) {
    genForm.addEventListener('submit', () => {
      const genBtn = document.getElementById('generateBtn');
      const spinner = document.getElementById('genSpinner');
      if (genBtn) {
        genBtn.disabled = true;
        genBtn.classList.add('disabled');
      }
      if (spinner) spinner.classList.remove('d-none');
      showLoading('Generating README...');
    });
  }

  // Repo picker
  if (pickBtn) {
    pickBtn.addEventListener('click', async () => {
      try {
        // Check auth
        const meResp = await fetch('/api/me', { credentials: 'same-origin' });
        const me = await meResp.json();
        if (!me.authenticated) {
          // Redirect to login
          window.location.href = '/login';
          return;
        }

        // Open modal
        const modalEl = document.getElementById('repoPickerModal');
        const repoList = document.getElementById('repoList');
        const repoEmpty = document.getElementById('repoEmpty');
        const repoSearch = document.getElementById('repoSearch');
        if (!modalEl) return;
        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        repoList.innerHTML = '<div class="text-center text-muted py-3">Loading repositories...</div>';
        repoEmpty.classList.add('d-none');
        modal.show();

        // Fetch repos
        const resp = await fetch('/api/repos', { credentials: 'same-origin' });
        if (!resp.ok) {
          repoList.innerHTML = '<div class="text-danger">Failed to fetch repositories.</div>';
          return;
        }
        const data = await resp.json();
        const repos = (data.repos || []).sort((a,b) => (a.full_name || '').localeCompare(b.full_name || ''));

        function render(list) {
          if (!list.length) {
            repoList.innerHTML = '';
            repoEmpty.classList.remove('d-none');
            return;
          }
          repoEmpty.classList.add('d-none');
          repoList.innerHTML = '';
          list.forEach(r => {
            const item = document.createElement('a');
            item.href = '#';
            item.className = 'list-group-item list-group-item-action d-flex justify-content-between align-items-center';
            item.innerHTML = `
              <div>
                <div class="fw-semibold">${r.full_name}</div>
                <div class="small text-muted">${r.description || ''}</div>
              </div>
              <span class="badge ${r.private ? 'bg-warning text-dark' : 'bg-success'}">${r.private ? 'Private' : (r.language || 'Public')}</span>
            `;
            item.addEventListener('click', (e) => {
              e.preventDefault();
              const input = document.getElementById('repo_url');
              if (input) {
                input.value = `https://github.com/${r.full_name}`;
              }
              modal.hide();
            });
            repoList.appendChild(item);
          });
        }

        render(repos);

        // Search filter
        if (repoSearch) {
          repoSearch.addEventListener('input', () => {
            const q = repoSearch.value.toLowerCase();
            const filtered = repos.filter(r =>
              (r.full_name || '').toLowerCase().includes(q) ||
              (r.description || '').toLowerCase().includes(q)
            );
            render(filtered);
          }, { passive: true });
        }
      } catch (e) {
        console.error(e);
        alert('Something went wrong while loading your repositories.');
      }
    });
  }

  // Expose for other scripts if needed
  window.AppLoading = { show: showLoading, hide: hideLoading };
})();

// Publish README handler on result page
(function () {
  const btn = document.getElementById('publishBtn');
  const modalEl = document.getElementById('publishModal');
  if (!btn || !modalEl) return;
  const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
  const confirmBtn = document.getElementById('publishConfirmBtn');
  const msgInput = document.getElementById('publishMessage');
  const repoInput = document.getElementById('publishRepo');
  const branchInput = document.getElementById('publishBranch');
  const errDiv = document.getElementById('publishError');

  btn.addEventListener('click', () => {
    // Prefill and open modal
    const fullName = btn.getAttribute('data-full-name') || '';
    const branch = btn.getAttribute('data-default-branch') || '';
    if (repoInput) repoInput.value = fullName;
    if (branchInput) branchInput.value = branch;
    if (errDiv) {
      errDiv.classList.add('d-none');
      errDiv.textContent = '';
    }
    modal.show();
  });

  async function publishNow() {
    try {
      const pre = document.getElementById('readme-content');
      const content = pre ? pre.textContent : '';
      const fullName = repoInput ? repoInput.value : '';
      const branch = branchInput ? branchInput.value : '';
      const message = msgInput ? msgInput.value : '';
      if (!fullName || !content) {
        if (errDiv) {
          errDiv.textContent = 'Missing repository or README content.';
          errDiv.classList.remove('d-none');
        }
        return;
      }
      confirmBtn.disabled = true;
      if (window.AppLoading) window.AppLoading.show('Publishing to GitHub...');

      const resp = await fetch('/api/publish', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ full_name: fullName, content, message, branch })
      });

      if (resp.status === 401) {
        window.location.href = '/login';
        return;
      }

      const data = await resp.json();
      if (!resp.ok || !data.success) {
        const details = data && data.details && data.details.message ? `\n${data.details.message}` : '';
        throw new Error((data && data.error) ? data.error + details : 'Failed to publish README');
      }

      modal.hide();
      alert('README published successfully!');
    } catch (e) {
      console.error(e);
      if (errDiv) {
        errDiv.textContent = e && e.message ? e.message : 'Failed to publish';
        errDiv.classList.remove('d-none');
      } else {
        alert('Error: ' + (e && e.message ? e.message : 'Failed to publish'));
      }
    } finally {
      confirmBtn.disabled = false;
      if (window.AppLoading) window.AppLoading.hide();
    }
  }

  confirmBtn.addEventListener('click', publishNow);
})();
