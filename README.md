# Dermasafe AI — Full-Stack Skin Disease Screening Platform

Dermasafe AI wraps a TensorFlow/Keras CNN image-classification model in a full-stack Flask application with authentication, MySQL persistence, scan history, dashboard analytics, image validation and PDF report generation.

## Current model scope
The supplied project documentation describes a five-class CNN model: Acne, Melanoma, Peeling skin, Ring worm and Vitiligo. It reports approximately 70% classification accuracy on a 500-image dataset. Treat all output as preliminary screening support, not a medical diagnosis.

## Stack
- Frontend: HTML/Jinja, CSS, vanilla JavaScript, Chart.js
- Backend: Flask
- Database: MySQL
- ML: TensorFlow / Keras CNN (`skindisease.h5`)
- Reports: ReportLab

## Setup
1. Create a Python virtual environment.
2. Install dependencies: `pip install -r requirements.txt`
3. Create the MySQL database/tables by running `schema.sql`.
4. Copy `.env.example` to `.env` and set your MySQL credentials.
5. Keep `skindisease.h5` in the project root.
6. Start: `python app.py`
7. Open `http://127.0.0.1:5000`

## Important changes from the original version
- Centralized shared layout with responsive navigation.
- Professional landing page and application dashboard.
- Dashboard statistics and disease-distribution chart.
- Live image preview and upload validation.
- Prediction response includes class probabilities.
- Removed random fallback predictions; model failures now return an explicit error.
- Unique upload filenames to prevent collisions.
- Passwords are hashed for new accounts; legacy plaintext passwords are upgraded after a successful login.
- Per-request MySQL connections instead of one global cursor/connection.
- Improved PDF report layout and authorization checks.
- `.env` support so database secrets are not hard-coded.
