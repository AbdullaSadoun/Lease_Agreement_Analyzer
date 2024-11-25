document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const analysisResults = document.getElementById('analysis-results');
    const loading = document.getElementById('loading');

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, unhighlight, false);
    });

    function highlight(e) {
        dropZone.classList.add('border-primary');
    }

    function unhighlight(e) {
        dropZone.classList.remove('border-primary');
    }

    dropZone.addEventListener('drop', handleDrop, false);
    fileInput.addEventListener('change', handleFileSelect, false);

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles(files);
    }

    function handleFileSelect(e) {
        const files = e.target.files;
        handleFiles(files);
    }

    function handleFiles(files) {
        if (files.length > 0) {
            const file = files[0];
            analyzeLease(file);
        }
    }

    async function analyzeLease(file) {
        const formData = new FormData();
        formData.append('file', file);

        loading.classList.remove('hidden');
        analysisResults.classList.add('hidden');

        try {
            const response = await fetch('/analyze', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) throw new Error('Analysis failed');

            const result = await response.json();
            displayResults(result);
        } catch (error) {
            console.error('Error:', error);
            alert('Failed to analyze lease agreement');
        } finally {
            loading.classList.add('hidden');
        }
    }

    function displayResults(result) {
        const riskSummary = analysisResults.querySelector('.risk-summary');
        const ruleChecks = analysisResults.querySelector('.rule-checks');
        const llmAnalysis = analysisResults.querySelector('.llm-analysis');

        // Risk Summary
        riskSummary.className = `risk-summary risk-${result.risk_level}`;
        riskSummary.innerHTML = `
            <h2>Risk Level: ${result.risk_level}</h2>
            <p>${result.summary}</p>
        `;

        // Rule Checks
        ruleChecks.innerHTML = `
            <h2>Rule-Based Checks</h2>
            <ul>
                ${result.rule_based_results.map(rule => `
                    <li>
                        <span class="${rule.passed ? 'text-success' : 'text-danger'}">
                            ${rule.passed ? '✓' : '✗'}
                        </span>
                        <strong>${rule.rule}:</strong> ${rule.details}
                    </li>
                `).join('')}
            </ul>
        `;

        // LLM Analysis
        llmAnalysis.innerHTML = `
            <h2>AI Analysis</h2>
            <div class="fairness-score">
                <h3>Fairness Score: ${result.llm_results.fairness_score}%</h3>
                <div class="progress">
                    <div class="progress-bar" 
                         style="width: ${result.llm_results.fairness_score}%">
                    </div>
                </div>
            </div>
            <div class="issues">
                <h3>Potential Issues</h3>
                <ul>
                    ${result.llm_results.potential_issues.map(issue => 
                        `<li>${issue}</li>`).join('')}
                </ul>
            </div>
            <div class="recommendations">
                <h3>Recommendations</h3>
                <ul>
                    ${result.llm_results.recommendations.map(rec => 
                        `<li>${rec}</li>`).join('')}
                </ul>
            </div>
        `;

        analysisResults.classList.remove('hidden');
    }
});