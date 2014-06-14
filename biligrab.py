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
import gzip
import json
import io
import logging
import os
import re
import subprocess
import tempfile
import urllib.request
import xml.dom.minidom
import zlib


USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/31.0.1650.63 Safari/537.36'
APPKEY = '876fe0ebd0e67a0f'  # The same key used in original Biligrab


def biligrab(url, *, oversea=False):
    regex = re.compile('http:/*[^/]+/av(\\d+)(/|/index.html|/index_(\\d+).html)?(\\?|#|$)')
    url_get_cid = 'http://api.bilibili.tv/view?type=json&appkey=%(appkey)s&id=%(aid)s&page=%(pid)s'
    url_get_comment = 'http://comment.bilibili.tv/%(cid)s.xml'
    url_get_media = 'http://interface.bilibili.tv/playurl?cid=%(cid)s' if not oversea else 'http://interface.bilibili.cn/v_cdn_play?cid=%(cid)s'
    regex_match = regex.match(url)
    if not regex_match:
        logging.error('Invalid URL: %s' % url)
    aid = regex_match.group(1)
    pid = regex_match.group(3) or '1'
    logging.info('Loading video info...')
    _, resp_cid = urlfetch(url_get_cid % {'appkey': APPKEY, 'aid': aid, 'pid': pid})
    try:
        cid = dict.get(json.loads(resp_cid.decode('utf-8', 'replace')), 'cid')
        if not cid:
            raise ValueError
    except (TypeError, ValueError):
        raise ValueError('Can not get \'cid\' from %s' % url)
    logging.info('Got video cid: %s' % cid)
    logging.info('Loading video content...')
    _, resp_media = urlfetch(url_get_media % {'cid': cid})
    media_urls = [str(k.wholeText).strip() for i in xml.dom.minidom.parseString(resp_media.decode('utf-8', 'replace')).getElementsByTagName('durl') for j in i.getElementsByTagName('url') for k in j.childNodes if k.nodeType == 4]
    logging.info('Media URLs:'+''.join(('\n      %d: %s' % (i+1, j) for i, j in enumerate(media_urls))))
    if len(media_urls) == 0:
        raise ValueError('Can not get valid media URLs')
    video_size = getvideosize(media_urls[0])
    logging.info('Video size: %sx%s' % video_size)
    video_size = (video_size[0]*1080/video_size[1], 1080)  # Simply fix ASS resolution to 1080p
    logging.info('Loading comments...')
    _, resp_comment = urlfetch(url_get_comment % {'cid': cid})
    comment_in = io.StringIO(resp_comment.decode('utf-8', 'replace'))
    comment_out = tempfile.NamedTemporaryFile(mode='w', encoding='utf-8-sig', newline='\r\n', prefix='tmp-danmaku2ass-', suffix='.ass')
    logging.info('Calling Danmaku2ASS, converting to %s' % comment_out.name)
    danmaku2ass.Danmaku2ASS([comment_in], comment_out, video_size[0], video_size[1], font_face='SimHei', font_size=video_size[1]/21.6)
    logging.info('Invoking media player...')
    player_process = subprocess.Popen(['mpv', '--ass', '--sub', comment_out.name, '--merge-files', '--autofit', '950x540', '--no-aspect']+media_urls)
    player_process.wait()
    comment_out.close()
    return player_process.returncode


def urlfetch(url):
    req_headers = {'User-Agent': USER_AGENT, 'Accept-Encoding': 'gzip, deflate'}
    req = urllib.request.Request(url=url, headers=req_headers)
    response = urllib.request.urlopen(req, timeout=120)
    content_encoding = response.info().get('Content-Encoding')
    if content_encoding == 'gzip':
        data = gzip.GzipFile(fileobj=response).read()
    elif content_encoding == 'deflate':
        decompressobj = zlib.decompressobj(-zlib.MAX_WBITS)
        data = decompressobj.decompress(response.read())+decompressobj.flush()
    else:
        data = response.read()
    return response, data


def getvideosize(url):
    ffprobe_command = ['ffprobe', '-show_streams', '-select_streams', 'v', '-print_format', 'json', '-user_agent', USER_AGENT, '-loglevel', 'repeat+error', url]
    ffprobe_output = json.loads(subprocess.Popen(ffprobe_command, stdout=subprocess.PIPE).communicate()[0].decode('utf-8', 'replace'))
    width, height, widthxheight = 0, 0, 0
    for stream in dict.get(ffprobe_output, 'streams'):
        if dict.get(stream, 'width')*dict.get(stream, 'height') > widthxheight:
            width, height = dict.get(stream, 'width'), dict.get(stream, 'height')
    return width, height


def checkenv():
    global danmaku2ass, requests
    retval = True
    try:
        import danmaku2ass
    except ImportError as e:
        logging.error('Please download \'danmaku2ass.py\'\n       from https://github.com/m13253/danmaku2ass\n       to %s' % os.path.abspath(os.path.join(__file__, '..', 'danmaku2ass.py')))
        retval = False
    try:
        subprocess.Popen(('mpv', '-V'), stdout=subprocess.DEVNULL)
    except OSError as e:
        logging.error('Please install \'mpv\' as the media player.')
        retval = False
    try:
        subprocess.Popen(('ffprobe', '-version'), stdout=subprocess.DEVNULL)
    except OSError as e:
        logging.error('Please install \'ffprobe\' from FFmpeg ultilities.')
        retval = False
    return retval


def main():
    logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.INFO)
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
        try:
            retval = retval or biligrab(url, oversea=args.oversea)
        except OSError as e:
            logging.error(e)
            retval = retval or e.errno
        except Exception as e:
            logging.error(e)
            retval = retval or 1
    return retval


if __name__ == '__main__':
    sys.exit(main())
