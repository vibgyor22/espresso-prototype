/**
 * Espresso - Sophisticated Animated Statistical Analysis Platform
 * Chat-based UI with parallax, animations, and coffee-themed design
 */

let selectedDataset = null;
let analysisHistory = [];
let rellaxInstance = null;

// ============================================================
// INITIALIZATION
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
    console.log('[INIT] Starting Espresso initialization');
    initializeApp();
    initParallax();
    loadDatasets();
    loadHistory();
    setupEventListeners();
    setupSuggestionChips();
    console.log('[INIT] Initialization complete');
});

function initializeApp() {
    console.log('%c ESPRESSO - Statistical Analysis Platform', 
                'font-size: 14px; font-weight: bold; color: #6D4C41; padding: 10px;');
}

function initParallax() {
    const messagesContainer = document.getElementById('messagesContainer');
    const parallaxLayers = document.querySelectorAll('.parallax-layer[data-rellax-speed]');

    if (messagesContainer && parallaxLayers.length > 0) {
        messagesContainer.addEventListener('scroll', () => {
            const scrollY = messagesContainer.scrollTop;
            parallaxLayers.forEach(layer => {
                const speed = parseFloat(layer.getAttribute('data-rellax-speed')) || 0.3;
                const y = scrollY * speed * 0.5;
                layer.style.transform = `translate3d(0, ${y}px, 0)`;
            });
        });
    }
}

// ============================================================
// EVENT LISTENERS
// ============================================================

function setupEventListeners() {
    console.log('[SETUP] Setting up event listeners');
    
    const datasetSelect = document.getElementById('datasetSelect');
    const questionInput = document.getElementById('questionInput');
    const sendBtn = document.getElementById('sendBtn');
    const closeModal = document.getElementById('closeModal');
    
    if (!datasetSelect) console.error('[ERROR] datasetSelect not found');
    if (!questionInput) console.error('[ERROR] questionInput not found');
    if (!sendBtn) console.error('[ERROR] sendBtn not found');
    if (!closeModal) console.error('[ERROR] closeModal not found');
    
    if (datasetSelect) {
        datasetSelect.addEventListener('change', selectDataset);
        console.log('[SETUP] Dataset select listener added');
    }
    
    if (questionInput) {
        questionInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey && !sendBtn.disabled) {
                console.log('[EVENT] Enter key pressed');
                e.preventDefault();
                sendAnalysis();
            }
        });
        console.log('[SETUP] Input keypress listener added');
    }
    
    if (sendBtn) {
        sendBtn.addEventListener('click', () => {
            console.log('[EVENT] Send button clicked');
            sendAnalysis();
        });
        console.log('[SETUP] Send button listener added');
    }
    
    if (closeModal) {
        closeModal.addEventListener('click', closeResults);
        console.log('[SETUP] Close modal listener added');
    }

    document.addEventListener('click', (e) => {
        if (e.target.classList.contains('modal-overlay')) {
            closeResults();
        }
    });
}

function setupSuggestionChips() {
    const chips = document.querySelectorAll('.suggestion-chip');
    chips.forEach(chip => {
        chip.addEventListener('click', () => {
            const question = chip.getAttribute('data-question');
            const questionInput = document.getElementById('questionInput');
            if (question && questionInput && selectedDataset) {
                questionInput.value = question;
                questionInput.focus();
                sendAnalysis();
            } else if (question && questionInput && !selectedDataset) {
                questionInput.value = question;
                questionInput.focus();
                document.getElementById('inputHint').textContent = 'Select a dataset, then press Enter or click send';
            }
        });
    });
}

// ============================================================
// DATASET MANAGEMENT
// ============================================================

async function loadDatasets() {
    console.log('[DATASETS] Loading datasets');
    try {
        const response = await fetch('/api/datasets');
        const datasets = await response.json();
        
        console.log(`[DATASETS] Loaded ${datasets.length} datasets`);
        
        const select = document.getElementById('datasetSelect');
        datasets.forEach(dataset => {
            const option = document.createElement('option');
            option.value = dataset.path;
            option.textContent = `${dataset.name} (${dataset.size})`;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('[ERROR] Loading datasets failed:', error);
    }
}

function selectDataset(e) {
    console.log('[DATASET] Dataset selected');
    selectedDataset = e.target.value;
    const select = e.target;
    const selectedOption = select.options[select.selectedIndex];
    
    const questionInput = document.getElementById('questionInput');
    const sendBtn = document.getElementById('sendBtn');
    const datasetInfo = document.getElementById('datasetInfo');
    const headerStatus = document.getElementById('headerStatus');
    
    if (selectedDataset) {
        console.log(`[DATASET] Selected: ${selectedDataset}`);
        questionInput.disabled = false;
        sendBtn.disabled = false;
        questionInput.focus();
        
        datasetInfo.innerHTML = `<p><strong>${selectedOption.textContent}</strong></p><p>Ready for analysis</p>`;
        headerStatus.textContent = `Dataset: ${selectedOption.textContent}`;
        document.getElementById('inputHint').textContent = 'Press Enter or click →';
    } else {
        console.log('[DATASET] Dataset cleared');
        questionInput.disabled = true;
        sendBtn.disabled = true;
        datasetInfo.innerHTML = '';
        headerStatus.textContent = 'Select a dataset and ask a question';
        document.getElementById('inputHint').textContent = 'Select a dataset first';
    }
}

// ============================================================
// ANALYSIS
// ============================================================

async function sendAnalysis() {
    console.log('[ANALYSIS] sendAnalysis called');
    
    const questionInput = document.getElementById('questionInput');
    const question = questionInput.value.trim();
    
    console.log(`[ANALYSIS] Question: "${question}"`);
    console.log(`[ANALYSIS] Dataset: "${selectedDataset}"`);
    
    if (!question || !selectedDataset) {
        console.warn('[WARN] Missing question or dataset');
        return;
    }
    
    // Hide welcome state when first message is sent
    hideWelcomeState();

    // Add user message to chat
    console.log('[CHAT] Adding user message');
    addMessage('user', question);
    questionInput.value = '';

    // Add typing indicator
    addTypingIndicator();

    // Show loading
    console.log('[LOADING] Showing loading overlay');
    showLoading();
    
    try {
        // Send to API
        console.log('[API] Sending POST request to /api/analyze');
        const response = await fetch('/api/analyze', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                dataset: selectedDataset,
                question: question
            })
        });
        
        console.log(`[API] Response status: ${response.status}`);
        removeTypingIndicator();
        hideLoading();

        if (!response.ok) {
            console.error(`[ERROR] API returned ${response.status}`);
            const error = await response.json();
            const errorMsg = error.error || 'Unknown error occurred';
            addMessage('assistant', `Error: ${errorMsg}`);
            return;
        }
        
        const result = await response.json();
        console.log('[API] Response received successfully');
        console.log(`[API] Model type: ${result.model_type}`);
        console.log(`[API] Logs count: ${result.logs.length}`);
        
        // Display logs first
        if (result.logs && result.logs.length > 0) {
            console.log('[DISPLAY] Adding process logs');
            const logsHtml = result.logs.map(log => {
                let className = 'log-line';
                if (log.includes('[OK]') || log.includes('✓')) className += ' success';
                else if (log.includes('[ERROR]') || log.includes('❌')) className += ' error';
                else if (log.includes('[WARN]')) className += ' warning';
                return `<div class="${className}">${log}</div>`;
            }).join('');
            
            addMessage('assistant', `<div class="process-logs">${logsHtml}</div>`);
        }
        
        // Then display results
        console.log('[DISPLAY] Showing results');
        displayResults(result);
        
    } catch (error) {
        removeTypingIndicator();
        hideLoading();
        console.error('[ERROR] Exception during analysis:', error);
        addMessage('assistant', `Connection error: ${error.message}`);
    }
}

// ============================================================
// UI UPDATES
// ============================================================

function hideWelcomeState() {
    const welcome = document.getElementById('welcomeState');
    if (welcome) welcome.classList.add('hidden');
}

function showWelcomeState() {
    const welcome = document.getElementById('welcomeState');
    const messages = document.getElementById('messagesContainer');
    if (welcome && messages && messages.children.length === 0) {
        welcome.classList.remove('hidden');
    }
}

function addTypingIndicator() {
    const container = document.getElementById('messagesContainer');
    if (!container) return;
    const indicator = document.createElement('div');
    indicator.className = 'typing-indicator';
    indicator.id = 'typingIndicator';
    indicator.innerHTML = '<span></span><span></span><span></span>';
    container.appendChild(indicator);
    container.scrollTop = container.scrollHeight;
}

function removeTypingIndicator() {
    const indicator = document.getElementById('typingIndicator');
    if (indicator) indicator.remove();
}

function addMessage(sender, content) {
    console.log(`[MESSAGE] Adding ${sender} message`);

    const messagesContainer = document.getElementById('messagesContainer');
    if (!messagesContainer) {
        console.error('[ERROR] messagesContainer element not found');
        return;
    }

    removeTypingIndicator();

    const messageBubble = document.createElement('div');
    messageBubble.className = `message-bubble ${sender}`;
    messageBubble.innerHTML = content;

    messagesContainer.appendChild(messageBubble);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function showLoading() {
    console.log('[LOADING] Show loading overlay');
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) {
        overlay.classList.add('active');
    } else {
        console.error('[ERROR] loadingOverlay not found');
    }
}

function hideLoading() {
    console.log('[LOADING] Hide loading overlay');
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) {
        overlay.classList.remove('active');
    }
}

function displayResults(result) {
    console.log('[RESULTS] Displaying results');
    
    const modal = document.getElementById('resultsModal');
    const container = document.getElementById('resultsContainer');
    
    if (!modal || !container) {
        console.error('[ERROR] Modal elements not found');
        return;
    }
    
    let html = '';
    const mr = result.model_result || {};
    const diag = result.diagnostics_data || {};
    
    // ============================================================
    // TITLE & QUESTION
    // ============================================================
    html += `<div class="result-section">
        <div class="result-title">📊 ${(result.model_type || 'UNKNOWN').toUpperCase()} Analysis Results</div>
        <div class="result-question">Question: <em>${result.question}</em></div>
    </div>`;
    
    // ============================================================
    // MODEL-SPECIFIC RESULTS
    // ============================================================
    if (result.model_type === 'arima') {
        console.log('[RESULTS] Formatting ARIMA results');
        
        // Key metrics cards
        html += `<div class="result-section">
            <div class="result-subtitle">📈 Forecast Metrics</div>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-label">Next Period Forecast</div>
                    <div class="stat-value">${(mr.forecast_next_period || 0).toFixed(2)}</div>
                    <div class="stat-unit">${result.intent?.outcome || 'units'}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">AR(1) Coefficient</div>
                    <div class="stat-value">${(mr.ar1_coef || 0).toFixed(4)}</div>
                    <div class="stat-unit">autocorrelation</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">RMSE</div>
                    <div class="stat-value">${(mr.rmse || 0).toFixed(4)}</div>
                    <div class="stat-unit">error magnitude</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Stability</div>
                    <div class="stat-value" style="font-size: 14px;">${(mr.process_stability || 'UNKNOWN')}</div>
                    <div class="stat-unit">process behavior</div>
                </div>
            </div>
        </div>`;
        
        // Diagnostics table
        if (diag && Object.keys(diag).length > 0) {
            html += `<div class="result-section">
                <div class="result-subtitle">🔍 Diagnostic Tests</div>
                <table class="diag-table">
                    <thead>
                        <tr>
                            <th>Test</th>
                            <th>Value</th>
                            <th>Interpretation</th>
                        </tr>
                    </thead>
                    <tbody>`;
            
            for (const [key, val] of Object.entries(diag)) {
                const displayKey = key.replace(/_/g, ' ').toUpperCase();
                let interpretation = '';
                
                if (key === 'autocorrelation' && val === 'None') interpretation = '✓ No problematic autocorrelation';
                else if (key === 'heteroscedasticity' && val === 'None') interpretation = '✓ Constant variance';
                else if (key === 'stationarity' && val === 'Yes') interpretation = '✓ Data is stationary';
                else if (key.includes('test')) interpretation = val;
                else interpretation = String(val).substring(0, 50);
                
                html += `<tr>
                    <td>${displayKey}</td>
                    <td><code>${String(val).substring(0, 30)}</code></td>
                    <td>${interpretation}</td>
                </tr>`;
            }
            
            html += `</tbody></table></div>`;
        }
        
    } else if (result.model_type === 'diff_in_diff') {
        console.log('[RESULTS] Formatting DiD results');
        
        html += `<div class="result-section">
            <div class="result-subtitle">🎯 Treatment Effect Estimates</div>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-label">Treatment Effect</div>
                    <div class="stat-value">${(mr.treatment_effect || 0).toFixed(4)}</div>
                    <div class="stat-unit">estimated impact</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Std. Error</div>
                    <div class="stat-value">${(mr.se || 0).toFixed(4)}</div>
                    <div class="stat-unit">uncertainty</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">P-value</div>
                    <div class="stat-value">${(mr.pvalue || 0).toFixed(4)}</div>
                    <div class="stat-unit">significance</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">R²</div>
                    <div class="stat-value">${(mr.r_squared || 0).toFixed(4)}</div>
                    <div class="stat-unit">fit quality</div>
                </div>
            </div>
        </div>`;
        
        // Regression table
        if (mr.regression_table) {
            html += `<div class="result-section">
                <div class="result-subtitle">📋 Regression Coefficients</div>
                <table class="diag-table">
                    <thead>
                        <tr><th>Variable</th><th>Coefficient</th><th>Std. Error</th><th>t-stat</th><th>p-value</th></tr>
                    </thead>
                    <tbody>`;
            
            for (const [var_name, coef_data] of Object.entries(mr.regression_table)) {
                html += `<tr>
                    <td><strong>${var_name}</strong></td>
                    <td>${parseFloat(coef_data.coef || 0).toFixed(4)}</td>
                    <td>${parseFloat(coef_data.se || 0).toFixed(4)}</td>
                    <td>${parseFloat(coef_data.t || 0).toFixed(4)}</td>
                    <td>${parseFloat(coef_data.pvalue || 0).toFixed(4)}</td>
                </tr>`;
            }
            
            html += `</tbody></table></div>`;
        }
    }
    
    // ============================================================
    // AI INTERPRETATION
    // ============================================================
    if (result.interpretation) {
        html += `<div class="result-section">
            <div class="result-subtitle">💡 What This Means</div>
            <div class="interpretation-box">`;
        
        // Try to format as bullet points if it's plain text
        const interp = result.interpretation;
        if (!interp.includes('<')) {
            // Plain text - convert to bullets
            const sentences = interp.split(/(?<=[.!?])\s+/);
            html += '<ul class="interpretation-list">';
            sentences.forEach(sent => {
                if (sent.trim().length > 10) {
                    html += `<li>${sent.trim()}</li>`;
                }
            });
            html += '</ul>';
        } else {
            // Already HTML
            html += interp;
        }
        
        html += `</div></div>`;
    }
    
    // ============================================================
    // FOOTER INFO
    // ============================================================
    html += `<div class="result-section result-footer">
        <strong>Analysis Info:</strong><br>
        Model: ${result.model_type} | Generated: ${new Date(result.timestamp).toLocaleString()}<br>
        Question: ${result.intent?.question_type || 'unknown'} | Outcome: ${result.intent?.outcome || 'N/A'}
    </div>`;
    
    container.innerHTML = html;
    modal.classList.add('active');
    console.log('[RESULTS] Modal shown');
}

function closeResults() {
    console.log('[RESULTS] Closing modal');
    const modal = document.getElementById('resultsModal');
    if (modal) {
        modal.classList.remove('active');
    }
}

function loadHistory() {
    console.log('[HISTORY] Loading history');
    try {
        fetch('/api/history')
            .then(r => r.json())
            .then(history => {
                console.log(`[HISTORY] Loaded ${history.length} items`);
                const historyList = document.getElementById('historyList');
                if (historyList) {
                    historyList.innerHTML = '';
                    
                    history.forEach(item => {
                        const div = document.createElement('div');
                        div.className = 'history-item';
                        div.innerHTML = `
                            <div class="history-question">${item.question}</div>
                            <div class="history-meta">${item.model} • ${new Date(item.timestamp).toLocaleString()}</div>
                        `;
                        historyList.appendChild(div);
                    });
                }
            });
    } catch (error) {
        console.error('[ERROR] Loading history failed:', error);
    }
}
