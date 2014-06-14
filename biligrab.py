#!/usr/bin/env python3

'''
Biligrab

Author: Beining@ACICFG https://github.com/cnbeining
Author: StarBrilliant https://github.com/m13253

Licensed under MIT licence

Danmaku2ASS has grant license for Biligrab
'''

import sys
if sys.version_info < (3,0):
    sys.stderr.write('ERROR: Python 3.0 or newer version is required.\n')
    sys.exit(1)
import argparse
import logging
import os
import urllib
import zlib

def biligrab(url, *, oversea=False):
    regex = re.compile('http:/*[^/]+/av(\\d+)(/|/index.html|/index_(\\d+).html)?(\\?|#|$)')
    regex_match = regex.match(url)
    if not regex_match:
        logging.error('Invalid URL: %s' % url)
    avid = regex_match.group(1)
    pid = regex_match.group(3) or '1'
    raise NotImplementedError  # TODO

def checkenv():
    global requests, danmaku2ass
    retval = True
    try:
        import requests
    except ImportError as e:
        logging.error('ERROR: Please install \'requests\' with \'sudo pip install requests\'.')
        retval = False
    try:
        import danmaku2ass
    except ImportError as e:
        logging.error('Please download \'danmaku2ass.py\'\n       from https://github.com/m13253/danmaku2ass\n       to %s' % os.path.abspath(os.path.join(__file__, '..', 'danmaku2ass.py')))
        retval = False
    return retval

def main():
    logging.basicConfig(format='%(levelname)s: %(message)s')
    if len(sys.argv) == 1:
        sys.argv.append('--help')
    parser = argparse.ArgumentParser()
    parser.add_argument('--oversea', action='store_true', help='Enable bilibili oversea proxy')
    parser.add_argument('url', metavar='URL', nargs='+', help='Bilibili video page URL (http://www.bilibili.tv/av*)')
    args = parser.parse_args()
    if not checkenv():
        return 1
    retval = 0
    for url in args.url:
        retval = retval or biligrab(url, oversea=args.oversea)
    return retval

if __name__ == '__main__':
    sys.exit(main())
