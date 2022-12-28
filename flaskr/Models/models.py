from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import UserMixin
from datetime import datetime, timedelta
import os
import string
import math
from random import choices
# Parse String to Array or Dict
from ast import literal_eval


from sqlalchemy import REAL

db = SQLAlchemy()

USER = os.getenv('USER')
PROVIDER = os.getenv('PROVIDER')
ADMIN = os.getenv('ADMIN')
SUPERADMIN = os.getenv('SUPERADMIN')
BUCKET = os.getenv('S3_BUCKET')

# Permissions
TO_PROVIDER = os.getenv('TO_PROVIDER')
DISABLED_USERS = os.getenv('DISABLED_USERS')
NEW_USERS = os.getenv('NEW_USERS')
ADS = os.getenv('ADS')
OFFERS = os.getenv('OFFERS')
FILES = os.getenv('FILES')
DATA = os.getenv('DATA')
TICKETS = os.getenv('TICKETS')


def app_config(app):
    # Setting up Database & app config
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.getenv('PROJECT_SECRET')
    app.config['SMTP_ALLOWLOCAL'] = 1
    db.app = app
    db.init_app(app)
    # Setting Up Migration
    Migrate(app, db)

    db.create_all()

    # Create Admin
    from flaskr.ABC.utils import create_admin, create_basic_static_data
    try:
        create_admin()
        create_basic_static_data()
    except Exception as e:
        print(e)


# MODELS: TABLES

class Users(db.Model, UserMixin):
    """
    Users Table
    Description :
        This is Users Table, which holds User's Information and GUID.
    """

    __tablename__ = "Users"

    id = db.Column(db.Integer, primary_key=True)  # User Unique Short ID
    uid = db.Column(db.String, nullable=False, unique=True)  # User Unique Long ID
    guid = db.Column(db.String, nullable=False, default=USER)  # User Group (Customer, Provider, Admin)
    permissions = db.Column(db.String, default='[]')  # List of User's Permissions

    # Admin Tools
    # (check_balance : Enabiling This will Activate Balance Validator when Adding a new Group)
    check_balance = db.Column(db.Boolean, default=False)

    company = db.Column(db.String)  # Provider's Company
    ad_addibility = db.Column(db.Boolean, default=False)  # The Capability of adding Groups
    main_ad_image = db.Column(db.String)  # Main Ads Image For This Provider's Company
    ad_images = db.Column(db.String, default="[]")

    is_provider = db.Column(db.Boolean, default=False)  # Simple Check if User is A Provider (Beside GUID)
    is_admin = db.Column(db.Boolean, default=False)  # Simple Check if User is An Admin
    is_associate = db.Column(db.Boolean, default=False)  # Simple Check if User is An Associate
    is_super = db.Column(db.Boolean, default=False)  # Simple Check if User is A SuperAdmin

    fullname = db.Column(db.String)  # User's Full Name
    username = db.Column(db.String, nullable=False, unique=True)  # User's Username
    balance = db.Column(REAL, nullable=False, default=0.0)  # User's Balance (USD)

    profile_img = db.Column(db.String)  # User's Profile Image

    country = db.Column(db.String)  # User's Country
    city = db.Column(db.String)  # User's City

    email = db.Column(db.String, nullable=False, unique=True)  # User's Email
    phone = db.Column(db.String, nullable=False, unique=True)  # User's Phone
    from_ksa = db.Column(db.Boolean, default=False)  # User From KSA?

    password = db.Column(db.String, nullable=False)  # User's Password

    is_active = db.Column(db.Boolean, default=False)  # User State (Active, Disabled) Activating Via Email/Phone
    disabled = db.Column(db.Boolean, default=False)  # User Disable (By Admin)

    claimed_today = db.Column(db.Boolean, default=False)  # Boolean To Check if User Claimed His Coupon For Today
    claim_date = db.Column(db.DateTime)  # DateTime of Claiming One Coupon (Reset After 24hrs)

    groups = db.relationship('Group', backref='Users', lazy=True)
    coupons = db.relationship('Coupon', backref='Users', lazy=True)
    tickets = db.relationship('Tickets', backref='Users', lazy=True)
    notifications = db.relationship('Notifications', backref='Users', lazy=True)
    applications = db.relationship('Applications', backref='Users', lazy=True)

    association_id = db.Column(db.Integer, db.ForeignKey('Association.id'))

    def __init__(self, username, country, email, password, phone, from_ksa=False,
                 company=None, fullname=None, balance="0", profile_img=None):
        self.username = username
        self.fullname = fullname
        self.balance = balance
        self.email = email
        self.phone = phone
        self.password = password
        self.company = company
        self.country = country
        self.profile_img = profile_img
        self.from_ksa = from_ksa
        self.uid = self.generate_uid()

    def generate_uid(self):
        """
            Function to return a random 9 digit User ID
        """
        nums = string.digits
        new_uid = ''.join(choices(nums, k=9))

        uids = self.query.filter_by(uid=new_uid).first()

        if uids:
            return self.generate_uid()

        return new_uid

    def getNotifs(self):
        notifs = 0
        for n in self.notifications:
            if not n.viewed:
                notifs += 1
        return notifs

    def display(self):
        return {
            'id': self.id,
            'uid': self.uid,
            'profile_img': self.profile_img,
            'main_ad_image': self.main_ad_image,
            'ad_images': literal_eval(self.ad_images),
            'username': self.username,
            'fullname': self.fullname,
            'email': self.email,
            'phone': self.phone,
            'company': self.company,
            'country': self.country,
            'city': self.city,
            'balance': self.balance,
            'claimed': self.claimed_today,
            'is_provider': self.is_provider,
            'is_associate': self.is_associate,
            'is_admin': self.is_admin,
            'is_super': self.is_super,
            'claimed_coupons': len(self.coupons),
            'notifications': self.getNotifs()
        }

    def claimedDisplay(self, group_id):
        coupon = Coupon.query.filter(Coupon.group_id == group_id).filter(Coupon.user_id == self.id).first()
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'phone': self.phone,
            'qr_code': coupon.qr_code if coupon else None
        }

    def adminDisplayNormal(self):
        if self.guid == PROVIDER:
            access_level = 'PROVIDER'
        elif self.guid == ADMIN:
            access_level = 'ADMIN'
        elif self.guid == USER:
            access_level = 'USER'
        else:
            access_level = 'SUPERADMIN'
        return {
            'id': self.id,
            'username': self.username,
            'fullname': self.fullname,
            'email': self.email,
            'phone': self.phone,
            'balance': self.balance,
            'country': self.country,
            'access_level': access_level,
            'claimed_coupons': len(self.coupons)
        }

    def adminDisplayProviders(self):
        return {
            'id': self.id,
            'username': self.username,
            'fullname': self.fullname,
            'email': self.email,
            'phone': self.phone,
            'company': self.company,
            'balance': self.balance,
            'country': self.country,
            'check_balance': self.check_balance,
            'owned_groups': len(self.groups)
        }

    def adminDisplayAssociates(self):
        association = Association.query.get(self.association_id)
        return {
            'id': self.id,
            'username': self.username,
            'fullname': self.fullname,
            'email': self.email,
            'phone': self.phone,
            'company': association.company,
            'balance': self.balance,
            'country': self.country,
        }

    def getPermissions(self):
        perms = {
            TO_PROVIDER: 'TO_PROVIDER',
            DISABLED_USERS: 'DISABLED_USERS',
            NEW_USERS: 'NEW_USERS',
            ADS: 'ADS',
            OFFERS: 'OFFERS',
            FILES: 'FILES',
            DATA: 'DATA',
            TICKETS: 'TICKETS'
        }

        return {perms[p]: True for p in literal_eval(self.permissions)}

    def adminDisplayAdmins(self):

        perms = {
            TO_PROVIDER: 'TO_PROVIDER',
            DISABLED_USERS: 'DISABLED_USERS',
            NEW_USERS: 'NEW_USERS',
            ADS: 'ADS',
            OFFERS: 'OFFERS',
            FILES: 'FILES',
            DATA: 'DATA',
            TICKETS: 'TICKETS'
        }

        return {
            'id': self.id,
            'username': self.username,
            'fullname': self.fullname,
            'email': self.email,
            'phone': self.phone,
            'balance': self.balance,
            'country': self.country,
            'permissions': {perms[p]: True for p in literal_eval(self.permissions)},
            'claimed_coupons': len(self.coupons)
        }

    def searchDis(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email
        }

    def insert(self):
        db.session.add(self)
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()

    @staticmethod
    def update():
        db.session.commit()


class Notifications(db.Model):
    """
        Notifications Model
        Description:
            Notify User's with (Coupon's Updates, Ticket's Updates)
    """

    __tablename__ = "Notifications"

    id = db.Column(db.Integer, primary_key=True)
    notification = db.Column(db.String, nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    viewed = db.Column(db.Boolean, nullable=False, default=False)

    user_id = db.Column(db.Integer, db.ForeignKey('Users.id'), nullable=False)

    def __init__(self, notification):
        self.notification = notification
        self.date = datetime.now()
        self.viewed = False

    def display(self):
        return {
            'id': self.id,
            'notification': self.notification,
            'viewed': self.viewed,
            'date': self.date.timestamp()
        }

    def insert(self):
        db.session.add(self)
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()

    @staticmethod
    def update():
        db.session.commit()


class Association(db.Model):
    """
        Associates Table
        Description :
            This is for Users whom are associated with a provider.
    """

    __tablename__ = "Association"

    id = db.Column(db.Integer, primary_key=True)

    head = db.Column(db.Integer, unique=True, nullable=False)
    company = db.Column(db.String, nullable=False)
    associates = db.relationship('Users', backref='Association', lazy=True)

    def __init__(self, head, company):
        self.head = head
        self.company = company

    def display(self):
        return {
            'head': self.head,
            'company': self.company,
            'associates': [u.display() for u in self.associates]
        }

    def insert(self):
        db.session.add(self)
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()

    @staticmethod
    def update():
        db.session.commit()


class Transfers(db.Model):
    """
    Transfers Table
    Description:
        User can Pay Money to get points to buy Coupons
        from other Users.
    """

    __tablename__ = 'Transfers'

    id = db.Column(db.Integer, primary_key=True)

    fullname = db.Column(db.String)
    email = db.Column(db.String, nullable=False)
    phone = db.Column(db.String, nullable=False)
    bank_account = db.Column(db.String)
    method = db.Column(db.String, nullable=False)
    amount = db.Column(REAL, nullable=False)
    verified = db.Column(db.Boolean, nullable=False, default=False)

    user_id = db.Column(db.String, db.ForeignKey('Users.uid'), nullable=False)

    def __init__(self, method, amount, fullname, email, phone,
                 user_id, bank_account=None, verified=False):
        self.fullname = fullname
        self.email = email
        self.phone = phone
        self.bank_account = bank_account
        self.method = method
        self.amount = amount
        self.user_id = user_id
        self.verified = verified

    def display(self):
        user = Users.query.filter(Users.uid == self.user_id).first()
        return {
            'id': self.id,
            'fullname': self.fullname,
            'username': user.username,
            'user_id': user.id,
            'email': self.email,
            'phone': self.phone,
            'bank_account': self.bank_account,
            'method': self.method,
            'amount': self.amount,
            'verified': self.verified
        }

    def insert(self):
        db.session.add(self)
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()

    @staticmethod
    def update():
        db.session.commit()


class Applications(db.Model):
    """
    Applications Table
    Description:
        User's can create an Application to switch To Provider
    """

    __tablename__ = 'Applications'

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String, nullable=False)
    content = db.Column(db.String)

    to_provider = db.Column(db.Boolean, default=False)
    company_name = db.Column(db.String)
    providerAgreement = db.Column(db.String)

    complain = db.Column(db.Boolean, default=False)

    status = db.Column(db.String, nullable=False, default="open")

    user_id = db.Column(db.String, db.ForeignKey('Users.uid'), nullable=False)

    def __init__(self, title, content=None, to_provider=False, status="open",
                 company_name=None, providerAgreement=None, complain=False):
        self.title = title
        self.content = content
        self.to_provider = to_provider
        self.company_name = company_name
        self.providerAgreement = providerAgreement
        self.complain = complain
        self.status = status

    def display(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'content': self.content,
            'to_provider': self.to_provider,
            'complain': self.complain,
            'status': self.status
        }

    def toProviderDisplay(self):
        user = Users.query.filter_by(uid=self.user_id).first()
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'content': self.content,
            'company_name': self.company_name,
            'providerAgreement': self.providerAgreement,
            'mainAdImage': user.main_ad_image,
            'status': self.status
        }

    def insert(self):
        db.session.add(self)
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()

    @staticmethod
    def update():
        db.session.commit()


class Tickets(db.Model):
    """
        Tickets Table
        Description:
            Users can make a Complain, Suggestion or
            Request to change data..

        Requests:
            1) Change Username
            2) Change Phone
            3) Change Country

        Message & Responds Structure:
            Messages : [
                {"body": "message....", "profile_img": "Image", "user": 'CUSTOMER', "date": "2020-11-30 15:30"}
            ]
            Responds : [
                {"body": "respond....", "profile_img": "Image", "user": 'ADMIN', "date": "2020-11-30 16:33"}
            ]

            AllnAll (Ordered by date) : [
                {"body": "message....", "profile_img": "Image", "user": 'CUSTOMER', "date": "2020-11-30 15:30"},
                {"body": "respond....", "profile_img": "Image", "user": 'ADMIN', "date": "2020-11-30 16:33"}
            ]
    """

    __tablename__ = "Tickets"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String, nullable=False)
    created = db.Column(db.DateTime, nullable=False)
    # Complain, Suggestion, or Request.
    type_ = db.Column(db.String, nullable=False)
    messages = db.Column(db.String, nullable=False, default="[]")
    responds = db.Column(db.String, default="[]")
    # Open, Waiting, and Solved
    status = db.Column(db.String, nullable=False, default="open")
    email = db.Column(db.String)
    last_activity = db.Column(db.DateTime, nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey('Users.id'), nullable=False)

    def __init__(self, title, type_, messages, email):
        self.title = title
        self.type_ = type_
        self.messages = messages
        self.email = email
        self.created = datetime.now()
        self.last_activity = datetime.now()

    def orderMessages(self):
        messages = literal_eval(self.messages) + literal_eval(self.responds)

        return sorted(messages, key=lambda m: m['date'])

    def checkUserResp(self):
        # Simple check if admin has respond to the previous message.
        user_messages = literal_eval(self.messages)
        admin_responds = literal_eval(self.responds)
        # If Yes, User can respond back, else User cannot respond.
        last_message = sorted((user_messages + admin_responds), key=lambda m: m['date'])[-1]
        if last_message in user_messages:
            return False
        return True

    def getLast(self):
        current = datetime.now()

        diff = current - self.last_activity
        indays = diff.days
        inseconds = diff.seconds
        inminutes = inseconds / 60
        inhours = inminutes / 60

        if indays >= 1:
            return f"{math.ceil(indays)} day(s)"
        elif inhours >= 1:
            return f"{math.ceil(inhours)} hour(s)"
        elif inminutes >= 1:
            return f"{math.ceil(inminutes)} minute(s)"
        else:
            return f"{math.ceil(inseconds)} second(s)"

    def display(self):
        messages = self.orderMessages()
        user = Users.query.get(self.user_id)
        user_resp = self.checkUserResp()

        return {
            'id': self.id,
            'title': self.title,
            'type': self.type_,
            'status': self.status,
            'email': self.email,
            'created': self.created.timestamp(),
            'last': self.last_activity.timestamp(),
            'last_activity': self.getLast(),
            'messages': messages,
            'user_resp': user_resp,
            'user': user.display()
        }

    def insert(self):
        db.session.add(self)
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()

    @staticmethod
    def update():
        db.session.commit()


class Files(db.Model):
    """
    Files Model
    Description:
        This Modal Generate a new name for each file uploaded,
        In case of two files having the same name.
    """

    __tablename__ = 'Files'
    id = db.Column(db.Integer, primary_key=True)
    original_name = db.Column(db.String, nullable=False)
    file_name = db.Column(db.String, nullable=False, unique=True)
    admin_file = db.Column(db.Boolean, default=False)
    key = db.Column(db.String)
    description = db.Column(db.String(64))

    def __init__(self, original_name, description=None, key=None, admin_file=False):
        self.original_name = original_name
        self.admin_file = admin_file
        self.key = key
        self.description = description
        self.file_name = self.generate_name()

    def generate_name(self):
        """
            Function to return a random 12 Letters File Name
        """
        strs = string.ascii_letters + string.digits
        new_name = ''.join(choices(strs, k=12))

        names = self.query.filter_by(file_name=new_name).first()

        if names:
            return self.generate_name()

        # Getting Extension From Original Filename
        ext = os.path.splitext(self.original_name)
        ext = ext[1]

        return new_name + ext

    def display(self):
        return {
            'id': self.id,
            'key': self.key,
            'original_name': self.original_name,
            'file_name': self.file_name,
            'description': self.description
        }

    def insert(self):
        db.session.add(self)
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()

    @staticmethod
    def update():
        db.session.commit()


class StaticLabels(db.Model):
    """
    Labels Model
    Description:
        Store Labels for Selectable Choices & Files. to add more
        values to each label(key)
    """

    __tablename__ = 'StaticLabels'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)  # Name Of Label
    description = db.Column(db.String(128))  # Brief Description (64 chr)
    key = db.Column(db.String, nullable=False)
    label = db.Column(db.String, nullable=False, unique=True)  # label of target
    values = db.Column(db.String, nullable=False)  # Could be a (string/list/dict)

    def __init__(self, label, values, key, name=None, description=None):
        self.label = label
        self.values = values
        self.key = key
        self.name = name
        self.description = description

    def display(self):
        return {
            'id': self.id,
            'key': self.key,
            'name': self.name,
            'description': self.description,
            'label': self.label,
            'values': literal_eval(self.values)
        }

    def insert(self):
        db.session.add(self)
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()

    @staticmethod
    def update():
        db.session.commit()


class Tokens(db.Model):
    """
    Tokens Model
    Description:
        Generate unique tokens for Password Reset, Phone Verification,
        Email Verification, etc..
    """

    __tablename__ = 'Tokens'

    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String, unique=True, nullable=False)
    email = db.Column(db.String)
    phone = db.Column(db.String)
    type_ = db.Column(db.String, nullable=False)
    expire = db.Column(db.DateTime, nullable=False)
    is_used = db.Column(db.Boolean, nullable=False, default=False)

    def __init__(self, type_, expire_date, expire_duration=6, email=None, phone=None, nums=64):
        self.type_ = type_
        self.email = email
        self.phone = phone
        self.expire = (expire_date + timedelta(hours=expire_duration))  # expire_duration in hours
        self.token = self.generate_unique_token(nums)

    def generate_unique_token(self, nums=64):
        """
            Function to return a random 64 Token String
        """

        strs = string.ascii_letters + string.digits
        new_token = ''.join(choices(strs, k=nums))

        tokens = self.query.filter_by(token=new_token).first()

        if tokens:
            return self.generate_unique_token()

        return new_token

    def insert(self):
        db.session.add(self)
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()

    @staticmethod
    def update():
        db.session.commit()


class Group(db.Model):
    """
    Coupons Group Table
    Description:
        Coupons Group, Where we can assing a set of coupons to one
        Provider easily.
    """

    __tablename__ = 'Group'

    id = db.Column(db.Integer, primary_key=True)
    company = db.Column(db.String, nullable=False)
    coupon_type = db.Column(db.String)
    coupons_num = db.Column(db.Integer, nullable=False)
    coupons_left = db.Column(db.Integer, nullable=False)
    coupon_price = db.Column(REAL, nullable=False)
    coupon_code = db.Column(db.String, nullable=False)
    full_price = db.Column(REAL, nullable=False)
    country = db.Column(db.String, nullable=False)
    branches = db.Column(db.String, nullable=False)
    description = db.Column(db.String)
    images = db.Column(db.String, nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    expire_date = db.Column(db.DateTime, nullable=False)
    # Days of staying On Site (Depands on if There are Coupons Left & Display Expire Date is Not Over)
    on_site = db.Column(db.DateTime, nullable=False)
    # Hide Groups From Panel.
    on_hide = db.Column(db.Boolean, default=False)
    # Pending, Canceled, Available, Expired, Finished.
    status = db.Column(db.String, nullable=False, default='pending')

    # Access Token, To View, Submit Coupon
    access_token = db.Column(db.String, nullable=False, unique=True)

    # How Long The Ad will be displayed on Page Even When it reaches 0 Coupon Left.
    display_expire_date = db.Column(db.DateTime)  # Entered When Approved

    # How Coupons Are Distributed (Display, Request)
    # Display : Users Register To Get A Chance of Getting The Coupon
    # Request : After Display, User Will Be Able To Request Coupons by Precedence.
    distribute_type = db.Column(db.String, nullable=False, default='display')
    distribute_end_date = db.Column(db.DateTime)  # End Date Of Display (For SignUps)

    claimants = db.Column(db.String, default="[]")  # Customers Who Signed Up To Get Coupon
    receivers = db.Column(db.String, default="[]")  # Customers Who Received Coupons

    coupons = db.relationship('Coupon', backref='Group', lazy=True)
    user_id = db.Column(db.String, db.ForeignKey('Users.uid'))

    # View count (per click) for this Group.
    views = db.Column(db.Integer, default=0)
    # View count for registered Users (1 per Unique User) for this Group.
    unique_views = db.Column(db.String, default="[]")

    def __init__(self, company, coupons_num, coupon_code, coupon_price, full_price,
                 country, start_date, images, branches, user_id,
                 description=None, coupon_type=None, expire=0, onsite=1):
        self.company = company
        self.coupon_type = coupon_type
        self.coupons_num = coupons_num
        self.coupons_left = coupons_num
        self.coupon_price = coupon_price
        self.coupon_code = coupon_code
        self.full_price = full_price
        self.start_date = start_date
        self.images = images
        self.country = country
        self.branches = branches
        self.description = description
        self.user_id = user_id

        self.access_token = self.generate_access_token()

        self.expire_date = start_date + timedelta(days=(expire + 10))
        self.on_site = start_date + timedelta(days=onsite)

    def generate_access_token(self):
        """
            Function to return a random 16 Access Token String
        """

        strs = string.ascii_letters + string.digits
        new_token = ''.join(choices(strs, k=16))

        tokens = self.query.filter_by(access_token=new_token).first()

        if tokens:
            return self.generate_access_token()

        return new_token

    def display(self):
        return {
            'id': self.id,
            'status': self.status,
            'company': self.company,
            'type': self.coupon_type,
            'coupon_code': self.coupon_code,
            'coupons_num': self.coupons_num,
            'coupons_left': self.coupons_left,
            'coupon_price': self.coupon_price,
            'full_price': self.full_price,
            'description': self.description,
            'country': self.country,
            'distribute_type': self.distribute_type,
            'branches': literal_eval(self.branches),
            'images': literal_eval(self.images),
            'claimants': literal_eval(self.claimants),
            # 'start_date': datetime.strftime(self.start_date, '%H:%M:%S %Y-%m-%d'),
            # 'expire_date': datetime.strftime(self.expire_date, '%H:%M:%S %Y-%m-%d'),
            # 'distribute_end_date': datetime.strftime(
            #     self.distribute_end_date, '%H:%M:%S %Y-%m-%d') if self.distribute_end_date else None,
            # 'on_site': datetime.strftime(self.on_site, '%H:%M:%S %Y-%m-%d'),
            # 'display_expire_date': datetime.strftime(self.display_expire_date, '%H:%M:%S %Y-%m-%d') if
            # self.display_expire_date else None,
            'start_date': self.start_date.timestamp(),
            'expire_date': self.expire_date.timestamp(),
            'distribute_end_date': self.distribute_end_date.timestamp() if self.distribute_end_date else None,
            'on_site': self.on_site.timestamp(),
            'display_expire_date': self.display_expire_date.timestamp() if self.display_expire_date else None,
            'views': self.views,
            'unique_views': len(literal_eval(self.unique_views or "[]"))
        }

    def adminDisplay(self):
        return {
            'id': self.id,
            'company': self.company,
            'type': self.coupon_type,
            'coupon_code': self.coupon_code,
            'description': self.description,
            'coupons_num': self.coupons_num,
            'coupons_left': self.coupons_left,
            'coupon_price': self.coupon_price,
            'full_price': self.full_price,
            'distribute_type': self.distribute_type,
            'images': literal_eval(self.images),
            'branches': literal_eval(self.branches),
            # 'start_date': datetime.strftime(self.start_date, '%H:%M:%S %Y-%m-%d'),
            # 'expire_date': datetime.strftime(self.expire_date, '%H:%M:%S %Y-%m-%d'),
            'start_date': self.start_date.timestamp(),
            'expire_date': self.expire_date.timestamp(),
            'status': self.status,
            'views': self.views,
            'unique_views': len(literal_eval(self.unique_views or "[]"))
        }

    def insert(self):
        db.session.add(self)
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()

    @staticmethod
    def update():
        db.session.commit()


class Coupon(db.Model):
    """
    Coupon Table
    Description:
        Coupon are assinged when user successfully claim it from
        a Display Event, or Request Event.
        (Display, and Request Events, Are The Types of Distripution
         Of Coupons)
    """

    __tablename__ = 'Coupon'

    id = db.Column(db.Integer, primary_key=True)
    coupon_code = db.Column(db.String, nullable=False)
    qr_code = db.Column(db.String, nullable=False)
    redeem_date = db.Column(db.DateTime)
    matcher = db.Column(db.Integer)
    coupon_status = db.Column(db.String, default='available')  # available, onhold, expired, used, canceled.

    group_id = db.Column(db.Integer, db.ForeignKey('Group.id'), nullable=False)
    group = db.relationship('Group', backref='Coupon', lazy=True)

    user_id = db.Column(db.Integer, db.ForeignKey('Users.id'), nullable=False)
    user = db.relationship('Users', backref='Coupon', lazy=True)
    offer = db.relationship('Offers', backref='Coupon', lazy=True)

    def __init__(self, coupon_code, group_id, user_id):
        self.coupon_code = coupon_code
        self.group_id = group_id
        self.user_id = user_id
        self.qr_code = self.generate_qr_code()

    def generate_qr_code(self):
        """
            Function to return a random 4 Letters QRCode
        """
        litters = string.ascii_uppercase
        new_code = f"{self.group_id}{''.join(choices(litters, k=4))}{self.user_id}"

        codes = self.query.filter_by(qr_code=new_code).first()

        if codes:
            return self.generate_qr_code()

        return new_code

    def display(self):
        group = Group.query.get(self.group_id)
        matcher = Users.query.get(self.matcher).display() if self.matcher else None
        return {
            'id': self.id,
            'user_id': self.user_id,
            'coupon_code': self.coupon_code,
            'coupon_status': self.coupon_status,
            'group_id': self.group_id,
            'qr_code': self.qr_code,
            'matcher': matcher,
            'coupon_price': group.coupon_price,
            # 'expire_date': datetime.strftime(group.expire_date, '%H:%M:%S %Y-%m-%d'),
            'expire_date': group.expire_date.timestamp(),
            'redeem_date': self.redeem_date.timestamp() if self.redeem_date else None,
            'group_company': group.company,
            'group_branches': literal_eval(group.branches)
        }

    def insert(self):
        db.session.add(self)
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()

    @staticmethod
    def update():
        db.session.commit()


class Offers(db.Model):
    """
    Offers Model
    Description:
        Users who own an Active Coupon, can Create an offer to sell
        their coupons at a price in range of (0, price of coupon).
        They can only place the offer if the expire date is 2 days
        ahead.
    """

    __tablename__ = "Offers"

    id = db.Column(db.Integer, primary_key=True)

    seller_id = db.Column(db.Integer, nullable=False)
    price = db.Column(REAL, nullable=False)
    completed = db.Column(db.Boolean, default=False, nullable=False)
    validated = db.Column(db.Boolean, default=False)
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)
    buyer_id = db.Column(db.Integer)

    coupon_id = db.Column(db.Integer, db.ForeignKey('Coupon.id'), nullable=False)

    def __init__(self, seller_id, price, coupon_id,
                 completed=False, validated=False):
        self.seller_id = seller_id
        self.price = price
        self.coupon_id = coupon_id
        self.completed = completed
        self.validated = validated
        self.start_date = datetime.now()

    def display(self):
        coupon = Coupon.query.get(self.coupon_id)
        seller = Users.query.get(self.seller_id)
        buyer = Users.query.get(self.buyer_id) if self.buyer_id else None
        return {
            'id': self.id,
            'group_id': coupon.group_id,
            'seller': seller.username,
            'buyer': buyer.username if buyer else None,
            # 'coupon_expire': datetime.strftime(coupon.group.expire_date, '%H:%M:%S %Y-%m-%d'),
            'coupon_expire': coupon.group.expire_date.timestamp(),
            'coupon_price': coupon.group.coupon_price,
            'price': self.price,
            # 'start_date': datetime.strftime(self.start_date, '%H:%M:%S %Y-%m-%d'),
            'start_date': self.start_date.timestamp(),
            # 'end_date': datetime.strftime(self.end_date, '%H:%M:%S %Y-%m-%d') if self.end_date else None,
            'end_date': self.end_date.timestamp() if self.end_date else None,
            'completed': self.completed
        }

    def buyerDisplay(self):
        coupon = Coupon.query.get(self.coupon_id)
        seller = Users.query.get(self.seller_id)
        return {
            'id': self.id,
            'group_id': coupon.group_id,
            'seller': seller.username,
            'coupon_type': coupon.group.coupon_type,
            'company': coupon.group.company,
            'branches': literal_eval(coupon.group.branches),
            'coupon_price': coupon.group.coupon_price,
            # 'expire_date': datetime.strftime(coupon.group.expire_date, '%H:%M:%S %Y-%m-%d'),
            'expire_date': coupon.group.expire_date.timestamp(),
            'price': self.price
        }

    def insert(self):
        db.session.add(self)
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()

    @staticmethod
    def update():
        db.session.commit()


class History(db.Model):
    """
        History Model
        Description:
            This Model is a History log, for Users, Groups, Coupons and Offers.
            It Covers every main action taken by the the Entity linked to.

            Entity Types:
                1) Users
                2) Groups
                3) Coupons
                4) Offers
            Record Types:
                Differ between each Entity Type.
                Example:
                    1) Users: Login (Failed, Success)
                    2) Users: Add Balance (Failed (Multiple), Succeed)
                    3) Groups: Start Distribute (Failed, Succeed)
                    4) Groups: Minus a Coupon (Failed, Succeed)
                    5) Coupons: Coupon gained (Failed, Succeed)
                    6) Coupons: Coupon gifting (Failed, Succeed)
                    7) Offers: Offer placed (Failed, Succeed)
                    8) Offers: Offer bought (Failed, Succeed)
            Record State:
                1) Succeed.
                2) Failed.
                3) Error.
            Record Message:
                Briefed message describing the Record.
    """

    __tablename__ = "History"

    id = db.Column(db.Integer, primary_key=True)

    entity_id = db.Column(db.Integer, nullable=False)
    entity_type = db.Column(db.String, nullable=False)

    date = db.Column(db.DateTime, nullable=False)

    record = db.Column(db.String, nullable=False)
    record_type = db.Column(db.String, nullable=False)
    record_state = db.Column(db.String, nullable=False)
    error_message = db.Column(db.String)

    def __init__(self, entity_id, entity_type, record, record_type,
                 record_state, error_message=None):
        self.entity_id = entity_id
        self.entity_type = entity_type
        self.date = datetime.now()
        self.record = record
        self.record_type = record_type
        self.record_state = record_state
        self.error_message = error_message

    def display(self):
        return {
            'id': self.id,
            'entity_id': self.entity_id,
            'entity_type': self.entity_type,
            # 'date': datetime.strftime(self.date, '%H:%M:%S %Y-%m-%d'),
            'date': self.date.timestamp(),
            'record': self.record,
            'record_type': self.record_type,
            'record_state': self.record_state,
            'error_message': self.error_message
        }

    def oneLine(self, offset):
        date = datetime.strftime((self.date + timedelta(minutes=abs(int(offset)))), '%H:%M:%S %Y-%m-%d')

        if self.record_state == "failed":
            return f"[{date}]: {self.record} (فشل)"
        else:
            return f"[{date}]: {self.record} (نجاح)"

    def insert(self):
        db.session.add(self)
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()

    @staticmethod
    def update():
        db.session.commit()

# # # Create A Logging Model :
# When User (Customer/Provider) Makes an Important Action,
# It will Log Automatically to the Admin Logging Page.
# Actions That Requires Logging :
# 1) Changing User Information.
# 2) Creating a New Coupon Group.
# 3) Ordering a Coupon.
# 4) Gifting a Coupon.
# 5) Selling/Buying a Coupon.

# # # Create A Ticket Model :
# User Can Create A Ticket To Communicate with Admins.
# User Can Create A Ticket To Switch His Account To Provider
# User Can Create A Ticket To Complain About Any Thing.

# # # Create A Payment Model :
# User Can Pay Other Users or Providers Points To Buy Coupons.
# Payment Can Automatically Be Confirmed.
# When Payments Go Through, Coupon Will Automatically Transfer To Buyer's Account.

# # # Create Transfer Model :
# User Can Pay Real Money In Exchange Of Points.
# Payment Automatically Transform Into Points (Balance) In User's Account.


# # # About User Balance :
# User Can Add To His Balance By Transfering Money Via Paypal, Mada, etc..
# User Can Get His Money Back Only Via Paypal.
