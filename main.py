#!/usr/bin/env python3

"""
Crawl and scrape a website. Originally written for CSES.
"""

import sys
import os
from os.path import join as pjoin
import argparse
import json
import logging
import logging.config
from collections.abc import Mapping, Sequence
from typing import Any

import shutil
from lxml import etree  # type: ignore
from urllib.parse import urljoin
import jinja2

from fetch import TimedFetcher


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
logger = logging.getLogger()


def configureLogging(out_dir: str, verbosity: int) -> None:
    with open(pjoin(BASE_DIR, 'loggingConfig.json')) as fp:
        config = json.load(fp)
    os.makedirs(out_dir, exist_ok=True)
    info_file = pjoin(out_dir, 'info.log')
    config['handlers']['info_file']['filename'] = info_file
    error_file = pjoin(out_dir, 'error.log')
    config['handlers']['error_file']['filename'] = error_file
    if verbosity <= 1:
        logging.getLogger('fetch').setLevel(logging.WARNING)
    elif verbosity >= 3:
        config['root']['level'] = 'DEBUG'
    logging.config.dictConfig(config)
    logger.info('')


def urlToId(url: str) -> str:
    url = url.split('?')[0]
    return url.split('/')[-1]


def scrapeIndex(config: Mapping[str, Any], out_dir: str,
        data: bytes) -> Sequence[Mapping[str, str]]:
    doc = etree.HTML(data)
    tags = doc.cssselect(config['index']['entryCSS'])
    d = []
    for tag in tags:
        title = ''.join(tag.itertext())
        rawUrl = tag.attrib.get('href')
        url = urljoin(config['index']['url'], rawUrl)
        id = urlToId(rawUrl)
        d.append({'url': url, 'title': title, 'id': id})
    indexInfoFpath = pjoin(out_dir, 'info', '_index.json')
    with open(indexInfoFpath, 'w') as fp:
        json.dump(d, fp, indent=2)
    return d


def scrapePage(config: Mapping[str, Any], out_dir: str, data: bytes) -> str:
    data = data.replace(b'\r\n', b'\n')
    doc = etree.HTML(data)
    tags = doc.cssselect(config['page']['contentCSS'])
    if len(tags) != 1:
        raise ValueError('More tags in page than expected')
    tagsToRemove = config['page'].get('tagsToRemove')
    if tagsToRemove:
        etree.strip_elements(tags[0], tagsToRemove)
    v = etree.tostring(tags[0], encoding='unicode').strip()
    return v


def copy(source: str, dest: str) -> None:
    'Copy all files in source to dest'
    os.makedirs(dest, exist_ok=True)
    for fname in os.listdir(source):
        source_path = pjoin(source, fname)
        dest_path = pjoin(dest, fname)
        shutil.copy(source_path, dest_path)


def getTemplate(themeDir: str, fname: str) -> Any:
    templatePath = pjoin(themeDir, 'templates', fname)
    try:
        with open(templatePath) as fobj:
            return jinja2.Template(fobj.read())
    except FileNotFoundError:
        logger.error(templatePath + ' was not found.')
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-dir', required=True, help='output directory of project')
    parser.add_argument('--config', required=True,
        help='path to config file (file will be copied to out_dir)')
    # parser.add_argument('--theme', help='Directory containing theme to apply to generated site')
    parser.add_argument('--verbosity', type=int, default=2,
        help='1: print errors, 2: print important messages, 3: print everything')
    parser.add_argument('--delay', type=float, default=1,
        help='delay between page downloads (in seconds)')
    parser.add_argument('--limit', type=int, help='maximum number of pages to fetch')
    parser.add_argument('--theme', help='directory containing theme to apply to generated site')
    args = parser.parse_args()

    configureLogging(args.out_dir, args.verbosity)

    # Load config
    if args.config:
        shutil.copyfile(args.config, pjoin(args.out_dir, 'config.json'))
    config_path = pjoin(args.out_dir, 'config.json')
    with open(config_path) as fobj:
        config = json.load(fobj)
    os.makedirs(pjoin(args.out_dir, 'info'), exist_ok=True)
    os.makedirs(pjoin(args.out_dir, 'raw'), exist_ok=True)

    # init theme
    if args.theme is None:
        args.theme = pjoin(BASE_DIR, 'theme')
    copy(pjoin(args.theme, 'static'), pjoin(args.out_dir, 'site'))
    indexTemplate = getTemplate(args.theme, 'index.html')
    pageTemplate = getTemplate(args.theme, 'page.html')

    fetcher = TimedFetcher(args.delay)

    try:
        indexUrl = config['index']['url']
        indexFpath = pjoin(args.out_dir, 'raw', '_index.html')
        indexData = fetcher.fetch(indexUrl, indexFpath)
        index = scrapeIndex(config, args.out_dir, indexData)
        if indexTemplate is not None:
            output = indexTemplate.render({'title': config['metadata'].get('title'),
                'extensions': config['extensions'], 'pageList': index})
            with open(pjoin(args.out_dir, 'site', 'index.html'), 'w') as fp:
                fp.write(output)
        for sno, indexEntry in enumerate(index):
            if args.limit is None or sno < args.limit:
                pageFpath = pjoin(args.out_dir, 'raw', indexEntry['id'] + '.html')
                pageData = fetcher.fetch(indexEntry['url'], pageFpath)
                content = scrapePage(config, args.out_dir, pageData)
                pageContentPath = pjoin(args.out_dir, 'info', indexEntry['id'] + '.html')
                with open(pageContentPath, 'w') as fp:
                    fp.write(content)
                if pageTemplate is not None:
                    context = {k: v for k, v in indexEntry.items()}
                    context['content'] = content
                    context['extensions'] = config['extensions']
                    output = pageTemplate.render(context)
                    with open(pjoin(args.out_dir, 'site', indexEntry['id'] + '.html'), 'w') as fp:
                        fp.write(output)
    except KeyboardInterrupt:
        logger.exception('Caught KeyboardInterrupt')
    except Exception:
        logger.exception('Caught exception')

    return 0


if __name__ == '__main__':
    sys.exit(main())
