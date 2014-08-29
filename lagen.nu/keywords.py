# -*- coding: utf-8 -*-
from __future__ import unicode_literals

# system libraries
import re
import os
from collections import defaultdict
from time import time

# 3rdparty libs
import pkg_resources
import requests
from lxml import etree
from lxml.builder import ElementMaker
from rdflib import Literal

# my libs
from ferenda import util
from ferenda import DocumentRepository, TripleStore, DocumentStore, Describer
from ferenda.decorators import managedparsing
from ferenda.elements import Body

MW_NS = "{http://www.mediawiki.org/xml/export-0.3/}"


class KeywordStore(DocumentStore):
    def basefile_to_pathfrag(self, basefile):
        first = basefile[0].lower()
        return "%s/%s" % (first, basefile)

    def pathfrag_to_basefile(self, pathfrag):
        first, basefile = pathfrag.split("/", 1)
        return basefile


class Keyword(DocumentRepository):

    """Implements support for 'keyword hubs', conceptual resources which
       themselves aren't related to any document, but to which other
       documents are related. As an example, if a docrepo has
       documents that each contains a set of keywords, and the docrepo
       parse implementation extracts these keywords as ``dcterms:subject``
       resources, this docrepo creates a document resource for each of
       those keywords. The main content for the keyword may come from
       the :class:`~ferenda.sources.general.MediaWiki` docrepo, and
       all other documents in any of the repos that refer to this
       concept resource are automatically listed.

    """  # FIXME be more comprehensible
    alias = "keyword"
    downloaded_suffix = ".txt"
    documentstore_class = KeywordStore
    
    def __init__(self, config=None, **kwargs):
        super(Keyword, self).__init__(config, **kwargs)
        # extra functions -- subclasses can add / remove from this
        self.termset_funcs = [self.download_termset_mediawiki,
                              self.download_termset_wikipedia]

    def get_default_options(self):
        opts = super(Keyword, self).get_default_options()
        # The API endpoint URLs change with MW language
        opts['mediawikiexport'] = 'http://localhost/wiki/Special:Export/%s(basefile)'
        opts['wikipediatitles'] = 'http://download.wikimedia.org/svwiki/latest/svwiki-latest-all-titles-in-ns0.gz'
        return opts

    def download(self, basefile=None):
        # Get all "term sets" (used dcterms:subject Objects, wiki pages
        # describing legal concepts, swedish wikipedia pages...)
        terms = defaultdict(dict)

        # 1) Query the triplestore for all dcterms:subject triples (is this
        # semantically sensible for a "download" action -- the content
        # isn't really external?) -- term set "subjects" (these come
        # from both court cases and legal definitions in law text)
        sq = """
        PREFIX dcterms:<http://purl.org/dc/terms/>
        PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>

        SELECT DISTINCT ?subject ?label
        WHERE { {?uri dcterms:subject ?subject . } 
                OPTIONAL {?subject rdfs:label ?label . } }
        """
        store = TripleStore.connect(self.config.storetype,
                                    self.config.storelocation,
                                    self.config.storerepository)
        results = store.select(sq, "python")
        for row in results:
            if 'label' in row:
                label = row['label']
            else:
                label = self.basefile_from_uri(row['subject'])
            if len(label) < 100:  # sanity, no legit keyword is 100 chars
                terms[label]['subjects'] = True

        self.log.debug("Retrieved %s subject terms from triplestore" % len(terms))

        for termset_func in self.termset_funcs:
            termset_func(terms)

        for term in terms:
            if not term:
                continue
            self.log.info("%s: in %s termsets" % (term, len(terms[term])))
            with self.store.open_downloaded(term, "w") as fp:
                for termset in sorted(terms[term]):
                    fp.write(termset + "\n")

    def download_termset_mediawiki(self, terms):
        # 2) Download the wiki.lagen.nu dump from
        # http://wiki.lagen.nu/pages-articles.xml -- term set "mediawiki"
        xml = etree.parse(requests.get(self.config.mediawikidump).text)
        wikinamespaces = []

        # FIXME: Handle any MW_NS namespace (c.f. wiki.py)

        for ns_el in xml.findall("//" + MW_NS + "namespace"):
            wikinamespaces.append(ns_el.text)
        for page_el in xml.findall(MW_NS + "page"):
            title = page_el.find(MW_NS + "title").text
            if title == "Huvudsida":
                continue
            if ":" in title and title.split(":")[0] in wikinamespaces:
                continue  # only process pages in the main namespace
            if title.startswith("SFS/"):  # FIXME: should be handled in
                                         # subclass -- or
                                         # repo-specific pages should
                                         # be kept in subclasses
                continue  # only proces normal keywords
            terms[title]['mediawiki'] = True

        self.log.debug("Retrieved subject terms from wiki, now have %s terms" %
                       len(terms))

    def download_termset_wikipedia(self, terms):
        # 3) Download the Wikipedia dump from
        # http://download.wikimedia.org/svwiki/latest/svwiki-latest-all-titles-in-ns0.gz
        # -- term set "wikipedia"
        # FIXME: only download when needed
        resp = requests.get(self.config.wikipediatitles)
        wikipediaterms = resp.text.split("\n")
        for utf8_term in wikipediaterms:
            term = utf8_term.decode('utf-8').strip()
            if term in terms:
                terms[term]['wikipedia'] = True

        self.log.debug("Retrieved terms from wikipedia, now have %s terms" % len(terms))

    @managedparsing
    def parse(self, doc):
        # create a dummy txt
        d = Describer(doc.meta, doc.uri)
        d.rdftype(self.rdf_type)
        d.value(self.ns['dcterms'].title, Literal(doc.basefile, lang=doc.lang))
        d.value(self.ns['prov'].wasGeneratedBy, self.qualified_class_name())
        doc.body = Body()  # can be empty, all content in doc.meta
        return True

    re_tagstrip = re.compile(r'<[^>]*>')

    # FIXME: This is copied verbatim from sfs.py -- maybe it could go
    # into DocumentRepository or util? (or possibly triplestore?)
    def store_select(self, store, query_template, uri, context=None):
        if os.path.exists(query_template):
            fp = open(query_template, 'rb')
        elif pkg_resources.resource_exists('ferenda', query_template):
            fp = pkg_resources.resource_stream('ferenda', query_template)
        else:
            raise ValueError("query template %s not found" % query_template)
        params = {'uri': uri}
        sq = fp.read().decode('utf-8') % params
        fp.close()
        return store.select(sq, "python")

    # FIXME: translate this to be consistent with construct_annotations
    # (e.g. return a RDF graph through one or a few SPARQL queries),
    # not a XML monstrosity
    def prep_annotation_file(self, basefile):
        uri = self.canonical_uri(basefile)
        keyword = basefile
        store = TripleStore.connect(self.config.storetype,
                                    self.config.storelocation,
                                    self.config.storerepository)

        # Use SPARQL queries to create a rdf graph (to be used by the
        # xslt transform) containing the wiki authored
        # dcterms:description for this term.

        values = {'basefile': basefile,
                  'count': None}
        msg = ("%(basefile)s: selected %(count)s descriptions "
               "(%(elapsed).3f sec)")
        with util.logtime(self.log.debug,
                          msg,
                          values):
            wikidesc = self.store_select(store,
                                         "res/sparql/keyword_subjects.rq",
                                         uri)
            values['count'] = len(wikidesc)


        # FIXME: these other sources of keyword annotations should be
        # handled by subclasses
        dvdataset = "http://localhost:8000/dataset/dv"
        sfsdataset = "http://localhost:8000/dataset/dv"

        msg = ("%(basefile)s: selected %(count)s legaldefs "
               "(%(elapsed).3f sec)")
        with util.logtime(self.log.debug,
                          msg,
                          values):
            legaldefinitioner = self.store_select(store,
                                                  "res/sparql/keyword_sfs.rq",
                                                  uri, sfsdataset)
            values['count'] = len(wikidesc)

        msg = ("%(basefile)s: selected %(count)s legalcases"
               "(%(elapsed).3f sec)")
        with util.logtime(self.log.debug,
                          msg,
                          values):
            rattsfall = self.store_select(store,
                                          "res/sparql/keyword_dv.rq",
                                          uri, dvdataset)
            values['count'] = len(rattsfall)

        # Maybe we should handle <urn:x-local:arn> triples here as well?

        root_node = etree.Element("rdf:RDF")
        for prefix in util.ns:
            etree._namespace_map[util.ns[prefix]] = prefix
            root_node.set("xmlns:" + prefix, util.ns[prefix])

        main_node = etree.SubElement(root_node, "rdf:Description")
        main_node.set("rdf:about", uri)

        for d in wikidesc:
            desc_node = etree.SubElement(main_node, "dcterms:description")
            xhtmlstr = "<xht2:div xmlns:xht2='%s'>%s</xht2:div>" % (
                util.ns['xht2'], d['desc'])
            xhtmlstr = xhtmlstr.replace(
                ' xmlns="http://www.w3.org/2002/06/xhtml2/"', '')
            desc_node.append(etree.fromstring(xhtmlstr.encode('utf-8')))

        for r in rattsfall:
            subject_node = etree.SubElement(main_node, "dcterms:subject")
            rattsfall_node = etree.SubElement(subject_node, "rdf:Description")
            rattsfall_node.set("rdf:about", r['uri'])
            id_node = etree.SubElement(rattsfall_node, "dcterms:identifier")
            id_node.text = r['id']
            desc_node = etree.SubElement(rattsfall_node, "dcterms:description")
            desc_node.text = r['desc']

        for l in legaldefinitioner:
            subject_node = etree.SubElement(main_node, "rinfoex:isDefinedBy")
            rattsfall_node = etree.SubElement(subject_node, "rdf:Description")
            rattsfall_node.set("rdf:about", l['uri'])
            id_node = etree.SubElement(rattsfall_node, "rdfs:label")
            # id_node.text = "%s %s" % (l['uri'].split("#")[1], l['label'])
            id_node.text = self.sfsmgr.display_title(l['uri'])

        treestring = etree.tostring(root_node,
                                    encoding="utf-8",
                                    pretty_print=True)
        with self.store.open_annotation(basefile, mode="wb") as fp:
            fp.write(treestring)
        return self.store.annotation_path(basefile)
