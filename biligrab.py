#!/usr/bin/env python3

# Biligrab
# 
# Author: Beining@ACICFG https://github.com/cnbeining
# Author: StarBrilliant https://github.com/m13253
# 
# Biligrab is licensed under MIT licence
# Permission has been granted for the use of Danmaku2ASS in Biligrab
# 
# Copyright (c) 2014
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the “Software”), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


import sys
if sys.version_info < (3,0):
    sys.stderr.write('ERROR: Python 3.0 or newer version is required.\n')
    sys.exit(1)
import argparse
import gzip
import json
import io
import logging
import math
import os
import re
import subprocess
import tempfile
import urllib.request
import xml.dom.minidom
import zlib


USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/31.0.1650.63 Safari/537.36'
APPKEY = '876fe0ebd0e67a0f'  # The same key as in original Biligrab


def biligrab(url, *, cookie=None, overseas=False, mpvflags=[], d2aflags={}):
    regex = re.compile('http:/*[^/]+/video/av(\\d+)(/|/index.html|/index_(\\d+).html)?(\\?|#|$)')
    url_get_cid = 'http://api.bilibili.tv/view?type=json&appkey=%(appkey)s&id=%(aid)s&page=%(pid)s'
    url_get_comment = 'http://comment.bilibili.com/%(cid)s.xml'
    url_get_media = 'http://interface.bilibili.com/playurl?cid=%(cid)s' if not overseas else 'http://interface.bilibili.com/v_cdn_play?cid=%(cid)s'
    regex_match = regex.match(url)
    if not regex_match:
        logging.error('Invalid URL: %s' % url)
        return 1
    aid = regex_match.group(1)
    pid = regex_match.group(3) or '1'
    logging.info('Loading video info...')
    _, resp_cid = urlfetch(url_get_cid % {'appkey': APPKEY, 'aid': aid, 'pid': pid}, cookie=cookie)
    try:
        resp_cid = dict(json.loads(resp_cid.decode('utf-8', 'replace')))
        cid = resp_cid.get('cid')
        if not cid:
            if 'error' in resp_cid:
                logging.error('Error message: %s' % resp_cid.get('error'))
            raise ValueError
    except (TypeError, ValueError):
        raise ValueError('Can not get \'cid\' from %s' % url)
    logging.info('Got video cid: %s' % cid)
    logging.info('Loading video content...')
    _, resp_media = urlfetch(url_get_media % {'cid': cid}, cookie=cookie)
    media_urls = [str(k.wholeText).strip() for i in xml.dom.minidom.parseString(resp_media.decode('utf-8', 'replace')).getElementsByTagName('durl') for j in i.getElementsByTagName('url')[:1] for k in j.childNodes if k.nodeType == 4]
    logging.info('Got media URLs:'+''.join(('\n      %d: %s' % (i+1, j) for i, j in enumerate(media_urls))))
    if len(media_urls) == 0:
        raise ValueError('Can not get valid media URLs.')
    logging.info('Determining video resolution...')
    video_size = getvideosize(media_urls[0])
    logging.info('Video resolution: %sx%s' % video_size)
    if video_size[0] > 0 and video_size[1] > 0:
        video_size = (video_size[0]*1080/video_size[1], 1080)  # Simply fix ASS resolution to 1080p
    else:
        logging.error('Can not get video size. Comments may be wrongly positioned.')
        video_size = (1920, 1080)
    logging.info('Loading comments...')
    _, resp_comment = urlfetch(url_get_comment % {'cid': cid}, cookie=cookie)
    comment_in = io.StringIO(resp_comment.decode('utf-8', 'replace'))
    comment_out = tempfile.NamedTemporaryFile(mode='w', encoding='utf-8-sig', newline='\r\n', prefix='tmp-danmaku2ass-', suffix='.ass')
    logging.info('Invoking Danmaku2ASS, converting to %s' % comment_out.name)
    d2aflags = dict({'stage_width': video_size[0], 'stage_height': video_size[1], 'font_face': 'SimHei', 'font_size': math.ceil(video_size[1]/21.6)}, **d2aflags)
    for i, j in ((('stage_width', 'stage_height', 'reserve_blank'), int), (('font_size', 'text_opacity', 'comment_duration'), float)):
        for k in i:
            if k in d2aflags:
                d2aflags[k] = j(d2aflags[k])
    danmaku2ass.Danmaku2ASS([comment_in], comment_out, **d2aflags)
    comment_out.flush()
    logging.info('Launching media player...')
    command_line = ['mpv', '--ass', '--autofit', '950x540', '--framedrop', 'no', '--http-header-fields', 'User-Agent: '+USER_AGENT.replace(',', '\\,'), '--merge-files', '--no-aspect', '--sub', comment_out.name, '--vf', 'lavfi="fps=60"']+mpvflags+media_urls
    logging.info(' '.join('\''+i+'\'' if ' ' in i or '&' in i else i for i in command_line)+'\n')
    player_process = subprocess.Popen(command_line)
    player_process.wait()
    comment_out.close()
    return player_process.returncode


def urlfetch(url, *, cookie=None):
    req_headers = {'User-Agent': USER_AGENT, 'Accept-Encoding': 'gzip, deflate'}
    if cookie:
        req_headers['Cookie'] = cookie
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
    parser.add_argument('-c', '--cookie', help='Import Cookies at bilibili.tv, type document.cookie at JavaScript console to acquire it')
    parser.add_argument('-o', '--overseas', action='store_true', help='Enable overseas proxy for user outside China')
    parser.add_argument('--mpvflags', metavar='FLAGS', default='', help='Parameters passed to mpv, formed as \'--option1=value1 --option2=value2\'')
    parser.add_argument('--d2aflags', '--danmaku2assflags', metavar='FLAGS', default='', help='Parameters passed to Danmaku2ASS, formed as \'option1=value1,option2=value2\'')
    parser.add_argument('url', metavar='URL', nargs='+', help='Bilibili video page URL (http://www.bilibili.tv/av*)')
    args = parser.parse_args()
    if not checkenv():
        return 2
    retval = 0
    for url in args.url:
        try:
            retval = retval or biligrab(url, cookie=args.cookie, overseas=args.overseas, mpvflags=args.mpvflags.split(), d2aflags=dict(map(lambda x: x.split('=', 1) if '=' in x else [x, ''], args.d2aflags.split(','))) if args.d2aflags else {})
        except OSError as e:
            logging.error(e)
            retval = retval or e.errno
        except Exception as e:
            logging.error(e)
            retval = retval or 1
    return retval


if __name__ == '__main__':
    sys.exit(main())
