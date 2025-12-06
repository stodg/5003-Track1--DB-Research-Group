import os
import datetime
import json
import base64
import uuid
import traceback
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

# ================= 配置与初始化 =================
app = Flask(__name__, static_folder='static')

# 【关键】修改 Flask 模板标签，避免与 Vue 的 {{ }} 冲突
app.jinja_env.variable_start_string = '[['
app.jinja_env.variable_end_string = ']]'

CORS(app)

# 数据库配置
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(BASE_DIR, 'restaurant.db')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 文件上传配置 - 使用相对路径确保跨平台兼容性
UPLOAD_BASE_PATH = os.path.join(BASE_DIR, 'uploads')
AVATAR_UPLOAD_FOLDER = os.path.join(UPLOAD_BASE_PATH, 'avatars')
FOOD_UPLOAD_FOLDER = os.path.join(BASE_DIR, 'food_images')  # 使用相对路径

# 确保上传目录存在
os.makedirs(AVATAR_UPLOAD_FOLDER, exist_ok=True)
os.makedirs(FOOD_UPLOAD_FOLDER, exist_ok=True)
print(f"✅ 创建头像上传目录: {AVATAR_UPLOAD_FOLDER}")
print(f"✅ 创建菜品图片上传目录: {FOOD_UPLOAD_FOLDER}")

# 静态文件目录
STATIC_FOLDER = os.path.join(BASE_DIR, 'static')
if not os.path.exists(STATIC_FOLDER):
    os.makedirs(STATIC_FOLDER, exist_ok=True)

# 设置默认图片路径
DEFAULT_AVATAR_URL = '/static/default-avatar.png'
DEFAULT_FOOD_URL = '/static/default-food.png'

app.config['AVATAR_UPLOAD_FOLDER'] = AVATAR_UPLOAD_FOLDER
app.config['FOOD_UPLOAD_FOLDER'] = FOOD_UPLOAD_FOLDER
app.config['UPLOAD_BASE_PATH'] = UPLOAD_BASE_PATH
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

db = SQLAlchemy(app)


# ================= 数据库模型 =================

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
        avatar_url = self.avatar or DEFAULT_AVATAR_URL

        # 【修复】增强头像URL处理逻辑
        if self.avatar:
            # 如果已经是完整的URL或相对路径，直接使用
            if self.avatar.startswith('http') or self.avatar.startswith('/'):
                avatar_url = self.avatar
            # 如果是绝对路径，转换为相对URL
            elif os.path.isabs(self.avatar):
                try:
                    # 检查是否是头像路径
                    if self.avatar.startswith(AVATAR_UPLOAD_FOLDER):
                        rel_path = os.path.relpath(self.avatar, AVATAR_UPLOAD_FOLDER)
                        avatar_url = f'/uploads/avatars/{rel_path.replace(os.sep, "/")}'
                    else:
                        rel_path = os.path.relpath(self.avatar, UPLOAD_BASE_PATH)
                        avatar_url = f'/uploads/{rel_path.replace(os.sep, "/")}'
                except Exception as e:
                    print(f"转换头像路径出错: {e}")
                    avatar_url = DEFAULT_AVATAR_URL

        return {
            'id': self.id,
            'name': self.name,
            'gender': self.gender,
            'age': self.age,
            'balance': float(self.balance) if self.balance else 0.0,
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
            'monthly_salary': float(self.monthly_salary) if self.monthly_salary else 0.0,
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

        # 如果是绝对路径，转换为相对URL
        if self.image and os.path.isabs(self.image):
            # 检查是否是菜品图片路径
            if self.image.startswith(FOOD_UPLOAD_FOLDER):
                rel_path = os.path.relpath(self.image, FOOD_UPLOAD_FOLDER)
                image_url = f'/food_images/{rel_path.replace(os.sep, "/")}'
            else:
                rel_path = os.path.relpath(self.image, UPLOAD_BASE_PATH)
                image_url = f'/uploads/{rel_path.replace(os.sep, "/")}'
        elif self.image and (self.image.startswith('/uploads/') or self.image.startswith('/food_images/')):
            image_url = self.image

        return {
            'id': self.id,
            'name': self.name,
            'price': float(self.price) if self.price else 0.0,
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
            'user_name': self.user.name if self.user else '未知用户',
            'total_price': float(self.total_price) if self.total_price else 0.0,
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
        food_image = self.food.image if self.food else ''
        if food_image and os.path.isabs(food_image):
            # 检查是否是菜品图片路径
            if food_image.startswith(FOOD_UPLOAD_FOLDER):
                rel_path = os.path.relpath(food_image, FOOD_UPLOAD_FOLDER)
                food_image = f'/food_images/{rel_path.replace(os.sep, "/")}'
            else:
                rel_path = os.path.relpath(food_image, UPLOAD_BASE_PATH)
                food_image = f'/uploads/{rel_path.replace(os.sep, "/")}'
        elif food_image and (food_image.startswith('/uploads/') or food_image.startswith('/food_images/')):
            food_image = food_image

        return {
            'food_id': self.food_id,
            'food_name': self.food.name if self.food else '未知菜品',
            'image': food_image,
            'price': float(self.price_snapshot) if self.price_snapshot else 0.0,
            'quantity': self.quantity
        }


# ================= 辅助函数 =================

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_image_from_form(file, folder_name, prefix, obj_id):
    """通用的保存图片函数"""
    if not file or file.filename == '':
        return None

    if not allowed_file(file.filename):
        return None

    try:
        # 确保目录存在
        os.makedirs(folder_name, exist_ok=True)

        # 获取安全的文件名
        original_filename = secure_filename(file.filename)
        ext = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else 'jpg'
        filename = f"{prefix}_{obj_id}_{uuid.uuid4().hex[:8]}.{ext}"
        filepath = os.path.join(folder_name, filename)
        file.save(filepath)
        return filepath
    except Exception as e:
        print(f"保存图片失败: {e}")
        traceback.print_exc()
        return None


def save_image_from_base64(base64_data, folder_name, prefix, obj_id):
    """保存base64格式的图片"""
    if not base64_data:
        return None

    try:
        # 确保目录存在
        os.makedirs(folder_name, exist_ok=True)

        if 'base64,' in base64_data:
            base64_data = base64_data.split('base64,')[1]

        ext = 'png'  # 默认使用png格式
        filename = f"{prefix}_{obj_id}_{uuid.uuid4().hex[:8]}.{ext}"
        filepath = os.path.join(folder_name, filename)

        image_data = base64.b64decode(base64_data)
        with open(filepath, 'wb') as f:
            f.write(image_data)

        return filepath
    except Exception as e:
        print(f"保存base64图片失败: {e}")
        traceback.print_exc()
        return None


def save_avatar_from_form(file, user_id):
    """保存用户头像"""
    return save_image_from_form(file, AVATAR_UPLOAD_FOLDER, 'avatar', user_id)


def save_avatar_from_base64(base64_data, user_id):
    """保存base64格式的用户头像"""
    return save_image_from_base64(base64_data, AVATAR_UPLOAD_FOLDER, 'avatar', user_id)


def save_food_image_from_form(file, food_id):
    """保存菜品图片"""
    return save_image_from_form(file, FOOD_UPLOAD_FOLDER, 'food', food_id)


def save_food_image_from_base64(base64_data, food_id):
    """保存base64格式的菜品图片"""
    return save_image_from_base64(base64_data, FOOD_UPLOAD_FOLDER, 'food', food_id)


def get_relative_url(absolute_path):
    """将绝对路径转换为相对URL"""
    if not absolute_path or not os.path.isabs(absolute_path):
        return absolute_path

    try:
        # 检查是否是菜品图片路径
        if absolute_path.startswith(FOOD_UPLOAD_FOLDER):
            rel_path = os.path.relpath(absolute_path, FOOD_UPLOAD_FOLDER)
            return f'/food_images/{rel_path.replace(os.sep, "/")}'
        # 检查是否是头像路径
        elif absolute_path.startswith(AVATAR_UPLOAD_FOLDER):
            rel_path = os.path.relpath(absolute_path, AVATAR_UPLOAD_FOLDER)
            return f'/uploads/avatars/{rel_path.replace(os.sep, "/")}'
        else:
            rel_path = os.path.relpath(absolute_path, UPLOAD_BASE_PATH)
            return f'/uploads/{rel_path.replace(os.sep, "/")}'
    except Exception as e:
        print(f"转换相对URL失败: {e}")
        return absolute_path


# ================= 功能函数 =================

def init_db_data():
    if not os.path.exists(db_path):
        with app.app_context():
            db.create_all()

            # 初始菜品
            f1 = Food(name='宫保鸡丁', price=28.0, stock=50, image='')
            f2 = Food(name='清炒时蔬', price=18.0, stock=100, image='')
            f3 = Food(name='红烧肉', price=45.0, stock=30, image='')
            db.session.add_all([f1, f2, f3])

            # 初始用户
            u1 = User(name='张三', gender='男', age=22, balance=200.0, password='123456', avatar='')
            u2 = User(name='李四', gender='女', age=25, balance=150.0, password='123456', avatar='')
            db.session.add_all([u1, u2])

            # 初始员工数据
            e1 = Employee(name='王五', gender='男', position='清洁', work_days=25, monthly_salary=3000)
            e2 = Employee(name='赵六', gender='女', position='服务员', work_days=28, monthly_salary=3500)
            e3 = Employee(name='钱七', gender='男', position='厨师', work_days=30, monthly_salary=6000)
            e4 = Employee(name='孙八', gender='女', position='经理', work_days=30, monthly_salary=8000)
            e5 = Employee(name='周九', gender='男', position='迎宾', work_days=26, monthly_salary=3200)
            db.session.add_all([e1, e2, e3, e4, e5])

            db.session.commit()
            print("✅ 数据库初始化完成")


# ================= API 路由 =================

@app.route('/')
def index():
    return render_template('index.html')


# --- 文件访问路由 ---
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    try:
        # 处理头像路径
        if filename.startswith('avatars/'):
            file_path = os.path.join(AVATAR_UPLOAD_FOLDER, filename.replace('avatars/', '', 1))
        else:
            file_path = os.path.join(UPLOAD_BASE_PATH, filename)

        # 安全检查：确保文件在允许的目录内
        if not os.path.abspath(file_path).startswith(os.path.abspath(UPLOAD_BASE_PATH)):
            return jsonify({'error': '访问被拒绝'}), 403

        if os.path.exists(file_path):
            return send_file(file_path)
        else:
            # 尝试提供默认图片
            if 'avatar' in filename or 'avatars' in filename:
                default_path = os.path.join(STATIC_FOLDER, 'default-avatar.png')
            else:
                default_path = os.path.join(STATIC_FOLDER, 'default-food.png')

            if os.path.exists(default_path):
                return send_file(default_path)
            return jsonify({'error': '文件不存在'}), 404
    except Exception as e:
        print(f"提供文件失败: {e}")
        traceback.print_exc()
        return jsonify({'error': '服务器错误'}), 500


# 菜品图片访问路由
@app.route('/food_images/<path:filename>')
def food_images(filename):
    try:
        file_path = os.path.join(FOOD_UPLOAD_FOLDER, filename)

        # 安全检查：确保文件在允许的目录内
        if not os.path.abspath(file_path).startswith(os.path.abspath(FOOD_UPLOAD_FOLDER)):
            return jsonify({'error': '访问被拒绝'}), 403

        if os.path.exists(file_path):
            return send_file(file_path)
        else:
            # 尝试提供默认菜品图片
            default_path = os.path.join(STATIC_FOLDER, 'default-food.png')
            if os.path.exists(default_path):
                return send_file(default_path)
            return jsonify({'error': '文件不存在'}), 404
    except Exception as e:
        print(f"提供菜品图片失败: {e}")
        traceback.print_exc()
        return jsonify({'error': '服务器错误'}), 500


# --- 统计 ---
@app.route('/api/stats')
def stats():
    employees = Employee.query.all()
    total_salary_expense = 0
    for emp in employees:
        daily_salary = emp.monthly_salary / 30 if emp.monthly_salary else 0
        total_salary = daily_salary * emp.work_days
        total_salary_expense += total_salary

    return jsonify({
        'user_count': User.query.count(),
        'order_count': Order.query.count(),
        'total_sales': float(db.session.query(db.func.sum(Order.total_price)).scalar() or 0),
        'food_count': Food.query.count(),
        'employee_count': Employee.query.count(),
        'total_salary_expense': round(total_salary_expense, 2)
    })


# --- 头像上传 ---
@app.route('/api/upload_avatar', methods=['POST'])
def upload_avatar():
    """上传用户头像 - 修复版"""
    print("收到头像上传请求")

    # 【修复】支持多种字段名，与菜品上传保持一致
    file = None
    field_name = None

    if 'avatar' in request.files:
        file = request.files['avatar']
        field_name = 'avatar'
    elif 'image' in request.files:
        file = request.files['image']
        field_name = 'image'
    elif 'file' in request.files:
        file = request.files['file']
        field_name = 'file'

    if not file:
        print("没有找到文件字段，支持的字段名: avatar, image, file")
        return jsonify({'error': '没有选择文件，支持的字段名: avatar, image, file'}), 400

    user_id = request.form.get('user_id', '0')
    print(f"上传头像，用户ID: {user_id}, 文件名: {file.filename}, 字段名: {field_name}")

    if file.filename == '':
        return jsonify({'error': '没有选择文件'}), 400

    if file and allowed_file(file.filename):
        avatar_path = save_avatar_from_form(file, user_id)
        print(f"头像保存路径: {avatar_path}")

        if avatar_path:
            avatar_url = get_relative_url(avatar_path)
            print(f"生成的头像URL: {avatar_url}")

            # 如果user_id不是0，更新用户头像
            if user_id and user_id != '0':
                try:
                    user = User.query.get(int(user_id))
                    if user:
                        print(f"更新用户 {user_id} 的头像为: {avatar_path}")
                        user.avatar = avatar_path  # 保存绝对路径
                        db.session.commit()
                        print(f"用户 {user_id} 头像更新成功")
                except Exception as e:
                    print(f"更新用户头像失败: {e}")
                    traceback.print_exc()

            return jsonify({
                'url': avatar_url,
                'message': '上传成功',
                'field_used': field_name,
                'original_filename': file.filename
            })

    return jsonify({'error': '文件格式不支持'}), 400


# --- 菜品图片上传 ---
@app.route('/api/upload_food_image', methods=['POST'])
def upload_food_image():
    """上传菜品图片"""
    print("收到菜品图片上传请求")

    # 支持多种字段名
    file = None
    field_name = None

    if 'food_image' in request.files:
        file = request.files['food_image']
        field_name = 'food_image'
    elif 'image' in request.files:
        file = request.files['image']
        field_name = 'image'
    elif 'file' in request.files:
        file = request.files['file']
        field_name = 'file'

    if not file:
        return jsonify({'error': '没有选择文件，支持的字段名: food_image, image, file'}), 400

    food_id = request.form.get('food_id', '0')
    print(f"上传菜品图片，菜品ID: {food_id}, 文件名: {file.filename}")

    if file.filename == '':
        return jsonify({'error': '没有选择文件'}), 400

    if file and allowed_file(file.filename):
        food_image_path = save_food_image_from_form(file, food_id)
        print(f"菜品图片保存路径: {food_image_path}")

        if food_image_path:
            food_image_url = get_relative_url(food_image_path)
            print(f"生成的菜品图片URL: {food_image_url}")

            # 如果food_id不是0，更新菜品图片
            if food_id and food_id != '0':
                try:
                    food = Food.query.get(int(food_id))
                    if food:
                        print(f"更新菜品 {food_id} 的图片为: {food_image_path}")
                        food.image = food_image_path  # 保存绝对路径
                        db.session.commit()
                        print(f"菜品 {food_id} 图片更新成功")
                except Exception as e:
                    print(f"更新菜品图片失败: {e}")
                    traceback.print_exc()

            return jsonify({
                'url': food_image_url,
                'message': '上传成功',
                'field_used': field_name,
                'original_filename': file.filename
            })

    return jsonify({'error': '文件格式不支持'}), 400


# --- 用户管理 ---
@app.route('/api/users', methods=['GET', 'POST'])
def users():
    if request.method == 'GET':
        name = request.args.get('name', '')
        query = User.query
        if name:
            query = query.filter(User.name.contains(name))
        res = [u.to_dict() for u in query.all()]
        return jsonify(res)

    elif request.method == 'POST':
        data = request.get_json()
        password = data.get('password', '123456')
        avatar = data.get('avatar', '')
        balance = data.get('balance', 100.0)

        # 处理头像
        avatar_path = ''
        if avatar and avatar.startswith('data:image'):
            avatar_path = save_avatar_from_base64(avatar, 0)
        elif avatar:
            avatar_path = avatar

        new_user = User(
            name=data['name'],
            gender=data.get('gender', '男'),
            age=data.get('age', 18),
            balance=float(balance),
            password=password,
            avatar=avatar_path
        )
        db.session.add(new_user)
        db.session.commit()
        return jsonify(new_user.to_dict())


@app.route('/api/users/<int:user_id>', methods=['PUT', 'DELETE'])
def user_detail(user_id):
    user = User.query.get_or_404(user_id)

    if request.method == 'PUT':
        data = request.get_json()
        user.name = data.get('name', user.name)
        user.gender = data.get('gender', user.gender)
        user.age = data.get('age', user.age)
        user.balance = float(data.get('balance', user.balance))

        if data.get('password'):
            user.password = data['password']

        # 处理头像
        avatar = data.get('avatar', '')
        if avatar and avatar.startswith('data:image'):
            avatar_path = save_avatar_from_base64(avatar, user_id)
            user.avatar = avatar_path
        elif avatar:
            user.avatar = avatar

        db.session.commit()
        return jsonify(user.to_dict())

    elif request.method == 'DELETE':
        db.session.delete(user)
        db.session.commit()
        return jsonify({'message': '删除成功'})


# --- 菜品管理 ---
@app.route('/api/foods', methods=['GET', 'POST'])
def foods():
    if request.method == 'GET':
        name = request.args.get('name', '')
        query = Food.query
        if name:
            query = query.filter(Food.name.contains(name))
        res = [f.to_dict() for f in query.all()]
        return jsonify(res)

    elif request.method == 'POST':
        data = request.get_json()
        image = data.get('image', '')
        image_path = ''

        if image and image.startswith('data:image'):
            image_path = save_food_image_from_base64(image, 0)
        elif image:
            image_path = image

        new_food = Food(
            name=data['name'],
            price=float(data['price']),
            stock=int(data.get('stock', 0)),
            image=image_path
        )
        db.session.add(new_food)
        db.session.commit()
        return jsonify(new_food.to_dict())


@app.route('/api/foods/<int:food_id>', methods=['PUT', 'DELETE'])
def food_detail(food_id):
    food = Food.query.get_or_404(food_id)

    if request.method == 'PUT':
        data = request.get_json()
        food.name = data.get('name', food.name)
        food.price = float(data.get('price', food.price))
        food.stock = int(data.get('stock', food.stock))

        image = data.get('image', '')
        if image and image.startswith('data:image'):
            image_path = save_food_image_from_base64(image, food_id)
            food.image = image_path
        elif image:
            food.image = image

        db.session.commit()
        return jsonify(food.to_dict())

    elif request.method == 'DELETE':
        db.session.delete(food)
        db.session.commit()
        return jsonify({'message': '删除成功'})


# --- 订单管理 ---
@app.route('/api/orders', methods=['GET', 'POST'])
def orders():
    if request.method == 'GET':
        order_no = request.args.get('order_no', '')
        user_name = request.args.get('user_name', '')

        query = Order.query
        if order_no:
            query = query.filter(Order.order_no.contains(order_no))
        if user_name:
            query = query.join(User).filter(User.name.contains(user_name))

        orders = query.all()
        res = [o.to_dict() for o in orders]
        return jsonify(res)

    elif request.method == 'POST':
        data = request.get_json()
        user_id = data['user_id']
        items = data['items']

        # 生成订单号
        order_no = f"ORD{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}{str(uuid.uuid4())[:4]}"

        # 计算总价
        total_price = 0
        for item in items:
            food = Food.query.get(item['food_id'])
            if not food:
                return jsonify({'error': f'菜品 {item["food_id"]} 不存在'}), 400
            total_price += food.price * item['quantity']

        # 检查用户余额
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': '用户不存在'}), 400

        if user.balance < total_price:
            return jsonify({'error': '用户余额不足'}), 400

        # 创建订单
        new_order = Order(
            order_no=order_no,
            user_id=user_id,
            total_price=total_price
        )
        db.session.add(new_order)
        db.session.flush()

        # 创建订单项并扣减库存
        for item in items:
            food = Food.query.get(item['food_id'])
            if food.stock < item['quantity']:
                db.session.rollback()
                return jsonify({'error': f'菜品 {food.name} 库存不足'}), 400

            order_item = OrderItem(
                order_id=new_order.id,
                food_id=item['food_id'],
                quantity=item['quantity'],
                price_snapshot=food.price
            )
            db.session.add(order_item)

            # 扣减库存
            food.stock -= item['quantity']

        # 扣减用户余额
        user.balance -= total_price
        db.session.commit()

        return jsonify(new_order.to_dict())


@app.route('/api/orders/<int:order_id>', methods=['PUT', 'DELETE'])
def order_detail(order_id):
    order = Order.query.get_or_404(order_id)

    if request.method == 'PUT':
        data = request.get_json()

        # 如果是修改订单，需要复杂的逻辑处理
        if 'user_id' in data or 'items' in data:
            # 先恢复用户余额和库存
            user = order.user
            user.balance += order.total_price

            for item in order.items:
                food = Food.query.get(item.food_id)
                if food:
                    food.stock += item.quantity

            # 然后重新计算
            if 'user_id' in data:
                order.user_id = data['user_id']

            if 'items' in data:
                # 删除旧订单项
                for item in order.items:
                    db.session.delete(item)

                # 添加新订单项
                total_price = 0
                for item_data in data['items']:
                    food = Food.query.get(item_data['food_id'])
                    if not food:
                        db.session.rollback()
                        return jsonify({'error': f'菜品 {item_data["food_id"]} 不存在'}), 400

                    total_price += food.price * item_data['quantity']

                    order_item = OrderItem(
                        order_id=order.id,
                        food_id=item_data['food_id'],
                        quantity=item_data['quantity'],
                        price_snapshot=food.price
                    )
                    db.session.add(order_item)

                    # 扣减库存
                    food.stock -= item_data['quantity']

                order.total_price = total_price

            # 扣减新用户余额
            new_user = order.user
            if new_user.balance < order.total_price:
                db.session.rollback()
                return jsonify({'error': '用户余额不足'}), 400
            new_user.balance -= order.total_price

        db.session.commit()
        return jsonify(order.to_dict())

    elif request.method == 'DELETE':
        # 删除订单时恢复用户余额和库存
        user = order.user
        user.balance += order.total_price

        for item in order.items:
            food = Food.query.get(item.food_id)
            if food:
                food.stock += item.quantity

        db.session.delete(order)
        db.session.commit()
        return jsonify({'message': '删除成功'})


# --- 员工管理 ---
@app.route('/api/employees', methods=['GET', 'POST'])
def employees():
    if request.method == 'GET':
        name = request.args.get('name', '')
        position = request.args.get('position', '')

        query = Employee.query
        if name:
            query = query.filter(Employee.name.contains(name))
        if position:
            query = query.filter(Employee.position == position)

        res = [e.to_dict() for e in query.all()]
        return jsonify(res)

    elif request.method == 'POST':
        data = request.get_json()
        new_employee = Employee(
            name=data['name'],
            gender=data.get('gender', '男'),
            position=data['position'],
            work_days=int(data.get('work_days', 0)),
            monthly_salary=float(data.get('monthly_salary', 0))
        )
        db.session.add(new_employee)
        db.session.commit()
        return jsonify(new_employee.to_dict())


@app.route('/api/employees/<int:employee_id>', methods=['PUT', 'DELETE'])
def employee_detail(employee_id):
    employee = Employee.query.get_or_404(employee_id)

    if request.method == 'PUT':
        data = request.get_json()
        employee.name = data.get('name', employee.name)
        employee.gender = data.get('gender', employee.gender)
        employee.position = data.get('position', employee.position)
        employee.work_days = int(data.get('work_days', employee.work_days))
        employee.monthly_salary = float(data.get('monthly_salary', employee.monthly_salary))

        db.session.commit()
        return jsonify(employee.to_dict())

    elif request.method == 'DELETE':
        db.session.delete(employee)
        db.session.commit()
        return jsonify({'message': '删除成功'})


# ================= 启动应用 =================
if __name__ == '__main__':
    init_db_data()
    print("🚀 启动应用，版本3.1 - 用户头像上传修复版")
    print("✅ 包含所有模块：用户管理、订单管理、菜品库存、员工管理")
    print("✅ 图片上传问题已完全修复（包含用户头像和菜品图片）")
    print(f"✅ 头像上传目录: {AVATAR_UPLOAD_FOLDER}")
    print(f"✅ 头像访问URL示例: /uploads/avatars/avatar_1_xxxxxx.jpg")
    app.run(debug=True, host='0.0.0.0', port=5000)