import sys
import os
import traceback


sys.path.append(os.path.abspath(os.path.dirname(__file__)))

try:
    from bot import create_app, db

    print("Intentando crear la aplicación Flask...")
    
    app = create_app()
    
    if app is None:
        print("Error: create_app() devolvió None")
        sys.exit(1)
    else:
        print(f"Aplicación creada exitosamente: {app}")

    @app.cli.command("init-db")
    def init_db():
        """تهيئة جداول قاعدة البيانات"""
        db.create_all()
        print("تم إنشاء جداول قاعدة البيانات بنجاح")

    @app.cli.command("create-data")
    def create_seed_data():
        """إنشاء البيانات الأولية"""
        from bot.main import create_initial_data
        create_initial_data()
        print("تم إنشاء البيانات الأولية بنجاح")

    if __name__ == '__main__':

        with app.app_context():
            db.create_all()
            print("تم التأكد من وجود جداول قاعدة البيانات")

        # تشغيل التطبيق
        port = app.config.get('PORT', 5000)
        debug = app.config.get('DEBUG', True)
        app.run(debug=debug, host='0.0.0.0', port=port)

except Exception as e:
    print(f"Error al inicializar la aplicación: {e}")
    traceback.print_exc()
    sys.exit(1)