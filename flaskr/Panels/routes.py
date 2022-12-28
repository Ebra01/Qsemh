import os
import json
import math
import time
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, abort
from flask_login import current_user, logout_user
from flaskr import USER, ASSOCIATE, ADMIN, PROVIDER, SUPERADMIN
from flaskr.Models.models import (Users, Group, StaticLabels, Transfers, Tickets,
                                  Files, Applications, Offers, Coupon,
                                  Association, Notifications)
from sqlalchemy import func, not_, desc, or_
from flaskr.Panels.utils import upload_files, download_files

# Auth
from flaskr.Auth.auth import requires_auth, requires_perms

# Create History
from flaskr.History.routes import create_history

from ast import literal_eval

panels = Blueprint('panels', __name__)

# Permissions
TO_PROVIDER = os.getenv('TO_PROVIDER')
DISABLED_USERS = os.getenv('DISABLED_USERS')
NEW_USERS = os.getenv('NEW_USERS')
ADS = os.getenv('ADS')
OFFERS = os.getenv('OFFERS')
FILES = os.getenv('FILES')
DATA = os.getenv('DATA')
TICKETS = os.getenv('TICKETS')


# Provider Panel

# This is Public to assign Items in Frontend,
# It will be called on Every Click.
@panels.route('/api/labels')
def get_db_data():
    GUID = {
        USER: 'USER',
        PROVIDER: 'PROVIDER',
        ADMIN: 'ADMIN',
        SUPERADMIN: 'SUPERADMIN'
    }

    labels = [lb.display() for lb in StaticLabels.query.all()]
    files = [fl.display() for fl in Files.query.filter_by(admin_file=True).all()]

    # Send Updated Current User Data
    if current_user.is_authenticated:
        if current_user.disabled:
            logout_user()
            abort(400, {
                'msg': 'Your Account Has Been Disabled',
                'code': 'DISABLED'
            })
        access_level = GUID.get(current_user.guid)
        user = current_user.display()
    else:
        access_level = "USER"
        user = None

    return jsonify({
        'labels': json.dumps(labels),
        'files': json.dumps(files),
        'user': json.dumps(user) if user else None,
        'notifications': user.get("notifications") if user else 0,
        'access_level': access_level,
        'success': True
    })


# Users

# USER CONFIGURATIONS

def disable_user(user_id):
    user = Users.query.get(user_id)

    if not user:
        abort(400, {
            'msg': f'No User Match ID #{user_id}',
            'code': 'NO_MATCH_ID'
        })

    if user.disabled:
        abort(400, {
            'msg': 'User Already Disabled',
            'code': 'DISABLED'
        })

    try:
        user.disabled = True
        user.update()
    except Exception as e:
        print(e)
        abort(500, e)


def update_info(user_id, amount, username, pre_phone, phone, country):
    user = Users.query.get(user_id)

    if not user:
        abort(400, {
            'msg': f'No User Match ID #{user_id}',
            'code': 'NO_MATCH_ID'
        })

    try:
        # Check if amount is changed
        if float(amount) > 0:
            old_balance = user.balance
            user.balance += float(amount)
            # Create A Histroy
            create_history(
                entity_type="Users",
                entity=user,
                record_type="user_balance_change",
                record_state="succeed",
                params={
                    "old_balance": old_balance
                }
            )
        # Check if phone is changed
        if f"{pre_phone}{phone}" != user.phone:
            old_phone = user.phone
            user.phone = f"{pre_phone}{phone}"
            # Create A Histroy
            create_history(
                entity_type="Users",
                entity=user,
                record_type="user_phone_change",
                record_state="succeed",
                params={
                    "old_phone": old_phone
                }
            )
        # Check if username is changed
        if username != user.username:
            old_username = user.username
            user.username = username
            # Create A Histroy
            create_history(
                entity_type="Users",
                entity=user,
                record_type="user_username_change",
                record_state="succeed",
                params={
                    "old_username": old_username
                }
            )
        # Check if country is changed
        if user.country != country:
            user.city = None
            old_country = user.country
            user.country = country
            # Create A Histroy
            create_history(
                entity_type="Users",
                entity=user,
                record_type="user_country_change",
                record_state="succeed",
                params={
                    "old_country": old_country
                }
            )

        user.update()
    except Exception as e:
        print(e)
        abort(500, e)


def update_user_access_level(user_id, new_al=None, company_name=None, check_balance=None):
    GUID = {
        'USER': USER,
        'PROVIDER': PROVIDER,
        'ADMIN': ADMIN
    }
    user = Users.query.get(user_id)

    if not user:
        abort(400, {
            'msg': f'No User Match ID #{user_id}',
            'code': 'NO_MATCH_ID'
        })

    try:
        # Check for changes in access level
        if new_al:
            access_level = GUID.get(new_al)
            user.guid = access_level

            # Check if the new access level is PROVIDER
            if access_level == PROVIDER:
                user.is_provider = True
                user.ad_addibility = True
                user.main_ad_image = None
                user.company = company_name
                # Create A History
                create_history(
                    entity_type="Users",
                    entity=user,
                    record_type="user_to_provider",
                    record_state="succeed"
                )

            # Check if the new access level is ADMIN
            elif access_level == ADMIN:
                user.is_admin = True
                # Create A History
                create_history(
                    entity_type="Users",
                    entity=user,
                    record_type="user_to_admin",
                    record_state="succeed"
                )

        # Check for changes in company name only if User is PROVIDER
        if company_name and user.company and user.guid == PROVIDER and not new_al:
            old_company = user.company
            user.company = company_name
            # Create A History
            create_history(
                entity_type="Users",
                entity=user,
                record_type="user_company_change",
                record_state="succeed",
                params={
                    "old_company": old_company
                }
            )

        # Check for changes in balance checking for the Provider
        if check_balance is not None and check_balance != user.check_balance and \
                user.guid == PROVIDER and not new_al:
            user.check_balance = check_balance
            if check_balance:
                # Create A History
                create_history(
                    entity_type="Users",
                    entity=user,
                    record_type="user_balance_checking_activated",
                    record_state="succeed",
                )
            else:
                # Create A History
                create_history(
                    entity_type="Users",
                    entity=user,
                    record_type="user_balance_checking_deactivated",
                    record_state="succeed",
                )

        user.update()
    except Exception as e:
        print(e)
        abort(500, e)


@panels.route('/api/panel/users/<int:user_id>/reactivate')
@requires_perms(permission='DISABLED_USERS')
@requires_auth(access_level='admin')
def reactivate_user(_payload0, _payload1, user_id):
    user = Users.query.get(user_id)

    if not user:
        abort(400, {
            'msg': f'No User Match ID #{user_id}',
            'code': 'NO_MATCH_ID'
        })

    if not user.disabled:
        abort(400, {
            'msg': 'User Already Active',
            'code': 'NOT_DISABLED'
        })

    try:
        user.disabled = False
        user.update()
    except Exception as e:
        print(e)
        abort(500, e)

    users = [u.adminDisplayNormal() for u in Users.query.all() if u.disabled]

    return jsonify({
        'users': users,
        'success': True
    })


@panels.route('/api/panel/users/<int:user_id>/activate')
@requires_perms(permission='NEW_USERS')
@requires_auth(access_level='admin')
def activate_user(_payload0, _payload1, user_id):
    user = Users.query.get(user_id)

    if not user:
        abort(400, {
            'msg': f'No User Match ID #{user_id}',
            'code': 'NO_MATCH_ID'
        })

    if user.is_active:
        abort(400, {
            'msg': 'User Already Active',
            'code': 'ACTIVE'
        })

    try:
        user.is_active = True
        user.update()
    except Exception as e:
        print(e)
        abort(500, e)

    users = [u.adminDisplayNormal() for u in Users.query.all() if not u.is_active]

    return jsonify({
        'users': users,
        'success': True
    })


@panels.route('/api/panel/users/<int:user_id>', methods=['DELETE'])
@requires_auth(access_level='superadmin')
def delete_normal_user(_payload, user_id):
    disable_user(user_id)

    USER_GUID = os.getenv('USER')
    users = [u.adminDisplayNormal() for u in Users.query.order_by(
        Users.id).filter_by(guid=USER_GUID).all() if not u.disabled]

    return jsonify({
        'users': users,
        'success': True
    })


@panels.route('/api/panel/providers/<int:user_id>', methods=['DELETE'])
@requires_auth(access_level='superadmin')
def delete_provider_user(_payload, user_id):
    disable_user(user_id)

    PROVIDER_GUID = os.getenv('PROVIDER')
    users = [u.adminDisplayProviders() for u in Users.query.order_by(
        Users.id).filter_by(guid=PROVIDER_GUID).all() if not u.disabled]

    return jsonify({
        'users': users,
        'success': True
    })


@panels.route('/api/panel/admins/<int:user_id>', methods=['DELETE'])
@requires_auth(access_level='superadmin')
def delete_admin_user(_payload, user_id):
    disable_user(user_id)

    ADMIN_GUID = os.getenv('ADMIN')
    users = [u.adminDisplayAdmins() for u in Users.query.order_by(
        Users.id).filter_by(guid=ADMIN_GUID).all() if not u.disabled]

    return jsonify({
        'users': users,
        'success': True
    })


@panels.route('/api/panel/users/<int:user_id>/settings', methods=['POST'])
@requires_auth(access_level='superadmin')
def change_normal_user_settings(_payload, user_id):
    req = request.get_json()

    username = req.get("username")
    pre_phone = req.get("pre_phone")
    phone = req.get("phone")
    country = req.get("country")
    amount = req.get('amount')

    if not req or (not amount and amount != 0) or not username or not pre_phone \
            or not phone or not country:
        abort(400, {
            'msg': 'Request is Not Valid',
            'code': 'INVALID_REQUEST'
        })

    registered_users = [u.display() for u in Users.query.all() if u.id != user_id]
    registered_usernames = [u['username'] for u in registered_users]
    registered_usernames = [u.lower() if u else u for u in registered_usernames]
    registered_phones = [u['phone'] for u in registered_users]

    if username.lower() in registered_usernames:
        abort(400, {
            'msg': f"Username {username} is taken",
            'code': "USERNAME_TAKEN"
        })

    if f"{pre_phone}{phone}" in registered_phones:
        abort(400, {
            'msg': f"Phone {pre_phone}{phone} is taken",
            'code': "PHONE_TAKEN"
        })

    update_info(user_id=user_id,
                amount=amount,
                username=username,
                country=country,
                pre_phone=pre_phone,
                phone=phone)

    USER_GUID = os.getenv('USER')
    users = [u.adminDisplayNormal() for u in Users.query.order_by(
        Users.id).filter_by(guid=USER_GUID).all() if not u.disabled]

    return jsonify({
        'users': users,
        'success': True
    })


@panels.route('/api/panel/providers/<int:user_id>/settings', methods=['POST'])
@requires_auth(access_level='superadmin')
def change_provider_user_settings(_payload, user_id):
    req = request.get_json()

    username = req.get("username")
    pre_phone = req.get("pre_phone")
    phone = req.get("phone")
    country = req.get("country")
    amount = req.get('amount')

    if not req or (not amount and amount != 0) or not username or not pre_phone \
            or not phone or not country:
        abort(400, {
            'msg': 'Request is Not Valid',
            'code': 'INVALID_REQUEST'
        })

    registered_users = [u.display() for u in Users.query.all() if u.id != user_id]
    registered_usernames = [u['username'] for u in registered_users]
    registered_usernames = [u.lower() if u else u for u in registered_usernames]
    registered_phones = [u['phone'] for u in registered_users]

    if username.lower() in registered_usernames:
        abort(400, {
            'msg': f"Username {username} is taken",
            'code': "USERNAME_TAKEN"
        })

    if f"{pre_phone}{phone}" in registered_phones:
        abort(400, {
            'msg': f"Phone {pre_phone}{phone} is taken",
            'code': "PHONE_TAKEN"
        })

    update_info(user_id=user_id,
                amount=amount,
                username=username,
                country=country,
                pre_phone=pre_phone,
                phone=phone)

    PROVIDER_GUID = os.getenv('PROVIDER')
    users = [u.adminDisplayProviders() for u in Users.query.order_by(
        Users.id).filter_by(guid=PROVIDER_GUID).all() if not u.disabled]

    return jsonify({
        'users': users,
        'success': True
    })


@panels.route('/api/panel/admins/<int:user_id>/settings', methods=['POST'])
@requires_auth(access_level='superadmin')
def change_admin_user_settings(_payload, user_id):
    req = request.get_json()

    username = req.get("username")
    pre_phone = req.get("pre_phone")
    phone = req.get("phone")
    country = req.get("country")
    amount = req.get('amount')

    if not req or (not amount and amount != 0) or not username or not pre_phone \
            or not phone or not country:
        abort(400, {
            'msg': 'Request is Not Valid',
            'code': 'INVALID_REQUEST'
        })

    registered_users = [u.display() for u in Users.query.all() if u.id != user_id]
    registered_usernames = [u['username'] for u in registered_users]
    registered_usernames = [u.lower() if u else u for u in registered_usernames]
    registered_phones = [u['phone'] for u in registered_users]

    if username.lower() in registered_usernames:
        abort(400, {
            'msg': f"Username {username} is taken",
            'code': "USERNAME_TAKEN"
        })

    if f"{pre_phone}{phone}" in registered_phones:
        abort(400, {
            'msg': f"Phone {pre_phone}{phone} is taken",
            'code': "PHONE_TAKEN"
        })

    update_info(user_id=user_id,
                amount=amount,
                username=username,
                country=country,
                pre_phone=pre_phone,
                phone=phone)

    ADMIN_GUID = os.getenv('ADMIN')
    users = [u.adminDisplayAdmins() for u in Users.query.order_by(
        Users.id).filter_by(guid=ADMIN_GUID).all() if not u.disabled]

    return jsonify({
        'users': users,
        'success': True
    })


@panels.route('/api/panel/users/<int:user_id>/access_level', methods=['POST'])
@requires_auth(access_level='superadmin')
def change_normal_user_access_level(_payload, user_id):
    req = request.get_json()
    access_level = req.get('access_level')
    company_name = req.get('company_name')

    if not req:
        abort(400, {
            'msg': 'Request is Not Valid',
            'code': 'INVALID_REQUEST'
        })

    update_user_access_level(
        user_id=user_id,
        new_al=access_level,
        company_name=company_name)

    USER_GUID = os.getenv('USER')
    users = [u.adminDisplayNormal() for u in Users.query.order_by(
        Users.id).filter_by(guid=USER_GUID).all() if not u.disabled]

    return jsonify({
        'users': users,
        'success': True
    })


@panels.route('/api/panel/providers/<int:user_id>/company', methods=['POST'])
@requires_auth(access_level='superadmin')
def change_provider_company(_payload, user_id):
    req = request.get_json()

    company_name = req.get('company_name')
    check_balance = req.get('check_balance')

    if not req:
        abort(400, {
            'msg': 'Request is Not Valid',
            'code': 'INVALID_REQUEST'
        })

    update_user_access_level(
        user_id=user_id,
        company_name=company_name,
        check_balance=check_balance)

    PROVIDER_GUID = os.getenv('PROVIDER')
    users = [u.adminDisplayProviders() for u in Users.query.order_by(
        Users.id).filter_by(guid=PROVIDER_GUID).all() if not u.disabled]

    return jsonify({
        'users': users,
        'success': True
    })


@panels.route('/api/panel/user/<int:user_id>/downgrade')
@requires_auth(access_level='superadmin')
def downgrade_user_access_level(_payload, user_id):
    user = Users.query.get(user_id)

    if not user:
        abort(400, {
            'msg': f'No User Match ID #{user_id}',
            'code': 'NO_MATCH_ID'
        })

    previous_al = user.guid

    try:
        user.guid = USER
        if previous_al == ADMIN:
            user.is_admin = False
            user.permissions = '[]'
            # Create A History
            create_history(
                entity_type="Users",
                entity=user,
                record_type="admin_to_user",
                record_state="succeed"
            )
        if previous_al == PROVIDER:
            company = user.company
            user.is_provider = False
            user.ad_addibility = False
            user.company = None
            user.main_ad_image = None
            # Create A History
            create_history(
                entity_type="Users",
                entity=user,
                record_type="provider_to_user",
                record_state="succeed",
                params={
                    "company": company
                }
            )
        user.update()
    except Exception as e:
        abort(500, e)

    if previous_al == ADMIN:
        users = [u.adminDisplayNormal() for u in Users.query.order_by(
            Users.id).filter_by(guid=ADMIN).all() if not u.disabled]
    elif previous_al == PROVIDER:
        users = [u.adminDisplayProviders() for u in Users.query.order_by(
            Users.id).filter_by(guid=PROVIDER).all() if not u.disabled]
    else:
        users = [u.adminDisplayAdmins() for u in Users.query.order_by(
            Users.id).filter_by(guid=USER).all() if not u.disabled]

    return jsonify({
        'users': users,
        'success': True
    })


@panels.route('/api/panel/user/<int:user_id>/permissions', methods=['PATCH'])
@requires_auth(access_level='superadmin')
def update_user_permissions(_payload, user_id):
    perms = {
        'TO_PROVIDER': TO_PROVIDER,
        'DISABLED_USERS': DISABLED_USERS,
        'NEW_USERS': NEW_USERS,
        'ADS': ADS,
        'OFFERS': OFFERS,
        'FILES': FILES,
        'DATA': DATA,
        'TICKETS': TICKETS
    }

    user = Users.query.get(user_id)

    if not user:
        abort(400, {
            'msg': f'No User Match ID #{user_id}',
            'code': 'NO_MATCH_ID'
        })

    if not user.is_admin and not user.guid == ADMIN:
        abort(400, {
            'msg': 'User is Not An Admin',
            'code': 'NOT_ADMIN'
        })

    req = request.get_json()
    permissions = req.get('permissions')
    try:
        updated_permissions = [perms[p] for p in permissions]
        user.permissions = str(updated_permissions)

        user.update()
    except Exception as e:
        print(e)
        abort(500, e)

    ADMIN_GUID = os.getenv('ADMIN')
    users = [u.adminDisplayAdmins() for u in Users.query.order_by(
        Users.id).filter_by(guid=ADMIN_GUID).all() if not u.disabled]

    return jsonify({
        'users': users,
        'success': True
    })


# USER CONFIGURATIONS

@panels.route('/api/panel/users', methods=['GET', 'POST'])
@requires_auth(access_level='superadmin')
def get_normal_users(_payload):
    """
    Getting All Normal Users, with the ability to filter.
    """
    USER_GUID = os.getenv('USER')
    users_query = Users.query.order_by(
        Users.id).filter_by(guid=USER_GUID)

    if request.method == 'POST':
        req = request.get_json()
        username = req.get('username')
        fullname = req.get('fullname')
        email = req.get('email')
        phone = req.get('phone')

        if username:
            users_query = users_query.filter(
                func.lower(Users.username).contains(username.lower()))
        if fullname:
            users_query = users_query.filter(
                func.lower(Users.fullname).contains(fullname.lower()))
        if email:
            users_query = users_query.filter(
                func.lower(Users.email).contains(email.lower()))
        if phone:
            users_query = users_query.filter(Users.phone.contains(phone))

    users = [u.adminDisplayNormal() for u in users_query.all() if not u.disabled]

    return jsonify({
        'users': users,
        'success': True
    })


@panels.route('/api/panel/providers', methods=['GET', 'POST'])
@requires_auth(access_level='superadmin')
def get_providers_users(_payload):
    """
    Getting All Provider Users, with the ability to filter.
    """
    PROVIDER_GUID = os.getenv('PROVIDER')
    users_query = Users.query.order_by(
        Users.id).filter_by(guid=PROVIDER_GUID)

    if request.method == 'POST':
        req = request.get_json()
        username = req.get('username')
        fullname = req.get('fullname')
        email = req.get('email')
        phone = req.get('phone')
        company = req.get('company')

        if username:
            users_query = users_query.filter(
                func.lower(Users.username).contains(username.lower()))
        if fullname:
            users_query = users_query.filter(
                func.lower(Users.fullname).contains(fullname.lower()))
        if email:
            users_query = users_query.filter(
                func.lower(Users.email).contains(email.lower()))
        if company:
            users_query = users_query.filter(
                func.lower(Users.company).contains(company.lower()))
        if phone:
            users_query = users_query.filter(Users.phone.contains(phone))

    users = [u.adminDisplayProviders() for u in users_query.all() if not u.disabled]

    return jsonify({
        'users': users,
        'success': True
    })


@panels.route('/api/panel/associates', methods=['GET', 'POST'])
@requires_auth(access_level='superadmin')
def get_associates_users(_payload):
    """
    Getting All Provider Users, with the ability to filter.
    """
    ASSOCIATE_GUID = os.getenv('ASSOCIATE')
    users_query = Users.query.order_by(
        Users.id).filter_by(guid=ASSOCIATE_GUID)

    if request.method == 'POST':
        req = request.get_json()
        username = req.get('username')
        fullname = req.get('fullname')
        email = req.get('email')
        phone = req.get('phone')
        company = req.get('company')

        if username:
            users_query = users_query.filter(
                func.lower(Users.username).contains(username.lower()))
        if fullname:
            users_query = users_query.filter(
                func.lower(Users.fullname).contains(fullname.lower()))
        if email:
            users_query = users_query.filter(
                func.lower(Users.email).contains(email.lower()))
        if company:
            users_query = users_query.filter(
                func.lower(Users.company).contains(company.lower()))
        if phone:
            users_query = users_query.filter(Users.phone.contains(phone))

    users = [u.adminDisplayAssociates() for u in users_query.all() if not u.disabled]

    return jsonify({
        'users': users,
        'success': True
    })


@panels.route('/api/panel/admins', methods=['GET', 'POST'])
@requires_auth(access_level='superadmin')
def get_admins_users(_payload):
    """
    Getting All Admin Users, with the ability to filter.
    """
    ADMIN_GUID = os.getenv('ADMIN')
    users_query = Users.query.order_by(
        Users.id).filter_by(guid=ADMIN_GUID)

    if request.method == 'POST':
        req = request.get_json()
        username = req.get('username')
        fullname = req.get('fullname')
        email = req.get('email')
        phone = req.get('phone')

        if username:
            users_query = users_query.filter(
                func.lower(Users.username).contains(username.lower()))
        if fullname:
            users_query = users_query.filter(
                func.lower(Users.fullname).contains(fullname.lower()))
        if email:
            users_query = users_query.filter(
                func.lower(Users.email).contains(email.lower()))
        if phone:
            users_query = users_query.filter(Users.phone.contains(phone))

    users = [u.adminDisplayAdmins() for u in users_query.all() if not u.disabled]

    return jsonify({
        'users': users,
        'success': True
    })


@panels.route('/api/panel/users/disabled', methods=['GET', 'POST'])
@requires_perms(permission='DISABLED_USERS')
@requires_auth(access_level='admin')
def get_disabled_users(_payload0, _payload1):
    """
    Getting All Disabled Users, with the ability to filter.
    """
    users = [u.adminDisplayNormal() for u in Users.query.all() if u.disabled]

    return jsonify({
        'users': users,
        'success': True
    })


@panels.route('/api/panel/users/inactive', methods=['GET', 'POST'])
@requires_perms(permission='NEW_USERS')
@requires_auth(access_level='admin')
def get_inactive_users(_payload0, _payload1):
    """
    Getting All InActive Users, with the ability to filter.
    """
    users = [u.adminDisplayNormal() for u in Users.query.all() if not u.is_active]

    return jsonify({
        'users': users,
        'success': True
    })


@panels.route('/api/panel/association/remove/<int:associate>')
@requires_auth(access_level='superadmin')
def admin_remove_associate(_payload, associate):

    user = Users.query.get(associate)

    if not user:
        abort(400, {
            'msg': f'No User match ID #{associate}',
            'code': 'NO_USER'
        })

    try:
        user.association_id = None
        user.is_associate = False
        user.guid = USER
        user.update()
    except Exception as e:
        abort(500, e)

    ASSOCIATE_GUID = os.getenv('ASSOCIATE')
    users_query = Users.query.order_by(
        Users.id).filter_by(guid=ASSOCIATE_GUID).all()

    return jsonify({
        'users': users_query,
        'success': True
    })


@panels.route('/api/panel/applications', methods=['GET', 'POST'])
@requires_perms(permission='TO_PROVIDER')
@requires_auth(access_level='admin')
def to_provider_applications(_payload0, _payload1):
    """
        Getting All Applications With Request To Change User Type to Provider
    """

    applications = [t.toProviderDisplay() for t in Applications.query.filter(
        Applications.to_provider).order_by(desc(Applications.id)).all()]

    return jsonify({
        'requests': applications,
        'success': True
    })


@panels.route('/api/panel/applications/<int:ticket_id>/approve')
@requires_perms(permission='TO_PROVIDER')
@requires_auth(access_level='admin')
def approve_application(_payload0, _payload1, ticket_id):
    ticket = Applications.query.get(ticket_id)

    if not ticket:
        abort(400, {
            'msg': f'No Ticket Match ID #{ticket_id}',
            'code': 'NO_MATCH_ID'
        })

    if not ticket.to_provider:
        abort(400, {
            'msg': 'Wrong Ticket Type',
            'code': 'INVALID_TYPE'
        })

    user = Users.query.filter_by(uid=ticket.user_id).first()

    if not user:
        abort(400, {
            'msg': 'This Ticket has No User',
            'code': 'NO_USER'
        })

    try:
        # Update Ticket Status
        ticket.status = 'accepted'
        ticket.update()

        # Update User Type, GUID, and Provider Status
        user.company = ticket.company_name
        user.guid = os.getenv('PROVIDER')
        user.is_provider = True
        user.ad_addibility = True

        # Create A History
        create_history(
            entity_type="Users",
            entity=user,
            record_type="user_to_provider",
            record_state="succeed"
        )

        user.update()

    except Exception as e:
        abort(500, e)

    applications = [t.toProviderDisplay() for t in Applications.query.filter(
        Applications.to_provider).order_by(desc(Applications.id)).all()]

    return jsonify({
        'requests': applications,
        'success': True
    })


@panels.route('/api/panel/applications/<int:ticket_id>/reject')
@requires_perms(permission='TO_PROVIDER')
@requires_auth(access_level='admin')
def reject_application(_payload0, _payload1, ticket_id):
    ticket = Applications.query.get(ticket_id)

    if not ticket:
        abort(400, {
            'msg': f'No Ticket Match ID #{ticket_id}',
            'code': 'NO_MATCH_ID'
        })

    if not ticket.to_provider:
        abort(400, {
            'msg': 'Wrong Ticket Type',
            'code': 'INVALID_TYPE'
        })

    try:
        # Update Ticket Status
        ticket.status = 'rejected'
        ticket.update()

    except Exception as e:
        abort(500, e)

    applications = [t.toProviderDisplay() for t in Applications.query.filter(
        Applications.to_provider).order_by(desc(Applications.id)).all()]

    return jsonify({
        'requests': applications,
        'success': True
    })


# Users


# Balance (Request, Transfers)

@panels.route('/api/panel/balance/requests')
@requires_auth(access_level='superadmin')
def get_add_balance_requests(_payload):
    requests = [t.display() for t in Transfers.query.order_by(
        Transfers.method, Transfers.verified, desc(Transfers.id)).all()]

    return jsonify({
        'requests': requests,
        'success': True
    })


@panels.route('/api/panel/balance/requests/<int:request_id>/accept', methods=['POST'])
@requires_auth(access_level='superadmin')
def accept_add_balance_request(_payload, request_id):
    balance_request = Transfers.query.get(request_id)

    if not balance_request:
        abort(400, {
            'msg': f'No Request Match ID #{request_id}',
            'code': 'NO_MATCH_ID'
        })

    if balance_request.verified:
        abort(400, {
            'msg': 'Request is Already Verified',
            'code': 'VERIFIED'
        })

    user = Users.query.filter_by(uid=balance_request.user_id).first()

    if not user:
        abort(400, {
            'msg': 'User is Not Available, Or Has Been Deleted',
            'code': 'NO_USER'
        })

    req = request.get_json()

    if not req:
        abort(400, {
            'msg': 'Request Must Not Be Empty',
            'code': 'INVALID_REQUEST'
        })

    amount = req.get('amount')

    if not amount:
        abort(400, {
            'msg': 'Missing Values, Amount Must Be Valid',
            'code': 'MISSING_VALUES'
        })

    try:
        # Update Request Status
        balance_request.verified = True
        balance_request.amount = float(amount)
        balance_request.update()

        # Update User Balance
        user.balance += float(amount)
        user.update()

        # Create A History
        create_history(
            entity_type="Users",
            entity=user,
            record_state="succeed",
            record_type="bank_balance_accept",
            params={
                "amount": balance_request.amount,
                "added_amount": amount,
                "current_balance": user.balance - float(amount),
                "new_balance": user.balance
            }
        )
    except Exception as e:
        print(e)
        abort(500, e)

    requests = [t.display() for t in Transfers.query.order_by(
        Transfers.method, not_(Transfers.verified), desc(Transfers.id)).all()]

    return jsonify({
        'requests': requests,
        'success': True
    })


@panels.route('/api/panel/balance/requests/<int:request_id>/reject')
@requires_auth(access_level='superadmin')
def reject_add_balance_request(_payload, request_id):
    balance_request = Transfers.query.get(request_id)

    if not balance_request:
        abort(400, {
            'msg': f'No Request Match ID #{request_id}',
            'code': 'NO_MATCH_ID'
        })

    if balance_request.verified:
        abort(400, {
            'msg': 'Request is Already Verified',
            'code': 'VERIFIED'
        })

    try:
        # Delete The Request
        balance_request.delete()
        user = Users.query.filter(Users.uid == balance_request.user_id).first()
        if user:
            # Create A History
            create_history(
                entity_type="Users",
                entity=user,
                record_state="failed",
                record_type="bank_balance_reject",
                error_key="BANK_REQUEST_ERROR",
                params={
                    "amount": balance_request.amount,
                    "current_balance": user.balance,
                }
            )
    except Exception as e:
        print(e)
        abort(500, e)

    requests = [t.display() for t in Transfers.query.order_by(
        Transfers.method, not_(Transfers.verified), desc(Transfers.id)).all()]

    return jsonify({
        'requests': requests,
        'success': True
    })


# Balance (Request, Transfers)


# Groups

@panels.route('/api/panel/groups', methods=['GET', 'POST'])
@requires_perms(permission='ADS')
@requires_auth(access_level='admin')
def get_groups(_payload0, _payload1):
    """
    Getting All Groups, with the ability to filter.
    """

    groups_query = Group.query.order_by(desc(Group.id)).filter(
        Group.status != 'pending').filter(not_(Group.on_hide))

    if request.method == 'POST':
        req = request.get_json()
        name = req.get('name')

        if name:
            groups_query = groups_query.filter(
                func.lower(Group.company).contains(name.lower()))

    groups = [g.adminDisplay() for g in groups_query.all()]
    return jsonify({
        'groups': groups,
        'success': True
    })


@panels.route('/api/panel/groups/<int:group_id>')
@requires_perms(permission='ADS')
@requires_auth(access_level='admin')
def delete_group(_payload0, _payload1, group_id):
    """
    Hiding A Group From The Panel.
    """

    group = Group.query.get(group_id)

    if not group:
        abort(400, {
            'msg': f'No Group Match ID #{group_id}',
            'code': 'NO_MATCH_ID'
        })

    try:
        group.on_hide = True
        group.update()
    except Exception as e:
        abort(500, e)

    groups = [g.adminDisplay() for g in Group.query.order_by(desc(Group.id)).filter(
        Group.status != 'pending').filter(not_(Group.on_hide)).all()]

    return jsonify({
        'groups': groups,
        'success': True
    })


@panels.route('/api/panel/new_groups', methods=['GET', 'POST'])
@requires_perms(permission='ADS')
@requires_auth(access_level='admin')
def get_new_groups(_payload0, _payload1):
    """
    Getting All (Pending) Groups, with the ability to filter.
   """

    groups = [g.adminDisplay() for g in Group.query.filter_by(status='pending').all()]

    return jsonify({
        'groups': groups,
        'success': True
    })


@panels.route('/api/panel/groups/<int:group_id>/approve', methods=['POST'])
@requires_perms(permission='ADS')
@requires_auth(access_level='admin')
def accept_group(_payload0, _payload1, group_id):
    group = Group.query.get(group_id)

    if not group:
        abort(400, {
            'msg': f'No Group Match ID #{group_id}'
        })

    req = request.get_json()

    if not req:
        abort(400, {
            'msg': 'Request Is Not Valid',
            'code': 'INVALID_REQUEST'
        })

    display_time = req.get('display_time')
    distribute_time = req.get('distribute_time')

    if not distribute_time:
        abort(400, {
            'msg': 'Important Values Must Be Provided',
            'code': 'MISSING_VALUES'
        })

    if not display_time or int(display_time) == 0:
        display_time = int(min(math.ceil((int(group.full_price) / 1000) * 24), 48))

    try:
        group.status = 'available'

        # Check if Start Date has accured, if true, set target to current date,
        # and if not, set target to start date.
        current_date = datetime.now()
        target_date = max(current_date, group.start_date)

        # Calculate End Date For Display (On Main Page)
        group.display_expire_date = target_date + timedelta(hours=int(display_time))
        # Calculate End Date For Distribution
        group.distribute_end_date = target_date + timedelta(minutes=int(distribute_time))

        group.update()
    except Exception as e:
        print(e)
        abort(500, e)

    groups = [g.adminDisplay() for g in Group.query.filter_by(status='pending').all()]

    return jsonify({
        'groups': groups,
        'success': True
    })


@panels.route('/api/panel/groups/<int:group_id>/cancel')
@requires_perms(permission='ADS')
@requires_auth(access_level='admin')
def cancel_group(_payload0, _payload1, group_id):
    group = Group.query.get(group_id)

    if not group:
        abort(400, {
            'msg': f'No Group Match ID #{group_id}'
        })

    try:
        group.status = 'canceled'
        group.update()
    except Exception as e:
        print(e)
        abort(500, e)

    groups = [g.adminDisplay() for g in Group.query.filter_by(status='pending').all()]

    return jsonify({
        'groups': groups,
        'success': True
    })


# Groups

# Tickets
@panels.route('/api/panel/tickets')
@requires_perms(permission='TICKETS')
@requires_auth(access_level='admin')
def get_tickets(_payload0, _payload1):
    """
    Getting All Tickets
   """

    tickets_ = [t.display() for t in Tickets.query.order_by(desc(Tickets.id)).all()]

    return jsonify({
        'tickets': tickets_,
        'success': True
    })

# Tickets


# Offers

@panels.route('/api/panel/offers/invalid', methods=['GET', 'POST'])
@requires_perms(permission='OFFERS')
@requires_auth(access_level='admin')
def get_invalidated_offers(_payload0, _payload1):
    offers = [o.display() for o in Offers.query.order_by(desc(Offers.id)).all()
              if Coupon.query.get(o.coupon_id).coupon_status not
              in ['expired', 'canceled', 'used'] and not o.validated and not o.completed]

    return jsonify({
        'offers': offers,
        'success': True
    })


@panels.route('/api/panel/offers', methods=['GET', 'POST'])
@requires_perms(permission='OFFERS')
@requires_auth(access_level='admin')
def get_offers(_payload0, _payload1):
    offers = [o.display() for o in Offers.query.order_by(desc(Offers.id)).all()
              if Coupon.query.get(o.coupon_id).coupon_status not
              in ['expired', 'canceled', 'used'] and o.validated and not o.completed]

    return jsonify({
        'offers': offers,
        'success': True
    })


@panels.route('/api/panel/offers/<int:offer_id>/validate', methods=['GET', 'POST'])
@requires_perms(permission='OFFERS')
@requires_auth(access_level='admin')
def validate_offers(_payload0, _payload1, offer_id):
    offer = Offers.query.get(offer_id)

    if not offer:
        abort(404, {
            'msg': f'No Offer Match ID #{offer_id}',
            'code': 'NO_MATCH_ID'
        })

    if offer.completed:
        abort(400, {
            'msg': 'Offer is Finished Already',
            'code': 'FINISHED_OFFER'
        })

    coupon = Coupon.query.get(offer.coupon_id)

    if not coupon:
        abort(400, {
            'msg': 'Offer Coupon Doesn\'t Exist',
            'code': 'NO_COUPON'
        })

    try:
        offer.validated = True
        offer.update()
    except Exception as e:
        abort(500, e)

    offers = [o.display() for o in Offers.query.order_by(desc(Offers.id)).all()
              if Coupon.query.get(o.coupon_id).coupon_status not
              in ['expired', 'canceled', 'used'] and not o.validated and not o.completed]

    return jsonify({
        'offers': offers,
        'success': True
    })


@panels.route('/api/panel/offers/<int:offer_id>/cancel', methods=['GET'])
@requires_perms(permission='OFFERS')
@requires_auth(access_level='admin')
def cancel_offers(_payload0, _payload1, offer_id):
    offer = Offers.query.get(offer_id)

    if not offer:
        abort(404, {
            'msg': f'No Offer Match ID #{offer_id}',
            'code': 'NO_MATCH_ID'
        })

    if offer.completed:
        abort(400, {
            'msg': 'Offer is Finished Already',
            'code': 'FINISHED_OFFER'
        })

    coupon = Coupon.query.get(offer.coupon_id)

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
    except Exception as e:
        abort(500, e)

    offers = [o.display() for o in Offers.query.order_by(desc(Offers.id)).all()
              if Coupon.query.get(o.coupon_id).coupon_status not
              in ['expired', 'canceled', 'used'] and o.validated and not o.completed]

    return jsonify({
        'offers': offers,
        'success': True
    })


@panels.route('/api/panel/offers/invalid/<int:offer_id>/cancel', methods=['GET'])
@requires_perms(permission='OFFERS')
@requires_auth(access_level='admin')
def cancel_invalid_offers(_payload0, _payload1, offer_id):
    offer = Offers.query.get(offer_id)

    if not offer:
        abort(404, {
            'msg': f'No Offer Match ID #{offer_id}',
            'code': 'NO_MATCH_ID'
        })

    if offer.completed:
        abort(400, {
            'msg': 'Offer is Finished Already',
            'code': 'FINISHED_OFFER'
        })

    coupon = Coupon.query.get(offer.coupon_id)

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
    except Exception as e:
        abort(500, e)

    offers = [o.display() for o in Offers.query.order_by(desc(Offers.id)).all()
              if Coupon.query.get(o.coupon_id).coupon_status not
              in ['expired', 'canceled', 'used'] and not o.validated and not o.completed]

    return jsonify({
        'offers': offers,
        'success': True
    })


# Offers


# Elements (Labels)

@panels.route('/api/panel/labels', methods=['GET', 'POST'])
@requires_perms(permission='DATA')
@requires_auth(access_level='admin')
def get_labels(_payload0, _payload1):
    labels_query = StaticLabels.query.order_by(StaticLabels.name)
    if request.method == 'POST':
        req = request.get_json()
        name = req.get('name')
        label = req.get('label')

        if name:
            labels_query = labels_query.filter(
                func.lower(StaticLabels.name).contains(name.lower()))
        if label:
            labels_query = labels_query.filter(
                func.lower(StaticLabels.label).contains(label.lower()))

    labels = [lb.display() for lb in labels_query.all()]
    return jsonify({
        'labels': labels,
        'success': True
    })


# Key: Country

@panels.route('/api/panel/country', methods=['POST'])
@requires_perms(permission='DATA')
@requires_auth(access_level='admin')
def create_country(_payload0, _payload1):
    req = request.get_json()

    if not req:
        abort(400, {
            'msg': 'Request Is Not Valid',
            'code': 'INVALID_REQUEST'
        })

    label = req.get('label')
    country_ar = req.get('country_ar')
    country_en = req.get('country_en')
    cities_ar = req.get('cities_ar')
    cities_en = req.get('cities_en')
    telecode = req.get('telecode')
    description = req.get('description')

    if not label or not country_ar or not country_en or not \
            cities_ar or not cities_en or not telecode:
        abort(400, {
            'msg': 'Missing Values In Request',
            'code': 'MISSING_VALUES'
        })

    try:
        # Turn Cities String to Array.
        # cities_ar_array = [ar.strip() for ar in cities_ar.split(',')]
        # cities_en_array = [en.strip() for en in cities_en.split(',')]

        # Turning Values into a Dictionary
        values = {
            'country': {
                'en': country_en,
                'ar': country_ar
            },
            'telecode': telecode,
            'cities': {
                'en': cities_en,
                'ar': cities_ar
            }
        }

        new_country = StaticLabels(
            key="country",
            label=label,
            name="الدولة و المدن",
            values=str(values),
            description=description,
        )

        new_country.insert()
    except Exception as e:
        print(e)
        abort(500, e)

    labels = [lb.display() for lb in StaticLabels.query.order_by(StaticLabels.name).all()]
    return jsonify({
        'labels': labels,
        'success': True
    })


@panels.route('/api/panel/country/<int:label_id>', methods=['PATCH'])
@requires_perms(permission='DATA')
@requires_auth(access_level='admin')
def update_country(_payload0, _payload1, label_id):
    country = StaticLabels.query.get(label_id)

    req = request.get_json()

    if not req:
        abort(400, {
            'msg': 'Request Is Not Valid',
            'code': 'INVALID_REQUEST'
        })

    label = req.get('label')
    name = req.get('name')
    country_ar = req.get('country_ar')
    country_en = req.get('country_en')
    cities_ar = req.get('cities_ar')
    cities_en = req.get('cities_en')
    telecode = req.get('telecode')
    description = req.get('description')

    if not label or not name or not country_ar or not country_en or not \
            cities_ar or not cities_en or not description or not telecode:
        abort(400, {
            'msg': 'Missing Values In Request',
            'code': 'MISSING_VALUES'
        })

    try:
        # Turn Cities String to Array.
        # cities_ar_array = [ar.strip() for ar in cities_ar.split(',')]
        # cities_en_array = [en.strip() for en in cities_en.split(',')]

        # Turning Values into a Dictionary
        values = {
            'country': {
                'en': country_en,
                'ar': country_ar
            },
            'telecode': telecode,
            'cities': {
                'en': cities_en,
                'ar': cities_ar
            }
        }

        country.label = label
        country.name = name
        country.description = description
        country.values = str(values)

        country.update()
    except Exception as e:
        print(e)
        abort(500, e)

    labels = [lb.display() for lb in StaticLabels.query.order_by(StaticLabels.name).all()]
    return jsonify({
        'labels': labels,
        'success': True
    })


# Key: Country


# Key : Coupon Group

@panels.route('/api/panel/coupons/<int:label_id>', methods=['PATCH'])
@requires_perms(permission='DATA')
@requires_auth(access_level='admin')
def update_coupon_types(_payload0, _payload1, label_id):
    couponType = StaticLabels.query.get(label_id)

    req = request.get_json()

    if not req:
        abort(400, {
            'msg': 'Request Is Not Valid',
            'code': 'INVALID_REQUEST'
        })

    description = req.get('description')
    values_ar = req.get('values_ar')
    values_en = req.get('values_en')

    if not values_ar or not values_en:
        abort(400, {
            'msg': 'Missing Values In Request',
            'code': 'MISSING_VALUES'
        })

    try:
        # Turn Cities String to Array.
        # values_ar_array = [ar.strip() for ar in values_ar.split(',')]
        # values_en_array = [en.strip() for en in values_en.split(',')]

        # Turning Values into a Dictionary
        values = {
            'en': values_en,
            'ar': values_ar
        }

        couponType.values = str(values)
        couponType.description = description

        couponType.update()
    except Exception as e:
        print(e)
        abort(500, e)

    labels = [lb.display() for lb in StaticLabels.query.order_by(StaticLabels.name).all()]
    return jsonify({
        'labels': labels,
        'success': True
    })


# Key : Coupon Group

# Elements (Labels)


# Files (Labels)

@panels.route('/api/panel/files', methods=['GET'])
@requires_perms(permission='FILES')
@requires_auth(access_level='admin')
def get_files(_payload0, _payload1):
    files = [f.display() for f in Files.query.filter_by(admin_file=True).all()]

    return jsonify({
        'files': files,
        'success': True
    })


@panels.route('/api/panel/files', methods=['POST'])
@requires_perms(permission='FILES')
@requires_auth(access_level='admin')
def create_files(_payload0, _payload1):
    req = request.get_json()

    # Check if Request is Valid
    if not req:
        abort(400, {
            'msg': 'Request Must Not Be Empty',
            'code': 'INVALID_REQUEST'
        })

    key = req.get('key')
    description = req.get('description')
    files = req.get('files')
    # Check if key and description are provided
    if not key or not description:
        abort(400, {
            'msg': 'Important Values Are Missing',
            'code': 'MISSING_VALUES'
        })

    # Fetch Submitted Files Only
    submitted_files = [f.get('name') for f in files if f.get('status') == 'success']

    # Check if 'submitted files' is empty
    if not submitted_files:
        abort(400, {
            'msg': 'No Files Provided',
            'code': 'NO_FILES'
        })

    try:
        # Add Values to File
        for f in submitted_files:
            file = Files.query.filter_by(file_name=f).first()
            # Update File Type, Key, & Description
            file.admin_file = True
            file.key = key
            file.description = description

            file.update()
    except Exception as e:
        print(e)
        abort(500, e)

    files = [f.display() for f in Files.query.filter_by(admin_file=True).all()]

    return jsonify({
        'files': files,
        'success': True
    })


@panels.route('/api/panel/files/<int:file_id>', methods=['DELETE'])
@requires_perms(permission='FILES')
@requires_auth(access_level='admin')
def delete_file(_payload0, _payload1, file_id):
    file = Files.query.get(file_id)

    if not file:
        abort(400, {
            'msg': f'No File Match ID #{file_id}',
            'code': 'NO_MATCH_FILE'
        })

    try:
        # Delete The File with file_id
        file.delete()
    except Exception as e:
        print(e)
        abort(500, e)

    files = [f.display() for f in Files.query.filter_by(admin_file=True).all()]

    return jsonify({
        'files': files,
        'success': True
    })


@panels.route('/api/panel/files/<string:file_name>')
@requires_perms(permission='FILES')
@requires_auth(access_level='admin')
def download_file(_payload0, _payload1, file_name):
    return jsonify({
        'download_link': download_files(key=file_name),
        'success': True
    })


@panels.route('/api/panel/files/download', methods=['POST'])
@requires_auth(access_level='customer')
def download_list_files(_payload):
    req = request.get_json()
    keys = req.get('keys')

    if not req or not keys:
        abort(400, {
            'msg': 'No Keys Provided',
            'code': 'NO_KEYS'
        })
    links = []
    try:
        for key in keys:
            file = Files.query.filter_by(file_name=key).first()

            if file:
                link = download_files(key=key, expire=180)
                links.append(link)

    except Exception as e:
        abort(500, e)

    return jsonify({
        'download_links': links[-1],
        'success': True
    })


# This is Admins Only Route, To Upload Files (pdf, zip, docx, etc..)
# This will have to be linked to 'update_labels' [values = filenames]
@panels.route('/api/panel/files/upload', methods=['POST'])
@requires_perms(permission='FILES')
@requires_auth(access_level='admin')
def upload_files_s3(_payload0, _payload1):
    files = request.files
    if not files:
        abort(400, {
            'msg': 'You Must Provide A Valid Request',
            'code': 'INVALID_REQUEST'
        })
    filenames = []
    try:

        for name in files:
            file = files.get(name)
            try:
                filename, status = upload_files(file)
                filenames.append({
                    'name': filename,
                    'status': status
                })
            except Exception as e:
                print(e)
    except Exception as e:
        abort(500, e)

    return jsonify({
        'success': True,
        'files': filenames
    })


# Files (Labels)


# PROVIDER PANEL  (NOT INCLUDED IN ADMIN)

@panels.route('/api/panel/user/groups/<string:user_id>', methods=['GET', 'POST'])
@requires_auth(access_level='provider')
def get_company_info(_payload, user_id):
    """
    Getting All Groups, with the ability to filter.
    """

    user = Users.query.filter(Users.uid == user_id).first()

    association = Association.query.filter(Association.head == user.id).first()
    associates = [u.display() for u in association.associates] if association else []

    groups = [g.adminDisplay() for g in Group.query.order_by(desc(Group.id)).filter(
        Group.status != 'pending').filter(not_(Group.on_hide)).filter(
        Group.user_id == user_id).all()]

    used_coupons = [c.display() for c in Coupon.query.order_by(desc(Coupon.id)).all() if
                    c.group.user_id == user_id and c.coupon_status == 'used']

    return jsonify({
        'groups': groups,
        'associates': associates,
        'coupons': used_coupons,
        'success': True
    })


@panels.route('/api/panel/user/groups/<string:user_id>/<int:group_id>')
@requires_auth(access_level='provider')
def delete_company_group(_payload, user_id, group_id):
    """
    Hiding A Group From The Panel.
    """

    group = Group.query.get(group_id)

    if not group:
        abort(400, {
            'msg': f'No Group Match ID #{group_id}',
            'code': 'NO_MATCH_ID'
        })

    if group.user_id != user_id:
        abort(400, {
            'msg': 'This Coupon is Not Yours To Hide',
            'code': 'NOT_YOURS'
        })

    if group.status not in ['expired', 'finished', 'canceled']:
        abort(400, {
            'msg': 'You Can Only Hide Expired Groups',
            'code': 'NOT_EXPIRED'
        })

    try:
        group.on_hide = True
        group.update()
    except Exception as e:
        abort(500, e)

    groups = [g.adminDisplay() for g in Group.query.order_by(desc(Group.id)).filter(
        Group.status != 'pending').filter(not_(Group.on_hide)).filter(Group.user_id == user_id).all()]

    return jsonify({
        'groups': groups,
        'success': True
    })


@panels.route('/api/panel/user/groups/<string:user_id>/<int:group_id>', methods=['POST'])
@requires_auth(access_level='provider')
def update_company_group(_payload, user_id, group_id):
    """
    Hiding A Group From The Panel.
    """

    group = Group.query.get(group_id)

    if not group:
        abort(400, {
            'msg': f'No Group Match ID #{group_id}',
            'code': 'NO_MATCH_ID'
        })

    if group.user_id != user_id:
        abort(400, {
            'msg': 'This Coupon is Not Yours To Hide',
            'code': 'NOT_YOURS'
        })

    if group.status == 'expired':
        abort(400, {
            'msg': 'You Can Only Update Available Groups',
            'code': 'EXPIRED'
        })

    req = request.get_json()
    coupons_plus = req.get('coupons_plus')

    if not req or not coupons_plus:
        abort(400, {
            'msg': 'Request is Not Valid',
            'code': 'INVALID_REQUEST'
        })

    try:

        new_sum = float(group.coupon_price * (int(group.coupons_num) + int(coupons_plus)))

        additional_display = int(min(math.ceil((int(new_sum) / 1000) * 24), 48))

        group.coupons_num = int(group.coupons_num) + int(coupons_plus)
        group.coupons_left = int(group.coupons_left) + int(coupons_plus)
        group.full_price = new_sum
        # Calculate End Date For Display (On Main Page)
        group.display_expire_date = group.start_date + timedelta(hours=int(additional_display))
        group.update()

        # Create A History
        create_history(
            entity=group,
            entity_type="Groups",
            record_state="succeed",
            record_type="additional_coupons",
            params={
                'new_sum': new_sum,
                'new_coupons': coupons_plus,
                'additionalDis': min(additional_display, 48)
            }
        )
    except Exception as e:
        abort(500, e)

    groups = [g.adminDisplay() for g in Group.query.order_by(desc(Group.id)).filter(
        Group.status != 'pending').filter(not_(Group.on_hide)).filter(Group.user_id == user_id).all()]

    return jsonify({
        'groups': groups,
        'success': True
    })


@panels.route('/api/panel/search/associates', methods=['POST'])
@requires_auth(access_level='provider')
def search_for_associates(_payload):
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
        )).filter(Users.is_active).all() if u.username != current_user.username and u.guid == USER]

    return jsonify({
        'users': searched_users,
        'length': len(searched_users),
        'success': True
    })


@panels.route('/api/panel/association/<int:user_id>', methods=['POST'])
@requires_auth(access_level='provider')
def set_association(_payload, user_id):
    if not current_user.is_authenticated:
        abort(400, {
            'msg': 'You Must Log-in First',
            'code': 'LOGIN_REQUIRED'
        })

    req = request.get_json()
    associate = req.get('accosiate')

    if not req or not associate:
        abort(400, {
            'msg': 'You Must Provide A Valid Request',
            'code': 'INVALID_REQUEST'
        })

    user = Users.query.get(associate)

    if not user:
        abort(400, {
            'msg': f'No User match ID #{associate}',
            'code': 'NO_USER'
        })

    association = Association.query.filter(Association.head == user_id).first()
    try:
        if not association:
            new_association = Association(
                head=user_id,
                company=current_user.company
            )

            new_association.insert()
            user.association_id = new_association.id
            user.guid = ASSOCIATE
            user.is_associate = True

            user.update()
        else:
            user.association_id = association.id
            user.is_associate = True
            user.guid = ASSOCIATE
            user.update()
    except Exception as e:
        abort(500, e)

    return jsonify({
        'success': True
    })


@panels.route('/api/panel/association/<int:user_id>/remove/<int:associate>')
@requires_auth(access_level='provider')
def remove_associate(_payload, user_id, associate):
    if not current_user.is_authenticated:
        abort(400, {
            'msg': 'You Must Log-in First',
            'code': 'LOGIN_REQUIRED'
        })

    user = Users.query.get(associate)

    if not user:
        abort(400, {
            'msg': f'No User match ID #{associate}',
            'code': 'NO_USER'
        })

    association = Association.query.filter(Association.head == user_id).first()

    if not association:
        abort(400, {
            'msg': 'No Association Found',
            'code': 'NO_ASSOCIATION'
        })

    if user not in association.associates:
        abort(400, {
            'msg': 'No Associate Found',
            'code': 'NO_ASSOCIATE'
        })

    try:
        user.association_id = None
        user.is_associate = False
        user.guid = USER
        user.update()
    except Exception as e:
        abort(500, e)

    return jsonify({
        'success': True
    })

# PROVIDER PANEL  (NOT INCLUDED IN ADMIN)


# Admins

@panels.route('/api/panel/user/admins', methods=['GET'])
@requires_auth(access_level='admin')
def get_admin_permissions(_payload):
    if not current_user.is_authenticated:
        abort(400, {
            'msg': 'User is not Logged-in',
            'code': 'NOT_LOGGED_IN'
        })

    return jsonify({
        'permissions': current_user.getPermissions(),
        'success': True
    })

# Admins
