from flask import Flask, Blueprint, jsonify, render_template, request, redirect, url_for, flash
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from bson.objectid import ObjectId
import os
from datetime import datetime
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create a separate blueprint for API endpoints
api = Blueprint('api', __name__)

# MongoDB Atlas Configuration
MONGO_URI = os.getenv('MONGO_URI', "mongodb+srv://marsalded:db-password@tutedude.hs4khbf.mongodb.net/?retryWrites=true&w=majority&appName=tutedude")
DATABASE_NAME = "tutedude"
COLLECTION_NAME = "todos"

# Global variables for connection status
mongo_client = None
db = None
collection = None
db_connected = False

def connect_to_mongodb():
    """Initialize MongoDB connection"""
    global mongo_client, db, collection, db_connected
    print("Connecting to MongoDB Atlas...")
    logger.info("Connecting to MongoDB Atlas...")
    logger.info(f"mongo_uri: {MONGO_URI}")
    logger.info(f"database_name: {DATABASE_NAME}")
    try:
        # Create a new client with the ServerApi version 1
        mongo_client = MongoClient(MONGO_URI)
        # Test the connection by sending a ping
        mongo_client.admin.command('ping')
        db = mongo_client[DATABASE_NAME]
        collection = db[COLLECTION_NAME]
        db_connected = True
        logger.info("Successfully connected to MongoDB Atlas")
        return True
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        db_connected = False
        return False

def get_db_status():
    """Check current database connection status"""
    global mongo_client, db_connected
    if not mongo_client:
        return False
    try:
        mongo_client.admin.command('ping')
        db_connected = True
        return True
    except Exception as e:
        logger.error(f"Database connection lost: {e}")
        db_connected = False
        return False

def expose(route, **options):
    """
    Custom decorator to register API endpoints in the blueprint.
    """
    def decorator(func):
        api.route(route, **options)(func)
        return func
    return decorator

def get_todos():
    """
    Get todos from MongoDB.
    """
    try:
        if not get_db_status():
            logger.error("Database connection not available")
            return []
        
        # Fetch all todos from MongoDB, sorted by creation date (newest first)
        todos = list(collection.find().sort('created_at', -1))
        
        # Convert ObjectId to string for JSON serialization
        for todo in todos:
            todo['_id'] = str(todo['_id'])
            # Ensure we have an 'id' field for compatibility
            if 'id' not in todo:
                todo['id'] = todo['_id']
        
        return todos
    except Exception as e:
        logger.error(f"Error fetching todos: {e}")
        return []

def save_todo(todo_data):
    """
    Save a single todo to MongoDB.
    """
    try:
        if not get_db_status():
            logger.error("Database connection not available")
            return False
        
        result = collection.insert_one(todo_data)
        if result.inserted_id:
            logger.info(f"Todo saved successfully with ID: {result.inserted_id}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error saving todo: {e}")
        return False

def update_todo(todo_id, update_data):
    """
    Update a todo in MongoDB.
    """
    try:
        if not get_db_status():
            logger.error("Database connection not available")
            return False
        
        # Convert string ID to ObjectId if needed
        if isinstance(todo_id, str):
            todo_id = ObjectId(todo_id)
        
        result = collection.update_one({'_id': todo_id}, {'$set': update_data})
        return result.modified_count > 0
    except Exception as e:
        logger.error(f"Error updating todo: {e}")
        return False

def delete_todo_by_id(todo_id):
    """
    Delete a todo from MongoDB.
    """
    try:
        if not get_db_status():
            logger.error("Database connection not available")
            return False
        
        # Convert string ID to ObjectId if needed
        if isinstance(todo_id, str):
            todo_id = ObjectId(todo_id)
        
        result = collection.delete_one({'_id': todo_id})
        return result.deleted_count > 0
    except Exception as e:
        logger.error(f"Error deleting todo: {e}")
        return False

@expose('/api', methods=['GET'])
def get_data():
    """
    API endpoint to fetch all data including todos from MongoDB.
    """
    try:
        if not get_db_status():
            return jsonify({"error": "Database connection not available"}), 500
        
        todos = get_todos()
        
        # Return the data in the same format as before for compatibility
        data = {
            "todos": todos,
            "metadata": {
                "version": "2.0",
                "last_updated": datetime.now().strftime('%Y-%m-%d'),
                "total_todos": len(todos),
                "database": "MongoDB Atlas"
            }
        }
        
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error in get_data endpoint: {e}")
        return jsonify({"error": str(e)}), 500

@expose('/todos', methods=['GET'])
def todo_page():
    """
    Render the todo page with all todo items.
    """
    todos = get_todos()
    return render_template('todo.html', todos=todos)

@expose('/submittodoitem', methods=['POST'])
def add_todo():
    """
    Add a new todo item to MongoDB.
    """
    try:
        item_name = request.form.get('item_name', '').strip()
        item_description = request.form.get('item_description', '').strip()
        
        if not item_name or not item_description:
            flash('Both item name and description are required!', 'error')
            return redirect(url_for('api.todo_page'))
        
        # Check database connection
        if not get_db_status():
            flash('Database connection error. Please try again later.', 'error')
            return redirect(url_for('api.todo_page'))
        
        # Create new todo document
        new_todo = {
            'name': item_name,
            'description': item_description,
            'completed': False,
            'created_at': datetime.utcnow(),
            'ip_address': request.remote_addr
        }
        
        # Save to MongoDB
        if save_todo(new_todo):
            flash(f'Todo item "{item_name}" added successfully!', 'success')
        else:
            flash('Error saving todo item. Please try again.', 'error')
        
        return redirect(url_for('api.todo_page'))
        
    except Exception as e:
        logger.error(f"Error adding todo: {e}")
        flash(f'An error occurred: {str(e)}', 'error')
        return redirect(url_for('api.todo_page'))

@expose('/todos/<string:todo_id>/toggle', methods=['POST'])
def toggle_todo(todo_id):
    """
    Toggle the completion status of a todo item in MongoDB.
    """
    try:
        if not get_db_status():
            flash('Database connection error. Please try again later.', 'error')
            return redirect(url_for('api.todo_page'))
        
        # Find the todo to get current status
        todo = collection.find_one({'_id': ObjectId(todo_id)})
        
        if todo:
            new_status = not todo.get('completed', False)
            update_data = {
                'completed': new_status,
                'updated_at': datetime.utcnow()
            }
            
            if update_todo(todo_id, update_data):
                status = 'completed' if new_status else 'pending'
                flash(f'Todo item marked as {status}!', 'success')
            else:
                flash('Error updating todo item. Please try again.', 'error')
        else:
            flash('Todo item not found!', 'error')
        
        return redirect(url_for('api.todo_page'))
        
    except Exception as e:
        logger.error(f"Error toggling todo: {e}")
        flash(f'An error occurred: {str(e)}', 'error')
        return redirect(url_for('api.todo_page'))

@expose('/todos/<string:todo_id>/delete', methods=['POST'])
def delete_todo(todo_id):
    """
    Delete a todo item from MongoDB.
    """
    try:
        if not get_db_status():
            flash('Database connection error. Please try again later.', 'error')
            return redirect(url_for('api.todo_page'))
        
        if delete_todo_by_id(todo_id):
            flash('Todo item deleted successfully!', 'success')
        else:
            flash('Todo item not found or error deleting!', 'error')
        
        return redirect(url_for('api.todo_page'))
        
    except Exception as e:
        logger.error(f"Error deleting todo: {e}")
        flash(f'An error occurred: {str(e)}', 'error')
        return redirect(url_for('api.todo_page'))

# Create the Flask app and register the blueprint
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-change-this-in-production')
app.register_blueprint(api)

@app.template_filter('datetime_format')
def datetime_format(value):
    """Format datetime for display"""
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d %H:%M:%S')
    return str(value)

@app.route('/')
def home():
    """
    Root endpoint to show the home page with database status.
    """
    db_status = "🟢 Connected to MongoDB" if get_db_status() else "🔴 MongoDB Connection Failed"
    return render_template('home.html', db_status=db_status, db_connected=get_db_status())

if __name__ == '__main__':
    # Initialize MongoDB connection
    connect_to_mongodb()
    
    # Run the Flask application
    app.run(debug=True)
