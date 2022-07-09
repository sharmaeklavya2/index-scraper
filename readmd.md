# Index Scraper

A website that has an 'index page' which links to a list of other pages is
what I call an 'index website'. This tool scrapes an index website.
It takes as input a config file which lists the CSS selectors to grab
index entries and page content from.

The first website I scraped was the [CSES Problemset](https://cses.fi/problemset/),
so that I can read it offline. See `cses.json` for an example config file.
