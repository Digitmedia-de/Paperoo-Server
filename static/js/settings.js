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
    loadPrinters();
})();
