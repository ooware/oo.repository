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
from resources.lib.dropboxfilebrowser import DropboxFileBrowser

def addDir(name, module, contentType, iconImage=''):
    url = sys.argv[0]
    url += '?content_type=' + contentType
    url += "&module=" + module
    if iconImage == '':
        if contentType == 'audio':
            iconImage = 'DefaultAddonMusic.png'
        elif contentType == 'video':
            iconImage = 'DefaultAddonVideo.png'
        elif contentType == 'image':
            iconImage = 'DefaultAddonPicture.png'
    listItem = xbmcgui.ListItem(name, iconImage=iconImage, thumbnailImage=iconImage)
    xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=url, listitem=listItem, isFolder=True)

 
if ( __name__ == "__main__" ):
    log_debug('Argument List: %s' % str(sys.argv))
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
                if 'module' in params: # plugin (module) to run
                    path = sys.argv[0] + sys.argv[2]
                    xbmc.executebuiltin('container.update(%s)'%path)
                elif 'media_items' in params:
                    #Loading more media items requested...
                    path = sys.argv[0] + sys.argv[2]
                    xbmc.executebuiltin('container.update(%s, replace)'%path)
                    #xbmc.executebuiltin('container.update(%s)'%path)
            else:
                unlocked = True
                win = xbmcgui.Window(xbmcgui.getCurrentWindowId())
                if ('true' == ADDON.getSetting('passcodelock').lower()):
                    unlockTimeout = float( ADDON.getSetting('passcodetimeout') ) * 60 # to minutes
                    try:
                        unlockedTime = float( win.getProperty('Unlocked') )
                    except ValueError:
                        unlockedTime = 0.0
                    #unlocked = True when timeout not expired
                    unlocked = (time.time() < (unlockedTime + unlockTimeout) )
                    if not unlocked:
                        log('Unlock with passcode required...')
                        keyboard = xbmc.Keyboard('', LANGUAGE_STRING(30013))
                        keyboard.setHiddenInput(True)
                        keyboard.doModal()
                        if keyboard.isConfirmed() and keyboard.getText() == ADDON.getSetting('passcode'):
                            unlocked = True
                        else:
                            #Wrong passcode
                            dialog = xbmcgui.Dialog()
                            dialog.ok(ADDON_NAME, LANGUAGE_STRING(30014) )
                if unlocked:
                    #update the unlock time
                    win.setProperty('Unlocked', '%s'%time.time() )
                    if 'module' in params: # Module chosen, load and execute module
                        module = params['module']
                        __import__(module)
                        current_module = sys.modules[module]
                        current_module.run(params)
                    else: # No module chosen
                        if False: #list modules, creates an extra menu for dropbox addon, but for now, do not use...
                            contentType = params.get('content_type', 'all')
                            addDir(LANGUAGE_STRING(30016), 'browse_folder', contentType)
                            addDir(LANGUAGE_STRING(30017), 'search_dropbox', contentType, iconImage='DefaultAddonProgram.png')
                            # Add extra modules here, using addDir(name, module)
                            xbmcplugin.endOfDirectory(int(sys.argv[1]))
                        else:
                            #Run the browse_folder module
                            module = 'browse_folder'
                            params['module'] = module
                            __import__(module)
                            current_module = sys.modules[module]
                            current_module.run(params)
                else:
                    xbmcplugin.endOfDirectory(int(sys.argv[1]), succeeded=False)
        else:
            xbmcplugin.endOfDirectory(int(sys.argv[1]), succeeded=False)
    else: # run as script
        action = params.get('action', '')
        if action == 'login':
            import resources.lib.login as login
            login.doTokenDialog()
        elif action == 'clear_token':
            ADDON.setSetting('access_token', '')
        elif action == 'delete':
            if 'path' in params:
                path = urllib.unquote( params['path'] )
                dialog = xbmcgui.Dialog()
                if dialog.yesno(ADDON_NAME, LANGUAGE_STRING(30023), path ) == True:
                    client = XBMCDropBoxClient()
                    success = client.delete(path)
                    if success:
                        log('File removed: %s' % path)
                    else:
                        log_error('File removed Failed: %s' % path)
                    xbmc.executebuiltin('container.Refresh()')
        elif action == 'copy':
            if 'path' in params:
                path = urllib.unquote( params['path'] )
                dialog = DropboxFileBrowser("FileBrowser.xml", os.getcwd())
                dialog.setHeading(LANGUAGE_STRING(30025) + LANGUAGE_STRING(30026))
                dialog.doModal()
                if dialog.selectedFolder:
                    #dropbox path -> don't use os.path.join()!
                    toPath = dialog.selectedFolder
                    if dialog.selectedFolder[-1:] != '/': toPath += '/'
                    toPath += os.path.basename(path)
                    client = XBMCDropBoxClient()
                    success = client.copy(path, toPath)
                    if success:
                        log('File copied: %s to %s' % (path, toPath) ) 
                    else:
                        log_error('File copy Failed: %s to %s' % (path, toPath) )
                del dialog
        elif action == 'move':
            if 'path' in params:
                path = urllib.unquote( params['path'] )
                dialog = DropboxFileBrowser("FileBrowser.xml", os.getcwd())
                dialog.setHeading(LANGUAGE_STRING(30025) + LANGUAGE_STRING(30028))
                dialog.doModal()
                if dialog.selectedFolder:
                    #dropbox path -> don't use os.path.join()!
                    toPath = dialog.selectedFolder
                    if dialog.selectedFolder[-1:] != '/': toPath += '/'
                    toPath += os.path.basename(path)
                    client = XBMCDropBoxClient()
                    success = client.move(path, toPath)
                    if success:
                        log('File moved: from %s to %s' % (path, toPath) ) 
                        xbmc.executebuiltin('container.Refresh()')
                    else:
                        log_error('File move Failed: from %s to %s' % (path, toPath) )
                del dialog
        elif action == 'create_folder':
            if 'path' in params:
                path = urllib.unquote( params['path'] )
                keyboard = xbmc.Keyboard('', LANGUAGE_STRING(30030))
                keyboard.doModal()
                if keyboard.isConfirmed():
                    newFolder = path
                    if path[-1:] != '/': newFolder += '/'
                    newFolder += keyboard.getText()
                    client = XBMCDropBoxClient()
                    success = client.createFolder(newFolder)
                    if success:
                        log('New folder created: %s' % newFolder)
                        xbmc.executebuiltin('container.Refresh()')
                    else:
                        log_error('Creating new folder Failed: %s' % newFolder)
        elif action == 'upload':
            if 'to_path' in params:
                toPath = urllib.unquote( params['to_path'] )
                dialog = xbmcgui.Dialog()
                fileName = dialog.browse(1, LANGUAGE_STRING(30032), 'files')
                if fileName:
                    client = XBMCDropBoxClient()
                    success = client.upload(fileName, toPath)
                    if success:
                        log('File uploaded: %s to %s' % (fileName, toPath) )
                        xbmc.executebuiltin('container.Refresh()')
                    else:
                        log_error('File uploading Failed: %s to %s' % (fileName, toPath))
                

