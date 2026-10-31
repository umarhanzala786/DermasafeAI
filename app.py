import os
import io
import logging
import hashlib
import hmac
from datetime import datetime

try:
    import bcrypt
    HAS_BCRYPT = True
except ImportError:
    bcrypt = None
    HAS_BCRYPT = False

import numpy as np
import mysql.connector
import tensorflow as tf

from flask import (
    Flask,
    request,
    render_template,
    jsonify,
    redirect,
    url_for,
    session,
    send_file,
    g
)

from werkzeug.utils import secure_filename

from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import (
    Input,
    Conv2D,
    MaxPooling2D,
    Flatten,
    Dense
)

from tensorflow.keras.preprocessing import image

from reportlab.lib.pagesizes import letter
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas

from dotenv import load_dotenv


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger("dermasafe")


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# FLASK APPLICATION
# ============================================================

app = Flask(__name__)

app.secret_key = os.getenv(
    "SECRET_KEY",
    "dermasafe_secure_secret_key"
)

app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024


# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

MODEL_PATH = os.path.join(
    BASE_DIR,
    "skindisease.h5"
)

UPLOAD_DIR = os.path.join(
    BASE_DIR,
    "uploads"
)

PROFILE_UPLOAD_DIR = os.path.join(
    BASE_DIR,
    "static",
    "uploads"
)

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PROFILE_UPLOAD_DIR, exist_ok=True)


# ============================================================
# AI MODEL CLASSES
# ============================================================

MODEL_CLASSES = [
    "Acne",
    "Melanoma",
    "Peeling skin",
    "Ring worm",
    "Vitiligo"
]


# ============================================================
# GEMINI AI CONFIGURATION
# ============================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

gemini_model = None

if GEMINI_API_KEY:

    try:

        import google.generativeai as genai

        genai.configure(api_key=GEMINI_API_KEY)

        gemini_model = genai.GenerativeModel(
            "gemini-2.0-flash"
        )

        logger.info("Gemini AI: CONFIGURED")

    except Exception as e:

        logger.warning(
            "Gemini AI: UNAVAILABLE (%s)", e
        )

        gemini_model = None

else:
    logger.info(
        "Gemini AI: No API key set (GEMINI_API_KEY in .env)"
    )


# ============================================================
# AI MODEL
# ============================================================

model = None


def load_dermasafe_model():

    """
    Loads the legacy Dermasafe AI H5 model.

    Original architecture:

        Input       : 64 x 64 x 3
        Conv2D      : 32 filters, 3x3 kernel, 3x3 stride
        MaxPooling  : 2x2
        Flatten
        Dense       : 500 ReLU
        Dense       : 5 Softmax

    The old model was created using an older Keras version,
    so we rebuild the architecture and load the saved weights.
    """

    try:

        if not os.path.exists(MODEL_PATH):

            raise FileNotFoundError(
                f"Model file not found: {MODEL_PATH}"
            )

        loaded_model = Sequential([

            Input(shape=(64, 64, 3)),

            Conv2D(
                filters=32,
                kernel_size=(3, 3),
                strides=(3, 3),
                padding="valid",
                activation="relu",
                name="conv2d"
            ),

            MaxPooling2D(
                pool_size=(2, 2),
                padding="valid",
                name="max_pooling2d"
            ),

            Flatten(name="flatten"),

            Dense(
                500,
                activation="relu",
                name="dense"
            ),

            Dense(
                5,
                activation="softmax",
                name="dense_1"
            )

        ])

        loaded_model.build(
            input_shape=(None, 64, 64, 3)
        )

        loaded_model.load_weights(MODEL_PATH)

        loaded_model.compile(
            optimizer="adam",
            loss="categorical_crossentropy",
            metrics=["accuracy"]
        )

        logger.info("AI Model: LOADED (%s)", MODEL_PATH)

        return loaded_model

    except Exception as e:

        logger.error("AI Model: FAILED (%s)", e)

        return None


# Load model once when server starts
model = load_dermasafe_model()


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "skin_disease_db"),
    "autocommit": False
}


def auto_migrate_schema():
    """
    Ensures backwards compatibility by adding any missing columns
    (e.g., last_login, confidence, ai_insights) without failing.
    """
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cur = conn.cursor()

        # 1. Expand password column for bcrypt (VARCHAR 255)
        try:
            cur.execute("ALTER TABLE users MODIFY COLUMN password VARCHAR(255) NOT NULL")
            conn.commit()
        except Exception:
            pass

        # 2. Add last_login to users
        try:
            cur.execute("ALTER TABLE users ADD COLUMN last_login DATETIME DEFAULT NULL")
            conn.commit()
        except Exception:
            pass

        # 3. Add profile_image to users
        try:
            cur.execute("ALTER TABLE users ADD COLUMN profile_image VARCHAR(500) DEFAULT NULL")
            conn.commit()
        except Exception:
            pass

        # 4. Add confidence to scan_records
        try:
            cur.execute("ALTER TABLE scan_records ADD COLUMN confidence FLOAT DEFAULT NULL")
            conn.commit()
        except Exception:
            pass

        # 5. Add ai_insights to scan_records
        try:
            cur.execute("ALTER TABLE scan_records ADD COLUMN ai_insights TEXT DEFAULT NULL")
            conn.commit()
        except Exception:
            pass

        cur.close()
        conn.close()
        logger.info("Database schema auto-migration check complete.")
    except Exception as e:
        logger.warning("Database schema check skipped: %s", e)


# Run auto-migration once on startup
auto_migrate_schema()


# ============================================================
# PER-REQUEST DATABASE CONNECTION (THREAD-SAFE)
# ============================================================

def get_db():

    """
    Returns a per-request MySQL connection stored in Flask's
    g object. This is the correct Flask pattern — each request
    gets its own connection, avoiding thread-safety issues.
    """

    if "db" not in g:

        try:

            g.db = mysql.connector.connect(**DB_CONFIG)
            g.cursor = g.db.cursor(dictionary=True)

        except Exception as e:

            logger.error("Database connection failed: %s", e)
            g.db = None
            g.cursor = None

    return g.db, g.cursor


@app.teardown_appcontext
def close_db(exception):

    """Close the database connection at the end of each request."""

    cursor = g.pop("cursor", None)
    db = g.pop("db", None)

    if cursor:
        try:
            cursor.close()
        except Exception:
            pass

    if db:
        try:
            db.close()
        except Exception:
            pass


# ============================================================
# PASSWORD HASHING (BCRYPT WITH BUILT-IN FALLBACK)
# ============================================================

def hash_password(plain_password):

    """
    Hash a plaintext password using bcrypt if installed,
    otherwise fallback to hashlib sha256 with salt.
    """

    if HAS_BCRYPT and bcrypt is not None:
        return bcrypt.hashpw(
            plain_password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")

    # Built-in fallback: SHA256 with secret salt
    salt = os.getenv("SECRET_KEY", "dermasafe_salt")
    return "sha256$" + hashlib.sha256(
        (plain_password + salt).encode("utf-8")
    ).hexdigest()


def verify_password(plain_password, stored_password):

    """
    Verify a password against stored value.
    Supports bcrypt, sha256 fallback, and legacy plaintext.
    """

    if not stored_password:
        return False

    # 1. Check bcrypt hash
    if is_password_hashed(stored_password):
        if HAS_BCRYPT and bcrypt is not None:
            try:
                return bcrypt.checkpw(
                    plain_password.encode("utf-8"),
                    stored_password.encode("utf-8")
                )
            except Exception:
                return False
        return False

    # 2. Check sha256 fallback hash
    if stored_password.startswith("sha256$"):
        salt = os.getenv("SECRET_KEY", "dermasafe_salt")
        expected = "sha256$" + hashlib.sha256(
            (plain_password + salt).encode("utf-8")
        ).hexdigest()
        return hmac.compare_digest(stored_password, expected)

    # 3. Legacy plaintext password
    return plain_password == stored_password


def is_password_hashed(password_value):

    """Check if a stored password is already bcrypt or sha256 hashed."""

    if not password_value:
        return False

    return (
        password_value.startswith("$2b$")
        or password_value.startswith("$2a$")
        or password_value.startswith("sha256$")
    )


# ============================================================
# GEMINI AI INSIGHTS GENERATOR
# ============================================================

def generate_ai_insights(diagnosis, confidence, symptoms, age, gender):

    """
    Calls Google Gemini to generate detailed clinical insights
    about the predicted skin condition.
    """

    if gemini_model is None:
        return None

    try:

        prompt = f"""You are a medical AI assistant integrated into a skin disease screening platform called DermasafeAI.

A CNN model has classified a skin lesion image with the following results:

- Predicted Condition: {diagnosis}
- Confidence: {confidence:.1f}%
- Patient Age: {age}
- Patient Gender: {gender}
- Reported Symptoms: {symptoms}

Please provide a concise, helpful response with these sections (use clear headings with markdown ##):

## About {diagnosis}
A brief 2-3 sentence overview of this skin condition.

## Common Causes
List 3-4 common causes or triggers.

## Recommended Care
Provide 3-4 practical treatment suggestions or home remedies.

## When to See a Doctor
List 2-3 warning signs that need immediate professional attention.

## Precautions
2-3 skincare precautions specific to this condition.

IMPORTANT: End with a clear disclaimer that this is AI-generated screening support and NOT a medical diagnosis. Keep the total response under 350 words. Do NOT use asterisks for bold — use plain text."""

        response = gemini_model.generate_content(prompt)

        if response and response.text:
            return response.text.strip()

        return None

    except Exception as e:

        logger.warning("Gemini insights error: %s", e)
        return None


# ============================================================
# GLOBAL TEMPLATE VARIABLES
# ============================================================

@app.context_processor
def inject_global_variables():

    current_name = session.get("name", "User")
    logged_in = ("user" in session)

    return {
        "current_name": current_name,
        "logged_in": logged_in,
        "model_status": (
            "Available" if model is not None
            else "Unavailable"
        ),
        "gemini_status": (
            "Available" if gemini_model is not None
            else "Unavailable"
        ),
        "year": datetime.now().year
    }


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    return render_template("home.html")


# ============================================================
# HOW IT WORKS
# ============================================================

@app.route("/how-it-works")
def how_it_works():

    return render_template("how_it_works.html")


# ============================================================
# ABOUT
# ============================================================

@app.route("/about")
def about():

    return render_template("about.html")


# ============================================================
# LOGIN
# ============================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        email = (
            request.form
            .get("email", "")
            .strip()
            .lower()
        )

        password = (
            request.form
            .get("password", "")
        )

        if not email or not password:

            return render_template(
                "login.html",
                error="Please enter email and password."
            )

        try:

            db, cursor = get_db()

            if db is None:

                return render_template(
                    "login.html",
                    error="Database connection failed."
                )

            cursor.execute(
                """
                SELECT *
                FROM users
                WHERE email = %s
                LIMIT 1
                """,
                (email,)
            )

            user = cursor.fetchone()

            if user and verify_password(
                password,
                user["password"]
            ):

                # Safely auto-upgrade plaintext passwords to bcrypt if possible
                try:
                    if not is_password_hashed(user["password"]):
                        cursor.execute(
                            """
                            UPDATE users
                            SET password = %s
                            WHERE email = %s
                            """,
                            (
                                hash_password(password),
                                email
                            )
                        )
                        db.commit()
                        logger.info(
                            "Password upgraded to bcrypt for: %s",
                            email
                        )
                except Exception as up_err:
                    logger.warning("Could not auto-upgrade password: %s", up_err)

                # Safely update last login if column exists
                try:
                    cursor.execute(
                        """
                        UPDATE users
                        SET last_login = NOW()
                        WHERE email = %s
                        """,
                        (email,)
                    )
                    db.commit()
                except Exception as log_err:
                    logger.debug("Could not update last_login: %s", log_err)

                session["user"] = user["email"]
                session["name"] = user["username"]
                session.permanent = True

                return redirect(url_for("dashboard"))

            return render_template(
                "login.html",
                error="Invalid Email or Password!"
            )

        except Exception as e:

            logger.error("Login error: %s", e)

            return render_template(
                "login.html",
                error="Unable to login. Please try again."
            )

    return render_template("login.html")


# ============================================================
# SIGNUP
# ============================================================

@app.route(
    "/signup",
    methods=["GET", "POST"]
)
def signup():

    if request.method == "POST":

        name = (
            request.form
            .get("username", "")
            .strip()
        )

        email = (
            request.form
            .get("email", "")
            .strip()
            .lower()
        )

        password = (
            request.form
            .get("password", "")
        )

        if not name or not email or not password:

            return render_template(
                "signup.html",
                error="All fields are required."
            )

        if len(password) < 8:

            return render_template(
                "signup.html",
                error="Password must be at least 8 characters."
            )

        try:

            db, cursor = get_db()

            if db is None:

                return render_template(
                    "signup.html",
                    error="Database connection failed."
                )

            cursor.execute(
                """
                SELECT id
                FROM users
                WHERE email = %s
                LIMIT 1
                """,
                (email,)
            )

            existing_user = cursor.fetchone()

            if existing_user:

                return render_template(
                    "signup.html",
                    error="Email already registered!"
                )

            # Hash the password with bcrypt
            hashed = hash_password(password)

            cursor.execute(
                """
                INSERT INTO users
                (username, email, password)
                VALUES (%s, %s, %s)
                """,
                (name, email, hashed)
            )

            db.commit()

            logger.info("New user registered: %s", email)

            return redirect(
                url_for("login", created=1)
            )

        except Exception as e:

            try:
                db.rollback()
            except Exception:
                pass

            logger.error("Signup error: %s", e)

            return render_template(
                "signup.html",
                error="Unable to create account."
            )

    return render_template("signup.html")


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/dashboard")
def dashboard():

    if "user" not in session:
        return redirect(url_for("login"))

    try:

        db, cursor = get_db()

        if db is None:

            return render_template(
                "dashboard.html",
                records=[],
                total_scans=0,
                recent_scans=0
            )

        user_email = session["user"]

        # Scan history
        cursor.execute(
            """
            SELECT *
            FROM scan_records
            WHERE user_email = %s
            ORDER BY created_at DESC
            """,
            (user_email,)
        )

        records = cursor.fetchall()

        # Total scans
        cursor.execute(
            """
            SELECT COUNT(*) AS total_scans
            FROM scan_records
            WHERE user_email = %s
            """,
            (user_email,)
        )

        result = cursor.fetchone()

        total_scans = (
            int(result["total_scans"])
            if result else 0
        )

        # Recent 30 days
        cursor.execute(
            """
            SELECT COUNT(*) AS recent_scans
            FROM scan_records
            WHERE user_email = %s
              AND created_at >=
                  NOW() - INTERVAL 30 DAY
            """,
            (user_email,)
        )

        result = cursor.fetchone()

        recent_scans = (
            int(result["recent_scans"])
            if result else 0
        )

        # Average confidence (safely handle if column missing)
        avg_confidence = 0
        try:
            cursor.execute(
                """
                SELECT AVG(confidence) AS avg_conf
                FROM scan_records
                WHERE user_email = %s
                  AND confidence IS NOT NULL
                """,
                (user_email,)
            )
            result = cursor.fetchone()
            if result and result["avg_conf"] is not None:
                avg_confidence = round(float(result["avg_conf"]), 1)
        except Exception:
            avg_confidence = 0

        return render_template(
            "dashboard.html",
            records=records,
            total_scans=total_scans,
            recent_scans=recent_scans,
            avg_confidence=avg_confidence
        )

    except Exception as e:

        logger.error("Dashboard error: %s", e)

        return render_template(
            "dashboard.html",
            records=[],
            total_scans=0,
            recent_scans=0,
            avg_confidence=0
        )


# ============================================================
# PROFILE
# ============================================================

@app.route(
    "/profile",
    methods=["GET", "POST"]
)
def profile():

    if "user" not in session:
        return redirect(url_for("login"))

    try:

        db, cursor = get_db()

        if db is None:

            return render_template(
                "profile.html",
                user=None,
                total_scans=0,
                name=session.get("name", "User")
            )

        user_email = session["user"]

        # Profile image upload
        if request.method == "POST":

            profile_file = request.files.get(
                "profile_image"
            )

            if profile_file and profile_file.filename:

                original_filename = secure_filename(
                    profile_file.filename
                )

                if original_filename:

                    timestamp = datetime.now().strftime(
                        "%Y%m%d_%H%M%S_%f"
                    )

                    filename = (
                        f"{timestamp}_{original_filename}"
                    )

                    filepath = os.path.join(
                        PROFILE_UPLOAD_DIR,
                        filename
                    )

                    profile_file.save(filepath)

                    relative_path = (
                        f"uploads/{filename}"
                    )

                    cursor.execute(
                        """
                        UPDATE users
                        SET profile_image = %s
                        WHERE email = %s
                        """,
                        (relative_path, user_email)
                    )

                    db.commit()

        # Get user
        cursor.execute(
            """
            SELECT *
            FROM users
            WHERE email = %s
            LIMIT 1
            """,
            (user_email,)
        )

        user_info = cursor.fetchone()

        # Scan count
        cursor.execute(
            """
            SELECT COUNT(*) AS total_scans
            FROM scan_records
            WHERE user_email = %s
            """,
            (user_email,)
        )

        result = cursor.fetchone()

        scan_count = (
            int(result["total_scans"])
            if result else 0
        )

        return render_template(
            "profile.html",
            user=user_info,
            total_scans=scan_count,
            name=session.get("name", "User")
        )

    except Exception as e:

        logger.error("Profile error: %s", e)

        return render_template(
            "profile.html",
            user=None,
            total_scans=0,
            name=session.get("name", "User")
        )


# ============================================================
# PREDICT SCAN
# ============================================================

@app.route(
    "/predict_scan",
    methods=["POST"]
)
def predict_scan():

    # --------------------------------------------------------
    # Authentication
    # --------------------------------------------------------

    if "user" not in session:

        return jsonify({
            "success": False,
            "error": "Unauthorized. Please login again."
        }), 401

    # --------------------------------------------------------
    # Database
    # --------------------------------------------------------

    db, cursor = get_db()

    if db is None:

        return jsonify({
            "success": False,
            "error": "Database connection failed."
        }), 500

    # --------------------------------------------------------
    # Model
    # --------------------------------------------------------

    if model is None:

        return jsonify({
            "success": False,
            "error": "AI model is currently unavailable."
        }), 503

    # --------------------------------------------------------
    # Form data
    # --------------------------------------------------------

    patient_name = (
        request.form
        .get("patient_name", "")
        .strip()
    )

    age = (
        request.form
        .get("age", "")
        .strip()
    )

    gender = (
        request.form
        .get("gender", "")
        .strip()
    )

    symptoms = (
        request.form
        .get("symptoms", "")
        .strip()
    )

    uploaded_file = request.files.get("image")

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    if not patient_name:
        return jsonify({
            "success": False,
            "error": "Patient name is required."
        }), 400

    if not age:
        return jsonify({
            "success": False,
            "error": "Patient age is required."
        }), 400

    try:
        age_value = int(age)
    except ValueError:
        return jsonify({
            "success": False,
            "error": "Age must be a valid number."
        }), 400

    if age_value < 1 or age_value > 120:
        return jsonify({
            "success": False,
            "error": "Age must be between 1 and 120."
        }), 400

    if not gender:
        return jsonify({
            "success": False,
            "error": "Gender is required."
        }), 400

    if not symptoms:
        return jsonify({
            "success": False,
            "error": "Symptoms or observations are required."
        }), 400

    if uploaded_file is None or not uploaded_file.filename:
        return jsonify({
            "success": False,
            "error": "Please upload a skin image."
        }), 400

    # --------------------------------------------------------
    # File validation
    # --------------------------------------------------------

    original_filename = secure_filename(
        uploaded_file.filename
    )

    if not original_filename:
        return jsonify({
            "success": False,
            "error": "Invalid image filename."
        }), 400

    allowed_extensions = {
        ".jpg", ".jpeg", ".png", ".webp"
    }

    extension = os.path.splitext(
        original_filename
    )[1].lower()

    if extension not in allowed_extensions:
        return jsonify({
            "success": False,
            "error": "Only JPG, JPEG, PNG and WEBP images are supported."
        }), 400


    # ========================================================
    # DUPLICATE REQUEST PROTECTION
    # ========================================================

    user_email = session["user"]

    try:

        cursor.execute(
            """
            SELECT id, status, created_at
            FROM scan_records
            WHERE user_email = %s
              AND patient_name = %s
              AND age = %s
              AND gender = %s
              AND symptoms = %s
              AND created_at >=
                  NOW() - INTERVAL 10 SECOND
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (
                user_email,
                patient_name,
                age_value,
                gender,
                symptoms
            )
        )

        existing_scan = cursor.fetchone()

        if existing_scan:

            existing_status = existing_scan.get(
                "status", "Already processed"
            )

            diagnosis = (
                str(existing_status).split(" (")[0]
            )

            confidence = None

            try:
                confidence_text = (
                    str(existing_status)
                    .split("(")[1]
                    .split("%")[0]
                )
                confidence = float(confidence_text)
            except Exception:
                confidence = None

            return jsonify({
                "success": True,
                "duplicate": True,
                "scan_id": existing_scan["id"],
                "result": existing_status,
                "diagnosis": diagnosis,
                "confidence": confidence,
                "message": "This screening request was already processed."
            })

    except Exception as e:

        logger.warning("Duplicate check error: %s", e)


    # ========================================================
    # SAVE IMAGE
    # ========================================================

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    filename = f"{timestamp}_{original_filename}"

    filepath = os.path.join(UPLOAD_DIR, filename)

    try:

        uploaded_file.save(filepath)

    except Exception as e:

        logger.error("Image save error: %s", e)

        return jsonify({
            "success": False,
            "error": "Unable to save uploaded image."
        }), 500


    # ========================================================
    # AI PREDICTION
    # ========================================================

    try:

        img = image.load_img(
            filepath,
            target_size=(64, 64)
        )

        x = image.img_to_array(img)
        x = np.expand_dims(x, axis=0)

        if x.shape != (1, 64, 64, 3):
            raise ValueError(
                f"Unexpected image shape: {x.shape}"
            )

        preds = model.predict(x, verbose=0)

        if (
            len(preds.shape) != 2
            or preds.shape[1] != 5
        ):
            raise ValueError(
                f"Unexpected model output shape: {preds.shape}"
            )

        label_index = int(
            np.argmax(preds, axis=1)[0]
        )

        confidence = float(np.max(preds)) * 100

        if (
            label_index < 0
            or label_index >= len(MODEL_CLASSES)
        ):
            raise ValueError(
                "Invalid predicted class index."
            )

        diagnosis = MODEL_CLASSES[label_index]

        diagnosis_result = (
            f"{diagnosis} "
            f"({confidence:.1f}% Match)"
        )

        # Build class probabilities
        class_probabilities = {}
        for i, cls in enumerate(MODEL_CLASSES):
            class_probabilities[cls] = round(
                float(preds[0][i]) * 100, 1
            )

    except Exception as e:

        logger.error("Prediction error: %s", e)

        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception:
            pass

        return jsonify({
            "success": False,
            "error": "AI model could not process this image.",
            "details": str(e)
        }), 503


    # ========================================================
    # GEMINI AI INSIGHTS
    # ========================================================

    ai_insights = generate_ai_insights(
        diagnosis=diagnosis,
        confidence=confidence,
        symptoms=symptoms,
        age=age_value,
        gender=gender
    )


    # ========================================================
    # SAVE SCAN RECORD
    # ========================================================

    try:

        cursor.execute(
            """
            INSERT INTO scan_records
            (
                user_email,
                patient_name,
                age,
                gender,
                symptoms,
                image_path,
                status,
                confidence,
                ai_insights
            )
            VALUES
            (
                %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            """,
            (
                user_email,
                patient_name,
                age_value,
                gender,
                symptoms,
                filepath,
                diagnosis_result,
                round(confidence, 1),
                ai_insights
            )
        )

        db.commit()
        scan_id = cursor.lastrowid

    except Exception as e:

        # Fallback to legacy schema if confidence/ai_insights columns missing
        try:
            cursor.execute(
                """
                INSERT INTO scan_records
                (
                    user_email,
                    patient_name,
                    age,
                    gender,
                    symptoms,
                    image_path,
                    status
                )
                VALUES
                (
                    %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    user_email,
                    patient_name,
                    age_value,
                    gender,
                    symptoms,
                    filepath,
                    diagnosis_result
                )
            )
            db.commit()
            scan_id = cursor.lastrowid
        except Exception as fallback_err:
            try:
                db.rollback()
            except Exception:
                pass

            logger.error("Database insert error: %s", fallback_err)

            return jsonify({
                "success": False,
                "error": "Prediction completed, but the record could not be saved.",
                "details": str(fallback_err)
            }), 500


    # ========================================================
    # SUCCESS RESPONSE
    # ========================================================

    return jsonify({
        "success": True,
        "duplicate": False,
        "scan_id": scan_id,
        "result": diagnosis_result,
        "diagnosis": diagnosis,
        "confidence": round(confidence, 1),
        "probabilities": class_probabilities,
        "ai_insights": ai_insights
    })


# ============================================================
# SCAN DETAIL PAGE
# ============================================================

@app.route("/scan/<int:scan_id>")
def scan_detail(scan_id):

    if "user" not in session:
        return redirect(url_for("login"))

    try:

        db, cursor = get_db()

        if db is None:
            return render_template(
                "404.html"
            ), 404

        cursor.execute(
            """
            SELECT *
            FROM scan_records
            WHERE id = %s
              AND user_email = %s
            LIMIT 1
            """,
            (scan_id, session["user"])
        )

        record = cursor.fetchone()

        if not record:
            return render_template(
                "404.html"
            ), 404

        # Parse class probabilities from status
        # (for records without stored probabilities)
        diagnosis = str(
            record["status"]
        ).split(" (")[0]

        conf = record.get("confidence", 0)

        return render_template(
            "scan_detail.html",
            record=record,
            diagnosis=diagnosis,
            confidence=conf
        )

    except Exception as e:

        logger.error(
            "Scan detail error: %s", e
        )

        return render_template(
            "404.html"
        ), 404


# ============================================================
# DASHBOARD STATISTICS API
# ============================================================

@app.route("/api/stats")
def api_stats():

    if "user" not in session:
        return jsonify({
            "success": False,
            "error": "Unauthorized"
        }), 401

    try:

        db, cursor = get_db()

        if db is None:
            return jsonify({
                "success": False,
                "error": "Database connection failed.",
                "distribution": []
            }), 500

        cursor.execute(
            """
            SELECT
                status,
                COUNT(*) AS count
            FROM scan_records
            WHERE user_email = %s
            GROUP BY status
            ORDER BY count DESC
            """,
            (session["user"],)
        )

        rows = cursor.fetchall()

        distribution = []

        for row in rows:
            distribution.append({
                "status": row["status"],
                "count": int(row["count"])
            })

        total = sum(
            item["count"]
            for item in distribution
        )

        return jsonify({
            "success": True,
            "total": total,
            "distribution": distribution
        })

    except Exception as e:

        logger.error("Stats error: %s", e)

        return jsonify({
            "success": False,
            "error": "Unable to load statistics.",
            "distribution": []
        }), 500


# ============================================================
# MONTHLY TRENDS API
# ============================================================

@app.route("/api/trends")
def api_trends():

    if "user" not in session:
        return jsonify({
            "success": False,
            "error": "Unauthorized"
        }), 401

    try:

        db, cursor = get_db()

        if db is None:
            return jsonify({
                "success": False,
                "trends": []
            }), 500

        cursor.execute(
            """
            SELECT
                DATE_FORMAT(created_at, '%%Y-%%m') AS month,
                COUNT(*) AS count
            FROM scan_records
            WHERE user_email = %s
              AND created_at >=
                  DATE_SUB(NOW(), INTERVAL 12 MONTH)
            GROUP BY month
            ORDER BY month ASC
            """,
            (session["user"],)
        )

        rows = cursor.fetchall()

        trends = []

        for row in rows:
            trends.append({
                "month": row["month"],
                "count": int(row["count"])
            })

        return jsonify({
            "success": True,
            "trends": trends
        })

    except Exception as e:

        logger.error("Trends error: %s", e)

        return jsonify({
            "success": False,
            "trends": []
        }), 500


# ============================================================
# DOWNLOAD PDF REPORT
# ============================================================

@app.route(
    "/download_report/<int:scan_id>"
)
def download_report(scan_id):

    if "user" not in session:
        return redirect(url_for("login"))

    try:

        db, cursor = get_db()

        if db is None:
            return ("Database connection failed.", 500)

        cursor.execute(
            """
            SELECT *
            FROM scan_records
            WHERE id = %s
              AND user_email = %s
            LIMIT 1
            """,
            (scan_id, session["user"])
        )

        record = cursor.fetchone()

        if not record:
            return ("Record not found", 404)

        # ----------------------------------------------------
        # PDF Generation (Enhanced)
        # ----------------------------------------------------

        buffer = io.BytesIO()

        pdf = canvas.Canvas(
            buffer, pagesize=letter
        )

        width, height = letter

        # Colors
        primary = HexColor("#0f766e")
        dark = HexColor("#0f172a")
        muted = HexColor("#64748b")

        # Header bar
        pdf.setFillColor(primary)
        pdf.rect(0, height - 80, width, 80, fill=True, stroke=False)

        pdf.setFillColor(HexColor("#ffffff"))
        pdf.setFont("Helvetica-Bold", 22)
        pdf.drawString(50, height - 50, "Dermasafe AI")

        pdf.setFont("Helvetica", 11)
        pdf.drawString(
            50, height - 68,
            "AI-Assisted Skin Screening Report"
        )

        # Report ID
        pdf.drawRightString(
            width - 50, height - 50,
            f"Report #{scan_id}"
        )

        pdf.drawRightString(
            width - 50, height - 68,
            f"Generated: {datetime.now().strftime('%d %b %Y, %H:%M')}"
        )

        # Patient information
        y = height - 120

        pdf.setFillColor(dark)
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(50, y, "Patient Information")

        y -= 8
        pdf.setStrokeColor(HexColor("#e2e8f0"))
        pdf.line(50, y, width - 50, y)

        y -= 25
        pdf.setFont("Helvetica", 11)
        pdf.setFillColor(muted)
        pdf.drawString(50, y, "Patient Name")
        pdf.setFillColor(dark)
        pdf.drawString(200, y, str(record["patient_name"]))

        y -= 22
        pdf.setFillColor(muted)
        pdf.drawString(50, y, "Age")
        pdf.setFillColor(dark)
        pdf.drawString(200, y, str(record["age"]))

        y -= 22
        pdf.setFillColor(muted)
        pdf.drawString(50, y, "Gender")
        pdf.setFillColor(dark)
        pdf.drawString(200, y, str(record["gender"]))

        y -= 22
        pdf.setFillColor(muted)
        pdf.drawString(50, y, "Screening Date")
        pdf.setFillColor(dark)
        pdf.drawString(200, y, str(record["created_at"]))

        # Symptoms
        y -= 45

        pdf.setFillColor(dark)
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(50, y, "Symptoms / Observations")

        y -= 8
        pdf.line(50, y, width - 50, y)

        y -= 22
        pdf.setFont("Helvetica", 11)
        pdf.setFillColor(dark)

        symptoms_text = str(record["symptoms"])
        symptom_lines = [
            symptoms_text[i:i + 80]
            for i in range(0, len(symptoms_text), 80)
        ]

        for line in symptom_lines[:5]:
            pdf.drawString(50, y, line)
            y -= 17

        # AI Result
        y -= 30

        pdf.setFillColor(dark)
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(50, y, "AI Screening Result")

        y -= 8
        pdf.line(50, y, width - 50, y)

        y -= 30

        # Result box
        pdf.setFillColor(HexColor("#ecfdf5"))
        pdf.roundRect(
            50, y - 15, width - 100, 40,
            8, fill=True, stroke=False
        )

        pdf.setFillColor(primary)
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(65, y, str(record["status"]))

        # AI Insights (if available)
        if record.get("ai_insights"):

            y -= 55

            pdf.setFillColor(dark)
            pdf.setFont("Helvetica-Bold", 14)
            pdf.drawString(50, y, "AI-Generated Insights")

            y -= 8
            pdf.line(50, y, width - 50, y)

            y -= 20
            pdf.setFont("Helvetica", 9)
            pdf.setFillColor(muted)

            insights_text = str(record["ai_insights"])
            # Simple line wrapping
            for line in insights_text.split("\n"):
                wrapped = [
                    line[i:i + 95]
                    for i in range(0, max(len(line), 1), 95)
                ]
                for wl in wrapped:
                    if y < 80:
                        pdf.showPage()
                        y = height - 60
                    pdf.drawString(50, y, wl.strip())
                    y -= 13

        # Disclaimer
        y -= 30

        if y < 100:
            pdf.showPage()
            y = height - 60

        pdf.setFont("Helvetica-Oblique", 9)
        pdf.setFillColor(muted)

        disclaimer = (
            "This report is generated by an AI-assisted "
            "screening system and is not a medical diagnosis. "
            "Please consult a qualified dermatologist or "
            "healthcare professional for clinical evaluation."
        )

        disclaimer_lines = [
            disclaimer[i:i + 90]
            for i in range(0, len(disclaimer), 90)
        ]

        for line in disclaimer_lines:
            pdf.drawString(50, y, line)
            y -= 14

        # Footer
        pdf.setFont("Helvetica", 8)
        pdf.setFillColor(muted)
        pdf.drawString(
            50, 35,
            "Dermasafe AI - Preliminary AI Screening Report"
        )
        pdf.drawRightString(
            width - 50, 35,
            f"Confidential - Report #{scan_id}"
        )

        pdf.showPage()
        pdf.save()

        buffer.seek(0)

        safe_patient_name = secure_filename(
            str(record["patient_name"])
        )

        if not safe_patient_name:
            safe_patient_name = "Patient"

        return send_file(
            buffer,
            as_attachment=True,
            download_name=(
                f"DermasafeAI_Report_{safe_patient_name}_{scan_id}.pdf"
            ),
            mimetype="application/pdf"
        )

    except Exception as e:

        logger.error("PDF generation error: %s", e)

        return (
            "Unable to generate report.",
            500
        )


# ============================================================
# EXPORT HISTORY (CSV)
# ============================================================

@app.route("/export/csv")
def export_csv():

    if "user" not in session:
        return redirect(url_for("login"))

    try:

        db, cursor = get_db()

        if db is None:
            return ("Database connection failed.", 500)

        cursor.execute(
            """
            SELECT
                id,
                patient_name,
                age,
                gender,
                symptoms,
                status,
                confidence,
                created_at
            FROM scan_records
            WHERE user_email = %s
            ORDER BY created_at DESC
            """,
            (session["user"],)
        )

        rows = cursor.fetchall()

        # Build CSV
        lines = [
            "ID,Patient Name,Age,Gender,Symptoms,Result,Confidence,Date"
        ]

        for row in rows:

            line = ",".join([
                str(row["id"]),
                f'"{row["patient_name"]}"',
                str(row["age"]),
                row["gender"],
                f'"{row["symptoms"]}"',
                f'"{row["status"]}"',
                str(row.get("confidence", "")),
                str(row["created_at"])
            ])

            lines.append(line)

        csv_content = "\n".join(lines)
        buffer = io.BytesIO(
            csv_content.encode("utf-8")
        )

        return send_file(
            buffer,
            as_attachment=True,
            download_name=(
                f"DermasafeAI_History_{datetime.now().strftime('%Y%m%d')}.csv"
            ),
            mimetype="text/csv"
        )

    except Exception as e:

        logger.error("CSV export error: %s", e)
        return ("Unable to export.", 500)


# ============================================================
# DELETE SCAN RECORD
# ============================================================

@app.route(
    "/scan/<int:scan_id>/delete",
    methods=["POST"]
)
def delete_scan(scan_id):

    if "user" not in session:
        return jsonify({
            "success": False,
            "error": "Unauthorized"
        }), 401

    try:

        db, cursor = get_db()

        if db is None:
            return jsonify({
                "success": False,
                "error": "Database error"
            }), 500

        # Verify ownership
        cursor.execute(
            """
            SELECT id, image_path
            FROM scan_records
            WHERE id = %s
              AND user_email = %s
            LIMIT 1
            """,
            (scan_id, session["user"])
        )

        record = cursor.fetchone()

        if not record:
            return jsonify({
                "success": False,
                "error": "Record not found"
            }), 404

        # Delete from database
        cursor.execute(
            """
            DELETE FROM scan_records
            WHERE id = %s
              AND user_email = %s
            """,
            (scan_id, session["user"])
        )

        db.commit()

        # Try to delete the image file
        try:
            img_path = record.get("image_path", "")
            if img_path and os.path.exists(img_path):
                os.remove(img_path)
        except Exception:
            pass

        logger.info(
            "Scan %s deleted by %s",
            scan_id,
            session["user"]
        )

        return jsonify({
            "success": True
        })

    except Exception as e:

        logger.error("Delete scan error: %s", e)

        return jsonify({
            "success": False,
            "error": "Unable to delete."
        }), 500


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()
    return redirect(url_for("login"))


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def page_not_found(error):

    return render_template("404.html"), 404


@app.errorhandler(500)
def internal_error(error):

    return render_template("500.html"), 500


@app.errorhandler(413)
def file_too_large(error):

    if request.path == "/predict_scan":

        return jsonify({
            "success": False,
            "error": "Image is too large. Maximum size is 8 MB."
        }), 413

    return ("File too large.", 413)


# ============================================================
# START SERVER
# ============================================================

if __name__ == "__main__":

    print()
    print("==========================================")
    print("       DERMASAFE AI")
    print("   Healthcare AI Screening Platform")
    print("==========================================")
    print(f"  Database : {DB_CONFIG['database']}")
    print(f"  AI Model : {'Ready' if model else 'Unavailable'}")
    print(f"  Gemini   : {'Ready' if gemini_model else 'Not configured'}")
    print(f"  Security : {'bcrypt' if HAS_BCRYPT else 'sha256 fallback'} password hashing")
    print("==========================================")
    print()

    app.run(
        debug=True,
        threaded=True
    )
