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

import time
import shutil, os

from resources.lib.utils import *
from resources.lib.dropboxclient import XBMCDropBoxClient

try:
    import StorageServer
except:
    import storageserverdummy as StorageServer

class DropboxSynchronizer:
    _enabled = False
    _syncPath = ''
    _syncFreq = 0 #minutes
    _newSyncTime = 0
    _client = None
    
    def __init__( self ):
        # get addon settings
        self._get_settings()
        #get storage server
        self._DB = StorageServer.StorageServer(ADDON_NAME+'sync', 168) # (Your plugin name, Cache time in hours)
        #TODO remove +'sync'
        self._clientCursor = self._DB.get('client_cursor')

    def run(self):
        # start daemon
        while (not xbmc.abortRequested):
            if self._enabled and self._client:
                now = time.time()
                if self._newSyncTime < now:
                    #update new sync time
                    self._updateSyncTime()
                    log_debug('Start sync...')
                    self._getRemoteChanges()
                    if not xbmc.abortRequested:
                        self._downloadFiles()
                    log_debug('Finished sync...')
            xbmc.sleep(1000)
        
    def _get_settings( self ):
        self._enabled = ('true' == ADDON.getSetting('synchronisation').lower())
        tempPath = ADDON.getSetting('syncpath').decode("utf-8")
        if tempPath == '' or os.path.normpath(tempPath) == '':
            #get the default path 
            tempPath = xbmc.translatePath( ADDON.getAddonInfo('profile') ) + '/sync/'
        if self._syncPath == '':
            #get initial location
            self._syncPath = tempPath
        if self._syncPath != tempPath:
            if os.listdir(tempPath).empty():
                #move the old sync path to the new one
                xbmc.executebuiltin('Notification(%s,%s,%i)' % (LANGUAGE(30103), tempPath, 7000))
                log('Moving sync location from %s to %s'%(self._syncPath, tempPath))
                shutil.move(self._syncPath, tempPath)
                self._syncPath = tempPath
            else:
                log_error('New sync location is not empty: %s'%(tempPath))
                xbmc.executebuiltin('Notification(%s,%s,%i)' % (LANGUAGE(30104), tempPath, 7000))
                #restore the old location
                ADDON.setSetting('syncpath', self._syncPath)
        tempFreq = float( ADDON.getSetting('syncfreq') )
        self._updateSyncTime(tempFreq)
        #reconnect to Dropbox (in case the token has changed)
        if self._client:
            self._client.disconnect()
        else:
            self._client = XBMCDropBoxClient(autoConnect=False)
        succes, msg = self._client.connect()
        if not succes:
            log_error('DropboxSynchronizer could not connect to dropbox: %s'%(msg))
            self._client = None
        # init the player class (re-init when settings have changed)
        self.monitor = SettingsMonitor(callback=self._get_settings)

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
    
    def _getRemoteChanges(self):
        meta = '' #fake
        while meta and not xbmc.abortRequested:
            #initial sync, get all metadata
            meta, self._clientCursor = self._client.getRemoteChanges(self._clientCursor)
            #store new cursor
            self._DB.set('client_cursor', self._clientCursor)
            #store new data
            self._DB.set(meta['path'], meta)
        
    def _downloadFiles(self):
        return

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
