import copy
import json
import time
import plotly.graph_objects as go
import numpy as np
import sys
if "./editolido" not in sys.path:
    sys.path.append("./editolido")
from editolido.geolite import rad_to_km, km_to_rad
from editolido.geoindex import GeoGridIndex
from editolido.geopoint import as_geopoint
from editolido.ogimet import get_nearest_wmo as get_nearest_wmo_results
from editolido.route import Route

start_time = time.time()
wmo_grid = GeoGridIndex()
wmo_grid.load()
wmo_loading_time = (time.time() - start_time) * 1000
dtype = [('name', 'object'), ('lat', 'float'), ('lng', 'float')]

wmo = np.array(
    [tuple(item) for sublist in wmo_grid.data.values() for item in sublist],
    dtype)


class DebugRoute(Route):
    """
    DebugRoute allows:
     - to add a name on split points
     - to get the route as a np array
    """
    def __init__(self, *args, **kwargs):
        super(DebugRoute, self).__init__(*args, **kwargs)

    def split(self, *args, **kwargs):
        counter = 0
        label = ''
        for point in super(DebugRoute, self).split(*args, **kwargs):
            p = copy.copy(point)
            if p.name:
                label = p.name
                counter = 0
            else:
                counter += 1
            if counter > 0:
                p.name = '{0}-{1}'.format(label, counter)
            yield p

    def as_array(self):
        return np.array([(p.name, float(p.latitude), float(p.longitude)) for p in self.route], dtype)


def get_wmo_stations():
    """
    wmo stations (worldwide)
    :return: numpy.ndarray
    """
    return wmo


def get_bounded_wmo_stations(route):
    """
    wmo stations in the bounding box defined by the route
    :param route: Route
    :return: numpy.ndarray
    """
    latmin = min([p.latitude for p in route]) - 1
    latmax = max([p.latitude for p in route]) + 1
    lngmin = min([p.longitude for p in route]) - 1
    lngmax = max([p.longitude for p in route]) + 1
    return wmo[np.where(
        (wmo['lat'] > latmin) & (wmo['lat'] < latmax)
        & (wmo['lng'] > lngmin) & (wmo['lng'] < lngmax))]


def load_ofp_route(filename):
    """
    reads a json file describing the route
    :param filename: str
    :return: DebugRoute
    """
    with open(filename, "r") as f:
        route = DebugRoute([as_geopoint(d) for d in json.load(f)])
    # add name to geographic waypoints
    for p in route:
        if not p.name:
            p.name = p.dm.replace('00.0', '')
    return route


def get_nearby_wmo(route, grid=wmo_grid):
    all_neighbours = []
    o_index = {}
    neighbour_radius = (rad_to_km(grid.grid_size) / 2.0) - 0.1
    for p in route.split(60, converter=km_to_rad, preserve=True):
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


def get_nearest_wmo(route, grid=wmo_grid):
    ogimet_results = get_nearest_wmo_results(route, grid)
    points = []
    for r in ogimet_results:
        if r.fpl.name:
            r.ogimet.name += ' ({0})'.format(r.fpl.name)
        points.append(r.ogimet)
    return points


def scatter_geopoints(points, **options):
    data = list(zip(*([p.name, float(p.latitude), float(p.longitude)] for p in points)))
    return go.Scattergeo(
        lon=data[2],
        lat=data[1],
        text=data[0],
        **options
    )


def basemap(route=None, nearby_wmo=None, nearest_wmo=None, route_color='#A825DA', title='',
            text_labels=('waypoints', 'splits',), legend_only=('splits',)):
    fig = go.Figure()
    if nearby_wmo:
        fig.add_trace(
            scatter_geopoints(nearby_wmo,
                              mode='markers+text' if 'nearby wmo' in text_labels else 'markers',
                              name='nearby wmo',
                              visible="legendonly" if 'nearby wmo' in legend_only else True,
                              marker=dict(size=4, color='blue'),
                              opacity=0.2,
                              ))
    if route:
        fig.add_trace(
            scatter_geopoints(route,
                              mode='lines+markers+text' if 'waypoints' in text_labels else 'lines+markers',
                              name='waypoints',
                              visible="legendonly" if 'waypoints' in legend_only else True,
                              textposition='top center',
                              line=dict(width=1, color=route_color),
                              marker=dict(size=2, color=route_color),
                              textfont=dict(size=8, color=route_color),
                              ))
        fig.add_trace(
            scatter_geopoints(list(route.split(60, converter=km_to_rad, preserve=True)),
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
            scatter_geopoints(nearest_wmo,
                              mode='lines+markers+text' if 'nearest wmo' in text_labels else 'lines+markers',
                              name='nearest wmo',
                              visible="legendonly" if 'nearest wmo' in legend_only else True,
                              marker=dict(size=3, color='blue'),
                              line=dict(width=1, ),
                              opacity=0.2,
                              ))
    fig.update_layout(
        # autosize=False,
        # width=1440,
        # height=860,
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
        legend=go.layout.Legend(orientation='h'),
    )
    if title:
        fig.update_layout(
            title=title,
        )
    fig.update_geos(fitbounds='locations')
    return fig
