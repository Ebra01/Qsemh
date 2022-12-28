import os
from flaskr import SUPERADMIN, bcrypt
from flaskr.Models.models import Users, StaticLabels

ADMIN_USERNAME = os.getenv('ADMIN_USERNAME')
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL')
ADMIN_FULLNAME = os.getenv('ADMIN_FULLNAME')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')
ADMIN_PHONE = os.getenv('ADMIN_PHONE')

# Permissions
ALL = os.getenv('ALL')


def create_admin():
    try:

        admin = Users.query.filter_by(email=ADMIN_EMAIL).first()

        if not admin:
            try:
                new_admin = Users(
                    username=ADMIN_USERNAME,
                    email=ADMIN_EMAIL,
                    fullname=ADMIN_FULLNAME,
                    phone=ADMIN_PHONE,
                    country="السعودية",
                    password=bcrypt.generate_password_hash(ADMIN_PASSWORD).decode('utf-8')
                )
                new_admin.permissions = str([ALL])
                new_admin.guid = SUPERADMIN
                new_admin.is_super = True
                new_admin.is_active = True
                new_admin.insert()
            except:
                pass
    except:
        pass


def create_basic_static_data():
    # Create Elements
    elements = {
        'SA': {
            'country': {
                'en': 'Saudi Arabia',
                'ar': 'السعودية'
            },
            'telecode': '966',
            'cities': {
                'ar': ["الرياض", "جدة", "مكة"],
                'en': ["Riyadh", "Jeddah", "Makkah"]
            }
        },
        'CouponTypes': {
            'ar': [
                'مطعم',
                'مقهى',
                'مطعم-مقهى'
            ],
            'en': [
                'Restaurant',
                'Coffee Shop',
                'Restaurant-Coffee'
            ]
        }
    }

    types = {
        'SA': {
            'title': 'الدولة والمدن',
            'description': 'قائمة المدن للمملكة العربية السعودية, يتم الإختيار منها في الإدخال.',
            'key': 'country'
        },
        'CouponTypes': {
            'title': 'أنواع الكوبونات',
            'description': 'قائمة أنواع الكوبونات, يتم الإختيار منها في الإدخال.',
            'key': 'coupon_types'
        }
    }

    for key in elements:

        label = StaticLabels.query.filter_by(label=key).first()

        if label:
            # Skip if label Exists
            continue

        values = elements[key]

        try:
            # Create a Country in Static Labels
            new_label = StaticLabels(
                label=key,
                values=str(values),
                description=types[key].get('description'),
                name=types[key].get('title'),
                key=types[key].get('key')
            )

            new_label.insert()

        except:
            pass

    # Create Groups Types
