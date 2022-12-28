from flask import Blueprint, jsonify, abort, request
from flaskr.Models.models import History, Notifications, Users
from flaskr.Auth.auth import requires_auth
from sqlalchemy import or_, func, desc, String, cast
from ast import literal_eval

from datetime import datetime, timedelta
from flaskr.utils import sendNotifications

history = Blueprint("history", __name__)


# Get All/Filtered Histories
@history.route('/api/histories', methods=['GET', 'POST'])
@requires_auth(access_level="superadmin")
def get_histories(_payload):
    """
        Return All Histories registered in the Database Or
        Only Filtered Histories Entered by Admin
    """
    filteredQuery = History.query.order_by(desc(History.id))

    if request.method == 'POST':
        # Get Query Request
        req = request.get_json()

        search = req.get('search')
        search_id = req.get('search_id')
        entity_type = req.get('entity_type')
        record_type = req.get('record_type')
        record_state = req.get('record_state')
        start_date = req.get('start_date')
        end_date = req.get('end_date')
        offset = req.get('offset')

        # Apply all Filters
        try:
            # KeyWord in History object
            if search:
                searchTerm = search.lower()
                filteredQuery = filteredQuery.filter(or_(
                    cast(History.id, String) == search_id,
                    func.lower(History.entity_type).contains(searchTerm),
                    func.lower(History.record).contains(searchTerm),
                    func.lower(History.record_type).contains(searchTerm),
                    func.lower(History.record_state).contains(searchTerm)
                ))

            # By ID
            if search_id:
                filteredQuery = filteredQuery.filter(cast(
                    History.entity_id, String) == search_id)

            # Entity Type (Users, Groups, Coupons, or Offers)
            if entity_type:
                filteredQuery = filteredQuery.filter(History.entity_type == entity_type)

            # Record Type (Multiple for each Entity Type)
            if record_type:
                filteredQuery = filteredQuery.filter(History.record_type == record_type)

            # Record State (Succeed, Failed)
            if record_state:
                filteredQuery = filteredQuery.filter(History.record_state == record_state)

            # Start/End Date Filtering
            if start_date and not end_date:
                startDate = datetime.fromisoformat(start_date) + timedelta(minutes=int(offset))
                filteredQuery = filteredQuery.filter(History.date >= startDate)

            elif end_date and not start_date:
                endDate = datetime.fromisoformat(end_date) + timedelta(minutes=int(offset))
                filteredQuery = filteredQuery.filter(History.date <= endDate)

            elif end_date and start_date:
                startDate = datetime.fromisoformat(start_date) + timedelta(minutes=int(offset))
                endDate = datetime.fromisoformat(end_date) + timedelta(minutes=int(offset))
                filteredQuery = filteredQuery.filter(History.date >= startDate) \
                    .filter(History.date <= endDate)
        except Exception as e:
            abort(500, e)

    histories = [h.display() for h in filteredQuery.all()]

    return jsonify({
        'histories': histories,
        'success': True
    })


# Extract Histories
@history.route('/api/histories/extract', methods=['GET', 'POST'])
@requires_auth(access_level='superadmin')
def extract_histories(_payload):
    """
        Return All Histories registered in the Database Or
        Only Filtered Histories Entered by Admin in One Line to Copy.
    """
    filteredQuery = History.query.order_by(desc(History.id))

    # Get Query Request
    req = request.get_json()

    search = req.get('search')
    search_id = req.get('search_id')
    entity_type = req.get('entity_type')
    record_type = req.get('record_type')
    record_state = req.get('record_state')
    start_date = req.get('start_date')
    end_date = req.get('end_date')
    offset = req.get('offset')

    # Apply all Filters
    try:
        # KeyWord in History object
        if search:
            searchTerm = search.lower()
            filteredQuery = filteredQuery.filter(or_(
                cast(History.id, String) == search_id,
                func.lower(History.entity_type).contains(searchTerm),
                func.lower(History.record).contains(searchTerm),
                func.lower(History.record_type).contains(searchTerm),
                func.lower(History.record_state).contains(searchTerm)
            ))

        # By ID
        if search_id:
            filteredQuery = filteredQuery.filter(cast(
                History.entity_id, String) == search_id)

        # Entity Type (Users, Groups, Coupons, or Offers)
        if entity_type:
            filteredQuery = filteredQuery.filter(History.entity_type == entity_type)

        # Record Type (Multiple for each Entity Type)
        if record_type:
            filteredQuery = filteredQuery.filter(History.record_type == record_type)

        # Record State (Succeed, Failed)
        if record_state:
            filteredQuery = filteredQuery.filter(History.record_state == record_state)

        # Start/End Date Filtering
        if start_date and not end_date:
            startDate = datetime.fromisoformat(start_date) + timedelta(minutes=int(offset))
            filteredQuery = filteredQuery.filter(History.date >= startDate)

        elif end_date and not start_date:
            endDate = datetime.fromisoformat(end_date) + timedelta(minutes=int(offset))
            filteredQuery = filteredQuery.filter(History.date <= endDate)

        elif end_date and start_date:
            startDate = datetime.fromisoformat(start_date) + timedelta(minutes=int(offset))
            endDate = datetime.fromisoformat(end_date) + timedelta(minutes=int(offset))
            filteredQuery = filteredQuery.filter(History.date >= startDate) \
                .filter(History.date <= endDate)
    except Exception as e:
        abort(500, e)

    records = ""
    histories = [h.oneLine(offset) for h in filteredQuery.all()]

    for h in histories:
        records += f"{h}\n\n"

    return jsonify({
        'records': records,
        'success': True
    })


# Register a new History
def create_history(entity_type, entity, record_type,
                   record_state, error_key=None, params=None):
    """
    * entity_type: User, Group, Coupon, or Offer
    * entity: The Object of the entity itself.
    * Records Structure:
        records = {
            'record_key': {
                'record_type': "value",
                'record_message': String contain the record (as a message)
            }
        }
    """

    if params is None:
        params = {}

    if entity_type == 'Users':
        records = {
            # # # USERS
            "activated": {
                "type": 'تفعيل الحساب',
                "record": f"تم تفعيل الحساب للمستخدم {entity.username}."
            },
            # Login/Logout
            "login": {
                "type": 'تسجيل الدخول',
                "record": f"قام المستخدم {entity.username} بمحاولة تسجيل الدخول."
            },
            "logout": {
                "type": 'تسجيل الخروج',
                "record": f"قام المستخدم {entity.username} بمحاولة تسجيل الخروج."
            },
            # Password Reset
            "reset_password_out_request": {
                "type": 'طلب تغيير كلمة المرور',
                "record": f"قام المستخدم {entity.username} بطلب تغيير كلمة المرور من صفحة الدخول."
            },
            "reset_password_out": {
                "type": 'تغيير كلمة المرور',
                "record": f"قام المستخدم {entity.username} بمحاولة تغيير كلمة المرور من صفحة الدخول."
            },
            "reset_password_in": {
                "type": 'تغيير كلمة المرور',
                "record": f"قام المستخدم {entity.username} بتغيير كلمة المرور من صفحة الإعدادات."
            },
            # User Updates
            "update_user_fullname": {
                "type": "تغيير الإسم الشخصي",
                "record": f"قام المستخدم {entity.username} بتغيير الإسم الشخصي من "
                          f"{params.get('old_fullname')} إلى {params.get('new_fullname')}. "
            },
            "update_user_country_city": {
                "type": "تغيير الدولة والمدينة",
                "record": f"قام المستخدم {entity.username} بتغيير الدولة من {params.get('old_country')} إلى "
                          f"{params.get('new_country')}, والمدينة من "
                          f"{params.get('old_city')} إلى {params.get('new_city')}."
            },
            "reset_user_profile_img": {
                "type": "تغيير الصورة الشخصية",
                "record": f"قام المستخدم {entity.username} بتغيير الصورة الشخصية."
            },
            "reset_user_email": {
                "type": "تغيير البريد الإلكتروني",
                "record": f"قام المستخدم {entity.username} بمحاولة تغيير البريد الإلكتروني "
                          f"من {params.get('old_email')} إلى {params.get('new_email')}."
            },
            "ticket_to_provider": {
                "type": "طلب تحويل الحساب لمعلن",
                "record": f"قام المستخدم {entity.username} بطلب تحويل حسابه لمعلن."
            },
            # Gifting
            "send_coupon_attempt": {
                "type": "إهداء القسيمة",
                "record": f"قام المستخدم {params.get('sender')} بمحاولة إهداء القسيمة {params.get('coupon_code')}."
            },
            "send_coupon": {
                "type": "إهداء القسيمة",
                "record": f"قام المستخدم {params.get('sender')} بإهداء المستخدم {params.get('receiver')}"
                          f" القسيمة {params.get('coupon_code')}, "
                          f"تم تحويل الـ QRCode من {params.get('old_qr_code')} إلى {params.get('new_qr_code')}."
            },
            "receive_coupon": {
                "type": "إستقبال القسيمة",
                "record": f"قام المستخدم {params.get('receiver')} بإستقبال القسيمة (هدية) {params.get('coupon_code')}"
                          f" من المستخدم {params.get('sender')}, تم تحويل الـ QRCode من "
                          f"{params.get('old_qr_code')} إلى {params.get('new_qr_code')}."
            },
            # Selling
            "sell_coupon_attempt": {
                "type": "محاولة بيع القسيمة",
                "record": f"قام المستخدم {params.get('seller')} بمحاولة بيع القسيمة {params.get('coupon_code')}"
                          f" ذات القيمة {params.get('coupon_price')}$."
            },
            "sell_coupon": {
                "type": "محاولة بيع القسيمة",
                "record": f"قام المستخدم {params.get('seller')} بمحاولة بيع القسيمة {params.get('coupon_code')}"
                          f" ذات القيمة {params.get('coupon_price')}$ بمبلغ {params.get('offer_price')}$."
            },
            # Buying
            "buy_coupon_attempt": {
                'type': 'محاولة شراء القسيمة',
                'record': f"قام المستخدم {params.get('buyer')}"
                          f" بمحاولة شراء القسيمة {params.get('coupon_code')} من المستخدم {params.get('seller')}"
            },
            "buy_coupon_seller": {
                'type': "بيع القسيمة",
                'record': f"قام المستخدم {params.get('seller')} ببيع القسيمة {params.get('coupon_code')}"
                          f" بمبلغ {params.get('offer_price')}$ تم تحويل {params.get('money_gain')}$"
                          f" منها لحساب البائع ليصبح رصيده {params.get('seller_balance')}$, وتم تغيير الـ"
                          f" QRCode من {params.get('old_qr_code')} إلى {params.get('new_qr_code')}."
            },
            "buy_coupon_buyer": {
                'type': "شراء القسيمة",
                'record': f"قام المستخدم {params.get('buyer')} بشراء القسيمة {params.get('coupon_code')}"
                          f" بمبلغ {params.get('offer_price')}$ من المستخدم {params.get('seller')},"
                          f" تم خصم المبلغ {params.get('money_lost')}$ من حساب المشتري ليصبح رصيده "
                          f"{params.get('buyer_balance')}$, وتم تغيير الـ"
                          f" QRCode من {params.get('old_qr_code')} إلى {params.get('new_qr_code')}."
            },
            # Canceling Offer
            "cancel_offer": {
                'type': "محاولة إلغاء العرض",
                'record': f"قام المستخدم {entity.username} بمحاولة إلغاء العرض للقسيمة {params.get('coupon_code')}."
            },
            # Balance Requests
            # Paypal
            "paypal_balance_request": {
                "type": "طلب إضافة رصيد بالبايبال",
                "record": f"قام المستخدم {entity.username} بطلب إضافة رصيد بقيمة "
                          f"{params.get('amount')}$, (الرصيد الحالي: {params.get('current_balance')}$), "
                          f"(الرصيد بعد الإضافة: {params.get('new_balance')}$)."
            },
            "paypal_balance_error": {
                "type": "طلب إضافة رصيد بالبايبال",
                "record": f"قام المستخدم {entity.username} بطلب إضافة رصيد بقيمة "
                          f"{params.get('amount')}$, (الرصيد الحالي: {params.get('current_balance')}$)."
            },
            # Bank
            "bank_balance_request": {
                "type": "طلب إضافة رصيد بالتحويل البنكي",
                "record": f"قام المستخدم {entity.username} بطلب إضافة رصيد بقيمة "
                          f"{params.get('amount')}$, (الرصيد الحالي: {params.get('current_balance')}$), "
                          f"(الرصيد المتوقع بعد قبول طلب الإضافة: {params.get('new_balance')}$)."
            },
            "bank_balance_accept": {
                "type": "طلب إضافة رصيد بالتحويل البنكي مقبول",
                "record": f"تمت الموافقة على طلب المستخدم {entity.username} لإضافة رصيد بقيمة "
                          f"{params.get('amount')}$, تم إضافة {params.get('added_amount')}$"
                          f" لرصيد المستخدم من قبل الإدارة (الرصيد الحالي: {params.get('current_balance')}$), "
                          f"(الرصيد بعد الإضافة: {params.get('new_balance')}$)."
            },
            "bank_balance_reject": {
                "type": "طلب إضافة رصيد بالتحويل البنكي مرفوض",
                "record": f"تم رفض طلب المستخدم {entity.username} لإضافة رصيد بقيمة "
                          f"{params.get('amount')}$, (الرصيد الحالي: {params.get('current_balance')}$)."
            },
            # Account Information Changes (From Admin Panel)
            "user_balance_change": {
                "type": "تعديل بيانات المستخدم",
                "record": f"تم تعديل رصيد المستخدم {entity.username} من قبل الإدارة, "
                          f"(الرصيد السابق {params.get('old_balance')}$), (الرصيد الحالي {entity.balance}$)."
            },
            "user_phone_change": {
                "type": "تعديل بيانات المستخدم",
                "record": f"تم تعديل رقم جوال المستخدم {entity.username} من قبل الإدارة, "
                          f"رقم الجوال السابق {params.get('old_phone')} رقم الجوال الحالي {entity.phone}."
            },
            "user_username_change": {
                "type": "تعديل بيانات المستخدم",
                "record": f"تم تغيير إسم المستخدم للمستخدم ID#{entity.id} من قبل الإدارة, "
                          f"من {params.get('old_username')} إلى {entity.username}."
            },
            "user_country_change": {
                "type": "تعديل بيانات المستخدم",
                "record": f"تم تغيير الدولة الخاصة بالمستخدم {entity.username} من قبل الإدارة, "
                          f"من {params.get('old_country')} إلى "
                          f"{entity.country} وتم إعادة تعيين المدينة لـ(غير محدد)."
            },
            "user_balance_checking_activated": {
                'type': "تفعيل التحقق من رصيد المعلن",
                'record': f"تم تفعيل التحقق من رصيد المعلن قبل إضافة إعلان جديد للمعلن "
                          f"{entity.username} للشركة {entity.company}."
            },
            "user_balance_checking_deactivated": {
                'type': "إلغاء تفعيل التحقق من رصيد المعلن",
                'record': f"تم إلغاء تفعيل التحقق من رصيد المعلن قبل إضافة إعلان جديد للمعلن "
                          f"{entity.username} للشركة {entity.company}."
            },
            # Access Level Changes (From Admin Panel)
            "user_to_provider": {
                'type': "ترقية رتبة المستخدم",
                'record': f"تم تغيير رتبة المستخدم {entity.username} من مستخدم عادي إلى معلن للشركة {entity.company}."
            },
            "user_to_admin": {
                'type': "ترقية رتبة المستخدم",
                'record': f"تم تغيير رتبة المستخدم {entity.username} من مستخدم عادي إلى إداري."
            },
            "admin_to_user": {
                'type': "سحب رتبة المستخدم",
                'record': f"تم سحب رتبة الإداري من المستخدم {entity.username} من طرف الإدارة."
            },
            "provider_to_user": {
                'type': "سحب رتبة المستخدم",
                'record': f"تم سحب رتبة المعلن من المستخدم {entity.username} لشركة "
                          f"{params.get('company')} من طرف الإدارة."
            },
            "user_company_change": {
                'type': "تغيير إسم الشركة",
                'record': f"تم تغيير إسم الشركة للمستخدم {entity.username} من طرف الإدارة, "
                          f"من {params.get('old_company')} إلى {entity.company}."
            },
            # Coupon Request (On Display)
            "coupon_request_on_display": {
                "type": "طلب الحصول على القسيمة (التوزيع العشوائي)",
                "record": f"قام المستخدم {entity.username}"
                          f" بطلب المشاركة في التوزيع العشوائي على القسيمة {params.get('group')} "
                          f"ذات رقم المعرف (ID {params.get('group_id')}#)."
            },
            "coupon_request_on_display_received": {
                "type": "طلب الحصول على القسيمة (التوزيع العشوائي)",
                "record": f"قام المستخدم {entity.username} بالحصول على القسيمة {params.get('group')},"
                          f" رمز الـ QRCode الخاص به هو {params.get('qr_code')}."
            },
            # Coupon Request (On Request)
            "coupon_request_on_request": {
                "type": "طلب الحصول على القسيمة (طلب مباشر)",
                "record": f"قام المستخدم {entity.username} بطلب الحصول على القسيمة {params.get('group')} "
                          f"ذات رقم المعرف (ID {params.get('group_id')}#)."
            },
            "coupon_request_on_request_received": {
                "type": "طلب الحصول على القسيمة (طلب مباشر)",
                "record": f"قام المستخدم {entity.username} بالحصول على القسيمة {params.get('group')} "
                          f"ذات رقم المعرف (ID {params.get('group_id')}#),"
                          f" رمز الـ QRCode الخاص به هو {params.get('qr_code')}."
            },
            # # # USERS
        }
        notifs = {
            "activated": {
                "notification": "مبروك, تم تفعيل حسابك!",
                "user_id": entity.id
            },
            "coupon_request_on_display_received": {
                'notification': "مبروك! حصلت على قسيمة عبر التوزيع العشوائي.",
                'user_id': entity.id
            },
            "coupon_request_on_request_received": {
                'notification': "مبروك! حصلت على قسيمة عبر الطلب المباشر.",
                'user_id': entity.id
            },
            "buy_coupon_seller": {
                'notification': f"مبروك! تم شراء القسيمة {params.get('old_qr_code')} وإضافة المبلغ لرصيدك.",
                'user_id': entity.id
            },
            "receive_coupon": {
                'notification': f"مبروك! تم إهدائك قسيمة بقيمة {params.get('price')}$"
                                f" من المستخدم {params.get('sender')}.",
                'user_id': entity.id
            },
            "group_expired": {
                'notification': f"للأسف إنتهت صلاحية القسيمة {params.get('code')} التي تملكها.",
                'user_id': params.get('user_id')
            }
        }
    elif entity_type == 'Coupons':
        records = {
            # # # COUPONS
            # Coupon Requests
            "coupon_received_on_display": {
                "type": "إستلام القسيمة (توزيع عشوائي)",
                "record": f"حصل المستخدم {params.get('user')} على القسيمة {entity.coupon_code} للإعلان "
                          f"(ID {entity.group_id}#),"
                          f" ذات القيمة {entity.group.coupon_price}$ عبر التوزيع العشوائي, رمز الـ QRCode"
                          f" هو {params.get('qr_code')}."
            },
            "coupon_received_on_request": {
                "type": "إستلام القسيمة (طلب مباشر)",
                "record": f"حصل المستخدم {params.get('user')} على القسيمة {entity.coupon_code} للإعلان "
                          f"(ID {entity.group_id}#),"
                          f" ذات القيمة {entity.group.coupon_price}$ عبر الطلب المباشر, رمز الـ QRCode"
                          f" هو {params.get('qr_code')}, تبقى {entity.group.coupons_left} من قسائم الإعلان."
            },
            # Coupon Offer
            "offer_coupon": {
                "type": "عرض القسيمة للبيع",
                "record": f"تم عرض القسيمة {params.get('coupon_code')} للإعلان (ID {entity.group_id}#),"
                          f" ذات القيمة {params.get('coupon_price')}$ بمبلغ "
                          f"{params.get('offer_price')}$, من المستخدم (البائع) {params.get('seller')}."
            },
            # Coupon Buy
            "buy_coupon": {
                "type": "شراء عرض القسيمة",
                "record": f"تم نقل القسيمة {entity.coupon_code} للإعلان (ID {entity.group_id}#),"
                          f" من البائع {params.get('seller')}"
                          f" للمشتري {params.get('buyer')} بقيمة {params.get('offer_price')}$ "
                          f"تم تحويل الـ QRCode من {params.get('old_qr_code')} إلى {entity.qr_code}."
            },
            # Coupon Gift
            "gift_coupon": {
                "type": "إنتقال القسيمة (إهداء)",
                "record": f"تم نقل القسيمة {entity.coupon_code} للإعلان (ID {entity.group_id}#),"
                          f" من المستخدم {params.get('sender')} للمستخدم "
                          f"{params.get('receiver')}, تم تحويل الـ QRCode من {params.get('old_qr_code')}"
                          f" إلى {entity.qr_code}"
            },
            # Coupon Redeem
            "redeem_coupon": {
                "type": "محاولة مطابقة القسيمة",
                "record": f"قامت الشركة {entity.group.company} عن طريق المستخدم ID(#{entity.matcher})"
                          f" بمحاولة مطابقة القسيمة {entity.coupon_code} "
                          f"للإعلان (ID {entity.group_id}#), للمستفيد {entity.user.username},"
                          f" ذات القيمة {entity.group.coupon_price}$, الـ QRCode الخاص بالقسيمة هو {entity.qr_code}."
            },
            # # # COUPONS
        }
        notifs = {
            "redeem_coupon": {
                'notification': f"مبروك! تم مطابقة القسيمة {entity.qr_code} الخاصة بك بنجاح.",
                'user_id': params.get("user_id")
            }
        }
    elif entity_type == "Groups":
        records = {
            # # # GROUPS
            # New Group
            "new_group": {
                'type': "إضافة إعلان جديد",
                'record': f"تم إضافة إعلان جديد من قبل {entity.company} رقم المعرف (ID {entity.id}#)"
                          f" بعدد قسائم {entity.coupons_num} بقيمة {entity.coupon_price}$"
                          f" لكل قسيمة و قيمة الموازنة {entity.full_price}$, "
                          f"الرمز المشترك لقسائم الإعلان {entity.coupon_code}."
            },
            # Starting Distributing Coupons
            "display_distribution_ends": {
                'type': 'إنتهاء التوزيع العشوائي',
                'record': f"إنتهى التوزيع العشوائي للقسيمة {entity.coupon_code} ذات رقم المعرف (ID {entity.id}#) "
                          f"عدد المشاركين في التوزيع {len(literal_eval(entity.claimants))}, عدد المستفيدين "
                          f"{len(literal_eval(entity.receivers))}, عدد القسائم المتبقية {entity.coupons_left}"
            },
            # Group Expiration
            "group_expired": {
                'type': "إنتهاء صلاحية الإعلان",
                "record": f"إنتهت صلاحية الإعلان {entity.coupon_code} رقم المعرف (ID {entity.id}#)"
                          f", عدد القسائم المكتسبة من الإعلان {int(entity.coupons_num) - int(entity.coupons_left)},"
                          f" وعدد القسائم المتبقية {entity.coupons_left}, بقيمة {entity.coupon_price}$ لكل قسيمة, "
                          f"وقيمة موازنة {entity.full_price}$."
            },
            # Group Display Expiration
            "group_display_expired": {
                'type': "إنتهاء فترة عرض الإعلان",
                "record": f"إنتهت فترة عرض الإعلان {entity.coupon_code} رقم المعرف (ID {entity.id}#)"
                          f", عدد القسائم المكتسبة من الإعلان {int(entity.coupons_num) - int(entity.coupons_left)},"
                          f" وعدد القسائم المتبقية {entity.coupons_left}, بقيمة {entity.coupon_price}$ لكل قسيمة, "
                          f"وقيمة موازنة {entity.full_price}$."
            },
            # No Coupons Left in Group
            "group_coupons_ends": {
                'type': "إنتهاء عدد قسائم الإعلان",
                "record": f"تم إكتساب جميع قسائم الإعلان {entity.coupon_code} رقم المعرف (ID {entity.id}#)"
                          f", عدد القسائم المكتسبة من الإعلان {int(entity.coupons_num)},"
                          f" بقيمة {entity.coupon_price}$ لكل قسيمة, وقيمة موازنة {entity.full_price}$."
            },
            # Adding Coupons to Group
            "additional_coupons": {
                'type': "إضافة قسائم جديدة للإعلان",
                'record': f"تم إضافة قسائم جديدة للإعلان {entity.coupon_code} رقم المعرف (ID {entity.id}#)"
                          f", عدد القسائم المضافة "
                          f"{params.get('new_coupons')} بقيمة موازنة إضافية {params.get('new_sum')}$, فترة بقاء الإعلان"
                          f" {params.get('additionalDis')}  ساعة/ساعات من وقت صدور الإعلان."
            }
            # # # GROUPS
        }
        notifs = {}
    else:
        records = {}
        notifs = {}

    errors = {
        # Login Errors
        "LOGGED_IN": f"المستخدم قام بتسجيل دخوله مسبقاً.",
        "NOT_ACTIVE": f"المستخدم غير مفعل.",
        "DISABLED": f"المستخدم موقوف حالياً.",
        "WRONG_PASSW": f"كلمة المرور خاطئة.",
        # Logout Errors
        "LOGOUT_SERVER": "خطأ في السيرفر أثناء محاولة تسجيل الخروج.",
        # Reset Password (Logged-Out) Errors
        "RESET_PASSW_NO_TOKEN": "رمز تغيير كلمة المرور غير صحيح.",
        "RESET_PASSW_TOKEN_USED": "رمز تغيير كلمة المرور مستخدم مسبقاً.",
        "RESET_PASSW_TOKEN_EXPIRE": "رمز تغيير كلمة المرور منتهي الصلاحية.",
        "RESET_PASSW_SERVER": "خطأ في السيرفر أثناء محاول تغيير كلمة المرور.",
        # Reset Email Errors
        "RESET_EMAIL_NO_TOKEN": "رمز تغيير البريد الإلكتروني غير صحيح.",
        "RESET_EMAIL_NO_MATCH_EMAIL": "البريد الإلكتروني الخاص بالمستخدم لا يطابق البريد الإلكتروني المسجل في الطلب.",
        "RESET_EMAIL_TOKEN_USED": "رمز تغيير البريد الإلكتروني مستخدم مسبقاً.",
        "RESET_EMAIL_TOKEN_EXPIRED": "رمز تغيير البريد الإلكتروني منتهي الصلاحية.",
        "RESET_EMAIL_SERVER": "خطأ في السيرفر أثناء محاول تغيير البريد الإلكتروني.",
        # Gifting Coupon Errors
        "SEND_COUPON_NO_COUPON": "القسيمة غير موجودة أو قد تم إزالتها.",
        "SEND_COUPON_NOT_YOURS": "المستخدم يحاول إهداء قسيمة لا يملكها.",
        "SEND_COUPON_NOT_AVAILABLE": "القسيمة غير صالحة للإستخدام.",
        "SEND_COUPON_NO_RECEIVER": "المستخدم (المستقبل) غير موجود, أو قد تم حذفه.",
        "SEND_COUPON_SERVER": "خطأ في السيرفر أثناء محاولة إهداء القسيمة.",
        # Selling Coupon Errors
        "SELL_COUPON_NOT_AVAILABE": "القسيمة غير صالحة للإستخدام.",
        "SELL_COUPON_NOT_YOURS": "المستخدم يحاول بيع قسيمة لا يملكها.",
        "SELL_COUPON_INVALID_PRICE": "المستخدم يحاول بيع القسيمة بسعر غير مقبول.",
        "SELL_COUPON_SERVER": "خطأ في السيرفر أثناء محاولة بيع القسيمة.",
        # Buying Coupon Errors
        "BUY_COUPON_EXPIRED": "القسيمة منتهية الصلاحية.",
        "BUY_COUPON_INVALID_BALANCE": "المشتري لا يملك رصيد كافي لشراء العرض.",
        "BUY_COUPON_SERVER": "خطأ في السيرفر أثناء محاولة شراء القسيمة.",
        # Canceling Offer Errors
        "CANCEL_OFFER_COMPLETED": "لقد تم شراء العرض مسبقاً.",
        "CANCEL_OFFER_SERVER": "خطأ في السيرفر أثناء محاولة إلغاء العرض.",
        # Request Balance Paypal Errors
        "PAYPAL_REQUEST_ERROR": "حدث خطأ في تأكيد عملية الدفع بالبايبال.",
        # Reqeust Balance Bank Errors
        "BANK_REQUEST_ERROR": "رفض من طرف الإدارة.",
        # Coupon Requests Errors (DISPLAY)
        "COUPONS_DISPLAY_SIGNING_EXPIRED": "إنتهت فترة التسجيل للتوزيع العشوائي.",
        "COUPONS_DISPLAY_USER_CLAIMED": "المستخدم قد إستخدم فرصة الحصول على القسيمة لليوم مسبقاً.",
        "COUPONS_DISPLAY_ALREADY_REGISTERED": "المستخدم قد قام مسبقاً بالتسجيل لهذا الإعلان.",
        # Coupon Requests Errors (REQUEST)
        "COUPONS_REQUEST_ZERO": "لا يوجد قسائم متبقية لهذا الإعلان.",
        "COUPONS_REQUEST_CLAIMED": "المستخدم قد إستخدم فرصة الحصول على القسيمة لليوم مسبقاً.",
        "COUPONS_REQUEST_RECEIVED": "المستخدم قد حصل على هذه القسيمة مسبقاً.",
        # Coupon Redeem Errors
        "REDEEM_COUPON_USED": "القسيمة مستخدمة سابقاً.",
        "REDEEM_COUPON_ONHOLD": "القسيمة موقوفة حالياً.",
        "REDEEM_COUPON_EXPIRED": "القسيمة منتهية.",
        "REDEEM_COUPON_CANCELED": "القسيمة ملغية.",
        "REDEEM_COUPON_SERVER": "خطأ أثناء محاولة مطابقة القسيمة.",
    }

    try:
        record = records.get(record_type)
        if record:
            new_history = History(
                entity_type=entity_type,
                entity_id=entity.id,
                record_type=record.get("type"),
                record_state=record_state,
                record=record.get("record"),
                error_message=(errors[error_key] if error_key else None)
            )
            new_history.insert()
    except Exception as e:
        print(e)

    try:
        if record_state == "succeed":
            notif = notifs[record_type]
            new_notif = Notifications(
                notification=notif.get('notification'),
            )
            new_notif.user_id = notif.get("user_id")
            new_notif.insert()

            user = Users.query.get(notif.get("user_id"))
            sendNotifications(
                key="notifications",
                params={
                    'email': user.email,
                    'username': user.username,
                    'msg': notif
                }
            )
    except Exception as e:
        print(e)
