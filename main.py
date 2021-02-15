#!/bin/env python3
import re
import unicodedata
from datetime import timedelta
from pathlib import Path
from typing import List

from bs4 import BeautifulSoup, Tag
from spoofbot import Firefox, Browser
from spoofbot.adapter import FileCacheAdapter
from urllib3.util import Url, parse_url

MAIN_SITE = 'papers.nips.cc'


class PaperEntry:
    url: Url
    title: str
    authors: List[str]

    def __init__(self, path: str, title: str, authors: List[str]):
        self.url = Url('https', host=MAIN_SITE, path=path)
        self.title = title
        self.authors = authors

    def __str__(self) -> str:
        return f"{self.title} ({', '.join(self.authors)})"


class Paper:
    paper_entry: PaperEntry
    abstract: str  # .col > p:nth-child(8)

    def __init__(self, paper_entry: PaperEntry, abstract: str):
        self.paper_entry = paper_entry
        self.abstract = abstract

    def __str__(self) -> str:
        return str(self.paper_entry)

    @property
    def author_feedback_url(self) -> Url:
        return parse_url(
            self.paper_entry.url.url.replace('hash', 'file').replace('Abstract.html', 'AuthorFeedback.pdf'))

    @property
    def bibtex_url(self) -> Url:
        return parse_url(self.paper_entry.url.url.replace('hash', 'file').replace('Abstract.html', 'Bibtex.bib'))

    @property
    def meta_review_url(self) -> Url:
        return parse_url(self.paper_entry.url.url.replace('hash', 'file').replace('Abstract.html', 'MetaReview.html'))

    @property
    def paper_url(self) -> Url:
        return parse_url(self.paper_entry.url.url.replace('hash', 'file').replace('Abstract.html', 'Paper.pdf'))

    @property
    def review_url(self) -> Url:
        return parse_url(self.paper_entry.url.url.replace('hash', 'file').replace('Abstract.html', 'Review.html'))

    @property
    def supplemental_url(self) -> Url:
        return parse_url(self.paper_entry.url.url.replace('hash', 'file').replace('Abstract.html', 'Supplemental.pdf'))


def get_paper_entries(browser: Browser, year: int) -> List[PaperEntry]:
    main_site = BeautifulSoup(browser.navigate(f"https://{MAIN_SITE}/paper/{year}").content, features="html5lib")
    paper_entries = []
    li: Tag
    for li in main_site.select('.col > ul > li'):
        a = li.select_one('a')
        i = li.select_one('i')
        paper_entries.append(PaperEntry(a.get('href'), a.text, i.text.split(', ')))
    return paper_entries


def get_paper(browser: Browser, paper_entry: PaperEntry) -> Paper:
    paper_site = BeautifulSoup(browser.navigate(paper_entry.url.url).content, features="html5lib")
    return Paper(
        paper_entry,
        BeautifulSoup(  # The abstract is uninterpreted html code
            paper_site.select_one('.col > p:nth-child(8)').text,
            features="html5lib"
        ).text.strip()
    )


def slugify(string: str, allow_unicode: bool = False) -> str:
    """
    Slugify a given string.
    :param string: The string to slugify.
    :param allow_unicode: Whether to allow unicode characters or only ASCII characters.
    :return: The slug.
    """
    string = str(string)
    if allow_unicode:
        # noinspection SpellCheckingInspection
        string = unicodedata.normalize('NFKC', string)
    else:
        # noinspection SpellCheckingInspection
        string = unicodedata.normalize('NFKD', string).encode('ascii', 'ignore').decode('ascii')
    string = re.sub(r'[^\w\s-]', '', string).strip()
    return re.sub(r'[-\s]+', '-', string)


if __name__ == '__main__':
    year = 2020
    ff = Firefox()
    ff.request_timeout = timedelta(0, 0.2)
    ff.adapter = FileCacheAdapter()
    papers = list(map(get_paper, [ff], get_paper_entries(ff, year)))
    auth_to_paper = {}
    # for paper_entry in get_paper_entries(ff, year):
    #     for author in paper_entry.authors:
    #         authored_papers = auth_to_paper.get(author, [])
    #         authored_papers.append(paper_entry)
    #         auth_to_paper[author] = authored_papers
    # for author, coauthored_papers in sorted(auth_to_paper.items(), key=lambda kvp: len(kvp[1]), reverse=True):
    #     if len(coauthored_papers) == 1:
    #         break
    #     print(f"{author} co-authored {len(coauthored_papers)} papers:")
    #     for coauthored_paper in coauthored_papers:
    #         print(f"  - {coauthored_paper}")
    # exit(0)
    for paper_entry in get_paper_entries(ff, year):
        print(f"Processing: {paper_entry}")
        paper = get_paper(ff, paper_entry)
        paper_home = Path('out', str(year), slugify(paper_entry.title))
        paper_home.mkdir(parents=True, exist_ok=True)

        print(f"    Writing Authors")
        authors = Path(paper_home, 'Authors.txt')
        with open(authors, 'w') as f:
            f.write('\n'.join(paper_entry.authors))

        print(f"    Downloading Author Feedback")
        author_feedback = Path(paper_home, 'AuthorFeedback.pdf')
        with open(author_feedback, 'wb') as f:
            f.write(ff.get(paper.author_feedback_url.url).content)

        print(f"    Downloading Bibtex Entry")
        bibtex = Path(paper_home, 'Bibtex.bib')
        with open(bibtex, 'wb') as f:
            f.write(ff.get(paper.bibtex_url.url).content)

        print(f"    Downloading Meta Review")
        meta_review = Path(paper_home, 'MetaReview.html')
        meta_review_html = BeautifulSoup(ff.get(paper.meta_review_url.url).text, features="html5lib")
        with open(meta_review, 'w') as f:
            f.write(meta_review_html.select_one('body > p').text)

        print(f"    Downloading Paper")
        paper_pdf = Path(paper_home, 'Paper.pdf')
        with open(paper_pdf, 'wb') as f:
            f.write(ff.get(paper.paper_url.url).content)

        print(f"    Downloading Review")
        review = Path(paper_home, 'Review.html')
        review_html = BeautifulSoup(ff.get(paper.review_url.url).text, features="html5lib")
        with open(review, 'w') as f:
            f.write(review_html.select_one('body > p').text)

        print(f"    Downloading Supplemental Material")
        supplemental = Path(paper_home, 'Supplemental.pdf')
        with open(supplemental, 'wb') as f:
            f.write(ff.get(paper.supplemental_url.url).content)
