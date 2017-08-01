#!/usr/bin/python3
###########################
#
# This was originally heavily inspired by tknorris' premiumize kodi addon.
# Although this project has pretty much nothing to do with his original
# code anymore, I still wish to recognize his work.
# You can find him on github at
# https://github.com/tknorris/
#
##########################
import time
import requests
import os
import errno
import ast
import shutil
import sys
import argparse
import configparser
import colorama
from colorama import Back
import threading
import logging
from datetime import timedelta, datetime

__version__ = '0.17'


colorama.init()

prog_description = ("Generates kodi-compatible strm files from torrents on "
                    "premiumize. Parameters are required for first run to "
                    "generate config file")

# on disk torrent hash db
hash_db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hash.db")

config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "config_p2l.ini")


# Define video and subs extensions
VIDEO_EXTS = ['M4V', '3G2', '3GP', 'NSV', 'TP', 'TS', 'TY', 'PLS', 'RM',
              'RMVB', 'MPD', 'M3U', 'M3U8', 'IFO', 'MOV', 'QT', 'DIVX', 'XVID',
              'BIVX', 'VOB', 'NRG', 'PVA', 'WMV', 'ASF', 'ASX', 'OGM', 'M2V',
              'AVI', 'DAT', 'MPG', 'MPEG', 'MP4', 'MKV', 'MK3D', 'AVC', 'VP3',
              'SVQ3', 'NUV', 'VIV', 'DV', 'FLI', 'FLV', '001', 'WPL', 'VDR',
              'DVR-MS', 'XSP', 'MTS', 'M2T', 'M2TS', 'EVO', 'OGV', 'SDP',
              'AVS', 'REC', 'URL', 'PXML', 'VC1', 'H264', 'RCV', 'RSS',
              'MPLS', 'WEBM', 'BDMV', 'WTV']
SUBS_EXTS = ['SRT']

# Get torrent list from root_list


def get_torrents(content, all_at_once):
    logger = logging.getLogger("get_torrents")
    torrents = []
    imported_torrents = []
    for item in content:
            if item['type'] == 'torrent':
                ondisk_hashes = []
                curTorrent = {'name': item['name'], 'hash': item['hash'],
                              'date': datetime.today().strftime("%d%m%y"),
                              'skip': False}
                torrents.append(curTorrent)
                print(Back.GREEN + "Found torrent" + Back.BLACK)
                print("Torrent: " + item['name'])
                print("Hash: " + item['hash'])
                # Load hash db from disk
                if os.path.exists(hash_db):
                    with open(hash_db, 'r') as file:
                        raw = file.read()
                        ondisk_hashes = ast.literal_eval(raw)
                # check for unique hash before import
                for od_hash in ondisk_hashes:
                    if (od_hash['hash'] == curTorrent['hash'] and
                        (datetime.today() -
                         datetime.strptime(od_hash['date'], "%d%m%y")) <
                        timedelta(7) and
                        (od_hash['skip'] or
                        os.path.exists(os.path.join(base_dir,
                                                    od_hash['name'])))):
                        print("Skipping, already on disk or marked as skip")
                        break
                else:
                    while True:
                        if all_at_once:
                            import_torrent = 'Y'
                        else:
                            import_torrent = input("Import torrent? (y/n)")
                        if import_torrent.upper() == 'Y':
                            logger.debug("Importing " + item['name'] +
                                         " hash: " + item['hash'])
                            imported_torrents.append(curTorrent)
                            browse_torrent(item['hash'])
                            break
                        elif import_torrent.upper() == 'N':
                            curTorrent['skip'] = True
                            imported_torrents.append(curTorrent)
                            logger.debug("Skipping " + item['name'] +
                                         " hash: " + item['hash'])
                            break
    cleanup(torrents, imported_torrents)


# Browse content of torrent for videos
def browse_torrent(hash_id):
    for i in range(0, 5):  # Try 5 times
        try:
            results = (requests.
                       post('https://www.premiumize.me/api/torrent/browse',
                            data={'customer_id': customer_id, 'pin': pin,
                                  'hash': hash_id})).json()
        except requests.exceptions.ConnectionError:
            print("Unable to contact premiumize, waiting 60 secs")
            time.sleep(60)
        except requests.exceptions.HTTPError:
            print("HTTP Error, waiting")
            time.sleep(60)
        except requests.exceptions.RequestException:
            print("Unable to handle exception, quitting")
            sys.exit(1)
        else:
            break
    else:
        print("Unable to handle exception, quitting")
        sys.exit(1)

    if 'content' in results:
        get_subs(results['content'])
        videos = get_videos(results['content'])
        for video in videos:
            # Generate strm files from video results
            create_strm(video)

# Generate array of videos from torrent


def get_videos(content):
    logger = logging.getLogger("get_videos")
    videos = []
    for item in content.values():
        if item['type'] == 'dir':
            videos += get_videos(item['children'])
        else:
            # if item is video, add to list
            if 'ext' in item and item['ext'].upper() in VIDEO_EXTS:
                logger.info("Found video: " + item['name'])
                path = os.path.join(base_dir,
                                    os.path.splitext(item['path'])[0]+'.strm')
                video = {'path': path, 'name': item['name'],
                         'url': item['url']}
                videos.append(video)
    return videos

# Get subs from torrent


def get_subs(content):
    logger = logging.getLogger("get_subs")
    for item in content.values():
        if item['type'] == 'dir':
            get_subs(item['children'])
        else:
            # if item is subtitle, download
            if 'ext' in item and item['ext'].upper() in SUBS_EXTS:
                logger.info("Found subtitle: " + item['name'])
                path = os.path.join(base_dir, item['path'])
                sub = {'path': path, 'name': item['name'], 'url': item['url']}
                t = threading.Thread(target=download_sub, args=((sub),),
                                     name="Download: " + item['name'])
                t.start()

# Generate strm file


def create_strm(video):
    logger = logging.getLogger("create_strm")
    # create directory if not exists
    if not os.path.exists(os.path.dirname(video['path'])):
        try:
            os.makedirs(os.path.dirname(video['path']))
            logger.debug("Created path: " + os.path.dirname(video['path']))
        except OSError as exc:  # Guard against race condition
            if exc.errno != errno.EEXIST:
                raise
    # create strm file if not exists
    if not os.path.exists(video['path']):
        logger.debug("Creating file: " + video['path'])
        with open(video['path'], "w") as f:
            f.write(video['url'])
    else:
        logger.debug("Skipping file " + video['path'] + " already exists")

# Download subtitle file


def download_sub(sub):
    # create directory if not exists
    logger = logging.getLogger("download_sub")
    if not os.path.exists(os.path.dirname(sub['path'])):
        try:
            os.makedirs(os.path.dirname(sub['path']))
            logger.debug("Created path: " + os.path.dirname(sub['path']))
        except OSError as exc:  # Guard against race condition
            if exc.errno != errno.EEXIST:
                raise
    # create sub file if not exists
    if not os.path.exists(sub['path']):
        logger.debug("Creating file: " + sub['path'])
        with open(sub['path'], "wb") as file:
            for i in range(0, 5):  # Try 5 times
                try:
                    sub_file = requests.get(sub['url'])
                except requests.exceptions.ConnectionError:
                    print("Unable to contact premiumize, waiting 60 secs")
                    time.sleep(60)
                except requests.exceptions.HTTPError:
                    print("HTTP Error, waiting")
                    time.sleep(60)
                except requests.exceptions.RequestException:
                    print("Unable to handle exception, quitting")
                    sys.exit(1)
                else:
                    break
            else:
                print("Unable to handle exception, quitting")
                sys.exit(1)
            file.write(sub_file.content)
    else:
        logger.debug("Skipping file " + sub['path'] + " already exists")

# Check if files on disk are still available on premiumize
# Delete if remotely deleted


def cleanup(torrents, imported_torrents):
    logger = logging.getLogger("cleanup")
    logger.info("Cleanup...")
    ondisk_hashes = []
    # Load hash db from disk
    if os.path.exists(hash_db):
        with open(hash_db, 'r') as file:
            raw = file.read()
            ondisk_hashes = ast.literal_eval(raw)
    # check for unique hash before import
    for im_torrent in imported_torrents:
        for od_hash in ondisk_hashes:
            if od_hash['hash'] == im_torrent['hash']:
                break
        else:
            ondisk_hashes.append(im_torrent)
    # compare ondisk_hashes with torrents hashes
    cleaned_hashes = []
    for od_hash in ondisk_hashes:
        for torrent in torrents:
            if (od_hash['hash'] == torrent['hash']):
                logger.info("Keeping " + od_hash['name'])
                cleaned_hashes.append(od_hash)
                break
        else:
            if os.path.exists(os.path.join(base_dir, od_hash['name'])):
                logger.warning("Deleting " + od_hash['name'] + " from disk" +
                               " because it was deleted on premiumize")
                shutil.rmtree(os.path.join(base_dir, od_hash['name']))
                logger.debug("Deleted " +
                             os.path.join(base_dir, od_hash['name']))
            else:
                logger.warning(od_hash['name'] + " has been removed " +
                               "from premiumize")
    ondisk_hashes = cleaned_hashes

    # create directory if not exists
    if not os.path.exists(os.path.dirname(hash_db)):
        try:
            os.makedirs(os.path.dirname(hash_db))
            logger.debug("Created path: " + os.path.dirname(hash_db))
        except OSError as exc:  # Guard against race condition
            if exc.errno != errno.EEXIST:
                raise
    # save hash db to disk
    with open(hash_db, "w") as file:
        file.write(str(ondisk_hashes))


def main():
    global base_dir, customer_id, pin

    parser = argparse.ArgumentParser(description=prog_description)
    config = configparser.ConfigParser()
    config['MAIN'] = {}

    # if config not exists, make args required
    if not os.path.exists(config_file):
        parser.add_argument('-u', '--user', metavar="ID", required=True,
                            help="Premiumize customer id")
        parser.add_argument('-p', '--pin', required=True,
                            help="Premiumize PIN")
        parser.add_argument('-o', '--outdir', required=True, metavar="PATH",
                            help="Output directory for generated files")
    # Config file exists, load its values first, override with args
    else:
        config.read(config_file)
        customer_id = config['MAIN']['customer_id']
        pin = config['MAIN']['pin']
        base_dir = config['MAIN']['base_dir']

        parser.add_argument('-u', '--user', metavar="ID",
                            help="Premiumize customer id")
        parser.add_argument('-p', '--pin', help="Premiumize PIN")
        parser.add_argument('-o', '--outdir', metavar="PATH",
                            help="Output directory for generated files")

    parser.add_argument('-a', '--all', action='store_true',
                        help="Import all videos from premiumize at once")
    debug_group = parser.add_argument_group("Debug", "Debug related options")
    debug_options = debug_group.add_mutually_exclusive_group()
    debug_options.add_argument('-d', '--debug', action="store_true",
                               help="Show debug output")
    debug_options.add_argument('-v', '--verbose', action='store_true',
                               help="Show verbose output")
    debug_options.add_argument('-q', '--quiet', action='store_true',
                               help="Disable output")
    parser.add_argument('--version', action='version',
                        version='%(prog)s {version}'
                        .format(version=__version__))

    args = parser.parse_args()
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    elif args.verbose:
        logging.basicConfig(level=logging.INFO)
    elif args.quiet:
        logging.basicConfig(level=60)
        sys.stdout = open(os.devnull, "w")
    else:
        logging.basicConfig(level=logging.WARNING)
    if args.user is not None:
        customer_id = args.user
        config['MAIN']['customer_id'] = args.user
    if args.pin is not None:
        pin = args.pin
        config['MAIN']['pin'] = args.pin
    if args.outdir is not None:
        base_dir = os.path.join(args.outdir, '')
        config['MAIN']['base_dir'] = os.path.join(args.outdir, '')

    logger = logging.getLogger("main")
    logger.debug("Arguments from command line: " + str(sys.argv[1:]))

    with open(config_file, 'w') as configfile:
        config.write(configfile)
        logger.debug("Saved config to file: " + config_file)

    # Start actual creation process
    for i in range(0, 5):  # Try 5 times
        try:
            root_list = (requests.post(
                         'https://www.premiumize.me/api/folder/list',
                         data={'customer_id': customer_id, 'pin': pin})).json()
        except requests.exceptions.ConnectionError:
            print("Unable to contact premiumize, waiting 60 secs")
            time.sleep(60)
        except requests.exceptions.HTTPError:
            print("HTTP Error, waiting")
            time.sleep(60)
        except requests.exceptions.RequestException:
            print("Unable to handle exception, quitting")
            sys.exit(1)
        else:
            break
    else:
        print("Unable to handle exception, quitting")
        sys.exit(1)

    try:
        get_torrents(root_list['content'], args.all)
    except KeyboardInterrupt:
        print("Exiting...")
        sys.exit(1)

    if threading.active_count() > 1:
        print("Waiting for download processes to finish")
        logger.debug("Active threads: " + str(threading.active_count()))
    while threading.active_count() > 1:
        pass
    print("Exiting...")
    sys.exit(0)

if __name__ == "__main__":
    main()
