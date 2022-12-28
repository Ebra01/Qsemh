import os
# For AWS S3
from boto3 import client as botoClient, resource

# Async Messaging
from threading import Thread
from flaskr import send_async_mail, send_async_sms

# User Data
from flaskr.Models.models import Users

# For Email
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


ACCESS_KEY = os.getenv('AWS_ACCESS_KEY')
SECRET_KEY = os.getenv('AWS_SECRET_KEY')
REGION = os.getenv('REGION')

s3 = botoClient(
    's3',
    region_name=REGION,
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY
)

s3_resource = resource(
        's3',
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name=REGION
)


# Handle Notifications
def sendNotifications(key, params=None):
    MESSAGES = {
        'account_activation': {
            'msg_title': 'تفعيل الحساب | Account Activation',
            'msg_text': f"""رابط التفعيل: {params.get('activation_link')}""",
            'msg_html': f"""
                        <div dir='rtl'>
                            <p style="font-weight:700!important;">
                                لقد قمت بالتسجيل في موقع قسيمة, لتفعيل حسابك  
                                <a href="{params.get('activation_link')}"> إضغط هنا</a>
                                <br/><br/>
                                أو من خلال هذا الرابط :
                                <br/>
                                {params.get('activation_link')}
                            </p>
                            <p>
                                إذا لم تكن أنت من قام بالتسجيل, الرجاء تجاهل هذه الرسالة.
                            </p>
                        </div>
                    """,
            'msg_initial': ""
        },
        'notifications': {
            'msg_title': 'تنبيه جديد | Notification',
            'msg_text': 'لديك تنبيه جديد في موقع قسيمة.',
            'msg_html': f"""
                            <p>{params.get('msg')}</p>
                        """,
            'msg_initial': "لديك تنبيه جديد في موقع قسيمة:"
        }
    }

    email = params.get('email')
    username = params.get('username')
    # phone = params.get('phone')
    message = MESSAGES[key]

    notification_handler(
        email=email,
        user=username,
        message_text=message['msg_text'],
        message_html=message['msg_html'],
        message_initial=message['msg_initial'],
        title=message['msg_title']
    )

    # user = Users.query.filter_by(phone=phone).first()

    # if user and user.from_ksa and key == "account_activation":
    #     sms_handler(
    #         phone=phone,
    #         message=message['msg_text']
    #     )


# Auto Mail Service
def notification_handler(email, title, user, message_initial, message_html, message_text):
    html_object = f"""\
    <div style="unicode-bidi:bidi-override!important;direction:unset!important;text-align:right;font-size:1.25rem;">
        <div style="background-color:#f2f2f2;width:100%;padding-right:15px;padding-left:15px;margin-right:auto;margin-left:auto;text-align:center;padding:3rem!important;">
        <a href="https://qsemh.com/">
          <img src="https://qsemh.com/static/media/logo-d.70ee291e.png" style="max-width:100%;height:auto;" width="400px" alt="Logo" title="logo">
        </a>
      </div>
    
      <div style="background-color:#fff;width:100%;padding-right:15px;padding-left:15px;margin-right:auto;margin-left:auto;text-align:center;padding:3rem!important;">
        <div style="display:-ms-flexbox;display:flex;-ms-flex-wrap:wrap;flex-wrap:wrap;margin-right:-15px;margin-left:-15px;">
          <div style="-ms-flex:0 0 16.666667%;flex:0 0 16.666667%;max-width:16.666667%;"></div>
          <div style="text-align:right;-ms-flex:0 0 66.666667%;flex:0 0 66.666667%;max-width:66.666667%;">
    
            <p style="font-size:1.5rem;font-weight:700!important;">مرحباً {user}،</p>
            
            <p>{message_initial}</p>
    
            {message_html}
    
            <p style="margin-top:1.5rem!important;">
              مع أطيب التحيات،
              <br>
              <a style="text-decoration:none;" href="https://qsemh.com">موقع قسيمة.</a>
            </p>
    
          </div>
    
        </div>
      </div>
    </div>
    """

    try:

        msg = MIMEMultipart('alternative')

        msg['From'] = 'noreply@qsemh.com'
        msg['To'] = email
        msg['Subject'] = title
        msg.attach(MIMEText(message_text, 'plain'))
        msg.attach(MIMEText(html_object, 'html'))

        thr = Thread(target=send_async_mail, args=[msg])
        thr.start()

    except Exception:
        raise Exception('Error While Sending Mail')


# Auto SMS Service
def sms_handler(phone, message):

    BASE_URL = os.getenv('SMS_BASE_URL')
    SENDER = os.getenv('SMS_SENDER')
    USERNAME = os.getenv('SMS_USERNAME')
    PASSW = os.getenv('SMS_PASSW')

    receiver = f'{phone[1:4]}{phone[5:]}'

    print('Receiver: ', receiver)

    # Build SMS Message Sender URL
    url = f'{BASE_URL}&username={USERNAME}&password={PASSW}&sender={SENDER}&numbers={receiver}&message={message}'
    send_async_sms(url)



