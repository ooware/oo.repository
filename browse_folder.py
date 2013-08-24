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
import xbmcaddon
import xbmcgui

import urllib
import os, sys

from resources.lib.utils import *
from resources.lib.dropboxclient import XBMCDropBoxClient

MAX_MEDIA_ITEMS_TO_LOAD_ONCE = 15

class FolderBrowser(XBMCDropBoxClient):
    _current_url = ''
    _current_path = ''
    _nrOfMediaItems = 0
    _loadedMediaItems = 0
    _totalItems = 0
    _filterFiles = False
        
    def __init__( self ):
        super(FolderBrowser, self).__init__()
        runAsScript, params = parse_argv()
        #get Settings
        self._filterFiles = ("TRUE" == ADDON.getSetting('filefilter').upper()) 
        #form default url
        self._current_url = sys.argv[0]
        log('Argument List: %s' % str(sys.argv))
        self._current_path = urllib.unquote( params.get('path', '') )
        self._nrOfMediaItems = int( params.get('media_items', '%s'%MAX_MEDIA_ITEMS_TO_LOAD_ONCE) )
        #Add sorting options
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_TITLE)
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_DATE)
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_FILE)

    def buildList(self):
        resp = self.getMetaData(self._current_path, directory=True)
        if resp != None and 'contents' in resp:
            contents = resp['contents']
        else:
            contents = []
        self._totalItems = len(contents)
        #first add all the folders
        for f in contents:
            if f['is_dir']:
                fpath = f['path']
                name = os.path.basename(fpath)
                self.addFolder(name, fpath)
        #Now add the maximum number of defined files
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
            url=self._current_url+'?path=%s&media_items=%s'%( urllib.quote(self._current_path), (media_items) )
            listItem = xbmcgui.ListItem( LANGUAGE_STRING(30010) )
            xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=url, listitem=listItem, isFolder=False, totalItems=self._totalItems)
        
    def show(self):
        xbmcplugin.endOfDirectory(int(sys.argv[1]))
 
    def addFile(self, name, path):
        url = None
        listItem = None
        meta = self.getMetaData(path)
        #print "meta: ", meta
        type = 'other'
        if 'image' in meta['mime_type']:
            type = 'pictures'
        elif 'video' in meta['mime_type']:
            type = 'video'
        elif 'audio' in meta['mime_type']:
            type = 'music'
        if type in ['pictures','video','music']:
            listItem = xbmcgui.ListItem(name)
            self._loadedMediaItems += 1
            url = self.getMediaUrl(path)
            self.metadata2ItemInfo(listItem, meta, type)
        elif not self._filterFiles:
            listItem = xbmcgui.ListItem(name)
            url='No action'#self._current_url+'?path='+urllib.quote(path)
        if listItem:
            xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=url, listitem=listItem, isFolder=False, totalItems=self._totalItems)
    
    def addFolder(self, name, path):
        url=self._current_url+'?path='+urllib.quote(path)
        listItem = xbmcgui.ListItem(name)
        #no useful metadata of folder
        xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=url, listitem=listItem, isFolder=True, totalItems=self._totalItems)

    def metadata2ItemInfo(self, item, metadata, mediatype):
        # metadata item : ListItem.property
        convertTable = {#'path':'path',
                        #'modified':'date',
                        #'client_mtime':'date', #prefered date
                        'bytes':'size'}
        #added value for picture is only the size. the other data is retrieved from the photo itself...
        info = {}
        for key in convertTable:
            if key in metadata:
                info[convertTable[key]] = str(metadata[key])
        if len(info) > 0: item.setInfo(mediatype, info)
    
    

if ( __name__ == "__main__" ):
    runAsScript, params = parse_argv()
    if not runAsScript:
        if ADDON.getSetting('access_token').decode("utf-8") == '':
            import resources.lib.login as login
            dialog = xbmcgui.Dialog()
            dialog.ok(ADDON_NAME, LANGUAGE_STRING(30002), LANGUAGE_STRING(30003) )
            xbmcplugin.endOfDirectory(int(sys.argv[1]),succeeded=False)
            login.doTokenDialog()
            #ADDON.openSettings()
        elif ADDON.getSetting('access_token').decode("utf-8") != '':
            if int(sys.argv[1]) < 0:
                #handle action of a file (or a "Show me more..." item)
                #path = urllib.unquote( params.get('path', '') )
                media_items = params.get('media_items', '')
                if media_items != '':
                    #Loading more media items requested...
                    path = sys.argv[0] + sys.argv[2]
                    xbmc.executebuiltin('container.update(%s, replace)'%path)
            else:
                browser = FolderBrowser()
                browser.buildList()
                browser.show()
        else:
            xbmcplugin.endOfDirectory(int(sys.argv[1]), succeeded=False)
    else: # run as script
        action = params.get('action', '')
        if action == 'login':
            import resources.lib.login as login
            login.doTokenDialog()
        elif action == 'clear_token':
            ADDON.setSetting('access_token', '')
        
