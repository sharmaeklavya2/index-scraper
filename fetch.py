import time
import os
from urllib.request import urlopen, Request
from urllib.parse import quote
from http.client import HTTPException
import logging
from typing import Optional

logger = logging.getLogger('fetch')


def clean_url(url: str) -> str:
    return quote(url, safe="/:=&?#+!$,;'@()*[]")


class TimedFetcher:

    DEFAULT_DELAY: float = 1
    DEFAULT_RETRY_DELAY = 5
    DEFAULT_RETRIES = 2
    USER_AGENT = 'eku-scraper'

    def __init__(self, delay: Optional[float] = None, retry_delay: Optional[float] = None,
            retries: Optional[int] = None):
        self.last_time: Optional[float] = None
        self.delay = TimedFetcher.DEFAULT_DELAY if delay is None else delay
        self.retry_delay = TimedFetcher.DEFAULT_RETRY_DELAY if retry_delay is None else retry_delay
        self.retries = TimedFetcher.DEFAULT_RETRIES if retries is None else retries
        self.count = 0

    def _get_current_time(self) -> float:
        return time.perf_counter()

    def _log_before(self, url: str, retry: int) -> None:
        if retry == 0:
            logger.info('Fetching: ' + url)
        else:
            logger.info('Fetching (retry {}): {}'.format(retry, url))

    def _log_after(self, url: str, retry: int, data: bytes) -> None:
        # logger.debug('Fetched {} bytes'.format(len(data)))
        pass

    def _sleep(self) -> None:
        current_time = self._get_current_time()
        if self.last_time is not None:
            sleep_time = self.last_time + self.delay - current_time
            if sleep_time > 0:
                # logger.debug('sleeping for {:.6f} seconds'.format(sleep_time))
                time.sleep(sleep_time)

    def fetch(self, url: str, fpath: str) -> bytes:
        if os.path.exists(fpath):
            with open(fpath, 'rb') as fp:
                logger.info('Fetching url {} cached at {}'.format(url, fpath))
                return fp.read()
        else:
            self._sleep()
            url = clean_url(url)
            request = Request(url=url, headers={'User-Agent': self.USER_AGENT})
            for retry in range(self.retries + 1):
                self._log_before(url, retry)
                data = None
                # url2 = None
                try:
                    with urlopen(request) as fobj:
                        data = fobj.read()
                        # url2 = fobj.geturl()
                except (OSError, IOError, HTTPException):
                    if retry == self.retries:
                        raise
                    else:
                        logger.exception('Fetch failed; retrying in {} seconds'.format(
                            self.retry_delay))
                        time.sleep(self.retry_delay)
                        continue
                self.count += 1
                self._log_after(url, retry, data)
                self.last_time = self._get_current_time()
                break
            with open(fpath, 'wb') as fp:
                assert data is not None
                fp.write(data)
            return data
