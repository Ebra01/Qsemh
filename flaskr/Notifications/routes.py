import os
from sqlalchemy import not_, desc
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, abort
from flask_login import current_user, logout_user
from flaskr.Models.models import Users, Notifications

# Auth
from flaskr.Auth.auth import requires_auth

from ast import literal_eval


notify = Blueprint(__name__, "notify")


@notify.route('/api/notifications')
def get_notifications():

    if not current_user.is_authenticated:
        abort(400, {
            'msg': 'User is not Logged-in',
            'code': 'NO_USER'
        })

    notifications = Notifications.query.filter(
        Notifications.user_id == current_user.id).order_by(
        desc(Notifications.date)).order_by(Notifications.viewed).all()

    # try:
    #     for notif in notifications:
    #         notif.viewed = True
    #         notif.update()
    # except Exception as e:
    #     abort(500, e)

    return jsonify({
        'notifications': [n.display() for n in notifications],
        'success': True
    })


@notify.route('/api/notifications/<int:notif_id>/read', methods=['GET', 'POST'])
def mark_as_read(notif_id):
    if not current_user.is_authenticated:
        abort(400, {
            'msg': 'User is not Logged-in',
            'code': 'NO_USER'
        })

    notif = Notifications.query.get(notif_id)

    if not notif:
        abort(404, {
            'msg': f'No Notification Match ID #{notif_id}',
            'code': 'NO_MATCH_ID'
        })

    if notif.user_id != current_user.id:
        abort(400, {
            'msg': "You can only view your own notifications",
            'code': 'NOT_YOURS'
        })

    try:
        notif.viewed = True
        notif.update()
    except Exception as e:
        abort(500, e)

    notifications = [n.display() for n in Notifications.query.filter(
        Notifications.user_id == current_user.id).order_by(
        Notifications.date).order_by(Notifications.viewed).all()]

    return jsonify({
        'notifications': notifications,
        'success': True
    })


@notify.route('/api/notifications/<int:notif_id>/unread', methods=['GET', 'POST'])
def mark_as_unread(notif_id):
    if not current_user.is_authenticated:
        abort(400, {
            'msg': 'User is not Logged-in',
            'code': 'NO_USER'
        })

    notif = Notifications.query.get(notif_id)

    if not notif:
        abort(404, {
            'msg': f'No Notification Match ID #{notif_id}',
            'code': 'NO_MATCH_ID'
        })

    if notif.user_id != current_user.id:
        abort(400, {
            'msg': "You can only view your own notifications",
            'code': 'NOT_YOURS'
        })

    try:
        notif.viewed = False
        notif.update()
    except Exception as e:
        abort(500, e)

    notifications = [n.display() for n in Notifications.query.filter(
        Notifications.user_id == current_user.id).order_by(
        Notifications.date).order_by(Notifications.viewed).all()]

    return jsonify({
        'notifications': notifications,
        'success': True
    })


@notify.route('/api/notifications/<int:notif_id>/delete', methods=['GET', 'POST'])
def delete_notification(notif_id):
    if not current_user.is_authenticated:
        abort(400, {
            'msg': 'User is not Logged-in',
            'code': 'NO_USER'
        })

    notif = Notifications.query.get(notif_id)

    if not notif:
        abort(404, {
            'msg': f'No Notification Match ID #{notif_id}',
            'code': 'NO_MATCH_ID'
        })

    if notif.user_id != current_user.id:
        abort(400, {
            'msg': "You can only view your own notifications",
            'code': 'NOT_YOURS'
        })

    try:
        notif.delete()
    except Exception as e:
        abort(500, e)

    notifications = [n.display() for n in Notifications.query.filter(
        Notifications.user_id == current_user.id).order_by(
        Notifications.date).order_by(Notifications.viewed).all()]

    return jsonify({
        'notifications': notifications,
        'success': True
    })


@notify.route('/api/notifications/all/read', methods=['GET', 'POST'])
def mark_all_as_read():
    if not current_user.is_authenticated:
        abort(400, {
            'msg': 'User is not Logged-in',
            'code': 'NO_USER'
        })

    notifications_to_view = Notifications.query.filter(
        Notifications.user_id == current_user.id).filter(
        not_(Notifications.viewed)).all()

    try:
        for notif in notifications_to_view:
            notif.viewed = True
            notif.update()
    except Exception as e:
        abort(500, e)

    notifications = [n.display() for n in Notifications.query.filter(
        Notifications.user_id == current_user.id).order_by(
        Notifications.date).order_by(Notifications.viewed).all()]

    return jsonify({
        'notifications': notifications,
        'success': True
    })


@notify.route('/api/notifications/all/delete', methods=['GET', 'POST'])
def delete_all_notifications():
    if not current_user.is_authenticated:
        abort(400, {
            'msg': 'User is not Logged-in',
            'code': 'NO_USER'
        })

    notifications_to_delete = Notifications.query.filter(
        Notifications.user_id == current_user.id).all()

    try:
        for notif in notifications_to_delete:
            notif.delete()
    except Exception as e:
        abort(500, e)

    notifications = [n.display() for n in Notifications.query.filter(
        Notifications.user_id == current_user.id).order_by(
        Notifications.date).order_by(Notifications.viewed).all()]

    return jsonify({
        'notifications': notifications,
        'success': True
    })
