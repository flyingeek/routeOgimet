from editolidoProxy import load_ofp
from editolido.geopoint import GeoPointEncoder
import json
import os.path
import sys

BASEDIR = 'ofp'


def pdf2json(pathname):
    json_file = os.path.splitext(pathname)[0] + '.route.json'
    ofp = load_ofp(pathname)
    with open(json_file, "w") as f:
        json.dump(ofp.route.route, f, cls=GeoPointEncoder)
        print(json_file)


def main(argv):  # pragma: no cover
    if len(argv) > 0:
        for pathname in argv:
            pdf2json(pathname)
    else:
        dirs = os.listdir(BASEDIR)
        for file in dirs:
            if '.pdf' == os.path.splitext(file)[1]:
                pdf2json(os.path.join(BASEDIR, file))


if __name__ == '__main__':
    main(sys.argv[1:])
