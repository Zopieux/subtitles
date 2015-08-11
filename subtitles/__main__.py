#!/usr/bin/env python
from __future__ import print_function, unicode_literals, division

import base64
import collections
import io
import gzip
import os
import re
import struct
import traceback
import unicodedata
try:
    from io import BytesIO
except ImportError:
    # Python 2 legacy
    try:
        from cStringIO import StringIO as BytesIO
    except ImportError:
        from StringIO import StringIO as BytesIO
try:
    import xmlrpc.client as xmlrpclib
except ImportError:
    # Python 2 legacy
    import xmlrpclib

VERSION = '0.1'
MAX_LIMIT = 99
FALLBACK_LANG = 'eng'
OPENSUB_URL = 'https://api.opensubtitles.org/xml-rpc'
# parsed from GetSubLanguages()
ISO_TO_OPENSUB_LANGS = {
    'si': 'sin', 'hi': 'hin', 'ja': 'jpn', 'zt': 'zht', 'it': 'ita',
    'mn': 'mon', 'es': 'spa', 'he': 'heb', 'cs': 'cze', 'da': 'dan',
    'sk': 'slo', 'bs': 'bos', 'ur': 'urd', 'zh': 'chi', 'fa': 'per',
    'el': 'ell', 'ze': 'zhe', 'hu': 'hun', 'me': 'mne', 'ms': 'may',
    'eo': 'epo', 'eu': 'baq', 'no': 'nor', 'br': 'bre', 'sw': 'swa',
    'vi': 'vie', 'sv': 'swe', 'sr': 'scc', 'lt': 'lit', 'my': 'bur',
    'tl': 'tgl', 'mk': 'mac', 'nl': 'dut', 'gl': 'glg', 'oc': 'oci',
    'hr': 'hrv', 'pt': 'por', 'is': 'ice', 'hy': 'arm', 'id': 'ind',
    'uk': 'ukr', 'et': 'est', 'ml': 'mal', 'lb': 'ltz', 'ma': 'mni',
    'be': 'bel', 'ta': 'tam', 'sq': 'alb', 'sl': 'slv', 'fr': 'fre',
    'lv': 'lav', 'en': 'eng', 'de': 'ger', 'ar': 'ara', 'ro': 'rum',
    'ca': 'cat', 'te': 'tel', 'ka': 'geo', 'sy': 'syr', 'th': 'tha',
    'ko': 'kor', 'ru': 'rus', 'pl': 'pol', 'bg': 'bul', 'km': 'khm',
    'kk': 'kaz', 'bn': 'ben', 'af': 'afr', 'fi': 'fin', 'tr': 'tur',
    'pb': 'pob'
}


class AbortedError(Exception):
    pass


def slugify(s, ok='-_', lower=True, spaces=False, only_ascii=True):
    """
    Courtesy of Mozilla unicode-slugify, BSD licensed.
    https://github.com/mozilla/unicode-slugify
    """
    rv = []
    for c in unicodedata.normalize('NFKC', s):
        cat = unicodedata.category(c)[0]
        if cat in 'LN' or c in ok:
            rv.append(c)
        elif cat == 'Z':  # space
            rv.append(' ')
        else:
            rv.append(ok[0])
    new = ''.join(rv).strip()
    if not spaces:
        new = re.sub('[-\s]+', ok[0], new)
    new = re.sub(re.escape(ok[0]) + '{2,}', ok[0], new).strip(ok[0])
    new = new.lower() if lower else new
    if only_ascii:
        new = new.encode('ascii', 'ignore').decode('ascii')
    return new


def compute_movie_hash(file_name):
    byte_size = struct.calcsize('<q')
    file_size = os.path.getsize(file_name)
    if file_size < 1 << 17:
        raise ValueError("size too short")

    file_hash = file_size

    with open(file_name, 'rb') as f:
        def compute(file_hash):
            for x in range((1 << 16) // byte_size):
                buff = f.read(byte_size)
                l_value = struct.unpack('<q', buff)[0]
                file_hash += l_value
                file_hash &= 0xffffffffffffffff  # 64 bit
            return file_hash

        file_hash = compute(file_hash)
        f.seek(max(0, file_size - (1 << 16)), io.SEEK_SET)
        file_hash = compute(file_hash)

    return file_size, "{:016x}".format(file_hash)


class Opensubtitles:
    def __init__(self):
        self.client = xmlrpclib.ServerProxy(OPENSUB_URL)
        self.token = None

    def login(self):
        resp = self.client.LogIn('', '', 'en', 'subdl {}'.format(VERSION))
        self.token = resp['token']

    def format_result(self, i, result):
        return "  {:>2d}. [{}] {}".format(
               i, result['SubLanguageID'],
               (result['MovieReleaseName'] or result['MovieName']).strip())

    def download_subtitle(self, result, fname, opts):
        if os.path.exists(fname):
            if opts.exist == 'ignore':
                print("{}: file already exists. Ignoring download."
                      .format(fname))
                raise AbortedError
            elif opts.exist == 'ask':
                while True:
                    answer = input("{}: file already exists. Overwrite? [y/n] "
                                   .format(fname)).strip().lower()
                    if answer == 'n':
                        raise AbortedError
                    if answer == 'y':
                        break
            else:
                print("{}: file already exists. Overwriting.".format(fname))

        try:
            answer = self.client.DownloadSubtitles(self.token, [result['IDSubtitleFile']])
            gziped_data = answer['data'][0]['data']
            with gzip.open(BytesIO(base64.b64decode(gziped_data))) as gziped:
                with open(fname, 'wb') as f:
                    f.write(gziped.read())
            print("Wrote {}".format(fname))
        except Exception:
            traceback.print_exc()
            pass

    def choose_subtitle(self, results, preferred_fname, opts):
        if not results or opts.download == 'none':
            raise AbortedError
        if opts.download == 'first':
            result = results[0]
        elif opts.download == 'ask':
            while True:
                try:
                    index = input("Subtitle to download ({}-{}): "
                                  .format(1, len(results)))
                except EOFError:
                    print()
                    index = None
                if not index:
                    raise AbortedError
                try:
                    index = int(index)
                    if not 1 <= index <= len(results):
                        raise ValueError
                    break
                except ValueError:
                    print("Invalid index. Try again or quit with Ctrl-C.")
            result = results[index - 1]
        else:
            try:
                result = results[int(opts.download) - 1]
            except (IndexError, ValueError):
                print("Invalid --download: {}".format(opts.download))
                raise AbortedError

        try:
            sub_ext = os.path.splitext(result['SubFileName'])[1]
        except (KeyError, IndexError):
            # arbitrary guess
            sub_ext = '.srt'
        if preferred_fname is None:
            fname = slugify(result['MovieReleaseName'] or result['MovieName'])
        else:
            fname = os.path.splitext(preferred_fname)[0]

        fname += sub_ext
        return result, fname

    def download_from_files(self, opts):
        limit = min(MAX_LIMIT, opts.limit)
        langs = ','.join(opts.lang or []) or 'all'

        def process_file(file_obj):
            movie_size, movie_hash = compute_movie_hash(file_obj.name)
            return {
                'sublanguageid': langs,
                'moviehash': movie_hash,
                'moviebytesize': movie_size,
            }

        query_set = []
        hash_to_fileobj = collections.OrderedDict()
        for file_obj in opts.file:
            try:
                attrs = process_file(file_obj)
            except ValueError:
                print("Invalid movie file: {}".format(file_obj.name))
                continue
            query_set.append(attrs)
            hash_to_fileobj[attrs['moviehash']] = file_obj

        if not query_set:
            return

        items = self.client.SearchSubtitles(self.token,
                                            query_set,
                                            {'limit': limit})['data']
        results = collections.defaultdict(list)
        for item in items:
            results[item['MovieHash']].append(item)

        for movie_hash, file_obj in hash_to_fileobj.items():
            movie_results = results[movie_hash][:limit]

            print("Results for: {}".format(file_obj.name))
            if not movie_results:
                print("  (no results)")
                print()
                continue

            for i, result in enumerate(movie_results):
                print(self.format_result(i + 1, result))
            print()

            try:
                result, fname = self.choose_subtitle(movie_results,
                                                     file_obj.name,
                                                     opts)
                self.download_subtitle(result, fname, opts)
            except AbortedError:
                print("Aborted.")

    def download_from_search(self, opts):
        limit = min(MAX_LIMIT, opts.limit)
        query = ' '.join(opts.query).lower()
        attrs = {
            'sublanguageid': ','.join(opts.lang or []) or 'all',
            'query': query,
        }
        results = self.client.SearchSubtitles(self.token,
                                              [attrs],
                                              {'limit': limit})['data']
        results = results[:limit]
        print("Results for: {}".format(query))
        if not results:
            print("  (no results)")
            return

        for i, result in enumerate(results):
            print(self.format_result(i + 1, result))

        try:
            result, fname = self.choose_subtitle(results, None, opts)
            self.download_subtitle(result, fname, opts)
        except AbortedError:
            print("Aborted.")

    def list_languages(self, opts):
        query = ' '.join(opts.query or []).strip().lower()
        for lng in sorted(self.client.GetSubLanguages()['data'],
                          key=lambda e: e['LanguageName'].lower()):
            if (not query or query in lng['LanguageName'].lower()
                    or query in lng['SubLanguageID'].lower()):
                print('{:>24s}: {}'.format(lng['LanguageName'],
                                           lng['SubLanguageID']))


def main():
    import argparse
    import locale
    sys_lang, _ = locale.getdefaultlocale()
    sys_lang = sys_lang.split('_', 1)[0]
    sys_lang = ISO_TO_OPENSUB_LANGS.get(sys_lang, FALLBACK_LANG)

    parser = argparse.ArgumentParser(
        description="Download subtitles from movie files or text query")
    parser.add_argument('-l', '--lang', action='append',
                        help="subtitle languages(s) to download [default: {}]"
                             .format(sys_lang))
    parser.add_argument('-n', '--limit', type=int, default=10,
                        help="search results limit")
    parser.add_argument('-d', '--download', default='first',
                        help="result to download; valid choices are: 'first', "
                             "'ask', 'none', or the result index (1-indexed) "
                             "[default: first]")
    parser.add_argument('-e', '--exist', default='ask',
                        choices=('overwrite', 'replace', 'ignore', 'ask'),
                        help="what to do when subtitle file already exists "
                             "(replace and overwrite have the same meaning) "
                             "[default: ask]")
    sub = parser.add_subparsers(dest='cmd')
    sub_from = sub.add_parser('for',
                              help="download subtitles from a movie file")
    sub_from.add_argument('file', nargs='+', type=argparse.FileType('rb'),
                          help="movie files to search for")
    sub_query = sub.add_parser('search',
                               help="download subtitles from a text search")
    sub_query.add_argument('-o', '--output', help="file name pattern")
    sub_query.add_argument('query', nargs='+',
                           help="search query (title, actor, etc.)")
    sub_lang = sub.add_parser('languages', help="list available languages")
    sub_lang.add_argument('query', nargs='*', help="filter languages")
    args = parser.parse_args()

    if args.lang is None:
        args.lang = [sys_lang]

    if args.cmd is None:
        parser.error("you must use one of the subcommands: "
                     "for, search, languages")
    if args.download not in ('first', 'ask', 'none'):
        try:
            int(args.download)
        except ValueError:
            parser.error('invalid value for --download: {}'
                         .format(args.download))

    client = Opensubtitles()
    client.login()

    if args.cmd == 'for':
        client.download_from_files(args)

    elif args.cmd == 'search':
        client.download_from_search(args)

    elif args.cmd == 'languages':
        client.list_languages(args)


if __name__ == '__main__':
    main()
