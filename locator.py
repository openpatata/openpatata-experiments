
import itertools as it
import json
from pathlib import Path

import begin
import cartopy.crs as ccrs
import cartopy.feature as cf
import icu
import matplotlib.pyplot as plt
from multidict import MultiDict
import seaborn  # noqa

from scrapers.models import Question
from stemming import stem

dummy = object()

capital_letters = 'ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ'

decompose = icu.Transliterator.createInstance('any-NFD').transliterate
normalise = icu.Transliterator.createInstance('any-NFD; '
                                              '[:nonspacing mark:] any-remove; '
                                              '[:punctuation:] any-remove; '
                                              'any-upper').transliterate

locations = [{**l, 'name': decompose(l['name'])}
             for p in Path('data').glob('childrenJSON*')
             for l in json.load(p.open())['geonames']]
location_pairs = MultiDict((' '.join(stem(w)
                                     for w in normalise(l['name']).split()), l)
                           for l in locations)
location_stems = set(location_pairs)


def prepare_text(text):
    text = (i if i[0] in capital_letters else dummy
            for i in text.strip(' «»').split())
    text = it.groupby(text, lambda i: i is dummy)
    text = {' '.join(stem(normalise(i)) for i in v)
            for k, v in text
            if k is False}
    return text


def parse_question(question):
    text = decompose(question['text'])
    return sorted({(i['geonameId'], question['_id'])
                   for m in prepare_text(text) & location_stems
                   for i in location_pairs.getall(m)} |
                  {(i['geonameId'], question['_id'])
                   for i in locations if i['name'] in text})


def gen_locations():
    return [{**l, '_id': l['geonameId']} for l in locations]


def gen_matches(query={}):
    qs_by_geonameid = it.groupby(sorted(p
                                        for q in Question.collection.find(query)
                                        for p in parse_question(q)),
                                 key=lambda i: i[0])
    return [{'_id': k, 'question_ids': [i for _, i in v]}
            for k, v in qs_by_geonameid]


@begin.subcommand
def plot(find_query='{}', filename='map.svg'):
    res = '10m'

    location_dict = {i['geonameId']: i for i in locations}
    matches = gen_matches(json.loads(find_query))
    max_len = max(len(i['question_ids']) for i in gen_matches())

    ax = plt.axes(projection=ccrs.Mercator())
    ax.set_extent((32, 35, 34.5, 35.75))
    ax.coastlines(resolution=res)
    ax.add_feature(cf.NaturalEarthFeature(category='cultural',
                                          name='admin_0_disputed_areas',
                                          scale=res,
                                          facecolor='None',
                                          edgecolor='gray'))
    ax.add_feature(cf.NaturalEarthFeature(category='cultural',
                                          name='admin_1_states_provinces_lines',
                                          scale=res,
                                          facecolor='None',
                                          edgecolor='gray'))
    for match in matches:
        location = location_dict[match['_id']]
        ax.plot(location['lng'], location['lat'], 'mo',
                markersize=3 + ((len(match['question_ids']) * 7) / max_len),
                transform=ccrs.Geodetic())
    for location in set(location_dict) - {m['_id'] for m in matches}:
        location = location_dict[location]
        ax.plot(location['lng'], location['lat'], 'yo',
                markersize=1, transform=ccrs.Geodetic())

    plt.suptitle('Settlements in MP questions with query\n{}'.format(find_query))
    plt.title('''\
Settlements that have received no mentions are coloured in yellow.
Marker size represents the number of questions (max: {}; max shown: {}).'''
              .format(max_len, max(len(i['question_ids']) for i in matches)),
              fontsize=10)
    plt.savefig(filename, orientation='landscape')


@begin.subcommand(name='print')
def print_(collection):
    out = {'locations': gen_locations, 'matches': gen_matches}[collection]()
    print(json.dumps(out, ensure_ascii=False, indent=2))

print_.__name__ = 'print'


@begin.start
def main():
    pass
