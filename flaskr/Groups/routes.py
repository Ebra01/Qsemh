import os
from sqlalchemy import not_, desc, cast, Integer, or_, func
from datetime import datetime, timedelta
from ast import literal_eval
from flask_login import current_user
from flask import Blueprint, request, jsonify, abort
from flaskr.Models.models import Group, Coupon, Users
from .utils import upload_images, delete_images

# For Authentication
from flaskr.Auth.auth import requires_auth, requires_perms

# Create History
from flaskr.History.routes import create_history

groups = Blueprint('groups', __name__)


# Get All Groups *Customize To Show Group in Specific Order*
@groups.route('/api/groups', methods=['POST'])
def get_groups():
    # Get Query Request
    req = request.get_json()

    user = req.get('user')

    # Customize Query Block
    limit = int(os.getenv('MAIN_QUERY'))
    # This Query is Customized To Order itself by 'full_price' & Take only first 'limit' results.
    # This Query Has The Following Conditions :
    # 1) Status Positive (Not Expired or On Pending)
    # 2) Start Date < Current Date
    # 3) Expire Date > Current Date
    # 4) Display Expire Date > Current Date (Only For Main Page)
    current_date = datetime.now()
    group_query = Group.query.order_by(desc(cast(Group.full_price, Integer))).order_by(
        desc(cast(Group.coupons_left, Integer))).filter(
        not_(Group.status.in_(['expired', 'pending', 'canceled', 'finished']))).filter(not_(Group.on_hide))

    if user and user.get('country'):
        group_query = group_query.filter(Group.country == user.get('country'))

    filtered_groups = [g for g in group_query if
                       g.expire_date > current_date > g.start_date]

    limited_groups = [g.display() for g in filtered_groups[:limit]]

    # End Customize Query Block

    return jsonify({
        'groups': limited_groups,
        'success': True
    })


# Get All Groups * Using Search & Filters Options *
@groups.route('/api/groups/all', methods=['POST'])
def get_all_groups():
    current_date = datetime.now()

    # Get Query Request
    req = request.get_json()

    user = req.get('user')

    search = req.get('search')
    group_type = req.get('coupon_type')
    group_branch = req.get('city')
    group_price = req.get('price')
    group_amount = req.get('amount')

    if not search and not group_type and not group_branch\
            and not group_price and not group_amount:
        filteredQuery = Group.query.order_by(desc(cast(Group.full_price, Integer))).order_by(
            desc(cast(Group.coupons_left, Integer))).filter(
            not_(Group.status.in_(['expired', 'pending', 'canceled', 'finished']))).filter(
            Group.expire_date > current_date).filter(Group.start_date < current_date).filter(
            not_(Group.on_hide))

        if user and user.get('country'):
            filteredQuery = filteredQuery.filter(Group.country == user.get('country'))

    else:

        filteredQuery = Group.query.filter(
            not_(Group.status.in_(['expired', 'pending', 'canceled', 'finished']))).filter(
            Group.expire_date > current_date).filter(
            Group.start_date < current_date).filter(not_(Group.on_hide))

        if user and user.get('country'):
            filteredQuery = filteredQuery.filter(Group.country == user.get('country'))

        # Apply All Filters.
        if search:
            searchTerm = search.lower()
            filteredQuery = filteredQuery.filter(or_(
                func.lower(Group.description).contains(searchTerm),
                func.lower(Group.company).contains(searchTerm),
                func.lower(Group.coupon_type).contains(searchTerm)
            ))

        if group_price:
            if group_price == 'highest':
                filteredQuery = filteredQuery.order_by(desc(cast(Group.coupon_price, Integer)))
            if group_price == 'lowest':
                filteredQuery = filteredQuery.order_by(cast(Group.coupon_price, Integer))

        if group_amount:
            if group_amount == 'available':
                filteredQuery = filteredQuery.filter(Group.coupons_left > 0).order_by(
                    desc(cast(Group.coupons_left, Integer)))
            if group_amount == 'highest':
                filteredQuery = filteredQuery.order_by(desc(cast(Group.coupons_left, Integer)))
            if group_amount == 'lowest':
                filteredQuery = filteredQuery.order_by(cast(Group.coupons_left, Integer))

        if group_type:
            # Normal Filteration
            filteredQuery = filteredQuery.order_by(
                desc(cast(Group.full_price, Integer))).order_by(
                desc(cast(Group.coupons_left, Integer)))

            # Filter By Type
            filteredQuery = filteredQuery.filter(Group.coupon_type.ilike(group_type))

        if group_branch:
            # Filter Using a Unique Method to scan
            # Group's Branches against Given Branches

            # Normal Filteration
            filteredQuery = filteredQuery.order_by(
                desc(cast(Group.full_price, Integer))).order_by(
                desc(cast(Group.coupons_left, Integer)))

            # Filter By City
            filteredQuery = [
                g for g in filteredQuery.all()
                if group_branch in [b.get('city') for b in literal_eval(g.branches)]
            ]

        if not group_amount and not group_price and not group_type and \
                not group_branch and not search:
            filteredQuery = filteredQuery.order_by(
                desc(cast(Group.full_price, Integer))).order_by(
                desc(cast(Group.coupons_left, Integer)))

    try:
        groups_ = [g.display() for g in filteredQuery.all()]
    except AttributeError:
        groups_ = [g.display() for g in filteredQuery]

    return jsonify({
        'groups': groups_,
        'success': True
    })


# Get One Group By ID
@groups.route('/api/groups/<int:group_id>')
def get_group(group_id):
    group = Group.query.filter_by(id=group_id).first()

    if not group:
        abort(404, {
            'msg': f'No Group with ID #{group_id}',
            'code': 'NO_MATCH_ID'
        })

    try:
        if current_user.is_authenticated:
            view_list = literal_eval(group.unique_views or "[]")
            if current_user.id not in view_list:
                view_list.append(current_user.id)
                group.unique_views = str(view_list)

        group.views += 1
        group.update()
    except Exception as e:
        print(e)

    return jsonify({
        'group': group.display(),
        'success': True
    })


# Get One Group By ID
@groups.route('/api/groups/<int:group_id>/admin')
@requires_perms(permission='ADS')
@requires_auth(access_level='admin')
def get_group_admin(_payload0, _payload1, group_id):

    if not current_user.is_authenticated:
        abort(400, {
            'msg': 'User Must be logged-in',
            'code': 'NO_USER'
        })

    group = Group.query.filter_by(id=group_id).first()
    # Temp
    users = Users.query.filter(Users.id.in_(literal_eval(group.receivers))).all()

    if not group:
        abort(404, {
            'msg': f'No Group with ID #{group_id}',
            'code': 'NO_MATCH_ID'
        })

    return jsonify({
        'group': group.display(),
        'receivers': [u.claimedDisplay(group_id) for u in users],
        'success': True
    })


# Create A New Group By Providing a Valid Request Body
# And Create A New Set of Coupons Linked to This Group.
@groups.route('/api/groups/create', methods=['POST'])
@requires_auth(access_level='provider')
def create_group(_payload):
    if not current_user.is_authenticated:
        abort(400, {
            'msg': 'Not Logged In',
            'code': 'LOGIN_REQUIRED'
        })

    req = request.get_json()

    if not req:
        abort(400, {
            'msg': 'You Must Provide A Valid Request',
            'code': 'INVALID_REQUEST'
        })

    if not current_user.company:
        abort(400, {
            'msg': 'Current User Has No Company',
            'code': 'NO_COMPANY'
        })

    if not current_user.country:
        abort(400, {
            'msg': 'Current User Has No Country',
            'code': 'NO_COUNTRY'
        })

    coupons_num = req.get('coupons_num')
    coupon_price = req.get('coupon_price')
    coupon_type = req.get('coupon_type')
    start = req.get('start')
    expire_days = req.get('expire')  # Default to 10 days added to start_date
    country = current_user.country
    branches = req.get('branches')
    description = req.get('description')
    offset = req.get('offset')
    onsite = req.get("onsite")

    # set Ad Images
    images = []
    try:
        user_main_ad_image = current_user.main_ad_image
        images = literal_eval(current_user.ad_images)
        images.insert(0, user_main_ad_image)
    except Exception as e:
        print(e)

    if not images:
        abort(400, {
            'msg': 'No Images To Display',
            'code': 'NO_IMAGES'
        })

    # For Coupons Set
    coupon_code = req.get('coupon_code')

    # Check For Missing Values
    if not coupon_price or not coupons_num or not start or not coupon_type \
            or not country or not branches or not description or not coupon_code:
        abort(400, {
            'msg': 'You Must Provide All Important Values',
            'code': 'MISSING_VALUES'
        })

    # Creating A new Group
    GROUP_ID = None
    try:
        full_price = int(coupons_num) * float(coupon_price)
        # start_date = start.replace('T', ' ')
        # start_date = datetime.strptime(start_date, "%Y-%m-%d %H:%M")
        start_date = datetime.fromisoformat(start) + timedelta(minutes=int(offset))
        expire = 10 if expire_days == '0' else int(expire_days)
        new_group = Group(
            company=str(current_user.company),
            coupon_price=coupon_price,
            coupons_num=coupons_num,
            coupon_code=coupon_code,
            coupon_type=coupon_type,
            start_date=start_date,
            expire=expire,
            images=str(images),
            country=str(country),
            branches=str(branches),
            description=str(description),
            full_price=str(full_price),
            user_id=current_user.uid,
            onsite=int(onsite)
        )
        new_group.insert()
        GROUP_ID = new_group.id

        # Create A History
        create_history(
            entity=new_group,
            entity_type="Groups",
            record_state="succeed",
            record_type="new_group"
        )
    except Exception as e:
        print(e)
        abort(500, e)

    return jsonify({
        'groupID': GROUP_ID,
        'success': True
    })


# Check if Provider have the currect amount of balance
@groups.route('/api/groups/balance', methods=['POST'])
@requires_auth(access_level='provider')
def check_balance(_payload):
    if not current_user.is_authenticated:
        abort(400, {
            'msg': 'Not Logged In',
            'code': 'LOGIN_REQUIRED'
        })

    req = request.get_json()
    full_price = req.get("full_price")

    if not req or not full_price:
        abort(400, {
            'msg': 'You Must Provide A Valid Request',
            'code': 'INVALID_REQUEST'
        })

    eligible = True
    try:
        if current_user.check_balance:
            if current_user.balance < float(full_price):
                eligible = False
    except Exception as e:
        abort(500, e)

    return jsonify({
        'success': True,
        'eligible': eligible,
        'user_balance': current_user.balance
    })


@groups.route('/api/images', methods=['POST'])
@requires_auth(access_level='provider')
def upload_images_s3(_payload):

    # User
    user = Users.query.filter(Users.email == _payload.get("email")).first()
    user_main_ad = user.main_ad_image
    user_ad_images = literal_eval(user.ad_images)

    images = request.files

    if not images:
        abort(400, {
            'msg': 'You Must Provide A Valid Request',
            'code': 'INVALID_REQUEST'
        })

    prev_images = []
    try:

        for name in images:
            img = images.get(name)
            try:
                filename = upload_images(img)
                if name == "imagePrimary":
                    user_main_ad = filename
                else:
                    if len(user_ad_images) == 3:
                        prev_images.append(user_ad_images[0])

                        user_ad_images = user_ad_images[1:]
                        user_ad_images.append(filename)
                    else:
                        user_ad_images.append(filename)
            except Exception as e:
                print(e)

        user.main_ad_image = user_main_ad
        user.ad_images = str(user_ad_images)
        user.update()

        # Delete Previous Images
        for img in prev_images:
            delete_images(img)

    except Exception as e:
        abort(500, e)

    return jsonify({
        'success': True,
        'user': user.display()
    })


@groups.route('/api/images/<string:image_name>')
@requires_auth(access_level='provider')
def remove_ad_images(_payload, image_name):

    # User
    user = Users.query.filter(Users.email == _payload.get("email")).first()
    user_ad_images = literal_eval(user.ad_images)

    if image_name == user.main_ad_image:
        abort(400, {
            'msg': 'You Cannot Delete The Main Ad Image',
            'code': 'MAIN_AD_IMAGE'
        })
    # Delete Images
    try:
        user_ad_images.remove(image_name)

        user.ad_images = str(user_ad_images)
        user.update()

        # Delete Images From AWS S3
        delete_images(image_name)
    except Exception as e:
        abort(500, e)

    return jsonify({
        'user': user.display(),
        'success': True
    })


# Requesting Coupons
@groups.route('/api/groups/request/<int:group_id>', methods=['POST'])
@requires_auth(access_level='customer')
def request_coupon(_payload, group_id):
    if not current_user.is_authenticated:
        abort(400, {
            'msg': 'You Have To Be Logged-In First',
            'code': 'LOGIN_REQUIRED'
        })

    if current_user.disabled:
        abort(400, {
            'msg': 'Your Account is Disabled',
            'code': 'DISABLED'
        })

    group = Group.query.get(group_id)

    # Check if Group is Available
    if not group:
        abort(404, {
            'msg': f'No Group Match ID #{group_id}',
            'code': 'NO_MATCH_ID'
        })

    # Check if Coupon is Available
    if group.status != 'available':
        abort(400, {
            'msg': 'Group is UnClaimable',
            'code': 'UNCLAIMABLE'
        })

    user_id = current_user.id

    # Check if There's a User Logged-in
    if not user_id:
        abort(400, {
            'msg': 'No ID\'s Provided',
            'code': 'SERVER'
        })

    # Check if User is the Owner
    if current_user.uid == group.user_id:
        abort(400, {
            'msg': 'You Can\'t Request Your Own Coupon',
            'code': 'ITS_YOUR_COUPON'
        })

    # Check for country match
    if current_user.country != group.country:
        abort(400, {
            "msg": "User Country Doesn't match Group Country",
            "code": "COUNTRY_ERROR"
        })

    req = request.get_json()

    request_type = req.get('request_type')
    try:
        if request_type == 'display':
            request_coupon_on_display(group=group, user_id=user_id)
        elif request_type == 'request':
            request_coupon_on_request(group=group, user_id=user_id)
        else:
            abort(400, {
                'msg': 'Request Type is Not Valid',
                'code': 'INVALID_TYPE'
            })
    except Exception as e:
        print(e)
        abort(500, e)

    return jsonify({
        'success': True
    })


def request_coupon_on_display(group, user_id):
    try:
        user = Users.query.get(user_id)
        is_expired = group.distribute_end_date < datetime.now()
        claimants = literal_eval(group.claimants)

        if is_expired:
            # Create A History
            create_history(
                entity_type="Users",
                entity=user,
                record_state="failed",
                record_type="coupon_request_on_display",
                error_key="COUPONS_DISPLAY_SIGNING_EXPIRED",
                params={
                    "group": group.coupon_code,
                    "group_id": group.id
                }
            )
            raise Exception({
                'msg': 'Registeration Time is Over',
                'code': 'SING_UPS_EXPIRED'
            })

        # Check if User Has Claimed A Coupon in The Past 24Hrs
        if user.claimed_today:
            # Create A History
            create_history(
                entity_type="Users",
                entity=user,
                record_state="failed",
                record_type="coupon_request_on_display",
                error_key="COUPONS_DISPLAY_USER_CLAIMED",
                params={
                    "group": group.coupon_code,
                    "group_id": group.id
                }
            )
            raise Exception({
                'msg': f'User #{user_id} Claimed A Coupon Today',
                'code': 'HAS_CLAIMED'
            })

        if user_id in claimants:
            # Create A History
            create_history(
                entity_type="Users",
                entity=user,
                record_state="failed",
                record_type="coupon_request_on_display",
                error_key="COUPONS_DISPLAY_ALREADY_REGISTERED",
                params={
                    "group": group.coupon_code,
                    "group_id": group.id
                }
            )
            raise Exception({
                'msg': 'You Signed Up For This Coupon Already',
                'code': 'ALREADY_SIGNED_UP'
            })

        claimants.append(user_id)
        group.claimants = str(claimants)
        group.update()

        user.claimed_today = True
        user.claim_date = datetime.now()
        user.update()

        # Create A History
        create_history(
            entity_type="Users",
            entity=user,
            record_state="succeed",
            record_type="coupon_request_on_display",
            params={
                "group": group.coupon_code,
                "group_id": group.id
            }
        )

    except Exception as e:
        raise Exception(e)


def request_coupon_on_request(group, user_id):
    try:
        user = Users.query.get(user_id)

        if int(group.coupons_left) == 0:
            # Create A History (User)
            create_history(
                entity_type="Users",
                entity=user,
                record_state="failed",
                record_type="coupon_request_on_request",
                error_key="COUPONS_REQUEST_ZERO",
                params={
                    "group": group.coupon_code,
                    "group_id": group.id
                }
            )
            raise Exception({
                'msg': 'No Coupons Left',
                'code': 'NO_COUPON'
            })

        # Check if User Has Claimed A Coupon in The Past 24Hrs
        if user.claimed_today:
            # Create A History (User)
            create_history(
                entity_type="Users",
                entity=user,
                record_state="failed",
                record_type="coupon_request_on_request",
                error_key="COUPONS_REQUEST_CLAIMED",
                params={
                    "group": group.coupon_code,
                    "group_id": group.id
                }
            )
            raise Exception({
                'msg': f'User #{user_id} Claimed A Coupon Today',
                'code': 'HAS_CLAIMED'
            })

        receivers = literal_eval(group.receivers)
        claimants = literal_eval(group.claimants)

        # Check if this User Has Received The Coupon Already
        if user_id in receivers:
            # Create A History (User)
            create_history(
                entity_type="Users",
                entity=user,
                record_state="failed",
                record_type="coupon_request_on_request",
                error_key="COUPONS_REQUEST_RECEIVED",
                params={
                    "group": group.coupon_code,
                    "group_id": group.id
                }
            )
            raise Exception({
                'msg': f'User #{user_id} Has Received This Coupon Already!',
                'code': 'HAS_A_COUPON'
            })
        # Create A New Coupon With User ID
        new_coupon = Coupon(
            coupon_code=group.coupon_code,
            group_id=group.id,
            user_id=user_id
        )
        new_coupon.insert()

        # Add This User To Receivers List
        receivers.append(user_id)
        claimants.append(user_id)

        # Update Group Coupons Number & Receivers List
        number_of_coupon = int(group.coupons_left)
        number_of_coupon -= 1

        group.coupons_left = number_of_coupon
        group.receivers = str(receivers)
        group.claimants = str(claimants)
        group.update()

        # Update User Coupon Limit Status
        user.claimed_today = True
        user.claim_date = datetime.now()
        user.update()
        # Create A History (User)
        create_history(
            entity_type="Users",
            entity=user,
            record_state="succeed",
            record_type="coupon_request_on_request_received",
            params={
                "group": group.coupon_code,
                "qr_code": new_coupon.qr_code,
                "group_id": group.id
            }
        )
        # Create A History (Coupon)
        create_history(
            entity_type="Coupons",
            entity=new_coupon,
            record_state="succeed",
            record_type="coupon_received_on_request",
            params={
                "user": user.username,
                "qr_code": new_coupon.qr_code
            }
        )
    except Exception as e:
        raise Exception(e)
