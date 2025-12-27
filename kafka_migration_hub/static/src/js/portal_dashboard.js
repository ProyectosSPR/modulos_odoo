/** @odoo-module **/

/**
 * Migration Hub Portal Dashboard
 * Handles dashboard interactions and real-time updates
 */

document.addEventListener('DOMContentLoaded', function() {
    const MigrationDashboard = {
        init: function() {
            this.bindEvents();
            this.initCharts();
            this.startAutoRefresh();
        },

        bindEvents: function() {
            // New project button
            const newProjectBtn = document.querySelector('.mh-btn-new-project');
            if (newProjectBtn) {
                newProjectBtn.addEventListener('click', this.handleNewProject.bind(this));
            }

            // Project card clicks
            document.querySelectorAll('.mh-project-card').forEach(card => {
                card.addEventListener('click', this.handleProjectClick.bind(this));
            });

            // Refresh button
            const refreshBtn = document.querySelector('.mh-refresh-btn');
            if (refreshBtn) {
                refreshBtn.addEventListener('click', this.refreshDashboard.bind(this));
            }

            // Filter buttons
            document.querySelectorAll('.mh-filter-btn').forEach(btn => {
                btn.addEventListener('click', this.handleFilter.bind(this));
            });
        },

        initCharts: function() {
            // Initialize progress circles
            document.querySelectorAll('.mh-progress-circle').forEach(circle => {
                this.animateProgressCircle(circle);
            });

            // Initialize stat counters
            document.querySelectorAll('.stat-number').forEach(stat => {
                this.animateCounter(stat);
            });
        },

        animateProgressCircle: function(element) {
            const progress = parseFloat(element.dataset.progress) || 0;
            const circle = element.querySelector('.progress-ring-circle');
            if (!circle) return;

            const radius = circle.r.baseVal.value;
            const circumference = radius * 2 * Math.PI;

            circle.style.strokeDasharray = `${circumference} ${circumference}`;
            circle.style.strokeDashoffset = circumference;

            // Animate
            setTimeout(() => {
                const offset = circumference - (progress / 100) * circumference;
                circle.style.strokeDashoffset = offset;
            }, 100);
        },

        animateCounter: function(element) {
            const target = parseInt(element.dataset.target) || parseInt(element.textContent);
            const duration = 1000;
            const start = 0;
            const startTime = performance.now();

            const updateCounter = (currentTime) => {
                const elapsed = currentTime - startTime;
                const progress = Math.min(elapsed / duration, 1);

                // Easing function
                const easeOutQuad = t => t * (2 - t);
                const current = Math.floor(start + (target - start) * easeOutQuad(progress));

                element.textContent = current.toLocaleString();

                if (progress < 1) {
                    requestAnimationFrame(updateCounter);
                }
            };

            requestAnimationFrame(updateCounter);
        },

        handleNewProject: function(e) {
            e.preventDefault();
            window.location.href = '/my/migration/new';
        },

        handleProjectClick: function(e) {
            const card = e.currentTarget;
            const projectId = card.dataset.projectId;
            if (projectId) {
                window.location.href = `/my/migration/project/${projectId}`;
            }
        },

        handleFilter: function(e) {
            const btn = e.currentTarget;
            const filter = btn.dataset.filter;

            // Update active state
            document.querySelectorAll('.mh-filter-btn').forEach(b => {
                b.classList.remove('active');
            });
            btn.classList.add('active');

            // Filter projects
            document.querySelectorAll('.mh-project-card').forEach(card => {
                const state = card.dataset.state;
                if (filter === 'all' || state === filter) {
                    card.style.display = 'block';
                    card.classList.add('mh-fade-in');
                } else {
                    card.style.display = 'none';
                }
            });
        },

        refreshDashboard: function() {
            const refreshBtn = document.querySelector('.mh-refresh-btn');
            if (refreshBtn) {
                refreshBtn.classList.add('fa-spin');
            }

            fetch('/my/migration/api/dashboard/stats', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            })
            .then(response => response.json())
            .then(data => {
                this.updateStats(data);
                if (refreshBtn) {
                    refreshBtn.classList.remove('fa-spin');
                }
            })
            .catch(error => {
                console.error('Error refreshing dashboard:', error);
                if (refreshBtn) {
                    refreshBtn.classList.remove('fa-spin');
                }
            });
        },

        updateStats: function(data) {
            // Update stat cards
            if (data.total_projects !== undefined) {
                const totalEl = document.querySelector('[data-stat="total"]');
                if (totalEl) {
                    totalEl.querySelector('.stat-number').textContent = data.total_projects;
                }
            }

            if (data.running_projects !== undefined) {
                const runningEl = document.querySelector('[data-stat="running"]');
                if (runningEl) {
                    runningEl.querySelector('.stat-number').textContent = data.running_projects;
                }
            }

            if (data.completed_projects !== undefined) {
                const completedEl = document.querySelector('[data-stat="completed"]');
                if (completedEl) {
                    completedEl.querySelector('.stat-number').textContent = data.completed_projects;
                }
            }

            if (data.error_count !== undefined) {
                const errorEl = document.querySelector('[data-stat="errors"]');
                if (errorEl) {
                    errorEl.querySelector('.stat-number').textContent = data.error_count;
                }
            }
        },

        startAutoRefresh: function() {
            // Refresh every 30 seconds if there are running projects
            const hasRunning = document.querySelector('.mh-project-card[data-state="running"]');
            if (hasRunning) {
                this.autoRefreshInterval = setInterval(() => {
                    this.refreshDashboard();
                }, 30000);
            }
        },

        stopAutoRefresh: function() {
            if (this.autoRefreshInterval) {
                clearInterval(this.autoRefreshInterval);
            }
        }
    };

    // Initialize dashboard
    if (document.querySelector('.mh-dashboard')) {
        MigrationDashboard.init();
    }
});

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { MigrationDashboard };
}
