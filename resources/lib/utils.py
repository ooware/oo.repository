import os, sys, urllib
import xbmc, xbmcaddon

ADDON           = xbmcaddon.Addon(id='plugin.dbmc')
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

def replaceFileExtension(path, extension):
    extension = '.' + extension
    if extension in path[-len(extension):]:
        #file extension is ok, nothing to do
        return path
    else:
        newPath = path.rsplit('.',1)[0]
        return newPath + extension

def xor(w1, w2):
    from itertools import izip, cycle
    '''xor two strings together with the lenght of the first string limiting'''
    return ''.join(chr(ord(c1)^ord(c2)) for c1, c2 in izip(w1, cycle(w2)))
    
def decode_key(word):
    from base64 import b64encode, b64decode
    '''decode the word which was encoded with the given secret key.
    '''
    base = xor(b64decode(word, '-_'), ADDON_NAME)
    return base[4:int(base[:3], 10)+4]
