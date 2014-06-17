Biligrab-Danmaku2ASS
====================

Play videos on Bilibili.tv with Danmaku2ASS


Requirements
------------

- [Python](https://www.python.org/) at least version 3.0
- [mpv Media Player](http://mpv.io/), a fork of MPlayer with features
  Biligrab-Danmaku2ASS requires
- [FFmpeg](https://www.ffmpeg.org/) with ffprobe installed
- [Danmaku2ASS](https://github.com/m13253/danmaku2ass), put `danmaku2ass.py`
  the same directory as `bilidan.py`


Example
-----

```
./bilidan.py http://www.bilibili.tv/video/av314/
```
Use option `--overseas` if your are outside China.


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
  [extreme density test](http://www.bilibili.tv/video/av332732/index_7.html) at
  60 fps on a Intel Core i5 laptop.


Tips
----

- Use key V to switch comment visibility.
- Some videos require logging in your account. Import your Cookie at bilibili.tv
  with `--cookie` option.
- If you have difficulties connecting to video server, try `--overseas`.
- If your computer is not fast enough, try `--mpvflags '--framedrop yes'`.
- Use `--d2aflags 'text_opacity=0.8'` to set comment opacity.
- Try to fast forward or rewind when streaming is stuck, or to tweak cache
  parameters of mpv.


License
-------

Like the original Biligrab, Biligrab-Danmaku2ASS is licensed under MIT license
as well. This program is provided **as is**, with absolutely no warranty.
