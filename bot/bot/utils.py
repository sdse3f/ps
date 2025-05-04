import random
import string
import json
import uuid
import base64
import smtplib
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import current_app
import jwt
from datetime import datetime, timedelta
from . import db
from .models import AuditLog
import bcrypt


def hash_password(password):
    """
    تشفير كلمة المرور باستخدام bcrypt
    """
  
    password_bytes = password.encode('utf-8')

    salt = bcrypt.gensalt(rounds=12) 
    hashed_password = bcrypt.hashpw(password_bytes, salt)
    
    return hashed_password.decode('utf-8')

def verify_password(plain_password, hashed_password):
    """
    التحقق من صحة كلمة المرور
    """
    return bcrypt.checkpw(
        plain_password.encode('utf-8'), 
        hashed_password.encode('utf-8')
    )


def generate_verification_code():
    """توليد رمز تحقق مكون من 6 أرقام"""
    return ''.join(random.choices(string.digits, k=6))

def send_verification_email(to_email, verification_code, email_config):
    """إرسال بريد إلكتروني للتحقق باستخدام Gmail"""
    try:
        msg = MIMEMultipart()
        msg['From'] = f"{email_config['sender_name']} <{email_config['username']}>"
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
        
        server = smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port'])
        server.starttls()
        server.login(email_config['username'], email_config['password'])
        server.send_message(msg)
        server.quit()
        
        return True
    except Exception as e:
        print(f"خطأ في إرسال البريد الإلكتروني: {str(e)}")
        return False

def upload_image_to_cloudflare(image_data, cloudflare_config):
    """رفع صورة إلى Cloudflare Images"""
    try:
        headers = {
            'Authorization': f'Bearer {cloudflare_config["api_token"]}'
        }

        image_id = str(uuid.uuid4())

        files = {
            'file': (f'{image_id}.jpg', base64.b64decode(image_data.split(',')[1]), 'image/jpeg')
        }
        
        metadata = {
            'id': image_id
        }
        
        response = requests.post(
            f'https://api.cloudflare.com/client/v4/accounts/{cloudflare_config["account_id"]}/images/v1',
            headers=headers,
            files=files,
            data={'metadata': json.dumps(metadata)}
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                image_data = result.get('result', {})
                return {
                    'id': image_data.get('id'),
                    'url': f"{cloudflare_config['image_delivery_url']}/{image_data.get('id')}/public"
                }
        
        return None
    except Exception as e:
        print(f"خطأ في رفع الصورة: {str(e)}")
        return None

def send_verification_email(to_email, message_body=None, email_config=None, verification_code=None, subject=None, is_html=False):
    """إرسال بريد إلكتروني للتحقق أو إعادة تعيين كلمة المرور"""
    try:
        if not email_config:
            from flask import current_app
            email_config = current_app.config.get('EMAIL_CONFIG', {})

        username = email_config.get('username')
        password = email_config.get('password')
        
        if not username or not password:
       
            print(f"خطأ: اسم المستخدم أو كلمة المرور للبريد الإلكتروني غير موجودة")
            return False
        
        msg = MIMEMultipart()
        sender_name = email_config.get('sender_name', 'نقطة وصل')
        msg['From'] = f"{sender_name} <{username}>"
        msg['To'] = to_email
        msg['Subject'] = subject or "رمز التحقق من حسابك"

        if not message_body and verification_code:
  
            message_body = f"""
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
            is_html = True

        if is_html:
            msg.attach(MIMEText(message_body, 'html'))
        else:
            msg.attach(MIMEText(message_body, 'plain'))
        
        smtp_server = email_config.get('smtp_server', 'smtp.gmail.com')
        smtp_port = int(email_config.get('smtp_port', 587))
        
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(username, password)
        server.send_message(msg)
        server.quit()
        
        return True
    except Exception as e:
        print(f"خطأ في إرسال البريد الإلكتروني: {str(e)}")
        return False
    
    
    
def log_activity(user_id, action, entity_type, entity_id, details=None, request=None):
    """تسجيل النشاط في سجل التدقيق"""
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

def create_token(user_id, is_admin, expiry_days=30):
    """إنشاء توكن المصادقة"""
    return jwt.encode({
        'user_id': user_id,
        'is_admin': is_admin,
        'exp': datetime.utcnow() + timedelta(days=expiry_days)
    }, current_app.config['SECRET_KEY'], algorithm="HS256")

def verify_token(token):
    """التحقق من صحة التوكن"""
    try:
        data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
        return data
    except:
        return None