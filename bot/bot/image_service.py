import os
import uuid
import base64
import requests
import json
from flask import current_app
import logging
from werkzeug.utils import secure_filename
import mimetypes

class ImageService:
    @staticmethod
    def allowed_file(filename):
        allowed_extensions = current_app.config.get('IMAGES_CONFIG', {}).get('allowed_extensions', ['jpg', 'jpeg', 'png', 'gif'])
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions
    
    @staticmethod
    def upload_image(image_data, folder='uploads'):
        try:
            cloudflare_config = current_app.config.get('CLOUDFLARE_CONFIG', {})
            image_id = str(uuid.uuid4())

            if isinstance(image_data, str) and ',' in image_data:
                file_data = base64.b64decode(image_data.split(',')[1])
            elif isinstance(image_data, str):
                file_data = base64.b64decode(image_data)
            else:
                file_data = image_data

            current_app.logger.info(f"معالجة صورة جديدة بمعرف: {image_id}")
            current_app.logger.info(f"نوع بيانات الصورة: {type(image_data)}")

            account_id = cloudflare_config.get('account_id')
            api_token = cloudflare_config.get('api_token')
            image_delivery_url = cloudflare_config.get('image_delivery_url')

            if account_id and api_token and image_delivery_url:
                current_app.logger.info("محاولة رفع الصورة إلى Cloudflare")
                try:
                    headers = {
                        'Authorization': f'Bearer {api_token}'
                    }
                    
                    files = {
                        'file': (f'{image_id}.jpg', file_data, 'image/jpeg')
                    }
                    
                    metadata = {
                        'id': image_id
                    }
                    
                    response = requests.post(
                        f'https://api.cloudflare.com/client/v4/accounts/{account_id}/images/v1',
                        headers=headers,
                        files=files,
                        data={'metadata': json.dumps(metadata)}
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        if result.get('success'):
                            image_data = result.get('result', {})
                            current_app.logger.info(f"تم رفع الصورة بنجاح إلى Cloudflare: {image_data.get('id')}")
                            return {
                                'id': image_data.get('id'),
                                'url': f"{image_delivery_url}/{image_data.get('id')}/public"
                            }
                        else:
                            current_app.logger.error(f"استجابة Cloudflare غير ناجحة: {result}")
                except Exception as cloudflare_error:
                    current_app.logger.error(f"فشل في رفع الصورة إلى Cloudflare: {str(cloudflare_error)}")
            else:
                current_app.logger.info("لم يتم تكوين Cloudflare بشكل كامل، سيتم استخدام التخزين المحلي")
            

            if file_data:
                try:
                    static_folder = current_app.static_folder
                    image_path = os.path.join(static_folder, 'images', folder)
                    os.makedirs(image_path, exist_ok=True)

                    image_extension = '.jpg'

                    try:
                       
                        import magic  
                        mime = magic.Magic(mime=True)
                        mime_type = mime.from_buffer(file_data[:1024])
                        if mime_type:
                            ext = mimetypes.guess_extension(mime_type)
                            if ext:
                                image_extension = ext
                    except ImportError:
                        if file_data.startswith(b'\xff\xd8'):
                            image_extension = '.jpg'
                        elif file_data.startswith(b'\x89PNG\r\n\x1a\n'):
                            image_extension = '.png'
                        elif file_data.startswith(b'GIF87a') or file_data.startswith(b'GIF89a'):
                            image_extension = '.gif'
                        elif file_data.startswith(b'RIFF') and file_data[8:12] == b'WEBP':
                            image_extension = '.webp'
                    
                    image_filename = f"{image_id}{image_extension}"
                    local_path = os.path.join(image_path, image_filename)
                    
                    current_app.logger.info(f"حفظ الصورة محلياً في: {local_path}")
                    
                    with open(local_path, 'wb') as f:
                        f.write(file_data)
                    
                    image_url = f"/static/images/{folder}/{image_filename}"
                    current_app.logger.info(f"تم حفظ الصورة محلياً بنجاح. URL: {image_url}")
                    
                    return {
                        'id': image_id,
                        'url': image_url
                    }
                except Exception as local_error:
                    current_app.logger.error(f"فشل في حفظ الصورة محلياً: {str(local_error)}")
                    current_app.logger.error(f"تفاصيل الخطأ المحلي: {str(local_error)}", exc_info=True)
            return None
            
        except Exception as e:
            current_app.logger.error(f"خطأ عام في رفع الصورة: {str(e)}")
            current_app.logger.error(f"تفاصيل الخطأ: {str(e)}", exc_info=True)
            return None
    
    @staticmethod
    def get_image_url(image_id, default_image=None, folder='uploads'):
        """الحصول على URL لصورة بناءً على المعرف"""
        current_app.logger.debug(f"طلب الحصول على URL للصورة بمعرف: {image_id} من مجلد: {folder}")
        
        if not image_id:
            current_app.logger.debug(f"معرف الصورة فارغ، استخدام الصورة الافتراضية: {default_image}")
            return default_image


        if isinstance(image_id, str) and (image_id.startswith(('http://', 'https://', '/'))):
            current_app.logger.debug(f"تم توفير URL مطلق: {image_id}")
            return image_id


        cloudflare_config = current_app.config.get('CLOUDFLARE_CONFIG', {})
        image_delivery_url = cloudflare_config.get('image_delivery_url')
        account_id = cloudflare_config.get('account_id')
        api_token = cloudflare_config.get('api_token')

        if image_delivery_url and account_id and api_token:
            cloudflare_url = f"{image_delivery_url}/{image_id}/public"
            current_app.logger.debug(f"استخدام URL الصورة من Cloudflare: {cloudflare_url}")

            try:
                headers = {'Authorization': f'Bearer {api_token}'}
                response = requests.head(cloudflare_url, headers=headers)
                if response.status_code == 200:
                    return cloudflare_url
            except Exception as e:
                current_app.logger.warning(f"فشل في التحقق من وجود الصورة في Cloudflare: {str(e)}")
            
       
            return cloudflare_url


        static_folder = current_app.static_folder
        image_folder = os.path.join(static_folder, 'images', folder)
        
        try:
            if os.path.exists(image_folder):
   
                for filename in os.listdir(image_folder):
                    if filename.startswith(f"{image_id}."):
                        local_url = f"/static/images/{folder}/{filename}"
                        current_app.logger.debug(f"تم العثور على صورة محلية: {local_url}")
                        return local_url
                
  
                if os.path.exists(os.path.join(image_folder, image_id)):
                    local_url = f"/static/images/{folder}/{image_id}"
                    current_app.logger.debug(f"تم العثور على صورة محلية بدون امتداد: {local_url}")
                    return local_url
                
                current_app.logger.warning(f"لم يتم العثور على صورة بمعرف {image_id} في مجلد {folder}")
            else:
                current_app.logger.warning(f"مجلد الصور غير موجود: {image_folder}")
        except Exception as e:
            current_app.logger.error(f"خطأ أثناء البحث عن الصورة المحلية: {str(e)}")

        current_app.logger.debug(f"استخدام الصورة الافتراضية: {default_image}")
        return default_image
    
    @staticmethod
    def delete_image(image_id, folder='uploads'):
        """حذف صورة من Cloudflare أو محلياً"""
        success = False

        if isinstance(image_id, str) and (image_id.startswith(('http://', 'https://', '/'))):
   
            image_parts = image_id.split('/')
            image_id = image_parts[-1]
            if image_id == 'public':
                image_id = image_parts[-2]
            
            current_app.logger.info(f"تم استخراج معرف الصورة من URL: {image_id}")
        
        cloudflare_config = current_app.config.get('CLOUDFLARE_CONFIG', {})
        account_id = cloudflare_config.get('account_id')
        api_token = cloudflare_config.get('api_token')


        if account_id and api_token:
            current_app.logger.info(f"محاولة حذف الصورة من Cloudflare: {image_id}")
            try:
                headers = {
                    'Authorization': f'Bearer {api_token}'
                }
                
                response = requests.delete(
                    f'https://api.cloudflare.com/client/v4/accounts/{account_id}/images/v1/{image_id}',
                    headers=headers
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('success'):
                        success = True
                        current_app.logger.info(f"تم حذف الصورة من Cloudflare: {image_id}")
                else:
                    current_app.logger.warning(f"استجابة Cloudflare حذف الصورة: {response.status_code} - {response.text}")
            except Exception as cloudflare_error:
                current_app.logger.error(f"فشل في حذف الصورة من Cloudflare: {str(cloudflare_error)}")


        try:
            static_folder = current_app.static_folder
            image_folder = os.path.join(static_folder, 'images', folder)
            
            if os.path.exists(image_folder):
        
                for filename in os.listdir(image_folder):
                    if filename.startswith(f"{image_id}.") or filename == image_id:
                        local_path = os.path.join(image_folder, filename)
                        os.remove(local_path)
                        current_app.logger.info(f"تم حذف الصورة المحلية: {local_path}")
                        success = True
                        break
            else:
                current_app.logger.warning(f"مجلد الصور غير موجود: {image_folder}")
        except Exception as local_error:
            current_app.logger.error(f"فشل في حذف الصورة المحلية: {str(local_error)}")
            
        return success
    
    @staticmethod
    def create_placeholder_images():
        """إنشاء صور وهمية افتراضية للاستخدام في التطبيق"""
        try:
            static_folder = current_app.static_folder
            
            folders = ['products', 'users', 'uploads', 'placeholders', 'categories']
            
            for folder in folders:
                folder_path = os.path.join(static_folder, 'images', folder)
                os.makedirs(folder_path, exist_ok=True)
                current_app.logger.info(f"تم التأكد من وجود مجلد الصور: {folder_path}")
                
            placeholders = {
                'default-avatar.png': os.path.join(static_folder, 'images', 'users'),
                'product-placeholder.jpg': os.path.join(static_folder, 'images', 'products'),
                'no-image.png': os.path.join(static_folder, 'images', 'placeholders'),
                'logo.png': os.path.join(static_folder, 'images')
            }
            
            for filename, folder in placeholders.items():
                file_path = os.path.join(folder, filename)
                if not os.path.exists(file_path):
                    try:
                        from PIL import Image, ImageDraw, ImageFont
                    
                        width, height = 200, 200

                        img = Image.new('RGB', (width, height), color=(240, 240, 240))
                        d = ImageDraw.Draw(img)

                        d.rectangle([0, 0, width-1, height-1], outline=(200, 200, 200))

                        text = filename.split('.')[0]
                        d.text((width/2-20, height/2-10), text, fill=(100, 100, 100))

                        img.save(file_path)
                        current_app.logger.info(f"تم إنشاء صورة افتراضية: {file_path}")
                    except Exception as img_error:
                        current_app.logger.warning(f"فشل إنشاء صورة وهمية باستخدام PIL: {str(img_error)}")
                        with open(file_path, 'wb') as f:
                            f.write(b'')
                        current_app.logger.info(f"تم إنشاء ملف فارغ: {file_path}")
        except Exception as e:
            current_app.logger.error(f"فشل في إنشاء مجلدات وصور وهمية: {str(e)}")
            
    @staticmethod
    def upload_file(file, folder='uploads'):
        """تحميل ملف من نوع werkzeug.FileStorage"""
        try:
            if file and ImageService.allowed_file(file.filename):
              
                file_data = file.read()
                file.seek(0) 
                
        
                current_app.logger.info(f"تحميل ملف جديد: {file.filename}, حجم: {len(file_data)} بايت، نوع: {file.content_type}")
                
           
                result = ImageService.upload_image(file_data, folder)
                
     
                if result:
                    current_app.logger.info(f"تم تحميل الملف بنجاح، معرف الصورة: {result['id']}, URL: {result['url']}")
                else:
                    current_app.logger.error(f"فشل في تحميل الملف: {file.filename}")
                    
                return result
            else:
                current_app.logger.warning(f"نوع الملف غير مسموح: {file.filename if file else 'لا يوجد ملف'}")
             
                allowed_extensions = current_app.config.get('IMAGES_CONFIG', {}).get('allowed_extensions', [])
                current_app.logger.warning(f"أنواع الملفات المسموح بها: {allowed_extensions}")
                return None
        except Exception as e:
            current_app.logger.error(f"خطأ في تحميل الملف: {str(e)}")
            current_app.logger.exception("التفاصيل الكاملة للخطأ:")
            return None