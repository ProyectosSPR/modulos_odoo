/** @odoo-module **/

/**
 * Migration Hub Live Monitor
 * Real-time migration progress monitoring
 */

document.addEventListener('DOMContentLoaded', function() {
    const LiveMonitor = {
        projectId: null,
        pollInterval: null,
        pollRate: 2000, // 2 seconds
        isRunning: false,
        logs: [],
        maxLogs: 100,

        init: function(projectId) {
            this.projectId = projectId;
            this.bindEvents();
            this.startPolling();
        },

        bindEvents: function() {
            // Pause/Resume button
            const pauseBtn = document.querySelector('.mh-btn-pause');
            if (pauseBtn) {
                pauseBtn.addEventListener('click', () => this.togglePause());
            }

            // Stop button
            const stopBtn = document.querySelector('.mh-btn-stop');
            if (stopBtn) {
                stopBtn.addEventListener('click', () => this.stopMigration());
            }

            // Log level filter
            document.querySelectorAll('.mh-log-filter').forEach(btn => {
                btn.addEventListener('click', (e) => this.filterLogs(e.target.dataset.level));
            });

            // Clear logs button
            const clearLogsBtn = document.querySelector('.mh-btn-clear-logs');
            if (clearLogsBtn) {
                clearLogsBtn.addEventListener('click', () => this.clearLogs());
            }

            // Export logs button
            const exportBtn = document.querySelector('.mh-btn-export-logs');
            if (exportBtn) {
                exportBtn.addEventListener('click', () => this.exportLogs());
            }

            // Error retry buttons
            document.addEventListener('click', (e) => {
                if (e.target.closest('.mh-btn-retry-error')) {
                    const errorId = e.target.closest('.mh-error-item').dataset.errorId;
                    this.retryError(errorId);
                }
                if (e.target.closest('.mh-btn-ignore-error')) {
                    const errorId = e.target.closest('.mh-error-item').dataset.errorId;
                    this.ignoreError(errorId);
                }
            });

            // Poll rate adjustment
            const pollRateSelect = document.querySelector('.mh-poll-rate');
            if (pollRateSelect) {
                pollRateSelect.addEventListener('change', (e) => {
                    this.pollRate = parseInt(e.target.value);
                    if (this.isRunning) {
                        this.stopPolling();
                        this.startPolling();
                    }
                });
            }
        },

        startPolling: function() {
            this.isRunning = true;
            this.updateLiveIndicator(true);
            this.fetchProgress(); // Initial fetch

            this.pollInterval = setInterval(() => {
                this.fetchProgress();
            }, this.pollRate);
        },

        stopPolling: function() {
            this.isRunning = false;
            this.updateLiveIndicator(false);

            if (this.pollInterval) {
                clearInterval(this.pollInterval);
                this.pollInterval = null;
            }
        },

        fetchProgress: function() {
            fetch(`/my/migration/api/project/${this.projectId}/progress`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    this.updateProgress(data);
                    this.updateTopicProgress(data.topics);
                    this.addLogs(data.new_logs);
                    this.updateErrors(data.errors);
                    this.updateStats(data.stats);

                    // Check if migration is complete
                    if (data.state === 'completed' || data.state === 'error') {
                        this.onMigrationEnd(data.state);
                    }
                }
            })
            .catch(error => {
                console.error('Error fetching progress:', error);
            });
        },

        updateProgress: function(data) {
            // Update main progress circle
            const progressCircle = document.querySelector('.mh-progress-circle');
            if (progressCircle) {
                const progress = data.overall_progress || 0;
                this.animateProgressCircle(progressCircle, progress);

                const progressText = progressCircle.querySelector('.progress-text');
                if (progressText) {
                    progressText.textContent = `${Math.round(progress)}%`;
                }
            }

            // Update progress bar
            const progressBar = document.querySelector('.mh-overall-progress .progress-bar');
            if (progressBar) {
                progressBar.style.width = `${data.overall_progress || 0}%`;
                progressBar.setAttribute('aria-valuenow', data.overall_progress || 0);
            }

            // Update record counts
            this.updateElement('.mh-records-migrated', data.migrated_records);
            this.updateElement('.mh-records-total', data.total_records);
            this.updateElement('.mh-records-errors', data.error_records);
            this.updateElement('.mh-records-rate', `${data.records_per_second || 0}/s`);

            // Update time estimates
            this.updateElement('.mh-time-elapsed', this.formatDuration(data.elapsed_time));
            this.updateElement('.mh-time-remaining', this.formatDuration(data.estimated_remaining));

            // Update state indicator
            const stateIndicator = document.querySelector('.mh-state-indicator');
            if (stateIndicator) {
                stateIndicator.className = `mh-state-indicator state-${data.state}`;
                stateIndicator.textContent = this.getStateLabel(data.state);
            }
        },

        updateTopicProgress: function(topics) {
            const container = document.querySelector('.mh-topic-progress-list');
            if (!container || !topics) return;

            let html = '';
            topics.forEach(topic => {
                const progress = topic.total > 0 ? (topic.migrated / topic.total) * 100 : 0;
                html += `
                    <div class="mh-topic-progress">
                        <div class="topic-label">
                            <span class="topic-name">${topic.icon || ''} ${topic.name}</span>
                            <span class="topic-stats">${topic.migrated.toLocaleString()} / ${topic.total.toLocaleString()}</span>
                        </div>
                        <div class="progress mh-progress">
                            <div class="progress-bar bg-${topic.errors > 0 ? 'warning' : 'success'}"
                                 style="width: ${progress}%"
                                 role="progressbar"></div>
                        </div>
                        ${topic.errors > 0 ? `<span class="text-danger small">${topic.errors} errores</span>` : ''}
                    </div>
                `;
            });

            container.innerHTML = html;
        },

        addLogs: function(newLogs) {
            if (!newLogs || newLogs.length === 0) return;

            const logViewer = document.querySelector('.mh-log-viewer');
            if (!logViewer) return;

            newLogs.forEach(log => {
                // Add to internal array
                this.logs.push(log);

                // Trim if over max
                if (this.logs.length > this.maxLogs) {
                    this.logs.shift();
                }

                // Add to DOM
                const logEntry = document.createElement('div');
                logEntry.className = 'mh-log-entry';
                logEntry.dataset.level = log.level;
                logEntry.innerHTML = `
                    <span class="log-time">${this.formatTime(log.timestamp)}</span>
                    <span class="log-level ${log.level}">${log.level.toUpperCase()}</span>
                    <span class="log-message">${this.escapeHtml(log.message)}</span>
                `;

                logViewer.appendChild(logEntry);
            });

            // Auto-scroll to bottom
            logViewer.scrollTop = logViewer.scrollHeight;

            // Apply current filter
            const activeFilter = document.querySelector('.mh-log-filter.active');
            if (activeFilter && activeFilter.dataset.level !== 'all') {
                this.filterLogs(activeFilter.dataset.level);
            }
        },

        updateErrors: function(errors) {
            const errorList = document.querySelector('.mh-error-list');
            if (!errorList || !errors) return;

            if (errors.length === 0) {
                errorList.innerHTML = `
                    <div class="mh-empty-state p-4">
                        <i class="fa fa-check-circle text-success fa-2x"></i>
                        <p class="mt-2">No hay errores pendientes</p>
                    </div>
                `;
                return;
            }

            let html = '';
            errors.forEach(error => {
                html += `
                    <div class="mh-error-item" data-error-id="${error.id}">
                        <div class="error-icon">
                            <i class="fa fa-exclamation-triangle"></i>
                        </div>
                        <div class="error-content">
                            <div class="error-title">${error.source_table} - ${error.error_type}</div>
                            <div class="error-details">
                                <small>Record ID: ${error.source_record_id}</small>
                                <p class="mb-0">${this.escapeHtml(error.error_message)}</p>
                            </div>
                        </div>
                        <div class="error-actions">
                            <button class="btn btn-sm btn-outline-primary mh-btn-retry-error"
                                    title="Reintentar">
                                <i class="fa fa-refresh"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-secondary mh-btn-ignore-error"
                                    title="Ignorar">
                                <i class="fa fa-times"></i>
                            </button>
                        </div>
                    </div>
                `;
            });

            errorList.innerHTML = html;

            // Update error count badge
            const errorBadge = document.querySelector('.mh-error-count');
            if (errorBadge) {
                errorBadge.textContent = errors.length;
                errorBadge.style.display = errors.length > 0 ? 'inline' : 'none';
            }
        },

        updateStats: function(stats) {
            if (!stats) return;

            // Update speed chart if exists
            const speedChart = document.querySelector('.mh-speed-chart');
            if (speedChart && stats.speed_history) {
                this.updateSpeedChart(stats.speed_history);
            }
        },

        togglePause: function() {
            const btn = document.querySelector('.mh-btn-pause');

            fetch(`/my/migration/api/project/${this.projectId}/toggle-pause`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    if (data.state === 'paused') {
                        btn.innerHTML = '<i class="fa fa-play"></i> Reanudar';
                        btn.classList.replace('btn-warning', 'btn-success');
                        this.stopPolling();
                    } else {
                        btn.innerHTML = '<i class="fa fa-pause"></i> Pausar';
                        btn.classList.replace('btn-success', 'btn-warning');
                        this.startPolling();
                    }
                }
            })
            .catch(error => {
                console.error('Error toggling pause:', error);
            });
        },

        stopMigration: function() {
            if (!confirm('¿Está seguro de detener la migración? Los datos ya migrados se conservarán.')) {
                return;
            }

            fetch(`/my/migration/api/project/${this.projectId}/stop`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    this.stopPolling();
                    this.showNotification('Migración detenida', 'info');

                    // Update UI
                    const stateIndicator = document.querySelector('.mh-state-indicator');
                    if (stateIndicator) {
                        stateIndicator.className = 'mh-state-indicator state-cancelled';
                        stateIndicator.textContent = 'Cancelado';
                    }
                }
            })
            .catch(error => {
                console.error('Error stopping migration:', error);
            });
        },

        retryError: function(errorId) {
            fetch(`/my/migration/api/error/${errorId}/retry`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    this.showNotification('Reintentando registro...', 'info');
                    // Remove from list - will be updated on next poll
                    const errorItem = document.querySelector(`.mh-error-item[data-error-id="${errorId}"]`);
                    if (errorItem) {
                        errorItem.style.opacity = '0.5';
                    }
                } else {
                    this.showNotification(data.error || 'Error al reintentar', 'error');
                }
            })
            .catch(error => {
                console.error('Error retrying:', error);
            });
        },

        ignoreError: function(errorId) {
            fetch(`/my/migration/api/error/${errorId}/ignore`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Remove from list
                    const errorItem = document.querySelector(`.mh-error-item[data-error-id="${errorId}"]`);
                    if (errorItem) {
                        errorItem.remove();
                    }
                    this.showNotification('Error ignorado', 'info');
                }
            })
            .catch(error => {
                console.error('Error ignoring:', error);
            });
        },

        filterLogs: function(level) {
            // Update active button
            document.querySelectorAll('.mh-log-filter').forEach(btn => {
                btn.classList.remove('active');
                if (btn.dataset.level === level) {
                    btn.classList.add('active');
                }
            });

            // Filter log entries
            document.querySelectorAll('.mh-log-entry').forEach(entry => {
                if (level === 'all' || entry.dataset.level === level) {
                    entry.style.display = 'flex';
                } else {
                    entry.style.display = 'none';
                }
            });
        },

        clearLogs: function() {
            this.logs = [];
            const logViewer = document.querySelector('.mh-log-viewer');
            if (logViewer) {
                logViewer.innerHTML = '';
            }
        },

        exportLogs: function() {
            let content = 'Timestamp,Level,Message\n';
            this.logs.forEach(log => {
                content += `"${log.timestamp}","${log.level}","${log.message.replace(/"/g, '""')}"\n`;
            });

            const blob = new Blob([content], { type: 'text/csv' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `migration_logs_${this.projectId}_${new Date().toISOString().slice(0, 10)}.csv`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
        },

        onMigrationEnd: function(state) {
            this.stopPolling();

            const message = state === 'completed'
                ? 'Migración completada exitosamente'
                : 'Migración finalizada con errores';

            const type = state === 'completed' ? 'success' : 'error';

            this.showNotification(message, type);

            // Show completion modal
            this.showCompletionModal(state);
        },

        showCompletionModal: function(state) {
            const modalHtml = `
                <div class="modal fade" id="migrationCompleteModal" tabindex="-1">
                    <div class="modal-dialog modal-dialog-centered">
                        <div class="modal-content">
                            <div class="modal-header ${state === 'completed' ? 'bg-success' : 'bg-danger'} text-white">
                                <h5 class="modal-title">
                                    <i class="fa fa-${state === 'completed' ? 'check-circle' : 'exclamation-triangle'}"></i>
                                    Migración ${state === 'completed' ? 'Completada' : 'Finalizada'}
                                </h5>
                            </div>
                            <div class="modal-body text-center">
                                <p>${state === 'completed'
                                    ? 'Todos los registros han sido migrados exitosamente.'
                                    : 'La migración ha finalizado. Revise los errores para más detalles.'}
                                </p>
                                <div class="d-flex justify-content-center gap-3 mt-3">
                                    <a href="/my/migration/project/${this.projectId}" class="btn btn-primary">
                                        Ver Proyecto
                                    </a>
                                    <a href="/my/migration" class="btn btn-outline-secondary">
                                        Volver al Dashboard
                                    </a>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;

            document.body.insertAdjacentHTML('beforeend', modalHtml);
            const modal = new bootstrap.Modal(document.getElementById('migrationCompleteModal'));
            modal.show();
        },

        // Utility methods
        animateProgressCircle: function(element, progress) {
            const circle = element.querySelector('.progress-ring-circle');
            if (!circle) return;

            const radius = circle.r.baseVal.value;
            const circumference = radius * 2 * Math.PI;
            const offset = circumference - (progress / 100) * circumference;

            circle.style.strokeDasharray = `${circumference} ${circumference}`;
            circle.style.strokeDashoffset = offset;
        },

        updateLiveIndicator: function(isLive) {
            const indicator = document.querySelector('.mh-live-indicator');
            if (indicator) {
                if (isLive) {
                    indicator.classList.add('active');
                    indicator.querySelector('.status-text').textContent = 'En Vivo';
                } else {
                    indicator.classList.remove('active');
                    indicator.querySelector('.status-text').textContent = 'Pausado';
                }
            }
        },

        updateElement: function(selector, value) {
            const el = document.querySelector(selector);
            if (el) {
                el.textContent = typeof value === 'number' ? value.toLocaleString() : value;
            }
        },

        formatDuration: function(seconds) {
            if (!seconds || seconds < 0) return '--:--';

            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            const secs = Math.floor(seconds % 60);

            if (hours > 0) {
                return `${hours}h ${minutes}m ${secs}s`;
            } else if (minutes > 0) {
                return `${minutes}m ${secs}s`;
            } else {
                return `${secs}s`;
            }
        },

        formatTime: function(timestamp) {
            if (!timestamp) return '';
            const date = new Date(timestamp);
            return date.toLocaleTimeString();
        },

        getStateLabel: function(state) {
            const labels = {
                'draft': 'Borrador',
                'connecting': 'Conectando',
                'analyzing': 'Analizando',
                'mapping': 'Mapeando',
                'ready': 'Listo',
                'running': 'En Progreso',
                'paused': 'Pausado',
                'completed': 'Completado',
                'error': 'Error',
                'cancelled': 'Cancelado'
            };
            return labels[state] || state;
        },

        escapeHtml: function(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        },

        showNotification: function(message, type) {
            const notification = document.createElement('div');
            notification.className = `mh-notification ${type}`;
            notification.innerHTML = `
                <i class="fa fa-${type === 'success' ? 'check' : (type === 'error' ? 'times' : 'info')}-circle"></i>
                ${message}
            `;

            document.body.appendChild(notification);
            setTimeout(() => notification.classList.add('show'), 10);

            setTimeout(() => {
                notification.classList.remove('show');
                setTimeout(() => notification.remove(), 300);
            }, 4000);
        }
    };

    // Initialize if on monitor page
    const monitorContainer = document.querySelector('.mh-monitor');
    if (monitorContainer) {
        const projectId = monitorContainer.dataset.projectId;
        if (projectId) {
            LiveMonitor.init(projectId);
        }
    }

    // Export
    window.LiveMonitor = LiveMonitor;

    // Cleanup on page unload
    window.addEventListener('beforeunload', () => {
        if (LiveMonitor.pollInterval) {
            LiveMonitor.stopPolling();
        }
    });
});
