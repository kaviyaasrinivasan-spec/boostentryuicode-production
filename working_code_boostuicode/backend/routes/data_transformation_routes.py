# routes/data_transformation_routes.py
from flask import Blueprint, request, jsonify
import requests
import traceback
import os
from config.db_config import get_connection, release_connection
from datetime import datetime

data_transformation_bp = Blueprint("data_transformation_bp", __name__)

# External API endpoint - use server IP
TRANSFORMATION_API_URL = os.getenv("TRANSFORMATION_API_URL", "http://103.14.123.44:30019/api/transformations")

# ==========================================================
# ✅ API 1: Get All Transformations
# ==========================================================
@data_transformation_bp.route("/api/transformations", methods=["GET"])
def get_transformations():
    """
    Proxy GET request to fetch all transformation rules
    """
    try:
        # Forward request to the external API
        response = requests.get(TRANSFORMATION_API_URL, timeout=10)
        
        # Return the response from external API
        return jsonify(response.json()), response.status_code
        
    except requests.exceptions.RequestException as e:
        print("❌ Error fetching transformations:", str(e))
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"Failed to connect to transformation service: {str(e)}"
        }), 500
    except Exception as e:
        print("❌ Unexpected error:", str(e))
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ==========================================================
# ✅ API 2: Create New Transformation
# ==========================================================
@data_transformation_bp.route("/api/transformations", methods=["POST"])
def create_transformation():
    """
    Create a new transformation rule directly in database
    
    Expected Request Body:
    {
        "field_name": "Vehicle",
        "from_value": "TN12AB3456",
        "to_value": "TN34CD7890"
    }
    """
    conn = None
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "Request body is required"
            }), 400
        
        # Validate required fields
        field_name = data.get("field_name")
        from_value = data.get("from_value")
        to_value = data.get("to_value")
        
        if not all([field_name, from_value, to_value]):
            return jsonify({
                "success": False,
                "error": "field_name, from_value, and to_value are required"
            }), 400
        
        # Insert directly into database
        conn = get_connection()
        cur = conn.cursor()
        
        # Fix the sequence first to prevent duplicate key errors
        cur.execute("""
            SELECT setval('data_transformation_id_seq', 
                         COALESCE((SELECT MAX(id) FROM data_transformation), 0) + 1, 
                         false)
        """)
        
        # Insert with auto-generated ID
        query = """
            INSERT INTO data_transformation (field_name, from_value, to_value, created_at, updated_at)
            VALUES (%s, %s, %s, NOW(), NOW())
            RETURNING id, field_name, from_value, to_value, created_at, updated_at
        """
        cur.execute(query, (field_name, from_value, to_value))
        row = cur.fetchone()
        conn.commit()
        
        result = {
            'id': row[0],
            'field_name': row[1],
            'from_value': row[2],
            'to_value': row[3],
            'created_at': row[4].isoformat() if row[4] else None,
            'updated_at': row[5].isoformat() if row[5] else None
        }
        
        cur.close()
        release_connection(conn)
        
        print(f"✅ Created transformation: {result}")
        
        return jsonify({
            'success': True,
            'data': result,
            'message': 'Transformation created successfully'
        }), 201
        
    except Exception as e:
        print("❌ Error creating transformation:", str(e))
        traceback.print_exc()
        if conn:
            conn.rollback()
            release_connection(conn)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ==========================================================
# ✅ API 3: Update Transformation
# ==========================================================
@data_transformation_bp.route("/api/transformations/<int:transformation_id>", methods=["PUT"])
def update_transformation(transformation_id):
    """
    Proxy PUT request to update an existing transformation rule
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "Request body is required"
            }), 400
        
        # Forward request to the external API
        url = f"{TRANSFORMATION_API_URL}/{transformation_id}"
        response = requests.put(
            url,
            json=data,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        # Return the response from external API
        return jsonify(response.json()), response.status_code
        
    except requests.exceptions.RequestException as e:
        print("❌ Error updating transformation:", str(e))
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"Failed to connect to transformation service: {str(e)}"
        }), 500
    except Exception as e:
        print("❌ Unexpected error:", str(e))
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ==========================================================
# ✅ API 4: Delete Transformation
# ==========================================================
@data_transformation_bp.route("/api/transformations/<int:transformation_id>", methods=["DELETE"])
def delete_transformation(transformation_id):
    """
    Proxy DELETE request to remove a transformation rule
    """
    try:
        # Forward request to the external API
        url = f"{TRANSFORMATION_API_URL}/{transformation_id}"
        response = requests.delete(url, timeout=10)
        
        # Return the response from external API
        return jsonify(response.json()), response.status_code
        
    except requests.exceptions.RequestException as e:
        print("❌ Error deleting transformation:", str(e))
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"Failed to connect to transformation service: {str(e)}"
        }), 500
    except Exception as e:
        print("❌ Unexpected error:", str(e))
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ==========================================================
# ✅ API 5: Get Statistics
# ==========================================================
@data_transformation_bp.route("/api/transformations/stats", methods=["GET"])
def get_stats():
    """
    Get transformation statistics
    """
    try:
        url = f"{TRANSFORMATION_API_URL}/stats"
        response = requests.get(url, timeout=10)
        
        return jsonify(response.json()), response.status_code
        
    except requests.exceptions.RequestException as e:
        print("❌ Error fetching stats:", str(e))
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"Failed to connect to transformation service: {str(e)}"
        }), 500
    except Exception as e:
        print("❌ Unexpected error:", str(e))
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
