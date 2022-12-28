from flask import Blueprint, jsonify
import traceback
import time


errors = Blueprint('errors', __name__)


@errors.app_errorhandler(404)
def error_404(error):
    msg, code = message_handler(error)
    return jsonify({
        'error': 404,
        'message': msg or 'Not Found',
        'code': code,
        'success': False
    }), 404


@errors.app_errorhandler(400)
def error_400(error):
    msg, code = message_handler(error)
    return jsonify({
        'error': 400,
        'message': msg or 'Bad Request',
        'code': code,
        'success': False
    }), 400


@errors.app_errorhandler(405)
def error_405(error):
    msg, code = message_handler(error)
    return jsonify({
        'error': 405,
        'message': msg or 'Method Not Allowed',
        'code': code,
        'success': False
    }), 405


@errors.app_errorhandler(422)
def error_422(error):
    msg, code = message_handler(error)
    return jsonify({
        'error': 422,
        'message': msg or 'Unprocessable',
        'code': code,
        'success': False
    }), 422


@errors.app_errorhandler(500)
def error_500(error):
    msg, code = message_handler(error)
    return jsonify({
        'error': 500,
        'message': msg or 'Something Went Wrong On Our Side',
        'code': code or 'SERVER',
        'success': False
    }), 500


def message_handler(error):
    try:
        from ast import literal_eval
        error_block = str(error).split(':', 1)[1].strip()
        error_block = literal_eval(error_block)

        msg = error_block.get('msg')
        code = error_block.get('code')

        print(
            f"""Error:\n\tMessage : {msg},\n\tCode : {code}""")
    except SyntaxError:
        msg = None
        code = None
    logging(msg, code)
    return msg, code


def logging(msg, err):
    from flaskr import logger
    tb = traceback.format_exc()
    timestamp = time.strftime('[%Y-%b-%d %H:%M]')
    logger.error(f"{timestamp}:: Error: {err}\n Message: {msg}, {tb}")
