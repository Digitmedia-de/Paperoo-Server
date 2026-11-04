(() => {
    'use strict';

    const { csrfToken, translations: t } = window.settingsPage;
    const $ = (id) => document.getElementById(id);
    let settings = null;
    let updatePolling = null;

    function showAlert(message, type = 'success') {
        $('alertContainer').innerHTML = '';
        const alert = document.createElement('div');
        alert.className = `alert alert-${type} alert-dismissible fade show`;
        alert.textContent = message;
        const close = document.createElement('button');
        close.type = 'button';
        close.className = 'btn-close';
        close.setAttribute('data-bs-dismiss', 'alert');
        alert.appendChild(close);
        $('alertContainer').appendChild(alert);
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    async function api(path, options = {}) {
        const request = { ...options, headers: { ...(options.headers || {}) } };
        if (request.method && request.method !== 'GET') {
            request.headers['Content-Type'] = 'application/json';
            request.headers['X-CSRF-Token'] = csrfToken;
        }
        const response = await fetch(path, request);
        if (response.status === 401) {
            window.location.href = '/login';
            throw new Error(t.settings_save_failed);
        }
        const result = await response.json();
        if (!response.ok || !result.success) {
            throw new Error(result.error || t.settings_save_failed);
        }
        return result;
    }

    function setBusy(form, busy) {
        form.querySelectorAll('button, input, select').forEach((element) => {
            element.disabled = busy;
        });
    }

    async function submitForm(form, path, payload, onSuccess) {
        setBusy(form, true);
        try {
            const result = await api(path, { method: 'POST', body: JSON.stringify(payload) });
            showAlert(t.settings_saved);
            if (onSuccess) onSuccess(result.data);
        } catch (error) {
            showAlert(error.message, 'danger');
        } finally {
            setBusy(form, false);
        }
    }

    function fillProvider(provider) {
        if (!settings) return;
        const values = settings.motivation.providers[provider];
        $('providerBaseUrl').value = values.base_url;
        $('providerModel').value = values.model;
        $('providerApiKey').value = '';
        $('clearProviderApiKey').checked = false;
        $('apiKeyStatus').textContent = values.api_key_configured ? t.api_key_saved : '';
        $('apiKeyFields').hidden = provider === 'local';
    }

    async function loadSettings() {
        try {
            const result = await api('/api/settings');
            settings = result.data;
            const auth = settings.auth;
            $('authEnabled').checked = auth.enabled;
            $('webUsername').value = auth.username;
            $('sessionTimeout').value = auth.session_timeout;
            $('rememberDays').value = auth.remember_me_days;
            $('webPasswordStatus').textContent = auth.password_configured ? t.password_configured : t.password_not_configured;
            $('currentPasswordGroup').hidden = !auth.enabled;

            $('motivationEnabled').checked = settings.motivation.enabled;
            $('motivationProvider').value = settings.motivation.provider;
            fillProvider(settings.motivation.provider);

            const mqtt = settings.mqtt;
            $('mqttEnabled').checked = mqtt.enabled;
            $('mqttBroker').value = mqtt.broker;
            $('mqttPort').value = mqtt.port;
            $('mqttUsername').value = mqtt.username;
            $('mqttPasswordStatus').textContent = mqtt.password_configured ? t.password_configured : '';
            $('mqttTopicBefore').value = mqtt.topic_before_print;
            $('mqttPayloadBefore').value = mqtt.payload_before_print;
            $('mqttWaitSeconds').value = mqtt.wait_seconds;
            $('mqttTimeoutMinutes').value = mqtt.timeout_minutes;
            $('mqttTopicAfter').value = mqtt.topic_after_timeout;
            $('mqttPayloadAfter').value = mqtt.payload_after_timeout;
        } catch (error) {
            showAlert(error.message, 'danger');
        }
    }

    let managedApiKeys = [];

    function formatDate(value) {
        if (!value) return t.api_key_never_used;
        const date = new Date(`${value}Z`);
        return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
    }

    async function loadApiKeys() {
        try {
            const result = await api('/api/settings/api-keys');
            managedApiKeys = result.data;
            const selectedFilter = $('logKeyFilter').value;
            $('logKeyFilter').innerHTML = '';
            const allOption = document.createElement('option');
            allOption.value = '';
            allOption.textContent = t.all_api_keys;
            $('logKeyFilter').appendChild(allOption);
            for (const key of managedApiKeys) {
                const option = document.createElement('option');
                option.value = key.id;
                option.textContent = key.comment;
                option.selected = String(key.id) === selectedFilter;
                $('logKeyFilter').appendChild(option);
            }

            $('apiKeysList').innerHTML = '';
            if (!managedApiKeys.length) {
                $('apiKeysList').textContent = t.no_api_keys;
                return;
            }
            for (const key of managedApiKeys) {
                const card = document.createElement('div');
                card.className = `api-key-card${key.is_active ? '' : ' revoked'}`;
                const status = key.is_legacy ? t.api_key_legacy : (key.is_active ? t.api_key_active : t.api_key_revoked);
                const typeCounts = Object.entries(key.type_counts)
                    .map(([type, count]) => `<span class="type-count">${escapeHtml(t[`type_${type}`] || type)}: ${count}</span>`)
                    .join('');
                card.innerHTML = `
                    <div class="api-key-header">
                        <div><strong>${escapeHtml(key.comment)}</strong><div class="text-muted"><code>${escapeHtml(key.prefix)}…</code> · ${escapeHtml(status)}</div></div>
                        ${key.is_legacy || !key.is_active ? '' : `<button type="button" class="btn btn-sm btn-danger" data-revoke-key="${key.id}">${escapeHtml(t.revoke_api_key)}</button>`}
                    </div>
                    <div class="api-key-stats">
                        <div class="api-key-stat"><strong>${key.use_count}</strong><span>${escapeHtml(t.api_key_usage)}</span></div>
                        <div class="api-key-stat"><strong>${key.print_count}</strong><span>${escapeHtml(t.api_key_prints)}</span></div>
                    </div>
                    <div class="type-counts">${typeCounts}</div>
                    <small class="d-block mt-2 text-muted">${escapeHtml(t.api_key_last_used)}: ${escapeHtml(formatDate(key.last_used_at))}</small>
                `;
                $('apiKeysList').appendChild(card);
            }
        } catch (error) {
            showAlert(error.message, 'danger');
        }
    }

    $('apiKeyForm').addEventListener('submit', async (event) => {
        event.preventDefault();
        setBusy(event.target, true);
        try {
            const result = await api('/api/settings/api-keys', {
                method: 'POST',
                body: JSON.stringify({ comment: $('apiKeyComment').value }),
            });
            $('newApiKeyValue').textContent = result.data.api_key;
            $('newApiKeyContainer').hidden = false;
            $('apiKeyComment').value = '';
            await loadApiKeys();
        } catch (error) {
            showAlert(error.message || t.api_key_create_failed, 'danger');
        } finally {
            setBusy(event.target, false);
        }
    });

    $('copyApiKeyBtn').addEventListener('click', async () => {
        const value = $('newApiKeyValue').textContent;
        try {
            await navigator.clipboard.writeText(value);
        } catch {
            const textarea = document.createElement('textarea');
            textarea.value = value;
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand('copy');
            textarea.remove();
        }
        showAlert(t.api_key_copied);
    });

    $('apiKeysList').addEventListener('click', async (event) => {
        const button = event.target.closest('button[data-revoke-key]');
        if (!button || !window.confirm(t.confirm_revoke_api_key)) return;
        button.disabled = true;
        try {
            await api(`/api/settings/api-keys/${button.dataset.revokeKey}`, { method: 'DELETE' });
            await loadApiKeys();
            await loadPrintLog();
        } catch (error) {
            showAlert(error.message || t.api_key_revoke_failed, 'danger');
            button.disabled = false;
        }
    });

    async function loadPrintLog() {
        try {
            const filter = $('logKeyFilter').value;
            const result = await api(`/api/settings/print-log${filter ? `?key_id=${encodeURIComponent(filter)}` : ''}`);
            $('printLogBody').innerHTML = '';
            if (!result.data.length) {
                const row = document.createElement('tr');
                const cell = document.createElement('td');
                cell.colSpan = 5;
                cell.textContent = t.no_print_log;
                row.appendChild(cell);
                $('printLogBody').appendChild(row);
                return;
            }
            for (const event of result.data) {
                const row = document.createElement('tr');
                const values = [
                    formatDate(event.created_at),
                    event.key_comment || '–',
                    t[`type_${event.print_type}`] || event.print_type,
                ];
                for (const value of values) {
                    const cell = document.createElement('td');
                    cell.textContent = value;
                    row.appendChild(cell);
                }
                const content = document.createElement('td');
                content.className = 'log-content';
                content.textContent = event.text;
                const details = [];
                if (event.details.title) details.push(event.details.title);
                if (event.details.author) details.push(event.details.author);
                if (event.details.qr_size) details.push(`${t.qr_size}: ${event.details.qr_size}`);
                if (details.length) {
                    const small = document.createElement('small');
                    small.className = 'd-block text-muted';
                    small.textContent = details.join(' · ');
                    content.appendChild(small);
                }
                row.appendChild(content);
                const status = document.createElement('td');
                status.textContent = event.status === 'printed' ? t.log_printed : t.log_queued;
                row.appendChild(status);
                $('printLogBody').appendChild(row);
            }
        } catch (error) {
            showAlert(error.message, 'danger');
        }
    }

    $('refreshLogBtn').addEventListener('click', loadPrintLog);
    $('logKeyFilter').addEventListener('change', loadPrintLog);

    $('authEnabled').addEventListener('change', () => {
        $('currentPasswordGroup').hidden = !$('authEnabled').checked || !settings.auth.enabled;
    });

    $('authForm').addEventListener('submit', (event) => {
        event.preventDefault();
        const payload = {
            enabled: $('authEnabled').checked,
            username: $('webUsername').value,
            current_password: $('currentPassword').value,
            new_password: $('newPassword').value,
            password_confirmation: $('passwordConfirmation').value,
            session_timeout: Number($('sessionTimeout').value),
            remember_me_days: Number($('rememberDays').value),
        };
        submitForm(event.target, '/api/settings/auth', payload, () => {
            window.setTimeout(() => window.location.reload(), 800);
        });
    });

    $('motivationProvider').addEventListener('change', () => fillProvider($('motivationProvider').value));
    $('motivationForm').addEventListener('submit', (event) => {
        event.preventDefault();
        const provider = $('motivationProvider').value;
        const payload = {
            enabled: $('motivationEnabled').checked,
            provider,
            settings: {
                base_url: $('providerBaseUrl').value,
                model: $('providerModel').value,
                api_key: $('providerApiKey').value,
                clear_api_key: $('clearProviderApiKey').checked,
            },
        };
        submitForm(event.target, '/api/settings/motivation', payload, (data) => {
            settings.motivation = data;
            fillProvider(provider);
        });
    });

    $('mqttForm').addEventListener('submit', (event) => {
        event.preventDefault();
        const payload = {
            enabled: $('mqttEnabled').checked,
            broker: $('mqttBroker').value,
            port: Number($('mqttPort').value),
            username: $('mqttUsername').value,
            password: $('mqttPassword').value,
            clear_password: $('clearMqttPassword').checked,
            topic_before_print: $('mqttTopicBefore').value,
            payload_before_print: $('mqttPayloadBefore').value,
            wait_seconds: Number($('mqttWaitSeconds').value),
            timeout_minutes: Number($('mqttTimeoutMinutes').value),
            topic_after_timeout: $('mqttTopicAfter').value,
            payload_after_timeout: $('mqttPayloadAfter').value,
        };
        submitForm(event.target, '/api/settings/mqtt', payload, (data) => {
            settings.mqtt = data;
            $('mqttPassword').value = '';
            $('clearMqttPassword').checked = false;
            $('mqttPasswordStatus').textContent = data.password_configured ? t.password_configured : '';
        });
    });

    function escapeHtml(value) {
        const element = document.createElement('div');
        element.textContent = String(value ?? '');
        return element.innerHTML;
    }

    async function loadPrinters() {
        $('printerSelection').innerHTML = '<div class="loading-container"><div class="spinner-border" role="status"></div></div>';
        try {
            const result = await api('/api/printers');
            displayPrinters(result.data.printers, result.data.current);
        } catch (error) {
            $('printerSelection').textContent = error.message;
        }
    }

    function displayPrinters(printers, current) {
        let html = '';
        for (const printer of printers.usb || []) {
            const active = current.type === 'usb' && current.vendor_id === printer.vendor_id && current.product_id === printer.product_id;
            html += `<button type="button" class="printer-item ${active ? 'active' : ''}" data-type="usb" data-vendor-id="${escapeHtml(printer.vendor_id)}" data-product-id="${escapeHtml(printer.product_id)}"><span class="printer-info"><strong>${escapeHtml(printer.description)}</strong><span class="d-block">${escapeHtml(printer.vendor_name)} (${escapeHtml(printer.vendor_id)}:${escapeHtml(printer.product_id)})</span></span>${active ? `<span class="printer-badge">${escapeHtml(t.active)}</span>` : ''}</button>`;
        }
        for (const printer of printers.serial || []) {
            const active = current.type === 'serial' && current.serial_port === printer.port;
            html += `<button type="button" class="printer-item ${active ? 'active' : ''}" data-type="serial" data-port="${escapeHtml(printer.port)}"><span class="printer-info"><strong>${escapeHtml(printer.description)}</strong><span class="d-block">${escapeHtml(printer.port)}</span></span>${active ? `<span class="printer-badge">${escapeHtml(t.active)}</span>` : ''}</button>`;
        }
        html += `<div class="printer-item ${current.type === 'network' ? 'active' : ''}"><label for="networkPrinterIP" class="form-label">${escapeHtml(t.network_printer)}</label><div class="d-flex gap-2"><input type="text" class="form-control" id="networkPrinterIP" placeholder="${escapeHtml(t.enter_ip)}" value="${current.type === 'network' ? escapeHtml(current.network_ip || '') : ''}"><button type="button" class="btn btn-primary" id="saveNetworkPrinter">${escapeHtml(t.save_settings)}</button></div></div>`;
        if (!(printers.usb || []).length && !(printers.serial || []).length) {
            html += `<div class="alert alert-warning">${escapeHtml(t.no_printers)}</div>`;
        }
        $('printerSelection').innerHTML = html;
    }

    async function savePrinter(payload) {
        try {
            await api('/api/printers/select', { method: 'POST', body: JSON.stringify(payload) });
            showAlert(t.printer_saved);
            loadPrinters();
        } catch (error) {
            showAlert(error.message || t.printer_save_failed, 'danger');
        }
    }

    $('printerSelection').addEventListener('click', (event) => {
        const item = event.target.closest('button.printer-item');
        if (item) {
            const payload = { type: item.dataset.type };
            if (payload.type === 'usb') {
                payload.vendor_id = item.dataset.vendorId;
                payload.product_id = item.dataset.productId;
            } else {
                payload.port = item.dataset.port;
            }
            savePrinter(payload);
        }
        if (event.target.id === 'saveNetworkPrinter') {
            savePrinter({ type: 'network', ip: $('networkPrinterIP').value });
        }
    });
    $('refreshPrintersBtn').addEventListener('click', loadPrinters);

    document.querySelectorAll('.lang-btn').forEach((button) => {
        button.addEventListener('click', async () => {
            if (button.dataset.lang === document.documentElement.lang) return;
            try {
                await api('/api/settings/language', { method: 'POST', body: JSON.stringify({ language: button.dataset.lang }) });
                window.location.reload();
            } catch (error) {
                showAlert(error.message, 'danger');
            }
        });
    });

    function showUpdateError(error) {
        $('updateStatus').textContent = error.message || t.update_check_failed;
        $('updateStatus').classList.add('text-danger');
        $('checkUpdateBtn').disabled = false;
    }

    function pollUpdateStatus() {
        if (updatePolling) return;
        updatePolling = window.setInterval(async () => {
            try {
                const result = await api('/api/system/update/status');
                const job = result.data.job;
                if (!job) return;
                $('currentVersion').textContent = result.data.current_version;
                $('updateStatus').textContent = job.message;
                if (!job.running) {
                    clearInterval(updatePolling);
                    updatePolling = null;
                    $('checkUpdateBtn').disabled = false;
                    if (job.status === 'success') {
                        $('remoteVersion').textContent = result.data.current_version;
                        window.setTimeout(() => window.location.reload(), 1500);
                    }
                }
            } catch (error) {
                clearInterval(updatePolling);
                updatePolling = null;
                showUpdateError(error);
            }
        }, 2000);
    }

    $('checkUpdateBtn').addEventListener('click', async () => {
        $('checkUpdateBtn').disabled = true;
        $('installUpdateBtn').disabled = true;
        $('updateStatus').classList.remove('text-danger');
        $('updateStatus').textContent = t.checking_updates;
        try {
            const result = await api('/api/system/update/check', { method: 'POST', body: '{}' });
            $('remoteVersion').textContent = result.remote_version;
            if (result.update_available && result.fast_forward_possible) {
                $('updateStatus').textContent = t.update_available;
                $('installUpdateBtn').disabled = false;
            } else {
                $('updateStatus').textContent = result.fast_forward_possible ? t.up_to_date : t.update_diverged;
            }
        } catch (error) {
            showUpdateError(error);
        } finally {
            $('checkUpdateBtn').disabled = false;
        }
    });

    $('installUpdateBtn').addEventListener('click', async () => {
        if (!window.confirm(t.confirm_update)) return;
        $('installUpdateBtn').disabled = true;
        $('checkUpdateBtn').disabled = true;
        try {
            await api('/api/system/update/install', { method: 'POST', body: '{}' });
            $('updateStatus').textContent = t.update_started;
            pollUpdateStatus();
        } catch (error) {
            showUpdateError(error);
        }
    });

    api('/api/system/update/status').then((result) => {
        if (result.data.job && result.data.job.running) {
            $('updateStatus').textContent = result.data.job.message;
            $('checkUpdateBtn').disabled = true;
            pollUpdateStatus();
        }
    }).catch(showUpdateError);

    loadSettings();
    loadApiKeys();
    loadPrintLog();
    loadPrinters();
})();
