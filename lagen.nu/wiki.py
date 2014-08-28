# -*- coding: utf-8 -*-
from __future__ import unicode_literals

# system
from tempfile import mktemp
import random
import re
import os
from six import text_type as str

# 3rdparty
from lxml import etree
from rdflib import Namespace, URIRef, Literal

# mine
from ferenda import DocumentRepository, DocumentStore
from ferenda import util
from ferenda.sources.legal.se import SwedishCitationParser
# from ferenda.sources.general import Keyword
from keywords import Keyword, LNKeyword

try:
    from ferenda.thirdparty.mw import Parser, Semantics, Settings, Preprocessor
except ImportError as e:
    import sys
    if sys.version_info < (2, 7):
        raise RuntimeError("ferenda.sources.general.Wiki is not supported under python 2.6: %s" % str(e))
    else:
        raise e # dunno
        
import unicodedata
class MediaWikiStore(DocumentStore):
    def basefile_to_pathfrag(self, basefile):
        return basefile.replace(":", os.sep).replace(" ", "_")

    def pathfrag_to_basefile(self, pathfrag):
        # This unicode normalization turns "a" + U+0308 (COMBINING
        # DIAERESIS) into a honest 'ä'. This is an issue on mac file
        # systems. FIXME: should this be a part of
        # DocumentStore.pathfrag_to_basefile?
        return unicodedata.normalize("NFC", pathfrag.replace("_", " ").replace(os.sep, ":"))


class MediaWiki(DocumentRepository):

    """Downloads content from a Mediawiki system and converts it to annotations on other documents.

    For efficient downloads, this docrepo requires that there exists a
    XML dump (created by `dumpBackup.php
    <http://www.mediawiki.org/wiki/Manual:DumpBackup.php>`_) of the
    mediawiki contents that can be fetched over HTTP/HTTPS. Configure
    the location of this dump using the ``mediawikiexport``
    parameter::

        [mediawiki]
        class = ferenda.sources.general.MediaWiki
        mediawikiexport = http://localhost/wiki/allpages-dump.xml

    """

    alias = "mediawiki"
    downloaded_suffix = ".xml"
    documentstore_class = MediaWikiStore
    rdf_type = Namespace(util.ns['skos']).Concept
    keyword_class = Keyword
    
    def __init__(self, config=None, **kwargs):
        super(MediaWiki, self).__init__(config, **kwargs)
        if self.config._parent and hasattr(self.config._parent, 'keyword'):
            self.keywordrepo = self.keyword_class(self.config._parent.keyword)
        else:
            self.keywordrepo = self.keyword_class()
    
    def get_default_options(self):
        opts = super(MediaWiki, self).get_default_options()
        # The API endpoint URLs change with MW language
        opts['mediawikiexport'] = 'http://localhost/wiki/Special:Export/%s(basefile)'
        opts['mediawikidump'] = 'http://localhost/wiki/allpages-dump.xml'
        opts['mediawikinamespaces'] = ['Category']
            # process pages in this namespace (as well as pages in the default namespace)
        return opts

    def download(self, basefile=None):
        if basefile:
            return self.download_single(basefile)

        if self.config.mediawikidump:
            # resp = requests.get(self.config.mediawikidump)
            # xml = etree.parse(resp.content)
            xmldumppath = self.store.path('dump', 'downloaded', '.xml')
            xml = etree.parse(xmldumppath)
        else:
            raise ConfigurationError("config.mediawikidump not set")

        MW_NS = "{%s}" % xml.getroot().nsmap[None]
        wikinamespaces = []
        # FIXME: Find out the proper value of MW_NS
        for ns_el in xml.findall("//" + MW_NS + "namespace"):
            wikinamespaces.append(ns_el.text)

        # Get list of existing basefiles - if any of those
        # does not appear in the XML dump, remove them afterwards
        basefiles = list(self.store.list_basefiles_for("parse"))

        for page_el in xml.findall(MW_NS + "page"):
            basefile = page_el.find(MW_NS + "title").text
            if basefile == "Huvudsida":
                continue
            if ":" in basefile and basefile.split(":")[0] in wikinamespaces:
                (namespace, localtitle) = basefile.split(":", 1)
                if namespace not in self.config.mediawikinamespaces:
                    continue
            p = self.store.downloaded_path(basefile)
            self.log.info("%s: extracting from XML dump" % basefile)
            with self.store.open_downloaded(basefile, "w") as fp:
                fp.write(etree.tostring(page_el, encoding="utf-8"))

            if basefile in basefiles:
                del basefiles[basefiles.index(basefile)]

        for b in basefiles:
            self.log.debug("%s: removing stale document" % b)
            util.robust_remove(self.store.downloaded_path(b))

    def download_single(self, basefile):
        # download a single term, for speed
        url = self.config.mediawikiexport % {'basefile': basefile}
        self.download_if_needed(url, basefile)

    re_anchors = re.compile('(<a.*?</a>)', re.DOTALL)
    re_anchor = re.compile('<a[^>]*>(.*)</a>', re.DOTALL)
    re_tags = re.compile('(</?[^>]*>)', re.DOTALL)


    # NOTE: What is this thing, really? Is it a wiki document by
    # itself, or is it metadata about a concept identified by a
    # keyword / label?
    def parse_metadata_from_soup(self, soup, doc):
        super(MediaWiki, self).parse_metadata_from_soup(soup, doc)
        # remove dcterms:identifier because it's pointless
        doc.meta.remove((URIRef(doc.uri),
                         self.ns['dcterms'].identifier,
                         Literal(doc.basefile)))
    
    def parse_document_from_soup(self, soup, doc):
        
        wikitext = soup.find("text").text
        parser = self.get_wikiparser()
        settings = self.get_wikisettings()
        semantics = self.get_wikisemantics(parser, settings)
        preprocessor = self.get_wikipreprocessor(settings)
        
        # the main responsibility of the preprocessor is to expand templates
        wikitext = preprocessor.expand(doc.basefile, wikitext)

        xhtml = parser.parse(wikitext, "document",
                             filename=doc.basefile,
                             semantics=semantics,
                             trace=False)
        doc.body = self.postprocess(doc, xhtml)
        return None

    def canonical_uri(self, basefile):
        # by default, a wiki page is expected to describe a
        # concept/keyword -- so we use our associated Keyword repo to
        # find its uri.
        return self.keywordrepo.canonical_uri(basefile)

    def get_wikiparser(self):
        return Parser(parseinfo=False, whitespace='', nameguard=False)

    def get_wikisemantics(self, parser, settings):
        return WikiSemantics(parser, settings)
        
    def get_wikisettings(self):
        return WikiSettings(lang=self.lang)

    def get_wikipreprocessor(self, settings):
        return WikiPreprocessor(settings)

    def postprocess(self, doc, xhtmltree, toplevel_property=True):
        body = xhtmltree.getchildren()[0]
        # render_xhtml_tree will add @about
        if toplevel_property:
            # shouldn't add these in SFS mode
            body.set("property", "dcterms:description")
            body.set("datatype", "rdf:XMLLiteral")
        # find any links that indicate that this concept has the
        # dcterms:subject of something (typically indicated by
        # Category tags)
        for subjectlink in xhtmltree.findall(".//a[@rel='dcterms:subject']"):
            # add metadata
            doc.meta.add((URIRef(doc.uri),
                          self.ns['dcterms'].subject,
                          URIRef(subjectlink.get("href"))))
            # remove from tree
            parent = subjectlink.getparent()
            parent.remove(subjectlink)
            # if the containing element is empty, remove as well
            if not (len(parent) or
                    parent.text or
                    parent.tail):
                parent.getparent().remove(parent)
        
        # convert xhtmltree to a ferenda.Elements tree
        root = self.elements_from_node(xhtmltree)
        return root[0]

        
    def elements_from_node(self, node):
        
        from ferenda.elements.html import _tagmap
        assert node.tag in _tagmap
        element = _tagmap[node.tag](**node.attrib)
        if node.text and node.text.strip():
            element.append(str(node.text))
        for child in node:
            if isinstance(child, str):
                element.append(str(child))
            else:
                subelement = self.elements_from_node(child)
                if subelement: # != None? 
                    element.append(subelement)
                if child.tail and child.tail.strip():
                    element.append(str(child.tail))
        return element

    # differ from the default relate_triples in that it uses a different
    # context for every basefile and clears this beforehand.
    # Note that a basefile can contain statements
    # about multiple and changing subjects, so it's not trivial to erase all
    # statements that stem from a basefile w/o a dedicated context.
    def relate_triples(self, basefile):
        context = self.dataset_uri + "#" + basefile.replace(" ", "_")
        ts = self._get_triplestore()
        data = open(self.store.distilled_path(basefile)).read()
        ts.clear(context=context)
        ts.add_serialized(data, format="xml", context=context)


class WikiSemantics(Semantics):
    def internal_link(self, ast):
        el = super(WikiSemantics, self).internal_link(ast)
        target = "".join(ast.target).strip()
        name = self.settings.canonical_page_name(target)
        if name[0].prefix == 'category':
            el.set("rel", "dcterms:subject")
        return el


class WikiSettings(Settings):
    def make_url(self, name, **kwargs):
        uri = super(WikiSettings, self).make_url(name, **kwargs)
        return uri

class WikiPreprocessor(Preprocessor):
    def get_template(self, namespace, pagename):
        if namespace.prefix != "template":
            return None
        tmpl = self.settings.templates.get((namespace.prefix, pagename), None)
        return tmpl

    
# This is a set of subclasses to regular Wiki and scm.mw classes to
# customize behaviour. This should be moved out of wiki.py and into a
# separate subclass, once we have finished customizing.

# from ferenda.sources.legal.se import SFS
from sfs import SFS


class SFSMediaWiki(MediaWiki):
    re_sfs_uri = re.compile('https?://[^/]*lagen.nu/(\d+):(.*)')
    re_dom_uri = re.compile('https?://[^/]*lagen.nu/dom/(.*)')

    from ferenda.sources.legal.se.legalref import LegalRef
    
    p = LegalRef(LegalRef.LAGRUM, LegalRef.KORTLAGRUM,
                 LegalRef.FORARBETEN, LegalRef.RATTSFALL)

    keyword_class = LNKeyword

    lang = "sv"
    
    def __init__(self, config=None, **kwargs):
        super(SFSMediaWiki, self).__init__(config, **kwargs)
        if self.config._parent and hasattr(self.config._parent, "sfs"):
            self.sfsrepo = SFS(self.config._parent.sfs)
        else:
            self.sfsrepo = SFS()

    def get_wikisettings(self):
        settings = SFSSettings(lang=self.lang)
        # NOTE: The settings object (the make_url method) only needs
        # access to the canonical_uri method.
        settings.make_sfs_url = self.sfsrepo.canonical_uri
        settings.make_keyword_url = self.keywordrepo.canonical_uri
        return settings

    def get_wikisemantics(self, parser, settings):
        return SFSSemantics(parser, settings)

    def canonical_uri(self, basefile):
        if basefile.startswith("SFS/") or basefile.startswith("SFS:"):
            # "SFS/1998:204" -> "1998:204"
            return self.sfsrepo.canonical_uri(basefile[4:])
        else:
            return super(SFSMediaWiki, self).canonical_uri(basefile)
        
    def postprocess(self, doc, xhtmltree):
        # if SFS mode:
        # create a div for root content
        # find all headers, create div for everything there
        if doc.basefile.startswith("SFS/") or doc.basefile.startswith("SFS:"):
            self.postprocess_commentary(doc, xhtmltree)
            toplevel_property = False
        else:
            toplevel_property = True
        body = super(SFSMediaWiki, self).postprocess(doc, xhtmltree,
                                                     toplevel_property=toplevel_property)
        citparser = SwedishCitationParser(self.p, self.config.url)
        citparser.parse_recursive(body, predicate=None)
        return body
        
    def postprocess_commentary(self, doc, xhtmltree):
        uri = doc.uri
        body = xhtmltree.getchildren()[0]
        newbody = etree.Element("body")

        curruri = uri
        currdiv = etree.SubElement(newbody, "div")
        currdiv.set("about", curruri)
        currdiv.set("property", "dcterms:description")
        currdiv.set("datatype", "rdf:XMLLiteral")
        for child in body.getchildren():
            if child.tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
                # remove that <span> element that Semantics._h_el adds for us
                child.text = child[0].text
                child.remove(child[0])
                nodes = self.p.parse(child.text, curruri)
                curruri = nodes[0].uri
                # body.remove(child)
                newbody.append(child) 
                currdiv = etree.SubElement(newbody, "div")
                currdiv.set("about", curruri)
                currdiv.set("property", "dcterms:description")
                currdiv.set("datatype", "rdf:XMLLiteral")
            else:
                # body.remove(child)
                currdiv.append(child)
        xhtmltree.remove(body)
        xhtmltree.append(newbody)
        

class SFSSemantics(WikiSemantics):
    def internal_link(self, ast):
        el = super(SFSSemantics, self).internal_link(ast)
        return el


class SFSSettings(WikiSettings):
    def __init__(self, lang="en"):
        super(SFSSettings, self).__init__(lang)
        from ferenda.thirdparty.mw.settings import Namespace as MWNamespace
        template_ns = MWNamespace({"prefix": "template",
                                   "ident": 10,
                                   "name": {"en": "Template",
                                            "de": "Vorlage",
                                            "sv": "Mall"}})
        self.namespaces.add(MWNamespace({"prefix": "category",
                                         "ident": 14,
                                         "name": {"en": "Category",
                                                  "de": "Kategorie",
                                                  "sv": "Kategori"}}))
        self.namespaces.add(template_ns)
        self.namespaces.add(MWNamespace({"prefix": "user",
                                         "ident": 2,
                                         "name": {"en": "User",
                                                  "de": "Benutzer",
                                                  "sv": "Användare"}}))
        self.msgcat["toc"]["sv"] = "Innehåll"
        self.templates = {("template", "TranslatedAct"):
                          "\n<small>[{{{href}}} An unofficial translation of "
                          "{{{actname}}} is available from "
                          "{{{source}}}]</small>\n"}
        
    def make_url(self, name, **kwargs):
        # uri = super(SFSSettings, self).make_url(name, **kwargs)
        if name[1].startswith("SFS/"):
            uri = self.make_sfs_url(name[1][4:])
        else:
            if name[0].prefix == "user":
                uri = "https://lagen.nu/wiki/%s"% self.expand_page_name(*name)
            else:
                uri = self.make_keyword_url(name[1])
        return uri
        
#    def expand_page_name(self, namespace, pagename):
#        from pudb import set_trace; set_trace()
#        return super(SFSSettings, self).expand_page_name(namespace, pagename)
    
