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

import urllib

from resources.lib.utils import *
from resources.lib.dropboxviewer import *
from resources.lib.accountsettings import AccountSettings
import resources.lib.login as login

  
def run(params): # This is the entrypoint
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
        dialog.ok(ADDON_NAME, LANGUAGE_STRING(30004))
        xbmcplugin.endOfDirectory(int(sys.argv[1]), succeeded=True)
        path = sys.argv[0] + sys.argv[2]
        xbmc.executebuiltin('container.update(%s)'%path)
    else:
        xbmcplugin.endOfDirectory(int(sys.argv[1]), succeeded=False)
