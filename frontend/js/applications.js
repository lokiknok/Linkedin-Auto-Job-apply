// Applications Tracking & Status Management Logic

const applicationsView = {
  currentFilter: 'ALL',
  searchQuery: '',

  init() {
    // Filter Buttons
    document.querySelectorAll('.app-filter-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('.app-filter-btn').forEach(b => b.classList.remove('active'));
        e.currentTarget.classList.add('active');
        this.currentFilter = e.currentTarget.getAttribute('data-status');
        this.loadApplications();
      });
    });

    // Search Input
    const searchInp = document.getElementById('input-apps-search');
    if (searchInp) {
      searchInp.addEventListener('input', (e) => {
        this.searchQuery = e.target.value;
        this.loadApplications();
      });
    }
  },

  async loadApplications() {
    const tbody = document.getElementById('applications-table-body');
    try {
      let url = `/api/applications?status=${this.currentFilter}`;
      if (this.searchQuery) {
        url += `&search=${encodeURIComponent(this.searchQuery)}`;
      }

      const data = await app.apiGet(url);
      const apps = data.applications || [];

      // Update count badges
      await this.updateFilterCounts();

      if (apps.length === 0) {
        tbody.innerHTML = `
          <tr>
            <td colspan="7" style="text-align: center; color: var(--text-muted); padding: 32px;">
              No applications found for status "${this.currentFilter}".
            </td>
          </tr>
        `;
        return;
      }

      tbody.innerHTML = apps.map(app => this.renderTableRow(app)).join('');
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="7" style="color: var(--danger); padding: 20px;">Error: ${e.message}</td></tr>`;
    }
  },

  async updateFilterCounts() {
    try {
      const stats = await app.apiGet('/api/dashboard/stats');
      const setBadge = (id, count) => {
        const elem = document.getElementById(id);
        if (elem) elem.innerText = count || 0;
      };
      setBadge('count-all', stats.total_tracked);
      setBadge('count-ready', stats.ready_to_submit);
      setBadge('count-applied', stats.applied);
      setBadge('count-interview', stats.interviews);
      setBadge('count-rejected', stats.rejected);
    } catch (e) {
      // ignore
    }
  },

  renderTableRow(app) {
    const score = Math.round(app.match_score || 0);
    const dateApplied = app.date_applied ? new Date(app.date_applied).toLocaleDateString() : '—';

    const statuses = [
      'FOUND', 'REVIEWING', 'READY_TO_SUBMIT', 'APPLIED',
      'INTERVIEW', 'TECHNICAL_ROUND', 'OFFER', 'REJECTED', 'WITHDRAWN'
    ];

    const statusOptions = statuses.map(s => `
      <option value="${s}" ${app.application_status === s ? 'selected' : ''}>${s.replace(/_/g, ' ')}</option>
    `).join('');

    return `
      <tr>
        <td style="font-weight: 600;">${app.company}</td>
        <td>
          <a href="${app.job_url}" target="_blank" style="color: var(--text-main); font-weight: 600; text-decoration: none;">
            ${app.job_title}
          </a>
        </td>
        <td style="color: var(--text-muted);">${app.location}</td>
        <td>
          <span class="badge badge-score ${score >= 70 ? 'high' : 'medium'}">
            ⭐ ${score}%
          </span>
        </td>
        <td>
          <select class="form-select" style="padding: 4px 8px; font-size: 12px; width: auto;" onchange="applicationsView.updateStatus(${app.id}, this.value)">
            ${statusOptions}
          </select>
        </td>
        <td style="color: var(--text-muted); font-size: 12px;">${dateApplied}</td>
        <td>
          <div style="display: flex; gap: 6px;">
            <button class="btn btn-secondary btn-sm" onclick="applicationsView.showNotesModal(${app.id})">
              📝 Notes
            </button>
            ${app.application_status !== 'APPLIED' ? `
              <button class="btn btn-success btn-sm" onclick="applicationsView.markApplied(${app.id})">
                ✅ Applied
              </button>
            ` : ''}
          </div>
        </td>
      </tr>
    `;
  },

  async updateStatus(appId, newStatus) {
    try {
      const res = await app.apiPatch(`/api/applications/${appId}`, {
        application_status: newStatus
      });
      app.toast(`Status updated to ${newStatus}`, 'success');
      await this.loadApplications();
      await dashboardView.loadStats();
    } catch (e) {
      app.toast('Failed to update status: ' + e.message, 'error');
    }
  },

  async markApplied(appId) {
    try {
      const res = await app.apiPost('/api/application/mark-applied', {
        application_id: appId
      });
      app.toast('Application marked as APPLIED! Telegram notification sent.', 'success');
      app.closeModal();
      await this.loadApplications();
      await dashboardView.loadStats();
    } catch (e) {
      app.toast('Failed to mark applied: ' + e.message, 'error');
    }
  },

  async showNotesModal(appId) {
    try {
      const appData = await app.apiGet(`/api/applications/${appId}`);
      const bodyHtml = `
        <div style="display: flex; flex-direction: column; gap: 12px;">
          <div>
            <strong>${appData.job_title}</strong> at <strong>${appData.company}</strong>
          </div>
          <div class="form-group">
            <label class="form-label">Application Notes / History</label>
            <textarea id="notes-textarea" class="form-textarea" rows="6" placeholder="Interview details, recruiter feedback, follow-up dates...">${appData.notes || ''}</textarea>
          </div>
        </div>
      `;

      const footerHtml = `
        <button class="btn btn-secondary" onclick="app.closeModal()">Cancel</button>
        <button class="btn btn-primary" onclick="applicationsView.saveNotes(${appId})">Save Notes</button>
      `;

      app.openModal('Application Notes', bodyHtml, footerHtml);
    } catch (e) {
      app.toast('Failed to load notes: ' + e.message, 'error');
    }
  },

  async saveNotes(appId) {
    const notes = document.getElementById('notes-textarea').value;
    try {
      await app.apiPatch(`/api/applications/${appId}`, { notes: notes });
      app.toast('Notes saved.', 'success');
      app.closeModal();
      await this.loadApplications();
    } catch (e) {
      app.toast('Failed to save notes: ' + e.message, 'error');
    }
  }
};

window.addEventListener('DOMContentLoaded', () => {
  applicationsView.init();
});

