// Jobs View & Application Preparation Logic

const jobsView = {
  isSearching: false,

  init() {
    document.getElementById('btn-run-search').addEventListener('click', () => {
      this.startSearch();
    });

    document.getElementById('select-min-score').addEventListener('change', () => {
      this.loadJobs();
    });
  },

  async loadJobs() {
    const container = document.getElementById('jobs-list-container');
    const minScore = document.getElementById('select-min-score').value || 0;

    try {
      const data = await app.apiGet(`/api/jobs?min_score=${minScore}`);
      const jobs = data.jobs || [];

      if (jobs.length === 0) {
        container.innerHTML = `
          <div style="text-align: center; padding: 40px; color: var(--text-muted);">
            No jobs found matching score ${minScore}%+. Click "Search Jobs" to run a fresh scan.
          </div>
        `;
        return;
      }

      container.innerHTML = jobs.map(job => this.renderJobCard(job)).join('');
    } catch (e) {
      container.innerHTML = `<div style="color: var(--danger); padding: 20px;">Error loading jobs: ${e.message}</div>`;
    }
  },

  async startSearch() {
    if (this.isSearching) return;
    this.isSearching = true;

    const btn = document.getElementById('btn-run-search');
    const container = document.getElementById('jobs-list-container');
    const originalText = btn.innerHTML;

    btn.disabled = true;
    btn.innerHTML = `<span>⏳</span> Searching...`;
    container.innerHTML = `
      <div style="text-align: center; padding: 40px; color: var(--primary);">
        <div style="font-size: 24px; margin-bottom: 8px;">⏳</div>
        <strong>Searching & Scoring LinkedIn Job Listings...</strong>
        <p style="font-size: 13px; color: var(--text-muted); margin-top: 4px;">Matching Title (40%), Skills (30%), Location (20%), and Experience (10%).</p>
      </div>
    `;

    const keywordsVal = document.getElementById('input-search-keywords').value;
    const locationVal = document.getElementById('input-search-location').value;

    const keywords = keywordsVal ? keywordsVal.split(',').map(s => s.trim()).filter(Boolean) : null;
    const locations = locationVal ? locationVal.split(',').map(s => s.trim()).filter(Boolean) : null;

    try {
      const res = await app.apiPost('/api/jobs/search', {
        keywords: keywords,
        locations: locations,
        use_mock_if_offline: true
      });

      app.toast(res.message || 'Job search completed!', 'success');
      await this.loadJobs();
      await dashboardView.loadStats();
    } catch (e) {
      app.toast('Job search failed: ' + e.message, 'error');
      container.innerHTML = `<div style="color: var(--danger); padding: 20px;">Search failed: ${e.message}</div>`;
    } finally {
      this.isSearching = false;
      btn.disabled = false;
      btn.innerHTML = originalText;
    }
  },

  renderJobCard(job) {
    const score = Math.round(job.match_score || 0);
    const scoreClass = score >= 75 ? 'high' : (score >= 50 ? 'medium' : 'low');

    return `
      <div class="job-card">
        <div class="job-card-header">
          <div>
            <a href="${job.url}" target="_blank" class="job-title">${job.title}</a>
            <div class="job-company">${job.company} • 📍 ${job.location}</div>
          </div>
          <div class="badge badge-score ${scoreClass}">
            ⭐ ${score}% Match
          </div>
        </div>

        <div class="job-meta">
          <span class="badge">💼 ${job.employment_type || 'Full-time'}</span>
          <span class="badge">🎯 ${job.experience_level || 'Entry level'}</span>
          ${job.easy_apply ? '<span class="badge" style="background: var(--primary-light); color: var(--primary);">⚡ Easy Apply</span>' : ''}
          ${job.salary ? `<span class="badge">💵 ${job.salary}</span>` : ''}
          <span class="badge">📅 ${job.posted_date || 'Recent'}</span>
        </div>

        <div class="job-desc-snippet">
          ${job.description || 'No description provided.'}
        </div>

        <div class="job-card-actions">
          <div style="display: flex; gap: 8px;">
            <button class="btn btn-secondary btn-sm" onclick="jobsView.showDescriptionModal('${job.id}')">
              📄 Details
            </button>
            <a href="${job.url}" target="_blank" class="btn btn-secondary btn-sm">
              🔗 Open on LinkedIn
            </a>
          </div>

          <button class="btn btn-primary" onclick="jobsView.prepareApplication('${encodeURIComponent(job.url)}')">
            <span>⚡</span> 1-Click Auto Apply
          </button>
        </div>
      </div>
    `;
  },

  async showDescriptionModal(jobId) {
    try {
      const job = await app.apiGet(`/api/jobs/${jobId}`);
      const bodyHtml = `
        <div style="display: flex; flex-direction: column; gap: 14px;">
          <div>
            <h2 style="font-size: 18px; font-weight: 700;">${job.title}</h2>
            <div style="color: var(--text-muted); font-size: 14px;">${job.company} • 📍 ${job.location}</div>
          </div>
          <div class="job-meta">
            <span class="badge badge-score high">⭐ ${Math.round(job.match_score)}% Match</span>
            <span class="badge">💼 ${job.employment_type || 'Full-time'}</span>
            <span class="badge">🎯 ${job.experience_level || 'Entry level'}</span>
          </div>
          <div>
            <h4 style="font-size: 14px; font-weight: 600; margin-bottom: 6px;">Job Description</h4>
            <div style="font-size: 13px; line-height: 1.6; white-space: pre-wrap; background: #f8fafc; padding: 14px; border-radius: 8px; max-height: 350px; overflow-y: auto;">
              ${job.description || 'No detailed description available.'}
            </div>
          </div>
        </div>
      `;

      const footerHtml = `
        <button class="btn btn-secondary" onclick="app.closeModal()">Close</button>
        <button class="btn btn-primary" onclick="app.closeModal(); jobsView.prepareApplication('${encodeURIComponent(job.url)}')">
          <span>⚡</span> 1-Click Auto Apply
        </button>
      `;

      app.openModal('Job Details', bodyHtml, footerHtml);
    } catch (e) {
      app.toast('Failed to load job details: ' + e.message, 'error');
    }
  },

  async prepareApplication(encodedJobUrl) {
    const jobUrl = decodeURIComponent(encodedJobUrl);

    // Initial Loading Modal with Animated Steps
    const loadingHtml = `
      <div style="text-align: center; padding: 20px;">
        <div style="font-size: 36px; margin-bottom: 12px;">⚡</div>
        <h3 style="font-size: 17px; font-weight: 700; margin-bottom: 6px;">1-Click Auto Apply Assistant Running</h3>
        <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 16px;">
          The assistant is performing automation in the open browser:
        </p>

        <div style="text-align: left; background: #f8fafc; padding: 14px 18px; border-radius: 10px; font-size: 13px; display: flex; flex-direction: column; gap: 10px; border: 1px solid var(--border);">
          <div>🔄 <strong>Step 1:</strong> Opening job page on LinkedIn...</div>
          <div>✍️ <strong>Step 2:</strong> Detecting & auto-filling profile inputs...</div>
          <div>📄 <strong>Step 3:</strong> Attaching validated PDF resume...</div>
          <div>🤖 <strong>Step 4:</strong> Generating AI suggestions for custom questions...</div>
          <div>⏸️ <strong>Step 5:</strong> Stopping before final submit for your safety.</div>
        </div>

        <div style="margin-top: 14px; font-size: 12px; color: var(--primary); font-weight: 600;">
          Please wait a few seconds...
        </div>
      </div>
    `;
    app.openModal('Auto Apply Assistant', loadingHtml, '<button class="btn btn-secondary" disabled>Automating...</button>');

    try {
      const res = await app.apiPost('/api/application/prepare', { job_url: jobUrl });

      if (!res.success) {
        const errHtml = `
          <div class="alert-banner warning">
            <div>
              <strong>⚠️ Action Required:</strong><br>
              ${res.message || 'Could not complete automatic preparation.'}
            </div>
          </div>
          <p style="font-size: 13px; margin-top: 12px;">
            Please ensure the browser window is open and you are logged into LinkedIn.
          </p>
        `;
        const errFooter = `
          <button class="btn btn-secondary" onclick="app.closeModal()">Close</button>
          <button class="btn btn-primary" onclick="app.resumeBrowserSession(); app.closeModal();">
            <span>✅</span> Verify Login in Browser
          </button>
        `;
        app.openModal('Application Notice', errHtml, errFooter);
        return;
      }

      const appData = res.application || {};
      const actions = res.actions || [];

      // Success / Review Modal with clear acknowledgment
      const reviewHtml = `
        <div style="display: flex; flex-direction: column; gap: 14px;">
          <div class="alert-banner success" style="border-left: 4px solid var(--success);">
            <div>
              <strong>🎉 Auto-Preparation Finished Successfully!</strong><br>
              All standard profile fields and your resume have been attached.
            </div>
          </div>

          <div style="background: #ffffff; border: 1px solid var(--border); padding: 14px; border-radius: 8px;">
            <h3 style="font-size: 16px; font-weight: 700; color: var(--text-main);">${appData.job_title || 'Position'}</h3>
            <div style="color: var(--text-muted); font-size: 13px;">🏢 ${appData.company || ''} • 📍 ${appData.location || ''}</div>
          </div>

          <div>
            <h4 style="font-size: 13px; font-weight: 700; margin-bottom: 6px;">Automated Actions Acknowledged:</h4>
            <ul style="font-size: 13px; padding-left: 20px; line-height: 1.6; color: var(--text-main);">
              ${actions.map(a => `<li>✅ ${a}</li>`).join('')}
            </ul>
          </div>

          <div style="background: var(--warning-light); border: 1px solid #fce2a6; color: #8f4b00; padding: 14px; border-radius: 8px; font-size: 13px;">
            <strong>⚠️ Final Step (Human-in-the-Loop):</strong>
            <ol style="margin-top: 6px; padding-left: 18px; line-height: 1.5;">
              <li>Look at the open <strong>LinkedIn Chromium browser window</strong> on your screen.</li>
              <li>Review the filled form and click the final <strong>"Submit application"</strong> button on LinkedIn.</li>
              <li>Click the green <strong>"Mark as Applied"</strong> button below to save your confirmation.</li>
            </ol>
          </div>
        </div>
      `;

      const footerHtml = `
        <button class="btn btn-secondary" onclick="app.closeModal()">Close</button>
        <button class="btn btn-success" style="font-weight: 700;" onclick="applicationsView.markApplied(${appData.id})">
          ✅ Mark as Applied (Sent to DB & Telegram)
        </button>
      `;

      app.openModal('Application Ready for Final Submit', reviewHtml, footerHtml);
      app.toast('Application prepared! Please submit on LinkedIn.', 'info');
      await dashboardView.loadStats();

    } catch (e) {
      app.toast('Preparation failed: ' + e.message, 'error');
      app.openModal('Error', `<div class="alert-banner error">🚨 Error: ${e.message}</div>`);
    }
  }
};

window.addEventListener('DOMContentLoaded', () => {
  jobsView.init();
});

