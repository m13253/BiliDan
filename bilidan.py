#!/usr/bin/env python3

# Biligrab-Danmaku2ASS
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
if sys.version_info < (3, 0):
    sys.stderr.write('ERROR: Python 3.0 or newer version is required.\n')
    sys.exit(1)
import argparse
import gzip
import json
import hashlib
import io
import logging
import math
import os
import re
import subprocess
import tempfile
import urllib.parse
import urllib.request
import xml.dom.minidom
import zlib


USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/36.0.1985.125 Safari/537.36'
API_USER_AGENT = 'Biligrab-Danmaku2ASS Linux, Biligrab Engine/0.8 (sb@loli.con.sh)'
APPKEY = '85eb6835b0a1034e'  # The same key as in original Biligrab
APPSEC = '2ad42749773c441109bdc0191257a664'  # Do not abuse please, get one yourself if you need


def biligrab(url, *, debug=False, verbose=False, media=None, cookie=None, overseas=False, quality=None, mpvflags=[], d2aflags={}):
    # Parse URL
    regex = re.compile('http:/*[^/]+/video/av(\\d+)(/|/index.html|/index_(\\d+).html)?(\\?|#|$)')
    url_get_cid = 'http://api.bilibili.com/view?'
    url_get_comment = 'http://comment.bilibili.com/%(cid)s.xml'
    url_get_media = 'http://interface.bilibili.com/playurl?' if not overseas else 'http://interface.bilibili.com/v_cdn_play?'
    regex_match = regex.match(url)
    if not regex_match:
        raise ValueError('Invalid URL: %s' % url)
    aid = regex_match.group(1)
    pid = regex_match.group(3) or '1'

    # Fetch CID
    logging.info('Loading video info...')
    cid_args = {'type': 'json', 'appkey': APPKEY, 'id': aid, 'page': pid}
    cid_args['sign'] = bilibilihash(cid_args)
    _, resp_cid = urlfetch(url_get_cid+urllib.parse.urlencode(cid_args), user_agent=API_USER_AGENT, cookie=cookie)
    try:
        resp_cid = dict(json.loads(resp_cid.decode('utf-8', 'replace')))
        if 'error' in resp_cid:
            logging.error('Error message: %s' % resp_cid.get('error'))
        cid = resp_cid.get('cid')
    except (TypeError, ValueError):
        raise ValueError('Can not get \'cid\' from %s' % url)
    if not cid:
        raise ValueError('Can not get \'cid\' from %s' % url)
    logging.info('Got video cid: %s' % cid)

    # Fetch media URLs
    for user_agent in (API_USER_AGENT, USER_AGENT):
        logging.info('Loading video content...')
        if media is None:
            media_args = {'appkey': APPKEY, 'cid': cid}
            if quality is not None:
                media_args['quality'] = quality
            media_args['sign'] = bilibilihash(media_args)
            _, resp_media = urlfetch(url_get_media+urllib.parse.urlencode(media_args), user_agent=user_agent, cookie=cookie)
            media_urls = [str(k.wholeText).strip() for i in xml.dom.minidom.parseString(resp_media.decode('utf-8', 'replace')).getElementsByTagName('durl') for j in i.getElementsByTagName('url')[:1] for k in j.childNodes if k.nodeType == 4]
        else:
            media_urls = [media]
        logging.info('Got media URLs:'+''.join(('\n      %d: %s' % (i+1, j) for i, j in enumerate(media_urls))))
        if media_urls == ['http://static.hdslb.com/error.mp4']:
            logging.error('Detected User-Agent block. Switching to fuck-you-bishi mode.')
            continue
        break
    if len(media_urls) == 0 or media_urls[0] == 'http://static.hdslb.com/error.mp4':
        raise ValueError('Can not get valid media URLs.')

    # Analyze video
    logging.info('Determining video resolution...')
    video_size = getvideosize(media_urls[0], verbose=verbose)
    logging.info('Video resolution: %sx%s' % video_size)
    if video_size[0] > 0 and video_size[1] > 0:
        video_size = (video_size[0]*1080/video_size[1], 1080)  # Simply fix ASS resolution to 1080p
        comment_duration = min(max(6.75*video_size[0]/video_size[1]-4, 3.0), 8.0)
    else:
        logorraise(ValueError('Can not get video size. Comments may be wrongly positioned.'), debug=debug)
        video_size = (1920, 1080)
        comment_duration = 8.0

    # Load danmaku
    logging.info('Loading comments...')
    _, resp_comment = urlfetch(url_get_comment % {'cid': cid}, cookie=cookie)
    comment_in = io.StringIO(resp_comment.decode('utf-8', 'replace'))
    comment_out = tempfile.NamedTemporaryFile(mode='w', encoding='utf-8-sig', newline='\r\n', prefix='tmp-danmaku2ass-', suffix='.ass')
    logging.info('Invoking Danmaku2ASS, converting to %s' % comment_out.name)
    d2aflags = dict({'stage_width': video_size[0], 'stage_height': video_size[1], 'font_face': 'SimHei', 'font_size': math.ceil(video_size[1]/21.6), 'comment_duration': comment_duration}, **d2aflags)
    for i, j in ((('stage_width', 'stage_height', 'reserve_blank'), int), (('font_size', 'text_opacity', 'comment_duration'), float)):
        for k in i:
            if k in d2aflags:
                d2aflags[k] = j(d2aflags[k])
    try:
        danmaku2ass.Danmaku2ASS([comment_in], comment_out, **d2aflags)
    except Exception as e:
        logorraise(e)
        logging.error('Danmaku2ASS failed, comments are disabled.')
    comment_out.flush()

    # Launch MPV player
    logging.info('Launching media player...')
    mpv_version_master = tuple(checkenv.mpv_version.split('-', 1)[0].split('.'))
    mpv_version_gte_0_6 = mpv_version_master >= ('0', '6') or (len(mpv_version_master) >= 2 and len(mpv_version_master[1]) >= 2) or mpv_version_master[0] == 'git'
    mpv_version_gte_0_4 = mpv_version_gte_0_6 or mpv_version_master >= ('0', '4') or (len(mpv_version_master) >= 2 and len(mpv_version_master[1]) >= 2) or mpv_version_master[0] == 'git'
    logging.debug('Compare mpv version: %s %s 0.6' % (checkenv.mpv_version, '>=' if mpv_version_gte_0_6 else '<'))
    logging.debug('Compare mpv version: %s %s 0.4' % (checkenv.mpv_version, '>=' if mpv_version_gte_0_4 else '<'))
    command_line = ['mpv', '--autofit', '950x540', '--framedrop', 'no', '--http-header-fields', 'User-Agent: '+USER_AGENT.replace(',', '\\,')]
    if mpv_version_gte_0_6:
        command_line += ['--media-title', resp_cid.get('title', url)]
    command_line += ['--merge-files']
    if mpv_version_gte_0_4:
        command_line += ['--no-video-aspect', '--sub-ass', '--sub-file', comment_out.name]
    else:
        command_line += ['--no-aspect', '--ass', '--sub', comment_out.name]
    command_line += ['--vf', 'lavfi="fps=fps=50:round=down"', '--vo', 'wayland,opengl,opengl-old,x11,corevideo,direct3d_shaders,direct3d,sdl,xv,']
    command_line += mpvflags
    command_line += media_urls
    logcommand(command_line)
    player_process = subprocess.Popen(command_line)
    try:
        player_process.wait()
    except KeyboardInterrupt:
        logging.info('Terminating media player...')
        try:
            player_process.terminate()
            try:
                player_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                logging.info('Killing media player by force...')
                player_process.kill()
        except Exception:
            pass
        raise

    # Clean up
    comment_out.close()
    return player_process.returncode


def urlfetch(url, *, user_agent=USER_AGENT, cookie=None):
    logging.debug('Fetch: %s' % url)
    req_headers = {'User-Agent': user_agent, 'Accept-Encoding': 'gzip, deflate'}
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


def getvideosize(url, verbose=False):
    try:
        ffprobe_command = ['ffprobe', '-icy', '0', '-loglevel', 'repeat+warning' if verbose else 'repeat+error', '-print_format', 'json', '-select_streams', 'v', '-show_streams', '-timeout', '60000000', '-user-agent', USER_AGENT, url]
        logcommand(ffprobe_command)
        ffprobe_process = subprocess.Popen(ffprobe_command, stdout=subprocess.PIPE)
        try:
            ffprobe_output = json.loads(ffprobe_process.communicate()[0].decode('utf-8', 'replace'))
        except KeyboardInterrupt:
            logging.warning('Cancelling getting video size, press Ctrl-C again to terminate.')
            ffprobe_process.terminate()
            return 0, 0
        width, height, widthxheight = 0, 0, 0
        for stream in dict.get(ffprobe_output, 'streams') or []:
            if dict.get(stream, 'width')*dict.get(stream, 'height') > widthxheight:
                width, height = dict.get(stream, 'width'), dict.get(stream, 'height')
        return width, height
    except Exception as e:
        logorraise(e)
        return 0, 0


def bilibilihash(args):
    return hashlib.md5((urllib.parse.urlencode(sorted(args.items()))+APPSEC).encode('utf-8')).hexdigest()  # Fuck you bishi


def checkenv(debug=False):
    global danmaku2ass, requests
    retval = True
    try:
        import danmaku2ass
    except ImportError as e:
        danmaku2ass_filename = os.path.abspath(os.path.join(__file__, '..', 'danmaku2ass.py'))
        logging.error('Automatically downloading \'danmaku2ass.py\'\n       from https://github.com/m13253/danmaku2ass\n       to %s' % danmaku2ass_filename)
        try:
            danmaku2ass_downloaded = urlfetch('https://github.com/m13253/danmaku2ass/raw/master/danmaku2ass.py')
            with open(danmaku2ass_filename, 'wb') as f:
                f.write(danmaku2ass_downloaded[1])
            del danmaku2ass_downloaded
        except Exception as e:
            logging.error('Can not download Danmaku2ASS module automatically (%s), please get it yourself.' % e)
            retval = False
    if retval:
        try:
            import danmaku2ass
            danmaku2ass.Danmaku2ASS
        except (AttributeError, ImportError) as e:
            logging.error('Danmaku2ASS module is not working (%s), please update it at https://github.com/m13253/danmaku2ass' % e)
            retval = False
    try:
        mpv_process = subprocess.Popen(('mpv', '--version'), stdout=subprocess.PIPE, env=dict(os.environ, MPV_VERBOSE='-1'))
        mpv_output = mpv_process.communicate()[0].decode('utf-8', 'replace').splitlines()
        for line in mpv_output:
            if line.startswith('[cplayer] mpv '):
                checkenv.mpv_version = line.split(' ', 3)[2]
                logging.debug('Detected mpv version: %s' % checkenv.mpv_version)
                break
        else:
            logorraise('Can not detect mpv version.', debug=debug)
            checkenv.mpv_version = 'git-'
    except OSError as e:
        logging.error('Please install \'mpv\' as the media player.')
        retval = False
    try:
        mpv_process = subprocess.Popen(('mpv', '--vf', 'lavfi=help'), stdout=subprocess.DEVNULL)
        mpv_process.wait()
        if mpv_process.returncode != 0:
            logging.error('mpv is not configured to enable \'lavfi\' filter. (mpv or ffmpeg may be too old)')
            retval = False
    except OSError as e:
        logging.error('mpv is not configured to enable \'lavfi\' filter. (mpv or ffmpeg may be too old)')
        retval = False
    try:
        subprocess.Popen(('ffprobe', '-version'), stdout=subprocess.DEVNULL)
    except OSError as e:
        logging.error('Please install \'ffprobe\' from FFmpeg ultilities.')
        retval = False
    return retval


def logcommand(command_line):
    logging.debug('Executing: '+' '.join('\''+i+'\'' if ' ' in i or '&' in i or '"' in i else i for i in command_line))


def logorraise(message, debug=False):
    if debug:
        raise message
    else:
        logging.error(str(message))


def main():
    if len(sys.argv) == 1:
        sys.argv.append('--help')
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--cookie', help='Import Cookie at bilibili.com, type document.cookie at JavaScript console to acquire it')
    parser.add_argument('-d', '--debug', action='store_true', help='Stop execution immediately when an error occures')
    parser.add_argument('-m', '--media', help='Specify local media file to play with remote comments')
    parser.add_argument('-o', '--overseas', action='store_true', help='Enable overseas proxy for users outside China')
    parser.add_argument('-q', '--quality', type=int, help='Specify video quality, -q 4 for HD')
    parser.add_argument('-v', '--verbose', action='store_true', help='Print more debugging information')
    parser.add_argument('--hd', action='store_true', help='Shorthand for -q 4')
    parser.add_argument('--mpvflags', metavar='FLAGS', default='', help='Parameters passed to mpv, formed as \'--option1=value1 --option2=value2\'')
    parser.add_argument('--d2aflags', '--danmaku2assflags', metavar='FLAGS', default='', help='Parameters passed to Danmaku2ASS, formed as \'option1=value1,option2=value2\'')
    parser.add_argument('url', metavar='URL', nargs='+', help='Bilibili video page URL (http://www.bilibili.com/video/av*/)')
    args = parser.parse_args()
    logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG if args.verbose else logging.INFO)
    if not checkenv(debug=args.debug):
        return 2
    quality = args.quality if args.quality is not None else 4 if args.hd else None
    mpvflags = args.mpvflags.split()
    d2aflags = dict(map(lambda x: x.split('=', 1) if '=' in x else [x, ''], args.d2aflags.split(','))) if args.d2aflags else {}
    retval = 0
    for url in args.url:
        try:
            retval = retval or biligrab(url, debug=args.debug, verbose=args.verbose, media=args.media, cookie=args.cookie, overseas=args.overseas, quality=quality, mpvflags=mpvflags, d2aflags=d2aflags)
        except OSError as e:
            logging.error(e)
            retval = retval or e.errno
            if args.debug:
                raise
        except Exception as e:
            logging.error(e)
            retval = retval or 1
            if args.debug:
                raise
    return retval


if __name__ == '__main__':
    sys.exit(main())
