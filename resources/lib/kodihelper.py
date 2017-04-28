import sys
import os
import urllib
import re
import urlparse

from cmore import CMore

import xbmc
import xbmcvfs
import xbmcgui
import xbmcplugin
from xbmcaddon import Addon


class KodiHelper(object):
    def __init__(self, base_url=None, handle=None):
        addon = self.get_addon()
        self.base_url = base_url
        self.handle = handle
        self.addon_path = xbmc.translatePath(addon.getAddonInfo('path'))
        self.addon_profile = xbmc.translatePath(addon.getAddonInfo('profile'))
        self.addon_name = addon.getAddonInfo('id')
        self.addon_version = addon.getAddonInfo('version')
        self.language = addon.getLocalizedString
        self.logging_prefix = '[%s-%s]' % (self.addon_name, self.addon_version)
        if not xbmcvfs.exists(self.addon_profile):
            xbmcvfs.mkdir(self.addon_profile)
        self.c = CMore(self.addon_profile, self.get_country(self.get_setting('country')), True)

    def get_addon(self):
        """Returns a fresh addon instance."""
        return Addon()

    def get_setting(self, setting_id):
        addon = self.get_addon()
        setting = addon.getSetting(setting_id)
        if setting == 'true':
            return True
        elif setting == 'false':
            return False
        else:
            return setting

    def set_setting(self, key, value):
        return self.get_addon().setSetting(key, value)

    def log(self, string):
        msg = '%s: %s' % (self.logging_prefix, string)
        xbmc.log(msg=msg, level=xbmc.LOGDEBUG)

    def dialog(self, dialog_type, heading, message=None, options=None, nolabel=None, yeslabel=None):
        dialog = xbmcgui.Dialog()
        if dialog_type == 'ok':
            dialog.ok(heading, message)
        elif dialog_type == 'yesno':
            return dialog.yesno(heading, message, nolabel=nolabel, yeslabel=yeslabel)
        elif dialog_type == 'select':
            ret = dialog.select(heading, options)
            if ret > -1:
                return ret
            else:
                return None

    def get_user_input(self, heading, hidden=False):
        keyboard = xbmc.Keyboard('', heading, hidden)
        keyboard.doModal()
        if keyboard.isConfirmed():
            query = keyboard.getText()
            self.log('User input string: %s' % query)
        else:
            query = None

        if query and len(query) > 0:
            return query
        else:
            return None

    def get_numeric_input(self, heading):
        dialog = xbmcgui.Dialog()
        numeric_input = dialog.numeric(0, heading)

        if len(numeric_input) > 0:
            return str(numeric_input)
        else:
            return None

    def check_for_prerequisites(self):
        if self.set_login_credentials() and self.check_for_credentials():
            return True
        else:
            return False

    def set_login_credentials(self):
        username = self.get_setting('username')
        password = self.get_setting('password')

        if self.get_setting('tv_provider_login'):
            operator = self.get_operator(self.get_setting('operator'))
            if not operator:
                return False
        else:
            operator = None
            self.set_setting('operator_title', '')
            self.set_setting('operator', '')

        if not username or not password:
            if operator:
                return self.set_tv_provider_credentials()
            else:
                self.dialog('ok', self.language(30017), self.language(30018))
                self.get_addon().openSettings()
                return False
        else:
            return True

    def check_for_credentials(self):
        if not self.c.get_credentials():
            self.login_process()
        return True

    def login_process(self):
        username = self.get_setting('username')
        password = self.get_setting('password')
        operator = self.get_setting('operator')
        self.c.login(username, password, operator)

    def set_tv_provider_credentials(self):
        operator = self.get_setting('operator')
        operators = self.c.get_operators()
        for i in operators:
            if operator == i['name']:
                username_type = i['username']
                password_type = i['password']
                info_message = re.sub('<[^<]+?>', '', i['login'])  # strip html tags
                break
        self.dialog('ok', self.get_setting('operator_title'), message=info_message)
        username = self.get_user_input(username_type)
        password = self.get_user_input(password_type, hidden=True)

        if username and password:
            self.set_setting('username', username)
            self.set_setting('password', password)
            return True
        else:
            return False

    def get_country(self, country=None):
        countries = ['sv_SE', 'da_DK', 'nb_NO', 'fi_FI']
        if not country:
            options = [self.language(30013), self.language(30014), self.language(30015), self.language(30016)]
            selected_country = self.dialog('select', self.language(30012), options=options)
            if selected_country is None:
                selected_country = 0  # default to .se
            self.set_setting('country_title', options[selected_country])
            self.set_setting('country', countries[selected_country])
            if selected_country == 3:
                self.set_setting('tv_provider_login', 'false')  # fi_FI doesn't have any tv providers
            self.reset_credentials()  # reset credentials when country is changed

        return self.get_setting('country')

    def get_operator(self, operator=None):
        if not operator:
            self.set_setting('tv_provider_login', 'true')
            options = []
            operators = self.c.get_operators()
            for i in operators:
                options.append(i['title'])

            selected_operator = self.dialog('select', self.language(30010), options=options)
            if selected_operator is not None:
                operator = operators[selected_operator]['name']
                operator_title = operators[selected_operator]['title']
                self.set_setting('operator', operator)
                self.set_setting('operator_title', operator_title)

        return self.get_setting('operator')

    def reset_credentials(self):
        self.c.reset_credentials()
        self.set_setting('operator', '')
        self.set_setting('operator_title', '')
        self.set_setting('username', '')
        self.set_setting('password', '')

    def add_item(self, title, params, items=False, folder=True, playable=False, info=None, art=None, content=False):
        addon = self.get_addon()
        listitem = xbmcgui.ListItem(label=title)

        if playable:
            listitem.setProperty('IsPlayable', 'true')
            folder = False
        if art:
            listitem.setArt(art)
        else:
            art = {
                'icon': addon.getAddonInfo('icon'),
                'fanart': addon.getAddonInfo('fanart')
            }
            listitem.setArt(art)
        if info:
            listitem.setInfo('video', info)
        if content:
            xbmcplugin.setContent(self.handle, content)

        recursive_url = self.base_url + '?' + urllib.urlencode(params)

        if items is False:
            xbmcplugin.addDirectoryItem(self.handle, recursive_url, listitem, folder)
        else:
            items.append((recursive_url, listitem, folder))
            return items

    def get_image(self, url):
        cache_dir = os.path.join(self.addon_profile, 'cache')
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        image_uri = url.split('/')[3].strip()
        img_location = os.path.join(cache_dir, image_uri)
        if os.path.exists(img_location):
            return img_location
        else:
            image = self.c.make_request(url, 'get')
            with open(img_location, 'wb') as img:
                img.write(image)
            return img_location

    def eod(self):
        """Tell Kodi that the end of the directory listing is reached."""
        xbmcplugin.endOfDirectory(self.handle)

    def play_item(self, video_id):
        wv_proxy_base = 'http://localhost:' + str(self.get_setting('wv_proxy_port'))
        stream = self.c.get_stream(video_id)

        playitem = xbmcgui.ListItem(path=stream['mpd_url'])
        playitem.setProperty('inputstreamaddon', 'inputstream.adaptive')
        playitem.setProperty('inputstream.adaptive.manifest_type', 'mpd')

        if stream['drm_protected']:
            playitem.setProperty('inputstream.adaptive.license_type', 'com.widevine.alpha')
            wv_proxy_url = '{0}?mpd_url={1}&license_url={2}'.format(wv_proxy_base, stream['mpd_url'], stream['license_url'])
            playitem.setProperty('inputstream.adaptive.license_key', wv_proxy_url + '||R{SSM}|')
        xbmcplugin.setResolvedUrl(self.handle, True, listitem=playitem)
