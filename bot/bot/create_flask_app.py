"""
هذا الملف هو للتشغيل المباشر للتطبيق بدون واجهة CLI
استخدمه بدلاً من run.py لتشغيل التطبيق وإنشاء قاعدة البيانات
"""

import sys
import os
import traceback

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

try:
    from bot import create_app, db
    
    print("إنشاء تطبيق Flask...")
    app = create_app()
    
    if app is None:
        print("خطأ: create_app() أرجعت None")
        sys.exit(1)
    
    print("تهيئة قاعدة البيانات...")
    with app.app_context():
        db.create_all()
        print("تم إنشاء جداول قاعدة البيانات بنجاح")

        try:
            from bot.main import create_initial_data
            create_initial_data()
            print("تم إنشاء البيانات الأولية بنجاح")
        except Exception as e:
            print(f"تحذير: لم يتم إنشاء البيانات الأولية: {str(e)}")
    
    print("تشغيل التطبيق...")
    port = app.config.get('PORT', 5000)
    debug = app.config.get('DEBUG', True)
    app.run(debug=debug, host='0.0.0.0', port=port)
    
except Exception as e:
    print(f"خطأ في بدء التطبيق: {str(e)}")
    traceback.print_exc()
    sys.exit(1)