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
import resources.lib.login as login

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
            ADDON.setSetting('access_token', '')
            ADDON.setSetting('passcode', '')
            ADDON.setSetting('passcodetimeout', '')
            ADDON.setSetting('synchronisation', 'false')
            ADDON.setSetting('syncpath', '')
            ADDON.setSetting('remotepath', '')


    def buildList(self):
        #get the present accounts
        names = os.listdir(self._accounts_dir)
        for name in names:
            self.add_account(name)
        #add the account action items
        sessionId = ADDON.getSetting('session_id').decode("utf-8")
        if sessionId == '':
            #add new account
            self.add_action(LANGUAGE_STRING(30042), 'add')
        else:
            #finish adding account
            self.add_action(LANGUAGE_STRING(30043), 'add')
    
    def show(self):
        xbmcplugin.endOfDirectory(int(sys.argv[1]))

    def add_account(self, name):
        if self._content_type == 'audio':
            iconImage = 'DefaultAddonMusic.png'
        elif self._content_type == 'video':
            iconImage = 'DefaultAddonVideo.png'
        elif self._content_type == 'image':
            iconImage = 'DefaultAddonPicture.png'
        listItem = xbmcgui.ListItem(name, iconImage=iconImage, thumbnailImage=iconImage)
        #Create the url
        url = sys.argv[0]
        url += '?content_type=' + self._content_type
        url += "&module=" + 'browse_folder'
        url +="&account=" + urllib.quote(name)
        #Add a context menu item
        contextMenuItems = []
        contextMenuItems.append( (LANGUAGE_STRING(30044), self.getContextUrl('remove', name) ) )
        listItem.addContextMenuItems(contextMenuItems, replaceItems=True)
        xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=url, listitem=listItem, isFolder=True)

    def add_action(self, name, action):
        iconImage='DefaultAddSource.png'
        listItem = xbmcgui.ListItem(name, iconImage=iconImage, thumbnailImage=iconImage)
        #Create the url
        url = sys.argv[0]
        url += '?content_type=' + self._content_type
        url += "&module=" + 'browse_account'
        url +="&action=" + 'add'
        contextMenuItems = []
        listItem.addContextMenuItems(contextMenuItems, replaceItems=True)
        xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=url, listitem=listItem, isFolder=True)

    def getContextUrl(self, action, account_name):
        url = 'XBMC.RunPlugin(plugin://plugin.dbmc/?'
        url += 'action=%s' %( action )
        url += "&module=" + 'browse_account'
        url += '&account=' + urllib.quote(account_name)
        url += ')'
        return url

def run(params): # This is the entrypoint
    action = params.get('action', '')
    if action == 'add':
        #add an account
        access_token = login.getAccessToken()
        if access_token:
            #save the new account
            account_name = 'Account1'
            client = XBMCDropBoxClient(access_token=access_token)
            account_info = client.getAccountInfo()
            if 'display_name' in account_info:
                account_name = account_info['display_name']
            new_account = AccountSettings(account_name)
            new_account.access_token = access_token
            new_account.save()
            #notify account is added
            dialog = xbmcgui.Dialog()
            dialog.ok(ADDON_NAME, LANGUAGE_STRING(30004), account_name)
        #return to where we were
        xbmcplugin.endOfDirectory(int(sys.argv[1]), succeeded=False)
    elif action == 'remove':
        #remove the selected account
        account_name = urllib.unquote( params.get('account', '') )
        account_settings = login.get_account(account_name) 
        if account_settings:
            dialog = xbmcgui.Dialog()
            #'are you sure' dialog
            if dialog.yesno(ADDON_NAME, LANGUAGE_STRING(30045), account_name ) == True:
                try:
                    account_settings.remove()
                except Exception as exc:
                    log_error("Failed to remove the account: %s" % (str(exc)) )
        else:
            log_error("Failed to remove the account: no account name provided!")
            dialog = xbmcgui.Dialog()
            dialog.ok(ADDON_NAME, LANGUAGE_STRING(30203))
        #return to where we were
        xbmcplugin.endOfDirectory(int(sys.argv[1]), succeeded=False)
    else:
        browser = AccountBrowser(params)
        browser.buildList()
        browser.show()
                            

