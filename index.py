from flask import Blueprint, session, redirect, url_for # type: ignore

index_bp = Blueprint('index', __name__)

@index_bp.route('/')
def index():
    if not session.get('user_id'):
        return redirect(url_for('login.login')) # Assuming login blueprint/route is named login
    return redirect(url_for('dashboard.dashboard'))
