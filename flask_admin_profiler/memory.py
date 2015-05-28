import objgraph
import subprocess
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
        self._stat_difference = {}

    # Helpers
    def get_repr(self, obj, limit=250):
        return tools.get_repr(obj, limit=limit)

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

        # Figure out sorting
        sort_field = request.args.get('sort', type=int, default=0)
        sort_dir = bool(request.args.get('dir', type=int, default=0))

        if sort_field < 0 or sort_field > 1:
            sort_field = 0

        # Figure out paging
        page = request.args.get('page', type=int, default=0)
        if page < 0:
            page = 0

        # Helpers
        def generate_sort_url(field):
            new_dir = 0

            if field == sort_field:
                new_dir = 0 if sort_dir else 1
            else:
                new_dir = 0

            return url_for('.objects', type=obj_type, sort=field, dir=new_dir, page=page)

        def generate_pager_url(page):
            return url_for('.objects', type=obj_type, sort=sort_field, dir=sort_dir, page=page)

        # Get data
        objects = objgraph.by_type(obj_type)

        if sort_field == 0:
            # Just performance optimization - no need to format all objects if we're sorting by ID
            sorted_ids = sorted([id(obj) for obj in objects], reverse=sort_dir)

            raw_subset = sorted_ids[page * self.PAGE_SIZE:page * self.PAGE_SIZE + self.PAGE_SIZE]

            subset = [(obj_id, self.get_repr(objgraph.at(obj_id), limit=250)) for obj_id in raw_subset]
        else:
            sorted_objects = sorted([(id(obj), self.get_repr(obj, limit=250)) for obj in objects],
                                    key=lambda v: v[sort_field],
                                    reverse=sort_dir)

            subset = sorted_objects[page * self.PAGE_SIZE:page * self.PAGE_SIZE + self.PAGE_SIZE]

        pages = len(objects) / self.PAGE_SIZE

        # Render everything
        return self.render('flask-admin-profiler/memory/type_objects.html',
                           obj_type=obj_type,
                           objects=subset,
                           page=page,
                           pages=pages,
                           # Helpers
                           generate_sort_url=generate_sort_url,
                           generate_pager_url=generate_pager_url)

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
    @expose('/leaks/', methods=('GET', 'POST'))
    def leaks(self):
        if request.method == 'POST':
            all_objects = objgraph.most_common_types(limit=None)

            prev_stats = self._curr_stats
            self._curr_stats = {k: v for k, v in all_objects}

            # Remove data from prev_stats
            if 'dict' in self._curr_stats:
                self._curr_stats['dict'] -= 1

            if 'tuple' in self._curr_stats:
                self._curr_stats['tuple'] -= len(prev_stats)

            # Calculate difference
            self._stat_difference = []

            if prev_stats:
                for k, v in self._curr_stats.iteritems():
                    if k not in prev_stats:
                        self._stat_difference.append((k, v, v))
                    else:
                        if v > prev_stats[k]:
                            self._stat_difference.append((k, v, v - prev_stats[k]))

                self._stat_difference = sorted(self._stat_difference, key=lambda v: -v[2])

        return self.render('flask-admin-profiler/memory/leaks.html',
                           leaks=self._stat_difference)
