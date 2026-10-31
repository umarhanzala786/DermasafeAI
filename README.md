# 🩺 Dermasafe AI — Intelligent Dermatological Screening Platform

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=flat&logo=flask&logoColor=white)](https://palletsprojects.com/p/flask/)
[![TensorFlow](https://img.shields.io/badge/TensorFlow-2.15-FF6F00?style=flat&logo=tensorflow&logoColor=white)](https://www.tensorflow.org/)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-AI%20Insights-4285F4?style=flat&logo=google&logoColor=white)](https://ai.google.dev/)
[![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1?style=flat&logo=mysql&logoColor=white)](https://www.mysql.com/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)

**Dermasafe AI** is a production-grade, full-stack healthcare web application that combines computer vision deep learning (TensorFlow/Keras CNN) with Large Language Models (Google Gemini AI) to provide preliminary skin disease screening and clinical patient insights.

---

## 🌟 Key Features

### 🧠 Dual AI Pipeline
- **Computer Vision (CNN)**: Custom-trained Convolutional Neural Network classifying skin lesions across 5 dermatological classes (*Acne, Melanoma, Peeling Skin, Ringworm, Vitiligo*) with per-class probability breakdowns.
- **LLM Clinical Insights (Gemini 2.0 Flash)**: Automatically generates condition descriptions, potential triggers, home care remedies, precautions, and warning signs ("When to See a Doctor") based on the predicted diagnosis and patient symptoms.

### 🛡️ Enterprise Security & Architecture
- **Bcrypt Password Encryption**: Industry-standard salting & hashing for all user credentials with zero plaintext storage, plus auto-upgrade migration for legacy accounts.
- **Thread-Safe MySQL Connection Pooling**: Per-request database connection lifecycle management using Flask's application context (`flask.g`) and teardown handlers.
- **Duplicate Request Throttling**: Intelligent 10-second request deduplication window protecting against accidental double submissions.
- **File Upload Security**: Strict MIME-type validation, file extension filtering, filename sanitization via `secure_filename`, and an 8 MB size cap.

### 📊 Interactive Analytics & Clinical Workflow
- **Interactive Dashboard**: Real-time screening distribution doughnut chart and monthly activity trends chart powered by Chart.js.
- **Automated PDF Generation**: High-fidelity clinical screening reports generated programmatically with ReportLab.
- **Data Export & Management**: Instant CSV export of patient screening history and individual scan management with deletion support.
- **Dark / Light Mode**: Seamless theme toggling with CSS custom properties and persistent state in `localStorage`.
- **Responsive Healthcare UI**: Polished, mobile-first design with drag-and-drop file upload zones and live image previews.

---

## 🏗️ Architecture Overview

```
                          [ Client Browser ]
                                   │
                 ┌─────────────────┴─────────────────┐
                 │  Drag-and-Drop Intake & Analytics │
                 └─────────────────┬─────────────────┘
                                   │ HTTPS / REST API
                                   ▼
                       [ Flask Web Application ]
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         │                         │                         │
         ▼                         ▼                         ▼
  [ Auth & Security ]       [ ML Inference ]         [ Generative AI ]
   - bcrypt Hashing          - 64x64x3 Preprocess     - Gemini 2.0 Flash
   - Session State           - TensorFlow CNN         - Treatment Insights
   - CSRF & Upload Checks    - Softmax Probabilities  - Precaution Protocol
         │                         │                         │
         └─────────────────────────┼─────────────────────────┘
                                   │
                                   ▼
                    [ Persistent Storage Layer ]
                     - MySQL 8.0 (Users & Scans)
                     - ReportLab PDF Generation Engine
```

---

## 🔬 Supported Conditions & Model Scope

The deep learning model evaluates dermoscopic and macroscopic lesion images against five distinct categories:

| Condition | Description | Clinical Importance |
| :--- | :--- | :--- |
| **Acne Vulgaris** | Inflammatory skin condition affecting oil glands | Common outpatient complaint |
| **Melanoma** | High-risk malignancy originating in melanocytes | Early detection is critical |
| **Peeling Skin** | Exfoliative disorders and shedding episodes | Indicative of systemic/barrier issues |
| **Ringworm (Tinea)** | Fungal infection displaying circular lesions | Requires prompt topical antifungal care |
| **Vitiligo** | Depigmentation condition from melanocyte loss | Autoimmune evaluation recommended |

> *Disclaimer: Dermasafe AI is intended strictly for educational, research, and preliminary screening purposes and does not replace examination by a board-certified dermatologist.*

---

## 🛠️ Tech Stack

- **Backend**: Python 3.11+, Flask 3.0, Werkzeug
- **Deep Learning**: TensorFlow 2.15, Keras, NumPy
- **Generative AI**: Google Generative AI Python SDK (Gemini)
- **Database**: MySQL 8.0 with `mysql-connector-python`
- **Security**: `bcrypt`, `python-dotenv`
- **PDF Engine**: ReportLab 4.0
- **Frontend**: HTML5, CSS3 (CSS Variables, Flexbox/Grid), Modern Vanilla JavaScript (ES6+)
- **Data Visualization**: Chart.js
- **Containerization**: Docker, Docker Compose

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11 or higher
- MySQL Server 8.0+
- (Optional) Docker & Docker Compose
- (Optional) Google Gemini API Key ([Get one free at Google AI Studio](https://aistudio.google.com/))

### 1. Clone & Set Up Virtual Environment

```bash
git clone https://github.com/your-username/DermasafeAI_FullStack.git
cd DermasafeAI_FullStack

# Create and activate virtual environment
python -m venv venv

# Windows:
venv\Scripts\activate

# macOS / Linux:
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Database & Environment

1. Ensure MySQL is running on your machine.
2. Initialize database schema:
   ```bash
   mysql -u root -p < schema.sql
   ```
3. Create your `.env` configuration file (or copy from `.env.example`):
   ```ini
   DB_HOST=localhost
   DB_USER=root
   DB_PASSWORD=your_mysql_password
   DB_NAME=skin_disease_db
   SECRET_KEY=generate_a_secure_random_key_here
   GEMINI_API_KEY=your_gemini_api_key_optional
   ```

### 4. Run Application

```bash
python app.py
```

Visit **`http://127.0.0.1:5000`** in your browser.

---

## 🐳 Running with Docker

Deploy the complete application stack (Flask web app + MySQL database) with a single command:

```bash
docker-compose up --build
```

The application will be accessible at `http://localhost:5000` with automated MySQL healthchecks and data persistence.

---

## 📌 API Endpoints

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :---: |
| `GET` | `/` | Home / Landing Page | No |
| `POST` | `/signup` | User Registration (bcrypt hashing) | No |
| `POST` | `/login` | User Authentication | No |
| `GET` | `/dashboard` | User Workspace & Analytics | Yes |
| `POST` | `/predict_scan` | CNN Inference & Gemini Insights | Yes |
| `GET` | `/scan/<id>` | Full Scan Detail & Analysis View | Yes |
| `POST` | `/scan/<id>/delete` | Delete Scan Record & Associated Image | Yes |
| `GET` | `/download_report/<id>` | Download PDF Screening Summary | Yes |
| `GET` | `/export/csv` | Export Screening History as CSV | Yes |
| `GET` | `/api/stats` | JSON Disease Distribution Counts | Yes |
| `GET` | `/api/trends` | JSON Monthly Screening Trend Data | Yes |

---

## 💼 Resume Bullet Points (Copy & Paste)

- **Engineered an end-to-end AI dermatology screening web platform** combining a TensorFlow/Keras CNN for 5-class skin lesion classification with Google Gemini 2.0 Flash for automated clinical recommendations.
- **Architected thread-safe MySQL per-request database connection pooling** via Flask application context (`flask.g`), eliminating race conditions and connection leaks under concurrent traffic.
- **Strengthened authentication security** by implementing bcrypt password hashing with automatic cryptographic upgrade migrations for existing accounts.
- **Built an interactive analytics dashboard** with Chart.js displaying real-time condition distributions and 12-month activity trends, alongside automated ReportLab PDF report generation and CSV exports.
- **Containerized the full-stack architecture** with Docker and Docker Compose for reproducible cross-platform deployments with automated database health checking.

---

## 📄 License
This project is licensed under the MIT License — see the LICENSE file for details.
