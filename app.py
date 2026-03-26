from flask import Flask, request, jsonify
import jwt
import datetime
import requests
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'my_super_secret_key_1234' # เปลี่ยนเป็นคีย์ของคุณ

# ฐานข้อมูลจำลอง (Mock Database)
users_db = {"admin": "password123"}
my_tasks = [
    {"id": 1, "title": "Setup Flask", "status": "done"},
    {"id": 2, "title": "Implement JWT", "status": "in_progress"}
]

# ----------------------------------------------------
# ฟังก์ชันสำหรับตรวจสอบ JWT Token (Middleware)
# ----------------------------------------------------
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        # รับ Token จาก Header (รูปแบบ: Authorization: Bearer <token>)
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(" ")[1]
        
        if not token:
            return jsonify({"error": {"code": 401, "message": "Missing token!"}}), 401
        
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = data['user']
        except jwt.ExpiredSignatureError:
            return jsonify({"error": {"code": 401, "message": "Token has expired!"}}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": {"code": 401, "message": "Invalid token!"}}), 401
            
        return f(current_user, *args, **kwargs)
    return decorated

# ----------------------------------------------------
# 1. POST /login (รับ Username/Password -> ตอบกลับ JWT)
# ----------------------------------------------------
@app.route('/login', methods=['POST'])
def login():
    if not request.is_json:
        return jsonify({"error": {"code": 400, "message": "Request must be JSON"}}), 400
        
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": {"code": 400, "message": "Missing username or password"}}), 400

    if username in users_db and users_db[username] == password:
        # สร้าง JWT Token มีอายุ 1 ชั่วโมง
        token = jwt.encode({
            'user': username,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        }, app.config['SECRET_KEY'], algorithm="HS256")
        
        return jsonify({"data": {"token": token}}), 200
        
    return jsonify({"error": {"code": 401, "message": "Invalid credentials"}}), 401

# ----------------------------------------------------
# 2. GET /tasks (แสดงรายการงานของตัวเอง)
# ----------------------------------------------------
@app.route('/tasks', methods=['GET'])
@token_required
def get_tasks(current_user):
    return jsonify({"data": {"tasks": my_tasks, "owner": current_user}}), 200

# ----------------------------------------------------
# 3. POST /tasks (สร้างงานใหม่)
# ----------------------------------------------------
@app.route('/tasks', methods=['POST'])
@token_required
def create_task(current_user):
    if not request.is_json:
        return jsonify({"error": {"code": 400, "message": "Request must be JSON"}}), 400
        
    data = request.get_json()
    title = data.get('title')
    
    if not title:
        return jsonify({"error": {"code": 400, "message": "Task title is required"}}), 400
        
    new_task = {
        "id": len(my_tasks) + 1,
        "title": title,
        "status": data.get('status', 'pending')
    }
    my_tasks.append(new_task)
    
    return jsonify({"data": {"message": "Task created successfully", "task": new_task}}), 201

# ----------------------------------------------------
# 4. GET /external-tasks (รวมข้อมูลจาก API เพื่อน)
# ----------------------------------------------------
@app.route('/external-tasks', methods=['GET'])
@token_required
def get_external_tasks(current_user):
    friend_api_url = "https://friend-server.onrender.com/tasks" # เปลี่ยนเป็น URL ของเพื่อน
    friend_token = "FRIEND_JWT_TOKEN_HERE" # โทเค็นสำหรับเข้า API เพื่อน (ถ้าเพื่อนมีการทำ auth)
    
    headers = {"Authorization": f"Bearer {friend_token}"}
    
    try:
        # กำหนด timeout 5 วินาที เพื่อไม่ให้ระบบเรารอจนค้าง
        response = requests.get(friend_api_url, headers=headers, timeout=5)
        response.raise_for_status() # โยน Error ถ้าสถานะไม่ใช่ 200
        
        friend_data = response.json()
        friend_tasks = friend_data.get("data", {}).get("tasks", [])
        
        # นำมารวมกัน
        combined_tasks = {
            "my_tasks": my_tasks,
            "friend_tasks": friend_tasks
        }
        return jsonify({"data": combined_tasks}), 200
        
    except requests.exceptions.Timeout:
        return jsonify({"error": {"code": 500, "message": "Friend API timeout"}}), 500
    except requests.exceptions.RequestException as e:
        return jsonify({"error": {"code": 500, "message": f"Failed to fetch friend API: {str(e)}"}}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)