import os
from sqlalchemy import not_
from flask import Flask, request, render_template, send_from_directory, jsonify
from pathlib import Path
from dotenv import load_dotenv
from flask_cors import CORS
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
import logging
from logging.handlers import RotatingFileHandler
import traceback
# from .Models.models import app_config

# For Mail
import socket
import smtplib

# For Async Functions
from threading import Thread
import time
from datetime import datetime

# Set Absolute Directory
dir_path = Path().absolute()

# Create App
app = Flask(__name__)

# Logging Hanlder
logging_handler = RotatingFileHandler('./tmp/app.log', maxBytes=10000000, backupCount=3)
logger = logging.getLogger('tdm')
logger.setLevel(logging.ERROR)
logger.addHandler(logging_handler)


# Set env directory
env_folder = Path(Path(__file__).parent).parent
env_file = os.path.join(env_folder, '.env')
load_dotenv(dotenv_path=env_file)


# Set bcrypt
login_manager = LoginManager()
login_manager.login_view = 'users.login'
login_manager.login_message_category = 'info'

bcrypt = Bcrypt()


# GUID's
USER = os.getenv('USER')
ASSOCIATE = os.getenv('ASSOCIATE')
PROVIDER = os.getenv('PROVIDER')
ADMIN = os.getenv('ADMIN')
SUPERADMIN = os.getenv('SUPERADMIN')

SECRET_KEY = os.getenv('PROJECT_SECRET')


def create_app():
    # Configure Database
    app.static_folder = 'frontend/static'
    app.template_folder = 'frontend'
    # Setup Database, LoginManager, and Bcrypt
    from flaskr.Models.models import app_config
    app_config(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)

    # Setup CORS
    CORS(app, resources={r'/*': {'origins': '*'}})

    @app.after_request
    def after_request(resp):
        resp.headers.add('Access-Control-Allow-Headers',
                         'Content-Type,Authorization,true')
        resp.headers.add('Access-Control-Allow-Methods',
                         'GET,PUT,POST,DELETE,OPTIONS,PATCH')

        # timestamp = time.strftime('[%Y-%b-%d %H:%M]')
        # logger.error('%s %s %s %s %s %s', timestamp, request.remote_addr, request.method, request.scheme,
        #              request.full_path, resp.status)

        return resp

    # Register Blueprints
    from flaskr.Errors.handlers import errors
    from flaskr.Groups.routes import groups
    from flaskr.User.routes import users
    from flaskr.Panels.routes import panels
    from flaskr.History.routes import history
    from flaskr.Tickets.routes import tickets
    from flaskr.Notifications.routes import notify

    app.register_blueprint(errors)
    app.register_blueprint(users)
    app.register_blueprint(groups)
    app.register_blueprint(panels)
    app.register_blueprint(history)
    app.register_blueprint(tickets)
    app.register_blueprint(notify)

    # For Authentication Error
    from flaskr.Auth.auth import AuthError

    @app.errorhandler(AuthError)
    def authentification_failed(err):
        return jsonify({
            "error": 401,
            "msg": err.msg,
            "code": err.code,
            "success": False
        }), 401

    # @app.errorhandler(Exception)
    # def exceptions(e):
    #     tb = traceback.format_exc()
    #     timestamp = time.strftime('[%Y-%b-%d %H:%M]')
    #     logger.error('%s %s %s %s %s 5xx INTERNAL SERVER ERROR\n%s\n%s', timestamp, request.remote_addr,
    #                  request.method, request.scheme, request.full_path, tb, e)
    #     return e.status_code

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def catch_all(path):
        build_folder = dir_path.joinpath('frontend', 'build')

        if path != "" and os.path.exists(dir_path.joinpath(build_folder, path)):
            if path.count("/") > 1:
                [path, filename] = path.rsplit("/", maxsplit=1)
                return send_from_directory(dir_path.joinpath(build_folder, path), filename)
            else:
                filename = path
                return send_from_directory(dir_path.joinpath(build_folder), filename)
        else:
            return render_template("index.html")

    # Run ASync Threads
    @app.before_first_request
    def async_threads():
        
        try:
            # Reset Claim Status For Users When It Reaches 24 hrs
            async_reset_claim_status = Thread(target=reset_daily_claim_status)
            async_reset_claim_status.start()
        
            # Distribute Coupons After Display Time Is Over
            async_distribute_coupons = Thread(target=distribute_coupons)
            async_distribute_coupons.start()
        
            # Check if Group is Expired or Finished
            async_check_group_expiration = Thread(target=check_coupons_expiration_date)
            async_check_group_expiration.start()
        except Exception as e:
            print(e)

    return app


# Functions
def reset_daily_claim_status():
    from flaskr.Models.models import Users
    while True:
        with app.app_context():
            try:
                users = Users.query.filter_by(claimed_today=True).all()
                current_time = datetime.now()
                for u in users:

                    time_diff = current_time - u.claim_date

                    validate_diff = time_diff.total_seconds() / 60  # Change To 3600 in Production.
                    if validate_diff >= 5:  # Change To 24 in Production.
                        u.claimed_today = False
                        u.claimed_date = None
                        u.update()
                logger.error(f"Finish Validating Coupon Claiming For {len(users)} Users At {current_time}")
            except Exception as e:
                print("Error: ", e)

        time.sleep(600)


def distribute_coupons():
    from ast import literal_eval
    from random import sample
    from flaskr.Models.models import Group, Coupon, Users
    from flaskr.History.routes import create_history

    while True:
        with app.app_context():
            groups = Group.query.filter_by(distribute_type='display').filter(
                not_(Group.status.in_(['pending', 'canceled', 'expired', 'finished']))).all()

            current_time = datetime.now()
            for group in groups:
                # Check if Display Time Ends
                if group.distribute_end_date < current_time:
                    claimants = literal_eval(group.claimants)  # Users Who Resigtered To Get A Coupon
                    # Get A Random n (n: coupons_num or num of claimants) Users To Claim This Coupon
                    users = sample(claimants, min(len(claimants), int(group.coupons_left)))
                    for user_id in users:
                        try:
                            receivers = literal_eval(group.receivers)  # Users Who Received A Coupon
                            number_of_coupon = int(group.coupons_left)  # Number of Coupons Left
                            # Check if this User Has Received The Coupon Already
                            if user_id not in receivers and number_of_coupon > 0:
                                # Create A New Coupon With User ID
                                new_coupon = Coupon(
                                    coupon_code=group.coupon_code,
                                    group_id=group.id,
                                    user_id=user_id
                                )
                                new_coupon.insert()

                                # Add This User To Receivers List
                                receivers.append(user_id)

                                # Update Group Coupons Number & Receivers List

                                number_of_coupon -= 1

                                group.coupons_left = str(number_of_coupon)
                                group.receivers = str(receivers)
                                group.update()

                                user = Users.query.get(user_id)
                                if user:
                                    # Create A History (User)
                                    create_history(
                                        entity_type="Users",
                                        entity=user,
                                        record_state="succeed",
                                        record_type="coupon_request_on_display_received",
                                        params={
                                            "group": group.coupon_code,
                                            "qr_code": new_coupon.qr_code,
                                            "price": group.coupon_price
                                        }
                                    )
                                    # Create A History (Coupon)
                                    create_history(
                                        entity_type="Coupons",
                                        entity=new_coupon,
                                        record_state="succeed",
                                        record_type="coupon_received_on_display",
                                        params={
                                            "user": user.username,
                                            "qr_code": new_coupon.qr_code
                                        }
                                    )
                        except Exception as e:
                            print(e)
                        time.sleep(0.5)

                    try:
                        # Create A History
                        create_history(
                            entity=group,
                            entity_type="Groups",
                            record_state="succeed",
                            record_type="display_distribution_ends"
                        )
                        group.distribute_type = 'request'
                        group.update()
                    except Exception as e:
                        print(e)
                    logger.error(f'Finish Distributing Coupons From Group #{group.id} For {len(users)} Users')

        time.sleep(301)


def check_coupons_expiration_date():
    from ast import literal_eval
    from flaskr.Models.models import Group
    from flaskr.History.routes import create_history
    while True:
        with app.app_context():
            groups = Group.query.filter(not_(Group.status.in_(['expired', 'pending', 'canceled']))).all()
            current_date = datetime.now()
            for group in groups:
                if current_date > group.expire_date:
                    coupons = group.coupons

                    for coupon in coupons:
                        offers = coupon.offer
                        for offer in offers:
                            offer.delete()
                        coupon.coupon_status = 'expired'
                        coupon.update()

                        # Create A History
                        if coupon.coupon_status not in ['used', 'expired', 'canceled']:
                            create_history(
                                entity=None,
                                entity_type="Users",
                                record_state='succeed',
                                record_type="group_expired",
                                params={
                                    'user_id': coupon.user_id,
                                    'code': coupon.coupon_code
                                }
                            )

                    group.status = 'expired'
                    group.update()

                    # Create A History
                    create_history(
                        entity=group,
                        entity_type="Groups",
                        record_state="succeed",
                        record_type="group_expired"
                    )

                elif current_date > group.on_site and group.status != "finished":
                    group.status = 'finished'
                    group.update()
                    # Create A History
                    create_history(
                        entity=group,
                        entity_type="Groups",
                        record_state="succeed",
                        record_type="group_display_expired"
                    )
                elif current_date > group.display_expire_date:
                    if group.coupons_left == 0 and group.status != "finished":
                        group.status = 'finished'
                        group.update()
                        # Create A History
                        create_history(
                            entity=group,
                            entity_type="Groups",
                            record_state="succeed",
                            record_type="group_coupons_ends"
                        )
            logger.error(f"Finish Checking Expiration & Finishing Date For {len(groups)} Groups At {current_date}")

        time.sleep(121)


def send_async_mail(msg, loop=0):
    with app.app_context():

        SENDER = os.getenv('EMAIL_SENDER')
        PASSW = os.getenv('EMAIL_PASSW')
        SMTP = os.getenv('SMTP_CONF')
        try:
            with smtplib.SMTP_SSL(SMTP, 465) as smtp:
                smtp.login(SENDER, PASSW)
                smtp.send_message(msg)
        except socket.gaierror as gerr:
            print("Socket GaiError: ", gerr)
            if loop < 5:
                loop += 1
                send_async_mail(msg=msg, loop=loop)
        except socket.error as err:
            print("Socket Error: ", err)
            if loop < 5:
                loop += 1
                send_async_mail(msg=msg, loop=loop)
        except Exception as e:
            print("Error: ", e)


def send_async_sms(url):
    with app.app_context():
        import requests
        try:
            resp = requests.get(url)
            print(resp.text)
            status = resp.text[0]
            if status != '3':
                pass
                # Send A Notification Message To Admin.
                # notifyAdmin()
        except Exception as e:
            print(e)
