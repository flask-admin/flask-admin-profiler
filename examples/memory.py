from flask import Flask
import flask_admin as admin
from flask_admin_profiler import MemoryProfiler

# Create flask app
app = Flask(__name__, template_folder='templates')
app.debug = True

# Leak testing
HTML_PAYLOAD = '<a href="/admin/">Click me to get to Admin!</a><br><a href="/leak/">Click me to leak dict</a>'
_global_leak = []


class Leaky(object):
    def __init__(self):
        self.data = ['Leaky!']

    def __unicode__(self):
        return self.data


# Flask views
@app.route('/')
def index():
    return HTML_PAYLOAD


@app.route('/leak/')
def leak():
    for _ in xrange(10000):
        _global_leak.append(Leaky())

    return HTML_PAYLOAD


# Create admin interface
admin = admin.Admin(name="Simple Memory Profiler")
admin.add_view(MemoryProfiler('Memory'))
admin.init_app(app)


if __name__ == '__main__':
    # Start app
    app.run()
