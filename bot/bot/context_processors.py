from datetime import datetime
from flask import session, request, g, current_app, url_for

def format_price(price):

    try:
        return f"{float(price):,.0f}"
    except (ValueError, TypeError):
        return "0"

def time_since(timestamp):
    now = datetime.utcnow()
    
    if isinstance(timestamp, str):
        try:
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            return "وقت غير معروف"
    
    if not isinstance(timestamp, datetime):
        return "وقت غير معروف"
    
    diff_seconds = (now - timestamp).total_seconds()
    
    if diff_seconds < 60:
        return "منذ لحظات"
    elif diff_seconds < 3600:
        minutes = int(diff_seconds / 60)
        return f"منذ {minutes} دقيقة" if minutes == 1 else f"منذ {minutes} دقائق"
    elif diff_seconds < 86400:
        hours = int(diff_seconds / 3600)
        return f"منذ {hours} ساعة" if hours == 1 else f"منذ {hours} ساعات"
    elif diff_seconds < 2592000:
        days = int(diff_seconds / 86400)
        return f"منذ {days} يوم" if days == 1 else f"منذ {days} أيام"
    elif diff_seconds < 31536000:
        months = int(diff_seconds / 2592000)
        return f"منذ {months} شهر" if months == 1 else f"منذ {months} أشهر"
    else:
        years = int(diff_seconds / 31536000)
        return f"منذ {years} سنة" if years == 1 else f"منذ {years} سنوات"

def get_condition_name(condition):
    """الحصول على اسم حالة المنتج بالعربية"""
    conditions = {
        'new': 'جديد',
        'like_new': 'كالجديد',
        'good': 'حالة جيدة',
        'acceptable': 'حالة مقبولة',
        'refurbished': 'مجدد'
    }
    return conditions.get(condition, condition)

def format_date(date):
    """تنسيق التاريخ بصيغة مقروءة وعربية"""
    if not date:
        return "تاريخ غير معروف"
    months_ar = {
        1: "يناير",
        2: "فبراير",
        3: "مارس",
        4: "أبريل",
        5: "مايو",
        6: "يونيو",
        7: "يوليو",
        8: "أغسطس",
        9: "سبتمبر",
        10: "أكتوبر",
        11: "نوفمبر",
        12: "ديسمبر"
    }

    return f"{date.day} {months_ar[date.month]} {date.year}"

def url_for_with_args(endpoint, new_args=None, **kwargs):

    args = request.args.to_dict()
    if new_args:
        args.update(new_args)
    for key, value in kwargs.items():
        args[key] = value

    args = {k: v for k, v in args.items() if v is not None}
    
    return url_for(endpoint, **args)



def url_for_with_args(endpoint, **kwargs):
    """
    دالة مساعدة لإنشاء URL مع الحفاظ على معاملات الصفحة الحالية
    """
    from flask import request, url_for
    
    args = request.args.copy()
    for key, value in kwargs.items():
        if value is None:
            if key in args:
                args.pop(key)
        else:
            args[key] = value
    
    return url_for(endpoint, **args)

# Add these functions to your bot/bot/context_processors.py file

def action_badge_class(action):
    """Get CSS class for action badge based on action type"""
    if action.startswith('create'):
        return 'success'
    elif action.startswith('update'):
        return 'warning'
    elif action.startswith('delete'):
        return 'danger'
    elif action.startswith('login'):
        return 'info'
    elif action.startswith('logout'):
        return 'secondary'
    elif action.startswith('ban'):
        return 'danger'
    elif action.startswith('unban'):
        return 'success'
    elif action.startswith('activate'):
        return 'success'
    elif action.startswith('deactivate'):
        return 'warning'
    elif action.startswith('feature'):
        return 'primary'
    elif action.startswith('unfeature'):
        return 'secondary'
    else:
        return 'primary'

def action_name(action):
    """Get user-friendly name for action in Arabic"""
    action_names = {
        'create': 'إنشاء',
        'update': 'تحديث',
        'delete': 'حذف',
        'login': 'تسجيل دخول',
        'logout': 'تسجيل خروج',
        'ban_user': 'حظر مستخدم',
        'unban_user': 'إلغاء حظر مستخدم',
        'activate_product': 'تفعيل منتج',
        'deactivate_product': 'إيقاف منتج',
        'feature_product': 'تمييز منتج',
        'unfeature_product': 'إلغاء تمييز منتج',
        'update_profile_image': 'تحديث صورة الملف الشخصي',
        'register': 'تسجيل حساب',
        'password_reset_request': 'طلب إعادة تعيين كلمة المرور',
        'change_email_request': 'طلب تغيير البريد الإلكتروني',
        'change_email_completed': 'تغيير البريد الإلكتروني',
        'add_favorite': 'إضافة للمفضلة',
        'remove_favorite': 'إزالة من المفضلة',
        'report': 'إبلاغ',
        'update_report_pending': 'إعادة فتح البلاغ',
        'update_report_resolved': 'حل البلاغ',
        'update_report_rejected': 'رفض البلاغ'
    }
    
    # Check for exact match first
    if action in action_names:
        return action_names[action]
    
    # Otherwise, try to find a prefix match
    for key, value in action_names.items():
        if action.startswith(key):
            return value
    
    # Default fallback
    return action

def entity_type_name(entity_type):
    """Get user-friendly name for entity type in Arabic"""
    entity_types = {
        'user': 'مستخدم',
        'product': 'منتج',
        'category': 'تصنيف',
        'report': 'بلاغ',
        'message': 'رسالة'
    }
    return entity_types.get(entity_type, entity_type)

def inject_common_data():
    """حقن البيانات المشتركة لجميع القوالب"""

    if not hasattr(g, 'current_user'):
        token = None
        if 'auth_token' in session:
            token = session['auth_token']
        elif 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        
        if token:
            try:
                import jwt
                from .models import User
                data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
                user = User.query.get(data['user_id'])
                
                if user and not user.is_banned:
                    g.current_user = user
                    return {
                        'now': datetime.utcnow(),
                        'request': request,
                        'current_user': user,
                        'format_price': format_price,
                        'time_since': time_since,
                        'get_condition_name': get_condition_name,
                        'format_date': format_date,
                        'url_for_with_args': url_for_with_args
                    }
            except:
                pass
        

        g.current_user = type('AnonymousUser', (), {
            'is_authenticated': False,
            'id': None,
            'is_admin': False,
            'name': 'زائر',
            'profile_image': None,
            'location': None
        })()
    
    return {
        'now': datetime.utcnow(),
        'request': request,
        'current_user': g.current_user,
        'format_price': format_price,
        'time_since': time_since,
        'get_condition_name': get_condition_name,
        'format_date': format_date,
        'url_for_with_args': url_for_with_args
    }