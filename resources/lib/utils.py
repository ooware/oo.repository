import sys, urllib
import xbmc, xbmcaddon

ADDON           = xbmcaddon.Addon(id='plugin.dropbox')
LANGUAGE_STRING = ADDON.getLocalizedString
ADDON_NAME      = xbmcaddon.Addon().getAddonInfo('id')
DATAPATH        = xbmc.translatePath( xbmcaddon.Addon().getAddonInfo('profile') )

def log(txt):
    if isinstance (txt,str):
        txt = txt.decode("utf-8")
    message = u'%s: %s' % (ADDON_NAME, txt)
    xbmc.log(msg=message.encode("utf-8"), level=xbmc.LOGNOTICE)
    
def log_error(txt):
    if isinstance (txt,str):
        txt = txt.decode("utf-8")
    message = u'%s: %s' % (ADDON_NAME, txt)
    xbmc.log(msg=message.encode("utf-8"), level=xbmc.LOGERROR)

def log_debug(txt):
    if isinstance (txt,str):
        txt = txt.decode("utf-8")
    message = u'%s: %s' % (ADDON_NAME, txt)
    xbmc.log(msg=message.encode("utf-8"), level=xbmc.LOGDEBUG)

def parse_argv():
    # parse argv
    try:
        # started as plugin
        params = {}
        paramstring = sys.argv[2]
        if paramstring:
            splitparams = paramstring.lstrip('?').split('&')
            for item in splitparams:
                item = urllib.unquote_plus(item)
                keyval = item.split('=')
                params[keyval[0]] = keyval[1]
        return False, params
    except:
        # started as script
        params = dict( arg.split( "=" ) for arg in sys.argv[ 1 ].split( "&" ) )
        return True, params
