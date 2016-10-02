#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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
import codecs
import os
import re
import subprocess
import tempfile
import urllib.parse
import urllib.request
import xml.dom.minidom
import zlib


USER_AGENT_PLAYER = 'Mozilla/5.0 BiliDroid/4.24.0 (bbcallen@gmail.com)'
USER_AGENT_API = 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/34.0.1847.116 Safari/537.36'
APPKEY = '1q8o6' + 'r7q4523' + '3436'   # Unknown source
APPSEC = '560p52ppq288' + 'srq045859rq18' + 'ossq973'    # Do not abuse please, get one yourself if you need
BILIGRAB_HEADER = {'User-Agent': USER_AGENT_API, 'Cache-Control': 'no-cache', 'Pragma': 'no-cache'}


def biligrab(url, *, debug=False, verbose=False, media=None, comment=None, cookie=None, quality=None, source=None, keep_fps=False, mpvflags=[], d2aflags={}, fakeip=None):

    url_get_metadata = 'http://api.bilibili.com/view?'
    url_get_comment = 'http://comment.bilibili.com/%(cid)s.xml'
    if source == 'overseas':
        url_get_media = 'http://interface.bilibili.com/v_cdn_play?'
    else:
        url_get_media = 'http://interface.bilibili.com/playurl?'

    def parse_url(url):
        '''Parse a bilibili.com URL

        Return value: (aid, pid)
        '''
        if url.startswith('cid:'):
            try:
                return int(url[4:]), 'cid'
            except ValueError:
                raise ValueError('Invalid CID: %s' % url[4:])
        regex = re.compile('(?:http:/*[^/]+/(?:video/)?)?av(\\d+)(?:/|/index.html|/index_(\\d+).html)?(?:\\?|#|$)')
        regex_match = regex.match(url)
        if not regex_match:
            raise ValueError('Invalid URL: %s' % url)
        aid = regex_match.group(1)
        pid = regex_match.group(2) or '1'
        return aid, pid

    def fetch_video_metadata(aid, pid):
        '''Fetch video metadata

        Arguments: aid, pid

        Return value: {'cid': cid, 'title': title}
        '''
        req_args = {'type': 'json', 'appkey': codecs.decode(APPKEY,'rot13'), 'id': aid, 'page': pid}
        req_args['sign'] = bilibili_hash(req_args)
        _, response = fetch_url(url_get_metadata+urllib.parse.urlencode(req_args), user_agent=USER_AGENT_API, cookie=cookie)
        try:
            response = dict(json.loads(response.decode('utf-8', 'replace')))
        except (TypeError, ValueError):
            raise ValueError('Can not get \'cid\' from %s' % url)
        if 'error' in response:
            logging.error('Error message: %s' % response.get('error'))
        if 'cid' not in response:
            raise ValueError('Can not get \'cid\' from %s' % url)
        return response

    def get_media_urls(cid, *, fuck_you_bishi_mode=False):
        '''Request the URLs of the video

        Arguments: cid

        Return value: [media_urls]
        '''
        if source in {None, 'overseas'}:
            user_agent = USER_AGENT_API if not fuck_you_bishi_mode else USER_AGENT_PLAYER
            req_args = {'cid': cid}
            if quality is not None:
                req_args['quality'] = quality
            else:
                req_args['quality'] = None
            _, response = fetch_url(url_get_media+andro_mock(req_args), user_agent=user_agent, cookie=cookie, fakeip=fakeip)
            '''
            media_urls = [str(k.wholeText).strip() for i in xml.dom.minidom.parseString(response.decode('utf-8', 'replace')).getElementsByTagName('durl') for j in i.getElementsByTagName('url')[:1] for k in j.childNodes if k.nodeType == 4]
            '''
            json_obj = json.loads(response.decode('utf-8'))
            if json_obj['result'] != 'suee':  # => Not Success
                raise ValueError('Server returned an error: %s (%s)' % (json_obj['result'], json_obj['code']))
            media_urls = [str(i['url']).strip() for i in json_obj['durl']]
            if not fuck_you_bishi_mode and media_urls == ['http://static.hdslb.com/error.mp4']:
                logging.error('Detected User-Agent block. Switching to fuck-you-bishi mode.')
                return get_media_urls(cid, fuck_you_bishi_mode=True)
        elif source == 'html5':
            req_args = {'aid': aid, 'page': pid}
            logging.warning('HTML5 video source is experimental and may not always work.')
            _, response = fetch_url('http://www.bilibili.com/m/html5?'+urllib.parse.urlencode(req_args), user_agent=USER_AGENT_PLAYER)
            response = json.loads(response.decode('utf-8', 'replace'))
            media_urls = [dict.get(response, 'src')]
            if not media_urls[0]:
                media_urls = []
            if not fuck_you_bishi_mode and media_urls == ['http://static.hdslb.com/error.mp4']:
                logging.error('Failed to request HTML5 video source. Retrying.')
                return get_media_urls(cid, fuck_you_bishi_mode=True)
        elif source == 'flvcd':
            req_args = {'kw': url}
            if quality is not None:
                if quality == 3:
                    req_args['quality'] = 'high'
                elif quality >= 4:
                    req_args['quality'] = 'super'
            _, response = fetch_url('http://www.flvcd.com/parse.php?'+urllib.parse.urlencode(req_args), user_agent=USER_AGENT_PLAYER)
            resp_match = re.search('<input type="hidden" name="inf" value="([^"]+)"', response.decode('gbk', 'replace'))
            if resp_match:
                media_urls = resp_match.group(1).rstrip('|').split('|')
            else:
                media_urls = []
        elif source == 'bilipr':
            req_args = {'cid': cid}
            quality_arg = '1080' if quality is not None and quality >= 4 else '720'
            logging.warning('BilibiliPr video source is experimental and may not always work.')
            resp_obj, response = fetch_url('http://pr.lolly.cc/P%s?%s' % (quality_arg, urllib.parse.urlencode(req_args)), user_agent=USER_AGENT_PLAYER)
            if resp_obj.getheader('Content-Type', '').startswith('text/xml'):
                media_urls = [str(k.wholeText).strip() for i in xml.dom.minidom.parseString(response.decode('utf-8', 'replace')).getElementsByTagName('durl') for j in i.getElementsByTagName('url')[:1] for k in j.childNodes if k.nodeType == 4]
            else:
                media_urls = []
        else:
            assert source in {None, 'overseas', 'html5', 'flvcd', 'bilipr'}
        if len(media_urls) == 0 or media_urls == ['http://static.hdslb.com/error.mp4']:
            raise ValueError('Can not get valid media URLs.')
        return media_urls

    def get_video_size(media_urls):
        '''Determine the resolution of the video

        Arguments: [media_urls]

        Return value: (width, height)
        '''
        try:
            if media_urls[0].startswith('http:') or media_urls[0].startswith('https:'):
                ffprobe_command = ['ffprobe', '-icy', '0', '-loglevel', 'repeat+warning' if verbose else 'repeat+error', '-print_format', 'json', '-select_streams', 'v', '-show_streams', '-timeout', '60000000', '-user-agent', USER_AGENT_PLAYER, '--', media_urls[0]]
            else:
                ffprobe_command = ['ffprobe', '-loglevel', 'repeat+warning' if verbose else 'repeat+error', '-print_format', 'json', '-select_streams', 'v', '-show_streams', '--', media_urls[0]]
            log_command(ffprobe_command)
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
            log_or_raise(e, debug=debug)
            return 0, 0

    def convert_comments(cid, video_size):
        '''Convert comments to ASS subtitle format

        Arguments: cid

        Return value: comment_out -> file
        '''
        _, resp_comment = fetch_url(url_get_comment % {'cid': cid}, cookie=cookie)
        comment_in = io.StringIO(resp_comment.decode('utf-8', 'replace'))
        comment_out = tempfile.NamedTemporaryFile(mode='w', encoding='utf-8-sig', newline='\r\n', prefix='tmp-danmaku2ass-', suffix='.ass', delete=False)
        logging.info('Invoking Danmaku2ASS, converting to %s' % comment_out.name)
        d2a_args = dict({'stage_width': video_size[0], 'stage_height': video_size[1], 'font_face': 'SimHei', 'font_size': math.ceil(video_size[1]/21.6), 'text_opacity': 0.8, 'duration_marquee': min(max(6.75*video_size[0]/video_size[1]-4, 3.0), 8.0), 'duration_still': 5.0}, **d2aflags)
        for i, j in ((('stage_width', 'stage_height', 'reserve_blank'), int), (('font_size', 'text_opacity', 'comment_duration', 'duration_still', 'duration_marquee'), float)):
            for k in i:
                if k in d2aflags:
                    d2a_args[k] = j(d2aflags[k])
        try:
            danmaku2ass.Danmaku2ASS(input_files=[comment_in], input_format='Bilibili', output_file=comment_out, **d2a_args)
        except Exception as e:
            log_or_raise(e, debug=debug)
            logging.error('Danmaku2ASS failed, comments are disabled.')
        comment_out.flush()
        comment_out.close()  # Close the temporary file early to fix an issue related to Windows NT file sharing
        return comment_out

    def launch_player(video_metadata, media_urls, comment_out, is_playlist=False, increase_fps=True):
        '''Launch MPV media player

        Arguments: video_metadata, media_urls, comment_out

        Return value: player_exit_code -> int
        '''
        mpv_version_master = tuple(int(i) if i.isdigit() else float('inf') for i in check_env.mpv_version.split('-', 1)[0].split('.'))
        mpv_version_gte_0_10 = mpv_version_master >= (0, 10)
        mpv_version_gte_0_6 = mpv_version_gte_0_10 or mpv_version_master >= (0, 6)
        mpv_version_gte_0_4 = mpv_version_gte_0_6 or mpv_version_master >= (0, 4)
        logging.debug('Compare mpv version: %s %s 0.10' % (check_env.mpv_version, '>=' if mpv_version_gte_0_10 else '<'))
        logging.debug('Compare mpv version: %s %s 0.6' % (check_env.mpv_version, '>=' if mpv_version_gte_0_6 else '<'))
        logging.debug('Compare mpv version: %s %s 0.4' % (check_env.mpv_version, '>=' if mpv_version_gte_0_4 else '<'))
        if increase_fps:  # If hardware decoding (without -copy suffix) is used, do not increase fps
            for i in mpvflags:
                i = i.split('=', 1)
                if 'vdpau' in i or 'vaapi' in i or 'vda' in i:
                    increase_fps = False
                    break
        command_line = ['mpv', '--autofit', '950x540']
        if mpv_version_gte_0_6:
            command_line += ['--cache-file', 'TMP']
        if increase_fps and mpv_version_gte_0_6:  # Drop frames at vo side but not at decoder side to prevent A/V sync issues
            command_line += ['--framedrop', 'vo']
        command_line += ['--http-header-fields', 'User-Agent: '+USER_AGENT_PLAYER.replace(',', '\\,')]
        if mpv_version_gte_0_6:
            if mpv_version_gte_0_10:
                command_line += ['--force-media-title', video_metadata.get('title', url)]
            else:
                command_line += ['--media-title', video_metadata.get('title', url)]
        if is_playlist or len(media_urls) > 1:
            command_line += ['--merge-files']
        if mpv_version_gte_0_4:
            command_line += ['--no-video-aspect', '--sub-ass', '--sub-file', comment_out.name]
        else:
            command_line += ['--no-aspect', '--ass', '--sub', comment_out.name]
        if increase_fps:
            if mpv_version_gte_0_6:
                command_line += ['--vf', 'lavfi="fps=fps=60:round=down"']
            else:  # Versions < 0.6 have an A/V sync related issue
                command_line += ['--vf', 'lavfi="fps=fps=50:round=down"']
        command_line += mpvflags
        if is_playlist:
            command_line += ['--playlist']
        else:
            command_line += ['--']
        command_line += media_urls
        log_command(command_line)
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
        return player_process.returncode

    aid, pid = parse_url(url)

    logging.info('Loading video info...')
    if pid != 'cid':
        video_metadata = fetch_video_metadata(aid, pid)
    else:
        video_metadata = {'cid': aid, 'title': url}
    logging.info('Got video cid: %s' % video_metadata['cid'])

    logging.info('Loading video content...')
    if media is None:
        media_urls = get_media_urls(video_metadata['cid'])
    else:
        media_urls = [media]
    logging.info('Got media URLs:'+''.join(('\n      %d: %s' % (i+1, j) for i, j in enumerate(media_urls))))

    logging.info('Determining video resolution...')
    video_size = get_video_size(media_urls)
    logging.info('Video resolution: %sx%s' % video_size)
    if video_size[0] > 0 and video_size[1] > 0:
        video_size = (video_size[0]*1080/video_size[1], 1080)  # Simply fix ASS resolution to 1080p
    else:
        log_or_raise(ValueError('Can not get video size. Comments may be wrongly positioned.'), debug=debug)
        video_size = (1920, 1080)

    logging.info('Loading comments...')
    if comment is None:
        comment_out = convert_comments(video_metadata['cid'], video_size)
    else:
        comment_out = open(comment, 'r')
        comment_out.close()

    logging.info('Launching media player...')
    player_exit_code = launch_player(video_metadata, media_urls, comment_out, increase_fps=not keep_fps)

    if comment is None and player_exit_code == 0:
        os.remove(comment_out.name)

    return player_exit_code


def fetch_url(url, *, user_agent=USER_AGENT_PLAYER, cookie=None, fakeip=None):
    '''Fetch HTTP URL

    Arguments: url, user_agent, cookie

    Return value: (response_object, response_data) -> (http.client.HTTPResponse, bytes)
    '''
    logging.debug('Fetch: %s' % url)
    req_headers = {'User-Agent': user_agent, 'Accept-Encoding': 'gzip, deflate'}
    if cookie:
        req_headers['Cookie'] = cookie
    if fakeip:
        req_headers['X-Forwarded-For'] = fakeip
        req_headers['Client-IP'] = fakeip
    req = urllib.request.Request(url=url, headers=req_headers)
    response = urllib.request.urlopen(req, timeout=120)
    content_encoding = response.getheader('Content-Encoding')
    if content_encoding == 'gzip':
        data = gzip.GzipFile(fileobj=response).read()
    elif content_encoding == 'deflate':
        decompressobj = zlib.decompressobj(-zlib.MAX_WBITS)
        data = decompressobj.decompress(response.read())+decompressobj.flush()
    else:
        data = response.read()
    return response, data


def andro_mock(params):
    '''Simulate Android client

    Arguments: params

    Return value: request_string -> str
    '''
    import random
    import base64
    import collections
    our_lvl = 412
    _, api_response = fetch_url('http://app.bilibili.com/mdata/android3/android3.ver', user_agent=USER_AGENT_API)
    api_lvl = int(json.loads(api_response.decode('utf-8'))['upgrade']['ver'])
    logging.debug('Our simulated API level: %s, latest API level: %s' % (our_lvl, api_lvl))
    if api_lvl > our_lvl:
        logging.warning('Bilibili API server indicates the API protocol has been updated, the extraction may not work!')
    fake_hw = random.Random().randrange(start=0, stop=18000000000000000084).to_bytes(8, 'big').hex()
    add_req_args = collections.OrderedDict({
        'platform' : 'android',
        '_device': 'android',
        '_appver': '424000',
        '_p': '1',
        '_down': '0',
        'cid': params['cid'],
        '_tid': '0',
        'otype': 'json',
        '_hwid': fake_hw
        })
    if params['quality'] is not None:
                add_req_args['quality'] = params['quality']
    second_key = 'G&M40GdVRlW-v53V=yvd'
    second_sec = 'W;bIwGB##4G&y29Vr64yF=H|}HZ(LjH8?gmHeoU`'
    add_req_args['appkey'] = base64.b85decode(second_key)
    req_args = add_req_args
    add_req_args= collections.OrderedDict(sorted(req_args.items()))
    req_args['sign'] = hashlib.md5(bytes(urllib.parse.urlencode(add_req_args) + base64.b85decode(second_sec).decode('utf-8'), 'utf-8')).hexdigest()
    return urllib.parse.urlencode(req_args)

def bilibili_hash(args):
    '''Calculate API signature hash

    Arguments: {request_paramter: value}

    Return value: hash_value -> str
    '''
    return hashlib.md5((urllib.parse.urlencode(sorted(args.items()))+codecs.decode(APPSEC,'rot13')).encode('utf-8')).hexdigest()  # Fuck you bishi


def check_env(debug=False):
    '''Check the system environment to make sure dependencies are set up correctly

    Return value: is_successful -> bool
    '''
    global danmaku2ass, requests
    retval = True
    try:
        import danmaku2ass
    except ImportError as e:
        danmaku2ass_filename = os.path.abspath(os.path.join(os.path.realpath(__file__), '..', 'danmaku2ass.py'))
        logging.error('Automatically downloading \'danmaku2ass.py\'\n       from https://github.com/m13253/danmaku2ass\n       to %s' % danmaku2ass_filename)
        try:
            danmaku2ass_downloaded = fetch_url('https://github.com/m13253/danmaku2ass/raw/master/danmaku2ass.py')
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
                check_env.mpv_version = line.split(' ', 3)[2]
                logging.debug('Detected mpv version: %s' % check_env.mpv_version)
                break
        else:
            log_or_raise(RuntimeError('Can not detect mpv version.'), debug=debug)
            check_env.mpv_version = 'git-'
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


def log_command(command_line):
    '''Log the command line to be executed, escaping correctly
    '''
    logging.debug('Executing: '+' '.join('\''+i+'\'' if ' ' in i or '?' in i or '&' in i or '"' in i else i for i in command_line))


def log_or_raise(exception, debug=False):
    '''Log exception if debug == False, or raise it if debug == True
    '''
    if debug:
        raise exception
    else:
        logging.error(str(exception))


def preprocess_url(url):
    """
    Parse a readable Bilibili URL for method parse_url(url)
    from a Bangumi URL(A new URL format in Bilibili, e.g. http://bangumi.bilibili.com/anime/v/80085)
    :param url:
    :return:
    """
    regex = re.compile('(http://bangumi.bilibili.com/anime/v/[0-9]+)')
    regex_match = regex.match(url)
    if not regex_match:
        return url

    # extract Bilibili url from raw HTML.
    _, data = fetch_url(url)
    # data = str(data)
    data = data.decode('utf-8')
    av_str_class_position = data.index('v-av-link')
    aim_url_div = data[av_str_class_position - 57: av_str_class_position + 40]
    # for basic url
    match1 = re.search('(http://www.bilibili.com/video/av[0-9]+/)', aim_url_div)
    result = match1.group(0)
    # for episode number
    title_content = data[data.index('<title>'): data.index('</title>')]
    match2 = re.search('(第[0-9]+集)', title_content)
    if match2 is not None:
    	raw_number = match2.group(0)
    	result += 'index_' + raw_number[1: -1] + '.html'
    else:
        # print('None')
    	pass

    # c = urllib.request.urlopen(url)
    # soup = bs4.BeautifulSoup(c.read(), 'html.parser')
    # result = soup.find(class_='v-av-link')['href']
    # print(result)
    return result


class MyArgumentFormatter(argparse.HelpFormatter):

    def _split_lines(self, text, width):
        '''Patch the default argparse.HelpFormatter so that '\\n' is correctly handled
        '''
        return [i for line in text.splitlines() for i in argparse.HelpFormatter._split_lines(self, line, width)]


def main():
    if len(sys.argv) == 1:
        sys.argv.append('--help')
    parser = argparse.ArgumentParser(formatter_class=MyArgumentFormatter)
    parser.add_argument('-c', '--cookie', help='Import Cookie at bilibili.com, type document.cookie at JavaScript console to acquire it')
    parser.add_argument('-d', '--debug', action='store_true', help='Stop execution immediately when an error occures')
    parser.add_argument('-m', '--media', help='Specify local media file to play with remote comments')
    parser.add_argument('--comment', help='Specify local ASS comment file to play with remote media')
    parser.add_argument('-q', '--quality', type=int, help='Specify video quality, -q 1 for the lowest, -q 4 for HD')
    parser.add_argument('-s', '--source', help='Specify the source of video provider.\n' +
                                               'Available values:\n' +
                                               'default: Default source\n' +
                                               'overseas: CDN acceleration for users outside china\n' +
                                               'flvcd: Video parsing service provided by FLVCD.com\n' +
                                               'html5: Low quality video provided by m.acg.tv for mobile users')
    parser.add_argument('-f', '--fakeip', help='Fake ip for bypassing restrictions.')
    parser.add_argument('-v', '--verbose', action='store_true', help='Print more debugging information')
    parser.add_argument('--hd', action='store_true', help='Shorthand for -q 4')
    parser.add_argument('--keep-fps', action='store_true', help='Use the same framerate as the video to animate comments, instead of increasing to 60 fps')
    parser.add_argument('--mpvflags', metavar='FLAGS', default='', help='Parameters passed to mpv, formed as \'--option1=value1 --option2=value2\'')
    parser.add_argument('--d2aflags', '--danmaku2assflags', metavar='FLAGS', default='', help='Parameters passed to Danmaku2ASS, formed as \'option1=value1,option2=value2\'')
    parser.add_argument('url', metavar='URL', nargs='+', help='Bilibili video page URL (http://www.bilibili.com/video/av*/)')
    args = parser.parse_args()
    logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG if args.verbose else logging.INFO)
    if not check_env(debug=args.debug):
        return 2
    quality = args.quality if args.quality is not None else 4 if args.hd else None
    source = args.source if args.source != 'default' else None
    if source not in {None, 'overseas', 'html5', 'flvcd', 'bilipr'}:
        raise ValueError('invalid value specified for --source, see --help for more information')
    mpvflags = args.mpvflags.split()
    d2aflags = dict((i.split('=', 1) if '=' in i else [i, ''] for i in args.d2aflags.split(','))) if args.d2aflags else {}
    fakeip = args.fakeip if args.fakeip else None
    retval = 0

    for url in args.url:
        # if url is a Bangumi format URL (e.g. http://bangumi.bilibili.com/anime/v/80085)
        url = preprocess_url(url)
        try:
            retval = retval or biligrab(url, debug=args.debug, verbose=args.verbose, media=args.media, comment=args.comment, cookie=args.cookie, quality=quality, source=source, keep_fps=args.keep_fps, mpvflags=mpvflags, d2aflags=d2aflags, fakeip=args.fakeip)
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
