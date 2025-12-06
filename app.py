import os
import datetime
import json
import base64
import uuid
import traceback
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

app = Flask(__name__, static_folder='static')

# Change jinja2 delimiter to avoid conflict with Vue
app.jinja_env.variable_start_string = '[['
app.jinja_env.variable_end_string = ']]'

CORS(app)

# DB config
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(BASE_DIR, 'restaurant.db')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Upload configs
UPLOAD_BASE_PATH = os.path.join(BASE_DIR, 'uploads')
AVATAR_UPLOAD_FOLDER = os.path.join(UPLOAD_BASE_PATH, 'avatars')
FOOD_UPLOAD_FOLDER = os.path.join(BASE_DIR, 'food_images')

# Init folders
for folder in [AVATAR_UPLOAD_FOLDER, FOOD_UPLOAD_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

STATIC_FOLDER = os.path.join(BASE_DIR, 'static')
if not os.path.exists(STATIC_FOLDER):
    os.makedirs(STATIC_FOLDER)

DEFAULT_AVATAR_URL = '/static/default-avatar.png'
DEFAULT_FOOD_URL = '/static/default-food.png'

app.config.update({
    'AVATAR_UPLOAD_FOLDER': AVATAR_UPLOAD_FOLDER,
    'FOOD_UPLOAD_FOLDER': FOOD_UPLOAD_FOLDER,
    'UPLOAD_BASE_PATH': UPLOAD_BASE_PATH,
    'MAX_CONTENT_LENGTH': 2 * 1024 * 1024  # Limit 2MB
})

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
db = SQLAlchemy(app)


# --- Models ---

class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    gender = db.Column(db.String(10), default='男')
    age = db.Column(db.Integer, default=18)
    balance = db.Column(db.Float, default=100.0)
    password = db.Column(db.String(100), default='123456')
    avatar = db.Column(db.String(500), default='')
    created_at = db.Column(db.DateTime, default=datetime.datetime.now)

    def to_dict(self):
        # Handle avatar url
        avatar_url = self.avatar or DEFAULT_AVATAR_URL
        if self.avatar:
            if self.avatar.startswith(('http', '/')):
                avatar_url = self.avatar
            elif os.path.isabs(self.avatar):
                try:
                    # Convert abs path to relative url
                    if self.avatar.startswith(AVATAR_UPLOAD_FOLDER):
                        rel = os.path.relpath(self.avatar, AVATAR_UPLOAD_FOLDER)
                        avatar_url = f'/uploads/avatars/{rel.replace(os.sep, "/")}'
                    else:
                        rel = os.path.relpath(self.avatar, UPLOAD_BASE_PATH)
                        avatar_url = f'/uploads/{rel.replace(os.sep, "/")}'
                except Exception as e:
                    print(f"Path convert error: {e}")
                    avatar_url = DEFAULT_AVATAR_URL

        return {
            'id': self.id,
            'name': self.name,
            'gender': self.gender,
            'age': self.age,
            'balance': float(self.balance or 0),
            'password': self.password,
            'avatar': avatar_url,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }


class Employee(db.Model):
    __tablename__ = 'employee'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    gender = db.Column(db.String(10), default='男')
    position = db.Column(db.String(20), nullable=False)
    work_days = db.Column(db.Integer, default=0)
    monthly_salary = db.Column(db.Float, nullable=False)
    daily_salary = db.Column(db.Float, default=0.0)
    total_salary = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.datetime.now)

    def to_dict(self):
        self.daily_salary = round(self.monthly_salary / 30, 2) if self.monthly_salary else 0
        self.total_salary = round(self.daily_salary * self.work_days, 2)

        return {
            'id': self.id,
            'name': self.name,
            'gender': self.gender,
            'position': self.position,
            'work_days': self.work_days,
            'monthly_salary': float(self.monthly_salary or 0),
            'daily_salary': self.daily_salary,
            'total_salary': self.total_salary,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }


class Food(db.Model):
    __tablename__ = 'food'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, default=0)
    image = db.Column(db.String(500), default='')

    def to_dict(self):
        image_url = self.image or DEFAULT_FOOD_URL
        # fix image path issue
        if self.image and os.path.isabs(self.image):
            if self.image.startswith(FOOD_UPLOAD_FOLDER):
                rel = os.path.relpath(self.image, FOOD_UPLOAD_FOLDER)
                image_url = f'/food_images/{rel.replace(os.sep, "/")}'
            else:
                rel = os.path.relpath(self.image, UPLOAD_BASE_PATH)
                image_url = f'/uploads/{rel.replace(os.sep, "/")}'
        elif self.image and self.image.startswith(('/uploads/', '/food_images/')):
            image_url = self.image

        return {
            'id': self.id,
            'name': self.name,
            'price': float(self.price or 0),
            'stock': self.stock,
            'image': image_url
        }


class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.String(50), unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    total_price = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.datetime.now)

    user = db.relationship('User', backref='orders')
    items = db.relationship('OrderItem', backref='order', cascade="all, delete-orphan")

    def to_dict(self):
        return {
            'id': self.id,
            'order_no': self.order_no,
            'user_id': self.user_id,
            'user_name': self.user.name if self.user else 'Unknown',
            'total_price': float(self.total_price or 0),
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'items': [item.to_dict() for item in self.items]
        }


class OrderItem(db.Model):
    __tablename__ = 'order_item'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'))
    food_id = db.Column(db.Integer, db.ForeignKey('food.id'))
    quantity = db.Column(db.Integer, default=1)
    price_snapshot = db.Column(db.Float)

    food = db.relationship('Food')

    def to_dict(self):
        img = self.food.image if self.food else ''
        if img and os.path.isabs(img):
            if img.startswith(FOOD_UPLOAD_FOLDER):
                rel = os.path.relpath(img, FOOD_UPLOAD_FOLDER)
                img = f'/food_images/{rel.replace(os.sep, "/")}'
            else:
                rel = os.path.relpath(img, UPLOAD_BASE_PATH)
                img = f'/uploads/{rel.replace(os.sep, "/")}'
        
        return {
            'food_id': self.food_id,
            'food_name': self.food.name if self.food else 'Unknown',
            'image': img,
            'price': float(self.price_snapshot or 0),
            'quantity': self.quantity
        }


# --- Helper Functions ---

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def _save_img_common(file, folder, prefix, obj_id):
    if not file or not file.filename or not allowed_file(file.filename):
        return None
    try:
        if not os.path.exists(folder):
            os.makedirs(folder)

        original = secure_filename(file.filename)
        ext = original.rsplit('.', 1)[1].lower() if '.' in original else 'jpg'
        # unique filename
        fname = f"{prefix}_{obj_id}_{uuid.uuid4().hex[:8]}.{ext}"
        fpath = os.path.join(folder, fname)
        file.save(fpath)
        return fpath
    except Exception as e:
        print(f"Save image error: {e}")
        traceback.print_exc()
        return None

def _save_b64_common(b64_data, folder, prefix, obj_id):
    if not b64_data: return None
    try:
        if not os.path.exists(folder):
            os.makedirs(folder)

        if 'base64,' in b64_data:
            b64_data = b64_data.split('base64,')[1]

        fname = f"{prefix}_{obj_id}_{uuid.uuid4().hex[:8]}.png"
        fpath = os.path.join(folder, fname)

        with open(fpath, 'wb') as f:
            f.write(base64.b64decode(b64_data))
        return fpath
    except Exception as e:
        print(f"Save base64 error: {e}")
        return None

# Wrappers for upload
def save_avatar_from_form(file, uid): return _save_img_common(file, AVATAR_UPLOAD_FOLDER, 'avatar', uid)
def save_avatar_from_base64(data, uid): return _save_b64_common(data, AVATAR_UPLOAD_FOLDER, 'avatar', uid)
def save_food_image_from_form(file, fid): return _save_img_common(file, FOOD_UPLOAD_FOLDER, 'food', fid)
def save_food_image_from_base64(data, fid): return _save_b64_common(data, FOOD_UPLOAD_FOLDER, 'food', fid)

def get_relative_url(abs_path):
    if not abs_path or not os.path.isabs(abs_path): return abs_path
    try:
        if abs_path.startswith(FOOD_UPLOAD_FOLDER):
            return f'/food_images/{os.path.relpath(abs_path, FOOD_UPLOAD_FOLDER).replace(os.sep, "/")}'
        elif abs_path.startswith(AVATAR_UPLOAD_FOLDER):
            return f'/uploads/avatars/{os.path.relpath(abs_path, AVATAR_UPLOAD_FOLDER).replace(os.sep, "/")}'
        return f'/uploads/{os.path.relpath(abs_path, UPLOAD_BASE_PATH).replace(os.sep, "/")}'
    except:
        return abs_path

def init_db_data():
    if not os.path.exists(db_path):
        with app.app_context():
            db.create_all()
            # Initial data
            db.session.add_all([
                Food(name='宫保鸡丁', price=28.0, stock=50),
                Food(name='清炒时蔬', price=18.0, stock=100),
                Food(name='红烧肉', price=45.0, stock=30),
                User(name='张三', gender='男', age=22, balance=200.0),
                User(name='李四', gender='女', age=25, balance=150.0),
                Employee(name='王五', position='清洁', work_days=25, monthly_salary=3000),
                Employee(name='赵六', position='服务员', work_days=28, monthly_salary=3500),
                Employee(name='钱七', position='厨师', work_days=30, monthly_salary=6000),
                Employee(name='孙八', position='经理', work_days=30, monthly_salary=8000),
                Employee(name='周九', position='迎宾', work_days=26, monthly_salary=3200)
            ])
            db.session.commit()
            print("DB initialized.")


# --- Routes ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    try:
        if filename.startswith('avatars/'):
            fpath = os.path.join(AVATAR_UPLOAD_FOLDER, filename.replace('avatars/', '', 1))
        else:
            fpath = os.path.join(UPLOAD_BASE_PATH, filename)
        
        # Security check
        if not os.path.abspath(fpath).startswith(os.path.abspath(UPLOAD_BASE_PATH)):
            return jsonify({'error': 'Forbidden'}), 403

        if os.path.exists(fpath):
            return send_file(fpath)
        
        # Fallback to default
        default = 'default-avatar.png' if 'avatar' in filename else 'default-food.png'
        dpath = os.path.join(STATIC_FOLDER, default)
        if os.path.exists(dpath):
            return send_file(dpath)
        return jsonify({'error': 'Not found'}), 404
    except Exception as e:
        print(f"File serve error: {e}")
        return jsonify({'error': 'Server error'}), 500

@app.route('/food_images/<path:filename>')
def food_images(filename):
    try:
        fpath = os.path.join(FOOD_UPLOAD_FOLDER, filename)
        if not os.path.abspath(fpath).startswith(os.path.abspath(FOOD_UPLOAD_FOLDER)):
            return jsonify({'error': 'Forbidden'}), 403
            
        if os.path.exists(fpath):
            return send_file(fpath)
        
        dpath = os.path.join(STATIC_FOLDER, 'default-food.png')
        return send_file(dpath) if os.path.exists(dpath) else (jsonify({'error': 'Not found'}), 404)
    except Exception as e:
        print(f"Food image error: {e}")
        return jsonify({'error': 'Server error'}), 500

@app.route('/api/stats')
def stats():
    emps = Employee.query.all()
    total_expense = sum([(e.monthly_salary/30 * e.work_days) for e in emps if e.monthly_salary])
    
    return jsonify({
        'user_count': User.query.count(),
        'order_count': Order.query.count(),
        'total_sales': float(db.session.query(db.func.sum(Order.total_price)).scalar() or 0),
        'food_count': Food.query.count(),
        'employee_count': Employee.query.count(),
        'total_salary_expense': round(total_expense, 2)
    })

# --- APIs ---

@app.route('/api/upload_avatar', methods=['POST'])
def upload_avatar():
    # support multiple field names
    f = request.files.get('avatar') or request.files.get('image') or request.files.get('file')
    if not f: return jsonify({'error': 'No file'}), 400
    
    uid = request.form.get('user_id', '0')
    if f.filename == '': return jsonify({'error': 'No selection'}), 400

    path = save_avatar_from_form(f, uid)
    if path:
        url = get_relative_url(path)
        if uid and uid != '0':
            try:
                u = User.query.get(int(uid))
                if u:
                    u.avatar = path
                    db.session.commit()
            except Exception as e:
                print(f"Update avatar db error: {e}")
        return jsonify({'url': url, 'message': 'success'})
    return jsonify({'error': 'Invalid file'}), 400

@app.route('/api/upload_food_image', methods=['POST'])
def upload_food_image():
    f = request.files.get('food_image') or request.files.get('image') or request.files.get('file')
    if not f: return jsonify({'error': 'No file'}), 400
    
    fid = request.form.get('food_id', '0')
    if f.filename == '': return jsonify({'error': 'No selection'}), 400

    path = save_food_image_from_form(f, fid)
    if path:
        url = get_relative_url(path)
        if fid and fid != '0':
            try:
                food = Food.query.get(int(fid))
                if food:
                    food.image = path
                    db.session.commit()
            except Exception as e:
                print(f"Update food image db error: {e}")
        return jsonify({'url': url, 'message': 'success'})
    return jsonify({'error': 'Invalid file'}), 400

@app.route('/api/users', methods=['GET', 'POST'])
def users():
    if request.method == 'GET':
        name = request.args.get('name', '')
        q = User.query
        if name: q = q.filter(User.name.contains(name))
        return jsonify([u.to_dict() for u in q.all()])

    # Create User
    data = request.get_json()
    avt = data.get('avatar', '')
    avt_path = save_avatar_from_base64(avt, 0) if avt.startswith('data:image') else avt

    u = User(
        name=data['name'],
        gender=data.get('gender', '男'),
        age=data.get('age', 18),
        balance=float(data.get('balance', 100)),
        password=data.get('password', '123456'),
        avatar=avt_path or ''
    )
    db.session.add(u)
    db.session.commit()
    return jsonify(u.to_dict())

@app.route('/api/users/<int:uid>', methods=['PUT', 'DELETE'])
def user_detail(uid):
    u = User.query.get_or_404(uid)
    if request.method == 'DELETE':
        db.session.delete(u)
        db.session.commit()
        return jsonify({'message': 'deleted'})

    data = request.get_json()
    u.name = data.get('name', u.name)
    u.gender = data.get('gender', u.gender)
    u.age = data.get('age', u.age)
    u.balance = float(data.get('balance', u.balance))
    if data.get('password'): u.password = data['password']
    
    avt = data.get('avatar', '')
    if avt.startswith('data:image'):
        u.avatar = save_avatar_from_base64(avt, uid)
    elif avt:
        u.avatar = avt
    
    db.session.commit()
    return jsonify(u.to_dict())

@app.route('/api/foods', methods=['GET', 'POST'])
def foods():
    if request.method == 'GET':
        name = request.args.get('name', '')
        q = Food.query
        if name: q = q.filter(Food.name.contains(name))
        return jsonify([f.to_dict() for f in q.all()])

    data = request.get_json()
    img = data.get('image', '')
    img_path = save_food_image_from_base64(img, 0) if img.startswith('data:image') else img

    f = Food(
        name=data['name'],
        price=float(data['price']),
        stock=int(data.get('stock', 0)),
        image=img_path or ''
    )
    db.session.add(f)
    db.session.commit()
    return jsonify(f.to_dict())

@app.route('/api/foods/<int:fid>', methods=['PUT', 'DELETE'])
def food_detail(fid):
    f = Food.query.get_or_404(fid)
    if request.method == 'DELETE':
        db.session.delete(f)
        db.session.commit()
        return jsonify({'message': 'deleted'})

    data = request.get_json()
    f.name = data.get('name', f.name)
    f.price = float(data.get('price', f.price))
    f.stock = int(data.get('stock', f.stock))
    
    img = data.get('image', '')
    if img.startswith('data:image'):
        f.image = save_food_image_from_base64(img, fid)
    elif img:
        f.image = img
        
    db.session.commit()
    return jsonify(f.to_dict())

@app.route('/api/orders', methods=['GET', 'POST'])
def orders():
    if request.method == 'GET':
        no = request.args.get('order_no', '')
        uname = request.args.get('user_name', '')
        q = Order.query
        if no: q = q.filter(Order.order_no.contains(no))
        if uname: q = q.join(User).filter(User.name.contains(uname))
        return jsonify([o.to_dict() for o in q.all()])

    data = request.get_json()
    uid = data['user_id']
    items = data['items']
    
    # Calculate total
    total = sum([Food.query.get(i['food_id']).price * i['quantity'] for i in items if Food.query.get(i['food_id'])])
    u = User.query.get(uid)
    
    if not u or u.balance < total:
        return jsonify({'error': 'Insufficient balance or user invalid'}), 400

    ord_no = f"ORD{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}{str(uuid.uuid4())[:4]}"
    new_order = Order(order_no=ord_no, user_id=uid, total_price=total)
    db.session.add(new_order)
    db.session.flush()

    for i in items:
        food = Food.query.get(i['food_id'])
        if food.stock < i['quantity']:
            db.session.rollback()
            return jsonify({'error': f'Stock out: {food.name}'}), 400
        
        db.session.add(OrderItem(
            order_id=new_order.id, food_id=i['food_id'],
            quantity=i['quantity'], price_snapshot=food.price
        ))
        food.stock -= i['quantity']

    u.balance -= total
    db.session.commit()
    return jsonify(new_order.to_dict())

@app.route('/api/orders/<int:oid>', methods=['PUT', 'DELETE'])
def order_detail(oid):
    o = Order.query.get_or_404(oid)

    if request.method == 'DELETE':
        # restore balance & stock
        o.user.balance += o.total_price
        for i in o.items:
            if i.food: i.food.stock += i.quantity
        db.session.delete(o)
        db.session.commit()
        return jsonify({'message': 'deleted'})

    # Update logic (complicated)
    data = request.get_json()
    if 'items' in data:
        # Revert old
        o.user.balance += o.total_price
        for i in o.items:
            if i.food: i.food.stock += i.quantity
            db.session.delete(i)
        
        # Apply new
        total = 0
        for item in data['items']:
            f = Food.query.get(item['food_id'])
            if not f: 
                db.session.rollback()
                return jsonify({'error': 'Invalid food'}), 400
            total += f.price * item['quantity']
            f.stock -= item['quantity']
            db.session.add(OrderItem(order_id=o.id, food_id=f.id, quantity=item['quantity'], price_snapshot=f.price))
        
        o.total_price = total
        if o.user.balance < total:
            db.session.rollback()
            return jsonify({'error': 'Insufficient balance'}), 400
        o.user.balance -= total

    db.session.commit()
    return jsonify(o.to_dict())

@app.route('/api/employees', methods=['GET', 'POST'])
def employees():
    if request.method == 'GET':
        name = request.args.get('name', '')
        pos = request.args.get('position', '')
        q = Employee.query
        if name: q = q.filter(Employee.name.contains(name))
        if pos: q = q.filter(Employee.position == pos)
        return jsonify([e.to_dict() for e in q.all()])

    data = request.get_json()
    emp = Employee(
        name=data['name'], gender=data.get('gender', '男'),
        position=data['position'], work_days=int(data.get('work_days', 0)),
        monthly_salary=float(data.get('monthly_salary', 0))
    )
    db.session.add(emp)
    db.session.commit()
    return jsonify(emp.to_dict())

@app.route('/api/employees/<int:eid>', methods=['PUT', 'DELETE'])
def employee_detail(eid):
    e = Employee.query.get_or_404(eid)
    if request.method == 'DELETE':
        db.session.delete(e)
        db.session.commit()
        return jsonify({'message': 'deleted'})

    data = request.get_json()
    for k in ['name', 'gender', 'position']:
        if k in data: setattr(e, k, data[k])
    e.work_days = int(data.get('work_days', e.work_days))
    e.monthly_salary = float(data.get('monthly_salary', e.monthly_salary))
    
    db.session.commit()
    return jsonify(e.to_dict())

if __name__ == '__main__':
    init_db_data()
    print("Server running on 5000...")
    app.run(debug=True, host='0.0.0.0', port=5000)
