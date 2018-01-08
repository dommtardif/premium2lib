# premium2lib
[Premiumize.me](https://www.premiumize.me) allows you to store video files online.
Although an api is available, as well as a [Kodi plugin](https://github.com/tknorris/plugin.video.premiumize) to browse your files,
it is up to now impossible to integrate Premiumize with the Kodi library.

This is why I decided to create this script. It is meant to be run from the
commandline. I have tested this under Linux and Python 3 and all works well.
It should also be able to run under Windows, although this has not been tested (comments welcome).

On the first run, the commandline parameters are mandatory to initialize the config file.
After the first run, the values of the config file will be used, unless parameters are specified.

The script will output .strm files that are compatible with Kodi into the specified output directory. All that is left to do is add the output directory as a media source in Kodi.

## Usage
```
usage: premium2lib.py [-h] [-u ID] [-p PIN] [-o PATH] [-a] [-d | -v | -q]
                      [--version]

Generates kodi-compatible strm files from torrents on premiumize. Parameters
are required for first run to generate config file

optional arguments:
  -h, --help            show this help message and exit
  -u ID, --user ID      Premiumize customer id
  -p PIN, --pin PIN     Premiumize PIN
  -o PATH, --outdir PATH
                        Output directory for generated files
  -a, --all             Import all videos from premiumize at once
  --version             show program's version number and exit

Ouput:
  Output related options

  -d, --debug           Show debug output
  -v, --verbose         Show verbose output
  -q, --quiet           Disable output

```

## Thanks
Thanks to [tknorris](https://github.com/tknorris) and his premiumize plugin
for the original inspiration.
