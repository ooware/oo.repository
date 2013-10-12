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
from StringIO import StringIO

from dropboxprogress import DropboxBackgroundProgress

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
                dialog.ok(ADDON_NAME, LANGUAGE_STRING(31006), '%s' % (msg))

        wrapper.__doc__ = f.__doc__
        return wrapper
    return decorate

def string_path(path):
    '''
    Dropbox API uses "utf-8" conding.
    This functions converts the path to string (if unicode)
    '''
    if isinstance (path, unicode):
        path = path.encode("utf-8")
    return path


class XBMCDropBoxClient(object):
    '''
    Provides a more 'general' interface to dropbox.
    Handles all dropbox API specifics
    '''
    DropboxAPI = None
    _cache = None
    
#TODO: fix singleton --> it doesn't work!
#     _instance = None
#     def __new__(cls, *args, **kwargs):
#         if not cls._instance:
#             cls._instance = super(XBMCDropBoxClient, cls).__new__(
#                                 cls, *args, **kwargs)
#         return cls._instance

    def __init__( self, autoConnect = True ):
        #get storage server
        self._cache = StorageServer.StorageServer(ADDON_NAME, 168) # (Your plugin name, Cache time in hours)
        if autoConnect:
            succes, msg = self.connect()
            if not succes:
                dialog = xbmcgui.Dialog()
                dialog.ok(ADDON_NAME, LANGUAGE_STRING(31005), '%s' % (msg))

    def connect(self):
        msg = 'No error'
        #get Settings
        token = ADDON.getSetting('access_token').decode("utf-8")
        #get Dropbox API (handle)
        if self.DropboxAPI == None:
            #log_debug("Getting dropbox client with token: %s"%token)
            try:
                self.DropboxAPI = client.DropboxClient(token)
            except rest.ErrorResponse, e:
                msg = e.user_error_msg or str(e)
        return (self.DropboxAPI != None), msg

    def disconnect(self):
        self.DropboxAPI == None

    def getFolderContents(self, path):
        contents = []
        resp, changed = self.getMetaData(path, directory=True)
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
        changed = False
        dirname = path
        if not directory:
            #strip the filename
            dirname = os.path.dirname(path)
        #check if a hash is available
        stored = self._cache.get(dirname.decode("utf-8"))
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
                        log_debug("Metadata using stored data for %s"%dirname)
                        resp = stored
                    else:
                        log_error("Failed retrieving Metadata: %s"%msg)
                        self.DropboxAPI = None
                        msg = e.user_error_msg or str(e)
                        dialog = xbmcgui.Dialog()
                        dialog.ok(ADDON_NAME, LANGUAGE_STRING(31006), '%s' % (msg))
                else:
                    #When no exception: store new retrieved data
                    log_debug("New/updated Metadata is stored for %s"%dirname)
                    self._cache.set(dirname.decode("utf-8"), repr(resp))
                    changed = True
            else:
                #get the file metadata using the stored data
                resp = stored
            if resp and not directory:
                #get the file metadata
                items = resp['contents']
                resp = None
                for item in items:
                    if string_path(item['path']) == path:
                        resp = item
                        break;
        return resp, changed

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
        stored = self._cache.get(u"mediaUrl:"+path.decode("utf-8"))
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
            self._cache.set(u"mediaUrl:"+path.decode("utf-8"), repr(resp))
        if resp:
            return resp['url']
        else:
            return '' 
    
    @command()
    def search(self, searchText, path):
        searchResult = self.DropboxAPI.search(path, searchText)
        return searchResult
    
    @command()
    def delete(self, path):
        succes = False
        resp = self.DropboxAPI.file_delete(path)
        if resp and 'is_deleted' in resp:
            succes = resp['is_deleted']
        return succes

    @command()
    def copy(self, path, toPath):
        succes = False
        resp = self.DropboxAPI.file_copy(path, toPath)
        if resp and 'path' in resp:
            succes = ( string_path(resp['path']) == toPath)
        return succes

    @command()
    def move(self, path, toPath):
        succes = False
        resp = self.DropboxAPI.file_move(path, toPath)
        if resp and 'path' in resp:
            succes = ( string_path(resp['path']) == toPath)
        return succes

    @command()
    def createFolder(self, path):
        succes = False
        resp = self.DropboxAPI.file_create_folder(path)
        if resp and 'path' in resp:
            succes = ( string_path(resp['path']) == path)
        return succes

    @command()
    def upload(self, fileName, toPath):
        succes = False
        size = os.stat(fileName).st_size
        if size > 0:
            uploadFile = open(fileName, 'rb')
            uploader = Uploader(self.DropboxAPI, uploadFile, size)
            dialog = xbmcgui.DialogProgress()
            dialog.create(LANGUAGE_STRING(30033), fileName)
            dialog.update( (uploader.offset*100) / uploader.target_length )
            while uploader.offset < uploader.target_length:
                if dialog.iscanceled():
                    log('User canceled the upload!')
                    break
                uploader.uploadNext()
                dialog.update( (uploader.offset*100) / uploader.target_length )
            dialog.close()
            if uploader.offset == uploader.target_length:
                #user didn't cancel
                path = toPath + '/' + os.path.basename(fileName) 
                resp = uploader.finish(path)
                print "resp", resp
                if resp and 'path' in resp:
                    succes = ( string_path(resp['path']) == path)
        else:
            log_error('File size of Upload file <= 0!')
        return succes
        
    def saveThumbnail(self, path, location):
        succes = False
        dirName = os.path.dirname(location)
        # create the data dir if needed
        if not xbmcvfs.exists( dirName ):
            xbmcvfs.mkdirs( dirName )
        try:
            cacheFile = open(location, 'wb') # 'b' option required for windows!
            #download the file
            #jpeg (default) or png. For images that are photos, jpeg should be preferred, while png is better for screenshots and digital art.
            tumbFile = self.DropboxAPI.thumbnail(path, size='large', format='JPEG')
            shutil.copyfileobj(tumbFile, cacheFile)
            cacheFile.close()
            log_debug("Downloaded file to: %s"%location)
            succes = True
        except IOError, e:
            msg = str(e)
            log_error('Failed saving file %s. Error: %s' %(location,msg) )
        except rest.ErrorResponse, e:
            msg = e.user_error_msg or str(e)
            log_error('Failed downloading file %s. Error: %s' %(location,msg))
        return succes

    def saveFile(self, path, location):
        succes = False
        dirName = os.path.dirname(location)
        # create the data dir if needed
        if not xbmcvfs.exists( dirName ):
            xbmcvfs.mkdirs( dirName )
        try:
            cacheFile = open(location, 'wb') # 'b' option required for windows!
            #download the file
            orgFile = self.DropboxAPI.get_file(path)
            shutil.copyfileobj(orgFile, cacheFile)
            cacheFile.close()
            log_debug("Downloaded file to: %s"%location)
            succes = True
        except IOError, e:
            msg = str(e)
            log_error('Failed saving file %s. Error: %s' %(location,msg) )
        except rest.ErrorResponse, e:
            msg = e.user_error_msg or str(e)
            log_error('Failed downloading file %s. Error: %s' %(location,msg))
        return succes

    def getRemoteChanges(self, cursor):
        return None, cursor

class Uploader(client.DropboxClient.ChunkedUploader):
    """
    Use the client.DropboxClient.ChunkedUploader, but create a
    step() function to  
    """
    def __init__( self, client, file_obj, length):
        super(Uploader, self).__init__(client, file_obj, length)
        self.chunk_size = 1*1024*1024 # 1 MB sizes

    def uploadNext(self):
        """Uploads data from this ChunkedUploader's file_obj in chunks.
        When this function is called 1 chunk is uploaded.
        Throws an exception when an error occurs, and can
        be called again to resume the upload.
        """
        next_chunk_size = min(self.chunk_size, self.target_length - self.offset)
        if self.last_block == None:
            self.last_block = self.file_obj.read(next_chunk_size)

        try:
            (self.offset, self.upload_id) = self.client.upload_chunk(StringIO(self.last_block), next_chunk_size, self.offset, self.upload_id)
            self.last_block = None
        except rest.ErrorResponse, e:
            reply = e.body
            if "offset" in reply and reply['offset'] != 0:
                if reply['offset'] > self.offset:
                    self.last_block = None
                    self.offset = reply['offset']
