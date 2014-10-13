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
import shutil
import os

from resources.lib.utils import *
from resources.lib.dropboxclient import XBMCDropBoxClient
from resources.lib.accountsettings import AccountSettings

class AccountBrowser(object):
    '''
    Shows the list of account to the user and implements all the account features:
    - Showing the current accounts
    - Converting old addon settings to new account settings
    - add/remove/rename accounts
    ''' 
        
    def __init__( self, params ):
        self._content_type = params.get('content_type', 'other')
        #check if the accounts directory is present, create otherwise
        dataPath = xbmc.translatePath( ADDON.getAddonInfo('profile') )
        self._accounts_dir = dataPath + '/accounts'
        if not xbmcvfs.exists( self._accounts_dir ):
            xbmcvfs.mkdirs( self._accounts_dir )
        #Check if we need to get previous account settings from old addon settings
        if ADDON.getSetting('access_token').decode("utf-8") != '':
            #Old access_token present so convert old settings!
            log('Converting old account settings and saving it')
            account_name = 'Account1'
            access_token = ADDON.getSetting('access_token').decode("utf-8")
            client = XBMCDropBoxClient(access_token=access_token)
            account_info = client.getAccountInfo()
            if 'display_name' in account_info:
                account_name = account_info['display_name']
            new_account = AccountSettings(account_name)
            new_account.access_token = ADDON.getSetting('access_token').decode("utf-8")
            new_account.passcode = ADDON.getSetting('passcode')
            new_account.passcodetimeout = int(ADDON.getSetting('passcodetimeout'))
            #new_account.session_id = tmp_dict.session_id
            new_account.synchronisation = ('true' == ADDON.getSetting('synchronisation').lower())
            new_account.syncfreq = float( ADDON.getSetting('syncfreq') )
            new_account.syncpath = ADDON.getSetting('syncpath')
            new_account.remotepath = ADDON.getSetting('remotepath')
            new_account.save()
            #Now clear all old settings
#             ADDON.setSetting('access_token', '')
#             ADDON.setSetting('passcode', '')
#             ADDON.setSetting('passcodetimeout', '')
#             ADDON.setSetting('synchronisation', 'false')
#             ADDON.setSetting('syncpath', '')
#             ADDON.setSetting('remotepath', '')


    def buildList(self):
        #get the present accounts
        names = os.listdir(self._accounts_dir)
        for name in names:
            self.add_dir(name, 'browse_folder', self._content_type, account=name)
        #add the account as items
        sessionId = ADDON.getSetting('session_id').decode("utf-8")
        if sessionId == '':
            #add new account
            self.add_dir(LANGUAGE_STRING(30042), 'add_account', self._content_type, iconImage='DefaultAddSource.png')
        else:
            #finish adding account
            self.add_dir(LANGUAGE_STRING(30043), 'add_account', self._content_type, iconImage='DefaultAddSource.png')
    
    def show(self):
        xbmcplugin.endOfDirectory(int(sys.argv[1]))

    def add_dir(self, name, module, content_type, iconImage='', account=''):
        url = sys.argv[0]
        url += '?content_type=' + content_type
        url += "&module=" + module
        if account != '':
            url +="&account=" + urllib.quote(account)
        if iconImage == '':
            if content_type == 'audio':
                iconImage = 'DefaultAddonMusic.png'
            elif content_type == 'video':
                iconImage = 'DefaultAddonVideo.png'
            elif content_type == 'image':
                iconImage = 'DefaultAddonPicture.png'
        listItem = xbmcgui.ListItem(name, iconImage=iconImage, thumbnailImage=iconImage)
        xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=url, listitem=listItem, isFolder=True)


def run(params): # This is the entrypoint
    browser = AccountBrowser(params)
    browser.buildList()
    browser.show()
                            

