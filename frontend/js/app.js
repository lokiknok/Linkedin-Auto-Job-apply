// Core Application & Navigation Manager

const app = {
  activeView: 'dashboard',
  browserRunning: false,
  browserLoggedIn: false,

  init() {
    this.bindEvents();
    this.setupRouter();
    this.startBrowserPolling();
    this.refreshDashboard();
  },

  bindEvents() {
    // Navigation Buttons
    document.querySelectorAll('.nav-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const view = e.currentTarget.getAttribute('data-view');
        this.navigate(view);
      });
    });

    // Browser Toggle Button
    document.getElementById('btn-toggle-browser').addEventListener('click', () => {
      this.toggleBrowser();
    });

    // Quick Search Button
    document.getElementById('btn-quick-search').addEventListener('click', () => {
      this.navigate('jobs');
      jobsView.startSearch();
    });
  },

  setupRouter() {
    window.addEventListener('hashchange', () => {
      const hash = window.location.hash.replace('#', '') || 'dashboard';
      this.navigate(hash, false);
    });

    const initial = window.location.hash.replace('#', '') || 'dashboard';
    this.navigate(initial, false);
  },

  navigate(viewId, updateHash = true) {
    if (updateHash) {
      window.location.hash = viewId;
    }
    this.activeView = viewId;

    // Update active tab buttons
    document.querySelectorAll('.nav-btn').forEach(btn => {
      if (btn.getAttribute('data-view') === viewId) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });

    // Toggle active section
    document.querySelectorAll('.view-section').forEach(sec => {
      sec.classList.remove('active');
    });

    const targetSection = document.getElementById(`view-${viewId}`);
    if (targetSection) {
      targetSection.classList.add('active');
    }

    // Trigger view-specific loads
    if (viewId === 'dashboard') this.refreshDashboard();
    if (viewId === 'jobs') jobsView.loadJobs();
    if (viewId === 'applications') applicationsView.loadApplications();
    if (viewId === 'settings') settingsView.loadSettings();
  },

  async refreshDashboard() {
    await dashboardView.loadStats();
    await dashboardView.loadRecentJobs();
  },

  // -------------------------------------------------------------
  // Browser Management & Polling
  // -------------------------------------------------------------

  async toggleBrowser() {
    const btnLabel = document.getElementById('btn-browser-label');
    try {
      if (this.browserRunning) {
        btnLabel.innerText = "Closing...";
        const res = await this.apiPost('/api/browser/stop');
        this.toast('Browser closed.', 'info');
      } else {
        btnLabel.innerText = "Launching...";
        const res = await this.apiPost('/api/browser/start', { headless: false });
        if (res.success) {
          this.toast('Browser launched in headed mode.', 'success');
        } else {
          this.toast(res.message || 'Failed to start browser.', 'error');
        }
      }
      await this.checkBrowserStatus();
    } catch (e) {
      this.toast('Browser error: ' + e.message, 'error');
    }
  },

  async checkBrowserStatus() {
    try {
      const res = await fetch('/api/browser/status');
      if (!res.ok) return;
      const data = await res.json();

      this.browserRunning = data.is_running;
      this.browserLoggedIn = data.is_logged_in;

      const badge = document.getElementById('browser-status-badge');
      const text = document.getElementById('browser-status-text');
      const btnLabel = document.getElementById('btn-browser-label');
      const taskText = document.getElementById('browser-active-task');
      const sidebarTask = document.getElementById('sidebar-task-text');

      const resumeBtn = document.getElementById('btn-resume-browser');

      if (data.is_running) {
        btnLabel.innerText = 'Stop Browser';
        if (data.is_logged_in) {
          badge.className = 'status-badge running';
          text.innerText = 'LinkedIn Logged In & Ready';
          if (resumeBtn) resumeBtn.style.display = 'none';
        } else {
          badge.className = 'status-badge warning';
          text.innerText = data.active_task.includes('Security') ? 'Paused for Security Check' : 'Awaiting Login in Browser';
          if (resumeBtn) resumeBtn.style.display = 'inline-flex';
        }
      } else {
        badge.className = 'status-badge stopped';
        text.innerText = 'Browser Stopped';
        btnLabel.innerText = 'Launch Browser';
        if (resumeBtn) resumeBtn.style.display = 'none';
      }

      taskText.innerText = data.active_task ? `• ${data.active_task}` : '';
      sidebarTask.innerText = data.status_message || 'Idle';

    } catch (e) {
      // ignore
    }
  },

  async resumeBrowserSession() {
    const resumeBtn = document.getElementById('btn-resume-browser');
    if (resumeBtn) resumeBtn.innerText = 'Verifying...';
    try {
      const res = await this.apiPost('/api/browser/resume');
      if (res.success) {
        this.toast('Session verified! LinkedIn is logged in and ready.', 'success');
      } else {
        this.toast(res.message || 'Login not detected yet in browser window.', 'warning');
      }
      await this.checkBrowserStatus();
    } catch (e) {
      this.toast('Verification error: ' + e.message, 'error');
    } finally {
      if (resumeBtn) resumeBtn.innerHTML = '<span>✅</span> I Logged In / Solved CAPTCHA';
    }
  },

  startBrowserPolling() {
    this.checkBrowserStatus();
    setInterval(() => this.checkBrowserStatus(), 3000);
  },

  // -------------------------------------------------------------
  // Modal Utilities
  // -------------------------------------------------------------

  openModal(title, bodyHtml, footerHtml = null) {
    document.getElementById('modal-title').innerText = title;
    document.getElementById('modal-body').innerHTML = bodyHtml;

    const footer = document.getElementById('modal-footer');
    if (footerHtml) {
      footer.innerHTML = footerHtml;
    } else {
      footer.innerHTML = `<button class="btn btn-secondary" onclick="app.closeModal()">Close</button>`;
    }

    document.getElementById('app-modal').classList.add('show');
  },

  closeModal() {
    document.getElementById('app-modal').classList.remove('show');
  },

  // -------------------------------------------------------------
  // Toast Notifications
  // -------------------------------------------------------------

  toast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    let icon = 'ℹ️';
    if (type === 'success') icon = '✅';
    if (type === 'error') icon = '🚨';

    toast.innerHTML = `<span>${icon}</span> <div>${message}</div>`;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  },

  // -------------------------------------------------------------
  // API Fetch Helpers
  // -------------------------------------------------------------

  async apiGet(url) {
    const res = await fetch(url);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'API request failed');
    }
    return res.json();
  },

  async apiPost(url, data = {}) {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'API request failed');
    }
    return res.json();
  },

  async apiPatch(url, data = {}) {
    const res = await fetch(url, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'API request failed');
    }
    return res.json();
  },

  async apiPut(url, data = {}) {
    const res = await fetch(url, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'API request failed');
    }
    return res.json();
  }
};

window.addEventListener('DOMContentLoaded', () => {
  app.init();
});

