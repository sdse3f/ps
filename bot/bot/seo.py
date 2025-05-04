# bot/bot/seo.py
from flask import request, url_for
from datetime import datetime

def generate_sitemap(app, routes_to_include):
    """توليد ملف sitemap.xml ديناميكيًا"""
    
    base_url = request.host_url.rstrip('/')
    now = datetime.utcnow().strftime('%Y-%m-%d')
    
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    
    # الصفحات الثابتة
    for route in routes_to_include:
        xml += '  <url>\n'
        xml += f'    <loc>{base_url}{route}</loc>\n'
        xml += f'    <lastmod>{now}</lastmod>\n'
        xml += '    <changefreq>weekly</changefreq>\n'
        xml += '  </url>\n'
    
    # إضافة صفحات المنتجات بشكل ديناميكي
    from .models import Product
    products = Product.query.filter_by(is_active=True, is_sold=False).all()
    
    for product in products:
        product_url = url_for('products.view', product_id=product.id, _external=True)
        update_date = product.updated_at.strftime('%Y-%m-%d')
        
        xml += '  <url>\n'
        xml += f'    <loc>{product_url}</loc>\n'
        xml += f'    <lastmod>{update_date}</lastmod>\n'
        xml += '    <changefreq>daily</changefreq>\n'
        xml += '  </url>\n'
    
    # إضافة صفحات التصنيفات
    from .models import Category
    categories = Category.query.all()
    
    for category in categories:
        category_url = url_for('products.search', category_id=category.id, _external=True)
        
        xml += '  <url>\n'
        xml += f'    <loc>{category_url}</loc>\n'
        xml += f'    <lastmod>{now}</lastmod>\n'
        xml += '    <changefreq>weekly</changefreq>\n'
        xml += '  </url>\n'
    
    xml += '</urlset>'
    return xml