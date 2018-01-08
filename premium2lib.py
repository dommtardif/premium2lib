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
import sys
import argparse
import configparser
import threading
import logging
from pathlib import Path
from datetime import timedelta, datetime

__version__ = '0.17'

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


def load_hashdb():
    # Load hash db from disk
    logger = logging.getLogger("load_hashdb")
    if os.path.exists(hash_db):
        try:
            with open(hash_db, 'r') as file:
                raw = file.read()
                ondisk_hashes = ast.literal_eval(raw)
        except Exception as e:
            logger.warning("{0}".format(e))
            logger.warning("Assuming empty hash db")
            ondisk_hashes = []
    else:
        ondisk_hashes = []
    return ondisk_hashes

# Get torrent list from root_list


def get_torrents(content, all_at_once):
    days_before_refresh = 7
    logger = logging.getLogger("get_torrents")
    torrents = []
    imported_torrents = []
    ondisk_hashes = load_hashdb()
    for item in content:
            if item['type'] == 'torrent':
                curTorrent = {'name': item['name'], 'hash': item['hash'],
                              'date': datetime.today().strftime("%d%m%y"),
                              'skip': False}
                torrents.append(curTorrent)
                print("----------   Found torrent   ----------")
                print("Torrent: " + item['name'])
                print("Hash: " + item['hash'])
                skip = False
                if not ondisk_hashes == []:
                    # check for unique hash before import
                    for od_hash in ondisk_hashes:
                        if (od_hash['hash'] == curTorrent['hash'] and
                            (datetime.today() -
                             datetime.strptime(od_hash['date'], "%d%m%y")) <
                            timedelta(days_before_refresh) and
                            (od_hash['skip'] or
                            os.path.exists(os.path.join(base_dir,
                                                        od_hash['name'])))):
                            print("Skipping, already on disk or" +
                                  " marked as skip")
                            skip = True
                            break
                while not skip:
                    if all_at_once:
                        import_torrent = 'Y'
                    else:
                        import_torrent = input("Import torrent? (y/n)")
                    if import_torrent.upper() == 'Y':
                        logger.debug("Importing " + item['name'] +
                                     " hash: " + item['hash'])
                        imported_torrents.append(curTorrent)
                        browse_torrent(item['hash'], all_at_once)
                        break
                    elif import_torrent.upper() == 'N':
                        curTorrent['skip'] = True
                        imported_torrents.append(curTorrent)
                        logger.debug("Skipping " + item['name'] +
                                     " hash: " + item['hash'])
                        break
    cleanup(torrents, imported_torrents)


# Browse content of torrent for videos
def browse_torrent(hash_id, all_at_once):
    number_of_retries = 5
    logger = logging.getLogger("browse_torrent")
    for i in range(1, number_of_retries + 1):
        try:
            results = (requests.
                       post('https://www.premiumize.me/api/torrent/browse',
                            data={'customer_id': customer_id, 'pin': pin,
                                  'hash': hash_id})).json()
        except (requests.ConnectionError,
                requests.HTTPError, requests.Timeout) as e:
            logger.warning("Error getting torrent " + hash_id)
            logger.warning("{0}".format(e))
            logger.warning("Retry: " + str(i) + "/" + str(number_of_retries))
            time.sleep(10)
        except requests.RequestException as e:
            logger.critical("{0}".format(e))
            logger.critical("Unable to handle exception, quitting")
            sys.exit(1)
        else:
            break
    else:
        logger.critical("Unable to handle exception, quitting")
        sys.exit(1)

    if 'content' in results:
        get_subs(results['content'], all_at_once)
        videos = get_videos(results['content'])
        for video in videos:
            # Generate strm files from video results
            create_strm(video, all_at_once)

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


def get_subs(content, all_at_once):
    logger = logging.getLogger("get_subs")
    for item in content.values():
        if item['type'] == 'dir':
            get_subs(item['children'], all_at_once)
        else:
            # if item is subtitle, download
            if 'ext' in item and item['ext'].upper() in SUBS_EXTS:
                logger.info("Found subtitle: " + item['name'])
                path = os.path.join(base_dir, item['path'])
                sub = {'path': path, 'name': item['name'], 'url': item['url']}
                t = threading.Thread(target=download_sub,
                                     args=(sub, all_at_once),
                                     name="Download: " + item['name'])
                t.start()

# Generate strm file


def create_strm(video, all_at_once):
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
    logger.debug("Creating file: " + video['path'])
    while True:
        try:
            with open(video['path'], "w") as f:
                f.write(video['url'])
        except Exception as e:
            logger.warning("{0}".format(e))
            e_handling = input("(R)etry, (S)kip, (A)bort?")
            if e_handling.upper() == 'S' or all_at_once:
                break
            elif e_handling.upper() == 'A':
                sys.exit(1)
            else:
                pass
        else:
            break

# Download subtitle file


def download_sub(sub, all_at_once):
    number_of_retries = 5
    logger = logging.getLogger("download_sub")
    # create directory if not exists
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
        while True:
            try:
                with open(sub['path'], "wb") as file:
                    for i in range(1, number_of_retries + 1):
                        try:
                            sub_file = requests.get(sub['url'])
                        except (requests.ConnectionError,
                                requests.HTTPError, requests.Timeout) as e:
                            logger.warning("Error getting subtitle " +
                                           sub['url'])
                            logger.warning("{0}".format(e))
                            logger.warning("Retry: " + str(i) + "/" +
                                           str(number_of_retries))
                            time.sleep(10)
                        except requests.RequestException as e:
                            logger.critical("{0}".format(e))
                            logger.critical("Unable to handle exception," +
                                            "quitting")
                            sys.exit(1)
                        else:
                            break
                    else:
                        print("Unable to handle exception, quitting")
                        sys.exit(1)
                    file.write(sub_file.content)
            except Exception as e:
                logger.warning("{0}".format(e))
                e_handling = input("(R)etry, (S)kip, (A)bort?")
                if e_handling.upper() == 'S' or all_at_once:
                    break
                elif e_handling.upper() == 'A':
                    sys.exit(1)
                else:
                    pass
            else:
                break
    else:
        logger.debug("Skipping file " + sub['path'] + " already exists")

# Check if files on disk are still available on premiumize
# Delete if remotely deleted


def cleanup(torrents, imported_torrents):
    logger = logging.getLogger("cleanup")
    logger.info("Cleanup...")
    ondisk_hashes = load_hashdb()
    # Load hash db from disk
    if not ondisk_hashes == []:
        # check for unique hash before import
        for im_torrent in imported_torrents:
            for od_hash in ondisk_hashes:
                if od_hash['hash'] == im_torrent['hash']:
                    break
            else:
                ondisk_hashes.append(im_torrent)
    else:
        ondisk_hashes = imported_torrents
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
                try:
                    torrent_path = Path(os.path.join(base_dir,
                                                     od_hash['name']))
                    for f in torrent_path.glob("**/*.strm"):
                        print("Deleting " + str(f))
                        os.remove(str(f))
                except Exception as e:
                    logger.warning("{0}".format(e))
                    logger.warning("Unable to properly delete torrent")
                    logger.warning("Keeping in db for next cleanup")
                    cleaned_hashes.append(od_hash)
                else:
                    logger.debug("Deleted " +
                                 os.path.join(base_dir, od_hash['name']))
            else:
                logger.warning(od_hash['name'] + " has been removed " +
                               "from premiumize")
    ondisk_hashes = cleaned_hashes

    # create directory if not exists
    try:
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
    except Exception as e:
        logger.warning("{0}".format(e))
        logger.warning("Unable to save hash db to disc")


def main():
    global base_dir, customer_id, pin

    parser = argparse.ArgumentParser(description=prog_description)
    config = configparser.ConfigParser()
    config['MAIN'] = {}

    # if config not exists, make args required
    # args_req = True
    if not os.path.exists(config_file):
        args_req = True
    # Config file exists, load its values first, override with args
    else:
        try:
            config.read(config_file)
            customer_id = config.get('MAIN', 'customer_id')
            pin = config.get('MAIN', 'pin')
            base_dir = config.get('MAIN', 'base_dir')
        except (configparser.Error) as e:
            print("{0}".format(e))
            print("Error reading config file, ignoring")
            customer_id = ""
            pin = ""
            base_dir = ""
            args_req = True
        else:
            args_req = False

    parser.add_argument('-u', '--user', metavar="ID", required=args_req,
                        help="Premiumize customer id")
    parser.add_argument('-p', '--pin', required=args_req,
                        help="Premiumize PIN")
    parser.add_argument('-o', '--outdir', required=args_req, metavar="PATH",
                        help="Output directory for generated files")
    parser.add_argument('-a', '--all', action='store_true',
                        help="Import all videos from premiumize at once")
    debug_group = parser.add_argument_group("Ouput", "Output related options")
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
    number_of_retries = 5
    for i in range(1, number_of_retries + 1):  # Try 5 times
        try:
            root_list = (requests.post(
                         'https://www.premiumize.me/api/folder/list',
                         data={'customer_id': customer_id, 'pin': pin})).json()
        except (requests.ConnectionError,
                requests.HTTPError, requests.Timeout) as e:
            logger.warning("Error getting root folder from premiumize")
            logger.warning("{0}".format(e))
            logger.warning("Retry: " + str(i) + "/" + str(number_of_retries))
            time.sleep(10)
        except requests.RequestException as e:
            logger.critical("{0}".format(e))
            logger.critical("Unable to handle exception, quitting")
            sys.exit(1)
        else:
            break
    else:
        logger.critical("Unable to handle exception, quitting")
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
