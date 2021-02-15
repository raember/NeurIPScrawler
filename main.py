#!/bin/env python3
import re
import unicodedata
from datetime import timedelta
from os.path import splitext
from pathlib import Path
from typing import List
from zipfile import ZipFile, BadZipFile

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
    abstract: str
    author_feedback_url: Url
    bibtex_url: Url
    meta_review_url: Url
    paper_url: Url
    review_url: Url
    supplemental_url: Url

    def __init__(self, paper_entry: PaperEntry, abstract: Url, author_feedback_url: Url, bibtex_url: Url,
                 meta_review_url: Url, paper_url: Url, review_url: Url, supplemental_url: Url):
        self.paper_entry = paper_entry
        self.abstract = abstract
        self.author_feedback_url = author_feedback_url
        self.bibtex_url = bibtex_url
        self.meta_review_url = meta_review_url
        self.paper_url = paper_url
        self.review_url = review_url
        self.supplemental_url = supplemental_url

    def __str__(self) -> str:
        return str(self.paper_entry)


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
    url = paper_entry.url
    author_feedback_url = None
    bibtex_url = None
    meta_review_url = None
    paper_url = None
    review_url = None
    supplemental_url = None
    for a in paper_site.select('a.btn'):
        if a.text == 'AuthorFeedback »':
            author_feedback_url = parse_url(f"{url.scheme}://{url.host}{a.get('href')}")
        elif a.text == 'Bibtex »':
            bibtex_url = parse_url(f"{url.scheme}://{url.host}{a.get('href')}")
        elif a.text == 'MetaReview »':
            meta_review_url = parse_url(f"{url.scheme}://{url.host}{a.get('href')}")
        elif a.text == 'Paper »':
            paper_url = parse_url(f"{url.scheme}://{url.host}{a.get('href')}")
        elif a.text == 'Review »':
            review_url = parse_url(f"{url.scheme}://{url.host}{a.get('href')}")
        elif a.text == 'Supplemental »':
            supplemental_url = parse_url(f"{url.scheme}://{url.host}{a.get('href')}")
        else:
            raise Exception(f"Failed to bin link for '{a.text}': {a.get('href')}")
    return Paper(
        paper_entry,
        BeautifulSoup(  # The abstract is uninterpreted html code
            paper_site.select_one('.col > p:nth-child(8)').text,
            features="html5lib"
        ).text.strip(),
        author_feedback_url,
        bibtex_url,
        meta_review_url,
        paper_url,
        review_url,
        supplemental_url
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

    # # How many papers are there?
    # pprs = []
    # for pprentry in get_paper_entries(ff, year):
    #     pprs.append(get_paper(ff, pprentry))
    # print(len(pprs))
    # exit(0)

    # # How co-authored the most?
    # auth_to_paper = {}
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

    # Scrape and store
    no_author_feedback = 0
    no_supplemental_material = 0
    supplemental_material_zipped = 0
    supplemental_material_pdf = 0
    for paper_entry in get_paper_entries(ff, year):
        print(f"Processing: {paper_entry}")
        paper = get_paper(ff, paper_entry)
        paper_home = Path('out', str(year), slugify(paper_entry.title))
        paper_home.mkdir(parents=True, exist_ok=True)

        # print(f"    Writing Authors")
        # authors = Path(paper_home, 'Authors.txt')
        # with open(authors, 'w') as f:
        #     f.write('\n'.join(paper_entry.authors))
        #
        # # Exactly two papers (2020) don't have an author feedback:
        # # https://papers.nips.cc/paper/2020/hash/7ac52e3f2729d1b3f6d2b7e8f6467226-Abstract.html
        # # https://papers.nips.cc/paper/2020/hash/d6f1dd034aabde7657e6680444ceff62-Abstract.html
        # if paper.author_feedback_url is not None:
        #     print(f"    Downloading Author Feedback")
        #     _, ext = splitext(paper.author_feedback_url.path)
        #     assert(ext == '.pdf')
        #     author_feedback = Path(paper_home, 'AuthorFeedback.pdf')
        #     with open(author_feedback, 'wb') as f:
        #         f.write(ff.get(paper.author_feedback_url.url).content)
        # else:
        #     no_author_feedback += 1
        #
        # print(f"    Downloading Bibtex Entry")
        # _, ext = splitext(paper.bibtex_url.path)
        # assert(ext == '.bib')
        # bibtex = Path(paper_home, 'Bibtex.bib')
        # with open(bibtex, 'wb') as f:
        #     f.write(ff.get(paper.bibtex_url.url).content)
        #
        # print(f"    Downloading Meta Review")
        # _, ext = splitext(paper.meta_review_url.path)
        # assert(ext == '.html')
        # meta_review = Path(paper_home, 'MetaReview.html')
        # meta_review_html = BeautifulSoup(ff.get(paper.meta_review_url.url).text, features="html5lib")
        # with open(meta_review, 'w') as f:
        #     f.write(meta_review_html.select_one('body > p').text)
        #
        # print(f"    Downloading Paper")
        # _, ext = splitext(paper.paper_url.path)
        # assert(ext == '.pdf')
        # paper_pdf = Path(paper_home, 'Paper.pdf')
        # with open(paper_pdf, 'wb') as f:
        #     f.write(ff.get(paper.paper_url.url).content)
        #
        # print(f"    Downloading Review")
        # _, ext = splitext(paper.review_url.path)
        # assert(ext == '.html')
        # review = Path(paper_home, 'Review.html')
        # review_html = BeautifulSoup(ff.get(paper.review_url.url).text, features="html5lib")
        # with open(review, 'w') as f:
        #     f.write(review_html.select_one('body > p').text)

        if paper.supplemental_url is None:
            no_supplemental_material += 1
            continue  # No supplemental material
        print(f"    Downloading Supplemental Material")
        _, ext = splitext(paper.supplemental_url.path)
        assert (ext in ('.pdf', '.zip'))
        supplemental = Path(paper_home, f'Supplemental{ext}')
        with open(supplemental, 'wb') as f:
            f.write(ff.get(paper.supplemental_url.url).content)
        if ext == '.zip':
            supplemental_material_zipped += 1
            print(f"        Unzipping...")
            extraction_path = Path(paper_home, 'Supplemental')
            extraction_path.mkdir(parents=True, exist_ok=True)
            try:
                with ZipFile(supplemental, 'r') as f:
                    f.extractall(extraction_path)
            except BadZipFile:
                # https://papers.nips.cc/paper/2020/hash/95424358822e753eb993c97ee76a9076-Abstract.html
                print("        !!! Failed to unzip faulty zip file !!!!")
        else:
            supplemental_material_pdf += 1
    print(f"Papers without author feedback: {no_author_feedback}")
    print(f"Papers without supplemental material: {no_supplemental_material}")
    print(f"Papers with zipped supplemental material: {supplemental_material_zipped}")
    print(f"Papers with pdfs as supplemental material: {supplemental_material_pdf}")
