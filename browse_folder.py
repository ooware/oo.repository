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

import urllib
import os, uuid

from resources.lib.utils import *
from resources.lib.dropboxclient import XBMCDropBoxClient, FileLoader

MAX_MEDIA_ITEMS_TO_LOAD_ONCE = 15

class FolderBrowser(XBMCDropBoxClient):
    _current_path = ''
    _nrOfMediaItems = 0
    _loadedMediaItems = 0
    _totalItems = 0
    _filterFiles = False
    _loader = None
    _session = ''
        
    def __init__( self, params ):
        super(FolderBrowser, self).__init__()
        #get Settings
        self._filterFiles = ('true' == ADDON.getSetting('filefilter').lower()) 
        #form default url
        log_debug('Argument List: %s' % str(sys.argv))
        self._current_path = urllib.unquote( params.get('path', '') )
        self._nrOfMediaItems = int( params.get('media_items', '%s'%MAX_MEDIA_ITEMS_TO_LOAD_ONCE) )
        self._contentType = params.get('content_type', 'other')
        #Add sorting options
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_TITLE)
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_DATE)
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_FILE)
        #Set/change 'SessionId' to let the other FolderBrowser know that it has to quit... 
        self._session = str( uuid.uuid4() ) #generate unique session id
        self.win = xbmcgui.Window(xbmcgui.getCurrentWindowId())
        self.win.setProperty('SessionId', self._session)
        xbmc.sleep(100)

    def buildList(self):
        resp = self.getMetaData(self._current_path, directory=True)
        if resp != None and 'contents' in resp:
            contents = resp['contents']
            #create and start the thread that will download the files
            self._loader = FileLoader(self.DropboxAPI, self._current_path, contents, self._shadowPath, self._thumbPath)
        else:
            contents = []
        self._totalItems = len(contents)
        #first add all the folders
        for f in contents:
            if f['is_dir']:
                fpath = f['path']
                name = os.path.basename(fpath)
                self.addFolder(name, fpath)
        #Now add the maximum(define) number of files
        for f in contents:
            if not f['is_dir']:
                fpath = f['path']
                name = os.path.basename(fpath)
                self.addFile(name, fpath)
            if self._loadedMediaItems >= self._nrOfMediaItems:
                #don't load more for now
                break;
        #Add a "show more" item, for loading more if required
        if self._loadedMediaItems >= self._nrOfMediaItems:
            media_items = self._loadedMediaItems+MAX_MEDIA_ITEMS_TO_LOAD_ONCE
            url = self.getUrl(self._current_path, media_items=media_items)
            listItem = xbmcgui.ListItem( LANGUAGE_STRING(30010) )
            xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=url, listitem=listItem, isFolder=False, totalItems=self._totalItems)
        
    def show(self):
        xbmcplugin.endOfDirectory(int(sys.argv[1]), cacheToDisc=False)
        if self._loader:
            self._loader.start()
            #now wait for the FileLoader
            #We cannot run the FileLoader standalone (without) this plugin(script)
            # for that we would need to use the xbmc.abortRequested, which becomes
            # True as soon as we exit this plugin(script)
            self._loader.stopWhenFinished = True
            while self._loader.isAlive():
                if self.mustStop():
                    #force the thread to stop
                    self._loader.stop()
                    #Wait for the thread
                    self._loader.join()
                    break
                xbmc.sleep(100)
 
    def mustStop(self):
        '''When xbmc quits or the plugin(visible menu) is changed, stop this thread'''
        #win = xbmcgui.Window(xbmcgui.getCurrentWindowId())
        session = self.win.getProperty('SessionId')
        if xbmc.abortRequested:
            log_debug("xbmc.abortRequested")
            return True
        elif session != self._session:
            log_debug("SessionId changed")
            return True
        else:
            return False

    def addFile(self, name, path):
        url = None
        listItem = None
        meta = self.getMetaData(path)
        #print "meta: ", meta
        mediatype = 'other'
        iconImage = 'DefaultFile.png'
        showItem = False
        if not self._filterFiles:
            showItem = True
        if 'image' in meta['mime_type']:
            mediatype = 'pictures'
            iconImage = 'DefaultImage.png'
            if not showItem and (self._contentType == 'image'):
                showItem = True
        elif 'video' in meta['mime_type']:
            mediatype = 'video'
            iconImage = 'DefaultVideo.png'
            if not showItem and (self._contentType == 'video' or self._contentType == 'image'):
                showItem = True
        elif 'audio' in meta['mime_type']:
            mediatype = 'music'
            iconImage = 'DefaultAudio.png'
            if not showItem and (self._contentType == 'audio'):
                showItem = True
        if showItem:
            listItem = xbmcgui.ListItem(name, iconImage=iconImage)
            if mediatype in ['pictures','video','music']:
                self._loadedMediaItems += 1
                tumb = self._loader.getThumbnail(path)
                if not tumb:
                    tumb = '' 
                listItem.setThumbnailImage(tumb)
                #listItem.setInfo( type=mediatype, infoLabels={ 'Title': name } ) don't for media items, it screws up the 'default' (file)content scanner
                url = self._loader.getFile(path)
                #url = self.getMediaUrl(path)
                self.metadata2ItemInfo(listItem, meta, mediatype)
            else:
                listItem.setInfo( type='pictures', infoLabels={ 'Title': name } )
                self.metadata2ItemInfo(listItem, meta, 'pictures')
                url='No action'
            if listItem:
                xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=url, listitem=listItem, isFolder=False, totalItems=self._totalItems)
    
    def addFolder(self, name, path):
        url=self.getUrl(path)
        listItem = xbmcgui.ListItem(name,iconImage='DefaultFolder.png', thumbnailImage='DefaultFolder.png')
        listItem.setInfo( type='pictures', infoLabels={'Title': name} )
        #no useful metadata of folder
        xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=url, listitem=listItem, isFolder=True, totalItems=self._totalItems)

    def getUrl(self, path, media_items=0):
        url = sys.argv[0]
        url += '?content_type=' + self._contentType
        url += '&module=browse_folder'
        url += '&path=' + urllib.quote(path)
        if media_items != 0:
            url += '&media_items=' + str(media_items)
        return url
        
    def metadata2ItemInfo(self, item, metadata, mediatype):
        # example metadata from Dropbox 
        #'rev': 'a7d0389464b',
        #'thumb_exists': False,
        #'path': '/Music/Backspacer/11 - The End.mp3',
        #'is_dir': False,
        #'client_mtime': 'Sat, 27 Feb 2010 11:55:43 +0000'
        #'icon': 'page_white_sound',
        #'bytes': 4260601,
        #'modified': 'Thu, 28 Jun 2012 17:55:59 +0000',
        #'size': '4.1 MB',
        #'root': 'dropbox',
        #'mime_type': 'audio/mpeg',
        #'revision': 2685
        info = {}
        #added value for picture is only the size. the other data is retrieved from the photo itself...
        if mediatype == 'pictures':
            info['size'] = str(metadata['bytes'])
        # For video and music, nothing interesting...
        # elif mediatype == 'video':
        # elif mediatype == 'music':

        if len(info) > 0: item.setInfo(mediatype, info)
    
    
def run(params): # This is the entrypoint
    browser = FolderBrowser(params)
    browser.buildList()
    browser.show()
