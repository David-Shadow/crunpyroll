import httpx
import re

from typing import Optional, List, Dict

from ..utils import *
from ..types import *
from ..errors import CrunchyrollError

class Crunchyroll:
    """Initialize Crunchyroll Client
    
    Parameters:
        email (``str``):
            Email or username of the account
        password (``str``):
            Password of the account
        locale (``str``, optional):
            The language to use in Crunchyroll
            E.g.: en-US, it-IT...
            Default to en-US
    """
    def __init__(self, email, password, locale: str="en-US") -> None:
        self.email = email
        self.password = password
        self.locale = locale
        self.config = dict()
        self.api_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36",
            "Content-Type": "application/x-www-form-urlencoded"
        }

    def start(self):
        """Start Crunchyroll and login"""
        print(f"Starting Crunchyroll Client {version}!\nMade by stefanodvx | https://github.com/stefanodvx/crunchyroll\n")
        self._login()

    def _make_request(self, method: str, url: str, headers: Dict=dict(), params=None, data=None, login=False) -> Optional[Dict]:
        if not self.config and not login:
            raise CrunchyrollError("Client is not started yet!")
        if not login:
            self._update_session()
        headers.update(self.api_headers)
        r = httpx.request(
            method,
            url,
            headers=headers,
            params=params,
            data=data
        )
        code = r.status_code
        r_json = r.json()
        if "error" in r_json:
            error_code = r_json.get("error")
            if error_code == "invalid_grant":
                raise CrunchyrollError(f"[{code}] Invalid login credentials.")
        elif "message" in r_json and "code" in r_json:
            message = r_json.get("message")
            raise CrunchyrollError(f"[{code}] Error occured: {message}")
        if code != 200:
            raise CrunchyrollError(f"[{code}] {r.text}")
        return r_json

    def _login(self) -> None:
        headers = {"Authorization": AUTHORIZATION}
        r = self._make_request(
            method="POST",
            url=TOKEN_ENDPOINT,
            headers=headers,
            data = {
                "username": self.email,
                "password": self.password,
                "grant_type": "password",
                "scope": "offline_access",
            },
            login=True
        )
        access_token = r.get("access_token")
        token_type = r.get("token_type")
        authorization = {"Authorization": f"{token_type} {access_token}"}
        self.config.update(r)
        self.api_headers.update(authorization)
        r = self._make_request(method="GET", url=INDEX_ENDPOINT, login=True)
        self.config.update(r)
        r = self._make_request(method="GET", url=PROFILE_ENDPOINT, login=True)
        self.config.update(r)

    def _update_session(self):
        if "cms" in self.config:
            current_time = get_date()
            expires_time = str_to_date(self.config["cms"]["expires"])
            if current_time > expires_time:
                self._login()

    def search(self, query: str, n: int=6, raw_json=False) -> Optional[List[Collection]]:
        """Search series

        Parameters:
            query (``str``):
                Query to search
            n (``int``, optional):
                Number of results to return
                Default to 6

        Returns:
            ``List``: On success, list of ``Collection`` is returned
        """
        r = self._make_request(
            method="GET",
            url=SEARCH_ENDPOINT,
            params = {
                "q": query,
                "n": str(n),
                "locale": self.locale
            }
        )
        return [Collection(**collection) for collection in r.get("items")] if not raw_json else r

    def get_series(self, series_id: str, raw_json=False) -> Optional[Series]:
        """Get info about a series

        Parameters:
            series_id (``str``):
                ID of the series

        Returns:
            ``Series``: On success, ``Series`` object is returned
        """
        r = self._make_request(
            method="GET",
            url=SERIES_ENDPOINT.format(self.config.get("cms", {}).get("bucket"), series_id),
            params = {
                "Policy": self.config.get("cms", {}).get("policy"),
                "Signature": self.config.get("cms", {}).get("signature"),
                "Key-Pair-Id": self.config.get("cms", {}).get("key_pair_id"),
                "locale": self.locale
            }
        )
        return Series(**r) if not raw_json else r
        
    def get_seasons(self, series_id: str, raw_json=False) -> Optional[List[Season]]:
        """Get seasons of a series

        Parameters:
            series_id (``str``):
                ID of the series

        Returns:
            ``List``: On success, list of ``Season`` is returned
        """
        r = self._make_request(
            method="GET",
            url=SEASONS_ENDPOINT.format(self.config.get("cms", {}).get("bucket")),
            params = {
                "series_id": series_id,
                "Policy": self.config.get("cms", {}).get("policy"),
                "Signature": self.config.get("cms", {}).get("signature"),
                "Key-Pair-Id": self.config.get("cms", {}).get("key_pair_id"),
                "locale": self.locale
            }
        )
        return [Season(**season) for season in r.get("items")] if not raw_json else r

    def get_episodes(self, season_id: str, raw_json=False) -> Optional[List[Episode]]:
        """Get episodes of a series (from season)

        Parameters:
            season_id (``str``):
                ID of a season

        Returns:
            ``List``: On success, list of ``Episode`` is returned
        """
        r = self._make_request(
            method="GET",
            url=EPISODES_ENDPOINT.format(self.config.get("cms", {}).get("bucket")),
            params = {
                "season_id": season_id,
                "Policy": self.config.get("cms", {}).get("policy"),
                "Signature": self.config.get("cms", {}).get("signature"),
                "Key-Pair-Id": self.config.get("cms", {}).get("key_pair_id"),
                "locale": self.locale
            }
        )
        return [Episode(**episode) for episode in r.get("items")] if not raw_json else r

    def get_streams(self, episode: Episode, raw_json=False) -> Optional[StreamsInfo]:
        """Get streams from an episode

        Parameters:
            episode (``Episode``):
                Pass one of the items that ``get_episodes()`` returns

        Returns:
            ``StreamsInfo``: On success, ``StreamsInfo`` object is returned
        """
        stream_id = re.search(r"videos\/(.+?)\/streams", episode.links.streams.href).group(1)
        r = self._make_request(
            method="GET",
            url=STREAMS_ENDPOINT.format(self.config.get("cms", {}).get("bucket"), stream_id),
            params = {
                "Policy": self.config.get("cms", {}).get("policy"),
                "Signature": self.config.get("cms", {}).get("signature"),
                "Key-Pair-Id": self.config.get("cms", {}).get("key_pair_id"),
                "locale": self.locale
            }
        )
        
        # Fix empty key in video streams
        fixup(r)
    
        return StreamsInfo(**r) if not raw_json else r

    def get_similar(self, series_id: str, n: int=6, raw_json=False) -> Optional[List[Panel]]:
        """Get similar series

        Parameters:
            series_id (``str``):
                ID of the series
            n (``int``, optional):
                Number of results to return
                Default to 6

        Returns:
            ``List``: On success, list of ``Panel`` is returned
        """
        r = self._make_request(
            method="GET",
            url=SIMILAR_ENDPOINT.format(self.config.get("account_id")),
            params = {
                "guid": series_id,
                "n": str(n),
                "locale": self.locale
            }
        )
        return [Panel(**panel) for panel in  r.get("items")] if not raw_json else r

    def news_feed(self, n: int=6, raw_json=False) -> Optional[NewsFeed]:
        """Get news feed

        Parameters:
            n (``int``, optional):
                Number of results to return
                Default to 6

        Returns:
            ``NewsFeed``: On success, ``NewsFeed`` object is returned
        """
        r = self._make_request(
            method="GET",
            url=NEWSFEED_ENDPOINT,
            params = {
                "n": str(n),
                "locale": self.locale
            }
        )
        return NewsFeed(**r) if not raw_json else r

    def browse(self, sort_by: str = "newly_added", n: int=6, raw_json=False) -> Optional[List[Panel]]:
        """Browse Crunchyroll catalog

        Parameters:
            sort_by (``str``, optional):
                Sort by ``newly_added`` or ``popularity``
                Default to ``newly_added``
            n (``int``, optional):
                Number of results to return
                Default to 6

        Returns:
            ``List``: On success, list of ``Panel`` is returned
        """
        r = self._make_request(
            method="GET",
            url=BROWSE_ENDPOINT,
            params = {
                "sort_by": sort_by,
                "n": str(n),
                "locale": self.locale
            }
        )
        return [Panel(**panel) for panel in  r.get("items")] if not raw_json else r

    def get_formats(self, url: str) -> Optional[List[PlaylistItem]]:
        """Get formats in a playlist

        Parameters:
            url (``str``):
                URL of the m3u8 playlist

        Returns:
            ``List``: On success, list of ``PlaylistItem`` is returned
        """
        formats = list()
        r = httpx.get(url)
        lines = r.text.split("\n")
        for i, line in enumerate(lines, 1):
            regesp = re.match(PLAYLIST_REG, line.strip())
            if regesp:
                formats.append({
                    "url": lines[i].strip(),
                    "bandwidth": int(regesp.group(1)),
                    "width": int(regesp.group(2)),
                    "height": int(regesp.group(3)),
                    "framerate": regesp.group(4),
                    "codecs": regesp.group(5)
                })
        return [PlaylistItem(**frmt) for frmt in formats]