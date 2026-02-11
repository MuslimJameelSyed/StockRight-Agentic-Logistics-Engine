"""
Configuration module for Warehouse Qdrant System - LOCAL DEPLOYMENT
Uses local MySQL Docker + Ollama instead of Cloud SQL + Gemini
Qdrant remains cloud-based (API)
"""
import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict

# Load environment variables from local .env file (same directory)
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

# Setup logging
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing"""
    pass


class ConfigLocal:
    """Local deployment configuration class with validation and error handling"""

    # Ollama Configuration (Local LLM)
    OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'localhost')
    OLLAMA_PORT = int(os.getenv('OLLAMA_PORT', '11434'))
    OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'llama3.2')
    OLLAMA_BASE_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}"

    # Qdrant Configuration (Cloud API - kept from original)
    QDRANT_URL = os.getenv('QDRANT_URL')
    QDRANT_API_KEY = os.getenv('QDRANT_API_KEY')
    QDRANT_COLLECTION_NAME = os.getenv('QDRANT_COLLECTION_NAME', 'PartSummary')

    # MySQL Configuration (can be local Docker or Cloud SQL)
    # Try Cloud SQL first, fall back to local settings
    MYSQL_HOST = os.getenv('CLOUD_SQL_HOST') or os.getenv('MYSQL_HOST', 'localhost')
    MYSQL_PORT = int(os.getenv('CLOUD_SQL_PORT') or os.getenv('MYSQL_PORT', '3306'))
    MYSQL_DATABASE = os.getenv('CLOUD_SQL_DATABASE') or os.getenv('MYSQL_DATABASE', 'mydatabase_gdpr')
    MYSQL_USER = os.getenv('CLOUD_SQL_USER') or os.getenv('MYSQL_USER', 'muslim')
    MYSQL_PASSWORD = os.getenv('CLOUD_SQL_PASSWORD') or os.getenv('MYSQL_PASSWORD', 'warehouse_pass_2024')

    # Application Configuration
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    ENABLE_AUDIT_LOG = os.getenv('ENABLE_AUDIT_LOG', 'true').lower() == 'true'
    MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
    REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '30'))

    # LLM Generation Settings
    OLLAMA_TEMPERATURE = float(os.getenv('OLLAMA_TEMPERATURE', '0.1'))
    OLLAMA_MAX_TOKENS = int(os.getenv('OLLAMA_MAX_TOKENS', '1024'))
    OLLAMA_REQUEST_TIMEOUT = int(os.getenv('OLLAMA_REQUEST_TIMEOUT', '60'))

    @classmethod
    def get_db_config(cls) -> Dict[str, any]:
        """
        Get database configuration as dict

        Returns:
            Dict with database connection parameters

        Raises:
            ConfigurationError: If required database config is missing
        """
        required = ['MYSQL_HOST', 'MYSQL_DATABASE', 'MYSQL_USER', 'MYSQL_PASSWORD']
        missing = [key for key in required if not getattr(cls, key)]

        if missing:
            raise ConfigurationError(f"Missing required database configuration: {', '.join(missing)}")

        return {
            'host': cls.MYSQL_HOST,
            'port': cls.MYSQL_PORT,
            'database': cls.MYSQL_DATABASE,
            'user': cls.MYSQL_USER,
            'password': cls.MYSQL_PASSWORD,
            'connection_timeout': cls.REQUEST_TIMEOUT,
            'autocommit': True
        }

    @classmethod
    def get_ollama_config(cls) -> Dict[str, any]:
        """
        Get Ollama configuration as dict

        Returns:
            Dict with Ollama connection parameters
        """
        return {
            'base_url': cls.OLLAMA_BASE_URL,
            'model': cls.OLLAMA_MODEL,
            'temperature': cls.OLLAMA_TEMPERATURE,
            'max_tokens': cls.OLLAMA_MAX_TOKENS,
            'timeout': cls.OLLAMA_REQUEST_TIMEOUT
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

        # Check Ollama config
        if not cls.OLLAMA_HOST:
            errors.append("OLLAMA_HOST is required (set in .env file)")
        if not cls.OLLAMA_MODEL:
            errors.append("OLLAMA_MODEL is required (set in .env file)")

        # Check Qdrant config (still using cloud API)
        if not cls.QDRANT_URL:
            errors.append("QDRANT_URL is required (set in .env file)")
        if not cls.QDRANT_API_KEY:
            errors.append("QDRANT_API_KEY is required (set in .env file)")

        # Check MySQL config (local)
        if not cls.MYSQL_HOST:
            errors.append("MYSQL_HOST is required (set in .env file)")
        if not cls.MYSQL_DATABASE:
            errors.append("MYSQL_DATABASE is required (set in .env file)")
        if not cls.MYSQL_USER:
            errors.append("MYSQL_USER is required (set in .env file)")
        if not cls.MYSQL_PASSWORD:
            errors.append("MYSQL_PASSWORD is required (set in .env file)")

        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            logger.error(error_msg)
            raise ConfigurationError(error_msg)

        logger.info("Local deployment configuration validated successfully")
        return True

    @classmethod
    def log_config_status(cls):
        """Log configuration status (without exposing secrets)"""
        logger.info("LOCAL DEPLOYMENT Configuration loaded:")
        logger.info(f"  Ollama Model: {cls.OLLAMA_MODEL} @ {cls.OLLAMA_BASE_URL}")
        logger.info(f"  Qdrant Collection: {cls.QDRANT_COLLECTION_NAME} (Cloud API)")
        logger.info(f"  MySQL Database: {cls.MYSQL_DATABASE} @ {cls.MYSQL_HOST}:{cls.MYSQL_PORT} (Local Docker)")
        logger.info(f"  Log Level: {cls.LOG_LEVEL}")
        logger.info(f"  Audit Logging: {'Enabled' if cls.ENABLE_AUDIT_LOG else 'Disabled'}")


# Create singleton instance and validate
config = ConfigLocal()

# Validate configuration on import (fail fast)
try:
    config.validate()
    config.log_config_status()
except ConfigurationError as e:
    logger.critical(f"FATAL: {e}")
    logger.critical("Please check your .env file and ensure all required variables are set.")
    logger.critical("For local deployment, you need: OLLAMA_HOST, OLLAMA_MODEL, MYSQL_HOST, MYSQL_PASSWORD, QDRANT_URL, QDRANT_API_KEY")
    raise