import copy
from collections import namedtuple
import math
import base64
import json
import time
import plotly.graph_objects as go
from editolido.ofp import OFP, io_base64_decoder, ofp_to_text
from editolido.geolite import rad_to_km, km_to_rad
from editolido.geoindex import GeoGridIndex
from editolido.geopoint import as_geopoint
from editolido.ogimet import Result
from editolido.route import Route

start_time = time.time()
wmo_grid = GeoGridIndex()
wmo_grid.load()
wmo_loading_time = (time.time() - start_time) * 1000


def load_ofp(filename):
    with open(filename, "rb") as pdf_file:
        pdf_io = io_base64_decoder(base64.b64encode(pdf_file.read()))
        return OFP(ofp_to_text(pdf_io))


def load_ofp_route(filename):
    with open(filename, "r") as f:
        route = Route([as_geopoint(d) for d in json.load(f)])
    for p in route:
        if not p.name:
            p.name = p.dm.replace('00.0', '')
    return route


def split_route_with_label(route, length=60, converter=km_to_rad, preserve=True):
    counter = 0
    label = ''
    for point in route.split(length, converter=converter, preserve=preserve):
        p = copy.copy(point)
        if p.name:
            label = p.name
            counter = 0
        else:
            counter += 1
        if counter > 0:
            p.name = '{0}-{1}'.format(label, counter)
        yield p


def get_nearby_wmo(route, grid=wmo_grid):
    all_neighbours = []
    o_index = {}
    neighbour_radius = (rad_to_km(grid.grid_size) / 2.0) - 0.1
    for p in split_route_with_label(route):
        neighbours = grid.get_nearest_points(p, neighbour_radius)
        for n, _ in neighbours:
            if n.name not in o_index:
                o_index[n.name] = [p.name]
                all_neighbours.append(n)
            elif p.name:
                o_index[n.name].append(p.name)
    for n in all_neighbours:
        description = ', '.join(o_index[n.name])
        if description:
            n.name += ' ({0})'.format(description)
    return all_neighbours


def get_nearest_wmo_results(route, wmo_grid):
    # Here we find all ogimet points for our route
    # The same ogimet point can be used by many fpl points
    # prepare o_index which will be used to deduplicate
    # we place in o_index points with the shortest distance
    ogimet_results = []
    o_index = {}
    neighbour_radius = (rad_to_km(wmo_grid.grid_size) / 2.0) - 0.1

    def get_neighbour(point):
        """
        Find neighbour ogimet point
        Prefer fpl point if it exists
        :param point:
        :return: tuple(Geopoint, float)
        """
        neighbours = sorted(
            wmo_grid.get_nearest_points(point, neighbour_radius),
            key=lambda t: t[1]
        )
        if neighbours:
            if point.name in [n.name for n, _ in neighbours]:
                return point, 0
            return neighbours[0][0], neighbours[0][1]
        return None, None

    for p in split_route_with_label(route, 60, converter=km_to_rad, preserve=True):
        neighbour, x = get_neighbour(p)
        if neighbour:
            if neighbour.name in o_index:
                if o_index[neighbour.name][0] > x:
                    o_index[neighbour.name] = (x, p)
            else:
                o_index[neighbour.name] = (x, p)
            ogimet_results.append(Result(p, neighbour))

    # filter using o_index (keep points that were stored in o.index)
    return list(
        filter(lambda r: o_index[r.ogimet.name][1] == r.fpl, ogimet_results)
    )

def get_nearest_wmo(route, grid=wmo_grid):
    ogimet_results = get_nearest_wmo_results(route, grid)
    points = []
    for r in ogimet_results:
        if r.fpl.name:
            r.ogimet.name += ' ({0})'.format(r.fpl.name)
        points.append(r.ogimet)
    return points


def scatter_route(route, **options):
    return go.Scattergeo(
        lon=[p.longitude for p in route],
        lat=[p.latitude for p in route],
        text=[p.name for p in route],
        **options
    )


def basemap(route, nearby_wmo=None, nearest_wmo=None, route_color='#A825DA', title='', text_labels=('waypoints', 'splits',), legend_only=('splits',)):
    fig = go.Figure()
    if nearby_wmo:
        fig.add_trace(
            scatter_route(nearby_wmo,
                          mode='markers+text' if 'nearby wmo' in text_labels else 'markers',
                          name='nearby wmo',
                          visible="legendonly" if 'nearby wmo' in legend_only else True,
                          marker=dict(size=4, color='blue'),
                          opacity=0.2,
                          ))
    fig.add_trace(
        scatter_route(route,
                      mode='lines+markers+text' if 'waypoints' in text_labels else 'lines+markers',
                      name='waypoints',
                      visible="legendonly" if 'waypoints' in legend_only else True,
                      textposition='top center',
                      line=dict(width=1, color=route_color),
                      marker=dict(size=2, color=route_color),
                      textfont=dict(size=8, color=route_color),
                      ))
    fig.add_trace(
        scatter_route(list(split_route_with_label(route)),
                      mode='lines+markers+text' if 'splits' in text_labels else 'lines+markers',
                      name='splits',
                      visible="legendonly" if 'splits' in legend_only else True,
                      textposition='top center',
                      line=dict(width=1, color=route_color),
                      marker=dict(size=2, color=route_color),
                      textfont=dict(size=8, color=route_color),
                      ))
    if nearest_wmo:
        fig.add_trace(
            scatter_route(nearest_wmo,
                          mode='lines+markers+text' if 'nearest wmo' in text_labels else 'lines+markers',
                          name='nearest wmo',
                          visible="legendonly" if 'nearest wmo' in legend_only else True,
                          marker=dict(size=3, color='blue'),
                          line=dict(width=1, ),
                          opacity=0.2,
                          ))
    fig.update_layout(
        legend=go.layout.Legend(orientation='h'),
    )
    fig.update_layout(
        width=1440,
        height=860,
        geo=dict(
            landcolor="rgb(212, 212, 212)",
        ),
        margin=dict(
            l=10,
            r=10,
            b=10,
            t=50,
            pad=4
        ),
    )
    if title:
        fig.update_layout(
            title=title,
        )
    fig.update_geos(fitbounds='locations')
    return fig


# Point proxy to use my python functions
class Point(object):
    def __init__(self, value, name=None, pid=None):
        self.value = value
        self.pid = pid
        if name is None:
            self.name = '{0}_{1}'.format(*value)
        else:
            self.name = name
        self.x = value[0]
        self.y = value[1]

    def xtd_to(self, segment):
        """
        Given the segment AB, computes cross track error
        :param segment: (Point, Point) the segment AB
        :return: float the cross track error
        """
        p1 = segment[0]
        p2 = segment[1]
        x_diff = p2.x - p1.x
        y_diff = p2.y - p1.y
        num = abs(y_diff*self.x - x_diff*self.y + p2.x*p1.y - p2.y*p1.x)
        den = math.sqrt(y_diff**2 + x_diff**2)
        if den == 0:
            return 0
        return num / den

    def distance_to(self, other):
        x_diff = other.x - self.x
        y_diff = other.y - self.y
        return math.sqrt(y_diff**2 + x_diff**2)

