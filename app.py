import config
from logger import get_logger


logger = get_logger(__name__)


def main():
    logger.info("Starting application")

    print("=" * 40)
    print(f"Application: {config.APP_NAME}")
    print(f"Environment: {config.ENVIRONMENT}")
    print("Status: Running")
    print("=" * 40)

    logger.info("Application started successfully")


if __name__ == "__main__":
    main()