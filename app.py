from flask import Flask, render_template, request, jsonify, session, redirect
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
import os

app = Flask(__name__)

# Sử dụng MySQL thay vì SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost/student_db'
app.config['SECRET_KEY'] = 'your-secret-key-here'
db = SQLAlchemy(app)

# Setup Logging
if not os.path.exists('logs'):
    os.mkdir('logs')

file_handler = RotatingFileHandler('logs/app.log', maxBytes=10240000, backupCount=10)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('Application startup')

# Database Model
class Student(db.Model):
    __tablename__ = 'student'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    student_id = db.Column(db.String(20), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    major = db.Column(db.String(100))
    gpa = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ActivityLog(db.Model):
    __tablename__ = 'activity_log'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    action = db.Column(db.String(100))
    details = db.Column(db.String(500))
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class DatabaseLog(db.Model):
    """Log các thay đổi database"""
    __tablename__ = 'database_log'
    id = db.Column(db.Integer, primary_key=True)
    table_name = db.Column(db.String(50))
    operation = db.Column(db.String(20))  # INSERT, UPDATE, DELETE
    record_id = db.Column(db.Integer)
    old_value = db.Column(db.String(500))
    new_value = db.Column(db.String(500))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class StudentGrade(db.Model):
    """Lưu điểm số của sinh viên"""
    __tablename__ = 'student_grade'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    credit = db.Column(db.Integer, nullable=False)
    grade = db.Column(db.String(5), nullable=False)  # A, A+, B+, B, C+, C, D+, D, F
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

with app.app_context():
    db.create_all()

def log_activity(student_id, action, details=""):
    """Ghi lại hoạt động người dùng"""
    log = ActivityLog(
        student_id=student_id, 
        action=action, 
        details=details,
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent', '')
    )
    db.session.add(log)
    db.session.commit()
    app.logger.info(f"User {student_id} - Action: {action} - IP: {request.remote_addr} - Details: {details}")

def log_database_change(table_name, operation, record_id, old_value, new_value):
    """Ghi nhận thay đổi database"""
    log = DatabaseLog(
        table_name=table_name,
        operation=operation,
        record_id=record_id,
        old_value=str(old_value),
        new_value=str(new_value)
    )
    db.session.add(log)
    db.session.commit()
    app.logger.info(f"DB Change: {table_name}.{operation} (ID: {record_id})")

@app.before_request
def log_request():
    """Ghi log mỗi HTTP request"""
    app.logger.info(f"REQUEST: {request.method} {request.path} - IP: {request.remote_addr} - User-Agent: {request.headers.get('User-Agent', 'N/A')}")

@app.after_request
def log_response(response):
    """Ghi log response"""
    app.logger.info(f"RESPONSE: {response.status_code} - {request.method} {request.path}")
    return response

# API Routes
@app.route('/')
def index():
    app.logger.info(f"Homepage accessed from IP: {request.remote_addr}")
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            data = request.get_json()
            
            if not all([data.get('name'), data.get('email'), data.get('password'), data.get('student_id')]):
                return jsonify({'success': False, 'message': 'Missing required fields'})
            
            if Student.query.filter_by(email=data['email']).first():
                app.logger.warning(f"Registration attempt with existing email: {data['email']} from IP: {request.remote_addr}")
                return jsonify({'success': False, 'message': 'Email already exists'})
            
            if Student.query.filter_by(student_id=data['student_id']).first():
                app.logger.warning(f"Registration attempt with existing student_id: {data['student_id']} from IP: {request.remote_addr}")
                return jsonify({'success': False, 'message': 'Student ID already exists'})
            
            student = Student(
                name=data['name'],
                email=data['email'],
                password=generate_password_hash(data['password']),
                student_id=data['student_id'],
                phone=data.get('phone', ''),
                major=data.get('major', '')
            )
            db.session.add(student)
            db.session.commit()
            
            # Ghi log database change
            log_database_change('student', 'INSERT', student.id, None, 
                f"name={data['name']}, email={data['email']}, student_id={data['student_id']}")
            
            app.logger.info(f"New student registered: {data['email']} from IP: {request.remote_addr}")
            return jsonify({'success': True, 'message': 'Registration successful'})
        except Exception as e:
            app.logger.error(f"Registration error: {str(e)} from IP: {request.remote_addr}")
            return jsonify({'success': False, 'message': 'Registration failed'})
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            data = request.get_json()
            student = Student.query.filter_by(email=data['email']).first()
            
            if student and check_password_hash(student.password, data['password']):
                session['student_id'] = student.id
                log_activity(student.id, 'LOGIN', f'Email: {data["email"]}')
                return jsonify({'success': True, 'message': 'Login successful'})
            
            app.logger.warning(f"Failed login attempt for: {data.get('email')} from IP: {request.remote_addr}")
            return jsonify({'success': False, 'message': 'Invalid credentials'})
        except Exception as e:
            app.logger.error(f"Login error: {str(e)} from IP: {request.remote_addr}")
            return jsonify({'success': False, 'message': 'Login failed'})
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'student_id' not in session:
        return redirect('/login')
    log_activity(session['student_id'], 'ACCESS_DASHBOARD', 'Accessed dashboard page')
    return render_template('dashboard.html')

@app.route('/api/profile', methods=['GET'])
def get_profile():
    if 'student_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        student = Student.query.get(session['student_id'])
        if not student:
            return jsonify({'error': 'Student not found'}), 404
        
        # Lấy CPA thay vì GPA
        student_grades = StudentGrade.query.filter_by(student_id=student.id).all()
        subjects = [{
            'subject': g.subject,
            'credit': g.credit,
            'grade': g.grade
        } for g in student_grades]
        cpa = calculate_cpa(subjects)
        
        log_activity(student.id, 'VIEW_PROFILE', 'Viewed own profile')
        return jsonify({
            'id': student.id,
            'name': student.name,
            'email': student.email,
            'student_id': student.student_id,
            'phone': student.phone,
            'major': student.major,
            'cpa': cpa  # Thay gpa thành cpa
        })
    except Exception as e:
        app.logger.error(f"Get profile error: {str(e)}")
        return jsonify({'error': 'Server error'}), 500

@app.route('/api/profile', methods=['PUT'])
def update_profile():
    if 'student_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        student = Student.query.get(session['student_id'])
        
        if not student:
            return jsonify({'error': 'Student not found'}), 404
        
        old_values = f"phone: {student.phone}, major: {student.major}, gpa: {student.gpa}"
        
        student.phone = data.get('phone', student.phone)
        student.major = data.get('major', student.major)
        student.gpa = float(data.get('gpa', student.gpa))
        student.updated_at = datetime.utcnow()
        db.session.commit()
        
        new_values = f"phone: {student.phone}, major: {student.major}, gpa: {student.gpa}"
        
        # Ghi log database change
        log_database_change('student', 'UPDATE', student.id, old_values, new_values)
        
        log_activity(student.id, 'UPDATE_PROFILE', f'Changed from: {old_values}')
        app.logger.info(f"Student {student.id} updated profile")
        return jsonify({'success': True, 'message': 'Profile updated'})
    except ValueError:
        app.logger.error("Invalid GPA value submitted")
        return jsonify({'success': False, 'message': 'Invalid GPA format'})
    except Exception as e:
        app.logger.error(f"Update profile error: {str(e)}")
        return jsonify({'success': False, 'message': 'Update failed'})

@app.route('/api/all-students', methods=['GET'])
def get_all_students():
    if 'student_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        students = Student.query.all()
        log_activity(session['student_id'], 'VIEW_ALL_STUDENTS', f'Viewed {len(students)} students')
        return jsonify([{
            'id': s.id,
            'name': s.name,
            'email': s.email,
            'student_id': s.student_id,
            'major': s.major,
            'gpa': s.gpa
        } for s in students])
    except Exception as e:
        app.logger.error(f"Get all students error: {str(e)}")
        return jsonify({'error': 'Server error'}), 500

@app.route('/api/activity-log', methods=['GET'])
def get_activity_log():
    if 'student_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        activities = ActivityLog.query.filter_by(student_id=session['student_id']).order_by(ActivityLog.timestamp.desc()).all()
        return jsonify([{
            'action': a.action,
            'details': a.details,
            'ip_address': a.ip_address,
            'timestamp': a.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        } for a in activities])
    except Exception as e:
        app.logger.error(f"Get activity log error: {str(e)}")
        return jsonify({'error': 'Server error'}), 500

@app.route('/logout')
def logout():
    if 'student_id' in session:
        log_activity(session['student_id'], 'LOGOUT', 'User logged out')
    session.clear()
    app.logger.info("User logged out")
    return jsonify({'success': True})

@app.route('/grades')
def grades():
    """Trang xem điểm số - Tính năng mới"""
    if 'student_id' not in session:
        return redirect('/login')
    
    try:
        student = Student.query.get(session['student_id'])
        if not student:
            return redirect('/login')
        
        # Ghi log khi user vào trang điểm số
        log_activity(student.id, 'VIEW_GRADES', 'Accessed grades page')
        app.logger.info(f"Student {student.id} accessed grades page")
        
        return render_template('grades.html')
    except Exception as e:
        app.logger.error(f"Grades page error: {str(e)}")
        return jsonify({'error': 'Server error'}), 500

@app.route('/api/grades', methods=['GET'])
def get_grades():
    """API lấy dữ liệu điểm số từ database"""
    if 'student_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        student = Student.query.get(session['student_id'])
        if not student:
            return jsonify({'error': 'Student not found'}), 404
        
        # Lấy điểm từ database
        student_grades = StudentGrade.query.filter_by(student_id=student.id).all()
        
        subjects = [{
            'id': g.id,
            'subject': g.subject,
            'credit': g.credit,
            'grade': g.grade
        } for g in student_grades]
        
        # Tính CPA
        cpa = calculate_cpa(subjects)
        
        grades_data = {
            'student_name': student.name,
            'student_id': student.student_id,
            'major': student.major,
            'current_cpa': cpa,
            'subjects': subjects
        }
        
        log_activity(student.id, 'VIEW_GRADES', f'Viewed grades - CPA: {cpa}')
        return jsonify(grades_data)
    except Exception as e:
        app.logger.error(f"Get grades error: {str(e)}")
        return jsonify({'error': 'Server error'}), 500

@app.route('/api/grades', methods=['POST'])
def add_grade():
    """API thêm môn học mới"""
    if 'student_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        student_id = session['student_id']
        
        # Validate
        if not all([data.get('subject'), data.get('grade')]):
            return jsonify({'success': False, 'message': 'Vui lòng điền đủ thông tin'}), 400
        
        if data.get('grade').upper() not in ['A', 'A+', 'B+', 'B', 'C+', 'C', 'D+', 'D', 'F']:
            return jsonify({'success': False, 'message': 'Điểm không hợp lệ'}), 400
        
        credit = int(data.get('credit', 3))
        if credit <= 0:
            return jsonify({'success': False, 'message': 'Tín chỉ phải lớn hơn 0'}), 400
        
        # Kiểm tra môn học đã tồn tại chưa
        existing = StudentGrade.query.filter_by(
            student_id=student_id,
            subject=data['subject']
        ).first()
        
        if existing:
            return jsonify({'success': False, 'message': 'Môn học này đã tồn tại'}), 400
        
        # Thêm môn học mới
        grade = StudentGrade(
            student_id=student_id,
            subject=data['subject'],
            credit=credit,
            grade=data['grade'].upper()
        )
        db.session.add(grade)
        db.session.commit()
        
        # Ghi log
        log_database_change('student_grade', 'INSERT', grade.id, None,
            f"subject={data['subject']}, credit={credit}, grade={data['grade']}")
        log_activity(student_id, 'ADD_GRADE', f"Added subject: {data['subject']} - Grade: {data['grade']}")
        
        return jsonify({
            'success': True,
            'message': 'Thêm môn học thành công',
            'grade': {
                'id': grade.id,
                'subject': grade.subject,
                'credit': grade.credit,
                'grade': grade.grade
            }
        })
    except Exception as e:
        app.logger.error(f"Add grade error: {str(e)}")
        return jsonify({'success': False, 'message': 'Thêm môn học thất bại'})

@app.route('/api/grades/<int:grade_id>', methods=['PUT'])
def update_grade(grade_id):
    """API cập nhật môn học"""
    if 'student_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        grade = StudentGrade.query.get(grade_id)
        
        if not grade or grade.student_id != session['student_id']:
            return jsonify({'error': 'Grade not found'}), 404
        
        data = request.get_json()
        
        old_value = f"subject={grade.subject}, credit={grade.credit}, grade={grade.grade}"
        
        if data.get('subject'):
            grade.subject = data['subject']
        if data.get('credit'):
            grade.credit = int(data['credit'])
        if data.get('grade'):
            if data['grade'].upper() not in ['A', 'A+', 'B+', 'B', 'C+', 'C', 'D+', 'D', 'F']:
                return jsonify({'success': False, 'message': 'Điểm không hợp lệ'}), 400
            grade.grade = data['grade'].upper()
        
        grade.updated_at = datetime.utcnow()
        db.session.commit()
        
        new_value = f"subject={grade.subject}, credit={grade.credit}, grade={grade.grade}"
        
        # Ghi log
        log_database_change('student_grade', 'UPDATE', grade_id, old_value, new_value)
        log_activity(session['student_id'], 'UPDATE_GRADE', f"Updated grade ID {grade_id}")
        
        return jsonify({'success': True, 'message': 'Cập nhật thành công'})
    except Exception as e:
        app.logger.error(f"Update grade error: {str(e)}")
        return jsonify({'success': False, 'message': 'Cập nhật thất bại'})

@app.route('/api/grades/<int:grade_id>', methods=['DELETE'])
def delete_grade(grade_id):
    """API xóa môn học"""
    if 'student_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        grade = StudentGrade.query.get(grade_id)
        
        if not grade or grade.student_id != session['student_id']:
            return jsonify({'error': 'Grade not found'}), 404
        
        old_value = f"subject={grade.subject}, credit={grade.credit}, grade={grade.grade}"
        
        # Ghi log trước khi xóa
        log_database_change('student_grade', 'DELETE', grade_id, old_value, None)
        log_activity(session['student_id'], 'DELETE_GRADE', f"Deleted subject: {grade.subject}")
        
        db.session.delete(grade)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Xóa môn học thành công'})
    except Exception as e:
        app.logger.error(f"Delete grade error: {str(e)}")
        return jsonify({'success': False, 'message': 'Xóa thất bại'})

@app.route('/api/calculate-cpa', methods=['POST'])
def calculate_cpa_api():
    """API tính CPA từ tất cả môn học của user"""
    if 'student_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        student_id = session['student_id']
        
        # Lấy tất cả môn học từ database
        student_grades = StudentGrade.query.filter_by(student_id=student_id).all()
        
        if not student_grades:
            return jsonify({'success': False, 'message': 'Vui lòng thêm ít nhất 1 môn học'}), 400
        
        subjects = [{
            'subject': g.subject,
            'credit': g.credit,
            'grade': g.grade
        } for g in student_grades]
        
        # Tính CPA
        cpa = calculate_cpa(subjects)
        
        # Ghi log
        log_activity(student_id, 'CALCULATE_CPA', f'Calculated CPA: {cpa} from {len(subjects)} subjects')
        
        return jsonify({
            'success': True,
            'cpa': cpa,
            'subjects': subjects
        })
    except Exception as e:
        app.logger.error(f"Calculate CPA error: {str(e)}")
        return jsonify({'success': False, 'message': 'Tính toán thất bại'})

def calculate_gpa_from_grade(grade):
    """Chuyển đổi điểm chữ sang điểm số"""
    grade_mapping = {
        'A': 4.0,
        'A+': 4.0,
        'B+': 3.5,
        'B': 3.0,
        'C+': 2.5,
        'C': 2.0,
        'D+': 1.5,
        'D': 1.0,
        'F': 0.0
    }
    return grade_mapping.get(grade.upper(), 0.0)

def calculate_cpa(subjects):
    """Tính CPA từ danh sách môn học"""
    if not subjects:
        return 0.0
    
    total_points = 0
    total_credits = 0
    
    for subject in subjects:
        grade_point = calculate_gpa_from_grade(subject['grade'])
        credits = subject['credit']
        total_points += grade_point * credits
        total_credits += credits
    
    if total_credits == 0:
        return 0.0
    
    cpa = total_points / total_credits
    return round(cpa, 2)

if __name__ == '__main__':
    app.run(debug=True)