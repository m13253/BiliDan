Biligrab-Danmaku2ASS
====================

Play videos on Bilibili.com with MPV and Danmaku2ASS


Requirements
------------

- [Python](https://www.python.org/) at least version 3.0
- [mpv Media Player](http://mpv.io/), a fork of MPlayer with features
  Biligrab-Danmaku2ASS requires
- [FFmpeg](https://www.ffmpeg.org/) with ffprobe installed. [Do not use Libav](https://github.com/mpv-player/mpv/wiki/FFmpeg-versus-Libav/9fc3989d00b2df54f7bc92f5de8442fc223091a2).
- [Danmaku2ASS](https://github.com/m13253/danmaku2ass), automatically installed

Note that [Libav](https://www.libav.org/) does not work. See [why FFmpeg is preferred](https://github.com/mpv-player/mpv/wiki/FFmpeg-versus-Libav).

Example
-----

```
./bilidan.py http://www.bilibili.com/video/av899574/
./bilidan.py http://www.bilibili.com/video/av314/     # High density comments!
./bilidan.py http://www.bilibili.com/video/av332732/index_7.html # Extreme density!
./bilidan.py http://www.bilibili.com/video/av297197/  # Even Toukome (advanced comments)!
```
Use option `--source overseas` if your are outside China. And `--source html5`  to use the the experimental HTML5 API.
Use `--fakeip` if you can't get valid media URLs due to ip restrictions.


Why Biligrab-Danmaku2ASS?
-------------------------

- Bilibili uses a Flash-based video player. Flash is unavailable since
  **Chromium** 35 to Linux users.
- Chrome Pepper Flash has a font-related bug on Linux, which causes the whole
  page crash when Flash tries to render certain CJK fonts so that you have no
  chance to switch to another font. This caused Bilibili Flash player unusable
  to **Google Chrome** users on Linux.
- **Mozilla Firefox** users on Linux never receives a newer Flash player than
  11.2 from Adobe. It is certain that Adobe has abandoned Flash.
- Flash consumes too much energy. Flash causes a burning laptop.
- Experiments show that Danmaku2ASS renders a lot faster than the native
  Bilibili player and even similar software such as
  [ABPlayerHTML5](https://github.com/jabbany/ABPlayerHTML5). Thanks to libass,
  Danmaku2ASS has passed a
  [extreme density test](http://www.bilibili.com/video/av332732/index_7.html) at
  60 fps on a Intel Core i5 laptop.


Tips
----

- Use key V to switch comment visibility.
- Some videos require logging in your account. Import your Cookie at bilibili.tv
  with `--cookie` option.
- If you have difficulties connecting to video server, try `--overseas`.
- If your computer is not fast enough, try `--mpvflags '--framedrop yes'`.
- Use `--d2aflags 'duration_marquee=5'` to set comment flow speed.
- Use `--d2aflags 'text_opacity=0.8'` to set comment opacity.
- Try to fast forward or rewind when streaming is stuck, or to tweak cache
  parameters of mpv.
- For issue related to URL parsing (especially the experimental HTML5 API),
  please report directly to Biligrab, the upstream parser:
  https://github.com/cnbeining/Biligrab/issues

License
-------

Like the original Biligrab, Biligrab-Danmaku2ASS is licensed under MIT license
as well. This program is provided **as is**, with absolutely no warranty.
