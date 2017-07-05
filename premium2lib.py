#!/usr/bin/python3
import requests
import os
import errno
import ast
import shutil
import sys

customer_id = '797850487' #premiumize customer id
pin = '3rhaut52ssckmq7r' #premiumize pin
base_dir = '/home/dom/test/' #base directory for strm file output
hash_db = base_dir + 'hash.db' #on disk torrent hash db
root_list = (requests.get('https://www.premiumize.me/api/folder/list',params={'customer_id':customer_id,'pin':pin})).json()


#Define video and subs extensions
VIDEO_EXTS = ['M4V' , '3G2' , '3GP' , 'NSV' , 'TP' , 'TS' , 'TY' , 'PLS' , 'RM' , 'RMVB' , 'MPD' , 'M3U' , 'M3U8' , 'IFO' , 'MOV' , 'QT' , 'DIVX' , 'XVID' , 'BIVX' , 'VOB' , 'NRG' , 'PVA' , 'WMV' , 'ASF' , 'ASX' , 'OGM' , 'M2V' , 'AVI' , 'DAT' , 'MPG' , 'MPEG' , 'MP4' , 'MKV' , 'MK3D' , 'AVC' , 'VP3' , 'SVQ3' , 'NUV' , 'VIV' , 'DV' , 'FLI' , 'FLV' , '001' , 'WPL' , 'VDR' , 'DVR-MS' , 'XSP' , 'MTS' , 'M2T' , 'M2TS' , 'EVO' , 'OGV' , 'SDP' , 'AVS' , 'REC' , 'URL' , 'PXML' , 'VC1' , 'H264' , 'RCV' , 'RSS' , 'MPLS' , 'WEBM' , 'BDMV' , 'WTV']
SUBS_EXTS = ['SRT']

#Get torrent list from root_list
def get_torrents(content):
    torrents = []
    imported_torrents = []
    for item in content:
            if item['type'] == 'torrent':
                ondisk_hashes = []
                curTorrent = {'name':item['name'],'hash':item['hash']}
                torrents.append(curTorrent)
                print("Torrent: " + item['name'])
                print("Hash: " + item['hash'])
                #Load hash db from disk
                if os.path.exists(hash_db):
                    with open(hash_db, 'r') as file:
                        raw = file.read()
                        ondisk_hashes = ast.literal_eval(raw)
                #check for unique hash before import
                for od_hash in ondisk_hashes:
                    if od_hash['hash'] == curTorrent['hash']:
                        print("Skipping, already on disk")
                        break
                else:
                    while True:
                        import_torrent = input("Import torrent? (y/n)")
                        if import_torrent.upper() == 'Y':
                            imported_torrents.append(curTorrent)
                            browse_torrent(item['hash'])
                            break
                        elif import_torrent.upper() == 'N':
                            print("Skipping...")
                            break
    cleanup(torrents,imported_torrents)
    
                
#Browse content of torrent for videos
def browse_torrent(hash_id):
    results = (requests.get('https://www.premiumize.me/api/torrent/browse',params={'customer_id':customer_id,'pin':pin, 'hash':hash_id})).json()
    if 'content' in results:
        #print(results['content'])
        get_subs(results['content'])
        videos = get_videos(results['content'])
        for video in videos:
            #print(video)
            #Generate strm files from video results
            create_strm(video)

#Generate array of videos from torrent
def get_videos(content):
    videos = []
    for item in content.values():
        #print (item)
        if item['type'] == 'dir':
            videos += get_videos(item['children'])
        else:
            #if item is video, add to list
            if 'ext' in item and item['ext'].upper() in VIDEO_EXTS:
                print("Found video: " + item['name'])
                path = os.path.splitext(base_dir + item['path'])[0]+'.strm'
                video = {'path': path, 'name': item['name'], 'url': item['url']}
                videos.append(video)
    return videos

#Get subs from torrent
def get_subs(content):
    for item in content.values():
        #print (item)
        if item['type'] == 'dir':
            get_subs(item['children'])
        else:
            #if item is subtitle, download
            if 'ext' in item and item['ext'].upper() in SUBS_EXTS:
                print("Found subtitle: " + item['name'])
                path = base_dir + item['path']
                sub = {'path': path, 'name': item['name'], 'url': item['url']}  
                download_sub(sub)
                
#Generate strm file
def create_strm(video):
    #create directory if not exists
    if not os.path.exists(os.path.dirname(video['path'])):
        try:
            os.makedirs(os.path.dirname(video['path']))
            print("Created path: " + os.path.dirname(video['path']))
        except OSError as exc: # Guard against race condition
            if exc.errno != errno.EEXIST:
                raise
    #create strm file if not exists
    if not os.path.exists(video['path']):
        print("Creating file: " + video['path'])
        with open(video['path'], "w") as f:
            f.write(video['url'])
    else:
        print("Skipping file " + video['path'] + " already exists")

#Download subtitle file
def download_sub(sub):
    #create directory if not exists
    if not os.path.exists(os.path.dirname(sub['path'])):
        try:
            os.makedirs(os.path.dirname(sub['path']))
            print("Created path: " + os.path.dirname(sub['path']))
        except OSError as exc: # Guard against race condition
            if exc.errno != errno.EEXIST:
                raise
    #create sub file if not exists
    if not os.path.exists(sub['path']):
        print("Creating file: " + sub['path'])
        with open(sub['path'], "wb") as file:
            sub_file = requests.get(sub['url'])
            file.write(sub_file.content)
    else:
        print("Skipping file " + sub['path'] + " already exists")

#Check if files on disk are still available on premiumize
#Delete if remotely deleted
def cleanup(torrents,imported_torrents):
    print("Cleanup...")
    ondisk_hashes = []
    #Load hash db from disk
    if os.path.exists(hash_db):
        with open(hash_db, 'r') as file:
            raw = file.read()
            ondisk_hashes = ast.literal_eval(raw)
    #check for unique hash before import
    for im_torrent in imported_torrents:
        for od_hash in ondisk_hashes:
            if od_hash['hash'] == im_torrent['hash']:
                break
        else:
            ondisk_hashes.append(im_torrent)
    #compare ondisk_hashes with torrents hashes
    cleaned_hashes = []
    for od_hash in ondisk_hashes:
        for torrent in torrents:
            if od_hash['hash'] == torrent['hash']:
                print ("Keeping " + od_hash['name'] + " on disk")
                cleaned_hashes.append(od_hash)
                break
        else:
            print ("Deleting " + od_hash['name'] + " from disk")
            shutil.rmtree(base_dir + od_hash['name'])      
    ondisk_hashes = cleaned_hashes
    
    #create directory if not exists
    if not os.path.exists(os.path.dirname(hash_db)):
        try:
            os.makedirs(os.path.dirname(hash_db))
            print("Created path: " + os.path.dirname(hash_db))
        except OSError as exc: # Guard against race condition
            if exc.errno != errno.EEXIST:
                raise
    #save hash db to disk
    with open(hash_db, "w") as file:
        file.write(str(ondisk_hashes))

def main():    
    try:
        get_torrents(root_list['content'])
    except KeyboardInterrupt:
        print("Exiting...")
        sys.exit()

if __name__ == "__main__":
    main()

