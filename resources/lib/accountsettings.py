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

import xbmcvfs
import shutil
import os
import pickle

from resources.lib.utils import *

class AccountSettings(object):
    '''
    Class which loads and saves all the account settings,
    for easy access to the account settings
    '''
    
    def __init__(self, account_name):
        self.account_name = account_name
        self.access_token = ''
        self.passcode = ''
        self.passcodetimeout = 30
        self.session_id = ''
        self.synchronisation = False
        self.syncfreq = 5
        self.syncpath = ''
        self.remotepath = ''
        dataPath = xbmc.translatePath( ADDON.getAddonInfo('profile') )
        self.account_dir = os.path.normpath(dataPath + '/accounts/' + self.account_name)
        #read from location if present
        if xbmcvfs.exists( self.account_dir ):
            self.load()
            #Don't use the stored account_dir 
            self.account_dir = os.path.normpath(dataPath + '/accounts/' + self.account_name)
        
    def load(self):
        log_debug('Loading account settings: %s' % (self.account_name) )
        settings_file = os.path.normpath(self.account_dir + '/settings')
        try:
            with open(settings_file, 'r') as file_obj:
                tmp_dict = pickle.load(file_obj)
        except Exception as exc:
            log_error('Failed to load the settings: %s' % (str(exc)) )
        else:
            self.__dict__.update(tmp_dict)
        
    def save(self):
        log_debug('Save account settings: %s' % (self.account_name) )
        #check if the account directory is present, create otherwise
        if not xbmcvfs.exists( self.account_dir ):
            xbmcvfs.mkdirs( self.account_dir )
        #Save...
        settings_file = os.path.normpath(self.account_dir + '/settings')
        try:
            with open(settings_file, 'w') as file_obj:
                pickle.dump(self.__dict__, file_obj)
        except Exception as exc:
            log_error('Failed saving the settings: %s' % (str(exc)) )
    
    def remove(self):
        log_debug('Remove account folder: %s' % (self.account_dir) )
        shutil.rmtree( self.account_dir )
        #remove cache folder
        shutil.rmtree( get_cache_path(self.account_name) )
        #remove synced data is done in the DropboxSynchronizer!

