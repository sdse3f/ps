from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, current_app, g
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, timedelta
import jwt
import os
from . import db
import uuid
import base64
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests
from flask import current_app
from .models import AuditLog
from .models import User, Category, Product, UserReview, Message
from .main import admin_required
from flask import send_from_directory, make_response, current_app as app


main_bp = Blueprint('main', __name__)


products_bp = Blueprint('products', __name__, url_prefix='/products')


user_bp = Blueprint('user', __name__, url_prefix='/user')


auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


messages_bp = Blueprint('messages', __name__, url_prefix='/messages')


admin_bp = Blueprint('admin', __name__, url_prefix='/admin')




@main_bp.route('/')
def index():
    """الصفحة الرئيسية"""
 
    from .models import Category, Product, User, Message
    from sqlalchemy import func, desc
    from sqlalchemy.sql import text
    

    categories = Category.query.filter_by(parent_id=None).all()
    

    featured_products = Product.query.filter_by(is_active=True, is_sold=False, is_featured=True).order_by(Product.created_at.desc()).limit(4).all()
    

    latest_products = Product.query.filter_by(is_active=True, is_sold=False).order_by(Product.created_at.desc()).limit(8).all()
    location_counts = db.session.query(
        Product.location, 
        func.count(Product.id).label('count')
    ).filter_by(
        is_active=True, 
        is_sold=False
    ).group_by(
        Product.location
    ).order_by(
        desc('count')
    ).limit(14).all()
    popular_locations = [
        {'id': location, 'name': get_location_name(location), 'count': count}
        for location, count in location_counts
    ]
    

    if len(popular_locations) < 14:
     
        all_syrian_locations = [
            {'id': 'damascus', 'name': 'دمشق'},
            {'id': 'aleppo', 'name': 'حلب'},
            {'id': 'homs', 'name': 'حمص'},
            {'id': 'latakia', 'name': 'اللاذقية'},
            {'id': 'tartus', 'name': 'طرطوس'},
            {'id': 'hama', 'name': 'حماة'},
            {'id': 'daraa', 'name': 'درعا'},
            {'id': 'idlib', 'name': 'إدلب'},
            {'id': 'hasaka', 'name': 'الحسكة'},
            {'id': 'suwayda', 'name': 'السويداء'},
            {'id': 'deir-ez-zor', 'name': 'دير الزور'},
            {'id': 'raqqa', 'name': 'الرقة'},
            {'id': 'quneitra', 'name': 'القنيطرة'},
            {'id': 'rif-dimashq', 'name': 'ريف دمشق'}
        ]
        
       
        existing_locations = {loc['id'] for loc in popular_locations}
        for loc in all_syrian_locations:
            if loc['id'] not in existing_locations and len(popular_locations) < 14:
             
                count = Product.query.filter_by(
                    location=loc['id'], 
                    is_active=True, 
                    is_sold=False
                ).count()
                
                popular_locations.append({
                    'id': loc['id'],
                    'name': loc['name'],
                    'count': count
                })
    
    stats = {
        'users_count': User.query.count(),
        'products_count': Product.query.filter_by(is_active=True).count(),
        'sales_count': Product.query.filter_by(is_sold=True).count(),
        'regions_count': len(set([p.location for p in Product.query.with_entities(Product.location).distinct()]))
    }
    
    token_user = None
    token = None
    if 'auth_token' in session:
        token = session['auth_token']
    elif 'Authorization' in request.headers:
        auth_header = request.headers['Authorization']
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
    if token:
        try:
            data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
            token_user = User.query.get(data['user_id'])
        except:
            pass
    
    if token_user:
        for product in featured_products + latest_products:
            product.is_favorite = product in token_user.favorites_products
    else:
        for product in featured_products + latest_products:
            product.is_favorite = False
    
    return render_template(
        'index.html', 
        categories=categories, 
        featured_products=featured_products, 
        latest_products=latest_products,
        popular_locations=popular_locations,
        site_stats=stats
    )

def get_location_name(location_id):
    """الحصول على اسم المحافظة بناءً على المعرف"""
    locations = {
        'damascus': 'دمشق',
        'aleppo': 'حلب',
        'homs': 'حمص',
        'latakia': 'اللاذقية',
        'tartus': 'طرطوس',
        'hama': 'حماة',
        'daraa': 'درعا',
        'idlib': 'إدلب',
        'hasaka': 'الحسكة',
        'suwayda': 'السويداء',
        'deir-ez-zor': 'دير الزور',
        'raqqa': 'الرقة',
        'quneitra': 'القنيطرة',
        'rif-dimashq': 'ريف دمشق'
    }
    return locations.get(location_id, location_id)

@messages_bp.route('/api/send_message', methods=['POST'])
def api_send_message():
    if not g.current_user or not g.current_user.is_authenticated:
        return jsonify({'success': False, 'message': 'غير مصرح'}), 401
    
    data = request.json
    receiver_id = data.get('receiver_id')
    content = data.get('content')
    product_id = data.get('product_id')
    
    if not receiver_id or not content:
        return jsonify({'success': False, 'message': 'بيانات غير كاملة'}), 400
    
    message = Message(
        sender_id=g.current_user.id,
        receiver_id=receiver_id,
        content=content,
        product_id=product_id
    )
    
    db.session.add(message)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': {
            'id': message.id,
            'content': message.content,
            'created_at': 'الآن',
            'is_read': False
        }
    })


@admin_bp.route('/api/reports/<int:report_id>', methods=['GET'])
@admin_required
def api_report_details(current_user, report_id):
    """API للحصول على تفاصيل البلاغ"""
    from .models import Report
    
    report = Report.query.get_or_404(report_id)
    
    # Create a properly formatted response
    result = {
        'id': report.id,
        'reason': report.reason,
        'details': report.details,
        'status': report.status,
        'created_at': report.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        'reporter': {
            'id': report.reporter.id,
            'name': report.reporter.name,
            'email': report.reporter.email,
            'profile_image': report.reporter.profile_image_url or url_for('static', filename='images/users/default-avatar.png')
        }
    }
    
    # Add product or user details based on report type
    if report.product_id:
        result['product'] = {
            'id': report.product.id,
            'title': report.product.title,
            'seller_name': report.product.seller.name,
            'image_url': (report.product.images[0].url if report.product.images and len(report.product.images) > 0 
                        else url_for('static', filename='images/products/product-placeholder.jpg'))
        }
    
    if report.reported_user_id:
        result['reported_user'] = {
            'id': report.reported_user.id,
            'name': report.reported_user.name,
            'email': report.reported_user.email,
            'profile_image': report.reported_user.profile_image_url or url_for('static', filename='images/users/default-avatar.png')
        }
    
    return jsonify({'success': True, 'report': result})

@products_bp.route('/report/<int:product_id>', methods=['POST'])
def report(product_id):
    """إبلاغ عن منتج"""
    from .models import Product, Report
    from flask import current_app
    
    if not g.current_user or not g.current_user.is_authenticated:
        flash('يجب تسجيل الدخول للإبلاغ عن منتج', 'warning')
        return redirect(url_for('auth.login', next=request.path))
    
    product = Product.query.get_or_404(product_id)
    
    # التحقق من أن المستخدم ليس صاحب المنتج
    if product.seller_id == g.current_user.id:
        flash('لا يمكنك الإبلاغ عن منتجاتك الخاصة', 'warning')
        return redirect(url_for('products.view', product_id=product_id))
    
    try:
        reason = request.form.get('reason')
        details = request.form.get('details')
        
        if not reason:
            flash('يرجى تحديد سبب الإبلاغ', 'danger')
            return redirect(url_for('products.view', product_id=product_id))
        
        # التحقق من عدم وجود بلاغ سابق من نفس المستخدم
        existing_report = Report.query.filter_by(
            reporter_id=g.current_user.id,
            product_id=product_id
        ).first()
        
        if existing_report:
            flash('لقد قمت بالإبلاغ عن هذا المنتج من قبل. سيتم مراجعة بلاغك قريباً.', 'info')
            return redirect(url_for('products.view', product_id=product_id))
        
        # إنشاء بلاغ جديد
        report = Report(
            reporter_id=g.current_user.id,
            product_id=product_id,
            reason=reason,
            details=details,
            status='pending'  # حالة البلاغ الافتراضية: قيد الانتظار
        )
        
        db.session.add(report)
        db.session.commit()
        
        # تسجيل النشاط
        from .main import log_activity
        log_activity(
            user_id=g.current_user.id,
            action='report',
            entity_type='product',
            entity_id=product_id,
            details=f"إبلاغ عن منتج: {reason}",
            request=request
        )
        
        flash('تم إرسال البلاغ بنجاح. سيتم مراجعته من قبل فريق الإدارة.', 'success')
        return redirect(url_for('products.view', product_id=product_id))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"خطأ في إرسال البلاغ: {str(e)}")
        flash('حدث خطأ أثناء إرسال البلاغ. يرجى المحاولة مرة أخرى.', 'danger')
        return redirect(url_for('products.view', product_id=product_id))
    
@admin_bp.route('/api/reports/<int:report_id>/status', methods=['POST'])
@admin_required
def api_update_report_status(current_user, report_id):
    """API لتحديث حالة البلاغ"""
    from .models import Report
    
    report = Report.query.get_or_404(report_id)
    
    data = request.json
    new_status = data.get('status')
    
    if new_status not in ['pending', 'resolved', 'rejected']:
        return jsonify({'success': False, 'message': 'حالة غير صالحة'}), 400
    
    report.status = new_status
    
    if new_status in ['resolved', 'rejected']:
        report.resolved_at = datetime.utcnow()
    
    db.session.commit()
    
    # تسجيل النشاط
    from .main import log_activity
    log_activity(
        user_id=current_user.id,
        action=f'update_report_{new_status}',
        entity_type='report',
        entity_id=report_id,
        details=f"تغيير حالة البلاغ إلى {new_status}",
        request=request
    )
    
    return jsonify({'success': True, 'message': 'تم تحديث حالة البلاغ بنجاح'})

@admin_bp.route('/api/products/<int:product_id>/deactivate', methods=['POST'])
@admin_required
def api_deactivate_product(current_user, product_id):
    """API لإيقاف منتج"""
    from .models import Product
    
    product = Product.query.get_or_404(product_id)
    product.is_active = False
    
    # تسجيل النشاط
    from .main import log_activity
    log_activity(
        user_id=current_user.id,
        action='deactivate_product',
        entity_type='product',
        entity_id=product.id,
        details=f"إيقاف المنتج من تفاصيل البلاغ: {product.title}",
        request=request
    )
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'تم إيقاف المنتج بنجاح'})


@admin_bp.route('/api/products/<int:product_id>/activate', methods=['POST'])
@admin_required
def api_activate_product(current_user, product_id):
    """API لتفعيل منتج"""
    from .models import Product
    
    product = Product.query.get_or_404(product_id)
    product.is_active = True
    
    # تسجيل النشاط
    from .main import log_activity
    log_activity(
        user_id=current_user.id,
        action='activate_product',
        entity_type='product',
        entity_id=product.id,
        details=f"تفعيل المنتج من تفاصيل البلاغ: {product.title}",
        request=request
    )
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'تم تفعيل المنتج بنجاح'})


@admin_bp.route('/api/users/<int:user_id>/ban', methods=['POST'])
@admin_required
def api_ban_user(current_user, user_id):
    """API لحظر مستخدم"""
    from .models import User
    
    user = User.query.get_or_404(user_id)
    
    # منع حظر المشرفين
    if user.is_admin:
        return jsonify({'success': False, 'message': 'لا يمكن حظر المشرفين'}), 400
    
    user.is_banned = True
    
    # تسجيل النشاط
    from .main import log_activity
    log_activity(
        user_id=current_user.id,
        action='ban_user',
        entity_type='user',
        entity_id=user.id,
        details=f"حظر المستخدم من تفاصيل البلاغ: {user.name}",
        request=request
    )
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'تم حظر المستخدم بنجاح'})


@admin_bp.route('/api/users/<int:user_id>/unban', methods=['POST'])
@admin_required
def api_unban_user(current_user, user_id):
    """API لإلغاء حظر مستخدم"""
    from .models import User
    
    user = User.query.get_or_404(user_id)
    user.is_banned = False
    
    # تسجيل النشاط
    from .main import log_activity
    log_activity(
        user_id=current_user.id,
        action='unban_user',
        entity_type='user',
        entity_id=user.id,
        details=f"إلغاء حظر المستخدم من تفاصيل البلاغ: {user.name}",
        request=request
    )
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'تم إلغاء حظر المستخدم بنجاح'})

@admin_bp.route('/user_products/<int:user_id>')
@admin_required
def user_products(current_user, user_id):
    """عرض منتجات مستخدم معين"""
    from .models import User, Product
    
    user = User.query.get_or_404(user_id)
    products = Product.query.filter_by(seller_id=user_id).order_by(Product.created_at.desc()).all()
    
    return render_template('admin/user_products.html', user=user, products=products)

@admin_bp.route('/user_reports/<int:user_id>')
@admin_required
def user_reports(current_user, user_id):
    """عرض بلاغات مستخدم معين"""
    from .models import User, Report
    
    user = User.query.get_or_404(user_id)
    reports_filed = Report.query.filter_by(reporter_id=user_id).order_by(Report.created_at.desc()).all()
    reports_received = Report.query.filter_by(reported_user_id=user_id).order_by(Report.created_at.desc()).all()
    
    return render_template(
        'admin/user_reports.html', 
        user=user, 
        reports_filed=reports_filed, 
        reports_received=reports_received
    )


@messages_bp.route('/api/get_messages/<int:user_id>', methods=['GET'])
def api_get_messages(user_id):
    if not g.current_user or not g.current_user.is_authenticated:
        return jsonify({'success': False, 'message': 'غير مصرح'}), 401
    

    last_id = request.args.get('last_id', 0, type=int)
    
    messages = Message.query.filter(
        ((Message.sender_id == g.current_user.id) & (Message.receiver_id == user_id)) |
        ((Message.sender_id == user_id) & (Message.receiver_id == g.current_user.id)),
        Message.id > last_id
    ).order_by(Message.created_at).all()
    

    for message in messages:
        if message.receiver_id == g.current_user.id and not message.is_read:
            message.is_read = True
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'messages': [{
            'id': msg.id,
            'content': msg.content,
            'sender_id': msg.sender_id,
            'receiver_id': msg.receiver_id,
            'created_at': msg.created_at.isoformat(),
            'is_read': msg.is_read
        } for msg in messages]
    })

@main_bp.route('/categories')
def categories():
    """صفحة التصنيفات"""
    from .models import Category
    categories = Category.query.all()
    return render_template('categories.html', categories=categories)

@main_bp.route('/about')
def about():
    """صفحة من نحن"""
    return render_template('about.html')

@main_bp.route('/contact')
def contact():
    """صفحة اتصل بنا"""
    return render_template('contact.html')

@main_bp.route('/terms')
def terms():
    """صفحة شروط الاستخدام"""
    return render_template('terms.html')

@main_bp.route('/privacy')
def privacy():
    """صفحة سياسة الخصوصية"""
    return render_template('privacy.html')

@main_bp.route('/newsletter_subscribe', methods=['POST'])
def newsletter_subscribe():
    """الاشتراك في النشرة البريدية"""
    email = request.form.get('email')
    if not email:
        flash('يرجى إدخال بريد إلكتروني صحيح', 'danger')
    else:
        flash('تم اشتراكك بنجاح في النشرة البريدية', 'success')
    return redirect(url_for('main.index'))


@products_bp.route('/')
def index():
    """صفحة عرض جميع المنتجات"""
    from .models import Product
    
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    products = Product.query.filter_by(is_active=True, is_sold=False).paginate(page=page, per_page=per_page)
    
    return render_template('products/index.html', products=products)

@products_bp.route('/search')
def search():
    """البحث عن المنتجات"""
    from .models import Product, Category
    
    search_query = request.args.get('q', '')
    category_id = request.args.get('category_id')
    location = request.args.get('location')
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    condition = request.args.getlist('condition')
    featured_only = request.args.get('featured') == 'true'
    sort_by = request.args.get('sort_by', 'created_at')
    sort_dir = request.args.get('sort_dir', 'desc')
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    query = Product.query.filter_by(is_active=True, is_sold=False)
    
    if search_query:
        query = query.filter(Product.title.ilike(f'%{search_query}%') | Product.description.ilike(f'%{search_query}%'))
    
    if category_id:
        query = query.filter_by(category_id=category_id)
    
    if location:
        query = query.filter_by(location=location)
    
    if min_price is not None:
        query = query.filter(Product.price >= min_price)
    
    if max_price is not None:
        query = query.filter(Product.price <= max_price)
    
    if condition:
        query = query.filter(Product.condition.in_(condition))
    
    if featured_only:
        query = query.filter_by(is_featured=True)
    
    if sort_by == 'price':
        order_column = Product.price
    elif sort_by == 'views':
        order_column = Product.views_count
    else:
        order_column = Product.created_at
    
    if sort_dir == 'asc':
        query = query.order_by(order_column.asc())
    else:
        query = query.order_by(order_column.desc())
    
    products_paginated = query.paginate(page=page, per_page=per_page)
    
    categories = Category.query.all()
    
    conditions = [
        {'id': 'new', 'name': 'جديد'},
        {'id': 'like_new', 'name': 'كالجديد'},
        {'id': 'good', 'name': 'حالة جيدة'},
        {'id': 'acceptable', 'name': 'حالة مقبولة'},
        {'id': 'refurbished', 'name': 'مُجدّد'}
    ]
    
    locations = [
        {'id': 'damascus', 'name': 'دمشق'},
        {'id': 'aleppo', 'name': 'حلب'},
        {'id': 'homs', 'name': 'حمص'},
        {'id': 'latakia', 'name': 'اللاذقية'},
        {'id': 'tartus', 'name': 'طرطوس'},
        {'id': 'hama', 'name': 'حماة'},
        {'id': 'daraa', 'name': 'درعا'},
        {'id': 'idlib', 'name': 'إدلب'},
        {'id': 'hasaka', 'name': 'الحسكة'},
        {'id': 'suwayda', 'name': 'السويداء'},
        {'id': 'deir-ez-zor', 'name': 'دير الزور'},
        {'id': 'raqqa', 'name': 'الرقة'},
        {'id': 'quneitra', 'name': 'القنيطرة'},
        {'id': 'rif-dimashq', 'name': 'ريف دمشق'}
    ]
    
    if search_query:
        page_title = f'نتائج البحث عن "{search_query}"'
    elif category_id:
        category = Category.query.get(category_id)
        page_title = f'منتجات تصنيف {category.name}' if category else 'تصفح المنتجات'
    elif featured_only:
        page_title = 'المنتجات المميزة'
    else:
        page_title = 'تصفح المنتجات'
    
    return render_template(
        'search_products.html',
        products=products_paginated.items,
        pagination=products_paginated,
        search_query=search_query,
        selected_category_id=category_id,
        selected_location=location,
        min_price=min_price,
        max_price=max_price,
        selected_conditions=condition,
        featured_only=featured_only,
        sort_by=sort_by,
        sort_dir=sort_dir,
        categories=categories,
        conditions=conditions,
        locations=locations,
        page_title=page_title
    )

@products_bp.route('/category/<int:category_id>')
def category(category_id):
    """عرض منتجات تصنيف معين"""
    from .models import Category
    
    return redirect(url_for('products.search', category_id=category_id))


@products_bp.route('/view/<int:product_id>')
def view(product_id):
    """عرض تفاصيل منتج"""
    from .models import Product, Category
    from flask import current_app
    
    product = Product.query.get_or_404(product_id)
    
    product.views_count += 1
    db.session.commit()
    
    current_app.logger.info(f"عرض تفاصيل المنتج: {product.id} - {product.title}")
    current_app.logger.info(f"عدد صور المنتج: {len(product.images)}")

    if product.images:
        for i, image in enumerate(product.images):
            current_app.logger.debug(f"صورة {i+1}: ID={image.id}, CloudflareID={image.cloudflare_id}, is_primary={image.is_primary}")
    else:
        current_app.logger.warning(f"المنتج {product.id} ليس له صور")

    similar_products = Product.query.filter(
        Product.category_id == product.category_id,
        Product.id != product.id,
        Product.is_active == True,
        Product.is_sold == False
    ).order_by(Product.created_at.desc()).limit(4).all()

    if g.current_user and g.current_user.is_authenticated:
        product.is_favorite = product in g.current_user.favorites_products
        for p in similar_products:
            p.is_favorite = p in g.current_user.favorites_products
    else:
        product.is_favorite = False
        for p in similar_products:
            p.is_favorite = False

    product.category_name = Category.query.get(product.category_id).name
    
    product.seller.rating = product.seller.calculate_rating()
    product.seller.reviews_count = len(product.seller.reviews_received)

    for p in similar_products:
        p.seller.rating = p.seller.calculate_rating()
        p.seller.reviews_count = len(p.seller.reviews_received)
    
    return render_template(
        'product_view.html',
        product=product,
        similar_products=similar_products
    )

@products_bp.route('/create', methods=['GET', 'POST'])
def create():
    """إضافة منتج جديد"""
    from .models import Category, Product, ProductImage, ProductAttribute
    from .context_processors import get_condition_name
    from .image_service import ImageService
    from flask import current_app

    if not g.current_user or not g.current_user.is_authenticated:
        flash('يجب تسجيل الدخول لإضافة منتج جديد', 'warning')
        return redirect(url_for('auth.login', next=request.path))

    try:
        main_categories = Category.query.filter_by(parent_id=None).all()
        
        categories = []
        for main_cat in main_categories:
            main_cat.subcategories = Category.query.filter_by(parent_id=main_cat.id).all()
            categories.append(main_cat)
        
        if not categories:
            flash('لم يتم العثور على تصنيفات. سيتم استخدام تصنيفات افتراضية.', 'warning')
            from .main import create_initial_data
            create_initial_data()
            main_categories = Category.query.filter_by(parent_id=None).all()
            categories = []
            for main_cat in main_categories:
                main_cat.subcategories = Category.query.filter_by(parent_id=main_cat.id).all()
                categories.append(main_cat)
    except Exception as e:
        current_app.logger.error(f"خطأ في جلب التصنيفات: {str(e)}")
        categories = []
        flash('حدث خطأ في جلب التصنيفات. يرجى المحاولة لاحقاً.', 'danger')

    conditions = [
        {'id': 'new', 'name': 'جديد'},
        {'id': 'like_new', 'name': 'كالجديد'},
        {'id': 'good', 'name': 'حالة جيدة'},
        {'id': 'acceptable', 'name': 'حالة مقبولة'},
        {'id': 'refurbished', 'name': 'مجدد'}
    ]

    locations = [
        {'id': 'damascus', 'name': 'دمشق'},
        {'id': 'aleppo', 'name': 'حلب'},
        {'id': 'homs', 'name': 'حمص'},
        {'id': 'latakia', 'name': 'اللاذقية'},
        {'id': 'tartus', 'name': 'طرطوس'},
        {'id': 'hama', 'name': 'حماة'},
        {'id': 'daraa', 'name': 'درعا'},
        {'id': 'idlib', 'name': 'إدلب'},
        {'id': 'hasaka', 'name': 'الحسكة'},
        {'id': 'suwayda', 'name': 'السويداء'},
        {'id': 'deir-ez-zor', 'name': 'دير الزور'},
        {'id': 'raqqa', 'name': 'الرقة'},
        {'id': 'quneitra', 'name': 'القنيطرة'},
        {'id': 'rif-dimashq', 'name': 'ريف دمشق'}
    ]
    
    if request.method == 'POST':
        try:
            title = request.form.get('title')
            category_id = request.form.get('category_id')
            price = request.form.get('price')
            currency = request.form.get('currency')
            condition = request.form.get('condition')
            location = request.form.get('location')
            description = request.form.get('description')
            
            if not all([title, category_id, price, condition, location, description]):
                flash('جميع الحقول المطلوبة يجب ملؤها', 'danger')
                return render_template(
                    'create_product.html',
                    categories=categories,
                    conditions=conditions,
                    locations=locations,
                    get_condition_name=get_condition_name
                )
                
            current_app.logger.info(f"بدء إنشاء منتج جديد: {title}")
            
            new_product = Product(
                title=title,
                description=description,
                price=float(price),
                currency=currency,
                condition=condition,
                category_id=int(category_id),
                location=location,
                seller_id=g.current_user.id
            )
            
            db.session.add(new_product)
            db.session.commit()
            
            current_app.logger.info(f"تم إنشاء المنتج بنجاح بمعرف: {new_product.id}")

            files = request.files.getlist('product_images[]')
            primary_image_index = request.form.get('primary_image', '0')
            
            current_app.logger.info(f"عدد الصور المرفقة: {len(files)}")
            

            file_names = [f.filename for f in files if f and f.filename]
            current_app.logger.info(f"أسماء الملفات المرفقة: {file_names}")
            
            has_images = False
            
            for i, file in enumerate(files):
                if file and file.filename:
                    has_images = True
                    current_app.logger.info(f"معالجة الصورة {i+1} من {len(files)}: {file.filename}")
         
                    result = ImageService.upload_file(file, folder='products')
                    
                    if result:
                        current_app.logger.info(f"تم رفع الصورة {i+1} بنجاح: {result['id']}")
                        
              
                        is_primary = (str(i) == primary_image_index)
                        
                        image = ProductImage(
                            cloudflare_id=result['id'],
                            url=result['url'],
                            product_id=new_product.id,
                            is_primary=is_primary
                        )
                        db.session.add(image)
                    else:
                        current_app.logger.error(f"فشل في رفع الصورة {i+1}: {file.filename}")
            
            if not has_images:
                current_app.logger.warning(f"المنتج {new_product.id} ليس له صور")

            for i in range(20):
                name = request.form.get(f'attributes[{i}][name]')
                value = request.form.get(f'attributes[{i}][value]')
                
                if name and value:
                    attribute = ProductAttribute(
                        product_id=new_product.id,
                        name=name,
                        value=value
                    )
                    db.session.add(attribute)
            
            db.session.commit()
            current_app.logger.info(f"تم حفظ التغييرات بنجاح للمنتج: {new_product.id}")

            from .main import log_activity
            log_activity(
                user_id=g.current_user.id,
                action='create',
                entity_type='product',
                entity_id=new_product.id,
                request=request
            )
            
            flash('تم إضافة المنتج بنجاح', 'success')
            return redirect(url_for('products.view', product_id=new_product.id))
        
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"خطأ في إضافة المنتج: {str(e)}", exc_info=True)
            flash('حدث خطأ أثناء إضافة المنتج. يرجى المحاولة مرة أخرى.', 'danger')
    
    return render_template(
        'create_product.html',
        categories=categories,
        conditions=conditions,
        locations=locations,
        get_condition_name=get_condition_name
    )


@products_bp.route('/edit/<int:product_id>', methods=['GET', 'POST'])
def edit(product_id):
    """تعديل منتج"""
    from .models import Product, Category

    if not g.current_user or not g.current_user.is_authenticated:
        flash('يجب تسجيل الدخول لتعديل المنتج', 'warning')
        return redirect(url_for('auth.login', next=request.path))

    product = Product.query.get_or_404(product_id)

    if product.seller_id != g.current_user.id and not g.current_user.is_admin:
        flash('ليس لديك صلاحية لتعديل هذا المنتج', 'danger')
        return redirect(url_for('products.view', product_id=product_id))

    if request.method == 'POST':
        flash('تم تعديل المنتج بنجاح', 'success')
        return redirect(url_for('products.view', product_id=product_id))

    categories = Category.query.all()

    conditions = [
        {'id': 'new', 'name': 'جديد'},
        {'id': 'like_new', 'name': 'كالجديد'},
        {'id': 'good', 'name': 'حالة جيدة'},
        {'id': 'acceptable', 'name': 'حالة مقبولة'},
        {'id': 'refurbished', 'name': 'مُجدّد'}
    ]

    locations = [
        {'id': 'damascus', 'name': 'دمشق'},
        {'id': 'aleppo', 'name': 'حلب'},
        {'id': 'homs', 'name': 'حمص'},
        {'id': 'latakia', 'name': 'اللاذقية'},
        {'id': 'tartus', 'name': 'طرطوس'},
        {'id': 'hama', 'name': 'حماة'},
        {'id': 'daraa', 'name': 'درعا'},
        {'id': 'idlib', 'name': 'إدلب'},
        {'id': 'hasaka', 'name': 'الحسكة'},
        {'id': 'suwayda', 'name': 'السويداء'},
        {'id': 'deir-ez-zor', 'name': 'دير الزور'},
        {'id': 'raqqa', 'name': 'الرقة'},
        {'id': 'quneitra', 'name': 'القنيطرة'},
        {'id': 'rif-dimashq', 'name': 'ريف دمشق'}
    ]
    
    return render_template(
        'edit_product.html',
        product=product,
        categories=categories,
        conditions=conditions,
        locations=locations
    )

@products_bp.route('/delete/<int:product_id>', methods=['POST'])
def delete(product_id):
    """حذف منتج"""
    from .models import Product

    if not g.current_user or not g.current_user.is_authenticated:
        flash('يجب تسجيل الدخول لحذف المنتج', 'warning')
        return redirect(url_for('auth.login', next=request.path))

    product = Product.query.get_or_404(product_id)

    if product.seller_id != g.current_user.id and not g.current_user.is_admin:
        flash('ليس لديك صلاحية لحذف هذا المنتج', 'danger')
        return redirect(url_for('products.view', product_id=product_id))

    from .main import db
    db.session.delete(product)
    db.session.commit()
    
    flash('تم حذف المنتج بنجاح', 'success')
    return redirect(url_for('user.profile'))

@products_bp.route('/mark-as-sold/<int:product_id>')
def mark_product_as_sold(product_id):
    """تعيين منتج كمباع"""
    from .models import Product

    if not g.current_user or not g.current_user.is_authenticated:
        flash('يجب تسجيل الدخول لتعديل حالة المنتج', 'warning')
        return redirect(url_for('auth.login', next=request.path))

    product = Product.query.get_or_404(product_id)

    if product.seller_id != g.current_user.id and not g.current_user.is_admin:
        flash('ليس لديك صلاحية لتعديل حالة هذا المنتج', 'danger')
        return redirect(url_for('products.view', product_id=product_id))

    product.is_sold = True
    from .main import db
    db.session.commit()
    
    flash('تم تعيين المنتج كمباع بنجاح', 'success')
    return redirect(url_for('user.profile'))

@products_bp.route('/favorites')
def favorites():
    """عرض المنتجات المفضلة للمستخدم"""
    if not g.current_user or not g.current_user.is_authenticated:
        flash('يجب تسجيل الدخول لعرض المفضلة', 'warning')
        return redirect(url_for('auth.login', next=request.path))
    products = g.current_user.favorites_products
    
    return render_template('products/favorites.html', products=products)


@user_bp.route('/change_email', methods=['POST'])
def change_email():
    """تغيير البريد الإلكتروني"""
    if not g.current_user or not g.current_user.is_authenticated:
        flash('يجب تسجيل الدخول لتغيير البريد الإلكتروني', 'warning')
        return redirect(url_for('auth.login', next=request.path))
    
    new_email = request.form.get('new_email')
    password = request.form.get('password')
    
    if not new_email or not password:
        flash('جميع الحقول مطلوبة', 'danger')
        return redirect(url_for('user.profile'))
    
  
    if not check_password_hash(g.current_user.password, password):
        flash('كلمة المرور غير صحيحة', 'danger')
        return redirect(url_for('user.profile'))
    

    from .models import User
    existing_user = User.query.filter_by(email=new_email).first()
    if existing_user:
        flash('البريد الإلكتروني مستخدم بالفعل', 'danger')
        return redirect(url_for('user.profile'))
    

    from .utils import generate_verification_code
    verification_code = generate_verification_code()
    g.current_user.verification_code = verification_code
    g.current_user.is_verified = False
    

    g.current_user.new_email_pending = new_email
    
    from .main import db
    db.session.commit()
    

    from .utils import send_verification_email
    email_config = current_app.config.get('EMAIL_CONFIG', {})
    verification_link = f"{request.host_url.rstrip('/')}{url_for('user.verify_email', code=verification_code)}"
    
    email_body = f"""
    <html>
    <body dir="rtl" style="font-family: Arial, sans-serif;">
        <h2>تأكيد البريد الإلكتروني الجديد</h2>
        <p>لقد طلبت تغيير بريدك الإلكتروني في موقع نقطة وصل. للتأكيد، يرجى النقر على الرابط أدناه:</p>
        <p><a href="{verification_link}" 
              style="padding: 10px 20px; background-color: #0d6efd; color: white; text-decoration: none; border-radius: 5px;">
           تأكيد البريد الإلكتروني</a></p>
        <p>أو يمكنك استخدام رمز التحقق التالي: <strong>{verification_code}</strong></p>
        <p>هذا الرابط صالح لمدة 24 ساعة فقط.</p>
        <p>إذا لم تطلب هذا التغيير، يرجى تجاهل هذا البريد الإلكتروني.</p>
        <p>مع تحياتنا،<br>فريق نقطة وصل</p>
    </body>
    </html>
    """
    
    email_sent = send_verification_email(
        to_email=new_email,
        message_body=email_body,
        email_config=email_config,
        subject="تأكيد تغيير البريد الإلكتروني - نقطة وصل",
        is_html=True
    )
    
    if email_sent:
        flash('تم إرسال رابط تأكيد إلى بريدك الإلكتروني الجديد. يرجى التحقق من صندوق الوارد الخاص بك', 'success')
        

        from .main import log_activity
        log_activity(
            user_id=g.current_user.id,
            action='change_email_request',
            entity_type='user',
            entity_id=g.current_user.id,
            details=f"طلب تغيير البريد الإلكتروني من {g.current_user.email} إلى {new_email}",
            request=request
        )
    else:
        flash('حدث خطأ أثناء إرسال البريد الإلكتروني. يرجى المحاولة لاحقاً', 'danger')
    
    return redirect(url_for('user.profile'))

@user_bp.route('/verify_email/<code>')
def verify_email(code):
    """تأكيد تغيير البريد الإلكتروني"""
    if not g.current_user or not g.current_user.is_authenticated:
        flash('يجب تسجيل الدخول لتأكيد البريد الإلكتروني', 'warning')
        return redirect(url_for('auth.login'))

    if not g.current_user.verification_code or g.current_user.verification_code != code:
        flash('رمز التحقق غير صالح أو منتهي الصلاحية', 'danger')
        return redirect(url_for('user.profile'))
    

    if hasattr(g.current_user, 'new_email_pending') and g.current_user.new_email_pending:
        old_email = g.current_user.email
        g.current_user.email = g.current_user.new_email_pending
        g.current_user.new_email_pending = None
        g.current_user.verification_code = None
        g.current_user.is_verified = True
        
        from .main import db
        db.session.commit()
        
        # تسجيل النشاط
        from .main import log_activity
        log_activity(
            user_id=g.current_user.id,
            action='change_email_completed',
            entity_type='user',
            entity_id=g.current_user.id,
            details=f"تم تغيير البريد الإلكتروني من {old_email} إلى {g.current_user.email}",
            request=request
        )
        
        flash('تم تغيير البريد الإلكتروني بنجاح', 'success')
    else:
        flash('حدث خطأ أثناء تأكيد البريد الإلكتروني', 'danger')
    
    return redirect(url_for('user.profile'))


@products_bp.route('/my-products')
def my_products():
    """عرض منتجات المستخدم"""
    if not g.current_user or not g.current_user.is_authenticated:
        flash('يجب تسجيل الدخول لعرض منتجاتك', 'warning')
        return redirect(url_for('auth.login', next=request.path))

    from .models import Product
    products = Product.query.filter_by(seller_id=g.current_user.id).order_by(Product.created_at.desc()).all()
    

    return render_template('my-products.html', products=products)


@user_bp.route('/profile')
def profile():
    """الملف الشخصي للمستخدم الحالي"""
    if not g.current_user or not g.current_user.is_authenticated:
        flash('يجب تسجيل الدخول لعرض الملف الشخصي', 'warning')
        return redirect(url_for('auth.login', next=request.path))

    user = g.current_user
    user.rating = user.calculate_rating()
    user.reviews_count = len(user.reviews_received)
    user.active_products_count = len([p for p in user.products if p.is_active and not p.is_sold])
    user.sold_products_count = len([p for p in user.products if p.is_sold])
    
    return render_template('user_profile.html', user=user)

@user_bp.route('/public_profile/<int:user_id>')
def public_profile(user_id):
    """الملف الشخصي العام لمستخدم"""
    from .models import User, UserReview, Product  # استيراد النماذج

    user = User.query.get_or_404(user_id)

    if user.is_banned:
        flash('هذا المستخدم محظور', 'warning')
        return redirect(url_for('main.index'))

    reviews = UserReview.query.filter_by(reviewed_user_id=user_id).order_by(UserReview.created_at.desc()).limit(5).all()

    user_products = Product.query.filter_by(seller_id=user_id, is_active=True, is_sold=False).order_by(Product.created_at.desc()).limit(6).all()

    user.rating = user.calculate_rating()
    user.reviews_count = len(user.reviews_received)
    user.active_products_count = len([p for p in user.products if p.is_active and not p.is_sold])
    user.sold_products_count = len([p for p in user.products if p.is_sold])

    show_review_button = False
    if g.current_user and g.current_user.is_authenticated and g.current_user.id != user_id:
        existing_review = UserReview.query.filter_by(reviewer_id=g.current_user.id, reviewed_user_id=user_id).first()
        show_review_button = existing_review is None

    locations = [
        {'id': 'damascus', 'name': 'دمشق'},
        {'id': 'aleppo', 'name': 'حلب'},
        {'id': 'homs', 'name': 'حمص'},
        {'id': 'latakia', 'name': 'اللاذقية'},
        {'id': 'tartus', 'name': 'طرطوس'},
        {'id': 'hama', 'name': 'حماة'},
        {'id': 'daraa', 'name': 'درعا'},
        {'id': 'idlib', 'name': 'إدلب'},
        {'id': 'hasaka', 'name': 'الحسكة'},
        {'id': 'suwayda', 'name': 'السويداء'},
        {'id': 'deir-ez-zor', 'name': 'دير الزور'},
        {'id': 'raqqa', 'name': 'الرقة'},
        {'id': 'quneitra', 'name': 'القنيطرة'},
        {'id': 'rif-dimashq', 'name': 'ريف دمشق'}
    ]
    
    return render_template(
        'user_profile.html',
        user=user,
        reviews=reviews,
        user_products=user_products,
        show_review_button=show_review_button,
        has_more_products=len(user_products) > 0,
        locations=locations,
        Product=Product,  # تمرير نموذج Product للقالب
        UserReview=UserReview  # تمرير نموذج UserReview للقالب
    )

@user_bp.route('/add_review/<int:user_id>', methods=['POST'])
def add_review(user_id):
    """إضافة تقييم لمستخدم مرتبط بمنتج تم شراؤه"""
    if not g.current_user or not g.current_user.is_authenticated:
        flash('يجب تسجيل الدخول لإضافة تقييم', 'warning')
        return redirect(url_for('auth.login', next=request.path))

    user = User.query.get_or_404(user_id)

    if g.current_user.id == user_id:
        flash('لا يمكنك إضافة تقييم لنفسك', 'warning')
        return redirect(url_for('user.public_profile', user_id=user_id))
    
    # الحصول على معرف المنتج من النموذج
    product_id = request.form.get('product_id')
    
    if not product_id:
        flash('يجب تحديد المنتج الذي قمت بشرائه', 'warning')
        return redirect(url_for('user.public_profile', user_id=user_id))
    
    # التحقق من المنتج
    product = Product.query.get_or_404(product_id)
    
    # التحقق من أن المستخدم هو المشتري الفعلي للمنتج وأن البائع هو المستخدم المراد تقييمه
    if product.seller_id != user_id or product.buyer_id != g.current_user.id:
        flash('يمكنك فقط تقييم البائعين الذين اشتريت منهم بالفعل', 'warning')
        return redirect(url_for('user.public_profile', user_id=user_id))
    
    # التحقق من عدم وجود تقييم سابق لهذا المنتج
    existing_review = UserReview.query.filter_by(
        reviewer_id=g.current_user.id, 
        reviewed_user_id=user_id,
        product_id=product_id
    ).first()
    
    if existing_review:
        flash('لقد قمت بتقييم هذا المنتج من قبل', 'warning')
        return redirect(url_for('user.public_profile', user_id=user_id))

    # الحصول على بيانات التقييم
    rating = int(request.form.get('rating', 5))
    comment = request.form.get('comment', '')

    if rating < 1 or rating > 5:
        flash('يجب أن يكون التقييم بين 1 و 5', 'warning')
        return redirect(url_for('user.public_profile', user_id=user_id))

    # إنشاء تقييم جديد مرتبط بالمنتج
    review = UserReview(
        reviewer_id=g.current_user.id,
        reviewed_user_id=user_id,
        product_id=product_id,
        rating=rating,
        comment=comment
    )

    db.session.add(review)
    db.session.commit()
    
    flash('تم إضافة التقييم بنجاح', 'success')
    return redirect(url_for('user.public_profile', user_id=user_id))


@user_bp.route('/update_profile', methods=['POST'])
def update_profile():
    """تحديث معلومات الملف الشخصي"""
    if not g.current_user or not g.current_user.is_authenticated:
        flash('يجب تسجيل الدخول لتحديث الملف الشخصي', 'warning')
        return redirect(url_for('auth.login', next=request.path))

    # سجّل البيانات الواردة للتصحيح
    current_app.logger.info(f"بيانات النموذج الواردة: {request.form}")
    current_app.logger.info(f"الملفات الواردة: {request.files}")

    name = request.form.get('name')
    phone = request.form.get('phone')
    location = request.form.get('location')
    bio = request.form.get('bio')

    if not name:
        flash('الاسم مطلوب', 'danger')
        return redirect(url_for('user.profile'))

    g.current_user.name = name
    g.current_user.phone = phone
    g.current_user.location = location
    g.current_user.bio = bio

    # معالجة صورة الملف الشخصي إذا كانت موجودة
    profile_image = request.files.get('profile_image')
    if profile_image and profile_image.filename:
        try:
            from .image_service import ImageService
            
            # التحقق من نوع الملف
            if not ImageService.allowed_file(profile_image.filename):
                flash('صيغة الملف غير مدعومة، الصيغ المدعومة هي: JPG، PNG، GIF', 'danger')
                return redirect(url_for('user.profile'))
                
            # التحقق من حجم الملف
            profile_image.seek(0, os.SEEK_END)
            file_size = profile_image.tell()
            profile_image.seek(0)
            if file_size > 5 * 1024 * 1024:  # 5MB
                flash('حجم الصورة يجب أن لا يتجاوز 5 ميجابايت', 'danger')
                return redirect(url_for('user.profile'))
            
            # تسجيل معلومات الصورة
            current_app.logger.info(f"معالجة صورة الملف الشخصي: {profile_image.filename}, النوع: {profile_image.content_type}, الحجم: {file_size} بايت")
            
            # رفع الصورة
            result = ImageService.upload_file(profile_image, folder='users')
            
            if result:
                # حفظ معرّف الصورة القديمة لحذفها لاحقاً
                old_image_id = g.current_user.profile_image
                
                # تحديث معرّف الصورة في قاعدة البيانات
                g.current_user.profile_image = result['id']
                
                # تحديث رابط الصورة المباشر أيضاً
                g.current_user.profile_image_url = result['url']
                
                current_app.logger.info(f"تم رفع الصورة بنجاح: معرّف={result['id']}, رابط={result['url']}")
                
                # حذف الصورة القديمة
                if old_image_id:
                    try:
                        ImageService.delete_image(old_image_id, folder='users')
                        current_app.logger.info(f"تم حذف الصورة القديمة: {old_image_id}")
                    except Exception as e:
                        current_app.logger.warning(f"فشل في حذف الصورة القديمة: {str(e)}")
                
                # تسجيل النشاط
                from .main import log_activity
                log_activity(
                    user_id=g.current_user.id,
                    action='update_profile_image',
                    entity_type='user',
                    entity_id=g.current_user.id,
                    details=f"تم تغيير الصورة الشخصية من خلال تحديث الملف الشخصي",
                    request=request
                )
                
                flash('تم تحديث الصورة الشخصية بنجاح', 'success')
            else:
                current_app.logger.error(f"فشل في رفع صورة الملف الشخصي")
                flash('حدث خطأ أثناء رفع الصورة', 'danger')
        except Exception as e:
            current_app.logger.error(f"خطأ أثناء معالجة الصورة: {str(e)}")
            current_app.logger.exception("تفاصيل الخطأ:")
            flash('حدث خطأ غير متوقع أثناء معالجة الصورة', 'danger')

    # سجّل القيم النهائية
    current_app.logger.info(f"قيم المستخدم بعد التحديث: profile_image={g.current_user.profile_image}, profile_image_url={g.current_user.profile_image_url}")

    # حفظ التغييرات في قاعدة البيانات
    from .main import db
    db.session.commit()
    
    flash('تم تحديث الملف الشخصي بنجاح', 'success')
    return redirect(url_for('user.profile'))

@admin_bp.route('/debug/user-images')
@admin_required
def debug_user_images(current_user):
    """عرض معلومات تشخيصية عن صور المستخدمين (للمسؤولين فقط)"""
    from .models import User
    from .image_service import ImageService
    
    users = User.query.all()
    
    user_images = []
    for user in users:
        image_info = {
            'user_id': user.id,
            'user_name': user.name,
            'profile_image': user.profile_image,
            'profile_image_url': user.profile_image_url,
            'generated_url': None,
            'image_exists': False,
            'created_at': user.created_at,
        }
        
        # محاولة توليد URL باستخدام معرّف الصورة
        if user.profile_image:
            default_image = current_app.config['IMAGES_CONFIG']['default_avatar']
            generated_url = ImageService.get_image_url(user.profile_image, default_image, 'users')
            image_info['generated_url'] = generated_url
            
            # التحقق مما إذا كانت صورة فعلية أم صورة افتراضية
            image_info['image_exists'] = generated_url != default_image
        
        user_images.append(image_info)
    
    # إعدادات المجلدات
    static_folder = current_app.static_folder
    users_folder = os.path.join(static_folder, 'images', 'users')
    
    # معلومات التخزين
    storage_info = {
        'users_folder': users_folder,
        'folder_exists': os.path.exists(users_folder),
        'folder_writable': os.access(users_folder, os.W_OK) if os.path.exists(users_folder) else False,
        'file_count': len(os.listdir(users_folder)) if os.path.exists(users_folder) else 0,
    }
    
    # معلومات التكوين
    config_info = {
        'cloudflare_enabled': bool(all([
            current_app.config['CLOUDFLARE_CONFIG'].get('account_id'),
            current_app.config['CLOUDFLARE_CONFIG'].get('api_token'),
            current_app.config['CLOUDFLARE_CONFIG'].get('image_delivery_url')
        ])),
        'default_avatar': current_app.config['IMAGES_CONFIG'].get('default_avatar'),
        'allowed_extensions': current_app.config['IMAGES_CONFIG'].get('allowed_extensions'),
        'max_image_size': current_app.config['IMAGES_CONFIG'].get('max_size')
    }
    
    return render_template(
        'admin/debug_user_images.html',
        user_images=user_images,
        storage_info=storage_info,
        config_info=config_info
    )


@user_bp.route('/change_password', methods=['POST'])
def change_password():
    """تغيير كلمة المرور"""
    if not g.current_user or not g.current_user.is_authenticated:
        flash('يجب تسجيل الدخول لتغيير كلمة المرور', 'warning')
        return redirect(url_for('auth.login', next=request.path))

    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    if not check_password_hash(g.current_user.password, current_password):
        flash('كلمة المرور الحالية غير صحيحة', 'danger')
        return redirect(url_for('user.profile'))

    if new_password != confirm_password:
        flash('كلمتا المرور غير متطابقتين', 'danger')
        return redirect(url_for('user.profile'))

    if len(new_password) < 8:
        flash('كلمة المرور يجب أن تكون 8 أحرف على الأقل', 'danger')
        return redirect(url_for('user.profile'))

    g.current_user.password = generate_password_hash(new_password)

    from .main import db
    db.session.commit()
    
    flash('تم تغيير كلمة المرور بنجاح', 'success')
    return redirect(url_for('user.profile'))

@user_bp.route('/change_profile_image', methods=['POST'])
def change_profile_image():
    """تغيير الصورة الشخصية"""

    if not g.current_user or not g.current_user.is_authenticated:
        flash('يجب تسجيل الدخول لتغيير الصورة الشخصية', 'warning')
        return redirect(url_for('auth.login', next=request.path))

    profile_image = request.files.get('profile_image')

    if not profile_image:
        flash('لم يتم اختيار صورة', 'danger')
        return redirect(url_for('user.profile'))

    if not profile_image.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
        flash('يجب أن تكون الصورة بصيغة JPG أو PNG أو GIF', 'danger')
        return redirect(url_for('user.profile'))

    # التحقق من حجم الملف
    profile_image.seek(0, os.SEEK_END)
    file_size = profile_image.tell()
    if file_size > 5 * 1024 * 1024:
        flash('حجم الصورة يجب أن لا يتجاوز 5 ميجابايت', 'danger')
        return redirect(url_for('user.profile'))

    profile_image.seek(0)
    
    try:
        from .image_service import ImageService
        
        # تسجيل الطلب
        current_app.logger.info(f"طلب تغيير الصورة الشخصية للمستخدم {g.current_user.id} ({g.current_user.name})")
        current_app.logger.info(f"معلومات الصورة: {profile_image.filename}, النوع: {profile_image.content_type}")
        
        # تحميل الصورة
        result = ImageService.upload_file(profile_image, folder='users')
        
        if result:
            # حفظ المعرف القديم للحذف لاحقًا
            old_image_id = g.current_user.profile_image
            
            # تحديث معرف الصورة في قاعدة البيانات
            g.current_user.profile_image = result['id']
            
            # لتصحيح المشكلة: نحتفظ أيضًا برابط URL بشكل مباشر لمدة مؤقتة للتحقق
            g.current_user.profile_image_url = result['url']
            
            # حفظ التغييرات في قاعدة البيانات
            db.session.commit()
            
            # حذف الصورة القديمة
            if old_image_id:
                try:
                    ImageService.delete_image(old_image_id, folder='users')
                    current_app.logger.info(f"تم حذف الصورة القديمة: {old_image_id}")
                except Exception as e:
                    current_app.logger.warning(f"فشل في حذف الصورة القديمة: {str(e)}")
            
            # تسجيل النشاط
            from .main import log_activity
            log_activity(
                user_id=g.current_user.id,
                action='update_profile_image',
                entity_type='user',
                entity_id=g.current_user.id,
                details=f"تم تغيير الصورة الشخصية، المعرف الجديد: {result['id']}",
                request=request
            )
            
            flash('تم تغيير الصورة الشخصية بنجاح', 'success')
            current_app.logger.info(f"تم تغيير الصورة الشخصية بنجاح للمستخدم {g.current_user.id}")
        else:
            flash('حدث خطأ أثناء رفع الصورة. يرجى المحاولة مرة أخرى.', 'danger')
            current_app.logger.error(f"فشل في تحميل الصورة الشخصية للمستخدم {g.current_user.id}")
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"خطأ في تغيير الصورة الشخصية: {str(e)}")
        current_app.logger.exception("تفاصيل الخطأ:")
        flash('حدث خطأ غير متوقع. يرجى المحاولة مرة أخرى.', 'danger')
    
    return redirect(url_for('user.profile'))


@user_bp.route('/delete_account', methods=['POST'])
def delete_account():
    """حذف الحساب"""
  
    if not g.current_user or not g.current_user.is_authenticated:
        flash('يجب تسجيل الدخول لحذف الحساب', 'warning')
        return redirect(url_for('auth.login', next=request.path))
    
 
    password_confirm = request.form.get('password_confirm')
    confirm_delete = request.form.get('confirm_delete') == 'on'

    if not confirm_delete:
        flash('يرجى تأكيد رغبتك في حذف الحساب', 'danger')
        return redirect(url_for('user.profile'))
    

    if not check_password_hash(g.current_user.password, password_confirm):
        flash('كلمة المرور غير صحيحة', 'danger')
        return redirect(url_for('user.profile'))
    
    try:
     
        user_id = g.current_user.id
        user_email = g.current_user.email
        
    
        from .models import Product
        products = Product.query.filter_by(seller_id=user_id).all()
        for product in products:
        
            product.is_active = False
            db.session.delete(product)  # اختياري: حذف المنتجات بالكامل
        

        from .models import Message
        sent_messages = Message.query.filter_by(sender_id=user_id).all()
        received_messages = Message.query.filter_by(receiver_id=user_id).all()
        
        for message in sent_messages + received_messages:
            db.session.delete(message)
        

        from .models import UserReview
        reviews_given = UserReview.query.filter_by(reviewer_id=user_id).all()
        reviews_received = UserReview.query.filter_by(reviewed_user_id=user_id).all()
        
        for review in reviews_given + reviews_received:
            db.session.delete(review)
        

        g.current_user.favorites_products = []
        
  
        if g.current_user.profile_image:
            from .image_service import ImageService
            ImageService.delete_image(g.current_user.profile_image, folder='users')

        from .main import log_activity
        log_activity(
            user_id=None, 
            action='account_deleted',
            entity_type='user',
            entity_id=user_id,
            details=f"تم حذف الحساب {user_email}",
            request=request
        )
        

        db.session.delete(g.current_user)
        db.session.commit()
        

        session.pop('auth_token', None)
        
        flash('تم حذف الحساب بنجاح', 'success')
        return redirect(url_for('main.index'))
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"خطأ في حذف الحساب: {str(e)}")
        flash('حدث خطأ أثناء حذف الحساب. يرجى المحاولة مرة أخرى.', 'danger')
        return redirect(url_for('user.profile'))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """تسجيل الدخول"""
    if g.current_user and g.current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember_me = request.form.get('remember_me') == 'on'
        
        if not email or not password:
            flash('يرجى إدخال البريد الإلكتروني وكلمة المرور', 'danger')
            return redirect(url_for('auth.login'))

        from .models import User
        user = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.password, password):
            flash('البريد الإلكتروني أو كلمة المرور غير صحيحة', 'danger')
            return redirect(url_for('auth.login'))

        if user.is_banned:
            flash('هذا الحساب محظور. يرجى التواصل مع الإدارة', 'danger')
            return redirect(url_for('auth.login'))

        user.last_login = datetime.utcnow()
        from .main import db
        db.session.commit()

        from .utils import create_token
        token = create_token(user.id, user.is_admin, 30 if remember_me else 1)

        session['auth_token'] = token

        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)

        return redirect(url_for('main.index'))
    
    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """إنشاء حساب جديد"""
    if g.current_user and g.current_user.is_authenticated:
        return redirect(url_for('main.index'))

    locations = [
        {'id': 'damascus', 'name': 'دمشق'},
        {'id': 'aleppo', 'name': 'حلب'},
        {'id': 'homs', 'name': 'حمص'},
        {'id': 'latakia', 'name': 'اللاذقية'},
        {'id': 'tartus', 'name': 'طرطوس'},
        {'id': 'hama', 'name': 'حماة'},
        {'id': 'daraa', 'name': 'درعا'},
        {'id': 'idlib', 'name': 'إدلب'},
        {'id': 'hasaka', 'name': 'الحسكة'},
        {'id': 'suwayda', 'name': 'السويداء'},
        {'id': 'deir-ez-zor', 'name': 'دير الزور'},
        {'id': 'raqqa', 'name': 'الرقة'},
        {'id': 'quneitra', 'name': 'القنيطرة'},
        {'id': 'rif-dimashq', 'name': 'ريف دمشق'}
    ]
    
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        location = request.form.get('location')
        password = request.form.get('password')
        password_confirm = request.form.get('password_confirm')
        terms = request.form.get('terms') == 'on'

        if not name or not email or not password:
            flash('جميع الحقول المطلوبة يجب ملؤها', 'danger')
            return redirect(url_for('auth.register'))

        if password != password_confirm:
            flash('كلمتا المرور غير متطابقتين', 'danger')
            return redirect(url_for('auth.register'))

        if len(password) < 8:
            flash('كلمة المرور يجب أن تكون 8 أحرف على الأقل', 'danger')
            return redirect(url_for('auth.register'))

        if not terms:
            flash('يجب الموافقة على شروط الاستخدام وسياسة الخصوصية', 'danger')
            return redirect(url_for('auth.register'))

        from .models import User
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('البريد الإلكتروني مستخدم بالفعل', 'danger')
            return redirect(url_for('auth.register'))

        from .utils import generate_verification_code
        verification_code = generate_verification_code()
        
        try:
            new_user = User(
                name=name,
                email=email,
                password=generate_password_hash(password),
                phone=phone,
                location=location,
                verification_code=verification_code,
                is_verified=False
            )

            db.session.add(new_user)
            db.session.commit()
            user_id = new_user.id

            token_data = {
                'user_id': user_id,
                'code': verification_code,
                'exp': datetime.utcnow() + timedelta(days=1)
            }
            token = jwt.encode(token_data, current_app.config['SECRET_KEY'], algorithm="HS256")

            verify_link = f"{request.host_url.rstrip('/')}{url_for('auth.verify', token=token)}"

            email_body = f"""
            <html>
            <body dir="rtl" style="font-family: Arial, sans-serif;">
                <h2>مرحباً بك في نقطة وصل!</h2>
                <p>شكراً لتسجيلك معنا. لتفعيل حسابك، يرجى النقر على الرابط أدناه:</p>
                <p><a href="{verify_link}" 
                      style="padding: 10px 20px; background-color: #0d6efd; color: white; text-decoration: none; border-radius: 5px;">
                   تفعيل الحساب</a></p>
                <p>أو يمكنك استخدام هذا الرمز: <strong>{verification_code}</strong></p>
                <p>هذا الرابط صالح لمدة 24 ساعة فقط.</p>
                <p>مع تحياتنا،<br>فريق نقطة وصل</p>
            </body>
            </html>
            """
            email_config = current_app.config.get('EMAIL_CONFIG', {})
            email_sent = send_verification_email(
                to_email=email,
                message_body=email_body,
                email_config=email_config,
                subject="تفعيل حسابك في نقطة وصل",
                is_html=True
            )
            
            if email_sent:
                from .main import log_activity
                log_activity(
                    user_id=user_id,
                    action='register',
                    entity_type='user',
                    entity_id=user_id,
                    details=f"تسجيل مستخدم جديد: {email}",
                    request=request
                )
                
                flash('تم إنشاء الحساب بنجاح! يرجى التحقق من بريدك الإلكتروني لتفعيل حسابك', 'success')
            else:
                current_app.logger.error(f"فشل في إرسال بريد التحقق إلى {email}")
                flash('تم إنشاء الحساب ولكن حدث خطأ في إرسال بريد التحقق. يرجى الاتصال بالدعم.', 'warning')
                
            return redirect(url_for('auth.login'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"خطأ في تسجيل المستخدم: {str(e)}")
            flash('حدث خطأ أثناء إنشاء الحساب. يرجى المحاولة مرة أخرى.', 'danger')
            return redirect(url_for('auth.register'))
    
    return render_template('register.html', locations=locations)

@products_bp.route('/api/favorite/<int:product_id>', methods=['POST'])
def toggle_favorite(product_id):
    """إضافة/إزالة منتج من المفضلة"""
    if not g.current_user or not g.current_user.is_authenticated:
        return jsonify({'success': False, 'message': 'يجب تسجيل الدخول لإضافة المنتج للمفضلة'}), 401
    
    try:
        from .models import Product
        product = Product.query.get_or_404(product_id)
        is_favorite = product in g.current_user.favorites_products
        
        if is_favorite:
            g.current_user.favorites_products.remove(product)
            action = 'remove_favorite'
            message = 'تمت إزالة المنتج من المفضلة'
        else:
            g.current_user.favorites_products.append(product)
            action = 'add_favorite'
            message = 'تمت إضافة المنتج للمفضلة'

        db.session.commit()

        from .main import log_activity
        log_activity(
            user_id=g.current_user.id,
            action=action,
            entity_type='product',
            entity_id=product.id,
            request=request
        )
        
        return jsonify({
            'success': True,
            'message': message,
            'is_favorite': not is_favorite
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"خطأ في تبديل حالة المفضلة: {str(e)}")
        return jsonify({'success': False, 'message': 'حدث خطأ. يرجى المحاولة مرة أخرى.'}), 500

@products_bp.route('/mark-as-sold/<int:product_id>', methods=['GET', 'POST'])
def mark_as_sold(product_id):
    """تعيين منتج كمباع مع تحديد المشتري"""
    from .models import Product, User  # أضفنا User هنا
    
    if not g.current_user or not g.current_user.is_authenticated:
        flash('يجب تسجيل الدخول لتعديل حالة المنتج', 'warning')
        return redirect(url_for('auth.login', next=request.path))

    product = Product.query.get_or_404(product_id)

    if product.seller_id != g.current_user.id and not g.current_user.is_admin:
        flash('ليس لديك صلاحية لتعديل حالة هذا المنتج', 'danger')
        return redirect(url_for('products.view', product_id=product_id))
    
    # التحقق من أن المنتج غير مباع بالفعل
    if product.is_sold:
        flash('هذا المنتج مباع بالفعل', 'warning')
        return redirect(url_for('products.view', product_id=product_id))
    
    if request.method == 'POST':
        buyer_email = request.form.get('buyer_email')
        
        if buyer_email:
            # البحث عن المشتري في قاعدة البيانات
            buyer = User.query.filter_by(email=buyer_email).first()
            
            if buyer:
                # التحقق من أن المشتري ليس هو البائع نفسه
                if buyer.id == g.current_user.id:
                    flash('لا يمكنك تسجيل نفسك كمشتري للمنتج', 'danger')
                    return redirect(url_for('products.mark_as_sold', product_id=product_id))
                    
                # حفظ معلومات المشتري وتحديث حالة المنتج
                product.buyer_id = buyer.id
                product.is_sold = True
                db.session.commit()
                
                
                flash('تم تعيين المنتج كمباع بنجاح', 'success')
                return redirect(url_for('user.profile'))
            else:
                flash('لم يتم العثور على مستخدم بهذا البريد الإلكتروني، يجب أن يكون المشتري مسجل في المنصة', 'danger')
                return redirect(url_for('products.mark_as_sold', product_id=product_id))
        else:
            flash('يرجى إدخال البريد الإلكتروني للمشتري', 'danger')
            return redirect(url_for('products.mark_as_sold', product_id=product_id))
    
    # عرض نموذج تعيين المنتج كمباع (طلب GET)
    return render_template('products/mark_as_sold.html', product=product)

@auth_bp.route('/logout', methods=['POST'])
def logout():
    """تسجيل الخروج"""
    session.pop('auth_token', None)
    
    flash('تم تسجيل الخروج بنجاح', 'success')
    return redirect(url_for('main.index'))

@auth_bp.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    """نسيت كلمة المرور"""
    if request.method == 'POST':
        email = request.form.get('email')
        if not email:
            flash('يرجى إدخال البريد الإلكتروني', 'danger')
            return redirect(url_for('auth.forgot_password'))
        from .models import User
        user = User.query.filter_by(email=email).first()
        
        if user:
            from .utils import generate_verification_code
            reset_code = generate_verification_code()
            user.verification_code = reset_code
            db.session.commit()
            token_data = {
                'user_id': user.id,
                'code': reset_code,
                'exp': datetime.utcnow() + timedelta(hours=24)
            }
            token = jwt.encode(token_data, current_app.config['SECRET_KEY'], algorithm="HS256")
            reset_link = f"{request.host_url.rstrip('/')}{url_for('auth.reset_password', token=token)}"
            email_body = f"""
            <html>
            <body dir="rtl" style="font-family: Arial, sans-serif;">
                <h2>إعادة تعيين كلمة المرور</h2>
                <p>تم طلب إعادة تعيين كلمة المرور لحسابك. انقر على الرابط أدناه لإعادة تعيين كلمة المرور:</p>
                <p><a href="{reset_link}" 
                      style="padding: 10px 20px; background-color: #0d6efd; color: white; text-decoration: none; border-radius: 5px;">
                   إعادة تعيين كلمة المرور</a></p>
                <p>إذا لم تطلب إعادة تعيين كلمة المرور، يرجى تجاهل هذا البريد الإلكتروني.</p>
                <p>هذا الرابط صالح لمدة 24 ساعة فقط.</p>
                <p>مع تحياتنا،<br>فريق نقطة وصل</p>
            </body>
            </html>
            """
            email_config = current_app.config.get('EMAIL_CONFIG', {})
            email_sent = send_verification_email(
                to_email=email,
                message_body=email_body,
                email_config=email_config,
                subject="إعادة تعيين كلمة المرور - نقطة وصل",
                is_html=True
            )
            
            if email_sent:
                from .main import log_activity
                log_activity(
                    user_id=user.id,
                    action='password_reset_request',
                    entity_type='user',
                    entity_id=user.id,
                    details=f"طلب إعادة تعيين كلمة المرور من {request.remote_addr}",
                    request=request
                )
                
                flash('تم إرسال رابط إعادة تعيين كلمة المرور إلى بريدك الإلكتروني', 'success')
            else:
                current_app.logger.error(f"فشل في إرسال بريد إعادة تعيين كلمة المرور إلى {email}")
                flash('حدث خطأ أثناء إرسال البريد الإلكتروني. يرجى المحاولة لاحقاً.', 'danger')
        else:
            flash('تم إرسال رابط إعادة تعيين كلمة المرور إلى بريدك الإلكتروني (إذا كان الحساب موجودًا)', 'success')
            current_app.logger.info(f"محاولة إعادة تعيين كلمة المرور لبريد إلكتروني غير موجود: {email}")
        
        return redirect(url_for('auth.login'))
    
    return render_template('forgot_password.html')


def send_verification_email(to_email, message_body, email_config, subject=None, is_html=False):
    """إرسال بريد إلكتروني للتحقق أو إعادة تعيين كلمة المرور"""
    try:
        msg = MIMEMultipart()
        msg['From'] = f"{email_config.get('sender_name', 'نقطة وصل')} <{email_config.get('username')}>"
        msg['To'] = to_email
        msg['Subject'] = subject or "رابط إعادة تعيين كلمة المرور"

        if is_html:
            msg.attach(MIMEText(message_body, 'html'))
        else:
            msg.attach(MIMEText(message_body, 'plain'))
        
        server = smtplib.SMTP(email_config.get('smtp_server', 'smtp.gmail.com'), 
                             int(email_config.get('smtp_port', 587)))
        server.starttls()
        server.login(email_config.get('username'), email_config.get('password'))
        server.send_message(msg)
        server.quit()
        
        return True
    except Exception as e:
        print(f"خطأ في إرسال البريد الإلكتروني: {str(e)}")
        return False
    

@auth_bp.route('/verify/<token>')
def verify(token):
    """تفعيل الحساب"""
    try:
        data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
        user_id = data.get('user_id')
        verification_code = data.get('code')

        from .models import User
        user = User.query.get(user_id)
        if not user or user.verification_code != verification_code:
            flash('رابط التفعيل غير صالح', 'danger')
            return redirect(url_for('auth.login'))
        user.is_verified = True
        user.verification_code = None

        from .main import db
        db.session.commit()
        
        flash('تم تفعيل حسابك بنجاح! يمكنك الآن تسجيل الدخول', 'success')
    except:
        flash('رابط التفعيل غير صالح أو منتهي الصلاحية', 'danger')
    
    return redirect(url_for('auth.login'))

@auth_bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """إعادة تعيين كلمة المرور"""
    try:
        data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
        user_id = data.get('user_id')
        verification_code = data.get('code')
        from .models import User
        user = User.query.get(user_id)

        if not user or user.verification_code != verification_code:
            flash('رابط إعادة تعيين كلمة المرور غير صالح', 'danger')
            return redirect(url_for('auth.login'))
        
        if request.method == 'POST':
            password = request.form.get('password')
            password_confirm = request.form.get('password_confirm')

            if password != password_confirm:
                flash('كلمتا المرور غير متطابقتين', 'danger')
                return redirect(url_for('auth.reset_password', token=token))

            if len(password) < 8:
                flash('كلمة المرور يجب أن تكون 8 أحرف على الأقل', 'danger')
                return redirect(url_for('auth.reset_password', token=token))

            user.password = generate_password_hash(password)
            user.verification_code = None

            from .main import db
            db.session.commit()
            
            flash('تم تغيير كلمة المرور بنجاح! يمكنك الآن تسجيل الدخول', 'success')
            return redirect(url_for('auth.login'))
        
        return render_template('reset_password.html')
    except:
        flash('رابط إعادة تعيين كلمة المرور غير صالح أو منتهي الصلاحية', 'danger')
        return redirect(url_for('auth.login'))



@messages_bp.route('/')
def index():
    """صفحة المراسلات الرئيسية"""
    if not g.current_user or not g.current_user.is_authenticated:
        flash('يجب تسجيل الدخول للوصول إلى المراسلات', 'warning')
        return redirect(url_for('auth.login', next=request.path))

    conversations = []
    
    return render_template('messages/index.html', conversations=conversations)

# في ملف bot/bot/routes.py

@messages_bp.route('/chat/<int:user_id>')
def chat(user_id):
    """صفحة المحادثة مع مستخدم"""
    if not g.current_user or not g.current_user.is_authenticated:
        flash('يجب تسجيل الدخول للوصول إلى المراسلات', 'warning')
        return redirect(url_for('auth.login', next=request.path))

    from .models import User, Message, Product
    user = User.query.get_or_404(user_id)

    if g.current_user.id == user_id:
        flash('لا يمكنك إرسال رسائل لنفسك', 'warning')
        return redirect(url_for('messages.conversations'))

    product_id = request.args.get('product_id', type=int)
    product = None
    if product_id:
        product = Product.query.get(product_id)
    
    # جلب الرسائل بين المستخدمين والمتعلقة بالمنتج المحدد
    messages_query = Message.query.filter(
        ((Message.sender_id == g.current_user.id) & (Message.receiver_id == user_id)) |
        ((Message.sender_id == user_id) & (Message.receiver_id == g.current_user.id))
    )
    
    if product_id:
        messages_query = messages_query.filter(Message.product_id == product_id)
    
    messages = messages_query.order_by(Message.created_at).all()
    
    # تحديث حالة القراءة للرسائل الواردة
    for message in messages:
        if message.receiver_id == g.current_user.id and not message.is_read:
            message.is_read = True
    
    db.session.commit()
    
    return render_template('messages/chat.html', user=user, messages=messages, product_id=product_id, product=product)


@messages_bp.route('/conversations')
def conversations():
    """قائمة المحادثات"""
    if not g.current_user or not g.current_user.is_authenticated:
        flash('يجب تسجيل الدخول للوصول إلى المراسلات', 'warning')
        return redirect(url_for('auth.login', next=request.path))
    
    from .models import User, Message, Product
    from sqlalchemy import func, desc, or_, case, distinct
    
    # استعلام لجلب محادثات فريدة بناءً على المستخدم والمنتج
    subquery = db.session.query(
        func.max(Message.id).label('msg_id'),
        case(
            (Message.sender_id == g.current_user.id, Message.receiver_id),
            else_=Message.sender_id
        ).label('other_user_id'),
        Message.product_id.label('product_id')
    ).filter(
        or_(Message.sender_id == g.current_user.id, Message.receiver_id == g.current_user.id)
    ).group_by(
        case(
            (Message.sender_id == g.current_user.id, Message.receiver_id),
            else_=Message.sender_id
        ),
        Message.product_id
    ).subquery()
    
    # استعلام لجلب معلومات المحادثات
    conversations_query = db.session.query(
        User,
        Message,
        func.count(Message.id).filter(
            Message.receiver_id == g.current_user.id,
            Message.is_read == False,
            Message.product_id == subquery.c.product_id
        ).label('unread_count')
    ).join(
        subquery, subquery.c.other_user_id == User.id
    ).join(
        Message, Message.id == subquery.c.msg_id
    ).order_by(
        desc(Message.created_at)
    )
    
    conversations = []
    for user, last_message, unread_count in conversations_query.all():
        # Skip conversations where user is None
        if not user:
            continue
            
        # جلب معلومات المنتج المرتبط إذا وجد
        product = None
        if last_message and last_message.product_id:
            product = Product.query.get(last_message.product_id)
        
        conversations.append({
            'other_user': user,
            'last_message': last_message,
            'unread_count': unread_count,
            'product': product
        })
    
    return render_template('messages/conversations.html', conversations=conversations)


@main_bp.route('/robots.txt')
def robots():
    return send_from_directory(app.static_folder, 'robots.txt')

@main_bp.route('/sitemap.xml')
def sitemap():
    """توليد وعرض ملف sitemap.xml"""
    
    from .seo import generate_sitemap
    
    # قائمة المسارات الثابتة التي تريد إضافتها
    routes_to_include = [
        '/',
        '/about',
        '/contact',
        '/terms',
        '/privacy',
        '/products',
        '/categories'
    ]
    
    sitemap_xml = generate_sitemap(current_app, routes_to_include)
    response = make_response(sitemap_xml)
    response.headers["Content-Type"] = "application/xml"
    
    return response

@main_bp.route('/google123abc.html')
def google_verification():
    """صفحة التحقق من ملكية الموقع لجوجل"""
    return send_from_directory(app.static_folder, 'google123abc.html')


@messages_bp.route('/api/mark_as_read', methods=['POST'])
def mark_as_read():
    """تحديد الرسائل كمقروءة"""
    if not g.current_user or not g.current_user.is_authenticated:
        return jsonify({'success': False, 'message': 'غير مصرح'}), 401
    
    data = request.json
    message_ids = data.get('message_ids', [])
    
    if not message_ids:
        return jsonify({'success': False, 'message': 'لم يتم تحديد رسائل'}), 400
    
    from .models import Message
    messages = Message.query.filter(
        Message.id.in_(message_ids),
        Message.receiver_id == g.current_user.id,
        Message.is_read == False
    ).all()
    
    for message in messages:
        message.is_read = True
    
    db.session.commit()
    
    return jsonify({'success': True, 'count': len(messages)})



@messages_bp.route('/api/get_unread_message_count')
def get_unread_count():
    """عدد الرسائل غير المقروءة"""
    if not g.current_user or not g.current_user.is_authenticated:
        return jsonify({'success': False, 'message': 'غير مصرح'})
    
    from .models import Message
    count = Message.query.filter_by(
        receiver_id=g.current_user.id,
        is_read=False
    ).count()
    
    return jsonify({'success': True, 'unread_count': count})

@messages_bp.route('/api/get_unread_message_count_v2')  # Changed route path
def get_unread_message_count_v2():  # Changed function name
    """عدد الرسائل غير المقروءة"""
    if not g.current_user or not g.current_user.is_authenticated:
        return jsonify({'success': False, 'message': 'غير مصرح'})
    
    from .models import Message
    count = Message.query.filter_by(
        receiver_id=g.current_user.id,
        is_read=False
    ).count()
    
    return jsonify({'success': True, 'unread_count': count})

@messages_bp.route('/unread_count')
def unread_count():
    """عدد الرسائل غير المقروءة"""
    if not g.current_user or not g.current_user.is_authenticated:
        return jsonify({'success': False, 'message': 'غير مصرح'})
    unread_count = 0
    
    return jsonify({'success': True, 'unread_count': unread_count})


@admin_bp.route('/')
@admin_required
def dashboard(current_user):
    """لوحة التحكم الرئيسية"""
    # إحصائيات عامة
    from .models import User, Product, Report, Message, AuditLog
    stats = {
        'users_count': User.query.count(),
        'products_count': Product.query.count(),
        'reports_count': Report.query.count(),
        'sales_count': Product.query.filter_by(is_sold=True).count(),
        'active_users': User.query.filter_by(is_online=True).count(),
        'pending_reports': Report.query.filter_by(status='pending').count()
    }
    
    # آخر النشاطات
    recent_logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(10).all()
    
    # البلاغات الجديدة
    pending_reports = Report.query.filter_by(status='pending').order_by(Report.created_at.desc()).limit(5).all()
    
    return render_template('admin/dashboard.html', stats=stats, recent_logs=recent_logs, pending_reports=pending_reports)




@admin_bp.route('/users')
@admin_required
def users(current_user):
    """إدارة المستخدمين"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    search_query = request.args.get('search', '')
    status = request.args.get('status', '')
    verified = request.args.get('verified', '')
    
    from .models import User
    query = User.query
    
    # تطبيق الفلاتر
    if search_query:
        query = query.filter(db.or_(
            User.name.like(f'%{search_query}%'),
            User.email.like(f'%{search_query}%')
        ))
    
    if status == 'active':
        query = query.filter_by(is_banned=False)
    elif status == 'banned':
        query = query.filter_by(is_banned=True)
    elif status == 'admin':
        query = query.filter_by(is_admin=True)
    
    if verified == '1':
        query = query.filter_by(is_verified=True)
    elif verified == '0':
        query = query.filter_by(is_verified=False)
    
    # ترتيب النتائج
    query = query.order_by(User.created_at.desc())
    
    # تقسيم النتائج
    users_paginated = query.paginate(page=page, per_page=per_page)
    
    return render_template(
        'admin/users.html', 
        users=users_paginated.items,
        pagination=users_paginated,
        search_query=search_query,
        status=status,
        verified=verified
    )


@admin_bp.route('/products')
@admin_required
def products(current_user):
    """إدارة المنتجات"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    search_query = request.args.get('search', '')
    selected_category_id = request.args.get('category_id')
    status = request.args.get('status')
    sort_by = request.args.get('sort_by', 'created_at')
    
    from .models import Product, Category
    query = Product.query
    
    # تطبيق الفلاتر
    if search_query:
        query = query.filter(db.or_(
            Product.title.like(f'%{search_query}%'),
            Product.description.like(f'%{search_query}%')
        ))
    
    if selected_category_id:
        query = query.filter_by(category_id=selected_category_id)
    
    if status == 'active':
        query = query.filter_by(is_active=True, is_sold=False)
    elif status == 'sold':
        query = query.filter_by(is_sold=True)
    elif status == 'featured':
        query = query.filter_by(is_featured=True)
    elif status == 'inactive':
        query = query.filter_by(is_active=False)
    
    # ترتيب النتائج
    if sort_by == 'price':
        query = query.order_by(Product.price.asc())
    elif sort_by == 'views':
        query = query.order_by(Product.views_count.desc())
    else:  # created_at
        query = query.order_by(Product.created_at.desc())
    
    # تقسيم النتائج
    products_paginated = query.paginate(page=page, per_page=per_page)
    
    # الحصول على التصنيفات للفلتر
    categories = Category.query.filter_by(parent_id=None).all()
    
    return render_template(
        'admin/products.html',
        products=products_paginated.items,
        pagination=products_paginated,
        search_query=search_query,
        selected_category_id=selected_category_id,
        status=status,
        sort_by=sort_by,
        categories=categories
    )


@admin_bp.route('/activate_product', methods=['POST'])
@admin_required
def activate_product(current_user):
    """تفعيل منتج"""
    product_id = request.form.get('product_id')
    
    if not product_id:
        flash('معرف المنتج مطلوب', 'danger')
        return redirect(url_for('admin.products'))
    
    from .models import Product
    product = Product.query.get_or_404(product_id)
    product.is_active = True
    
    # تسجيل النشاط
    from .main import log_activity
    log_activity(
        user_id=current_user.id,
        action='activate_product',
        entity_type='product',
        entity_id=product.id,
        details=f"تفعيل المنتج: {product.title}",
        request=request
    )
    
    db.session.commit()
    
    flash('تم تفعيل المنتج بنجاح', 'success')
    return redirect(url_for('admin.products'))

@admin_bp.route('/deactivate_product', methods=['POST'])
@admin_required
def deactivate_product(current_user):
    """إيقاف منتج"""
    product_id = request.form.get('product_id')
    
    if not product_id:
        flash('معرف المنتج مطلوب', 'danger')
        return redirect(url_for('admin.products'))
    
    from .models import Product
    product = Product.query.get_or_404(product_id)
    product.is_active = False
    
    # تسجيل النشاط
    from .main import log_activity
    log_activity(
        user_id=current_user.id,
        action='deactivate_product',
        entity_type='product',
        entity_id=product.id,
        details=f"إيقاف المنتج: {product.title}",
        request=request
    )
    
    db.session.commit()
    
    flash('تم إيقاف المنتج بنجاح', 'success')
    return redirect(url_for('admin.products'))

@admin_bp.route('/feature_product', methods=['POST'])
@admin_required
def feature_product(current_user):
    """تمييز منتج"""
    product_id = request.form.get('product_id')
    
    if not product_id:
        flash('معرف المنتج مطلوب', 'danger')
        return redirect(url_for('admin.products'))
    
    from .models import Product
    product = Product.query.get_or_404(product_id)
    product.is_featured = True
    
    # تسجيل النشاط
    from .main import log_activity
    log_activity(
        user_id=current_user.id,
        action='feature_product',
        entity_type='product',
        entity_id=product.id,
        details=f"تمييز المنتج: {product.title}",
        request=request
    )
    
    db.session.commit()
    
    flash('تم تمييز المنتج بنجاح', 'success')
    return redirect(url_for('admin.products'))


@admin_bp.route('/unfeature_product', methods=['POST'])
@admin_required
def unfeature_product(current_user):
    """إلغاء تمييز منتج"""
    product_id = request.form.get('product_id')
    
    if not product_id:
        flash('معرف المنتج مطلوب', 'danger')
        return redirect(url_for('admin.products'))
    
    from .models import Product
    product = Product.query.get_or_404(product_id)
    product.is_featured = False
    
    # تسجيل النشاط
    from .main import log_activity
    log_activity(
        user_id=current_user.id,
        action='unfeature_product',
        entity_type='product',
        entity_id=product.id,
        details=f"إلغاء تمييز المنتج: {product.title}",
        request=request
    )
    
    db.session.commit()
    
    flash('تم إلغاء تمييز المنتج بنجاح', 'success')
    return redirect(url_for('admin.products'))


@admin_bp.route('/categories')
@admin_required
def categories(current_user):
    """إدارة التصنيفات"""
    from .models import Category
    categories = Category.query.all()
    return render_template('admin/categories.html', categories=categories)


@admin_bp.route('/add_category', methods=['POST'])
@admin_required
def add_category(current_user):
    """إضافة تصنيف جديد"""
    name = request.form.get('name')
    slug = request.form.get('slug')
    description = request.form.get('description')
    parent_id = request.form.get('parent_id')
    
    if not name or not slug:
        flash('جميع الحقول المطلوبة يجب ملؤها', 'danger')
        return redirect(url_for('admin.categories'))
    
    from .models import Category
    
    # التحقق من عدم وجود تصنيف بنفس الـ slug
    existing = Category.query.filter_by(slug=slug).first()
    if existing:
        flash('هذا الاسم التقني موجود بالفعل', 'danger')
        return redirect(url_for('admin.categories'))
    
    # إنشاء تصنيف جديد
    new_category = Category(
        name=name,
        slug=slug,
        description=description,
        parent_id=parent_id if parent_id else None
    )
    
    db.session.add(new_category)
    db.session.commit()
    
    flash('تم إضافة التصنيف بنجاح', 'success')
    return redirect(url_for('admin.categories'))

@admin_bp.route('/ban_user', methods=['POST'])
@admin_required
def ban_user(current_user):
    """حظر مستخدم"""
    user_id = request.form.get('user_id')
    
    if not user_id:
        flash('معرف المستخدم مطلوب', 'danger')
        return redirect(url_for('admin.users'))
    
    from .models import User
    user = User.query.get_or_404(user_id)
    
    # منع حظر المشرفين
    if user.is_admin:
        flash('لا يمكن حظر المشرفين الآخرين', 'danger')
        return redirect(url_for('admin.users'))
    
    user.is_banned = True
    
    # تسجيل النشاط
    from .main import log_activity
    log_activity(
        user_id=current_user.id,
        action='ban_user',
        entity_type='user',
        entity_id=user.id,
        details=f"حظر المستخدم: {user.name}",
        request=request
    )
    
    db.session.commit()
    
    flash('تم حظر المستخدم بنجاح', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/unban_user', methods=['POST'])
@admin_required
def unban_user(current_user):
    """إلغاء حظر مستخدم"""
    user_id = request.form.get('user_id')
    
    if not user_id:
        flash('معرف المستخدم مطلوب', 'danger')
        return redirect(url_for('admin.users'))
    
    from .models import User
    user = User.query.get_or_404(user_id)
    user.is_banned = False
    
    # تسجيل النشاط
    from .main import log_activity
    log_activity(
        user_id=current_user.id,
        action='unban_user',
        entity_type='user',
        entity_id=user.id,
        details=f"إلغاء حظر المستخدم: {user.name}",
        request=request
    )
    
    db.session.commit()
    
    flash('تم إلغاء حظر المستخدم بنجاح', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/verify_user', methods=['POST'])
@admin_required
def verify_user(current_user):
    """توثيق حساب مستخدم"""
    user_id = request.form.get('user_id')
    
    if not user_id:
        flash('معرف المستخدم مطلوب', 'danger')
        return redirect(url_for('admin.users'))
    
    from .models import User
    user = User.query.get_or_404(user_id)
    user.is_verified = True
    
    # تسجيل النشاط
    from .main import log_activity
    log_activity(
        user_id=current_user.id,
        action='verify_user',
        entity_type='user',
        entity_id=user.id,
        details=f"توثيق حساب المستخدم: {user.name}",
        request=request
    )
    
    db.session.commit()
    
    flash('تم توثيق حساب المستخدم بنجاح', 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/logs')
@admin_required
def logs(current_user):
    """سجلات النظام"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    action = request.args.get('action')
    entity_type = request.args.get('entity_type')
    user_filter = request.args.get('user')
    date_filter = request.args.get('date')
    
    from .models import AuditLog, User
    query = AuditLog.query
    
    # تطبيق الفلاتر
    if action:
        query = query.filter_by(action=action)
    
    if entity_type:
        query = query.filter_by(entity_type=entity_type)
    
    if user_filter:
        user_ids = db.session.query(User.id).filter(User.name.like(f'%{user_filter}%')).all()
        user_ids = [id[0] for id in user_ids]
        query = query.filter(AuditLog.user_id.in_(user_ids))
    
    if date_filter:
        from datetime import datetime, timedelta
        date_obj = datetime.strptime(date_filter, '%Y-%m-%d')
        next_day = date_obj + timedelta(days=1)
        query = query.filter(AuditLog.created_at >= date_obj, AuditLog.created_at < next_day)
    
    # ترتيب النتائج
    query = query.order_by(AuditLog.created_at.desc())
    
    # تقسيم النتائج
    logs_paginated = query.paginate(page=page, per_page=per_page)
    
    return render_template(
        'admin/logs.html', 
        logs=logs_paginated.items,
        pagination=logs_paginated,
        action=action,
        entity_type=entity_type,
        user_filter=user_filter,
        date_filter=date_filter
    )



@admin_bp.route('/edit_category', methods=['POST'])
@admin_required
def edit_category(current_user):
    """تعديل تصنيف"""
    category_id = request.form.get('id')
    name = request.form.get('name')
    slug = request.form.get('slug')
    description = request.form.get('description')
    parent_id = request.form.get('parent_id')
    
    if not name or not slug or not category_id:
        flash('جميع الحقول المطلوبة يجب ملؤها', 'danger')
        return redirect(url_for('admin.categories'))
    
    from .models import Category
    category = Category.query.get_or_404(category_id)
    
    # التحقق من عدم وجود تصنيف آخر بنفس الـ slug
    existing = Category.query.filter(Category.slug == slug, Category.id != int(category_id)).first()
    if existing:
        flash('هذا الاسم التقني موجود بالفعل', 'danger')
        return redirect(url_for('admin.categories'))
    
    # تحديث بيانات التصنيف
    category.name = name
    category.slug = slug
    category.description = description
    category.parent_id = parent_id if parent_id else None
    
    db.session.commit()
    
    flash('تم تعديل التصنيف بنجاح', 'success')
    return redirect(url_for('admin.categories'))

@admin_bp.route('/delete_category', methods=['POST'])
@admin_required
def delete_category(current_user):
    """حذف تصنيف"""
    category_id = request.form.get('id')
    
    if not category_id:
        flash('معرف التصنيف مطلوب', 'danger')
        return redirect(url_for('admin.categories'))
    
    from .models import Category, Product
    category = Category.query.get_or_404(category_id)
    
    # حذف المنتجات المرتبطة بالتصنيف أو نقلها إلى تصنيف آخر
    products = Product.query.filter_by(category_id=category.id).all()
    for product in products:
        db.session.delete(product)
    
    # حذف التصنيفات الفرعية
    subcategories = Category.query.filter_by(parent_id=category.id).all()
    for subcategory in subcategories:
        # حذف المنتجات في التصنيفات الفرعية
        sub_products = Product.query.filter_by(category_id=subcategory.id).all()
        for product in sub_products:
            db.session.delete(product)
        db.session.delete(subcategory)
    
    # حذف التصنيف الرئيسي
    db.session.delete(category)
    db.session.commit()
    
    flash('تم حذف التصنيف بنجاح', 'success')
    return redirect(url_for('admin.categories'))


@admin_bp.route('/reports')
@admin_required
def reports(current_user):
    """إدارة البلاغات"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    status = request.args.get('status')
    type = request.args.get('type')
    search_query = request.args.get('search')
    
    from .models import Report
    query = Report.query
    
    # تطبيق الفلاتر
    if status:
        query = query.filter_by(status=status)
    
    if type == 'product':
        query = query.filter(Report.product_id.isnot(None))
    elif type == 'user':
        query = query.filter(Report.reported_user_id.isnot(None))
    
    if search_query:
        from sqlalchemy import or_
        from .models import User, Product
        query = (query.join(User, User.id == Report.reporter_id)
                     .outerjoin(Product, Product.id == Report.product_id)
                     .filter(or_(
                         User.name.like(f'%{search_query}%'),
                         Report.reason.like(f'%{search_query}%'),
                         Product.title.like(f'%{search_query}%')
                     )))
    
    # ترتيب النتائج
    query = query.order_by(Report.created_at.desc())
    
    # تقسيم النتائج
    reports_paginated = query.paginate(page=page, per_page=per_page)
    
    return render_template(
        'admin/reports.html',
        reports=reports_paginated.items,
        pagination=reports_paginated,
        status=status,
        type=type,
        search_query=search_query
    )


# Add a detailed report view
@admin_bp.route('/reports/<int:report_id>')
@admin_required
def report_details(current_user, report_id):
    """عرض تفاصيل البلاغ"""
    from .models import Report
    report = Report.query.get_or_404(report_id)
    
    return render_template('admin/report_details.html', report=report)




@main_bp.before_app_request
def before_request():
    """التحقق من المستخدم الحالي قبل كل طلب"""
    g.current_user = None
    

    token = None
    if 'auth_token' in session:
        token = session['auth_token']
    elif 'Authorization' in request.headers:
        auth_header = request.headers['Authorization']
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]

    if token:
        try:
            from .models import User
            data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
            user = User.query.get(data['user_id'])
            
            if user and not user.is_banned:
                g.current_user = user
                return
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


@auth_bp.route('/facebook_login')
def facebook_login():
    """تسجيل الدخول عبر فيسبوك - غير مفعل حالياً"""
    flash('تسجيل الدخول عبر فيسبوك غير متاح حالياً', 'warning')
    return redirect(url_for('auth.login'))

@auth_bp.route('/google_login')
def google_login():
    """تسجيل الدخول عبر جوجل - غير مفعل حالياً"""
    flash('تسجيل الدخول عبر جوجل غير متاح حالياً', 'warning')
    return redirect(url_for('auth.login'))

@auth_bp.route('/twitter_login')
def twitter_login():
    """تسجيل الدخول عبر تويتر - غير مفعل حالياً"""
    flash('تسجيل الدخول عبر تويتر غير متاح حالياً', 'warning')
    return redirect(url_for('auth.login'))


def register_blueprints(app):
    app.register_blueprint(main_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(messages_bp)
    app.register_blueprint(admin_bp)