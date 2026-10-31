/* ============================================================
   DERMASAFE AI — COMPLETE CLIENT JAVASCRIPT
   Features:
   - Duplicate submission protection
   - Client-side drag-and-drop & image preview
   - Async AI inference (CNN + Gemini Insights)
   - Dynamic Probability Bars & Clinical Insights display
   - Chart.js Screening Distribution (Doughnut)
   - Chart.js Monthly Activity Trends (Bar)
   - Instant Client-side Table Search
   - Scan Record Deletion with Confirmation
   - Light / Dark Mode Toggle with localStorage persistence
   - Mobile Navigation Drawer Toggle
============================================================ */

if (window.dermasafeScriptLoaded) {
    console.warn("Dermasafe script already loaded. Skipping duplicate execution.");
} else {
    window.dermasafeScriptLoaded = true;

    document.addEventListener("DOMContentLoaded", function () {

        // =========================================================
        // 1. THEME TOGGLE (DARK / LIGHT MODE)
        // =========================================================
        const themeToggle = document.getElementById("themeToggle");
        const htmlElement = document.documentElement;

        // Load saved theme or system preference
        const savedTheme = localStorage.getItem("dermasafe-theme") ||
            (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
        htmlElement.setAttribute("data-theme", savedTheme);

        if (themeToggle) {
            themeToggle.addEventListener("click", function () {
                const currentTheme = htmlElement.getAttribute("data-theme") || "light";
                const newTheme = currentTheme === "dark" ? "light" : "dark";
                htmlElement.setAttribute("data-theme", newTheme);
                localStorage.setItem("dermasafe-theme", newTheme);

                // Update charts theme colors if initialized
                updateChartsTheme();
            });
        }

        // =========================================================
        // 2. MOBILE MENU TOGGLE
        // =========================================================
        const mobileToggle = document.querySelector("[data-mobile-menu]");
        const navLinks = document.querySelector("[data-nav]");

        if (mobileToggle && navLinks) {
            mobileToggle.addEventListener("click", function () {
                navLinks.classList.toggle("open");
            });
        }

        // =========================================================
        // 3. IMAGE PREVIEW & DRAG-AND-DROP
        // =========================================================
        const imageFile = document.getElementById("imageFile");
        const preview = document.getElementById("preview");
        const previewImage = document.getElementById("previewImage");
        const uploadZone = document.getElementById("uploadZone");
        const scanForm = document.getElementById("scanForm");
        const output = document.getElementById("output");
        const submitBtn = document.getElementById("submitBtn");
        const historySearch = document.getElementById("historySearch");
        const diseaseChart = document.getElementById("diseaseChart");
        const trendsChart = document.getElementById("trendsChart");

        let isSubmitting = false;

        function handleFileSelection(file) {
            if (!file) return;

            if (!file.type.startsWith("image/")) {
                showError("Please select a valid image file (JPG, PNG, WEBP).");
                if (imageFile) imageFile.value = "";
                return;
            }

            const maxSize = 8 * 1024 * 1024; // 8 MB
            if (file.size > maxSize) {
                showError("Image size must be less than 8 MB.");
                if (imageFile) imageFile.value = "";
                return;
            }

            const objectUrl = URL.createObjectURL(file);
            if (previewImage) previewImage.src = objectUrl;
            if (preview) preview.classList.remove("hidden");
        }

        if (imageFile) {
            imageFile.addEventListener("change", function () {
                if (imageFile.files && imageFile.files[0]) {
                    handleFileSelection(imageFile.files[0]);
                }
            });
        }

        if (uploadZone) {
            ["dragenter", "dragover"].forEach(eventName => {
                uploadZone.addEventListener(eventName, function (e) {
                    e.preventDefault();
                    uploadZone.classList.add("dragging");
                });
            });

            ["dragleave", "drop"].forEach(eventName => {
                uploadZone.addEventListener(eventName, function (e) {
                    e.preventDefault();
                    uploadZone.classList.remove("dragging");
                });
            });

            uploadZone.addEventListener("drop", function (e) {
                const files = e.dataTransfer.files;
                if (!files || files.length === 0) return;

                const file = files[0];
                handleFileSelection(file);

                try {
                    const dataTransfer = new DataTransfer();
                    dataTransfer.items.add(file);
                    if (imageFile) imageFile.files = dataTransfer.files;
                } catch (err) {
                    console.warn("Direct file transfer not supported in browser:", err);
                }
            });
        }

        // =========================================================
        // 4. SCAN FORM SUBMISSION (CNN + GEMINI AI)
        // =========================================================
        if (scanForm) {
            scanForm.addEventListener("submit", async function (event) {
                event.preventDefault();
                event.stopPropagation();

                if (isSubmitting) return;

                if (!scanForm.checkValidity()) {
                    scanForm.reportValidity();
                    return;
                }

                if (!imageFile || !imageFile.files || imageFile.files.length === 0) {
                    showError("Please upload a skin lesion image.");
                    return;
                }

                isSubmitting = true;
                setLoading(true);
                showInfo("AI model is classifying the lesion and retrieving clinical insights...");

                try {
                    const formData = new FormData(scanForm);

                    const response = await fetch(scanForm.action || "/predict_scan", {
                        method: "POST",
                        body: formData,
                        credentials: "same-origin"
                    });

                    const contentType = response.headers.get("content-type") || "";
                    let data;
                    if (contentType.includes("application/json")) {
                        data = await response.json();
                    } else {
                        throw new Error(`Unexpected server response (${response.status})`);
                    }

                    if (!response.ok || !data.success) {
                        throw new Error(data.error || `Prediction failed (${response.status})`);
                    }

                    showSuccess(data);

                    // Reset inputs
                    scanForm.reset();
                    if (preview) preview.classList.add("hidden");
                    if (previewImage) previewImage.removeAttribute("src");

                    // Refresh dashboard charts and table if on dashboard
                    await loadStatistics();
                    await loadTrends();

                    // Automatically refresh or stay with option to review
                    const note = document.createElement("div");
                    note.className = "result-next";
                    note.innerHTML = `✓ Screening record #${data.scan_id || ""} successfully saved. Page will update in 6 seconds, or <a href="/dashboard" style="color:var(--primary);text-decoration:underline;">click here to refresh now</a>.`;
                    output.appendChild(note);

                    setTimeout(() => {
                        window.location.reload();
                    }, 6000);

                } catch (error) {
                    console.error("Prediction error:", error);
                    showError(error.message || "Unable to complete screening. Please check server logs.");
                } finally {
                    isSubmitting = false;
                    setLoading(false);
                }
            });
        }

        // =========================================================
        // 5. RESULT RENDERING
        // =========================================================
        function showSuccess(data) {
            if (!output) return;

            output.className = "result-panel result-success";

            const diagnosis = escapeHtml(data.diagnosis || "Unknown");
            const confidence = data.confidence !== undefined ? `${Number(data.confidence).toFixed(1)}%` : "N/A";

            // Class Probabilities Breakdown
            let probabilitiesHtml = "";
            if (data.probabilities && typeof data.probabilities === "object") {
                probabilitiesHtml = `
                    <div style="margin-top: 14px; padding-top: 12px; border-top: 1px solid rgba(15,118,110,.15);">
                        <strong style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; display:block; margin-bottom: 8px;">
                            Class Probabilities Distribution:
                        </strong>
                        <div style="display: grid; gap: 6px;">
                            ${Object.entries(data.probabilities).map(([name, prob]) => `
                                <div style="display: flex; align-items: center; justify-content: space-between; font-size: 11px;">
                                    <span style="width: 90px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(name)}</span>
                                    <div style="flex: 1; margin: 0 10px; height: 6px; background: rgba(0,0,0,0.06); border-radius: 4px; overflow: hidden;">
                                        <div style="width: ${Math.min(prob, 100)}%; height: 100%; background: var(--primary); border-radius: 4px;"></div>
                                    </div>
                                    <span style="font-weight: 700; width: 42px; text-align: right;">${prob}%</span>
                                </div>
                            `).join("")}
                        </div>
                    </div>
                `;
            }

            // Gemini Clinical Insights
            let insightsHtml = "";
            if (data.ai_insights) {
                insightsHtml = `
                    <div class="gemini-section">
                        <h4>✦ AI Clinical Insights (Powered by Gemini)</h4>
                        <div class="gemini-text">${escapeHtml(data.ai_insights)}</div>
                    </div>
                `;
            }

            output.innerHTML = `
                <div class="result-header">
                    <div class="result-icon">✓</div>
                    <div>
                        <span>AI SCREENING COMPLETE</span>
                        <h3>${diagnosis}</h3>
                    </div>
                </div>

                <div class="confidence-row">
                    <span>Model Confidence</span>
                    <strong>${confidence}</strong>
                </div>

                ${data.scan_id ? `
                    <div class="scan-id-row" style="margin-top: 8px; font-size: 12px;">
                        Screening ID: <strong>#${data.scan_id}</strong> ·
                        <a href="/scan/${data.scan_id}" style="color:var(--primary); font-weight:700;">View Full Detail Page →</a>
                    </div>
                ` : ""}

                ${probabilitiesHtml}
                ${insightsHtml}

                <div class="result-disclaimer">
                    This screening is an AI-assisted classification and NOT a definitive clinical diagnosis.
                    Always consult a licensed medical professional or dermatologist.
                </div>
            `;
        }

        function showError(message) {
            if (!output) return;
            output.className = "result-panel result-error";
            output.innerHTML = `
                <div class="result-header">
                    <div class="result-icon">!</div>
                    <div>
                        <span>SCREENING ERROR</span>
                        <h3>Unable to complete screening</h3>
                    </div>
                </div>
                <p style="margin: 10px 0 0; font-size: 13px;">${escapeHtml(message)}</p>
            `;
        }

        function showInfo(message) {
            if (!output) return;
            output.className = "result-panel result-info";
            output.innerHTML = `
                <div class="result-loading">
                    <div class="spinner"></div>
                    <span>${escapeHtml(message)}</span>
                </div>
            `;
        }

        function setLoading(loading) {
            if (!submitBtn) return;
            submitBtn.disabled = loading;
            if (loading) {
                submitBtn.innerHTML = `<span class="spinner-small"></span> Analyzing...`;
            } else {
                submitBtn.innerHTML = `<span>Run AI Analysis</span> <span>→</span>`;
            }
        }

        // =========================================================
        // 6. RECORD DELETION
        // =========================================================
        document.addEventListener("click", async function (e) {
            const deleteBtn = e.target.closest(".delete-btn");
            if (!deleteBtn) return;

            const scanId = deleteBtn.getAttribute("data-scan-id");
            if (!scanId) return;

            if (!confirm(`Are you sure you want to permanently delete screening record #${scanId}?`)) {
                return;
            }

            deleteBtn.disabled = true;
            deleteBtn.textContent = "…";

            try {
                const response = await fetch(`/scan/${scanId}/delete`, {
                    method: "POST",
                    credentials: "same-origin"
                });

                const data = await response.json();
                if (response.ok && data.success) {
                    const tr = deleteBtn.closest("tr");
                    if (tr) {
                        tr.style.opacity = "0";
                        tr.style.transition = "opacity .3s ease";
                        setTimeout(() => tr.remove(), 300);
                    }
                    // Refresh stats
                    loadStatistics();
                    loadTrends();
                } else {
                    alert(data.error || "Failed to delete record.");
                    deleteBtn.disabled = false;
                    deleteBtn.textContent = "✕";
                }
            } catch (err) {
                console.error("Delete error:", err);
                alert("Error deleting record.");
                deleteBtn.disabled = false;
                deleteBtn.textContent = "✕";
            }
        });

        // =========================================================
        // 7. CHART.JS VISUALIZATIONS (DOUGHNUT + TRENDS)
        // =========================================================
        let diseaseChartInstance = null;
        let trendsChartInstance = null;

        async function loadStatistics() {
            if (!diseaseChart) return;

            try {
                const response = await fetch("/api/stats", {
                    method: "GET",
                    credentials: "same-origin"
                });
                if (!response.ok) return;

                const data = await response.json();
                renderDiseaseChart(data.distribution || []);
            } catch (error) {
                console.error("Error loading stats:", error);
            }
        }

        async function loadTrends() {
            if (!trendsChart) return;

            try {
                const response = await fetch("/api/trends", {
                    method: "GET",
                    credentials: "same-origin"
                });
                if (!response.ok) return;

                const data = await response.json();
                renderTrendsChart(data.trends || []);
            } catch (error) {
                console.error("Error loading trends:", error);
            }
        }

        function renderDiseaseChart(distribution) {
            if (!diseaseChart || typeof Chart === "undefined") return;

            const container = diseaseChart.parentElement;

            if (diseaseChartInstance) {
                diseaseChartInstance.destroy();
                diseaseChartInstance = null;
            }

            if (!distribution || distribution.length === 0) {
                diseaseChart.style.display = "none";
                let empty = container.querySelector(".chart-empty");
                if (!empty) {
                    empty = document.createElement("div");
                    empty.className = "chart-empty";
                    empty.innerHTML = `
                        <div class="chart-empty-icon">◌</div>
                        <strong>No screening data yet</strong>
                        <span>Complete your first screening to see disease distribution.</span>
                        <a href="#new-scan">Start a new scan →</a>
                    `;
                    container.appendChild(empty);
                }
                return;
            }

            diseaseChart.style.display = "block";
            const oldEmpty = container.querySelector(".chart-empty");
            if (oldEmpty) oldEmpty.remove();

            const labels = distribution.map(item => (item.status || "").split(" (")[0]);
            const counts = distribution.map(item => Number(item.count));

            const isDark = document.documentElement.getAttribute("data-theme") === "dark";
            const textColor = isDark ? "#94a3b8" : "#64748b";

            diseaseChartInstance = new Chart(diseaseChart, {
                type: "doughnut",
                data: {
                    labels: labels,
                    datasets: [{
                        data: counts,
                        backgroundColor: [
                            "#0f766e",
                            "#14b8a6",
                            "#2dd4bf",
                            "#5eead4",
                            "#99f6e4"
                        ],
                        borderWidth: isDark ? 2 : 0,
                        borderColor: isDark ? "#1e293b" : "#fff",
                        hoverOffset: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: "68%",
                    plugins: {
                        legend: {
                            position: "bottom",
                            labels: {
                                padding: 14,
                                boxWidth: 10,
                                usePointStyle: true,
                                color: textColor,
                                font: { size: 11, family: "Inter, sans-serif" }
                            }
                        }
                    }
                }
            });
        }

        function renderTrendsChart(trends) {
            if (!trendsChart || typeof Chart === "undefined") return;

            const container = trendsChart.parentElement;

            if (trendsChartInstance) {
                trendsChartInstance.destroy();
                trendsChartInstance = null;
            }

            if (!trends || trends.length === 0) {
                trendsChart.style.display = "none";
                return;
            }

            trendsChart.style.display = "block";

            const labels = trends.map(t => t.month);
            const counts = trends.map(t => Number(t.count));

            const isDark = document.documentElement.getAttribute("data-theme") === "dark";
            const textColor = isDark ? "#94a3b8" : "#64748b";
            const gridColor = isDark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.05)";

            trendsChartInstance = new Chart(trendsChart, {
                type: "bar",
                data: {
                    labels: labels,
                    datasets: [{
                        label: "Scans",
                        data: counts,
                        backgroundColor: "#14b8a6",
                        borderRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        x: {
                            grid: { display: false },
                            ticks: { color: textColor, font: { size: 10 } }
                        },
                        y: {
                            beginAtZero: true,
                            grid: { color: gridColor },
                            ticks: {
                                color: textColor,
                                stepSize: 1,
                                font: { size: 10 }
                            }
                        }
                    }
                }
            });
        }

        function updateChartsTheme() {
            if (diseaseChartInstance) loadStatistics();
            if (trendsChartInstance) loadTrends();
        }

        // =========================================================
        // 8. TABLE SEARCH FILTER
        // =========================================================
        if (historySearch) {
            historySearch.addEventListener("input", function () {
                const query = historySearch.value.toLowerCase().trim();
                const rows = document.querySelectorAll("#historyTable tbody tr");

                rows.forEach(function (row) {
                    if (row.querySelector(".empty-state")) return;
                    const text = row.innerText.toLowerCase();
                    row.style.display = (!query || text.includes(query)) ? "" : "none";
                });
            });
        }

        // Helper function
        function escapeHtml(value) {
            if (value === null || value === undefined) return "";
            return String(value)
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        }

        // Initial Load
        loadStatistics();
        loadTrends();
    });
}
