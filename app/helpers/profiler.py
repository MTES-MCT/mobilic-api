from werkzeug.middleware.profiler import ProfilerMiddleware

from app import app

app.wsgi_app = ProfilerMiddleware(
    app.wsgi_app, sort_by=("tottime",), restrictions=(5,)
)
