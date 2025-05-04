import os
import sys
import traceback

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

try:

    from bot import create_app, db
    from flask import current_app
    import sqlite3

    print("إنشاء تطبيق Flask...")
    app = create_app()

    if app is None:
        print("خطأ: create_app() أرجعت None")
        sys.exit(1)

 
    with app.app_context():
       
        db_uri = app.config['SQLALCHEMY_DATABASE_URI']
        print(f"مسار قاعدة البيانات: {db_uri}")

        if db_uri.startswith('sqlite:///'):

            import re
            db_path = re.sub(r'^sqlite:///', '', db_uri)
            if db_path.startswith('/'):
                db_path = db_path[1:]
            
            print(f"مسار ملف قاعدة البيانات SQLite: {db_path}")

            if not os.path.exists(db_path):
                print(f"خطأ: ملف قاعدة البيانات غير موجود: {db_path}")
                sys.exit(1)
     
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            cursor.execute("PRAGMA table_info(user)")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            if 'profile_image_url' in column_names:
                print("العمود profile_image_url موجود بالفعل، لا حاجة للإضافة.")
            else:
                try:
                    print("إضافة عمود profile_image_url إلى جدول user...")
                    cursor.execute("ALTER TABLE user ADD COLUMN profile_image_url VARCHAR(500)")
                    conn.commit()
                    print("تم إضافة العمود بنجاح!")
                    
       
                    print("تحديث روابط URL للصور الحالية...")
              
                    cursor.execute("SELECT id, profile_image FROM user WHERE profile_image IS NOT NULL")
                    users_with_images = cursor.fetchall()
                    
                    if users_with_images:
                        print(f"وجدت {len(users_with_images)} مستخدم بصور شخصية، جاري التحديث...")
  
                        from bot.image_service import ImageService
                        default_image = app.config['IMAGES_CONFIG']['default_avatar']
                        
                        update_count = 0
                        for user_id, image_id in users_with_images:
                            if image_id:
                           
                                image_url = ImageService.get_image_url(image_id, default_image, 'users')
                                if image_url != default_image:
                              
                                    cursor.execute(
                                        "UPDATE user SET profile_image_url = ? WHERE id = ?", 
                                        (image_url, user_id)
                                    )
                                    update_count += 1
                        
                        conn.commit()
                        print(f"تم تحديث {update_count} حساب من أصل {len(users_with_images)} مستخدم.")
                    else:
                        print("لم يتم العثور على مستخدمين بصور شخصية.")
                    
                except Exception as e:
                    conn.rollback()
                    print(f"خطأ في إضافة العمود: {str(e)}")
                    traceback.print_exc()
            
 
            conn.close()
        else:
            print(f"قاعدة البيانات ليست SQLite، يرجى استخدام Flask-Migrate لترحيل البيانات.")

except Exception as e:
    print(f"خطأ: {str(e)}")
    traceback.print_exc()
    sys.exit(1)