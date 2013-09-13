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

import time

from resources.lib.utils import *
from resources.lib.dropboxclient import XBMCDropBoxClient

class DropboxFileBrowser(xbmcgui.WindowXMLDialog):
    """
    Dialog class that let's user select the a folder from Dropbox.
    """
    #FileBrowser IDs
    DIRECTORY_LIST = 450
    HEADING_LABEL = 411
    OK_BUTTON = 413
    CANCEL_BUTTON = 414
    CREATE_FOLDER = 415
    FLIP_IMAGE_HOR = 416
    #ACTION IDs
    ACTION_SELECT_ITEM = 7
    
    _currentPath = ''
    selectedFolder = None

    def __init__(self, *args, **kwargs):
        super(DropboxFileBrowser, self).__init__(*args, **kwargs)
        self.client = XBMCDropBoxClient()

    def onInit(self):
        super(DropboxFileBrowser, self).onInit()
        self.getControl(self.FLIP_IMAGE_HOR).setVisible(False)
        self.getControl(self.HEADING_LABEL).setLabel(LANGUAGE_STRING(30025) + LANGUAGE_STRING(30026))
        self.showFolders('/')

    def showFolders(self, path):
        log_debug('Selecting path: %s'%path)
        listView = self.getControl(self.DIRECTORY_LIST)
        listView.reset()
        self._currentPath = path
        items = self.client.getFolderContents(path)
        listItems = []
        if path != '/':
            backPath = os.path.dirname(path)
            listItem = xbmcgui.ListItem(label='..', label2=backPath, iconImage="DefaultFolderBack.png", thumbnailImage="DefaultFolderBack.png")
            listItems.append(listItem)
        for item in items:
            if item['is_dir'] == True:
                listItem = xbmcgui.ListItem(label=os.path.basename(item['path']), label2=item['path'], iconImage="DefaultFolder.png", thumbnailImage="DefaultFolder.png")
                listItems.append(listItem)
        listView.addItems(listItems)
        
    def onClick(self, controlId):
        if controlId == self.DIRECTORY_LIST:
            #update with new selected path
            newPath = self.getControl(controlId).getSelectedItem().getLabel2()
            self.showFolders(newPath)
        elif controlId == self.OK_BUTTON:
            self.selectedFolder = self._currentPath
            self.close()
        elif controlId == self.CANCEL_BUTTON:
            self.close()

#     def onAction(self, action):
#         if (action.getId() == self.ACTION_SELECT_ITEM):
#             print "Action: %s"%action.getId()
#             controlId = self.getFocusId()
#             if controlId == self.DIRECTORY_LIST:
#                 #update with new selected path
#                 newPath = self.getControl(controlId).getSelectedItem().getLabel2()
#                 self.showFolders(newPath)
#             elif controlId == self.OK_BUTTON:
#                 self.selectedFolder = self._currentPath
#                 self.close()
#             elif controlId == self.CANCEL_BUTTON:
#                 self.close()
#             #self.onClick(controlId)
#         else:
#             super(DropboxFileBrowser, self).onAction(action)
