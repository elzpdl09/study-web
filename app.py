from flask import Flask, render_template, request, jsonify, redirect, url_for
import pymysql

app = Flask(__name__)

def get_db_connection():
    return pymysql.connect(
        host='localhost',
        user='root',
        password='1318',  # 본인 환경에 맞게 수정
        db='study_tracker',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    name = data.get('name')
    if not name:
        return jsonify({'success': False, 'message': '이름이 없습니다.'})
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            sql = "INSERT INTO users (name) VALUES (%s)"
            cursor.execute(sql, (name,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    name = data.get('name')
    if not name:
        return jsonify({'success': False, 'message': '이름을 입력해주세요.'})
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            sql = "SELECT * FROM users WHERE name = %s"
            cursor.execute(sql, (name,))
            user = cursor.fetchone()
        conn.close()
        if user:
            return redirect(url_for('main', username=name))
        else:
            return jsonify({'success': False, 'message': '사용자를 찾을 수 없습니다.'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/main')
def main():
    username = request.args.get('username', '게스트')
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT user_id, name, wake_up_time, phone_usage, study_time, score FROM users")
            users = cursor.fetchall()

            for user in users:
                cursor.execute("SELECT todo_id, task, is_done FROM todos WHERE user_id=%s ORDER BY todo_id", (user['user_id'],))
                todos = cursor.fetchall()
                user['todos'] = todos
                if todos:
                    done_count = sum(todo['is_done'] for todo in todos)
                    user['progress'] = int(done_count / len(todos) * 100)
                else:
                    user['progress'] = 0

            # 랭킹 리스트: 점수 내림차순, 이름 오름차순(동점자 처리)
            cursor.execute("SELECT name, score FROM users ORDER BY score DESC, name ASC")
            ranking_list = cursor.fetchall()

        conn.close()

        return render_template('main.html', username=username, user_list=users, ranking_list=ranking_list)
    except Exception as e:
        return f"<h2>오류 발생: {e}</h2>"

@app.route('/update/<int:user_id>', methods=['POST'])
def update_user(user_id):
    wake_up_time = request.form.get('wake_up_time')
    phone_usage = request.form.get('phone_usage')
    study_time = request.form.get('study_time')
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            sql = """
                UPDATE users
                SET wake_up_time = %s, phone_usage = %s, study_time = %s
                WHERE user_id = %s
            """
            cursor.execute(sql, (wake_up_time, phone_usage, study_time, user_id))
        conn.commit()
        conn.close()
        return redirect(url_for('main'))
    except Exception as e:
        return f"<h2>업데이트 중 오류 발생: {e}</h2>"

def update_progress_and_score(user_id):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS total, SUM(is_done) AS done FROM todos WHERE user_id=%s", (user_id,))
        result = cursor.fetchone()
        total = result['total']
        done = result['done'] or 0
        progress = int(done / total * 100) if total > 0 else 0

        cursor.execute("SELECT score FROM users WHERE user_id=%s", (user_id,))
        current_score = cursor.fetchone()['score'] or 0

        # 점수 중복 증가 방지 로직 (필요에 따라 조절 가능)
        score_increase = 1 if progress == 100 and current_score == 0 else 0
        new_score = current_score + score_increase
        cursor.execute("UPDATE users SET score=%s WHERE user_id=%s", (new_score, user_id))
    conn.commit()
    conn.close()

@app.route('/add_todo/<int:user_id>', methods=['POST'])
def add_todo(user_id):
    data = request.get_json()
    task = data.get('task')
    if not task or task.strip() == '':
        return jsonify({'success': False, 'message': '할 일을 입력하세요.'})
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("INSERT INTO todos (user_id, task, is_done) VALUES (%s, %s, 0)", (user_id, task))
        conn.commit()
        conn.close()
        update_progress_and_score(user_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/toggle_todo/<int:todo_id>', methods=['POST'])
def toggle_todo(todo_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT is_done, user_id FROM todos WHERE todo_id=%s", (todo_id,))
            todo = cursor.fetchone()
            if not todo:
                return jsonify({'success': False, 'message': '할 일을 찾을 수 없습니다.'})
            new_status = 0 if todo['is_done'] else 1
            cursor.execute("UPDATE todos SET is_done=%s WHERE todo_id=%s", (new_status, todo_id))
            conn.commit()
            user_id = todo['user_id']
        conn.close()
        update_progress_and_score(user_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/delete_todo/<int:todo_id>', methods=['POST'])
def delete_todo(todo_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT user_id FROM todos WHERE todo_id=%s", (todo_id,))
            todo = cursor.fetchone()
            if not todo:
                return jsonify({'success': False, 'message': '할 일을 찾을 수 없습니다.'})
            user_id = todo['user_id']
            cursor.execute("DELETE FROM todos WHERE todo_id=%s", (todo_id,))
            conn.commit()
        conn.close()
        update_progress_and_score(user_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

if __name__ == '__main__':
    app.run(debug=True)
