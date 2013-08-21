import os, sys, time, socket, urllib, urllib2, urlparse, httplib, hashlib
import xbmc, xbmcgui, xbmcplugin, xbmcaddon, xbmcvfs

ADDON           = xbmcaddon.Addon().getAddonInfo('id')
DATAPATH        = xbmc.translatePath( xbmcaddon.Addon().getAddonInfo('profile') )

APIKEY       = 'ehe9o5q5abevvq5'
APISECRET    = '6mbp7ww9hwzzczd'

def log(txt):
    if isinstance (txt,str):
        txt = txt.decode("utf-8")
    message = u'%s: %s' % (ADDON, txt)
    xbmc.log(msg=message.encode("utf-8"), level=xbmc.LOGNOTICE)
    
def log_error(txt):
    if isinstance (txt,str):
        txt = txt.decode("utf-8")
    message = u'%s: %s' % (ADDON, txt)
    xbmc.log(msg=message.encode("utf-8"), level=xbmc.LOGERROR)

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
