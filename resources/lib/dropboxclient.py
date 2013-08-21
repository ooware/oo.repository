#/*
# *      Copyright (C) 2013 Joost Kop
# *
# *
# *  This Program is free software; you can redistribute it and/or modify
# *  it under the terms of the GNU General Public License as published by
# *  the Free Software Foundation; either version 2, or (at your option)
# *  any later version.
# *
# *  This Program is distributed in the hope that it will be useful,
# *  but WITHOUT ANY WARRANTY; without even the implied warranty of
# *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# *  GNU General Public License for more details.
# *
# *  You should have received a copy of the GNU General Public License
# *  along with this program; see the file COPYING.  If not, write to
# *  the Free Software Foundation, 675 Mass Ave, Cambridge, MA 02139, USA.
# *  http://www.gnu.org/copyleft/gpl.html
# *
# */

import xbmc
import xbmcplugin
import xbmcgui
import xbmcaddon
import xbmcvfs

import os, sys
import time

from utils import *

from dropbox import client, rest

try:
    import StorageServer
except:
    import storageserverdummy as StorageServer


class XBMCDropBoxClient(object):
    DropboxAPI = None
    _cache = None
    
#todo, fix singleton --> it doesn't work!
    _instance = None
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(XBMCDropBoxClient, cls).__new__(
                                cls, *args, **kwargs)
        return cls._instance

    def __init__( self ):
        #get Settings
        token = xbmcaddon.Addon().getSetting('access_token').decode("utf-8")
        #get storage server
        self._cache = StorageServer.StorageServer(ADDON, 168) # (Your plugin name, Cache time in hours)
        #get Dropbox API (handle)
        if self.DropboxAPI == None:
            log("Getting dropbox client with token: %s"%token)
            try:
                self.DropboxAPI = client.DropboxClient(token)
            except rest.ErrorResponse, e:
                msg = e.user_error_msg or str(e)
                dialog = xbmcgui.Dialog()
                dialog.ok(ADDON, 'Error login into Dropbox:', '%s' % (msg))

    def getFolderContents(self, path):
        contents = []
        resp = self.getMetaData(path, directory=True)
        if 'contents' in resp:
            contents = resp['contents']
        return contents

    def getMetaData(self, path, directory=False):
        '''
        Metadata is cached the metadata of the directory.
        The metadata of a file is retrieved from the directory metadata.
        for storing caching the metadata, the StorageServer 
        (script.common.plugin.cache addon) is used.
        '''
        hashstr = None
        dirname = path
        if not directory:
            #strip the filename
            dirname = path.rpartition('/')[0]
        #check if a hash is available
        stored = self._cache.get(dirname)
        if stored != '':
            stored = eval(stored)
            if 'hash' in stored:
                hashstr = stored['hash']
                #log("Metadata using stored hash: %s"%hashstr)
        resp = None
        if self.DropboxAPI != None:
            if stored == '':
                try:
                    resp = self.DropboxAPI.metadata(path=dirname, hash=hashstr)
                except rest.ErrorResponse, e:
                    msg = e.user_error_msg or str(e)
                    if '304' in msg:
                        #cached data is still the same
                        log("Metadata using stored data")
                        resp = stored
                    else:
                        log_error("Failed retrieving Metadata: %s"%msg)
                else:
                    #When no execption: store new retrieved data
                    log("new/updated Metadata is stored")
                    self._cache.set(dirname, repr(resp))
            else:
                #get the file metadata using the stored data
                resp = stored
            if not directory:
                #get the file metadata
                for item in stored['contents']:
                    if item['path'] == path:
                        resp = item
                        break;
        return resp

    def getMediaUrl(self, path):
        '''
        Cache this URL because it takes a lot of time requesting it...
        If the mediaUrl is still valid, within the margin, then don't
        request a new one yet.
        '''
        margin = 20*60 #20 mins
        resp = None
        #check if stored link is still valid
        stored = self._cache.get("mediaUrl:"+path)
        if stored != '':
            stored = eval(stored)
            if 'expires' in stored:
                # format: "Fri, 16 Sep 2011 01:01:25 +0000"
                until = time.strptime(stored['expires'], "%a, %d %b %Y %H:%M:%S +0000")
                #convert to floats
                until = time.mktime(until)
                currentTime = time.time() 
                if(until > (currentTime + margin) ):
                    #use stored link
                    resp = stored
                    log("MediaUrl using stored url")
        if resp == None and self.DropboxAPI != None:
            resp = self.DropboxAPI.media(path)
            #store the link
            log("MediaUrl storing url")
            self._cache.set("mediaUrl:"+path, repr(resp))
        return resp['url']
    
