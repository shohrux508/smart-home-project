# logging_config.py
from logging.config import dictConfig
from config import LoggingSettings


class LoggingConfig:
    def __init__(self, settings: LoggingSettings):
        self.settings = settings

    def setup(self) -> None:
        formatters = {
            "standard": {
                "format": self.settings.formatter,
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "telegram": {
                "format": self.settings.telegram_formatter,
                "datefmt": "%Y-%m-%d %H:%M:%S",
            }
        }

        handlers = {}

        if self.settings.log_to_console:
            handlers["console"] = {
                "class": "logging.StreamHandler",
                "level": self.settings.level,
                "formatter": "standard",
                "stream": "ext://sys.stdout",
            }

        if self.settings.log_to_file:
            handlers["file"] = {
                "class": "logging.handlers.RotatingFileHandler",
                "level": self.settings.level,
                "formatter": "standard",
                "filename": self.settings.log_file_path,
                "maxBytes": self.settings.max_bytes,
                "backupCount": self.settings.backup_count,
                "encoding": "utf8",
            }

        if self.settings.telegram_enabled:
            handlers["telegram"] = {
                "()": "app.infrastructure.logger_module.telegram.TelegramLogHandler",  # <-- путь к твоему классу
                "level": "WARNING",  # или INFO
                "formatter": 'telegram',
                "bot_token": self.settings.telegram_log_bot_token,
                "chat_id": self.settings.telegram_chat_id,
            }

        config = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": formatters,

            "handlers": handlers,
            "loggers": {
                "": {
                    "handlers": list(handlers.keys()),
                    "level": self.settings.level,
                    "propagate": False,
                }
            },
        }

        dictConfig(config)