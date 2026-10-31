-- ============================================================
-- DERMASAFE AI — DATABASE SCHEMA
-- ============================================================
--
-- Run this file to set up the database:
--
--   mysql -u root -p < schema.sql
--
-- ============================================================

CREATE DATABASE IF NOT EXISTS skin_disease_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE skin_disease_db;


-- ============================================================
-- USERS
-- ============================================================

CREATE TABLE IF NOT EXISTS users (

    id              INT             AUTO_INCREMENT PRIMARY KEY,

    username        VARCHAR(100)    NOT NULL,

    email           VARCHAR(255)    NOT NULL UNIQUE,

    password        VARCHAR(255)    NOT NULL,

    profile_image   VARCHAR(500)    DEFAULT NULL,

    created_at      DATETIME        DEFAULT CURRENT_TIMESTAMP,

    last_login      DATETIME        DEFAULT NULL,

    INDEX idx_email (email)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ============================================================
-- SCAN RECORDS
-- ============================================================

CREATE TABLE IF NOT EXISTS scan_records (

    id              INT             AUTO_INCREMENT PRIMARY KEY,

    user_email      VARCHAR(255)    NOT NULL,

    patient_name    VARCHAR(200)    NOT NULL,

    age             INT             NOT NULL,

    gender          VARCHAR(20)     NOT NULL,

    symptoms        TEXT            NOT NULL,

    image_path      VARCHAR(500)    NOT NULL,

    status          VARCHAR(255)    NOT NULL,

    confidence      FLOAT           DEFAULT NULL,

    ai_insights     TEXT            DEFAULT NULL,

    created_at      DATETIME        DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_user_email (user_email),
    INDEX idx_created_at (created_at),

    FOREIGN KEY (user_email)
        REFERENCES users(email)
        ON UPDATE CASCADE
        ON DELETE CASCADE

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

