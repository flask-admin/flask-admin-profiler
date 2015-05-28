import os.path as op

from flask_admin import BaseView


class ProfilerBaseView(BaseView):
    base_template = 'admin/base.html'

    def __init__(self, name, category=None, **kwargs):
        self.base_path = op.dirname(__file__)

        super(ProfilerBaseView, self).__init__(name,
                                               category=category,
                                               static_folder=op.join(self.base_path, 'static'),
                                               **kwargs)

    # Override template path
    def create_blueprint(self, admin):
        blueprint = super(ProfilerBaseView, self).create_blueprint(admin)
        blueprint.template_folder = op.join(self.base_path, 'templates')
        return blueprint
