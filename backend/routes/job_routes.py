from flask import Blueprint, request, jsonify
# Assume 'db' is your database connection helper from database/db.py
from database.db import get_db_connection 

job_blueprint = Blueprint('jobs', __name__)

# 1. API to Save Job Entry (MT and DT together)
@job_blueprint.route('/api/jobs', methods=['POST'])
def add_job_entry():
    data = request.json
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Insert into Master Table
        insert_mt_query = """
            INSERT INTO job_apply_mt 
            (job_no, organization_name, post_name, is_govt, application_start_date, application_end_date, exam_date, official_url, amount, status, remarks)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        cursor.execute(insert_mt_query, (
            data.get('job_no'),
            data.get('organization_name'),
            data.get('post_name'),
            1 if data.get('is_govt') else 0, # Convert Boolean to BIT
            data.get('application_start_date'),
            data.get('application_end_date'),
            data.get('exam_date'),
            data.get('official_url'),
            data.get('amount', 0.00),
            data.get('status', 'Applied'),
            data.get('remarks')
        ))
        
        mt_id = cursor.fetchone()[0]
        
        # Automatically insert initial activity in Detail Table
        insert_dt_query = """
            INSERT INTO job_apply_dt (mt_id, activity_name, activity_status, activity_date, remarks)
            VALUES (?, ?, ?, ?, ?)
        """
        cursor.execute(insert_dt_query, (
            mt_id,
            'Application Submitted',
            data.get('status', 'Applied'),
            data.get('application_start_date'),
            'Initial entry from job entry screen'
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"message": "Job entry saved successfully!", "id": mt_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 2. API to Get Job History
@job_blueprint.route('/api/jobs/history', methods=['GET'])
def get_job_history():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT id, job_no, organization_name, post_name, is_govt, 
                   application_start_date, application_end_date, exam_date, 
                   official_url, amount, status, remarks, created_date 
            FROM job_apply_mt 
            ORDER BY created_date DESC
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        
        # Formatting rows into JSON list
        jobs_list = []
        for row in rows:
            jobs_list.append({
                "id": row[0],
                "job_no": row[1],
                "organization_name": row[2],
                "post_name": row[3],
                "is_govt": bool(row[4]), # BIT to Boolean
                "application_start_date": str(row[5]) if row[5] else None,
                "application_end_date": str(row[6]) if row[6] else None,
                "exam_date": str(row[7]) if row[7] else None,
                "official_url": row[8],
                "amount": float(row[9]) if row[9] else 0.0,
                "status": row[10],
                "remarks": row[11],
                "created_date": str(row[12])
            })
            
        cursor.close()
        conn.close()
        return jsonify(jobs_list), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500