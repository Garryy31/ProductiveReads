from functools import wraps

from flask import flash, redirect, request, session, url_for


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "error")
            return redirect(url_for("auth.login", next_url=request.path))
        return view(*args, **kwargs)

    return wrapped_view
