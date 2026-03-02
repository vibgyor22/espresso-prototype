#!/usr/bin/env python3
"""Flask server wrapper with better error handling"""

import sys
import signal
import logging
from app import app

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def signal_handler(sig, frame):
    """Handle graceful shutdown"""
    logger.info("Received shutdown signal")
    sys.exit(0)

if __name__ == '__main__':
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        logger.info("Starting Flask application")
        app.run(debug=False, port=5000, use_reloader=False, threaded=True)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
