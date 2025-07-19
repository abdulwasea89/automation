import json
import logging
import sys
import os
import time
import random
from datetime import datetime
from typing import Dict, Any

try:
    import colorlog
    COLORLOG_AVAILABLE = True
except ImportError:
    COLORLOG_AVAILABLE = False


class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            'level': record.levelname,
            'time': self.formatTime(record, self.datefmt),
            'name': record.name,
            'message': record.getMessage(),
        }
        if record.exc_info:
            log_record['exc_info'] = self.formatException(record.exc_info)
        return json.dumps(log_record)


class ColorfulFormatter(logging.Formatter):
    """Enhanced colorful formatter with different colors for different loggers and operations."""
    
    def __init__(self):
        super().__init__()
        self.colors = {
            # Primary colors for different logger types
            'ROUTE': '\033[95m',      # Purple
            'REQUEST': '\033[94m',     # Blue
            'RESPONSE': '\033[92m',    # Green
            'DATABASE': '\033[96m',    # Cyan
            'AGENT': '\033[93m',       # Yellow
            'CACHE': '\033[35m',       # Magenta
            'ERROR': '\033[91m',       # Red
            'WARNING': '\033[33m',     # Orange
            'INFO': '\033[32m',        # Green
            'DEBUG': '\033[36m',       # Light Cyan
            
            # Additional colors for variety
            'PINK': '\033[38;5;213m',      # Pink
            'LIGHT_BLUE': '\033[38;5;117m', # Light Blue
            'LIGHT_GREEN': '\033[38;5;120m', # Light Green
            'LIGHT_YELLOW': '\033[38;5;227m', # Light Yellow
            'LIGHT_PURPLE': '\033[38;5;183m', # Light Purple
            'LIGHT_CYAN': '\033[38;5;159m',   # Light Cyan
            'LIGHT_RED': '\033[38;5;203m',    # Light Red
            'LIGHT_ORANGE': '\033[38;5;215m', # Light Orange
            'LIGHT_MAGENTA': '\033[38;5;219m', # Light Magenta
            'GOLD': '\033[38;5;220m',         # Gold
            'SILVER': '\033[38;5;248m',       # Silver
            'BRONZE': '\033[38;5;173m',       # Bronze
            
            # Formatting
            'RESET': '\033[0m',        # Reset
            'BOLD': '\033[1m',         # Bold
            'WHITE': '\033[97m',       # White
            'UNDERLINE': '\033[4m',    # Underline
            'BLINK': '\033[5m',        # Blink
        }
        
        # Color rotation for different operations
        self.operation_colors = [
            '\033[95m',   # Purple
            '\033[94m',   # Blue
            '\033[92m',   # Green
            '\033[96m',   # Cyan
            '\033[93m',   # Yellow
            '\033[35m',   # Magenta
            '\033[38;5;213m',  # Pink
            '\033[38;5;117m',  # Light Blue
            '\033[38;5;120m',  # Light Green
            '\033[38;5;227m',  # Light Yellow
            '\033[38;5;183m',  # Light Purple
            '\033[38;5;159m',  # Light Cyan
            '\033[38;5;203m',  # Light Red
            '\033[38;5;215m',  # Light Orange
            '\033[38;5;219m',  # Light Magenta
            '\033[38;5;220m',  # Gold
            '\033[38;5;248m',  # Silver
            '\033[38;5;173m',  # Bronze
        ]
        self.color_index = 0
    
    def get_next_color(self):
        """Get next color from the rotation."""
        color = self.operation_colors[self.color_index]
        self.color_index = (self.color_index + 1) % len(self.operation_colors)
        return color
    
    def format(self, record):
        # Get base color based on logger name
        base_color = self.colors.get(record.name.upper(), self.colors['INFO'])
        
        # Get operation-specific color for variety
        operation_color = self.get_next_color()
        
        # Format timestamp
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        
        # Format the message with colors
        formatted_msg = f"{base_color}{self.colors['BOLD']}[{record.name.upper()}]{self.colors['RESET']} "
        formatted_msg += f"{self.colors['WHITE']}{timestamp}{self.colors['RESET']} "
        formatted_msg += f"{operation_color}{record.getMessage()}{self.colors['RESET']}"
        
        return formatted_msg


def get_logger(name: str):
    """Get a logger with colorful formatting."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        
        if COLORLOG_AVAILABLE:
            # Use colorlog for better color support with more variety
            formatter = colorlog.ColoredFormatter(
                '%(log_color)s%(bold)s[%(name)s]%(reset)s %(white)s%(asctime)s%(reset)s %(log_color)s%(message)s',
                datefmt='%Y-%m-%d %H:%M:%S.%f',
                log_colors={
                    'DEBUG': 'cyan',
                    'INFO': 'green',
                    'WARNING': 'yellow',
                    'ERROR': 'red',
                    'CRITICAL': 'bold_red',
                },
                secondary_log_colors={
                    'name': {
                        'ROUTE': 'purple',
                        'REQUEST': 'blue',
                        'RESPONSE': 'green',
                        'DATABASE': 'cyan',
                        'AGENT': 'yellow',
                        'CACHE': 'magenta',
                        'ERROR': 'red',
                        'WARNING': 'yellow',
                        'INFO': 'green',
                        'DEBUG': 'light_cyan',
                    }
                }
            )
        else:
            # Fallback to custom colorful formatter
            formatter = ColorfulFormatter()
        
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    # Set log level based on environment
    env = os.getenv("ENVIRONMENT", "development")
    if env == "production":
        logger.setLevel(logging.WARNING)  # Reduce logging in production
    else:
        logger.setLevel(logging.INFO)
    
    return logger


# Specialized loggers for different operations
def get_route_logger():
    """Logger for route operations."""
    return get_logger("ROUTE")

def get_request_logger():
    """Logger for request operations."""
    return get_logger("REQUEST")

def get_response_logger():
    """Logger for response operations."""
    return get_logger("RESPONSE")

def get_database_logger():
    """Logger for database operations."""
    return get_logger("DATABASE")

def get_agent_logger():
    """Logger for agent operations."""
    return get_logger("AGENT")

def get_cache_logger():
    """Logger for cache operations."""
    return get_logger("CACHE")

def get_error_logger():
    """Logger for error operations."""
    return get_logger("ERROR")


# Utility functions for colorful logging with dynamic colors
def log_route(method: str, path: str, **kwargs):
    """Log route access with colorful output."""
    logger = get_route_logger()
    extra_info = " ".join([f"{k}={v}" for k, v in kwargs.items()])
    emoji = random.choice(["🚀", "⚡", "🔥", "💫", "🌟", "✨", "🎯", "🎪", "🎨", "🎭"])
    logger.info(f"{emoji} {method} {path} {extra_info}")

def log_request(chat_id: str = None, message: str = None, **kwargs):
    """Log incoming requests with colorful output."""
    logger = get_request_logger()
    chat_info = f"[Chat: {chat_id}]" if chat_id else ""
    message_preview = f"'{message[:50]}...'" if message and len(message) > 50 else f"'{message}'" if message else ""
    extra_info = " ".join([f"{k}={v}" for k, v in kwargs.items()])
    emoji = random.choice(["📥", "📨", "📬", "📩", "📪", "📫", "📭", "📮", "📯", "📰"])
    logger.info(f"{emoji} INCOMING {chat_info} {message_preview} {extra_info}")

def log_response(chat_id: str = None, response_type: str = None, **kwargs):
    """Log outgoing responses with colorful output."""
    logger = get_response_logger()
    chat_info = f"[Chat: {chat_id}]" if chat_id else ""
    response_info = f"[Type: {response_type}]" if response_type else ""
    extra_info = " ".join([f"{k}={v}" for k, v in kwargs.items()])
    emoji = random.choice(["📤", "📨", "📬", "📩", "📪", "📫", "📭", "📮", "📯", "📰"])
    logger.info(f"{emoji} OUTGOING {chat_info} {response_info} {extra_info}")

def log_database(operation: str, query: str = None, **kwargs):
    """Log database operations with colorful output."""
    logger = get_database_logger()
    query_preview = f"'{query[:50]}...'" if query and len(query) > 50 else f"'{query}'" if query else ""
    extra_info = " ".join([f"{k}={v}" for k, v in kwargs.items()])
    emoji = random.choice(["🗄️", "💾", "📊", "📈", "📉", "🔍", "🔎", "🔐", "🔑", "🔒"])
    logger.info(f"{emoji} {operation} {query_preview} {extra_info}")

def log_agent(agent_name: str, action: str, **kwargs):
    """Log agent operations with colorful output."""
    logger = get_agent_logger()
    extra_info = " ".join([f"{k}={v}" for k, v in kwargs.items()])
    emoji = random.choice(["🤖", "🧠", "💡", "🎯", "🎪", "🎨", "🎭", "🎪", "🎯", "🎨"])
    logger.info(f"{emoji} {agent_name} {action} {extra_info}")

def log_cache(operation: str, key: str = None, **kwargs):
    """Log cache operations with colorful output."""
    logger = get_cache_logger()
    key_preview = f"'{key[:30]}...'" if key and len(key) > 30 else f"'{key}'" if key else ""
    extra_info = " ".join([f"{k}={v}" for k, v in kwargs.items()])
    emoji = random.choice(["💾", "⚡", "🔥", "💫", "🌟", "✨", "🎯", "🎪", "🎨", "🎭"])
    logger.info(f"{emoji} {operation} {key_preview} {extra_info}")

def log_error(error_type: str, message: str, **kwargs):
    """Log errors with colorful output."""
    logger = get_error_logger()
    extra_info = " ".join([f"{k}={v}" for k, v in kwargs.items()])
    emoji = random.choice(["❌", "💥", "🔥", "💀", "☠️", "⚠️", "🚨", "🚫", "⛔", "🛑"])
    logger.error(f"{emoji} {error_type}: {message} {extra_info}")
