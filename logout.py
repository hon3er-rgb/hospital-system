from flask import Blueprint, session, redirect, url_for

logout_bp = Blueprint('logout', __name__)

@logout_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login.login'))
