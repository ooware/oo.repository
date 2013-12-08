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

import xbmcplugin
import xbmcgui
import xbmcvfs

import time, datetime
import threading
import shutil, os
from stat import *

from resources.lib.utils import *
from resources.lib.dropboxclient import *
from resources.lib.notifysync import *

try:
    import StorageServer
except:
    import storageserverdummy as StorageServer

class DropboxSynchronizer:
    DB_TABLE = 'remote_data'
    DB_CURSOR = 'client_cursor'
    DB_DATA = 'client_data'
    
    def __init__( self ):
        self._enabled = False
        self._syncPath = ''
        self._syncFreq = 0 #minutes
        self._newSyncTime = 0
        self._client = None
        self._root = None
        self._remoteSyncPath = '' #DROPBOX_SEP
        self._notified = None
        self._syncSemaphore = threading.Semaphore()
        #get storage server
        self._DB = StorageServer.StorageServer(self.DB_TABLE, 8760) # 1 year! (Your plugin name, Cache time in hours)

    def run(self):
        # start daemon
        xbmc.sleep(10000) #wait for CommonCache to startup
        #self._DB.delete('%')
        # get addon settings
        self._get_settings()
        while (not xbmc.abortRequested):
            if self._enabled:
                if not self._notified:
                    self._notified = NotifySyncServer()
                    self._notified.start()
                if self._getClient():
                    now = time.time()
                    updates = self._notified.getNotification()
                    syncNow = False
                    if self._newSyncTime < now:
                        syncNow = True
                        #update new sync time
                        self._updateSyncTime()
                    elif len(updates) > 0:
                        syncNow = True
                    if syncNow:
                        self._syncSemaphore.acquire()
                        log_debug('Start sync...')
                        self._getRemoteChanges()
                        if not xbmc.abortRequested:
                            self._synchronize()
                        self._syncSemaphore.release()
                        if not xbmc.abortRequested:
                            log_debug('Finished sync...')
                        else:
                            log('DropboxSynchronizer: Sync aborted...')
                    else:
                        xbmc.sleep(1000) #1 secs
                else:
                    #try again after 5 secs
                    xbmc.sleep(5000)
            else:
                xbmc.sleep(1000) #1 secs
        if self._notified:
            self._notified.closeServer()

    def _get_settings( self ):
        if not self._syncSemaphore.acquire(False):
            log_error('Can\'t change settings while synchronizing!')
            dialog = xbmcgui.Dialog()
            dialog.ok(ADDON_NAME, LANGUAGE_STRING(30110))
            return
        
        enable = ('true' == ADDON.getSetting('synchronisation').lower())
        tempPath = ADDON.getSetting('syncpath')
        tempRemotePath = ADDON.getSetting('remotepath')
        tempFreq = float( ADDON.getSetting('syncfreq') )
        #Enable?
        if enable and (tempPath == '' or tempRemotePath == ''):
            enable = False
            ADDON.setSetting('synchronisation', 'false')
            log_error('Can\'t enable synchronization: syncpath or remotepath not set!')
            dialog = xbmcgui.Dialog()
            dialog.ok(ADDON_NAME, LANGUAGE_STRING(30111))
        self._enabled = enable
        if self._syncPath == '':
            #get initial location
            self._syncPath = tempPath
        #Sync path changed?
        if self._syncPath != tempPath:
            if len(os.listdir(tempPath)) == 0:
                #move the old sync path to the new one
                log('Moving sync location from %s to %s'%(self._syncPath, tempPath))
                names = os.listdir(self._syncPath)
                for name in names:
                    srcname = os.path.join(self._syncPath, name)
                    shutil.move(srcname, tempPath)
                self._syncPath = tempPath
                if self._root:
                    self._root.updateLocalPath(self._syncPath)
                log('Move finished')
                xbmc.executebuiltin('Notification(%s,%s,%i)' % (LANGUAGE_STRING(30103), tempPath, 7000))
            else:
                log_error('New sync location is not empty: %s'%(tempPath))
                dialog = xbmcgui.Dialog()
                dialog.ok(ADDON_NAME, LANGUAGE_STRING(30104), tempPath)
                #restore the old location
                ADDON.setSetting('syncpath', self._syncPath)
        if self._remoteSyncPath == '':
            #get initial location
            self._remoteSyncPath = tempRemotePath
        #remote path changed?
        if tempRemotePath != self._remoteSyncPath:
            self._remoteSyncPath = tempRemotePath
            log('Changed remote path to %s'%(self._remoteSyncPath))
            if self._root:
                #restart the synchronization 
                #remove all the files in current syncPath
                if len(os.listdir(self._syncPath)) > 0:
                    shutil.rmtree(self._syncPath)
                #reset the complete data on client side
                self._DB.delete('%') #delete all
                del self._root
                self._root = None
                #Start sync immediately
                self._newSyncTime = time.time()
        #Time interval changed?
        self._updateSyncTime(tempFreq)
        #reconnect to Dropbox (in case the token has changed)
        self._getClient(reconnect=True)
        if self._enabled and not self._root:
            log('Enabled synchronization')
            self._setupSyncRoot()
        elif not self._enabled and self._root:
            log('Disabled synchronization')
            self._notified.closeServer()
            del self._notified
            self._notified = None
            del self._root
            self._root = None
        # re-init when settings have changed
        self.monitor = SettingsMonitor(callback=self._get_settings)
        self._syncSemaphore.release()

    def _getClient(self, reconnect=False):
        if reconnect and self._client:
            self._client.disconnect()
            self._client = None
        if not self._client:
            self._client = XBMCDropBoxClient(autoConnect=False)
            succes, msg = self._client.connect()
            if not succes:
                log_error('DropboxSynchronizer could not connect to dropbox: %s'%(msg))
                self._client = None
            #update changed client to the root syncfolder
            if self._root:
                self._root.setClient(self._client)
        return self._client
        
    def _updateSyncTime(self, newFreq = None):
        if newFreq and self._syncFreq == 0:
            #trigger initial sync after startup
            self._newSyncTime = time.time()
            self._syncFreq = newFreq
        else:
            update = False
            if newFreq == None:
                update = True
            elif self._syncFreq != newFreq:
                self._syncFreq = newFreq
                update = True
            if update:
                freqSecs = self._syncFreq * 60
                now = time.time()
                self._newSyncTime = float(freqSecs * round(float(now)/freqSecs))
                if self._newSyncTime < now:
                    self._newSyncTime += freqSecs
                log_debug('New sync time: %s'%( time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.localtime(self._newSyncTime) ) ) )
    
    def _setupSyncRoot(self):
        self._root = SyncFolder(self._remoteSyncPath, self._client, self._syncPath, self._remoteSyncPath)
        #Update items which are in the cache
        clientCursor = self._DB.get(self.DB_CURSOR)
        if clientCursor != '':
            clientCursor = eval(clientCursor)
            log_debug('Setup SyncRoot with stored remote data')
            remoteData = self._DB.get(self.DB_DATA)
            if remoteData != '':
                remoteData = eval(remoteData)
                for path, meta in remoteData.iteritems():
                    if path.find(self._remoteSyncPath) == 0:
                        self._root.setItemInfo(path, meta)
            else:
                log_error('Remote cursor present, but no remote data!')
    
    def _getRemoteChanges(self):
        hasMore = True
        clientCursor = self._DB.get(self.DB_CURSOR)
        initalSync = False
        if clientCursor != '':
            clientCursor = eval(clientCursor)
            log_debug('Using stored remote cursor')
        else:
            initalSync = True
            log('Starting first sync...')
        while hasMore and not xbmc.abortRequested:
            #Sync, get all metadata
            items, clientCursor, reset, hasMore = self._client.getRemoteChanges(clientCursor)
            if reset:
                #reset the complete data on client side
                log('Reset requested from remote server...')
                self._DB.delete('%') #delete all
                del self._root
                self._root = SyncFolder(self._remoteSyncPath, self._client, self._syncPath, self._remoteSyncPath)
                initalSync = True
            #prepare item list
            for path, meta in items.iteritems():
                if not initalSync:
                    log_debug('New item info received for %s'%(path) )
                if path.find(self._remoteSyncPath) == 0:
                    self._root.updateRemoteInfo(path, meta)
            if len(items) > 0:
                #store the new data
                data = repr(self._root.getItemsInfo())
                log_debug('Storing items info')
                self._DB.set(self.DB_DATA, data)
            #store new cursor
            log_debug('Storing remote cursor')
            self._DB.set(self.DB_CURSOR, repr(clientCursor))

    def _synchronize(self):
        #progress = DropboxBackgroundProgress("DialogExtendedProgressBar.xml", os.getcwd())
        #progress.setHeading(LANGUAGE_STRING(30035))
        #Get the items to sync
        syncDirs, syncItems = self._root.getItems2Sync()
        #alsways first sync(create) dirs, so that they will have the correct time stamps
        for dir in syncDirs:
            dir.sync()
        itemsTotal = len(syncItems)
        if itemsTotal > 0:
            itemNr = 0
            #progress = DropboxBackgroundProgress("DialogExtendedProgressBar.xml", os.getcwd())
            #progress.setHeading(LANGUAGE_STRING(30035))
            #progress.show()
            for item in syncItems:
                if not xbmc.abortRequested:
                    #progress.update(itemNr, itemsTotal)
                    item.sync()
                    itemNr += 1
                else:
                    break #exit for loop
            #progress.update(itemNr, itemsTotal)
            #store the new data
            data = repr(self._root.getItemsInfo())
            log_debug('Storing items info')
            self._DB.set(self.DB_DATA, data)
            log('Number of items synchronized: %s' % (itemNr) )
            xbmc.executebuiltin('Notification(%s,%s%s,%i)' % (LANGUAGE_STRING(30106), LANGUAGE_STRING(30107), itemNr, 7000))

class SyncObject(object):
    OBJECT_IN_SYNC = 0
    OBJECT_2_DOWNLOAD = 1
    OBJECT_2_UPLOAD = 2
    OBJECT_2_REMOVE = 3
    OBJECT_ADD_CHILD = 4
    OBJECT_REMOVED = 5
    
    def __init__(self, path, client, syncPath, syncRoot):
        #note: path is case-insensitive, meta['path'] is case-sensitive
        self.path = path #case-insensitive path
        self.isDir = False
        self._Path = None #case-sensitive path
        self._syncPath = syncPath
        self._syncRoot = syncRoot
        self._client = client
        self._localPath = None
        self._remotePresent = True
        self._remoteTimeStamp = 0
        self._remoteClientModifiedTime = 0
        self._newRemoteTimeStamp = 0
        self._localTimeStamp = 0

    def setItemInfo(self, meta):
        log_debug('Set stored metaData: %s'%self.path)
        if meta:
            if self.path != string_path(meta['path']):
                log_error('Stored metaData path(%s) not equal to path %s'%(meta['path'], self.path) )
            if 'present' in meta:
                self._remotePresent = meta['present']
            if 'local_mtime' in meta:
                self._localTimeStamp = meta['local_mtime']
            if 'remote_mtime' in meta:
                self._remoteTimeStamp = meta['remote_mtime']
                self._newRemoteTimeStamp = self._remoteTimeStamp
            if 'client_mtime' in meta:
                self._remoteClientModifiedTime = meta['client_mtime']
            if 'Path' in meta:
                self._Path = string_path(meta['Path'])
        else:
            self._remotePresent = False
        
    def getItemInfo(self):
        meta = {}
        meta['path'] = self.path
        meta['Path'] = self._Path
        meta['is_dir'] = self.isDir
        meta['present'] = self._remotePresent
        meta['local_mtime'] = self._localTimeStamp
        meta['remote_mtime'] = self._remoteTimeStamp
        meta['client_mtime'] = self._remoteClientModifiedTime
        return meta

    def updateRemoteInfo(self, meta):
        log_debug('Updated remote metaData: %s'%self.path)
        if meta:
            self._Path = string_path(meta['path']) # get the case-sensitive path!
            self.updateLocalPath(self._syncPath) # update with case-sensitive path!
            #convert to local time 'Thu, 28 Jun 2012 17:55:59 +0000',
            time_struct = time.strptime(meta['modified'], '%a, %d %b %Y %H:%M:%S +0000')
            self._newRemoteTimeStamp = utc2local( time.mktime(time_struct) )
            if 'client_mtime' in meta:
                time_struct = time.strptime(meta['client_mtime'], '%a, %d %b %Y %H:%M:%S +0000')
                self._remoteClientModifiedTime = utc2local( time.mktime(time_struct) )
        else:
            log_debug('Item removed on remote: %s'%self.path)
            self._remotePresent = False
            #keep remote/local time to compair lateron         
            #self._remoteTimeStamp = 0
            #self._localTimeStamp = 0
            
    def updateTimeStamp(self):
        #local modified time = client_mtime
        st = os.stat(self.getLocalPath())
        atime = st[ST_ATIME] #access time
        mtime = st[ST_MTIME] #modification time
        #modify the file timestamp
        os.utime(self.getLocalPath(), (atime, int(self._remoteClientModifiedTime) ))
        #read back and store the local timestamp value
        # this is used for comparison to the remote modified time
        st = os.stat(self.getLocalPath())
        self._localTimeStamp = st[ST_MTIME]
        self._remoteTimeStamp = self._newRemoteTimeStamp
        
    def getLocalPath(self):
        if not self._localPath:
            self.updateLocalPath(self._syncPath)
        return self._localPath 

    def updateLocalPath(self, syncPath):
        #Note: self.path should be the case-sensitive path by now!
        #localpath consists of syncPath + (self.path - syncRoot)
        self._syncPath = syncPath
        if self._Path:
            itemPath = self._Path
        else:
            itemPath = string_path(self.path) #use case-insensitive one...
        #decode the _localPath to 'utf-8'
        # in windows os.stat() only works with unicode...
        self._localPath = getLocalSyncPath(self._syncPath, self._syncRoot, itemPath).decode('utf-8')

class SyncFile(SyncObject):
    
    def __init__( self, path, client, syncPath, syncRoot):
        log_debug('SyncFile created: %s'%path)
        super(SyncFile, self).__init__(path, client, syncPath, syncRoot)

    def inSync(self):
        localPresent = xbmcvfs.exists(self.getLocalPath())
        localTimeStamp = 0
        if localPresent:
            st = os.stat(self.getLocalPath())
            localTimeStamp = st[ST_MTIME]
        #File present
        if not localPresent and self._remotePresent:
            return self.OBJECT_2_DOWNLOAD
        if not self._remotePresent:
            if localPresent:
                return self.OBJECT_2_REMOVE
#                 #Check if local file is a newer one than the old remote file
#                 # if so, use the new local file...
#                 if localTimeStamp > self._localTimeStamp:
#                     return self.OBJECT_2_UPLOAD
#                 else:
#                     return self.OBJECT_2_REMOVE
            else:
                #File is completely removed, so can be removed from memory as well
                return self.OBJECT_REMOVED
        #compair time stamps
        if self._newRemoteTimeStamp > self._remoteTimeStamp:
            return self.OBJECT_2_DOWNLOAD
#                 #Check if local file is a newer one than the new remote file
#                 # if so, use the new local file...
#                 if localTimeStamp > self._localTimeStamp and localTimeStamp > self._remoteTimeStamp:
#                     return self.OBJECT_2_UPLOAD
#                 else:
#                     return self.OBJECT_2_DOWNLOAD
#         if localTimeStamp > self._localTimeStamp:
#             return self.OBJECT_2_UPLOAD
        return self.OBJECT_IN_SYNC
        
    def sync(self):
        fileStatus = self.inSync()
        if fileStatus == self.OBJECT_2_DOWNLOAD:
            log_debug('Download file: %s'%self.path)
            self._client.saveFile(self.path, self.getLocalPath())
            self.updateTimeStamp()
        elif fileStatus == self.OBJECT_2_UPLOAD:
            log_debug('Upload file: %s'%self.path)
            self._client.upload(self.getLocalPath(), self.path)
            st = os.stat(self.getLocalPath())
            self._localTimeStamp = st[ST_MTIME] 
        elif fileStatus == self.OBJECT_2_REMOVE:
            log_debug('Removing file: %s'%self.path)
            os.remove(self.getLocalPath())
        elif fileStatus == self.OBJECT_IN_SYNC or fileStatus == self.OBJECT_REMOVED:
            pass
        else:
            log_error('Unknown file status(%s) for: %s!'%(fileStatus, self.path))
    
    def setItemInfo(self, path, meta):
        if path == self.path:
            super(SyncFile, self).setItemInfo(meta)
        else:
            log_error('setItemInfo() item with wrong path: %s should be: %s'%(path, self.path))

    def updateRemoteInfo(self, path, meta):
        if path == self.path:
            super(SyncFile, self).updateRemoteInfo(meta)
        else:
            log_error('updateRemoteInfo() item with wrong path: %s should be: %s'%(path, self.path))

    def setClient(self, client):
        self._client = client

class SyncFolder(SyncObject):

    def __init__( self, path, client, syncPath, syncRoot):
        log_debug('SyncFolder created: %s'%path)
        super(SyncFolder, self).__init__(path, client, syncPath, syncRoot)
        self.isDir = True
        self._children = {}

    def setItemInfo(self, path, meta):
        if path == self.path:
            super(SyncFolder, self).setItemInfo(meta)
        elif path.find(self.path) != 0:
            log_error('setItemInfo() Item(%s) isn\'t part of the remote sync path(%s)'%(path, self.path))            
            return
        else:
            child = self.getItem(path, meta)
            child.setItemInfo(path, meta)

    def updateRemoteInfo(self, path, meta):
        if path == self.path:
            super(SyncFolder, self).updateRemoteInfo(meta)
        elif path.find(self.path) != 0:
            log_error('updateRemoteInfo() Item(%s) isn\'t part of the remote sync path(%s)'%(path, self.path))            
            return
        else:
            child = self.getItem(path, meta)
            child.updateRemoteInfo(path, meta)
            
    def getItemsInfo(self):
        metaDataList = {}
        metaDataList[self.path] = self.getItemInfo()
        for path, child in self._children.iteritems():
            if child.isDir:
                childMetaData = child.getItemsInfo()
                metaDataList.update( childMetaData )
            else:
                metaDataList[path] = child.getItemInfo()
        return metaDataList
        
    def getItem(self, path, meta):
        #strip the child name
        #exclude it's own path from the search for the first seperator
        end = path.find(DROPBOX_SEP, len(self.path)+1)
        isDir = True
        if end > 0:
            #it wasn't my own child so create the new folder and search/update that one
            childPath = path[:end]
        elif meta and meta['is_dir']:
            #it is my child and it is a folder
            childPath = path
        else:
            #it is my child and it is a file
            childPath = path
            isDir = False
        if not(childPath in self._children):
            #create the child
            if isDir:
                child = SyncFolder(childPath, self._client, self._syncPath, self._syncRoot)
            else:
                child = SyncFile(childPath, self._client, self._syncPath, self._syncRoot)
            #add the new created child to the childern's list
            self._children[childPath] = child
        return self._children[childPath]

    def inSync(self):
        localPresent = xbmcvfs.exists(self.getLocalPath())
        #File present
        if not localPresent and self._remotePresent:
            return self.OBJECT_2_DOWNLOAD
        if not self._remotePresent:
            if localPresent:
                #TODO check if local file is a newer one than the old remote file
                # if so, use the new local file...
                return self.OBJECT_2_REMOVE
            else:
                #File is completely removed, so can be removed from memory as well
                return self.OBJECT_REMOVED
        #TODO Check if files are present on disk but not in it's 
        # _childern's list
        #return self.OBJECT_ADD_CHILD
        return self.OBJECT_IN_SYNC
        
    def sync(self):
        folderStatus = self.inSync() 
        if folderStatus == self.OBJECT_2_DOWNLOAD:
            log_debug('Create folder: %s'%self.path)
            xbmcvfs.mkdirs( self.getLocalPath() )
            self.updateTimeStamp()
        elif folderStatus == self.OBJECT_2_UPLOAD:
            log_error('Can\'t upload folder: %s'%self.path)
            #TODO Add files if new files found local
            #TODO: modify timestamp of dir...
        elif folderStatus == self.OBJECT_2_REMOVE:
            log_debug('Remove folder: %s'%self.path)
            shutil.rmtree(self.getLocalPath())
        elif folderStatus == self.OBJECT_ADD_CHILD:
            #TODO
            pass
        elif folderStatus == self.OBJECT_IN_SYNC:
            pass
        else:
            log_error('Unknown folder status(%s) for : %s!'%(folderStatus, self.path))
            
    def getItems2Sync(self):
        dirs2Sync = []
        items2Sync = []
        removeList = {}
        for path, child in self._children.iteritems():
            if child.isDir:
                newDirs, newItems = child.getItems2Sync()
                dirs2Sync += newDirs
                items2Sync += newItems
            childSyncStatus = child.inSync()
            if childSyncStatus == child.OBJECT_REMOVED:
                #Remove child from list
                removeList[path] = child
            elif childSyncStatus != child.OBJECT_IN_SYNC:
                if child.isDir:
                    dirs2Sync.append(child)
                else:
                    items2Sync.append(child)
        #Remove child's from list (this we can do now)
        for path in removeList:
            child = self._children.pop(path) 
            del child
        return dirs2Sync, items2Sync
    
    def setClient(self, client):
        self._client = client
        for child in self._children.itervalues():
            child.setClient(client)

    def updateLocalPath(self, syncPath):
        super(SyncFolder, self).updateLocalPath(syncPath)
        for path, child in self._children.iteritems():
            child.updateLocalPath(syncPath)


class SettingsMonitor(xbmc.Monitor):
    def __init__( self, callback ):
        xbmc.Monitor.__init__( self )
        self.callback = callback

    def onSettingsChanged( self ):
        log_debug('SettingsMonitor: onSettingsChanged()')
        # sleep before retrieving the new settings
        xbmc.sleep(500)
        self.callback()
 
if ( __name__ == "__main__" ):
    log_debug('sync_dropbox.py: Argument List: %s' % str(sys.argv))
    log('DropboxSynchronizer started')
    sync = DropboxSynchronizer()
    sync.run()
    log('DropboxSynchronizer ended')
