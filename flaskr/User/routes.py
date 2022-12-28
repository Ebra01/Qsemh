from flask import Blueprint, jsonify, request, abort
from sqlalchemy import or_, func, desc, not_
from flask_login import current_user, logout_user
from flaskr import login_manager, SECRET_KEY, USER, PROVIDER, ADMIN, SUPERADMIN
from flaskr.Models.models import Coupon, Users, Tokens, Applications, Offers, Transfers, Association
from flaskr.utils import sendNotifications
from .utils import (validate_current_user, addUserToDB,
                    upload_images, reset_user_passw, validate_password)

# Create History
from flaskr.History.routes import create_history

# For JWT Encoding & Decoding
import jwt
from time import time
from datetime import datetime

# For User Update
import json
import re

# For Authentication
from flaskr.Auth.auth import requires_auth

# Authenticate Paypal Payment
from .Paypal import GetOrder

users = Blueprint('users', __name__)


@login_manager.user_loader
def load_user(user_id):
    return Users.query.get(user_id)


# User's Coupons Management
@users.route('/api/user/coupons')
def get_user_coupons():
    if not current_user.is_authenticated:
        abort(400, {
            'msg': 'You Must Be Logged-In',
            'code': 'LOGIN_REQUIRED'
        })

    coupons = [c.display() for c in
               Coupon.query.order_by(Coupon.coupon_status).filter_by(user_id=current_user.id).all()]

    if not coupons:
        abort(404, {
            'msg': f'No Coupons Found For User #{current_user.id}',
            'code': 'NO_COUPONS'
        })

    return jsonify({
        'coupons': coupons,
        'success': True
    })


# Check if User is Disabled
@users.route('/api/user/<int:user_id>/is_active')
def check_user_(user_id):
    user = Users.query.get(user_id)

    if not user:
        abort(400, {
            'msg': f'No User Match ID #{user_id}',
            'code': 'NO_MATCH_ID'
        })

    if user.disabled:
        abort(400, {
            'msg': 'This Account is Disabled',
            'code': 'DISABLED'
        })

    return jsonify({
        'success': True
    })


@users.route('/api/user/coupons/gift', methods=['POST'])
@requires_auth(access_level='customer')
def gift_coupons(_payload):
    if not current_user.is_authenticated:
        abort(400, {
            'msg': 'You Must Be Logged-In',
            'code': 'LOGIN_REQUIRED'
        })

    req = request.get_json()

    if not req:
        abort(400, {
            'msg': 'You Must Provide A Valid Request',
            'code': 'INVALID_REQUEST'
        })

    coupon_id = req.get('coupon_id')
    target_user_id = req.get('to_user_id')

    if not coupon_id or not target_user_id:
        abort(400, {
            'msg': 'You Must Provide A Coupon ID & Target User ID',
            'code': 'MISSING_VALUES'
        })

    coupon = Coupon.query.get(coupon_id)

    if not coupon:
        # Create A History
        create_history(
            entity_type="Users",
            entity=current_user,
            record_state="failed",
            record_type="send_coupon_attempt",
            error_key="SEND_COUPON_NO_COUPON",
            params={
                "sender": current_user.username,
                "coupon_code": coupon.coupon_code,
            }
        )
        abort(400, {
            'msg': f'No Coupon Match ID #{coupon_id}',
            'code': 'NO_MATCH_COUPON'
        })

    if coupon.user_id != current_user.id:
        # Create A History
        create_history(
            entity_type="Users",
            entity=current_user,
            record_state="failed",
            record_type="send_coupon_attempt",
            error_key="SEND_COUPON_NOT_YOURS",
            params={
                "sender": current_user.username,
                "coupon_code": coupon.coupon_code,
            }
        )
        abort(400, {
            'msg': 'This Coupon Is Not Yours To Gift',
            'code': 'NOT_YOURS'
        })

    if coupon.coupon_status != 'available':
        # Create A History
        create_history(
            entity_type="Users",
            entity=current_user,
            record_state="failed",
            record_type="send_coupon_attempt",
            error_key="SEND_COUPON_NOT_AVAILABLE",
            params={
                "sender": current_user.username,
                "coupon_code": coupon.coupon_code,
            }
        )
        abort(400, {
            'msg': 'You Can\'t Gift This Coupon',
            'code': 'INVALID_STATUS'
        })

    target_user = Users.query.get(target_user_id)
    if not target_user:
        # Create A History
        create_history(
            entity_type="Users",
            entity=current_user,
            record_state="failed",
            record_type="send_coupon_attempt",
            error_key="SEND_COUPON_NO_RECEIVER",
            params={
                "sender": current_user.username,
                "coupon_code": coupon.coupon_code,
            }
        )
        abort(400, {
            'msg': f'No User Match ID #{target_user_id}',
            'code': 'NO_MATCH_USER'
        })

    try:
        coupon.user_id = target_user_id
        old_qr_code = coupon.qr_code
        coupon.qr_code = coupon.generate_qr_code()

        coupon.update()

        # Create two Histories (Sender/Receiver)
        # Sender
        create_history(
            entity_type="Users",
            entity=current_user,
            record_state="succeed",
            record_type="send_coupon",
            params={
                "sender": current_user.username,
                "receiver": target_user.username,
                "coupon_code": coupon.coupon_code,
                "old_qr_code": old_qr_code,
                "new_qr_code": coupon.qr_code
            }
        )
        # Receiver
        create_history(
            entity_type="Users",
            entity=target_user,
            record_state="succeed",
            record_type="receive_coupon",
            params={
                "sender": current_user.username,
                "receiver": target_user.username,
                "coupon_code": coupon.coupon_code,
                "old_qr_code": old_qr_code,
                "new_qr_code": coupon.qr_code,
                "price": coupon.group.coupon_price
            }
        )
        # Coupon
        create_history(
            entity_type="Coupons",
            entity=coupon,
            record_state="succeed",
            record_type="gift_coupon",
            params={
                "sender": current_user.username,
                "receiver": target_user.username,
                "old_qr_code": old_qr_code,
            }
        )
    except Exception as e:
        print(e)
        # Create A History
        create_history(
            entity_type="Users",
            entity=current_user,
            record_state="failed",
            record_type="send_coupon_attempt",
            error_key="SEND_COUPON_SERVER",
            params={
                "sender": current_user.username,
                "coupon_code": coupon.coupon_code,
            }
        )
        abort(500, e)

    return jsonify({
        'success': True
    })


@users.route('/api/user/coupons/<int:coupon_id>/sell', methods=['POST'])
@requires_auth(access_level='customer')
def sell_coupons(_payload, coupon_id):
    coupon = Coupon.query.get(coupon_id)

    if not coupon:
        abort(400, {
            'msg': f'No Coupon Match ID #{coupon_id}',
            'code': 'NO_MATCH_COUPON'
        })

    if coupon.coupon_status != 'available':
        # Create A History
        create_history(
            entity_type="Users",
            entity=current_user,
            record_state="failed",
            record_type="sell_coupon_attempt",
            error_key="SELL_COUPON_NOT_AVAILABE",
            params={
                "seller": current_user.username,
                "coupon_code": coupon.coupon_code,
                "coupon_price": coupon.group.coupon_price
            }
        )
        abort(400, {
            'msg': 'Coupon is Not Valid For Selling',
            'code': 'INVALID_STATUS'
        })

    if coupon.user_id != current_user.id:
        # Create A History
        create_history(
            entity_type="Users",
            entity=current_user,
            record_state="failed",
            record_type="sell_coupon_attempt",
            error_key="SELL_COUPON_NOT_YOURS",
            params={
                "seller": current_user.username,
                "coupon_code": coupon.coupon_code,
                "coupon_price": coupon.group.coupon_price
            }
        )
        abort(400, {
            'msg': 'This Coupon Is Not Yours',
            'code': 'NOT_YOURS'
        })

    req = request.get_json()

    if not req:
        abort(400, {
            'msg': 'Request Must Be Valid',
            'code': 'INVALID_REQUEST'
        })

    price = req.get('price')

    if not price:
        abort(400, {
            'msg': 'All Important Values Must Be Provided',
            'code': 'MISSING_VALUES'
        })

    if 0 > float(price) or float(price) > float(coupon.group.coupon_price):
        # Create A History
        create_history(
            entity_type="Users",
            entity=current_user,
            record_state="failed",
            record_type="sell_coupon",
            error_key="SELL_COUPON_INVALID_PRICE",
            params={
                "seller": current_user.username,
                "coupon_code": coupon.coupon_code,
                "coupon_price": coupon.group.coupon_price,
                "offer_price": price
            }
        )
        abort(400, {
            'msg': 'Price Is not Valid',
            'code': 'INVALID_PRICE'
        })

    try:
        # Create A New Offer
        new_offer = Offers(
            coupon_id=coupon_id,
            price=price,
            seller_id=current_user.id
        )

        # Update Coupon Status to OnHold
        coupon.coupon_status = 'onhold'
        coupon.update()

        new_offer.insert()

        # Create A History (User)
        create_history(
            entity_type="Users",
            entity=current_user,
            record_state="succeed",
            record_type="sell_coupon",
            params={
                "seller": current_user.username,
                "coupon_code": coupon.coupon_code,
                "coupon_price": coupon.group.coupon_price,
                "offer_price": price
            }
        )

        # Create A History (Coupon)
        create_history(
            entity_type="Coupons",
            entity=coupon,
            record_state="succeed",
            record_type="offer_coupon",
            params={
                "seller": current_user.username,
                "coupon_code": coupon.coupon_code,
                "coupon_price": coupon.group.coupon_price,
                "offer_price": price
            }
        )
    except Exception as e:
        # Create A History
        create_history(
            entity_type="Users",
            entity=current_user,
            record_state="failed",
            record_type="sell_coupon",
            error_key="SELL_COUPON_SERVER",
            params={
                "seller": current_user.username,
                "coupon_code": coupon.coupon_code,
                "coupon_price": coupon.group.coupon_price,
                "offer_price": price
            }
        )
        abort(400, e)

    return jsonify({
        'success': True
    })


@users.route('/api/offers')
def get_offers():
    offers = [o.buyerDisplay() for o in Offers.query.order_by(desc(Offers.id)).filter(
        not_(Offers.completed)).all()
              if Coupon.query.get(o.coupon_id).coupon_status not
              in ['expired', 'canceled', 'used'] and o.validated]

    return jsonify({
        'offers': offers,
        'success': True
    })


@users.route('/api/user/coupon/<int:offer_id>/buy', methods=['GET'])
@requires_auth(access_level='customer')
def buy_coupons(_payload, offer_id):
    if not current_user.is_authenticated:
        abort(400, {
            'msg': 'User is Not Logged In',
            'code': 'NOT_LOGGED_IN'
        })

    if current_user.disabled:
        abort(400, {
            'msg': 'Your Account is Disabled',
            'code': 'DISABLED'
        })

    offer = Offers.query.get(offer_id)

    if not offer:
        abort(400, {
            'msg': f'No Offer Match ID #{offer_id}',
            'code': 'NO_MATCH_ID'
        })

    if offer.completed:
        abort(400, {
            'msg': 'Offer Is Already Sold',
            'code': 'SOLD_OFFER'
        })

    if offer.seller_id == current_user.id:
        abort(400, {
            'msg': 'You Can\'t Buy Your Own Offer',
            'code': 'ITS_YOUR_OFFER'
        })

    coupon = Coupon.query.get(offer.coupon_id)

    if not coupon:
        abort(400, {
            'msg': f'No Coupon Attached With Given Offer',
            'code': 'NO_COUPON_FOUND'
        })

    if coupon.group.expire_date < datetime.now():
        # Create A History
        create_history(
            entity_type="Users",
            entity=current_user,
            record_state="failed",
            record_type="buy_coupon_attempt",
            error_key="BUY_COUPON_EXPIRED",
            params={
                "buyer": current_user.username,
                "seller": Users.query.get(offer.seller_id).username,
                "coupon_code": coupon.coupon_code
            }
        )
        abort(400, {
            'msg': 'Coupon is Expired',
            'code': 'EXPIRED'
        })

    if current_user.balance < offer.price:
        # Create A History
        create_history(
            entity_type="Users",
            entity=current_user,
            record_state="failed",
            record_type="buy_coupon_attempt",
            error_key="BUY_COUPON_INVALID_BALANCE",
            params={
                "buyer": current_user.username,
                "seller": Users.query.get(offer.seller_id).username,
                "coupon_code": coupon.coupon_code
            }
        )
        abort(400, {
            'msg': 'Not Enough Credit in Your Account',
            'code': 'LOWER_CREDIT'
        })

    try:
        # Update Offer Status
        offer.completed = True
        offer.end_date = datetime.now()
        offer.buyer_id = current_user.id

        offer.update()

        # Update Coupon Status
        coupon.user_id = current_user.id
        coupon.coupon_status = 'available'
        old_qr_code = coupon.qr_code
        coupon.qr_code = coupon.generate_qr_code()

        coupon.update()

        # Take Price From User's Balance
        buyer = Users.query.get(offer.buyer_id)
        seller = Users.query.get(offer.seller_id)
        admin = Users.query.filter(Users.guid == SUPERADMIN).first()

        # Take One Percent From Original Price.
        admin_profit = offer.price * 0.01
        seller_profit = offer.price - admin_profit

        # Add 99% of Original Price To Seller Balance.
        seller.balance += seller_profit
        # Add 1% of Original Price To Admin Balance.
        admin.balance += admin_profit
        # Subtract Original Price From Buyer Balance.
        buyer.balance -= offer.price

        # Update Users
        seller.update()
        admin.update()
        buyer.update()

        # Create two Histories (Seller/Buyer/Coupon)
        # Seller
        create_history(
            entity_type="Users",
            entity=seller,
            record_state="succeed",
            record_type="buy_coupon_seller",
            params={
                "seller": seller.username,
                "seller_balance": seller.balance,
                "buyer": buyer.username,
                "buyer_balance": buyer.balance,
                "coupon_code": coupon.coupon_code,
                "offer_price": offer.price,
                "old_qr_code": old_qr_code,
                "new_qr_code": coupon.qr_code,
                "money_gain": seller_profit
            }
        )
        # Buyer
        create_history(
            entity_type="Users",
            entity=buyer,
            record_state="succeed",
            record_type="buy_coupon_buyer",
            params={
                "seller": seller.username,
                "seller_balance": seller.balance,
                "buyer": buyer.username,
                "buyer_balance": buyer.balance,
                "coupon_code": coupon.coupon_code,
                "offer_price": offer.price,
                "old_qr_code": old_qr_code,
                "new_qr_code": coupon.qr_code,
                "money_lost": offer.price
            }
        )
        # Coupon
        create_history(
            entity_type="Coupons",
            entity=coupon,
            record_state="succeed",
            record_type="buy_coupon",
            params={
                "seller": seller.username,
                "buyer": buyer.username,
                "offer_price": offer.price,
                "old_qr_code": old_qr_code,
            }
        )

    except Exception as e:
        # Create A History
        create_history(
            entity_type="Users",
            entity=current_user,
            record_state="failed",
            record_type="buy_coupon_attempt",
            error_key="BUY_COUPON_SERVER",
            params={
                "buyer": current_user.username,
                "seller": Users.query.get(offer.seller_id).username,
                "coupon_code": coupon.coupon_code
            }
        )
        abort(500, e)

    offers = [o.buyerDisplay() for o in Offers.query.order_by(desc(Offers.id)).filter(
        not_(Offers.completed)).all()]

    return jsonify({
        'offers': offers,
        'success': True
    })


@users.route('/api/user/offers/<int:coupon_id>', methods=['DELETE'])
@requires_auth(access_level='customer')
def cancel_offer(_payload, coupon_id):
    offer = Offers.query.filter(not_(Offers.completed)).filter_by(
        coupon_id=coupon_id).first()

    if not offer:
        abort(404, {
            'msg': f'No Offer Match ID #{coupon_id}',
            'code': 'NO_MATCH_ID'
        })

    coupon = Coupon.query.get(coupon_id)

    if offer.completed:
        # Create A History
        create_history(
            entity_type="Users",
            entity=current_user,
            record_state="failed",
            record_type="cancel_offer",
            error_key="CANCEL_OFFER_COMPLETED",
            params={
                "coupon_code": coupon.coupon_code
            }
        )
        abort(400, {
            'msg': 'Offer is Finished Already',
            'code': 'FINISHED_OFFER'
        })

    if not coupon:
        abort(400, {
            'msg': 'Offer Coupon Doesn\'t Exist',
            'code': 'NO_COUPON'
        })

    try:
        # Return The Coupon To The Owner, And Update Its Status
        coupon.coupon_status = 'available'
        coupon.user_id = offer.seller_id
        coupon.update()

        # Delete Offer.
        offer.delete()

        # Create A History
        create_history(
            entity_type="Users",
            entity=current_user,
            record_state="succeed",
            record_type="cancel_offer",
            params={
                "coupon_code": coupon.coupon_code
            }
        )
    except Exception as e:
        # Create A History
        create_history(
            entity_type="Users",
            entity=current_user,
            record_state="failed",
            record_type="cancel_offer",
            error_key="CANCEL_OFFER_SERVER",
            params={
                "coupon_code": coupon.coupon_code
            }
        )
        abort(500, e)

    my_coupons = [c.display() for c in Coupon.query.filter_by(user_id=current_user.id).all()]

    return jsonify({
        'coupons': my_coupons,
        'success': True
    })


# Set Validation Based On Group ID & User (Remove Access Token Validation)
@users.route('/api/user/coupon/validate_provider', methods=['POST'])
@requires_auth(access_level='associate')
def validate_provider(_payload):
    if not current_user.is_authenticated:
        abort(400, {
            'msg': 'You Must Log-in First',
            'code': 'LOGIN_REQUIRED'
        })

    req = request.get_json()
    qr_code = req.get('qr_code')

    if not req or not qr_code:
        abort(400, {
            'msg': 'You Must Provide A Valid Request',
            'code': 'QRCODE_REQUIRED'
        })

    coupon = Coupon.query.filter_by(qr_code=qr_code).first()

    if not coupon:
        abort(404, {
            'msg': f'No Coupon Match Code ({qr_code})',
            'code': 'NO_MATCH_COUPON'
        })
    provider_company = coupon.group.company

    if not provider_company:
        abort(400, {
            'msg': 'This Coupon Has No Provider!',
            'code': 'NO_PROVIDER'
        })

    association = Association.query.filter(Association.company == provider_company).first()
    if association:
        if current_user.id != association.head and \
                current_user.association_id != association.id:
            abort(400, {
                'msg': 'Invalid Group Company, You Are Not Authorized',
                'code': 'INVALID_GROUP_COMPANY'
            })
    else:
        if current_user.company != provider_company:
            abort(400, {
                'msg': 'Invalid Group Company, You Are Not Authorized',
                'code': 'INVALID_GROUP_COMPANY'
            })

    return jsonify({
        'coupon': coupon.display(),
        'group': coupon.group.display(),
        'success': True
    })


@users.route('/api/user/coupon/redeem', methods=['POST'])
@requires_auth(access_level='associate')
def redeem_coupon(_payload):
    if not current_user.is_authenticated:
        abort(400, {
            'msg': 'You Must Log-in First',
            'code': 'LOGIN_REQUIRED'
        })

    req = request.get_json()
    coupon_id = req.get('coupon_id')

    if not req or not coupon_id:
        abort(400, {
            'msg': 'You Must Provide A Valid Request',
            'code': 'COUPON_ID_REQUIRED'
        })

    coupon = Coupon.query.get(coupon_id)

    if not coupon:
        abort(404, {
            'msg': f'No Coupon Match ID ({coupon_id})',
            'code': 'NO_MATCH_COUPON'
        })

    status = coupon.coupon_status

    if status == 'used':
        # Create A History
        create_history(
            entity_type="Coupons",
            entity=coupon,
            record_state="failed",
            record_type="redeem_coupon",
            error_key="REDEEM_COUPON_USED"
        )
        abort(400, {
            'msg': 'You Can\'t Redeem This Coupon.',
            'code': 'USED_COUPON'
        })
    if status == 'onhold':
        # Create A History
        create_history(
            entity_type="Coupons",
            entity=coupon,
            record_state="failed",
            record_type="redeem_coupon",
            error_key="REDEEM_COUPON_ONHOLD"
        )
        abort(400, {
            'msg': 'You Can\'t Redeem This Coupon.',
            'code': 'ONHOLD_COUPON'
        })
    if status == 'expired':
        # Create A History
        create_history(
            entity_type="Coupons",
            entity=coupon,
            record_state="failed",
            record_type="redeem_coupon",
            error_key="REDEEM_COUPON_EXPIRED"
        )
        abort(400, {
            'msg': 'You Can\'t Redeem This Coupon.',
            'code': 'EXPIRED_COUPON'
        })
    if status == 'canceled':
        # Create A History
        create_history(
            entity_type="Coupons",
            entity=coupon,
            record_state="failed",
            record_type="redeem_coupon",
            error_key="REDEEM_COUPON_CANCELED"
        )
        abort(400, {
            'msg': 'You Can\'t Redeem This Coupon.',
            'code': 'CANCELED_COUPON'
        })

    try:
        coupon.coupon_status = 'used'
        coupon.matcher = current_user.id
        coupon.redeem_date = datetime.now()
        coupon.update()

        # Create A History
        create_history(
            entity_type="Coupons",
            entity=coupon,
            record_state="succeed",
            record_type="redeem_coupon",
            params={
                "user_id": coupon.user_id
            }
        )
    except Exception as e:
        # Create A History
        create_history(
            entity_type="Coupons",
            entity=coupon,
            record_state="failed",
            record_type="redeem_coupon",
            error_key="REDEEM_COUPON_SERVER"
        )
        abort(500, e)

    return jsonify({
        'success': True
    })


# Login, Logout & Register Routes

@users.route('/api/login', methods=['POST'])
def login():
    GUID = {
        USER: 'USER',
        PROVIDER: 'PROVIDER',
        ADMIN: 'ADMIN',
        SUPERADMIN: 'SUPERADMIN'
    }

    req = request.get_json()

    if not req:
        abort(400, {
            'msg': 'Please Provide Credentials',
            'code': 'INVALID_REQUEST'
        })

    email = req.get('email')
    password = req.get('password')
    logged = req.get('logged')

    if not email or not password:
        abort(400, {
            'msg': 'You Must Provide A Valid Credentials',
            'code': 'INVALID_REQUEST'
        })

    # Check if there is a user logged-in already
    if current_user.is_authenticated:
        if logged:
            abort(400, {
                'msg': 'You Are Logged-In Already!',
                'code': 'LOGGED_IN'
            })
            # Create History Record
            create_history(
                entity_type="Users",
                entity=current_user,
                record_type="login",
                record_state="failed",
                error_key='LOGGED_IN'
            )
        else:
            logout_user()

    user_jwt = None
    access_level = "USER"
    try:
        # Try to log the user in as current user
        validate_current_user(email=email,
                              passw=password)
        user_jwt = jwt.encode({
            'uid': current_user.uid,
            'guid': current_user.guid,
            'permissions': current_user.permissions,
            'username': current_user.username,
            'email': current_user.email,
            'company': current_user.company,
            'expire': time() + 900
        }, SECRET_KEY, algorithm='HS256').decode('utf-8')
        access_level = GUID.get(current_user.guid)

        # Create History Record
        create_history(
            entity_type="Users",
            entity=current_user,
            record_type="login",
            record_state="succeed"
        )

    except Exception as e:
        print(e)
        abort(500, e)

    return jsonify({
        'user': current_user.display(),
        'jwt': user_jwt,
        'access_level': access_level,
        'profile_img': current_user.profile_img,
        'success': True
    })


@users.route('/api/logout', methods=['GET'])
def logout():
    # Check if Someone is logged-in
    if not current_user.is_authenticated:
        abort(400, {
            'msg': 'You Are Not Logged-In!',
            'code': 'SERVER'
        })

    # Try to logout user from login_manager
    try:
        # Create A History
        create_history(
            entity_type="Users",
            entity=current_user,
            record_state="succeed",
            record_type="logout"
        )
        logout_user()
    except Exception as e:
        print(e)
        # Create A History
        create_history(
            entity_type="Users",
            entity=current_user,
            record_state="failed",
            record_type="logout",
            error_key="LOGOUT_SERVER"
        )
        abort(500, 'Something Went Wrong in Our End!')

    return jsonify({
        'user': 'User Logged out successfully!',
        'success': True
    })


@users.route('/api/register', methods=['POST'])
def register():
    req = request.get_json()

    if not req:
        abort(400, {
            'msg': 'Please Provide an Email and Password',
            'code': 'INVALID_REQUEST'
        })

    logged = req.get('logged')

    # Check if there is a user logged-in already
    if current_user.is_authenticated:
        if logged:
            abort(400, {
                'msg': 'You Are Logged-In Already, Logout to Register a New Account!',
                'code': 'SERVER'
            })
        else:
            logout_user()

    username = req.get('username')
    pre_phone = req.get('pre_phone')
    phone = req.get('phone')
    email = req.get('email')
    password = req.get('password')
    country = req.get('country')

    # Important For Sending Activation Link
    hostname = req.get('hostname')

    if not username or not country or not email or not phone or not password:
        abort(400, {
            'msg': 'You Must Provide All Important Values!',
            'code': 'INVALID_REQUEST'
        })

    username_reg = "^[a-zA-Z0-9_]+$"

    if not re.match(username_reg, username):
        abort(400, {
            'msg': 'Username is Not Valid',
            'code': 'INVALID_USERNAME'
        })

    from_ksa = False
    if pre_phone == '+966':
        from_ksa = True

    body = {
        'username': username,
        'email': email,
        'phone': f'{pre_phone}{phone}',
        'password': password,
        'from_ksa': from_ksa,
        'country': country
    }

    try:
        # Try to add user to Database
        addUserToDB(body)

        # Sending Activation Link
        send_activation(username=username, email=email, phone=f'{pre_phone}{phone}', hostname=hostname)
    except Exception as e:
        print(e)
        abort(500, e)

    return jsonify({
        'user': 'User Was Registered Successfully!',
        'username': username,
        'success': True
    })


# Send Activation Link
@users.route('/api/activation', methods=['POST'])
def send_activation(username=None, email=None, phone=None, hostname=None):
    req = request.get_json()

    if not req and (not email or not hostname):
        abort(400, {
            'msg': 'Invalid Request, No Email Provided',
            'code': 'INVALID_REQUEST'
        })

    email = req.get('email') or email
    hostname = req.get('hostname') or hostname

    user = Users.query.filter(Users.email.ilike(email)).first()

    if not user:
        abort(400, {
            'msg': f'No User With Email ({email}) Registered!',
            'code': 'NO_EMAIL'
        })

    if user.is_active:
        abort(400, {
            'msg': 'User Already Has Been Activated',
            'code': 'ACTIVATED'
        })

    try:
        new_token = Tokens(
            type_="activation",
            email=email,
            phone=phone,
            nums=3,
            expire_date=datetime.now()
        )
        new_token.insert()
        sendNotifications(
            'account_activation',
            params={
                'activation_link': f'{hostname}/activate?token={new_token.token}',
                'email': email,
                'phone': phone,
                'username': username
            }
        )
    except Exception as e:
        print(e)
        abort(500, e)

    return jsonify({
        'success': True
    })


# Reset Password

@users.route('/api/user/<string:user_email>/sendResetToken', methods=['GET'])
def reset_user_password_link(user_email):
    if not user_email:
        abort(400, {
            'msg': 'No Email Provided',
            'code': 'NO_EMAIL'
        })

    user = Users.query.filter(Users.email.ilike(user_email)).first()

    if not user:
        abort(404, {
            'msg': f'No user match given email ({user_email})',
            'code': 'INVALID_EMAIL'
        })

    # Create a new Token & Send Email.
    try:
        new_token = Tokens(
            type_='reset_password',
            expire_duration=1,
            email=user_email,
            expire_date=datetime.now(),
            nums=12
        )

        new_token.insert()

        # Sending Email
        sendNotifications(
            key="reset_password_token",
            params={
                'email': user_email,
                'username': user.username,
                'token': new_token.token,
            }
        )

        # Create A History
        create_history(
            entity_type="Users",
            entity=user,
            record_state="succeed",
            record_type="reset_password_out_request"
        )
    except Exception as e:
        print(e)
        abort(500, e)

    return jsonify({
        'success': True
    })


@users.route('/api/user/resetPassword', methods=['POST'])
def reset_user_password():
    req = request.get_json()

    if not req:
        abort(400, {
            'msg': 'Request is empty',
            'code': 'INVALID_REQUEST'
        })

    email = req.get('email')
    reset_token = req.get('token')
    new_password = req.get('password')

    if not email or not reset_token or not new_password:
        abort(400, {
            'msg': 'Some values are missing',
            'code': 'MISSING_VALUES'
        })

    user = Users.query.filter(Users.email.ilike(email)).first()

    if not user:
        abort(404, {
            'msg': f'No User match given email ({email})',
            'code': 'NO_USER'
        })

    token = Tokens.query.filter(Tokens.token == reset_token).first()

    if not token:
        # Create A History
        create_history(
            entity_type="Users",
            entity=user,
            record_state="failed",
            record_type="reset_password_out",
            error_key="RESET_PASSW_NO_TOKEN"
        )
        abort(400, {
            'msg': 'Provided Token is not valid',
            'code': 'INVALID_TOKEN'
        })

    if token.is_used:
        # Create A History
        create_history(
            entity_type="Users",
            entity=user,
            record_state="failed",
            record_type="reset_password_out",
            error_key="RESET_PASSW_TOKEN_USED"
        )
        abort(400, {
            'msg': 'This Token has been used already',
            'code': 'USED_TOKEN'
        })

    if token.expire < datetime.now():
        # Create A History
        create_history(
            entity_type="Users",
            entity=user,
            record_state="failed",
            record_type="reset_password_out",
            error_key="RESET_PASSW_TOKEN_EXPIRE"
        )
        abort(400, {
            'msg': 'This Token is expired',
            'code': 'EXPIRED_TOKEN'
        })

    try:
        # Reset Password
        reset_user_passw(user, new_password)

        # Update Token State
        token.is_used = True
        token.update()

        # Create A History
        create_history(
            entity_type="Users",
            entity=user,
            record_state="succeed",
            record_type="reset_password_out"
        )
    except Exception as e:
        # Create A History
        create_history(
            entity_type="Users",
            entity=user,
            record_state="failed",
            record_type="reset_password_out",
            error_key="RESET_PASSW_SERVER"
        )
        print(e)
        abort(500, e)

    return jsonify({
        'success': True
    })


@users.route('/api/user/<int:user_id>/resetPassword', methods=['POST'])
def reset_logged_user_password(user_id):
    user = Users.query.get(user_id)

    if not user:
        abort(400, {
            'msg': f'No User match ID #{user_id}',
            'code': 'NO_USER'
        })

    req = request.get_json()

    if not req:
        abort(400, {
            'msg': 'Request is empty',
            'code': 'INVALID_REQUEST'
        })

    old_password = req.get('old_password')
    new_password = req.get('password')

    if not new_password and not old_password:
        abort(400, {
            'msg': 'Some values are missing',
            'code': 'MISSING_VALUES'
        })

    # Validate old Password
    if not validate_password(user, old_password):
        abort(400, {
            'msg': 'Password doesn\'t match Current Password',
            'code': 'WRONG_PASSWORD'
        })

    try:
        # Reset Password
        reset_user_passw(user, new_password)

        # Create A History
        create_history(
            entity_type="Users",
            entity=user,
            record_state="succeed",
            record_type="reset_password_in"
        )
    except Exception as e:
        print(e)
        abort(500, e)

    return jsonify({
        'success': True
    })


# Reset Password


# Activate User
@users.route('/api/activate', methods=['POST'])
def activate():
    req = request.get_json()
    if not req:
        abort(400, {
            'msg': 'Request Must Not Be Empty',
            'code': 'INVALID_REQUEST'
        })

    token = req.get('token')

    if not token:
        abort(400, {
            'msg': 'You Must Provide A Valid Request',
            'code': 'INVALID_REQUEST'
        })

    # Validate Token

    token = Tokens.query.filter_by(token=token).first()
    if not token:
        abort(404, {
            'msg': 'Token is not Valid',
            'code': 'INVALID_TOKEN'
        })

    # Check if token is expired

    if token.expire < datetime.now():
        abort(400, {
            'msg': 'Token is not Valid',
            'code': 'EXPIRED_TOKEN'
        })

    # Check if token is used

    if token.is_used:
        abort(400, {
            'msg': 'Token is not Valid',
            'code': 'USED_TOKEN'
        })

    # Activate User

    user = Users.query.filter(Users.email.ilike(token.email)).first()

    try:
        # Update User
        user.is_active = True
        user.update()

        # Create A History
        create_history(
            entity_type="Users",
            entity=user,
            record_type="activated",
            record_state="succeed",
        )

        # Update Token
        token.token = token.generate_unique_token(nums=64)
        token.is_used = True
        token.update()
    except Exception as e:
        print(e)
        abort(500, e)

    return jsonify({
        'success': True
    })


@users.route('/api/authenticate/customer')
@requires_auth(access_level="customer")
def authenticate_customer_gate(_payload):
    return jsonify({
        'success': True
    })


@users.route('/api/authenticate/associate')
@requires_auth(access_level="associate")
def authenticate_associate_gate(_payload):
    return jsonify({
        'success': True
    })


@users.route('/api/authenticate/provider')
@requires_auth(access_level="provider")
def authenticate_provider_gate(_payload):
    return jsonify({
        'success': True
    })


@users.route('/api/authenticate/admin')
@requires_auth(access_level="admin")
def authenticate_admin_gate(_payload):
    return jsonify({
        'success': True
    })


@users.route('/api/authenticate/superadmin')
@requires_auth(access_level="superadmin")
def authenticate_superadmin_gate(_payload):
    return jsonify({
        'success': True
    })


@users.route('/api/user')
def get_logged_user():
    if not current_user.is_authenticated:
        abort(500, {
            'msg': 'Something Went Wrong',
            'code': 'SERVER'
        })

    return jsonify({
        'user': current_user.display(),
        'success': True
    })


# Blanace

@users.route('/api/user/balance')
def get_user_balance():
    if not current_user.is_authenticated:
        abort(500, {
            'msg': 'Something Went Wrong',
            'code': 'SERVER'
        })

    return jsonify({
        'user_id': current_user.id,
        'balance': current_user.balance,
        'email': current_user.email,
        'success': True
    })


@users.route('/api/user/balance/<int:user_id>', methods=['POST'])
def request_balance(user_id):
    user = Users.query.get(user_id)

    if not user:
        abort(400, {
            'msg': f'No User Match ID #{user_id}',
            'code': 'NO_MATCH_ID'
        })

    if user.disabled:
        abort(400, {
            'msg': 'This Account is Disabled',
            'code': 'DISABLED'
        })

    req = request.get_json()

    if not req:
        abort(400, {
            'msg': 'Request Must Not Be Empty',
            'code': 'INVALID_REQUEST'
        })

    method = req.get('method')
    amount = req.get('amount')
    verified = req.get('verified')

    if not method or not amount or verified is None:
        abort(400, {
            'msg': 'Important Values Are Required',
            'code': 'MISSING_VALUES'
        })

    email = req.get('email')
    fullname = req.get("fullname")
    bank_account = req.get('bank_account')
    order_id = req.get('order_id')

    if not order_id and not bank_account:
        abort(400, {
            'msg': 'Invalid Payment Method, You Can Only Use Paypal, Mada, Or Bank Transfer',
            'code': 'INVALID_METHOD'
        })

    try:
        # if Method is PayPal
        if method == 'paypal':
            # Validate Payment
            validator = GetOrder()

            result = validator.get_order(order_id=order_id)

            if result.status != 'COMPLETED' or result.id != order_id:
                # Create A History
                create_history(
                    entity_type="Users",
                    entity=user,
                    record_state="failed",
                    record_type="paypal_balance_error",
                    error_key="PAYPAL_REQUEST_ERROR",
                    params={
                        "amount": amount,
                        "current_balance": user.balance
                    }
                )
                raise Exception('Payment Error')

            new_transfer = Transfers(
                amount=amount,
                email=user.email,
                phone=user.phone,
                fullname=fullname or user.fullname,
                method=method,
                user_id=user.uid
            )
            new_transfer.verified = True
            new_transfer.insert()

            # Add Balance To User
            old_balance = user.balance
            user.balance += float(amount)
            user.update()

            # Create A History
            create_history(
                entity_type="Users",
                entity=user,
                record_state="succeed",
                record_type="paypal_balance_request",
                params={
                    "amount": amount,
                    "new_balance": user.balance,
                    "current_balance": old_balance
                }
            )

        # if Method is Bank Transfer
        if method == 'bank':

            if not bank_account or not fullname:
                raise Exception("Bank Account & Fullname Required")

            new_transfer = Transfers(
                amount=amount,
                email=email or user.email,
                phone=user.phone,
                bank_account=bank_account,
                fullname=fullname,
                method=method,
                user_id=user.uid
            )
            new_transfer.verified = False
            new_transfer.insert()

            # Create A History
            create_history(
                entity_type="Users",
                entity=user,
                record_state="succeed",
                record_type="bank_balance_request",
                params={
                    "amount": amount,
                    "current_balance": user.balance,
                    "new_balance": user.balance + float(amount)
                }
            )
    except Exception as e:
        print(e)
        abort(500, e)

    return jsonify({
        'success': True
    })


# Search For Users
@users.route('/api/user/search', methods=['POST'])
def search_users():
    if not current_user.is_authenticated:
        abort(400, {
            'msg': 'You Must Log-in First',
            'code': 'LOGIN_REQUIRED'
        })

    req = request.get_json()

    if not req:
        abort(400, {
            'msg': 'You Must Provide A Valid Request',
            'code': 'INVALID_REQUEST'
        })

    searchQuery = req.get('searchQuery').lower()
    searched_users = []
    if searchQuery:
        searched_users = [u.searchDis() for u in Users.query.filter(or_(
            func.lower(Users.username).contains(searchQuery),
            func.lower(Users.email).contains(searchQuery)
        )).filter(Users.is_active).all() if u.username != current_user.username]

    return jsonify({
        'users': searched_users,
        'length': len(searched_users),
        'success': True
    })


@users.route('/api/user/<int:user_id>', methods=['PATCH'])
def update_user(user_id):
    if not current_user.is_authenticated:
        abort(500, {
            'msg': 'Something Went Wrong',
            'code': 'SERVER'
        })

    user = Users.query.get(user_id)

    if not user:
        abort(404, {
            'msg': f'No User Match ID #{user_id}',
            'code': 'NO_MATCH_ID'
        })

    req = request.get_json()

    if not req:
        abort(400, {
            'msg': 'Request Cannot be Empty',
            'code': 'INVALID_REQUEST'
        })

    # Sub-Update : Fullname
    fullname = req.get('fullname')

    # Sub-Update : Username
    username = req.get('username')

    # Sub-Updates : Country & City
    country = req.get('country')
    city = req.get('city')

    # Check if Updates Values Are Not Valid
    if (not fullname) and (not username) and (not country or not city):
        abort(400, {
            'msg': 'One Or More Values Is/Are Not Valid',
            'code': 'MISSING_VALUES'
        })

    # Validate Username
    if username:
        users_usernames = [u.username.lower() for u in Users.query.all() if u.id != current_user.id]
        if username.lower() in users_usernames:
            abort(400, {
                'msg': f'Username {username} already exists',
                'code': 'INVALID_USERNAME'
            })

    # Validate Fullname
    if fullname:
        reg = '[^a-zA-Z\u0600-\u06FF ]+'

        matches = re.findall(reg, fullname)

        if matches:
            abort(400, {
                'msg': f'{fullname} contain invalid characters',
                'code': 'INVALID_NAME'
            })

    # Trying To Update Values
    updated = None
    try:
        if fullname:
            old_fullname = user.fullname
            user.fullname = fullname
            updated = {
                'id': 'fullname',
                'value': fullname
            }

            # Create A History
            create_history(
                entity_type="Users",
                entity=user,
                record_state="succeed",
                record_type="update_user_fullname",
                params={
                    "old_fullname": old_fullname,
                    "new_fullname": fullname
                }
            )

        if username:
            user.username = username
            updated = {
                'id': 'username',
                'value': username
            }

        if country and city:
            old_country = user.country
            old_city = user.city
            user.country = country
            user.city = city
            updated = {
                'country_id': 'country',
                'city_id': 'city',
                'country_value': country,
                'city_value': city
            }

            # Create A History
            create_history(
                entity_type="Users",
                entity=user,
                record_state="succeed",
                record_type="update_user_country_city",
                params={
                    "old_country": old_country,
                    "old_city": old_city,
                    "new_country": user.country,
                    "new_city": user.city
                }
            )

        user.update()
    except Exception as e:
        print(e)
        abort(500, e)

    return jsonify({
        'user': user.display(),
        'updated': json.dumps(updated),
        'success': True
    })


@users.route('/api/user/image/<int:user_id>', methods=['PATCH'])
def update_user_profile_img(user_id):
    if not current_user.is_authenticated:
        abort(500, {
            'msg': 'Something Went Wrong',
            'code': 'SERVER'
        })

    user = Users.query.get(user_id)

    if not user:
        abort(404, {
            'msg': f'No User Match ID #{user_id}',
            'code': 'NO_MATCH_ID'
        })

    req = request.files

    if not req:
        abort(400, {
            'msg': 'You Must Provide A Valid Request',
            'code': 'INVALID_REQUEST'
        })

    profile_img = None
    old_profile_img = user.profile_img
    try:
        image = req.get('profile_img')
        name = upload_images(image, useUsername=True, username=user.username)

        profile_img = name
        user.profile_img = name
        user.update()

        # Delete Old Profile Image (if Exist)
        if old_profile_img:
            from flaskr.Groups.utils import delete_images
            delete_image(old_profile_img)

        # Create A History
        create_history(
            entity_type="Users",
            entity=user,
            record_state="succeed",
            record_type="reset_user_profile_img",
        )

    except Exception as e:
        abort(500, e)

    return jsonify({
        'key': profile_img,
        'success': True,
    })


@users.route('/api/user/send_reset_email_token', methods=['POST'])
def send_reset_email_token():
    if not current_user.is_authenticated:
        abort(500, {
            'msg': 'Something Went Wrong',
            'code': 'SERVER'
        })

    req = request.get_json()
    email = req.get('email')

    if not req or not email:
        abort(400, {
            'msg': 'Request Cannot be Empty',
            'code': 'INVALID_REQUEST'
        })

    users_emails = [u.email for u in Users.query.all()]
    users_emails = [e.lower() for e in users_emails]

    if email in users_emails:
        abort(400, {
            'msg': f'{email} already registered',
            'code': 'INVALID_EMAIL'
        })

    try:
        new_token = Tokens(
            email=email,
            type_='change_email',
            nums=9,
            expire_date=datetime.now(),
            expire_duration=1
        )
        new_token.insert()
        sendNotifications(
            'reset_email_token',
            params={
                'email': email,
                'username': current_user.username,
                'token': new_token.token
            }
        )
    except Exception as e:
        print(e)
        abort(500, {
            'msg': 'Something Went Wrong',
            'code': 'SERVER'
        })

    return jsonify({
        'success': True
    })


@users.route('/api/user/verify_reset_email_token/<int:user_id>', methods=['POST'])
def verify_reset_email_token(user_id):
    if not current_user.is_authenticated:
        abort(500, {
            'msg': 'Something Went Wrong',
            'code': 'SERVER'
        })

    user = Users.query.get(user_id)

    if not user:
        abort(404, {
            'msg': f'No User Match ID #{user_id}',
            'code': 'NO_MATCH_ID'
        })

    old_email = user.email

    req = request.get_json()
    email = req.get('email')
    token = req.get('token')
    if not req or not email or not token:
        abort(400, {
            'msg': 'Request Cannot be Empty',
            'code': 'INVALID_REQUEST'
        })

    # Validate Token Existance
    token = Tokens.query.filter_by(token=token).first()

    if not token:
        # Create A History
        create_history(
            entity_type="Users",
            entity=user,
            record_state="failed",
            record_type="reset_user_email",
            error_key="RESET_EMAIL_NO_TOKEN",
            params={
                "old_email": old_email,
                "new_email": email
            }
        )
        abort(400, {
            'msg': f'"{token}" is InValid!',
            'code': 'INVALID_TOKEN'
        })
    # Validate Email
    if token.email.lower() != email.lower():
        # Create A History
        create_history(
            entity_type="Users",
            entity=user,
            record_state="failed",
            record_type="reset_user_email",
            error_key="RESET_EMAIL_NO_MATCH_EMAIL",
            params={
                "old_email": old_email,
                "new_email": email
            }
        )
        abort(400, {
            'msg': f'Email ({email}) Not Matching With Token Email!',
            'code': 'INVALID_EMAIL'
        })
    # Check if Token is used
    if token.is_used:
        # Create A History
        create_history(
            entity_type="Users",
            entity=user,
            record_state="failed",
            record_type="reset_user_email",
            error_key="RESET_EMAIL_TOKEN_USED",
            params={
                "old_email": old_email,
                "new_email": email
            }
        )
        abort(400, {
            'msg': 'Token Has Been Used',
            'code': 'USED_TOKEN'
        })
    # Check if Token is expired
    if datetime.now() > token.expire:
        # Create A History
        create_history(
            entity_type="Users",
            entity=user,
            record_state="failed",
            record_type="reset_user_email",
            error_key="RESET_EMAIL_TOKEN_EXPIRED",
            params={
                "old_email": old_email,
                "new_email": email
            }
        )
        abort(400, {
            'msg': 'Token Is Expired',
            'code': 'EXPIRED_TOKEN'
        })

    # Change User's Email & Update Token Status
    try:
        user.email = email
        user.update()
        token.is_used = True
        token.update()

        # Create A History
        create_history(
            entity_type="Users",
            entity=user,
            record_state="succeed",
            record_type="reset_user_email",
            params={
                "old_email": old_email,
                "new_email": email
            }
        )

    except Exception as e:
        print(e)
        # Create A History
        create_history(
            entity_type="Users",
            entity=user,
            record_state="failed",
            record_type="reset_user_email",
            error_key="RESET_EMAIL_SERVER",
            params={
                "old_email": old_email,
                "new_email": email
            }
        )
        abort(500, {
            'msg': 'Something Went Wrong',
            'code': 'SERVER'
        })

    return jsonify({
        'success': True
    })


@users.route('/api/user/files', methods=['POST'])
def upload_files():
    if not current_user.is_authenticated:
        abort(400, {
            'msg': 'You Must Login First!',
            'code': 'NOT_LOGGED'
        })

    req = request.files
    if not req:
        abort(400, {
            'msg': 'You Must Provide A Valid Request',
            'code': 'INVALID_REQUEST'
        })
    filename = ''
    try:
        file = req.get('adImage') or req.get('formPDF')
        filename = upload_images(file)

    except Exception as e:
        print(e)
        abort(500, e)

    return jsonify({
        'success': True,
        'key': filename
    })


@users.route('/api/user/check_Applications/<int:user_id>')
def check_open_Applications(user_id):
    if not current_user.is_authenticated:
        abort(500, {
            'msg': 'Something Went Wrong',
            'code': 'SERVER'
        })

    user = Users.query.get(user_id)

    if not user:
        abort(400, {
            'msg': f'No User Match Given ID #{user_id}',
            'code': 'NO_MATCH_ID'
        })

    prev_ticket = Applications.query.filter_by(user_id=user.uid).filter(
        Applications.to_provider).filter(Applications.status == 'open').first()

    if prev_ticket:
        abort(400, {
            'msg': 'You Have an Open Ticket Already, Please Wait Until it Closes',
            'code': 'OPEN_TICKET'
        })

    return jsonify({
        'success': True
    })


@users.route('/api/user/upgrade_to_provider/<int:user_id>', methods=['POST'])
def upgrade_to_provider(user_id):
    if not current_user.is_authenticated:
        abort(500, {
            'msg': 'Something Went Wrong',
            'code': 'SERVER'
        })

    user = Users.query.get(user_id)

    if not user:
        abort(400, {
            'msg': f'No User Match Given ID #{user_id}',
            'code': 'NO_MATCH_ID'
        })

    prev_ticket = Applications.query.filter_by(user_id=user.uid).filter(
        Applications.to_provider).filter(Applications.status == 'open').first()

    if prev_ticket:
        abort(400, {
            'msg': 'You Have an Open Ticket Already, Please Wait Until it Closes',
            'code': 'OPEN_TICKET'
        })

    req = request.get_json()

    if not req:
        abort(400, {
            'msg': 'You Must Provide A Valid Request',
            'code': 'INVALID_REQUEST'
        })

    company_name = req.get('company_name')
    company_country = req.get('country')
    providerAgreement = req.get('pdfFile')
    mainAdImage = req.get('adImage')

    if not company_name or not company_country or not providerAgreement:
        abort(400, {
            'msg': 'You Must Provide All Important Values',
            'code': 'MISSING_VALUES'
        })

    try:
        # Create A New Ticket
        new_ticket = Applications(
            title="تحويل الحساب إلى معلن",
            to_provider=True,
            company_name=company_name,
            providerAgreement=providerAgreement,
            content=f"يرغب المستخدم {user.username} بتحويل حسابه إلى معلن لشركة {company_name}"
        )

        new_ticket.user_id = user.uid

        new_ticket.insert()

        user.main_ad_image = mainAdImage
        user.country = company_country

        user.update()

        # Create A History
        create_history(
            entity_type="Users",
            entity=user,
            record_state="succeed",
            record_type="ticket_to_provider",
        )

    except Exception as e:
        print(e)
        abort(500, e)

    return jsonify({
        'success': True
    })
