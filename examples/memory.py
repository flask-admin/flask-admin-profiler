from flask import Flask
import flask_admin as admin
from flask_admin_profiler import MemoryProfiler

# Create flask app
app = Flask(__name__, template_folder='templates')
app.debug = True


# Flask views
@app.route('/')
def index():
    return '<a href="/admin/">Click me to get to Admin!</a>'


# Create admin interface
admin = admin.Admin(name="Simple Memory Profiler")
admin.add_view(MemoryProfiler('Memory'))
admin.init_app(app)


if __name__ == '__main__':
    # Start app
    app.run()
