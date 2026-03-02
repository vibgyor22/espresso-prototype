#!/usr/bin/env python3
"""Minimal Flask test"""

from flask import Flask, jsonify, request

app = Flask(__name__)

@app.route('/test', methods=['POST'])
def test():
    data = request.json
    return jsonify({'received': data, 'status': 'ok'})

if __name__ == '__main__':
    app.run(debug=False, port=5001, use_reloader=False)
