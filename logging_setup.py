"""Initialize a logging format for the application."""

from logging.config import dictConfig


def setup_logging(level: str = "DEBUG") -> None:
    """Initialize the logging format for the application."""
    dictConfig(
        {
            "version": 1,
            "formatters": {
                "default": {
                    "format": "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d — %(message)s",
                }
            },
            "handlers": {
                "console": {"class": "logging.StreamHandler", "formatter": "default"}
            },
            "root": {"handlers": ["console"], "level": level},
        },
    )
