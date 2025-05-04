from datetime import datetime
from sqlalchemy.sql import func
from flask import current_app
from werkzeug.security import generate_password_hash, check_password_hash
from . import db

favorites = db.Table('favorites',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('product_id', db.Integer, db.ForeignKey('product.id'), primary_key=True),
    db.Column('created_at', db.DateTime, default=datetime.utcnow)
)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    profile_image = db.Column(db.String(500), nullable=True)
    profile_image_url = db.Column(db.String(500), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    location = db.Column(db.String(100), nullable=True)
    is_verified = db.Column(db.Boolean, default=False)
    verification_code = db.Column(db.String(6), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    is_banned = db.Column(db.Boolean, default=False)
    is_online = db.Column(db.Boolean, default=False)
    new_email_pending = db.Column(db.String(150), nullable=True)

    @property
    def is_authenticated(self):
        return True
        
    # تصحيح العلاقات بإضافة foreign_keys
    products = db.relationship('Product', 
                              foreign_keys='Product.seller_id', 
                              backref='seller', 
                              lazy=True)
                              
    purchased_products = db.relationship('Product',
                                        foreign_keys='Product.buyer_id',
                                        backref='buyer', 
                                        lazy=True)
                                        
    reviews_received = db.relationship('UserReview', 
                                      foreign_keys='UserReview.reviewed_user_id', 
                                      backref='reviewed_user', 
                                      lazy=True)
                                      
    reviews_given = db.relationship('UserReview', 
                                   foreign_keys='UserReview.reviewer_id', 
                                   backref='reviewer', 
                                   lazy=True)
                                   
    sent_messages = db.relationship('Message', 
                                   foreign_keys='Message.sender_id', 
                                   backref='sender', 
                                   lazy=True)
                                   
    received_messages = db.relationship('Message', 
                                      foreign_keys='Message.receiver_id', 
                                      backref='receiver', 
                                      lazy=True)
                                      
    reports_filed = db.relationship('Report', 
                                   foreign_keys='Report.reporter_id', 
                                   backref='reporter', 
                                   lazy=True)
                                   
    reports_received = db.relationship('Report', 
                                      foreign_keys='Report.reported_user_id', 
                                      backref='reported_user', 
                                      lazy=True)
                                      
    favorites_products = db.relationship('Product', 
                                        secondary=favorites, 
                                        lazy='subquery', 
                                        backref=db.backref('favorited_by', lazy=True))
    
    audit_logs = db.relationship('AuditLog', backref='user', lazy=True)
    
    def calculate_rating(self):
        reviews = UserReview.query.filter_by(reviewed_user_id=self.id).all()
        if not reviews:
            return 0
        total = sum(review.rating for review in reviews)
        return round((total / len(reviews)) * 20, 1)


class UserReview(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reviewed_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=True)
    product = db.relationship('Product', backref='reviews')

    def __init__(self, **kwargs):
        super(UserReview, self).__init__(**kwargs)
        if self.rating < 1 or self.rating > 5:
            raise ValueError("يجب أن يكون التقييم بين 1 و 5")


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    
    subcategories = db.relationship('Category', backref=db.backref('parent', remote_side=[id]), lazy=True)
    products = db.relationship('Product', backref='category_rel', lazy=True)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='SYP')
    condition = db.Column(db.String(20), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    views_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)
    is_sold = db.Column(db.Boolean, default=False)
    buyer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    images = db.relationship('ProductImage', backref='product', lazy=True, cascade="all, delete-orphan")
    attributes = db.relationship('ProductAttribute', backref='product', lazy=True, cascade="all, delete-orphan")
    messages = db.relationship('Message', backref='product', lazy=True)
    reports = db.relationship('Report', backref='product', lazy=True)


class ProductImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cloudflare_id = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    is_primary = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ProductAttribute(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    value = db.Column(db.String(500), nullable=False)


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=True)
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reported_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=True)
    reason = db.Column(db.String(200), nullable=False)
    details = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(50), nullable=False)
    entity_id = db.Column(db.Integer, nullable=False)
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


def get_profile_image_url(self):
    from flask import current_app
    from .image_service import ImageService
    
    default_image = current_app.config['IMAGES_CONFIG']['default_avatar']
    
    if self.profile_image_url:
        return self.profile_image_url
    
    if not self.profile_image:
        return default_image
        
    return ImageService.get_image_url(self.profile_image, default_image, 'users')


def update_profile_image(self, image_data):
    from .image_service import ImageService
    from . import db
    
    try:
        result = ImageService.upload_image(image_data, 'users')
        
        if result:
            if self.profile_image:
                ImageService.delete_image(self.profile_image, 'users')
            
            self.profile_image = result['id']
            self.profile_image_url = result['url']
            
            db.session.commit()
            return True
            
        return False
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"خطأ في تحديث الصورة الشخصية: {str(e)}")
        return False


def get_main_image_url(self):
    from flask import current_app
    from .image_service import ImageService
    
    default_image = current_app.config['IMAGES_CONFIG']['default_product']

    primary_image = None
    if self.images:
        for image in self.images:
            if image.is_primary:
                primary_image = image
                break
                
        if not primary_image and self.images:
            primary_image = self.images[0]
    
    if primary_image:
        return ImageService.get_image_url(primary_image.cloudflare_id, default_image, 'products')
    
    return default_image


def add_product_image(self, image_data, is_primary=False):
    from .image_service import ImageService
    from .models import ProductImage
    from . import db
    
    try:
        result = ImageService.upload_image(image_data, 'products')
        
        if result:
            if is_primary and self.images:
                for image in self.images:
                    image.is_primary = False
            product_image = ProductImage(
                cloudflare_id=result['id'],
                url=result['url'],
                product_id=self.id,
                is_primary=is_primary
            )
            
            db.session.add(product_image)
            db.session.commit()
            
            return product_image
            
        return None
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"خطأ في إضافة صورة للمنتج: {str(e)}")
        return None


def delete_product_image(self, image_id):
    from .image_service import ImageService
    from . import db
    
    try:
        image = None
        for img in self.images:
            if img.id == image_id:
                image = img
                break
                
        if not image:
            return False
        ImageService.delete_image(image.cloudflare_id, 'products')
        
        db.session.delete(image)
    
        if image.is_primary and len(self.images) > 1:
            for img in self.images:
                if img.id != image_id:
                    img.is_primary = True
                    break
        
        db.session.commit()
        return True
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"خطأ في حذف صورة المنتج: {str(e)}")
        return False