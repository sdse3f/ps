import os
import logging
import sys
import traceback
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect


__version__ = '1.0.0'


db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()

def create_app():
    try:
        print("بدء إنشاء تطبيق Flask...")
        app = Flask(__name__)

  
        app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 's0$j329o];UtV{4=1[yEC')
        app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///marketplace.db')
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

      
        app.config['CLOUDFLARE_CONFIG'] = {
            'account_id': os.getenv('CLOUDFLARE_ACCOUNT_ID'),
            'api_token': os.getenv('CLOUDFLARE_API_TOKEN'),
            'image_delivery_url': os.getenv('CLOUDFLARE_IMAGE_DELIVERY_URL')
        }

   
        app.config['IMAGES_CONFIG'] = {
            'max_size': int(os.getenv('MAX_IMAGE_SIZE', 5 * 1024 * 1024)),
            'default_avatar': '/static/images/users/default-avatar.png',
            'default_product': '/static/images/products/product-placeholder.jpg',
            'allowed_extensions': ['jpg', 'jpeg', 'png', 'gif'],
        }

        app.config['EMAIL_CONFIG'] = {
            'smtp_server': os.getenv('EMAIL_SMTP_SERVER', 'smtp.gmail.com'),
            'smtp_port': int(os.getenv('EMAIL_SMTP_PORT', 587)),
            'username': os.getenv('EMAIL_USERNAME'),
            'password': os.getenv('EMAIL_PASSWORD'),
            'sender_name': os.getenv('EMAIL_SENDER_NAME', 'نقطة وصل')
        }


        if not app.debug:
            handler = logging.StreamHandler()
            handler.setLevel(logging.INFO)
            app.logger.addHandler(handler)
        else:
            handler = logging.StreamHandler()
            handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            app.logger.addHandler(handler)
            app.logger.setLevel(logging.DEBUG)
            
            app.logger.info("تم تفعيل وضع التصحيح مع تسجيل مفصل")


        cloudflare_config = app.config['CLOUDFLARE_CONFIG']
        if all([
            cloudflare_config['account_id'],
            cloudflare_config['api_token'],
            cloudflare_config['image_delivery_url']
        ]):
            app.logger.info("تم تكوين Cloudflare بنجاح، سيتم استخدامه لتخزين الصور")
        else:
            app.logger.warning("تكوين Cloudflare غير مكتمل، سيتم استخدام التخزين المحلي للصور")

        print("إنشاء مجلدات الصور...")
  
        static_folder = app.static_folder
        image_folders = ['products', 'users', 'uploads', 'categories', 'placeholders']
        for folder in image_folders:
            folder_path = os.path.join(static_folder, 'images', folder)
            os.makedirs(folder_path, exist_ok=True)
          
            try:
                test_file_path = os.path.join(folder_path, '.test_write')
                with open(test_file_path, 'w') as f:
                    f.write('test')
                os.remove(test_file_path)
                app.logger.info(f"تم التأكد من وجود مجلد الصور وهو قابل للكتابة: {folder_path}")
            except Exception as e:
                app.logger.warning(f"مجلد الصور موجود لكن قد لا يكون قابلاً للكتابة: {folder_path} - {str(e)}")

        print("تهيئة امتدادات Flask...")
  
        CORS(app)
        db.init_app(app)
        migrate.init_app(app, db)
        csrf.init_app(app)


        from .context_processors import format_price, time_since, get_condition_name, format_date, action_badge_class, action_name, entity_type_name
        app.jinja_env.filters['format_price'] = format_price
        app.jinja_env.filters['time_since'] = time_since
        app.jinja_env.filters['get_condition_name'] = get_condition_name
        app.jinja_env.filters['format_date'] = format_date
        app.jinja_env.filters['action_badge_class'] = action_badge_class
        app.jinja_env.filters['action_name'] = action_name
        app.jinja_env.filters['entity_type_name'] = entity_type_name


        from .image_service import ImageService
        
        @app.template_filter('image_url')
        def image_url_filter(image_id, default=None, folder='uploads'):
            """مرشح لعرض روابط الصور في القوالب"""
            if not default:
                if folder == 'users':
                    default = app.config['IMAGES_CONFIG']['default_avatar']
                elif folder == 'products':
                    default = app.config['IMAGES_CONFIG']['default_product']
            

            if not image_id:
                app.logger.debug(f"image_url_filter: معرف صورة فارغ، استخدام الافتراضي: {default}")
                return default
            
            app.logger.debug(f"image_url_filter: طلب URL للصورة {image_id} من المجلد {folder}")
            
     
            if isinstance(image_id, str) and (image_id.startswith(('http://', 'https://', '/'))):
                app.logger.debug(f"image_url_filter: معرف الصورة هو URL مطلق: {image_id}")
                return image_id
            
         
            url = ImageService.get_image_url(image_id, default, folder)
            app.logger.debug(f"image_url_filter: URL الناتج: {url}")
            return url
        
        app.jinja_env.filters['image_url'] = image_url_filter

        print("إنشاء قاعدة البيانات وتسجيل المسارات...")
   
        with app.app_context():
            from .image_service import ImageService
            app.logger.info("جاري إنشاء الصور الافتراضية...")
            try:
                ImageService.create_placeholder_images()
                app.logger.info("تم إنشاء الصور الافتراضية بنجاح")
            except Exception as e:
                app.logger.error(f"فشل في إنشاء الصور الافتراضية: {str(e)}")

            db.create_all()

            from .routes import register_blueprints
            register_blueprints(app)

            from .context_processors import inject_common_data
            app.context_processor(inject_common_data)
            

            try:
                from .main import create_initial_data
                create_initial_data()
            except Exception as e:
                app.logger.warning(f"ملاحظة: لم يتم إنشاء البيانات الأولية: {str(e)}")
                app.logger.info("يمكنك تنفيذ الأمر 'flask create-data' لاحقاً لإنشاء البيانات الأولية.")

  
        app.logger.info(f"URL خادم التطبيق: {os.getenv('SERVER_URL', 'http://localhost:5000')}")
        app.logger.info(f"تكوين مجلد static: {app.static_folder}")
        app.logger.info(f"تكوين معالجة الصور: استخدام Cloudflare = {bool(all([app.config['CLOUDFLARE_CONFIG']['account_id'], app.config['CLOUDFLARE_CONFIG']['api_token'], app.config['CLOUDFLARE_CONFIG']['image_delivery_url']]))}")
        
        print("تم إنشاء التطبيق بنجاح!")
        return app
    
    except Exception as e:
        print(f"خطأ في إنشاء التطبيق: {str(e)}")
        traceback.print_exc()
    
        return None