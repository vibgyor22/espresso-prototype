#!/usr/bin/env python
"""
Flask server runner - starts Espresso web interface
"""
import sys
import os
import traceback

# Set working directory
os.chdir(r'c:\Users\vibho\Documents\espresso-prototype')

print("[BOOT] Starting Espresso Web Interface")
print("[BOOT] Python version:", sys.version)
print("[BOOT] Working directory:", os.getcwd())

try:
    print("[IMPORT] Importing Flask app...")
    from app import app
    print("[OK] App imported successfully")
    
    print("[RUN] Starting Flask server on http://127.0.0.1:5000")
    print("[RUN] Press Ctrl+C to stop")
    print("="*60)
    
    app.run(
        host='127.0.0.1',
        port=5000,
        debug=False,
        use_reloader=False,
        threaded=True
    )
    
except KeyboardInterrupt:
    print("\n[STOP] Server stopped by user")
    sys.exit(0)
    
except Exception as e:
    print(f"\n[ERROR] Failed to start server: {e}")
    print("[TRACEBACK]")
    traceback.print_exc()
    sys.exit(1)
