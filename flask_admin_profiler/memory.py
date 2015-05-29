import objgraph
import subprocess
import gc
from itertools import chain
from collections import defaultdict
from cStringIO import StringIO

from flask import request, redirect, url_for, Response
from flask_admin import expose

from . import base, tools


# Helpers
def format_id(obj):
    return id(obj)


# Admin view
class MemoryProfiler(base.ProfilerBaseView):
    MAX_DEPTH = 20
    PAGE_SIZE = 500

    def __init__(self, *args, **kwargs):
        super(MemoryProfiler, self).__init__(*args, **kwargs)

        self.dot_path = 'dot'

        self._curr_stats = {}
        self._stat_difference = []
        self._obj_difference = {}

    # Helpers
    def get_repr(self, obj, limit=250):
        return tools.get_repr(obj, limit=limit)

    def _pager(self, data_fn, endpoint, **kwargs):
        # Figure out sorting
        sort_field = request.args.get('sort', type=int, default=0)
        sort_dir = bool(request.args.get('dir', type=int, default=0))

        if sort_field < 0 or sort_field > 1:
            sort_field = 0

        # Figure out paging
        page = request.args.get('page', type=int, default=0)
        if page < 0:
            page = 0

        data = data_fn()

        sorted_objects = sorted(data, key=lambda v: v[sort_field], reverse=sort_dir)

        subset = sorted_objects[page * self.PAGE_SIZE:page * self.PAGE_SIZE + self.PAGE_SIZE]

        pages = len(data) / self.PAGE_SIZE

        # Helpers
        def generate_sort_url(field):
            new_dir = 0

            if field == sort_field:
                new_dir = 0 if sort_dir else 1
            else:
                new_dir = 0

            return url_for(endpoint, sort=field, dir=new_dir, page=page, **kwargs)

        def generate_pager_url(page):
            return url_for(endpoint, sort=sort_field, dir=sort_dir, page=page, **kwargs)

        # Final result
        return {
            'data': subset,
            'page': page,
            'pages': pages,
            'generate_sort_url': generate_sort_url,
            'generate_pager_url': generate_pager_url
        }

    # Views
    @expose()
    def overview(self):
        types = objgraph.most_common_types(30)

        return self.render('flask-admin-profiler/memory/overview.html',
                           common_types=types)

    @expose('/type-objects/')
    def objects(self):
        obj_type = request.args.get('type')

        if not obj_type:
            return redirect(url_for('.overview'))

        def get_data():
            return [(id(obj), self.get_repr(obj)) for obj in objgraph.by_type(obj_type)]

        subset = self._pager(get_data, '.objects', type=obj_type)

        return self.render('flask-admin-profiler/memory/type_objects.html',
                           obj_type=obj_type,
                           **subset)

    # Single object
    def _get_request_object(self):
        obj_id = request.args.get('id', type=long)

        if not obj_id:
            return None

        return objgraph.at(obj_id)

    @expose('/inspect/')
    def inspect(self):
        obj = self._get_request_object()
        if obj is None:
            return redirect(url_for('.overview'))

        # Figure out attributes
        attrs = tools.get_public_attrs(obj)

        # Backrefs
        referrers = objgraph.find_backref_chain(obj, objgraph.is_proper_module, 2)
        sorted_referrers = sorted([(self.get_repr(o), o) for o in referrers if id(o) != id(obj)])

        # Refs
        referrents = objgraph.find_ref_chain(obj, objgraph.is_proper_module, 2)
        sorted_referrents = sorted([(self.get_repr(o), o) for o in referrents if id(o) != id(obj)])

        return self.render('flask-admin-profiler/memory/object.html',
                           obj=obj,
                           obj_text=tools.pretty_print(obj),
                           obj_id=format_id(obj),
                           obj_type=tools.get_type(obj),
                           format_id=format_id,
                           attrs=attrs,
                           referrers=sorted_referrers,
                           referrents=sorted_referrents)

    # Plotting
    def _run_dot(self, dot):
        try:
            process = subprocess.Popen([self.dot_path, '-Tpng'],
                                       stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE)
            process.stdin.write(dot)
            process.stdin.close()

            data = process.stdout.read()
            return data
        except:
            return 'Failed to run dot'

    def _render_ref_graph(self, objs):
        io = StringIO()

        objgraph.show_chain(objs, output=io)
        dot = io.getvalue()

        png_image = self._run_dot(dot)
        return Response(png_image, mimetype='image/png')

    @expose('/backrefs-graph/')
    def backref_graph(self):
        obj = self._get_request_object()
        if obj is None:
            return redirect(url_for('.overview'))

        depth = request.args.get('depth', type=int, default=self.MAX_DEPTH)
        if depth > self.MAX_DEPTH:
            depth = self.MAX_DEPTH

        objs = objgraph.find_backref_chain(obj, objgraph.is_proper_module, depth)
        return self._render_ref_graph(objs)

    @expose('/refs-graph/')
    def ref_graph(self):
        obj = self._get_request_object()
        if obj is None:
            return redirect(url_for('.overview'))

        depth = request.args.get('depth', type=int, default=self.MAX_DEPTH)
        if depth > self.MAX_DEPTH:
            depth = self.MAX_DEPTH

        objs = objgraph.find_ref_chain(obj, objgraph.is_proper_module, depth)
        return self._render_ref_graph(objs)

    # Leak manager
    def _capture_stats(self):
        # Prepare and garbage-collect
        self._stat_difference = []
        self._obj_difference = {}

        prev_stats = self._curr_stats
        self._curr_stats = defaultdict(set)

        # Collect object IDs
        gc.collect()

        for obj in gc.get_objects():
            self._curr_stats[tools.get_type(obj)].add(id(obj))

        # Capture difference
        for type_name, type_objects in self._curr_stats.iteritems():
            if type_name not in prev_stats:
                self._stat_difference.append((type_name, len(type_objects), len(type_objects)))

                self._obj_difference[type_name] = type_objects
            else:
                old_objs = prev_stats[type_name]

                if len(type_objects) > len(old_objs):
                    new_objects = type_objects - old_objs

                    self._stat_difference.append((type_name, len(new_objects), len(type_objects)))
                    self._obj_difference[type_name] = new_objects

        self._stat_difference = sorted(self._stat_difference, key=lambda v: v[1], reverse=True)

    @expose('/leaks/', methods=('GET', 'POST'))
    def leaks(self):
        if request.method == 'POST':
            self._capture_stats()

        return self.render('flask-admin-profiler/memory/leaks.html',
                           leaks=self._stat_difference)

    @expose('/leak-objects/')
    def leaked_objects(self):
        obj_type = request.args.get('type')

        if not obj_type or obj_type not in self._obj_difference:
            return redirect(url_for('.leaks'))

        def get_data():
            objs = tools.get_objects_by_id(self._obj_difference[obj_type])
            return [(id(obj), self.get_repr(obj)) for obj in objs]

        subset = self._pager(get_data, '.leaked_objects', type=obj_type)

        return self.render('flask-admin-profiler/memory/leaked_objects.html',
                           obj_type=obj_type,
                           **subset)
