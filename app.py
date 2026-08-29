import os
import io
from datetime import datetime

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
    send_file
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
from reportlab.pdfgen import canvas

from dotenv import load_dotenv


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

os.makedirs(
    UPLOAD_DIR,
    exist_ok=True
)

os.makedirs(
    PROFILE_UPLOAD_DIR,
    exist_ok=True
)


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

        # ----------------------------------------------------
        # Check model file
        # ----------------------------------------------------

        if not os.path.exists(MODEL_PATH):

            raise FileNotFoundError(
                f"Model file not found: {MODEL_PATH}"
            )


        # ----------------------------------------------------
        # Rebuild original architecture
        # ----------------------------------------------------

        loaded_model = Sequential([

            Input(
                shape=(64, 64, 3)
            ),

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

            Flatten(
                name="flatten"
            ),

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


        # ----------------------------------------------------
        # Build model
        # ----------------------------------------------------

        loaded_model.build(
            input_shape=(
                None,
                64,
                64,
                3
            )
        )


        # ----------------------------------------------------
        # Load trained weights
        # ----------------------------------------------------

        loaded_model.load_weights(
            MODEL_PATH
        )


        # ----------------------------------------------------
        # Compile
        # ----------------------------------------------------

        loaded_model.compile(
            optimizer="adam",
            loss="categorical_crossentropy",
            metrics=["accuracy"]
        )


        print("------------------------------------------")
        print("AI MODEL STATUS: LOADED")
        print(f"Model: {MODEL_PATH}")
        print(
            f"Input shape: {loaded_model.input_shape}"
        )
        print(
            f"Output shape: {loaded_model.output_shape}"
        )
        print("------------------------------------------")


        return loaded_model


    except Exception as e:

        print("------------------------------------------")
        print("AI MODEL STATUS: FAILED")
        print(f"Model: {MODEL_PATH}")
        print(f"Error: {e}")
        print("------------------------------------------")

        return None


# Load model once when server starts
model = load_dermasafe_model()


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

DB_HOST = os.getenv(
    "DB_HOST",
    "localhost"
)

DB_USER = os.getenv(
    "DB_USER",
    "root"
)

DB_PASSWORD = os.getenv(
    "DB_PASSWORD",
    ""
)

DB_NAME = os.getenv(
    "DB_NAME",
    "skin_disease_db"
)


# ============================================================
# DATABASE CONNECTION
# ============================================================

db = None
cursor = None


def connect_database():

    global db
    global cursor

    try:

        db = mysql.connector.connect(

            host=DB_HOST,

            user=DB_USER,

            password=DB_PASSWORD,

            database=DB_NAME,

            autocommit=False

        )

        cursor = db.cursor(
            dictionary=True
        )

        print("------------------------------------------")
        print("DATABASE STATUS: CONNECTED")
        print(f"Database: {DB_NAME}")
        print("------------------------------------------")

        return True


    except Exception as e:

        db = None
        cursor = None

        print("------------------------------------------")
        print("DATABASE STATUS: FAILED")
        print(f"Error: {e}")
        print("------------------------------------------")

        return False


connect_database()


# ============================================================
# ENSURE DATABASE CONNECTION
# ============================================================

def ensure_db_connection():

    global db
    global cursor

    try:

        if db is None:

            return connect_database()


        if not db.is_connected():

            db.reconnect(
                attempts=3,
                delay=1
            )

            cursor = db.cursor(
                dictionary=True
            )


        return True


    except Exception as e:

        print(
            "Database reconnect error:",
            e
        )

        return connect_database()


# ============================================================
# GLOBAL TEMPLATE VARIABLES
# ============================================================

@app.context_processor
def inject_global_variables():

    current_name = session.get(
        "name",
        "User"
    )

    logged_in = (
        "user" in session
    )

    return {

        "current_name":
            current_name,

        "logged_in":
            logged_in,

        "model_status":
            (
                "Available"
                if model is not None
                else "Unavailable"
            ),

        "year":
            datetime.now().year

    }


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    return render_template(
        "home.html"
    )


# ============================================================
# HOW IT WORKS
# ============================================================

@app.route("/how-it-works")
def how_it_works():

    return render_template(
        "how_it_works.html"
    )


# ============================================================
# ABOUT
# ============================================================

@app.route("/about")
def about():

    return render_template(
        "about.html"
    )


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

            if not ensure_db_connection():

                return render_template(
                    "login.html",
                    error="Database connection failed."
                )


            cursor.execute(
                """
                SELECT *
                FROM users
                WHERE email = %s
                  AND password = %s
                LIMIT 1
                """,
                (
                    email,
                    password
                )
            )

            user = cursor.fetchone()


            if user:

                # IMPORTANT:
                # Do not clear session here.
                # Set authenticated session values.

                session["user"] = user["email"]

                session["name"] = user["username"]

                session.permanent = True

                return redirect(
                    url_for("dashboard")
                )


            return render_template(
                "login.html",
                error="Invalid Email or Password!"
            )


        except Exception as e:

            print(
                "Login error:",
                e
            )

            return render_template(
                "login.html",
                error="Unable to login. Please try again."
            )


    return render_template(
        "login.html"
    )


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


        try:

            if not ensure_db_connection():

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


            cursor.execute(
                """
                INSERT INTO users
                (
                    username,
                    email,
                    password
                )
                VALUES
                (
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    name,
                    email,
                    password
                )
            )

            db.commit()


            return redirect(
                url_for(
                    "login",
                    created=1
                )
            )


        except Exception as e:

            try:
                db.rollback()
            except Exception:
                pass


            print(
                "Signup error:",
                e
            )


            return render_template(
                "signup.html",
                error="Unable to create account."
            )


    return render_template(
        "signup.html"
    )


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/dashboard")
def dashboard():

    if "user" not in session:

        return redirect(
            url_for("login")
        )


    try:

        if not ensure_db_connection():

            return render_template(
                "dashboard.html",
                records=[],
                total_scans=0,
                recent_scans=0
            )


        user_email = session["user"]


        # ----------------------------------------------------
        # Scan history
        # ----------------------------------------------------

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


        # ----------------------------------------------------
        # Total scans
        # ----------------------------------------------------

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
            if result
            else 0
        )


        # ----------------------------------------------------
        # Recent 30 days
        # ----------------------------------------------------

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
            if result
            else 0
        )


        return render_template(

            "dashboard.html",

            records=records,

            total_scans=total_scans,

            recent_scans=recent_scans

        )


    except Exception as e:

        print(
            "Dashboard error:",
            e
        )


        return render_template(

            "dashboard.html",

            records=[],

            total_scans=0,

            recent_scans=0

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

        return redirect(
            url_for("login")
        )


    try:

        if not ensure_db_connection():

            return render_template(
                "profile.html",
                user=None,
                total_scans=0,
                name=session.get(
                    "name",
                    "User"
                )
            )


        user_email = session["user"]


        # ----------------------------------------------------
        # Profile image upload
        # ----------------------------------------------------

        if request.method == "POST":

            profile_file = request.files.get(
                "profile_image"
            )


            if (
                profile_file
                and profile_file.filename
            ):

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


                    profile_file.save(
                        filepath
                    )


                    relative_path = (
                        f"uploads/{filename}"
                    )


                    cursor.execute(
                        """
                        UPDATE users
                        SET profile_image = %s
                        WHERE email = %s
                        """,
                        (
                            relative_path,
                            user_email
                        )
                    )


                    db.commit()


        # ----------------------------------------------------
        # Get user
        # ----------------------------------------------------

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


        # ----------------------------------------------------
        # Scan count
        # ----------------------------------------------------

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
            if result
            else 0
        )


        return render_template(

            "profile.html",

            user=user_info,

            total_scans=scan_count,

            name=session.get(
                "name",
                "User"
            )

        )


    except Exception as e:

        print(
            "Profile error:",
            e
        )


        return render_template(

            "profile.html",

            user=None,

            total_scans=0,

            name=session.get(
                "name",
                "User"
            )

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

            "error":
                "Unauthorized. Please login again."

        }), 401


    # --------------------------------------------------------
    # Database
    # --------------------------------------------------------

    if not ensure_db_connection():

        return jsonify({

            "success": False,

            "error":
                "Database connection failed."

        }), 500


    # --------------------------------------------------------
    # Model
    # --------------------------------------------------------

    if model is None:

        return jsonify({

            "success": False,

            "error":
                "AI model is currently unavailable. Please check the model file and restart the server."

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

    uploaded_file = request.files.get(
        "image"
    )


    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    if not patient_name:

        return jsonify({

            "success": False,

            "error":
                "Patient name is required."

        }), 400


    if not age:

        return jsonify({

            "success": False,

            "error":
                "Patient age is required."

        }), 400


    try:

        age_value = int(age)

    except ValueError:

        return jsonify({

            "success": False,

            "error":
                "Age must be a valid number."

        }), 400


    if age_value < 1 or age_value > 120:

        return jsonify({

            "success": False,

            "error":
                "Age must be between 1 and 120."

        }), 400


    if not gender:

        return jsonify({

            "success": False,

            "error":
                "Gender is required."

        }), 400


    if not symptoms:

        return jsonify({

            "success": False,

            "error":
                "Symptoms or observations are required."

        }), 400


    if (
        uploaded_file is None
        or not uploaded_file.filename
    ):

        return jsonify({

            "success": False,

            "error":
                "Please upload a skin image."

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

            "error":
                "Invalid image filename."

        }), 400


    allowed_extensions = {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp"
    }


    extension = os.path.splitext(
        original_filename
    )[1].lower()


    if extension not in allowed_extensions:

        return jsonify({

            "success": False,

            "error":
                "Only JPG, JPEG, PNG and WEBP images are supported."

        }), 400


    # ========================================================
    # DUPLICATE REQUEST PROTECTION
    # ========================================================

    user_email = session["user"]


    try:

        cursor.execute(
            """
            SELECT
                id,
                status,
                created_at
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

            existing_status = (
                existing_scan.get(
                    "status",
                    "Already processed"
                )
            )


            diagnosis = (
                str(existing_status)
                .split(" (")[0]
            )


            confidence = None


            try:

                confidence_text = (
                    str(existing_status)
                    .split("(")[1]
                    .split("%")[0]
                )

                confidence = float(
                    confidence_text
                )

            except Exception:

                confidence = None


            return jsonify({

                "success": True,

                "duplicate": True,

                "scan_id":
                    existing_scan["id"],

                "result":
                    existing_status,

                "diagnosis":
                    diagnosis,

                "confidence":
                    confidence,

                "message":
                    "This screening request was already processed."

            })


    except Exception as e:

        print(
            "Duplicate check error:",
            e
        )


    # ========================================================
    # SAVE IMAGE
    # ========================================================

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"
    )


    filename = (
        f"{timestamp}_{original_filename}"
    )


    filepath = os.path.join(
        UPLOAD_DIR,
        filename
    )


    try:

        uploaded_file.save(
            filepath
        )

    except Exception as e:

        print(
            "Image save error:",
            e
        )


        return jsonify({

            "success": False,

            "error":
                "Unable to save uploaded image."

        }), 500


    # ========================================================
    # AI PREDICTION
    # ========================================================

    try:

        # Load image as 64x64
        img = image.load_img(
            filepath,
            target_size=(64, 64)
        )


        # Convert to numpy
        x = image.img_to_array(
            img
        )


        # Add batch dimension
        x = np.expand_dims(
            x,
            axis=0
        )


        # Verify shape
        if x.shape != (
            1,
            64,
            64,
            3
        ):

            raise ValueError(
                f"Unexpected image shape: {x.shape}"
            )


        # Predict
        preds = model.predict(
            x,
            verbose=0
        )


        # Verify output
        if (
            len(preds.shape) != 2
            or preds.shape[1] != 5
        ):

            raise ValueError(
                f"Unexpected model output shape: {preds.shape}"
            )


        # Predicted class
        label_index = int(
            np.argmax(
                preds,
                axis=1
            )[0]
        )


        # Confidence
        confidence = float(
            np.max(preds)
        ) * 100


        # Class
        if (
            label_index < 0
            or label_index >= len(MODEL_CLASSES)
        ):

            raise ValueError(
                "Invalid predicted class index."
            )


        diagnosis = (
            MODEL_CLASSES[
                label_index
            ]
        )


        diagnosis_result = (
            f"{diagnosis} "
            f"({confidence:.1f}% Match)"
        )


    except Exception as e:

        print(
            "Prediction error:",
            e
        )


        # Delete failed upload
        try:

            if os.path.exists(
                filepath
            ):

                os.remove(
                    filepath
                )

        except Exception:
            pass


        return jsonify({

            "success": False,

            "error":
                "AI model could not process this image.",

            "details":
                str(e)

        }), 503


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
                status
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
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


    except Exception as e:

        try:
            db.rollback()
        except Exception:
            pass


        print(
            "Database insert error:",
            e
        )


        return jsonify({

            "success": False,

            "error":
                "Prediction completed, but the screening record could not be saved.",

            "details":
                str(e)

        }), 500


    # ========================================================
    # SUCCESS
    # ========================================================

    return jsonify({

        "success": True,

        "duplicate": False,

        "scan_id":
            scan_id,

        "result":
            diagnosis_result,

        "diagnosis":
            diagnosis,

        "confidence":
            round(
                confidence,
                1
            )

    })


# ============================================================
# DASHBOARD STATISTICS
# ============================================================

@app.route("/api/stats")
def api_stats():

    if "user" not in session:

        return jsonify({

            "success": False,

            "error":
                "Unauthorized"

        }), 401


    try:

        if not ensure_db_connection():

            return jsonify({

                "success": False,

                "error":
                    "Database connection failed.",

                "distribution":
                    []

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
            (
                session["user"],
            )
        )


        rows = cursor.fetchall()


        distribution = []


        for row in rows:

            distribution.append({

                "status":
                    row["status"],

                "count":
                    int(row["count"])

            })


        total = sum(
            item["count"]
            for item in distribution
        )


        return jsonify({

            "success": True,

            "total":
                total,

            "distribution":
                distribution

        })


    except Exception as e:

        print(
            "Stats error:",
            e
        )


        return jsonify({

            "success": False,

            "error":
                "Unable to load statistics.",

            "distribution":
                []

        }), 500


# ============================================================
# DOWNLOAD PDF REPORT
# ============================================================

@app.route(
    "/download_report/<int:scan_id>"
)
def download_report(scan_id):

    if "user" not in session:

        return redirect(
            url_for("login")
        )


    try:

        if not ensure_db_connection():

            return (
                "Database connection failed.",
                500
            )


        cursor.execute(
            """
            SELECT *
            FROM scan_records
            WHERE id = %s
              AND user_email = %s
            LIMIT 1
            """,
            (
                scan_id,
                session["user"]
            )
        )


        record = cursor.fetchone()


        if not record:

            return (
                "Record not found",
                404
            )


        # ----------------------------------------------------
        # PDF
        # ----------------------------------------------------

        buffer = io.BytesIO()


        pdf = canvas.Canvas(
            buffer,
            pagesize=letter
        )


        # Header

        pdf.setFont(
            "Helvetica-Bold",
            20
        )

        pdf.drawString(
            50,
            750,
            "Dermasafe AI"
        )


        pdf.setFont(
            "Helvetica",
            11
        )

        pdf.drawString(
            50,
            730,
            "AI-Assisted Skin Screening Report"
        )


        pdf.line(
            50,
            715,
            560,
            715
        )


        # Patient information

        pdf.setFont(
            "Helvetica-Bold",
            13
        )

        pdf.drawString(
            50,
            680,
            "Patient Information"
        )


        pdf.setFont(
            "Helvetica",
            11
        )


        pdf.drawString(
            50,
            650,
            f"Patient Name: {record['patient_name']}"
        )


        pdf.drawString(
            50,
            630,
            f"Age: {record['age']}"
        )


        pdf.drawString(
            50,
            610,
            f"Gender: {record['gender']}"
        )


        pdf.drawString(
            50,
            590,
            f"Date: {record['created_at']}"
        )


        # Symptoms

        pdf.setFont(
            "Helvetica-Bold",
            13
        )

        pdf.drawString(
            50,
            550,
            "Symptoms / Observations"
        )


        pdf.setFont(
            "Helvetica",
            11
        )


        symptoms_text = str(
            record["symptoms"]
        )


        symptom_lines = [

            symptoms_text[i:i + 80]

            for i in range(
                0,
                len(symptoms_text),
                80
            )

        ]


        y = 525


        for line in symptom_lines[:5]:

            pdf.drawString(
                50,
                y,
                line
            )

            y -= 17


        # AI Result

        y -= 15


        pdf.setFont(
            "Helvetica-Bold",
            13
        )

        pdf.drawString(
            50,
            y,
            "AI Screening Result"
        )


        y -= 30


        pdf.setFont(
            "Helvetica-Bold",
            12
        )

        pdf.drawString(
            50,
            y,
            str(
                record["status"]
            )
        )


        # Disclaimer

        y -= 60


        pdf.setFont(
            "Helvetica-Oblique",
            9
        )


        disclaimer = (
            "This report is generated by an AI-assisted "
            "screening system and is not a medical diagnosis. "
            "Please consult a qualified dermatologist or "
            "healthcare professional for clinical evaluation."
        )


        disclaimer_lines = [

            disclaimer[i:i + 90]

            for i in range(
                0,
                len(disclaimer),
                90
            )

        ]


        for line in disclaimer_lines:

            pdf.drawString(
                50,
                y,
                line
            )

            y -= 14


        # Footer

        pdf.setFont(
            "Helvetica",
            8
        )


        pdf.drawString(
            50,
            45,
            "Dermasafe AI - Preliminary AI Screening Report"
        )


        pdf.showPage()

        pdf.save()


        buffer.seek(0)


        safe_patient_name = secure_filename(
            str(
                record["patient_name"]
            )
        )


        if not safe_patient_name:

            safe_patient_name = "Patient"


        return send_file(

            buffer,

            as_attachment=True,

            download_name=(
                f"Report_{safe_patient_name}_{scan_id}.pdf"
            ),

            mimetype="application/pdf"

        )


    except Exception as e:

        print(
            "PDF generation error:",
            e
        )


        return (
            "Unable to generate report.",
            500
        )


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )


# ============================================================
# FILE TOO LARGE
# ============================================================

@app.errorhandler(413)
def file_too_large(error):

    if request.path == "/predict_scan":

        return jsonify({

            "success": False,

            "error":
                "Image is too large. Maximum size is 8 MB."

        }), 413


    return (
        "File too large.",
        413
    )


# ============================================================
# START SERVER
# ============================================================

if __name__ == "__main__":

    print()
    print("==========================================")
    print("       DERMASAFE AI")
    print("   Healthcare AI Screening Platform")
    print("==========================================")

    print(
        f"Database: {DB_NAME}"
    )

    print(
        f"Model available: {model is not None}"
    )

    print(
        f"Model path: {MODEL_PATH}"
    )

    print("==========================================")
    print()


    app.run(
        debug=True,
        threaded=False
    )