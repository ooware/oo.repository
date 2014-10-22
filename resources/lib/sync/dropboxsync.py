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
import xbmcvfs

import time
import threading
import shutil, os
import pickle

from resources.lib.utils import *
from resources.lib.dropboxclient import *
from resources.lib.sync.notifysync import *
from resources.lib.sync.syncaccount import SyncAccount


class DropboxSynchronizer:
    '''
    The DropboxSynchronizer is the XBMC service which runs in the background and
    executes the synchronization of the accounts.
    '''
    
    def __init__( self ):
        self._accounts = []
        self._notified = None

    def run(self):
        # start daemon
        xbmc.sleep(10000) #wait for CommonCache to startup
        # Get available accounts and create them
        self.update_accounts()
        self._notified = NotifySyncServer()
        self._notified.start()
        while (not xbmc.abortRequested):
            #get all notifications
            notification = True
            while notification:
                account_name, notification = self._notified.getNotification()
                if notification:
                    account = None
                    if account_name:
                        #find the account
                        for item in self._accounts:
                            if account_name == item.account_name:
                                account = item
                    if notification == NOTIFY_SYNC_PATH:
                        if account:
                            account.notify_sync_request(None)
                        else:
                            log_error('DropboxSynchronizer: NOTIFY_SYNC_PATH recieved without account!')
                    elif notification == NOTIFY_CHANGED_ACCOUNT:
                        if account:
                            account.notify_changed_settings()
                        else:
                            log_error('DropboxSynchronizer: NOTIFY_CHANGED_ACCOUNT recieved without account!')
                    elif notification == NOTIFY_ADDED_REMOVED_ACCOUNT:
                        self.update_accounts()
                    else:
                        log_error('DropboxSynchronizer: Unknown notification recieved!')
            #Check if sync is needed...
            for item in self._accounts:
                item.check_sync()
            #Sleep for a while. Prevent from checking stuff continuesly 
            xbmc.sleep(1000) #1 secs
        # Service stopped
        #stop any syncing
        for item in self._accounts:
            item.stop_sync()
        #wait until stopped
        for item in self._accounts:
            while not item.sync_stopped():
                xbmc.sleep(100)
        if self._notified:
            self._notified.closeServer()

    def update_accounts(self):
        '''
        Get available accounts and create/delete them
        '''
        new_accounts = []
        dataPath = xbmc.translatePath( ADDON.getAddonInfo('profile') )
        accounts_dir = dataPath + '/accounts'
        if xbmcvfs.exists( accounts_dir ):
            #get the present accounts
            new_accounts = os.listdir(accounts_dir)
        # remove/add accounts
        removed_accounts = []
        existing_accounts = []
        for account in self._accounts:
            if account.account_name in new_accounts:
                existing_accounts.append(account.account_name)
            else:
                removed_accounts.append(account)
        #remove accounts
        for account in removed_accounts:
            log_debug('DropboxSynchronizer: account %s removed' % (account.account_name) )
            account.stop_sync()
            #wait for the sync to stop
            while not account.sync_stopped():
                xbmc.sleep(100)
            account.remove_sync_data()
            self._accounts.remove(account)
            del account
        # Add accounts
        for name in new_accounts:
            if name not in existing_accounts:
                log_debug('DropboxSynchronizer: account %s added' % (name) )
                account = SyncAccount(name)
                account.init()
                self._accounts.append(account)
