import os
from ast import literal_eval
from flask import request
from flask_login import current_user
from flaskr import SECRET_KEY, SUPERADMIN, ADMIN, PROVIDER, ASSOCIATE, USER
import jwt
from time import time
from functools import wraps

ALL = os.getenv("ALL")
TO_PROVIDER = os.getenv("TO_PROVIDER")
DISABLED_USERS = os.getenv("DISABLED_USERS")
NEW_USERS = os.getenv("NEW_USERS")
ADS = os.getenv("ADS")
OFFERS = os.getenv("OFFERS")
FILES = os.getenv("FILES")
DATA = os.getenv("DATA")
TICKETS = os.getenv("TICKETS")


"""
Errors:
    1) NOT_LOGGED_IN => User is not Logged-in
    2) INVALID_AUTH_HEADER => Header is not valid
    3) NO_TOKEN => No Token With Header
    4) SERVER => Server Error
    5) INVALID_ACCESS_LEVEL => Access Level is Not Valid
    6) ACCESS_DENIED => No Permission For User
    7) AUTH_ERROR => Authorization Error
"""


class AuthError(Exception):
    def __init__(self, error):
        self.msg = error.get('msg') or 'Auth Error'
        self.code = error.get('code') or 'AUTH_ERROR'


def refresh_jwt():
    # Refresh JWT in Expiration.
    if current_user.is_authenticated:
        user_jwt = jwt.encode({
            'uid': current_user.uid,
            'guid': current_user.guid,
            'permissions': current_user.permissions,
            'username': current_user.username,
            'email': current_user.email,
            'company': current_user.company,
            'expire': time() + 900
        }, SECRET_KEY, algorithm='HS256').decode('utf-8')
        return user_jwt
    else:
        raise AuthError({
            'msg': 'You Must Log-in First',
            'code': 'NOT_LOGGED_IN'
        })


def get_jwt_auth_header():
    auth = request.headers.get('Authorization')
    if not auth:
        raise AuthError({
            "msg": 'Authorization Header is Not Provided',
            'code': 'INVALID_AUTH_HEADER'
        })

    parts = auth.split()

    if parts[0].lower() != 'bearer':
        raise AuthError({
            'msg': 'Authorization Header Must Start With "Bearer"',
            'code': 'INVALID_AUTH_HEADER'
        })
    elif len(parts) == 1:
        raise AuthError({
            "msg": 'Token Not Found',
            'code': 'NO_TOKEN'
        })

    elif len(parts) > 2:
        raise AuthError({
            "msg": 'Authorization Header Must Be Bearer Token',
            'code': 'INVALID_AUTH_HEADER'
        })

    return parts[1]


def decode_jwt(token):
    payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
    if payload.get('expire') < time():
        try:
            new_jwt = refresh_jwt()
            payload = jwt.decode(new_jwt, SECRET_KEY, algorithms=['HS256'])
        except:
            raise AuthError({
                'msg': 'Error When Decoding JWT',
                'code': 'SERVER'
            })
    return payload


def check_access_level(access_level, payload):
    # Permission Viewed As GUID
    GUID = {
        'superadmin': [SUPERADMIN],
        'admin': [SUPERADMIN, ADMIN],
        'provider': [SUPERADMIN, PROVIDER],
        'associate': [SUPERADMIN, ADMIN, PROVIDER, ASSOCIATE],
        'customer': [SUPERADMIN, ADMIN, PROVIDER, ASSOCIATE, USER],
    }

    # Check For Permission
    level = None
    try:
        level = GUID.get(access_level)
    except KeyError:
        pass

    if not level:
        raise AuthError({
            'msg': 'Permission Not Found',
            'code': 'INVALID_ACCESS_LEVEL'
        })

    if payload.get('guid') not in level:
        raise AuthError({
            'msg': 'You Are Not Allowed',
            'code': 'ACCESS_DENIED'
        })

    return True


def check_permission(perm, payload):
    # Permissions
    PERMISSIONS = {
        'DATA': [DATA, ALL],
        'TO_PROVIDER': [TO_PROVIDER, ALL],
        'DISABLED_USERS': [DISABLED_USERS, ALL],
        'NEW_USERS': [NEW_USERS, ALL],
        'ADS': [ADS, ALL],
        'OFFERS': [OFFERS, ALL],
        'FILES': [FILES, ALL],
        'TICKETS': [TICKETS, ALL]
    }
    # Check For Permission
    required_perm = None
    try:
        required_perm = PERMISSIONS.get(perm)
    except KeyError:
        pass

    if not required_perm:
        raise AuthError({
            'msg': 'Permission Not Found',
            'code': 'INVALID_ACCESS_LEVEL'
        })

    permissions = literal_eval(payload.get("permissions"))

    # Check if Permission acquired
    for prm in permissions:
        if prm in required_perm:
            return True

    raise AuthError({
        'msg': 'You Are Not Allowed',
        'code': 'ACCESS_DENIED'
    })


def requires_auth(access_level=''):

    def requires_auth_decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            token = get_jwt_auth_header()
            try:
                payload = decode_jwt(token)
            except:
                raise AuthError({
                    'msg': 'Authentication Failed',
                    'code': 'AUTH_ERROR'
                })
            check_access_level(access_level, payload)

            return f(payload, *args, **kwargs)
        return wrapper
    return requires_auth_decorator


def requires_perms(permission=''):
    def requires_auth_decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            token = get_jwt_auth_header()
            try:
                payload = decode_jwt(token)
            except:
                raise AuthError({
                    'msg': 'Authentication Failed',
                    'code': 'AUTH_ERROR'
                })
            check_permission(permission, payload)

            return f(payload, *args, **kwargs)
        return wrapper
    return requires_auth_decorator


# # Authenticate Json Web Token
# @users.route('/api/authenticate', methods=['POST'])
# def authenticate():
#     # Permission Viewed As GUID
#     GUID = {
#         'admin': [ADMIN],
#         'provider': [ADMIN, PROVIDER],
#         'customer': [ADMIN, PROVIDER, CUSTOMER],
#     }
#
#     req = request.get_json()
#
#     if not req:
#         abort(400, 'You Must Provide A Valid Request')
#
#     user_jwt = req.get('jwt')
#     permission = req.get('permission')
#
#     if not permission:
#         abort(400, 'You Must Be Logged-In')
#
#     # Check If JWT is Expired
#     payload = {
#         'guid': USER  # GUID For Normal Users
#     }
#     if user_jwt:
#         payload = jwt.decode(user_jwt, SECRET_KEY, algorithms=['HS256'])
#
#         if payload.get('expire') < time():
#             try:
#                 new_jwt = refresh_jwt()
#                 payload = jwt.decode(new_jwt, SECRET_KEY, algorithms=['HS256'])
#             except Exception as e:
#                 print(e)
#                 abort(400, e)
#     # Check For Permission
#     access_level = None
#     try:
#         access_level = GUID[permission]
#     except KeyError:
#         pass
#
#     if not access_level:
#         abort(401, 'Permission is Not Allowed')
#
#     if payload.get('guid') not in access_level:
#         abort(401, 'You Are Not Allowed')
#
#     return jsonify({
#         'success': True
#     })


# Profile, Settings & Balance Routes
