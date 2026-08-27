// Dashboard View Logic

const dashboardView = {
  async loadStats() {
    try {
      const stats = await app.apiGet('/api/dashboard/stats');
      document.getElementById('stat-found').innerText = stats.jobs_found || 0;
      document.getElementById('stat-ready').innerText = stats.ready_to_submit || 0;
      document.getElementById('stat-applied').innerText = stats.applied || 0;
      document.getElementById('stat-interviews').innerText = stats.interviews || 0;
    } catch (e) {
      console.error('Failed to load dashboard stats:', e);
    }
  },

  async loadRecentJobs() {
    const container = document.getElementById('dashboard-jobs-container');
    try {
      const data = await app.apiGet('/api/jobs?min_score=60');
      const jobs = data.jobs || [];

      if (jobs.length === 0) {
        container.innerHTML = `<div style="color: var(--text-muted); font-size: 13px; padding: 12px 0;">No high-match jobs found yet. Try searching for jobs!</div>`;
        return;
      }

      container.innerHTML = jobs.slice(0, 3).map(job => this.renderJobCard(job)).join('');
    } catch (e) {
      container.innerHTML = `<div style="color: var(--danger); font-size: 13px;">Error loading jobs: ${e.message}</div>`;
    }
  },

  renderJobCard(job) {
    const score = Math.round(job.match_score || 0);
    const scoreClass = score >= 75 ? 'high' : (score >= 50 ? 'medium' : 'low');

    return `
      <div class="job-card" style="padding: 16px;">
        <div class="job-card-header">
          <div>
            <a href="${job.url}" target="_blank" class="job-title" style="font-size: 15px;">${job.title}</a>
            <div class="job-company">${job.company} • 📍 ${job.location}</div>
          </div>
          <div class="badge badge-score ${scoreClass}">
            ⭐ ${score}% Match
          </div>
        </div>
        <div class="job-desc-snippet" style="-webkit-line-clamp: 1;">
          ${job.description || 'No description available'}
        </div>
        <div class="job-card-actions">
          <span class="badge">${job.employment_type || 'Full-time'}</span>
          <button class="btn btn-primary btn-sm" onclick="jobsView.prepareApplication('${encodeURIComponent(job.url)}')">
            <span>⚡</span> 1-Click Auto Apply
          </button>
        </div>
      </div>
    `;
  }
};

