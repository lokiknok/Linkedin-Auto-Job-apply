// Settings & Profile Management Logic

const settingsView = {
  init() {
    const fileInput = document.getElementById('resume-file-input');
    if (fileInput) {
      fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
          this.uploadResume(e.target.files[0]);
        }
      });
    }
  },

  async loadSettings() {
    try {
      const data = await app.apiGet('/api/settings');
      const profile = data.profile || {};
      const prefs = data.preferences || {};
      const tg = data.telegram || {};

      // Profile
      document.getElementById('set-first-name').value = profile.first_name || '';
      document.getElementById('set-last-name').value = profile.last_name || '';
      document.getElementById('set-email').value = profile.email || '';
      document.getElementById('set-phone').value = profile.phone || '';
      document.getElementById('set-city').value = profile.location_city || '';
      document.getElementById('set-country').value = profile.location_country || '';
      document.getElementById('set-linkedin').value = profile.linkedin_url || '';
      document.getElementById('set-portfolio').value = profile.portfolio_url || '';

      // Preferences
      document.getElementById('set-job-titles').value = (prefs.job_titles || []).join(', ');
      document.getElementById('set-locations').value = (prefs.locations || []).join(', ');
      document.getElementById('set-skills').value = (prefs.keywords || []).join(', ');
      document.getElementById('set-exp-level').value = prefs.experience_level || 'Entry level';
      document.getElementById('set-years-exp').value = profile.years_of_experience || 2;
      document.getElementById('set-remote').checked = !!prefs.remote;

      // Resume
      const resumeNameSpan = document.getElementById('resume-filename');
      if (prefs.resume_path) {
        const name = prefs.resume_path.split(/[\\/]/).pop();
        resumeNameSpan.innerText = `Current: ${name}`;
      } else {
        resumeNameSpan.innerText = 'No resume selected';
      }

      // Sync Search Inputs on Jobs Page
      const searchKey = document.getElementById('input-search-keywords');
      const searchLoc = document.getElementById('input-search-location');
      if (searchKey && !searchKey.value) searchKey.value = (prefs.job_titles || []).join(', ');
      if (searchLoc && !searchLoc.value) searchLoc.value = (prefs.locations || []).join(', ');

      // Telegram Status Banner
      const tgWarn = document.getElementById('telegram-warning');
      const tgSucc = document.getElementById('telegram-success');
      if (tg.configured) {
        tgWarn.style.display = 'none';
        tgSucc.style.display = 'flex';
      } else {
        tgWarn.style.display = 'flex';
        tgSucc.style.display = 'none';
      }

      // AI Status
      const ai = data.ai || {};
      const aiProvider = document.getElementById('ai-status-provider');
      const aiBadge = document.getElementById('ai-status-badge');
      const aiModel = document.getElementById('ai-status-model');
      if (aiProvider && aiBadge) {
        aiProvider.innerText = ai.provider || 'Heuristic / Rule-based';
        if (ai.configured) {
          aiBadge.className = 'badge';
          aiBadge.style.background = 'var(--success-light)';
          aiBadge.style.color = 'var(--success)';
          aiBadge.innerText = 'Active';
          if (aiModel) aiModel.innerText = `Model: ${ai.model || 'Standard'}`;
        } else {
          aiBadge.className = 'badge';
          aiBadge.style.background = 'var(--warning-light)';
          aiBadge.style.color = 'var(--warning)';
          aiBadge.innerText = 'Rule-based Fallback';
          if (aiModel) aiModel.innerText = 'Add GEMINI_API_KEY or OPENAI_API_KEY in .env for generative AI';
        }
      }

    } catch (e) {
      app.toast('Failed to load settings: ' + e.message, 'error');
    }
  },

  async saveSettings() {
    const profile = {
      first_name: document.getElementById('set-first-name').value.trim(),
      last_name: document.getElementById('set-last-name').value.trim(),
      email: document.getElementById('set-email').value.trim(),
      phone: document.getElementById('set-phone').value.trim(),
      location_city: document.getElementById('set-city').value.trim(),
      location_country: document.getElementById('set-country').value.trim(),
      linkedin_url: document.getElementById('set-linkedin').value.trim(),
      portfolio_url: document.getElementById('set-portfolio').value.trim(),
      years_of_experience: parseInt(document.getElementById('set-years-exp').value) || 2,
    };

    const jobTitles = document.getElementById('set-job-titles').value.split(',').map(s => s.trim()).filter(Boolean);
    const locations = document.getElementById('set-locations').value.split(',').map(s => s.trim()).filter(Boolean);
    const skills = document.getElementById('set-skills').value.split(',').map(s => s.trim()).filter(Boolean);

    const preferences = {
      job_titles: jobTitles,
      locations: locations,
      keywords: skills,
      experience_level: document.getElementById('set-exp-level').value,
      remote: document.getElementById('set-remote').checked,
    };

    try {
      const res = await app.apiPut('/api/settings', {
        profile: profile,
        preferences: preferences
      });
      app.toast('Settings and profile saved successfully!', 'success');
      await this.loadSettings();
    } catch (e) {
      app.toast('Failed to save settings: ' + e.message, 'error');
    }
  },

  async uploadResume(file) {
    const statusAlert = document.getElementById('resume-status-alert');
    statusAlert.innerHTML = `<span style="color: var(--primary);">⏳ Validating and uploading PDF...</span>`;

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('/api/settings/resume', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();

      if (!res.ok || !data.success) {
        statusAlert.innerHTML = `<span style="color: var(--danger);">🚨 ${data.message || 'Upload failed'}</span>`;
        app.toast('Resume validation failed.', 'error');
        return;
      }

      statusAlert.innerHTML = `<span style="color: var(--success);">✅ ${data.filename} (${data.size_kb} KB) validated and ready.</span>`;
      document.getElementById('resume-filename').innerText = `Current: ${data.filename}`;
      app.toast('Resume uploaded successfully!', 'success');
    } catch (e) {
      statusAlert.innerHTML = `<span style="color: var(--danger);">🚨 ${e.message}</span>`;
      app.toast('Upload error: ' + e.message, 'error');
    }
  },

  async testTelegram() {
    const resultSpan = document.getElementById('telegram-test-result');
    const btn = document.getElementById('btn-test-telegram');
    resultSpan.innerText = 'Connecting...';
    btn.disabled = true;

    try {
      const res = await app.apiPost('/api/telegram/test');
      if (res.success) {
        resultSpan.innerHTML = `<span style="color: var(--success);">✅ ${res.message}</span>`;
        app.toast('Telegram test notification delivered!', 'success');
      } else {
        resultSpan.innerHTML = `<span style="color: var(--danger);">⚠️ ${res.message}</span>`;
        app.toast('Telegram connection test failed.', 'error');
      }
    } catch (e) {
      resultSpan.innerHTML = `<span style="color: var(--danger);">🚨 ${e.message}</span>`;
      app.toast('Telegram test error: ' + e.message, 'error');
    } finally {
      btn.disabled = false;
    }
  }
};

window.addEventListener('DOMContentLoaded', () => {
  settingsView.init();
});

