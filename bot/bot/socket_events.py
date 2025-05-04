from flask import request, session, g
from flask_socketio import emit, join_room, leave_room
from . import socketio, db
from .models import User, Message
from datetime import datetime

@socketio.on('connect')
def handle_connect():
    """Manejar conexión del cliente"""
    if 'auth_token' in session:
        token = session['auth_token']
        
        try:
            import jwt
            from flask import current_app
            data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
            user_id = data['user_id']
            
        
            join_room(f"user_{user_id}")

            user = User.query.get(user_id)
            if user:
                user.is_online = True
                db.session.commit()
      
                emit('user_status', {'user_id': user_id, 'is_online': True}, broadcast=True)
                
                return {"status": "connected", "user_id": user_id}
        except Exception as e:
            current_app.logger.error(f"Error en conexión de socket: {str(e)}")
    
    return {"status": "error", "message": "Authentication required"}

@socketio.on('disconnect')
def handle_disconnect():
    """Manejar desconexión del cliente"""
    if 'auth_token' in session:
        token = session['auth_token']
        
        try:
            import jwt
            from flask import current_app
            data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
            user_id = data['user_id']
   
            leave_room(f"user_{user_id}")

            user = User.query.get(user_id)
            if user:
                user.is_online = False
                db.session.commit()
                
           
                emit('user_status', {'user_id': user_id, 'is_online': False}, broadcast=True)
        except Exception as e:
            current_app.logger.error(f"Error en desconexión de socket: {str(e)}")

@socketio.on('send_message')
def handle_send_message(data):
    """Manejar envío de mensajes"""
    if 'auth_token' in session:
        token = session['auth_token']
        
        try:
            import jwt
            from flask import current_app
            token_data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
            sender_id = token_data['user_id']
            
            receiver_id = data.get('receiver_id')
            content = data.get('content')
            product_id = data.get('product_id')
            
            if not receiver_id or not content:
                return {"status": "error", "message": "Faltan campos obligatorios"}
            
   
            message = Message(
                sender_id=sender_id,
                receiver_id=receiver_id,
                content=content,
                product_id=product_id if product_id else None
            )
            
            db.session.add(message)
            db.session.commit()
            
     
            formatted_message = {
                'id': message.id,
                'sender_id': message.sender_id,
                'receiver_id': message.receiver_id,
                'content': message.content,
                'product_id': message.product_id,
                'is_read': message.is_read,
                'created_at': message.created_at.isoformat(),
                'sender_name': message.sender.name,
                'sender_image': message.sender.profile_image
            }
            
          
            emit('receive_message', formatted_message, room=f"user_{sender_id}")
            emit('receive_message', formatted_message, room=f"user_{receiver_id}")
            
            return {"status": "success", "message": formatted_message}
        except Exception as e:
            from flask import current_app
            current_app.logger.error(f"Error al enviar mensaje: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    return {"status": "error", "message": "Se requiere autenticación"}

@socketio.on('mark_as_read')
def handle_mark_as_read(data):
    """Marcar mensajes como leídos"""
    if 'auth_token' in session:
        token = session['auth_token']
        
        try:
            import jwt
            from flask import current_app
            token_data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
            user_id = token_data['user_id']
            
            message_ids = data.get('message_ids', [])
            
            if not message_ids:
                return {"status": "error", "message": "No se proporcionaron IDs de mensajes"}
            
        
            messages = Message.query.filter(
                Message.id.in_(message_ids),
                Message.receiver_id == user_id,
                Message.is_read == False
            ).all()
            
            for message in messages:
                message.is_read = True
            
            db.session.commit()

            for message in messages:
                emit('message_read', {'message_id': message.id}, room=f"user_{message.sender_id}")
            
            return {"status": "success", "count": len(messages)}
        except Exception as e:
            from flask import current_app
            current_app.logger.error(f"Error al marcar mensajes como leídos: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    return {"status": "error", "message": "Se requiere autenticación"}