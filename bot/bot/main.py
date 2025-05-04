from flask import Flask, request, jsonify, session
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from sqlalchemy.sql import func, desc
from sqlalchemy.orm import relationship, backref
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv
import jwt
import os
import random
import string
import json
import smtplib
import base64
import uuid
import requests

from . import db

load_dotenv()

EMAIL_CONFIG = {
    'smtp_server': os.getenv('EMAIL_SMTP_SERVER', 'smtp.gmail.com'),
    'smtp_port': int(os.getenv('EMAIL_SMTP_PORT', 587)),
    'username': os.getenv('EMAIL_USERNAME'),
    'password': os.getenv('EMAIL_PASSWORD'),
    'sender_name': os.getenv('EMAIL_SENDER_NAME', 'نقطة وصل')
}

CLOUDFLARE_CONFIG = {
    'account_id': os.getenv('CLOUDFLARE_ACCOUNT_ID'),
    'api_token': os.getenv('CLOUDFLARE_API_TOKEN'),
    'image_delivery_url': os.getenv('CLOUDFLARE_IMAGE_DELIVERY_URL')
}

def generate_verification_code():
    return ''.join(random.choices(string.digits, k=6))

def send_verification_email(to_email, verification_code):
    try:
        msg = MIMEMultipart()
        msg['From'] = f"{EMAIL_CONFIG['sender_name']} <{EMAIL_CONFIG['username']}>"
        msg['To'] = to_email
        msg['Subject'] = "رمز التحقق من حسابك"
        
        body = f"""
        <html>
        <body dir="rtl" style="font-family: Arial, sans-serif;">
            <h2>مرحباً بك في موقعنا</h2>
            <p>شكراً لتسجيلك معنا. يرجى استخدام الرمز التالي للتحقق من حسابك:</p>
            <h1 style="color: #4CAF50; text-align: center;">{verification_code}</h1>
            <p>هذا الرمز صالح لمدة ساعة واحدة فقط.</p>
            <p>مع تحياتنا،<br>فريق الموقع</p>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
        server.starttls()
        server.login(EMAIL_CONFIG['username'], EMAIL_CONFIG['password'])
        server.send_message(msg)
        server.quit()
        
        return True
    except Exception as e:
        return False

def upload_image_to_cloudflare(image_data):
    try:
        from .image_service import ImageService
        return ImageService.upload_image(image_data, folder='uploads')
    except Exception as e:

        from flask import current_app
        current_app.logger.error(f"خطأ في رفع الصورة: {str(e)}")
        return None



def log_activity(user_id, action, entity_type, entity_id, details=None, request=None):
    from .models import AuditLog
    
    ip_address = None
    if request:
        ip_address = request.remote_addr
    
    log = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        ip_address=ip_address
    )
    
    db.session.add(log)
    db.session.commit()

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
   
        from .models import User
        from flask import current_app
        
        token = None

        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        if not token and 'auth_token' in session:
            token = session['auth_token']
            
        if not token:
            return jsonify({'success': False, 'message': 'يجب تسجيل الدخول للوصول إلى هذه الخدمة'}), 401
        
        try:
            data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = User.query.get(data['user_id'])
            if not current_user:
                return jsonify({'success': False, 'message': 'المستخدم غير موجود'}), 401

            if current_user.is_banned:
                return jsonify({'success': False, 'message': 'تم حظر حسابك. يرجى التواصل مع الإدارة'}), 403
        except:
            return jsonify({'success': False, 'message': 'التوكن غير صالح أو منتهي الصلاحية'}), 401
            
        return f(current_user, *args, **kwargs)
    
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        from .models import User
        from flask import current_app
        
        token = None

        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        if not token and 'auth_token' in session:
            token = session['auth_token']
            
        if not token:
            return jsonify({'success': False, 'message': 'يجب تسجيل الدخول للوصول إلى هذه الخدمة'}), 401
        
        try:
            data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = User.query.get(data['user_id'])
            if not current_user:
                return jsonify({'success': False, 'message': 'المستخدم غير موجود'}), 401

            if not current_user.is_admin:
                return jsonify({'success': False, 'message': 'ليس لديك صلاحية للوصول إلى هذه الخدمة'}), 403
        except:
            return jsonify({'success': False, 'message': 'التوكن غير صالح أو منتهي الصلاحية'}), 401
            
        return f(current_user, *args, **kwargs)
    
    return decorated

def init_app(app):
    with app.app_context():
        db.create_all()

        create_initial_data()
        
    from .routes import register_blueprints
    register_blueprints(app)

    from .context_processors import inject_common_data
    app.context_processor(inject_common_data)

def create_initial_data():
    try:
        from .models import User, Category
        admin_exists = User.query.filter_by(email=os.getenv('ADMIN_EMAIL')).first()
        if not admin_exists and os.getenv('ADMIN_EMAIL') and os.getenv('ADMIN_PASSWORD'):
            admin_user = User(
                email=os.getenv('ADMIN_EMAIL'),
                password=generate_password_hash(os.getenv('ADMIN_PASSWORD'), method='pbkdf2:sha256'),
                name='admin system',
                is_verified=True,
                is_admin=True
            )
            db.session.add(admin_user)

        categories_exist = Category.query.first()
        if not categories_exist:
            main_categories = [
                {'name': 'إلكترونيات', 'slug': 'electronics', 'description': 'أجهزة إلكترونية وتقنية'},
                {'name': 'مركبات', 'slug': 'vehicles', 'description': 'سيارات، دراجات، وسائل نقل'},
                {'name': 'عقارات', 'slug': 'property', 'description': 'منازل، شقق، أراضي'},
                {'name': 'المنزل والحديقة', 'slug': 'home', 'description': 'أثاث، مستلزمات المنزل، حدائق'},
                {'name': 'الموضة والملابس', 'slug': 'fashion', 'description': 'ملابس، أحذية، إكسسوارات'},
                {'name': 'الهوايات والترفيه', 'slug': 'hobby', 'description': 'ألعاب، كتب، آلات موسيقية'},
                {'name': 'الرياضة واللياقة البدنية', 'slug': 'sports', 'description': 'معدات رياضية، ملابس رياضية'},
                {'name': 'الأطفال والألعاب', 'slug': 'kids', 'description': 'مستلزمات الأطفال، ألعاب'},
                {'name': 'أخرى', 'slug': 'other', 'description': 'منتجات لا تندرج تحت التصنيفات الأخرى'}
            ]
            
            for cat_data in main_categories:
                category = Category(
                    name=cat_data['name'],
                    slug=cat_data['slug'],
                    description=cat_data['description']
                )
                db.session.add(category)
            
        
            db.session.commit()

            electronics = Category.query.filter_by(slug='electronics').first()
            if electronics:
                electronics_subcategories = [
                    {'name': 'هواتف محمولة', 'slug': 'phones', 'description': 'هواتف ذكية وملحقاتها'},
                    {'name': 'أجهزة كمبيوتر', 'slug': 'computers', 'description': 'حواسيب محمولة، حواسيب مكتبية'},
                    {'name': 'أجهزة لوحية', 'slug': 'tablets', 'description': 'آيباد، تابلت أندرويد وغيرها'},
                    {'name': 'تلفزيونات وصوتيات', 'slug': 'tv-audio', 'description': 'تلفزيونات، أنظمة صوت'},
                    {'name': 'كاميرات', 'slug': 'cameras', 'description': 'كاميرات رقمية، كاميرات فيديو'}
                ]
                
                for sub_data in electronics_subcategories:
                    sub_category = Category(
                        name=sub_data['name'],
                        slug=sub_data['slug'],
                        description=sub_data['description'],
                        parent_id=electronics.id
                    )
                    db.session.add(sub_category)

            vehicles = Category.query.filter_by(slug='vehicles').first()
            if vehicles:
                vehicles_subcategories = [
                    {'name': 'سيارات', 'slug': 'cars', 'description': 'سيارات مستعملة وجديدة'},
                    {'name': 'دراجات نارية', 'slug': 'motorcycles', 'description': 'دراجات نارية وسكوترات'},
                    {'name': 'قطع غيار', 'slug': 'spare-parts', 'description': 'قطع غيار وإكسسوارات المركبات'},
                    {'name': 'شاحنات وحافلات', 'slug': 'trucks-buses', 'description': 'مركبات تجارية ونقل'}
                ]
                
                for sub_data in vehicles_subcategories:
                    sub_category = Category(
                        name=sub_data['name'],
                        slug=sub_data['slug'],
                        description=sub_data['description'],
                        parent_id=vehicles.id
                    )
                    db.session.add(sub_category)
        
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()