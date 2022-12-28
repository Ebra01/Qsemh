from flaskr import bcrypt, SECRET_KEY
from flask_login import login_user, current_user
import os
from random import choice

from flaskr.Models.models import Users, Files

# For AWS S3
from flaskr.utils import s3, s3_resource


# Create History
from flaskr.History.routes import create_history


# For JWT Encoding
import jwt
from time import time

BUCKET = os.getenv('S3_BUCKET')


def validate_current_user(email, passw):
    user = Users.query.filter(Users.email.ilike(email)).first()

    if not user:
        raise Exception({
            'msg': 'No User Match Given Email',
            'code': 'NO_EMAIL'
        })

    # Check if User is Active
    if not user.is_active:
        # Create History Record
        create_history(
            entity_type="Users",
            entity=user,
            record_type="login",
            record_state="failed",
            error_key="NOT_ACTIVE"
        )
        raise Exception({
            'msg': "This User is Not Activated Yet!",
            'code': 'NOT_ACTIVE'
        })

    # Check if User is Disabled
    if user.disabled:
        # Create History Record
        create_history(
            entity_type="Users",
            entity=user,
            record_type="login",
            record_state="failed",
            error_key="DISABLED"
        )
        raise Exception({
            'msg': 'This User is Disabled!',
            'code': 'DISABLED'
        })

    # Check if entered password matches user's hashed password
    if bcrypt.check_password_hash(user.password, passw):
        # Logging the user as current user
        login_user(user, remember=False)
    else:
        # Create History Record
        create_history(
            entity_type="Users",
            entity=user,
            record_type="login",
            record_state="failed",
            error_key="WRONG_PASSW"
        )
        raise Exception({
            'msg': "Wrong Credentials, Try Again!",
            'code': 'WRONG_PASSW'
        })


def addUserToDB(body):
    """
    Add users to the Database, by providing the body
    {username, email, password}
    """
    registered_users = [u.display() for u in Users.query.all()]

    registered_emails = [u['email'] for u in registered_users]
    registered_emails = [u.lower() if u else u for u in registered_emails]
    registered_usernames = [u['username'] for u in registered_users]
    registered_usernames = [u.lower() if u else u for u in registered_usernames]
    registered_phones = [u['phone'] for u in registered_users]
    # Check if the email & username are not already in the Database, and
    # if not, adding the user credentials to the Database.
    if body['email'].lower() in registered_emails:
        raise Exception({
            'msg': "User With Same Email is Already Registered!",
            'code': "EMAIL_EXIST"
        })
    if body['username'].lower() in registered_usernames:
        raise Exception({
            'msg': "User With Same Username is Already Registered!",
            'code': "USERNAME_EXIST"
        })
    if body['phone'] in registered_phones:
        raise Exception({
            'msg': 'User With Same Phone Number is Already Registered!',
            'code': 'PHONE_EXIST'
        })

    hashed_password = bcrypt.generate_password_hash(
        body['password']).decode('utf-8')

    new_user = Users(
        username=body['username'],
        email=body['email'],
        phone=body['phone'],
        from_ksa=body['from_ksa'],
        country=body['country'],
        password=hashed_password,
    )

    # new_user.is_active = True  # Remove This in Production

    new_user.insert()

    return True


def reset_user_passw(user, passw):
    try:
        hashed_password = bcrypt.generate_password_hash(
            password=passw).decode('utf-8')
        user.password = hashed_password
        # Update User
        user.update()
    except Exception:
        raise Exception

    return True


def validate_password(user, passw):
    return bcrypt.check_password_hash(user.password, passw)


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
        raise Exception({
            'msg': 'You Must Log-in First',
            'code': 'NOT_LOGGED_IN'
        })


# AWS S3
def upload_images(img, useUsername=False, username=None):
    """
    Upload An Image To AWS S3
    """

    my_bucket = s3_resource.Bucket(BUCKET)

    filename = img.filename

    if filename == '':
        raise Exception('No File Uploaded')

    if useUsername:
        # Getting Extension From Original Filename
        ext = os.path.splitext(filename)
        ext = ext[1] or '.png'

        filename = f'{username}_profile_img{ext}'
    else:

        try:
            new_file = Files(filename)
            new_file.insert()
            filename = new_file.file_name
        except Exception as e:
            print(e)

    try:
        my_bucket.Object(filename).put(Body=img)
    except Exception as e:
        print(e)
        raise Exception('Error While Uploading Image')

    return filename

