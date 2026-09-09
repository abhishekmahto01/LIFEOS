import datetime
from flask import Blueprint, request, jsonify
from database.db import get_connection
from utils.helpers import module_required, is_admin_user

job_blueprint = Blueprint('jobs', __name__)

def parse_date(date_val):
    if not date_val or date_val == "":
        return None
    return date_val

def get_current_job_user_id(data=None, current_user=None):
    if current_user and isinstance(current_user, dict) and "user_id" in current_user:
        return int(current_user["user_id"])
    req_user = getattr(request, "current_user", None)
    if req_user and isinstance(req_user, dict) and "user_id" in req_user:
        return int(req_user["user_id"])
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            from utils.jwt_handler import decode_token
            token = auth_header.split(" ")[1]
            payload = decode_token(token)
            if "user_id" in payload:
                return int(payload["user_id"])
        except Exception:
            pass
    if data and isinstance(data, dict) and data.get('user_id'):
        try:
            return int(data.get('user_id'))
        except (ValueError, TypeError):
            pass
    return None

@job_blueprint.route('/api/jobs', methods=['POST'])
@module_required("career")
def add_job_entry(current_user=None):
    data = request.get_json() or {}
    organization_name = data.get('organization_name', '').strip()
    post_name = data.get('post_name', '').strip()

    if not organization_name or not post_name:
        return jsonify({"success": False, "error": "Organization Name and Job Role/Post are required."}), 400

    job_no = data.get('job_no', '').strip()
    if not job_no:
        timestamp_suffix = datetime.datetime.now().strftime("%y%m%d%H%M%S")
        job_no = f"JOB-{timestamp_suffix}"

    user_id = get_current_job_user_id(data, current_user)

    try:
        conn = get_connection()
        cur = conn.cursor()

        insert_mt_query = """
            INSERT INTO job_apply_mt (
                job_no, organization_name, post_name, is_govt,
                application_start_date, application_end_date, exam_date,
                official_url, amount, status, remarks,
                location, work_mode, job_portal, salary_range,
                resume_version, skills, hr_contact, user_id,
                created_date, updated_at
            )
            VALUES (
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            RETURNING id, created_date;
        """

        app_date = parse_date(data.get('application_start_date')) or datetime.date.today().isoformat()
        end_date = parse_date(data.get('application_end_date'))
        exam_date = parse_date(data.get('exam_date'))

        cur.execute(insert_mt_query, (
            job_no,
            organization_name,
            post_name,
            bool(data.get('is_govt', False)),
            app_date,
            end_date,
            exam_date,
            data.get('official_url', '').strip() or None,
            float(data.get('amount') or 0.0),
            data.get('status', 'Applied') or 'Applied',
            data.get('remarks', '').strip() or None,
            data.get('location', '').strip() or None,
            data.get('work_mode', 'Remote') or 'Remote',
            data.get('job_portal', 'LinkedIn') or 'LinkedIn',
            data.get('salary_range', '').strip() or None,
            data.get('resume_version', '').strip() or None,
            data.get('skills', '').strip() or None,
            data.get('hr_contact', '').strip() or None,
            get_current_job_user_id(data)
        ))

        new_row = cur.fetchone()
        mt_id = new_row[0]
        created_date = new_row[1]

        # Automatically record initial activity in Detail Table
        insert_dt_query = """
            INSERT INTO job_apply_dt (mt_id, activity_name, activity_status, activity_date, remarks, created_date)
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP);
        """
        cur.execute(insert_dt_query, (
            mt_id,
            'Application Submitted',
            data.get('status', 'Applied') or 'Applied',
            app_date,
            data.get('remarks') or f"Applied for {post_name} at {organization_name}"
        ))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "success": True,
            "message": "Job application recorded successfully!",
            "id": mt_id,
            "created_date": str(created_date)
        }), 201

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@job_blueprint.route('/api/jobs/history', methods=['GET'])
@module_required("career")
def get_job_history(current_user=None):
    search = request.args.get('search', '').strip()
    status = request.args.get('status', '').strip()
    work_mode = request.args.get('work_mode', '').strip()
    job_portal = request.args.get('job_portal', '').strip()
    user_id = get_current_job_user_id(None, current_user)

    try:
        conn = get_connection()
        cur = conn.cursor()

        query = """
            SELECT 
                id, job_no, organization_name, post_name, is_govt,
                application_start_date, application_end_date, exam_date,
                official_url, amount, status, remarks, created_date,
                location, work_mode, job_portal, salary_range,
                resume_version, skills, hr_contact, user_id, updated_at
            FROM job_apply_mt
            WHERE 1=1
        """
        params = []

        if not is_admin_user(current_user) and user_id:
            query += " AND (user_id = %s OR user_id IS NULL)"
            params.append(user_id)

        if search:
            query += """
                AND (
                    organization_name ILIKE %s 
                    OR post_name ILIKE %s 
                    OR skills ILIKE %s 
                    OR location ILIKE %s 
                    OR remarks ILIKE %s
                )
            """
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param, search_param, search_param])

        if status and status != 'All':
            query += " AND status = %s"
            params.append(status)

        if work_mode and work_mode != 'All':
            query += " AND work_mode = %s"
            params.append(work_mode)

        if job_portal and job_portal != 'All':
            query += " AND job_portal = %s"
            params.append(job_portal)

        query += " ORDER BY created_date DESC, id DESC"

        cur.execute(query, tuple(params))
        rows = cur.fetchall()

        jobs_list = []
        for row in rows:
            jobs_list.append({
                "id": row[0],
                "job_no": row[1],
                "organization_name": row[2],
                "post_name": row[3],
                "is_govt": bool(row[4]),
                "application_start_date": str(row[5]) if row[5] else None,
                "application_end_date": str(row[6]) if row[6] else None,
                "exam_date": str(row[7]) if row[7] else None,
                "official_url": row[8],
                "amount": float(row[9]) if row[9] else 0.0,
                "status": row[10] or "Applied",
                "remarks": row[11],
                "created_date": str(row[12]) if row[12] else None,
                "location": row[13],
                "work_mode": row[14] or "Remote",
                "job_portal": row[15] or "LinkedIn",
                "salary_range": row[16],
                "resume_version": row[17],
                "skills": row[18],
                "hr_contact": row[19],
                "user_id": row[20],
                "updated_at": str(row[21]) if row[21] else None
            })

        cur.close()
        conn.close()

        return jsonify({"success": True, "jobs": jobs_list, "total": len(jobs_list)}), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@job_blueprint.route('/api/jobs/stats', methods=['GET'])
@module_required("career")
def get_job_stats(current_user=None):
    user_id = get_current_job_user_id(None, current_user)
    try:
        conn = get_connection()
        cur = conn.cursor()

        where_clause = ""
        params = []
        if not is_admin_user(current_user) and user_id:
            where_clause = " WHERE (user_id = %s OR user_id IS NULL)"
            params = [user_id]

        cur.execute(f"SELECT COUNT(*) FROM job_apply_mt{where_clause}", tuple(params))
        total = cur.fetchone()[0]

        cur.execute(f"""
            SELECT status, COUNT(*) 
            FROM job_apply_mt 
            {where_clause}
            GROUP BY status
        """, tuple(params))
        status_rows = cur.fetchall()
        status_map = {row[0] or 'Applied': row[1] for row in status_rows}

        cur.execute(f"""
            SELECT work_mode, COUNT(*) 
            FROM job_apply_mt 
            {where_clause}
            GROUP BY work_mode
        """, tuple(params))
        work_mode_rows = cur.fetchall()
        work_mode_map = {row[0] or 'Remote': row[1] for row in work_mode_rows}

        cur.execute(f"""
            SELECT post_name, COUNT(*) as cnt 
            FROM job_apply_mt 
            {where_clause}
            GROUP BY post_name 
            ORDER BY cnt DESC 
            LIMIT 5
        """, tuple(params))
        top_roles = [{"role": row[0], "count": row[1]} for row in cur.fetchall()]

        cur.execute(f"""
            SELECT job_portal, COUNT(*) as cnt 
            FROM job_apply_mt 
            {where_clause}
            GROUP BY job_portal 
            ORDER BY cnt DESC 
            LIMIT 5
        """, tuple(params))
        top_portals = [{"portal": row[0] or 'Direct', "count": row[1]} for row in cur.fetchall()]

        interview_count = status_map.get('Interview', 0)
        interview_rate = round((interview_count / total * 100), 1) if total > 0 else 0.0

        cur.execute(f"""
            SELECT id, organization_name, post_name, status, created_date 
            FROM job_apply_mt 
            {where_clause}
            ORDER BY created_date DESC, id DESC 
            LIMIT 5
        """, tuple(params))
        recent_rows = cur.fetchall()
        recent_jobs = [{
            "id": r[0],
            "organization_name": r[1],
            "post_name": r[2],
            "status": r[3] or 'Applied',
            "created_date": str(r[4]) if r[4] else None
        } for r in recent_rows]

        cur.close()
        conn.close()

        return jsonify({
            "success": True,
            "metrics": {
                "total_applied": total,
                "applied": status_map.get('Applied', 0),
                "shortlisted": status_map.get('Shortlisted', 0),
                "interview": interview_count,
                "selected": status_map.get('Selected', 0),
                "rejected": status_map.get('Rejected', 0),
                "active_pipeline": status_map.get('Applied', 0) + status_map.get('Shortlisted', 0) + interview_count
            },
            "raw_statuses": status_map,
            "work_mode_breakdown": work_mode_map,
            "top_roles": top_roles,
            "top_portals": top_portals,
            "interview_rate": interview_rate,
            "recent_jobs": recent_jobs
        }), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@job_blueprint.route('/api/jobs/<int:job_id>', methods=['GET'])
@module_required("career")
def get_single_job(job_id, current_user=None):
    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT 
                id, job_no, organization_name, post_name, is_govt,
                application_start_date, application_end_date, exam_date,
                official_url, amount, status, remarks, created_date,
                location, work_mode, job_portal, salary_range,
                resume_version, skills, hr_contact, user_id, updated_at
            FROM job_apply_mt
            WHERE id = %s
        """, (job_id,))
        row = cur.fetchone()

        if not row:
            cur.close()
            conn.close()
            return jsonify({"success": False, "error": "Job application not found."}), 404

        job = {
            "id": row[0],
            "job_no": row[1],
            "organization_name": row[2],
            "post_name": row[3],
            "is_govt": bool(row[4]),
            "application_start_date": str(row[5]) if row[5] else None,
            "application_end_date": str(row[6]) if row[6] else None,
            "exam_date": str(row[7]) if row[7] else None,
            "official_url": row[8],
            "amount": float(row[9]) if row[9] else 0.0,
            "status": row[10] or "Applied",
            "remarks": row[11],
            "created_date": str(row[12]) if row[12] else None,
            "location": row[13],
            "work_mode": row[14] or "Remote",
            "job_portal": row[15] or "LinkedIn",
            "salary_range": row[16],
            "resume_version": row[17],
            "skills": row[18],
            "hr_contact": row[19],
            "user_id": row[20],
            "updated_at": str(row[21]) if row[21] else None
        }

        # Fetch activities/timeline
        cur.execute("""
            SELECT id, mt_id, activity_name, activity_status, activity_date, remarks, created_date
            FROM job_apply_dt
            WHERE mt_id = %s
            ORDER BY activity_date DESC, created_date DESC, id DESC
        """, (job_id,))
        act_rows = cur.fetchall()

        activities = []
        for a in act_rows:
            activities.append({
                "id": a[0],
                "mt_id": a[1],
                "activity_name": a[2],
                "activity_status": a[3],
                "activity_date": str(a[4]) if a[4] else None,
                "remarks": a[5],
                "created_date": str(a[6]) if a[6] else None
            })

        job["activities"] = activities

        cur.close()
        conn.close()
        return jsonify({"success": True, "job": job}), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@job_blueprint.route('/api/jobs/<int:job_id>', methods=['PUT'])
@module_required("career")
def update_job_entry(job_id, current_user=None):
    data = request.get_json() or {}
    try:
        conn = get_connection()
        cur = conn.cursor()

        # Check existing job
        cur.execute("SELECT status FROM job_apply_mt WHERE id = %s", (job_id,))
        prev_job = cur.fetchone()
        if not prev_job:
            cur.close()
            conn.close()
            return jsonify({"success": False, "error": "Job application not found."}), 404

        old_status = prev_job[0]
        new_status = data.get('status', old_status) or old_status

        app_date = parse_date(data.get('application_start_date'))
        end_date = parse_date(data.get('application_end_date'))
        exam_date = parse_date(data.get('exam_date'))

        update_query = """
            UPDATE job_apply_mt
            SET 
                job_no = %s,
                organization_name = %s,
                post_name = %s,
                is_govt = %s,
                application_start_date = %s,
                application_end_date = %s,
                exam_date = %s,
                official_url = %s,
                amount = %s,
                status = %s,
                remarks = %s,
                location = %s,
                work_mode = %s,
                job_portal = %s,
                salary_range = %s,
                resume_version = %s,
                skills = %s,
                hr_contact = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """

        cur.execute(update_query, (
            data.get('job_no') or None,
            data.get('organization_name'),
            data.get('post_name'),
            bool(data.get('is_govt', False)),
            app_date,
            end_date,
            exam_date,
            data.get('official_url', '').strip() or None,
            float(data.get('amount') or 0.0),
            new_status,
            data.get('remarks', '').strip() or None,
            data.get('location', '').strip() or None,
            data.get('work_mode', 'Remote') or 'Remote',
            data.get('job_portal', 'LinkedIn') or 'LinkedIn',
            data.get('salary_range', '').strip() or None,
            data.get('resume_version', '').strip() or None,
            data.get('skills', '').strip() or None,
            data.get('hr_contact', '').strip() or None,
            job_id
        ))

        # If status changed or explicit activity passed, record timeline activity
        if old_status != new_status or data.get('log_activity'):
            activity_name = data.get('activity_name') or f"Status changed to {new_status}"
            cur.execute("""
                INSERT INTO job_apply_dt (mt_id, activity_name, activity_status, activity_date, remarks, created_date)
                VALUES (%s, %s, %s, CURRENT_DATE, %s, CURRENT_TIMESTAMP)
            """, (
                job_id,
                activity_name,
                new_status,
                data.get('activity_remarks') or f"Status updated from {old_status} to {new_status}"
            ))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"success": True, "message": "Job application updated successfully!"}), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@job_blueprint.route('/api/jobs/<int:job_id>', methods=['DELETE'])
@module_required("career")
def delete_job_entry(job_id, current_user=None):
    try:
        conn = get_connection()
        cur = conn.cursor()

        # Delete activity history first just in case CASCADE isn't enabled
        cur.execute("DELETE FROM job_apply_dt WHERE mt_id = %s", (job_id,))
        cur.execute("DELETE FROM job_apply_mt WHERE id = %s", (job_id,))
        deleted_count = cur.rowcount

        conn.commit()
        cur.close()
        conn.close()

        if deleted_count == 0:
            return jsonify({"success": False, "error": "Job application not found."}), 404

        return jsonify({"success": True, "message": "Job application deleted successfully."}), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@job_blueprint.route('/api/jobs/<int:job_id>/activity', methods=['POST'])
@module_required("career")
def add_job_activity(job_id, current_user=None):
    data = request.get_json() or {}
    activity_name = data.get('activity_name', '').strip()

    if not activity_name:
        return jsonify({"success": False, "error": "Activity name is required."}), 400

    try:
        conn = get_connection()
        cur = conn.cursor()

        activity_date = parse_date(data.get('activity_date')) or datetime.date.today().isoformat()
        activity_status = data.get('activity_status')

        cur.execute("""
            INSERT INTO job_apply_dt (mt_id, activity_name, activity_status, activity_date, remarks, created_date)
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            RETURNING id, created_date;
        """, (
            job_id,
            activity_name,
            activity_status,
            activity_date,
            data.get('remarks', '').strip() or None
        ))

        new_act = cur.fetchone()

        # If status updated as part of activity, update master table as well
        if activity_status:
            cur.execute("""
                UPDATE job_apply_mt 
                SET status = %s, updated_at = CURRENT_TIMESTAMP 
                WHERE id = %s
            """, (activity_status, job_id))
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "success": True,
            "message": "Activity log added successfully!",
            "activity": {
                "id": new_act[0],
                "mt_id": job_id,
                "activity_name": activity_name,
                "activity_status": activity_status,
                "activity_date": activity_date,
                "remarks": data.get('remarks'),
                "created_date": str(new_act[1])
            }
        }), 201

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500