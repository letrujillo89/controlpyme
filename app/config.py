import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///controlpyme.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "instance/uploads")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB