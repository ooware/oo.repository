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

from utils import *

from dropbox import client, rest
APP_KEY = 'ehe9o5q5abevvq5'
APP_SECRET = '6mbp7ww9hwzzczd'

def doTokenDialog():
    try:
        from webviewer import webviewer #@UnresolvedImport @UnusedImport
        doNormalTokenDialog()
    except:
        dialog = xbmcgui.Dialog()
        dialog.ok(ADDON, 'Please install XMBC addon : Webviewer', 'This is required for authorizing the Dropbox addon.')
    
def doNormalTokenDialog():
    flow = client.DropboxOAuth2FlowNoRedirect(APP_KEY, APP_SECRET)
    authorize_url = flow.start()
    xbmcplugin.endOfDirectory(int(sys.argv[1]),succeeded=False)
    from webviewer import webviewer #@UnresolvedImport
    autoforms = [
                     {'action':'/login',
                      'autofill': 'login_email=joost.kop@gmail.com,login_password=dropAlfagt1972',
                      'autosubmit': 'true'},
                     {'name':'login-form',
                      'action':'/1/oauth2/authorize' } 
                 ]

    autoClose = {    #'url':'.+authorize',
                    'html':'.(Enter this code into).',
                    'heading':'geen idee',
                    'message':'doen we later'}
    url,html = webviewer.getWebResult(authorize_url,dialog=True,autoForms=autoforms,autoClose=autoClose) #@UnusedVariable
    print 'AUTH RESPONSE URL: ' + url

