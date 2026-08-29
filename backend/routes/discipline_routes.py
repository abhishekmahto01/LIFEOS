import calendar
import datetime
import json
import psycopg2
from psycopg2.extras import Json
from flask import Blueprint, request, jsonify
from database.db import get_connection

discipline_blueprint = Blueprint('discipline', __name__)

HABIT_NAMES = ["Gym", "Job", "Study", "Project"]

def get_today_date():
    return datetime.date.today()

def calculate_score(gym, job, study, project):
    completed = sum([1 for h in [gym, job, study, project] if h])
    return round((completed / 4.0) * 100, 2)

def get_user_id():
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

    uid = request.args.get('user_id')
    if not uid:
        json_data = request.get_json(silent=True)
        if json_data and isinstance(json_data, dict):
            uid = json_data.get('user_id')
    try:
        return int(uid) if uid else 1
    except (ValueError, TypeError):
        return 1

# -----------------------------------------------------------------------------
# 1. GET TODAY'S STATUS & SUMMARY (For Main LifeOS Dashboard Card & Top Widget)
# -----------------------------------------------------------------------------
@discipline_blueprint.route('/api/discipline/today', methods=['GET'])
def get_today_summary():
    user_id = get_user_id()
    today = get_today_date()
    today_str = today.isoformat()

    try:
        conn = get_connection()
        cur = conn.cursor()

        # Fetch today's record
        cur.execute("""
            SELECT gym_completed, job_completed, study_completed, project_completed, daily_score, notes
            FROM discipline_daily
            WHERE user_id = %s AND date = %s;
        """, (user_id, today))
        row = cur.fetchone()

        today_data = {
            "date": today_str,
            "gym_completed": bool(row[0]) if row else False,
            "job_completed": bool(row[1]) if row else False,
            "study_completed": bool(row[2]) if row else False,
            "project_completed": bool(row[3]) if row else False,
            "daily_score": float(row[4]) if row else 0.0,
            "notes": row[5] if row else ""
        }

        # Fetch current month stats
        first_day_month = datetime.date(today.year, today.month, 1)
        cur.execute("""
            SELECT 
                COUNT(*) as logged_days,
                SUM(CASE WHEN gym_completed THEN 1 ELSE 0 END) as gym_cnt,
                SUM(CASE WHEN job_completed THEN 1 ELSE 0 END) as job_cnt,
                SUM(CASE WHEN study_completed THEN 1 ELSE 0 END) as study_cnt,
                SUM(CASE WHEN project_completed THEN 1 ELSE 0 END) as proj_cnt,
                AVG(daily_score) as avg_score
            FROM discipline_daily
            WHERE user_id = %s AND date >= %s AND date <= %s;
        """, (user_id, first_day_month, today))
        m_row = cur.fetchone()
        
        days_in_month_so_far = max(today.day, 1)
        total_activities_month = (m_row[1] or 0) + (m_row[2] or 0) + (m_row[3] or 0) + (m_row[4] or 0) if m_row else 0
        monthly_score = round((total_activities_month / (days_in_month_so_far * 4.0)) * 100, 1) if days_in_month_so_far > 0 else 0.0

        # Calculate Current Streak
        cur.execute("""
            SELECT date, daily_score
            FROM discipline_daily
            WHERE user_id = %s AND date <= %s
            ORDER BY date DESC;
        """, (user_id, today))
        history_rows = cur.fetchall()

        history_map = {r[0]: float(r[1]) for r in history_rows}
        current_streak = 0
        check_date = today

        # If today is not disciplined yet, check if yesterday was part of streak
        if history_map.get(today, 0.0) < 75.0:
            check_date = today - datetime.timedelta(days=1)

        while check_date in history_map and history_map[check_date] >= 75.0:
            current_streak += 1
            check_date -= datetime.timedelta(days=1)

        # 2026 Mission Progress
        start_of_year = datetime.date(2026, 1, 1)
        end_of_year = datetime.date(2026, 12, 31)
        total_year_days = 365
        days_passed_2026 = max((today - start_of_year).days + 1, 0)
        days_remaining_2026 = max((end_of_year - today).days, 0)

        # Overall 2026 Discipline Score
        cur.execute("""
            SELECT 
                COUNT(*) as logged_days,
                SUM(CASE WHEN gym_completed THEN 1 ELSE 0 END) as gym_cnt,
                SUM(CASE WHEN job_completed THEN 1 ELSE 0 END) as job_cnt,
                SUM(CASE WHEN study_completed THEN 1 ELSE 0 END) as study_cnt,
                SUM(CASE WHEN project_completed THEN 1 ELSE 0 END) as proj_cnt,
                COUNT(CASE WHEN daily_score = 100 THEN 1 END) as perfect_days,
                COUNT(CASE WHEN daily_score >= 75 THEN 1 END) as disciplined_days
            FROM discipline_daily
            WHERE user_id = %s AND date >= %s AND date <= %s;
        """, (user_id, start_of_year, today))
        y_row = cur.fetchone()

        total_activities_year = (y_row[1] or 0) + (y_row[2] or 0) + (y_row[3] or 0) + (y_row[4] or 0) if y_row else 0
        possible_activities_year = max(days_passed_2026, 1) * 4
        yearly_score = round((total_activities_year / possible_activities_year) * 100, 1) if possible_activities_year > 0 else 0.0

        cur.close()
        conn.close()

        return jsonify({
            "success": True,
            "today": today_data,
            "today_completion": today_data["daily_score"],
            "current_streak": current_streak,
            "monthly_completion": monthly_score,
            "current_month_name": today.strftime("%B"),
            "year_2026_progress": {
                "days_passed": days_passed_2026,
                "days_remaining": days_remaining_2026,
                "yearly_score": yearly_score,
                "perfect_days": y_row[5] if y_row else 0,
                "disciplined_days": y_row[6] if y_row else 0,
                "total_activities_completed": total_activities_year
            }
        }), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# -----------------------------------------------------------------------------
# 2. GET OR TOGGLE SINGLE DAY
# -----------------------------------------------------------------------------
@discipline_blueprint.route('/api/discipline/day/<date_str>', methods=['GET'])
def get_day_data(date_str):
    user_id = get_user_id()
    try:
        req_date = datetime.date.fromisoformat(date_str)
    except ValueError:
        return jsonify({"success": False, "error": "Invalid date format. Use YYYY-MM-DD"}), 400

    today = get_today_date()
    is_future = req_date > today

    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT gym_completed, job_completed, study_completed, project_completed, daily_score, notes
            FROM discipline_daily
            WHERE user_id = %s AND date = %s;
        """, (user_id, req_date))
        row = cur.fetchone()

        cur.close()
        conn.close()

        return jsonify({
            "success": True,
            "data": {
                "date": date_str,
                "gym_completed": bool(row[0]) if row else False,
                "job_completed": bool(row[1]) if row else False,
                "study_completed": bool(row[2]) if row else False,
                "project_completed": bool(row[3]) if row else False,
                "daily_score": float(row[4]) if row else 0.0,
                "notes": row[5] if row else "",
                "is_future": is_future,
                "is_today": req_date == today
            }
        }), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@discipline_blueprint.route('/api/discipline/day/<date_str>', methods=['POST'])
def save_day_data(date_str):
    user_id = get_user_id()
    try:
        req_date = datetime.date.fromisoformat(date_str)
    except ValueError:
        return jsonify({"success": False, "error": "Invalid date format. Use YYYY-MM-DD"}), 400

    today = get_today_date()
    if req_date > today:
        return jsonify({"success": False, "error": "Cannot record discipline for future dates."}), 400

    data = request.get_json() or {}
    gym = bool(data.get('gym_completed', False))
    job = bool(data.get('job_completed', False))
    study = bool(data.get('study_completed', False))
    project = bool(data.get('project_completed', False))
    notes = data.get('notes', '').strip() if data.get('notes') else None

    daily_score = calculate_score(gym, job, study, project)

    try:
        conn = get_connection()
        cur = conn.cursor()

        upsert_query = """
            INSERT INTO discipline_daily (
                user_id, date, gym_completed, job_completed, study_completed, project_completed, daily_score, notes, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id, date) DO UPDATE
            SET 
                gym_completed = EXCLUDED.gym_completed,
                job_completed = EXCLUDED.job_completed,
                study_completed = EXCLUDED.study_completed,
                project_completed = EXCLUDED.project_completed,
                daily_score = EXCLUDED.daily_score,
                notes = COALESCE(EXCLUDED.notes, discipline_daily.notes),
                updated_at = CURRENT_TIMESTAMP
            RETURNING id, daily_score;
        """

        cur.execute(upsert_query, (
            user_id, req_date, gym, job, study, project, daily_score, notes
        ))
        res = cur.fetchone()
        conn.commit()

        cur.close()
        conn.close()

        return jsonify({
            "success": True,
            "message": "Discipline status updated successfully!",
            "data": {
                "id": res[0],
                "date": date_str,
                "gym_completed": gym,
                "job_completed": job,
                "study_completed": study,
                "project_completed": project,
                "daily_score": float(res[1]),
                "notes": notes or ""
            }
        }), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# -----------------------------------------------------------------------------
# 3. GET MONTH CALENDAR DATA (Day-wise grid + Heatmap intensity)
# -----------------------------------------------------------------------------
@discipline_blueprint.route('/api/discipline/month/<int:year>/<int:month>', methods=['GET'])
def get_month_calendar(year, month):
    user_id = get_user_id()
    if month < 1 or month > 12:
        return jsonify({"success": False, "error": "Invalid month"}), 400

    today = get_today_date()
    num_days = calendar.monthrange(year, month)[1]
    start_date = datetime.date(year, month, 1)
    end_date = datetime.date(year, month, num_days)

    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT date, gym_completed, job_completed, study_completed, project_completed, daily_score, notes
            FROM discipline_daily
            WHERE user_id = %s AND date >= %s AND date <= %s
            ORDER BY date ASC;
        """, (user_id, start_date, end_date))
        rows = cur.fetchall()

        cur.close()
        conn.close()

        db_map = {}
        for r in rows:
            d_str = r[0].isoformat()
            db_map[d_str] = {
                "gym_completed": bool(r[1]),
                "job_completed": bool(r[2]),
                "study_completed": bool(r[3]),
                "project_completed": bool(r[4]),
                "daily_score": float(r[5]),
                "notes": r[6] or ""
            }

        days_list = []
        gym_total = 0
        job_total = 0
        study_total = 0
        project_total = 0
        perfect_days = 0
        disciplined_days = 0
        elapsed_days_count = 0

        for day in range(1, num_days + 1):
            d_obj = datetime.date(year, month, day)
            d_str = d_obj.isoformat()
            is_future = d_obj > today
            is_today = d_obj == today
            rec = db_map.get(d_str, {
                "gym_completed": False,
                "job_completed": False,
                "study_completed": False,
                "project_completed": False,
                "daily_score": 0.0,
                "notes": ""
            })

            if not is_future:
                elapsed_days_count += 1
                if rec["gym_completed"]: gym_total += 1
                if rec["job_completed"]: job_total += 1
                if rec["study_completed"]: study_total += 1
                if rec["project_completed"]: project_total += 1
                if rec["daily_score"] == 100.0: perfect_days += 1
                if rec["daily_score"] >= 75.0: disciplined_days += 1

            days_list.append({
                "day_number": day,
                "date": d_str,
                "weekday": d_obj.strftime("%a"),
                "weekday_index": d_obj.weekday(), # 0 = Monday, 6 = Sunday
                "gym_completed": rec["gym_completed"],
                "job_completed": rec["job_completed"],
                "study_completed": rec["study_completed"],
                "project_completed": rec["project_completed"],
                "daily_score": rec["daily_score"],
                "notes": rec["notes"],
                "is_future": is_future,
                "is_today": is_today,
                "is_perfect": rec["daily_score"] == 100.0,
                "is_disciplined": rec["daily_score"] >= 75.0
            })

        total_activities_month = gym_total + job_total + study_total + project_total
        possible_activities = max(elapsed_days_count, 1) * 4
        month_score = round((total_activities_month / possible_activities) * 100, 1) if possible_activities > 0 else 0.0

        return jsonify({
            "success": True,
            "year": year,
            "month": month,
            "month_name": start_date.strftime("%B"),
            "days": days_list,
            "first_day_weekday": start_date.weekday(), # 0 = Monday
            "summary": {
                "days_in_month": num_days,
                "elapsed_days": elapsed_days_count,
                "monthly_score": month_score,
                "perfect_days": perfect_days,
                "disciplined_days": disciplined_days,
                "gym_consistency": round((gym_total / max(elapsed_days_count, 1)) * 100, 1),
                "job_consistency": round((job_total / max(elapsed_days_count, 1)) * 100, 1),
                "study_consistency": round((study_total / max(elapsed_days_count, 1)) * 100, 1),
                "project_consistency": round((project_total / max(elapsed_days_count, 1)) * 100, 1),
            }
        }), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# -----------------------------------------------------------------------------
# 4. GET FULL YEAR 365-DAY HEATMAP DATA
# -----------------------------------------------------------------------------
@discipline_blueprint.route('/api/discipline/year/<int:year>', methods=['GET'])
def get_year_heatmap(year):
    user_id = get_user_id()
    today = get_today_date()
    start_date = datetime.date(year, 1, 1)
    end_date = datetime.date(year, 12, 31)

    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT date, daily_score, gym_completed, job_completed, study_completed, project_completed
            FROM discipline_daily
            WHERE user_id = %s AND date >= %s AND date <= %s
            ORDER BY date ASC;
        """, (user_id, start_date, end_date))
        rows = cur.fetchall()

        cur.close()
        conn.close()

        db_map = {r[0].isoformat(): {
            "score": float(r[1]),
            "gym": bool(r[2]),
            "job": bool(r[3]),
            "study": bool(r[4]),
            "project": bool(r[5])
        } for r in rows}

        heatmap_days = []
        cur_date = start_date
        total_activities = 0
        elapsed_days = 0
        perfect_days = 0
        disciplined_days = 0

        while cur_date <= end_date:
            d_str = cur_date.isoformat()
            is_future = cur_date > today
            is_today = cur_date == today

            rec = db_map.get(d_str, {"score": 0.0, "gym": False, "job": False, "study": False, "project": False})
            completed_count = sum([1 for k in ["gym", "job", "study", "project"] if rec[k]])

            if not is_future:
                elapsed_days += 1
                total_activities += completed_count
                if rec["score"] == 100.0: perfect_days += 1
                if rec["score"] >= 75.0: disciplined_days += 1

            heatmap_days.append({
                "date": d_str,
                "month": cur_date.month,
                "month_name": cur_date.strftime("%b"),
                "day": cur_date.day,
                "weekday": cur_date.weekday(), # 0 = Mon, 6 = Sun
                "score": rec["score"],
                "completed_count": completed_count,
                "is_future": is_future,
                "is_today": is_today
            })

            cur_date += datetime.timedelta(days=1)

        yearly_score = round((total_activities / (max(elapsed_days, 1) * 4.0)) * 100, 1)

        return jsonify({
            "success": True,
            "year": year,
            "days": heatmap_days,
            "summary": {
                "elapsed_days": elapsed_days,
                "total_days": len(heatmap_days),
                "yearly_score": yearly_score,
                "perfect_days": perfect_days,
                "disciplined_days": disciplined_days,
                "total_activities_completed": total_activities
            }
        }), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# -----------------------------------------------------------------------------
# 5. GET FULL QUARTERLY ANALYTICS, STREAKS, HABIT INSIGHTS & BMW S1000 PROGRESS
# -----------------------------------------------------------------------------
@discipline_blueprint.route('/api/discipline/analytics/<int:year>', methods=['GET'])
def get_analytics(year):
    user_id = get_user_id()
    today = get_today_date()
    start_date = datetime.date(year, 1, 1)
    end_date = datetime.date(year, 12, 31)

    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT date, gym_completed, job_completed, study_completed, project_completed, daily_score
            FROM discipline_daily
            WHERE user_id = %s AND date >= %s AND date <= %s
            ORDER BY date ASC;
        """, (user_id, start_date, end_date))
        rows = cur.fetchall()

        cur.close()
        conn.close()

        db_map = {}
        for r in rows:
            db_map[r[0]] = {
                "gym": bool(r[1]),
                "job": bool(r[2]),
                "study": bool(r[3]),
                "project": bool(r[4]),
                "score": float(r[5])
            }

        # 1. Streaks Calculations
        cur_date = start_date
        all_dates_until_today = []
        while cur_date <= min(today, end_date):
            all_dates_until_today.append(cur_date)
            cur_date += datetime.timedelta(days=1)

        current_streak = 0
        longest_streak = 0
        temp_streak = 0
        perfect_days = 0
        total_disciplined_days = 0

        # Longest streak calculation
        for d in all_dates_until_today:
            score = db_map.get(d, {}).get("score", 0.0)
            if score == 100.0:
                perfect_days += 1
            if score >= 75.0:
                total_disciplined_days += 1
                temp_streak += 1
                if temp_streak > longest_streak:
                    longest_streak = temp_streak
            else:
                temp_streak = 0

        # Current streak calculation (backwards from today)
        check_date = today
        if db_map.get(today, {}).get("score", 0.0) < 75.0:
            check_date = today - datetime.timedelta(days=1)

        while check_date >= start_date and db_map.get(check_date, {}).get("score", 0.0) >= 75.0:
            current_streak += 1
            check_date -= datetime.timedelta(days=1)

        # 2. Monthly Scores Progression (12 Months)
        monthly_scores = []
        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        monthly_consistency_data = []

        for m in range(1, 13):
            num_days_m = calendar.monthrange(year, m)[1]
            m_start = datetime.date(year, m, 1)
            m_end = datetime.date(year, m, num_days_m)

            if m_start > today:
                status = "upcoming"
                m_score = 0.0
                m_perfect = 0
                m_disciplined = 0
                gym_c, job_c, study_c, proj_c = 0.0, 0.0, 0.0, 0.0
            else:
                status = "completed" if m_end < today else "in_progress"
                m_days = [datetime.date(year, m, d) for d in range(1, min(num_days_m, (today - m_start).days + 1) + 1)]
                elapsed_m = len(m_days)

                gym_sum = sum([1 for d in m_days if db_map.get(d, {}).get("gym")])
                job_sum = sum([1 for d in m_days if db_map.get(d, {}).get("job")])
                study_sum = sum([1 for d in m_days if db_map.get(d, {}).get("study")])
                proj_sum = sum([1 for d in m_days if db_map.get(d, {}).get("project")])
                m_perfect = sum([1 for d in m_days if db_map.get(d, {}).get("score", 0.0) == 100.0])
                m_disciplined = sum([1 for d in m_days if db_map.get(d, {}).get("score", 0.0) >= 75.0])

                total_acts = gym_sum + job_sum + study_sum + proj_sum
                m_score = round((total_acts / (max(elapsed_m, 1) * 4.0)) * 100, 1) if elapsed_m > 0 else 0.0

                gym_c = round((gym_sum / max(elapsed_m, 1)) * 100, 1)
                job_c = round((job_sum / max(elapsed_m, 1)) * 100, 1)
                study_c = round((study_sum / max(elapsed_m, 1)) * 100, 1)
                proj_c = round((proj_sum / max(elapsed_m, 1)) * 100, 1)

            monthly_scores.append({
                "month_index": m,
                "month_name": month_names[m - 1],
                "full_month_name": m_start.strftime("%B"),
                "score": m_score,
                "perfect_days": m_perfect,
                "disciplined_days": m_disciplined,
                "status": status
            })

            if status != "upcoming":
                monthly_consistency_data.append({
                    "month": m,
                    "score": m_score,
                    "gym": gym_c,
                    "job": job_c,
                    "study": study_c,
                    "project": proj_c
                })

        # 3. Overall Habit Consistency (Year to Date)
        elapsed_year_days = len(all_dates_until_today)
        gym_y_sum = sum([1 for d in all_dates_until_today if db_map.get(d, {}).get("gym")])
        job_y_sum = sum([1 for d in all_dates_until_today if db_map.get(d, {}).get("job")])
        study_y_sum = sum([1 for d in all_dates_until_today if db_map.get(d, {}).get("study")])
        proj_y_sum = sum([1 for d in all_dates_until_today if db_map.get(d, {}).get("project")])

        habit_consistency = {
            "Gym": round((gym_y_sum / max(elapsed_year_days, 1)) * 100, 1),
            "Job": round((job_y_sum / max(elapsed_year_days, 1)) * 100, 1),
            "Study": round((study_y_sum / max(elapsed_year_days, 1)) * 100, 1),
            "Project": round((proj_y_sum / max(elapsed_year_days, 1)) * 100, 1)
        }

        # 4. Quarterly Breakdown
        quarters = [
            {"quarter": "Q1", "title": "January – March", "months": [1, 2, 3]},
            {"quarter": "Q2", "title": "April – June", "months": [4, 5, 6]},
            {"quarter": "Q3", "title": "July – September", "months": [7, 8, 9]},
            {"quarter": "Q4", "title": "October – December", "months": [10, 11, 12]}
        ]

        quarterly_analytics = []
        for q in quarters:
            q_months = q["months"]
            q_days = [d for d in all_dates_until_today if d.month in q_months]

            if not q_days:
                quarterly_analytics.append({
                    "quarter": q["quarter"],
                    "title": q["title"],
                    "status": "upcoming",
                    "avg_score": 0.0,
                    "gym_consistency": 0.0,
                    "job_consistency": 0.0,
                    "study_consistency": 0.0,
                    "project_consistency": 0.0,
                    "perfect_days": 0,
                    "missed_days": 0,
                    "best_month": "--",
                    "worst_month": "--",
                    "best_streak": 0
                })
                continue

            q_elapsed = len(q_days)
            gym_q = sum([1 for d in q_days if db_map.get(d, {}).get("gym")])
            job_q = sum([1 for d in q_days if db_map.get(d, {}).get("job")])
            study_q = sum([1 for d in q_days if db_map.get(d, {}).get("study")])
            proj_q = sum([1 for d in q_days if db_map.get(d, {}).get("project")])
            perf_q = sum([1 for d in q_days if db_map.get(d, {}).get("score", 0.0) == 100.0])
            missed_q = sum([1 for d in q_days if db_map.get(d, {}).get("score", 0.0) == 0.0])

            q_total_acts = gym_q + job_q + study_q + proj_q
            q_score = round((q_total_acts / (max(q_elapsed, 1) * 4.0)) * 100, 1)

            # Month comparisons in quarter
            q_m_scores = [m for m in monthly_scores if m["month_index"] in q_months and m["status"] != "upcoming"]
            best_m = max(q_m_scores, key=lambda x: x["score"])["full_month_name"] if q_m_scores else "--"
            worst_m = min(q_m_scores, key=lambda x: x["score"])["full_month_name"] if q_m_scores else "--"

            # Best streak in quarter
            q_streak = 0
            q_best_streak = 0
            for d in q_days:
                if db_map.get(d, {}).get("score", 0.0) >= 75.0:
                    q_streak += 1
                    if q_streak > q_best_streak: q_best_streak = q_streak
                else:
                    q_streak = 0

            quarterly_analytics.append({
                "quarter": q["quarter"],
                "title": q["title"],
                "status": "completed" if q_months[-1] < today.month else "in_progress",
                "avg_score": q_score,
                "gym_consistency": round((gym_q / max(q_elapsed, 1)) * 100, 1),
                "job_consistency": round((job_q / max(q_elapsed, 1)) * 100, 1),
                "study_consistency": round((study_q / max(q_elapsed, 1)) * 100, 1),
                "project_consistency": round((proj_q / max(q_elapsed, 1)) * 100, 1),
                "perfect_days": perf_q,
                "missed_days": missed_q,
                "best_month": best_m,
                "worst_month": worst_m,
                "best_streak": q_best_streak
            })

        # 5. Dynamic Self-Improvement Insights
        sorted_habits = sorted(habit_consistency.items(), key=lambda x: x[1], reverse=True)
        strongest_habit = {"name": sorted_habits[0][0], "consistency": sorted_habits[0][1]}
        weakest_habit = {"name": sorted_habits[-1][0], "consistency": sorted_habits[-1][1]}

        # Month over month trend
        if len(monthly_consistency_data) >= 2:
            prev_m = monthly_consistency_data[-2]["score"]
            curr_m = monthly_consistency_data[-1]["score"]
            mom_change = round(curr_m - prev_m, 1)
        else:
            mom_change = 0.0

        focus_recommendation = f"{weakest_habit['name']} consistency (currently at {weakest_habit['consistency']}%) to maximize daily momentum."

        # Generated actionable sentences
        insights_list = [
            f"💪 {strongest_habit['name']} is your strongest anchor habit with {strongest_habit['consistency']}% consistency.",
            f"🎯 Prioritize {weakest_habit['name']} early in the day to prevent drop-offs (currently {weakest_habit['consistency']}%).",
            f"⭐ You have achieved {perfect_days} perfect (100%) discipline days so far in 2026.",
            f"🔥 Your longest unbroken discipline streak stands at {longest_streak} consecutive days."
        ]

        if mom_change > 0:
            insights_list.insert(1, f"📈 Improvement: +{mom_change}% compared to previous month.")
        elif mom_change < 0:
            insights_list.insert(1, f"⚠️ Monthly score shifted {mom_change}% vs last month. Refocus on daily rituals.")

        # 6. BMW S1000 Motivation System
        total_possible_year_acts = max(elapsed_year_days, 1) * 4
        total_actual_year_acts = gym_y_sum + job_y_sum + study_y_sum + proj_y_sum
        overall_year_discipline = round((total_actual_year_acts / total_possible_year_acts) * 100, 1) if total_possible_year_acts > 0 else 0.0

        bmw_progress = overall_year_discipline
        if bmw_progress <= 30:
            bmw_quote = "“You have a dream. Now build the discipline.”"
            bmw_tier = "Ignition Stage"
        elif bmw_progress <= 60:
            bmw_quote = "“You're getting closer. Don't slow down.”"
            bmw_tier = "Acceleration Stage"
        elif bmw_progress <= 80:
            bmw_quote = "“The goal is getting closer. Stay consistent.”"
            bmw_tier = "High Performance"
        elif bmw_progress <= 99:
            bmw_quote = "“You're almost there. Finish strong.”"
            bmw_tier = "Apex Stage"
        else:
            bmw_quote = "“You proved that discipline compounds.”"
            bmw_tier = "Mastery Reached"

        return jsonify({
            "success": True,
            "year": year,
            "streaks": {
                "current_streak": current_streak,
                "longest_streak": longest_streak,
                "perfect_days": perfect_days,
                "disciplined_days": total_disciplined_days,
                "elapsed_days": elapsed_year_days
            },
            "overall_year_discipline": overall_year_discipline,
            "habit_consistency": habit_consistency,
            "monthly_scores": monthly_scores,
            "quarterly_analytics": quarterly_analytics,
            "self_improvement": {
                "strongest_habit": strongest_habit,
                "weakest_habit": weakest_habit,
                "mom_change": mom_change,
                "focus_recommendation": focus_recommendation,
                "insights": insights_list
            },
            "bmw_motivation": {
                "goal_name": "BMW S1000 RR",
                "progress_percent": bmw_progress,
                "tier": bmw_tier,
                "quote": bmw_quote,
                "tagline": "“The bike is the reward. Discipline is the price.”"
            }
        }), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# -----------------------------------------------------------------------------
# 5. SPREADSHEET HABIT MATRIX & ADVANCED ANALYTICS (MONTH MATRIX)
# -----------------------------------------------------------------------------
DEFAULT_ROUTINE_PRESETS = [
    {"key": "deep_work", "label": "Deep Work", "icon": "💼", "category": "Productivity"},
    {"key": "gym", "label": "Gym / Workout", "icon": "🏋️", "category": "Fitness"},
    {"key": "study", "label": "Study / DS-365", "icon": "🧠", "category": "Learning"},
    {"key": "job", "label": "Job Applications", "icon": "🎯", "category": "Career"},
    {"key": "reading", "label": "Reading / Meditating", "icon": "📖", "category": "Mind"},
    {"key": "wake_early", "label": "Wake Up Early", "icon": "⏰", "category": "Routine"},
    {"key": "budget", "label": "Budget Tracking", "icon": "💰", "category": "Finance"},
    {"key": "cold_shower", "label": "Cold Shower", "icon": "🚿", "category": "Health"},
    {"key": "clean_living", "label": "Clean Living / No Alcohol", "icon": "🚫", "category": "Health"},
    {"key": "reflection", "label": "Time with Self / Reflection", "icon": "🧘", "category": "Mind"},
]

@discipline_blueprint.route('/api/discipline/month-matrix/<int:year>/<int:month>', methods=['GET'])
def get_month_matrix(year, month):
    user_id = get_user_id()
    if month < 1 or month > 12:
        return jsonify({"success": False, "error": "Invalid month"}), 400

    today = get_today_date()
    num_days = calendar.monthrange(year, month)[1]
    start_date = datetime.date(year, month, 1)
    end_date = datetime.date(year, month, num_days)
    month_name = start_date.strftime("%B").upper()

    try:
        conn = get_connection()
        cur = conn.cursor()

        # Fetch records for this month
        cur.execute("""
            SELECT date, gym_completed, job_completed, study_completed, project_completed, daily_score, notes, habits_data
            FROM discipline_daily
            WHERE user_id = %s AND date >= %s AND date <= %s
            ORDER BY date ASC;
        """, (user_id, start_date, end_date))
        rows = cur.fetchall()

        # Fetch all user records up to today for streaks
        cur.execute("""
            SELECT date, daily_score
            FROM discipline_daily
            WHERE user_id = %s AND date <= %s
            ORDER BY date DESC;
        """, (user_id, today))
        history_rows = cur.fetchall()

        cur.close()
        conn.close()

        history_map = {r[0]: float(r[1]) for r in history_rows}
        current_streak = 0
        check_date = today
        if history_map.get(today, 0.0) < 75.0:
            check_date = today - datetime.timedelta(days=1)
        while check_date in history_map and history_map[check_date] >= 75.0:
            current_streak += 1
            check_date -= datetime.timedelta(days=1)

        db_map = {}
        for r in rows:
            d_str = r[0].isoformat()
            h_data = r[7] if (len(r) > 7 and r[7]) else {}
            if not isinstance(h_data, dict):
                h_data = {}

            # Populate fallback standard keys
            if "gym" not in h_data: h_data["gym"] = bool(r[1])
            if "job" not in h_data: h_data["job"] = bool(r[2])
            if "study" not in h_data: h_data["study"] = bool(r[3])
            if "deep_work" not in h_data: h_data["deep_work"] = bool(r[4])

            db_map[d_str] = {
                "gym_completed": bool(r[1]),
                "job_completed": bool(r[2]),
                "study_completed": bool(r[3]),
                "project_completed": bool(r[4]),
                "daily_score": float(r[5]),
                "notes": r[6] or "",
                "habits_data": h_data
            }

        WEEK_COLORS = ["cyan", "emerald", "purple", "blue", "amber"]
        WEEK_HEX = ["#00f2fe", "#10b981", "#8b5cf6", "#3b82f6", "#f59e0b"]

        days_data = []
        weekday_stats = {i: {"done": 0, "total": 0} for i in range(7)} # 0=Mon, 6=Sun
        habit_counts = {p["key"]: 0 for p in DEFAULT_ROUTINE_PRESETS}
        total_month_done = 0
        total_month_goal = 0

        # Partition days into weeks
        for day in range(1, num_days + 1):
            d_obj = datetime.date(year, month, day)
            d_str = d_obj.isoformat()
            is_future = d_obj > today
            is_today = d_obj == today
            weekday_num = d_obj.weekday() # 0 = Mon, 6 = Sun
            weekday_abbr = d_obj.strftime("%a") # Mon, Tue, etc.

            # Week 1 to 5 calculation
            week_idx = min((day - 1) // 7, 4)
            week_num = week_idx + 1

            rec = db_map.get(d_str)
            habits_map = rec["habits_data"] if rec else {}

            # Calculate done count for this day
            done_count = sum([1 for p in DEFAULT_ROUTINE_PRESETS if habits_map.get(p["key"], False)])
            goal_count = len(DEFAULT_ROUTINE_PRESETS)
            open_count = max(goal_count - done_count, 0)
            score_percent = round((done_count / float(goal_count)) * 100, 1)

            if not is_future:
                weekday_stats[weekday_num]["done"] += done_count
                weekday_stats[weekday_num]["total"] += goal_count
                total_month_done += done_count
                total_month_goal += goal_count

                for p in DEFAULT_ROUTINE_PRESETS:
                    if habits_map.get(p["key"], False):
                        habit_counts[p["key"]] += 1

            days_data.append({
                "day": day,
                "date": d_str,
                "weekday": weekday_abbr,
                "weekday_num": weekday_num,
                "week_num": week_num,
                "week_color": WEEK_COLORS[week_idx],
                "week_hex": WEEK_HEX[week_idx],
                "is_today": is_today,
                "is_future": is_future,
                "habits": {p["key"]: habits_map.get(p["key"], False) for p in DEFAULT_ROUTINE_PRESETS},
                "done_count": done_count,
                "goal_count": goal_count,
                "open_count": open_count,
                "score_percent": score_percent,
                "notes": rec["notes"] if rec else ""
            })

        # Build Weekly Groupings
        weeks_summary = []
        for w_idx in range(5):
            w_num = w_idx + 1
            w_days = [d for d in days_data if d["week_num"] == w_num]
            if not w_days:
                continue
            w_done = sum([d["done_count"] for d in w_days if not d["is_future"]])
            w_goal = sum([d["goal_count"] for d in w_days if not d["is_future"]])
            w_progress = round((w_done / float(max(w_goal, 1))) * 100, 1) if w_goal > 0 else 0.0

            weeks_summary.append({
                "week_num": w_num,
                "label": f"WEEK {w_num}",
                "color_name": WEEK_COLORS[w_idx],
                "color_hex": WEEK_HEX[w_idx],
                "days_count": len(w_days),
                "start_day": w_days[0]["day"],
                "end_day": w_days[-1]["day"],
                "total_done": w_done,
                "total_goal": w_goal,
                "progress_percent": w_progress
            })

        # Build Habit Adherence Stats
        elapsed_days_so_far = max(sum([1 for d in days_data if not d["is_future"]]), 1)
        habit_adherence = []
        for p in DEFAULT_ROUTINE_PRESETS:
            c_cnt = habit_counts.get(p["key"], 0)
            adh_pct = round((c_cnt / float(elapsed_days_so_far)) * 100, 1)
            habit_adherence.append({
                "key": p["key"],
                "label": p["label"],
                "icon": p["icon"],
                "category": p["category"],
                "completed_count": c_cnt,
                "goal_target": num_days,
                "adherence_percent": adh_pct
            })

        # Build Day-of-Week Variance Data
        DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        day_of_week_distribution = []
        for i in range(7):
            tot = weekday_stats[i]["total"]
            dn = weekday_stats[i]["done"]
            pct = round((dn / float(max(tot, 1))) * 100, 1) if tot > 0 else 0.0
            day_of_week_distribution.append({
                "day_name": DAY_NAMES[i],
                "day_index": i,
                "done": dn,
                "total": tot,
                "adherence_percent": pct
            })

        # Monthly overall average
        monthly_avg_score = round((total_month_done / float(max(total_month_goal, 1))) * 100, 1) if total_month_goal > 0 else 0.0

        return jsonify({
            "success": True,
            "year": year,
            "month": month,
            "month_name": month_name,
            "total_days": num_days,
            "monthly_avg_score": monthly_avg_score,
            "current_streak": current_streak,
            "routines_presets": DEFAULT_ROUTINE_PRESETS,
            "days": days_data,
            "weeks_summary": weeks_summary,
            "habit_adherence": habit_adherence,
            "day_of_week_distribution": day_of_week_distribution
        }), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# -----------------------------------------------------------------------------
# 6. TOGGLE SINGLE HABIT CELL (Instant Click Persist)
# -----------------------------------------------------------------------------
@discipline_blueprint.route('/api/discipline/toggle-cell', methods=['POST'])
def toggle_habit_cell():
    user_id = get_user_id()
    data = request.get_json(silent=True) or {}
    date_str = data.get("date")
    habit_key = data.get("habit_key")
    completed = bool(data.get("completed"))

    if not date_str or not habit_key:
        return jsonify({"success": False, "error": "Missing date or habit_key"}), 400

    try:
        req_date = datetime.date.fromisoformat(date_str)
        if req_date > get_today_date():
            return jsonify({"success": False, "error": "Cannot log activities for future dates."}), 400
    except ValueError:
        return jsonify({"success": False, "error": "Invalid date format"}), 400

    try:
        conn = get_connection()
        cur = conn.cursor()

        # Fetch existing record
        cur.execute("""
            SELECT gym_completed, job_completed, study_completed, project_completed, habits_data, notes
            FROM discipline_daily
            WHERE user_id = %s AND date = %s;
        """, (user_id, req_date))
        row = cur.fetchone()

        habits_data = row[4] if (row and len(row) > 4 and row[4]) else {}
        if not isinstance(habits_data, dict):
            habits_data = {}

        # Set the habit key
        habits_data[habit_key] = completed

        # Sync standard columns
        gym_val = habits_data.get("gym", bool(row[0]) if row else False)
        job_val = habits_data.get("job", bool(row[1]) if row else False)
        study_val = habits_data.get("study", bool(row[2]) if row else False)
        proj_val = habits_data.get("deep_work", bool(row[3]) if row else False)

        # Recalculate score based on default routines
        done_cnt = sum([1 for p in DEFAULT_ROUTINE_PRESETS if habits_data.get(p["key"], False)])
        total_cnt = len(DEFAULT_ROUTINE_PRESETS)
        new_score = round((done_cnt / float(total_cnt)) * 100, 2)

        notes_val = row[5] if row else ""

        # Upsert
        cur.execute("""
            INSERT INTO discipline_daily (
                user_id, date, gym_completed, job_completed, study_completed, project_completed,
                habits_data, daily_score, notes, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id, date) DO UPDATE SET
                gym_completed = EXCLUDED.gym_completed,
                job_completed = EXCLUDED.job_completed,
                study_completed = EXCLUDED.study_completed,
                project_completed = EXCLUDED.project_completed,
                habits_data = EXCLUDED.habits_data,
                daily_score = EXCLUDED.daily_score,
                updated_at = CURRENT_TIMESTAMP;
        """, (
            user_id, req_date, gym_val, job_val, study_val, proj_val,
            Json(habits_data),
            new_score, notes_val
        ))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "success": True,
            "date": date_str,
            "habit_key": habit_key,
            "completed": completed,
            "daily_score": new_score,
            "done_count": done_cnt,
            "goal_count": total_cnt
        }), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

