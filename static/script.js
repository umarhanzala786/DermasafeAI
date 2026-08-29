if (window.dermasafeScriptLoaded) {
    console.warn("Dermasafe script already loaded. Skipping duplicate.");
} else {

  window.dermasafeScriptLoaded = true;

  document.addEventListener("DOMContentLoaded", function () {

      // =========================================================
      // ELEMENTS
      // =========================================================

      const imageFile = document.getElementById("imageFile");
      const preview = document.getElementById("preview");
      const previewImage = document.getElementById("previewImage");
      const uploadZone = document.getElementById("uploadZone");

      const scanForm = document.getElementById("scanForm");
      const output = document.getElementById("output");
      const submitBtn = document.getElementById("submitBtn");

      const historySearch =
          document.getElementById("historySearch");

      const diseaseChart =
          document.getElementById("diseaseChart");


      // =========================================================
      // IMPORTANT: DUPLICATE SUBMISSION LOCK
      // =========================================================

      let isSubmitting = false;


      // =========================================================
      // IMAGE PREVIEW
      // =========================================================

      if (imageFile) {

          imageFile.addEventListener("change", function () {

              const file = imageFile.files[0];

              if (!file) {
                  return;
              }


              // Validate image type

              if (!file.type.startsWith("image/")) {

                  showError(
                      "Please select a valid image file."
                  );

                  imageFile.value = "";

                  return;
              }


              // Validate file size - 8 MB

              const maxSize = 8 * 1024 * 1024;

              if (file.size > maxSize) {

                  showError(
                      "Image size must be less than 8 MB."
                  );

                  imageFile.value = "";

                  return;
              }


              // Create preview

              const objectUrl =
                  URL.createObjectURL(file);


              if (previewImage) {

                  previewImage.src =
                      objectUrl;

              }


              if (preview) {

                  preview.classList.remove(
                      "hidden"
                  );

              }

          });

      }


      // =========================================================
      // DRAG & DROP
      // =========================================================

      if (uploadZone) {

          uploadZone.addEventListener(
              "dragover",
              function (event) {

                  event.preventDefault();

                  uploadZone.classList.add(
                      "dragging"
                  );

              }
          );


          uploadZone.addEventListener(
              "dragleave",
              function () {

                  uploadZone.classList.remove(
                      "dragging"
                  );

              }
          );


          uploadZone.addEventListener(
              "drop",
              function (event) {

                  event.preventDefault();

                  uploadZone.classList.remove(
                      "dragging"
                  );


                  const files =
                      event.dataTransfer.files;


                  if (!files || files.length === 0) {
                      return;
                  }


                  const file =
                      files[0];


                  // Validate file

                  if (!file.type.startsWith("image/")) {

                      showError(
                          "Please drop a valid image file."
                      );

                      return;
                  }


                  const maxSize =
                      8 * 1024 * 1024;


                  if (file.size > maxSize) {

                      showError(
                          "Image size must be less than 8 MB."
                      );

                      return;
                  }


                  // Put dropped file into input

                  try {

                      const dataTransfer =
                          new DataTransfer();

                      dataTransfer.items.add(
                          file
                      );

                      imageFile.files =
                          dataTransfer.files;


                      // Trigger preview

                      imageFile.dispatchEvent(
                          new Event("change")
                      );

                  } catch (error) {

                      console.error(
                          "Drag/drop error:",
                          error
                      );

                  }

              }
          );

      }


      // =========================================================
      // FORM SUBMISSION
      // =========================================================

      if (scanForm) {

          scanForm.addEventListener(
              "submit",
              async function (event) {

                  // -------------------------------------------------
                  // ALWAYS prevent normal browser submission
                  // -------------------------------------------------

                  event.preventDefault();
                  event.stopPropagation();


                  // -------------------------------------------------
                  // DUPLICATE SUBMISSION PROTECTION
                  // -------------------------------------------------

                  if (isSubmitting) {

                      console.log(
                          "Duplicate submission blocked."
                      );

                      return;
                  }


                  // Lock immediately
                  isSubmitting = true;


                  // -------------------------------------------------
                  // HTML FORM VALIDATION
                  // -------------------------------------------------

                  if (!scanForm.checkValidity()) {

                      isSubmitting = false;

                      scanForm.reportValidity();

                      return;
                  }


                  // -------------------------------------------------
                  // IMAGE VALIDATION
                  // -------------------------------------------------

                  if (
                      !imageFile ||
                      !imageFile.files ||
                      imageFile.files.length === 0
                  ) {

                      isSubmitting = false;

                      showError(
                          "Please upload a skin image."
                      );

                      return;
                  }


                  // -------------------------------------------------
                  // LOADING STATE
                  // -------------------------------------------------

                  setLoading(true);


                  showInfo(
                      "AI is analyzing the uploaded skin image..."
                  );


                  try {

                      // -------------------------------------------------
                      // CREATE FORM DATA
                      // -------------------------------------------------

                      const formData =
                          new FormData(scanForm);


                      // -------------------------------------------------
                      // SEND ONLY ONE REQUEST
                      // -------------------------------------------------

                      const response =
                          await fetch(
                              scanForm.action ||
                              "/predict_scan",
                              {
                                  method: "POST",

                                  body: formData,

                                  credentials:
                                      "same-origin"
                              }
                          );


                      // -------------------------------------------------
                      // CHECK CONTENT TYPE
                      // -------------------------------------------------

                      const contentType =
                          response.headers.get(
                              "content-type"
                          ) || "";


                      let data;


                      if (
                          contentType.includes(
                              "application/json"
                          )
                      ) {

                          data =
                              await response.json();

                      } else {

                          throw new Error(
                              `Unexpected server response (${response.status}).`
                          );

                      }


                      // -------------------------------------------------
                      // SERVER ERROR
                      // -------------------------------------------------

                      if (!response.ok) {

                          throw new Error(
                              data.error ||
                              `Prediction failed (${response.status}).`
                          );

                      }


                      // -------------------------------------------------
                      // SUCCESS
                      // -------------------------------------------------

                      console.log(
                          "Prediction successful:",
                          data
                      );


                      showSuccess(data);


                      // -------------------------------------------------
                      // RESET FORM
                      // -------------------------------------------------

                      scanForm.reset();


                      if (preview) {

                          preview.classList.add(
                              "hidden"
                          );

                      }


                      if (previewImage) {

                          previewImage.removeAttribute(
                              "src"
                          );

                      }


                      // -------------------------------------------------
                      // REFRESH CHART
                      // -------------------------------------------------

                      await loadStatistics();


                      // -------------------------------------------------
                      // KEEP USER ON DASHBOARD
                      // -------------------------------------------------

                      // Do NOT immediately redirect.
                      // User can see the result first.


                      setTimeout(
                          function () {

                              window.location.href =
                                  "/dashboard";

                          },
                          5000
                      );


                  } catch (error) {

                      console.error(
                          "Prediction error:",
                          error
                      );


                      showError(
                          error.message ||
                          "Unable to process the screening request."
                      );


                      // Allow retry only after failure
                      isSubmitting = false;

                      setLoading(false);

                  }

              }
          );

      }


      // =========================================================
      // SUCCESS RESULT
      // =========================================================

      function showSuccess(data) {

          if (!output) {
              return;
          }


          const diagnosis =
              data.diagnosis ||
              (
                  data.result
                      ? data.result.split(" (")[0]
                      : "Unknown"
              );


          const confidence =
              data.confidence !== undefined
                  ? Number(data.confidence).toFixed(1) + "%"
                  : "N/A";


          output.classList.remove(
              "hidden"
          );


          output.classList.remove(
              "result-error",
              "result-info"
          );


          output.classList.add(
              "result-success"
          );


          output.innerHTML = `

              <div class="result-header">

                  <div class="result-icon">
                      ✓
                  </div>

                  <div>

                      <span>
                          AI SCREENING COMPLETE
                      </span>

                      <h3>
                          ${escapeHtml(diagnosis)}
                      </h3>

                  </div>

              </div>


              <div class="confidence-row">

                  <span>
                      Model confidence
                  </span>

                  <strong>
                      ${confidence}
                  </strong>

              </div>


              ${
                  data.scan_id
                  ?
                  `
                  <div class="scan-id-row">
                      Scan ID:
                      <strong>
                          #${data.scan_id}
                      </strong>
                  </div>
                  `
                  :
                  ""
              }


              <div class="result-disclaimer">

                  This AI result is a preliminary
                  screening aid and is not a medical
                  diagnosis. Consult a qualified
                  healthcare professional for evaluation.

              </div>


              <div class="result-next">

                  ✓ Record saved to your screening history

              </div>

          `;

      }


      // =========================================================
      // ERROR RESULT
      // =========================================================

      function showError(message) {

          if (!output) {
              return;
          }


          output.classList.remove(
              "hidden"
          );


          output.classList.remove(
              "result-success",
              "result-info"
          );


          output.classList.add(
              "result-error"
          );


          output.innerHTML = `

              <div class="result-header">

                  <div class="result-icon">
                      !
                  </div>

                  <div>

                      <span>
                          SCREENING ERROR
                      </span>

                      <h3>
                          Unable to complete screening
                      </h3>

                  </div>

              </div>


              <p>
                  ${escapeHtml(message)}
              </p>

          `;

      }


      // =========================================================
      // INFORMATION / LOADING MESSAGE
      // =========================================================

      function showInfo(message) {

          if (!output) {
              return;
          }


          output.classList.remove(
              "hidden"
          );


          output.classList.remove(
              "result-success",
              "result-error"
          );


          output.classList.add(
              "result-info"
          );


          output.innerHTML = `

              <div class="result-loading">

                  <div class="spinner"></div>

                  <span>
                      ${escapeHtml(message)}
                  </span>

              </div>

          `;

      }


      // =========================================================
      // BUTTON LOADING STATE
      // =========================================================

      function setLoading(loading) {

          if (!submitBtn) {
              return;
          }


          submitBtn.disabled =
              loading;


          if (loading) {

              submitBtn.innerHTML = `

                  <span class="spinner-small"></span>

                  Analyzing...

              `;

          } else {

              submitBtn.innerHTML = `

                  <span>
                      Run AI Analysis
                  </span>

                  <span>
                      →
                  </span>

              `;

          }

      }


      // =========================================================
      // LOAD STATISTICS
      // =========================================================

      async function loadStatistics() {

          if (!diseaseChart) {
              return;
          }


          try {

              const response =
                  await fetch(
                      "/api/stats",
                      {
                          method: "GET",

                          credentials:
                              "same-origin"
                      }
                  );


              if (!response.ok) {

                  throw new Error(
                      "Unable to load statistics."
                  );

              }


              const data =
                  await response.json();


              const distribution =
                  data.distribution ||
                  data.disease_distribution ||
                  [];


              renderChart(
                  distribution
              );


          } catch (error) {

              console.error(
                  "Statistics error:",
                  error
              );

          }

      }


      // =========================================================
      // RENDER DISEASE CHART
      // =========================================================

      function renderChart(distribution) {

          const canvas =
              diseaseChart;


          if (!canvas) {
              return;
          }


          const container =
              canvas.parentElement;


          // Destroy existing chart

          if (
              window.diseaseChart &&
              typeof window.diseaseChart.destroy ===
                  "function"
          ) {

              window.diseaseChart.destroy();

              window.diseaseChart =
                  null;

          }


          // -----------------------------------------------------
          // NO DATA
          // -----------------------------------------------------

          if (
              !distribution ||
              distribution.length === 0
          ) {

              canvas.style.display =
                  "none";


              let emptyState =
                  container.querySelector(
                      ".chart-empty"
                  );


              if (!emptyState) {

                  emptyState =
                      document.createElement(
                          "div"
                      );


                  emptyState.className =
                      "chart-empty";


                  emptyState.innerHTML = `

                      <div class="chart-empty-icon">
                          ◌
                      </div>

                      <strong>
                          No screening data yet
                      </strong>

                      <span>
                          Complete your first AI skin
                          screening to see disease distribution.
                      </span>

                      <a href="#new-scan">
                          Start a new scan →
                      </a>

                  `;


                  container.appendChild(
                      emptyState
                  );

              }


              return;
          }


          // -----------------------------------------------------
          // DATA AVAILABLE
          // -----------------------------------------------------

          canvas.style.display =
              "block";


          const oldEmpty =
              container.querySelector(
                  ".chart-empty"
              );


          if (oldEmpty) {

              oldEmpty.remove();

          }


          const labels =
              distribution.map(
                  function (item) {

                      const value =
                          item.status ||
                          item.label ||
                          "";

                      return value
                          .split(" (")[0];

                  }
              );


          const values =
              distribution.map(
                  function (item) {

                      return Number(
                          item.count
                      );

                  }
              );


          // -----------------------------------------------------
          // CHECK CHART.JS
          // -----------------------------------------------------

          if (
              typeof Chart ===
              "undefined"
          ) {

              console.error(
                  "Chart.js is not loaded."
              );

              return;
          }


          // -----------------------------------------------------
          // CREATE CHART
          // -----------------------------------------------------

          window.diseaseChart =
              new Chart(
                  canvas,
                  {

                      type: "doughnut",

                      data: {

                          labels: labels,

                          datasets: [

                              {

                                  data: values,

                                  backgroundColor: [
                                      "#0f766e",
                                      "#14b8a6",
                                      "#2dd4bf",
                                      "#5eead4",
                                      "#99f6e4"
                                  ],

                                  borderWidth: 0,

                                  hoverOffset: 6

                              }

                          ]

                      },

                      options: {

                          responsive: true,

                          maintainAspectRatio:
                              false,

                          cutout: "68%",

                          plugins: {

                              legend: {

                                  position:
                                      "bottom",

                                  labels: {

                                      padding:
                                          18,

                                      boxWidth:
                                          12,

                                      usePointStyle:
                                          true,

                                      font: {

                                          size:
                                              11

                                      }

                                  }

                              }

                          }

                      }

                  }
              );

      }


      // =========================================================
      // HISTORY SEARCH
      // =========================================================

      if (historySearch) {

          historySearch.addEventListener(
              "input",
              function () {

                  const query =
                      historySearch.value
                          .toLowerCase()
                          .trim();


                  const rows =
                      document.querySelectorAll(
                          "#historyTable tbody tr"
                      );


                  rows.forEach(
                      function (row) {

                          const text =
                              row.innerText
                                  .toLowerCase();


                          if (
                              !query ||
                              text.includes(query)
                          ) {

                              row.style.display =
                                  "";

                          } else {

                              row.style.display =
                                  "none";

                          }

                      }
                  );

              }
          );

      }


      // =========================================================
      // HTML ESCAPE
      // =========================================================

      function escapeHtml(value) {

          if (value === null ||
              value === undefined) {

              return "";

          }


          return String(value)
              .replace(/&/g, "&amp;")
              .replace(/</g, "&lt;")
              .replace(/>/g, "&gt;")
              .replace(/"/g, "&quot;")
              .replace(/'/g, "&#039;");

      }


      // =========================================================
      // INITIAL DASHBOARD LOAD
      // =========================================================

      loadStatistics();

  });
}