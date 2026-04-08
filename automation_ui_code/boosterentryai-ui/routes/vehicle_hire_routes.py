from flask import Blueprint, request, jsonify
from config.db_config import get_connection, release_connection
import traceback
import requests
import json
from datetime import datetime

vehicle_hire_bp = Blueprint('vehicle_hire', __name__)

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = "8429056081:AAGvjIVnO9-a0I7p4-PZY-p63ZveS_EKfws"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

@vehicle_hire_bp.route('/api/vehicle-hire', methods=['POST'])
def create_vehicle_hire():
    """
    Create a vehicle hire entry for a document
    
    Expected JSON payload:
    {
        "doc_id": 123,
        "manifest_no": "ARAK2506672",
        "advance_amount": 2000.00,
        "payable_at": "BANGALORE",
        "paid_by": "Bank",
        "account": "HDFC BANK A/C-8080",
        "paymode": "UPI",
        "filling_station": "KALPATARU FILLING POINT-IOCL",
        "slip_no": "14",
        "slip_date": "2025-11-11",
        "qty": 200.000,
        "rate": 20.00,
        "amount": null or calculated value
    }
    """
    conn = None
    try:
        data = request.get_json()
        
        # Validate required fields (removed manifest_no as it will be auto-generated)
        required_fields = ['doc_id', 'advance_amount', 'payable_at', 
                          'paid_by', 'account', 'paymode', 'filling_station', 
                          'slip_no', 'slip_date', 'qty', 'rate']
        
        missing_fields = [field for field in required_fields if field not in data or not data[field]]
        if missing_fields:
            return jsonify({
                'error': f'Missing required fields: {", ".join(missing_fields)}'
            }), 400
        
        conn = get_connection()
        cur = conn.cursor()
        
        # Fetch extracted_json from doc_processing_log to get ConsignmentNo
        cur.execute(
            "SELECT extracted_json FROM doc_processing_log WHERE doc_id = %s",
            (data['doc_id'],)
        )
        result = cur.fetchone()
        
        if not result:
            return jsonify({'error': 'Document not found'}), 404
        
        extracted_json = result[0]
        
        # Parse JSON and extract ConsignmentNo
        import json
        try:
            if isinstance(extracted_json, str):
                extracted_data = json.loads(extracted_json)
            else:
                extracted_data = extracted_json
            
            consignment_no = extracted_data.get('ConsignmentNo', '')
            if not consignment_no:
                return jsonify({'error': 'ConsignmentNo not found in extracted data'}), 400
            
            # Auto-generate manifest_no: ARAK250 + ConsignmentNo
            manifest_no = f"ARAK250{consignment_no}"
            
        except Exception as e:
            return jsonify({'error': f'Failed to parse extracted_json: {str(e)}'}), 400
        
        # Insert vehicle hire record
        insert_query = """
            INSERT INTO vehicle_hire 
            (doc_id, manifest_no, advance_amount, payable_at, paid_by, account, 
             paymode, filling_station, slip_no, slip_date, qty, rate, amount)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        
        cur.execute(insert_query, (
            data['doc_id'],
            manifest_no,  # Auto-generated from ConsignmentNo
            data['advance_amount'],
            data['payable_at'],
            data['paid_by'],
            data['account'],
            data['paymode'],
            data['filling_station'],
            data['slip_no'],
            data['slip_date'],
            data['qty'],
            data['rate'],
            data.get('amount')  # Optional field
        ))
        
        vehicle_hire_id = cur.fetchone()[0]
        conn.commit()
        
        # Update document vehicle_hire_status to 'Completed'
        update_query = """
            UPDATE doc_processing_log
            SET vehicle_hire_status = 'Ready To Run',
                updated_at = CURRENT_TIMESTAMP
            WHERE doc_id = %s
        """
        cur.execute(update_query, (data['doc_id'],))
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Vehicle hire data saved successfully',
            'vehicle_hire_id': vehicle_hire_id
        }), 201
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error creating vehicle hire: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'error': f'Failed to save vehicle hire data: {str(e)}'
        }), 500
        
    finally:
        if conn:
            release_connection(conn)


@vehicle_hire_bp.route('/api/vehicle-hire/<int:doc_id>', methods=['GET'])
def get_vehicle_hire_by_doc(doc_id):
    """Get vehicle hire data for a specific document"""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        query = """
            SELECT id, doc_id, manifest_no, advance_amount, payable_at, paid_by, 
                   account, paymode, filling_station, slip_no, slip_date, qty, rate, amount,
                   created_at, updated_at
            FROM vehicle_hire
            WHERE doc_id = %s
            ORDER BY created_at DESC
            LIMIT 1
        """
        
        cur.execute(query, (doc_id,))
        row = cur.fetchone()
        
        if not row:
            return jsonify({'error': 'Vehicle hire data not found'}), 404
        
        vehicle_hire_data = {
            'id': row[0],
            'doc_id': row[1],
            'manifest_no': row[2],
            'advance_amount': float(row[3]) if row[3] else None,
            'payable_at': row[4],
            'paid_by': row[5],
            'account': row[6],
            'paymode': row[7],
            'filling_station': row[8],
            'slip_no': row[9],
            'slip_date': str(row[10]) if row[10] else None,
            'qty': float(row[11]) if row[11] else None,
            'rate': float(row[12]) if row[12] else None,
            'amount': float(row[13]) if row[13] else None,
            'created_at': str(row[14]),
            'updated_at': str(row[15])
        }
        
        return jsonify(vehicle_hire_data), 200
        
    except Exception as e:
        print(f"Error fetching vehicle hire: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'error': f'Failed to fetch vehicle hire data: {str(e)}'
        }), 500
        
    finally:
        if conn:
            release_connection(conn)


@vehicle_hire_bp.route('/api/vehicle-hire/send-message', methods=['POST'])
def initiate_telegram_session():
    """
    Initiate a Telegram session for vehicle hire confirmation
    
    Expected JSON payload:
    {
        "doc_id": 123,
        "phone_no": "9876543210"
    }
    """
    conn = None
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['doc_id', 'phone_no']
        missing_fields = [field for field in required_fields if field not in data or not data[field]]
        if missing_fields:
            return jsonify({
                'error': f'Missing required fields: {", ".join(missing_fields)}'
            }), 400
        
        conn = get_connection()
        cur = conn.cursor()
        
        # Fetch extracted_json from doc_processing_log to get ConsignmentNo
        cur.execute(
            "SELECT extracted_json FROM doc_processing_log WHERE doc_id = %s",
            (data['doc_id'],)
        )
        result = cur.fetchone()
        
        if not result:
            return jsonify({'error': 'Document not found'}), 404
        
        extracted_json = result[0]
        
        # Parse JSON and extract ConsignmentNo
        try:
            if isinstance(extracted_json, str):
                extracted_data = json.loads(extracted_json)
            else:
                extracted_data = extracted_json
            
            consignment_no = extracted_data.get('ConsignmentNo', '')
            if not consignment_no:
                return jsonify({'error': 'ConsignmentNo not found in extracted data'}), 400
            
            # Auto-generate manifest_no: ARAK250 + ConsignmentNo
            manifest_no = f"ARAK250{consignment_no}"
            
        except Exception as e:
            return jsonify({'error': f'Failed to parse extracted_json: {str(e)}'}), 400
        
        # Check if session already exists for this doc_id
        cur.execute(
            "SELECT id FROM telegram_pending_sessions WHERE doc_id = %s AND status != 'completed'",
            (data['doc_id'],)
        )
        existing = cur.fetchone()
        
        if existing:
            # Update existing session
            cur.execute("""
                UPDATE telegram_pending_sessions 
                SET phone_no = %s, manifest_no = %s, status = 'pending', updated_at = CURRENT_TIMESTAMP
                WHERE doc_id = %s AND status != 'completed'
                RETURNING id
            """, (data['phone_no'], manifest_no, data['doc_id']))
            session_id = cur.fetchone()[0]
        else:
            # Create new session
            cur.execute("""
                INSERT INTO telegram_pending_sessions 
                (doc_id, phone_no, manifest_no, status)
                VALUES (%s, %s, %s, 'pending')
                RETURNING id
            """, (data['doc_id'], data['phone_no'], manifest_no))
            session_id = cur.fetchone()[0]
        
        # Update vehicle_hire_status to 'In Progress' so it disappears from the list
        cur.execute("""
            UPDATE doc_processing_log
            SET vehicle_hire_status = 'In Progress',
                updated_at = CURRENT_TIMESTAMP
            WHERE doc_id = %s
        """, (data['doc_id'],))
        
        conn.commit()
        
        # Send WhatsApp message via Askeva API
        whatsapp_sent = False
        import sys
        print(f"📤 Attempting to send WhatsApp message to {data['phone_no']}...", flush=True)
        sys.stdout.flush()
        try:
            from whatsapp_sender import send_vehicle_hire_request_whatsapp
            print(f"📤 Calling send_vehicle_hire_request_whatsapp with phone={data['phone_no']}, manifest={manifest_no}, doc_id={data['doc_id']}", flush=True)
            sys.stdout.flush()
            whatsapp_sent = send_vehicle_hire_request_whatsapp(data['phone_no'], manifest_no, data['doc_id'])
            print(f"📤 Result: {whatsapp_sent}", flush=True)
            sys.stdout.flush()
        except Exception as wa_err:
            print(f"⚠️ WhatsApp send error (continuing): {wa_err}", flush=True)
            import traceback
            traceback.print_exc()
            sys.stdout.flush()
        
        # Return response
        return jsonify({
            'success': True,
            'message': 'Session created and WhatsApp message sent!' if whatsapp_sent else 'Session created! WhatsApp message pending.',
            'session_id': session_id,
            'manifest_no': manifest_no,
            'phone_no': data['phone_no'],
            'whatsapp_sent': whatsapp_sent
        }), 201
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error creating telegram session: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'error': f'Failed to create session: {str(e)}'
        }), 500
        
    finally:
        if conn:
            release_connection(conn)


@vehicle_hire_bp.route('/api/vehicle-hire/session/<int:doc_id>', methods=['GET'])
def get_session_status(doc_id):
    """Get the status of a telegram session for a document"""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, doc_id, phone_no, manifest_no, advance_amount, qty, status, created_at
            FROM telegram_pending_sessions 
            WHERE doc_id = %s
            ORDER BY created_at DESC
            LIMIT 1
        """, (doc_id,))
        
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'Session not found'}), 404
        
        return jsonify({
            'id': row[0],
            'doc_id': row[1],
            'phone_no': row[2],
            'manifest_no': row[3],
            'advance_amount': float(row[4]) if row[4] else None,
            'qty': float(row[5]) if row[5] else None,
            'status': row[6],
            'created_at': str(row[7])
        }), 200
        
    except Exception as e:
        print(f"Error getting session: {str(e)}")
        return jsonify({'error': f'Failed to get session: {str(e)}'}), 500
        
    finally:
        if conn:
            release_connection(conn)

