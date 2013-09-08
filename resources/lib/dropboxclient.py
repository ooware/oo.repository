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
import xbmcgui
import xbmcvfs
import shutil

import os
import time
import threading, Queue

from utils import *

from dropbox import client, rest

try:
    import StorageServer
except:
    import storageserverdummy as StorageServer

def command():
    """a decorator for handling authentication and exceptions"""
    def decorate(f):
        def wrapper(self, *args):
            try:
                return f(self, *args)
            except TypeError, e:
                log_error('TypeError: %s' %str(e))
            except rest.ErrorResponse, e:
                self.DropboxAPI = None
                msg = e.user_error_msg or str(e)
                log_error("%s failed: %s"%(f.__name__, msg) )
                dialog = xbmcgui.Dialog()
                dialog.ok(ADDON_NAME, LANGUAGE_STRING(31005), '%s' % (msg))

        wrapper.__doc__ = f.__doc__
        return wrapper
    return decorate

class XBMCDropBoxClient(object):
    DropboxAPI = None
    _cache = None
    
#TODO: fix singleton --> it doesn't work!
    _instance = None
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(XBMCDropBoxClient, cls).__new__(
                                cls, *args, **kwargs)
        return cls._instance

    def __init__( self ):
        #get Settings
        token = ADDON.getSetting('access_token').decode("utf-8")
        #Use user defined location?
        datapath = ADDON.getSetting('cachepath').decode("utf-8")
        if datapath == '' or os.path.normpath(datapath) == '':
            #get the default path 
            datapath = xbmc.translatePath( ADDON.getAddonInfo('profile') )
        self._shadowPath = datapath + '/shadow/'
        self._thumbPath = datapath + '/thumb/'
        #get storage server
        self._cache = StorageServer.StorageServer(ADDON_NAME, 168) # (Your plugin name, Cache time in hours)
        #get Dropbox API (handle)
        if self.DropboxAPI == None:
            log_debug("Getting dropbox client with token: %s"%token)
            try:
                self.DropboxAPI = client.DropboxClient(token)
            except rest.ErrorResponse, e:
                msg = e.user_error_msg or str(e)
                dialog = xbmcgui.Dialog()
                dialog.ok(ADDON_NAME, LANGUAGE_STRING(31005), '%s' % (msg))

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
            if directory or stored == '':
                try:
                    resp = self.DropboxAPI.metadata(path=dirname, hash=hashstr)
                except rest.ErrorResponse, e:
                    msg = e.user_error_msg or str(e)
                    if '304' in msg:
                        #cached data is still the same
                        log_debug("Metadata using stored data")
                        resp = stored
                    else:
                        log_error("Failed retrieving Metadata: %s"%msg)
                        self.DropboxAPI = None
                        msg = e.user_error_msg or str(e)
                        dialog = xbmcgui.Dialog()
                        dialog.ok(ADDON_NAME, LANGUAGE_STRING(31005), '%s' % (msg))
                else:
                    #When no exception: store new retrieved data
                    log_debug("New/updated Metadata is stored")
                    self._cache.set(dirname, repr(resp))
                    self._removeCachedFileFolder(resp)
            else:
                #get the file metadata using the stored data
                resp = stored
            if resp and not directory:
                #get the file metadata
                for item in resp['contents']:
                    if item['path'] == path:
                        resp = item
                        break;
        return resp

    def _removeCachedFileFolder(self, metadata):
        cachedLocation = self._shadowPath + metadata['path']
        cachedLocation = os.path.normpath(cachedLocation)
        tumbLocation = self._thumbPath + metadata['path']
        tumbLocation = os.path.normpath(tumbLocation)
        folderItems = []
        fileItems = []
        if xbmcvfs.exists(cachedLocation) or xbmcvfs.exists(tumbLocation):
            #folderItems = (os.path.basename(item['path']) for item in metadata['contents'] if item['is_dir']) if folder not in folderitems of generator expression does not work...
            for item in metadata['contents']:
                if item['is_dir']:
                    folderItems.append(os.path.basename(item['path']))
                else:
                    fileItems.append(os.path.basename(item['path']))
        #remove shadow files/folders
        if xbmcvfs.exists(cachedLocation):
            cachedFolders, cachedFiles = xbmcvfs.listdir(cachedLocation)
            #check if folders/files needs to be removed
            for folder in cachedFolders:
                if folder not in folderItems:
                    folderName = os.path.join(cachedLocation, folder)
                    log_debug('Removing cached folder: %s' % (folderName))
                    shutil.rmtree(folderName)
            for f in cachedFiles:
                if f not in fileItems:
                    fileName = os.path.join(cachedLocation, f)
                    log_debug('Removing cached file: %s' % (fileName))
                    os.remove(fileName)
        #remove tumb files/folders
        if xbmcvfs.exists(tumbLocation):
            tumbFolders, tumbFiles = xbmcvfs.listdir(tumbLocation)
            #check if folders/files needs to be removed
            for folder in tumbFolders:
                if folder not in folderItems:
                    folderName = os.path.join(tumbLocation, folder)
                    log_debug('Removing tumb folder: %s' % (folderName))
                    shutil.rmtree(folderName)
            #first replace the tumb file extention
            for i, f in enumerate(fileItems):
                fileItems[i] = replaceFileExtension(f, 'jpg')
            for f in tumbFiles:
                if f not in fileItems:
                    fileName = os.path.join(tumbLocation, f)
                    log_debug('Removing tumb file: %s' % (fileName))
                    os.remove(fileName)
            
        
    @command()
    def getMediaUrl(self, path, cachedonly=False):
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
                    log_debug("MediaUrl using stored url.")
                else:
                    log_debug("MediaUrl expired. End time was: %s"%stored['expires'])
        if not cachedonly and resp == None and self.DropboxAPI != None:
            resp = self.DropboxAPI.media(path)
            #store the link
            log_debug("MediaUrl storing url.")
            self._cache.set("mediaUrl:"+path, repr(resp))
        if resp:
            return resp['url']
        else:
            return '' 
    
    @command()
    def search(self, searchText):
        searchResult = self.DropboxAPI.search('', searchText)
        return searchResult

class FileLoader(threading.Thread):
    DropboxAPI = None
    _stop = False
    stopWhenFinished = False
    _itemsHandled = 0
    _itemsTotal = 0
    
    def __init__( self, DropboxAPI, module, metadata, shadowPath, thumbPath):
        threading.Thread.__init__(self)
        self._shadowPath = shadowPath
        self._thumbPath = thumbPath
        self.DropboxAPI = DropboxAPI
        self._module = module
        self._metadata = metadata
        self._thumbList = Queue.Queue() #thread safe
        self._fileList = Queue.Queue() #thread safe
#         self._progress = xbmcgui.DialogProgress()
#         self._progress.create('Dropbox: downloading files...', 'Dropbox: downloading files...')

    def run(self):
        #check if need to quit
        log_debug("FileLoader started for: %s"%self._module)
        while not self._stop and not self.ready():
            #First get all the thumbnails(priority), then all the original files
            thumb2Retrieve = None
            file2Retrieve = None
            if not self._thumbList.empty():
                thumb2Retrieve = self._thumbList.get()
            elif not self._fileList.empty():
                file2Retrieve = self._fileList.get()
            if thumb2Retrieve:
                location = self._getThumbLocation(thumb2Retrieve)
                #Check if thumb already exists
                # TODO: use database checking for this!
                if not xbmcvfs.exists(location):
                    #Doesn't exist so download it.
                    self._getThumbnail(thumb2Retrieve)
                else:
                    log_debug("Thumbnail already downloaded: %s"%location)
                self._itemsHandled += 1
#                 precent = (self._itemsHandled / self._itemsTotal) * 100
#                 self._progress.update(precent)
            elif file2Retrieve:
                location = self._getShadowLocation(file2Retrieve)
                #Check if thumb already exists
                #TODO: use database checking for this!
                if not xbmcvfs.exists(location):
                    #Doesn't exist so download it.
                    self._getFile(file2Retrieve)
                else:
                    log_debug("Original file already downloaded: %s"%location)
                self._itemsHandled += 1
#                 precent = (self._itemsHandled / self._itemsTotal) * 100
#                 self._progress.update(precent)
            time.sleep(0.100)
        if self._stop:
            log_debug("FileLoader stopped (as requested) for: %s"%self._module)
        else:
            log_debug("FileLoader finished for: %s"%self._module)
#         self._progress.close()
        
    def stop(self):
        self._stop = True
        
    def ready(self):
        if self.stopWhenFinished and ( self._thumbList.empty() and self._fileList.empty() ):
            return True
        else:
            return False
        
    def getThumbnail(self, path):
        #get the file metadata
        for item in self._metadata:
            if item['path'] == path:
                metadata = item
                break;
        if metadata['thumb_exists']:
            self._thumbList.put(path)
            self._itemsTotal += 1
            return self._getThumbLocation(path)
        else:
            return None

    def getFile(self, path):
        self._fileList.put(path)
        self._itemsTotal += 1
        return self._getShadowLocation(path)
    
    def _getThumbLocation(self, path):
        #jpeg (default) or png. For images that are photos, jpeg should be preferred, while png is better for screenshots and digital art.
        location = replaceFileExtension(path, 'jpg')
        location = self._thumbPath + location
        location = os.path.normpath(location)
        return location

    def _getThumbnail(self, path):
        location = self._getThumbLocation(path)
        dirName = os.path.dirname(location)
        # create the data dir if needed
        if not xbmcvfs.exists( dirName ):
            xbmcvfs.mkdirs( dirName )
        try:
            cacheFile =open(location, 'w')
            #download the file
            #jpeg (default) or png. For images that are photos, jpeg should be preferred, while png is better for screenshots and digital art.
            tumbFile = self.DropboxAPI.thumbnail(path, size='large', format='JPEG')
            cacheFile.write( tumbFile.read() )
            cacheFile.close()
            log_debug("Downloaded file to: %s"%location)
        except IOError, e:
            msg = str(e)
            log_error('Failed saving file %s. Error: %s' %(location,msg) )
        except rest.ErrorResponse, e:
            msg = e.user_error_msg or str(e)
            log_error('Failed downloading file %s. Error: %s' %(location,msg))
        return location

    def _getShadowLocation(self, path):
        location = self._shadowPath + path
        location = os.path.normpath(location)
        return location
    
    def _getFile(self, path):
        location = self._getShadowLocation(path)
        dirName = os.path.dirname(location)
        # create the data dir if needed
        if not xbmcvfs.exists( dirName ):
            xbmcvfs.mkdirs( dirName )
        try:
            #log("Download file to: %s"%location)
            cacheFile =open(location, 'w')
            #download the file
            orgFile = self.DropboxAPI.get_file(path)
            cacheFile.write( orgFile.read())
            cacheFile.close()
            log_debug("Downloaded file to: %s"%location)
        except IOError, e:
            msg = str(e)
            log_error('Failed saving file %s. Error: %s' %(location,msg) )
        except rest.ErrorResponse, e:
            msg = e.user_error_msg or str(e)
            log_error('Failed downloading file %s. Error: %s' %(location,msg))
        return location
