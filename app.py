from flask import Flask, Blueprint, jsonify
import json

# Create a separate blueprint for API endpoints
api_bp = Blueprint('api', __name__)

def expose(route, **options):
    """
    Custom decorator to register API endpoints in the blueprint.
    """
    def decorator(func):
        api_bp.route(route, **options)(func)
        return func
    return decorator

def load_data():
    """
    Load JSON data from the backend file.
    """
    try:
        with open('data.json', 'r') as file:
            return json.load(file)
    except Exception as e:
        # Return error information to be handled by the endpoint
        return {"error": str(e)}

@expose('/api', methods=['GET'])
def get_data():
    """
    API endpoint to fetch data from data.json.
    """
    data = load_data()
    if isinstance(data, dict) and data.get("error"):
        return jsonify(data), 500
    return jsonify(data)

# Create the Flask app and register the blueprint
app = Flask(__name__)
app.register_blueprint(api_bp)

@app.route('/')
def home():
    """
    Root endpoint to show that the flask server is running.
    """
    return "Flask server is up and running!", 200

if __name__ == '__main__':
    app.run(debug=True)
