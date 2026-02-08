"""
Configuration module for Warehouse Qdrant System
Loads environment variables and provides configuration objects with validation
"""
import os
import logging
from dotenv import load_dotenv
from typing import Dict

# Load environment variables from .env file
load_dotenv()

# Setup logging
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing"""
    pass


class Config:
    """Main configuration class with validation and error handling"""

    # Gemini Configuration
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')

    # Qdrant Configuration
    QDRANT_URL = os.getenv('QDRANT_URL')
    QDRANT_API_KEY = os.getenv('QDRANT_API_KEY')
    QDRANT_COLLECTION_NAME = os.getenv('QDRANT_COLLECTION_NAME', 'PartSummary')

    # Cloud SQL Configuration
    CLOUD_SQL_HOST = os.getenv('CLOUD_SQL_HOST')
    CLOUD_SQL_PORT = int(os.getenv('CLOUD_SQL_PORT', '3306'))
    CLOUD_SQL_DATABASE = os.getenv('CLOUD_SQL_DATABASE')
    CLOUD_SQL_USER = os.getenv('CLOUD_SQL_USER')
    CLOUD_SQL_PASSWORD = os.getenv('CLOUD_SQL_PASSWORD')

    # Application Configuration
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    ENABLE_AUDIT_LOG = os.getenv('ENABLE_AUDIT_LOG', 'true').lower() == 'true'
    MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
    REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '30'))

    @classmethod
    def get_db_config(cls) -> Dict[str, any]:
        """
        Get database configuration as dict

        Returns:
            Dict with database connection parameters

        Raises:
            ConfigurationError: If required database config is missing
        """
        required = ['CLOUD_SQL_HOST', 'CLOUD_SQL_DATABASE', 'CLOUD_SQL_USER', 'CLOUD_SQL_PASSWORD']
        missing = [key for key in required if not getattr(cls, key)]

        if missing:
            raise ConfigurationError(f"Missing required database configuration: {', '.join(missing)}")

        return {
            'host': cls.CLOUD_SQL_HOST,
            'port': cls.CLOUD_SQL_PORT,
            'database': cls.CLOUD_SQL_DATABASE,
            'user': cls.CLOUD_SQL_USER,
            'password': cls.CLOUD_SQL_PASSWORD,
            'connection_timeout': cls.REQUEST_TIMEOUT,
            'autocommit': True
        }

    @classmethod
    def validate(cls) -> bool:
        """
        Validate that all required configuration is present

        Returns:
            True if configuration is valid

        Raises:
            ConfigurationError: If configuration is invalid
        """
        errors = []

        # Check Gemini config
        if not cls.GEMINI_API_KEY:
            errors.append("GEMINI_API_KEY is required (set in .env file)")

        # Check Qdrant config
        if not cls.QDRANT_URL:
            errors.append("QDRANT_URL is required (set in .env file)")
        if not cls.QDRANT_API_KEY:
            errors.append("QDRANT_API_KEY is required (set in .env file)")

        # Check Cloud SQL config
        if not cls.CLOUD_SQL_HOST:
            errors.append("CLOUD_SQL_HOST is required (set in .env file)")
        if not cls.CLOUD_SQL_DATABASE:
            errors.append("CLOUD_SQL_DATABASE is required (set in .env file)")
        if not cls.CLOUD_SQL_USER:
            errors.append("CLOUD_SQL_USER is required (set in .env file)")
        if not cls.CLOUD_SQL_PASSWORD:
            errors.append("CLOUD_SQL_PASSWORD is required (set in .env file)")

        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            logger.error(error_msg)
            raise ConfigurationError(error_msg)

        logger.info("Configuration validated successfully")
        return True

    @classmethod
    def log_config_status(cls):
        """Log configuration status (without exposing secrets)"""
        logger.info("Configuration loaded:")
        logger.info(f"  Gemini Model: {cls.GEMINI_MODEL}")
        logger.info(f"  Qdrant Collection: {cls.QDRANT_COLLECTION_NAME}")
        logger.info(f"  Database: {cls.CLOUD_SQL_DATABASE} @ {cls.CLOUD_SQL_HOST}")
        logger.info(f"  Log Level: {cls.LOG_LEVEL}")
        logger.info(f"  Audit Logging: {'Enabled' if cls.ENABLE_AUDIT_LOG else 'Disabled'}")


# Create singleton instance and validate
config = Config()

# Validate configuration on import (fail fast)
try:
    config.validate()
    config.log_config_status()
except ConfigurationError as e:
    logger.critical(f"FATAL: {e}")
    logger.critical("Please check your .env file and ensure all required variables are set.")
    raise
