import os
from sqlalchemy import desc
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, abort
from flask_login import current_user, logout_user
from flaskr.Models.models import Users, Tickets, Notifications

from flaskr.utils import sendNotifications

# Auth
from flaskr.Auth.auth import requires_auth

from ast import literal_eval

TICKETS = os.getenv('TICKETS')
ALL = os.getenv('ALL')


tickets = Blueprint(__name__, "tickets")


@tickets.route("/api/user/tickets")
def get_tickets():

    if not current_user.is_authenticated:
        abort(400, {
            'msg': 'User is not logged-in',
            'code': 'NO_USER'
        })

    tickets_ = [t.display() for t in Tickets.query.filter_by(
        user_id=current_user.id).order_by(desc(Tickets.id)).all()]

    return jsonify({
        'tickets': tickets_,
        'success': True
    })


@tickets.route("/api/user/tickets/<int:ticket_id>")
def get_ticket(ticket_id):

    ticket = Tickets.query.get(ticket_id)

    if not ticket:
        abort(404, {
            'msg': f'No ticket match ID #{ticket_id}',
            'code': 'NO_TICKET'
        })

    is_admin = checkAdmin(current_user) and ticket.user_id != current_user.id
    if not is_admin:
        if not current_user.is_authenticated or ticket.user_id != current_user.id:
            abort(400, {
                'msg': 'You can only show your tickets',
                'code': 'NOT_YOURS'
            })

    return jsonify({
        'ticket': ticket.display(),
        'is_admin': is_admin,
        'success': True
    })


@tickets.route("/api/user/tickets", methods=['GET', 'POST'])
def create_ticket():

    req = request.get_json()

    if not req:
        abort(400, {
            'msg': 'Request is not valid',
            'code': 'INVALID_REQUEST'
        })

    title = req.get('title')
    email = req.get('email')
    type_ = req.get('type')
    message = req.get('message')

    if not title or not type_ or not message:
        abort(400, {
            'msg': 'Request is not valid',
            'code': 'INVALID_REQUEST'
        })

    try:
        messages = [{"body": message, "image": current_user.profile_img,
                     "user": current_user.username, "date": datetime.now().timestamp()}]
        new_ticket = Tickets(
            title=title,
            email=email,
            type_=type_,
            messages=str(messages)
        )
        new_ticket.user_id = current_user.id
        new_ticket.insert()
    except Exception as e:
        abort(500, e)

    tickets_ = [t.display() for t in Tickets.query.filter_by(
        user_id=current_user.id).order_by(Tickets.status).all()]

    return jsonify({
        'tickets': tickets_,
        'success': True
    })


@tickets.route("/api/user/tickets/<int:ticket_id>", methods=['POST'])
def respond_ticket(ticket_id):
    ticket = Tickets.query.get(ticket_id)

    if not ticket:
        abort(404, {
            'msg': f'No ticket match ID #{ticket_id}',
            'code': 'NO_TICKET'
        })

    req = request.get_json()

    if not req:
        abort(400, {
            'msg': 'Invalid request',
            'code': 'INVALID_REQUEST'
        })

    message = req.get('message')
    status = req.get('status')
    is_admin = checkAdmin(current_user) and ticket.user_id != current_user.id
    if not is_admin:
        if not current_user.is_authenticated or ticket.user_id != current_user.id:
            abort(400, {
                'msg': 'You can only show your tickets',
                'code': 'NOT_YOURS'
            })
        else:
            # Ticket Owner Actions
            try:
                messages = literal_eval(ticket.messages)
                messages.append(
                    {"body": message, "image": current_user.profile_img,
                     "user": current_user.username, "date": datetime.now().timestamp()})

                ticket.messages = str(messages)
                ticket.last_activity = datetime.now()
                ticket.status = status or 'open'

                ticket.update()
            except Exception as e:
                abort(500, e)
    else:
        # Admin Actions
        try:
            responds = literal_eval(ticket.responds)
            responds.append(
                {"body": message, "image": current_user.profile_img,
                 "user": current_user.username, "date": datetime.now().timestamp()})

            ticket.responds = str(responds)
            ticket.last_activity = datetime.now()
            ticket.status = status or 'waiting'

            ticket.update()

            # Create A Notification For The User
            new_notif = Notifications(
                notification=f"تم إضافة رد جديد لتذكرتك ({ticket.title}), رقم التذكرة #{ticket_id}.",
            )
            new_notif.user_id = ticket.user_id
            new_notif.insert()

            # Send Email
            user = Users.query.get(ticket.user_id)
            sendNotifications(
                key="notifications",
                params={
                    'email': user.email,
                    'username': user.username,
                    'msg': f"تم إضافة رد جديد لتذكرتك ({ticket.title}), رقم التذكرة #{ticket_id}."
                }
            )
        except Exception as e:
            abort(500, e)

    return jsonify({
        'ticket': ticket.display(),
        'is_admin': is_admin,
        'success': True
    })


@tickets.route('/api/user/tickets/<int:ticket_id>/close')
def close_ticket(ticket_id):
    ticket = Tickets.query.get(ticket_id)

    if not ticket:
        abort(404, {
            'msg': f'No ticket match ID #{ticket_id}',
            'code': 'NO_TICKET'
        })

    is_admin = checkAdmin(current_user) and ticket.user_id != current_user.id
    if not is_admin:
        if not current_user.is_authenticated or ticket.user_id != current_user.id:
            abort(400, {
                'msg': 'You can only show your tickets',
                'code': 'NOT_YOURS'
            })
        else:
            # Ticket Owner Actions
            try:
                ticket.status = 'closed'

                ticket.update()
            except Exception as e:
                abort(500, e)
    else:
        # Admin Actions
        try:
            ticket.status = 'closed'

            ticket.update()
        except Exception as e:
            abort(500, e)

    return jsonify({
        'ticket': ticket.display(),
        'is_admin': is_admin,
        'success': True
    })


def checkAdmin(user):
    if not user.is_authenticated:
        return False

    permissions = [TICKETS, ALL]
    user_perms = literal_eval(user.permissions)

    for perm in user_perms:
        if perm in permissions:
            return True

    return False
